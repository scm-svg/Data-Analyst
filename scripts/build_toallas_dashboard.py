#!/usr/bin/env python3
"""Build / update DASHBOARD TOALLAS ESTAMPADAS.html from sales, inventory and transit Excel files."""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "DASHBOARD TOALLAS ESTAMPADAS.html"
SALES_XLSX = Path("/home/ubuntu/.cursor/projects/workspace/uploads/VENTAS_ACTUALIZADAS_TOALLAS_0a56.xlsx")
INV_XLSX = Path("/home/ubuntu/.cursor/projects/workspace/uploads/TOALLA_ESTAMPADA_INVENTARIO_ACTUAL4_e0fa.xlsx")
TRANSIT_XLSX = Path("/home/ubuntu/.cursor/projects/workspace/uploads/Compras_Marzo_-_TOALLAS_ESTAMPADAS_e9cb.xlsx")
OUTPUT = ROOT / "DASHBOARD TOALLAS ESTAMPADAS.html"

G2 = "TOALLA ESTAMPADA 2.0"
LEAD_TIME_MONTHS = 3.5

MESES_MAP = {
    "ENERO": "enero", "FEBRERO": "febrero", "MARZO": "marzo", "ABRIL": "abril",
    "MAYO": "mayo", "JUNIO": "junio", "JULIO": "julio", "AGOSTO": "agosto",
    "SEPTIEMBRE": "septiembre", "OCTUBRE": "octubre", "NOVIEMBRE": "noviembre", "DICIEMBRE": "diciembre",
    "enero": "enero", "febrero": "febrero", "marzo": "marzo", "abril": "abril",
    "mayo": "mayo", "junio": "junio", "julio": "julio", "agosto": "agosto",
    "septiembre": "septiembre", "octubre": "octubre", "noviembre": "noviembre", "diciembre": "diciembre",
}

STORE_MAP = {
    "GRAND PLAZ": "GRANDPLAZ", "GRANDPLAZ": "GRANDPLAZ", "Grandplaz": "GRANDPLAZ", "Grandplaz ": "GRANDPLAZ",
    "GRIETA": "LA GRIETA", "La Grieta": "LA GRIETA", "LA GRIETA": "LA GRIETA",
    "CERRO VERDE": "CERRO VERDE", "Cerro Verde": "CERRO VERDE", "Cerro Verde ": "CERRO VERDE",
    "SAMBIL CHACAO": "SAMBIL CHACAO", "Sambil Chacao": "SAMBIL CHACAO", "Sambil Chacao ": "SAMBIL CHACAO",
    "CHACAO": "SAMBIL CHACAO",
    "SAMBIL VALENCIA": "SAMBIL VALENCIA", "Sambil Valencia": "SAMBIL VALENCIA", "SAMBIL": "SAMBIL VALENCIA",
    "TOLON": "TOLON", "Tolon": "TOLON",
    "LA VELA": "LA VELA", "La Vela": "LA VELA", "VELA": "LA VELA",
    "WEB": "WEB",
    "PEDIDOS": "PEDIDOS", "Pedidos": "PEDIDOS", "CORPORATIVO": "PEDIDOS",
}

INV_LOC_MAP = {
    "CERRO VERDE": "CERRO VERDE", "CHACAO": "SAMBIL CHACAO", "GRANDPLAZ": "GRANDPLAZ",
    "GRIETA": "LA GRIETA", "SAMBIL": "SAMBIL VALENCIA", "TALLER": "TALLER",
    "TOLON": "TOLON", "VELA": "LA VELA",
}

TRANSIT_COLOR_MAP = {
    "MARGARITA": "Margarita", "MORROCOY": "Morrocoy", "CANAIMA": "Canaima",
    "PICO BOLIVAR": "Pico Bolivar", "CARIBE": "Caribe", "BEATS": "Beat", "BEAT": "Beat", "WAVES": "Waves",
}

LUGARES = {"Canaima", "Margarita", "Morrocoy", "Caribe", "Pico Bolivar", "Cayo de Agua", "Avila", "Roraima", "Choroni", "Amazonas", "Horizonte"}
PRINTS = {"Beat", "Waves", "Stripes", "Retro", "Candy", "Bitacora", "Oceano"}

CUTOVER = "octubre-2025"
TIPOS = ["Dama", "Caballero", "Empresa"]
MODELOS = ["TOALLA ESTAMPADA", "TOALLA ESTAMPADA 2.0"]


def norm_store(raw: str) -> str:
    s = str(raw).strip()
    return STORE_MAP.get(s, STORE_MAP.get(s.upper(), s.upper()))


def norm_mes(mes_raw, year) -> str:
    m = str(mes_raw).strip().upper()
    key = MESES_MAP.get(m, MESES_MAP.get(m.lower(), m.lower()))
    return f"{key}-{int(year)}"


def mes_sort_key(m: str) -> tuple:
    p = m.split("-")
    return (int(p[1]), list(dict.fromkeys(MESES_MAP.values())).index(p[0]) if p[0] in MESES_MAP.values() else 99)


def load_template_parts():
    html = TEMPLATE.read_text(encoding="utf-8")
    m = re.search(r"var DATA=(\{.*?\});", html, re.DOTALL)
    if not m:
        raise RuntimeError("Could not find var DATA= in template")
    return html[: m.start()], html[m.end() :], json.loads(m.group(1))


def build_gender_ratios(rows):
    ratios = defaultdict(Counter)
    overall = Counter()
    for r in rows:
        ratios[(r["o"], r["c"])][r["g"]] += r["v"]
        overall[r["g"]] += r["v"]
    default = {g: overall[g] / sum(overall.values()) for g in TIPOS}
    out = {"__default__": default}
    for k, c in ratios.items():
        t = sum(c.values())
        out[k] = {g: c[g] / t for g in TIPOS}
    return out


def split_qty(qty, ratios):
    if qty <= 0:
        return []
    order = sorted(TIPOS, key=lambda g: ratios.get(g, 0), reverse=True)
    parts, rem = [], qty
    for i, g in enumerate(order):
        n = rem if i == len(order) - 1 else min(int(round(qty * ratios.get(g, 0))), rem)
        if n > 0:
            parts.append((g, n))
            rem -= n
    return parts


