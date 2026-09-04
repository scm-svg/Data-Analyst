#!/usr/bin/env python3
"""Rebuild SPOTS DASHBOARD.html from ventas + inventario CSV."""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

HTML_PATH = Path(__file__).resolve().parent / "SPOTS DASHBOARD.html"
VENTAS_PATH = Path(__file__).resolve().parent / "data" / "spots_ventas.csv"
INV_PATH = Path(__file__).resolve().parent / "data" / "spots_inventario.csv"

HIGH_SEASON_FACTOR = 1.2
DECEMBER_HS_FACTOR = 1.4
LEAD_MONTHS = 3
PROD_MONTHS_OPTIONS = [3, 4, 6]
DEFAULT_PROD_MONTHS = 3
TALLA_BOOST = {"XL": 1.15, "2XL": 1.20}
PARTIAL_MONTH = "septiembre-2026"
VELOCITY_MONTHS_COUNT = 3
BASE_STORE = "VELA"
DECISION_STORES = ["VELA"]
BQT_DISENO_CIUDAD = "Ciudad"
BQT_DISENO_VIRGEN = "Virgen"
BQT_VIRGEN_REF = "Virgen del Valle"
BQT_CIUDAD_REF = "Nueva Esparta"
ADDITIONAL_COLOR = "Color adicional"
ADDITIONAL_COLOR_FACTOR = 0.70
MC_MODEL = "SPOTS MANGA CORTA"
EXPANSION_STORES = ["CARACAS", "VALENCIA", "BARQUISIMETO"]
PROD_ZONE_ORDER = ["MARGARITA", "CARACAS", "VALENCIA", "BARQUISIMETO"]
# Proyección 3 meses calibrada · color adicional = 70% del blanco principal
EXPANSION_CAPS = {
    "CARACAS": {
        "tiendas": 4,
        "tienda_weights": [1.0, 1.0, 0.5, 0.15],
        "target_total_3m": 475,
        "label": (
            "Caracas · 4 tiendas CCS (2 alto peso · 1 media · 1 bajo) · MC · "
            f"Blanco + {ADDITIONAL_COLOR} al {int(ADDITIONAL_COLOR_FACTOR * 100)}%"
        ),
        "modelos": [MC_MODEL],
        "blanco_diseno": "Caracas",
        "adicional_diseno": "Caracas Alt",
    },
    "VALENCIA": {
        "tiendas": 2,
        "target_total_3m": 375,
        "label": (
            f"Valencia · 2 tiendas · MC · Blanco + {ADDITIONAL_COLOR} al "
            f"{int(ADDITIONAL_COLOR_FACTOR * 100)}%"
        ),
        "modelos": [MC_MODEL],
        "blanco_diseno": "Valencia",
        "adicional_diseno": "Valencia Alt",
    },
    "BARQUISIMETO": {
        "tiendas": 1,
        "target_total_3m": 450,
        "label": (
            f"Barquisimeto · 1 tienda · MC · Ciudad ~180 + Virgen 100-120 + "
            f"{ADDITIONAL_COLOR} 70% Ciudad · total ~450"
        ),
        "modelos": [MC_MODEL],
        "design_targets_3m": [
            {
                "diseno": BQT_DISENO_CIUDAD,
                "color": "Blanco",
                "target": 200,
                "hs_factor": HIGH_SEASON_FACTOR,
            },
            {
                "diseno": BQT_DISENO_VIRGEN,
                "color": "Blanco",
                "target": 110,
                "hs_factor": DECEMBER_HS_FACTOR,
                "seasonality": "Festividad Virgen · rotación dic ×1.4",
            },
            {
                "diseno": "Barquisimeto",
                "color": ADDITIONAL_COLOR,
                "pct_of_diseno": BQT_DISENO_CIUDAD,
                "hs_factor": HIGH_SEASON_FACTOR,
            },
        ],
    },
}
MESES_ORDER = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
STORE_MAP = {
    "la vela": "VELA",
    "vela": "VELA",
    "pedidos": "PEDIDOS",
    "web": "WEB",
    "taller": "TALLER",
}


def mes_sort_key(mes: str):
    part, year = mes.rsplit("-", 1)
    return (int(year), MESES_ORDER.index(part))


def norm_store(name: str) -> str:
    key = (name or "").strip().lower()
    return STORE_MAP.get(key, (name or "").strip().upper().replace(" ", "_"))


def norm_diseno(val: str, modelo: str) -> str:
    d = (val or "").strip()
    if not d and "MANGA LARGA" in modelo:
        return "Manga Larga"
    return d or "Sin diseño"


def stock_key(modelo, genero, color, diseno, talla) -> str:
    return f"{modelo}/{genero}/{color}/{diseno}/{talla}"


def load_ventas() -> list:
    rows = []
    with VENTAS_PATH.open(encoding="latin-1") as f:
        for r in csv.DictReader(f, delimiter=";"):
            mes = (r.get("fecha (mes año)") or "").strip()
            if not mes:
                continue
            qty = int(float(r.get("Cant. ordenada") or 0))
            if qty == 0:
                continue
            modelo = (r.get("modelo") or "").strip()
            rows.append({
                "tienda": norm_store(r.get("tienda / ubicación", "")),
                "genero": (r.get("GENERO") or "").strip(),
                "color": (r.get("COLOR") or "").strip(),
                "diseno": norm_diseno(r.get("DISEÑO"), modelo),
                "talla": (r.get("TALLA") or "").strip(),
                "mes": mes,
                "modelo": modelo,
                "sku": (r.get("SKU") or "").strip(),
                "v": qty,
            })
    return rows


def load_inventario() -> list:
    rows = []
    with INV_PATH.open(encoding="latin-1") as f:
        for r in csv.DictReader(f, delimiter=";"):
            qty = int(float(r.get("Cantidad en inventario") or 0))
            if qty <= 0:
                continue
            modelo = (r.get("MODELO") or "").strip()
            rows.append({
                "ubicacion": norm_store(r.get("Ubicación", "")),
                "modelo": modelo,
                "genero": (r.get("GENERO") or "").strip(),
                "color": (r.get("COLOR") or "").strip(),
                "diseno": norm_diseno(r.get("DISEÑO"), modelo),
                "talla": (r.get("TALLA") or "").strip(),
                "qty": qty,
                "sku": (r.get("SKU") or "").strip(),
            })
    return rows


def talla_factor(talla: str) -> float:
    return TALLA_BOOST.get((talla or "").upper(), 1.0)


def prod_needs(v_mes: float, stk: int = 0) -> dict:
    return {f"need_{m}m": max(0, round(v_mes * m - stk)) for m in PROD_MONTHS_OPTIONS}


def velocity_months(meses_order: list) -> list:
    if PARTIAL_MONTH in meses_order:
        i = meses_order.index(PARTIAL_MONTH)
        if i >= VELOCITY_MONTHS_COUNT:
            return meses_order[i - VELOCITY_MONTHS_COUNT : i]
    return meses_order[-VELOCITY_MONTHS_COUNT:]


def base_velocity(rows, modelo, genero, color, diseno, talla, vel_months):
    qty = sum(
        r["v"] for r in rows
        if r["modelo"] == modelo and r["genero"] == genero and r["color"] == color
        and r["diseno"] == diseno and r["talla"] == talla and r["mes"] in vel_months
    )
    return qty / len(vel_months) if vel_months else 0.0


