#!/usr/bin/env python3
"""Build Jacket 2.0 dashboard DATA from CSV files."""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

VENTAS_PATH = Path(__file__).resolve().parent / "data" / "jacket_ventas.csv"
INV_PATH = Path(__file__).resolve().parent / "data" / "jacket_inventario.csv"
TEMPLATE_PATH = Path(__file__).resolve().parent / "Dashboard_Jacket_2_0 (3).html"
OUTPUT_PATH = TEMPLATE_PATH

MODEL = "CUADRO JACKET 2.0"
LINEAS = ["CAB", "DAMA", "KIDS"]
MESES_ORDER = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
MESES_MAP = {m.upper(): m for m in MESES_ORDER}
ME_SHORT = {
    "enero": "Ene", "febrero": "Feb", "marzo": "Mar", "abril": "Abr",
    "mayo": "May", "junio": "Jun", "julio": "Jul", "agosto": "Ago",
    "septiembre": "Sep", "octubre": "Oct", "noviembre": "Nov", "diciembre": "Dic",
}
PARTIAL_MONTH = "agosto-2026"
HIGH_SEASON_FACTOR = 1.25
COVER_MONTHS = 9
LEAD_MONTHS = 3
ALL_STORES = [
    "CERRO VERDE", "CHACAO", "GRAND PLAZ", "GRIETA", "SAMBIL",
    "TOLON", "WEB", "PEDIDOS", "CORPORATIVO",
]
STORE_ORDER = ALL_STORES + ["VELA", "BARQUISIMETO", "TALLER"]
STORE_ALIASES = {
    "LA GRIETA": "GRIETA",
    "GRIETA": "GRIETA",
    "GRIE": "GRIETA",
    "SAMBIL VALENCIA": "SAMBIL",
    "SAMBIL": "SAMBIL",
    "SAMBIL CHACAO": "CHACAO",
    "CHACAO": "CHACAO",
    "CERRO VERDE": "CERRO VERDE",
    "GRAND PLAZ": "GRAND PLAZ",
    "GRANDPLAZ": "GRAND PLAZ",
    "GRAND PLAZA": "GRAND PLAZ",
    "LA VELA": "VELA",
    "VELA": "VELA",
    "MARGARITA": "VELA",
    "TOLON": "TOLON",
    "TOLÓN": "TOLON",
    "WEB": "WEB",
    "PEDIDOS": "PEDIDOS",
    "CORPORATIVO": "CORPORATIVO",
    "BARQUISIMETO": "BARQUISIMETO",
    "TALLER": "TALLER",
    "TALLER TERMINADO": "TALLER",
}


def read_csv(path: Path):
    for enc in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            with path.open(encoding=enc, newline="") as f:
                return list(csv.DictReader(f, delimiter=";"))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode {path}")


def parse_num(value) -> float:
    if value is None:
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def get_col_like(row: dict, *patterns: str) -> str:
    for pat in patterns:
        for k, v in row.items():
            if pat.upper() in k.upper() and v is not None:
                return str(v).strip()
    return ""


def normalize_store(name: str) -> str:
    n = re.sub(r"\s+", " ", name.strip().upper())
    return STORE_ALIASES.get(n, n)


def normalize_genero(value: str) -> str:
    g = str(value).strip().upper()
    if g in ("CABALLERO", "CAB"):
        return "CAB"
    if g == "DAMA":
        return "DAMA"
    if g == "KIDS":
        return "KIDS"
    return g


def normalize_color(value: str) -> str:
    c = str(value).strip()
    cl = c.lower()
    mapping = {
        "negro": "Negro",
        "black": "Negro",
        "blanco": "Blanco",
        "white": "Blanco",
        "azul polo": "Azul Polo",
        "aguamarina": "Aguamarina",
        "verde militar": "Verde Militar",
        "magenta": "Magenta",
    }
    if cl in mapping:
        return mapping[cl]
    return c.title() if c.isupper() else c


def mes_sort_key(mes: str):
    part, year = mes.rsplit("-", 1)
    return (int(year), MESES_ORDER.index(part))


def month_label(mes: str) -> str:
    part, year = mes.rsplit("-", 1)
    return f"{ME_SHORT[part]} {year[-2:]}"


def velocity_months(meses_order):
    if PARTIAL_MONTH in meses_order and meses_order.index(PARTIAL_MONTH) >= 3:
        i = meses_order.index(PARTIAL_MONTH)
        return meses_order[i - 3 : i]
    return meses_order[-3:]


