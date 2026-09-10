#!/usr/bin/env python3
"""Build MAR ORIGINAL dashboard + proyecciones Excel from sales/inventory files."""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = Path("/home/ubuntu/.cursor/projects/workspace/uploads")
TEMPLATE = UPLOADS / "DASHBOARD_MAR_ORIGINAL_7340.html"
VENTAS_XLSX = UPLOADS / "VENTAS_ARREGLADAS_MAR_ORIGINAL_ACTUALIZADAS_5e6d.xlsx"
INV_XLSX = UPLOADS / "MAR_ORIGINAL_INVENTARIO_ARREGLADO_b31f.xlsx"
OUT_HTML = ROOT / "DASHBOARD_MAR_ORIGINAL.html"
OUT_XLSX = ROOT / "MAR_ORIGINAL_Proyeccion_Produccion.xlsx"

MESES_NUM = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
    "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
MESES_SLUG = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}
MESES_SHORT = {
    "enero": "Ene", "febrero": "Feb", "marzo": "Mar", "abril": "Abr", "mayo": "May", "junio": "Jun",
    "julio": "Jul", "agosto": "Ago", "septiembre": "Sep", "octubre": "Oct", "noviembre": "Nov", "diciembre": "Dic",
}

STORE_MAP = {
    "SAMBIL VALENCIA": "SAMBIL", "Sambil Valencia": "SAMBIL",
    "SAMBIL CHACAO": "CHACAO", "Sambil Chacao": "CHACAO",
    "GRIETA": "GRIE", "La Grieta": "GRIE",
    "GRAND PLAZ": "GRAND", "Grandplaz": "GRAND", "GRANDPLAZ": "GRAND",
    "LA VELA": "VELA", "La Vela": "VELA",
    "TOLON": "TOLON", "Tolon": "TOLON",
    "CERRO VERDE": "CERRO VERDE", "Cerro Verde": "CERRO VERDE",
    "PEDIDOS": "PEDIDOS", "Pedidos": "PEDIDOS",
    "WEB": "WEB", "CORPORATIVO": "CORPORATIVO",
}
INV_STORE_MAP = {
    "GRIETA": "GRIE", "GRANDPLAZ": "GRAND", "CHACAO": "CHACAO", "SAMBIL": "SAMBIL",
    "TOLON": "TOLON", "VELA": "VELA", "CERRO VERDE": "CERRO VERDE", "TALLER": "TALLER",
}
GEN_MAP = {
    "Caballero": "CAB", "CAB": "CAB", "caballero": "CAB",
    "Dama": "DAMA", "DAMA": "DAMA", "dama": "DAMA",
    "Kids": "KIDS", "KIDS": "KIDS", "kids": "KIDS",
}

# Colores disponibles para producción — catálogo Mar (Modelos disponibles para la venta)
COLORES_PRODUCCION = {
    "CAB": [
        "Aguamarina", "Amarillo Neón", "Azul Lavanda", "Azul Marino", "Azul Rey", "Blanco",
        "Gris Claro", "Negro", "Rojo", "Verde Militar", "Vinotinto",
    ],
    "DAMA": [
        "Aguamarina", "Amarillo Neón", "Azul Lavanda", "Azul Marino", "Blanco", "Lila",
        "Negro", "Púrpura", "Rojo", "Rosado Pastel", "Verde Militar", "Vinotinto",
    ],
    "KIDS": [
        "Negro", "Azul Marino", "Blanco", "Verde Militar", "Azul Lavanda", "Azul Rey",
        "Aguamarina", "Rojo", "Lila", "Rosado Pastel", "Púrpura", "Amarillo Neón",
    ],
}
COLORES_DISP = COLORES_PRODUCCION

RETAIL_STORES = ["SAMBIL", "GRIE", "CERRO VERDE", "CHACAO", "GRAND", "TOLON", "VELA"]
PROJECTED_STORES = ["BARQUISIMETO", "WEB"]

HIGH_SEASON_FACTOR = {"CAB": 1.60, "DAMA": 1.60, "KIDS": 2.05}
TOLON_BOOST = 1.45
WEB_STRONGEST_RATIO = 0.5
COVERAGE_MONTHS = {"CAB": 4, "DAMA": 4, "KIDS": 5}
SAFETY_BUFFER = {"CAB": 1.28, "DAMA": 1.28, "KIDS": 1.48}
MAX_RANGE_PCT = 0.06
TELA_CONSUMO = {"CAB": 0.50, "DAMA": 0.40, "KIDS": 0.26}
TELA_SS = 0.20
TELA_NOMBRE = "Jabón Microfibra"
VELOCITY_PERIODS = ["mayo-2026", "junio-2026", "julio-2026", "agosto-2026"]
VELOCITY_WEIGHTS = {"mayo-2026": 0.85, "junio-2026": 0.95, "julio-2026": 1.0, "agosto-2026": 1.15}
ALL_DIST_STORES = ["SAMBIL", "GRIE", "CERRO VERDE", "CHACAO", "GRAND", "TOLON", "VELA", "BARQUISIMETO", "WEB"]
STORE_LABELS_XL = {
    "SAMBIL": "SAMBIL", "GRIE": "GRIETA", "CERRO VERDE": "CERRO VERDE", "CHACAO": "CHACAO",
    "GRAND": "GRAND PLAZ ★", "TOLON": "TOLON ★", "VELA": "LA VELA ★",
    "BARQUISIMETO": "BARQUISIMETO ★", "WEB": "WEB ★",
}
TALLA_ORDER = {
    "CAB": ["XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL"],
    "DAMA": ["XS", "S", "M", "L", "XL", "2XL", "3XL"],
    "KIDS": ["2", "4", "6", "8", "10", "12", "14"],
}
TARGET_PRODUCE_MIN = {"CAB": 2650, "DAMA": 2450, "KIDS": 2950}
MIN_VARIANT = {"CAB": 1, "DAMA": 1, "KIDS": 1}
LOW_COLOR_FLOOR = {"CAB": 28, "DAMA": 32, "KIDS": 38}
# Tallas fuera de proyección de producción (ventas históricas siguen en dashboard)
PRODUCTION_EXCLUDE_TALLAS: dict[str, set[str]] = {
    "CAB": {"3XL", "4XL"},
    "DAMA": {"2XL"},
}
# Ajuste fino sobre curva de ventas antes de repartir el objetivo
TALLA_WEIGHT_BOOST: dict[str, dict[str, float]] = {
    "CAB": {"2XL": 1.22},
    "DAMA": {"L": 1.22},
}


def norm_color(c: str) -> str:
    if not isinstance(c, str) or not c.strip():
        return "Sin color"
    c = c.strip()
    repl = {
        "amarillo neon": "Amarillo Neón", "amarillo neón": "Amarillo Neón",
        "verde militar": "Verde Militar", "verde miliar": "Verde Militar",
        "azul marino": "Azul Marino", "azul lavanda": "Azul Lavanda", "azul rey": "Azul Rey",
        "gris claro": "Gris Claro", "gris": "Gris", "rosado pastel": "Rosado Pastel",
        "rosa pastel": "Rosado Pastel",
        "azul cielo": "Azul Cielo", "azul turquesa": "Azul Turquesa",
        "amarillo pastel": "Amarillo Pastel", "coral neón": "Coral Neón",
        "rosado neón": "Rosado Neón", "morado": "Morado", "purpura": "Púrpura", "púrpura": "Púrpura",
        "fucsia": "Fucsia", "vinotinto": "Vinotinto", "aguamarina": "Aguamarina",
        "negro": "Negro", "blanco": "Blanco", "rojo": "Rojo", "lila": "Lila",
    }
    key = c.lower()
    if key in repl:
        return repl[key]
    return c[0].upper() + c[1:] if len(c) > 1 else c.upper()


def norm_store(raw: str) -> str:
    raw = str(raw).strip()
    return STORE_MAP.get(raw, raw.upper())


def norm_inv_store(raw: str) -> str:
    raw = str(raw).strip()
    return INV_STORE_MAP.get(raw, raw.upper())


def norm_genero(raw: str) -> str:
    return GEN_MAP.get(str(raw).strip(), str(raw).strip().upper())


def period_key(year: int, mes: str) -> tuple[int, int, str]:
    mn = MESES_NUM[mes]
    slug = f"{MESES_SLUG[mn]}-{year}"
    return year, mn, slug


def load_sales() -> pd.DataFrame:
    df = pd.read_excel(VENTAS_XLSX)
    df["tienda"] = df["tienda / ubicación"].map(norm_store)
    df["genero"] = df["GENERO"].map(norm_genero)
    df["color"] = df["COLOR"].map(norm_color)
    df["talla"] = df["TALLA"].astype(str).str.strip()
    df["v"] = df["Cant. ordenada"].astype(float)
    keys = df.apply(lambda r: period_key(int(r["Año"]), r["Mes"]), axis=1)
    df["year"] = keys.map(lambda x: x[0])
    df["mes_num"] = keys.map(lambda x: x[1])
    df["mes"] = keys.map(lambda x: x[2])
    return df


def load_inventory() -> pd.DataFrame:
    df = pd.read_excel(INV_XLSX)
    df["tienda"] = df["Ubicación"].map(norm_inv_store)
    df["genero"] = df["GENERO"].map(norm_genero)
    df["color"] = df["COLOR"].map(norm_color)
    df["talla"] = df["TALLA"].astype(str).str.strip()
    df["v"] = df["Cantidad en inventario"].astype(float)
    return df


