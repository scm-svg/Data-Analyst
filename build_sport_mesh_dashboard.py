#!/usr/bin/env python3
"""Build COLECCION SPORT MESH.html DATA from CSV ventas/inventario."""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

VENTAS_PATH = Path(__file__).resolve().parent / "data" / "sport_mesh_ventas.csv"
INV_PATH = Path(__file__).resolve().parent / "data" / "sport_mesh_inventario.csv"
HTML_PATH = Path(__file__).resolve().parent / "COLECCION SPORT MESH.html"

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
MESES_UPPER = {m.upper(): m for m in MESES}
TALLA_ORDER = ["XS", "S", "M", "L", "XL", "2XL", "3XL", "6", "8", "10", "12", "14"]
BASE_MESES = ["febrero-2026", "marzo-2026", "abril-2026"]
EXCLUDED_COLORS = {"Rosa Seca", "Rosa Palo"}


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


def mes_sort_key(m):
    part, year = m.rsplit("-", 1)
    return (int(year), MESES.index(part))


def mes_key_from_row(row: dict) -> str | None:
    mes_raw = get_col(row, "Mes", "MES").upper()
    year_raw = get_col(row, "Año", "Ano", "AÑO")
    if mes_raw and year_raw:
        mes = MESES_UPPER.get(mes_raw)
        if mes:
            return f"{mes}-{year_raw.strip()}"
    return None


def norm_genero(g):
    g = str(g).strip().upper()
    if g in ("CABALLERO", "CAB"):
        return "CAB"
    if g == "DAMA":
        return "DAMA"
    if g == "KIDS":
        return "KIDS"
    return g


def norm_modelo_from_product(producto: str, genero: str):
    p = str(producto).strip().upper()
    p = p.replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
    if "ELIMINAR" in p:
        return None
    if "CLASICA" in p:
        return "CLASICA SPORT"
    if "SABRI" in p:
        return "SABRI SPORT"
    if "MAFE" in p:
        return "MAFE SPORT"
    if "CAB" in p:
        return "CLASICA SPORT"
    if "KIDS" in p:
        return "CLASICA SPORT"
    if genero == "DAMA" and "SPORT" in p:
        return "SABRI SPORT"
    return None


def norm_modelo(m):
    m = str(m).strip().upper()
    m = m.replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
    if "ELIMINAR" in m:
        return None
    if "CLASICA" in m:
        return "CLASICA SPORT"
    if "SABRI" in m:
        return "SABRI SPORT"
    if "MAFE" in m:
        return "MAFE SPORT"
    return str(m).strip()


def norm_color(c):
    c = str(c).strip()
    if " - " in c:
        c = c.split(" - ")[0].strip()
    return c


def is_excluded_color(color: str) -> bool:
    c = norm_color(color)
    if c in EXCLUDED_COLORS:
        return True
    low = c.lower()
    return "rosa palo" in low or "rosa seca" in low


def norm_tienda(t):
    t = " ".join(str(t).strip().upper().split())
    mapping = {
        "GRIETA": "GRIE",
        "LA GRIETA": "GRIE",
        "GRIE": "GRIE",
        "CERRO VERDE": "CERRO VERDE",
        "GRANDPLAZ": "GRANDPLAZ",
        "GRAND PLAZ": "GRANDPLAZ",
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
        "CORPORATIVO": "CORPORATIVO",
    }
    return mapping.get(t, t)


def loc_key(raw_loc: str) -> str:
    loc = str(raw_loc).strip()
    prefix = loc.split("/")[0].strip().upper()
    prefix_map = {
        "CERRV": "CERRO VERDE",
        "CHACAO": "SAMBIL CHACAO",
        "GRACH": "GRANDPLAZ",
        "GRIETA": "GRIE",
        "SAMBIL": "SAMBIL VALENCIA",
        "TH": "TALLER",
        "TOLON": "TOLON",
        "VELA": "VELA",
    }
    if prefix in prefix_map:
        return prefix_map[prefix]
    return norm_tienda(loc)


def talla_sort(t):
    try:
        return TALLA_ORDER.index(t)
    except ValueError:
        return 99


def month_label(mes: str) -> str:
    part, year = mes.rsplit("-", 1)
    short = {
        "enero": "Ene", "febrero": "Feb", "marzo": "Mar", "abril": "Abr",
        "mayo": "May", "junio": "Jun", "julio": "Jul", "agosto": "Ago",
        "septiembre": "Sep", "octubre": "Oct", "noviembre": "Nov", "diciembre": "Dic",
    }
    return f"{short.get(part, part[:3].title())} {year[-2:]}"


