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
PARTIAL_MONTH = "septiembre-2026"
VELOCITY_MONTHS_COUNT = 3
BASE_STORE = "VELA"
DECISION_STORES = ["VELA"]
BQT_DISENO_CIUDAD = "Ciudad"
BQT_DISENO_VIRGEN = "Virgen"
BQT_VIRGEN_REF = "Virgen del Valle"
BQT_CIUDAD_REF = "Nueva Esparta"
EXPANSION_STORES = ["CARACAS", "VALENCIA", "BARQUISIMETO"]
PROD_ZONE_ORDER = ["MARGARITA", "CARACAS", "VALENCIA", "BARQUISIMETO"]
EXPANSION_CAPS = {
    "CARACAS": {
        "mult": 1.0,
        "label": "Modelo exclusivo zona Caracas · incluye Manga Larga",
        "zone_model": "Modelo Caracas",
        "modelos": ["SPOTS MANGA CORTA", "SPOTS MANGA LARGA"],
    },
    "VALENCIA": {
        "mult": 1.0,
        "label": "Modelo exclusivo zona Valencia",
        "zone_model": "Modelo Valencia",
        "modelos": ["SPOTS MANGA CORTA"],
    },
    "BARQUISIMETO": {
        "mult": 1.0,
        "label": (
            "Barquisimeto · Blanco en 2 diseños (Ciudad + Virgen) · "
            f"Virgen festividad dic ×{DECEMBER_HS_FACTOR}"
        ),
        "zone_model": "Modelo Barquisimeto",
        "modelos": ["SPOTS MANGA CORTA"],
        "blanco_designs": [
            {
                "diseno": BQT_DISENO_CIUDAD,
                "ref_diseno": BQT_CIUDAD_REF,
                "hs_factor": HIGH_SEASON_FACTOR,
            },
            {
                "diseno": BQT_DISENO_VIRGEN,
                "ref_diseno": BQT_VIRGEN_REF,
                "hs_factor": DECEMBER_HS_FACTOR,
                "seasonality": "Festividad Virgen · rotación dic ×1.4",
            },
        ],
    },
}
ADDITIONAL_COLOR = "Color adicional"
ADDITIONAL_COLOR_FACTOR = 0.70
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
        v_mes_base = round(base_v, 1)
        v_mes = round(base_v * HIGH_SEASON_FACTOR, 1)
        key = stock_key(modelo, genero, color, diseno, talla)
        stk = int(stock.get(key, 0))
        stk_pt = int(stock_taller.get(key, 0))
        cob = round(stk / v_mes, 1) if v_mes > 0 else 999
        need_1m = max(0, round(v_mes * 1 - stk))
        need_2m = max(0, round(v_mes * 2 - stk))
        need_3m = max(0, round(v_mes * LEAD_MONTHS - stk))
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
            "need_1m": need_1m,
            "need_2m": need_2m,
            "need_3m": need_3m,
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
            "need_1m": sum(r["need_1m"] for r in rows_m),
            "need_2m": sum(r["need_2m"] for r in rows_m),
            "need_3m": sum(r["need_3m"] for r in rows_m),
        }
    return prod_rows, summary


def _blanco_velocity_groups(store_rows, vel_months):
    """Velocidad mensual Blanco VELA por línea/género/talla (agregado y por diseño)."""
    total = defaultdict(float)
    by_diseno = defaultdict(float)
    for r in store_rows:
        if r["color"].lower() != "blanco":
            continue
        if r["mes"] not in vel_months:
            continue
        v = r["v"] / len(vel_months)
        k = (r["modelo"], r["genero"], r["talla"])
        total[k] += v
        by_diseno[(r["modelo"], r["genero"], r["talla"], r["diseno"])] += v
    return total, by_diseno


