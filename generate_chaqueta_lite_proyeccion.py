#!/usr/bin/env python3
"""Genera proyección de producción Chaqueta Lite (DAMA, XS–XL).

Referencia: ventas DAMA combinadas de Jacket 1.0 + Jacket 2.0 (adjuntos).
Restricción: cierres QX Negro 0580 — 60 cm (748 und) y 75 cm (744 und).
"""

import json
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

BASE = Path(__file__).resolve().parent
HTML_PATHS = [
    BASE / "Dashboard_Jacket_1_0.html",
    BASE / "Dashboard_Jacket_2_0.html",
]
OUTPUT_PATH = BASE / "CHAQUETA_LITE_RANGO_PRODUCCION.xlsx"

PRODUCTO = "CHAQUETA LITE"
GENERO = "DAMA"
TALLAS = ["XS", "S", "M", "L", "XL"]
TORD = {"XS": 0, "S": 1, "M": 2, "L": 3, "XL": 4}
TALLAS_60CM = {"XS", "S", "M"}
TALLAS_75CM = {"L", "XL"}

# ── Parámetros de proyección ──
HIGH_SEASON_FACTOR = 1.25
SAFETY_STOCK_PCT = 0.15
COVER_MONTHS_MIN = 2.5
COVER_MONTHS_MAX = 3.5
MAX_PCT_ABOVE_MIN = 1.12
TOLON_VS_CHACAO = 0.85          # Tolón ≈ 85% de Chacao
WEB_VS_CERRO_VERDE = 0.50       # Web ≈ 50% de Cerro Verde
GRAND_PLAZ_BONUS = 1.40         # Grand Plaz +40% sobre histórico
PROD_RANGE_MIN = 850            # Rango global acordado
PROD_RANGE_MAX = 940
VELOCITY_MONTHS = ["junio-2026", "julio-2026", "agosto-2026"]

# ── Insumo limitante: cierres ──
CIERRES_60CM = 748
CIERRES_75CM = 744

# ── Tiendas ──
HISTORICAL_STORES = ["SAMBIL", "GRIETA", "CERRO VERDE", "CHACAO", "GRAND PLAZ", "LA VELA"]
NEW_STORE = "BARQUISIMETO"
WEB_STORE = "WEB"
TOLON_STORE = "TOLON"
EXCLUDE_STORES = {"CORPORATIVO", "PEDIDOS"}
DISTRIBUTION_STORES = HISTORICAL_STORES + [TOLON_STORE, WEB_STORE, NEW_STORE]

# ── Estilos Excel ──
title_fill = PatternFill("solid", fgColor="1E3A5F")
sub_fill = PatternFill("solid", fgColor="4A7FB5")
color_fill = PatternFill("solid", fgColor="D6E4F0")
tot_fill = PatternFill("solid", fgColor="A8C8E8")
min_fill = PatternFill("solid", fgColor="FFF9C4")
max_fill = PatternFill("solid", fgColor="FFE0B2")
warn_fill = PatternFill("solid", fgColor="FFCDD2")
white_fill = PatternFill("solid", fgColor="FFFFFF")
adj_fill = PatternFill("solid", fgColor="FFF3E0")
thin = Side(style="thin", color="1E3A5F")
border = Border(left=thin, right=thin, top=thin, bottom=thin)
center = Alignment(horizontal="center", vertical="center")
left = Alignment(horizontal="left", vertical="center", wrap_text=True)


def load_combined_data() -> dict:
    all_rows = []
    meses_order = []
    for path in HTML_PATHS:
        html = path.read_text(encoding="utf-8")
        match = re.search(r"var DATA=(\{.*?\});", html, re.DOTALL)
        if not match:
            raise ValueError(f"No se encontró DATA en {path.name}")
        data = json.loads(match.group(1))
        meses_order.extend(data.get("meses_order", []))
        all_rows.extend(data["raw_rows"])

    seen = set()
    months_chrono = []
    for m in meses_order:
        if m not in seen:
            seen.add(m)
            months_chrono.append(m)

    return {"raw_rows": all_rows, "meses_order": months_chrono}


