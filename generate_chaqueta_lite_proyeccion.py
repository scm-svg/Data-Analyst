#!/usr/bin/env python3
"""Genera proyección de producción Chaqueta Lite (DAMA, XS–XL).

Referencia: ventas DAMA de CUADRO JACKET 2.0 (importado, producto similar).
Restricción: cierres QX Negro 0580 — 60 cm (748 und) y 75 cm (744 und).
"""

import json
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HTML_PATH = Path(__file__).resolve().parent / "Dashboard_Jacket_2_0 (3).html"
OUTPUT_PATH = Path(__file__).resolve().parent / "CHAQUETA_LITE_RANGO_PRODUCCION.xlsx"

PRODUCTO = "CHAQUETA LITE"
GENERO = "DAMA"
TALLAS = ["XS", "S", "M", "L", "XL"]
TORD = {"XS": 0, "S": 1, "M": 2, "L": 3, "XL": 4}
TALLAS_60CM = {"XS", "S", "M"}
TALLAS_75CM = {"L", "XL"}

# ── Parámetros de proyección ──
HIGH_SEASON_FACTOR = 1.25       # Temporada alta (diciembre)
SAFETY_STOCK_PCT = 0.15         # Stock de seguridad +15%
COVER_MONTHS_MIN = 2.5          # Cobertura mínima (meses, velocidad ajustada)
COVER_MONTHS_MAX = 3.5          # Cobertura máxima
MAX_PCT_ABOVE_MIN = 1.12        # Techo máximo = mín × 112%
NEW_STORE_RAMP = 0.85           # Ramp-up Barquisimeto (85% capacidad proxy)
WEB_SHARE_PCT = 0.06            # Web ~6% de red (PEDIDOS subestima canal web)
VELOCITY_MONTHS = 3             # Base: últimos 3 meses (Mar–May 2026)

# ── Insumo limitante: cierres ──
CIERRES_60CM = 748
CIERRES_75CM = 744

# ── Tiendas ──
PHYSICAL_STORES = ["SAMBIL", "GRIETA", "CERRO VERDE", "CHACAO", "GRAND PLAZ", "TOLON"]
NEW_STORE = "BARQUISIMETO"
WEB_STORE = "WEB"
EXCLUDE_STORES = {"CORPORATIVO", "PEDIDOS"}
BARQUISIMETO_PROXY = ["GRIETA", "CHACAO", "TOLON"]

# ── Estilos Excel ──
title_fill = PatternFill("solid", fgColor="1E3A5F")
sub_fill = PatternFill("solid", fgColor="4A7FB5")
color_fill = PatternFill("solid", fgColor="D6E4F0")
tot_fill = PatternFill("solid", fgColor="A8C8E8")
min_fill = PatternFill("solid", fgColor="FFF9C4")
max_fill = PatternFill("solid", fgColor="FFE0B2")
warn_fill = PatternFill("solid", fgColor="FFCDD2")
white_fill = PatternFill("solid", fgColor="FFFFFF")
thin = Side(style="thin", color="1E3A5F")
border = Border(left=thin, right=thin, top=thin, bottom=thin)
center = Alignment(horizontal="center", vertical="center")
left = Alignment(horizontal="left", vertical="center", wrap_text=True)


def load_jacket_data() -> dict:
    html = HTML_PATH.read_text(encoding="utf-8")
    match = re.search(r"var DATA=(\{.*?\});", html, re.DOTALL)
    if not match:
        raise ValueError("No se encontró DATA en el dashboard Jacket 2.0")
    return json.loads(match.group(1))