def read_ventas():
    rows = []
    for raw in read_csv(VENTAS_PATH):
        row = norm_key(raw)
        genero = norm_genero(get_col(row, "GENERO"))
        producto = get_col(row, "Producto")
        modelo = norm_modelo_from_product(producto, genero)
        if not modelo:
            continue
        color = norm_color(get_col(row, "COLOR"))
        if is_excluded_color(color):
            continue
        qty = parse_num(get_col(row, "Cant. ordenada"))
        if qty == 0:
            continue
        mes = mes_key_from_row(row)
        if not mes:
            continue
        rows.append({
            "tienda": norm_tienda(get_col(row, "tienda / ubicación", "tienda/ubicación")),
            "genero": genero,
            "color": color,
            "talla": get_col(row, "TALLA"),
            "mes": mes,
            "modelo": modelo,
            "v": round(qty),
        })
    return rows


def read_inventario():
    stock = defaultdict(int)
    stock_by_loc = defaultdict(lambda: defaultdict(int))
    inv_rows = []
    for raw in read_csv(INV_PATH):
        row = norm_key(raw)
        modelo = norm_modelo(get_col(row, "MODELO"))
        if not modelo:
            continue
        color = norm_color(get_col(row, "COLOR"))
        if is_excluded_color(color):
            continue
        qty = round(parse_num(get_col(row, "Cantidad en inventario")))
        if qty <= 0:
            continue
        loc = loc_key(get_col(row, "Ubicación", "Ubicacion"))
        genero = norm_genero(get_col(row, "GENERO"))
        talla = get_col(row, "TALLA")
        sku = get_col(row, "SKU")
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
            "sku": sku,
        })
    return dict(stock), {k: dict(v) for k, v in stock_by_loc.items()}, inv_rows


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
        stk_total = max(0, stock.get(key, 0))
        stk_pt = max(0, stk_taller.get(key, 0))
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
    return curve, base


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


def build_data():
    raw_rows = read_ventas()
    stock, stock_by_loc, inv_rows = read_inventario()
    prod_curve, _ = compute_prod_curve(raw_rows, stock, stock_by_loc)
    summary_prod = compute_summary_prod(prod_curve)
    margarita = compute_margarita(raw_rows, mult=2.0)

    meses_order = sorted({r["mes"] for r in raw_rows}, key=mes_sort_key)
    meses_und = {m: sum(r["v"] for r in raw_rows if r["mes"] == m) for m in meses_order}

    stock_by_modelo = defaultdict(int)
    for k, v in stock.items():
        stock_by_modelo[k.split("/")[0]] += v

    tiendas = sorted(set(r["tienda"] for r in raw_rows) | set(stock_by_loc.keys()))
    all_stores = sorted(set(tiendas) - {"TALLER", "WEB", "PEDIDOS", "CORPORATIVO"})
    stock_pt_total = sum(max(0, q) for q in stock_by_loc.get("TALLER", {}).values())
    last_mes = meses_order[-1] if meses_order else ""
    es_parcial = last_mes == "agosto-2026"

    date_range = (
        f"{month_label(meses_order[0])} — {month_label(meses_order[-1])}"
        if meses_order else ""
    )

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
        "summary_prod": summary_prod,
        "margarita": margarita,
        "tolon": compute_tolon(raw_rows),
        "date_range": date_range,
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
        r"Sport Mesh · Dashboard de Ventas · [^<]+",
        f"Sport Mesh · Dashboard de Ventas · {dr}",
        html,
    )
    return html


def main():
    data = build_data()
    HTML_PATH.write_text(build_html(data), encoding="utf-8")
    print(f"Wrote {HTML_PATH}")
    print(f"Total ventas: {data['total']}")
    print(f"Periodo: {data['date_range']}")
    print(f"Colores: {data['filtros']['colores']}")
    print(f"Stock total: {data['stock_total']}")
    print(f"Raw rows: {len(data['raw_rows'])}")
    rosa = [c for c in data["filtros"]["colores"] if "rosa" in c.lower()]
    if rosa:
        raise SystemExit(f"ERROR: Rosa colors still present: {rosa}")


if __name__ == "__main__":
    main()
