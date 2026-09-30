#!/usr/bin/env python3
"""Compare data_para_chequeo.xlsx against Plantilla_Ajuste_Posproduccion.xlsx."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from match_sku_ajuste import load_catalog, load_urban_cotton_lookup, match_row, norm
from r1_quants6 import is_invalid_r1_catalog_sku, load_r1_quants6, resolve_r1_sku
from sku_catalog import norm_sku
from ventas_sku_map import apply_sku_remap, augment_r1_from_ventas

CHEQUEO_PATH = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/data_para_chequeo_dafc.xlsx"
)
PLANTILLA_PATH = Path("/workspace/output/Plantilla_Ajuste_Posproduccion.xlsx")
OUT_PATH = Path("/workspace/output/verificacion.xlsx")
LOCATION = "TH/Posproducción"

OK_MATCH = frozenset({"ok", "ok_urban_cotton", "ok_r1_quants6"})


def load_plantilla_by_sku() -> tuple[pd.DataFrame, pd.DataFrame]:
    tr = pd.read_excel(PLANTILLA_PATH, sheet_name="Trazabilidad")
    tr["SKU"] = tr["SKU"].map(norm_sku)
    by_sku = (
        tr.groupby("SKU", as_index=False)
        .agg(
            qty_plantilla=("inventory_quantity", "sum"),
            product_id=("product_id", "first"),
            sources=("source", lambda s: ", ".join(sorted(set(s.astype(str))))),
        )
    )
    by_source = tr.copy()
    return by_sku, by_source


def load_chequeo_no_migrados() -> pd.DataFrame:
    df = pd.read_excel(CHEQUEO_PATH, sheet_name="SKU No Migrados")
    df["SKU"] = df["SKU"].map(norm_sku)
    df["SKU_original"] = df["SKU"]
    df["source"] = "SKU No Migrados"
    df = df.rename(columns={"Cantidad": "qty_chequeo", "Producto (Instancia Anterior)": "referencia"})
    return df[["source", "SKU", "SKU_original", "qty_chequeo", "referencia"]]


def load_chequeo_entrada() -> pd.DataFrame:
    df = pd.read_excel(CHEQUEO_PATH, sheet_name="Hoja4", header=None, names=["SKU", "qty_chequeo", "nota"])
    df["SKU_original"] = df["SKU"].map(norm_sku)
    df["SKU"] = df["SKU_original"].map(lambda s: apply_sku_remap(s)[0])
    df["source"] = "Entrada almacén (Hoja4)"
    df["referencia"] = df["nota"]
    return df[["source", "SKU", "SKU_original", "qty_chequeo", "referencia"]]


def resolve_production_sku(row, catalog, urban, r1_skus, r1_index) -> tuple[str | None, str, str | None]:
    """Return (sku, status, sku_remap_from)."""
    mrow = {
        "Tipo de Producto": row["Tipo de Producto"],
        "Talla": row["Talla"],
        "GENERO": row["Genero"],
        "color": row["Color"],
    }
    sku, _prod, status = match_row(mrow, catalog, urban)
    sku_remap_from = None
    if sku:
        sku = norm_sku(sku)
        if is_invalid_r1_catalog_sku(sku) or norm(row["Tipo de Producto"]) == "R1":
            new_sku, _pid = resolve_r1_sku(
                sku,
                tipo_producto=row["Tipo de Producto"],
                talla=row["Talla"],
                color=row["Color"],
                fallback_name=f"SHORT SPORT R1 {'CAB' if norm(row['Genero']) in ('CABALLERO','CAB') else 'DAMA'}",
                r1_skus=r1_skus,
                r1_index=r1_index,
            )
            if new_sku != sku:
                sku_remap_from = sku
                sku = new_sku
        remapped, from_sk = apply_sku_remap(sku)
        if from_sk:
            sku_remap_from = from_sk
            sku = remapped
        return sku, status if status in OK_MATCH else "ok_resuelto", sku_remap_from

    if norm(row["Tipo de Producto"]) == "R1":
        new_sku, _pid = resolve_r1_sku(
            "",
            tipo_producto="R1",
            talla=row["Talla"],
            color=row["Color"],
            fallback_name=f"SHORT SPORT R1 {'CAB' if norm(row['Genero']) in ('CABALLERO','CAB') else 'DAMA'}",
            r1_skus=r1_skus,
            r1_index=r1_index,
        )
        if new_sku:
            return norm_sku(new_sku), "ok_r1_resolve", None
    return None, status, None


def load_chequeo_produccion(catalog, urban, r1_skus, r1_index) -> pd.DataFrame:
    df = pd.read_excel(CHEQUEO_PATH, sheet_name="Reporte Piezas de producccion", header=1)
    rows = []
    for i, row in df.iterrows():
        sku, status, remap_from = resolve_production_sku(row, catalog, urban, r1_skus, r1_index)
        rows.append(
            {
                "source": "Reporte Piezas producción",
                "fila_chequeo": i + 2,
                "Tipo de Producto": row["Tipo de Producto"],
                "Talla": row["Talla"],
                "Genero": row["Genero"],
                "Color": row["Color"],
                "qty_chequeo": row["Cantidad"],
                "SKU": sku,
                "match_status": status,
                "sku_remap_from": remap_from,
            }
        )
    return pd.DataFrame(rows)


def compare_lines(chequeo: pd.DataFrame, plantilla_by_sku: pd.DataFrame) -> pd.DataFrame:
    merged = chequeo.merge(plantilla_by_sku, on="SKU", how="left")
    merged["en_plantilla"] = merged["qty_plantilla"].notna()
    merged["qty_plantilla"] = merged["qty_plantilla"].fillna(0).astype(int)
    merged["qty_chequeo"] = merged["qty_chequeo"].astype(int)

    def estado(r) -> str:
        if not r["SKU"] or pd.isna(r["SKU"]):
            return "SIN SKU"
        if not r["en_plantilla"]:
            return "FALTA EN PLANTILLA"
        if r["qty_plantilla"] == r["qty_chequeo"]:
            return "OK cantidad exacta"
        if r["qty_plantilla"] >= r["qty_chequeo"]:
            return "OK (plantilla incluye más fuentes)"
        return "CANTIDAD MENOR EN PLANTILLA"

    merged["estado"] = merged.apply(estado, axis=1)
    merged["delta_qty"] = merged["qty_plantilla"] - merged["qty_chequeo"]
    return merged


def compare_by_source(
    chequeo_src: pd.DataFrame,
    plantilla_src: pd.DataFrame,
    source_name: str,
) -> pd.DataFrame:
    p = plantilla_src[plantilla_src["source"] == source_name].copy()
    p = p.groupby("SKU", as_index=False).agg(qty_plantilla=("inventory_quantity", "sum"), product_id=("product_id", "first"))
    c = chequeo_src.groupby("SKU", as_index=False).agg(
        qty_chequeo=("qty_chequeo", "sum"),
        sku_original=("SKU_original", "first") if "SKU_original" in chequeo_src.columns else ("SKU", "first"),
    )
    m = c.merge(p, on="SKU", how="outer", indicator=True)
    m["estado"] = "OK"
    m.loc[m["_merge"] == "left_only", "estado"] = "FALTA EN PLANTILLA"
    m.loc[m["_merge"] == "right_only", "estado"] = "SOLO EN PLANTILLA (fuente)"
    m["qty_chequeo"] = m["qty_chequeo"].fillna(0).astype(int)
    m["qty_plantilla"] = m["qty_plantilla"].fillna(0).astype(int)
    both = m["_merge"] == "both"
    m.loc[both & (m["qty_chequeo"] != m["qty_plantilla"]), "estado"] = "CANTIDAD DISTINTA"
    m = m.drop(columns=["_merge"])
    return m


def main() -> None:
    plantilla_by_sku, plantilla_src = load_plantilla_by_sku()
    carga = pd.read_excel(PLANTILLA_PATH, sheet_name="Carga Posproducción")
    carga["SKU"] = carga["product_id"].astype(str).str.extract(r"^\[([^\]]+)\]", expand=False).map(norm_sku)
    carga_qty = carga.groupby("SKU")["inventory_quantity"].sum()

    nm = load_chequeo_no_migrados()
    ent = load_chequeo_entrada()

    r1_skus, r1_index, _ = load_r1_quants6()
    augment_r1_from_ventas(r1_skus, r1_index, {})
    catalog = load_catalog()
    urban = load_urban_cotton_lookup()
    prod = load_chequeo_produccion(catalog, urban, r1_skus, r1_index)

    # Line-level compare (no migrados + entrada): qty should match same source in plantilla
    nm_cmp = compare_by_source(nm, plantilla_src, "SKU No Migrados")
    ent_cmp = compare_by_source(ent, plantilla_src, "ENTRADA LIMPIA")

    # Production: aggregate by SKU from chequeo report
    prod_ok = prod[prod["SKU"].notna()].copy()
    prod_agg = prod_ok.groupby("SKU", as_index=False).agg(qty_chequeo=("qty_chequeo", "sum"))
    prod_pl = plantilla_src[plantilla_src["source"] == "LISTA POR AJUSTE"].groupby("SKU", as_index=False).agg(
        qty_plantilla=("inventory_quantity", "sum"),
        product_id=("product_id", "first"),
    )
    prod_cmp = prod_agg.merge(prod_pl, on="SKU", how="left")
    prod_cmp["en_plantilla"] = prod_cmp["qty_plantilla"].notna()
    prod_cmp["qty_plantilla"] = prod_cmp["qty_plantilla"].fillna(0).astype(int)
    prod_cmp["estado"] = "OK"
    prod_cmp.loc[~prod_cmp["en_plantilla"], "estado"] = "FALTA EN PLANTILLA"
    prod_cmp.loc[
        prod_cmp["en_plantilla"] & (prod_cmp["qty_plantilla"] < prod_cmp["qty_chequeo"]),
        "estado",
    ] = "CANTIDAD MENOR EN PLANTILLA"
    prod_cmp.loc[
        prod_cmp["en_plantilla"] & (prod_cmp["qty_plantilla"] > prod_cmp["qty_chequeo"]),
        "estado",
    ] = "OK (plantilla incluye más líneas de producción)"

    prod_sin_sku = prod[prod["SKU"].isna()].copy()

    # Consolidado: all chequeo SKUs vs carga final
    parts = []
    for part in (nm, ent, prod_ok[["SKU", "qty_chequeo"]]):
        parts.append(part.assign(SKU=part["SKU"].map(norm_sku)))
    all_ch = pd.concat(parts, ignore_index=True)
    all_ch = all_ch[all_ch["SKU"].notna() & (all_ch["SKU"] != "")]
    cons_chequeo = all_ch.groupby("SKU", as_index=False).agg(qty_chequeo=("qty_chequeo", "sum"))
    cons = cons_chequeo.merge(plantilla_by_sku, on="SKU", how="left")
    cons["qty_plantilla"] = cons["qty_plantilla"].fillna(0).astype(int)
    cons["en_carga"] = cons["SKU"].map(lambda s: s in carga_qty.index)
    cons["qty_carga"] = cons["SKU"].map(lambda s: int(carga_qty.get(s, 0)))
    cons["estado"] = cons.apply(
        lambda r: "FALTA EN CARGA"
        if not r["en_carga"]
        else (
            "OK"
            if r["qty_carga"] >= r["qty_chequeo"]
            else "CANTIDAD MENOR EN CARGA"
        ),
        axis=1,
    )

    solo_plantilla = plantilla_by_sku[~plantilla_by_sku["SKU"].isin(cons_chequeo["SKU"])].copy()
    solo_plantilla["nota"] = "En plantilla pero no aparece en archivo de chequeo"

    resumen = pd.DataFrame(
        [
            {"concepto": "SKU No Migrados (filas)", "chequeo": len(nm), "ok": (nm_cmp["estado"] == "OK").sum()},
            {"concepto": "Entrada Hoja4 (filas)", "chequeo": len(ent), "ok": (ent_cmp["estado"] == "OK").sum()},
            {
                "concepto": "Reporte producción (filas)",
                "chequeo": len(prod),
                "ok": len(prod_ok),
            },
            {
                "concepto": "Producción sin SKU resuelto",
                "chequeo": len(prod_sin_sku),
                "ok": 0,
            },
            {
                "concepto": "Nota producción sin SKU",
                "chequeo": "SHORT SPORT KIDS talla 16 (2 filas)",
                "ok": "Revisar catálogo / Odoo",
            },
            {
                "concepto": "SKUs únicos chequeo (consolidado)",
                "chequeo": len(cons_chequeo),
                "ok": (cons["estado"] == "OK").sum(),
            },
            {
                "concepto": "Cantidad total chequeo",
                "chequeo": int(all_ch["qty_chequeo"].sum()),
                "ok": int(carga["inventory_quantity"].sum()),
            },
            {
                "concepto": "Filas carga plantilla",
                "chequeo": len(carga),
                "ok": len(carga),
            },
        ]
    )

    problemas = pd.concat(
        [
            nm_cmp[nm_cmp["estado"] != "OK"].assign(hoja="No Migrados"),
            ent_cmp[ent_cmp["estado"] != "OK"].assign(hoja="Entrada"),
            prod_cmp[prod_cmp["estado"].str.startswith("FALTA") | prod_cmp["estado"].str.contains("MENOR")].assign(
                hoja="Producción"
            ),
            cons[cons["estado"] != "OK"].assign(hoja="Consolidado carga"),
        ],
        ignore_index=True,
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
        resumen.to_excel(writer, sheet_name="Resumen", index=False)
        nm_cmp.to_excel(writer, sheet_name="No Migrados vs plantilla", index=False)
        ent_cmp.to_excel(writer, sheet_name="Entrada vs plantilla", index=False)
        prod.to_excel(writer, sheet_name="Produccion detalle", index=False)
        prod_cmp.to_excel(writer, sheet_name="Produccion SKU vs plantilla", index=False)
        cons.to_excel(writer, sheet_name="Consolidado chequeo vs carga", index=False)
        problemas.to_excel(writer, sheet_name="Pendientes revision", index=False)
        solo_plantilla.to_excel(writer, sheet_name="Solo en plantilla", index=False)
        if len(prod_sin_sku):
            prod_sin_sku.to_excel(writer, sheet_name="Produccion sin SKU", index=False)

    print(f"Output: {OUT_PATH}")
    print(resumen.to_string(index=False))
    print(f"Pendientes revision: {len(problemas)}")


if __name__ == "__main__":
    main()
