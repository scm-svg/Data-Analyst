#!/usr/bin/env python3
"""Recalculate SHORT PLAYA SUBL dashboard DATA — Barquisimeto + factor diciembre 1.4."""

import json
import re
from collections import defaultdict
from pathlib import Path

HTML_PATH = Path(__file__).resolve().parent / "SHORT PLAYA SUBL.html"

MODELS = ["SHORT PLAYA UNICOLOR", "SHORT PLAYA SUBLIMADO"]
LINEAS = ["CAB", "KIDS"]
MESES_ORDER = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
ME_SHORT = {
    "enero": "Ene", "febrero": "Feb", "marzo": "Mar", "abril": "Abr",
    "mayo": "May", "junio": "Jun", "julio": "Jul", "agosto": "Ago",
    "septiembre": "Sep", "octubre": "Oct", "noviembre": "Nov", "diciembre": "Dic",
}
PARTIAL_MONTH = "agosto-2026"
VELOCITY_MONTHS_COUNT = 6
HIGH_SEASON_FACTOR = 1.4
DEC_BASE_FACTOR = 1.4
LEAD_MONTHS = 3
UNICOLOR_ACTIVE = {"Verde Pino", "Azul Pizarra", "Azul Verdoso", "Marron", "Cereza"}
SUBLIMADO_ACTIVE = {"Playuela", "Sal", "Tucupido", "Sombrero"}
SUBLIMADO_COLOR_ORDER = ["Playuela", "Sal", "Tucupido", "Sombrero"]
DEFAULT_LAUNCH_COLORS_CONFIG = [
    {
        "modelo": "SHORT PLAYA SUBLIMADO",
        "color": "Nuevo color",
        "display_after": "Sombrero",
        "benchmark_top_n": 3,
    },
]
NEW_STORES = ["VELA", "BARQUISIMETO"]


def mes_sort_key(mes: str):
    part, year = mes.rsplit("-", 1)
    return (int(year), MESES_ORDER.index(part))


def month_label(mes: str) -> str:
    part, year = mes.rsplit("-", 1)
    return f"{ME_SHORT[part]} {year[-2:]}"


def is_active(modelo: str, color: str) -> bool:
    if modelo == "SHORT PLAYA UNICOLOR":
        return color in UNICOLOR_ACTIVE
    if modelo == "SHORT PLAYA SUBLIMADO":
        return color in SUBLIMADO_ACTIVE
    return True


def load_data() -> dict:
    html = HTML_PATH.read_text(encoding="utf-8")
    match = re.search(r"var DATA=(\{.*?\});", html, re.DOTALL)
    if not match:
        raise ValueError("DATA block not found")
    return json.loads(match.group(1))


def velocity_months(meses_order: list) -> list:
    if PARTIAL_MONTH in meses_order and meses_order.index(PARTIAL_MONTH) >= VELOCITY_MONTHS_COUNT:
        i = meses_order.index(PARTIAL_MONTH)
        return meses_order[i - VELOCITY_MONTHS_COUNT : i]
    return meses_order[-VELOCITY_MONTHS_COUNT:]


def month_weight(mes: str) -> float:
    return DEC_BASE_FACTOR if mes.startswith("diciembre") else 1.0


def base_velocity(rows, genero, color, talla, vel_months):
    weighted = 0.0
    weights = 0.0
    for mes in vel_months:
        w = month_weight(mes)
        qty = sum(
            r["v"] for r in rows
            if r["genero"] == genero and r["color"] == color and r["talla"] == talla and r["mes"] == mes
        )
        weighted += qty * w
        weights += w
    return weighted / weights if weights > 0 else 0.0


