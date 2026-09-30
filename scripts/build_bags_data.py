#!/usr/bin/env python3
"""Build DATA object for Bags dashboard from sales and inventory CSVs."""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

STORE_MAP = {
    "cerro verde": "CERRO VERDE",
    "sambil chacao": "CHACAO",
    "sambil valencia": "SAMBIL",
    "la grieta": "GRIE",
    "web": "WEB",
    "grandplaz": "GRAND",
    "tolon": "TOLON",
    "la vela": "LA VELA",
    "pedidos": "PEDIDOS",
    "grieta": "GRIE",
    "vela": "LA VELA",
    "chacao": "CHACAO",
    "sambil": "SAMBIL",
    "taller": "TALLER",
}

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def norm_store(value: str) -> str:
    return STORE_MAP.get(value.strip().lower(), value.strip().upper())


def parse_qty(value: str) -> float:
    return float(str(value).replace(",", "."))


def mes_key(value: str) -> tuple[int, int]:
    nombre, year = value.split("-")
    return int(year), MESES.index(nombre)


def ubic_col(columns: list[str]) -> str:
    for col in columns:
        if "ubic" in col.lower():
            return col
    raise KeyError("ubicacion column not found")


def load_sales(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    if not rows:
        return []

    store_col = ubic_col(list(rows[0].keys()))
    agg: dict[tuple, float] = defaultdict(float)

    for row in rows:
        qty = parse_qty(row["Cant. ordenada"])
        if qty == 0:
            continue
        key = (
            norm_store(row[store_col]),
            "UNICO",
            row["color"].strip(),
            "UNICA",
            row["fecha"].strip(),
            row["modelo"].strip(),
        )
        agg[key] += qty

    raw_rows = []
    for (tienda, genero, color, talla, mes, modelo), qty in sorted(agg.items()):
        units = int(round(qty))
        if units == 0:
            continue
        raw_rows.append(
            {
                "tienda": tienda,
                "genero": genero,
                "color": color,
                "talla": talla,
                "mes": mes,
                "modelo": modelo,
                "v": units,
            }
        )
    return raw_rows


def load_inventory(path: Path) -> tuple[dict[str, int], dict[str, int]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))

    stock_acc: dict[str, float] = defaultdict(float)
    for row in rows:
        qty = parse_qty(row["Cantidad en inventario"])
        key = f"{row['MODELO'].strip()}/UNICO/{row['COLOR'].strip()}/UNICA"
        stock_acc[key] += qty

    stock = {
        key: int(round(qty))
        for key, qty in sorted(stock_acc.items())
        if int(round(qty)) != 0
    }

    stock_by_modelo: dict[str, int] = defaultdict(int)
    for key, qty in stock.items():
        stock_by_modelo[key.split("/")[0]] += qty

    return stock, dict(sorted(stock_by_modelo.items()))


def build_data(sales_path: Path, inventory_path: Path) -> dict:
    raw_rows = load_sales(sales_path)
    stock, stock_by_modelo = load_inventory(inventory_path)

    meses_order = sorted({row["mes"] for row in raw_rows}, key=mes_key)
    meses_und = {mes: sum(row["v"] for row in raw_rows if row["mes"] == mes) for mes in meses_order}
    all_stores = sorted({row["tienda"] for row in raw_rows})
    modelos = sorted({row["modelo"] for row in raw_rows} | set(stock_by_modelo))
    colores = sorted({row["color"] for row in raw_rows})

    return {
        "raw_rows": raw_rows,
        "stock": stock,
        "stock_by_modelo": stock_by_modelo,
        "meses_order": meses_order,
        "meses_und": meses_und,
        "filtros": {
            "tiendas": all_stores,
            "generos": ["UNICO"],
            "colores": colores,
            "modelos": modelos,
        },
        "es_parcial": bool(meses_order) and meses_order[-1].endswith("-2026"),
        "stock_total": sum(stock.values()),
        "total": sum(row["v"] for row in raw_rows),
        "all_stores": all_stores,
    }


def inject_data(html_path: Path, data: dict) -> None:
    html = html_path.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    updated, count = re.subn(r"var DATA=\{[\s\S]*?\};", f"var DATA={payload};", html, count=1)
    if count != 1:
        raise RuntimeError("Could not replace DATA block in index.html")
    html_path.write_text(updated, encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    sales = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "uploads" / "modelos_bags_data_ventas22_4f93.csv"
    inventory = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "uploads" / "INVENTARIO_DE_MODELOS_BAGS_3930.csv"
    html_path = root / "index.html"

    data = build_data(sales, inventory)
    inject_data(html_path, data)
    print(json.dumps({
        "raw_rows": len(data["raw_rows"]),
        "total": data["total"],
        "stock_total": data["stock_total"],
        "modelos": data["filtros"]["modelos"],
        "meses": [data["meses_order"][0], data["meses_order"][-1]],
        "stores": data["all_stores"],
    }, indent=2))


if __name__ == "__main__":
    main()
