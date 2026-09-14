#!/usr/bin/env python3
"""
Planificación de producción Mar / Rio con prioridad KIDS.
Genera Excel con prioridades basado en tela disponible, lote ya cortado y metas sugeridas.
"""

from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ── Inventario tela JABON (kg) — foto usuario ──────────────────────────────
TELA_KG = {
    "Aguamarina": 348.34,
    "Amarillo Neón": 57.94,
    "Azul Lavanda": 221.00,
    "Azul Marino": 689.90,
    "Azul Rey": 271.46,
    "Blanco": 162.04,
    "Gris Claro": 47.68,
    "Lila": 188.44,
    "Morado": 94.20,
    "Negro": 657.16,
    "Púrpura": 0.00,
    "Rojo": 0.18,
    "Rosado Pastel": 31.44,
    "Verde Militar": 46.02,
    "Vinotinto": 175.38,
}

# Colores activos Mar Kids (lote ya cortado)
MAR_KIDS_COLORES = [
    "Verde Militar",
    "Vinotinto",
    "Azul Marino",
    "Azul Rey",
    "Rojo",
    "Gris Claro",
    "Azul Lavanda",  # Lavanda en producción
    "Aguamarina",
    "Rosado Pastel",
    "Negro",
    "Lila",
]

# Lote Mar Kids ya cortado — tallas totales del lote (rep. proporcional entre colores)
LOTE_CORTADO_TALLAS = {"8": 260, "10": 260, "12": 260, "14": 520}
LOTE_CORTADO_TOTAL = sum(LOTE_CORTADO_TALLAS.values())  # 1 300 und total del lote

# Consumo tela estimado (kg/unidad) — ajustar si tienen ficha técnica
CONSUMO_KG = {
    "KIDS": 0.132,
    "CAB": 0.205,
    "DAMA": 0.195,
}

# Meta sugerida placeholder por color/género (und) — reemplazar con Excel real
# Estructura: modelo -> genero -> color -> unidades sugeridas máximas
# Valores estimados conservadores para demostrar lógica; pegar datos reales del Excel.
META_SUGERIDA: dict[str, dict[str, dict[str, int]]] = {
    "MAR": {
        "KIDS": {c: 2600 for c in MAR_KIDS_COLORES},
        "CAB": {
            "Aguamarina": 800, "Azul Lavanda": 600, "Azul Marino": 1200,
            "Azul Rey": 700, "Blanco": 500, "Gris Claro": 400, "Lila": 500,
            "Morado": 350, "Negro": 1100, "Rosado Pastel": 300, "Verde Militar": 400,
            "Vinotinto": 550, "Amarillo Neón": 250,
        },
        "DAMA": {
            "Aguamarina": 900, "Azul Lavanda": 650, "Azul Marino": 1300,
            "Azul Rey": 750, "Blanco": 550, "Gris Claro": 450, "Lila": 550,
            "Morado": 400, "Negro": 1200, "Rosado Pastel": 350, "Verde Militar": 450,
            "Vinotinto": 600, "Amarillo Neón": 280,
        },
    },
    "RIO": {
        "KIDS": {c: 2200 for c in MAR_KIDS_COLORES if c != "Rojo"},
        "CAB": {
            "Aguamarina": 700, "Azul Lavanda": 550, "Azul Marino": 1000,
            "Azul Rey": 650, "Blanco": 450, "Gris Claro": 350, "Lila": 450,
            "Morado": 300, "Negro": 950, "Rosado Pastel": 280, "Verde Militar": 350,
            "Vinotinto": 500, "Amarillo Neón": 220,
        },
        "DAMA": {
            "Aguamarina": 800, "Azul Lavanda": 600, "Azul Marino": 1100,
            "Azul Rey": 700, "Blanco": 500, "Gris Claro": 400, "Lila": 500,
            "Morado": 350, "Negro": 1050, "Rosado Pastel": 320, "Verde Militar": 400,
            "Vinotinto": 550, "Amarillo Neón": 250,
        },
    },
}

