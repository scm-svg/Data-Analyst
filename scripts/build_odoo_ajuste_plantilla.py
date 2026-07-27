#!/usr/bin/env python3
"""Build Odoo inventory adjustment template from consolidated data workbook."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from r1_quants6 import (
    INVALID_R1_SKU_PREFIXES,
    is_invalid_r1_catalog_sku,
    load_r1_quants6,
    resolve_r1_sku,
)
from sku_catalog import load_product_id_map, load_quants_product_id_map, norm_sku, resolve_product_id
from ventas_sku_map import (
    apply_sku_remap,
    augment_r1_from_ventas,
    audit_ventas_coverage,
    load_ventas_product_id_map,
    validate_product_ids,
)

DATA_PATH = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/"
    "data_para_darle_forma_como_plantilla_b695.xlsx"
)
OUT_PATH = Path("/workspace/output/Plantilla_Ajuste_Posproduccion.xlsx")
LOCATION = "TH/Posproducción"

COLS = ["product_id", "inventory_quantity", "location_id"]


def load_sources(r1_skus: set[str], r1_index: dict, r1_pid: dict[str, str]) -> tuple[list[pd.DataFrame], pd.DataFrame]:
    chunks: list[pd.DataFrame] = []
    r1_unresolved_parts: list[pd.DataFrame] = []

    nm = pd.read_excel(DATA_PATH, sheet_name="SKU No Migrados")
    nm = nm.rename(
        columns={
            "Producto (Instancia Anterior)": "product_id_raw",
            "Cantidad": "qty",
        }
    )
    nm["source"] = "SKU No Migrados"
    nm["SKU"] = nm["SKU"].map(lambda s: apply_sku_remap(s)[0])
    nm["product_id"] = nm["product_id_raw"].astype(str).str.strip()
    chunks.append(nm[["source", "SKU", "product_id", "qty"]])

    ent = pd.read_excel(DATA_PATH, sheet_name="ENTRADA LIMPIA")
    ent["source"] = "ENTRADA LIMPIA"
    ent["SKU"] = ent["SKU"].map(lambda s: apply_sku_remap(s)[0])
    ent = ent.rename(columns={"CANT": "qty", "PRODUCTO": "fallback_name"})
    ent["product_id"] = None
    chunks.append(ent[["source", "SKU", "product_id", "qty", "fallback_name"]])

    lista = pd.read_excel(DATA_PATH, sheet_name="LISTA POR AJUSTE produccion ", header=2)
    lista = lista[lista["SKU"].notna()].copy()
    remapped_rows: list[dict] = []
    for _, row in lista.iterrows():
        sku_after_remap, sku_remap_from = apply_sku_remap(row["SKU"])
        new_sku, r1_pid_row = resolve_r1_sku(
            sku_after_remap,
            tipo_producto=row.get("Tipo de Producto"),
            talla=row.get("Talla"),
            color=row.get("color"),
            fallback_name=row.get("PRODUCTO CATALOGO"),
            r1_skus=r1_skus,
            r1_index=r1_index,
        )
        remapped_rows.append(
            {
                "source": "LISTA POR AJUSTE",
                "SKU": new_sku,
                "qty": row["Cantidad"],
                "fallback_name": row.get("PRODUCTO CATALOGO"),
                "product_id": r1_pid_row or (r1_pid.get(new_sku) if new_sku in r1_pid else None),
                "sku_remap_from": sku_remap_from
                or (norm_sku(row["SKU"]) if new_sku != norm_sku(row["SKU"]) else None),
                "r1_unresolved": is_invalid_r1_catalog_sku(row["SKU"])
                and new_sku == norm_sku(row["SKU"]),
                "Tipo de Producto": row.get("Tipo de Producto"),
                "Talla": row.get("Talla"),
                "color": row.get("color"),
                "SKU_original": norm_sku(row["SKU"]),
            }
        )
    lista = pd.DataFrame(remapped_rows)
    bad = lista[lista["r1_unresolved"]].copy()
    if len(bad):
        r1_unresolved_parts.append(
            bad[
                [
                    "SKU_original",
                    "Tipo de Producto",
                    "Talla",
                    "color",
                    "fallback_name",
                    "qty",
                ]
            ].rename(columns={"SKU_original": "SKU", "qty": "Cantidad"})
        )
    lista = lista[~lista["r1_unresolved"]].drop(
        columns=["r1_unresolved", "Tipo de Producto", "Talla", "color", "SKU_original"],
        errors="ignore",
    )
    lista = (
        lista.groupby("SKU", as_index=False)
        .agg(
            qty=("qty", "sum"),
            fallback_name=("fallback_name", "first"),
            product_id=("product_id", "first"),
            sku_remap_from=("sku_remap_from", "first"),
        )
        .assign(source="LISTA POR AJUSTE")
    )
    chunks.append(lista)

    return chunks, pd.concat(r1_unresolved_parts, ignore_index=True) if r1_unresolved_parts else pd.DataFrame()


def enrich_product_ids(
    df: pd.DataFrame,
    pid_map: dict[str, str],
    quants_pid: dict[str, str],
    ventas_pid: dict[str, str],
) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        sku = norm_sku(r["SKU"])
        preset = r.get("product_id")
        if sku in ventas_pid:
            pid = ventas_pid[sku]
            method = "ventas_master"
        elif pd.notna(preset) and str(preset).startswith("["):
            pid = str(preset).strip()
            method = "r1_quants6" if r.get("sku_remap_from") else "provided"
        elif sku in quants_pid:
            pid = quants_pid[sku]
            method = "quants_master"
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
    "ventas_master": -1,
    "quants_master": 0,
    "r1_quants6": 0,
    "provided": 1,
    "map": 2,
    "lookup_odoo": 3,
    "desc:MANUFACTURADO": 4,
    "desc:CLASFSKUSYSGRIETA": 5,
    "fallback_name": 9,
    "not_found": 99,
}


def canonical_product_ids(enriched: pd.DataFrame) -> pd.Series:
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


def validate_no_invented_r1(consolidado: pd.DataFrame) -> pd.DataFrame:
    import re

    bad = []
    for _, r in consolidado.iterrows():
        m = re.match(r"^\[([^\]]+)\]", str(r["product_id"]))
        sku = m.group(1).upper() if m else ""
        if is_invalid_r1_catalog_sku(sku):
            bad.append(r)
    return pd.DataFrame(bad)


def main() -> None:
    r1_skus, r1_index, r1_pid = load_r1_quants6()
    augment_r1_from_ventas(r1_skus, r1_index, r1_pid)
    ventas_pid = load_ventas_product_id_map()
    pid_map = load_product_id_map()
    pid_map.update(ventas_pid)
    quants_pid = load_quants_product_id_map()
    quants_pid.update(r1_pid)

    chunks, r1_unresolved = load_sources(r1_skus, r1_index, r1_pid)

    detail_frames: list[pd.DataFrame] = []
    for raw in chunks:
        enriched = enrich_product_ids(raw, pid_map, quants_pid, ventas_pid)
        plantilla = to_plantilla(enriched)
        plantilla["source"] = raw["source"].iloc[0]
        detail_frames.append(plantilla)

    all_enriched = pd.concat(
        [enrich_product_ids(c, pid_map, quants_pid, ventas_pid) for c in chunks],
        ignore_index=True,
    )
    all_enriched["location_id"] = LOCATION
    all_enriched = all_enriched.rename(columns={"qty": "inventory_quantity"})

    consolidado = aggregate_consolidado(all_enriched)
    invalid_r1 = validate_no_invented_r1(consolidado)

    remaps = pd.DataFrame()
    if "sku_remap_from" in all_enriched.columns:
        remaps = all_enriched[all_enriched["sku_remap_from"].notna()][
            ["source", "sku_remap_from", "SKU", "product_id", "inventory_quantity"]
        ].drop_duplicates(subset=["sku_remap_from", "SKU"])

    pendientes = all_enriched[all_enriched["product_id"].isna()][
        ["source", "SKU", "inventory_quantity", "fallback_name", "product_id_method"]
    ]

    sin_q5 = all_enriched[~all_enriched["SKU"].isin(quants_pid.keys())][
        ["source", "SKU", "product_id", "inventory_quantity", "product_id_method"]
    ].drop_duplicates(subset=["SKU"])

    sku_from_pid = consolidado["product_id"].str.extract(
        r"^\[([^\]]+)\]", expand=False
    ).map(norm_sku)
    validacion = validate_product_ids(
        pd.DataFrame(
            {
                "SKU": sku_from_pid,
                "product_id": consolidado["product_id"],
                "inventory_quantity": consolidado["inventory_quantity"],
            }
        ),
        ventas_pid,
    )
    audit_ventas = audit_ventas_coverage(all_enriched, ventas_pid)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
        consolidado.to_excel(writer, sheet_name="Carga Posproducción", index=False, startrow=0)

        for frame, name in zip(
            detail_frames,
            ["Detalle No Migrados", "Detalle Entrada", "Detalle Produccion"],
        ):
            frame[COLS].to_excel(writer, sheet_name=name, index=False)

        all_enriched[all_enriched["product_id"].notna()][
            ["source", "SKU", "product_id", "inventory_quantity", "location_id", "product_id_method"]
        ].to_excel(writer, sheet_name="Trazabilidad", index=False)

        if len(remaps):
            remaps.to_excel(writer, sheet_name="R1 SKU corregidos Q6", index=False)
        if len(pendientes):
            pendientes.to_excel(writer, sheet_name="PENDIENTES product_id", index=False)
        if len(sin_q5):
            sin_q5.to_excel(writer, sheet_name="Sin referencia Quants 5", index=False)
        if len(invalid_r1):
            invalid_r1.to_excel(writer, sheet_name="ERROR SKU R1 invalidos", index=False)
        if len(r1_unresolved):
            r1_unresolved.to_excel(writer, sheet_name="R1 sin match Quants 6", index=False)
        if len(validacion):
            validacion.to_excel(writer, sheet_name="Validacion vs Ventas", index=False)
        if len(audit_ventas):
            audit_ventas.to_excel(writer, sheet_name="Etiquetas distintas ventas", index=False)

    print(f"Output: {OUT_PATH}")
    print(f"Consolidado filas (unique SKU): {len(consolidado)}")
    print(f"Total qty consolidado: {consolidado['inventory_quantity'].sum()}")
    print(f"R1 remaps: {len(remaps)}")
    print(f"Invalid R1 catalog SKUs remaining: {len(invalid_r1)}")
    print(f"R1 sin match Quants 6: {len(r1_unresolved)}")
    print(f"Pendientes product_id: {len(pendientes)}")
    print(f"Validacion vs Ventas (mismatches): {len(validacion)}")
    print(f"Etiquetas distintas ventas (trazabilidad): {len(audit_ventas)}")
    if len(invalid_r1):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