def analyze_reference(data: dict) -> dict:
    rows = [r for r in data["raw_rows"] if r["genero"] == GENERO and r["tienda"] not in EXCLUDE_STORES]
    months = data["meses_order"]
    months_with_data = [m for m in months if any(r["mes"] == m for r in rows)]
    n_months = len(months_with_data)

    by_month = {m: sum(r["v"] for r in rows if r["mes"] == m) for m in months}
    vel_base = sum(by_month.get(m, 0) for m in VELOCITY_MONTHS) / len(VELOCITY_MONTHS)
    vel_all = sum(by_month.values()) / n_months if n_months else 0
    dec_vel = by_month.get("diciembre-2025", 0)

    talla_tot = {t: 0 for t in TALLAS}
    for r in rows:
        if r["talla"] in talla_tot:
            talla_tot[r["talla"]] += r["v"]
    talla_grand = sum(talla_tot.values())
    talla_pct = {t: talla_tot[t] / talla_grand if talla_grand else 0 for t in TALLAS}

    store_tot = {}
    for s in set(r["tienda"] for r in rows):
        store_tot[s] = sum(r["v"] for r in rows if r["tienda"] == s)
    store_monthly_hist = {s: store_tot.get(s, 0) / n_months for s in store_tot}

    sambil_m = store_monthly_hist.get("SAMBIL", 0)
    chacao_m = store_monthly_hist.get("CHACAO", 0)
    cerro_m = store_monthly_hist.get("CERRO VERDE", 0)
    grieta_m = store_monthly_hist.get("GRIETA", 0)
    grand_hist = store_monthly_hist.get("GRAND PLAZ", 0)
    vela_hist = store_monthly_hist.get("LA VELA", 0)

    tolon_proj = chacao_m * TOLON_VS_CHACAO
    web_proj = cerro_m * WEB_VS_CERRO_VERDE
    barq_proj = (grieta_m + chacao_m + tolon_proj) / 3
    vela_proj = (sambil_m + cerro_m) / 2
    grand_proj = grand_hist * GRAND_PLAZ_BONUS

    store_monthly = {}
    for s in HISTORICAL_STORES:
        if s == "GRAND PLAZ":
            store_monthly[s] = grand_proj
        elif s == "LA VELA":
            store_monthly[s] = vela_proj
        else:
            store_monthly[s] = store_monthly_hist.get(s, 0)
    store_monthly[TOLON_STORE] = tolon_proj
    store_monthly[WEB_STORE] = web_proj
    store_monthly[NEW_STORE] = barq_proj

    total_weight = sum(store_monthly.values())
    store_share = {s: store_monthly[s] / total_weight if total_weight else 0 for s in DISTRIBUTION_STORES}

    return {
        "vel_base": vel_base,
        "vel_all": vel_all,
        "dec_vel": dec_vel,
        "vel_months": VELOCITY_MONTHS,
        "talla_pct": talla_pct,
        "talla_tot": talla_tot,
        "store_monthly": store_monthly,
        "store_monthly_hist": store_monthly_hist,
        "store_share": store_share,
        "tolon_proj": tolon_proj,
        "web_proj": web_proj,
        "barq_proj": barq_proj,
        "vela_proj": vela_proj,
        "grand_proj": grand_proj,
        "grand_hist": grand_hist,
        "vela_hist": vela_hist,
        "sambil_m": sambil_m,
        "chacao_m": chacao_m,
        "cerro_m": cerro_m,
        "months": months,
        "by_month": by_month,
        "sources": [p.name for p in HTML_PATHS],
    }


def calc_zipper_cap(talla_pct: dict) -> dict:
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
    vel_adj = ref["vel_base"] * HIGH_SEASON_FACTOR
    barq_add = ref["barq_proj"]
    vel_network = vel_adj + barq_add

    raw_min = round(vel_network * COVER_MONTHS_MIN * (1 + SAFETY_STOCK_PCT))
    raw_max = round(vel_network * COVER_MONTHS_MAX * (1 + SAFETY_STOCK_PCT))

    prod_min = PROD_RANGE_MIN
    prod_max = PROD_RANGE_MAX
    cap = zip_cap["cap_total"]

    use_60_min = round(prod_min * zip_cap["pct_60"])
    use_60_max = round(prod_max * zip_cap["pct_60"])
    use_75_min = round(prod_min * zip_cap["pct_75"])
    use_75_max = round(prod_max * zip_cap["pct_75"])
    deficit_60_max = max(0, use_60_max - CIERRES_60CM)

    return {
        "vel_adj": vel_adj,
        "vel_network": vel_network,
        "barq_add": barq_add,
        "raw_min": raw_min,
        "raw_max": raw_max,
        "prod_min": prod_min,
        "prod_max": prod_max,
        "zipper_limited": prod_max > cap,
        "use_60_min": use_60_min,
        "use_60_max": use_60_max,
        "use_75_min": use_75_min,
        "use_75_max": use_75_max,
        "deficit_60_max": deficit_60_max,
        "cap_cierres": cap,
    }


