#!/usr/bin/env python3
"""Update DAILY 3.0 DASHBOARD PARA ACTUALIZAR.html — merge jul/ago ventas + inventario."""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

HTML_PATH = Path(__file__).resolve().parent / "DAILY 3.0 DASHBOARD PARA ACTUALIZAR.html"
VENTAS_UPDATE_PATH = Path(__file__).resolve().parent / "data" / "daily_3_ventas_jul_ago_2026.csv"
INV_PATH = Path(__file__).resolve().parent / "data" / "daily_3_inventario.csv"

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
MESES_UPPER = {m.upper(): m for m in MESES}
TALLA_ORDER = ["XS", "S", "M", "L", "XL", "2XL", "3XL", "6", "8", "10", "12", "14"]
BASE_MESES = ["febrero-2026", "marzo-2026", "abril-2026"]
MODEL_ONLY = "CLASICA DAILY 3.0"
LINEAS = ["CAB", "DAMA"]
REPLACE_MESES = {"julio-2026", "agosto-2026"}
PARTIAL_MONTH = "agosto-2026"
VELOCITY_MONTHS_COUNT = 6
HIGH_SEASON_FACTOR = 1.4
DEC_BASE_FACTOR = 1.4
LEAD_MONTHS = 3


def read_csv(path: Path):
    for enc in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            with path.open(encoding=enc, newline="") as f:
                return list(csv.DictReader(f, delimiter=";"))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode {path}")


def norm_key(row: dict) -> dict:
    return {re.sub(r"\s+", " ", k.strip()): v for k, v in row.items()}


def get_col(row: dict, *candidates: str) -> str:
    for c in candidates:
        if c in row and row[c] is not None:
            return str(row[c]).strip()
    upper = {k.upper(): k for k in row}
    for c in candidates:
        if c.upper() in upper and row[upper[c.upper()]] is not None:
            return str(row[upper[c.upper()]]).strip()
    return ""


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


def mes_sort_key(m):
    part, year = m.rsplit("-", 1)
    return (int(year), MESES.index(part))


def month_label(mes: str) -> str:
    part, year = mes.rsplit("-", 1)
    short = {
        "enero": "Ene", "febrero": "Feb", "marzo": "Mar", "abril": "Abr",
        "mayo": "May", "junio": "Jun", "julio": "Jul", "agosto": "Ago",
        "septiembre": "Sep", "octubre": "Oct", "noviembre": "Nov", "diciembre": "Dic",
    }
    return f"{short.get(part, part[:3].title())} {year[-2:]}"


def norm_genero(g):
    g = str(g).strip().upper()
    if g in ("CABALLERO", "CAB"):
        return "CAB"
    if g == "DAMA":
        return "DAMA"
    if g == "KIDS":
        return "KIDS"
    return g


def norm_modelo(m):
    s = str(m).strip().upper()
    s = s.replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
    if "ELIMINAR" in s:
        return None
    if "3.0" in s or "3,0" in s or "DAILY 3" in s:
        return MODEL_ONLY
    return None


def norm_color(c):
    c = str(c).strip()
    if " - " in c:
        c = c.split(" - ")[0].strip()
    return c


def norm_tienda(t):
    t = " ".join(str(t).strip().upper().split())
    mapping = {
        "GRIETA": "GRIE",
        "LA GRIETA": "GRIE",
        "GRIE": "GRIE",
        "CERRO VERDE": "CERRO VERDE",
        "CERRV": "CERRO VERDE",
        "GRAND PLAZ": "GRANDPLAZ",
        "GRANDPLAZ": "GRANDPLAZ",
        "GRAND": "GRANDPLAZ",
        "GRACH": "GRANDPLAZ",
        "SAMBIL CHACAO": "SAMBIL CHACAO",
        "CHACAO": "SAMBIL CHACAO",
        "SAMBIL VALENCIA": "SAMBIL VALENCIA",
        "SAMBIL": "SAMBIL VALENCIA",
        "PEDIDOS": "PEDIDOS",
        "WEB": "WEB",
        "TOLON": "TOLON",
        "TOLÓN": "TOLON",
        "LA VELA": "VELA",
        "VELA": "VELA",
        "TALLER": "TALLER",
        "TH": "TALLER",
    }
    return mapping.get(t, t)


def loc_key(name):
    return norm_tienda(name)


def talla_sort(t):
    try:
        return TALLA_ORDER.index(str(t))
    except ValueError:
        return 99


