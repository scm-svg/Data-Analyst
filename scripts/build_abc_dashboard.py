#!/usr/bin/env python3
"""
Procesa ventas + inventario Odoo y genera abc_dashboard_data.json para el dashboard ABC.
Clasificación Pareto por margen de contribución (80 / 15 / 5).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_JSON = ROOT / "abc_dashboard_data.json"

MES_MAP = {
    "ENERO": 1,
    "FEBRERO": 2,
    "MARZO": 3,
    "ABRIL": 4,
    "MAYO": 5,
    "JUNIO": 6,
    "JULIO": 7,
    "AGOSTO": 8,
    "SEPTIEMBRE": 9,
    "OCTUBRE": 10,
    "NOVIEMBRE": 11,
    "DICIEMBRE": 12,
}

MES_LABEL = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

ABC_THRESHOLDS = {"A": 0.80, "B": 0.95}  # acumulado margen positivo


def load_sales() -> pd.DataFrame:
    path = DATA_DIR / "Ordenes_de_Ventas_Oct2025_COMPLETO.xlsx"
    df = pd.read_excel(path, sheet_name="VENTAS")
    df = df[df["SKU"].notna()].copy()
    df["SKU"] = df["SKU"].astype(str).str.strip()
    df["Mes"] = df["Mes"].astype(str).str.strip().str.upper()
    df["mnum"] = df["Mes"].map(MES_MAP)
    if df["mnum"].isna().any():
        bad = df.loc[df["mnum"].isna(), "Mes"].unique()
        raise ValueError(f"Meses no mapeados: {bad}")
    df["Año"] = df["Año"].astype(int)
    df["period"] = (
        df["Año"].astype(str)
        + "-"
        + df["mnum"].astype(int).astype(str).str.zfill(2)
    )
    df["tienda"] = df["tienda / ubicación"].fillna("SIN TIENDA").astype(str).str.strip()
    df["categoria"] = df["Categoría del producto"].fillna("Sin categoría").astype(str)
    df["producto"] = df["Producto"].fillna("").astype(str).str.strip()
    df["variante"] = df["Variante del producto"].fillna("").astype(str)
    df["genero"] = df["GENERO"].fillna("").astype(str)
    df["color"] = df["COLOR"].fillna("").astype(str)
    df["talla"] = df["TALLA"].fillna("").astype(str)
    df["qty"] = pd.to_numeric(df["Cant. ordenada"], errors="coerce").fillna(0)
    df["revenue"] = pd.to_numeric(df["TOTAL ($)"], errors="coerce").fillna(0)
    df["cost"] = pd.to_numeric(df["COSTO ($) TOTAL"], errors="coerce").fillna(0)
    df["margin"] = df["revenue"] - df["cost"]
    return df


def load_inventory() -> pd.DataFrame:
    path = DATA_DIR / "INVENTARIO_TALLER_TIENDAS_COMPLETO.xlsx"
    df = pd.read_excel(path, sheet_name="Inventario")
    df = df[df["SKU"].notna()].copy()
    df["SKU"] = df["SKU"].astype(str).str.strip()
    df["ubicacion"] = df["Ubicación"].fillna("SIN UBICACIÓN").astype(str).str.strip()
    df["modelo"] = df["MODELO"].fillna("").astype(str).str.strip()
    df["qty"] = pd.to_numeric(df["Cantidad en inventario"], errors="coerce").fillna(0)
    return df


def build_indexes(sales: pd.DataFrame, inv: pd.DataFrame) -> dict:
    periods = sorted(sales["period"].unique())
    period_meta = []
    for p in periods:
        y, m = p.split("-")
        mi = int(m)
        period_meta.append(
            {
                "key": p,
                "year": int(y),
                "month": mi,
                "label": f"{MES_LABEL[mi]} {y}",
                "short": f"{MES_LABEL[mi][:3]} {y[-2:]}",
            }
        )

    stores = sorted(sales["tienda"].unique())
    categories = sorted(sales["categoria"].unique())
    skus = sorted(set(sales["SKU"].unique()) | set(inv["SKU"].unique()))

    sku_master = {}
    sales_info = (
        sales.groupby("SKU")
        .agg(
            producto=("producto", "first"),
            categoria=("categoria", "first"),
            genero=("genero", "first"),
        )
        .to_dict("index")
    )
    inv_model = inv.groupby("SKU")["modelo"].first().to_dict()
    for sku in skus:
        info = sales_info.get(sku, {})
        sku_master[sku] = {
            "producto": info.get("producto") or inv_model.get(sku, sku),
            "categoria": info.get("categoria", "Sin ventas / solo stock"),
            "genero": info.get("genero", ""),
            "modelo": inv_model.get(sku) or info.get("producto") or sku,
        }

    sku_idx = {s: i for i, s in enumerate(skus)}
    store_idx = {s: i for i, s in enumerate(stores)}
    cat_idx = {c: i for i, c in enumerate(categories)}
    period_idx = {p["key"]: i for i, p in enumerate(period_meta)}

    # Filas compactas: [pi, si, ti, ci, qty, revenue, cost, margin]
    rows = []
    g = sales.groupby(
        ["period", "SKU", "tienda", "categoria"], as_index=False
    ).agg(qty=("qty", "sum"), revenue=("revenue", "sum"), cost=("cost", "sum"))
    g["margin"] = g["revenue"] - g["cost"]
    for _, r in g.iterrows():
        rows.append(
            [
                period_idx[r["period"]],
                sku_idx[r["SKU"]],
                store_idx[r["tienda"]],
                cat_idx[r["categoria"]],
                round(float(r["qty"]), 4),
                round(float(r["revenue"]), 4),
                round(float(r["cost"]), 4),
                round(float(r["margin"]), 4),
            ]
        )

    locations = sorted(inv["ubicacion"].unique())
    loc_idx = {l: i for i, l in enumerate(locations)}
    inv_rows = []
    inv_g = inv.groupby(["SKU", "ubicacion"], as_index=False)["qty"].sum()
    for _, r in inv_g.iterrows():
        if r["SKU"] not in sku_idx:
            continue
        inv_rows.append(
            [sku_idx[r["SKU"]], loc_idx[r["ubicacion"]], round(float(r["qty"]), 4)]
        )

    stats = {
        "lineas_ventas": int(len(sales)),
        "lineas_neg_qty": int((sales["qty"] < 0).sum()),
        "lineas_neg_revenue": int((sales["revenue"] < 0).sum()),
        "lineas_neg_margin": int((sales["margin"] < 0).sum()),
        "skus_unicos": len(skus),
        "periodos": len(periods),
        "rango": f"{period_meta[0]['label']} → {period_meta[-1]['label']}",
        "margen_neto_total": round(float(sales["margin"].sum()), 2),
        "ingresos_neto_total": round(float(sales["revenue"].sum()), 2),
    }

    return {
        "meta": {
            "generated": pd.Timestamp.now().isoformat(),
            "metric": "margen_contribucion",
            "abc_thresholds": ABC_THRESHOLDS,
            "premisas": {
                "A": {"margen_pct": 80, "sku_pct_objetivo": 20},
                "B": {"margen_pct": 15, "sku_pct_objetivo": 30},
                "C": {"margen_pct": 5, "sku_pct_objetivo": 50},
            },
            "notas": [
                "ABC por margen de contribución (TOTAL $ − COSTO TOTAL $), neto de devoluciones.",
                "Cantidades/importes negativos: devoluciones o notas; se incluyen en el neto del período.",
                "Clasificación Pareto: A ≤80% margen acumulado (positivo), B hasta 95%, resto C.",
                "SKUs sin margen positivo en el período filtrado se clasifican C.",
            ],
            "stats": stats,
        },
        "periods": period_meta,
        "stores": stores,
        "categories": categories,
        "locations": locations,
        "skus": skus,
        "skuMaster": sku_master,
        "salesRows": rows,
        "invRows": inv_rows,
    }


def build_standalone() -> None:
    html_path = ROOT / "abc_inventario_dashboard.html"
    out_path = ROOT / "abc_inventario_standalone.html"
    html = html_path.read_text(encoding="utf-8")
    data = OUT_JSON.read_text(encoding="utf-8")
    inject = f"<script>window.__ABC_DATA__={data};</script>\n"
    marker = '<script src="abc_dashboard.js"></script>'
    if marker not in html:
        raise RuntimeError("Marcador HTML no encontrado para standalone")
    standalone = html.replace(marker, marker + "\n" + inject)
    out_path.write_text(standalone, encoding="utf-8")
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"OK → {out_path} ({size_mb:.2f} MB)")


def main() -> None:
    sales = load_sales()
    inv = load_inventory()
    payload = build_indexes(sales, inv)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    size_mb = OUT_JSON.stat().st_size / (1024 * 1024)
    print(f"OK → {OUT_JSON} ({size_mb:.2f} MB)")
    print(json.dumps(payload["meta"]["stats"], indent=2, ensure_ascii=False))
    build_standalone()


if __name__ == "__main__":
    main()