def distribute_by_talla(total: int, talla_pct: dict) -> dict:
    result = {}
    allocated = 0
    for t in TALLAS[:-1]:
        qty = round(total * talla_pct[t])
        result[t] = qty
        allocated += qty
    result[TALLAS[-1]] = total - allocated
    return result


def distribute_by_store(total: int, ref: dict) -> dict:
    weights = ref["store_monthly"]
    total_w = sum(weights.values())
    store_units = {s: round(total * weights[s] / total_w) for s in DISTRIBUTION_STORES}
    diff = total - sum(store_units.values())
    if diff:
        top = max(DISTRIBUTION_STORES, key=lambda s: store_units[s])
        store_units[top] += diff
    return store_units


def distribute_store_talla(store_units: dict, talla_pct: dict) -> dict:
    return {store: distribute_by_talla(qty, talla_pct) for store, qty in store_units.items()}


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
        ["Referencia analítica", "Jacket 1.0 + Jacket 2.0 — ventas DAMA combinadas"],
        ["Fuentes datos", " + ".join(ref["sources"])],
        ["Período velocidad base", f"Jun–Jul–Ago 2026 ({', '.join(ref['vel_months'])})"],
        [],
        ["── VELOCIDAD ──"],
        ["Velocidad base (3m combinado)", round(ref["vel_base"], 1), "und/mes"],
        ["Velocidad histórica promedio", round(ref["vel_all"], 1), "und/mes"],
        ["Diciembre 2025 (temporada alta ref.)", ref["dec_vel"], "und"],
        ["Factor temporada alta aplicado", HIGH_SEASON_FACTOR, "×"],
        ["Velocidad ajustada temporada alta", round(prod["vel_adj"], 1), "und/mes"],
        ["Barquisimeto adicional (tienda nueva)", round(prod["barq_add"], 1), "und/mes"],
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
        ["Tope teórico cierres 60 cm", zip_cap["cap_total"], "und"],
        ["¿Máximo supera cierres 60 cm?", "SÍ — ver hoja Cierres" if prod["deficit_60_max"] else "NO"],
        [],
        ["── RANGO DE PRODUCCIÓN (ACORDADO) ──"],
        ["MÍNIMO (compromiso)", prod["prod_min"], "und"],
        ["MÁXIMO", prod["prod_max"], "und"],
        ["Rango de acción", prod["prod_max"] - prod["prod_min"], "und"],
        ["Cierres 60 cm al máximo", prod["use_60_max"], f"de {CIERRES_60CM} disp."],
        ["Déficit cierres 60 cm al máximo", prod["deficit_60_max"] or "—", "und" if prod["deficit_60_max"] else ""],
        [],
        ["── AJUSTES DE TIENDA (DISTRIBUCIÓN) ──"],
        ["Tolón histórico", round(ref["store_monthly_hist"].get("TOLON", 0), 1), "und/mes"],
        [f"Tolón proyectado ({int(TOLON_VS_CHACAO*100)}% Chacao)", round(ref["tolon_proj"], 1), "und/mes"],
        ["Web histórica", round(ref["store_monthly_hist"].get("WEB", 0), 1), "und/mes"],
        [f"Web proyectada ({int(WEB_VS_CERRO_VERDE*100)}% Cerro Verde)", round(ref["web_proj"], 1), "und/mes"],
        ["La Vela histórica", round(ref["vela_hist"], 1), "und/mes"],
        ["La Vela proyectada (avg Sambil + Cerro Verde)", round(ref["vela_proj"], 1), "und/mes"],
        ["Grand Plaz histórica", round(ref["grand_hist"], 1), "und/mes"],
        [f"Grand Plaz proyectada (+{round((GRAND_PLAZ_BONUS - 1) * 100)}% hist.)", round(ref["grand_proj"], 1), "und/mes"],
        ["Barquisimeto (avg Grieta+Chacao+Tolón proy.)", round(ref["barq_proj"], 1), "und/mes"],
        ["Corporativo", "EXCLUIDO"],
        [],
        ["Notas"],
        ["• Dashboards adjuntos Jacket 1.0 y Jacket 2.0 leídos y combinados."],
        ["• Producto NUEVO manufacturado — sin stock inicial."],
        ["• Solo género DAMA, tallas XS a XL."],
        ["• Cierres 60 cm → XS, S, M | Cierres 75 cm → L, XL."],
    ]
    for r, row in enumerate(rows, start=1):
        for c, val in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            if r == 1:
                cell.font = Font(bold=True, size=14, color="FFFFFF")
                cell.fill = title_fill
            elif row and row[0] and str(row[0]).startswith("──"):
                cell.font = Font(bold=True, color="1E3A5F")
    ws.column_dimensions["A"].width = 44
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["C"].width = 14


