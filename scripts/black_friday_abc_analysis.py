#!/usr/bin/env python3
"""ABC + inventario/ventas · Propuesta Black Friday · Categoría C · Manufacturado · Equipamiento."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

INV_PATH = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/"
    "INVENTARIO_TOTAL_CUADRO_PARA_ABC_-_PROPUESTA_d5b9.xlsx"
)
SALES_PATH = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/"
    "VENTAS_CUADRO_ACTUALIZADAS_ARREGLADO_091c.xlsx"
)
OUT_XLSX = Path("/workspace/output/PROPUESTA_BLACK_FRIDAY_ABC_C_EQUIPAMIENTO.xlsx")
OUT_JSON = Path("/workspace/output/dashboard_bf_abc_data.json")
OUT_HTML = Path("/workspace/DASHBOARD_BLACK_FRIDAY_ABC_C_EQUIPAMIENTO.html")

# Marcas / líneas de terceros (no manufactura propia)
COMPRADO_PREFIXES = ("CONTIGO", "KAMBUKKA", "REFRESH ")

# Palabras clave equipamiento (accesorios / equipo)
EQUIP_PATTERNS = re.compile(
    r"(SOCKS|BACKPACK|BAG|CAP|HAT|TOALLA|LANYARD|BANDANA|HEADBAND|BUCKET|"
    r"VISERA|TOTE|DRY BAG|CAVAPACK|CITYBAG|MINI BAG|ECO BAG|PACKING|OVERGRIP|"
    r"PELOTAS|PROTECTOR|PORTAVASOS|LLAVERO|STICKER|PARCHES|CUADRO BAND|CUADRO TAG|"
    r"FLEX COVER|PONCHO|SUNNY CORD|ZENIT|MANGAS )",
    re.I,
)


def norm(s) -> str:
    if pd.isna(s):
        return ""
    return str(s).strip().upper()


def norm_talla(s) -> str:
    t = norm(s)
    if t in ("", "NAN", "NONE"):
        return "ÚNICA"
    if t in ("UNICA", "ÚNICA", "UNICO", "ÚNICO", "U"):
        return "ÚNICA"
    return t


def first_non_empty(series: pd.Series) -> str:
    for v in series:
        if norm(v):
            return norm(v)
    return ""


def classify_linea(modelo: str) -> str:
    m = norm(modelo)
    if any(m.startswith(p) or p in m for p in COMPRADO_PREFIXES):
        return "Comprado / terceros"
    if EQUIP_PATTERNS.search(m):
        return "Equipamiento"
    return "Confección (manufacturado)"


def abc_class(cum_pct: float) -> str:
    if cum_pct <= 80:
        return "A"
    if cum_pct <= 95:
        return "B"
    return "C"


def assign_abc(df: pd.DataFrame, group_col: str, value_col: str) -> pd.DataFrame:
    g = (
        df.groupby(group_col, as_index=False)[value_col]
        .sum()
        .sort_values(value_col, ascending=False)
    )
    total = g[value_col].sum()
    g["pct_ventas"] = (g[value_col] / total * 100).round(2) if total else 0
    g["cum_pct"] = g["pct_ventas"].cumsum().round(2)
    g["ABC"] = g["cum_pct"].apply(abc_class)
    return g


def suggest_discount(row) -> str:
    """Propuesta orientativa para directiva (C + stock)."""
    abc = row.get("ABC_MODELO", row.get("ABC", "C"))
    if abc != "C":
        return "—"
    inv = row.get("Inventario_Total", 0) or 0
    ventas = row.get("Ventas_Total", 0) or 0
    if inv <= 0:
        return "Sin stock"
    ratio = inv / max(ventas, 1)
    if ventas == 0 and inv >= 20:
        return "40–50% (liquidación)"
    if ratio >= 3:
        return "35–45%"
    if ratio >= 1.5:
        return "25–35%"
    if ratio >= 0.8:
        return "15–25%"
    return "10–20%"


def main():
    inv = pd.read_excel(INV_PATH)
    sales = pd.read_excel(SALES_PATH)

    inv["SKU"] = inv["SKU"].map(norm)
    inv["MODELO"] = inv["MODELO"].map(norm)
    inv["GENERO"] = inv["GENERO"].map(norm)
    inv["COLOR"] = inv["COLOR"].map(norm)
    inv["TALLA"] = inv["TALLA"].map(norm_talla)
    sales["SKU"] = sales["SKU"].map(norm)
    sales["modelo"] = sales["modelo"].map(norm)
    sales["GENERO"] = sales["GENERO"].map(norm)
    sales["COLOR"] = sales["COLOR"].map(norm)
    sales["TALLA"] = sales["TALLA"].map(norm_talla)

    inv_agg = (
        inv.groupby("SKU", as_index=False)
        .agg(
            Inventario_Total=("Cantidad en inventario", "sum"),
            MODELO_INV=("MODELO", first_non_empty),
            GENERO=("GENERO", first_non_empty),
            COLOR=("COLOR", first_non_empty),
            TALLA=("TALLA", first_non_empty),
        )
    )
    sales_agg = (
        sales.groupby("SKU", as_index=False)
        .agg(
            Ventas_Total=("Cant. ordenada", "sum"),
            MODELO_VTA=("modelo", first_non_empty),
            GENERO_VTA=("GENERO", first_non_empty),
            COLOR_VTA=("COLOR", first_non_empty),
            TALLA_VTA=("TALLA", first_non_empty),
        )
    )

    sku_master = pd.merge(inv_agg, sales_agg, on="SKU", how="outer")
    sku_master["Inventario_Total"] = sku_master["Inventario_Total"].fillna(0)
    sku_master["Ventas_Total"] = sku_master["Ventas_Total"].fillna(0)
    sku_master["MODELO"] = sku_master["MODELO_INV"].combine_first(
        sku_master["MODELO_VTA"]
    )
    for col, a, b in [
        ("GENERO", "GENERO", "GENERO_VTA"),
        ("COLOR", "COLOR", "COLOR_VTA"),
        ("TALLA", "TALLA", "TALLA_VTA"),
    ]:
        sku_master[col] = sku_master[a].combine_first(sku_master[b])
    sku_master.drop(
        columns=["MODELO_INV", "MODELO_VTA", "GENERO_VTA", "COLOR_VTA", "TALLA_VTA"],
        inplace=True,
    )

    sku_master["Inventario_Total"] = sku_master["Inventario_Total"].astype(int)
    sku_master["Ventas_Total"] = sku_master["Ventas_Total"].astype(int)
    sku_master["Linea_Negocio"] = sku_master["MODELO"].map(classify_linea)
    sku_master["Es_Manufacturado"] = sku_master["Linea_Negocio"].isin(
        ["Confección (manufacturado)", "Equipamiento"]
    )

    abc_sku = assign_abc(sku_master, "SKU", "Ventas_Total")
    sku_master = sku_master.merge(
        abc_sku[["SKU", "ABC", "pct_ventas", "cum_pct"]],
        on="SKU",
        how="left",
        suffixes=("", "_sku"),
    )
    sku_master.rename(columns={"ABC": "ABC_SKU"}, inplace=True)

    modelo_sales = (
        sku_master.groupby("MODELO", as_index=False)
        .agg(
            Ventas_Total=("Ventas_Total", "sum"),
            Inventario_Total=("Inventario_Total", "sum"),
            SKUs_Activos=("SKU", "nunique"),
        )
    )
    modelo_sales["Linea_Negocio"] = modelo_sales["MODELO"].map(classify_linea)
    modelo_sales["Es_Manufacturado"] = modelo_sales["Linea_Negocio"].isin(
        ["Confección (manufacturado)", "Equipamiento"]
    )

    abc_mod = assign_abc(modelo_sales, "MODELO", "Ventas_Total")
    modelo_sales = modelo_sales.merge(
        abc_mod[["MODELO", "ABC", "pct_ventas", "cum_pct"]],
        on="MODELO",
        how="left",
    )
    modelo_sales.rename(columns={"ABC": "ABC_MODELO"}, inplace=True)
    modelo_sales["Meses_Cobertura_Approx"] = (
        modelo_sales["Inventario_Total"]
        / modelo_sales["Ventas_Total"].replace(0, pd.NA)
    ).astype("Float64").round(1)
    modelo_sales["Propuesta_Descuento_BF"] = modelo_sales.apply(
        suggest_discount, axis=1
    )

    sku_master = sku_master.merge(
        modelo_sales[["MODELO", "ABC_MODELO"]], on="MODELO", how="left"
    )

    # Foco: C + manufacturado + equipamiento
    bf_modelos = modelo_sales[
        (modelo_sales["ABC_MODELO"] == "C")
        & (modelo_sales["Linea_Negocio"] == "Equipamiento")
        & (modelo_sales["Es_Manufacturado"])
    ].sort_values("Inventario_Total", ascending=False)

    bf_skus = sku_master[
        (sku_master["ABC_MODELO"] == "C")
        & (sku_master["Linea_Negocio"] == "Equipamiento")
        & (sku_master["Es_Manufacturado"])
        & (sku_master["Inventario_Total"] > 0)
    ].sort_values(["MODELO", "Inventario_Total"], ascending=[True, False])

    inv_by_store = (
        inv.groupby(["Ubicación", "MODELO"], as_index=False)["Cantidad en inventario"]
        .sum()
        .rename(columns={"Cantidad en inventario": "Inventario"})
    )

    sales_monthly = (
        sales.groupby(["Año", "Mes", "modelo"], as_index=False)["Cant. ordenada"]
        .sum()
        .rename(columns={"modelo": "MODELO", "Cant. ordenada": "Ventas"})
    )
    sales_monthly["MODELO"] = sales_monthly["MODELO"].map(norm)

    resumen = pd.DataFrame(
        {
            "Indicador": [
                "Unidades vendidas (total período)",
                "Unidades en inventario (total)",
                "SKUs únicos con stock o venta",
                "Modelos únicos",
                "Modelos ABC A (por ventas)",
                "Modelos ABC B",
                "Modelos ABC C",
                "Modelos C · Equipamiento · Manufacturado",
                "SKUs C · Equipamiento con stock",
                "Inventario C · Equipamiento (und)",
            ],
            "Valor": [
                int(sku_master["Ventas_Total"].sum()),
                int(sku_master["Inventario_Total"].sum()),
                sku_master["SKU"].nunique(),
                modelo_sales["MODELO"].nunique(),
                int((modelo_sales["ABC_MODELO"] == "A").sum()),
                int((modelo_sales["ABC_MODELO"] == "B").sum()),
                int((modelo_sales["ABC_MODELO"] == "C").sum()),
                len(bf_modelos),
                len(bf_skus),
                int(bf_skus["Inventario_Total"].sum()),
            ],
        }
    )

    metodo = pd.DataFrame(
        {
            "Tema": [
                "Fuente inventario",
                "Fuente ventas",
                "Nivel ABC principal",
                "Regla ABC",
                "Línea Equipamiento",
                "Manufacturado",
                "Propuesta descuento",
            ],
            "Detalle": [
                INV_PATH.name,
                SALES_PATH.name,
                "Modelo (MODELO) por unidades vendidas; ABC por SKU en hoja detalle",
                "Pareto clásico: A ≤80% acumulado, B 80–95%, C >95%",
                "Modelos cuyo nombre coincide con patrones de accesorios/equipo "
                "(gorras, bolsos, medias, toallas, etc.) excl. marcas terceros",
                "Confección propia + equipamiento propio; excluye Contigo, Kambukka, Refresh",
                "Rangos sugeridos según exceso de inventario vs ventas (revisión directiva)",
            ],
        }
    )

    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_XLSX, engine="xlsxwriter") as writer:
        resumen.to_excel(writer, sheet_name="00_RESUMEN", index=False)
        metodo.to_excel(writer, sheet_name="00_METODOLOGIA", index=False)
        modelo_sales.sort_values("Ventas_Total", ascending=False).to_excel(
            writer, sheet_name="ABC_MODELOS", index=False
        )
        bf_modelos.to_excel(
            writer, sheet_name="BF_LISTADO_C_EQUIP", index=False
        )
        bf_skus.to_excel(
            writer, sheet_name="BF_SKUS_C_EQUIP_STOCK", index=False
        )
        sku_master.sort_values("Ventas_Total", ascending=False).to_excel(
            writer, sheet_name="DETALLE_SKU", index=False
        )
        inv_by_store.to_excel(writer, sheet_name="INV_POR_TIENDA", index=False)

    # Dashboard JSON
    abc_counts = modelo_sales["ABC_MODELO"].value_counts().to_dict()
    linea_counts = modelo_sales.groupby("Linea_Negocio")["Inventario_Total"].sum().to_dict()

    top_bf = bf_modelos[
        [
            "MODELO",
            "Ventas_Total",
            "Inventario_Total",
            "Meses_Cobertura_Approx",
            "Propuesta_Descuento_BF",
            "pct_ventas",
            "cum_pct",
        ]
    ].to_dict(orient="records")

    equip_abc = (
        modelo_sales[modelo_sales["Linea_Negocio"] == "Equipamiento"]
        .groupby("ABC_MODELO")["Inventario_Total"]
        .sum()
        .to_dict()
    )

    months_equip = sales_monthly.copy()
    equip_models = set(
        modelo_sales[modelo_sales["Linea_Negocio"] == "Equipamiento"]["MODELO"]
    )
    months_equip = months_equip[months_equip["MODELO"].isin(equip_models)]
    trend = (
        months_equip.groupby(["Año", "Mes"], as_index=False)["Ventas"]
        .sum()
        .sort_values(["Año", "Mes"])
    )
    trend["periodo"] = trend["Año"].astype(str) + "-" + trend["Mes"].astype(str)

    payload = {
        "resumen": dict(zip(resumen["Indicador"], resumen["Valor"])),
        "abc_modelos": abc_counts,
        "inventario_por_linea": linea_counts,
        "inventario_equip_abc": equip_abc,
        "top_bf_c_equip": top_bf,
        "trend_equip": trend[["periodo", "Ventas"]].to_dict(orient="records"),
        "bf_modelos_count": len(bf_modelos),
        "bf_inv_units": int(bf_skus["Inventario_Total"].sum()),
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    if OUT_HTML.exists():
        html = OUT_HTML.read_text(encoding="utf-8")
        blob = json.dumps(payload, ensure_ascii=False)
        marker = "const DATA = "
        i = html.find(marker)
        if i >= 0:
            j = html.find(";", i)
            html = html[: i + len(marker)] + blob + html[j:]
            OUT_HTML.write_text(html, encoding="utf-8")

    print("Wrote", OUT_XLSX)
    print("Wrote", OUT_JSON)
    print("BF modelos C equip:", len(bf_modelos))
    print(bf_modelos[["MODELO", "Ventas_Total", "Inventario_Total"]].head(20).to_string())


if __name__ == "__main__":
    main()