def analyze_reference(data: dict) -> dict:
    """Analiza ventas DAMA Jacket 2.0 como proxy."""
    rows = [r for r in data["raw_rows"] if r["genero"] == GENERO]
    months = data["meses_order"]
    vel_months = months[-VELOCITY_MONTHS:]

    by_month = {}
    for m in months:
        by_month[m] = sum(r["v"] for r in rows if r["mes"] == m and r["tienda"] not in EXCLUDE_STORES)

    vel_base = sum(by_month[m] for m in vel_months) / len(vel_months)
    vel_all = sum(by_month.values()) / len(months)
    dec_vel = by_month.get("diciembre-2025", 0)

    # Curva de tallas
    talla_tot = {t: 0 for t in TALLAS}
    for r in rows:
        if r["tienda"] not in EXCLUDE_STORES and r["talla"] in talla_tot:
            talla_tot[r["talla"]] += r["v"]
    talla_grand = sum(talla_tot.values())
    talla_pct = {t: talla_tot[t] / talla_grand if talla_grand else 0 for t in TALLAS}

    # Participación por tienda
    store_tot = {}
    for s in PHYSICAL_STORES:
        store_tot[s] = sum(r["v"] for r in rows if r["tienda"] == s)
    store_grand = sum(store_tot.values())
    store_share = {s: store_tot[s] / store_grand if store_grand else 0 for s in PHYSICAL_STORES}

    # Barquisimeto proxy
    n_months = len(months)
    proxy_monthly = sum(store_tot.get(s, 0) / n_months for s in BARQUISIMETO_PROXY) / len(BARQUISIMETO_PROXY)
    barq_monthly = proxy_monthly * NEW_STORE_RAMP

    web_monthly = vel_base * WEB_SHARE_PCT

    return {
        "vel_base": vel_base,
        "vel_all": vel_all,
        "dec_vel": dec_vel,
        "vel_months": vel_months,
        "talla_pct": talla_pct,
        "talla_tot": talla_tot,
        "store_share": store_share,
        "store_tot": store_tot,
        "barq_monthly": barq_monthly,
        "web_monthly": web_monthly,
        "months": months,
        "by_month": by_month,
    }


def calc_zipper_cap(talla_pct: dict) -> dict:
    """Calcula tope de producción según cierres disponibles."""
    pct_60 = sum(talla_pct[t] for t in TALLAS_60CM)
    pct_75 = sum(talla_pct[t] for t in TALLAS_75CM)
    cap_60 = int(CIERRES_60CM / pct_60) if pct_60 else 0
    cap_75 = int(CIERRES_75CM / pct_75) if pct_75 else 0
    cap_total = min(cap_60, cap_75)
    return {
        "pct_60": pct_60,
        "pct_75": pct_75,
        "cap_60": cap_60,
        "cap_75": cap_75,
        "cap_total": cap_total,
        "use_60_at_cap": round(cap_total * pct_60),
        "use_75_at_cap": round(cap_total * pct_75),
    }


def calc_production(ref: dict, zip_cap: dict) -> dict:
    """Calcula rango mínimo/máximo de producción."""
    vel_adj = ref["vel_base"] * HIGH_SEASON_FACTOR
    network_factor = 1 + (ref["barq_monthly"] + ref["web_monthly"]) / ref["vel_base"]
    vel_network = vel_adj * network_factor

    raw_min = round(vel_network * COVER_MONTHS_MIN * (1 + SAFETY_STOCK_PCT))
    raw_max = round(vel_network * COVER_MONTHS_MAX * (1 + SAFETY_STOCK_PCT))
    pct_max = round(raw_min * MAX_PCT_ABOVE_MIN)

    cap = zip_cap["cap_total"]
    zipper_limited = raw_min > cap

    if zipper_limited:
        # Demanda supera cierres: máximo = tope duro; mínimo = ~87% del tope (buffer cierres/defectos)
        prod_max = cap
        prod_min = round(cap * 0.87)
        prod_min = min(prod_min, prod_max - 1) if prod_max > 1 else prod_max
    else:
        prod_min = raw_min
        prod_max = min(max(raw_max, pct_max), cap)
        prod_max = max(prod_max, prod_min)

    return {
        "vel_adj": vel_adj,
        "vel_network": vel_network,
        "network_factor": network_factor,
        "raw_min": raw_min,
        "raw_max": raw_max,
        "prod_min": prod_min,
        "prod_max": prod_max,
        "zipper_limited": zipper_limited,
    }


