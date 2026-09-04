#!/usr/bin/env python3
"""Genera Excel de rango de producción Short Playa Sublimado.

Mínimo = cantidades establecidas en el dashboard (compromiso de producción).
Máximo = techo de acción hacia arriba, aprovechando tela adicional sin sobrestock.
"""

import json
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HTML_PATH = Path(__file__).resolve().parent / "SHORT PLAYA SUBL.html"
OUTPUT_PATH = Path(__file__).resolve().parent / "SHORT_PLAYA_SUBL_RANGO_PRODUCCION.xlsx"

MODELO = "SHORT PLAYA SUBLIMADO"
TORD = {
    "XS": 0, "S": 1, "M": 2, "L": 3, "XL": 4, "2XL": 5, "3XL": 6,
    "1": 10, "2": 11, "4": 12, "6": 13, "8": 14, "10": 15, "12": 16, "14": 17,
}
COLOR_ORDER = ["Playuela", "Sal", "Tucupido", "Sombrero", "Nuevo color"]
MAX_COVERAGE_MONTHS = 6
# Colchón hacia arriba cuando hay tela disponible (diciembre, carnaval, tiendas nuevas)
MAX_PCT_ABOVE_MIN = 1.15

title_fill = PatternFill("solid", fgColor="6ABF4A")
sub_fill = PatternFill("solid", fgColor="A8D5A2")
color_fill = PatternFill("solid", fgColor="E2F0E4")
tot_fill = PatternFill("solid", fgColor="C8E6C9")
min_fill = PatternFill("solid", fgColor="FFF9C4")
max_fill = PatternFill("solid", fgColor="FFE0B2")
white_fill = PatternFill("solid", fgColor="FFFFFF")
thin = Side(style="thin", color="2D5016")
border = Border(left=thin, right=thin, top=thin, bottom=thin)
center = Alignment(horizontal="center", vertical="center")
left = Alignment(horizontal="left", vertical="center", wrap_text=True)


def load_data() -> dict:
    html = HTML_PATH.read_text(encoding="utf-8")
    match = re.search(r"var DATA=(\{.*?\});", html, re.DOTALL)
    return json.loads(match.group(1))


def merge_rows(data: dict, genero: str) -> list:
    plan = [r for r in data["production_plan"] if r["modelo"] == MODELO and r["genero"] == genero]
    launch = [r for r in data.get("launch_production_plan", []) if r["modelo"] == MODELO and r["genero"] == genero]
    merged = {r["color"]: r for r in plan}
    for row in launch:
        merged[row["color"]] = row

    def sort_key(row):
        color = row["color"]
        if color in COLOR_ORDER:
            return (0, COLOR_ORDER.index(color))
        return (1, color)

    return sorted(merged.values(), key=sort_key)


def calc_range(talla_row: dict, is_launch: bool = False) -> tuple[int, int]:
    """Mínimo = cantidad establecida (dashboard). Máximo = techo con tela adicional."""
    mn = int(talla_row.get("produce", 0) or 0)
    if mn <= 0:
        return 0, 0

    v_mes = float(talla_row.get("v_mes", 0) or 0)
    stk = int(talla_row.get("stk", 0) or 0)

    cap_coverage = max(0, round(v_mes * MAX_COVERAGE_MONTHS - stk)) if v_mes > 0 else mn
    pct = MAX_PCT_ABOVE_MIN + (0.05 if is_launch else 0)  # +5% extra techo en lanzamiento
    cap_pct = max(0, round(mn * pct))
    mx = min(cap_coverage, cap_pct)
    mx = max(mx, mn)
    return mn, mx


def style_cell(cell, fill=None, bold=False, align=center):
    if fill:
        cell.fill = fill
    if bold:
        cell.font = Font(bold=True)
    cell.alignment = align
    cell.border = border


def write_genero_sheet(ws, genero: str, rows: list):
    talla_set = set()
    for row in rows:
        for t in row["tallas"]:
            talla_set.add(t["talla"])
    tallas = sorted(talla_set, key=lambda t: TORD.get(t, 99))
    ncol = 1 + len(tallas) * 2

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(row=1, column=1, value="CANTIDADES POR COLORES — MÍNIMO Y MÁXIMO")
    style_cell(c, title_fill, bold=True)

    ws.cell(row=2, column=1, value=f"SHORT PLAYA SUBLIMADO {genero}").font = Font(bold=True, italic=True)
    style_cell(ws.cell(row=2, column=1), sub_fill, align=left)

    col = 2
    for talla in tallas:
        ws.merge_cells(start_row=2, start_column=col, end_row=2, end_column=col + 1)
        h = ws.cell(row=2, column=col, value=talla)
        style_cell(h, sub_fill, bold=True)
        for off, label, fill in [(0, "Mín", min_fill), (1, "Máx", max_fill)]:
            sub = ws.cell(row=3, column=col + off, value=label)
            style_cell(sub, fill, bold=True)
        col += 2

    totals = {"min": 0, "max": 0}
    r_idx = 4
    for cp in rows:
        tmap = {t["talla"]: t for t in cp["tallas"]}
        label = cp["color"] + (" (lanzamiento)" if cp.get("is_launch") else "")
        style_cell(ws.cell(row=r_idx, column=1, value=label), color_fill, bold=True, align=left)

        row_min = row_max = 0
        col = 2
        for talla in tallas:
            t = tmap.get(talla, {"talla": talla, "produce": 0, "v_mes": 0, "stk": 0})
            mn, mx = calc_range(t, is_launch=bool(cp.get("is_launch")))
            for off, val, fill in [(0, mn, min_fill), (1, mx, max_fill)]:
                cell = ws.cell(row=r_idx, column=col + off, value=val if val else None)
                style_cell(cell, white_fill if val else fill)
                if val:
                    cell.font = Font(bold=True)
            row_min += mn
            row_max += mx
            col += 2

        totals["min"] += row_min
        totals["max"] += row_max
        r_idx += 1

    style_cell(ws.cell(row=r_idx, column=1, value="TOTAL"), tot_fill, bold=True, align=left)
    style_cell(ws.cell(row=r_idx, column=2, value=totals["min"]), tot_fill, bold=True)
    style_cell(ws.cell(row=r_idx, column=3, value=totals["max"]), tot_fill, bold=True)

    ws.column_dimensions["A"].width = 24
    for i in range(2, ncol + 1):
        ws.column_dimensions[get_column_letter(i)].width = 8

    return totals