def store_weights(by_store: dict[str, float]) -> dict[str, float]:
    grie = by_store.get("GRIE", 0)
    chacao = by_store.get("CHACAO", 0)
    tolon = by_store.get("TOLON", 0)
    strongest = max([by_store.get(s, 0) for s in RETAIL_STORES] + [1])

    weights = {}
    for s in RETAIL_STORES:
        base = by_store.get(s, 0)
        if s == "TOLON":
            base *= TOLON_BOOST
        weights[s] = base
    weights["VELA"] = grie
    weights["BARQUISIMETO"] = (grie + chacao + tolon) / 3
    weights["WEB"] = strongest * WEB_STRONGEST_RATIO

    total = sum(weights.values()) or 1
    return {k: v / total for k, v in weights.items()}


def weighted_velocity(df: pd.DataFrame) -> float:
    total_w = sum(VELOCITY_WEIGHTS.get(m, 1.0) for m in VELOCITY_PERIODS)
    acc = 0.0
    for mes in VELOCITY_PERIODS:
        w = VELOCITY_WEIGHTS.get(mes, 1.0)
        acc += df.loc[df["mes"] == mes, "v"].sum() * w
    return acc / max(total_w, 1)


def min_max_qty(qty: int) -> tuple[int, int]:
    if qty <= 0:
        return 0, 0
    qmin = qty
    qmax = int(math.ceil(qty * (1 + MAX_RANGE_PCT)))
    return qmin, qmax


def distribute_units(total: int, shares: dict[str, float], stores: list[str]) -> dict[str, int]:
    if total <= 0:
        return {s: 0 for s in stores}
    raw = {s: total * shares.get(s, 0) for s in stores}
    result = {s: int(math.floor(raw[s])) for s in stores}
    active = [s for s in stores if shares.get(s, 0) >= 0.025]
    if total >= max(len(active), 1):
        for s in active:
            if result[s] < 1:
                result[s] = 1
    diff = total - sum(result.values())
    if diff > 0:
        order = sorted(stores, key=lambda s: raw[s] - result[s], reverse=True)
        for i in range(diff):
            result[order[i % len(order)]] += 1
    elif diff < 0:
        order = sorted(stores, key=lambda s: result[s], reverse=True)
        for i in range(-diff):
            if order[i % len(order)] > 0:
                result[order[i % len(order)]] -= 1
    return result


def sort_tallas(genero: str, tallas: list[str]) -> list[str]:
    order = TALLA_ORDER.get(genero, [])
    ranked = sorted(tallas, key=lambda t: (order.index(t) if t in order else 99, t))
    return ranked


def to_production_color(color: str, genero: str) -> str:
    """Map sales/inventory color names to production catalog color."""
    c = norm_color(color)
    if genero == "CAB" and c in ("Gris Claro", "Gris"):
        return "Gris Claro"
    return c


def production_color_variants(prod_color: str, genero: str) -> list[str]:
    """Inventory/sales aliases when looking up stock for a production color."""
    if genero == "CAB" and prod_color == "Gris Claro":
        return ["Gris Claro", "Gris"]
    return [prod_color]


def remap_vel_colors(df: pd.DataFrame, genero: str) -> pd.DataFrame:
    out = df.copy()
    out["prod_color"] = out["color"].map(lambda c: to_production_color(c, genero))
    allowed = set(COLORES_PRODUCCION.get(genero, []))
    out = out[out["prod_color"].isin(allowed)]
    out["color"] = out["prod_color"]
    return out.drop(columns=["prod_color"])


def active_colors(genero: str, period_vel: pd.DataFrame, all_sales: pd.DataFrame) -> list[str]:
    """Only production-catalog colors, ordered by recent sales (May–Ago)."""
    disp = COLORES_PRODUCCION.get(genero, [])
    g_mapped = remap_vel_colors(period_vel, genero)
    sales_rank = g_mapped.groupby("color")["v"].sum().to_dict()
    return sorted(disp, key=lambda c: sales_rank.get(c, 0), reverse=True)


def active_tallas(genero: str, hist_vel: pd.DataFrame, *, for_production: bool = False) -> list[str]:
    """Only tallas with real sales — same basis as dashboard talla charts."""
    sold = hist_vel.groupby("talla")["v"].sum()
    sold = sold[sold > 0].index.astype(str).tolist()
    tallas = sort_tallas(genero, sold)
    if for_production:
        excluded = PRODUCTION_EXCLUDE_TALLAS.get(genero, set())
        tallas = [t for t in tallas if t not in excluded]
    return tallas


def production_talla_boost(genero: str, talla: str) -> float:
    return TALLA_WEIGHT_BOOST.get(genero, {}).get(talla, 1.0)


def calc_prop(hist: float, line_total: float, fc: float) -> int:
    """Dashboard calcProp: round(hist / lineTotal * fc)."""
    if not line_total or not fc:
        return 0
    return int(round(hist / line_total * fc))


def set_variant_qty(t: dict, qty: int, shares: dict[str, float]) -> None:
    pm, px = min_max_qty(max(qty, 0))
    t["produce_min"] = pm
    t["produce"] = pm
    t["produce_max"] = px
    t["store_split"] = distribute_units(pm, shares, ALL_DIST_STORES)
    t["store_split_max"] = distribute_units(px, shares, ALL_DIST_STORES)


def rebuild_gender_aggregates(
    plan: list, summary: dict, rango: dict, genero: str, shares: dict[str, float]
) -> None:
    items = [p for p in plan if p["genero"] == genero]
    g_prod = g_prod_max = 0
    color_rows = []
    talla_totals: dict = defaultdict(lambda: {"min": 0, "max": 0, "curve_pct": 0.0})
    store_talla = {s: defaultdict(lambda: {"min": 0, "max": 0}) for s in ALL_DIST_STORES}

    for item in items:
        c_min = sum(t["produce_min"] for t in item["tallas"])
        c_max = sum(t["produce_max"] for t in item["tallas"])
        item["produce_min"] = c_min
        item["produce"] = c_min
        item["produce_max"] = c_max
        item["store_split"] = distribute_units(c_min, shares, ALL_DIST_STORES)
        g_prod += c_min
        g_prod_max += c_max
        color_rows.append({
            "color": item["color"],
            "pct": item["color_pct"],
            "sales_pct": item.get("sales_pct", item["color_pct"] / 100),
            "min": c_min,
            "max": c_max,
            "tallas": item["tallas"],
        })
        for t in item["tallas"]:
            if t["produce_min"] <= 0:
                continue
            talla_totals[t["talla"]]["min"] += t["produce_min"]
            talla_totals[t["talla"]]["max"] += t["produce_max"]
            for store in ALL_DIST_STORES:
                store_talla[store][t["talla"]]["min"] += t["store_split"][store]
                store_talla[store][t["talla"]]["max"] += t["store_split_max"][store]

    for td in talla_totals.values():
        td["curve_pct"] = round(td["min"] / g_prod * 100, 1) if g_prod else 0.0

    summary[genero]["produce"] = g_prod
    summary[genero]["produce_max"] = g_prod_max
    rango[genero]["talla_totals"] = dict(talla_totals)
    color_rows.sort(key=lambda x: x.get("sales_pct", x["pct"]), reverse=True)
    rango[genero]["color_rows"] = color_rows
    rango[genero]["store_talla"] = {s: dict(v) for s, v in store_talla.items()}


def allocate_by_weights(weights: dict[tuple[str, str], float], target: int, floor: int = 1) -> dict[tuple[str, str], int]:
    """Largest-remainder allocation preserving proportional mix."""
    total_w = sum(weights.values())
    if total_w <= 0 or target <= 0:
        return {k: 0 for k in weights}
    keys = list(weights.keys())
    floats = [weights[k] / total_w * target for k in keys]
    ints = [max(floor, int(math.floor(f))) for f in floats]
    diff = target - sum(ints)
    if diff > 0:
        order = sorted(range(len(keys)), key=lambda i: floats[i] - ints[i], reverse=True)
        for i in range(diff):
            ints[order[i % len(order)]] += 1
    elif diff < 0:
        order = sorted(range(len(ints)), key=lambda i: ints[i] - floor, reverse=True)
        for i in range(-diff):
            idx = order[i % len(order)]
            if ints[idx] > floor:
                ints[idx] -= 1
    return {keys[i]: ints[i] for i in range(len(keys))}


def color_tier_multiplier(color: str, color_sales: pd.Series, genero: str) -> float:
    """Lower-selling colors get less than leaders, but not flat equal amounts."""
    if color not in color_sales.index or color_sales[color] <= 0:
        hist_rank = abs(hash(f"{genero}:{color}")) % 100
        return 0.42 + (hist_rank % 17) * 0.025
    rank = list(color_sales.index).index(color)
    share = color_sales[color] / (color_sales.sum() or 1)
    if share >= 0.08:
        return 1.0
    if share >= 0.03:
        return 0.72 + (rank % 5) * 0.04
    return 0.48 + (rank % 7) * 0.035 + share * 2.5


