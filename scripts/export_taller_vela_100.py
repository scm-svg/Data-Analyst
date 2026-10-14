#!/usr/bin/env python3
"""
Orden de producción interna — Taller → LA VELA (100 und urgentes).

Uso:
  python scripts/export_taller_vela_100.py
  python scripts/export_taller_vela_100.py --qty 100
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "short_playa.html"
OUT_XLSX = ROOT / "SHORT_PLAYA_TALLER_VELA_100und.xlsx"

MODELO = "Short Playa"
DESTINO = "LA VELA"
FABRIC_M = 0.75
BATCH_QTY = 100
TOP_COLORS_BATCH = 5  # primer lote urgente — solo los más críticos en VELA
VELOCITY_MONTHS = 6
HIGH_SEASON = 1.25

PRODUCTION_TALLAS = ["XS", "S", "M", "L", "XL", "2XL"]
FIXED_TALLA_PCT = {"XS": 0, "S": 12, "M": 25, "L": 32, "XL": 18, "2XL": 13}

PRODUCT_TO_TELA = {
    "Aguamarina": "Aguamarina",
    "Verde Oliva": "Verde Oliva",
    "Azul Marino": "Azul Marino",
    "Gris Azulado": "Gris Azulado",
    "Marron": "Habano",
    "Azul Pizarra": "Azul Pizzarra",
    "Azul Verdoso": "Azul Verdoso",
    "Verde Pino": "Verde Pino",
    "Cereza": "Rojo",
}

# Colores activos liso — prioridad VELA por rotación playa
ACTIVE_COLORS = [
    "Azul Pizarra", "Verde Pino", "Marron", "Cereza", "Azul Verdoso",
    "Azul Marino", "Gris Azulado", "Verde Oliva", "Aguamarina",
]


def load_data() -> dict:
    text = HTML.read_text(encoding="utf-8")
    m = re.search(r"var DATA = (\{.*?\});\s*\nvar", text, re.DOTALL)
    if not m:
        raise SystemExit("No DATA en short_playa.html")
    return json.loads(m.group(1))


def largest_remainder(weights: dict[str, float], total: int) -> dict[str, int]:
    if total <= 0:
        return {k: 0 for k in weights}
    s = sum(weights.values()) or 1
    raw = {k: weights[k] / s * total for k in weights}
    floor = {k: int(math.floor(raw[k] + 1e-9)) for k in weights}
    used = sum(floor.values())
    frac = sorted(weights.keys(), key=lambda k: raw[k] - floor[k], reverse=True)
    i = 0
    while used < total and frac:
        floor[frac[i % len(frac)]] += 1
        used += 1
        i += 1
    return floor


def distribute_tallas(total: int) -> dict[str, int]:
    weights = {t: FIXED_TALLA_PCT[t] for t in PRODUCTION_TALLAS if FIXED_TALLA_PCT[t] > 0}
    out = largest_remainder(weights, total)
    return {t: out.get(t, 0) for t in PRODUCTION_TALLAS}


def vela_color_priority(data: dict) -> list[tuple[str, float, int, float]]:
    """color, score, vela_stock, vela_vel/mes"""
    months = data.get("meses_order", [])[-VELOCITY_MONTHS:]
    by_color: dict[str, dict] = {}

    for s in data.get("sku_master", []):
        if s.get("genero") != "CAB" or s.get("modelo") != MODELO:
            continue
        col = s.get("color")
        if col not in ACTIVE_COLORS:
            continue
        c = by_color.setdefault(col, {"vela_inv": 0, "vela_vel": 0.0, "urgent": 0})
        vela_inv = int(s.get("inv_by_store", {}).get("LA VELA", 0) or 0)
        c["vela_inv"] += max(0, vela_inv)
        by_m = s.get("ventas_by_mes") or {}
        vel = sum(by_m.get(m, 0) for m in months) / max(len(months), 1) * HIGH_SEASON
        c["vela_vel"] += vel
        vela_sales = s.get("ventas_by_store", {}).get("LA VELA", 0) or 0
        if vela_inv <= 1 and vela_sales >= 1:
            c["urgent"] += 2
        elif vel > 0 and vela_inv / vel < 2:
            c["urgent"] += 1

    rows = []
    for col, c in by_color.items():
        score = c["vela_vel"] * 2 + c["urgent"] * 5 + max(0, 20 - c["vela_inv"])
        rows.append((col, score, c["vela_inv"], round(c["vela_vel"], 1)))
    rows.sort(key=lambda x: -x[1])
    return rows


def allocate_colors(
    total: int,
    priorities: list[tuple[str, float, int, float]],
    max_colors: int = TOP_COLORS_BATCH,
) -> dict[str, int]:
    """Reparte und por color según urgencia VELA (top N colores críticos)."""
    if not priorities:
        return {}
    top = priorities[:max_colors]
    scores = {col: max(score, 0.1) for col, score, _, _ in top}
    colors = [col for col, _, _, _ in top if col in ACTIVE_COLORS]
    weights = {c: scores[c] for c in colors}
    return largest_remainder(weights, total)


def find_sku(data: dict, color: str, talla: str) -> str:
    for s in data.get("sku_master", []):
        if (
            s.get("genero") == "CAB"
            and s.get("modelo") == MODELO
            and s.get("color") == color
            and s.get("talla") == talla
        ):
            return s.get("sku") or ""
    return ""


def build_order(data: dict, qty: int) -> dict:
    priorities = vela_color_priority(data)
    color_qty = allocate_colors(qty, priorities)

    lines = []
    color_talla: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    talla_totals = defaultdict(int)
    tela_m = defaultdict(float)

    for col in [c for c, _, _, _ in priorities if c in color_qty]:
        ctotal = color_qty[col]
        if ctotal <= 0:
            continue
        by_talla = distribute_tallas(ctotal)
        for t, n in by_talla.items():
            if n <= 0:
                continue
            sku = find_sku(data, col, t)
            color_talla[col][t] = n
            talla_totals[t] += n
            tela = PRODUCT_TO_TELA.get(col, col)
            tela_m[tela] += n * FABRIC_M
            lines.append({
                "sku": sku,
                "modelo": MODELO,
                "color": col,
                "tela": tela,
                "talla": t,
                "qty": n,
                "metros": round(n * FABRIC_M, 2),
                "destino": DESTINO,
            })

    return {
        "qty": qty,
        "destino": DESTINO,
        "fecha": date.today().isoformat(),
        "priorities": priorities,
        "color_qty": color_qty,
        "color_talla": dict(color_talla),
        "talla_totals": dict(talla_totals),
        "tela_m": dict(tela_m),
        "lines": lines,
        "total_m": round(sum(tela_m.values()), 2),
    }


def export_excel(order: dict, path: Path) -> None:
    import xlsxwriter

    wb = xlsxwriter.Workbook(str(path))
    title = wb.add_format({"bold": True, "font_size": 14, "font_color": "#ef4444"})
    bold = wb.add_format({"bold": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#ef4444", "font_color": "white"})
    wrap = wb.add_format({"text_wrap": True, "valign": "top"})

    # ── 1. Orden Taller ──
    ws = wb.add_worksheet("Orden Taller")
    row = 0
    ws.write(row, 0, f"PRODUCCIÓN INTERNA TALLER → {order['destino']} ★", title)
    row += 1
    ws.write(
        row, 0,
        f"Lote urgente: {order['qty']} piezas · Top {TOP_COLORS_BATCH} colores críticos VELA · {order['fecha']}",
        bold,
    )
    row += 1
    ws.write(
        row, 0,
        "Curva talla: S 12% · M 25% · L 32% · XL 18% · 2XL 13% · Consumo 0,75 m/pza",
        wrap,
    )
    row += 2
    ws.write_row(row, 0, ["Prioridad VELA — color", "Score", "Stock VELA", "Vel/mes VELA", "Und lote"], hdr)
    row += 1
    for col, score, stk, vel in order["priorities"]:
        if col not in order["color_qty"]:
            continue
        ws.write_row(row, 0, [col, round(score, 1), stk, vel, order["color_qty"].get(col, 0)])
        row += 1
    row += 1
    active_tallas = [t for t in PRODUCTION_TALLAS if order["talla_totals"].get(t, 0) > 0]
    ws.write_row(row, 0, ["Color / Tela"] + active_tallas + ["Total"], hdr)
    row += 1
    for col in sorted(order["color_talla"].keys(), key=lambda c: -order["color_qty"].get(c, 0)):
        tela = PRODUCT_TO_TELA.get(col, col)
        ct = order["color_talla"][col]
        ws.write_row(
            row, 0,
            [f"{col} ({tela})"] + [ct.get(t, 0) for t in active_tallas] + [sum(ct.values())],
        )
        row += 1
    ws.write_row(
        row, 0,
        ["TOTAL TALLA"] + [order["talla_totals"].get(t, 0) for t in active_tallas] + [order["qty"]],
        bold,
    )

    # ── 2. Detalle SKU ──
    ws = wb.add_worksheet("Detalle SKU")
    row = 0
    ws.write(row, 0, "DETALLE POR SKU — enviar a LA VELA", title)
    row += 2
    ws.write_row(row, 0, ["#", "SKU", "Color", "Tela", "Talla", "Und", "Metros", "Destino"], hdr)
    row += 1
    for i, ln in enumerate(sorted(order["lines"], key=lambda x: (-order["color_qty"][x["color"]], x["color"], x["talla"])), 1):
        ws.write_row(row, 0, [
            i, ln["sku"], ln["color"], ln["tela"], ln["talla"], ln["qty"], ln["metros"], ln["destino"],
        ])
        row += 1
    ws.write_row(row, 0, ["", "", "", "", "TOTAL", order["qty"], order["total_m"], ""], bold)

    # ── 3. Tela a cortar ──
    ws = wb.add_worksheet("Tela a cortar")
    row = 0
    ws.write(row, 0, "TELA A CORTAR EN TALLER", title)
    row += 2
    ws.write_row(row, 0, ["Tela", "Producto", "Und", "Metros", "Nota"], hdr)
    row += 1
    for tela, meters in sorted(order["tela_m"].items(), key=lambda x: -x[1]):
        prod = next((k for k, v in PRODUCT_TO_TELA.items() if v == tela), tela)
        und = int(round(meters / FABRIC_M))
        note = ""
        if prod == "Cereza":
            note = "Tela ROJO"
        elif prod == "Marron":
            note = "Tela HABANO"
        elif prod == "Azul Pizarra":
            note = "Tela AZUL PIZZARRA"
        ws.write_row(row, 0, [tela, prod, und, round(meters, 2), note])
        row += 1
    ws.write_row(row, 0, ["TOTAL", "", order["qty"], order["total_m"], ""], bold)

    # ── 4. Checklist envío ──
    ws = wb.add_worksheet("Checklist envío VELA")
    row = 0
    ws.write(row, 0, f"CHECKLIST — {order['qty']} und → LA VELA", title)
    row += 2
    checks = [
        "☐ Corte tela según hoja 'Tela a cortar'",
        "☐ Confección por color/talla según 'Detalle SKU'",
        "☐ Etiquetado SKU + talla",
        f"☐ Bulto marcado: SHORT PLAYA CAB · LA VELA · {order['qty']} und",
        "☐ Verificar prioridad: Azul Pizarra, Marron, Azul Verdoso, Verde Pino, Cereza",
        "☐ Despacho directo a LA VELA (playa — stock crítico)",
    ]
    for c in checks:
        ws.write(row, 0, c)
        row += 1
    row += 1
    ws.write(row, 0, "Resumen por talla:", bold)
    row += 1
    for t in PRODUCTION_TALLAS:
        q = order["talla_totals"].get(t, 0)
        if q:
            ws.write(row, 0, f"  {t}: {q} und ({FIXED_TALLA_PCT[t]}%)")
            row += 1

    wb.close()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--qty", type=int, default=BATCH_QTY)
    parser.add_argument("--out", default=str(OUT_XLSX))
    args = parser.parse_args()

    data = load_data()
    order = build_order(data, args.qty)
    export_excel(order, Path(args.out))

    print(f"✓ {args.out}")
    print(f"  {order['qty']} und → {order['destino']} · {order['total_m']} m tela")
    print("  Por color:")
    for col in sorted(order["color_qty"], key=lambda c: -order["color_qty"][c]):
        print(f"    {col}: {order['color_qty'][col]} und")
    print("  Por talla:", dict(order["talla_totals"]))


if __name__ == "__main__":
    main()