def distribute_by_talla(total: int, talla_pct: dict) -> dict:
    """Distribuye unidades por talla respetando curva histórica."""
    result = {}
    allocated = 0
    for t in TALLAS[:-1]:
        qty = round(total * talla_pct[t])
        result[t] = qty
        allocated += qty
    result[TALLAS[-1]] = total - allocated
    return result


def distribute_by_store(total: int, ref: dict) -> dict:
    """Distribuye unidades por tienda incluyendo Barquisimeto y Web."""
    vel_base = ref["vel_base"]
    store_units = {}
    physical_total = 0

    for s in PHYSICAL_STORES:
        share = ref["store_share"].get(s, 0)
        qty = round(total * share * (vel_base / (vel_base + ref["barq_monthly"] + ref["web_monthly"])))
        store_units[s] = qty
        physical_total += qty

    barq = round(total * ref["barq_monthly"] / (vel_base + ref["barq_monthly"] + ref["web_monthly"]))
    web = round(total * ref["web_monthly"] / (vel_base + ref["barq_monthly"] + ref["web_monthly"]))
    store_units[NEW_STORE] = barq
    store_units[WEB_STORE] = web

    diff = total - sum(store_units.values())
    if diff != 0:
        top_store = max(PHYSICAL_STORES, key=lambda s: store_units[s])
        store_units[top_store] += diff

    return store_units


def distribute_store_talla(store_units: dict, talla_pct: dict) -> dict:
    """Matriz tienda × talla."""
    matrix = {}
    for store, total in store_units.items():
        matrix[store] = distribute_by_talla(total, talla_pct)
    return matrix


def style_cell(cell, fill=None, bold=False, align=center):
    if fill:
        cell.fill = fill
    if bold:
        cell.font = Font(bold=True)
    cell.alignment = align
    cell.border = border


def write_resumen(wb, ref, zip_cap, prod):
    ws = wb.create_sheet("Resumen", 0)
    rows = [
        [f"{PRODUCTO} — PROYECCIÓN DE PRODUCCIÓN (DAMA)"],
        [],
        ["Referencia analítica", "CUADRO JACKET 2.0 — ventas DAMA (importado, producto similar)"],
        ["Fuente datos", str(HTML_PATH.name)],
        ["Período referencia", f"Últimos {VELOCITY_MONTHS} meses: {', '.join(ref['vel_months'])}"],
        [],
        ["── VELOCIDAD ──"],
        ["Velocidad base (3m, red actual)", round(ref["vel_base"], 1), "und/mes"],
        ["Velocidad histórica promedio", round(ref["vel_all"], 1), "und/mes"],
        ["Diciembre 2025 (temporada alta ref.)", ref["dec_vel"], "und"],
        ["Factor temporada alta aplicado", HIGH_SEASON_FACTOR, "×"],
        ["Velocidad ajustada temporada alta", round(prod["vel_adj"], 1), "und/mes"],
        ["Factor expansión red (Barquisimeto + Web)", round(prod["network_factor"], 3), "×"],
        ["Velocidad red completa ajustada", round(prod["vel_network"], 1), "und/mes"],
        [],
        ["── COBERTURA Y STOCK DE SEGURIDAD ──"],
        ["Meses cobertura mínimo", COVER_MONTHS_MIN],
        ["Meses cobertura máximo", COVER_MONTHS_MAX],
        ["Stock de seguridad", f"{int(SAFETY_STOCK_PCT * 100)}%"],
        ["Demanda teórica mín (sin cap cierres)", prod["raw_min"], "und"],
        ["Demanda teórica máx (sin cap cierres)", prod["raw_max"], "und"],
        [],
        ["── INSUMO LIMITANTE: CIERRES QX NEGRO 0580 ──"],
        ["Cierre 60 cm (XS · S · M)", CIERRES_60CM, "und disponibles"],
        ["Cierre 75 cm (L · XL)", CIERRES_75CM, "und disponibles"],
        ["Curva tallas → % cierre 60 cm", f"{zip_cap['pct_60']*100:.1f}%"],
        ["Curva tallas → % cierre 75 cm", f"{zip_cap['pct_75']*100:.1f}%"],
        ["Tope producción (cierre 60 cm)", zip_cap["cap_60"], "und"],
        ["Tope producción (cierre 75 cm)", zip_cap["cap_75"], "und"],
        ["TOPE DURO PRODUCCIÓN", zip_cap["cap_total"], "und"],
        ["¿Limitado por cierres?", "SÍ" if prod["zipper_limited"] else "NO"],
        [],
        ["── RANGO DE PRODUCCIÓN SUGERIDO ──"],
        ["MÍNIMO (compromiso)", prod["prod_min"], "und"],
        ["MÁXIMO (techo con cierres)", prod["prod_max"], "und"],
        ["Rango de acción", prod["prod_max"] - prod["prod_min"], "und"],
        [],
        ["── TIENDAS ──"],
        ["Tiendas físicas incluidas", ", ".join(PHYSICAL_STORES)],
        ["Canal Web", "SÍ incluido"],
        ["Corporativo", "EXCLUIDO"],
        [f"Tienda nueva {NEW_STORE}", f"Promedio {BARQUISIMETO_PROXY} × {NEW_STORE_RAMP} ramp-up"],
        [f"Velocidad mensual {NEW_STORE} (proy.)", round(ref["barq_monthly"], 1), "und/mes"],
        [f"Velocidad mensual {WEB_STORE} (proy.)", round(ref["web_monthly"], 1), "und/mes"],
        [],
        ["Notas"],
        ["• Producto NUEVO manufacturado — sin stock inicial."],
        ["• Solo género DAMA, tallas XS a XL."],
        ["• Cierres 60 cm → XS, S, M | Cierres 75 cm → L, XL."],
        ["• La producción está limitada por cierres 60 cm (~902 und máx teórico)."],
        ["• Barquisimeto proyectada como promedio mensual Grieta + Chacao + Tolón."],
    ]
    for r, row in enumerate(rows, start=1):
        for c, val in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            if r == 1:
                cell.font = Font(bold=True, size=14, color="FFFFFF")
                cell.fill = title_fill
            elif row and row[0] and str(row[0]).startswith("──"):
                cell.font = Font(bold=True, color="1E3A5F")
            if r == 36 and c == 1:
                cell.font = Font(bold=True)
    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 14