def parse_mes(row: dict) -> str | None:
    raw = get_col(row, "fecha (mes año)", "fecha mes año")
    if raw:
        s = raw.strip().lower()
        if "-" in s:
            return s
        if "/" in s:
            mm, yy = s.split("/")
            if mm.isdigit() and int(mm) in range(1, 13):
                return f"{MESES[int(mm) - 1]}-{yy.strip()}"
    mes_raw = get_col(row, "Mes", "MES").upper()
    year_raw = get_col(row, "Año", "Ano", "AÑO")
    if mes_raw and year_raw:
        mes = MESES_UPPER.get(mes_raw)
        if mes:
            return f"{mes}-{year_raw.strip()}"
    return None


def venta_row_from_csv(row: dict) -> dict | None:
    row = norm_key(row)
    modelo = norm_modelo(get_col(row, "modelo", "Modelo", "MODELO"))
    if not modelo:
        return None
    qty = parse_num(get_col(row, "Cant. ordenada"))
    if qty == 0:
        return None
    mes = parse_mes(row)
    if not mes:
        return None
    talla = get_col(row, "TALLA", "talla")
    if not talla:
        return None
    return {
        "tienda": norm_tienda(get_col(row, "tienda / ubicación", "tienda/ubicación")),
        "genero": norm_genero(get_col(row, "GENERO", "genero")),
        "color": norm_color(get_col(row, "COLOR", "color")),
        "talla": talla,
        "mes": mes,
        "modelo": modelo,
        "v": int(qty) if qty == int(qty) else qty,
    }


def read_ventas_update():
    return [r for r in (venta_row_from_csv(raw) for raw in read_csv(VENTAS_UPDATE_PATH)) if r]


def read_inventario():
    stock = defaultdict(int)
    stock_by_loc = defaultdict(lambda: defaultdict(int))
    inv_rows = []
    for raw in read_csv(INV_PATH):
        row = norm_key(raw)
        modelo = norm_modelo(get_col(row, "MODELO"))
        if not modelo:
            continue
        loc = loc_key(get_col(row, "Ubicación", "Ubicacion"))
        genero = norm_genero(get_col(row, "GENERO"))
        color = norm_color(get_col(row, "COLOR"))
        talla = get_col(row, "TALLA")
        qty = round(parse_num(get_col(row, "Cantidad en inventario")))
        if qty == 0:
            continue
        key = f"{modelo}/{genero}/{color}/{talla}"
        stock[key] += qty
        stock_by_loc[loc][key] += qty
        inv_rows.append({
            "ubicacion": loc,
            "modelo": modelo,
            "genero": genero,
            "color": color,
            "talla": talla,
            "qty": qty,
            "sku": get_col(row, "SKU"),
        })
    return dict(stock), {k: dict(v) for k, v in stock_by_loc.items()}, inv_rows


def load_existing_data() -> dict:
    html = HTML_PATH.read_text(encoding="utf-8")
    match = re.search(r"var DATA=(\{.*?\});", html, re.DOTALL)
    if not match:
        raise ValueError("DATA block not found")
    return json.loads(match.group(1))


def merge_raw_rows(existing_rows: list, update_rows: list) -> list:
    kept = [r for r in existing_rows if r["mes"] not in REPLACE_MESES]
    return kept + update_rows


def velocity_months(meses_order: list) -> list:
    if PARTIAL_MONTH in meses_order and meses_order.index(PARTIAL_MONTH) >= VELOCITY_MONTHS_COUNT:
        i = meses_order.index(PARTIAL_MONTH)
        return meses_order[i - VELOCITY_MONTHS_COUNT : i]
    return meses_order[-VELOCITY_MONTHS_COUNT:]


def month_weight(mes: str) -> float:
    return DEC_BASE_FACTOR if mes.startswith("diciembre") else 1.0


def base_velocity(rows, genero, color, talla, vel_months):
    weighted = 0.0
    weights = 0.0
    for mes in vel_months:
        w = month_weight(mes)
        qty = sum(
            r["v"] for r in rows
            if r["genero"] == genero and r["color"] == color and r["talla"] == talla and r["mes"] == mes
        )
        weighted += qty * w
        weights += w
    return weighted / weights if weights > 0 else 0.0