def write_resumen(wb, data: dict, summary: dict):
    ws = wb.create_sheet("Resumen", 0)
    hs = data.get("high_season_factor", 1.4)
    rows = [
        ["SHORT PLAYA SUBLIMADO — RANGO DE PRODUCCIÓN"],
        [],
        ["Fuente", "Dashboard cursor/short-playa-launch-color-b710"],
        ["Factor temporada alta", hs],
        ["Peso diciembre en rotación base", data.get("dec_base_factor", 1.4)],
        ["Lead time / cobertura solicitada", f"{data.get('lead_months', 3)} meses"],
        ["Tiendas nuevas consideradas", ", ".join(data.get("new_stores", ["VELA", "BARQUISIMETO"]))],
        ["Ramp-up tiendas nuevas (lanzamiento)", f"{int((data.get('launch_new_store_uptake', 0.7) or 0.7) * 100)}%"],
        [],
        ["Género", "Mínimo (compromiso)", "Máximo (con tela adicional)"],
        ["CAB", summary["CAB"]["min"], summary["CAB"]["max"]],
        ["KIDS", summary["KIDS"]["min"], summary["KIDS"]["max"]],
        ["TOTAL", summary["TOTAL"]["min"], summary["TOTAL"]["max"]],
        [],
        ["Notas"],
        ["• Mínimo = cantidades establecidas en el dashboard (compromiso de producción)."],
        ["• Máximo = techo si hay tela disponible (hasta +15% o 6 meses cobertura, lo que sea menor)."],
        ["• La diferencia entre Mín y Máx es el rango de acción hacia arriba."],
        ["• Incluye color de lanzamiento y proyección temporada alta / tiendas nuevas."],
    ]
    for r, row in enumerate(rows, start=1):
        for c, val in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            if r == 1:
                cell.font = Font(bold=True, size=13)
            if r == 10:
                cell.font = Font(bold=True)
                cell.fill = sub_fill
    ws.column_dimensions["A"].width = 42
    for col in "BCD":
        ws.column_dimensions[col].width = 18


def write_metodologia(wb, data: dict):
    ws = wb.create_sheet("Metodología")
    hs = data.get("high_season_factor", 1.4)
    text = [
        "METODOLOGÍA — MÍNIMO Y MÁXIMO SHORT PLAYA SUBLIMADO",
        "",
        "1. MÍNIMO (compromiso de producción)",
        "   Son las cantidades establecidas en el dashboard por color y talla.",
        "   Representan lo que SÍ hay que fabricar sí o sí: curva óptima, cobertura 3 meses,",
        "   factor temporada alta (×{hs}), diciembre ponderado, tiendas nuevas (VELA, Barquisimeto)",
        "   y color de lanzamiento.".format(hs=hs),
        "",
        "2. MÁXIMO (rango de acción hacia arriba)",
        "   Si hay tela disponible que hoy está parada, producción puede subir HASTA el máximo.",
        "   El techo es el menor entre:",
        "   a) Mínimo + 15% (20% en color de lanzamiento)",
        "   b) Unidades para no superar 6 meses de cobertura por talla (anti sobrestock).",
        "",
        "3. LÓGICA DE LA REUNIÓN",
        "   • El mínimo cubre disponibilidad en red (diciembre, enero, carnaval).",
        "   • El máximo permite aprovechar tela adicional sin dejarla idle ni inflar inventario.",
        "   • Producción decide cuánto fabricar entre Mín y Máx según tela y capacidad del mes.",
        "   • Lo fabricado se distribuye y mueve entre tiendas para cubrir huecos.",
        "",
        "4. EJEMPLO",
        "   Si Mín = 41 und talla M color nuevo y Máx = 47 und → hay 6 und de margen",
        "   para usar tela extra si el pico festivo lo justifica.",
    ]
    for r, line in enumerate(text, start=1):
        cell = ws.cell(row=r, column=1, value=line)
        if line.startswith(("METODOLOGÍA", "1.", "2.", "3.", "4.", "5.")):
            cell.font = Font(bold=True)
    ws.column_dimensions["A"].width = 95


def main():
    data = load_data()
    wb = Workbook()
    wb.remove(wb.active)

    summary = {}
    for genero in ["CAB", "KIDS"]:
        rows = merge_rows(data, genero)
        ws = wb.create_sheet(genero)
        totals = write_genero_sheet(ws, genero, rows)
        summary[genero] = totals

    summary["TOTAL"] = {
        k: summary["CAB"][k] + summary["KIDS"][k] for k in ("min", "max")
    }
    write_resumen(wb, data, summary)
    write_metodologia(wb, data)
    wb.save(OUTPUT_PATH)
    print(f"Guardado: {OUTPUT_PATH}")
    print(f"CAB:  mín {summary['CAB']['min']} — máx {summary['CAB']['max']}")
    print(f"KIDS: mín {summary['KIDS']['min']} — máx {summary['KIDS']['max']}")
    print(f"TOTAL:mín {summary['TOTAL']['min']} — máx {summary['TOTAL']['max']}")


if __name__ == "__main__":
    main()