def write_tallas_sheet(wb, ref, prod):
    ws = wb.create_sheet("Producción por Talla")
    talla_min = distribute_by_talla(prod["prod_min"], ref["talla_pct"])
    talla_max = distribute_by_talla(prod["prod_max"], ref["talla_pct"])

    ws.merge_cells("A1:G1")
    style_cell(ws.cell(row=1, column=1, value=f"{PRODUCTO} — CANTIDADES POR TALLA (MÍN / MÁX)"), title_fill, bold=True)
    ws.cell(row=2, column=1, value=f"{GENERO} · Curva Jacket 1.0 + 2.0 DAMA combinado").font = Font(italic=True)

    headers = ["Talla", "Curva %", "Cierre (cm)", "Mínimo", "Máximo", "Cierres Mín", "Cierres Máx"]
    for c, h in enumerate(headers, 1):
        style_cell(ws.cell(row=4, column=c, value=h), sub_fill, bold=True)

    cierres_map = {"XS": 60, "S": 60, "M": 60, "L": 75, "XL": 75}
    c60_min = c75_min = c60_max = c75_max = 0
    t_min_total = t_max_total = 0

    for i, t in enumerate(TALLAS, start=5):
        mn, mx = talla_min[t], talla_max[t]
        style_cell(ws.cell(row=i, column=1, value=t), color_fill, bold=True)
        ws.cell(row=i, column=2, value=f"{ref['talla_pct'][t]*100:.1f}%")
        ws.cell(row=i, column=3, value=cierres_map[t])
        style_cell(ws.cell(row=i, column=4, value=mn), min_fill, bold=True)
        style_cell(ws.cell(row=i, column=5, value=mx), max_fill, bold=True)
        ws.cell(row=i, column=6, value=mn)
        ws.cell(row=i, column=7, value=mx)
        t_min_total += mn
        t_max_total += mx
        if cierres_map[t] == 60:
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
    fill60 = warn_fill if c60_max > CIERRES_60CM else color_fill
    style_cell(ws.cell(row=r, column=1, value="Disponible cierres 60 cm"), fill60, align=left)
    ws.cell(row=r, column=4, value=CIERRES_60CM)
    deficit = c60_max - CIERRES_60CM
    ws.cell(row=r, column=5, value=f"Usa máx {c60_max}" + (f" (faltan {deficit})" if deficit > 0 else f" ({c60_max/CIERRES_60CM*100:.0f}%)"))
    r += 1
    style_cell(ws.cell(row=r, column=1, value="Disponible cierres 75 cm"), color_fill, align=left)
    ws.cell(row=r, column=4, value=CIERRES_75CM)
    ws.cell(row=r, column=5, value=f"Usa máx {c75_max} ({c75_max/CIERRES_75CM*100:.0f}%)")

    for col in "ABCDEFG":
        ws.column_dimensions[col].width = 14
    ws.column_dimensions["A"].width = 18


