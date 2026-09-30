#!/usr/bin/env python3
"""
Genera INVENTARIO_SERV_JOSE_MEJORADO.xlsx a partir del archivo original.
Preserva datos y tablas; corrige fórmulas, añade control visual y hojas de gestión.
"""
from __future__ import annotations

import shutil
from copy import copy
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

SRC = Path("/home/ubuntu/.cursor/projects/workspace/uploads/INVENTARIO_SERV_JOSE_eb9f.xlsx")
OUT = Path("/workspace/inventario/INVENTARIO_SERV_JOSE_MEJORADO.xlsx")

# Paleta corporativa
COLOR_HEADER = "1F4E79"
COLOR_HEADER_FONT = "FFFFFF"
COLOR_ACCENT = "2E75B6"
COLOR_OK = "C6EFCE"
COLOR_WARN = "FFEB9C"
COLOR_CRIT = "FFC7CE"
COLOR_NEG = "FF0000"
COLOR_DASH_BG = "F2F2F2"

thin = Side(style="thin", color="B4B4B4")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)


def style_header_row(ws, row: int, col_start: int, col_end: int):
    for c in range(col_start, col_end + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = Font(bold=True, color=COLOR_HEADER_FONT, size=11)
        cell.fill = PatternFill("solid", fgColor=COLOR_HEADER)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER


def fix_stock_entradas_formula(wb):
    ws = wb["STOCK"]
    tbl = ws.tables["PRODUCTOS"]
    # Corregir fórmula de columna calculada ENTRADAS en la definición de tabla
    for col in tbl.tableColumns:
        if col.name == "ENTRADAS" and col.calculatedColumnFormula is not None:
            col.calculatedColumnFormula.attr_text = (
                "SUMIFS(ENTRADAS[CANTIDAD],ENTRADAS[CODIGO],PRODUCTOS[[#This Row],[CODIGO]])"
            )
    # Aplicar en celdas visibles (por si Excel no recalcula la columna calculada al abrir)
    for r in range(16, ws.max_row):
        cell = ws.cell(r, 6)
        if cell.value and isinstance(cell.value, str) and "STOCK!B" in cell.value:
            cell.value = (
                "=SUMIFS(ENTRADAS[CANTIDAD],ENTRADAS[CODIGO],PRODUCTOS[[#This Row],[CODIGO]])"
            )


def extend_stock_table(wb):
    ws = wb["STOCK"]
    tbl = ws.tables["PRODUCTOS"]
    old_ref = tbl.ref  # e.g. A15:H1290
    start, end = old_ref.split(":")
    end_col = end[0]
    end_row = end[1:]
    if end_col < "K":
        new_ref = f"{start}:K{end_row}"
        tbl.ref = new_ref
        ws.tables["PRODUCTOS"] = tbl

    header_row = 15
    ws.cell(header_row, 9, "STOCK MÍN.")
    ws.cell(header_row, 10, "ESTADO")
    ws.cell(header_row, 11, "OBSERVACIÓN")
    style_header_row(ws, header_row, 1, 11)

    last_data = int(end_row) - 1  # excluir fila totales
    for r in range(16, last_data + 1):
        ws.cell(r, 9).value = 0
        ws.cell(r, 9).number_format = "0"
        # ESTADO
        ws.cell(r, 10).value = (
            f'=IF(PRODUCTOS[[#This Row],[STOCK]]<0,"NEGATIVO",'
            f'IF(PRODUCTOS[[#This Row],[STOCK]]=0,"SIN STOCK",'
            f'IF(PRODUCTOS[[#This Row],[STOCK]]<=PRODUCTOS[[#This Row],[STOCK MÍN.]],"BAJO","OK")))'
        )
        ws.cell(r, 11).value = (
            f'=IF(PRODUCTOS[[#This Row],[STOCK]]<0,"Revisar movimientos: salidas > entradas",'
            f'IF(AND(PRODUCTOS[[#This Row],[STOCK]]>0,PRODUCTOS[[#This Row],[STOCK]]<=PRODUCTOS[[#This Row],[STOCK MÍN.]]),'
            f'"Programar reposición",""))'
        )

    # Ampliar columnas en definición de tabla
    next_id = max(c.id for c in tbl.tableColumns) + 1
    from openpyxl.worksheet.table import TableColumn

    for name in ("STOCK MÍN.", "ESTADO", "OBSERVACIÓN"):
        tc = TableColumn(id=next_id, name=name)
        tbl.tableColumns.append(tc)
        next_id += 1

    # Formato condicional STOCK y ESTADO
    stock_range = f"H16:H{last_data}"
    estado_range = f"J16:J{last_data}"
    ws.conditional_formatting.add(
        stock_range,
        CellIsRule(operator="lessThan", formula=["0"], fill=PatternFill("solid", fgColor=COLOR_CRIT)),
    )
    ws.conditional_formatting.add(
        stock_range,
        CellIsRule(operator="equal", formula=["0"], fill=PatternFill("solid", fgColor=COLOR_WARN)),
    )
    ws.conditional_formatting.add(
        estado_range,
        FormulaRule(
            formula=['J16="OK"'],
            fill=PatternFill("solid", fgColor=COLOR_OK),
        ),
    )
    ws.conditional_formatting.add(
        estado_range,
        FormulaRule(
            formula=['J16="BAJO"'],
            fill=PatternFill("solid", fgColor=COLOR_WARN),
        ),
    )
    ws.conditional_formatting.add(
        estado_range,
        FormulaRule(
            formula=['OR(J16="NEGATIVO",J16="SIN STOCK")'],
            fill=PatternFill("solid", fgColor=COLOR_CRIT),
        ),
    )

    ws.column_dimensions["I"].width = 11
    ws.column_dimensions["J"].width = 12
    ws.column_dimensions["K"].width = 36


def fix_entrada_header_typo(wb):
    ws = wb["ENTRADA"]
    for r in range(1, 30):
        for c in range(1, 15):
            v = ws.cell(r, c).value
            if v and isinstance(v, str) and "UNTARIO" in v:
                ws.cell(r, c).value = v.replace("UNTARIO", "UNITARIO")


def extract_salida_lists(wb):
    ws = wb["SALIDA"]
    tiendas = []
    tecnicos = []
    for r in range(1, 120):
        t = ws.cell(r, 22).value
        tech = ws.cell(r, 21).value
        if t and str(t).strip() and str(t).strip() not in tiendas:
            tiendas.append(str(t).strip())
        if tech and str(tech).strip() and str(tech).strip() not in tecnicos:
            tecnicos.append(str(tech).strip())
    return sorted(tiendas), sorted(tecnicos)


def create_config_sheet(wb, tiendas, tecnicos):
    if "CONFIG" in wb.sheetnames:
        del wb["CONFIG"]
    ws = wb.create_sheet("CONFIG", 0)
    ws["A1"] = "PARÁMETROS Y LISTAS MAESTRAS"
    ws["A1"].font = Font(bold=True, size=14, color=COLOR_HEADER)
    ws["A3"] = "Última actualización plantilla:"
    ws["B3"] = datetime.now().strftime("%Y-%m-%d")
    ws["A4"] = "Stock mínimo por defecto (nuevos ítems):"
    ws["B4"] = 0
    ws["A6"] = "TIENDAS / DESTINOS"
    ws["C6"] = "TÉCNICOS / RESPONSABLES"
    style_header_row(ws, 6, 1, 1)
    style_header_row(ws, 6, 3, 3)
    for i, t in enumerate(tiendas, start=7):
        ws.cell(i, 1, t)
    for i, t in enumerate(tecnicos, start=7):
        ws.cell(i, 3, t)
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["C"].width = 28
    # Rangos con nombre implícito para validación
    ws["E6"] = "Rango tiendas"
    ws["E7"] = f"=CONFIG!$A$7:$A${6 + len(tiendas)}"
    ws["E8"] = "Rango técnicos"
    ws["E9"] = f"=CONFIG!$C$7:$C${6 + len(tecnicos)}"
    return ws


def add_salida_validation(wb, n_tiendas: int, n_tecnicos: int):
    ws = wb["SALIDA"]
    if n_tiendas < 1 or n_tecnicos < 1:
        return
    tienda_dv = DataValidation(
        type="list",
        formula1=f"=CONFIG!$A$7:$A${6 + n_tiendas}",
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Tienda no válida",
        error="Seleccione una tienda de la lista CONFIG.",
    )
    resp_dv = DataValidation(
        type="list",
        formula1=f"=CONFIG!$C$7:$C${6 + n_tecnicos}",
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Responsable no válido",
        error="Seleccione un responsable de la lista CONFIG.",
    )
    ws.add_data_validation(tienda_dv)
    ws.add_data_validation(resp_dv)
    last = min(ws.max_row, 2000)
    tienda_dv.add(f"G18:G{last}")
    resp_dv.add(f"H18:H{last}")


def create_dashboard(wb):
    if "DASHBOARD" in wb.sheetnames:
        del wb["DASHBOARD"]
    ws = wb.create_sheet("DASHBOARD", 0)
    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:L1")
    t = ws["A1"]
    t.value = "PANEL DE CONTROL — INVENTARIO S.S.G.G."
    t.font = Font(bold=True, size=18, color=COLOR_HEADER_FONT)
    t.fill = PatternFill("solid", fgColor=COLOR_HEADER)
    t.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 36

    ws["A3"] = "Indicador"
    ws["B3"] = "Valor"
    ws["C3"] = "Detalle"
    style_header_row(ws, 3, 1, 3)

    kpis = [
        ("Total SKUs en catálogo", '=COUNTA(LISTADO[CODIGOS])', "Hoja PRODUCTOS"),
        ("Stock total (unidades)", '=SUBTOTAL(109,PRODUCTOS[STOCK])', "Suma visible en STOCK"),
        ("Productos sin stock", '=COUNTIF(PRODUCTOS[STOCK],0)', "Requieren reposición"),
        ("Productos stock bajo", '=COUNTIF(PRODUCTOS[ESTADO],"BAJO")', "Por debajo del mínimo"),
        ("Productos stock negativo", '=COUNTIF(PRODUCTOS[STOCK],"<0")', "Revisar kardex"),
        ("Total entradas (unidades)", '=SUBTOTAL(109,ENTRADAS[CANTIDAD])', "Hoja ENTRADA"),
        ("Total salidas (unidades)", '=SUBTOTAL(109,SALIDAS[CANTIDAD])', "Hoja SALIDA"),
        ("Movimientos de entrada", '=COUNTA(ENTRADAS[CODIGO])', "Registros"),
        ("Movimientos de salida", '=COUNTA(SALIDAS[CODIGO])', "Registros"),
    ]
    row = 4
    for label, formula, detail in kpis:
        ws.cell(row, 1, label)
        ws.cell(row, 2, formula)
        ws.cell(row, 3, detail)
        ws.cell(row, 2).number_format = "#,##0"
        for c in range(1, 4):
            ws.cell(row, c).border = BORDER
            ws.cell(row, c).fill = PatternFill("solid", fgColor=COLOR_DASH_BG if row % 2 == 0 else "FFFFFF")
        row += 1

    ws["A14"] = "Accesos rápidos"
    ws["A14"].font = Font(bold=True, size=12, color=COLOR_ACCENT)
    links = [
        ("Registrar ENTRADA", "ENTRADA!A4"),
        ("Registrar SALIDA", "SALIDA!A7"),
        ("Consultar STOCK", "STOCK!A5"),
        ("Catálogo PRODUCTOS", "PRODUCTOS!B4"),
        ("Alertas", "ALERTAS!A1"),
        ("Instrucciones", "INSTRUCCIONES!A1"),
    ]
    r = 15
    for label, addr in links:
        ws.cell(r, 1, label)
        cell = ws.cell(r, 2, f'=HYPERLINK("#{addr}","{label}")')
        cell.font = Font(color="0563C1", underline="single")
        r += 1

    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 40


def create_alertas_sheet(wb):
    if "ALERTAS" in wb.sheetnames:
        del wb["ALERTAS"]
    ws = wb.create_sheet("ALERTAS")
    ws["A1"] = "PRODUCTOS QUE REQUIEREN ATENCIÓN"
    ws["A1"].font = Font(bold=True, size=14, color=COLOR_HEADER)
    ws["A3"] = (
        "Filtre en STOCK por columna ESTADO (NEGATIVO, SIN STOCK, BAJO) "
        "o use la tabla dinámica INVENTARIO ABC para consumo."
    )
    headers = ["CODIGO", "PRODUCTO", "CATEGORIA", "STOCK", "STOCK MÍN.", "ESTADO", "OBSERVACIÓN"]
    for i, h in enumerate(headers, start=1):
        ws.cell(5, i, h)
    style_header_row(ws, 5, 1, len(headers))
    # Fórmulas dinámicas FILTER (Excel 365) — fallback texto si no aplica
    ws["A6"] = (
        '=IFERROR(FILTER(PRODUCTOS[[CODIGO]:[OBSERVACIÓN]],'
        '(PRODUCTOS[ESTADO]="NEGATIVO")+(PRODUCTOS[ESTADO]="SIN STOCK")+(PRODUCTOS[ESTADO]="BAJO")),'
        '"Use filtros en hoja STOCK columna ESTADO")'
    )
    ws.column_dimensions["B"].width = 45
    ws.column_dimensions["G"].width = 38


def create_instrucciones(wb):
    if "INSTRUCCIONES" in wb.sheetnames:
        del wb["INSTRUCCIONES"]
    ws = wb.create_sheet("INSTRUCCIONES")
    lines = [
        ("GUÍA DE USO — INVENTARIO MEJORADO", 14, True),
        ("", 11, False),
        ("1. Catálogo (PRODUCTOS)", 12, True),
        ("   • Agregue filas solo en la tabla LISTADO. El código se genera automáticamente.", 11, False),
        ("   • Mantenga categorías alineadas con la lista de referencias (columna J-K).", 11, False),
        ("", 11, False),
        ("2. Entradas (ENTRADA)", 12, True),
        ("   • Registre código, fecha, cantidad, motivo y proveedor.", 11, False),
        ("   • El stock se actualiza automáticamente en STOCK.", 11, False),
        ("", 11, False),
        ("3. Salidas (SALIDA)", 12, True),
        ("   • Indique tienda y responsable (listas en CONFIG).", 11, False),
        ("   • No registre salidas si el stock es insuficiente (revise columna ESTADO).", 11, False),
        ("", 11, False),
        ("4. Stock (STOCK)", 12, True),
        ("   • Columna STOCK MÍN.: defina punto de reorden por producto.", 11, False),
        ("   • ESTADO: OK / BAJO / SIN STOCK / NEGATIVO (con colores).", 11, False),
        ("   • CORRECCIÓN v2: fórmula de ENTRADAS unificada por código de producto.", 11, False),
        ("", 11, False),
        ("5. Panel DASHBOARD", 12, True),
        ("   • KPIs y enlaces rápidos. Actualice filtros en tablas para ver subtotales.", 11, False),
        ("", 11, False),
        ("6. Hoja PINTURAS (antes Hoja1)", 12, True),
        ("   • Listado auxiliar de pinturas; considere migrar a códigos del catálogo.", 11, False),
    ]
    r = 1
    for text, size, bold in lines:
        c = ws.cell(r, 1, text)
        c.font = Font(size=size, bold=bold, color=COLOR_HEADER if bold and size >= 12 else "000000")
        r += 1
    ws.column_dimensions["A"].width = 85


def rename_hoja1(wb):
    if "Hoja1" in wb.sheetnames:
        ws = wb["Hoja1"]
        ws.title = "PINTURAS_AUX"


def polish_main_sheets(wb):
    for name, title_row in [("STOCK", 5), ("ENTRADA", 4), ("SALIDA", 7), ("PRODUCTOS", 4)]:
        if name not in wb.sheetnames:
            continue
        ws = wb[name]
        for r in range(1, 25):
            v = ws.cell(r, 1).value
            if v and isinstance(v, str) and "INVENTARIO" in v.upper() or "MOVIMIENTOS" in str(v).upper():
                ws.cell(r, 1).font = Font(bold=True, size=14, color=COLOR_ACCENT)


def reorder_sheets(wb):
    order = [
        "DASHBOARD",
        "INSTRUCCIONES",
        "STOCK",
        "ENTRADA",
        "SALIDA",
        "PRODUCTOS",
        "ALERTAS",
        "CONFIG",
        "INVENTARIO ABC",
        "PINTURAS_AUX",
    ]
    for i, name in enumerate(order):
        if name in wb.sheetnames:
            wb.move_sheet(name, offset=i - wb.sheetnames.index(name))


def main():
    shutil.copy2(SRC, OUT)
    wb = openpyxl.load_workbook(OUT, data_only=False)

    fix_stock_entradas_formula(wb)
    extend_stock_table(wb)
    fix_entrada_header_typo(wb)
    tiendas, tecnicos = extract_salida_lists(wb)
    create_config_sheet(wb, tiendas, tecnicos)
    add_salida_validation(wb, len(tiendas), len(tecnicos))
    create_dashboard(wb)
    create_alertas_sheet(wb)
    create_instrucciones(wb)
    rename_hoja1(wb)
    polish_main_sheets(wb)
    reorder_sheets(wb)

    wb.save(OUT)
    print(f"Guardado: {OUT}")


if __name__ == "__main__":
    main()