def _ref_velocity(by_diseno, ref_diseno, modelo, genero, talla, v_total):
    v = by_diseno.get((modelo, genero, talla, ref_diseno), 0)
    if v > 0:
        return v
    # Reparto proporcional si falta talla en el diseño referencia
    design_total = sum(
        v_d for (m, g, t, _), v_d in by_diseno.items()
        if m == modelo and g == genero and t == talla
    )
    if design_total > 0:
        ref_sum = sum(
            v_d for (m, g, t, d), v_d in by_diseno.items()
            if m == modelo and g == genero and d == ref_diseno
        )
        share = ref_sum / design_total if design_total else 0.5
        return v_total * share
    return v_total * 0.5


def _append_sku(skus, modelo, genero, talla, diseno, color, zone_model, v_adj, hs_factor, seasonality=""):
    need_1m = max(0, round(v_adj))
    need_2m = max(0, round(v_adj * 2))
    need_3m = max(0, round(v_adj * LEAD_MONTHS))
    skus.append({
        "modelo": modelo,
        "genero": genero,
        "diseno": diseno,
        "zone_model": zone_model,
        "talla": talla,
        "color": color,
        "v_mes": v_adj,
        "hs_factor": hs_factor,
        "seasonality": seasonality,
        "need_1m": need_1m,
        "need_2m": need_2m,
        "need_3m": need_3m,
    })
    return need_3m