def rows_from_sales(df, gender_ratios, cl_start):
    rows, cl = [], cl_start
    for _, r in df.iterrows():
        store = norm_store(r["tienda / ubicación"])
        modelo = str(r["Producto"]).strip()
        color = str(r["COLOR"]).strip()
        mes = norm_mes(r["Mes"], r["Año"])
        qty = int(r["Cant. ordenada"])
        if qty <= 0:
            continue
        parts = [("Empresa", qty)] if store == "PEDIDOS" else split_qty(
            qty, gender_ratios.get((modelo, color), gender_ratios["__default__"])
        )
        for g, v in parts:
            rows.append({"t": store, "g": g, "c": color, "m": mes, "o": modelo, "v": v, "cl": cl})
            cl += 1
    return rows, cl


def build_transit():
    df = pd.read_excel(TRANSIT_XLSX, header=None)
    eta = None
    items = []
    for _, row in df.iterrows():
        for cell in row:
            if isinstance(cell, pd.Timestamp):
                eta = cell.strftime("%Y-%m-%d")
        if pd.notna(row.iloc[1]) and pd.notna(row.iloc[3]):
            name = str(row.iloc[1]).strip().upper()
            try:
                qty = int(row.iloc[3])
            except (ValueError, TypeError):
                continue
            if name in ("NOMBRE", "TOTAL", "COLOR", "NAN") or qty <= 0:
                continue
            color = TRANSIT_COLOR_MAP.get(name, name.title())
            items.append({"color": color, "qty": qty, "modelo": G2})
    by_color = defaultdict(int)
    for it in items:
        by_color[it["color"]] += it["qty"]
    total = sum(by_color.values())
    rows = [{"ubicacion": "EN TRÁNSITO", "modelo": G2, "color": c, "qty": q, "sku": "", "transito": True} for c, q in sorted(by_color.items())]
    return dict(by_color), total, eta or "2026-03-27", rows


def build_inventory(transit_by_color):
    inv = pd.read_excel(INV_XLSX)
    stock = defaultdict(int)
    stock_by_loc = defaultdict(lambda: defaultdict(int))
    stock_by_modelo = defaultdict(int)
    inv_rows = []
    stock_taller = 0

    for _, r in inv.iterrows():
        loc = str(r["Ubicación"]).strip()
        modelo = str(r["MODELO"]).strip()
        color = str(r["COLOR"]).strip()
        qty = int(r["Cantidad en inventario"])
        if qty <= 0:
            continue
        key = f"{modelo}/{color}"
        stock[key] += qty
        stock_by_modelo[modelo] += qty
        mapped = INV_LOC_MAP.get(loc, loc)
        stock_by_loc[mapped][key] += qty
        inv_rows.append({"ubicacion": mapped, "modelo": modelo, "color": color, "qty": qty, "sku": str(r["SKU"]).strip(), "transito": False})
        if mapped == "TALLER":
            stock_taller += qty

    transit_rows = []
    for color, qty in transit_by_color.items():
        key = f"{G2}/{color}"
        stock_by_loc["EN TRÁNSITO"][key] = qty
        transit_rows.append({"ubicacion": "EN TRÁNSITO", "modelo": G2, "color": color, "qty": qty, "sku": "", "transito": True})

    inv_rows.extend(transit_rows)
    locs = sorted(set(list(stock_by_loc.keys()) + ["EN TRÁNSITO"]))

    return {
        "stock": dict(stock),
        "stock_by_loc": {k: dict(v) for k, v in stock_by_loc.items()},
        "stock_by_modelo": dict(stock_by_modelo),
        "stock_total": sum(stock.values()),
        "stock_taller": stock_taller,
        "inv_rows": inv_rows,
        "inv_locations": locs,
        "transit_by_color": transit_by_color,
    }


def compute_season_factors(meses_order, meses_und):
    dec = [m for m in meses_order if m.startswith("diciembre-")]
    feb_mar = [m for m in meses_order if m.startswith("febrero-") or m.startswith("marzo-")]
    other = [m for m in meses_order if m not in dec and m not in feb_mar and meses_und.get(m, 0) > 100]
    if not other:
        other = [m for m in meses_order if meses_und.get(m, 0) > 0]
    base = sum(meses_und[m] for m in other) / max(1, len(other))
    dec_v = sum(meses_und.get(m, 0) for m in dec) / max(1, len(dec)) if dec else base
    fm_v = sum(meses_und.get(m, 0) for m in feb_mar) / max(1, len(feb_mar)) if feb_mar else base
    dec_f = round(min(2.0, max(1.25, dec_v / base)), 2) if base else 1.5
    carn_f = round(min(1.5, max(1.1, fm_v / base)), 2) if base else 1.15
    return {
        "diciembre_pct": int(round((dec_f - 1) * 100)),
        "carnaval_pct": int(round((carn_f - 1) * 100)),
        "diciembre_factor": dec_f,
        "carnaval_factor": carn_f,
        "combined_factor": round(max(dec_f, carn_f), 2),
    }


def build_designs(raw_rows, meses_order, stock):
    by_design = defaultdict(lambda: {"total": 0, "tc": Counter(), "tiendas": Counter(), "mensual": Counter(), "o": "", "first_mes": None})
    for r in raw_rows:
        d = by_design[r["c"]]
        d["total"] += r["v"]
        d["tc"][r["g"]] += r["v"]
        d["tiendas"][r["t"]] += r["v"]
        d["mensual"][r["m"]] += r["v"]
        d["o"] = r["o"]
        if d["first_mes"] is None or mes_sort_key(r["m"]) < mes_sort_key(d["first_mes"]):
            d["first_mes"] = r["m"]

    closed = meses_order[:-1] if len(meses_order) > 1 else meses_order
    last3 = closed[-3:] if len(closed) >= 3 else closed
    designs = []
    for nombre, d in by_design.items():
        modelo = d["o"]
        stk = stock.get(f"{modelo}/{nombre}", 0)
        mensual = [d["mensual"].get(m, 0) for m in meses_order]
        v3 = sum(d["mensual"].get(m, 0) for m in last3)
        v_mes = round(v3 / max(1, len(last3)), 1)
        rot = round(d["total"] / (d["total"] + stk) * 100) if (d["total"] + stk) > 0 else 100
        fm = d["first_mes"]
        mo, y = fm.split("-")
        mo_i = list(dict.fromkeys(MESES_MAP.values())).index(mo) + 1
        designs.append({
            "nombre": nombre, "gen": modelo, "g2": modelo == G2,
            "launch_date": f"{int(y):04d}-{mo_i:02d}-01", "launch_mes": fm,
            "total": d["total"], "stk": stk, "stk_taller": 0, "v_mes": v_mes,
            "cob": round(stk / v_mes, 1) if v_mes > 0 else 0.0, "rot": rot,
            "mensual": mensual, "tc": dict(d["tc"]), "tiendas": dict(d["tiendas"]),
            "meses_vida": len([x for x in mensual if x > 0]),
            "tipo": "lugar" if nombre in LUGARES else "print" if nombre in PRINTS else "otro",
        })
    designs.sort(key=lambda x: x["total"], reverse=True)
    return designs