def compute_production_plan(raw_rows, stock, stock_taller_by_key, vel_months):
    production_rows = []
    model_rows = [r for r in raw_rows if r["modelo"] == MODEL_ONLY]
    for genero in LINEAS:
        colors = sorted({r["color"] for r in model_rows if r["genero"] == genero})
        for color in colors:
            tallas = sorted(
                {r["talla"] for r in model_rows if r["genero"] == genero and r["color"] == color},
                key=lambda t: (len(t), t),
            )
            talla_rows = []
            color_v = color_v_base = color_stk = color_stk_taller = color_produce = 0.0

            for talla in tallas:
                base_v = base_velocity(model_rows, genero, color, talla, vel_months)
                v_mes_base = round(base_v, 1)
                v_mes = round(base_v * HIGH_SEASON_FACTOR, 1)
                key = f"{MODEL_ONLY}/{genero}/{color}/{talla}"
                stk = int(stock.get(key, 0))
                stk_taller = int(stock_taller_by_key.get(key, 0))
                cob = round(stk / v_mes, 1) if v_mes > 0 else 999
                need = max(0, round(v_mes * LEAD_MONTHS - stk)) if cob < LEAD_MONTHS else 0
                talla_rows.append({
                    "talla": talla,
                    "v_mes_base": v_mes_base,
                    "v_mes": v_mes,
                    "stk": stk,
                    "stk_taller": stk_taller,
                    "cob": cob,
                    "produce": need,
                    "urgente": cob < LEAD_MONTHS,
                })
                color_v += v_mes
                color_v_base += v_mes_base
                color_stk += stk
                color_stk_taller += stk_taller
                color_produce += need

            if not talla_rows:
                continue
            production_rows.append({
                "modelo": MODEL_ONLY,
                "genero": genero,
                "color": color,
                "v_mes_base": round(color_v_base, 1),
                "v_mes": round(color_v, 1),
                "stk": color_stk,
                "stk_taller": color_stk_taller,
                "cob": round(color_stk / color_v, 1) if color_v > 0 else 999,
                "produce": color_produce,
                "tallas": talla_rows,
            })

    v_mes = sum(r["v_mes"] for r in production_rows)
    v_mes_base = sum(r["v_mes_base"] for r in production_rows)
    stk = sum(r["stk"] for r in production_rows)
    stk_taller = sum(r["stk_taller"] for r in production_rows)
    produce = sum(r["produce"] for r in production_rows)
    summary = {
        MODEL_ONLY: {
            "v_mes_base": round(v_mes_base, 1),
            "v_mes": round(v_mes, 1),
            "stk": stk,
            "stk_taller": stk_taller,
            "cob": round(stk / v_mes, 1) if v_mes > 0 else 999,
            "produce": produce,
        }
    }

    summary_genero = {}
    for genero in LINEAS:
        rows_g = [r for r in production_rows if r["genero"] == genero]
        g_v = sum(r["v_mes"] for r in rows_g)
        g_v_base = sum(r["v_mes_base"] for r in rows_g)
        g_stk = sum(r["stk"] for r in rows_g)
        g_prod = sum(r["produce"] for r in rows_g)
        summary_genero[genero] = {
            "v_mes_base": round(g_v_base, 1),
            "v_mes": round(g_v, 1),
            "stk": g_stk,
            "cob": round(g_stk / g_v, 1) if g_v > 0 else 999,
            "produce": g_prod,
        }

    return production_rows, summary, summary_genero


def compute_prod_curve(raw_rows, stock, stock_by_loc):
    base = [m for m in BASE_MESES if any(r["mes"] == m for r in raw_rows)]
    if not base:
        base = sorted({r["mes"] for r in raw_rows}, key=mes_sort_key)[-3:]

    sales = defaultdict(int)
    for r in raw_rows:
        if r["mes"] in base:
            k = (r["modelo"], r["genero"], r["color"], r["talla"])
            sales[k] += r["v"]

    stk_taller = stock_by_loc.get("TALLER", {})
    curve = []
    keys = set(sales.keys())
    for k in stock:
        parts = k.split("/")
        keys.add((parts[0], parts[1], parts[2], parts[3]))

    for modelo, genero, color, talla in sorted(keys):
        v3m = sales.get((modelo, genero, color, talla), 0)
        v_mes = round(v3m / len(base), 1) if base else 0
        key = f"{modelo}/{genero}/{color}/{talla}"
        stk_total = stock.get(key, 0)
        stk_pt = stk_taller.get(key, 0)
        cobertura = round(stk_total / v_mes, 1) if v_mes > 0 else 0
        need = lambda n, vm=v_mes, st=stk_total: max(0, round(vm * n - st))
        curve.append({
            "modelo": modelo,
            "genero": genero,
            "talla": talla,
            "color": color,
            "v3m": v3m,
            "v_mes": v_mes,
            "stk_total": stk_total,
            "stk_pt": stk_pt,
            "cobertura": cobertura,
            "need_1m": need(1),
            "need_2m": need(2),
            "need_3m": need(3),
            "tsort": talla_sort(talla),
        })
    curve.sort(key=lambda r: (r["modelo"], r["color"], r["tsort"]))
    return curve