def write_tallas_sheet(wb, ref, prod):
    ws = wb.create_sheet("Producción por Talla")
    talla_min = distribute_by_talla(prod["prod_min"], ref["talla_pct"])
    talla_max = distribute_by_talla(prod["prod_max"], ref["talla_pct"])

    ws.merge_cells("A1:G1")
    style_cell(ws.cell(row=1, column=1, value=f"{PRODUCTO} — CANTIDADES POR TALLA (MÍN / MÁX)"), title_fill, bold=True)
    ws.cell(row=2, column=1, value=f"{GENERO} · Curva basada en Jacket 2.0 DAMA").font = Font(italic=True)

    headers = ["Talla", "Curva %", "Cierre (cm)", "Mínimo", "Máximo", "Cierres Mín", "Cierres Máx"]
    for c, h in enumerate(headers, 1):
        style_cell(ws.cell(row=4, column=c, value=h), sub_fill, bold=True)

    cierres_map = {"XS": 60, "S": 60, "M": 60, "L": 75, "XL": 75}
    t_min_total = t_max_total = 0
    c60_min = c75_min = c60_max = c75_max = 0

    for i, t in enumerate(TALLAS, start=5):
        mn, mx = talla_min[t], talla_max[t]
        pct = ref["talla_pct"][t]
        cm = cierres_map[t]
        style_cell(ws.cell(row=i, column=1, value=t), color_fill, bold=True)
        ws.cell(row=i, column=2, value=f"{pct*100:.1f}%")
        ws.cell(row=i, column=3, value=cm)
        style_cell(ws.cell(row=i, column=4, value=mn), min_fill, bold=True)
        style_cell(ws.cell(row=i, column=5, value=mx), max_fill, bold=True)
        ws.cell(row=i, column=6, value=mn)
        ws.cell(row=i, column=7, value=mx)
        t_min_total += mn
        t_max_total += mx
        if cm == 60:
            c60_min += mn
            c60_max += mx
        else:
            c75_min += mn
            c75_max += mx

    r = len(TALLAS) + 5
    style_cell(ws.cell(row=r, column=1, value="TOTAL"), tot_fill, bold=True, align=left)
    style_cell(ws.cell(row=r, column=4, value=t_min_total), tot_fill, bold=True)
    style_cell(ws.cell(row=r, column=5, value=t_max_total), tot_fill, bold=True)
    style_cell(ws.cell(row=r, column=6, value=c60_min), tot_fill, bold=True)
    style_cell(ws.cell(row=r, column=7, value=c60_max), tot_fill, bold=True)

    r += 2
    style_cell(ws.cell(row=r, column=1, value="Disponible cierres 60 cm"), warn_fill if c60_max > CIERRES_60CM else color_fill, align=left)
    ws.cell(row=r, column=4, value=CIERRES_60CM)
    ws.cell(row=r, column=5, value=f"Usa máx {c60_max} ({c60_max/CIERRES_60CM*100:.0f}%)")

    r += 1
    style_cell(ws.cell(row=r, column=1, value="Disponible cierres 75 cm"), warn_fill if c75_max > CIERRES_75CM else color_fill, align=left)
    ws.cell(row=r, column=4, value=CIERRES_75CM)
    ws.cell(row=r, column=5, value=f"Usa máx {c75_max} ({c75_max/CIERRES_75CM*100:.0f}%)")

    for col in "ABCDEFG":
        ws.column_dimensions[col].width = 14
    ws.column_dimensions["A"].width = 18