def build_gender_plan_proportional(
    plan: list,
    genero: str,
    g_vel: pd.DataFrame,
    all_sales: pd.DataFrame,
    inv: pd.DataFrame,
    shares: dict[str, float],
    target: int,
) -> tuple[dict, dict]:
    """Build production from dashboard-style sales proportions (color × talla)."""
    hs = HIGH_SEASON_FACTOR[genero]
    low_color_floor = LOW_COLOR_FLOOR[genero]

    g_vel = remap_vel_colors(g_vel, genero)
    hist_vel = remap_vel_colors(all_sales[all_sales["genero"] == genero], genero)
    period_vel = hist_vel[hist_vel["mes"].isin(VELOCITY_PERIODS)]
    colors = active_colors(genero, period_vel, all_sales)
    sold_tallas = active_tallas(genero, period_vel, for_production=True)
    excluded_tallas = PRODUCTION_EXCLUDE_TALLAS.get(genero, set())
    color_sales = period_vel.groupby("color")["v"].sum().sort_values(ascending=False)
    color_total = color_sales.sum() or 1
    gender_total = period_vel["v"].sum() or 1
    gender_talla = period_vel.groupby("talla")["v"].sum()
    gender_talla_pct = (gender_talla / gender_total).to_dict()

    mix_weights: dict[tuple[str, str], float] = {}
    meta: dict[tuple[str, str], dict] = {}
    color_meta: dict[str, dict] = {}

    for color in colors:
        c_vel = g_vel[g_vel["color"] == color]
        c_hist = period_vel[period_vel["color"] == color]
        c_total = float(c_hist["v"].sum())
        c_talla = c_hist.groupby("talla")["v"].sum()
        tier = color_tier_multiplier(color, color_sales, genero)
        v_base = weighted_velocity(c_vel) if len(c_vel) else max(c_total / max(len(VELOCITY_PERIODS), 1) * 0.12, 0.8)
        v_adj = v_base * hs * tier

        if c_total > 0:
            color_tallas = sort_tallas(genero, list(c_talla.index.astype(str)))
            t_mix = (c_talla / c_total).to_dict()
        else:
            color_tallas = sold_tallas
            t_mix = gender_talla_pct

        color_variants = production_color_variants(color, genero)
        stk_rows = inv[(inv["genero"] == genero) & (inv["color"].isin(color_variants))]
        stk = int(stk_rows["v"].sum())
        stk_taller = int(stk_rows[stk_rows["tienda"] == "TALLER"]["v"].sum())
        cob = round(stk / v_adj, 1) if v_adj > 0 else 99.0
        sales_share = (color_sales.get(color, 0) / color_total) if color in color_sales.index else 0.0
        color_meta[color] = {
            "color_pct": round(sales_share * 100, 1),
            "sales_share": sales_share,
            "stk": stk,
            "stk_taller": stk_taller,
            "cob": cob,
            "v_mes_base": round(v_base, 1),
            "v_mes": round(v_adj, 1),
        }

        for talla in color_tallas:
            if talla in excluded_tallas:
                continue
            ct = float(c_talla.get(talla, 0))
            if ct > 0:
                w = (ct / gender_total) * tier
                t_share = ct / c_total if c_total else gender_talla_pct.get(talla, 0)
            elif c_total > 0 and talla in sold_tallas:
                t_share = gender_talla_pct.get(talla, 0)
                w = (c_total * t_share / gender_total) * tier
            else:
                t_share = gender_talla_pct.get(talla, 0)
                w = (t_share / max(len(colors), 1)) * tier * 0.25

            w *= production_talla_boost(genero, talla)
            if w <= 0:
                continue

            tdf = c_vel[c_vel["talla"] == talla] if len(c_vel) else pd.DataFrame()
            tv_base = weighted_velocity(tdf) if len(tdf) else v_base * t_share
            tv_adj = tv_base * hs * tier
            inv_mask = (inv["genero"] == genero) & (inv["color"].isin(color_variants)) & (inv["talla"] == talla)
            t_stk = int(inv.loc[inv_mask, "v"].sum())
            t_stk_taller = int(inv.loc[inv_mask & (inv["tienda"] == "TALLER"), "v"].sum())
            t_cob = round(t_stk / tv_adj, 1) if tv_adj > 0 else 99.0
            mix_weights[(color, talla)] = w
            meta[(color, talla)] = {
                "v_mes_base": round(tv_base, 1),
                "v_mes": round(tv_adj, 1),
                "stk": t_stk,
                "stk_taller": t_stk_taller,
                "cob": t_cob,
                "curve_pct": round(t_share * 100, 1),
                "urgente": bool(t_cob < 3),
            }

    allocated = allocate_by_weights(mix_weights, target, floor=0)

    color_totals = defaultdict(int)
    for (color, _), qty in allocated.items():
        color_totals[color] += qty
    for color in colors:
        c_share = (color_sales.get(color, 0) / color_total) if color in color_sales.index else 0.0
        tier = color_tier_multiplier(color, color_sales, genero)
        min_color = max(8, int(low_color_floor * tier * (0.55 + c_share * 8)))
        if color_totals[color] >= min_color:
            continue
        deficit = min_color - color_totals[color]
        color_keys = [k for k in mix_weights if k[0] == color]
        if not color_keys:
            continue
        sub_w = {k: mix_weights[k] for k in color_keys}
        sub_alloc = allocate_by_weights(sub_w, deficit, floor=0)
        for k, add in sub_alloc.items():
            allocated[k] = allocated.get(k, 0) + add
            color_totals[color] += add

    total_now = sum(allocated.values())
    if total_now != target and total_now > 0:
        allocated = allocate_by_weights(
            {k: float(v) for k, v in allocated.items() if v > 0}, target, floor=0
        )

    plan[:] = [p for p in plan if p["genero"] != genero]

    g_stk = 0
    for color in colors:
        cm = color_meta[color]
        talla_objs = []
        for (c, talla), qty in sorted(allocated.items(), key=lambda x: (-x[1], x[0][1])):
            if c != color or qty <= 0:
                continue
            m = meta[(color, talla)]
            t_obj = {
                "talla": str(talla),
                "v_mes_base": m["v_mes_base"],
                "v_mes": m["v_mes"],
                "stk": m["stk"],
                "stk_taller": m["stk_taller"],
                "cob": m["cob"],
                "produce": qty,
                "produce_min": qty,
                "produce_max": min_max_qty(qty)[1],
                "curve_pct": m["curve_pct"],
                "urgente": m["urgente"],
                "store_split": {},
                "store_split_max": {},
            }
            set_variant_qty(t_obj, qty, shares)
            talla_objs.append(t_obj)
        c_min = sum(t["produce_min"] for t in talla_objs)
        plan.append({
            "genero": genero,
            "color": color,
            "color_pct": cm["color_pct"],
            "sales_pct": cm["sales_share"],
            "v_mes_base": cm["v_mes_base"],
            "v_mes": cm["v_mes"],
            "stk": cm["stk"],
            "stk_taller": cm["stk_taller"],
            "cob": cm["cob"],
            "produce": c_min,
            "produce_min": c_min,
            "produce_max": sum(t["produce_max"] for t in talla_objs),
            "tallas": sorted(talla_objs, key=lambda x: x["produce_min"], reverse=True),
            "store_split": distribute_units(c_min, shares, ALL_DIST_STORES),
        })
        g_stk += cm["stk"]

    g_vel_base = weighted_velocity(g_vel)
    g_vel_adj = g_vel_base * hs
    summary = {
        "v_mes_base": round(g_vel_base, 1),
        "v_mes": round(g_vel_adj, 1),
        "stk": g_stk,
        "produce": 0,
        "produce_max": 0,
        "cob": round(g_stk / g_vel_adj, 1) if g_vel_adj > 0 else 99.0,
    }
    rango_slice: dict = {"shares": shares, "vel_mes": round(g_vel_adj, 1)}
    rebuild_gender_aggregates(plan, {genero: summary}, {genero: rango_slice}, genero, shares)
    return summary, rango_slice


def build_data(sales: pd.DataFrame, inv: pd.DataFrame) -> dict:
    retail_sales = sales[sales["tienda"].isin(RETAIL_STORES + ["WEB", "PEDIDOS", "CORPORATIVO", "VELA", "TOLON"])].copy()

    meses_sorted = sorted(retail_sales[["year", "mes_num", "mes"]].drop_duplicates().values.tolist())
    meses_order = [m[2] for m in meses_sorted]
    meses_labels = []
    for _, mn, slug in meses_sorted:
        parts = slug.split("-")
        meses_labels.append(f"{MESES_SHORT[parts[0]].title()} {parts[1][-2:]}")

    meses_und = retail_sales.groupby("mes")["v"].sum().to_dict()
    total = int(retail_sales["v"].sum())

    # var_pct: last full month vs previous
    monthly = retail_sales.groupby("mes")["v"].sum()
    ordered = [m for _, _, m in meses_sorted]
    var_pct = 0.0
    if len(ordered) >= 2:
        prev, last = monthly.get(ordered[-2], 0), monthly.get(ordered[-1], 0)
        if prev > 0:
            var_pct = round((last - prev) / prev * 100, 1)

    raw_rows = []
    for _, r in retail_sales.iterrows():
        raw_rows.append({
            "tienda": r["tienda"],
            "genero": r["genero"],
            "color": r["color"],
            "talla": r["talla"],
            "mes": r["mes"],
            "v": int(r["v"]),
        })

    stock = defaultdict(float)
    stock_by_store = defaultdict(lambda: defaultdict(float))
    for _, r in inv.iterrows():
        key = f"{r['color']}/{r['talla']}/{r['genero']}"
        stock[key] += r["v"]
        stock_by_store[r["tienda"]][key] += r["v"]

    stock_dict = {k: int(round(v)) for k, v in stock.items()}
    sbs = {store: {k: int(round(v)) for k, v in items.items()} for store, items in stock_by_store.items()}

    store_totals = {s: sum(items.values()) for s, items in sbs.items()}
    stores_order = sorted(store_totals.keys(), key=lambda s: (-store_totals[s], s))
    if "TALLER" in stores_order:
        stores_order = [s for s in stores_order if s != "TALLER"] + ["TALLER"]

    tiendas_list = ["CERRO VERDE", "CHACAO", "GRAND", "GRIE", "SAMBIL", "TOLON", "VELA", "WEB"]
    colores = sorted({r["color"] for r in raw_rows})
    generos = ["CAB", "DAMA", "KIDS"]

    line_order = {}
    for g in generos:
        gdf = retail_sales[retail_sales["genero"] == g]
        vel_base = weighted_velocity(gdf)
        vel_adj = vel_base * HIGH_SEASON_FACTOR[g]
        line_order[g] = {"m1": int(round(vel_adj)), "m2": int(round(vel_adj * 1.10))}

    production_plan, summary_genero, rango_data = build_production_plan(retail_sales, inv, sales)
    excel_context = build_excel_context(retail_sales, inv, summary_genero, sbs, meses_labels)

    return {
        "nombre": "MAR ORIGINAL",
        "periodo": f"{meses_labels[0]} — {meses_labels[-1]}",
        "total": total,
        "var_pct": var_pct,
        "es_parcial": False,
        "n_sem": len(meses_order),
        "meses_order": meses_order,
        "meses_labels": meses_labels,
        "meses_und": {k: int(v) for k, v in meses_und.items()},
        "lineas": generos,
        "tiendas_list": tiendas_list,
        "filtros": {
            "tiendas": tiendas_list + ["PEDIDOS", "CORPORATIVO"],
            "generos": generos,
            "colores": colores,
            "meses": meses_order,
        },
        "raw_rows": raw_rows,
        "stock": stock_dict,
        "stock_total": int(sum(stock_dict.values())),
        "stock_by_store": sbs,
        "stores_order": stores_order,
        "stock_taller": int(sum(sbs.get("TALLER", {}).values())),
        "line_order": line_order,
        "method": "sales_prop_color_talla",
        "high_season_factor": max(HIGH_SEASON_FACTOR.values()),
        "gender_season_factors": HIGH_SEASON_FACTOR,
        "tolon_boost": TOLON_BOOST,
        "velocity_months": VELOCITY_PERIODS,
        "velocity_months_label": "May–Ago 26 (ponderado)",
        "velocity_months_count": len(VELOCITY_PERIODS),
        "coverage_months": max(COVERAGE_MONTHS.values()),
        "coverage_by_gender": COVERAGE_MONTHS,
        "safety_buffer": max(SAFETY_BUFFER.values()),
        "safety_by_gender": SAFETY_BUFFER,
        "new_stores": ["VELA", "BARQUISIMETO"],
        "production_plan": production_plan,
        "summary_genero": summary_genero,
        "rango_data": rango_data,
        "target_produce_min": TARGET_PRODUCE_MIN,
        "excel_context": excel_context,
    }