PCT_KIDS_OBJETIVO = 0.50  # 50% del pendiente kids
PCT_ADULTOS_OBJETIVO = 1.00  # adultos: usar tela restante al máximo sugerido
MIN_KG_PRODUCIR = 5.0  # mínimo kg para considerar viable un color
PRIORIDAD_ORDEN = ["MAR KIDS", "RIO KIDS", "MAR CAB", "MAR DAMA", "RIO CAB", "RIO DAMA"]

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=10)
SUBHEADER_FILL = PatternFill("solid", fgColor="D9E2F3")
KIDS_FILL = PatternFill("solid", fgColor="FFF2CC")
ALERT_FILL = PatternFill("solid", fgColor="FCE4D6")
OK_FILL = PatternFill("solid", fgColor="E2EFDA")
THIN = Side(style="thin", color="AAAAAA")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def style_header(ws, row: int, cols: int) -> None:
    for c in range(1, cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER


def auto_width(ws, max_width: int = 22) -> None:
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        width = min(max(len(str(c.value or "")) for c in col) + 2, max_width)
        ws.column_dimensions[letter].width = width


def lote_por_color() -> dict[str, float]:
    """Distribuye el lote cortado proporcionalmente entre colores Mar Kids."""
    n = len(MAR_KIDS_COLORES)
    por_color = LOTE_CORTADO_TOTAL / n
    return {c: por_color for c in MAR_KIDS_COLORES}


def kg_usado_lote() -> dict[str, float]:
    usado = {}
    for color, und in lote_por_color().items():
        usado[color] = und * CONSUMO_KG["KIDS"]
    return usado


def tela_disponible_neta() -> dict[str, float]:
    usado = kg_usado_lote()
    neto = {}
    for color, kg in TELA_KG.items():
        neto[color] = max(0.0, kg - usado.get(color, 0.0))
    return neto


def calc_prioridades() -> list[dict]:
    """Calcula prioridades de producción por modelo/género/color."""
    neto = tela_disponible_neta()
    cortado = lote_por_color()
    filas = []

    for prio_idx, etiqueta in enumerate(PRIORIDAD_ORDEN, 1):
        partes = etiqueta.split()
        modelo, genero = partes[0], partes[1]
        pct = PCT_KIDS_OBJETIVO if genero == "KIDS" else PCT_ADULTOS_OBJETIVO

        metas = META_SUGERIDA.get(modelo, {}).get(genero, {})
        for color, meta in sorted(metas.items(), key=lambda x: -neto.get(x[0], 0)):
            tela = neto.get(color, 0.0)
            if tela < MIN_KG_PRODUCIR:
                filas.append({
                    "prioridad": prio_idx,
                    "orden": etiqueta,
                    "modelo": modelo,
                    "genero": genero,
                    "color": color,
                    "meta_sugerida": meta,
                    "ya_cortado": cortado.get(color, 0) if modelo == "MAR" and genero == "KIDS" else 0,
                    "pendiente_meta": max(0, meta - cortado.get(color, 0)) if modelo == "MAR" and genero == "KIDS" else meta,
                    "objetivo_pct": pct,
                    "und_objetivo": 0,
                    "und_por_tela": 0,
                    "und_asignar": 0,
                    "kg_necesarios": 0,
                    "tela_disponible_kg": round(tela, 2),
                    "estado": "SIN TELA" if tela < MIN_KG_PRODUCIR else "PENDIENTE",
                    "nota": "Stock crítico — excluir o esperar compra" if tela < MIN_KG_PRODUCIR else "",
                })
                continue

            pendiente = max(0, meta - cortado.get(color, 0)) if modelo == "MAR" and genero == "KIDS" else meta
            und_obj = int(pendiente * pct)
            consumo = CONSUMO_KG[genero]
            und_tela = int(tela / consumo)
            und_asignar = min(und_obj, und_tela)
            kg_nec = und_asignar * consumo

            if und_asignar == 0:
                estado = "SIN TELA"
            elif und_asignar < und_obj:
                estado = "PARCIAL (limitado tela)"
            else:
                estado = "OK"

            nota = ""
            if color == "Rojo":
                nota = "Stock 0.18 kg — no viable"
            elif tela > 400:
                nota = "Alta flexibilidad — puede repartirse entre modelos"

            filas.append({
                "prioridad": prio_idx,
                "orden": etiqueta,
                "modelo": modelo,
                "genero": genero,
                "color": color,
                "meta_sugerida": meta,
                "ya_cortado": round(cortado.get(color, 0), 1) if modelo == "MAR" and genero == "KIDS" else 0,
                "pendiente_meta": pendiente,
                "objetivo_pct": pct,
                "und_objetivo": und_obj,
                "und_por_tela": und_tela,
                "und_asignar": und_asignar,
                "kg_necesarios": round(kg_nec, 2),
                "tela_disponible_kg": round(tela, 2),
                "estado": estado,
                "nota": nota,
            })

    return filas


def simular_consumo_secuencial(filas: list[dict]) -> list[dict]:
    """Descuenta tela en orden de prioridad; adultos comparten tela restante por color."""
    saldo = tela_disponible_neta().copy()
    resultado: list[dict] = []
    adultos_pendientes: dict[str, list[dict]] = {}

    # Fase 1: KIDS (prioridad estricta)
    kids_filas = [f for f in filas if f["genero"] == "KIDS"]
    adult_filas = [f for f in filas if f["genero"] != "KIDS"]

    for f in sorted(kids_filas, key=lambda x: (x["prioridad"], -x["tela_disponible_kg"])):
        color = f["color"]
        tela = saldo.get(color, 0.0)
        if tela < MIN_KG_PRODUCIR or f["estado"] == "SIN TELA":
            resultado.append({**f, "und_asignar_final": 0, "kg_usar_final": 0, "tela_restante_kg": round(tela, 2)})
            continue
        consumo = CONSUMO_KG["KIDS"]
        und = min(f["und_objetivo"], int(tela / consumo))
        kg = und * consumo
        saldo[color] = max(0.0, tela - kg)
        estado = "OK" if und == f["und_objetivo"] and und > 0 else ("PARCIAL (limitado tela)" if und > 0 else "SIN TELA")
        resultado.append({**f, "und_asignar_final": und, "kg_usar_final": round(kg, 2), "tela_restante_kg": round(saldo[color], 2), "estado": estado})

    # Fase 2: Adultos — reparto flexible por color según peso de meta sugerida
    for f in adult_filas:
        adultos_pendientes.setdefault(f["color"], []).append(f)

    for color, grupo in adultos_pendientes.items():
        tela = saldo.get(color, 0.0)
        if tela < MIN_KG_PRODUCIR:
            for f in grupo:
                resultado.append({**f, "und_asignar_final": 0, "kg_usar_final": 0, "tela_restante_kg": round(tela, 2), "estado": "SIN TELA"})
            continue

        # Peso = meta sugerida; reparte tela restante proporcionalmente
        peso_total = sum(g["und_objetivo"] for g in grupo) or 1
        asignaciones: list[dict] = []
        tela_usada = 0.0

        for f in sorted(grupo, key=lambda x: x["prioridad"]):
            share = f["und_objetivo"] / peso_total
            tela_share = tela * share
            consumo = CONSUMO_KG[f["genero"]]
            und = min(f["und_objetivo"], int(tela_share / consumo))
            kg = und * consumo
            tela_usada += kg
            estado = "OK" if und == f["und_objetivo"] and und > 0 else ("PARCIAL (limitado tela)" if und > 0 else "SIN TELA")
            asignaciones.append({**f, "und_asignar_final": und, "kg_usar_final": round(kg, 2), "estado": estado})

        saldo[color] = max(0.0, tela - tela_usada)
        for a in asignaciones:
            a["tela_restante_kg"] = round(saldo[color], 2)
            resultado.append(a)

    return sorted(resultado, key=lambda x: (x["prioridad"], x["modelo"], x["genero"], x["color"]))


def write_excel(path: Path, filas: list[dict]) -> None:
    wb = Workbook()

    # ── Hoja 1: Resumen ejecutivo ──
    ws = wb.active
    ws.title = "RESUMEN"
    ws["A1"] = "PLAN DE PRIORIDADES — MAR / RIO (TELA JABÓN)"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:F1")

    resumen = [
        ("", ""),
        ("Total tela disponible (kg)", round(sum(TELA_KG.values()), 2)),
        ("Tela usada lote Mar Kids ya cortado (kg)", round(sum(kg_usado_lote().values()), 2)),
        ("Tela neta disponible (kg)", round(sum(tela_disponible_neta().values()), 2)),
        ("Lote Mar Kids cortado (und total)", LOTE_CORTADO_TOTAL),
        ("Und por color en lote (promedio)", round(LOTE_CORTADO_TOTAL / len(MAR_KIDS_COLORES), 1)),
        ("Objetivo Kids (% pendiente)", f"{PCT_KIDS_OBJETIVO:.0%}"),
        ("", ""),
        ("ORDEN DE PRIORIDAD", ""),
    ]
    for i, (k, v) in enumerate(resumen, 3):
        ws.cell(row=i, column=1, value=k)
        ws.cell(row=i, column=2, value=v)

    row = len(resumen) + 3
    for i, p in enumerate(PRIORIDAD_ORDEN, 1):
        ws.cell(row=row, column=1, value=f"P{i}")
        ws.cell(row=row, column=2, value=p)
        ws.cell(row=row, column=1).fill = KIDS_FILL if "KIDS" in p else SUBHEADER_FILL
        row += 1

    row += 1
    ws.cell(row=row, column=1, value="REGLAS DE FLEXIBILIDAD").font = Font(bold=True)
    row += 1
    reglas = [
        "1. KIDS primero (Mar Kids → Rio Kids) al 50% del pendiente tras descontar lote cortado.",
        "2. Con tela restante: Mar CAB/DAMA y Rio CAB/DAMA según stock por color.",
        "3. Colores con >400 kg (Azul Marino, Negro): flexibles entre modelos/géneros.",
        "4. Rojo (0.18 kg) y Púrpura (0 kg): EXCLUIR de producción.",
        "5. Si un color no alcanza para un modelo, reasignar a otro modelo del mismo color.",
        "6. Actualizar columnas META con datos reales de los Excel de proyección.",
    ]
    for r in reglas:
        ws.cell(row=row, column=1, value=r)
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        row += 1

    auto_width(ws)

    # ── Hoja 2: Inventario tela ──
    ws2 = wb.create_sheet("INVENTARIO TELA")
    headers = ["Color", "Stock kg", "Usado lote Mar Kids", "Disponible neto kg", "Und max KIDS", "Und max CAB", "Und max DAMA", "Alerta"]
    ws2.append(headers)
    style_header(ws2, 1, len(headers))

    for color, kg in sorted(TELA_KG.items(), key=lambda x: -x[1]):
        usado = kg_usado_lote().get(color, 0)
        disp = max(0, kg - usado)
        alerta = ""
        if kg < MIN_KG_PRODUCIR:
            alerta = "SIN STOCK"
        elif disp > 400:
            alerta = "ALTA — flexibilidad total"
        elif disp < 30:
            alerta = "BAJA — solo kids parcial"

        ws2.append([
            color, round(kg, 2), round(usado, 2), round(disp, 2),
            int(disp / CONSUMO_KG["KIDS"]),
            int(disp / CONSUMO_KG["CAB"]),
            int(disp / CONSUMO_KG["DAMA"]),
            alerta,
        ])

    auto_width(ws2)

    # ── Hoja 3: Mar Kids lote cortado ──
    ws3 = wb.create_sheet("MAR KIDS CORTADO")
    ws3.append(["Detalle lote Mar Kids ya en corte"])
    ws3["A1"].font = Font(bold=True, size=12)
    ws3.append([])
    ws3.append(["Talla", "Und lote total"])
    for t, u in LOTE_CORTADO_TALLAS.items():
        ws3.append([t, u])
    ws3.append(["TOTAL", LOTE_CORTADO_TOTAL])
    ws3.append([])
    ws3.append(["Color", "Und cortadas (prop.)", "Meta sugerida", "Pendiente", "Objetivo 50%", "Tela disp. kg"])
    style_header(ws3, ws3.max_row, 6)

    cortado = lote_por_color()
    for color in MAR_KIDS_COLORES:
        meta = META_SUGERIDA["MAR"]["KIDS"].get(color, 0)
        pend = max(0, meta - cortado[color])
        obj = int(pend * PCT_KIDS_OBJETIVO)
        ws3.append([
            color, round(cortado[color], 1), meta, int(pend), obj,
            round(tela_disponible_neta().get(color, 0), 2),
        ])

    auto_width(ws3)

    # ── Hoja 4: Prioridades producción ──
    ws4 = wb.create_sheet("PRIORIDADES PRODUCCION")
    cols = [
        "Prioridad", "Orden", "Modelo", "Género", "Color",
        "Meta sugerida", "Ya cortado", "Pendiente", "% Objetivo",
        "Und objetivo", "Und asignar FINAL", "Kg usar", "Tela restante kg",
        "Estado", "Nota",
    ]
    ws4.append(cols)
    style_header(ws4, 1, len(cols))

    total_und = 0
    total_kg = 0
    for f in filas:
        ws4.append([
            f["prioridad"], f["orden"], f["modelo"], f["genero"], f["color"],
            f["meta_sugerida"], f["ya_cortado"], f["pendiente_meta"],
            f"{f['objetivo_pct']:.0%}",
            f["und_objetivo"], f.get("und_asignar_final", 0), f.get("kg_usar_final", 0),
            f.get("tela_restante_kg", f["tela_disponible_kg"]),
            f["estado"], f["nota"],
        ])
        total_und += f.get("und_asignar_final", 0)
        total_kg += f.get("kg_usar_final", 0)

        r = ws4.max_row
        if f["genero"] == "KIDS":
            for c in range(1, len(cols) + 1):
                ws4.cell(row=r, column=c).fill = KIDS_FILL
        if f["estado"] == "SIN TELA":
            ws4.cell(row=r, column=14).fill = ALERT_FILL
        elif f["estado"] == "OK":
            ws4.cell(row=r, column=14).fill = OK_FILL

    ws4.append([])
    ws4.append(["TOTALES", "", "", "", "", "", "", "", "", "", total_und, round(total_kg, 2)])

    auto_width(ws4)

    # ── Hoja 5: Por color (vista flexibilidad) ──
    ws5 = wb.create_sheet("FLEXIBILIDAD POR COLOR")
    ws5.append(["Color", "Tela neta kg", "Mar Kids", "Rio Kids", "Mar CAB", "Mar DAMA", "Rio CAB", "Rio DAMA", "Recomendación"])
    style_header(ws5, 1, 9)

    by_color: dict[str, dict[str, int]] = {}
    for f in filas:
        c = f["color"]
        by_color.setdefault(c, {})
        key = f"{f['modelo']} {f['genero']}"
        by_color[c][key] = f.get("und_asignar_final", 0)

    for color in sorted(TELA_KG.keys(), key=lambda c: -tela_disponible_neta().get(c, 0)):
        tela = tela_disponible_neta().get(color, 0)
        rec = ""
        if tela < MIN_KG_PRODUCIR:
            rec = "No producir — sin tela"
        elif tela > 500:
            rec = "Priorizar CAB/DAMA ambos modelos + completar kids"
        elif tela > 150:
            rec = "Kids 50% + balance CAB/DAMA"
        else:
            rec = "Solo KIDS parcial"

        ws5.append([
            color, round(tela, 2),
            by_color.get(color, {}).get("MAR KIDS", 0),
            by_color.get(color, {}).get("RIO KIDS", 0),
            by_color.get(color, {}).get("MAR CAB", 0),
            by_color.get(color, {}).get("MAR DAMA", 0),
            by_color.get(color, {}).get("RIO CAB", 0),
            by_color.get(color, {}).get("RIO DAMA", 0),
            rec,
        ])

    auto_width(ws5)

    wb.save(path)


def main() -> None:
    out_dir = Path("/workspace/output")
    out_dir.mkdir(exist_ok=True)

    filas = calc_prioridades()
    filas = simular_consumo_secuencial(filas)

    xlsx_path = out_dir / "PLAN_PRIORIDADES_MAR_RIO_KIDS.xlsx"
    write_excel(xlsx_path, filas)

    summary = {
        "tela_total_kg": round(sum(TELA_KG.values()), 2),
        "tela_neta_kg": round(sum(tela_disponible_neta().values()), 2),
        "lote_cortado_und": LOTE_CORTADO_TOTAL,
        "total_und_plan": sum(f.get("und_asignar_final", 0) for f in filas),
        "total_kg_plan": round(sum(f.get("kg_usar_final", 0) for f in filas), 2),
        "prioridades": PRIORIDAD_ORDEN,
        "filas": filas,
    }
    json_path = out_dir / "plan_prioridades.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Excel generado: {xlsx_path}")
    print(f"JSON generado: {json_path}")
    print(f"Total unidades planificadas: {summary['total_und_plan']}")
    print(f"Total kg a usar: {summary['total_kg_plan']}")


if __name__ == "__main__":
    main()