def write_tiendas_sheet(wb, ref, prod):
    ws = wb.create_sheet("Distribución por Tienda")
    all_stores = PHYSICAL_STORES + [NEW_STORE, WEB_STORE]

    store_min = distribute_by_store(prod["prod_min"], ref)
    store_max = distribute_by_store(prod["prod_max"], ref)
    matrix_min = distribute_store_talla(store_min, ref["talla_pct"])
    matrix_max = distribute_store_talla(store_max, ref["talla_pct"])

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=2 + len(TALLAS) * 2)
    style_cell(ws.cell(row=1, column=1, value=f"{PRODUCTO} — DISTRIBUCIÓN POR TIENDA Y TALLA"), title_fill, bold=True)

    col = 2
    for t in TALLAS:
        ws.merge_cells(start_row=3, start_column=col, end_row=3, end_column=col + 1)
        style_cell(ws.cell(row=3, column=col, value=t), sub_fill, bold=True)
        style_cell(ws.cell(row=4, column=col, value="Mín"), min_fill, bold=True)
        style_cell(ws.cell(row=4, column=col + 1, value="Máx"), max_fill, bold=True)
        col += 2

    style_cell(ws.cell(row=3, column=1, value="Tienda"), sub_fill, bold=True, align=left)
    style_cell(ws.cell(row=4, column=1, value=""), sub_fill)

    row = 5
    for store in all_stores:
        is_new = store in (NEW_STORE, WEB_STORE)
        label = store + (" ★" if is_new else "")
        style_cell(ws.cell(row=row, column=1, value=label), color_fill if is_new else white_fill, bold=is_new, align=left)
        col = 2
        for t in TALLAS:
            style_cell(ws.cell(row=row, column=col, value=matrix_min[store][t]), min_fill if matrix_min[store][t] else white_fill)
            style_cell(ws.cell(row=row, column=col + 1, value=matrix_max[store][t]), max_fill if matrix_max[store][t] else white_fill)
            col += 2
        row += 1

    style_cell(ws.cell(row=row, column=1, value="TOTAL"), tot_fill, bold=True, align=left)
    col = 2
    for t in TALLAS:
        tmin = sum(matrix_min[s][t] for s in all_stores)
        tmax = sum(matrix_max[s][t] for s in all_stores)
        style_cell(ws.cell(row=row, column=col, value=tmin), tot_fill, bold=True)
        style_cell(ws.cell(row=row, column=col + 1, value=tmax), tot_fill, bold=True)
        col += 2

    row += 2
    ws.cell(row=row, column=1, value="Totales por tienda (Mín / Máx):").font = Font(bold=True)
    row += 1
    for store in all_stores:
        ws.cell(row=row, column=1, value=store)
        ws.cell(row=row, column=2, value=store_min[store])
        ws.cell(row=row, column=3, value=store_max[store])
        row += 1

    ws.column_dimensions["A"].width = 18
    for i in range(2, 2 + len(TALLAS) * 2):
        ws.column_dimensions[get_column_letter(i)].width = 7


