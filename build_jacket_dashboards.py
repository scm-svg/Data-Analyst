#!/usr/bin/env python3
"""Build Jacket 2.0 and Jacket 1.0 dashboards from Excel sales data."""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

EXCEL_PATH = Path("/home/ubuntu/.cursor/projects/workspace/uploads/ventas_cuadro_jacket_actualizadas_c8db.xlsx")
TEMPLATE_20_PATH = Path("/home/ubuntu/.cursor/projects/workspace/uploads/index__28__1673.html")
OUT_20_PATH = Path("/workspace/Dashboard_Jacket_2_0.html")
OUT_10_PATH = Path("/workspace/Dashboard_Jacket_1_0.html")

MES_NUM = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
MES_SHORT = {
    "enero": "Ene", "febrero": "Feb", "marzo": "Mar", "abril": "Abr", "mayo": "May",
    "junio": "Jun", "julio": "Jul", "agosto": "Ago", "septiembre": "Sep",
    "octubre": "Oct", "noviembre": "Nov", "diciembre": "Dic",
}
MES_MAP = {
    "ENERO": "enero", "FEBRERO": "febrero", "MARZO": "marzo", "ABRIL": "abril",
    "MAYO": "mayo", "JUNIO": "junio", "JULIO": "julio", "AGOSTO": "agosto",
    "SEPTIEMBRE": "septiembre", "OCTUBRE": "octubre", "NOVIEMBRE": "noviembre", "DICIEMBRE": "diciembre",
}
STORE_MAP = {
    "CERRO VERDE": "CERRO VERDE", "Cerro Verde ": "CERRO VERDE", "Cerro Verde": "CERRO VERDE",
    "GRAND PLAZ": "GRAND PLAZ", "Grandplaz ": "GRAND PLAZ", "Grandplaz": "GRAND PLAZ",
    "GRIETA": "GRIETA", "La Grieta": "GRIETA", "GRIE": "GRIETA",
    "CHACAO": "CHACAO", "SAMBIL CHACAO": "CHACAO", "Sambil Chacao ": "CHACAO", "Sambil Chacao": "CHACAO",
    "SAMBIL": "SAMBIL", "SAMBIL VALENCIA": "SAMBIL", "Sambil Valencia": "SAMBIL",
    "TOLON": "TOLON", "Tolon": "TOLON",
    "PEDIDOS": "PEDIDOS", "Pedidos": "PEDIDOS",
    "LA VELA": "LA VELA", "La Vela": "LA VELA",
    "WEB": "WEB", "CORPORATIVO": "CORPORATIVO",
}
COLOR_MAP = {
    "NEGRO": "Negro", "BLANCO": "Blanco", "AGUAMARINA": "Aguamarina",
    "VERDE MILITAR": "Verde Militar", "AZUL POLO": "Azul Polo", "MAGENTA": "Magenta",
    "PINK": "Pink", "AZUL MARINO": "Azul Marino", "AZUL TURQUESA": "Azul Turquesa",
    "KAKI": "Kaki", "LILA": "Lila", "VERDE NEON": "Verde Neon", "VINOTINTO": "Vinotinto",
}
CUADRO_PRODUCTS = {
    "CUADRO JACKET 2.0", "CUADRO JACKET 2.0 CAB", "CUADRO JACKET 2.0 DAMA", "CUADRO JACKET 2.0 KIDS",
}
JACKET10_PRODUCTS = {"JACKET CAB", "JACKET DAMA", "JACKET KIDS", "JACKET"}
COVER_MONTHS = 9
LEAD_MONTHS = 3
REAL_STORES = ["CERRO VERDE", "CHACAO", "GRAND PLAZ", "GRIETA", "SAMBIL", "TOLON", "LA VELA"]
# Tiendas excluidas del dashboard 2.0 (pedidos corporativos / no retail)
EXCLUDE_STORES_20 = {"PEDIDOS"}


def norm_store(s: str) -> str:
    s = str(s).strip()
    return STORE_MAP.get(s, STORE_MAP.get(s.upper(), s.upper()))


def norm_color(c: str) -> str:
    c = str(c).strip()
    if c.upper() in COLOR_MAP:
        return COLOR_MAP[c.upper()]
    if c.isupper():
        return c.title()
    return c


def norm_mes(row) -> str:
    m = str(row["Mes"]).strip().upper()
    m = MES_MAP.get(m, m.lower())
    return f"{m}-{int(row['Año'])}"


def mes_sort_key(mes_key: str) -> tuple:
    parts = mes_key.split("-")
    return (int(parts[1]), MES_NUM.get(parts[0], 99))


def mes_label(mes_key: str) -> str:
    parts = mes_key.split("-")
    return f"{MES_SHORT.get(parts[0], parts[0][:3].title())} {parts[1][-2:]}"