def compute_summary_prod(prod_curve):
    summary = {}
    for modelo in sorted({r["modelo"] for r in prod_curve}):
        rows = [r for r in prod_curve if r["modelo"] == modelo]
        summary[modelo] = {
            "v_mes": round(sum(r["v_mes"] for r in rows), 1),
            "stk_total": sum(r["stk_total"] for r in rows),
            "need_1m": sum(r["need_1m"] for r in rows),
            "need_2m": sum(r["need_2m"] for r in rows),
            "need_3m": sum(r["need_3m"] for r in rows),
            "stk_pt": sum(r["stk_pt"] for r in rows),
        }
    return summary


def compute_margarita(raw_rows, mult=2.0):
    base = [m for m in BASE_MESES if any(r["mes"] == m for r in raw_rows)]
    if not base:
        base = sorted({r["mes"] for r in raw_rows}, key=mes_sort_key)[-3:]

    grie_sales = defaultdict(float)
    for r in raw_rows:
        if r["tienda"] == "GRIE" and r["mes"] in base:
            k = (r["modelo"], r["genero"], r["color"], r["talla"])
            grie_sales[k] += r["v"]

    skus = []
    v_mes_total = 0
    for (modelo, genero, color, talla), v3m in sorted(grie_sales.items()):
        v_mes = round(v3m / len(base) * mult, 4)
        if v_mes <= 0:
            continue
        need = lambda n, vm=v_mes: max(0, round(vm * n))
        skus.append({
            "MODELO": modelo,
            "GENERO": genero,
            "COLOR": color,
            "TALLA": talla,
            "need_1m": need(1),
            "need_2m": need(2),
            "need_3m": need(3),
            "v_mes": v_mes,
        })
        v_mes_total += v_mes

    return {
        "v_mes": round(v_mes_total, 1),
        "need_1m": sum(s["need_1m"] for s in skus),
        "need_2m": sum(s["need_2m"] for s in skus),
        "need_3m": sum(s["need_3m"] for s in skus),
        "nota": f"{mult:.0f}× velocidad GRIE (tienda nueva proyectada)".replace(".0×", "×"),
        "skus": skus,
    }


def compute_tolon(raw_rows):
    base = [m for m in BASE_MESES if any(r["mes"] == m for r in raw_rows)]
    if not base:
        base = sorted({r["mes"] for r in raw_rows}, key=mes_sort_key)[-3:]
    v = sum(r["v"] for r in raw_rows if r["tienda"] == "TOLON" and r["mes"] in base)
    return {"v_base": v, "v_mes": round(v / len(base), 1) if base else 0}


