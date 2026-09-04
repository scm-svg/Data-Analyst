"""Renderiza hojas del modelo a PNG (solo para revisar el resultado)."""

import subprocess
import sys
from pathlib import Path

import openpyxl

RECALC = Path("recalc/Modelo_Capacidad_CUADRO_v4.xlsx")
OUT = Path("render")
HOJAS = {
    "Lineas por Escenario": ("lineas_por_escenario", "A1:O44"),
    "Capacidad": ("capacidad", "A1:G26"),
    "Cambio v3 a v4": ("cambio_v3_v4", "A1:E30"),
    "Demanda y Deficit": ("demanda_y_deficit", "A1:G14"),
    "Escenarios": ("escenarios", "A1:E10"),
    "Inversion": ("inversion", "A1:H16"),
    "Supuestos": ("supuestos", "A1:D33"),
}


def render(hoja, nombre, area):
    wb = openpyxl.load_workbook(RECALC, data_only=True)
    for otra in list(wb.sheetnames):
        if otra != hoja:
            del wb[otra]
    ws = wb[hoja]
    ws.print_area = area
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A3
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.page_margins.left = ws.page_margins.right = 0.2
    ws.page_margins.top = ws.page_margins.bottom = 0.2
    tmp = OUT / f"{nombre}.xlsx"
    wb.save(tmp)
    subprocess.run(["soffice", "--headless", "--norestore", "--convert-to", "pdf",
                    "--outdir", str(OUT), str(tmp)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["pdftoppm", "-png", "-r", "150", "-cropbox",
                    str(OUT / f"{nombre}.pdf"), str(OUT / nombre)], check=True)
    tmp.unlink()


def main():
    OUT.mkdir(exist_ok=True)
    for hoja, (nombre, area) in HOJAS.items():
        render(hoja, nombre, area)
        print("renderizado", nombre)
    return 0


if __name__ == "__main__":
    sys.exit(main())
