#!/usr/bin/env python3
"""Build Explore Pants dashboard DATA from CSV files."""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

VENTAS_PATH = Path(__file__).resolve().parent / "data" / "explore_pants_ventas.csv"
INV_PATH = Path(__file__).resolve().parent / "data" / "explore_pants_inventario.csv"
TEMPLATE_PATH = Path(__file__).resolve().parent / "dash_explorepants.html"
OUTPUT_PATH = TEMPLATE_PATH

MESES_ORDER = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
ME_SHORT = {
    "enero": "Ene", "febrero": "Feb", "marzo": "Mar", "abril": "Abr",
    "mayo": "May", "junio": "Jun", "julio": "Jul", "agosto": "Ago",
    "septiembre": "Sep", "octubre": "Oct", "noviembre": "Nov", "diciembre": "Dic",
}
LINEAS = ["CAB", "DAMA", "KIDS"]
STORE_ORDER = ["GRIE", "SAMBIL", "CERRO VERDE", "CHACAO", "GRAND", "TOLON", "VELA", "TALLER"]
STORE_ALIASES = {
    "LA GRIETA": "GRIE",
    "GRIETA": "GRIE",
    "GRIE": "GRIE",
    "CERRO VERDE": "CERRO VERDE",
    "CHACAO": "CHACAO",
    "SAMBIL CHACAO": "CHACAO",
    "SAMBIL": "SAMBIL",
    "SAMBIL VALENCIA": "SAMBIL",
    "GRAND": "GRAND",
    "GRANDPLAZ": "GRAND",
    "GRAND PLAZ": "GRAND",
    "TOLON": "TOLON",
    "TOLÓN": "TOLON",
    "VELA": "VELA",
    "LA VELA": "VELA",
    "TALLER": "TALLER",
    "TALLER TERMINADO": "TALLER",
}
PARTIAL_MONTH = "agosto-2026"


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


def mes_sort_key(mes: str):
    if "-" not in mes:
        return (9999, 99)
    part, year = mes.rsplit("-", 1)
    part = part.lower()
    try:
        y = int(year)
    except ValueError:
        y = 9999
    if part in MESES_ORDER:
        return (y, MESES_ORDER.index(part))
    return (y, 99)


def month_label(mes: str) -> str:
    part, year = mes.rsplit("-", 1)
    return f"{ME_SHORT.get(part.lower(), part[:3].title())} {year[-2:]}"


def forecast_months(meses_order, meses_und, es_parcial):
    if es_parcial and len(meses_order) >= 3:
        return meses_order[-2], meses_order[-3]
    if len(meses_order) >= 2:
        return meses_order[-1], meses_order[-2]
    if meses_order:
        return meses_order[-1], None
    return None, None