def build_purchase_plan(raw_rows, meses_order, stock, transit_by_color, season, velocity_months=2):
    """Lead time 3-4m: compra nueva NO alcanza diciembre. Separamos cobertura dic vs compra Q1."""
    closed = meses_order[:-1] if len(meses_order) > 1 else meses_order
    base_months = closed[-velocity_months:] if len(closed) >= velocity_months else closed
    dec_f = season["diciembre_factor"]
    carn_f = season["carnaval_factor"]
    plan, prod_curve = [], []
    sm_need = {1: 0, 2: 0, 3: 0}
    sm_stk, sm_transit, sm_v_base = 0, 0, 0

    colors = sorted({r["c"] for r in raw_rows if r["o"] == G2})
    for color in colors:
        key = f"{G2}/{color}"
        stk = stock.get(key, 0)
        transit = transit_by_color.get(color, 0)
        avail = stk + transit
        retail = [r for r in raw_rows if r["o"] == G2 and r["c"] == color and r["m"] in base_months and r["t"] != "PEDIDOS"]
        v_base = sum(r["v"] for r in retail) / max(1, len(base_months))
        v_adj = round(v_base * dec_f, 1)  # rotación ajustada referencia diciembre

        # Hasta diciembre 2026: Oct + Nov (base) + Dic (×dec) + Barquisimeto (~18% grieta)
        demand_dic = v_base * 2 + v_base * dec_f + v_base * 0.18
        cob_dic = round(avail / v_base, 1) if v_base > 0 else 99
        cubre_dic = avail >= demand_dic

        # Compra Q1 (ene-mar 2027): llegada ~ene con lead time · incluye carnaval/SS
        demand_q1 = v_base * carn_f + v_base * 2  # feb-mar carnaval + ene
        buy_q1 = max(0, int(round(demand_q1 - max(0, avail - demand_dic))))
        cob = round(avail / v_base, 1) if v_base > 0 else 99

        needs = {m: max(0, int(round(v_base * m - avail))) for m in (1, 2, 3)}
        for m in (1, 2, 3):
            sm_need[m] += needs[m]
        sm_stk += stk
        sm_transit += transit
        sm_v_base += v_base

        prod_curve.append({
            "modelo": G2, "color": color, "v_mes_base": round(v_base, 1), "v_mes": v_adj,
            "stk_total": stk, "stk_transit": transit, "stk_disponible": avail,
            "stk_pt": 0, "cobertura": min(cob, 99), "cobertura_pt": round(stk / v_base, 1) if v_base > 0 else 99,
            "cobertura_dic": round(avail / demand_dic * 3, 1) if demand_dic > 0 else 99,
            "demanda_dic": int(round(demand_dic)), "cubre_diciembre": cubre_dic,
            "need_1m": needs[1], "need_2m": needs[2], "need_3m": needs[3], "comprar": buy_q1,
        })
        plan.append({
            "modelo": G2, "color": color, "v_mes_base": round(v_base, 1), "v_mes": v_adj,
            "stk": stk, "transit": transit, "disponible": avail, "cobertura": cob,
            "demanda_dic": int(round(demand_dic)), "cubre_diciembre": cubre_dic, "comprar": buy_q1,
        })

    summary = {
        G2: {
            "v_mes_base": round(sm_v_base, 1), "v_mes": round(sm_v_base * dec_f, 1),
            "stk_total": sm_stk, "stk_transit": sm_transit, "stk_disponible": sm_stk + sm_transit,
            "need_1m": sm_need[1], "need_2m": sm_need[2], "need_3m": sm_need[3],
            "comprar_total": sum(p["comprar"] for p in plan),
            "cubre_diciembre_all": all(p["cubre_diciembre"] for p in plan),
            "stk_pt": 0,
        }
    }
    plan.sort(key=lambda x: x["comprar"], reverse=True)
    return plan, prod_curve, summary, base_months


def build_analysis_brief(raw_rows, meses_order, plan, transit_total, season, summary_prod):
    closed = meses_order[:-1]
    last2 = closed[-2:]
    recent = [r for r in raw_rows if r["o"] == G2 and r["m"] in last2 and r["t"] != "PEDIDOS"]
    by_c = Counter(r["c"] for r in recent)
    lugares = [(c, v) for c, v in by_c.most_common() if c in LUGARES]
    prints = [(c, v) for c, v in by_c.most_common() if c in PRINTS]
    rec_lugares = [c for c, _ in lugares[:2]]
    rec_prints = [c for c, _ in prints[:2]]

    buy_total = sum(p["comprar"] for p in plan)
    cubre_dic = [p for p in plan if p["cubre_diciembre"]]
    no_cubre_dic = [p for p in plan if not p["cubre_diciembre"]]
    prop4 = rec_lugares + rec_prints
    prop4_status = {p["color"]: "✓ cubre dic" if p["cubre_diciembre"] else f'⚠ faltan ~{p["demanda_dic"] - p["disponible"]} und' for p in plan if p["color"] in prop4}

    smry = summary_prod.get(G2, {})
    if smry.get("cubre_diciembre_all") and all(prop4_status.get(c, "").startswith("✓") for c in prop4):
        conclusion = (
            f"Los 4 diseños propuestos ({' / '.join(prop4)}) quedan cubiertos hasta diciembre "
            f"con PT + tránsito ({transit_total:,} und). Lead time {LEAD_TIME_MONTHS}m impide "
            f"compra nueva para dic-2026; pedido hoy llega ~ene-2027. "
            + (f"Compra Q1 sugerida: {buy_total} und para carnaval/SS." if buy_total else "Sin compra Q1 urgente.")
            + " Para 3.0 definir SKUs nuevos aparte."
        )
    elif no_cubre_dic:
        conclusion = (
            f"Atención: {len(no_cubre_dic)} diseños 2.0 no cubren diciembre incluso con tránsito "
            f"({', '.join(p['color'] for p in no_cubre_dic[:4])}). "
            f"Lead time {LEAD_TIME_MONTHS}m — reasignar stock o acelerar tránsito. "
            f"Compra Q1 adicional sugerida: {buy_total} und."
        )
    else:
        conclusion = f"Revisar cobertura por diseño. Compra Q1 sugerida: {buy_total} und."

    return {
        "contexto": "Reevaluación Toallas Sublimadas 3.0 · tránsito + Barquisimeto + temporada alta + escenario C/E",
        "propuesta_julio": "4 diseños para diciembre: 2 lugares + 2 estampados (prints)",
        "recomendacion_lugares": rec_lugares,
        "recomendacion_prints": rec_prints,
        "propuesta4_status": prop4_status,
        "escenario_reciente": f"Últimos 2 meses cerrados ({', '.join(m.replace('-', ' ').title() for m in last2)}): {sum(by_c.values())} und retail 2.0 (sin corporativo)",
        "transito_total": transit_total,
        "lead_time_meses": LEAD_TIME_MONTHS,
        "temporada_diciembre_pct": season["diciembre_pct"],
        "temporada_carnaval_pct": season["carnaval_pct"],
        "comprar_total_sugerido": buy_total,
        "cubre_diciembre_count": len(cubre_dic),
        "disenos_comprar_q1": [{"color": p["color"], "und": p["comprar"]} for p in plan if p["comprar"] > 0],
        "conclusion": conclusion,
    }