def compute_production_plan(raw_rows, stock, stock_taller_by_key, vel_months):
    production_rows = []
    for modelo in MODELS:
        model_rows = [r for r in raw_rows if r["modelo"] == modelo]
        if not model_rows:
            continue
        for genero in LINEAS:
            colors = sorted({
                r["color"] for r in model_rows
                if r["genero"] == genero and is_active(modelo, r["color"])
            })
            for color in colors:
                tallas = sorted({
                    r["talla"] for r in model_rows
                    if r["genero"] == genero and r["color"] == color
                }, key=lambda t: (len(t), t))
                talla_rows = []
                color_v = color_v_base = color_stk = color_stk_taller = color_produce = 0.0

                for talla in tallas:
                    base_v = base_velocity(model_rows, genero, color, talla, vel_months)
                    v_mes_base = round(base_v, 1)
                    v_mes = round(base_v * HIGH_SEASON_FACTOR, 1)
                    key = f"{modelo}/{genero}/{color}/{talla}"
                    stk = int(stock.get(key, 0))
                    stk_taller = int(stock_taller_by_key.get(key, 0))
                    cob = round(stk / v_mes, 1) if v_mes > 0 else 999
                    need = max(0, round(v_mes * LEAD_MONTHS - stk)) if cob < LEAD_MONTHS else 0
                    talla_rows.append({
                        "talla": talla,
                        "v_mes_base": v_mes_base,
                        "v_mes": v_mes,
                        "stk": stk,
                        "stk_taller": stk_taller,
                        "cob": cob,
                        "produce": need,
                        "urgente": cob < LEAD_MONTHS,
                    })
                    color_v += v_mes
                    color_v_base += v_mes_base
                    color_stk += stk
                    color_stk_taller += stk_taller
                    color_produce += need

                if not talla_rows:
                    continue
                production_rows.append({
                    "modelo": modelo,
                    "genero": genero,
                    "color": color,
                    "v_mes_base": round(color_v_base, 1),
                    "v_mes": round(color_v, 1),
                    "stk": color_stk,
                    "stk_taller": color_stk_taller,
                    "cob": round(color_stk / color_v, 1) if color_v > 0 else 999,
                    "produce": color_produce,
                    "tallas": talla_rows,
                })

    summary = {}
    for modelo in MODELS:
        rows_m = [r for r in production_rows if r["modelo"] == modelo]
        v_mes = sum(r["v_mes"] for r in rows_m)
        v_mes_base = sum(r["v_mes_base"] for r in rows_m)
        stk = sum(r["stk"] for r in rows_m)
        stk_taller = sum(r["stk_taller"] for r in rows_m)
        produce = sum(r["produce"] for r in rows_m)
        summary[modelo] = {
            "v_mes_base": round(v_mes_base, 1),
            "v_mes": round(v_mes, 1),
            "stk": stk,
            "stk_taller": stk_taller,
            "cob": round(stk / v_mes, 1) if v_mes > 0 else 999,
            "produce": produce,
        }

    summary_genero = {}
    for genero in LINEAS:
        rows_g = [r for r in production_rows if r["genero"] == genero]
        v_mes = sum(r["v_mes"] for r in rows_g)
        v_mes_base = sum(r["v_mes_base"] for r in rows_g)
        stk = sum(r["stk"] for r in rows_g)
        produce = sum(r["produce"] for r in rows_g)
        summary_genero[genero] = {
            "v_mes_base": round(v_mes_base, 1),
            "v_mes": round(v_mes, 1),
            "stk": stk,
            "cob": round(stk / v_mes, 1) if v_mes > 0 else 999,
            "produce": produce,
        }

    return production_rows, summary, summary_genero


def rank_colors(model_rows, genero, vel_months, exclude=None, top_n=3):
    exclude = set(exclude or [])
    color_v = defaultdict(float)
    for r in model_rows:
        if r["genero"] != genero or r["mes"] not in vel_months or r["color"] in exclude:
            continue
        if not r.get("activo", True):
            continue
        color_v[r["color"]] += r["v"] * month_weight(r["mes"])
    ranked = sorted(color_v.items(), key=lambda x: -x[1])
    return [color for color, _ in ranked[:top_n]]


def compute_store_shares(model_rows, genero, stores):
    rows = [r for r in model_rows if r["genero"] == genero and r.get("activo", True)]
    tot = sum(r["v"] for r in rows)
    return {
        s: (sum(r["v"] for r in rows if r["tienda"] == s) / tot if tot > 0 else 0)
        for s in stores
    }


def resolve_store_share(store, shares, new_store_caps):
    cap = new_store_caps.get(store)
    if cap:
        if cap.get("type") == "avg" and cap.get("bases"):
            return sum(shares.get(b, 0) for b in cap["bases"]) / len(cap["bases"])
        return shares.get(cap.get("base"), 0) * cap.get("mult", 1)
    return shares.get(store, 0)