def compute_purchase_plan(raw_rows, stock, stock_taller_by_key):
    vel_months = velocity_months(sorted({r["mes"] for r in raw_rows}, key=mes_sort_key))
    purchase_rows = []

    for genero in LINEAS:
        colors = sorted({r["color"] for r in raw_rows if r["genero"] == genero})
        for color in colors:
            tallas = sorted(
                {r["talla"] for r in raw_rows if r["genero"] == genero and r["color"] == color},
                key=lambda t: (len(t), t),
            )
            talla_rows = []
            color_v = 0.0
            color_stk = 0
            color_stk_taller = 0
            color_buy = 0

            for talla in tallas:
                base_v = sum(
                    r["v"] for r in raw_rows
                    if r["genero"] == genero and r["color"] == color and r["talla"] == talla
                    and r["mes"] in vel_months
                ) / max(len(vel_months), 1)
                v_mes = round(base_v * HIGH_SEASON_FACTOR, 1)
                key = f"{MODEL}/{genero}/{color}/{talla}"
                stk = int(stock.get(key, 0))
                stk_taller = int(stock_taller_by_key.get(key, 0))
                need = max(0, round(v_mes * COVER_MONTHS - stk))
                cob = round(stk / v_mes, 1) if v_mes > 0 else 999
                talla_rows.append({
                    "talla": talla,
                    "v_mes": v_mes,
                    "stk": stk,
                    "stk_taller": stk_taller,
                    "cob": cob,
                    "buy": need,
                    "urgente": cob < LEAD_MONTHS,
                })
                color_v += v_mes
                color_stk += stk
                color_stk_taller += stk_taller
                color_buy += need

            if not talla_rows:
                continue
            purchase_rows.append({
                "genero": genero,
                "color": color,
                "v_mes": round(color_v, 1),
                "stk": color_stk,
                "stk_taller": color_stk_taller,
                "cob": round(color_stk / color_v, 1) if color_v > 0 else 999,
                "buy": color_buy,
                "tallas": talla_rows,
            })

    summary = {}
    for genero in LINEAS:
        rows_g = [r for r in purchase_rows if r["genero"] == genero]
        v_mes = sum(r["v_mes"] for r in rows_g)
        stk = sum(r["stk"] for r in rows_g)
        stk_taller = sum(r["stk_taller"] for r in rows_g)
        buy = sum(r["buy"] for r in rows_g)
        summary[genero] = {
            "v_mes": round(v_mes, 1),
            "stk": stk,
            "stk_taller": stk_taller,
            "cob": round(stk / v_mes, 1) if v_mes > 0 else 999,
            "buy": buy,
        }
    return purchase_rows, summary, vel_months


def compute_new_store_projection(raw_rows, store_name, base_store, mult, meses):
    grie_monthly = defaultdict(float)
    for r in raw_rows:
        if r["tienda"] == base_store and r["mes"] in meses:
            key = (r["genero"], r["color"], r["talla"])
            grie_monthly[key] += r["v"]
    n = max(len(meses), 1)
    skus = []
    total_v = 0.0
    for (genero, color, talla), qty in sorted(grie_monthly.items()):
        v_mes = round(qty / n * mult * HIGH_SEASON_FACTOR, 2)
        total_v += v_mes
        skus.append({
            "Genero": genero,
            "Color": color,
            "Talla": talla,
            "v_mes": v_mes,
            "need_1m": max(0, round(v_mes * 1)),
            "need_2m": max(0, round(v_mes * 2)),
            "need_3m": max(0, round(v_mes * 3)),
        })
    return {
        "v_mes": round(total_v, 1),
        "need_1m": max(0, round(total_v * 1)),
        "need_2m": max(0, round(total_v * 2)),
        "need_3m": max(0, round(total_v * 3)),
        "nota": f"{mult}× velocidad {base_store} · factor temporada alta ×{HIGH_SEASON_FACTOR}",
        "skus": skus,
    }


