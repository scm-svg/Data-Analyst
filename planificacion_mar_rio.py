#!/usr/bin/env python3
"""
Planificación Mar / Rio — prioridad KIDS, flexibilidad por color.

IMPORTANTE — Lote Mar Kids ya cortado:
  • Las tallas (8=260, 10=260, 12=260, 14=520) son UNIDADES (und), total 1.300 und.
  • Repartidas proporcionalmente entre 11 colores (~118 und/color).
  • Esa tela salió de PRODUCCIÓN (WIP), NO del inventario actual de la foto.
  • Solo se descuentan las UND ya cortadas de la meta Mar KIDS (50% del pendiente).
  • El inventario kg de la foto se usa COMPLETO para planificar lo que sigue.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ── Rutas ───────────────────────────────────────────────────────────────────
MAR_XLSX = Path("/home/ubuntu/.cursor/projects/workspace/uploads/MAR_PROYECCION_CANTIDADES_SUGERIDAS__2__23dd.xlsx")
RIO_XLSX = Path("/home/ubuntu/.cursor/projects/workspace/uploads/RIO_PROYECCION_CANTIDADES_SUGERIDAS__2__cc77.xlsx")
OUT_DIR = Path("/workspace/output")

# ── Inventario tela JABON (kg) — foto usuario ───────────────────────────────
TELA_KG = {
    "Aguamarina": 348.34,
    "Amarillo Neón": 57.94,
    "Azul Lavanda": 221.00,
    "Azul Marino": 689.90,
    "Azul Rey": 271.46,
    "Blanco": 162.04,
    "Gris Claro": 47.68,
    "Lila": 188.44,
    "Morado": 94.20,  # = Púrpura en Excel
    "Negro": 657.16,
    "Rojo": 0.18,
    "Rosado Pastel": 31.44,
    "Verde Militar": 46.02,
    "Vinotinto": 175.38,
}

# Púrpura (Excel) = Morado (inventario físico)
COLOR_CANONICAL = {"Púrpura": "Morado", "Morado": "Morado"}


def canonical_color(color: str) -> str:
    return COLOR_CANONICAL.get(color, color)


def tela_stock(color: str) -> float:
    """Stock kg; Púrpura del Excel usa inventario Morado."""
    key = canonical_color(color)
    return TELA_KG.get(key, TELA_KG.get(color, 0.0))

# ── Lote Mar Kids ya cortado ────────────────────────────────────────────────
LOTE_CORTADO_COLORES = [
    "Verde Militar", "Vinotinto", "Azul Marino", "Azul Rey", "Rojo",
    "Gris Claro", "Azul Lavanda", "Aguamarina", "Rosado Pastel", "Negro", "Lila",
]
LOTE_CORTADO_TALLAS = {"8": 260, "10": 260, "12": 260, "14": 520}  # UND
LOTE_CORTADO_TOTAL = sum(LOTE_CORTADO_TALLAS.values())  # 1 300 und

# Mapeo nombres lote → Excel Mar KIDS (para descontar und de meta)
LOTE_A_META_KIDS = {
    "Verde Militar": "Verde Militar",
    "Vinotinto": None,  # cortado en kids pero no está en meta Excel KIDS
    "Azul Marino": "Azul Marino",
    "Azul Rey": "Azul Rey",
    "Rojo": "Rojo",
    "Gris Claro": None,
    "Azul Lavanda": "Azul Lavanda",  # Lavanda en planta
    "Aguamarina": "Aguamarina",
    "Rosado Pastel": "Rosado Pastel",
    "Negro": "Negro",
    "Lila": "Lila",
}

PCT_KIDS_OBJETIVO = 0.50
MIN_KG_PRODUCIR = 5.0
PRIORIDAD_ORDEN = ["MAR KIDS", "RIO KIDS", "MAR CAB", "MAR DAMA", "RIO CAB", "RIO DAMA"]

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=10)
KIDS_FILL = PatternFill("solid", fgColor="FFF2CC")
ALERT_FILL = PatternFill("solid", fgColor="FCE4D6")
OK_FILL = PatternFill("solid", fgColor="E2EFDA")
THIN = Side(style="thin", color="AAAAAA")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def parse_colores(path: Path) -> dict[str, dict[str, int]]:
    df = pd.read_excel(path, sheet_name="Cantidades por Colores", header=None)
    result: dict[str, dict[str, int]] = {"CAB": {}, "DAMA": {}, "KIDS": {}}
    current: str | None = None
    for _, row in df.iterrows():
        val0 = str(row[0]) if pd.notna(row[0]) else ""
        upper = val0.upper()
        if "CABALLERO" in upper:
            current = "CAB"
            continue
        if "DAMA" in upper and "CAB" not in upper:
            current = "DAMA"
            continue
        if "KIDS" in upper or "NIÑ" in upper:
            current = "KIDS"
            continue
        if val0.strip() in ("Color", "TOTAL", "nan", "") or not current:
            continue
        if pd.notna(row[3]):
            try:
                result[current][val0.strip()] = int(float(row[3]))
            except (ValueError, TypeError):
                pass
    return result


def parse_consumo(path: Path) -> dict[str, float]:
    df = pd.read_excel(path, sheet_name="Compra de Tela", header=None)
    consumo: dict[str, float] = {}
    for _, row in df.iterrows():
        v0 = str(row[0]).strip() if pd.notna(row[0]) else ""
        if v0 in ("CABALLERO", "DAMA", "KIDS") and pd.notna(row[1]):
            key = "CAB" if v0 == "CABALLERO" else v0
            consumo[key] = float(row[1])
    return consumo


def load_metas() -> tuple[dict, dict, dict, dict]:
    mar = parse_colores(MAR_XLSX)
    rio = parse_colores(RIO_XLSX)
    mar_consumo = parse_consumo(MAR_XLSX)
    rio_consumo = parse_consumo(RIO_XLSX)
    return (
        {"MAR": mar, "RIO": rio},
        {"MAR": mar_consumo, "RIO": rio_consumo},
        mar_consumo,
        rio_consumo,
    )


def lote_cortado_por_color() -> dict[str, float]:
    """1 300 und totales repartidas proporcionalmente (= und, NO kg)."""
    n = len(LOTE_CORTADO_COLORES)
    por_color = LOTE_CORTADO_TOTAL / n  # ~118.18 und/color
    return {c: por_color for c in LOTE_CORTADO_COLORES}


def lote_cortado_meta_kids() -> dict[str, float]:
    """Und ya cortadas descontables de meta Mar KIDS (solo colores en Excel)."""
    por_color = lote_cortado_por_color()
    descuento: dict[str, float] = {}
    for color_lote, und in por_color.items():
        meta_color = LOTE_A_META_KIDS.get(color_lote)
        if meta_color:
            descuento[meta_color] = descuento.get(meta_color, 0.0) + und
    return descuento


def tela_disponible() -> dict[str, float]:
    """Inventario actual completo (foto) — NO se descuenta lote de producción."""
    neto = dict(TELA_KG)
    neto["Púrpura"] = neto.get("Morado", 0.0)
    return neto


def calc_filas(metas: dict, consumos: dict) -> list[dict]:
    cortado_meta = lote_cortado_meta_kids()
    filas: list[dict] = []

    for prio_idx, etiqueta in enumerate(PRIORIDAD_ORDEN, 1):
        modelo, genero = etiqueta.split()[0], etiqueta.split()[1]
        pct = PCT_KIDS_OBJETIVO if genero == "KIDS" else 1.0
        consumo = consumos[modelo][genero]
        color_metas = metas[modelo][genero]

        for color, meta in sorted(color_metas.items(), key=lambda x: -tela_stock(x[0])):
            tela = tela_stock(color)  # inventario actual completo
            ya_cort = cortado_meta.get(color, 0) if modelo == "MAR" and genero == "KIDS" else 0
            pendiente = max(0, meta - ya_cort)
            und_obj = int(pendiente * pct)

            if tela < MIN_KG_PRODUCIR:
                filas.append(_fila(prio_idx, etiqueta, modelo, genero, color, meta, ya_cort,
                                   pendiente, pct, und_obj, consumo, tela, "SIN TELA",
                                   "Stock crítico — excluir o esperar compra"))
                continue

            und_tela = int(tela / consumo)
            und_asignar = min(und_obj, und_tela)
            nota = ""
            if color == "Rojo" and tela < 1:
                nota = "Stock 0.18 kg — no viable"
            elif tela > 400:
                nota = "Alta flexibilidad — repartir entre modelos"
            elif und_asignar < und_obj:
                nota = "Limitado por tela disponible"

            estado = "OK" if und_asignar == und_obj and und_asignar > 0 else (
                "PARCIAL (limitado tela)" if und_asignar > 0 else "SIN TELA"
            )
            filas.append(_fila(prio_idx, etiqueta, modelo, genero, color, meta, ya_cort,
                               pendiente, pct, und_obj, consumo, tela, estado, nota,
                               und_asignar=und_asignar))

    return filas


def _fila(prio, orden, modelo, genero, color, meta, ya_cort, pendiente, pct, und_obj,
          consumo, tela, estado, nota, und_asignar=0) -> dict:
    kg = und_asignar * consumo
    return {
        "prioridad": prio, "orden": orden, "modelo": modelo, "genero": genero,
        "color": color, "meta_sugerida": meta, "ya_cortado": round(ya_cort, 1),
        "pendiente_meta": int(pendiente), "objetivo_pct": pct, "und_objetivo": und_obj,
        "consumo_kg": consumo, "und_asignar": und_asignar,
        "kg_necesarios": round(kg, 2), "tela_disponible_kg": round(tela, 2),
        "estado": estado, "nota": nota,
    }


def simular_consumo(filas: list[dict]) -> list[dict]:
    saldo = tela_disponible().copy()
    resultado: list[dict] = []
    adultos_pend: dict[str, list[dict]] = {}

    kids = [f for f in filas if f["genero"] == "KIDS"]
    adultos = [f for f in filas if f["genero"] != "KIDS"]

    for f in sorted(kids, key=lambda x: (x["prioridad"], -x["tela_disponible_kg"])):
        color = f["color"]
        stock_key = canonical_color(color)
        tela = saldo.get(stock_key, tela_stock(color))

        if tela < MIN_KG_PRODUCIR or f["estado"] == "SIN TELA":
            resultado.append({**f, "und_asignar_final": 0, "kg_usar_final": 0,
                              "tela_restante_kg": round(tela, 2)})
            continue

        consumo = f["consumo_kg"]
        und = min(f["und_objetivo"], int(tela / consumo))
        kg = und * consumo
        saldo[stock_key] = max(0.0, tela - kg)
        if color == "Púrpura":
            saldo["Púrpura"] = saldo[stock_key]

        estado = "OK" if und == f["und_objetivo"] and und > 0 else (
            "PARCIAL (limitado tela)" if und > 0 else "SIN TELA"
        )
        resultado.append({**f, "und_asignar_final": und, "kg_usar_final": round(kg, 2),
                          "tela_restante_kg": round(saldo[stock_key], 2), "estado": estado})

    for f in adultos:
        adultos_pend.setdefault(f["color"], []).append(f)

    for color, grupo in adultos_pend.items():
        stock_key = canonical_color(color)
        tela = saldo.get(stock_key, 0.0)
        if tela < MIN_KG_PRODUCIR:
            for f in grupo:
                resultado.append({**f, "und_asignar_final": 0, "kg_usar_final": 0,
                                  "tela_restante_kg": round(tela, 2), "estado": "SIN TELA"})
            continue

        peso_total = sum(g["und_objetivo"] for g in grupo) or 1
        tela_usada = 0.0
        asignaciones = []

        for f in sorted(grupo, key=lambda x: x["prioridad"]):
            share = f["und_objetivo"] / peso_total
            tela_share = tela * share
            und = min(f["und_objetivo"], int(tela_share / f["consumo_kg"]))
            kg = und * f["consumo_kg"]
            tela_usada += kg
            estado = "OK" if und == f["und_objetivo"] and und > 0 else (
                "PARCIAL (limitado tela)" if und > 0 else "SIN TELA"
            )
            asignaciones.append({**f, "und_asignar_final": und, "kg_usar_final": round(kg, 2),
                                 "estado": estado})

        saldo[stock_key] = max(0.0, tela - tela_usada)
        for a in asignaciones:
            a["tela_restante_kg"] = round(saldo[stock_key], 2)
            resultado.append(a)

    return sorted(resultado, key=lambda x: (x["prioridad"], x["modelo"], x["genero"], x["color"]))


def write_excel(path: Path, filas: list[dict], metas: dict, consumos: dict) -> None:
    wb = Workbook()
    cortado = lote_cortado_meta_kids()

    # RESUMEN
    ws = wb.active
    ws.title = "RESUMEN"
    ws["A1"] = "PLAN PRIORIDADES MAR / RIO — DATOS REALES EXCEL"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:F1")

    mar_kids_max = sum(metas["MAR"]["KIDS"].values())
    rio_kids_max = sum(metas["RIO"]["KIDS"].values())
    resumen = [
        ("Fuente metas", "MAR/RIO PROYECCION CANTIDADES SUGERIDAS (2).xlsx"),
        ("Total tela disponible (kg)", round(sum(TELA_KG.values()), 2)),
        ("Inventario tela actual (kg) — foto", round(sum(TELA_KG.values()), 2)),
        ("Lote Mar Kids cortado (und) — tela de PRODUCCIÓN, no inventario", LOTE_CORTADO_TOTAL),
        ("Und/color lote (~118 und, rep. proporcional)", round(LOTE_CORTADO_TOTAL / len(LOTE_CORTADO_COLORES), 1)),
        ("Nota lote", "Solo descuenta UND de meta Mar KIDS; NO resta kg del inventario"),
        ("Meta máx Mar KIDS (Excel)", mar_kids_max),
        ("Meta máx Rio KIDS (Excel)", rio_kids_max),
        ("Objetivo KIDS", f"{PCT_KIDS_OBJETIVO:.0%} del pendiente (meta − cortado)"),
        ("Consumo Mar KIDS", f"{consumos['MAR']['KIDS']} kg/und"),
        ("Consumo Rio KIDS", f"{consumos['RIO']['KIDS']} kg/und"),
    ]
    for i, (k, v) in enumerate(resumen, 3):
        ws.cell(row=i, column=1, value=k)
        ws.cell(row=i, column=2, value=v)

    row = len(resumen) + 4
    ws.cell(row=row, column=1, value="ORDEN PRIORIDAD").font = Font(bold=True)
    row += 1
    for i, p in enumerate(PRIORIDAD_ORDEN, 1):
        ws.cell(row=row, column=1, value=f"P{i}")
        ws.cell(row=row, column=2, value=p)
        row += 1

    # INVENTARIO
    ws2 = wb.create_sheet("INVENTARIO TELA")
    cortado_meta = lote_cortado_meta_kids()
    h = ["Color", "Inventario kg (foto)", "Und ya cortadas Mar KIDS", "Max und Mar KIDS Excel",
         "Max und Rio KIDS", "Max und Mar CAB", "Alerta"]
    ws2.append(h)
    style_header(ws2, 1, len(h))
    for color in sorted(TELA_KG.keys(), key=lambda c: -TELA_KG[c]):
        kg = TELA_KG[color]
        alerta = "SIN STOCK" if kg < MIN_KG_PRODUCIR else (
            "ALTA flexibilidad" if kg > 400 else ("BAJA" if kg < 30 else "MEDIA")
        )
        ws2.append([
            color, round(kg, 2), round(cortado_meta.get(color, 0), 1),
            metas["MAR"]["KIDS"].get(color, 0),
            metas["RIO"]["KIDS"].get(color, 0),
            metas["MAR"]["CAB"].get(color, 0),
            alerta,
        ])
    auto_width(ws2)

    # MAR KIDS CORTADO vs OBJETIVO
    ws3 = wb.create_sheet("MAR KIDS OBJETIVO")
    ws3.append(["Color", "Meta máx Excel", "Ya cortado", "Pendiente", "Objetivo 50%",
                "Und asignar FINAL", "Tela disp kg", "Estado"])
    style_header(ws3, 1, 8)
    kids_filas = {f["color"]: f for f in filas if f["orden"] == "MAR KIDS"}
    for color, meta in sorted(metas["MAR"]["KIDS"].items(), key=lambda x: -x[1]):
        c = cortado.get(color, 0)
        pend = max(0, meta - c)
        obj = int(pend * PCT_KIDS_OBJETIVO)
        f = kids_filas.get(color, {})
        ws3.append([
            color, meta, round(c, 1), pend, obj,
            f.get("und_asignar_final", 0),
            f.get("tela_disponible_kg", round(tela_stock(color), 2)),
            f.get("estado", ""),
        ])
    auto_width(ws3)

    # PRIORIDADES
    ws4 = wb.create_sheet("PRIORIDADES PRODUCCION")
    cols = ["Prioridad", "Orden", "Modelo", "Género", "Color", "Meta máx", "Ya cortado",
            "Pendiente", "% Obj", "Und objetivo", "Und FINAL", "Kg usar", "Consumo kg/und",
            "Tela rest kg", "Estado", "Nota"]
    ws4.append(cols)
    style_header(ws4, 1, len(cols))
    total_und = total_kg = 0
    for f in filas:
        ws4.append([
            f["prioridad"], f["orden"], f["modelo"], f["genero"], f["color"],
            f["meta_sugerida"], f["ya_cortado"], f["pendiente_meta"],
            f"{f['objetivo_pct']:.0%}", f["und_objetivo"],
            f.get("und_asignar_final", 0), f.get("kg_usar_final", 0), f["consumo_kg"],
            f.get("tela_restante_kg", f["tela_disponible_kg"]),
            f["estado"], f["nota"],
        ])
        total_und += f.get("und_asignar_final", 0)
        total_kg += f.get("kg_usar_final", 0)
        r = ws4.max_row
        if f["genero"] == "KIDS":
            for c in range(1, len(cols) + 1):
                ws4.cell(row=r, column=c).fill = KIDS_FILL
    ws4.append(["", "TOTALES", "", "", "", "", "", "", "", "", total_und, round(total_kg, 2)])
    auto_width(ws4)

    # FLEXIBILIDAD POR COLOR
    ws5 = wb.create_sheet("FLEXIBILIDAD POR COLOR")
    ws5.append(["Color", "Tela neta kg", "Mar KIDS", "Rio KIDS", "Mar CAB", "Mar DAMA",
                "Rio CAB", "Rio DAMA", "Total und", "Recomendación"])
    style_header(ws5, 1, 10)
    by_color: dict[str, dict[str, int]] = {}
    for f in filas:
        by_color.setdefault(f["color"], {})
        by_color[f["color"]][f"{f['modelo']} {f['genero']}"] = f.get("und_asignar_final", 0)

    all_colors = sorted(set(list(TELA_KG.keys()) + list(by_color.keys())),
                        key=lambda c: -tela_stock(c))
    for color in all_colors:
        tela = tela_stock(color)
        vals = [by_color.get(color, {}).get(f"{m} {g}", 0)
                for m, g in [("MAR", "KIDS"), ("RIO", "KIDS"), ("MAR", "CAB"),
                             ("MAR", "DAMA"), ("RIO", "CAB"), ("RIO", "DAMA")]]
        tot = sum(vals)
        if tela < MIN_KG_PRODUCIR:
            rec = "NO PRODUCIR — sin tela"
        elif tela > 500:
            rec = "Kids 50% + repartir excedente Mar/Rio adultos"
        elif tela > 100:
            rec = "Kids prioritario + balance adultos"
        else:
            rec = "Solo KIDS parcial"
        ws5.append([color, round(tela, 2), *vals, tot, rec])
    auto_width(ws5)

    # METAS EXCEL (referencia)
    ws6 = wb.create_sheet("METAS EXCEL REF")
    ws6.append(["Modelo", "Género", "Color", "Máximo sugerido"])
    style_header(ws6, 1, 4)
    for modelo in ("MAR", "RIO"):
        for gen in ("KIDS", "CAB", "DAMA"):
            for color, mx in sorted(metas[modelo][gen].items(), key=lambda x: -x[1]):
                ws6.append([modelo, gen, color, mx])
    auto_width(ws6)

    wb.save(path)


def style_header(ws, row: int, cols: int) -> None:
    for c in range(1, cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER


def auto_width(ws, max_width: int = 24) -> None:
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        width = min(max(len(str(c.value or "")) for c in col) + 2, max_width)
        ws.column_dimensions[letter].width = width


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    metas_dict, consumos, mar_c, rio_c = load_metas()
    metas = metas_dict

    filas = calc_filas(metas, consumos)
    filas = simular_consumo(filas)

    xlsx = OUT_DIR / "PLAN_PRIORIDADES_MAR_RIO_KIDS.xlsx"
    write_excel(xlsx, filas, metas, consumos)

    summary = {
        "tela_inventario_kg": round(sum(TELA_KG.values()), 2),
        "lote_cortado_und": LOTE_CORTADO_TOTAL,
        "lote_cortado_nota": "Und de producción WIP — NO descuenta inventario kg",
        "lote_cortado_por_color_und": lote_cortado_por_color(),
        "lote_descuento_meta_kids_und": lote_cortado_meta_kids(),
        "meta_max_mar_kids": sum(metas["MAR"]["KIDS"].values()),
        "meta_max_rio_kids": sum(metas["RIO"]["KIDS"].values()),
        "consumo": {"MAR": mar_c, "RIO": rio_c},
        "total_und_plan": sum(f.get("und_asignar_final", 0) for f in filas),
        "total_kg_plan": round(sum(f.get("kg_usar_final", 0) for f in filas), 2),
        "por_prioridad": {},
        "filas": filas,
    }
    for p in PRIORIDAD_ORDEN:
        pf = [f for f in filas if f["orden"] == p]
        summary["por_prioridad"][p] = {
            "und": sum(f.get("und_asignar_final", 0) for f in pf),
            "kg": round(sum(f.get("kg_usar_final", 0) for f in pf), 2),
            "und_objetivo": sum(f["und_objetivo"] for f in pf),
        }

    json_path = OUT_DIR / "plan_prioridades.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Excel: {xlsx}")
    print(f"JSON:  {json_path}")
    print(f"\nInventario tela (foto): {summary['tela_inventario_kg']} kg")
    print(f"Lote cortado: {summary['lote_cortado_und']} und (NO resta del inventario)")
    print(f"Plan total: {summary['total_und_plan']} und / {summary['total_kg_plan']} kg\n")
    for p in PRIORIDAD_ORDEN:
        d = summary["por_prioridad"][p]
        print(f"  {p}: objetivo={d['und_objetivo']} und → asignado={d['und']} und ({d['kg']} kg)")


if __name__ == "__main__":
    main()