def build_production_plan(
    sales: pd.DataFrame, inv: pd.DataFrame, all_sales: pd.DataFrame
) -> tuple[list, dict, dict]:
    vel_sales = sales[sales["mes"].isin(VELOCITY_PERIODS)]
    plan: list = []
    summary: dict = {}
    rango: dict = {}

    for genero in ["CAB", "DAMA", "KIDS"]:
        g_vel = vel_sales[vel_sales["genero"] == genero]
        shares = store_weights(g_vel.groupby("tienda")["v"].sum().to_dict())
        target = TARGET_PRODUCE_MIN[genero]
        summary[genero], rango[genero] = build_gender_plan_proportional(
            plan, genero, g_vel, all_sales, inv, shares, target
        )

    return plan, summary, rango


def calibrate_gender_targets(
    plan: list, summary: dict, rango: dict, genero: str, target: int
) -> None:
    """Scale to target while keeping every active color×talla >= MIN_VARIANT."""
    items = [p for p in plan if p["genero"] == genero]
    shares = rango[genero]["shares"]
    floor = MIN_VARIANT[genero]
    refs: list[tuple[dict, dict]] = []
    for item in items:
        for t in item["tallas"]:
            set_variant_qty(t, max(t["produce_min"], floor), shares)
            refs.append((item, t))

    current = sum(t["produce_min"] for _, t in refs)
    if current <= 0:
        return

    if current < target:
        floats = [t["produce_min"] * target / current for _, t in refs]
        ints = [int(math.floor(f)) for f in floats]
        diff = target - sum(ints)
        if diff > 0:
            order = sorted(range(len(floats)), key=lambda i: floats[i] - ints[i], reverse=True)
            for i in range(diff):
                ints[order[i % len(order)]] += 1
        for (_, t), qty in zip(refs, ints):
            set_variant_qty(t, max(qty, floor), shares)
    elif current > target:
        reducible = [max(0, t["produce_min"] - floor) for _, t in refs]
        pool = sum(reducible)
        excess = current - target
        if pool <= 0:
            pass
        elif excess >= pool:
            for (_, t), _ in zip(refs, reducible):
                set_variant_qty(t, floor, shares)
        else:
            cuts = [r * excess / pool for r in reducible]
            new_vals = []
            for (_, t), r, cut in zip(refs, reducible, cuts):
                new_vals.append(max(floor, t["produce_min"] - int(math.floor(cut))))
            diff = target - sum(new_vals)
            if diff > 0:
                order = sorted(
                    range(len(new_vals)),
                    key=lambda i: (refs[i][1]["produce_min"] - new_vals[i], new_vals[i]),
                    reverse=True,
                )
                for i in range(diff):
                    new_vals[order[i % len(order)]] += 1
            elif diff < 0:
                order = sorted(range(len(new_vals)), key=lambda i: new_vals[i] - floor, reverse=True)
                for i in range(-diff):
                    idx = order[i % len(order)]
                    if new_vals[idx] > floor:
                        new_vals[idx] -= 1
            for (_, t), qty in zip(refs, new_vals):
                set_variant_qty(t, max(qty, floor), shares)

    rebuild_gender_aggregates(plan, summary, rango, genero, shares)


GENDER_XL = {"CAB": "CABALLERO", "DAMA": "DAMA", "KIDS": "KIDS"}
RESUMEN_STORES = [
    ("SAMBIL", "SAMBIL VALENCIA"),
    ("GRIE", "GRIETA"),
    ("CHACAO", "SAMBIL CHACAO"),
    ("CERRO VERDE", "CERRO VERDE"),
    ("GRAND", "GRAND PLAZA"),
    ("VELA", "LA VELA (Margarita)"),
    ("TOLON", "TOLÓN"),
    ("WEB", "WEB / PEDIDOS (online)"),
    ("BARQUISIMETO", "BARQUISIMETO (nueva)"),
]
STOCK_COVERAGE_STORES = [
    ("SAMBIL", "SAMBIL VALENCIA"),
    ("GRIE", "GRIETA"),
    ("CHACAO", "SAMBIL CHACAO"),
    ("CERRO VERDE", "CERRO VERDE"),
    ("GRAND", "GRAND PLAZA"),
    ("VELA", "LA VELA (Margarita)"),
    ("TOLON", "TOLÓN"),
    ("TALLER", "TALLER (buffer PT)"),
]


def _store_vel_base(g_vel: pd.DataFrame, store_key: str) -> float:
    if store_key == "VELA":
        return weighted_velocity(g_vel[g_vel["tienda"] == "GRIE"])
    if store_key == "BARQUISIMETO":
        parts = [
            weighted_velocity(g_vel[g_vel["tienda"] == "GRIE"]),
            weighted_velocity(g_vel[g_vel["tienda"] == "CHACAO"]),
            weighted_velocity(g_vel[g_vel["tienda"] == "TOLON"]),
        ]
        return sum(parts) / 3
    if store_key == "WEB":
        strongest = max(weighted_velocity(g_vel[g_vel["tienda"] == s]) for s in RETAIL_STORES)
        return strongest * WEB_STRONGEST_RATIO
    if store_key == "TOLON":
        return weighted_velocity(g_vel[g_vel["tienda"] == "TOLON"]) * TOLON_BOOST
    return weighted_velocity(g_vel[g_vel["tienda"] == store_key])


def build_excel_context(
    retail_sales: pd.DataFrame,
    inv: pd.DataFrame,
    summary_genero: dict,
    stock_by_store: dict,
    meses_labels: list[str],
) -> dict:
    vel_sales = retail_sales[retail_sales["mes"].isin(VELOCITY_PERIODS)]
    periodo = f"{meses_labels[0]}–{meses_labels[-1]}" if meses_labels else ""
    generos_ctx: dict = {}

    for genero in ["CAB", "DAMA", "KIDS"]:
        g_vel = vel_sales[vel_sales["genero"] == genero]
        hs = HIGH_SEASON_FACTOR[genero]
        cov = COVERAGE_MONTHS[genero]
        s = summary_genero[genero]
        store_rows = []
        for key, label in RESUMEN_STORES:
            base = _store_vel_base(g_vel, key)
            store_rows.append({
                "key": key,
                "label": label,
                "vel_base": round(base, 1),
                "vel_hs": round(base * hs, 1),
            })
        total_base = sum(r["vel_base"] for r in store_rows)
        total_hs = sum(r["vel_hs"] for r in store_rows)
        for r in store_rows:
            r["weight"] = round(r["vel_base"] / total_base, 4) if total_base else 0
        generos_ctx[genero] = {
            "label": GENDER_XL[genero],
            "store_rows": store_rows,
            "vel_base_total": round(total_base, 1),
            "vel_hs_total": round(total_hs, 1),
            "stock": s["stk"],
            "demand_min": round(s["v_mes_base"] * cov * 1.15, 1),
            "demand_max": round(s["v_mes"] * (cov + 0.5) * 1.20, 1),
            "produce_min": s["produce"],
            "produce_max": s["produce_max"],
            "hs_factor": hs,
            "coverage_min": cov,
            "coverage_max": round(cov + 0.5, 1),
            "safety_min": 0.15,
            "safety_max": 0.20,
        }

    vel_by_store = vel_sales.groupby("tienda")["v"].sum().to_dict()
    store_stock_rows = []
    for key, label in STOCK_COVERAGE_STORES:
        stk = int(sum(stock_by_store.get(key, {}).values()))
        if key == "TALLER":
            store_stock_rows.append({"label": label, "stock": stk, "vel_base": None, "coverage": None, "status": "Buffer operativo"})
            continue
        vel_b = vel_by_store.get(key, 0) / max(len(VELOCITY_PERIODS), 1)
        if key == "TOLON":
            vel_b *= TOLON_BOOST
        if key == "VELA":
            vel_b = vel_by_store.get("GRIE", 0) / max(len(VELOCITY_PERIODS), 1)
        cov_m = round(stk / vel_b, 1) if vel_b > 0 else 999
        if cov_m < 2:
            status = "CRÍTICO"
        elif cov_m < 3.5:
            status = "AJUSTADO"
        elif cov_m < 7:
            status = "SALUDABLE"
        else:
            status = "SOBRESTOCK"
        store_stock_rows.append({
            "label": label,
            "stock": stk,
            "vel_base": round(vel_b, 1),
            "coverage": cov_m,
            "status": status,
        })

    jun_ago = [m for m in vel_sales["mes"].unique() if m in VELOCITY_PERIODS]
    base_5 = vel_sales[vel_sales["tienda"].isin(RETAIL_STORES[:5])]["v"].sum() / max(len(jun_ago), 1)
    dic = int(retail_sales[retail_sales["mes"] == "diciembre-2025"]["v"].sum())

    return {
        "periodo": periodo,
        "generos": generos_ctx,
        "store_stock_rows": store_stock_rows,
        "season_ref": {"base_jun_ago": round(base_5, 0), "dic_2025": dic, "ratio": round(dic / base_5, 2) if base_5 else 0},
    }