def write_cierres_sheet(wb, ref, prod, zip_cap):
    ws = wb.create_sheet("Cierres (Insumo)")
    talla_min = distribute_by_talla(prod["prod_min"], ref["talla_pct"])
    talla_max = distribute_by_talla(prod["prod_max"], ref["talla_pct"])

    rows = [
        ["PLAN DE CIERRES — QX NEGRO 0580"],
        [],
        ["Modelo", "QX Negro 0580"],
        ["Color producto", "Negro (inferido del insumo)"],
        [],
        ["Longitud", "Tallas", "Disponible", "Usa Mín", "Usa Máx", "Remanente Mín", "Remanente Máx", "% uso máx"],
        [
            "60 cm", "XS · S · M", CIERRES_60CM,
            sum(talla_min[t] for t in TALLAS_60CM),
            sum(talla_max[t] for t in TALLAS_60CM),
            CIERRES_60CM - sum(talla_min[t] for t in TALLAS_60CM),
            CIERRES_60CM - sum(talla_max[t] for t in TALLAS_60CM),
            f"{sum(talla_max[t] for t in TALLAS_60CM)/CIERRES_60CM*100:.0f}%",
        ],
        [
            "75 cm", "L · XL", CIERRES_75CM,
            sum(talla_min[t] for t in TALLAS_75CM),
            sum(talla_max[t] for t in TALLAS_75CM),
            CIERRES_75CM - sum(talla_min[t] for t in TALLAS_75CM),
            CIERRES_75CM - sum(talla_max[t] for t in TALLAS_75CM),
            f"{sum(talla_max[t] for t in TALLAS_75CM)/CIERRES_75CM*100:.0f}%",
        ],
        [],
        ["Detalle por talla (Mín / Máx)"],
        ["Talla", "Cierre", "Mín", "Máx"],
    ]
    for t in TALLAS:
        rows.append([t, "60 cm" if t in TALLAS_60CM else "75 cm", talla_min[t], talla_max[t]])

    rows += [
        [],
        ["Tope teórico si se agotan todos los cierres 60 cm", zip_cap["cap_total"], "und"],
        ["Cierres 75 cm necesarios al tope", zip_cap["use_75_at_cap"], "und"],
        ["Cierres 75 cm sobrantes al tope", CIERRES_75CM - zip_cap["use_75_at_cap"], "und"],
        [],
        ["Recomendación"],
        ["• El cierre 60 cm es el INSUMO LIMITANTE — planificar producción desde este tope."],
        ["• Al máximo de producción se usan ~100% cierres 60 cm y ~21% cierres 75 cm."],
        ["• Reservar remanente 75 cm para reposición o segunda producción."],
    ]

    for r, row in enumerate(rows, start=1):
        for c, val in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            if r in (1, 6, 13):
                cell.font = Font(bold=True)
                cell.fill = sub_fill if r > 1 else title_fill
            if r == 6:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = sub_fill

    ws.column_dimensions["A"].width = 42
    for col in "BCDEFGH":
        ws.column_dimensions[col].width = 14