def period_label(meses: list[str]) -> str:
    if not meses:
        return ""
    return f"{mes_label(meses[0])} — {mes_label(meses[-1])}"


def load_existing_stock() -> dict:
    content = TEMPLATE_20_PATH.read_text(encoding="utf-8")
    match = re.search(r"var DATA=(\{.*?\});", content, re.DOTALL)
    if not match:
        return {}
    data = json.loads(match.group(1))
    return data.get("stock", {})


def build_raw_rows(df: pd.DataFrame, modelo_fn) -> list[dict]:
    rows = []
    grouped = df.groupby(
        ["store_norm", "GENERO", "color_norm", "TALLA", "mes_key", "Producto"],
        as_index=False,
    )["Cant. ordenada"].sum()
    for _, r in grouped.iterrows():
        modelo = modelo_fn(r["Producto"])
        if not modelo:
            continue
        rows.append({
            "tienda": r["store_norm"],
            "genero": r["GENERO"],
            "color": r["color_norm"],
            "talla": str(r["TALLA"]),
            "mes": r["mes_key"],
            "modelo": modelo,
            "v": int(r["Cant. ordenada"]),
        })
    return rows


def compute_meses(raw_rows: list[dict], es_parcial: bool) -> tuple[list[str], dict[str, int], bool]:
    meses_und = defaultdict(int)
    for r in raw_rows:
        meses_und[r["mes"]] += r["v"]
    meses_order = sorted(meses_und.keys(), key=mes_sort_key)
    return meses_order, dict(meses_und), es_parcial


def complete_months(meses_order: list[str], es_parcial: bool) -> list[str]:
    if es_parcial and len(meses_order) > 1:
        return meses_order[:-1]
    return meses_order


def monthly_velocity(raw_rows, genero, color, talla, modelo, months, n_months=3):
    use_months = months[-n_months:] if len(months) >= n_months else months
    if not use_months:
        return 0.0
    total = sum(
        r["v"] for r in raw_rows
        if r["genero"] == genero and r["color"] == color and r["talla"] == talla
        and r["modelo"] == modelo and r["mes"] in use_months
    )
    return round(total / len(use_months), 1)


def get_stock(stock: dict, modelo, genero, color, talla):
    return stock.get(f"{modelo}/{genero}/{color}/{talla}", 0)


def get_color_stock(stock: dict, modelo, genero, color):
    prefix = f"{modelo}/{genero}/{color}/"
    return sum(v for k, v in stock.items() if k.startswith(prefix))


def build_purchase_plan(raw_rows, stock, modelos, meses_order, es_parcial):
    months = complete_months(meses_order, es_parcial)
    plan = []
    summary = {}
    for genero in sorted({r["genero"] for r in raw_rows}):
        g_rows = [r for r in raw_rows if r["genero"] == genero]
        colors = sorted({r["color"] for r in g_rows})
        g_v_mes = 0.0
        g_stk = 0
        g_buy = 0
        for color in colors:
            tallas = sorted({r["talla"] for r in g_rows if r["color"] == color})
            c_v_mes = 0.0
            c_stk = 0
            c_buy = 0
            talla_rows = []
            for talla in tallas:
                v_mes = 0.0
                for modelo in modelos:
                    v_mes += monthly_velocity(raw_rows, genero, color, talla, modelo, months)
                stk = sum(get_stock(stock, m, genero, color, talla) for m in modelos)
                stk_taller = stk
                cob = round(stk / v_mes, 1) if v_mes > 0 else 999
                need = max(0, round(v_mes * COVER_MONTHS - stk))
                talla_rows.append({
                    "talla": talla, "v_mes": v_mes, "stk": stk, "stk_taller": stk_taller,
                    "cob": cob, "buy": need, "urgente": cob < 3,
                })
                c_v_mes += v_mes
                c_stk += stk
                c_buy += need
            c_cob = round(c_stk / c_v_mes, 1) if c_v_mes > 0 else 999
            plan.append({
                "genero": genero, "color": color, "v_mes": round(c_v_mes, 1),
                "stk": c_stk, "stk_taller": c_stk, "cob": c_cob,
                "buy": c_buy, "tallas": talla_rows,
            })
            g_v_mes += c_v_mes
            g_stk += c_stk
            g_buy += c_buy
        g_cob = round(g_stk / g_v_mes, 1) if g_v_mes > 0 else 999
        summary[genero] = {
            "v_mes": round(g_v_mes, 1), "stk": g_stk, "cob": g_cob,
            "buy": g_buy, "stk_taller": g_stk,
        }
    return plan, summary