def compute_prod_curve(raw_rows, stock, stock_taller, vel_months):
    store_rows = [r for r in raw_rows if r["tienda"] == BASE_STORE]
    prod_rows = []
    combos = sorted({
        (r["modelo"], r["genero"], r["color"], r["diseno"], r["talla"])
        for r in store_rows
    })
    for modelo, genero, color, diseno, talla in combos:
        base_v = base_velocity(store_rows, modelo, genero, color, diseno, talla, vel_months)
        base_v *= talla_factor(talla)
        v_mes_base = round(base_v, 1)
        v_mes = round(base_v * HIGH_SEASON_FACTOR, 1)
        key = stock_key(modelo, genero, color, diseno, talla)
        stk = int(stock.get(key, 0))
        stk_pt = int(stock_taller.get(key, 0))
        cob = round(stk / v_mes, 1) if v_mes > 0 else 999
        needs = prod_needs(v_mes, stk)
        prod_rows.append({
            "modelo": modelo,
            "genero": genero,
            "color": color,
            "diseno": diseno,
            "talla": talla,
            "v3m": sum(
                r["v"] for r in store_rows
                if r["modelo"] == modelo and r["genero"] == genero and r["color"] == color
                and r["diseno"] == diseno and r["talla"] == talla and r["mes"] in vel_months
            ),
            "v_mes_base": v_mes_base,
            "v_mes": v_mes,
            "stk_total": stk,
            "stk_pt": stk_pt,
            "cobertura": cob,
            **needs,
        })

    summary = {}
    for modelo in sorted({r["modelo"] for r in prod_rows}):
        rows_m = [r for r in prod_rows if r["modelo"] == modelo]
        v_mes = sum(r["v_mes"] for r in rows_m)
        stk = sum(r["stk_total"] for r in rows_m)
        summary[modelo] = {
            "v_mes_base": round(sum(r["v_mes_base"] for r in rows_m), 1),
            "v_mes": round(v_mes, 1),
            "stk_total": stk,
            "stk_pt": sum(r["stk_pt"] for r in rows_m),
            **{f"need_{m}m": sum(r[f"need_{m}m"] for r in rows_m) for m in PROD_MONTHS_OPTIONS},
        }
    return prod_rows, summary


def _vela_genero_talla_mix(store_rows, vel_months, modelo=MC_MODEL):
    """Mix para reparto: share género desde MC · curva talla/género como dashboard Tallas (todo SPOTS VELA)."""
    gen_qty = defaultdict(float)
    talla_by_gen = defaultdict(lambda: defaultdict(float))
    for r in store_rows:
        if r["mes"] not in vel_months:
            continue
        g, t = r["genero"], r["talla"]
        talla_by_gen[g][t] += r["v"]
        if r["modelo"] == modelo:
            gen_qty[g] += r["v"]
    gen_total = sum(gen_qty.values())
    if gen_total <= 0:
        return {("CAB", "M"): 0.5, ("DAMA", "M"): 0.5}
    mix = {}
    for g, gqty in gen_qty.items():
        g_share = gqty / gen_total
        tallas = talla_by_gen.get(g, {})
        t_total = sum(tallas.values()) or 1
        for t, v in tallas.items():
            mix[(g, t)] = g_share * (v / t_total) * talla_factor(t)
    btotal = sum(mix.values()) or 1
    return {k: v / btotal for k, v in mix.items()}


def _mc_blanco_mix(store_rows, vel_months, modelo=MC_MODEL):
    """Alias: mix alineado con análisis Tallas del dashboard (por género)."""
    return _vela_genero_talla_mix(store_rows, vel_months, modelo)


def _allocate_target(target_3m: int, mix: dict, modelo=MC_MODEL) -> list:
    """Reparte unidades enteras por género/talla (método mayor resto)."""
    if target_3m <= 0:
        return []
    keys = sorted(mix.keys())
    raw = {k: target_3m * mix[k] for k in keys}
    floors = {k: int(raw[k]) for k in keys}
    rem = target_3m - sum(floors.values())
    order = sorted(keys, key=lambda k: raw[k] - floors[k], reverse=True)
    for i in range(rem):
        floors[order[i % len(order)]] += 1
    return [
        (modelo, genero, talla, qty)
        for (genero, talla), qty in floors.items()
        if qty > 0
    ]


def _sku_from_alloc(modelo, genero, talla, diseno, color, need_3m, hs_factor, seasonality=""):
    v_mes = round(need_3m / LEAD_MONTHS, 2) if LEAD_MONTHS else need_3m
    needs = prod_needs(v_mes, 0)
    return {
        "modelo": modelo,
        "genero": genero,
        "diseno": diseno,
        "talla": talla,
        "color": color,
        "v_mes": v_mes,
        "hs_factor": hs_factor,
        "seasonality": seasonality,
        **needs,
    }


def _zone_design_targets(cap):
    """Objetivos 3m por diseño: blanco principal + adicional al 70%."""
    if cap.get("design_targets_3m"):
        specs = []
        resolved = {}
        for d in cap["design_targets_3m"]:
            if d.get("pct_of_diseno"):
                base = resolved.get(d["pct_of_diseno"], 0)
                target = round(base * ADDITIONAL_COLOR_FACTOR)
            else:
                target = d["target"]
            resolved[d["diseno"]] = target
            specs.append({**d, "target": target})
        return specs

    total = cap["target_total_3m"]
    blanco = round(total / (1 + ADDITIONAL_COLOR_FACTOR))
    adicional = total - blanco
    return [
        {
            "diseno": cap["blanco_diseno"],
            "color": "Blanco",
            "target": blanco,
            "hs_factor": HIGH_SEASON_FACTOR,
        },
        {
            "diseno": cap["adicional_diseno"],
            "color": ADDITIONAL_COLOR,
            "target": adicional,
            "hs_factor": HIGH_SEASON_FACTOR,
            "pct_of_diseno": cap["blanco_diseno"],
        },
    ]