def write_tiendas_sheet(wb, ref, prod):
    ws = wb.create_sheet("Distribución por Tienda")
    adjusted = {TOLON_STORE, WEB_STORE, NEW_STORE, "LA VELA", "GRAND PLAZ"}
    store_min = distribute_by_store(prod["prod_min"], ref)
    store_max = distribute_by_store(prod["prod_max"], ref)
    matrix_min = distribute_store_talla(store_min, ref["talla_pct"])
    matrix_max = distribute_store_talla(store_max, ref["talla_pct"])

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=2 + len(TALLAS) * 2)
    style_cell(ws.cell(row=1, column=1, value=f"{PRODUCTO} — DISTRIBUCIÓN POR TIENDA Y TALLA"), title_fill, bold=True)
    ws.cell(row=2, column=1, value="★ = tienda con velocidad proyectada/ajustada").font = Font(italic=True, color="E65100")

    col = 2
    for t in TALLAS:
        ws.merge_cells(start_row=3, start_column=col, end_row=3, end_column=col + 1)
        style_cell(ws.cell(row=3, column=col, value=t), sub_fill, bold=True)
        style_cell(ws.cell(row=4, column=col, value="Mín"), min_fill, bold=True)
        style_cell(ws.cell(row=4, column=col + 1, value="Máx"), max_fill, bold=True)
        col += 2

    style_cell(ws.cell(row=3, column=1, value="Tienda"), sub_fill, bold=True, align=left)

    row = 5
    for store in DISTRIBUTION_STORES:
        is_adj = store in adjusted
        label = store + (" ★" if is_adj else "")
        fill = adj_fill if is_adj else white_fill
        style_cell(ws.cell(row=row, column=1, value=label), fill, bold=is_adj, align=left)
        col = 2
        for t in TALLAS:
            style_cell(ws.cell(row=row, column=col, value=matrix_min[store][t]), min_fill if matrix_min[store][t] else white_fill)
            style_cell(ws.cell(row=row, column=col + 1, value=matrix_max[store][t]), max_fill if matrix_max[store][t] else white_fill)
            col += 2
        row += 1

    style_cell(ws.cell(row=row, column=1, value="TOTAL"), tot_fill, bold=True, align=left)
    col = 2
    for t in TALLAS:
        style_cell(ws.cell(row=row, column=col, value=sum(matrix_min[s][t] for s in DISTRIBUTION_STORES)), tot_fill, bold=True)
        style_cell(ws.cell(row=row, column=col + 1, value=sum(matrix_max[s][t] for s in DISTRIBUTION_STORES)), tot_fill, bold=True)
        col += 2

    row += 2
    ws.cell(row=row, column=1, value="Totales por tienda (Mín / Máx):").font = Font(bold=True)
    row += 1
    ws.cell(row=row, column=1, value="Tienda").font = Font(bold=True)
    ws.cell(row=row, column=2, value="Mín").font = Font(bold=True)
    ws.cell(row=row, column=3, value="Máx").font = Font(bold=True)
    ws.cell(row=row, column=4, value="Vel. mensual proy.").font = Font(bold=True)
    row += 1
    for store in DISTRIBUTION_STORES:
        ws.cell(row=row, column=1, value=store + (" ★" if store in adjusted else ""))
        ws.cell(row=row, column=2, value=store_min[store])
        ws.cell(row=row, column=3, value=store_max[store])
        ws.cell(row=row, column=4, value=round(ref["store_monthly"][store], 1))
        row += 1

    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["D"].width = 16
    for i in range(2, 2 + len(TALLAS) * 2):
        ws.column_dimensions[get_column_letter(i)].width = 7


def write_cierres_sheet(wb, ref, prod, zip_cap):
    ws = wb.create_sheet("Cierres (Insumo)")
    talla_min = distribute_by_talla(prod["prod_min"], ref["talla_pct"])
    talla_max = distribute_by_talla(prod["prod_max"], ref["talla_pct"])

    rows = [
        ["PLAN DE CIERRES — QX NEGRO 0580"],
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
        ["Rango producción acordado", f"{prod['prod_min']} – {prod['prod_max']} und"],
        ["Déficit cierres 60 cm al máximo", prod["deficit_60_max"] or 0, "und (comprar adicional)" if prod["deficit_60_max"] else "—"],
        ["Nota", "Al máximo (940) se supera stock cierres 60 cm; comprar ~14 und extra o producir tope 921 con stock actual." if prod["deficit_60_max"] else ""],
    ]
    for r, row in enumerate(rows, start=1):
        for c, val in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            if r in (1, 5):
                cell.font = Font(bold=True)
                cell.fill = title_fill if r == 1 else sub_fill
    ws.column_dimensions["A"].width = 42