def build_data():
    _, _, old = load_template_parts()
    gender_ratios = build_gender_ratios([r for r in old["raw_rows"] if r["m"] >= CUTOVER])
    max_cl = max((r.get("cl", 0) for r in old["raw_rows"]), default=0) + 1
    kept = [r for r in old["raw_rows"] if r["m"] < CUTOVER]
    sales = pd.read_excel(SALES_XLSX)
    new_rows, _ = rows_from_sales(sales, gender_ratios, max_cl)
    raw_rows = kept + new_rows

    meses_order = sorted({r["m"] for r in raw_rows}, key=mes_sort_key)
    meses_und = Counter()
    for r in raw_rows:
        meses_und[r["m"]] += r["v"]

    transit_by_color, transit_total, transit_eta, _ = build_transit()
    inv = build_inventory(transit_by_color)
    season = compute_season_factors(meses_order, dict(meses_und))
    designs = build_designs(raw_rows, meses_order, inv["stock"])
    plan, prod_curve, summary_prod, vel_months = build_purchase_plan(
        raw_rows, meses_order, inv["stock"], transit_by_color, season
    )
    brief = build_analysis_brief(raw_rows, meses_order, plan, transit_total, season, summary_prod)

    tipo_stats = {t: {"und": sum(r["v"] for r in raw_rows if r["g"] == t), "cli": len({r["cl"] for r in raw_rows if r["g"] == t})} for t in TIPOS}
    all_stores = sorted({r["t"] for r in raw_rows if r["t"] != "PEDIDOS"})
    total = sum(r["v"] for r in raw_rows)
    corp = sum(r["v"] for r in raw_rows if r["t"] == "PEDIDOS")
    dr = f"{meses_order[0].split('-')[0].capitalize()} {meses_order[0].split('-')[1]} — {meses_order[-1].split('-')[0].capitalize()} {meses_order[-1].split('-')[1]}"

    return {
        "raw_rows": raw_rows,
        "clientes": old.get("clientes", {}),
        "stock": inv["stock"],
        "stock_by_loc": inv["stock_by_loc"],
        "stock_by_modelo": inv["stock_by_modelo"],
        "stock_total": inv["stock_total"],
        "stock_taller": inv["stock_taller"],
        "inv_rows": inv["inv_rows"],
        "inv_locations": inv["inv_locations"],
        "transit_total": transit_total,
        "transit_eta": transit_eta,
        "transit_by_color": transit_by_color,
        "meses_order": meses_order,
        "meses_und": dict(meses_und),
        "filtros": {"tiendas": sorted(set(all_stores + ["PEDIDOS"])), "tipos": TIPOS, "colores": sorted({r["c"] for r in raw_rows}), "modelos": MODELOS},
        "all_stores": all_stores,
        "total": total,
        "clientes_total": len({r["cl"] for r in raw_rows}),
        "tipo_stats": tipo_stats,
        "designs": designs,
        "gen1_count": sum(1 for d in designs if not d["g2"]),
        "gen2_count": sum(1 for d in designs if d["g2"]),
        "es_parcial": True,
        "season_factors": season,
        "high_season_factor": season["combined_factor"],
        "corp_total": corp,
        "corp_pct": round(corp / total * 1000) / 10 if total else 0,
        "purchase_plan": plan,
        "prod_curve": prod_curve,
        "summary_prod": summary_prod,
        "velocity_months": vel_months,
        "velocity_months_count": len(vel_months),
        "velocity_months_label": ", ".join(m.replace("-", " ").title() for m in vel_months),
        "lead_time_months": LEAD_TIME_MONTHS,
        "new_stores": ["BARQUISIMETO"],
        "new_store_caps": {"BARQUISIMETO": {"base": "LA GRIETA", "mult": 1, "label": "1× LA GRIETA"}},
        "store_weights": {
            "LA VELA": {"base": "LA GRIETA", "mult": 2, "label": "2× LA GRIETA"},
            "WEB": {"base": "SAMBIL CHACAO", "mult": 1, "label": "≈ SAMBIL CHACAO (refuerzo web)"},
            "TOLON": {"mult": 1.35, "label": "+35% histórico"},
        },
        "analysis_brief": brief,
        "date_range": dr,
        "decisiones_modelo": G2,
    }