def build_new_store_projection(raw_rows, base_store, mult, modelos, meses_order, es_parcial, note):
    months = complete_months(meses_order, es_parcial)
    base_rows = [r for r in raw_rows if r["tienda"] == base_store and r["mes"] in months]
    base_total = sum(r["v"] for r in base_rows) or 1
    skus = []
    combos = sorted({(r["genero"], r["color"], r["talla"]) for r in raw_rows})
    v_mes_total = 0.0
    for genero, color, talla in combos:
        v = 0.0
        for modelo in modelos:
            v += monthly_velocity(raw_rows, genero, color, talla, modelo, months)
        v = round(v * mult, 1)
        if v <= 0:
            continue
        v_mes_total += v
        skus.append({
            "Genero": genero, "Color": color, "Talla": talla,
            "v_mes": v,
            "need_1m": max(1, round(v * 1)),
            "need_2m": max(1, round(v * 2)),
            "need_3m": max(1, round(v * 3)),
        })
    return {
        "v_mes": round(v_mes_total, 1),
        "need_1m": sum(s["need_1m"] for s in skus),
        "need_2m": sum(s["need_2m"] for s in skus),
        "need_3m": sum(s["need_3m"] for s in skus),
        "nota": note,
        "skus": skus,
    }


def build_data(raw_rows, modelos, stock=None, es_parcial=False):
    stock = stock or {}
    meses_order, meses_und, es_parcial = compute_meses(raw_rows, es_parcial)
    tiendas = sorted({r["tienda"] for r in raw_rows})
    generos = sorted({r["genero"] for r in raw_rows})
    colores = sorted({r["color"] for r in raw_rows})
    total = sum(r["v"] for r in raw_rows)
    stock_total = sum(stock.values())
    purchase_plan, summary_compra = build_purchase_plan(raw_rows, stock, modelos, meses_order, es_parcial)
    stock_by_modelo = {m: sum(v for k, v in stock.items() if k.startswith(m + "/")) for m in modelos}
    all_stores = [s for s in REAL_STORES if s in tiendas] + [s for s in tiendas if s not in REAL_STORES and s not in ("WEB", "CORPORATIVO")]
    return {
        "raw_rows": raw_rows,
        "stock": stock,
        "stock_by_modelo": stock_by_modelo,
        "meses_order": meses_order,
        "meses_und": meses_und,
        "filtros": {"tiendas": tiendas, "generos": generos, "colores": colores, "modelos": modelos},
        "es_parcial": es_parcial,
        "stock_total": stock_total,
        "stock_taller": stock_total,
        "total": total,
        "all_stores": all_stores,
        "purchase_plan": purchase_plan,
        "summary_compra": summary_compra,
        "margarita": build_new_store_projection(
            raw_rows, "GRIETA", 1, modelos, meses_order, es_parcial,
            "1× velocidad GRIETA (tienda nueva)",
        ),
        "tolon": build_new_store_projection(
            raw_rows, "TOLON", 1, modelos, meses_order, es_parcial,
            "Basado en ventas reales TOLON",
        ),
        "cover_months": COVER_MONTHS,
        "lead_months": LEAD_MONTHS,
    }


def replace_data_in_html(template: str, data: dict) -> str:
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ": "))
    return re.sub(r"var DATA=\{.*?\};", f"var DATA={data_json};", template, count=1, flags=re.DOTALL)


def patch_20_html(html: str, period: str, partial_msg: str) -> str:
    html = html.replace("<p>Dashboard de Ventas · Dic 2025 — May 2026</p>", f"<p>Dashboard de Ventas · {period}</p>")
    html = html.replace("Jacket 2.0 · Dashboard de Ventas · Dic 2025 — May 2026", f"Jacket 2.0 · Dashboard de Ventas · {period}")
    html = html.replace("'📅 Mayo 2026 con datos parciales'", f"'📅 {partial_msg}'")
    return html