def export_excel(data: dict, path: Path) -> None:
    summary = data["summary_genero"]
    rango = data["rango_data"]
    ctx = data["excel_context"]
    vel_label = data.get("velocity_months_label", "May–Ago 26")

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        wb = writer.book
        bold = wb.add_format({"bold": True})
        wrap = wb.add_format({"text_wrap": True})
        title = wb.add_format({"bold": True, "font_size": 14, "font_color": "#1F3864"})
        section = wb.add_format({"bold": True, "font_size": 11, "font_color": "#1F3864"})
        hdr = wb.add_format({"bold": True, "bg_color": "#4472C4", "font_color": "white", "border": 1})
        pct = wb.add_format({"num_format": "0.0%"})
        pct4 = wb.add_format({"num_format": "0.0000"})
        num = wb.add_format({"num_format": "#,##0"})
        dec = wb.add_format({"num_format": "0.0"})
        blue = wb.add_format({"bg_color": "#DDEBF7", "num_format": "#,##0", "border": 1})
        total_fmt = wb.add_format({"bold": True, "top": 2})

        # ── 1. Resumen ──
        ws = wb.add_worksheet("Resumen")
        ws.set_column("A:A", 42)
        ws.set_column("B:F", 16)
        row = 0
        ws.merge_range(row, 0, row, 5, "MAR ORIGINAL — PROYECCIÓN DE PRODUCCIÓN · CAB / DAMA / KIDS", title)
        row += 1
        ws.merge_range(
            row, 0, row, 5,
            f"Somos Cuadro · Logística e Inventarios · Ventas {ctx['periodo']} + inventario actual + colores activos para producción",
            wrap,
        )
        row += 2
        ws.merge_range(row, 0, row, 5, "CONSIDERACIONES APLICADAS", section)
        row += 1
        bullets = [
            "• LA VELA (Margarita): tienda nueva → proyectada con la misma velocidad que GRIETA.",
            f"• TOLÓN: velocidad reciente × {TOLON_BOOST} para subir su participación futura.",
            "• BARQUISIMETO: tienda nueva sin histórico → promedio de GRIETA, SAMBIL CHACAO y TOLÓN.",
            "• WEB/PEDIDOS: canal potenciado → 50% de la tienda física más fuerte.",
            f"• TEMPORADA ALTA: factor ×{max(HIGH_SEASON_FACTOR.values()):.2f} (CAB/DAMA ×1.60 · KIDS ×2.05).",
            "• Solo colores ACTIVOS para producción según catálogo Mar Original.",
            f"• Meta de producción: CAB {TARGET_PRODUCE_MIN['CAB']:,} · DAMA {TARGET_PRODUCE_MIN['DAMA']:,} · KIDS {TARGET_PRODUCE_MIN['KIDS']:,} und (mínimo compromiso).",
            "• CAB: sin 3XL ni 4XL en producción; 2XL con boost moderado (+22%).",
            "• DAMA: sin 2XL en producción; L con boost moderado (+22%).",
        ]
        for b in bullets:
            ws.merge_range(row, 0, row, 5, b, wrap)
            row += 1

        for genero in ["CAB", "DAMA", "KIDS"]:
            gc = ctx["generos"][genero]
            row += 1
            ws.merge_range(row, 0, row, 5, f"{gc['label']} — SUPUESTOS, VELOCIDAD Y CANTIDAD A PRODUCIR", section)
            row += 2
            ws.write(row, 0, "Factor temporada alta", bold)
            ws.write(row, 1, gc["hs_factor"])
            ws.write(row, 2, "Meses cobertura MÍN / MÁX", bold)
            ws.write(row, 3, gc["coverage_min"])
            ws.write(row, 4, gc["coverage_max"])
            row += 1
            ws.write(row, 0, f"Boost Tolón (×{TOLON_BOOST})", bold)
            ws.write(row, 1, TOLON_BOOST)
            ws.write(row, 2, "Stock seguridad MÍN / MÁX", bold)
            ws.write(row, 3, gc["safety_min"], pct)
            ws.write(row, 4, gc["safety_max"], pct)
            row += 2
            ws.write_row(row, 0, ["Tienda", "Vel. Base (u/mes)", "Vel. Temporada Alta", "Peso %"], hdr)
            row += 1
            for sr in gc["store_rows"]:
                ws.write(row, 0, sr["label"])
                ws.write(row, 1, sr["vel_base"], dec)
                ws.write(row, 2, sr["vel_hs"], dec)
                ws.write(row, 3, sr["weight"], pct4)
                row += 1
            ws.write(row, 0, "TOTAL RED", bold)
            ws.write(row, 1, gc["vel_base_total"], dec)
            ws.write(row, 2, gc["vel_hs_total"], dec)
            ws.write(row, 3, 1, pct4)
            row += 2
            ws.write(row, 0, "Stock actual (todas ubicaciones)", bold)
            ws.write(row, 1, gc["stock"], num)
            row += 1
            ws.write(row, 0, "Demanda teórica MÍNIMO", bold)
            ws.write(row, 1, gc["demand_min"], dec)
            row += 1
            ws.write(row, 0, "Demanda teórica MÁXIMO", bold)
            ws.write(row, 1, gc["demand_max"], dec)
            row += 1
            ws.write(row, 0, "PRODUCIR — MÍNIMO (meta de negocio)", bold)
            ws.write(row, 1, gc["produce_min"], blue)
            row += 1
            ws.write(row, 0, "PRODUCIR — MÁXIMO (meta de negocio)", bold)
            ws.write(row, 1, gc["produce_max"], blue)
            row += 1
            ws.merge_range(
                row, 0, row, 5,
                "↑ Meta definida por decisión de negocio — alimenta talla, color, tienda y tela.",
                wrap,
            )
            row += 1

        row += 1
        ws.merge_range(row, 0, row, 5, "RESUMEN — TOTAL A PRODUCIR POR GÉNERO", section)
        row += 1
        ws.write_row(row, 0, ["Género", "Vel. Base (u/mes)", "Vel. Temporada Alta", "Stock Actual", "PRODUCIR MÍN", "PRODUCIR MÁX"], hdr)
        row += 1
        totals = {"vb": 0, "vh": 0, "st": 0, "pm": 0, "px": 0}
        for genero in ["CAB", "DAMA", "KIDS"]:
            gc = ctx["generos"][genero]
            ws.write_row(row, 0, [gc["label"], gc["vel_base_total"], gc["vel_hs_total"], gc["stock"], gc["produce_min"], gc["produce_max"]])
            totals["vb"] += gc["vel_base_total"]
            totals["vh"] += gc["vel_hs_total"]
            totals["st"] += gc["stock"]
            totals["pm"] += gc["produce_min"]
            totals["px"] += gc["produce_max"]
            row += 1
        ws.write_row(row, 0, ["TOTAL GENERAL", totals["vb"], totals["vh"], totals["st"], totals["pm"], totals["px"]], total_fmt)

        row += 2
        sr = ctx["season_ref"]
        ws.merge_range(row, 0, row, 5, "TEMPORADA ALTA — REFERENCIA", section)
        row += 1
        ws.write(row, 0, "Promedio base reciente (5 tiendas)", bold)
        ws.write(row, 1, sr["base_jun_ago"], num)
        row += 1
        ws.write(row, 0, "Diciembre 2025 (pico real)", bold)
        ws.write(row, 1, sr["dic_2025"], num)
        row += 1
        ws.write(row, 0, "Ratio observado (Dic / base)", bold)
        ws.write(row, 1, sr["ratio"], dec)

        row += 2
        ws.merge_range(row, 0, row, 5, "STOCK ACTUAL Y COBERTURA POR TIENDA (todos los géneros)", section)
        row += 1
        ws.write_row(row, 0, ["Tienda", "Stock actual", "Vel. Base total (u/mes)", "Cobertura (meses)", "Estado"], hdr)
        row += 1
        for sr in ctx["store_stock_rows"]:
            ws.write(row, 0, sr["label"])
            ws.write(row, 1, sr["stock"], num)
            if sr["vel_base"] is None:
                ws.write(row, 2, "—")
                ws.write(row, 3, "—")
                ws.write(row, 4, sr["status"])
            else:
                ws.write(row, 2, sr["vel_base"], dec)
                ws.write(row, 3, sr["coverage"], dec)
                ws.write(row, 4, sr["status"])
            row += 1

        # ── 2. Producción por Talla ──
        ws = wb.add_worksheet("Producción por Talla")
        row = 0
        ws.write(row, 0, "MAR ORIGINAL — CANTIDADES POR TALLA (MÍN / MÁX)", title)
        row += 2
        for genero in ["CAB", "DAMA", "KIDS"]:
            rd = rango[genero]
            s = summary[genero]
            g_label = GENDER_XL[genero]
            ws.write(row, 0, f"{g_label} — CURVA DE TALLA (% sobre venta {vel_label})", section)
            row += 1
            ws.write_row(row, 0, ["Talla", "%", "Mínimo", "Máximo"], hdr)
            row += 1
            tallas = sort_tallas(genero, list(rd["talla_totals"].keys()))
            tmin = tmax = 0
            for t in tallas:
                td = rd["talla_totals"][t]
                if td["min"] <= 0 and td["max"] <= 0:
                    continue
                ws.write(row, 0, t)
                ws.write(row, 1, td["curve_pct"] / 100, pct4)
                ws.write(row, 2, td["min"], num)
                ws.write(row, 3, td["max"], num)
                tmin += td["min"]
                tmax += td["max"]
                row += 1
            ws.write(row, 0, "TOTAL", bold)
            ws.write(row, 1, 1 if tmin else 0, pct4)
            ws.write(row, 2, tmin, num)
            ws.write(row, 3, tmax, num)
            row += 2

        # ── 3. Cantidades por Colores ──
        ws = wb.add_worksheet("Cantidades por Colores")
        row = 0
        ws.write(row, 0, "MAR ORIGINAL — CANTIDADES POR COLOR (colores activos para producción)", title)
        row += 2
        for genero in ["CAB", "DAMA", "KIDS"]:
            rd = rango[genero]
            s = summary[genero]
            g_label = GENDER_XL[genero]
            ws.write(row, 0, f"{g_label} — CANTIDADES POR COLOR", section)
            row += 1
            ws.write_row(row, 0, ["Color", "%", "Mínimo", "Máximo"], hdr)
            row += 1
            cmin = cmax = 0
            color_rows_sorted = sorted(
                rd["color_rows"],
                key=lambda x: x.get("sales_pct", x["pct"] / 100 if isinstance(x["pct"], (int, float)) and x["pct"] > 1 else x.get("pct", 0)),
                reverse=True,
            )
            for cr in color_rows_sorted:
                if cr["min"] <= 0:
                    continue
                share = cr.get("sales_pct")
                if share is None:
                    share = cr["pct"] / 100 if cr["pct"] > 1 else cr["pct"]
                ws.write(row, 0, cr["color"])
                ws.write(row, 1, share, pct4)
                ws.write(row, 2, cr["min"], num)
                ws.write(row, 3, cr["max"], num)
                cmin += cr["min"]
                cmax += cr["max"]
                row += 1
            ws.write_row(row, 0, ["TOTAL", 1 if cmin else 0, cmin, cmax], total_fmt)
            row += 2

        # ── 4. Producción Color × Talla (matriz) ──
        ws = wb.add_worksheet("Producción Color × Talla")
        row = 0
        ws.write(row, 0, "MAR ORIGINAL — PRODUCCIÓN POR COLOR Y TALLA", title)
        row += 2
        for genero in ["CAB", "DAMA", "KIDS"]:
            rd = rango[genero]
            g_label = GENDER_XL[genero]
            tallas = sort_tallas(
                genero,
                list({t["talla"] for cr in rd["color_rows"] for t in cr["tallas"] if t["produce_min"] > 0}),
            )
            if not tallas:
                continue
            ws.write(row, 0, f"{g_label} — PRODUCCIÓN COLOR × TALLA", section)
            row += 1
            ws.write_row(row, 0, ["Color / Talla"] + tallas + ["Total"], hdr)
            row += 1
            color_rows_sorted = sorted(
                rd["color_rows"],
                key=lambda x: x.get("sales_pct", x["pct"] / 100 if x["pct"] > 1 else x.get("pct", 0)),
                reverse=True,
            )
            for cr in color_rows_sorted:
                if cr["min"] <= 0:
                    continue
                by_min = {t["talla"]: t["produce_min"] for t in cr["tallas"]}
                by_max = {t["talla"]: t["produce_max"] for t in cr["tallas"]}
                ws.write_row(row, 0, [f"{cr['color']} — Mín"] + [by_min.get(t, 0) for t in tallas] + [cr["min"]])
                row += 1
                ws.write_row(row, 0, [f"{cr['color']} — Máx"] + [by_max.get(t, 0) for t in tallas] + [cr["max"]])
                row += 1
            row += 1

        # ── 5. Compra de Tela ──
        ws = wb.add_worksheet("Compra de Tela")
        row = 0
        ws.write(row, 0, f"MAR ORIGINAL — COMPRA DE TELA {TELA_NOMBRE.upper()}", title)
        row += 1
        ws.write(row, 0, f"Consumo promedio por unidad (m/und) · SS tela +{int(TELA_SS * 100)}%", wrap)
        row += 2
        ws.write(row, 0, "Stock de seguridad tela (compra)", bold)
        ws.write(row, 1, TELA_SS, pct)
        row += 2
        ws.write(row, 0, "Género", bold)
        ws.write(row, 1, "Consumo (m/und)", bold)
        row += 1
        for g in ["CAB", "DAMA", "KIDS"]:
            ws.write_row(row, 0, [GENDER_XL[g], TELA_CONSUMO[g]])
            row += 1
        row += 1
        tela_hdr = ["Color", "Und Mín", "Und Máx", "Mts consumo Mín", "Mts consumo Máx", "Mts compra Mín (+SS)", "Mts compra Máx (+SS)"]
        for genero in ["CAB", "DAMA", "KIDS"]:
            cons = TELA_CONSUMO[genero]
            g_label = GENDER_XL[genero]
            ws.write(row, 0, f"{g_label} — COMPRA DE TELA POR COLOR (consumo {cons} m/und)", section)
            row += 1
            ws.write_row(row, 0, tela_hdr, hdr)
            row += 1
            gmin = gmax = gm_min = gm_max = gc_min = gc_max = 0
            color_rows_sorted = sorted(
                rango[genero]["color_rows"],
                key=lambda x: x.get("sales_pct", x["pct"] / 100 if x["pct"] > 1 else x.get("pct", 0)),
                reverse=True,
            )
            for cr in color_rows_sorted:
                if cr["min"] <= 0:
                    continue
                mts_min = cr["min"] * cons
                mts_max = cr["max"] * cons
                buy_min = mts_min * (1 + TELA_SS)
                buy_max = mts_max * (1 + TELA_SS)
                ws.write_row(
                    row, 0,
                    [cr["color"], cr["min"], cr["max"], round(mts_min, 1), round(mts_max, 1), round(buy_min, 1), round(buy_max, 1)],
                )
                gmin += cr["min"]
                gmax += cr["max"]
                gm_min += mts_min
                gm_max += mts_max
                gc_min += buy_min
                gc_max += buy_max
                row += 1
            ws.write_row(
                row, 0,
                [f"TOTAL {g_label}", gmin, gmax, round(gm_min, 1), round(gm_max, 1), round(gc_min, 1), round(gc_max, 1)],
                total_fmt,
            )
            row += 2

        # ── 6. Distribución por Tienda ──
        ws = wb.add_worksheet("Distribución por Tienda")
        row = 0
        ws.write(row, 0, "MAR ORIGINAL — DISTRIBUCIÓN POR TIENDA Y TALLA", title)
        row += 1
        ws.write(row, 0, "★ = tienda con velocidad proyectada/ajustada", bold)
        row += 2
        for genero in ["CAB", "DAMA", "KIDS"]:
            rd = rango[genero]
            tallas = sort_tallas(genero, list(rd["talla_totals"].keys()))
            active_tallas = [t for t in tallas if rd["talla_totals"][t]["min"] > 0]
            if not active_tallas:
                continue
            g_label = GENDER_XL[genero]
            ws.write(row, 0, f"{g_label} · {summary[genero]['produce']} – {summary[genero]['produce_max']} und", section)
            row += 1
            hdr_cells = ["Tienda"]
            for t in active_tallas:
                hdr_cells.extend([t, ""])
            hdr_cells.append("Tot")
            ws.write_row(row, 0, hdr_cells, hdr)
            row += 1
            sub = ["", ""]
            for _ in active_tallas:
                sub.extend(["Mín", "Máx"])
            sub.append("")
            ws.write_row(row, 0, sub, hdr)
            row += 1
            col_tot_min = defaultdict(int)
            col_tot_max = defaultdict(int)
            for store in ALL_DIST_STORES:
                st = rd["store_talla"][store]
                vals = [STORE_LABELS_XL[store]]
                st_min = st_max = 0
                for t in active_tallas:
                    mn = st.get(t, {}).get("min", 0)
                    mx = st.get(t, {}).get("max", 0)
                    vals.extend([mn, mx])
                    st_min += mn
                    st_max += mx
                    col_tot_min[t] += mn
                    col_tot_max[t] += mx
                if st_min <= 0:
                    continue
                vals.append(st_min)
                ws.write_row(row, 0, vals)
                row += 1
            dist_total = ["TOTAL"]
            gt_min = 0
            for t in active_tallas:
                dist_total.extend([col_tot_min[t], col_tot_max[t]])
                gt_min += col_tot_min[t]
            dist_total.append(gt_min)
            ws.write_row(row, 0, dist_total, bold)
            row += 2
            ws.write(row, 0, "Totales por tienda (Mín):", bold)
            row += 1
            ws.write_row(row, 0, ["Tienda", "Mín", "Vel. mensual proy."], hdr)
            row += 1
            vel_total = rd["vel_mes"]
            for store in ALL_DIST_STORES:
                st_min = sum(rd["store_talla"][store].get(t, {}).get("min", 0) for t in active_tallas)
                if st_min <= 0:
                    continue
                vel_proy = round(vel_total * rd["shares"].get(store, 0), 1)
                ws.write_row(row, 0, [STORE_LABELS_XL[store], st_min, vel_proy])
                row += 1
            row += 2

        # ── 7. Metodología ──
        ws = wb.add_worksheet("Metodología")
        ws.set_column("A:A", 100)
        row = 0
        ws.write(row, 0, "METODOLOGÍA — MAR ORIGINAL · PROYECCIÓN DE PRODUCCIÓN (CAB / DAMA / KIDS)", title)
        row += 2
        metodologia = [
            ("1. FUENTES DE DATOS", None),
            (f"• Ventas: {VENTAS_XLSX.name} — {ctx['periodo']} ({data['n_sem']} meses).", None),
            (f"• Inventario actual: {INV_XLSX.name} — {data['stock_total']:,} unidades.", None),
            (f"• Colores activos para producción: catálogo Mar Original ({len(COLORES_PRODUCCION['CAB'])} CAB · {len(COLORES_PRODUCCION['DAMA'])} DAMA · {len(COLORES_PRODUCCION['KIDS'])} KIDS).", None),
            (f"• Consumo tela {TELA_NOMBRE}: CAB {TELA_CONSUMO['CAB']} m/und · DAMA {TELA_CONSUMO['DAMA']} m/und · KIDS {TELA_CONSUMO['KIDS']} m/und.", None),
            ("2. VELOCIDAD BASE Y AJUSTES POR TIENDA", None),
            (f"• Ventana base: {vel_label} ponderado por tienda y género.", None),
            ("• LA VELA: tienda nueva → misma velocidad que GRIETA.", None),
            (f"• TOLÓN: velocidad × {TOLON_BOOST}.", None),
            ("• BARQUISIMETO: promedio GRIETA + CHACAO + TOLÓN.", None),
            ("• WEB/PEDIDOS: 50% de la tienda física más fuerte.", None),
            ("3. FACTOR DE TEMPORADA ALTA", None),
            (f"• CAB/DAMA × {HIGH_SEASON_FACTOR['CAB']} · KIDS × {HIGH_SEASON_FACTOR['KIDS']}.", None),
            (f"• Referencia Dic-25 vs base: ratio ≈ {ctx['season_ref']['ratio']}×.", None),
            ("4. CANTIDAD A PRODUCIR", None),
            (f"• Metas MÍN: CAB {TARGET_PRODUCE_MIN['CAB']:,} · DAMA {TARGET_PRODUCE_MIN['DAMA']:,} · KIDS {TARGET_PRODUCE_MIN['KIDS']:,} und.", None),
            (f"• Mix color × talla desde ventas {vel_label} (mismo criterio que curvas del Excel de referencia).", None),
            ("• CAB: color de producción 'Gris Claro' (agrupa ventas Gris + Gris Claro).", None),
            ("• CAB: sin 3XL/4XL · boost 2XL +22%. DAMA: sin 2XL · boost L +22%.", None),
            ("5. CURVAS DE TALLA, COLOR Y TELA", None),
            ("• Producción Color × Talla: matriz color × talla (Mín/Máx por color).", None),
            (f"• Compra de tela: metros = unidades × consumo género × (1 + {int(TELA_SS * 100)}% SS).", None),
            ("6. DISTRIBUCIÓN POR TIENDA", None),
            ("• Cada tienda recibe proporción igual a su peso en velocidad de red.", None),
        ]
        for heading, _ in metodologia:
            fmt = section if heading and heading[0].isdigit() else wrap
            ws.write(row, 0, heading, fmt)
            row += 1


