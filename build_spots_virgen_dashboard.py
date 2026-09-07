#!/usr/bin/env python3
"""Dashboard + Excel de producción sugerida — SPOTS Virgen del Valle (VELA + WEB)."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent
VENTAS_PATH = ROOT / "data" / "spots_virgen_ventas.xlsx"
INV_PATH = ROOT / "data" / "spots_virgen_inventario.xlsx"
HTML_PATH = ROOT / "SPOTS VIRGEN DEL VALLE DASHBOARD.html"
XLSX_PATH = ROOT / "SPOTS_VIRGEN_PRODUCCION_SUGERIDA.xlsx"

DISENO = "Virgen del Valle"
MODELO = "SPOTS MANGA CORTA"
COLOR = "Blanco"
REF_DATE = date(2026, 9, 7)
TALLA_ORDER = ["XS", "S", "M", "L", "XL", "2XL"]
GENDER_ORDER = ["CAB", "DAMA"]
STORE_MAP = {"la vela": "VELA", "vela": "VELA", "pedidos": "PEDIDOS", "web": "WEB", "taller": "TALLER"}

# Proyección post-pico · sept restante + mitad octubre
PEAK_DAYS = 4
WEB_SHARE = 0.35
WEB_SHARE_RANGE = (0.30, 0.40)
STOCK_BUFFER = 0.12
TALLER_UTIL = 0.55
OCT_FACTOR = 0.88
MIN_PRODUCE = 2

THIN = Side(style="thin", color="CCCCCC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HDR_FILL = PatternFill("solid", fgColor="1F2937")
HDR_FONT = Font(bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(bold=True, size=12)
TOTAL_FILL = PatternFill("solid", fgColor="E5E7EB")
TOTAL_FONT = Font(bold=True)
ACCENT_FILL = PatternFill("solid", fgColor="D1FAE5")
ACCENT_FONT = Font(bold=True, color="065F46")


def norm_store(name: str) -> str:
    return STORE_MAP.get((name or "").strip().lower(), (name or "").strip().upper())


def norm_gender(val: str) -> str:
    g = (val or "").strip().upper()
    if "CAB" in g:
        return "CAB"
    if "DAM" in g:
        return "DAMA"
    return g


def talla_idx(t: str) -> int:
    try:
        return TALLA_ORDER.index(t)
    except ValueError:
        return 99


def load_ventas(path: Path):
    wb = load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r[0]:
            continue
        rows.append({
            "mes": str(r[1]).strip().lower(),
            "mes_key": str(r[11] or f"{r[1]}-{r[0]}").strip().lower(),
            "modelo": str(r[2] or MODELO).strip(),
            "sku": str(r[4] or "").strip(),
            "genero": norm_gender(r[5]),
            "color": str(r[6] or COLOR).strip(),
            "diseno": str(r[7] or DISENO).strip(),
            "talla": str(r[8]).strip().upper(),
            "tienda": norm_store(r[9]),
            "qty": int(r[10] or 0),
        })
    return rows


def load_inventario(path: Path):
    wb = load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r[0]:
            continue
        rows.append({
            "ubicacion": str(r[0]).strip().upper(),
            "sku": str(r[2] or "").strip(),
            "modelo": str(r[3] or MODELO).strip(),
            "genero": norm_gender(r[4]),
            "color": COLOR,
            "diseno": DISENO,
            "talla": str(r[6]).strip().upper(),
            "qty": int(r[7] or 0),
        })
    return rows


def aggregate(rows, *keys):
    out = defaultdict(int)
    for r in rows:
        if len(keys) == 1:
            k = r[keys[0]]
        else:
            k = tuple(r[x] for x in keys)
        out[k] += r["qty"]
    return out


def compute_velocity(sept_vela: int, days_elapsed: int):
    peak_days = min(PEAK_DAYS, max(days_elapsed - 1, 1))
    recent_days = max(days_elapsed - peak_days, 1)
    peak_share = min(0.78, 0.45 + peak_days * 0.08)
    peak_sales = sept_vela * peak_share
    recent_sales = max(sept_vela - peak_sales, 0)
    peak_daily = peak_sales / peak_days if peak_days else 0
    post_peak_daily = recent_sales / recent_days if recent_days else sept_vela / max(days_elapsed, 1)
    observed_daily = sept_vela / max(days_elapsed, 1)
    return {
        "days_elapsed": days_elapsed,
        "peak_days": peak_days,
        "recent_days": recent_days,
        "peak_share": round(peak_share, 3),
        "peak_daily": round(peak_daily, 2),
        "post_peak_daily": round(post_peak_daily, 2),
        "observed_daily": round(observed_daily, 2),
    }


def compute_projection(ventas, inv_rows, ref_date: date = REF_DATE):
    days_elapsed = ref_date.day
    rest_sept_days = max(30 - ref_date.day, 0) if ref_date.month == 9 else 0
    mid_oct_days = 15

    sept_rows = [r for r in ventas if r["mes"] == "septiembre"]
    aug_rows = [r for r in ventas if r["mes"] == "agosto"]
    sept_vela = sum(r["qty"] for r in sept_rows if r["tienda"] == "VELA")
    sept_total = sum(r["qty"] for r in sept_rows)
    aug_total = sum(r["qty"] for r in aug_rows)

    vel = compute_velocity(sept_vela, days_elapsed)

    # Mix: sept 85% + agosto 15%
    mix_rows = []
    for r in ventas:
        w = 0.85 if r["mes"] == "septiembre" else 0.15
        mix_rows.extend([r] * max(r["qty"], 0) for _ in [0] * 1)
    mix_weighted = defaultdict(float)
    sept_mix = aggregate([r for r in ventas if r["mes"] == "septiembre"], "genero", "talla")
    aug_mix = aggregate([r for r in ventas if r["mes"] == "agosto"], "genero", "talla")
    all_keys = set(sept_mix) | set(aug_mix)
    mix_total = 0.0
    for k in all_keys:
        v = sept_mix.get(k, 0) * 0.85 + aug_mix.get(k, 0) * 0.15
        mix_weighted[k] = v
        mix_total += v
    mix_pct = {k: (v / mix_total if mix_total else 0) for k, v in mix_weighted.items()}

    gen_mix = defaultdict(float)
    for (g, t), pct in mix_pct.items():
        gen_mix[g] += pct

    inv_by_loc = aggregate(inv_rows, "ubicacion", "genero", "talla")
    inv_vela = aggregate([r for r in inv_rows if r["ubicacion"] == "VELA"], "genero", "talla")
    inv_taller = aggregate([r for r in inv_rows if r["ubicacion"] == "TALLER"], "genero", "talla")
    inv_web = aggregate([r for r in inv_rows if r["ubicacion"] == "WEB"], "genero", "talla")
    inv_total = aggregate(inv_rows, "genero", "talla")

    post_peak = vel["post_peak_daily"]
    vela_horizon = post_peak * rest_sept_days + post_peak * OCT_FACTOR * mid_oct_days
    web_horizon = vela_horizon * WEB_SHARE

    scenarios = []
    for label, days_s, days_o, web_pct in [
        ("Resto septiembre", rest_sept_days, 0, WEB_SHARE),
        ("Sept + mitad octubre", rest_sept_days, mid_oct_days, WEB_SHARE),
        ("Sept + mitad oct (WEB 30%)", rest_sept_days, mid_oct_days, 0.30),
        ("Sept + mitad oct (WEB 40%)", rest_sept_days, mid_oct_days, 0.40),
    ]:
        vela_u = post_peak * days_s + post_peak * OCT_FACTOR * days_o
        web_u = vela_u * web_pct
        scenarios.append({
            "label": label,
            "days_sept": days_s,
            "days_oct": days_o,
            "web_pct": web_pct,
            "vela_units": round(vela_u),
            "web_units": round(web_u),
            "total_units": round(vela_u + web_u),
        })

    primary = scenarios[1]
    recs = []
    total_suggest = 0
    total_vela_d = 0
    total_web_d = 0
    total_stock_eff = 0

    for g in GENDER_ORDER:
        for t in TALLA_ORDER:
            key = (g, t)
            pct = mix_pct.get(key, 0)
            if pct <= 0 and not inv_total.get(key):
                continue
            vela_d = primary["vela_units"] * pct
            web_d = primary["web_units"] * pct
            stock_vela = inv_vela.get(key, 0)
            stock_taller = inv_taller.get(key, 0)
            stock_web = inv_web.get(key, 0)
            stock_all = inv_total.get(key, 0)
            effective = stock_vela + stock_web + stock_taller * TALLER_UTIL
            gap = (vela_d + web_d) * (1 + STOCK_BUFFER) - effective
            suggest = max(0, int(math.ceil(gap))) if gap > 0.5 else 0
            if 0 < suggest < MIN_PRODUCE:
                suggest = MIN_PRODUCE
            cob_vela = round(stock_vela / post_peak / pct, 1) if post_peak * pct > 0 else None
            recs.append({
                "genero": g,
                "talla": t,
                "mix_pct": round(pct * 100, 1),
                "ventas_sept": sept_mix.get(key, 0),
                "ventas_total": sept_mix.get(key, 0) + aug_mix.get(key, 0),
                "stock_vela": stock_vela,
                "stock_taller": stock_taller,
                "stock_web": stock_web,
                "stock_total": stock_all,
                "demanda_vela": round(vela_d),
                "demanda_web": round(web_d),
                "demanda_total": round(vela_d + web_d),
                "stock_efectivo": round(effective),
                "produccion_sugerida": suggest,
                "cobertura_vela_dias": cob_vela,
            })
            total_suggest += suggest
            total_vela_d += round(vela_d)
            total_web_d += round(web_d)
            total_stock_eff += round(effective)

    by_store = aggregate(ventas, "tienda")
    by_month = aggregate(ventas, "mes")
    by_gen = aggregate(ventas, "genero")
    by_talla = aggregate(ventas, "talla")

    return {
        "meta": {
            "diseno": DISENO,
            "modelo": MODELO,
            "ref_date": ref_date.isoformat(),
            "days_elapsed_sept": days_elapsed,
            "rest_sept_days": rest_sept_days,
            "mid_oct_days": mid_oct_days,
            "web_share": WEB_SHARE,
            "web_share_range": list(WEB_SHARE_RANGE),
            "stock_buffer": STOCK_BUFFER,
            "taller_util": TALLER_UTIL,
            "oct_factor": OCT_FACTOR,
        },
        "totals": {
            "ventas_total": sum(r["qty"] for r in ventas),
            "ventas_sept": sept_total,
            "ventas_agosto": aug_total,
            "ventas_vela_sept": sept_vela,
            "inventario_total": sum(r["qty"] for r in inv_rows),
            "inventario_vela": sum(r["qty"] for r in inv_rows if r["ubicacion"] == "VELA"),
            "inventario_taller": sum(r["qty"] for r in inv_rows if r["ubicacion"] == "TALLER"),
            "produccion_sugerida": total_suggest,
            "demanda_vela": total_vela_d,
            "demanda_web": total_web_d,
        },
        "velocity": vel,
        "scenarios": scenarios,
        "recommendations": recs,
        "ventas_rows": ventas,
        "inv_rows": inv_rows,
        "by_store": dict(by_store),
        "by_month": dict(by_month),
        "by_gen": dict(by_gen),
        "by_talla": dict(by_talla),
        "mix_pct": {f"{g}|{t}": round(v * 100, 1) for (g, t), v in mix_pct.items()},
        "primary_scenario": primary["label"],
    }


def _style_range(ws, row, c1, c2, fill=None, font=None):
    for c in range(c1, c2 + 1):
        cell = ws.cell(row=row, column=c)
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center")
        if fill:
            cell.fill = fill
        if font:
            cell.font = font


def export_xlsx(data: dict, path: Path):
    wb = Workbook()
    recs = data["recommendations"]
    meta = data["meta"]
    wb.remove(wb.active)

    # RESUMEN
    ws = wb.create_sheet("RESUMEN")
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 18
    rows = [
        ("SPOTS Virgen del Valle — Producción sugerida", ""),
        ("Fecha análisis", meta["ref_date"]),
        ("Horizonte principal", data["primary_scenario"]),
        ("", ""),
        ("Ventas septiembre (total)", data["totals"]["ventas_sept"]),
        ("Ventas VELA septiembre", data["totals"]["ventas_vela_sept"]),
        ("Inventario VELA", data["totals"]["inventario_vela"]),
        ("Inventario TALLER", data["totals"]["inventario_taller"]),
        ("", ""),
        ("Ritmo post-pico VELA (und/día)", data["velocity"]["post_peak_daily"]),
        ("Demanda proyectada VELA", data["totals"]["demanda_vela"]),
        (f"Demanda proyectada WEB ({int(meta['web_share']*100)}%)", data["totals"]["demanda_web"]),
        ("Producción sugerida total", data["totals"]["produccion_sugerida"]),
        ("", ""),
        ("Supuestos", ""),
        ("WEB vs VELA", f"{int(meta['web_share_range'][0]*100)}–{int(meta['web_share_range'][1]*100)}% (base {int(meta['web_share']*100)}%)"),
        ("Stock seguridad", f"+{int(meta['stock_buffer']*100)}%"),
        ("TALLER en cobertura", f"{int(meta['taller_util']*100)}% del stock"),
        ("Octubre (mitad)", f"×{meta['oct_factor']} vs ritmo sept"),
        ("Pico", f"Primeros {data['velocity']['peak_days']} días ≈ {int(data['velocity']['peak_share']*100)}% ventas sept"),
    ]
    for i, (a, b) in enumerate(rows, 1):
        ws.cell(i, 1, a)
        ws.cell(i, 2, b)
        if a.startswith("SPOTS"):
            ws.cell(i, 1).font = TITLE_FONT
        if a == "Producción sugerida total":
            ws.cell(i, 2).font = ACCENT_FONT
            ws.cell(i, 2).fill = ACCENT_FILL

    for gen in GENDER_ORDER:
        _write_gen_sheet(wb, gen, recs)

    ws_ped = wb.create_sheet("PEDIDO_TS", 1)
    ws_ped.append(["Género", "Talla", "Cantidad a producir", "Demanda VELA", "Demanda WEB", "Stock VELA actual"])
    for c in range(1, 7):
        ws_ped.cell(1, c).fill = HDR_FILL
        ws_ped.cell(1, c).font = HDR_FONT
    r = 2
    for rec in sorted(recs, key=lambda x: (x["genero"], talla_idx(x["talla"]))):
        if rec["produccion_sugerida"] <= 0:
            continue
        ws_ped.append([
            rec["genero"], rec["talla"], rec["produccion_sugerida"],
            rec["demanda_vela"], rec["demanda_web"], rec["stock_vela"],
        ])
        ws_ped.cell(r, 3).font = ACCENT_FONT
        ws_ped.cell(r, 3).fill = ACCENT_FILL
        r += 1
    ws_ped.append(["TOTAL", "", sum(x["produccion_sugerida"] for x in recs), "", "", ""])
    ws_ped.cell(r, 1).font = TOTAL_FONT
    ws_ped.cell(r, 3).font = ACCENT_FONT
    ws_ped.cell(r, 3).fill = ACCENT_FILL
    for i, w in enumerate([10, 8, 18, 14, 14, 16], 1):
        ws_ped.column_dimensions[get_column_letter(i)].width = w

    ws2 = wb.create_sheet("ESCENARIOS")
    ws2.append(["Escenario", "Días sept", "Días oct", "WEB %", "VELA und", "WEB und", "Total"])
    for s in data["scenarios"]:
        ws2.append([s["label"], s["days_sept"], s["days_oct"], s["web_pct"], s["vela_units"], s["web_units"], s["total_units"]])
    for c in range(1, 8):
        ws2.cell(1, c).fill = HDR_FILL
        ws2.cell(1, c).font = HDR_FONT

    wb.save(path)


def _write_gen_sheet(wb, genero: str, recs: list):
    ws = wb.create_sheet(genero)
    headers = [
        "Talla", "Mix %", "Ventas sept", "Stock VELA", "Stock TALLER", "Stock WEB",
        "Demanda VELA", "Demanda WEB", "Demanda total", "Stock efectivo",
        "Producción sugerida", "Cobertura VELA (días)",
    ]
    ws.append([f"SPOTS MANGA CORTA {genero} · Virgen del Valle · Blanco"])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ws.cell(1, 1).font = TITLE_FONT
    ws.append(headers)
    _style_range(ws, 2, 1, len(headers), HDR_FILL, HDR_FONT)

    gen_recs = [r for r in recs if r["genero"] == genero]
    r = 3
    col_totals = defaultdict(int)
    for rec in sorted(gen_recs, key=lambda x: talla_idx(x["talla"])):
        row = [
            rec["talla"], rec["mix_pct"], rec["ventas_sept"],
            rec["stock_vela"], rec["stock_taller"], rec["stock_web"],
            rec["demanda_vela"], rec["demanda_web"], rec["demanda_total"],
            rec["stock_efectivo"], rec["produccion_sugerida"],
            rec["cobertura_vela_dias"] if rec["cobertura_vela_dias"] is not None else "—",
        ]
        ws.append(row)
        for i, val in enumerate(row[2:], 3):
            if isinstance(val, (int, float)):
                col_totals[i] += val
        if rec["produccion_sugerida"] > 0:
            ws.cell(r, 11).font = ACCENT_FONT
            ws.cell(r, 11).fill = ACCENT_FILL
        _style_range(ws, r, 1, len(headers))
        r += 1

    ws.cell(r, 1, "TOTAL").font = TOTAL_FONT
    for c, key in [(3, "ventas_sept"), (4, "stock_vela"), (5, "stock_taller"), (6, "stock_web"),
                   (7, "demanda_vela"), (8, "demanda_web"), (9, "demanda_total"),
                   (10, "stock_efectivo"), (11, "produccion_sugerida")]:
        ws.cell(r, c, sum(x[key] for x in gen_recs))
    _style_range(ws, r, 1, len(headers), TOTAL_FILL, TOTAL_FONT)
    ws.cell(r, 11).fill = ACCENT_FILL

    for i, w in enumerate([8, 8, 10, 10, 12, 10, 12, 12, 12, 12, 16, 14], 1):
        ws.column_dimensions[get_column_letter(i)].width = w


TEMPLATE_PATH = ROOT / "spots_virgen_dashboard_template.html"


def build_html(data: dict) -> str:
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.replace("__DATA_JSON__", data_json)




def main():
    ventas = load_ventas(VENTAS_PATH)
    inv = load_inventario(INV_PATH)
    data = compute_projection(ventas, inv)
    HTML_PATH.write_text(build_html(data), encoding="utf-8")
    export_xlsx(data, XLSX_PATH)
    t = data["totals"]
    v = data["velocity"]
    print(f"Wrote {HTML_PATH}")
    print(f"Wrote {XLSX_PATH}")
    print(f"Ventas sept: {t['ventas_sept']} | Inv VELA: {t['inventario_vela']} | TALLER: {t['inventario_taller']}")
    print(f"Ritmo post-pico: {v['post_peak_daily']} und/día | Producir sugerido: {t['produccion_sugerida']} und")
    print(f"  VELA proj: {t['demanda_vela']} | WEB proj: {t['demanda_web']}")


if __name__ == "__main__":
    main()