INV_CSS = """
.inv-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:14px}
@media(max-width:900px){.inv-summary{grid-template-columns:repeat(2,1fr)}}
@media(max-width:500px){.inv-summary{grid-template-columns:1fr}}
.inv-sum-card{background:var(--s2);border:1px solid var(--brd);border-radius:12px;padding:18px 14px;text-align:center}
.inv-sum-card .num{font-family:var(--fh);font-size:1.8rem;font-weight:800;line-height:1;color:var(--ac)}
.inv-sum-card .lbl{font-size:0.65rem;color:var(--mu);text-transform:uppercase;letter-spacing:0.5px;margin-top:5px}
.inv-sum-card.tiendas .num{color:#00bcd4}
.inv-sum-card.taller .num{color:#f97316}
.inv-sum-card.transito{border-color:#a855f766;background:rgba(168,85,247,.08)}
.inv-sum-card.transito .num{color:#a855f7}
.inv-loc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}
.inv-loc-card{background:var(--surf);border:1px solid var(--brd);border-radius:12px;padding:14px 16px}
.inv-loc-card.transito{border-color:#a855f766;background:rgba(168,85,247,.05)}
.inv-loc-hdr{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:10px;gap:8px}
.inv-loc-hdr h4{font-family:var(--fh);font-size:0.82rem;font-weight:800;margin:0}
.inv-loc-hdr .sub2{font-size:0.63rem;color:var(--mu);margin-top:2px}
.inv-loc-tot{font-family:var(--fh);font-size:0.9rem;font-weight:800;color:var(--ac);white-space:nowrap}
.qty-pill{display:inline-block;background:rgba(91,106,247,.18);color:#a5b4fc;border-radius:5px;padding:1px 8px;font-size:0.72rem;font-weight:700}
.qty-pill.transito{background:rgba(168,85,247,.18);color:#c084fc}
.qty-ventas{display:block;font-size:0.58rem;color:var(--mu2);margin-top:1px}
"""

INVENTARIO_HTML = """
<div class="sec" id="sec-inventario">
  <div class="inv-summary" id="invSummary"></div>
  <div class="inv-loc-grid" id="invLocGrid"></div>
</div>
"""

DECISIONES_HTML = """
<div class="sec" id="sec-decisiones">
  <div class="card" style="margin-bottom:14px;background:rgba(99,102,241,.06);border-color:rgba(99,102,241,.25)">
    <h3 style="color:var(--ac);margin-bottom:6px">📋 Contexto · Toallas Sublimadas 3.0</h3>
    <div class="sub" style="margin-bottom:8px">Auditoría solicitada: tránsito + Barquisimeto + temporada alta + escenario C/E reciente</div>
    <div id="decBrief" style="font-size:0.74rem;color:var(--mu);line-height:1.65"></div>
  </div>
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap">
    <div style="font-family:var(--fh);font-size:0.82rem;font-weight:700;color:var(--mu)">📅 Meses base (solo 2.0):</div>
    <div style="display:flex;gap:6px">
      <button onclick="setDecMeses(1)" id="dm1" class="dmb" style="background:var(--s2);color:var(--mu);border:1px solid var(--brd);border-radius:20px;padding:4px 12px;font-size:0.73rem;cursor:pointer;font-family:var(--fb)">1 mes</button>
      <button onclick="setDecMeses(2)" id="dm2" class="dmb" style="background:var(--ac);color:#fff;border:1px solid var(--ac);border-radius:20px;padding:4px 12px;font-size:0.73rem;cursor:pointer;font-family:var(--fb)">2 meses</button>
      <button onclick="setDecMeses(3)" id="dm3" class="dmb" style="background:var(--s2);color:var(--mu);border:1px solid var(--brd);border-radius:20px;padding:4px 12px;font-size:0.73rem;cursor:pointer;font-family:var(--fb)">3 meses</button>
    </div>
    <div style="font-size:0.68rem;color:var(--mu2)">🎄 Dic +<span id="decPct">0</span>% · 🎭 Carnaval/SS +<span id="carnPct">0</span>% · Lead time <span id="leadTime">3.5</span>m · 🏢 Corp: <strong id="corpPctLabel">0%</strong></div>
  </div>
  <div class="tkpis" id="decKpis"></div>
  <div class="g1 card">
    <h3>🛒 Curva de Compra · Colección 2.0</h3>
    <div class="sub">Compra internacional · cobertura en meses · incluye tránsito marzo (<span id="transitHdr">0</span> und ETA <span id="transitEta">—</span>)</div>
    <div id="propGrid" style="display:grid;grid-template-columns:1fr;gap:12px;margin-top:10px"></div>
  </div>
  <div class="card g1">
    <h3>🏪 Distribución por Tienda · 2.0</h3>
    <div class="sub"><span style="color:#f97316">VELA 2× GRIETA · WEB ≈ CHACAO · TOLON +35% · BARQUISIMETO 1× GRIETA</span></div>
    <div id="reabastGrid" style="margin-top:10px"></div>
  </div>
  <div class="card g1" id="decPropuesta4"></div>
</div>
"""