def compute_expansion(raw_rows, vel_months, prod_rows):
    """Proyección calibrada 3m por zona · MC · Blanco principal + color adicional 70%.

  Caracas: ~475 und (4 tiendas ponderadas: 2 alto · 1 media · 1 bajo).
  Valencia: ~375 und · Barquisimeto: ~450 (Ciudad 200 + Virgen 110 + adicional 70% Ciudad).
  Reparto talla/género según mix VELA MC Blanco.
    """
    store_rows = [r for r in raw_rows if r["tienda"] == BASE_STORE]
    mix = _mc_blanco_mix(store_rows, vel_months)
    expansion = {
        "base_store": BASE_STORE,
        "stores": EXPANSION_STORES,
        "additional_color": ADDITIONAL_COLOR,
        "additional_color_factor": ADDITIONAL_COLOR_FACTOR,
        "high_season_factor": HIGH_SEASON_FACTOR,
        "december_hs_factor": DECEMBER_HS_FACTOR,
        "velocity_months_count": VELOCITY_MONTHS_COUNT,
        "lead_months": LEAD_MONTHS,
        "prod_months_options": PROD_MONTHS_OPTIONS,
        "default_prod_months": DEFAULT_PROD_MONTHS,
        "talla_boost": TALLA_BOOST,
        "vela_exclusive_note": (
            "Diseños VELA (Nueva Esparta, Virgen del Valle, Manga Larga, etc.) "
            "son exclusivos de la zona Margarita"
        ),
        "by_store": [],
        "by_color": [],
        "total_blanco": 0,
        "total_adicional": 0,
        "total_expansion": 0,
    }

    for store in EXPANSION_STORES:
        cap = EXPANSION_CAPS[store]
        tiendas = cap.get("tiendas", 1)
        weights = cap.get("tienda_weights")
        effective_tiendas = round(sum(weights), 2) if weights else tiendas
        design_specs = _zone_design_targets(cap)
        store_blanco = 0
        store_adicional = 0
        skus = []
        designs_meta = []

        for dspec in design_specs:
            target = dspec["target"]
            alloc = _allocate_target(target, mix)
            design_total = 0
            for modelo, genero, talla, need_3m in alloc:
                sku = _sku_from_alloc(
                    modelo, genero, talla,
                    dspec["diseno"], dspec["color"], need_3m,
                    dspec.get("hs_factor", HIGH_SEASON_FACTOR),
                    dspec.get("seasonality", ""),
                )
                skus.append(sku)
                design_total += need_3m
            if dspec["color"] == "Blanco":
                store_blanco += design_total
            else:
                store_adicional += design_total
            designs_meta.append({
                "diseno": dspec["diseno"],
                "color": dspec["color"],
                "target_3m": design_total,
            })

        store_total = store_blanco + store_adicional
        expansion["by_store"].append({
            "store": store,
            "label": cap.get("label", ""),
            "tiendas": tiendas,
            "tienda_weights": weights,
            "effective_tiendas": effective_tiendas,
            "target_total_3m": cap.get("target_total_3m", store_total),
            "blanco": store_blanco,
            "adicional": store_adicional,
            "total": store_total,
            "skus": skus,
            "designs": designs_meta,
        })
        expansion["total_blanco"] += store_blanco
        expansion["total_adicional"] += store_adicional

    expansion["total_expansion"] = expansion["total_blanco"] + expansion["total_adicional"]
    expansion["by_color"] = [
        {"color": "Blanco", "need_3m": expansion["total_blanco"]},
        {
            "color": ADDITIONAL_COLOR,
            "need_3m": expansion["total_adicional"],
            "note": f"{int(ADDITIONAL_COLOR_FACTOR * 100)}% del blanco principal",
        },
    ]
    vel_lbl = ", ".join(velocity_months_label(vel_months))
    expansion["nota"] = (
        f"Proyección calibrada {LEAD_MONTHS}m · mix talla/género VELA ({vel_lbl}): "
        f"share género MC · curva talla por género como dashboard Tallas (todo SPOTS). "
        f"Blanco principal + {ADDITIONAL_COLOR} al {int(ADDITIONAL_COLOR_FACTOR * 100)}%. "
        f"Caracas ~475 · Valencia ~375 · Barquisimeto ~450. Solo Manga Corta."
    )
    return expansion


def build_prod_zones(prod_curve, summary_prod, expansion):
    """Curva de producción segmentada: Margarita → Caracas → Valencia → Barquisimeto."""
    zones = []
    margarita_rows = list(prod_curve)
    zones.append({
        "zone": "MARGARITA",
        "label": "Margarita (VELA)",
        "is_expansion": False,
        "zone_model": None,
        "note": "Diseños exclusivos zona · stock y cobertura reales",
        "summary": {
            "v_mes": round(sum(r["v_mes"] for r in margarita_rows), 1),
            "stk_total": sum(r["stk_total"] for r in margarita_rows),
            "stk_pt": sum(r["stk_pt"] for r in margarita_rows),
            **{f"need_{m}m": sum(r[f"need_{m}m"] for r in margarita_rows) for m in PROD_MONTHS_OPTIONS},
        },
        "by_modelo": {},
    })
    for mod in sorted({r["modelo"] for r in margarita_rows}):
        rows_m = [r for r in margarita_rows if r["modelo"] == mod]
        zones[-1]["by_modelo"][mod] = {
            "summary": summary_prod.get(mod, {}),
            "rows": rows_m,
        }

    store_map = {s["store"]: s for s in expansion.get("by_store", [])}
    for store in [z for z in PROD_ZONE_ORDER if z != "MARGARITA"]:
        es = store_map.get(store)
        if not es:
            continue
        rows = []
        for sku in es["skus"]:
            v = sku["v_mes"]
            hs = sku.get("hs_factor", HIGH_SEASON_FACTOR) or HIGH_SEASON_FACTOR
            rows.append({
                "modelo": sku["modelo"],
                "genero": sku["genero"],
                "color": sku["color"],
                "diseno": sku.get("diseno") or sku["color"],
                "talla": sku["talla"],
                "v_mes": v,
                "v_mes_base": round(v / hs, 2) if hs else v,
                "hs_factor": hs,
                "seasonality": sku.get("seasonality", ""),
                "stk_total": 0,
                "stk_pt": 0,
                "cobertura": 0,
                **{f"need_{m}m": sku.get(f"need_{m}m", max(0, round(v * m))) for m in PROD_MONTHS_OPTIONS},
            })
        zones.append({
            "zone": store,
            "label": store.title(),
            "is_expansion": True,
            "tiendas": es.get("tiendas", 1),
            "effective_tiendas": es.get("effective_tiendas"),
            "note": es["label"],
            "summary": {
                "v_mes": round(sum(r["v_mes"] for r in rows), 1),
                "stk_total": 0,
                "stk_pt": 0,
                **{f"need_{m}m": sum(r[f"need_{m}m"] for r in rows) for m in PROD_MONTHS_OPTIONS},
                "blanco": es["blanco"],
                "adicional": es["adicional"],
            },
            "by_modelo": {},
        })
        for mod in sorted({r["modelo"] for r in rows}):
            rows_m = [r for r in rows if r["modelo"] == mod]
            zones[-1]["by_modelo"][mod] = {
                "summary": {
                    "v_mes": round(sum(r["v_mes"] for r in rows_m), 1),
                    **{f"need_{m}m": sum(r[f"need_{m}m"] for r in rows_m) for m in PROD_MONTHS_OPTIONS},
                },
                "rows": rows_m,
            }
    return zones


def velocity_months_label(vel_months):
    short = {
        "enero": "Jun", "febrero": "Feb", "marzo": "Mar", "abril": "Abr",
        "mayo": "May", "junio": "Jun", "julio": "Jul", "agosto": "Ago",
        "septiembre": "Sep", "octubre": "Oct", "noviembre": "Nov", "diciembre": "Dic",
    }
    return [f"{short.get(m.split('-')[0], m[:3])} {m[-2:]}" for m in vel_months]