def line_velocity_adj(model_rows, genero, vel_months):
    weighted = 0.0
    weights = 0.0
    for mes in vel_months:
        w = month_weight(mes)
        qty = sum(
            r["v"] for r in model_rows
            if r["genero"] == genero and r["mes"] == mes and r.get("activo", True)
        )
        weighted += qty * w
        weights += w
    return (weighted / weights if weights > 0 else 0) * HIGH_SEASON_FACTOR


def compute_launch_plan(raw_rows, vel_months, configs, new_store_caps, decision_stores):
    launch_rows = []
    store_distribution = []
    for cfg in configs:
        modelo = cfg["modelo"]
        color = cfg["color"]
        top_n = int(cfg.get("benchmark_top_n", 3))
        after = cfg.get("display_after", "Sombrero")
        model_rows = [r for r in raw_rows if r["modelo"] == modelo]

        for genero in LINEAS:
            benchmark_colors = rank_colors(
                model_rows,
                genero,
                vel_months,
                exclude={color},
                top_n=top_n,
            )
            if not benchmark_colors:
                continue

            tallas = sorted(
                {
                    r["talla"] for r in model_rows
                    if r["genero"] == genero and r["color"] in benchmark_colors
                },
                key=lambda t: (len(t), t),
            )
            talla_rows = []
            color_v = color_v_base = color_produce = 0.0
            talla_v_map = {}

            for talla in tallas:
                refs = [
                    base_velocity(model_rows, genero, ref_color, talla, vel_months)
                    for ref_color in benchmark_colors
                ]
                base_v = sum(refs) / len(refs)
                v_mes_base = round(base_v, 1)
                v_mes = round(base_v * HIGH_SEASON_FACTOR, 1)
                produce_qty = max(0, round(v_mes * LEAD_MONTHS))
                talla_v_map[talla] = v_mes
                talla_rows.append({
                    "talla": talla,
                    "v_mes_base": v_mes_base,
                    "v_mes": v_mes,
                    "stk": 0,
                    "stk_taller": 0,
                    "cob": 0,
                    "produce": produce_qty,
                    "urgente": True,
                    "benchmark_refs": [
                        round(base_velocity(model_rows, genero, ref_color, talla, vel_months), 2)
                        for ref_color in benchmark_colors
                    ],
                })
                color_v += v_mes
                color_v_base += v_mes_base
                color_produce += produce_qty

            if not talla_rows:
                continue

            total_v = sum(talla_v_map.values())
            talla_mix = {t: (talla_v_map[t] / total_v if total_v > 0 else 0) for t in tallas}
            share_stores = sorted(
                set(decision_stores)
                | set(NEW_STORES)
                | {r["tienda"] for r in model_rows if r["genero"] == genero}
            )
            shares = compute_store_shares(model_rows, genero, share_stores)

            reabast_stores = list(decision_stores) + [
                s for s in NEW_STORES if s not in decision_stores
            ]
            store_weights = {
                s: resolve_store_share(s, shares, new_store_caps)
                if s in NEW_STORES else shares.get(s, 0)
                for s in reabast_stores
            }
            total_w = sum(store_weights.values())
            if total_w > 0:
                for store in reabast_stores:
                    store_total = round(color_produce * store_weights[store] / total_w)
                    if store_total < 1:
                        continue
                    talla_dist = []
                    allocated = 0
                    for idx, tr in enumerate(talla_rows):
                        qty = (
                            store_total - allocated
                            if idx == len(talla_rows) - 1
                            else round(store_total * talla_mix[tr["talla"]])
                        )
                        allocated += qty
                        if qty > 0:
                            talla_dist.append({"talla": tr["talla"], "qty": qty})
                    store_distribution.append({
                        "store": store,
                        "modelo": modelo,
                        "genero": genero,
                        "color": color,
                        "is_launch": True,
                        "is_new_store": store in NEW_STORES,
                        "total": store_total,
                        "tallas": talla_dist,
                        "share_pct": round(store_weights[store] / total_w * 1000) / 10,
                    })

            bench_label = " · ".join(benchmark_colors)
            launch_rows.append({
                "modelo": modelo,
                "genero": genero,
                "color": color,
                "is_launch": True,
                "display_after": after,
                "benchmark_colors": benchmark_colors,
                "benchmark_note": (
                    f"Prom. top {top_n}: {bench_label} · red completa "
                    f"(VELA 1.5× GRIETA · BARQUISIMETO prom. CHACAO+GRIETA)"
                ),
                "v_mes_base": round(color_v_base, 1),
                "v_mes": round(color_v, 1),
                "stk": 0,
                "stk_taller": 0,
                "cob": 0,
                "produce": color_produce,
                "tallas": talla_rows,
            })

    summary_launch = {}
    for modelo in MODELS:
        rows_m = [r for r in launch_rows if r["modelo"] == modelo]
        if not rows_m:
            continue
        summary_launch[modelo] = {
            "v_mes_base": round(sum(r["v_mes_base"] for r in rows_m), 1),
            "v_mes": round(sum(r["v_mes"] for r in rows_m), 1),
            "produce": sum(r["produce"] for r in rows_m),
            "colors": sorted({r["color"] for r in rows_m}),
        }

    return launch_rows, summary_launch, store_distribution


