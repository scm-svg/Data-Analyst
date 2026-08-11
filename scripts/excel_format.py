"""Formateo visual para analisis_microfibra_jabon.xlsx."""

from __future__ import annotations

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(name="Calibri", bold=True, size=14, color="1F4E79")
SUBTITLE_FONT = Font(name="Calibri", bold=True, size=11, color="2E75B6")
SECTION_FILL = PatternFill("solid", fgColor="D6E4F0")
THIN = Side(style="thin", color="B4C6E7")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)

FILLS = {
    "ok": PatternFill("solid", fgColor="C6EFCE"),
    "warn": PatternFill("solid", fgColor="FFEB9C"),
    "crit": PatternFill("solid", fgColor="FFC7CE"),
    "info": PatternFill("solid", fgColor="DDEBF7"),
    "pedido": PatternFill("solid", fgColor="E2EFDA"),
    "abc_a": PatternFill("solid", fgColor="C6EFCE"),
    "abc_b": PatternFill("solid", fgColor="FFEB9C"),
    "abc_c": PatternFill("solid", fgColor="EDEDED"),
}


def _auto_width(ws, max_width=42):
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        length = max(len(str(c.value)) if c.value is not None else 0 for c in col)
        ws.column_dimensions[letter].width = min(max(length + 2, 10), max_width)


def _style_header_row(ws, row=1):
    for cell in ws[row]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
        cell.border = BORDER


def _add_table(ws, name: str, ref: str):
    tab = Table(displayName=name[:255], ref=ref)
    tab.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    ws.add_table(tab)


def format_workbook(path: str) -> None:
    wb = load_workbook(path)

    # --- Hoja 0: Resumen Ejecutivo ---
    ws = wb["0. Resumen Ejecutivo"]
    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 72
    ws["A1"].font = TITLE_FONT
    ws["A1"].fill = SECTION_FILL
    ws["A1"].alignment = LEFT
    ws.merge_cells("A1:B1")
    for row in range(3, ws.max_row + 1):
        ws[f"A{row}"].font = Font(bold=True, color="1F4E79")
        ws[f"A{row}"].fill = PatternFill("solid", fgColor="F2F2F2")
        ws[f"B{row}"].alignment = LEFT
        label = str(ws[f"A{row}"].value or "")
        if "Pedido tela" in label or "Crítico" in label:
            ws[f"B{row}"].fill = FILLS["pedido"]
            ws[f"B{row}"].font = Font(bold=True, color="006100")
        if "Top 5" in label:
            ws[f"B{row}"].fill = FILLS["info"]

    data_sheets = [
        "1. Resumen por Color",
        "2. Top 5 Logística",
        "3. Riesgo y Reorden",
        "4. Pedido Tela",
        "5. Resumen Modelos",
        "10. Semáforo Integrado",
        "11. Verificación y Notas",
    ]
    for sheet_name in data_sheets:
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        _style_header_row(ws, 1)
        ws.freeze_panes = "A2"
        if ws.max_row >= 2 and ws.max_column >= 1:
            ref = f"A1:{get_column_letter(ws.max_column)}{ws.max_row}"
            safe = sheet_name.replace(" ", "").replace(".", "")[:20]
            try:
                _add_table(ws, f"T_{safe}", ref)
            except ValueError:
                pass
        _auto_width(ws)

    # ABC badges
    if "1. Resumen por Color" in wb.sheetnames:
        ws = wb["1. Resumen por Color"]
        abc_col = None
        for cell in ws[1]:
            if cell.value == "ABC":
                abc_col = cell.column
                break
        if abc_col:
            for row in range(2, ws.max_row + 1):
                cell = ws.cell(row=row, column=abc_col)
                val = str(cell.value or "")
                cell.fill = FILLS.get(f"abc_{val.lower()}", FILLS["info"])
                cell.font = Font(bold=True)
                cell.alignment = CENTER

    # Riesgo colors (por fila)
    for sheet_name, col_name in [
        ("1. Resumen por Color", "Riesgo"),
        ("3. Riesgo y Reorden", "Riesgo"),
    ]:
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        col_idx = next((c.column for c in ws[1] if c.value == col_name), None)
        if not col_idx:
            continue
        for row in range(2, ws.max_row + 1):
            cell = ws.cell(row=row, column=col_idx)
            val = str(cell.value or "").upper()
            if any(x in val for x in ("CRÍTICA", "SIN TELA", "QUIEBRE")):
                cell.fill = FILLS["crit"]
            elif "SOBRE" in val:
                cell.fill = FILLS["warn"]
            elif "SALUDABLE" in val:
                cell.fill = FILLS["ok"]
            cell.alignment = LEFT

    # Pedido highlight
    if "4. Pedido Tela" in wb.sheetnames:
        ws = wb["4. Pedido Tela"]
        ped_col = next((c.column for c in ws[1] if c.value == "Pedido sugerido (kg)"), None)
        if ped_col:
            letter = get_column_letter(ped_col)
            for row in range(2, ws.max_row + 1):
                cell = ws.cell(row=row, column=ped_col)
                if isinstance(cell.value, (int, float)) and cell.value > 0:
                    for c in range(1, ws.max_column + 1):
                        ws.cell(row=row, column=c).fill = FILLS["pedido"]
                    cell.font = Font(bold=True, color="006100", size=12)

    # Semáforo sheet
    if "10. Semáforo Integrado" in wb.sheetnames:
        ws = wb["10. Semáforo Integrado"]
        sem_map = {
            "OK": FILLS["ok"], "SALUDABLE": FILLS["ok"], "REGULAR": FILLS["ok"], "ALTA": FILLS["ok"],
            "CRÍTICO": FILLS["crit"], "SIN TELA": FILLS["crit"], "QUIEBRE": FILLS["crit"],
            "SOBRESTOCK": FILLS["warn"], "BAJO": FILLS["warn"], "VARIABLE": FILLS["warn"], "MEDIA": FILLS["warn"],
        }
        for row in range(2, ws.max_row + 1):
            for col_name in ["Rotación", "Regularidad", "Riesgo PT", "Riesgo Tela"]:
                col_idx = next((c.column for c in ws[1] if c.value == col_name), None)
                if not col_idx:
                    continue
                cell = ws.cell(row=row, column=col_idx)
                val = str(cell.value or "").upper()
                for key, fill in sem_map.items():
                    if key in val:
                        cell.fill = fill
                        cell.alignment = CENTER
                        break

    # Top 5 score column
    if "2. Top 5 Logística" in wb.sheetnames:
        ws = wb["2. Top 5 Logística"]
        score_col = next((c.column for c in ws[1] if c.value == "SCORE TOTAL"), None)
        if score_col:
            for row in range(2, min(7, ws.max_row + 1)):
                ws.cell(row=row, column=score_col).fill = FILLS["info"]
                ws.cell(row=row, column=score_col).font = Font(bold=True, size=12, color="1F4E79")

    wb.save(path)
