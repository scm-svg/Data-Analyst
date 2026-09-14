#!/usr/bin/env python3
"""
Plan Mar/Rio — Excel editable con fórmulas, prioridad Rio KIDS → Mar KIDS,
adultos al 50%, detalle por talla.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

MAR_XLSX = Path("/home/ubuntu/.cursor/projects/workspace/uploads/MAR_PROYECCION_CANTIDADES_SUGERIDAS__2__23dd.xlsx")
RIO_XLSX = Path("/home/ubuntu/.cursor/projects/workspace/uploads/RIO_PROYECCION_CANTIDADES_SUGERIDAS__2__cc77.xlsx")
OUT_DIR = Path("/workspace/output")

TELA_KG = {
    "Aguamarina": 348.34, "Amarillo Neón": 57.94, "Azul Lavanda": 221.00,
    "Azul Marino": 689.90, "Azul Rey": 271.46, "Blanco": 162.04,
    "Gris Claro": 47.68, "Lila": 188.44, "Morado": 94.20, "Negro": 657.16,
    "Rojo": 0.18, "Rosado Pastel": 31.44, "Verde Militar": 46.02, "Vinotinto": 175.38,
}

LOTE_CORTADO_COLORES = [
    "Verde Militar", "Vinotinto", "Azul Marino", "Azul Rey", "Rojo", "Gris Claro",
    "Azul Lavanda", "Aguamarina", "Rosado Pastel", "Negro", "Lila",
]
LOTE_CORTADO_TOTAL = 1300
LOTE_A_META_KIDS = {
    "Verde Militar": "Verde Militar", "Vinotinto": None, "Azul Marino": "Azul Marino",
    "Azul Rey": "Azul Rey", "Rojo": "Rojo", "Gris Claro": None,
    "Azul Lavanda": "Azul Lavanda", "Aguamarina": "Aguamarina",
    "Rosado Pastel": "Rosado Pastel", "Negro": "Negro", "Lila": "Lila",
}

PCT_KIDS = 0.50
PCT_ADULTOS = 0.50
MIN_KG = 5.0
PRIORIDAD_ORDEN = ["RIO KIDS", "MAR KIDS", "MAR CAB", "MAR DAMA", "RIO CAB", "RIO DAMA"]

COLOR_CANONICAL = {"Púrpura": "Morado", "Morado": "Morado"}
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=10)
SECTION_FILL = PatternFill("solid", fgColor="D9E2F3")
KIDS_FILL = PatternFill("solid", fgColor="E2EFDA")
THIN = Side(style="thin", color="AAAAAA")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

GEN_MAP = {"CABALLERO": "CAB", "DAMA": "DAMA", "KIDS": "KIDS"}


def canonical_color(c: str) -> str:
    return COLOR_CANONICAL.get(c, c)


def tela_stock(color: str) -> float:
    return TELA_KG.get(canonical_color(color), TELA_KG.get(color, 0.0))


def parse_colores(path: Path) -> dict[str, dict[str, int]]:
    df = pd.read_excel(path, sheet_name="Cantidades por Colores", header=None)
    result: dict[str, dict[str, int]] = {"CAB": {}, "DAMA": {}, "KIDS": {}}
    current = None
    for _, row in df.iterrows():
        val0 = str(row[0]) if pd.notna(row[0]) else ""
        u = val0.upper()
        if "CABALLERO" in u:
            current = "CAB"
        elif "DAMA" in u and "CAB" not in u:
            current = "DAMA"
        elif "KIDS" in u or "NIÑ" in u:
            current = "KIDS"
        elif val0.strip() in ("Color", "TOTAL", "nan", "") or not current:
            continue
        elif pd.notna(row[3]):
            try:
                result[current][val0.strip()] = int(float(row[3]))
            except (ValueError, TypeError):
                pass
    return result


def parse_consumo(path: Path) -> dict[str, float]:
    df = pd.read_excel(path, sheet_name="Compra de Tela", header=None)
    out: dict[str, float] = {}
    for _, row in df.iterrows():
        v0 = str(row[0]).strip() if pd.notna(row[0]) else ""
        if v0 in ("CABALLERO", "DAMA", "KIDS") and pd.notna(row[1]):
            out["CAB" if v0 == "CABALLERO" else v0] = float(row[1])
    return out


def parse_color_talla(path: Path) -> list[dict]:
    """Mix talla máx por modelo/género/color desde Excel proyección."""
    df = pd.read_excel(path, sheet_name="Producción Color × Talla", header=None)
    modelo = "MAR" if "MAR" in path.name.upper() else "RIO"
    rows: list[dict] = []
    section = None
    tallas: list[str] = []

    for _, row in df.iterrows():
        val0 = str(row[0]) if pd.notna(row[0]) else ""
        if "CABALLERO" in val0.upper() and "PRODUCCIÓN" in val0.upper():
            section = "CAB"
            continue
        if "DAMA" in val0.upper() and "PRODUCCIÓN" in val0.upper():
            section = "DAMA"
            continue
        if "KIDS" in val0.upper() and "PRODUCCIÓN" in val0.upper():
            section = "KIDS"
            continue
        if val0.strip() == "Color / Talla":
            tallas = [str(row[i]) for i in range(1, len(row)) if pd.notna(row[i]) and str(row[i]) != "Total"]
            continue
        if section and "Máx" in val0:
            color = val0.split("—")[0].strip()
            total = int(float(row[len(tallas) + 1])) if pd.notna(row[len(tallas) + 1]) else 0
            for i, t in enumerate(tallas):
                v = row[i + 1]
                if pd.notna(v):
                    rows.append({
                        "modelo": modelo, "genero": section, "color": color,
                        "talla": str(t).replace(".0", ""), "und_max": int(float(v)),
                        "total_color": total,
                    })
    return rows


def lote_cortado_meta_kids() -> dict[str, float]:
    por = LOTE_CORTADO_TOTAL / len(LOTE_CORTADO_COLORES)
    out: dict[str, float] = {}
    for c in LOTE_CORTADO_COLORES:
        mc = LOTE_A_META_KIDS.get(c)
        if mc:
            out[mc] = out.get(mc, 0) + por
    return out


def load_all() -> tuple[dict, dict, list[dict]]:
    mar, rio = parse_colores(MAR_XLSX), parse_colores(RIO_XLSX)
    metas = {"MAR": mar, "RIO": rio}
    consumos = {"MAR": parse_consumo(MAR_XLSX), "RIO": parse_consumo(RIO_XLSX)}
    mix = parse_color_talla(MAR_XLSX) + parse_color_talla(RIO_XLSX)
    return metas, consumos, mix


def build_plan_rows(metas: dict, consumos: dict) -> list[dict]:
    cortado = lote_cortado_meta_kids()
    rows: list[dict] = []
    for prio, etiqueta in enumerate(PRIORIDAD_ORDEN, 1):
        modelo, genero = etiqueta.split()[0], etiqueta.split()[1]
        pct = PCT_KIDS if genero == "KIDS" else PCT_ADULTOS
        for color, meta in metas[modelo][genero].items():
            ya = cortado.get(color, 0) if modelo == "MAR" and genero == "KIDS" else 0
            rows.append({
                "prio": prio, "orden": etiqueta, "modelo": modelo, "genero": genero,
                "color": color, "meta": meta, "ya_cortado": ya, "pct": pct,
                "consumo": consumos[modelo][genero],
                "inventario": tela_stock(color),
            })
    return rows


def style_header(ws, row: int, cols: int) -> None:
    for c in range(1, cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        cell.border = BORDER


def style_input(cell) -> None:
    cell.fill = INPUT_FILL
    cell.border = BORDER


def auto_width(ws, mx: int = 22) -> None:
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        ws.column_dimensions[letter].width = min(max(len(str(c.value or "")) for c in col) + 2, mx)


def write_workbook(path: Path, metas: dict, consumos: dict, mix: list[dict]) -> None:
    wb = Workbook()
    cortado = lote_cortado_meta_kids()
    plan_rows = build_plan_rows(metas, consumos)

    # ── 1. INSTRUCCIONES ──
    ws0 = wb.active
    ws0.title = "INSTRUCCIONES"
    lines = [
        "PLAN DE PRODUCCIÓN MAR / RIO — Guía rápida",
        "",
        "1. Edita celdas AMARILLAS en PARAMETROS (% objetivo, inventario kg, und ya cortadas).",
        "2. PLAN COLORES recalcula solo con fórmulas (pendiente, objetivo, und final, kg).",
        "3. Prioridad de tela: P1 Rio KIDS → P2 Mar KIDS → P3-P6 adultos (50% meta).",
        "4. Lote Mar Kids ya cortado = UND de producción WIP — NO resta kg del inventario.",
        "5. Detalle por talla en pestañas: RIO KIDS, MAR KIDS, MAR CAB-DAMA, RIO CAB-DAMA.",
        "",
        "Orden prioridad:",
        "  P1 — RIO KIDS (primero — Mar ya tiene lote en corte)",
        "  P2 — MAR KIDS",
        "  P3 — MAR CAB  |  P4 — MAR DAMA  |  P5 — RIO CAB  |  P6 — RIO DAMA (50% meta máx)",
    ]
    for i, t in enumerate(lines, 1):
        ws0.cell(i, 1, t)
        if i == 1:
            ws0.cell(i, 1).font = Font(bold=True, size=14)
    auto_width(ws0)

    # ── 2. PARAMETROS ──
    ws_p = wb.create_sheet("PARAMETROS")
    ws_p["A1"] = "PARÁMETROS EDITABLES (celdas amarillas)"
    ws_p["A1"].font = Font(bold=True, size=12)
    ws_p["A3"], ws_p["B3"] = "% Objetivo KIDS", PCT_KIDS
    ws_p["A4"], ws_p["B4"] = "% Objetivo CAB/DAMA", PCT_ADULTOS
    style_input(ws_p["B3"])
    style_input(ws_p["B4"])

    ws_p["A6"] = "Inventario tela Jabón (kg) — foto actual"
    ws_p["A6"].font = Font(bold=True)
    ws_p.append([])
    inv_start = 8
    ws_p.cell(inv_start, 1, "Color")
    ws_p.cell(inv_start, 2, "Inventario kg")
    style_header(ws_p, inv_start, 2)
    inv_map: dict[str, int] = {}
    r = inv_start + 1
    for color in sorted(TELA_KG, key=lambda c: -TELA_KG[c]):
        ws_p.cell(r, 1, color)
        ws_p.cell(r, 2, round(TELA_KG[color], 2))
        style_input(ws_p.cell(r, 2))
        inv_map[color] = r
        inv_map["Púrpura"] = inv_map.get("Morado", r) if color == "Morado" else inv_map.get("Púrpura")
        if color == "Morado":
            inv_map["Púrpura"] = r
        r += 1
    inv_end = r - 1

    ws_p.cell(r + 1, 1, "Und ya cortadas Mar KIDS (lote producción — solo descuenta meta)")
    ws_p.cell(r + 1, 1).font = Font(bold=True)
    lote_start = r + 3
    ws_p.cell(lote_start, 1, "Color meta Mar KIDS")
    ws_p.cell(lote_start, 2, "Und cortadas")
    style_header(ws_p, lote_start, 2)
    lote_map: dict[str, int] = {}
    lr = lote_start + 1
    for color in sorted(metas["MAR"]["KIDS"], key=lambda c: -metas["MAR"]["KIDS"][c]):
        ws_p.cell(lr, 1, color)
        ws_p.cell(lr, 2, round(cortado.get(color, 0), 1))
        style_input(ws_p.cell(lr, 2))
        lote_map[color] = lr
        lr += 1
    lote_end = lr - 1

    # Named refs for formulas
    pct_kids_ref = "$B$3"
    pct_adult_ref = "$B$4"

    # ── 3. METAS (referencia) ──
    ws_m = wb.create_sheet("METAS")
    ws_m.append(["Modelo", "Género", "Color", "Meta máx Excel"])
    style_header(ws_m, 1, 4)
    meta_lookup: dict[tuple, int] = {}
    for modelo in ("MAR", "RIO"):
        for gen in ("KIDS", "CAB", "DAMA"):
            for color, mx in sorted(metas[modelo][gen].items(), key=lambda x: -x[1]):
                ws_m.append([modelo, gen, color, mx])
                meta_lookup[(modelo, gen, color)] = mx
    meta_end = ws_m.max_row
    auto_width(ws_m)

    # ── 4. MIX TALLAS (referencia Excel) ──
    ws_mix = wb.create_sheet("MIX TALLAS")
    ws_mix.append(["Modelo", "Género", "Color", "Talla", "Und máx Excel", "Total color"])
    style_header(ws_mix, 1, 6)
    mix_lookup: dict[tuple, dict] = {}
    for m in mix:
        ws_mix.append([m["modelo"], m["genero"], m["color"], m["talla"], m["und_max"], m["total_color"]])
        mix_lookup[(m["modelo"], m["genero"], m["color"], m["talla"])] = m
    mix_end = ws_mix.max_row
    auto_width(ws_mix)

    # ── 5. PLAN COLORES (fórmulas) ──
    ws_plan = wb.create_sheet("PLAN COLORES")
    headers = [
        "P", "Línea", "Modelo", "Género", "Color", "Meta máx", "Ya cortado", "Pendiente",
        "% Obj", "Und objetivo", "Consumo kg/und", "Inventario kg", "Kg usado antes",
        "Saldo kg", "Und max tela", "Und FINAL", "Kg usar", "Estado",
    ]
    ws_plan.append(headers)
    style_header(ws_plan, 1, len(headers))
    plan_start = 2

    def inv_formula(color_cell: str) -> str:
        return (
            f'=IFERROR(INDEX(PARAMETROS!$B${inv_start + 1}:$B${inv_end},'
            f'MATCH({color_cell},PARAMETROS!$A${inv_start + 1}:$A${inv_end},0)),'
            f'IFERROR(INDEX(PARAMETROS!$B${inv_start + 1}:$B${inv_end},'
            f'MATCH("Morado",PARAMETROS!$A${inv_start + 1}:$A${inv_end},0)),0))'
        )

    def lote_formula(color_cell: str, genero_cell: str, modelo_cell: str) -> str:
        return (
            f'=IF(AND({modelo_cell}="MAR",{genero_cell}="KIDS"),'
            f'IFERROR(INDEX(PARAMETROS!$B${lote_start + 1}:$B${lote_end},'
            f'MATCH({color_cell},PARAMETROS!$A${lote_start + 1}:$A${lote_end},0)),0),0)'
        )

    for i, pr in enumerate(plan_rows):
        r = plan_start + i
        ws_plan.cell(r, 1, pr["prio"])
        ws_plan.cell(r, 2, pr["orden"])
        ws_plan.cell(r, 3, pr["modelo"])
        ws_plan.cell(r, 4, pr["genero"])
        ws_plan.cell(r, 5, pr["color"])
        ws_plan.cell(r, 6, pr["meta"])
        ws_plan.cell(r, 7, lote_formula("E" + str(r), "D" + str(r), "C" + str(r)))
        ws_plan.cell(r, 8, f"=MAX(0,F{r}-G{r})")
        ws_plan.cell(r, 9, f'=IF(D{r}="KIDS",PARAMETROS!{pct_kids_ref},PARAMETROS!{pct_adult_ref})')
        ws_plan.cell(r, 9).number_format = "0%"
        ws_plan.cell(r, 10, f"=ROUND(H{r}*I{r},0)")
        ws_plan.cell(r, 11, pr["consumo"])
        ws_plan.cell(r, 12, inv_formula("E" + str(r)))
        if r == plan_start:
            ws_plan.cell(r, 13, 0)
        else:
            ws_plan.cell(r, 13, f'=SUMIFS($Q${plan_start}:Q{r - 1},$E${plan_start}:$E{r - 1},E{r})')
        ws_plan.cell(r, 14, f"=MAX(0,L{r}-M{r})")
        ws_plan.cell(r, 15, f'=IF(N{r}<{MIN_KG},0,FLOOR(N{r}/K{r},1))')
        ws_plan.cell(r, 16, f"=MIN(J{r},O{r})")
        ws_plan.cell(r, 17, f"=P{r}*K{r}")
        ws_plan.cell(r, 18, f'=IF(P{r}=0,"SIN TELA",IF(P{r}<J{r},"PARCIAL","OK"))')
        if pr["genero"] == "KIDS":
            for c in range(1, len(headers) + 1):
                ws_plan.cell(r, c).fill = KIDS_FILL

    plan_end = plan_start + len(plan_rows) - 1
    tr = plan_end + 2
    ws_plan.cell(tr, 2, "TOTALES")
    ws_plan.cell(tr, 16, f"=SUM(P{plan_start}:P{plan_end})")
    ws_plan.cell(tr, 17, f"=SUM(Q{plan_start}:Q{plan_end})")
    auto_width(ws_plan)

    # ── 6-9. DETALLE POR TALLA (4 pestañas) ──
    sections = [
        ("RIO KIDS", "RIO", "KIDS"),
        ("MAR KIDS", "MAR", "KIDS"),
        ("MAR CAB-DAMA", "MAR", ("CAB", "DAMA")),
        ("RIO CAB-DAMA", "RIO", ("CAB", "DAMA")),
    ]

    for sheet_name, modelo_filt, gen_filt in sections:
        ws_t = wb.create_sheet(sheet_name[:31])
        th = ["Modelo", "Género", "Color", "Talla", "Und máx Excel (mix)", "Total color Excel",
              "Und FINAL color", "Und talla A PRODUCIR"]
        ws_t.append(th)
        style_header(ws_t, 1, len(th))
        trow = 2

        gens = gen_filt if isinstance(gen_filt, tuple) else (gen_filt,)
        for pr in plan_rows:
            if pr["modelo"] != modelo_filt or pr["genero"] not in gens:
                continue
            # find plan row number for this color
            plan_r = None
            for j, p2 in enumerate(plan_rows):
                if p2["modelo"] == pr["modelo"] and p2["genero"] == pr["genero"] and p2["color"] == pr["color"]:
                    plan_r = plan_start + j
                    break
            if plan_r is None:
                continue

            color_mix = [m for m in mix if m["modelo"] == pr["modelo"] and m["genero"] == pr["genero"]
                         and m["color"] == pr["color"]]
            if not color_mix:
                continue

            for m in sorted(color_mix, key=lambda x: x["talla"]):
                ws_t.cell(trow, 1, m["modelo"])
                ws_t.cell(trow, 2, m["genero"])
                ws_t.cell(trow, 3, m["color"])
                ws_t.cell(trow, 4, m["talla"])
                ws_t.cell(trow, 5, m["und_max"])
                ws_t.cell(trow, 6, m["total_color"])
                ws_t.cell(trow, 7, f"='PLAN COLORES'!P{plan_r}")
                ws_t.cell(trow, 8, f'=IF(G{trow}=0,0,IF(F{trow}=0,0,ROUND(G{trow}*E{trow}/F{trow},0)))')
                trow += 1

        # Totals per color
        trow += 1
        ws_t.cell(trow, 3, "Verificar: suma tallas ≈ und color")
        auto_width(ws_t)

    # ── RESUMEN ──
    ws_r = wb.create_sheet("RESUMEN")
    ws_r["A1"] = "RESUMEN POR LÍNEA (desde PLAN COLORES)"
    ws_r["A1"].font = Font(bold=True, size=12)
    ws_r.append([])
    ws_r.cell(3, 1, "Línea")
    ws_r.cell(3, 2, "Und FINAL")
    ws_r.cell(3, 3, "Kg usar")
    style_header(ws_r, 3, 3)
    for i, etq in enumerate(PRIORIDAD_ORDEN, 4):
        ws_r.cell(i, 1, etq)
        ws_r.cell(i, 2, f"=SUMIF('PLAN COLORES'!$B${plan_start}:$B${plan_end},\"{etq}\",'PLAN COLORES'!$P${plan_start}:$P${plan_end})")
        ws_r.cell(i, 3, f"=SUMIF('PLAN COLORES'!$B${plan_start}:$B${plan_end},\"{etq}\",'PLAN COLORES'!$Q${plan_start}:$Q${plan_end})")
    ws_r.cell(len(PRIORIDAD_ORDEN) + 5, 1, "TOTAL")
    ws_r.cell(len(PRIORIDAD_ORDEN) + 5, 2, f"=SUM(P4:P{len(PRIORIDAD_ORDEN) + 3})")
    ws_r.cell(len(PRIORIDAD_ORDEN) + 5, 3, f"=SUM(C4:C{len(PRIORIDAD_ORDEN) + 3})")
    auto_width(ws_r)

    wb.save(path)


def eval_plan_python(metas: dict, consumos: dict) -> dict:
    """Evalúa plan en Python (validación) con misma lógica que fórmulas."""
    cortado = lote_cortado_meta_kids()
    saldo = dict(TELA_KG)
    saldo["Púrpura"] = saldo.get("Morado", 0)
    rows = build_plan_rows(metas, consumos)
    results = []
    kg_usado_acum: dict[str, float] = {}

    for pr in rows:
        color_key = canonical_color(pr["color"])
        ya = cortado.get(pr["color"], 0) if pr["modelo"] == "MAR" and pr["genero"] == "KIDS" else 0
        pend = max(0, pr["meta"] - ya)
        und_obj = int(pend * pr["pct"])
        inv = tela_stock(pr["color"])
        kg_antes = kg_usado_acum.get(color_key, 0)
        saldo_kg = max(0, inv - kg_antes)
        und_max = int(saldo_kg / pr["consumo"]) if saldo_kg >= MIN_KG else 0
        und_final = min(und_obj, und_max)
        kg = und_final * pr["consumo"]
        kg_usado_acum[color_key] = kg_antes + kg
        results.append({**pr, "und_objetivo": und_obj, "und_final": und_final, "kg": round(kg, 2)})

    by_line = {}
    for etq in PRIORIDAD_ORDEN:
        subset = [r for r in results if r["orden"] == etq]
        by_line[etq] = {
            "und": sum(r["und_final"] for r in subset),
            "kg": round(sum(r["kg"] for r in subset), 2),
        }
    return {"filas": results, "por_linea": by_line,
            "total_und": sum(r["und_final"] for r in results),
            "total_kg": round(sum(r["kg"] for r in results), 2)}


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    metas, consumos, mix = load_all()
    xlsx = OUT_DIR / "PLAN_PRIORIDADES_MAR_RIO_KIDS.xlsx"
    write_workbook(xlsx, metas, consumos, mix)

    summary = eval_plan_python(metas, consumos)
    summary["prioridad"] = PRIORIDAD_ORDEN
    summary["pct_kids"] = PCT_KIDS
    summary["pct_adultos"] = PCT_ADULTOS
    (OUT_DIR / "plan_prioridades.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(f"Excel generado: {xlsx}")
    print(f"Prioridad: {' → '.join(PRIORIDAD_ORDEN)}")
    print(f"KIDS {PCT_KIDS:.0%} | Adultos {PCT_ADULTOS:.0%}\n")
    for etq in PRIORIDAD_ORDEN:
        d = summary["por_linea"][etq]
        print(f"  {etq}: {d['und']} und / {d['kg']} kg")
    print(f"\nTOTAL: {summary['total_und']} und / {summary['total_kg']} kg")


if __name__ == "__main__":
    main()
