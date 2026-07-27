#!/usr/bin/env python3
"""Build Odoo inventory adjustment template from consolidated data workbook."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sku_catalog import load_product_id_map, load_quants_product_id_map, norm_sku, resolve_product_id

DATA_PATH = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/"
    "data_para_darle_forma_como_plantilla_b695.xlsx"
)
OUT_PATH = Path("/workspace/output/Plantilla_Ajuste_Posproduccion.xlsx")
LOCATION = "TH/Posproducción"

COLS = ["product_id", "inventory_quantity", "location_id"]


def load_sources() -> list[pd.DataFrame]:
    chunks: list[pd.DataFrame] = []

    nm = pd.read_excel(DATA_PATH, sheet_name="SKU No Migrados")
    nm = nm.rename(
        columns={
            "Producto (Instancia Anterior)": "product_id_raw",
            "Cantidad": "qty",
        }
    )
    nm["source"] = "SKU No Migrados"
    nm["SKU"] = nm["SKU"].map(norm_sku)
    nm["product_id"] = nm["product_id_raw"].astype(str).str.strip()
    chunks.append(nm[["source", "SKU", "product_id", "qty"]])

    ent = pd.read_excel(DATA_PATH, sheet_name="ENTRADA LIMPIA")
    ent["source"] = "ENTRADA LIMPIA"
    ent["SKU"] = ent["SKU"].map(norm_sku)
    ent = ent.rename(columns={"CANT": "qty", "PRODUCTO": "fallback_name"})
    ent["product_id"] = None
    chunks.append(ent[["source", "SKU", "product_id", "qty", "fallback_name"]])

    lista = pd.read_excel(DATA_PATH, sheet_name="LISTA POR AJUSTE produccion ", header=2)
    lista = lista[lista["SKU"].notna()].copy()
    lista["source"] = "LISTA POR AJUSTE"
    lista["SKU"] = lista["SKU"].map(norm_sku)
    lista = lista.rename(columns={"Cantidad": "qty", "PRODUCTO CATALOGO": "fallback_name"})
    lista["product_id"] = None
    lista = (
        lista.groupby("SKU", as_index=False)
        .agg(qty=("qty", "sum"), fallback_name=("fallback_name", "first"))
    )
    lista["source"] = "LISTA POR AJUSTE"
    lista["product_id"] = None
    chunks.append(lista[["source", "SKU", "product_id", "qty", "fallback_name"]])

    return chunks


def enrich_product_ids(
    df: pd.DataFrame, pid_map: dict[str, str], quants_pid: dict[str, str]
) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        sku = norm_sku(r["SKU"])
        if sku in quants_pid:
            pid = quants_pid[sku]
            method = "quants_master"
        elif pd.notna(r.get("product_id")) and str(r["product_id"]).startswith("["):
            pid = str(r["product_id"]).strip()
            method = "provided"
        else:
            fb = r.get("fallback_name") if "fallback_name" in r.index else None
            fb = None if pd.isna(fb) else str(fb)
            pid, method = resolve_product_id(sku, pid_map, fb)
        rows.append({**r.to_dict(), "product_id": pid, "product_id_method": method})
    return pd.DataFrame(rows)


def to_plantilla(df: pd.DataFrame) -> pd.DataFrame:
    out = df[df["product_id"].notna()].copy()
    out = out.rename(columns={"qty": "inventory_quantity"})
    out["location_id"] = LOCATION
    out = out.sort_values("product_id", kind="stable")
    return out[COLS]


METHOD_PRIORITY = {
    "quants_master": 0,
    "provided": 1,
    "map": 2,
    "lookup_odoo": 3,
    "desc:MANUFACTURADO": 4,
    "desc:CLASFSKUSYSGRIETA": 5,
    "fallback_name": 9,
    "not_found": 99,
}


def canonical_product_ids(enriched: pd.DataFrame) -> pd.Series:
    """One product_id per SKU; prefer No Migrados / provided Odoo labels."""
    tmp = enriched[enriched["product_id"].notna()].copy()
    tmp["_pri"] = tmp["product_id_method"].map(lambda m: METHOD_PRIORITY.get(str(m), 50))
    tmp = tmp.sort_values(["SKU", "_pri"])
    return tmp.drop_duplicates(subset=["SKU"], keep="first").set_index("SKU")["product_id"]


def aggregate_consolidado(enriched: pd.DataFrame) -> pd.DataFrame:
    canon = canonical_product_ids(enriched)
    ok = enriched[enriched["SKU"].isin(canon.index)].copy()
    qty = ok.groupby("SKU", as_index=False)["inventory_quantity"].sum()
    qty["product_id"] = qty["SKU"].map(canon)
    qty["location_id"] = LOCATION
    qty = qty.sort_values("product_id", kind="stable")
    return qty[COLS]


def main() -> None:
    pid_map = load_product_id_map()
    quants_pid = load_quants_product_id_map()
    chunks = load_sources()

    detail_frames: list[pd.DataFrame] = []
    for raw in chunks:
        enriched = enrich_product_ids(raw, pid_map, quants_pid)
        plantilla = to_plantilla(enriched)
        plantilla["source"] = raw["source"].iloc[0]
        detail_frames.append(plantilla.assign(_sku=raw["SKU"].values))

    all_enriched = pd.concat(
        [enrich_product_ids(c, pid_map, quants_pid) for c in chunks], ignore_index=True
    )
    all_enriched["location_id"] = LOCATION
    all_enriched = all_enriched.rename(columns={"qty": "inventory_quantity"})

    consolidado = aggregate_consolidado(all_enriched)

    pendientes = all_enriched[all_enriched["product_id"].isna()][
        ["source", "SKU", "inventory_quantity", "fallback_name", "product_id_method"]
    ]

    sin_q5 = all_enriched[~all_enriched["SKU"].isin(quants_pid.keys())][
        ["source", "SKU", "product_id", "inventory_quantity", "product_id_method"]
    ].drop_duplicates(subset=["SKU"])

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
        # Main import sheet (like Plantilla Completa)
        consolidado.to_excel(writer, sheet_name="Carga Posproducción", index=False, startrow=0)

        for frame, name in zip(
            detail_frames,
            ["Detalle No Migrados", "Detalle Entrada", "Detalle Produccion"],
        ):
            frame[COLS].to_excel(writer, sheet_name=name, index=False)

        all_enriched[all_enriched["product_id"].notna()][
            ["source", "SKU", "product_id", "inventory_quantity", "location_id", "product_id_method"]
        ].to_excel(writer, sheet_name="Trazabilidad", index=False)

        if len(pendientes):
            pendientes.to_excel(writer, sheet_name="PENDIENTES product_id", index=False)

        if len(pendientes):
            pendientes.to_excel(writer, sheet_name="PENDIENTES product_id", index=False)
        if len(sin_q5):
            sin_q5.to_excel(writer, sheet_name="Sin referencia Quants 5", index=False)

    print(f"Output: {OUT_PATH}")
    print(f"Consolidado filas (unique SKU): {len(consolidado)}")
    print(f"Total qty consolidado: {consolidado['inventory_quantity'].sum()}")
    print(f"Pendientes product_id: {len(pendientes)}")
    print(f"SKUs sin Quants master: {sin_q5['SKU'].nunique() if len(sin_q5) else 0}")
    for i, frame in enumerate(detail_frames):
        print(f"  {frame['source'].iloc[0]}: {len(frame)} filas")


if __name__ == "__main__":
    main()