def rebuild_data() -> dict:
    raw_rows = load_ventas()
    inv_rows = load_inventario()

    meses_order = sorted({r["mes"] for r in raw_rows}, key=mes_sort_key)
    meses_und = defaultdict(int)
    for r in raw_rows:
        meses_und[r["mes"]] += r["v"]

    stock = defaultdict(int)
    stock_by_loc = defaultdict(lambda: defaultdict(int))
    stock_taller = defaultdict(int)
    for r in inv_rows:
        key = stock_key(r["modelo"], r["genero"], r["color"], r["diseno"], r["talla"])
        stock[key] += r["qty"]
        stock_by_loc[r["ubicacion"]][key] += r["qty"]
        if r["ubicacion"] == "TALLER":
            stock_taller[key] += r["qty"]

    vel_months = velocity_months(meses_order)
    prod_curve, summary_prod = compute_prod_curve(raw_rows, stock, stock_taller, vel_months)
    expansion = compute_expansion(raw_rows, vel_months, prod_curve)
    prod_zones = build_prod_zones(prod_curve, summary_prod, expansion)

    tiendas = sorted({r["tienda"] for r in raw_rows})
    real_stores = sorted({r["tienda"] for r in raw_rows if r["tienda"] not in {"PEDIDOS", "WEB", "TALLER"}})
    stock_by_modelo = defaultdict(int)
    for r in inv_rows:
        stock_by_modelo[r["modelo"]] += r["qty"]

    first_m = meses_order[0].split("-")[0].capitalize() if meses_order else ""
    last_m = meses_order[-1].split("-")[0].capitalize() if meses_order else ""
    date_range = f"{first_m} 2026 — {last_m} 2026"

    return {
        "nombre": "SPOTS",
        "periodo": date_range,
        "raw_rows": raw_rows,
        "inv_rows": inv_rows,
        "stock": dict(stock),
        "stock_by_loc": {k: dict(v) for k, v in stock_by_loc.items()},
        "stock_by_modelo": dict(stock_by_modelo),
        "meses_order": meses_order,
        "meses_und": dict(meses_und),
        "filtros": {
            "tiendas": tiendas,
            "generos": sorted({r["genero"] for r in raw_rows}),
            "colores": sorted({r["color"] for r in raw_rows}),
            "disenos": sorted({r["diseno"] for r in raw_rows}),
            "modelos": sorted({r["modelo"] for r in raw_rows}),
        },
        "es_parcial": PARTIAL_MONTH in meses_order,
        "partial_month": PARTIAL_MONTH,
        "stock_total": sum(stock.values()),
        "stock_pt_total": sum(stock_taller.values()),
        "total": sum(r["v"] for r in raw_rows),
        "all_stores": real_stores,
        "decision_stores": DECISION_STORES,
        "inv_locations": sorted(stock_by_loc.keys()),
        "prod_curve": prod_curve,
        "summary_prod": summary_prod,
        "high_season_factor": HIGH_SEASON_FACTOR,
        "december_hs_factor": DECEMBER_HS_FACTOR,
        "velocity_months_count": VELOCITY_MONTHS_COUNT,
        "lead_months": LEAD_MONTHS,
        "prod_months_options": PROD_MONTHS_OPTIONS,
        "default_prod_months": DEFAULT_PROD_MONTHS,
        "talla_boost": TALLA_BOOST,
        "velocity_months": vel_months,
        "velocity_months_label": " · ".join(velocity_months_label(vel_months)),
        "expansion": expansion,
        "prod_zones": prod_zones,
        "prod_zone_order": PROD_ZONE_ORDER,
        "expansion_stores": EXPANSION_STORES,
        "expansion_caps": EXPANSION_CAPS,
        "additional_color": ADDITIONAL_COLOR,
        "additional_color_factor": ADDITIONAL_COLOR_FACTOR,
        "date_range": date_range,
    }


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