def build_data():
    ventas = read_csv(VENTAS_PATH)
    inv = read_csv(INV_PATH)

    raw_rows = []
    tiendas_set = set()
    colores_set = set()
    generos_set = set()
    returns_units = 0

    for r in ventas:
        qty = parse_num(get_col_like(r, "Cant. ordenada", "Cant ordenada"))
        if qty == 0:
            continue
        mes = f"{MESES_MAP[r['Mes'].strip().upper()]}-{r['Año'].strip()}"
        genero = normalize_genero(get_col_like(r, "GENERO", "Genero"))
        color = normalize_color(get_col_like(r, "COLOR", "Color"))
        talla = get_col_like(r, "TALLA", "Talla")
        tienda = normalize_store(get_col_like(r, "tienda / ubic", "ubic"))
        v = round(qty)
        if v < 0:
            returns_units += v
        tiendas_set.add(tienda)
        colores_set.add(color)
        generos_set.add(genero)
        raw_rows.append({
            "tienda": tienda,
            "genero": genero,
            "color": color,
            "talla": talla,
            "mes": mes,
            "modelo": MODEL,
            "v": v,
        })

    meses_order = sorted({r["mes"] for r in raw_rows}, key=mes_sort_key)
    meses_und = {m: sum(r["v"] for r in raw_rows if r["mes"] == m) for m in meses_order}
    total = sum(r["v"] for r in raw_rows)

    stock = defaultdict(int)
    stock_by_store = defaultdict(lambda: defaultdict(int))
    stock_taller_by_key = defaultdict(int)
    for r in inv:
        store = normalize_store(get_col_like(r, "Ubicac"))
        genero = normalize_genero(get_col_like(r, "GENERO", "Genero"))
        color = normalize_color(get_col_like(r, "COLOR", "Color"))
        talla = get_col_like(r, "TALLA", "Talla", "talla")
        qty = round(parse_num(get_col_like(r, "Cantidad")))
        if qty == 0:
            continue
        key = f"{MODEL}/{genero}/{color}/{talla}"
        stock[key] += qty
        stock_by_store[store][key] += qty
        if store == "TALLER":
            stock_taller_by_key[key] += qty

    stock_total = sum(stock.values())
    stock_taller = sum(stock_by_store.get("TALLER", {}).values())

    purchase_plan, summary_compra, vel_months = compute_purchase_plan(
        raw_rows, stock, stock_taller_by_key
    )
    vela_proj = compute_new_store_projection(raw_rows, "VELA", "GRIETA", 1, vel_months)
    barquisimeto_proj = compute_new_store_projection(
        raw_rows, "BARQUISIMETO", "GRIETA", 1, vel_months
    )

    tiendas_list = [s for s in ALL_STORES + ["VELA"] if s in tiendas_set]
    for s in sorted(tiendas_set):
        if s not in tiendas_list and s != "TALLER":
            tiendas_list.append(s)

    stores_present = set(stock_by_store.keys())
    stores_order = [s for s in STORE_ORDER if s in stores_present]
    for s in sorted(stores_present):
        if s not in stores_order:
            stores_order.append(s)

    periodo = f"{month_label(meses_order[0])} — {month_label(meses_order[-1])}"
    vel_labels = " · ".join(month_label(m) for m in vel_months)

    return {
        "raw_rows": raw_rows,
        "stock": dict(stock),
        "stock_by_store": {k: dict(v) for k, v in stock_by_store.items()},
        "stock_by_modelo": {MODEL: stock_total},
        "meses_order": meses_order,
        "meses_und": meses_und,
        "filtros": {
            "tiendas": tiendas_list,
            "generos": [g for g in LINEAS if g in generos_set],
            "colores": sorted(colores_set),
            "modelos": [MODEL],
        },
        "es_parcial": PARTIAL_MONTH in meses_order,
        "stock_total": stock_total,
        "stock_taller": stock_taller,
        "total": total,
        "all_stores": ALL_STORES,
        "stores_order": stores_order,
        "purchase_plan": purchase_plan,
        "summary_compra": summary_compra,
        "vela": vela_proj,
        "barquisimeto": barquisimeto_proj,
        "margarita": vela_proj,
        "cover_months": COVER_MONTHS,
        "lead_months": LEAD_MONTHS,
        "high_season_factor": HIGH_SEASON_FACTOR,
        "velocity_months": vel_months,
        "velocity_months_label": vel_labels,
        "periodo": periodo,
        "_meta": {
            "returns_units": returns_units,
        },
    }


def build_html(data: dict) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    payload = {k: v for k, v in data.items() if not k.startswith("_")}
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    html = re.sub(
        r"var DATA=\{.*?\};\s*\nvar _modelo",
        f"var DATA={data_json};\nvar _modelo",
        template,
        count=1,
        flags=re.DOTALL,
    )
    periodo = data.get("periodo", "")
    html = re.sub(
        r"<p>Dashboard de Ventas · .*?</p>",
        f"<p>Dashboard de Ventas · {periodo}</p>",
        html,
        count=1,
    )
    html = re.sub(
        r"<div class=\"footer\">.*?</div>",
        f'<div class="footer">Jacket 2.0 · Dashboard de Ventas · {periodo}</div>',
        html,
        count=1,
    )
    return html


def main():
    data = build_data()
    OUTPUT_PATH.write_text(build_html(data), encoding="utf-8")
    meta = data.get("_meta", {})
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Total ventas: {data['total']}")
    print(f"Devoluciones netas: {meta.get('returns_units', 0)}")
    print(f"Periodo: {data['periodo']}")
    print(f"Stock total: {data['stock_total']} (Taller: {data['stock_taller']})")
    print(f"Velocity months: {data['velocity_months_label']}")
    print(f"High season factor: {data['high_season_factor']}")
    print(f"Compra total sugerida: {sum(r['buy'] for r in data['purchase_plan'])}")


if __name__ == "__main__":
    main()