def build_data():
    ventas = [norm_key(r) for r in read_csv(VENTAS_PATH)]
    inv = [norm_key(r) for r in read_csv(INV_PATH)]

    raw_rows = []
    meses_set = set()
    tiendas_set = set()
    colores_set = set()
    generos_set = set()
    returns_count = 0
    returns_units = 0

    for r in ventas:
        qty = parse_num(get_col_like(r, "Cant. ordenada", "Cant ordenada"))
        if qty == 0:
            continue
        tienda = normalize_store(get_col_like(r, "UBICAC"))
        if tienda in ("WEB", "PEDIDOS"):
            continue
        genero = normalize_genero(get_col(r, "Genero", "GENERO", "Género"))
        color = get_col(r, "Color", "COLOR")
        talla = get_col(r, "Talla", "TALLA")
        mes = get_col(r, "Fecha", "FECHA").lower()
        if not mes or not genero:
            continue

        v = round(qty)
        if v < 0:
            returns_count += 1
            returns_units += v

        meses_set.add(mes)
        tiendas_set.add(tienda)
        colores_set.add(color)
        generos_set.add(genero)
        raw_rows.append({
            "tienda": tienda,
            "genero": genero,
            "color": color,
            "talla": talla,
            "mes": mes,
            "v": v,
        })

    meses_order = sorted(meses_set, key=mes_sort_key)
    meses_labels = [month_label(m) for m in meses_order]
    meses_und = defaultdict(int)
    for r in raw_rows:
        meses_und[r["mes"]] += r["v"]

    total = sum(r["v"] for r in raw_rows)
    last_m = meses_order[-1]
    prev_m = meses_order[-2] if len(meses_order) >= 2 else None
    var_pct = 0.0
    if prev_m and meses_und[prev_m] > 0:
        var_pct = round((meses_und[last_m] - meses_und[prev_m]) / meses_und[prev_m] * 100, 1)

    es_parcial = bool(last_m and last_m == PARTIAL_MONTH)
    m1_key, m2_key = forecast_months(meses_order, meses_und, es_parcial)

    line_order = {}
    for linea in LINEAS:
        by_mes = defaultdict(int)
        for r in raw_rows:
            if r["genero"] == linea:
                by_mes[r["mes"]] += r["v"]
        m1 = by_mes.get(m1_key, 0) if m1_key else 0
        m2 = by_mes.get(m2_key, 0) if m2_key else 0
        line_order[linea] = {"m1": m1, "m2": m2}

    stock = defaultdict(int)
    stock_by_store = defaultdict(lambda: defaultdict(int))
    for r in inv:
        tienda = normalize_store(get_col_like(r, "Ubicac"))
        genero = normalize_genero(get_col(r, "Genero", "GENERO", "Género"))
        color = get_col(r, "Color", "COLOR")
        talla = get_col(r, "Talla", "TALLA", "talla")
        qty = round(parse_num(get_col_like(r, "Cantidad")))
        if qty == 0 or not genero:
            continue
        key = f"{color}/{talla}/{genero}"
        stock[key] += qty
        stock_by_store[tienda][key] += qty

    stores_present = set(stock_by_store.keys()) | tiendas_set
    stores_order = [s for s in STORE_ORDER if s in stores_present]
    for s in sorted(stores_present):
        if s not in stores_order:
            stores_order.append(s)

    tiendas_list = [s for s in STORE_ORDER if s in tiendas_set and s != "TALLER"]
    for s in sorted(tiendas_set):
        if s not in tiendas_list and s != "TALLER":
            tiendas_list.append(s)

    lineas = [g for g in LINEAS if g in generos_set]
    colores = sorted(colores_set)
    periodo = f"{meses_labels[0]} — {meses_labels[-1]}" if meses_labels else ""

    return {
        "nombre": "EXPLORE PANTS",
        "periodo": periodo,
        "total": total,
        "var_pct": var_pct,
        "es_parcial": es_parcial,
        "n_sem": max(1, len(meses_order) * 4),
        "meses_order": meses_order,
        "meses_labels": meses_labels,
        "meses_und": dict(meses_und),
        "lineas": lineas,
        "tiendas_list": tiendas_list,
        "filtros": {
            "tiendas": tiendas_list,
            "generos": lineas,
            "colores": colores,
        },
        "line_order": line_order,
        "stock": dict(stock),
        "stock_by_store": {k: dict(v) for k, v in stock_by_store.items()},
        "stores_order": stores_order,
        "raw_rows": raw_rows,
        "_meta": {
            "returns_rows": returns_count,
            "returns_units": returns_units,
        },
    }


def build_html(data: dict) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    payload = {k: v for k, v in data.items() if not k.startswith("_")}
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return re.sub(
        r"const DATA = \{.*?\};",
        f"const DATA = {data_json};",
        template,
        count=1,
        flags=re.DOTALL,
    )


def main():
    data = build_data()
    OUTPUT_PATH.write_text(build_html(data), encoding="utf-8")
    meta = data.get("_meta", {})
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Total ventas netas: {data['total']}")
    print(f"Devoluciones: {meta.get('returns_rows', 0)} filas / {meta.get('returns_units', 0)} und")
    print(f"Periodo: {data['periodo']}")
    print(f"Meses: {len(data['meses_order'])}")
    print(f"Raw rows: {len(data['raw_rows'])}")
    print(f"Stock total: {sum(data['stock'].values())}")
    print(f"Line order: {data['line_order']}")
    print(f"Partial month: {data['es_parcial']}")


if __name__ == "__main__":
    main()
