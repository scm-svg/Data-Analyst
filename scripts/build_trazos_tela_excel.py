#!/usr/bin/env python3
"""Tela Explore Pants (curvas Producción) + holgura Shorts R1 + licra Bahía."""

from __future__ import annotations

import json
import re
from pathlib import Path

import xlsxwriter

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "dash_explorepants.html"
OUT = ROOT / "EXPLORE_PANTS_Tela_Curvas_Produccion.xlsx"

TELA_EXISTENCIA = {
    "Negro": 317.7556,
    "Gris Oscuro": 280.4378,
    "Kaki": 168.8911,
    "Azul Marino": 159.9089,
    "Verde Militar": 58.84222,
}
TELA_KG_TOTAL = sum(TELA_EXISTENCIA.values())

TELA_CONSUMO = {"CAB": 0.30, "DAMA": 0.25, "KIDS": 0.22}
SHORTS_CONSUMO = {"CAB": 0.14, "DAMA": 0.12}
LICRA_BAHIA_KG = 0.14

COLORES = ["Negro", "Kaki", "Gris Oscuro", "Verde Militar", "Azul Marino"]

# Curvas enviadas por Producción (und por color, suma Trazo 1 + Trazo 2)
CAB = {
    "Negro": 351,
    "Kaki": 300,
    "Gris Oscuro": 303,
    "Verde Militar": 114,
    "Azul Marino": 252,
}
DAMA = {
    "Negro": 339,
    "Kaki": 318,
    "Gris Oscuro": 273,
    "Verde Militar": 74,
    "Azul Marino": 208,
}
KIDS = {
    "Negro": 167,
    "Kaki": 74,
    "Gris Oscuro": 100,
    "Verde Militar": 80,
    "Azul Marino": 229,
}


def shorts_blend_kg() -> tuple[float, float, float]:
    html = DASH.read_text(encoding="utf-8")
    m = re.search(r"const DATA = (\{.*?\});\s*\n", html, re.S)
    cab = dama = 0.0
    if m:
        data = json.loads(m.group(1))
        for r in data["raw_rows"]:
            if r["genero"] == "CAB":
                cab += r["v"]
            elif r["genero"] == "DAMA":
                dama += r["v"]
    total = cab + dama or 1.0
    blend = (cab / total) * SHORTS_CONSUMO["CAB"] + (dama / total) * SHORTS_CONSUMO["DAMA"]
    return blend, cab / total, dama / total


def kg_explore(genero: str, und: int) -> float:
    return und * TELA_CONSUMO[genero]


def split_cab_dama(pieces: int, cab_share: float) -> tuple[int, int]:
    cab = int(round(pieces * cab_share))
    cab = min(max(cab, 0), pieces)
    return cab, pieces - cab