def patch_html(html: str, data: dict) -> str:
    dr = data["date_range"]
    html = html.replace(
        "<p>Dashboard de Ventas · Junio 2026 — Julio 2026 · Manga Corta &amp; Manga Larga</p>",
        f"<p>Dashboard de Ventas · {dr} · Manga Corta &amp; Manga Larga · foco tienda {BASE_STORE}</p>",
    )
    html = html.replace(
        '<div class="footer">Colección Spots · Dashboard de Ventas · Junio 2026 — Julio 2026</div>',
        f'<div class="footer">Colección Spots · Dashboard de Ventas · {dr}</div>',
    )

    # Diseño filter in fbar
    if 'id="fD"' not in html:
        html = html.replace(
            '<div class="fg"><label>Color</label><select id="fC" onchange="af()"><option value="">Todos</option></select></div>',
            '<div class="fg"><label>Color</label><select id="fC" onchange="af()"><option value="">Todos</option></select></div>\n'
            '  <div class="fg"><label>Diseño</label><select id="fD" onchange="af()"><option value="">Todos</option></select></div>',
        )

    # Replace NEW_STORES config
    html = re.sub(
        r"var NEW_STORES=\['MARGARITA','TOLON'\];",
        "var NEW_STORES=DATA.expansion_stores||['VALENCIA','BARQUISIMETO','CARACAS'];",
        html,
    )
    html = re.sub(
        r"var NEW_STORE_CAPS=\{[^;]+\};",
        "var NEW_STORE_CAPS=DATA.expansion_caps||{};",
        html,
        count=2,
    )

    # gf() add diseno
    html = html.replace(
        "function gf(){return{tienda:document.getElementById('fT').value,genero:document.getElementById('fG').value,color:document.getElementById('fC').value};}",
        "function gf(){return{tienda:document.getElementById('fT').value,genero:document.getElementById('fG').value,color:document.getElementById('fC').value,diseno:(document.getElementById('fD')||{}).value||''};}",
    )

    # fr() add diseno filter
    html = html.replace(
        "(!f.color||r.color===f.color)&&mA.indexOf(r.mes)>=0;",
        "(!f.color||r.color===f.color)&&(!f.diseno||r.diseno===f.diseno)&&mA.indexOf(r.mes)>=0;",
    )

    # af() badge
    html = html.replace(
        "var active=f.tienda||f.genero||f.color||_per!=='all'||_modelo;",
        "var active=f.tienda||f.genero||f.color||f.diseno||_per!=='all'||_modelo;",
    )

    # rf() reset diseno
    html = html.replace(
        "document.getElementById('fC').value='';_modelo='';",
        "document.getElementById('fC').value='';if(document.getElementById('fD'))document.getElementById('fD').value='';_modelo='';",
    )

    # getFilteredInvRows diseno
    html = html.replace(
        "(!f.color||r.color===f.color);",
        "(!f.color||r.color===f.color)&&(!f.diseno||r.diseno===f.diseno);",
    )

    # tallasScope diseno (both occurrences)
    diseno_guard = (
        "if(f.color&&r.color!==f.color)return;\n"
        "    if(f.diseno&&r.diseno!==f.diseno)return;"
    )
    html = html.replace("if(f.color&&r.color!==f.color)return;", diseno_guard, 2)

    # salesTallaMap diseno - use diseno in key
    html = html.replace(
        "var k=r.genero+'|'+r.color+'|'+r.talla;",
        "var k=r.genero+'|'+r.color+'|'+(r.diseno||'')+'|'+r.talla;",
    )

    # inv matrix row key includes diseno
    html = html.replace(
        "var rowKey=r.genero+' · '+r.color;",
        "var rowKey=r.genero+' · '+r.color+' · '+(r.diseno||'');",
    )
    html = html.replace(
        "if(!byLoc[r.ubicacion].rows[rowKey])byLoc[r.ubicacion].rows[rowKey]={genero:r.genero,color:r.color,tallas:{}};",
        "if(!byLoc[r.ubicacion].rows[rowKey])byLoc[r.ubicacion].rows[rowKey]={genero:r.genero,color:r.color,diseno:r.diseno,tallas:{}};",
    )
    html = html.replace(
        "var sv=salesMap[rd.genero+'|'+rd.color+'|'+t]||0;",
        "var sv=salesMap[rd.genero+'|'+rd.color+'|'+(rd.diseno||'')+'|'+t]||0;",
    )

    # getLF with HS factor
    html = html.replace(
        "function getLF(genero,meses,modelo){\n"
        "  var mO=DATA.meses_order.slice(-meses);\n"
        "  var r=DATA.raw_rows.filter(function(r){return r.genero===genero&&r.modelo===modelo&&mO.indexOf(r.mes)>=0;});\n"
        "  return Math.round(r.reduce(function(a,x){return a+x.v;},0)/meses);\n"
        "}",
        "function getLF(genero,meses,modelo){\n"
        "  var mO=DATA.meses_order.slice(-meses);\n"
        "  var hs=DATA.high_season_factor||1.2;\n"
        "  var r=DATA.raw_rows.filter(function(r){return r.tienda==='VELA'&&r.genero===genero&&r.modelo===modelo&&mO.indexOf(r.mes)>=0;});\n"
        "  return Math.round(r.reduce(function(a,x){return a+x.v;},0)/meses*hs);\n"
        "}",
    )

    # getNewStoreShare for expansion caps
    html = html.replace(
        "function getNewStoreShare(store,realShares){\n"
        "  var cap=NEW_STORE_CAPS[store];if(!cap)return 0;\n"
        "  return(realShares[cap.base]||0)*cap.mult;\n"
        "}",
        "function getNewStoreShare(store,realShares){\n"
        "  var cap=NEW_STORE_CAPS[store];if(!cap)return 0;\n"
        "  if(cap.effective_tiendas!=null)return(realShares['VELA']||0)*cap.effective_tiendas;\n"
        "  if(cap.tienda_weights)return(realShares['VELA']||0)*cap.tienda_weights.reduce(function(a,w){return a+w;},0);\n"
        "  if(cap.tiendas!=null)return(realShares['VELA']||0)*cap.tiendas;\n"
        "  if(cap.mult!=null)return(realShares['VELA']||0)*cap.mult;\n"
        "  return(realShares[cap.base]||0)*(cap.mult||1);\n"
        "}",
    )

    # Init diseno filter options from DATA
    html = html.replace(
        "DATA.filtros.generos.forEach(function(g){document.getElementById('fG').innerHTML+='<option value=\"'+g+'\">'+g+'</option>';});",
        "DATA.filtros.generos.forEach(function(g){document.getElementById('fG').innerHTML+='<option value=\"'+g+'\">'+g+'</option>';});\n"
        "(DATA.filtros.disenos||[]).forEach(function(d){var el=document.getElementById('fD');if(el)el.innerHTML+='<option value=\"'+d+'\">'+d+'</option>';});",
    )

    html = html.replace(
        "updateColorFilter();filterModelButtons();",
        "updateColorFilter();updateDisenoFilter();filterModelButtons();",
    )

    if "function updateDisenoFilter" not in html:
        html = html.replace(
            "function updateColorFilter(){",
            "function updateDisenoFilter(){var sel=document.getElementById('fD');if(!sel)return;var cur=sel.value;sel.innerHTML='<option value=\"\">Todos</option>';var rows=DATA.raw_rows.filter(function(r){return(!_modelo||r.modelo===_modelo);});var ds={};rows.forEach(function(r){ds[r.diseno]=1;});Object.keys(ds).sort().forEach(function(d){sel.innerHTML+='<option value=\"'+d+'\">'+d+'</option>';});if(cur&&ds[cur])sel.value=cur;}\n"
            "function updateColorFilter(){",
        )
        html = html.replace(
            "function updateColorFilter(){var sel=document.getElementById('fC'),cur=sel.value;",
            "function updateColorFilter(){updateDisenoFilter();var sel=document.getElementById('fC'),cur=sel.value;",
        )

    # Decisiones sub text
    html = html.replace(
        '<div class="sub">Reabastecimiento por tienda (VELA, WEB, PEDIDOS) según ventas del período</div>',
        '<div class="sub">Foco tienda <strong style="color:var(--tx)">VELA Margarita</strong> · expansión <strong style="color:#f97316">Caracas</strong>, <strong style="color:#f97316">Valencia</strong> y <strong style="color:#f97316">Barquisimeto</strong> · temp. alta ×<span id="hsFactorLabel">1.2</span></div>',
    )

    # export CSV with diseno
    html = html.replace(
        "var lines=['Tienda,Modelo,Género,Color,Talla,Mes,Unidades'];rows.forEach(function(r){lines.push([r.tienda,r.modelo,r.genero,r.color,r.talla,r.mes,r.v].join(','));});",
        "var lines=['Tienda,Modelo,Género,Color,Diseño,Talla,Mes,Unidades'];rows.forEach(function(r){lines.push([r.tienda,r.modelo,r.genero,r.color,r.diseno||'',r.talla,r.mes,r.v].join(','));});",
    )

    # Meses proyección: 3 / 4 / 6 (default 3)
    html = html.replace(
        '<button onclick="setDecMeses(1)" id="dm1" style="background:var(--s2);color:var(--mu);border:1px solid var(--brd);border-radius:20px;padding:4px 12px;font-size:0.73rem;cursor:pointer;font-family:var(--fb)">1 mes</button>\n'
        '      <button onclick="setDecMeses(2)" id="dm2" style="background:var(--ac);color:#fff;border:1px solid var(--ac);border-radius:20px;padding:4px 12px;font-size:0.73rem;cursor:pointer;font-family:var(--fb)">2 meses</button>\n'
        '      <button onclick="setDecMeses(3)" id="dm3" style="background:var(--s2);color:var(--mu);border:1px solid var(--brd);border-radius:20px;padding:4px 12px;font-size:0.73rem;cursor:pointer;font-family:var(--fb)">3 meses</button>',
        '<button onclick="setDecMeses(3)" id="dm3" style="background:var(--ac);color:#fff;border:1px solid var(--ac);border-radius:20px;padding:4px 12px;font-size:0.73rem;cursor:pointer;font-family:var(--fb)">Producir 3 meses</button>\n'
        '      <button onclick="setDecMeses(4)" id="dm4" style="background:var(--s2);color:var(--mu);border:1px solid var(--brd);border-radius:20px;padding:4px 12px;font-size:0.73rem;cursor:pointer;font-family:var(--fb)">Producir 4 meses</button>\n'
        '      <button onclick="setDecMeses(6)" id="dm6" style="background:var(--s2);color:var(--mu);border:1px solid var(--brd);border-radius:20px;padding:4px 12px;font-size:0.73rem;cursor:pointer;font-family:var(--fb)">Producir 6 meses</button>',
    )
    html = html.replace("var _decMeses=2;", "var _decMeses=DATA.default_prod_months||3;")
    html = html.replace(
        "function setDecMeses(n){\n"
        "  _decMeses=n;\n"
        "  ['dm1','dm2','dm3'].forEach(function(id,i){\n"
        "    var b=document.getElementById(id);if(!b)return;\n"
        "    var a=(i+1)===n;b.style.background=a?'var(--ac)':'var(--s2)';b.style.color=a?'#fff':'var(--mu)';b.style.borderColor=a?'var(--ac)':'var(--brd)';\n"
        "  });\n"
        "  rDecisiones();\n"
        "}",
        "function setDecMeses(n){\n"
        "  _decMeses=n;\n"
        "  (DATA.prod_months_options||[3,4,6]).forEach(function(m){\n"
        "    var b=document.getElementById('dm'+m);if(!b)return;\n"
        "    var a=m===n;b.style.background=a?'var(--ac)':'var(--s2)';b.style.color=a?'#fff':'var(--mu)';b.style.borderColor=a?'var(--ac)':'var(--brd)';\n"
        "  });\n"
        "  rDecisiones();\n"
        "}\n"
        "function needM(r,meses){\n"
        "  var k='need_'+meses+'m';\n"
        "  if(r[k]!=null)return r[k];\n"
        "  return Math.max(0,Math.round((r.v_mes||0)*meses-(r.stk_total||0)));\n"
        "}",
    )
    html = html.replace("var meses=_decMeses||2;", "var meses=_decMeses||(DATA.default_prod_months||3);")

    # Decisiones: methodology + expansion + diseno grouping
    dec_methodology_js = (
        "function rDecisiones(){\n  var meses=_decMeses||(DATA.default_prod_months||3);\n"
        "  var hs=DATA.high_season_factor||1.2;\n"
        "  var hsLbl=document.getElementById('hsFactorLabel');if(hsLbl)hsLbl.textContent=hs;\n"
        "  var decHdr=document.getElementById('decMethodology');\n"
        "  if(decHdr){\n"
        "    var velLbl=DATA.velocity_months_label||'';\n"
        "    var velCnt=DATA.velocity_months_count||3;\n"
        "    var dicHs=DATA.december_hs_factor||1.4;\n"
        "    var addPct=Math.round((DATA.additional_color_factor||0.7)*100);\n"
        "    var exp=DATA.expansion||{};\n"
        "    var zoneCards=(exp.by_store||[]).map(function(z){\n"
        "      var dsg=(z.designs||[]).map(function(d){return d.diseno+' <span style=\"color:var(--mu2)\">('+d.color+': '+d.target_3m+'und)</span>';}).join(' · ');\n"
        "      var tw=z.tienda_weights?(' · pesos '+z.tienda_weights.join('/')+''):'';\n"
        "      return '<div style=\"background:rgba(0,0,0,.12);border-radius:8px;padding:8px 10px\">'\n"
        "        +'<strong style=\"color:#f97316\">'+z.store+'</strong> · <strong style=\"color:var(--tx)\">'+z.tiendas+'</strong> tienda(s)'+tw+' · objetivo <strong style=\"color:var(--tx)\">'+z.total+'</strong> und'\n"
        "        +'<div style=\"font-size:.64rem;margin-top:4px;color:var(--mu2)\">'+dsg+'</div>'\n"
        "        +'<div style=\"font-size:.64rem;margin-top:4px\">Blanco <strong>'+z.blanco+'</strong> + '+((DATA.additional_color)||'adicional')+' <strong>'+z.adicional+'</strong> ('+addPct+'% blanco principal)</div></div>';\n"
        "    }).join('');\n"
        "    decHdr.innerHTML='<div style=\"background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.22);border-radius:12px;padding:14px 16px;font-size:.71rem;color:var(--mu);line-height:1.55;margin-bottom:14px\">'\n"
        "      +'<div style=\"font-family:var(--fh);font-weight:800;color:var(--a2);margin-bottom:10px;font-size:.78rem\">📋 Metodología — rotación y producción</div>'\n"
        "      +'<div style=\"display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px 16px\">'\n"
        "      +'<div><strong style=\"color:var(--tx)\">Foco tienda VELA</strong><br>Base '+velCnt+' meses cerrados ('+velLbl+'). Share género desde <strong style=\"color:var(--tx)\">MC</strong>.</div>'\n"
        "      +'<div><strong style=\"color:var(--tx)\">Curva de tallas</strong><br>Share género desde <strong style=\"color:var(--tx)\">MC</strong> · proporción talla por género como pestaña <strong style=\"color:var(--tx)\">Tallas</strong> (todo SPOTS VELA). XL/2XL con boost.</div>'\n"
        "      +'<div><strong style=\"color:var(--tx)\">Caracas — 4 tiendas CCS</strong><br>2 alto peso · 1 media · 1 bajo movimiento. Objetivo ~<strong style=\"color:var(--tx)\">450-500</strong> und/3m.</div>'\n"
        "      +'<div><strong style=\"color:var(--tx)\">Valencia · Barquisimeto</strong><br>Valencia ~<strong style=\"color:var(--tx)\">350-400</strong> und. BQT: Ciudad ~180 + Virgen 100-120 (dic ×'+dicHs+') + adicional 70% Ciudad · total ~450.</div>'\n"
        "      +'</div></div>'\n"
        "      +'<div style=\"background:rgba(249,115,22,.08);border:1px solid rgba(249,115,22,.28);border-radius:12px;padding:14px 16px;margin-bottom:14px\">'\n"
        "      +'<div style=\"font-family:var(--fh);font-weight:800;color:#f97316;margin-bottom:8px;font-size:.78rem\">🚀 Proyección expansión — 3 meses (Caracas · Valencia · Barquisimeto)</div>'\n"
        "      +'<div style=\"display:flex;gap:16px;flex-wrap:wrap;margin-bottom:10px\">'\n"
        "      +'<div><span style=\"font-family:var(--fm);font-size:1.2rem;font-weight:800;color:var(--tx)\">'+(exp.total_expansion||0)+'</span> <span style=\"font-size:.65rem;color:var(--mu)\">und total</span></div>'\n"
        "      +'<div><span style=\"font-family:var(--fm);font-size:1rem;font-weight:700;color:#e4e4e7\">'+(exp.total_blanco||0)+'</span> <span style=\"font-size:.65rem;color:var(--mu)\">Blanco</span></div>'\n"
        "      +'<div><span style=\"font-family:var(--fm);font-size:1rem;font-weight:700;color:#a5b4fc\">'+(exp.total_adicional||0)+'</span> <span style=\"font-size:.65rem;color:var(--mu)\">'+((DATA.additional_color)||'Color adicional')+'</span></div>'\n"
        "      +'</div>'\n"
        "      +'<div style=\"display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px;margin-bottom:10px\">'+zoneCards+'</div>'\n"
        "      +'<div style=\"font-size:.65rem;color:var(--mu2)\">'+(exp.nota||'')+'</div></div>';\n"
        "  }\n"
    )
    html = re.sub(
        r"function rDecisiones\(\)\{\s*var meses=_decMeses\|\|2;.*?(?=\n  var TORD=)",
        dec_methodology_js,
        html,
        count=1,
        flags=re.DOTALL,
    )

    prod_curve_js = r"""  // ── CURVA DE PRODUCCIÓN POR ZONA
  var prodGrid=document.getElementById('propGrid');
  if(prodGrid){
    var zones=DATA.prod_zones||[];
    var prodOpts=DATA.prod_months_options||[3,4,6];
    prodGrid.innerHTML='';
    prodGrid.style.display='flex';
    prodGrid.style.flexDirection='column';
    prodGrid.style.gap='14px';
    zones.forEach(function(zn){
      if(_modelo){
        var hasMod=zn.by_modelo&&zn.by_modelo[_modelo];
        if(!hasMod)return;
      }
      var sm=zn.summary||{};
      var totalNeed=needM(sm,meses);
      var cob=(!zn.is_expansion&&sm.v_mes>0)?(sm.stk_total/sm.v_mes).toFixed(1):null;
      var cobColor=cob?(cob<1?'#ef4444':cob<2?'#f59e0b':cob<3?'#3b82f6':'#10b981'):'#f97316';
      var zoneBorder=zn.is_expansion?'rgba(249,115,22,.35)':'var(--brd)';
      var zoneBg=zn.is_expansion?'rgba(249,115,22,.04)':'var(--surf)';
      var modelos=Object.keys(zn.by_modelo||{}).sort();
      if(_modelo)modelos=modelos.filter(function(m){return m===_modelo;});
      var modelosHtml='';
      modelos.forEach(function(mod){
        var mdata=zn.by_modelo[mod];
        var mrows=mdata.rows||[];
        var byGroup={};
        mrows.forEach(function(r){
          var gk=zn.is_expansion?(r.diseno||r.color)+' · '+r.color:(r.diseno||r.color);
          if(!byGroup[gk])byGroup[gk]={rows:[],totalStk:0,totalNeed:0,v_mes:0,seasonality:''};
          byGroup[gk].rows.push(r);
          byGroup[gk].totalStk+=r.stk_total||0;
          byGroup[gk].totalNeed+=needM(r,meses);
          byGroup[gk].v_mes+=r.v_mes||0;
          if(r.seasonality)byGroup[gk].seasonality=r.seasonality;
        });
        var gKeys=Object.keys(byGroup).sort(function(a,b){return byGroup[b].v_mes-byGroup[a].v_mes;});
        var groupsHtml=gKeys.map(function(gk){
          var gd=byGroup[gk];
          var gNeed=gd.totalNeed;
          var uid='pg_'+zn.zone+'_'+mod.replace(/\W/g,'_')+'_'+gk.replace(/\W/g,'_');
          var col=gk==='Blanco'?'#e4e4e7':(gk.toLowerCase().indexOf('adicional')>=0?'#a5b4fc':cn(gk));
          var seasonNote=gd.seasonality?('<span style="font-size:.6rem;color:#f59e0b;margin-left:6px">'+gd.seasonality+'</span>'):'';
          var sortedRows=gd.rows.slice().sort(function(a,b){return(TORD[a.talla]||99)-(TORD[b.talla]||99);});
          var tallasHtml=sortedRows.map(function(r){
            var tn=needM(r,meses);
            var tc=r.cobertura<1?'#ef4444':r.cobertura<2?'#f59e0b':r.cobertura<3?'#3b82f6':'#10b981';
            if(zn.is_expansion)tc='#f97316';
            return '<div style="display:flex;align-items:center;gap:6px;padding:3px 8px 3px 12px;background:rgba(0,0,0,.15);border-radius:5px;margin-bottom:2px">'
              +'<span style="font-family:var(--fm);font-size:.68rem;color:var(--mu);width:28px">'+r.talla+'</span>'
              +'<span style="font-family:var(--fm);font-size:.65rem;color:var(--mu2)">'+(GICO[r.genero]||'')+' '+r.genero+'</span>'
              +'<span style="font-family:var(--fm);font-size:.65rem;color:var(--mu2)">'+r.v_mes.toFixed(1)+'/mes</span>'
              +(zn.is_expansion?'':('<span style="font-family:var(--fm);font-size:.65rem;color:var(--mu2)">stk '+r.stk_total+'</span>'
                +'<span style="font-family:var(--fm);font-size:.65rem;color:'+tc+';font-weight:700">'+r.cobertura.toFixed(1)+'m</span>'))
              +(tn>0?'<span style="margin-left:auto;background:rgba(245,158,11,.15);color:#f59e0b;border-radius:4px;padding:1px 7px;font-size:.63rem;font-weight:700">+'+tn+' prod</span>':'<span style="margin-left:auto;font-size:.63rem;color:#10b981">✓ OK</span>')
              +'</div>';
          }).join('');
          return '<div style="margin-bottom:6px">'
            +'<div data-pguid="'+uid+'" style="display:flex;align-items:center;gap:8px;cursor:pointer;padding:6px 8px;border-radius:6px;background:rgba(0,0,0,.15)">'
            +'<span style="width:9px;height:9px;border-radius:50%;background:'+col+';flex-shrink:0"></span>'
            +'<span style="font-size:.73rem;font-weight:700;color:var(--tx)">'+gk+'</span>'+seasonNote
            +'<span style="font-family:var(--fm);font-size:.64rem;color:var(--mu2)">'+gd.v_mes.toFixed(1)+'/mes</span>'
            +(zn.is_expansion?'':'<span style="font-family:var(--fm);font-size:.64rem;color:var(--mu2)">stk '+gd.totalStk+'</span>')
            +(gNeed>0?'<span style="background:rgba(245,158,11,.18);color:#f59e0b;border-radius:5px;padding:2px 8px;font-size:.66rem;font-weight:700;margin-left:auto">+'+gNeed+'</span>':'')
            +'<span style="color:var(--ac);font-size:.62rem;margin-left:4px">&#9658;</span></div>'
            +'<div id="'+uid+'" style="display:none;margin:4px 0 0 14px;padding:6px 8px;background:var(--s2);border-radius:6px;border-left:2px solid '+col+'44">'+tallasHtml+'</div></div>';
        }).join('');
        modelosHtml+='<div style="margin-bottom:10px">'
          +'<div style="font-family:var(--fh);font-size:.8rem;font-weight:800;color:var(--a2);margin-bottom:8px">'+(MICO[mod]||'')+' '+mod+'</div>'
          +groupsHtml+'</div>';
      });
      var prodBoxes=prodOpts.map(function(m,i){
        var cols=['rgba(99,102,241,.1)','rgba(245,158,11,.1)','rgba(244,63,94,.1)'];
        var tcols=['#818cf8','#f59e0b','#f43f5e'];
        var val=needM(sm,m);
        var active=m===meses?'2px solid var(--ac)':'1px solid transparent';
        return '<div style="text-align:center;background:'+cols[i%3]+';border-radius:8px;padding:8px;border:'+active+'">'
          +'<div style="font-family:var(--fm);font-size:1.1rem;font-weight:800;color:'+tcols[i%3]+'">'+val+'</div>'
          +'<div style="font-size:.63rem;color:var(--mu)">Producir '+m+' meses</div></div>';
      }).join('');
      var card=document.createElement('div');
      card.style.cssText='background:'+zoneBg+';border:1px solid '+zoneBorder+';border-radius:12px;padding:14px';
      card.innerHTML='<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">'
        +'<h3 style="margin:0;font-family:var(--fh);font-size:.92rem">'+(zn.is_expansion?'🆕 ':'🏝️ ')+zn.label+'</h3>'
        +(zn.tiendas?'<span style="font-size:.68rem;color:var(--mu2)">'+zn.tiendas+' tienda(s)</span>':'')
        +(zn.is_expansion?'<span style="background:rgba(249,115,22,.15);color:#f97316;border-radius:4px;padding:2px 8px;font-size:.62rem;font-weight:700">Expansión</span>':'')
        +'<span style="margin-left:auto;font-family:var(--fm);font-size:.78rem;font-weight:800;color:'+cobColor+'">'+(cob?cob+' meses cob':'Proyección '+totalNeed+' und')+'</span>'
        +'</div>'
        +(zn.note?'<div style="font-size:.65rem;color:var(--mu2);margin-bottom:10px">'+zn.note+'</div>':'')
        +'<div style="display:grid;grid-template-columns:repeat('+prodOpts.length+',1fr);gap:8px;margin-bottom:12px">'+prodBoxes+'</div>'
        +(zn.is_expansion?'':'<div style="font-size:.67rem;color:var(--mu2);margin-bottom:8px">📦 PT taller: '+(sm.stk_pt||0)+' und &nbsp;·&nbsp; Base VELA × '+hs+' temp. alta · '+((DATA.velocity_months_label)||'')+' · XL/2XL boost</div>')
        +modelosHtml;
      prodGrid.appendChild(card);
    });
  }

"""
    html = re.sub(
        r"  // ── (?:PRODUCTION CURVE|CURVA DE PRODUCCIÓN POR ZONA).*?(?=\n\}\n\nfunction exportCSV)",
        lambda _m: prod_curve_js,
        html,
        count=1,
        flags=re.DOTALL,
    )

    html = html.replace(
        "<h3>🏭 Curva de Producción por Modelo</h3>\n      <div class=\"sub\">Cobertura (meses) y producción neta por color/talla · CAB y DAMA</div>\n      <div id=\"propGrid\" style=\"display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px;margin-top:10px\"></div>",
        "<h3>🏭 Curva de Producción por Zona</h3>\n      <div class=\"sub\">Margarita → Caracas → Valencia → Barquisimeto · diseños expandibles con variantes a producir</div>\n      <div id=\"propGrid\" style=\"display:flex;flex-direction:column;gap:14px;margin-top:10px\"></div>",
    )

    # Quitar reabastecimiento por tienda (movido a curva de producción por zona)
    html = re.sub(
        r'\s*<div class="card g1">\s*<h3>🏪 Reabastecimiento por Tienda</h3>.*?</div>\s*</div>\s*</div>',
        "\n</div>\n</div>",
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"\n  // ── REABASTECIMIENTO.*?(?=\n\}\n\nfunction exportCSV)",
        "",
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = re.sub(r"\nfunction renderReabast\(allRows\)\{.*?\n\}\n\n", "\n", html, count=1, flags=re.DOTALL)

    # Pestaña y sección Diseños (al lado de Colores)
    if 'st(\'disenos\')' not in html:
        html = html.replace(
            '<button class="tab" onclick="st(\'colores\')">🎨 Colores</button>\n  <button class="tab" onclick="st(\'tallas\')">📐 Tallas</button>',
            '<button class="tab" onclick="st(\'colores\')">🎨 Colores</button>\n  <button class="tab" onclick="st(\'disenos\')">✨ Diseños</button>\n  <button class="tab" onclick="st(\'tallas\')">📐 Tallas</button>',
        )
    if 'id="sec-disenos"' not in html:
        html = html.replace(
            '</div>\n<div class="sec" id="sec-tallas">',
            '</div>\n<div class="sec" id="sec-disenos">\n  <div class="g2">\n'
            '    <div class="card"><h3>Ranking de Diseños</h3><div class="sub">Unidades y proporción total</div><div id="disRank"></div></div>\n'
            '    <div class="card"><h3>Diseños por Género</h3><div class="sub">Barras agrupadas por línea</div><div class="cw t"><canvas id="cDisGen"></canvas></div></div>\n'
            '  </div>\n  <div class="g1 card"><h3>Diseño × Tienda</h3><div class="sub">Heatmap de volumen</div><div class="hmw" id="disTiendaHM"></div></div>\n'
            '</div>\n<div class="sec" id="sec-tallas">',
            1,
        )
    html = html.replace(
        "var TABS=['resumen','colores','tallas','tiendas','inventario','decisiones'];",
        "var TABS=['resumen','colores','disenos','tallas','tiendas','inventario','decisiones'];",
    )
    html = html.replace(
        "if(tx.indexOf('Color')>=0)return'colores';if(tx.indexOf('Talla')>=0)return'tallas';",
        "if(tx.indexOf('Color')>=0)return'colores';if(tx.indexOf('Diseño')>=0)return'disenos';if(tx.indexOf('Talla')>=0)return'tallas';",
    )
    html = html.replace(
        "else if(n==='colores')rColores();else if(n==='tallas')rTallas();",
        "else if(n==='colores')rColores();else if(n==='disenos')rDisenos();else if(n==='tallas')rTallas();",
    )
    if "function rDisenos()" not in html:
        r_disenos = (
            "function rDisenos(){\n"
            "  var rows=fr();if(!rows.length){document.getElementById('disRank').innerHTML='<div class=\"nodata\">Sin datos</div>';return;}\n"
            "  var normRows=rows.map(function(r){return Object.assign({},r,{diseno:r.diseno||'Sin diseño'});});\n"
            "  var byDiseno=ag(normRows,'diseno');bRT(document.getElementById('disRank'),byDiseno,cn);\n"
            "  var generos=ag(normRows,'genero').map(function(x){return x.k;});\n"
            "  var topDisenos=byDiseno.slice(0,10).map(function(x){return x.k;});\n"
            "  var m2dg=ag2(normRows,'diseno','genero');\n"
            "  mc('cDisGen','bar',{labels:topDisenos,datasets:generos.map(function(g){var gRows=normRows.filter(function(r){return r.genero===g;});var gtot=gRows.reduce(function(a,r){return a+r.v;},0);return{label:(GICO[g]||'')+' '+g,data:topDisenos.map(function(d){return(m2dg[d]&&m2dg[d][g])||0;}),backgroundColor:gcol(g)+'bb',borderColor:gcol(g),borderWidth:1,borderRadius:4,_pcts:topDisenos.map(function(d){var v=(m2dg[d]&&m2dg[d][g])||0;return gtot>0?Math.round(v/gtot*1000)/10:0;})};})},Object.assign(bo(),{plugins:{legend:{display:true,position:'top',labels:{color:txCol(),font:{family:'DM Sans',size:10},boxWidth:10,padding:8}},tooltip:{mode:'index',intersect:false,backgroundColor:'#1e1f2b',borderColor:'#2a2b3a',borderWidth:1,titleFont:{family:'Syne',weight:'bold'},bodyFont:{family:'DM Sans'},padding:10,callbacks:{label:function(ctx){var pct=ctx.dataset._pcts[ctx.dataIndex];return ' '+ctx.dataset.label+': '+ctx.parsed.y+' und ('+pct+'%)';}}},datalabels:{display:true,color:'#fff',font:{family:'Syne',weight:'bold',size:12},textShadowBlur:3,textShadowColor:'rgba(0,0,0,0.7)',anchor:'end',align:'start',formatter:function(v){return v>0?v:'';}}},scales:{x:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7a7b95',font:{family:'DM Sans',size:9},maxRotation:30}},y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7a7b95',font:{family:'DM Sans',size:10}}}}}));\n"
            "  var tiendas=ag(normRows,'tienda').map(function(x){return x.k;});var m2dt=ag2(normRows,'diseno','tienda');var topD12=byDiseno.slice(0,12).map(function(x){return x.k;});var mxDT=0;topD12.forEach(function(d){tiendas.forEach(function(t){var v=(m2dt[d]&&m2dt[d][t])||0;if(v>mxDT)mxDT=v;});});\n"
            "  var h='<table class=\"hmt\"><thead><tr><th></th>'+tiendas.map(function(t){return'<th>'+t+'</th>';}).join('')+'</tr></thead><tbody>';topD12.forEach(function(d){h+='<tr><td class=\"rl\"><span class=\"chip\" style=\"background:'+cn(d)+'\"></span>'+d+'</td>'+tiendas.map(function(t){var v=(m2dt[d]&&m2dt[d][t])||0;return'<td style=\"background:'+hb(v,mxDT)+';color:'+ht(v,mxDT)+'\" title=\"'+d+' · '+t+': '+v+' und\">'+v+'</td>';}).join('')+'</tr>';});\n"
            "  document.getElementById('disTiendaHM').innerHTML=h+'</tbody></table>';\n"
            "}\n\n"
        )
        html = html.replace("function rTallas(){", r_disenos + "function rTallas(){")

    html = html.replace("DATA.high_season_factor||1.4", "DATA.high_season_factor||1.2")
    html = html.replace(
        "DATA.expansion_stores||['VALENCIA','BARQUISIMETO']",
        "DATA.expansion_stores||['VALENCIA','BARQUISIMETO','CARACAS']",
    )

    # Add decMethodology container
    if 'id="decMethodology"' not in html:
        html = html.replace(
            '  <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap">',
            '  <div id="decMethodology"></div>\n  <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap">',
            1,
        )

    # Inv matrix show diseno in cell label
    html = html.replace(
        "h+='<tr><td class=\"color-cell\"><span class=\"chip\" style=\"background:'+cn(rd.color)+'\"></span>'+(GICO[rd.genero]||'')+' '+rd.genero+' · '+rd.color+'</td>';",
        "h+='<tr><td class=\"color-cell\"><span class=\"chip\" style=\"background:'+cn(rd.color)+'\"></span>'+(GICO[rd.genero]||'')+' '+rd.genero+' · '+rd.color+(rd.diseno?' · '+rd.diseno:'')+'</td>';",
    )

    return html


def main():
    data = rebuild_data()
    html = patch_html(build_html(data), data)
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote {HTML_PATH}")
    print(f"ventas: {data['total']} und | meses: {data['meses_order']}")
    print(f"vel months: {data['velocity_months']}")
    print(f"expansion total: {data['expansion']['total_expansion']} (blanco {data['expansion']['total_blanco']} + adicional {data['expansion']['total_adicional']})")
    for s in data["expansion"]["by_store"]:
        print(f"  {s['store']}: {s['total']} und (B{s['blanco']} + A{s['adicional']})")


if __name__ == "__main__":
    main()