def compute_store_projection(raw_rows, stores, mult, meses, label):
    monthly = defaultdict(lambda: defaultdict(float))
    for r in raw_rows:
        if r["tienda"] not in stores or r["mes"] not in meses or not r.get("activo", True):
            continue
        key = (r["modelo"], r["genero"], r["color"], r["talla"])
        monthly[key][r["tienda"]] += r["v"]

    n = max(len(meses), 1)
    skus = []
    total_v = 0.0
    for key in sorted(monthly):
        per_store = [monthly[key][s] / n for s in stores]
        v_mes = round(sum(per_store) / len(stores) * mult * HIGH_SEASON_FACTOR, 2)
        total_v += v_mes
        modelo, genero, color, talla = key
        skus.append({
            "Modelo": modelo,
            "Genero": genero,
            "Color": color,
            "Talla": talla,
            "v_mes": v_mes,
            "need_1m": max(0, round(v_mes * 1)),
            "need_2m": max(0, round(v_mes * 2)),
            "need_3m": max(0, round(v_mes * 3)),
        })

    return {
        "v_mes": round(total_v, 1),
        "need_1m": max(0, round(total_v * 1)),
        "need_2m": max(0, round(total_v * 2)),
        "need_3m": max(0, round(total_v * 3)),
        "nota": label,
        "skus": skus,
    }


def rebuild_data(data: dict) -> dict:
    raw_rows = data["raw_rows"]
    stock = data["stock"]
    stock_taller = defaultdict(int)
    for store, items in data.get("stock_by_store", {}).items():
        if store == "TALLER":
            for key, qty in items.items():
                stock_taller[key] += qty

    meses_order = data["meses_order"]
    vel_months = velocity_months(meses_order)
    production_plan, summary_produccion, summary_genero = compute_production_plan(
        raw_rows, stock, stock_taller, vel_months
    )
    launch_config = data.get("launch_colors_config") or DEFAULT_LAUNCH_COLORS_CONFIG
    decision_stores = data.get("decision_stores") or [
        s for s in data.get("all_stores", [])
        if s not in {"WEB", "PEDIDOS", "CORPORATIVO", "VELA"}
    ]
    new_store_caps = {
        "VELA": {"base": "GRIETA", "mult": 1.5, "label": "1.5× GRIETA"},
        "BARQUISIMETO": {
            "type": "avg",
            "bases": ["CHACAO", "GRIETA"],
            "label": "prom. CHACAO + GRIETA",
        },
    }
    launch_production_plan, summary_launch, launch_store_distribution = compute_launch_plan(
        raw_rows, vel_months, launch_config, new_store_caps, decision_stores
    )

    data["production_plan"] = production_plan
    data["summary_produccion"] = summary_produccion
    data["summary_genero"] = summary_genero
    data["launch_colors_config"] = launch_config
    data["launch_production_plan"] = launch_production_plan
    data["summary_launch"] = summary_launch
    data["launch_store_distribution"] = launch_store_distribution
    data["sublimado_color_order"] = SUBLIMADO_COLOR_ORDER
    data["velocity_months"] = vel_months
    data["velocity_months_label"] = " · ".join(month_label(m) for m in vel_months)
    data["velocity_months_count"] = len(vel_months)
    data["high_season_factor"] = HIGH_SEASON_FACTOR
    data["december_base_factor"] = DEC_BASE_FACTOR
    data["new_store_caps"] = new_store_caps
    data["new_stores"] = NEW_STORES
    data["barquisimeto"] = compute_store_projection(
        raw_rows,
        ["CHACAO", "GRIETA"],
        1,
        vel_months,
        f"prom. CHACAO + GRIETA · factor temporada alta ×{HIGH_SEASON_FACTOR} · diciembre base ×{DEC_BASE_FACTOR}",
    )
    data["vela"] = compute_store_projection(
        raw_rows,
        ["GRIETA"],
        1.5,
        vel_months,
        f"1.5× GRIETA · factor temporada alta ×{HIGH_SEASON_FACTOR}",
    )
    return data


