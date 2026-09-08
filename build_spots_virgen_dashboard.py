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
REF_DATE = date(2026, 9, 8)
TALLA_ORDER = ["XS", "S", "M", "L", "XL", "2XL"]
GENDER_ORDER = ["CAB", "DAMA"]
STORE_MAP = {"la vela": "VELA", "vela": "VELA", "pedidos": "PEDIDOS", "web": "WEB", "taller": "TALLER"}

# Cobertura post-pico — el pool (267 und) ya cubre ~32 días agregados; producir solo quiebres + WEB
COVERAGE_DAYS_VELA = 20
COVERAGE_DAYS_WEB = 14
WEB_SHARE = 0.33
WEB_SHARE_RANGE = (0.30, 0.40)
TALLER_REPLENISH = 0.15
STOCK_BUFFER = 0.0
MAX_PRODUCTION = 120
TARGET_PRODUCTION_NOTE = "100–120 und · quiebres talla en tienda + reserva WEB incremental"
POST_PEAK_WINDOW = 3
MIX_SEPT_WEIGHT = 1.0
OCT_FACTOR = 0.88
MIN_PRODUCE = 0

PEAK_DAYS = 4

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
    peak_share = min(0.78, 0.45 + peak_days * 0.08)
    peak_sales = sept_vela * peak_share
    recent_sales = max(sept_vela - peak_sales, 0)
    peak_daily = peak_sales / peak_days if peak_days else 0
    post_peak_daily = recent_sales / POST_PEAK_WINDOW
    observed_daily = sept_vela / max(days_elapsed, 1)
    return {
        "days_elapsed": days_elapsed,
        "peak_days": peak_days,
        "recent_days": POST_PEAK_WINDOW,
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

    # Curva talla × género desde septiembre (tendencia post-lanzamiento; DAMA predomina ~58–60%)
    mix_weighted = defaultdict(float)
    sept_mix = aggregate([r for r in ventas if r["mes"] == "septiembre"], "genero", "talla")
    aug_mix = aggregate([r for r in ventas if r["mes"] == "agosto"], "genero", "talla")
    aug_w = max(0.0, 1.0 - MIX_SEPT_WEIGHT)
    all_keys = set(sept_mix) | set(aug_mix)
    mix_total = 0.0
    for k in all_keys:
        v = sept_mix.get(k, 0) * MIX_SEPT_WEIGHT + aug_mix.get(k, 0) * aug_w
        mix_weighted[k] = v
        mix_total += v
    mix_pct = {k: (v / mix_total if mix_total else 0) for k, v in mix_weighted.items()}

    gen_share = {}
    talla_within = {g: {} for g in GENDER_ORDER}
    for g in GENDER_ORDER:
        gen_units = sum(sept_mix.get((g, t), 0) for t in TALLA_ORDER)
        gen_share[g] = gen_units
    gen_total = sum(gen_share.values()) or 1
    gen_pct = {g: gen_share[g] / gen_total for g in GENDER_ORDER}
    for g in GENDER_ORDER:
        gen_units = gen_share[g] or 1
        for t in TALLA_ORDER:
            u = sept_mix.get((g, t), 0)
            if u:
                talla_within[g][t] = round(u / gen_units * 100, 1)

    inv_by_loc = aggregate(inv_rows, "ubicacion", "genero", "talla")
    inv_vela = aggregate([r for r in inv_rows if r["ubicacion"] == "VELA"], "genero", "talla")
    inv_taller = aggregate([r for r in inv_rows if r["ubicacion"] == "TALLER"], "genero", "talla")
    inv_web = aggregate([r for r in inv_rows if r["ubicacion"] == "WEB"], "genero", "talla")
    inv_total = aggregate(inv_rows, "genero", "talla")

    post_peak = vel["post_peak_daily"]
    inv_total_qty = sum(r["qty"] for r in inv_rows)
    pool_cover_days = round(inv_total_qty / post_peak, 1) if post_peak else 0

    scenarios = []
    for label, cov_v, cov_w, web_pct in [
        ("Cobertura 18d VELA + WEB", 18, 12, WEB_SHARE),
        ("Cobertura 20d VELA + WEB (base)", COVERAGE_DAYS_VELA, COVERAGE_DAYS_WEB, WEB_SHARE),
        ("Cobertura 20d · WEB 30%", COVERAGE_DAYS_VELA, COVERAGE_DAYS_WEB, 0.30),
        ("Resto sept post-pico (referencia)", rest_sept_days, 0, 0),
    ]:
        vela_u = post_peak * cov_v
        web_u = post_peak * cov_w * web_pct if cov_w else 0
        scenarios.append({
            "label": label,
            "days_sept": cov_v,
            "days_oct": cov_w,
            "web_pct": web_pct,
            "vela_units": round(vela_u),
            "web_units": round(web_u),
            "total_units": round(vela_u + web_u),
        })

    primary = scenarios[1]
    raw_recs = []
    for g in GENDER_ORDER:
        for t in TALLA_ORDER:
            key = (g, t)
            pct = mix_pct.get(key, 0)
            if pct <= 0 and not inv_total.get(key):
                continue
            stock_vela = inv_vela.get(key, 0)
            stock_taller = inv_taller.get(key, 0)
            stock_web = inv_web.get(key, 0)
            stock_all = inv_total.get(key, 0)

            vela_need = post_peak * pct * COVERAGE_DAYS_VELA
            web_need = post_peak * pct * WEB_SHARE * COVERAGE_DAYS_WEB
            vela_short = max(0.0, vela_need - stock_vela)
            web_short = max(0.0, web_need - stock_web)
            taller_cover = min(stock_taller * TALLER_REPLENISH, vela_short)
            raw_gap = vela_short - taller_cover + web_short
            if STOCK_BUFFER:
                raw_gap *= 1 + STOCK_BUFFER
            raw_suggest = max(0, int(math.ceil(raw_gap - 0.4)))

            cob_vela = round(stock_vela / (post_peak * pct), 1) if post_peak * pct > 0 else None
            cob_pool = round(stock_all / (post_peak * pct), 1) if post_peak * pct > 0 else None
            raw_recs.append({
                "genero": g,
                "talla": t,
                "mix_pct": round(pct * 100, 1),
                "ventas_sept": sept_mix.get(key, 0),
                "ventas_total": sept_mix.get(key, 0) + aug_mix.get(key, 0),
                "stock_vela": stock_vela,
                "stock_taller": stock_taller,
                "stock_web": stock_web,
                "stock_total": stock_all,
                "demanda_vela": round(vela_need),
                "demanda_web": round(web_need),
                "demanda_total": round(vela_need + web_need),
                "stock_efectivo": stock_all,
                "taller_aporte": round(taller_cover),
                "gap_bruto": round(raw_gap, 1),
                "produccion_raw": raw_suggest,
                "cobertura_vela_dias": cob_vela,
                "cobertura_pool_dias": cob_pool,
                "prioridad": raw_suggest * (2 if cob_vela and cob_vela < 7 else 1),
            })

    total_raw = sum(r["produccion_raw"] for r in raw_recs)
    scale = 1.0
    capped = False
    if total_raw > MAX_PRODUCTION and total_raw > 0:
        scale = MAX_PRODUCTION / total_raw
        capped = True

    recs = []
    total_suggest = 0
    total_vela_d = 0
    total_web_d = 0
    for r in raw_recs:
        suggest = int(math.floor(r["produccion_raw"] * scale + 0.45)) if r["produccion_raw"] else 0
        if capped and suggest == 0 and r["produccion_raw"] > 0 and r["cobertura_vela_dias"] is not None and r["cobertura_vela_dias"] < 5:
            suggest = MIN_PRODUCE or 1
        out = {k: v for k, v in r.items() if k not in {"produccion_raw", "prioridad", "gap_bruto", "taller_aporte"}}
        out["produccion_sugerida"] = suggest
        out["nota_cap"] = "Ajustado al tope 120 und" if capped and r["produccion_raw"] > suggest else ""
        recs.append(out)
        total_suggest += suggest
        total_vela_d += r["demanda_vela"]
        total_web_d += r["demanda_web"]

    by_store = aggregate(ventas, "tienda")
    by_month = aggregate(ventas, "mes")
    by_gen = aggregate(ventas, "genero")
    by_talla = aggregate(ventas, "talla")

    prod_by_gen = defaultdict(int)
    prod_by_gt = defaultdict(int)
    for r in recs:
        prod_by_gen[r["genero"]] += r["produccion_sugerida"]
        prod_by_gt[(r["genero"], r["talla"])] += r["produccion_sugerida"]
    prod_total = sum(prod_by_gen.values()) or 1
    prod_gen_pct = {g: round(prod_by_gen[g] / prod_total * 100, 1) for g in GENDER_ORDER}
    prod_talla_within = {}
    for g in GENDER_ORDER:
        gsum = prod_by_gen[g] or 1
        prod_talla_within[g] = {
            t: round(prod_by_gt[(g, t)] / gsum * 100, 1)
            for t in TALLA_ORDER if prod_by_gt[(g, t)]
        }

    curves = {
        "mix_source": "Septiembre · curva post-lanzamiento",
        "mix_sept_weight": MIX_SEPT_WEIGHT,
        "ventas_genero_pct": {g: round(gen_pct[g] * 100, 1) for g in GENDER_ORDER},
        "ventas_talla_within": talla_within,
        "produccion_genero_pct": prod_gen_pct,
        "produccion_talla_within": prod_talla_within,
        "nota": (
            "Demanda distribuida con share género × talla dentro del género (misma lógica SPOTS). "
            "Producción inclina más a DAMA donde hay quiebre de stock (M, XS)."
        ),
    }

    return {
        "meta": {
            "diseno": DISENO,
            "modelo": MODELO,
            "ref_date": ref_date.isoformat(),
            "days_elapsed_sept": days_elapsed,
            "rest_sept_days": rest_sept_days,
            "mid_oct_days": mid_oct_days,
            "coverage_days_vela": COVERAGE_DAYS_VELA,
            "coverage_days_web": COVERAGE_DAYS_WEB,
            "pool_cover_days": pool_cover_days,
            "web_share": WEB_SHARE,
            "web_share_range": list(WEB_SHARE_RANGE),
            "stock_buffer": STOCK_BUFFER,
            "taller_replenish": TALLER_REPLENISH,
            "max_production": MAX_PRODUCTION,
            "production_capped": capped,
            "oct_factor": OCT_FACTOR,
            "target_note": TARGET_PRODUCTION_NOTE,
            "mix_sept_weight": MIX_SEPT_WEIGHT,
        },
        "totals": {
            "ventas_total": sum(r["qty"] for r in ventas),
            "ventas_sept": sept_total,
            "ventas_agosto": aug_total,
            "ventas_vela_sept": sept_vela,
            "inventario_total": inv_total_qty,
            "inventario_vela": sum(r["qty"] for r in inv_rows if r["ubicacion"] == "VELA"),
            "inventario_taller": sum(r["qty"] for r in inv_rows if r["ubicacion"] == "TALLER"),
            "produccion_sugerida": total_suggest,
            "produccion_raw": total_raw,
            "demanda_vela": total_vela_d,
            "demanda_web": total_web_d,
            "pool_cover_days": pool_cover_days,
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
        "curves": curves,
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
        ("Cobertura pool actual (días @ post-pico)", data["totals"]["pool_cover_days"]),
        ("Objetivo cobertura VELA (días)", meta["coverage_days_vela"]),
        (f"Incremento WEB ({int(meta['web_share']*100)}%)", f"{meta['coverage_days_web']} días"),
        ("Producción bruta (sin tope)", data["totals"]["produccion_raw"]),
        ("Producción sugerida total", data["totals"]["produccion_sugerida"]),
        ("Tope recomendado", meta["max_production"]),
        ("", ""),
        ("Supuestos", ""),
        ("Metodología", "Quiebres por talla + WEB · no duplica horizonte calendario completo"),
        ("Pool VELA+TALLER", f"{data['totals']['inventario_vela']}+{data['totals']['inventario_taller']} und (~{data['totals']['pool_cover_days']} días post-pico)"),
        ("TALLER en plan tienda", f"{int(meta['taller_replenish']*100)}% puede reponer VELA"),
        ("WEB vs VELA", f"{int(meta['web_share_range'][0]*100)}–{int(meta['web_share_range'][1]*100)}% (base {int(meta['web_share']*100)}%)"),
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