def patch_html(template: str, data: dict) -> str:
    def _json_default(obj):
        if isinstance(obj, (bool,)):
            return obj
        if hasattr(obj, "item"):
            return obj.item()
        raise TypeError(f"Not serializable: {type(obj)}")

    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=_json_default)

    html = re.sub(r"const DATA = \{.*?\};", f"const DATA = {data_json};", template, count=1, flags=re.DOTALL)

    # Tabs: add inventario
    html = html.replace(
        '<button class="tab" onclick="st(\'tiendas\')">🏪 Tiendas</button>\n  <button class="tab" onclick="st(\'decisiones\')">💡 Decisiones</button>',
        '<button class="tab" onclick="st(\'tiendas\')">🏪 Tiendas</button>\n  <button class="tab" onclick="st(\'inventario\')">📦 Inventario</button>\n  <button class="tab" onclick="st(\'decisiones\')">💡 Decisiones</button>',
    )

    inv_section = """
<div class="sec" id="sec-inventario">
  <div class="tkpis" id="invKpis"></div>
  <div class="g1 card"><h3>📦 Inventario por Tienda</h3><div class="sub">Unidades disponibles en cada punto de venta y en taller (recién llegado, pendiente de distribuir) · clic en tienda para ver colores, clic en color para ver tallas</div><div id="invByStore" style="margin-top:10px"></div></div>
  <div class="g1 card"><h3>Color × Tienda (Inventario)</h3><div class="sub">Heatmap de stock disponible</div><div class="hmw" id="invColorTiendaHM"></div></div>
</div>
"""
    html = html.replace(
        '<div class="sec" id="sec-decisiones">',
        inv_section + '<div class="sec" id="sec-decisiones">',
    )

    html = html.replace(
        '<div class="sub">Orden sugerida − stock actual = producir · cobertura: <span id="propMesesLabel">2 meses</span></div>',
        '<div class="sub">Orden sugerida − stock actual = producir · cobertura: <span id="propMesesLabel">2 meses</span> · '
        '<span style="color:#f97316">VELA 1× GRIETA · TOLON ×1.45 · BARQ prom(G+Ch+T) · WEB 50% líder · mix proporcional color×talla · objetivo CAB 2650 · DAMA 2450 · KIDS 2950</span></div>',
    )

    html = html.replace(
        "if(tx.indexOf('Tienda')>=0)return'tiendas';return'decisiones';",
        "if(tx.indexOf('Tienda')>=0)return'tiendas';if(tx.indexOf('Inventario')>=0)return'inventario';return'decisiones';",
    )
    html = html.replace(
        "var TABS=['resumen','colores','tallas','tiendas','decisiones'];",
        "var TABS=['resumen','colores','tallas','tiendas','inventario','decisiones'];",
    )
    html = html.replace(
        "else if(n==='tiendas')rTiendas();else if(n==='decisiones')rDecisiones();",
        "else if(n==='tiendas')rTiendas();else if(n==='inventario')rInventario();else if(n==='decisiones')rDecisiones();",
    )

    # COLORES_DISP add KIDS
    html = re.sub(
        r"var COLORES_DISP=\{.*?\};",
        "var COLORES_DISP={"
        "CAB:{Aguamarina:1,'Amarillo Neón':1,'Azul Lavanda':1,'Azul Marino':1,'Azul Rey':1,Blanco:1,'Gris Claro':1,Negro:1,Rojo:1,'Verde Militar':1,Vinotinto:1},"
        "DAMA:{Aguamarina:1,'Amarillo Neón':1,'Azul Lavanda':1,'Azul Marino':1,Blanco:1,Lila:1,Negro:1,'Púrpura':1,Rojo:1,'Rosado Pastel':1,'Verde Militar':1,Vinotinto:1},"
        "KIDS:{Negro:1,'Azul Marino':1,Blanco:1,'Verde Militar':1,'Azul Lavanda':1,'Azul Rey':1,Aguamarina:1,Rojo:1,Lila:1,'Rosado Pastel':1,'Púrpura':1,'Amarillo Neón':1}"
        "};",
        html,
        count=1,
        flags=re.DOTALL,
    )

    # Replace getStoreWeights and store constants
    old_weights = re.search(
        r"// Store weights:.*?\nfunction getStoreWeights\(rows,l\)\{.*?\n\}",
        html,
        re.DOTALL,
    )
    new_weights = """// Store weights — VELA=GRIE, TOLON boost, BARQUISIMETO avg, WEB=50% líder
function getStoreWeights(rows,l){
  var byT={};rows.filter(function(r){return r.genero===l;}).forEach(function(r){byT[r.tienda]=(byT[r.tienda]||0)+r.v;});
  var grie=byT['GRIE']||0,chacao=byT['CHACAO']||0,tolon=byT['TOLON']||0;
  var strongest=Math.max(byT['SAMBIL']||0,grie,byT['CERRO VERDE']||0,chacao,byT['GRAND']||0,1);
  var tb=DATA.tolon_boost||1.45, w={};
  var stores=['SAMBIL','GRIE','CERRO VERDE','CHACAO','GRAND','TOLON'];
  for(var i=0;i<stores.length;i++){var base=byT[stores[i]]||0;if(stores[i]==='TOLON')base=Math.round(base*tb);w[stores[i]]=base;}
  w['VELA']=grie; w['BARQUISIMETO']=Math.round((grie+chacao+tolon)/3); w['WEB']=Math.round(strongest*0.5);
  var total=0;for(var k in w)total+=w[k];
  var shares={};for(var k in w)shares[k]=total>0?w[k]/total:0;
  return{weights:w,shares:shares,total:total};
}"""
    if old_weights:
        html = html[: old_weights.start()] + new_weights + html[old_weights.end() :]

    html = re.sub(
        r"var STORE_LABELS=\{.*?\};",
        "var STORE_LABELS={all:'📊 Producción Total',SAMBIL:'Sambil',GRIE:'Grieta','CERRO VERDE':'C.Verde',CHACAO:'Chacao',GRAND:'Grand',TOLON:'Tolón',VELA:'Vela ★',BARQUISIMETO:'Barquisimeto ★',WEB:'Web ★',TALLER:'Taller'};",
        html,
        count=1,
    )
    html = re.sub(
        r"var ALL_STORES=\[.*?\];",
        "var ALL_STORES=['SAMBIL','GRIE','CERRO VERDE','CHACAO','GRAND','TOLON','VELA','BARQUISIMETO','WEB'];",
        html,
        count=1,
    )

    # Update isNew checks in renderReabast and rDecisiones store tabs
    html = html.replace(
        "var isNew=_decTienda==='MARGARITA'||_decTienda==='TOLOM';",
        "var isNew=_decTienda==='VELA'||_decTienda==='BARQUISIMETO'||_decTienda==='WEB';",
    )
    html = html.replace(
        "var isNew=s==='MARGARITA'||s==='TOLOM';",
        "var isNew=s==='VELA'||s==='BARQUISIMETO'||s==='WEB';",
    )
    html = html.replace(
        "(store==='MARGARITA'?'2× capacidad GRIE':'1× capacidad CHACAO')",
        "(store==='VELA'?'1× Grieta':store==='BARQUISIMETO'?'Prom(Grieta+Chacao+Tolón)':'50% tienda líder')",
    )
    html = html.replace(
        "((_decTienda==='MARGARITA')?'2× GRIE':'1× CHACAO')",
        "(_decTienda==='VELA'?'1× Grieta':_decTienda==='BARQUISIMETO'?'Prom(G+Ch+T)':'50% líder')",
    )
    html = html.replace(
        "var isNew=store==='MARGARITA'||store==='TOLOM';",
        "var isNew=store==='VELA'||store==='BARQUISIMETO'||store==='WEB';",
    )
    html = html.replace(
        "'+ico+' '+store+'</div>'+(isNew?",
        "'+ico+' '+(STORE_LABELS[store]||store)+'</div>'+(isNew?",
    )

    # Insert rInventario before DECISIONES section if missing
    if "function rInventario" not in html:
        inv_js = """
// ══ INVENTARIO ══
var _invX={},_invColX={};
function toggleInv(uid){_invX[uid]=!_invX[uid];var d=document.getElementById(uid);if(!d)return;d.style.display=_invX[uid]?'block':'none';var arr=document.getElementById('arr_'+uid);if(arr)arr.style.transform=_invX[uid]?'rotate(90deg)':'rotate(0deg)';}
function toggleInvCol(uid){_invColX[uid]=!_invColX[uid];var d=document.getElementById(uid);if(!d)return;d.style.display=_invColX[uid]?'block':'none';}

function rInventario(){
  var sbs=DATA.stock_by_store||{},order=DATA.stores_order||Object.keys(sbs);
  var storeTotals={},grand=0;
  order.forEach(function(s){var t=0;Object.values(sbs[s]||{}).forEach(function(v){t+=v;});storeTotals[s]=t;grand+=t;});
  var tallerTotal=storeTotals['TALLER']||0,tiendaTotal=grand-tallerTotal;
  var colorGrand={};order.forEach(function(s){Object.entries(sbs[s]||{}).forEach(function(kv){var col=kv[0].split('/')[0];colorGrand[col]=(colorGrand[col]||0)+kv[1];});});
  var topColor=Object.entries(colorGrand).sort(function(a,b){return b[1]-a[1];})[0];
  document.getElementById('invKpis').innerHTML=
    '<div class="tkpi"><div class="tv">'+grand.toLocaleString()+'</div><div class="tl">Stock Total</div></div>'+
    '<div class="tkpi"><div class="tv">'+tiendaTotal.toLocaleString()+'</div><div class="tl">En Tiendas</div></div>'+
    '<div class="tkpi" style="border-color:#f97316"><div class="tv" style="color:#f97316">'+tallerTotal.toLocaleString()+'</div><div class="tl">🏭 En Taller</div></div>'+
    (topColor?'<div class="tkpi"><div class="tv"><span class="chip" style="background:'+cn(topColor[0])+'"></span>'+topColor[1].toLocaleString()+'</div><div class="tl">'+topColor[0]+'</div></div>':'');
  var h='';
  order.forEach(function(store){
    var isTaller=store==='TALLER';
    var data=sbs[store]||{};
    var cM={};Object.entries(data).forEach(function(kv){var p=kv[0].split('/'),col=p[0];cM[col]=(cM[col]||0)+kv[1];});
    var cA=Object.entries(cM).sort(function(a,b){return b[1]-a[1];});
    var colorItems=cA.map(function(ce){
      var col=ce[0],colV=ce[1];
      var tM={};Object.entries(data).forEach(function(kv){var p=kv[0].split('/');if(p[0]===col)tM[p[1]+' · '+p[2]]=(tM[p[1]+' · '+p[2]]||0)+kv[1];});
      var tA=Object.entries(tM).sort(function(a,b){return b[1]-a[1];});
      var tRows=tA.map(function(tv){return'<div style="display:flex;gap:6px;padding:2px 0;font-size:0.68rem"><div style="width:70px;font-weight:700;color:#c0c0e8">'+tv[0]+'</div><div style="color:var(--mu)">'+tv[1]+' und</div></div>';}).join('');
      var cUid='inv_'+store.replace(/[^a-z0-9]/gi,'_')+'_'+col.replace(/[^a-z0-9]/gi,'_');
      return'<div style="padding:2px 0"><div onclick="toggleInvCol(\\''+cUid+'\\')" style="display:flex;align-items:center;gap:6px;cursor:pointer;padding:3px 4px;border-radius:5px;font-size:0.73rem" onmouseover="this.style.background=\\'rgba(255,255,255,.04)\\'" onmouseout="this.style.background=\\'transparent\\'"><span style="width:8px;height:8px;border-radius:50%;background:'+cn(col)+'"></span><span style="flex:1;color:#e0e0f5">'+col+'</span><span style="color:var(--yw);font-weight:700;font-size:0.68rem">'+colV+'</span><span style="color:var(--ac);font-size:0.55rem">▶</span></div><div id="'+cUid+'" style="display:none;margin-left:16px;padding:2px 6px;border-left:2px solid '+cn(col)+'33">'+tRows+'</div></div>';
    }).join('');
    var sUid='inv_'+store.replace(/[^a-z0-9]/gi,'_');
    var ico=isTaller?'🏭':'🏪';
    var bg=isTaller?'rgba(249,115,22,.08)':'var(--s2)';
    var bdr=isTaller?'#f9731633':'var(--brd)';
    h+='<div style="background:'+bg+';border:1px solid '+bdr+';border-radius:12px;margin-bottom:10px"><div onclick="toggleInv(\\''+sUid+'\\')" style="display:flex;align-items:center;gap:10px;padding:14px 16px;cursor:pointer" onmouseover="this.style.opacity=\\'0.85\\'" onmouseout="this.style.opacity=\\'1\\'"><span id="arr_'+sUid+'" style="color:var(--ac);font-size:0.7rem;transition:transform .2s;flex-shrink:0">▶</span><div style="flex:1"><div style="font-family:var(--fh);font-weight:800;font-size:0.85rem">'+ico+' '+(STORE_LABELS[store]||store)+'</div>'+(isTaller?'<div style="font-size:0.6rem;color:#f97316">Recién llegado · pendiente por distribuir</div>':'')+'</div><div style="text-align:right"><div style="font-family:var(--fh);font-weight:800;color:'+(isTaller?'#f97316':'var(--yw)')+';font-size:1.1rem">'+storeTotals[store]+'</div><div style="font-size:0.6rem;color:var(--mu)">und</div></div></div>';
    h+='<div id="'+sUid+'" style="display:none;padding:0 16px 14px">'+(colorItems||'<div class="nodata">Sin stock</div>')+'</div></div>';
  });
  document.getElementById('invByStore').innerHTML=h;
  var colores=Object.keys(colorGrand).sort(function(a,b){return colorGrand[b]-colorGrand[a];});
  var allV=[];colores.forEach(function(c){order.forEach(function(s){var v=0;Object.entries(sbs[s]||{}).forEach(function(kv){if(kv[0].split('/')[0]===c)v+=kv[1];});allV.push(v);});});
  var mx=Math.max.apply(null,allV.concat([1]));
  document.getElementById('invColorTiendaHM').innerHTML=colores.length?'<table class="hmt"><thead><tr><th></th>'+order.map(function(s){return'<th>'+(STORE_LABELS[s]||s)+'</th>';}).join('')+'</tr></thead><tbody>'+colores.map(function(c){return'<tr><td class="rl"><span class="chip" style="background:'+cn(c)+'"></span>'+c+'</td>'+order.map(function(s){var v=0;Object.entries(sbs[s]||{}).forEach(function(kv){if(kv[0].split('/')[0]===c)v+=kv[1];});return'<td style="background:'+hb(v,mx)+';color:'+ht(v,mx)+'">'+(v||'—')+'</td>';}).join('')+'</tr>';}).join('')+'</tbody></table>':'<div class="nodata">Sin datos</div>';
}

"""
        html = html.replace("// ══ DECISIONES ══", inv_js + "// ══ DECISIONES ══", 1)

    # Remove stale hsFactorLabel updater if present
    html = html.replace(
        "  var hsLbl=document.getElementById('hsFactorLabel');if(hsLbl)hsLbl.textContent=DATA.high_season_factor||1.35;\n",
        "",
    )

    return html


def main() -> None:
    sales = load_sales()
    inv = load_inventory()
    data = build_data(sales, inv)

    template = TEMPLATE.read_text(encoding="utf-8")
    html = patch_html(template, data)
    OUT_HTML.write_text(html, encoding="utf-8")
    export_excel(data, OUT_XLSX)

    summary = data["summary_genero"]
    total_prod = sum(summary[g]["produce"] for g in summary)
    print(f"Dashboard: {OUT_HTML}")
    print(f"Excel: {OUT_XLSX}")
    print(f"Ventas total: {data['total']:,} | Stock: {data['stock_total']:,} | Producir: {total_prod:,}")
    for g in ["CAB", "DAMA", "KIDS"]:
        s = summary[g]
        print(f"  {g}: vel {s['v_mes']}/mes · stk {s['stk']} · cob {s['cob']}m · producir {s['produce']}")


if __name__ == "__main__":
    main()