def compute_expansion(raw_rows, vel_months, prod_rows):
    """Proyección por zona: modelo propio + Blanco + color adicional (70%).

    Referencia de velocidad = movimiento Blanco VELA (sin replicar diseños Margarita).
    Barquisimeto: Blanco en 2 diseños (Ciudad ×1.2, Virgen festividad dic ×1.4).
    """
    store_rows = [r for r in raw_rows if r["tienda"] == BASE_STORE]
    total_groups, design_groups = _blanco_velocity_groups(store_rows, vel_months)
    expansion = {
        "base_store": BASE_STORE,
        "stores": EXPANSION_STORES,
        "additional_color": ADDITIONAL_COLOR,
        "additional_color_factor": ADDITIONAL_COLOR_FACTOR,
        "high_season_factor": HIGH_SEASON_FACTOR,
        "december_hs_factor": DECEMBER_HS_FACTOR,
        "velocity_months_count": VELOCITY_MONTHS_COUNT,
        "lead_months": LEAD_MONTHS,
        "vela_exclusive_note": (
            "Diseños VELA (Nueva Esparta, Virgen del Valle, Manga Larga, etc.) "
            "son exclusivos de la zona Margarita"
        ),
        "by_store": [],
        "by_color": [],
        "total_blanco": 0,
        "total_adicional": 0,
        "total_zona_modelo": 0,
        "total_expansion": 0,
    }

    for store in EXPANSION_STORES:
        cap = EXPANSION_CAPS[store]
        mult = cap.get("mult", 1)
        zone_model = cap.get("zone_model", f"Modelo {store.title()}")
        store_blanco = 0
        store_adicional = 0
        store_zona = 0
        skus = []
        allowed_modelos = set(cap.get("modelos", ["SPOTS MANGA CORTA", "SPOTS MANGA LARGA"]))
        blanco_designs = cap.get("blanco_designs")

        for (modelo, genero, talla), v_base in sorted(total_groups.items()):
            if modelo not in allowed_modelos:
                continue
            v_zone = round(v_base * HIGH_SEASON_FACTOR * mult, 2)
            store_zona += _append_sku(
                skus, modelo, genero, talla, zone_model, zone_model, zone_model,
                v_zone, HIGH_SEASON_FACTOR,
            )

            v_blanco_total = 0.0
            if blanco_designs:
                for bd in blanco_designs:
                    v_ref = _ref_velocity(
                        design_groups, bd["ref_diseno"], modelo, genero, talla, v_base,
                    )
                    hs = bd.get("hs_factor", HIGH_SEASON_FACTOR)
                    v_adj = round(v_ref * mult * hs, 2)
                    v_blanco_total += v_adj
                    store_blanco += _append_sku(
                        skus, modelo, genero, talla, bd["diseno"], "Blanco", zone_model,
                        v_adj, hs, bd.get("seasonality", ""),
                    )
            else:
                v_adj = round(v_base * HIGH_SEASON_FACTOR * mult, 2)
                v_blanco_total = v_adj
                store_blanco += _append_sku(
                    skus, modelo, genero, talla, "Blanco", "Blanco", zone_model,
                    v_adj, HIGH_SEASON_FACTOR,
                )

            v_add = round(v_blanco_total * ADDITIONAL_COLOR_FACTOR, 2)
            adicional_3m = _append_sku(
                skus, modelo, genero, talla, ADDITIONAL_COLOR, ADDITIONAL_COLOR, zone_model,
                v_add, HIGH_SEASON_FACTOR,
            )
            store_adicional += adicional_3m

        store_total = store_zona + store_blanco + store_adicional
        expansion["by_store"].append({
            "store": store,
            "label": cap.get("label", ""),
            "zone_model": zone_model,
            "blanco": store_blanco,
            "adicional": store_adicional,
            "zona_modelo": store_zona,
            "total": store_total,
            "skus": skus,
            "blanco_designs": [bd["diseno"] for bd in blanco_designs] if blanco_designs else None,
        })
        expansion["total_blanco"] += store_blanco
        expansion["total_adicional"] += store_adicional
        expansion["total_zona_modelo"] += store_zona

    expansion["total_expansion"] = (
        expansion["total_zona_modelo"]
        + expansion["total_blanco"]
        + expansion["total_adicional"]
    )
    expansion["by_color"] = [
        {"color": "Blanco", "need_3m": expansion["total_blanco"]},
        {
            "color": ADDITIONAL_COLOR,
            "need_3m": expansion["total_adicional"],
            "note": f"{int(ADDITIONAL_COLOR_FACTOR * 100)}% vs Blanco",
        },
    ]
    zones_label = ", ".join(EXPANSION_STORES)
    vel_lbl = ", ".join(velocity_months_label(vel_months))
    expansion["nota"] = (
        f"Base {VELOCITY_MONTHS_COUNT} meses cerrados ({vel_lbl}) · ref. movimiento Blanco VELA. "
        f"Temp. alta ×{HIGH_SEASON_FACTOR} · Virgen Barquisimeto dic ×{DECEMBER_HS_FACTOR}. "
        f"Producción {LEAD_MONTHS}m · {zones_label}. "
        f"Cada zona: modelo propio + Blanco + {ADDITIONAL_COLOR} al "
        f"{int(ADDITIONAL_COLOR_FACTOR * 100)}%. Diseños VELA no se replican."
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
            "need_1m": sum(r["need_1m"] for r in margarita_rows),
            "need_2m": sum(r["need_2m"] for r in margarita_rows),
            "need_3m": sum(r["need_3m"] for r in margarita_rows),
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
                "zone_model": sku.get("zone_model", es["zone_model"]),
                "talla": sku["talla"],
                "v_mes": v,
                "v_mes_base": round(v / hs, 2) if hs else v,
                "hs_factor": hs,
                "seasonality": sku.get("seasonality", ""),
                "stk_total": 0,
                "stk_pt": 0,
                "cobertura": 0,
                "need_1m": sku.get("need_1m", max(0, round(v))),
                "need_2m": sku.get("need_2m", max(0, round(v * 2))),
                "need_3m": sku["need_3m"],
            })
        zones.append({
            "zone": store,
            "label": store.title(),
            "is_expansion": True,
            "zone_model": es["zone_model"],
            "note": es["label"],
            "summary": {
                "v_mes": round(sum(r["v_mes"] for r in rows), 1),
                "stk_total": 0,
                "stk_pt": 0,
                "need_1m": sum(r["need_1m"] for r in rows),
                "need_2m": sum(r["need_2m"] for r in rows),
                "need_3m": sum(r["need_3m"] for r in rows),
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
                    "need_1m": sum(r["need_1m"] for r in rows_m),
                    "need_2m": sum(r["need_2m"] for r in rows_m),
                    "need_3m": sum(r["need_3m"] for r in rows_m),
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

    # Decisiones: methodology + expansion + diseno grouping
    dec_methodology_js = (
        "function rDecisiones(){\n  var meses=_decMeses||2;\n"
        "  var hs=DATA.high_season_factor||1.2;\n"
        "  var hsLbl=document.getElementById('hsFactorLabel');if(hsLbl)hsLbl.textContent=hs;\n"
        "  var decHdr=document.getElementById('decMethodology');\n"
        "  if(decHdr){\n"
        "    var velLbl=DATA.velocity_months_label||'';\n"
        "    var velCnt=DATA.velocity_months_count||3;\n"
        "    var dicHs=DATA.december_hs_factor||1.4;\n"
        "    var exp=DATA.expansion||{};\n"
        "    var addPct=Math.round((DATA.additional_color_factor||0.7)*100);\n"
        "    var zoneCards=(exp.by_store||[]).map(function(z){\n"
        "      var extra=z.blanco_designs?(' · Blanco: <strong style=\"color:var(--tx)\">'+z.blanco_designs.join(' + ')+'</strong>'):'';\n"
        "      return '<div style=\"background:rgba(0,0,0,.12);border-radius:8px;padding:8px 10px\">'\n"
        "        +'<strong style=\"color:#f97316\">'+z.store+'</strong> · <span style=\"color:var(--tx)\">'+(z.zone_model||'')+'</span>'+extra\n"
        "        +'<div style=\"font-size:.64rem;margin-top:4px\">'+z.total+' und · Blanco <strong>'+z.blanco+'</strong> + '+((DATA.additional_color)||'adicional')+' <strong>'+z.adicional+'</strong></div></div>';\n"
        "    }).join('');\n"
        "    decHdr.innerHTML='<div style=\"background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.22);border-radius:12px;padding:14px 16px;font-size:.71rem;color:var(--mu);line-height:1.55;margin-bottom:14px\">'\n"
        "      +'<div style=\"font-family:var(--fh);font-weight:800;color:var(--a2);margin-bottom:10px;font-size:.78rem\">📋 Metodología — rotación y producción</div>'\n"
        "      +'<div style=\"display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px 16px\">'\n"
        "      +'<div><strong style=\"color:var(--tx)\">Foco tienda VELA</strong><br>Velocidad base = ventas <strong style=\"color:var(--tx)\">VELA Margarita</strong> en <strong style=\"color:var(--tx)\">'+velCnt+' meses</strong> cerrados ('+velLbl+'; sin '+((DATA.partial_month||'mes parcial').split('-')[0])+').</div>'\n"
        "      +'<div><strong style=\"color:var(--tx)\">Temporada alta</strong><br>Rotación ajustada = base × <strong style=\"color:var(--tx)\">'+hs+'</strong>. Barquisimeto Virgen (festividad dic) × <strong style=\"color:var(--tx)\">'+dicHs+'</strong>.</div>'\n"
        "      +'<div><strong style=\"color:var(--tx)\">Diseños exclusivos Margarita</strong><br>Nueva Esparta, Virgen del Valle, Manga Larga, etc. <strong style=\"color:var(--tx)\">no van</strong> a Valencia, Barquisimeto ni Caracas.</div>'\n"
        "      +'<div><strong style=\"color:var(--tx)\">🆕 Expansión — 3 zonas</strong><br>Modelo propio + Blanco + '+((DATA.additional_color)||'Color adicional')+' al <strong style=\"color:var(--tx)\">'+addPct+'%</strong>. Barquisimeto Blanco: <strong style=\"color:var(--tx)\">Ciudad</strong> + <strong style=\"color:var(--tx)\">Virgen</strong> (estacionalidad festividad).</div>'\n"
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
      var totalNeed=meses===1?sm.need_1m:meses===2?sm.need_2m:sm.need_3m;
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
          var gk=zn.is_expansion?(r.diseno||r.color):(r.diseno||r.color);
          if(!byGroup[gk])byGroup[gk]={rows:[],totalStk:0,totalNeed1:0,totalNeed2:0,totalNeed3:0,v_mes:0,seasonality:''};
          byGroup[gk].rows.push(r);
          byGroup[gk].totalStk+=r.stk_total||0;
          byGroup[gk].totalNeed1+=r.need_1m||0;
          byGroup[gk].totalNeed2+=r.need_2m||0;
          byGroup[gk].totalNeed3+=r.need_3m||0;
          byGroup[gk].v_mes+=r.v_mes||0;
          if(r.seasonality)byGroup[gk].seasonality=r.seasonality;
        });
        var gKeys=Object.keys(byGroup).sort(function(a,b){return byGroup[b].v_mes-byGroup[a].v_mes;});
        var groupsHtml=gKeys.map(function(gk){
          var gd=byGroup[gk];
          var gNeed=meses===1?gd.totalNeed1:meses===2?gd.totalNeed2:gd.totalNeed3;
          var uid='pg_'+zn.zone+'_'+mod.replace(/\W/g,'_')+'_'+gk.replace(/\W/g,'_');
          var col=gk==='Blanco'?'#e4e4e7':(gk.toLowerCase().indexOf('adicional')>=0?'#a5b4fc':cn(gk));
          var seasonNote=gd.seasonality?('<span style="font-size:.6rem;color:#f59e0b;margin-left:6px">'+gd.seasonality+'</span>'):'';
          var sortedRows=gd.rows.slice().sort(function(a,b){return(TORD[a.talla]||99)-(TORD[b.talla]||99);});
          var tallasHtml=sortedRows.map(function(r){
            var tn=meses===1?r.need_1m:meses===2?r.need_2m:r.need_3m;
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
      var card=document.createElement('div');
      card.style.cssText='background:'+zoneBg+';border:1px solid '+zoneBorder+';border-radius:12px;padding:14px';
      card.innerHTML='<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">'
        +'<h3 style="margin:0;font-family:var(--fh);font-size:.92rem">'+(zn.is_expansion?'🆕 ':'🏝️ ')+zn.label+'</h3>'
        +(zn.zone_model?'<span style="font-size:.68rem;color:var(--mu2)">'+zn.zone_model+'</span>':'')
        +(zn.is_expansion?'<span style="background:rgba(249,115,22,.15);color:#f97316;border-radius:4px;padding:2px 8px;font-size:.62rem;font-weight:700">Expansión</span>':'')
        +'<span style="margin-left:auto;font-family:var(--fm);font-size:.78rem;font-weight:800;color:'+cobColor+'">'+(cob?cob+' meses cob':'Proyección '+totalNeed+' und')+'</span>'
        +'</div>'
        +(zn.note?'<div style="font-size:.65rem;color:var(--mu2);margin-bottom:10px">'+zn.note+'</div>':'')
        +'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px">'
        +'<div style="text-align:center;background:rgba(99,102,241,.1);border-radius:8px;padding:8px"><div style="font-family:var(--fm);font-size:1.1rem;font-weight:800;color:#818cf8">'+(sm.need_1m||0)+'</div><div style="font-size:.63rem;color:var(--mu)">Producir 1 mes</div></div>'
        +'<div style="text-align:center;background:rgba(245,158,11,.1);border-radius:8px;padding:8px"><div style="font-family:var(--fm);font-size:1.1rem;font-weight:800;color:#f59e0b">'+(sm.need_2m||0)+'</div><div style="font-size:.63rem;color:var(--mu)">Producir 2 meses</div></div>'
        +'<div style="text-align:center;background:rgba(244,63,94,.1);border-radius:8px;padding:8px"><div style="font-family:var(--fm);font-size:1.1rem;font-weight:800;color:#f43f5e">'+(sm.need_3m||0)+'</div><div style="font-size:.63rem;color:var(--mu)">Producir 3 meses</div></div>'
        +'</div>'
        +(zn.is_expansion?'':'<div style="font-size:.67rem;color:var(--mu2);margin-bottom:8px">📦 PT taller: '+(sm.stk_pt||0)+' und &nbsp;·&nbsp; Base VELA × '+hs+' temp. alta · '+((DATA.velocity_months_label)||'')+'</div>')
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