EXTRA_JS = r"""
function rInventario(){
  var inv=DATA.inv_rows||[];
  if(!inv.length){document.getElementById('invSummary').innerHTML='<div class="nodata" style="grid-column:1/-1">Sin inventario</div>';document.getElementById('invLocGrid').innerHTML='';return;}
  var tot=0,taller=0,transito=DATA.transit_total||0,tiendas=0;
  var byLoc={};
  inv.forEach(function(r){
    if(!byLoc[r.ubicacion])byLoc[r.ubicacion]={total:0,rows:{}};
    var k=r.modelo+'/'+r.color;
    if(!byLoc[r.ubicacion].rows[k])byLoc[r.ubicacion].rows[k]={modelo:r.modelo,color:r.color,qty:0,transito:!!r.transito};
    byLoc[r.ubicacion].rows[k].qty+=r.qty;
    byLoc[r.ubicacion].total+=r.qty;
    if(r.ubicacion==='TALLER')taller+=r.qty;
    else if(r.ubicacion==='EN TRÁNSITO'){}
    else tiendas+=r.qty;
  });
  tot=DATA.stock_total+(transito||0);
  document.getElementById('invSummary').innerHTML=
    '<div class="inv-sum-card"><div class="num">'+DATA.stock_total.toLocaleString()+'</div><div class="lbl">Stock PT</div></div>'+
    '<div class="inv-sum-card transito"><div class="num">'+(transito||0).toLocaleString()+'</div><div class="lbl">En Tránsito</div><div style="font-size:.58rem;color:var(--mu2);margin-top:3px">ETA '+(DATA.transit_eta||'—')+'</div></div>'+
    '<div class="inv-sum-card tiendas"><div class="num">'+tiendas.toLocaleString()+'</div><div class="lbl">En Tiendas</div></div>'+
    '<div class="inv-sum-card taller"><div class="num">'+taller.toLocaleString()+'</div><div class="lbl">En Taller</div></div>';
  var locs=Object.keys(byLoc).sort(function(a,b){
    if(a==='EN TRÁNSITO')return-1;if(b==='EN TRÁNSITO')return 1;
    if(a==='TALLER')return 1;if(b==='TALLER')return-1;
    return byLoc[b].total-byLoc[a].total;
  });
  var salesMap={};
  fr().forEach(function(r){var k=r.o+'/'+r.c;salesMap[k]=(salesMap[k]||0)+r.v;});
  var h='';
  locs.forEach(function(loc){
    var ld=byLoc[loc],isTrans=loc==='EN TRÁNSITO',isTaller=loc==='TALLER';
    var keys=Object.keys(ld.rows).sort(function(a,b){return ld.rows[b].qty-ld.rows[a].qty;});
    h+='<div class="inv-loc-card'+(isTrans?' transito':'')+'">'+
      '<div class="inv-loc-hdr"><div><h4>'+(isTrans?'🚢 ':isTaller?'🏭 ':'🏬 ')+loc+'</h4>'+
      '<div class="sub2">'+(isTrans?'Compra marzo · llegada estimada '+(DATA.transit_eta||''):'Stock físico · ventas del período filtrado')+'</div></div>'+
      '<div class="inv-loc-tot" style="'+(isTrans?'color:#a855f7':isTaller?'color:#f97316':'')+'">'+ld.total+' und</div></div>'+
      '<table class="ct"><thead><tr><th>Diseño</th><th>Colección</th><th>Cant.</th><th>Ventas filt.</th></tr></thead><tbody>';
    keys.forEach(function(k){
      var rd=ld.rows[k],sv=salesMap[k]||0;
      h+='<tr><td><span class="chip" style="background:'+cn(rd.color)+'"></span>'+rd.color+'</td>'+
        '<td style="font-size:.68rem;color:var(--mu)">'+(rd.modelo==='TOALLA ESTAMPADA 2.0'?'2.0':'1.0')+'</td>'+
        '<td><span class="qty-pill'+(isTrans?' transito':'')+'">'+rd.qty+'</span></td>'+
        '<td style="font-size:.68rem;color:var(--mu)">'+sv+' und</td></tr>';
    });
    h+='</tbody></table></div>';
  });
  document.getElementById('invLocGrid').innerHTML=h;
}

// ── DECISIONES (solo 2.0) ──
var _decMeses=2;
var DEC_MOD=DATA.decisiones_modelo||'TOALLA ESTAMPADA 2.0';
var REAL_STORES=DATA.all_stores;
var NEW_STORES=DATA.new_stores||['BARQUISIMETO'];
var NEW_STORE_CAPS=DATA.new_store_caps||{};
var STORE_WEIGHTS=DATA.store_weights||{};

function setDecMeses(n){
  _decMeses=n;
  ['dm1','dm2','dm3'].forEach(function(id,i){
    var b=document.getElementById(id);if(!b)return;
    var a=(i+1)===n;b.style.background=a?'var(--ac)':'var(--s2)';b.style.color=a?'#fff':'var(--mu)';b.style.borderColor=a?'var(--ac)':'var(--brd)';
  });
  rDecisiones();
}
function getBaseMonths(meses){
  var m=DATA.meses_order.slice();
  if(DATA.es_parcial)m=m.slice(0,-1);
  return m.slice(-meses);
}
function getAdjFactor(){
  var s=DATA.season_factors||{};
  return s.combined_factor||DATA.high_season_factor||1.25;
}
function getStoreShares(rows,meses){
  var mO=getBaseMonths(meses),f=rows.filter(function(r){return r.o===DEC_MOD&&r.m===undefined||mO.indexOf(r.m)>=0;});
  f=rows.filter(function(r){return r.o===DEC_MOD&&mO.indexOf(r.m)>=0&&r.t!=='PEDIDOS';});
  var hist={},tot=0;
  REAL_STORES.forEach(function(s){var v=f.filter(function(r){return r.t===s;}).reduce(function(a,x){return a+x.v;},0);hist[s]=v;tot+=v;});
  var shares={};
  REAL_STORES.forEach(function(s){
    var sh=tot>0?hist[s]/tot:0;
    var w=STORE_WEIGHTS[s];
    if(w&&w.base){sh=(tot>0?(hist[w.base]||0)/tot:0)*(w.mult||1);}
    else if(w&&w.mult){sh=sh*(w.mult||1);}
    shares[s]=sh;
  });
  NEW_STORES.forEach(function(ns){
    var cap=NEW_STORE_CAPS[ns];shares[ns]=cap?(hist[cap.base]||0)/tot*(cap.mult||1):0;
  });
  var sum=0;for(var k in shares)sum+=shares[k];
  if(sum>0)for(var k in shares)shares[k]=shares[k]/sum;
  return{shares:shares,total:tot};
}
function getLineForecast(meses){
  var mO=getBaseMonths(meses);
  var r=DATA.raw_rows.filter(function(r){return r.o===DEC_MOD&&mO.indexOf(r.m)>=0&&r.t!=='PEDIDOS';});
  return mO.length?Math.round(r.reduce(function(a,x){return a+x.v;},0)/mO.length*getAdjFactor()):0;
}

function rDecisiones(){
  var meses=_decMeses||2,s=DATA.season_factors||{},brief=DATA.analysis_brief||{};
  var decPct=document.getElementById('decPct');if(decPct)decPct.textContent=s.diciembre_pct||0;
  var carnPct=document.getElementById('carnPct');if(carnPct)carnPct.textContent=s.carnaval_pct||0;
  var lt=document.getElementById('leadTime');if(lt)lt.textContent=DATA.lead_time_months||3.5;
  var th=document.getElementById('transitHdr');if(th)th.textContent=(DATA.transit_total||0).toLocaleString();
  var te=document.getElementById('transitEta');if(te)te.textContent=DATA.transit_eta||'—';
  var corpLbl=document.getElementById('corpPctLabel');if(corpLbl)corpLbl.textContent=(DATA.corp_pct||0)+'%';

  var briefEl=document.getElementById('decBrief');
  if(briefEl&&brief.conclusion){
    briefEl.innerHTML='<p><strong>Propuesta julio:</strong> '+brief.propuesta_julio+'</p>'+
      '<p><strong>Recomendación data-driven:</strong> Lugares → <em>'+(brief.recomendacion_lugares||[]).join(', ')+'</em> · Prints → <em>'+(brief.recomendacion_prints||[]).join(', ')+'</em></p>'+
      '<p>'+brief.escenario_reciente+' · Tránsito: '+(brief.transito_total||0).toLocaleString()+' und</p>'+
      '<p style="margin-top:8px;padding:8px 10px;background:rgba(76,175,118,.08);border-radius:8px;border-left:3px solid #4caf76"><strong>Conclusión:</strong> '+brief.conclusion+'</p>';
  }

  var plan=DATA.purchase_plan||[],smry=DATA.summary_prod[DEC_MOD]||{};
  var totalComprar=plan.reduce(function(a,r){return a+r.comprar;},0);
  var lf=getLineForecast(meses);

  document.getElementById('decKpis').innerHTML=
    '<div class="tkpi"><div class="tv">'+lf+'</div><div class="tl">Rotación adj. 2.0</div><div class="ts">× '+getAdjFactor()+' temporada</div></div>'+
    '<div class="tkpi"><div class="tv" style="color:#a855f7">'+(DATA.transit_total||0).toLocaleString()+'</div><div class="tl">En tránsito</div><div class="ts">Marzo · ETA '+((DATA.transit_eta||'').slice(0,10))+'</div></div>'+
    '<div class="tkpi"><div class="tv" style="color:#ffc107">'+(smry.stk_disponible||0).toLocaleString()+'</div><div class="tl">Disp. total 2.0</div><div class="ts">PT '+((smry.stk_total||0).toLocaleString())+' + tránsito</div></div>'+
    '<div class="tkpi"><div class="tv" style="color:'+(totalComprar>0?'#f59e0b':'#10b981')+'">'+totalComprar+'</div><div class="tl">Comprar Q1</div><div class="ts">Lead time '+(DATA.lead_time_months||3.5)+'m · llega ~ene</div></div>'+
    '<div class="tkpi"><div class="tv" style="color:#f97316">🆕 BQTO</div><div class="tl">Barquisimeto</div><div class="ts">1× LA GRIETA</div></div>';

  var pgEl=document.getElementById('propGrid');
  if(pgEl){
    var rows=DATA.prod_curve.filter(function(r){return r.modelo===DEC_MOD;}).sort(function(a,b){return b.v_mes-a.v_mes;});
    var cob=smry.v_mes>0?((smry.stk_disponible||0)/smry.v_mes).toFixed(1):0;
    var need=meses===1?smry.need_1m:meses===2?smry.need_2m:smry.need_3m;
    var html='<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">'+
      '<span style="font-size:.75rem;color:var(--mu2)">Cobertura disponible (PT+tránsito): <strong style="color:var(--ac)">'+cob+' meses</strong></span>'+
      '<span style="font-size:.75rem;color:var(--mu2)">Comprar '+meses+'m: <strong style="color:'+(need>0?'#f59e0b':'#10b981')+'">'+need+' und</strong></span></div>';
    html+=rows.map(function(r){
      var buy=r.comprar||0,tc=r.cobertura<1?'#ef4444':r.cobertura<2?'#f59e0b':r.cobertura<3?'#3b82f6':'#10b981';
      var dicOk=r.cubre_diciembre;
      return '<div style="display:grid;grid-template-columns:120px 1fr auto;gap:8px;align-items:center;padding:6px 10px;background:rgba(0,0,0,.12);border-radius:8px;margin-bottom:4px">'+
        '<span><span class="chip" style="background:'+cn(r.color)+'"></span><strong>'+r.color+'</strong></span>'+
        '<span style="font-size:.66rem;color:var(--mu2)">'+r.v_mes_base.toFixed(0)+'/mes base · PT '+r.stk_total+' · 🚢 '+r.stk_transit+' · disp. '+r.stk_disponible+
        ' · Dic: '+(r.demanda_dic||0)+' und '+(dicOk?'<span style="color:#10b981">✓</span>':'<span style="color:#ef4444">✗</span>')+'</span>'+
        (buy>0?'<span style="background:rgba(245,158,11,.15);color:#f59e0b;border-radius:5px;padding:2px 8px;font-size:.65rem;font-weight:700">Comprar Q1 +'+buy+'</span>':'<span style="color:#10b981;font-size:.65rem">'+(dicOk?'✓ Dic OK':'—')+'</span>')+
        '</div>';
    }).join('');
    pgEl.innerHTML=html;
  }

  var reEl=document.getElementById('reabastGrid');
  if(reEl){
    var allRows=DATA.raw_rows.filter(function(r){return r.o===DEC_MOD;});
    var sw=getStoreShares(allRows,meses);
    var stores=REAL_STORES.concat(NEW_STORES);
    var h='<table class="ct"><thead><tr><th>Tienda</th><th>Peso proj.</th><th>Und/mes 2.0</th><th>Notas</th></tr></thead><tbody>';
    stores.forEach(function(s){
      var sh=sw.shares[s]||0,proj=Math.round(lf*sh);
      if(proj<=0&&NEW_STORES.indexOf(s)<0&&sh<0.005)return;
      var note=(STORE_WEIGHTS[s]||{}).label||((NEW_STORE_CAPS[s]||{}).label||'');
      var isNew=NEW_STORES.indexOf(s)>=0;
      h+='<tr><td>'+(isNew?'🆕 ':'')+s+'</td><td>'+(Math.round(sh*1000)/10)+'%</td><td class="rn">'+proj+'</td>'+
        '<td style="font-size:.65rem;color:var(--mu2)">'+note+'</td></tr>';
    });
    reEl.innerHTML=h+'</tbody></table>';
  }

  var p4=document.getElementById('decPropuesta4');
  if(p4&&brief.recomendacion_lugares){
    var lug=brief.recomendacion_lugares||[],pr=brief.recomendacion_prints||[];
    p4.innerHTML='<h3>🎯 Propuesta 4 diseños · justificación con data</h3><div class="sub">Decisión julio: 2 lugares + 2 prints para diciembre / base 3.0</div>'+
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px">'+
      '<div style="background:rgba(247,91,138,.08);border-radius:10px;padding:12px;border:1px solid rgba(247,91,138,.2)"><div style="font-weight:700;color:#f75b8a;margin-bottom:6px">🗺️ Lugares (top retail reciente)</div>'+
      lug.map(function(c){var p=(DATA.purchase_plan||[]).find(function(x){return x.color===c;});var st=p?(p.cubre_diciembre?'✓ Cubre dic':'⚠ Falta dic · disp. '+p.disponible+'/nec. '+p.demanda_dic):'—';return '<div style="font-size:.72rem;padding:3px 0">'+c+' — '+st+(p&&p.comprar>0?' · Q1 +'+p.comprar:'')+'</div>';}).join('')+'</div>'+
      '<div style="background:rgba(171,123,250,.08);border-radius:10px;padding:12px;border:1px solid rgba(171,123,250,.2)"><div style="font-weight:700;color:#ab7bfa;margin-bottom:6px">🖼️ Prints (top retail reciente)</div>'+
      pr.map(function(c){var p=(DATA.purchase_plan||[]).find(function(x){return x.color===c;});var st=p?(p.cubre_diciembre?'✓ Cubre dic':'⚠ Falta dic · disp. '+p.disponible+'/nec. '+p.demanda_dic):'—';return '<div style="font-size:.72rem;padding:3px 0">'+c+' — '+st+(p&&p.comprar>0?' · Q1 +'+p.comprar:'')+'</div>';}).join('')+'</div></div>';
  }
}
"""