def build_html(data: dict) -> str:
    html = HTML_PATH.read_text(encoding="utf-8")
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = re.sub(
        r"var DATA=\{.*?\};",
        f"var DATA={data_json};",
        html,
        count=1,
        flags=re.DOTALL,
    )
    return html


def patch_js(html: str) -> str:
    old_share = (
        "function getNewStoreShare(store,realShares){\n"
        "  var cap=NEW_STORE_CAPS[store];if(!cap)return 0;\n"
        "  return(realShares[cap.base]||0)*cap.mult;\n"
        "}"
    )
    new_share = (
        "function getNewStoreShare(store,realShares){\n"
        "  var cap=NEW_STORE_CAPS[store];if(!cap)return 0;\n"
        "  if(cap.type==='avg'&&cap.bases&&cap.bases.length){\n"
        "    var sum=0;cap.bases.forEach(function(b){sum+=(realShares[b]||0);});\n"
        "    return sum/cap.bases.length;\n"
        "  }\n"
        "  return(realShares[cap.base]||0)*(cap.mult||1);\n"
        "}"
    )
    html = html.replace(old_share, new_share)

    html = html.replace(
        "VELA 1.5× GRIETA · BARQUISIMETO 1× GRIETA · factor temporada alta ×<span id=\"hsFactorLabel\">1.25</span>",
        "VELA 1.5× GRIETA · BARQUISIMETO prom. CHACAO+GRIETA · temporada alta ×<span id=\"hsFactorLabel\">1.4</span> · diciembre base ×1.4",
    )
    html = html.replace(
        "Base × '+hs+' (temporada alta). Es la velocidad usada para cobertura y producción.",
        "Base × '+hs+' (temporada alta / diciembre). Es la velocidad usada para cobertura y producción.",
    )
    return html


def main():
    data = rebuild_data(load_data())
    html = patch_js(build_html(data))
    HTML_PATH.write_text(html, encoding="utf-8")
    hs = data["high_season_factor"]
    barq = data["barquisimeto"]["v_mes"]
    prod = sum(r["produce"] for r in data["production_plan"])
    print(f"Wrote {HTML_PATH}")
    print(f"high_season_factor: {hs}")
    print(f"barquisimeto v_mes: {barq}")
    launch_prod = sum(r["produce"] for r in data["launch_production_plan"])
    print(f"total produce: {prod}")
    print(f"launch produce: {launch_prod}")
    if data["launch_production_plan"]:
        row = data["launch_production_plan"][0]
        print(f"launch sample: {row['genero']} {row['color']} -> {row['produce']} und (red completa)")
    vela_dist = sum(d["total"] for d in data["launch_store_distribution"] if d["store"] == "VELA")
    barq_dist = sum(d["total"] for d in data["launch_store_distribution"] if d["store"] == "BARQUISIMETO")
    print(f"launch dist VELA: {vela_dist} | BARQUISIMETO: {barq_dist}")
    print(f"new_store_caps BARQUISIMETO: {data['new_store_caps']['BARQUISIMETO']}")


if __name__ == "__main__":
    main()