def write_metodologia(wb, ref, zip_cap, prod):
    ws = wb.create_sheet("Metodología")
    text = [
        f"METODOLOGÍA — PROYECCIÓN {PRODUCTO}",
        "",
        "1. PRODUCTO DE REFERENCIA",
        "   Se usó CUADRO JACKET 2.0 (importado) filtrado a género DAMA como proxy de demanda.",
        "   Jacket 1.0 no estaba disponible en el repositorio; Jacket 2.0 tiene 6 meses de historial.",
        f"   Velocidad base = promedio últimos {VELOCITY_MONTHS} meses (Mar–May 2026): {ref['vel_base']:.0f} und/mes.",
        "",
        "2. AJUSTE TEMPORADA ALTA",
        f"   Factor ×{HIGH_SEASON_FACTOR} aplicado (diciembre + regalos navideños).",
        f"   Diciembre 2025 Jacket DAMA vendió {ref['dec_vel']} und ({ref['dec_vel']/ref['vel_base']:.2f}× vs base 3m).",
        "",
        "3. EXPANSIÓN DE RED",
        f"   • Barquisimeto (nueva): promedio mensual Grieta + Chacao + Tolón × ramp-up {NEW_STORE_RAMP}.",
        f"     → {ref['barq_monthly']:.0f} und/mes proyectadas.",
        f"   • Web: {WEB_SHARE_PCT*100:.0f}% de velocidad base → {ref['web_monthly']:.0f} und/mes.",
        "   • Corporativo: EXCLUIDO.",
        "",
        "4. COBERTURA Y STOCK DE SEGURIDAD",
        f"   Mínimo: {COVER_MONTHS_MIN} meses de venta a velocidad ajustada + {int(SAFETY_STOCK_PCT*100)}% SS.",
        f"   Máximo: {COVER_MONTHS_MAX} meses o mín × {MAX_PCT_ABOVE_MIN}, lo que aplique.",
        "",
        "5. INSUMO LIMITANTE — CIERRES",
        "   QX Negro 0580: 60 cm (748 und) para XS/S/M | 75 cm (744 und) para L/XL.",
        f"   Curva tallas Jacket DAMA: 60 cm = {zip_cap['pct_60']*100:.1f}%, 75 cm = {zip_cap['pct_75']*100:.1f}%.",
        f"   Tope duro = {zip_cap['cap_total']} und (limitado por cierres 60 cm).",
        "",
        "6. RANGO MÍNIMO / MÁXIMO",
        f"   Demanda teórica mín: {prod['raw_min']} und → ajustada a {prod['prod_min']} und (cap cierres).",
        f"   Demanda teórica máx: {prod['raw_max']} und → ajustada a {prod['prod_max']} und (cap cierres).",
        "",
        "7. DISTRIBUCIÓN",
        "   Por tienda: participación histórica Jacket DAMA + Barquisimeto + Web.",
        "   Por talla: curva histórica Jacket DAMA (XS 22%, S 32%, M 29%, L 11%, XL 6%).",
        "",
        "8. DECISIÓN EN REUNIÓN",
        "   • MÍNIMO = compromiso de producción para cubrir temporada alta + SS dentro del cap de cierres.",
        "   • MÁXIMO = techo si se confirma demanda fuerte; no supera cierres 60 cm disponibles.",
        "   • Distribuir a tiendas y mover entre puntos de venta según rotación real post-lanzamiento.",
    ]
    for r, line in enumerate(text, start=1):
        cell = ws.cell(row=r, column=1, value=line)
        if r == 1:
            cell.font = Font(bold=True, size=13)
        if line and line[0].isdigit():
            cell.font = Font(bold=True)
    ws.column_dimensions["A"].width = 90


def main():
    data = load_jacket_data()
    ref = analyze_reference(data)
    zip_cap = calc_zipper_cap(ref["talla_pct"])
    prod = calc_production(ref, zip_cap)

    wb = Workbook()
    wb.remove(wb.active)
    write_resumen(wb, ref, zip_cap, prod)
    write_tallas_sheet(wb, ref, prod)
    write_tiendas_sheet(wb, ref, prod)
    write_cierres_sheet(wb, ref, prod, zip_cap)
    write_metodologia(wb, ref, zip_cap, prod)
    wb.save(OUTPUT_PATH)

    print(f"✅ Generado: {OUTPUT_PATH}")
    print(f"   Velocidad base: {ref['vel_base']:.1f} und/mes")
    print(f"   Velocidad red ajustada: {prod['vel_network']:.1f} und/mes")
    print(f"   Tope cierres: {zip_cap['cap_total']} und")
    print(f"   Rango producción: {prod['prod_min']} – {prod['prod_max']} und")


if __name__ == "__main__":
    main()