def patch_html(before: str, after: str, data: dict) -> str:
    dr = data["date_range"]

    if ".inv-summary" not in before:
        before = before.replace("@media print{", INV_CSS + "\n@media print{")

    if "sec-inventario" not in before:
        before = before.replace(
            '<button class="tab" onclick="st(\'cliente\')">👥 Tipo Cliente</button>',
            '<button class="tab" onclick="st(\'cliente\')">👥 Tipo Cliente</button>\n  <button class="tab" onclick="st(\'inventario\')">📦 Inventario</button>',
        )

    if 'id="sec-decisiones"' not in before:
        before = before.replace(
            '</div>\n\n</div>\n<div class="footer">Toallas Estampadas',
            '</div>\n\n' + INVENTARIO_HTML + '\n' + DECISIONES_HTML + '\n</div>\n<div class="footer">Toallas Estampadas',
        )
    else:
        before = re.sub(r'<div class="sec" id="sec-decisiones">.*?(?=</div>\n<div class="footer">)', DECISIONES_HTML + "\n", before, flags=re.DOTALL)
        if "sec-inventario" not in before:
            before = before.replace('<div class="sec" id="sec-decisiones">', INVENTARIO_HTML + '\n<div class="sec" id="sec-decisiones">')

    before = re.sub(
        r'<div class="footer">Toallas Estampadas · Dashboard de Ventas con Género del Cliente · [^<]+</div>',
        f'<div class="footer">Toallas Estampadas · Dashboard de Ventas con Género del Cliente · {dr} · Somos Cuadro</div>',
        before,
    )
    before = re.sub(
        r"Dashboard de Ventas &nbsp;·&nbsp; [^<]+",
        f"Dashboard de Ventas &nbsp;·&nbsp; {dr} &nbsp;·&nbsp; Incluye género del cliente",
        before,
        count=1,
    )

    after = re.sub(
        r"var TABS=\[[^\]]+\];",
        "var TABS=['resumen','colores','tiendas','lanzamientos','cliente','inventario','decisiones'];",
        after,
    )
    after = re.sub(
        r"else if\(n==='cliente'\)rCliente\(\);.*?setTimeout\(addExpandBtns,120\);\}",
        "else if(n==='cliente')rCliente();else if(n==='inventario')rInventario();else if(n==='decisiones')rDecisiones();\n  setTimeout(addExpandBtns,120);}",
        after,
        flags=re.DOTALL,
    )

    # KPI header: add transit
    after = after.replace(
        "'<div class=\"kpib\"><div class=\"kv\" style=\"color:#ffc107\">'+gStk.toLocaleString()+'</div><div class=\"kl\">Stock</div><div class=\"ksub\">actualizado</div></div>'+",
        "'<div class=\"kpib\"><div class=\"kv\" style=\"color:#ffc107\">'+gStk.toLocaleString()+'</div><div class=\"kl\">Stock PT</div><div class=\"ksub\">actualizado</div></div>'+\n    '<div class=\"kpib\"><div class=\"kv\" style=\"color:#a855f7\">'+(DATA.transit_total||0).toLocaleString()+'</div><div class=\"kl\">En Tránsito</div><div class=\"ksub\">Mar '+((DATA.transit_eta||'').slice(5,7)||'')+'</div></div>'+",
    )

    # Alerts
    last_m = data["meses_order"][-1].replace("-", " ").title()
    after = re.sub(
        r"alerts\.push\(\{type:'info',text:'📅 [^']+'\}\);",
        f"alerts.push({{type:'info',text:'📅 {last_m} con datos parciales'}});",
        after,
        count=1,
    )
    if "transito" not in after[after.find("function renderAlertas"):after.find("function rResumen")]:
        after = after.replace(
            "alerts.push({type:'info',text:'📦 Stock Taller:",
            "alerts.push({type:'info',text:'🚢 En tránsito: '+(DATA.transit_total||0).toLocaleString()+' und 2.0 · ETA '+(DATA.transit_eta||'—')});\n  alerts.push({type:'info',text:'📦 Stock Taller:",
        )

    # Replace old decisiones JS block
    after = re.sub(r"// ── DECISIONES ──.*?/\* ── EXPORT / FULLSCREEN ── \*/", EXTRA_JS + "\n/* ── EXPORT / FULLSCREEN ── */", after, flags=re.DOTALL)

    return before + "var DATA=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";" + after


def main():
    before, after, _ = load_template_parts()
    data = build_data()
    html = patch_html(before, after, data)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(f"  stock PT: {data['stock_total']} | transit: {data['transit_total']}")
    print(f"  season: dic +{data['season_factors']['diciembre_pct']}% carn +{data['season_factors']['carnaval_pct']}%")
    print(f"  comprar 2.0: {data['summary_prod'][G2]['comprar_total']}")
    print(f"  brief: {data['analysis_brief']['conclusion'][:120]}...")


if __name__ == "__main__":
    main()