def build_10_html(template: str, data: dict, period: str, partial_msg: str) -> str:
    html = template
    html = html.replace("<title>Dashboard Jacket 2.0</title>", "<title>Dashboard Jacket 1.0</title>")
    html = html.replace("<h1>Jacket 2.0 · <em id=\"titleModelo\">Cuadro</em></h1>", "<h1>Jacket 1.0 · <em id=\"titleModelo\">Global</em></h1>")
    html = html.replace("<p>Dashboard de Ventas · Dic 2025 — May 2026</p>", f"<p>Dashboard de Ventas · {period}</p>")
    html = html.replace(
        '<div class="mbar"><span class="mbar-lbl">🧥 Modelo:</span><button class="mbtn active" data-m="" onclick="setModelo(\'\')">🧥 Cuadro Jacket 2.0 <span class="mcnt" id="mcnt_all">0</span></button></div>',
        '<div class="mbar"><span class="mbar-lbl">🧥 Modelo:</span>'
        '<button class="mbtn active" data-m="" onclick="setModelo(\'\')">🧥 Todos <span class="mcnt" id="mcnt_all">0</span></button>'
        '<button class="mbtn" data-m="JACKET CAB" onclick="setModelo(\'JACKET CAB\')">👔 Jacket CAB <span class="mcnt" id="mcnt_JACKET_CAB">0</span></button>'
        '<button class="mbtn" data-m="JACKET DAMA" onclick="setModelo(\'JACKET DAMA\')">👗 Jacket DAMA <span class="mcnt" id="mcnt_JACKET_DAMA">0</span></button>'
        '<button class="mbtn" data-m="JACKET KIDS" onclick="setModelo(\'JACKET KIDS\')">👶 Jacket KIDS <span class="mcnt" id="mcnt_JACKET_KIDS">0</span></button>'
        '<button class="mbtn" data-m="JACKET" onclick="setModelo(\'JACKET\')">🧥 Jacket <span class="mcnt" id="mcnt_JACKET">0</span></button>'
        '</div>',
    )
    html = html.replace("Jacket 2.0 · Dashboard de Ventas · Dic 2025 — May 2026", f"Jacket 1.0 · Dashboard de Ventas · {period}")
    html = html.replace("var MICO={'CUADRO JACKET 2.0':'🧥'};", "var MICO={'JACKET CAB':'👔','JACKET DAMA':'👗','JACKET KIDS':'👶','JACKET':'🧥'};")
    html = html.replace(
        "var MODELO_ID={'CUADRO JACKET 2.0':'CUADRO_JACKET_2_0'};",
        "var MODELO_ID={'JACKET CAB':'JACKET_CAB','JACKET DAMA':'JACKET_DAMA','JACKET KIDS':'JACKET_KIDS','JACKET':'JACKET'};",
    )
    html = html.replace(
        "if(titleEl){var sn={'CUADRO JACKET 2.0':'Cuadro'};titleEl.textContent='Cuadro';}",
        "if(titleEl){var sn={'JACKET CAB':'CAB','JACKET DAMA':'DAMA','JACKET KIDS':'KIDS','JACKET':'Jacket'};titleEl.textContent=m?sn[m]||m:'Global';}",
    )
    html = html.replace("a.download='Jacket_2_0.csv'", "a.download='Jacket_1_0.csv'")
    html = html.replace("'📅 Mayo 2026 con datos parciales'", f"'📅 {partial_msg}'")
    return replace_data_in_html(html, data)


def main():
    df = pd.read_excel(EXCEL_PATH)
    df["store_norm"] = df["tienda / ubicación"].apply(norm_store)
    df["color_norm"] = df["COLOR"].apply(norm_color)
    df["mes_key"] = df.apply(norm_mes, axis=1)

    # Detect partial month (current month = septiembre 2026)
    all_meses = sorted(df["mes_key"].unique(), key=mes_sort_key)
    last_mes = all_meses[-1] if all_meses else ""
    es_parcial = last_mes.startswith("septiembre-2026")
    partial_msg = f"{mes_label(last_mes)} con datos parciales" if es_parcial else f"{mes_label(last_mes)} con datos parciales"

    # Jacket 2.0 (excluir PEDIDOS — pedidos corporativos no retail)
    df20 = df[df["Producto"].isin(CUADRO_PRODUCTS)].copy()
    df20 = df20[~df20["store_norm"].isin(EXCLUDE_STORES_20)]
    raw20 = build_raw_rows(df20, lambda p: "CUADRO JACKET 2.0")
    stock = load_existing_stock()
    data20 = build_data(raw20, ["CUADRO JACKET 2.0"], stock=stock, es_parcial=es_parcial)
    period20 = period_label(data20["meses_order"])
    template = TEMPLATE_20_PATH.read_text(encoding="utf-8")
    html20 = patch_20_html(replace_data_in_html(template, data20), period20, partial_msg)
    OUT_20_PATH.write_text(html20, encoding="utf-8")
    print(f"✓ Jacket 2.0: {data20['total']:,} und · {len(raw20)} filas · {period20}")

    # Jacket 1.0
    df10 = df[df["Producto"].isin(JACKET10_PRODUCTS)].copy()
    raw10 = build_raw_rows(df10, lambda p: p)
    data10 = build_data(raw10, ["JACKET CAB", "JACKET DAMA", "JACKET KIDS", "JACKET"], stock={}, es_parcial=es_parcial)
    period10 = period_label(data10["meses_order"])
    html10 = build_10_html(template, data10, period10, partial_msg)
    OUT_10_PATH.write_text(html10, encoding="utf-8")
    print(f"✓ Jacket 1.0: {data10['total']:,} und · {len(raw10)} filas · {period10}")


if __name__ == "__main__":
    main()
