#!/usr/bin/env python3
"""Generate Short Playa Sublimado production proposal Excel (MÍN / MÁX format)."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
TEAM_XLSX = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/"
    "CANTIDAD_SUGERIDAS_PARA_PRODUCIR_ADAPTAR_A_CURVA_f9a8.xlsx"
)
DASHBOARD_HTML = ROOT / "DASHBOARD SHORTS PLAYA ALL.html"
OUTPUT_XLSX = ROOT / "PROPUESTA_PRODUCCION_SUBLIMADO_ACTUALIZADA.xlsx"

HIGH_SEASON_FACTOR = 1.2
UPLIFT_TEMPORADA = 1.22
UPLIFT_MARGARITA = 1.08
UPLIFT_TOTAL = UPLIFT_TEMPORADA * UPLIFT_MARGARITA
MIN_SIZE_QTY = 4

CAB_SIZES = ["S", "M", "L", "XL", "2XL"]
CAB_CURVE = {"S": 1, "M": 5, "L": 6, "XL": 3, "2XL": 2}

KIDS_SIZES = ["2", "4", "6", "8", "10", "12", "14"]
KIDS_CURVE = {"2": 1, "4": 2, "6": 2, "8": 2, "10": 2, "12": 2, "14": 3}

COLORS = ["Playuela", "Sal", "Tucupido", "Nuevo color"]
COLOR_ALIASES = {
    "Sal (Cayo Sal)": "Sal",
    "Nuevo Diseño": "Nuevo color",
    "Nuevo color 🆕": "Nuevo color",
}

HEADER_FILL = PatternFill("solid", fgColor="1F2937")
MIN_TOTAL_FILL = PatternFill("solid", fgColor="D1FAE5")
MAX_TOTAL_FILL = PatternFill("solid", fgColor="FDE68A")
BLUE_FONT = Font(color="0000FF")
WHITE_BOLD = Font(bold=True, color="FFFFFF")
BOLD = Font(bold=True)


def normalize_color(name: str) -> str:
    name = (name or "").strip()
    if name in COLOR_ALIASES:
        return COLOR_ALIASES[name]
    return name.replace(" 🆕", "").strip()


def enforce_min_qty(qty: int) -> int:
    if qty <= 0:
        return 0
    return max(MIN_SIZE_QTY, qty)


def load_team_base() -> dict[str, dict[str, dict[str, int]]]:
    wb = openpyxl.load_workbook(TEAM_XLSX, data_only=True)
    out: dict[str, dict[str, dict[str, int]]] = {"CAB": {}, "KIDS": {}}
    for genero, sizes in [("CAB", CAB_SIZES), ("KIDS", KIDS_SIZES)]:
        ws = wb[genero]
        for r in range(3, ws.max_row + 1):
            color = normalize_color(str(ws.cell(r, 1).value or ""))
            if not color or color.upper() == "TOTAL":
                continue
            row: dict[str, int] = {}
            for i, size in enumerate(sizes, start=2):
                val = ws.cell(r, i).value
                row[size] = int(val) if val not in (None, "") else 0
            out[genero][color] = row
    return out


def load_dashboard_produce() -> dict[str, dict[str, dict[str, int]]]:
    html = DASHBOARD_HTML.read_text(encoding="utf-8")
    match = re.search(r"var DATA=(\{.*?\});", html, re.DOTALL)
    if not match:
        return {"CAB": {}, "KIDS": {}}
    data = json.loads(match.group(1))
    out: dict[str, dict[str, dict[str, int]]] = {"CAB": {}, "KIDS": {}}
    for item in data.get("production_plan", []):
        if item.get("modelo") != "SHORT PLAYA SUBLIMADO":
            continue
        genero = item["genero"]
        color = normalize_color(item["color"])
        if color not in COLORS:
            continue
        row = out[genero].setdefault(color, {})
        for t in item.get("tallas", []):
            qty = int(round(t.get("produce", 0)))
            if qty > 0:
                row[t["talla"]] = max(row.get(t["talla"], 0), qty)
    launch = data.get("launch_production_plan") or []
    for item in launch:
        if item.get("modelo") != "SHORT PLAYA SUBLIMADO":
            continue
        color = normalize_color(item.get("color", ""))
        if color != "Nuevo color":
            continue
        genero = item["genero"]
        row = out[genero].setdefault(color, {})
        for t in item.get("tallas", []):
            qty = int(round(t.get("produce", 0)))
            if qty > 0:
                row[t["talla"]] = max(row.get(t["talla"], 0), qty)
    return out


def distribute_curve(total: int, sizes: list[str], curve: dict[str, int]) -> dict[str, int]:
    weights = [curve[s] for s in sizes]
    wsum = sum(weights) or 1
    result: dict[str, int] = {}
    allocated = 0
    for i, size in enumerate(sizes):
        if i == len(sizes) - 1:
            qty = total - allocated
        else:
            qty = int(round(total * curve[size] / wsum))
        result[size] = qty
        allocated += qty
    return result


def uplift_team_row(team_row: dict[str, int], sizes: list[str]) -> dict[str, int]:
    out = {s: 0 for s in sizes}
    for size in sizes:
        base = team_row.get(size, 0)
        if base > 0:
            out[size] = enforce_min_qty(int(round(base * UPLIFT_TOTAL)))
    return out


def merge_suggested(
    genero: str,
    team: dict[str, dict[str, int]],
    dashboard: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]]:
    sizes = CAB_SIZES if genero == "CAB" else KIDS_SIZES
    curve = CAB_CURVE if genero == "CAB" else KIDS_CURVE
    suggested: dict[str, dict[str, int]] = {}

    for color in COLORS:
        team_row = team.get(genero, {}).get(color, {s: 0 for s in sizes})
        dash_row = dashboard.get(genero, {}).get(color, {})
        row = uplift_team_row(team_row, sizes)

        for size in sizes:
            dash_qty = dash_row.get(size, 0)
            if dash_qty > 0:
                row[size] = max(row[size], enforce_min_qty(dash_qty))

        team_total = sum(team_row.get(s, 0) for s in sizes)
        has_team_sizes = {s for s in sizes if team_row.get(s, 0) > 0}
        dash_sizes = {s for s in sizes if dash_row.get(s, 0) > 0}

        if color == "Nuevo color" and team_total > 0:
            target = enforce_min_qty(int(round(team_total * UPLIFT_TOTAL)))
            if sum(row.values()) < target:
                curved = distribute_curve(target, sizes, curve)
                for size in sizes:
                    row[size] = max(row[size], enforce_min_qty(curved[size]))
        elif team_total > 0:
            missing = [s for s in sizes if row[s] == 0 and s not in has_team_sizes]
            fill_sizes = [s for s in missing if s in dash_sizes]
            if not fill_sizes and color in ("Playuela", "Sal"):
                fill_sizes = [s for s in missing if s in {"S", "2", "4", "6", "8"}]
            if fill_sizes:
                known_total = sum(row[s] for s in sizes)
                extra = max(0, enforce_min_qty(int(round(team_total * UPLIFT_TOTAL))) - known_total)
                if extra > 0:
                    sub_curve = {s: curve[s] for s in fill_sizes}
                    filled = distribute_curve(extra, fill_sizes, sub_curve)
                    for size in fill_sizes:
                        row[size] = enforce_min_qty(filled[size])
                else:
                    for size in fill_sizes:
                        row[size] = MIN_SIZE_QTY

        for size in sizes:
            row[size] = enforce_min_qty(row[size]) if row[size] > 0 else 0

        suggested[color] = row

    return suggested


def col_letter(idx: int) -> str:
    return get_column_letter(idx)


def write_range_sheet(
    wb: openpyxl.Workbook,
    genero: str,
    suggested: dict[str, dict[str, int]],
) -> None:
    sizes = CAB_SIZES if genero == "CAB" else KIDS_SIZES
    ws = wb.create_sheet(genero)
    title = f"Rango de producción MÍNIMO / MÁXIMO — Short Playa Sublimado ({genero})"
    ws["A1"] = title
    ws["A1"].font = BOLD
    ws["A3"] = "Factor de temporada alta"
    ws["A3"].font = BOLD
    ws["B3"] = HIGH_SEASON_FACTOR
    ws["B3"].font = BLUE_FONT

    header_row = 5
    ws.cell(header_row, 1, "Color").font = WHITE_BOLD
    ws.cell(header_row, 1).fill = HEADER_FILL
    for i, size in enumerate(sizes, start=2):
        cell = ws.cell(header_row, i, size)
        cell.font = WHITE_BOLD
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
    total_col = len(sizes) + 2
    cell = ws.cell(header_row, total_col, "Total")
    cell.font = WHITE_BOLD
    cell.fill = HEADER_FILL
    cell.alignment = Alignment(horizontal="center")

    min_rows: list[int] = []
    max_rows: list[int] = []
    row_idx = 6
    factor_ref = "$B$3"
    first_data_col = 2
    last_data_col = len(sizes) + 1

    for color in COLORS:
        min_row = row_idx
        min_rows.append(min_row)
        ws.cell(min_row, 1, f"{color} — MÍNIMO").font = BOLD
        row_data = suggested[color]
        for i, size in enumerate(sizes, start=2):
            qty = row_data.get(size, 0)
            cell = ws.cell(min_row, i)
            if qty > 0:
                cell.value = qty
                cell.font = BLUE_FONT
                cell.alignment = Alignment(horizontal="center")
        ws.cell(min_row, total_col, f"=SUM({col_letter(first_data_col)}{min_row}:{col_letter(last_data_col)}{min_row})")
        ws.cell(min_row, total_col).font = BOLD
        ws.cell(min_row, total_col).alignment = Alignment(horizontal="center")

        max_row = row_idx + 1
        max_rows.append(max_row)
        ws.cell(max_row, 1, f"{color} — MÁXIMO ")
        for i in range(first_data_col, last_data_col + 1):
            min_ref = f"{col_letter(i)}{min_row}"
            cell = ws.cell(max_row, i, f'=IF({min_ref}="","",ROUND({min_ref}*{factor_ref},0))')
            cell.alignment = Alignment(horizontal="center")
        ws.cell(max_row, total_col, f"=SUM({col_letter(first_data_col)}{max_row}:{col_letter(last_data_col)}{max_row})")
        ws.cell(max_row, total_col).alignment = Alignment(horizontal="center")
        row_idx += 2

    total_min_row = row_idx
    total_max_row = row_idx + 1
    ws.cell(total_min_row, 1, "TOTAL — MÍNIMO").font = BOLD
    ws.cell(total_max_row, 1, "TOTAL — MÁXIMO").font = BOLD
    for r, fill, src_rows in [
        (total_min_row, MIN_TOTAL_FILL, min_rows),
        (total_max_row, MAX_TOTAL_FILL, max_rows),
    ]:
        ws.cell(r, 1).fill = fill
        for i in range(first_data_col, last_data_col + 1):
            letter = col_letter(i)
            if r == total_min_row:
                formula = "+".join(f"{letter}{mr}" for mr in src_rows)
            else:
                formula = "+".join(f"{letter}{mr}" for mr in max_rows)
            cell = ws.cell(r, i, f"={formula}")
            cell.font = BOLD
            cell.fill = fill
            cell.alignment = Alignment(horizontal="center")
        total_letter = col_letter(total_col)
        if r == total_min_row:
            g_formula = "+".join(f"{total_letter}{mr}" for mr in src_rows)
        else:
            g_formula = "+".join(f"{total_letter}{mr}" for mr in max_rows)
        cell = ws.cell(r, total_col, f"={g_formula}")
        cell.font = BOLD
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center")

    ws.column_dimensions["A"].width = 28
    for i in range(first_data_col, total_col + 1):
        ws.column_dimensions[col_letter(i)].width = 10


def sum_matrix(rows: dict[str, dict[str, int]], sizes: list[str]) -> int:
    return sum(rows[c].get(s, 0) for c in rows for s in sizes)


def write_resumen(
    wb: openpyxl.Workbook,
    team: dict[str, dict[str, dict[str, int]]],
    suggested: dict[str, dict[str, dict[str, int]]],
) -> None:
    ws = wb.create_sheet("Resumen", 0)
    ws.append(
        [
            "Género",
            "Propuesta equipo",
            "SUGERIDO (MÍN)",
            "MÁXIMO",
            "Rango",
            "Δ vs equipo",
        ]
    )
    for genero, sizes in [("CAB", CAB_SIZES), ("KIDS", KIDS_SIZES)]:
        team_total = sum_matrix(team[genero], sizes)
        sug_total = sum_matrix(suggested[genero], sizes)
        max_total = sum(
            math.ceil(suggested[genero][c].get(s, 0) * HIGH_SEASON_FACTOR)
            for c in COLORS
            for s in sizes
            if suggested[genero][c].get(s, 0) > 0
        )
        ws.append([genero, team_total, sug_total, max_total, max_total - sug_total, sug_total - team_total])
    cab_min = ws["C2"].value or 0
    kids_min = ws["C3"].value or 0
    cab_max = ws["D2"].value or 0
    kids_max = ws["D3"].value or 0
    team_tot = (ws["B2"].value or 0) + (ws["B3"].value or 0)
    ws.append(["TOTAL", team_tot, cab_min + kids_min, cab_max + kids_max, (cab_max + kids_max) - (cab_min + kids_min), (cab_min + kids_min) - team_tot])
    ws["A1"].font = BOLD


def write_comp_sheet(
    wb: openpyxl.Workbook,
    genero: str,
    team: dict[str, dict[str, dict[str, int]]],
    suggested: dict[str, dict[str, int]],
) -> None:
    sizes = CAB_SIZES if genero == "CAB" else KIDS_SIZES
    ws = wb.create_sheet(f"Comp_{genero}")
    ws.append(["Color", "Talla", "Equipo", "Sugerido (MÍN)", "Cambio"])
    for color in COLORS:
        for size in sizes:
            eq = team[genero].get(color, {}).get(size, 0)
            sug = suggested[color].get(size, 0)
            if eq > 0 or sug > 0:
                ws.append([color, size, eq, sug, sug - eq])


def main() -> None:
    team = load_team_base()
    dashboard = load_dashboard_produce()
    suggested = {
        "CAB": merge_suggested("CAB", team, dashboard),
        "KIDS": merge_suggested("KIDS", team, dashboard),
    }

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    write_resumen(wb, team, suggested)
    write_range_sheet(wb, "CAB", suggested["CAB"])
    write_range_sheet(wb, "KIDS", suggested["KIDS"])
    write_comp_sheet(wb, "CAB", team, suggested["CAB"])
    write_comp_sheet(wb, "KIDS", team, suggested["KIDS"])
    wb.save(OUTPUT_XLSX)

    cab_total = sum_matrix(suggested["CAB"], CAB_SIZES)
    kids_total = sum_matrix(suggested["KIDS"], KIDS_SIZES)
    print(f"Saved {OUTPUT_XLSX}")
    print(f"CAB MÍN total: {cab_total} | KIDS MÍN total: {kids_total} | TOTAL: {cab_total + kids_total}")
    print(f"Min per size rule: {MIN_SIZE_QTY} | Uplift: ×{UPLIFT_TOTAL:.4f} | MÁX factor: ×{HIGH_SEASON_FACTOR}")


if __name__ == "__main__":
    main()