def compute_store_projection(raw_rows, stores, mult, meses, label):
    monthly = defaultdict(lambda: defaultdict(float))
    for r in raw_rows:
        if r["tienda"] not in stores or r["mes"] not in meses:
            continue
        key = (r["modelo"], r["genero"], r["color"], r["talla"])
        monthly[key][r["tienda"]] += r["v"]

    n = max(len(meses), 1)
    skus = []
    total_v = 0.0
    for key in sorted(monthly):
        per_store = [monthly[key][s] / n for s in stores]
        v_mes = round(sum(per_store) / len(stores) * mult * HIGH_SEASON_FACTOR, 2)
        total_v += v_mes
        modelo, genero, color, talla = key
        skus.append({
            "MODELO": modelo,
            "GENERO": genero,
            "COLOR": color,
            "TALLA": talla,
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
        "nota": label,
        "skus": skus,
    }


def build_data():
    existing = load_existing_data()
    update_rows = read_ventas_update()
    raw_rows = merge_raw_rows(existing["raw_rows"], update_rows)
    stock, stock_by_loc, inv_rows = read_inventario()
    prod_curve = compute_prod_curve(raw_rows, stock, stock_by_loc)
    meses_order = sorted({r["mes"] for r in raw_rows}, key=mes_sort_key)
    vel_months = velocity_months(meses_order)
    stock_taller = stock_by_loc.get("TALLER", {})
    production_plan, summary_produccion, summary_genero = compute_production_plan(
        raw_rows, stock, stock_taller, vel_months
    )
    meses_und = {m: sum(r["v"] for r in raw_rows if r["mes"] == m) for m in meses_order}

    stock_by_modelo = defaultdict(int)
    for k, v in stock.items():
        stock_by_modelo[k.split("/")[0]] += v

    tiendas = sorted(set(r["tienda"] for r in raw_rows) | set(stock_by_loc.keys()))
    all_stores = sorted(set(tiendas) - {"TALLER", "WEB", "PEDIDOS"})
    stock_pt_total = sum(stock_by_loc.get("TALLER", {}).values())
    last_mes = meses_order[-1] if meses_order else ""
    es_parcial = last_mes == "agosto-2026"

    return {
        "raw_rows": raw_rows,
        "stock": stock,
        "stock_by_loc": stock_by_loc,
        "inv_rows": inv_rows,
        "stock_by_modelo": dict(stock_by_modelo),
        "meses_order": meses_order,
        "meses_und": meses_und,
        "filtros": {
            "tiendas": tiendas,
            "generos": sorted({r["genero"] for r in raw_rows}),
            "colores": sorted({r["color"] for r in raw_rows}),
            "modelos": sorted({r["modelo"] for r in raw_rows}),
        },
        "es_parcial": es_parcial,
        "stock_total": sum(stock.values()),
        "stock_pt_total": stock_pt_total,
        "total": sum(r["v"] for r in raw_rows),
        "all_stores": all_stores,
        "inv_locations": sorted(stock_by_loc.keys()),
        "prod_curve": prod_curve,
        "summary_prod": compute_summary_prod(prod_curve),
        "production_plan": production_plan,
        "summary_produccion": summary_produccion,
        "summary_genero": summary_genero,
        "velocity_months": vel_months,
        "velocity_months_label": " · ".join(month_label(m) for m in vel_months),
        "velocity_months_count": len(vel_months),
        "high_season_factor": HIGH_SEASON_FACTOR,
        "december_base_factor": DEC_BASE_FACTOR,
        "stock_taller": sum(stock_taller.values()),
        "lead_months": LEAD_MONTHS,
        "new_stores": ["VELA", "BARQUISIMETO"],
        "new_store_caps": {
            "VELA": {"base": "GRIE", "mult": 1.5, "label": "1.5× GRIE"},
            "BARQUISIMETO": {
                "type": "avg",
                "bases": ["SAMBIL CHACAO", "GRIE"],
                "label": "prom. SAMBIL CHACAO + GRIE",
            },
        },
        "barquisimeto": compute_store_projection(
            raw_rows,
            ["SAMBIL CHACAO", "GRIE"],
            1,
            vel_months,
            f"prom. SAMBIL CHACAO + GRIE · factor temporada alta ×{HIGH_SEASON_FACTOR} · diciembre base ×{DEC_BASE_FACTOR}",
        ),
        "vela": compute_store_projection(
            raw_rows,
            ["GRIE"],
            1.5,
            vel_months,
            f"1.5× GRIE · factor temporada alta ×{HIGH_SEASON_FACTOR}",
        ),
        "margarita": compute_margarita(raw_rows, mult=2.0),
        "tolon": compute_tolon(raw_rows),
        "date_range": (
            f"{month_label(meses_order[0])} — {month_label(meses_order[-1])}"
            if meses_order else ""
        ),
    }


def build_html(data: dict) -> str:
    html = HTML_PATH.read_text(encoding="utf-8")
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = re.sub(
        r"var DATA=\{.*?\};",
        f"var DATA={data_json};",
        html,
        count=1,
        flags=re.DOTALL,
    )
    dr = data["date_range"]
    html = re.sub(
        r"Dashboard de Ventas · [^<&]+",
        f"Dashboard de Ventas · {dr}",
        html,
    )
    html = re.sub(
        r"Daily 3\.0 - Clásica · Dashboard de Ventas · [^<]+",
        f"Daily 3.0 - Clásica · Dashboard de Ventas · {dr}",
        html,
    )
    return html


def main():
    data = build_data()
    HTML_PATH.write_text(build_html(data), encoding="utf-8")

    jul = sum(r["v"] for r in data["raw_rows"] if r["mes"] == "julio-2026")
    ago = sum(r["v"] for r in data["raw_rows"] if r["mes"] == "agosto-2026")
    print(f"Wrote {HTML_PATH}")
    print(f"Total ventas: {data['total']}")
    print(f"Periodo: {data['date_range']}")
    print(f"Julio 2026: {jul} und | Agosto 2026: {ago} und")
    print(f"Stock total: {data['stock_total']} (antes 987)")
    print(f"Meses: {len(data['meses_order'])} | es_parcial: {data['es_parcial']}")
    print(f"summary_prod: {data['summary_prod']}")
    print(f"prod_curve need_3m total: {sum(r['need_3m'] for r in data['prod_curve'])}")
    print(f"production_plan produce total: {sum(r['produce'] for r in data['production_plan'])}")
    print(f"velocity_months: {data['velocity_months_label']}")
    print(f"barquisimeto v_mes: {data['barquisimeto']['v_mes']}")


if __name__ == "__main__":
    main()