def main() -> None:
    blend, cab_share, dama_share = shorts_blend_kg()

    explore_kg_by_gc: dict[tuple[str, str], float] = {}
    explore_und_by_gc: dict[tuple[str, str], int] = {}
    for genero, table in [("CAB", CAB), ("DAMA", DAMA), ("KIDS", KIDS)]:
        for color in COLORES:
            u = table[color]
            explore_und_by_gc[(genero, color)] = u
            explore_kg_by_gc[(genero, color)] = kg_explore(genero, u)

    explore_kg_color = {
        c: sum(explore_kg_by_gc[(g, c)] for g in ("CAB", "DAMA", "KIDS")) for c in COLORES
    }
    explore_kg_total = sum(explore_kg_color.values())

    slack_ng = {
        c: TELA_EXISTENCIA[c] - explore_kg_color[c] for c in ("Negro", "Gris Oscuro")
    }

    shorts_by_color = {}
    for color in ("Negro", "Gris Oscuro"):
        kg = max(0.0, slack_ng[color])
        pieces = int(kg // blend) if blend else 0
        kg_used = round(pieces * blend, 2)
        cab, dama = split_cab_dama(pieces, cab_share)
        shorts_by_color[color] = {
            "kg_slack": kg,
            "pieces": pieces,
            "kg_used": kg_used,
            "CAB": cab,
            "DAMA": dama,
        }

    shorts_total = sum(x["pieces"] for x in shorts_by_color.values())
    shorts_kg = sum(x["kg_used"] for x in shorts_by_color.values())
    licra_kg = round(shorts_total * LICRA_BAHIA_KG, 2)

    wb = xlsxwriter.Workbook(str(OUT))
    fmt_title = wb.add_format({"bold": True, "font_size": 14, "bg_color": "#1e1f2b", "font_color": "#ffffff"})
    fmt_hdr = wb.add_format({"bold": True, "bg_color": "#5b6af7", "font_color": "#ffffff", "border": 1})
    fmt_num = wb.add_format({"num_format": "#,##0", "border": 1})
    fmt_kg = wb.add_format({"num_format": "#,##0.00", "border": 1})
    fmt_txt = wb.add_format({"border": 1})
    fmt_warn = wb.add_format({"font_color": "#dc3545", "bold": True})
    fmt_ok = wb.add_format({"font_color": "#2e9e5e", "bold": True})

    # --- Resumen ---
    ws = wb.add_worksheet("Resumen")
    ws.set_column("A:A", 42)
    ws.set_column("B:C", 18)
    r = 0
    ws.write(r, 0, "Explore Pants — tela según curvas Producción", fmt_title)
    r += 2
    rows = [
        ("Fuente curvas", "Trazos CAB / DAMA / KIDS (Producción)", ""),
        ("Consumo Explore", f"CAB {TELA_CONSUMO['CAB']} · DAMA {TELA_CONSUMO['DAMA']} · KIDS {TELA_CONSUMO['KIDS']} kg/und", ""),
        ("Und Explore total", sum(explore_und_by_gc.values()), fmt_num),
        ("Kg tela Explore", explore_kg_total, fmt_kg),
        ("Existencia tela total", TELA_KG_TOTAL, fmt_kg),
        ("", "", ""),
        ("Shorts R1 (holgura Negro + Gris post-Explore)", "", ""),
        ("Consumo tela shorts (blend ventas Explore CAB/DAMA)", round(blend, 4), fmt_kg),
        ("Share CAB / DAMA shorts", f"{cab_share:.1%} / {dama_share:.1%}", ""),
        ("Und Shorts R1 posibles (máx. holgura)", shorts_total, fmt_num),
        ("Kg tela Shorts R1", shorts_kg, fmt_kg),
        ("Licra Bahía (0,14 kg/und × shorts)", licra_kg, fmt_kg),
        ("", "", ""),
        ("Programa tela (Explore + Shorts en Negro/Gris)", explore_kg_total + shorts_kg, fmt_kg),
        ("+ Licra Bahía (insumo aparte)", licra_kg, fmt_kg),
    ]
    for label, val, fmt in rows:
        ws.write(r, 0, label, fmt_txt)
        if fmt:
            ws.write(r, 1, val, fmt)
        else:
            ws.write(r, 1, val, fmt_txt)
        r += 1

    r += 1
    ws.write(r, 0, "Nota: Kaki / Azul / Verde en Explore superan existencia con estas curvas.", fmt_warn)
    r += 1
    ws.write(
        r,
        0,
        "Shorts usan solo holgura de Negro y Gris Oscuro tras el corte Explore.",
        fmt_txt,
    )

    # --- Explore und ---
    ws2 = wb.add_worksheet("Explore Und")
    ws2.write(0, 0, "Unidades Explore Pants — curvas Producción", fmt_title)
    hdr = ["Color", "CAB", "DAMA", "KIDS", "Total und"]
    for c, h in enumerate(hdr):
        ws2.write(2, c, h, fmt_hdr)
    row = 3
    for color in COLORES:
        vals = [CAB[color], DAMA[color], KIDS[color]]
        ws2.write(row, 0, color, fmt_txt)
        for i, v in enumerate(vals, 1):
            ws2.write(row, i, v, fmt_num)
        ws2.write(row, 4, sum(vals), fmt_num)
        row += 1
    ws2.write(row, 0, "TOTAL", fmt_hdr)
    for i, table in enumerate((CAB, DAMA, KIDS), 1):
        ws2.write(row, i, sum(table.values()), fmt_num)
    ws2.write(row, 4, sum(explore_und_by_gc.values()), fmt_num)

    # --- Explore kg ---
    ws3 = wb.add_worksheet("Explore Kg")
    ws3.write(0, 0, "Kg tela Explore — por género y color", fmt_title)
    hdr3 = ["Género", "Color", "Und", "Kg/und", "Kg tela"]
    for c, h in enumerate(hdr3):
        ws3.write(2, c, h, fmt_hdr)
    row = 3
    for genero in ("CAB", "DAMA", "KIDS"):
        for color in COLORES:
            u = explore_und_by_gc[(genero, color)]
            ws3.write(row, 0, genero, fmt_txt)
            ws3.write(row, 1, color, fmt_txt)
            ws3.write(row, 2, u, fmt_num)
            ws3.write(row, 3, TELA_CONSUMO[genero], fmt_kg)
            ws3.write(row, 4, explore_kg_by_gc[(genero, color)], fmt_kg)
            row += 1
    ws3.write(row, 0, "TOTAL", fmt_hdr)
    ws3.write(row, 4, explore_kg_total, fmt_kg)

    ws4 = wb.add_worksheet("Balance por color")
    ws4.write(0, 0, "Existencia vs consumo Explore (curvas)", fmt_title)
    hdr4 = ["Color", "Kg existencia", "Kg Explore", "Delta kg", "Estado"]
    for c, h in enumerate(hdr4):
        ws4.write(2, c, h, fmt_hdr)
    row = 3
    for color in COLORES:
        inv = TELA_EXISTENCIA[color]
        used = explore_kg_color[color]
        delta = inv - used
        ws4.write(row, 0, color, fmt_txt)
        ws4.write(row, 1, inv, fmt_kg)
        ws4.write(row, 2, used, fmt_kg)
        ws4.write(row, 3, delta, fmt_kg)
        if delta >= -0.05:
            ws4.write(row, 4, "OK / sobra" if delta > 0.5 else "OK", fmt_ok)
        else:
            ws4.write(row, 4, f"Faltan {abs(delta):.1f} kg", fmt_warn)
        row += 1

    # --- Shorts ---
    ws5 = wb.add_worksheet("Shorts R1 holgura")
    ws5.write(0, 0, "Short Sport R1 — máximo con holgura Negro / Gris Oscuro", fmt_title)
    ws5.write(2, 0, f"Consumo blend tela: {blend:.4f} kg/und (CAB {SHORTS_CONSUMO['CAB']} · DAMA {SHORTS_CONSUMO['DAMA']})", fmt_txt)
    hdr5 = [
        "Color tela",
        "Kg existencia",
        "Kg Explore",
        "Kg holgura",
        "Und Shorts máx",
        "Kg tela shorts",
        "Und CAB",
        "Und DAMA",
    ]
    for c, h in enumerate(hdr5):
        ws5.write(4, c, h, fmt_hdr)
    row = 5
    for color in ("Negro", "Gris Oscuro"):
        s = shorts_by_color[color]
        ws5.write(row, 0, color, fmt_txt)
        ws5.write(row, 1, TELA_EXISTENCIA[color], fmt_kg)
        ws5.write(row, 2, explore_kg_color[color], fmt_kg)
        ws5.write(row, 3, s["kg_slack"], fmt_kg)
        ws5.write(row, 4, s["pieces"], fmt_num)
        ws5.write(row, 5, s["kg_used"], fmt_kg)
        ws5.write(row, 6, s["CAB"], fmt_num)
        ws5.write(row, 7, s["DAMA"], fmt_num)
        row += 1
    ws5.write(row, 0, "TOTAL Shorts R1", fmt_hdr)
    ws5.write(row, 4, shorts_total, fmt_num)
    ws5.write(row, 5, shorts_kg, fmt_kg)
    ws5.write(row, 6, sum(shorts_by_color[c]["CAB"] for c in shorts_by_color), fmt_num)
    ws5.write(row, 7, sum(shorts_by_color[c]["DAMA"] for c in shorts_by_color), fmt_num)

    row += 2
    ws5.write(row, 0, "Comparación meta anterior 1.550 und", fmt_txt)
    ws5.write(row, 1, shorts_total - 1550, fmt_num)
    row += 1
    ws5.write(row, 0, "Kg tela shorts si fueran 1.550 und (referencia)", fmt_txt)
    ws5.write(row, 1, round(1550 * blend, 2), fmt_kg)

    # --- Licra ---
    ws6 = wb.add_worksheet("Licra Bahía")
    ws6.write(0, 0, "Licra Bahía — Shorts R1 (holgura máxima)", fmt_title)
    hdr6 = ["Concepto", "Valor"]
    for c, h in enumerate(hdr6):
        ws6.write(2, c, h, fmt_hdr)
    licra_rows = [
        ("Und Shorts R1 (holgura máx.)", shorts_total),
        ("Consumo licra promedio (kg/und)", LICRA_BAHIA_KG),
        ("Kg licra Bahía total", licra_kg),
        ("", ""),
        ("Referencia 1.550 shorts", 1550),
        ("Kg licra si 1.550 und", round(1550 * LICRA_BAHIA_KG, 2)),
    ]
    row = 3
    for label, val in licra_rows:
        ws6.write(row, 0, label, fmt_txt)
        if isinstance(val, float):
            ws6.write(row, 1, val, fmt_kg)
        elif val == "":
            pass
        else:
            ws6.write(row, 1, val, fmt_num if isinstance(val, int) else fmt_kg)
        row += 1

    wb.close()
    print(f"Wrote {OUT}")
    print(f"Explore kg: {explore_kg_total:.2f} | Shorts: {shorts_total} und / {shorts_kg:.2f} kg | Licra: {licra_kg} kg")


if __name__ == "__main__":
    main()