def write_metodologia(wb, ref, zip_cap, prod):
    ws = wb.create_sheet("Metodología")
    text = [
        f"METODOLOGÍA — PROYECCIÓN {PRODUCTO}",
        "",
        "1. PRODUCTO DE REFERENCIA",
        "   Fuentes: Dashboard_Jacket_1_0.html + Dashboard_Jacket_2_0.html (adjuntos).",
        "   Se combinaron ventas DAMA de Jacket 1.0 y CUADRO Jacket 2.0.",
        f"   Velocidad base = promedio Jun–Jul–Ago 2026: {ref['vel_base']:.0f} und/mes.",
        "",
        "2. AJUSTE TEMPORADA ALTA",
        f"   Factor ×{HIGH_SEASON_FACTOR} (diciembre). Diciembre 2025 combinado: {ref['dec_vel']} und.",
        "",
        "3. AJUSTES DE TIENDA (según indicación)",
        f"   • Tolón: proyectado al {int(TOLON_VS_CHACAO*100)}% de Chacao ({ref['chacao_m']:.0f} → {ref['tolon_proj']:.0f} und/mes).",
        f"     Histórico Tolón: {ref['store_monthly_hist'].get('TOLON', 0):.0f} und/mes — subestimado por tienda nueva.",
        f"   • Web: proyectada al {int(WEB_VS_CERRO_VERDE*100)}% de Cerro Verde ({ref['cerro_m']:.0f} → {ref['web_proj']:.0f} und/mes).",
        f"     Histórico Web: {ref['store_monthly_hist'].get('WEB', 0):.0f} und/mes.",
        f"   • La Vela (nueva): promedio Sambil + Cerro Verde = {ref['vela_proj']:.0f} und/mes.",
        f"     Histórico La Vela: {ref['vela_hist']:.0f} und/mes.",
        f"   • Grand Plaz: histórico × {GRAND_PLAZ_BONUS} (+{round((GRAND_PLAZ_BONUS-1)*100)}%) = {ref['grand_proj']:.0f} und/mes.",
        f"     Histórico Grand Plaz: {ref['grand_hist']:.0f} und/mes.",
        f"   • Barquisimeto (nueva): promedio Grieta + Chacao + Tolón proyectado = {ref['barq_proj']:.0f} und/mes.",
        "   • Corporativo: EXCLUIDO.",
        "",
        "4. RANGO GLOBAL ACORDADO",
        f"   Mínimo: {PROD_RANGE_MIN} und | Máximo: {PROD_RANGE_MAX} und.",
        f"   Demanda teórica calculada: {prod['raw_min']} – {prod['raw_max']} und (referencia).",
        "",
        "5. INSUMO LIMITANTE — CIERRES",
        f"   Tope teórico cierres 60 cm = {zip_cap['cap_total']} und.",
        f"   Al máximo ({prod['prod_max']} und) se necesitan {prod['use_60_max']} cierres 60 cm.",
        f"   Déficit al máximo: {prod['deficit_60_max']} und de cierre 60 cm (si no se compran más).",
        "",
        "6. RANGO MÍNIMO / MÁXIMO",
        f"   Compromiso mín: {prod['prod_min']} und.",
        f"   Techo máx: {prod['prod_max']} und.",
        "",
        "7. DISTRIBUCIÓN",
        "   Por tienda: pesos mensuales proyectados (Tolón/Web/Barquisimeto ajustados).",
        "   Por talla: curva combinada Jacket 1.0 + 2.0 DAMA.",
    ]
    for r, line in enumerate(text, start=1):
        cell = ws.cell(row=r, column=1, value=line)
        if r == 1:
            cell.font = Font(bold=True, size=13)
        if line and line[0].isdigit():
            cell.font = Font(bold=True)
    ws.column_dimensions["A"].width = 95


def main():
    data = load_combined_data()
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
    print(f"   Fuentes: {', '.join(ref['sources'])}")
    print(f"   Velocidad base (Jun-Ago 2026): {ref['vel_base']:.1f} und/mes")
    print(f"   Tolón proy: {ref['tolon_proj']:.1f}/mes ({TOLON_VS_CHACAO*100:.0f}% Chacao)")
    print(f"   Web proy: {ref['web_proj']:.1f}/mes ({WEB_VS_CERRO_VERDE*100:.0f}% Cerro Verde)")
    print(f"   Rango producción: {prod['prod_min']} – {prod['prod_max']} und")


if __name__ == "__main__":
    main()
