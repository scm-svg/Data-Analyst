#!/usr/bin/env python3
"""Short Sport R1 — plan fijo und + consumo tela y compra adicional (post Explore curvas)."""

from __future__ import annotations

from pathlib import Path

import xlsxwriter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "SHORTS_R1_Plan_2200und.xlsx"

TELA_EXISTENCIA = {
    "Negro": 317.7556,
    "Gris Oscuro": 280.4378,
}

SHORTS_CONSUMO = {"CAB": 0.14, "DAMA": 0.12}
LICRA_BAHIA_KG = 0.14
TELA_CONSUMO_EXPLORE = {"CAB": 0.30, "DAMA": 0.25, "KIDS": 0.22}

# Explore Pants — curvas Producción (kg usados en Negro / Gris)
EXPLORE_UND = {
    "Negro": {"CAB": 351, "DAMA": 339, "KIDS": 167},
    "Gris Oscuro": {"CAB": 303, "DAMA": 273, "KIDS": 100},
}

SHORTS_TOTAL = 2200
SHORTS_PER_COLOR = SHORTS_TOTAL // 2  # Negro / Gris Oscuro
SHORTS_PER_GC = SHORTS_PER_COLOR // 2  # CAB / DAMA por color


def explore_kg_color(color: str) -> float:
    rows = EXPLORE_UND[color]
    return sum(rows[g] * TELA_CONSUMO_EXPLORE[g] for g in rows)


def main() -> None:
    plan = []
    for color in ("Negro", "Gris Oscuro"):
        for genero in ("CAB", "DAMA"):
            und = SHORTS_PER_GC
            kg = und * SHORTS_CONSUMO[genero]
            plan.append(
                {
                    "color": color,
                    "genero": genero,
                    "und": und,
                    "kg_und": SHORTS_CONSUMO[genero],
                    "kg": kg,
                }
            )

    by_color = {}
    for color in ("Negro", "Gris Oscuro"):
        rows = [p for p in plan if p["color"] == color]
        kg_need = sum(p["kg"] for p in rows)
        kg_explore = explore_kg_color(color)
        kg_exist = TELA_EXISTENCIA[color]
        kg_disponible = kg_exist - kg_explore
        kg_compra = max(0.0, kg_need - kg_disponible)
        by_color[color] = {
            "und": SHORTS_PER_COLOR,
            "kg_need": kg_need,
            "kg_existencia": kg_exist,
            "kg_explore_curvas": kg_explore,
            "kg_disponible": kg_disponible,
            "kg_compra": kg_compra,
        }

    kg_tela_total = sum(c["kg_need"] for c in by_color.values())
    kg_compra_total = sum(c["kg_compra"] for c in by_color.values())
    licra_kg = SHORTS_TOTAL * LICRA_BAHIA_KG

    wb = xlsxwriter.Workbook(str(OUT))
    fmt_title = wb.add_format({"bold": True, "font_size": 14, "bg_color": "#1e1f2b", "font_color": "#ffffff"})
    fmt_hdr = wb.add_format({"bold": True, "bg_color": "#5b6af7", "font_color": "#ffffff", "border": 1})
    fmt_num = wb.add_format({"num_format": "#,##0", "border": 1})
    fmt_kg = wb.add_format({"num_format": "#,##0.00", "border": 1})
    fmt_txt = wb.add_format({"border": 1})
    fmt_bold = wb.add_format({"bold": True, "border": 1})
    fmt_warn = wb.add_format({"font_color": "#dc3545", "bold": True})

    # Resumen
    ws = wb.add_worksheet("Resumen")
    ws.set_column("A:A", 44)
    ws.set_column("B:B", 20)
    ws.write(0, 0, "SHORT SPORT R1 — plan 2.200 und", fmt_title)
    r = 2
    summary = [
        ("Modelo", "SHORT SPORT R1"),
        ("Total und", SHORTS_TOTAL),
        ("Negro / Gris Oscuro", f"{SHORTS_PER_COLOR:,} und c/u (50% / 50%)"),
        ("CAB / DAMA (cada color)", f"{SHORTS_PER_GC:,} und c/u (50% / 50%)"),
        ("Consumo tela CAB", f"{SHORTS_CONSUMO['CAB']} kg/und"),
        ("Consumo tela DAMA", f"{SHORTS_CONSUMO['DAMA']} kg/und"),
        ("", ""),
        ("Kg tela shorts (total programa)", kg_tela_total),
        ("Referencia Explore previo", "Curvas Producción ya descontadas en holgura"),
        ("Kg tela compra adicional (Negro + Gris)", kg_compra_total),
        ("", ""),
        ("Licra Bahía — consumo", f"{LICRA_BAHIA_KG} kg/und"),
        ("Kg licra Bahía (2.200 und)", licra_kg),
        ("Nota licra", "Sin stock en archivo; considerar compra completa de licra"),
    ]
    for label, val in summary:
        ws.write(r, 0, label, fmt_txt)
        if isinstance(val, float):
            ws.write(r, 1, val, fmt_kg)
        elif isinstance(val, int):
            ws.write(r, 1, val, fmt_num)
        else:
            ws.write(r, 1, val, fmt_txt)
        r += 1

    # Cantidades
    ws2 = wb.add_worksheet("Cantidades")
    ws2.write(0, 0, "Unidades Shorts R1", fmt_title)
    hdr = ["Color tela", "Género", "Und", "Kg/und", "Kg tela"]
    for c, h in enumerate(hdr):
        ws2.write(2, c, h, fmt_hdr)
    row = 3
    for p in plan:
        ws2.write(row, 0, p["color"], fmt_txt)
        ws2.write(row, 1, p["genero"], fmt_txt)
        ws2.write(row, 2, p["und"], fmt_num)
        ws2.write(row, 3, p["kg_und"], fmt_kg)
        ws2.write(row, 4, p["kg"], fmt_kg)
        row += 1
    ws2.write(row, 0, "TOTAL", fmt_hdr)
    ws2.write(row, 2, SHORTS_TOTAL, fmt_num)
    ws2.write(row, 4, kg_tela_total, fmt_kg)

    # Compra tela
    ws3 = wb.add_worksheet("Compra tela adicional")
    ws3.write(0, 0, "Tela principal — existencia vs Explore curvas vs Shorts 2.200", fmt_title)
    hdr3 = [
        "Color",
        "Kg existencia",
        "Kg Explore (curvas)",
        "Kg disponible post-Explore",
        "Kg necesarios Shorts",
        "Kg compra adicional",
    ]
    for c, h in enumerate(hdr3):
        ws3.write(2, c, h, fmt_hdr)
    ws3.set_column(0, 0, 14)
    ws3.set_column(1, 5, 16)
    row = 3
    for color in ("Negro", "Gris Oscuro"):
        c = by_color[color]
        ws3.write(row, 0, color, fmt_txt)
        ws3.write(row, 1, c["kg_existencia"], fmt_kg)
        ws3.write(row, 2, c["kg_explore_curvas"], fmt_kg)
        ws3.write(row, 3, c["kg_disponible"], fmt_kg)
        ws3.write(row, 4, c["kg_need"], fmt_kg)
        ws3.write(row, 5, c["kg_compra"], fmt_kg if c["kg_compra"] > 0 else fmt_bold)
        row += 1
    ws3.write(row, 0, "TOTAL", fmt_hdr)
    ws3.write(row, 4, kg_tela_total, fmt_kg)
    ws3.write(row, 5, kg_compra_total, fmt_kg)
    row += 2
    ws3.write(row, 0, "Fórmula compra adicional por color:", fmt_txt)
    row += 1
    ws3.write(row, 0, "max(0 ; kg Shorts − (existencia − kg Explore curvas))", fmt_txt)

    # Licra
    ws4 = wb.add_worksheet("Licra Bahía")
    ws4.write(0, 0, "Licra Bahía — Shorts R1", fmt_title)
    ws4.write(2, 0, "Concepto", fmt_hdr)
    ws4.write(2, 1, "Valor", fmt_hdr)
    licra_rows = [
        ("Und Shorts", SHORTS_TOTAL, fmt_num),
        ("Kg/und", LICRA_BAHIA_KG, fmt_kg),
        ("Kg licra total", licra_kg, fmt_kg),
    ]
    row = 3
    for label, val, fmt in licra_rows:
        ws4.write(row, 0, label, fmt_txt)
        ws4.write(row, 1, val, fmt)
        row += 1

    wb.close()
    print(f"Wrote {OUT}")
    print(f"Tela shorts: {kg_tela_total:.2f} kg | Compra adicional: {kg_compra_total:.2f} kg | Licra: {licra_kg:.2f} kg")


if __name__ == "__main__":
    main()
