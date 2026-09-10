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
OUT_XLSX = ROOT / "MAR_ORIGINAL_RANGO_PRODUCCION.xlsx"

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
        "Gris", "Negro", "Rojo", "Verde Militar", "Vinotinto",
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
    if genero == "CAB" and c == "Gris Claro":
        return "Gris"
    return c


def production_color_variants(prod_color: str, genero: str) -> list[str]:
    """Inventory/sales aliases when looking up stock for a production color."""
    if genero == "CAB" and prod_color == "Gris":
        return ["Gris", "Gris Claro"]
    return [prod_color]


def remap_vel_colors(df: pd.DataFrame, genero: str) -> pd.DataFrame:
    out = df.copy()
    out["prod_color"] = out["color"].map(lambda c: to_production_color(c, genero))
    allowed = set(COLORES_PRODUCCION.get(genero, []))
    out = out[out["prod_color"].isin(allowed)]
    out["color"] = out["prod_color"]
    return out.drop(columns=["prod_color"])


def active_colors(genero: str, g_vel: pd.DataFrame, all_sales: pd.DataFrame) -> list[str]:
    """Only production-catalog colors, ordered by sales volume."""
    disp = COLORES_PRODUCCION.get(genero, [])
    g_mapped = remap_vel_colors(g_vel, genero)
    hist = remap_vel_colors(all_sales[all_sales["genero"] == genero], genero)
    sales_rank = g_mapped.groupby("color")["v"].sum().add(
        hist.groupby("color")["v"].sum(), fill_value=0
    ).to_dict()
    return sorted(disp, key=lambda c: sales_rank.get(c, 0), reverse=True)


def active_tallas(genero: str, g_vel: pd.DataFrame) -> list[str]:
    sold = set(g_vel["talla"].astype(str).unique())
    standard = set(TALLA_ORDER.get(genero, []))
    return sort_tallas(genero, list(sold | standard))


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
    """Build production from sales mix: color % × talla curve + stock gap, no flat blocks."""
    hs = HIGH_SEASON_FACTOR[genero]
    cov = COVERAGE_MONTHS[genero]
    safety = SAFETY_BUFFER[genero]
    floor = MIN_VARIANT[genero]
    low_color_floor = LOW_COLOR_FLOOR[genero]

    g_vel = remap_vel_colors(g_vel, genero)
    hist_vel = remap_vel_colors(all_sales[all_sales["genero"] == genero], genero)
    colors = active_colors(genero, g_vel, all_sales)
    tallas = active_tallas(genero, g_vel)
    color_sales = g_vel.groupby("color")["v"].sum().add(
        hist_vel.groupby("color")["v"].sum(), fill_value=0
    ).sort_values(ascending=False)
    color_total = color_sales.sum() or 1
    gender_talla = g_vel.groupby("talla")["v"].sum()
    gender_talla = (gender_talla / (gender_talla.sum() or 1)).to_dict()

    mix_weights: dict[tuple[str, str], float] = {}
    meta: dict[tuple[str, str], dict] = {}
    color_meta: dict[str, dict] = {}

    for color in colors:
        c_vel = g_vel[g_vel["color"] == color]
        tier = color_tier_multiplier(color, color_sales, genero)
        c_hist = hist_vel[hist_vel["color"] == color]["v"].sum()
        v_base = weighted_velocity(c_vel) if len(c_vel) else max(c_hist / max(len(VELOCITY_PERIODS), 1) * 0.12, 0.8)
        v_adj = v_base * hs * tier

        if len(c_vel):
            t_mix = c_vel.groupby("talla")["v"].sum()
            t_mix = (t_mix / (t_mix.sum() or 1)).to_dict()
        else:
            t_mix = gender_talla

        color_variants = production_color_variants(color, genero)
        stk_rows = inv[(inv["genero"] == genero) & (inv["color"].isin(color_variants))]
        stk = int(stk_rows["v"].sum())
        stk_taller = int(stk_rows[stk_rows["tienda"] == "TALLER"]["v"].sum())
        cob = round(stk / v_adj, 1) if v_adj > 0 else 99.0
        color_meta[color] = {
            "color_pct": round((color_sales.get(color, 0) / color_total * 100) if color in color_sales.index else 0.0, 1),
            "stk": stk,
            "stk_taller": stk_taller,
            "cob": cob,
            "v_mes_base": round(v_base, 1),
            "v_mes": round(v_adj, 1),
        }

        for talla in tallas:
            tdf = c_vel[c_vel["talla"] == talla] if len(c_vel) else pd.DataFrame()
            tv_base = weighted_velocity(tdf) if len(tdf) else v_base * t_mix.get(talla, 1 / len(tallas))
            tv_adj = tv_base * hs * tier
            inv_mask = (inv["genero"] == genero) & (inv["color"].isin(color_variants)) & (inv["talla"] == talla)
            t_stk = int(inv.loc[inv_mask, "v"].sum())
            t_stk_taller = int(inv.loc[inv_mask & (inv["tienda"] == "TALLER"), "v"].sum())
            t_cob = round(t_stk / tv_adj, 1) if tv_adj > 0 else 99.0
            need = max(0.0, tv_adj * cov - t_stk) * safety
            t_share = t_mix.get(talla, 1 / len(tallas))
            w = max(v_adj * t_share + need, 0.15 * t_share if color in COLORES_DISP.get(genero, []) else 0.05)
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

    allocated = allocate_by_weights(mix_weights, target, floor=floor)

    # Boost low colors: ensure each active color has varied minimum total (not 7×3 flat)
    color_totals = defaultdict(int)
    for (color, _), qty in allocated.items():
        color_totals[color] += qty
    for color in colors:
        c_share = (color_sales.get(color, 0) / color_total) if color in color_sales.index else 0.0
        tier = color_tier_multiplier(color, color_sales, genero)
        min_color = max(
            floor * len(tallas),
            int(low_color_floor * tier * (0.55 + c_share * 8)),
        )
        if color_totals[color] >= min_color:
            continue
        deficit = min_color - color_totals[color]
        color_keys = [(color, t) for t in tallas]
        sub_w = {k: mix_weights[k] for k in color_keys}
        sub_alloc = allocate_by_weights(sub_w, deficit, floor=0)
        for k, add in sub_alloc.items():
            allocated[k] = allocated.get(k, 0) + add
            color_totals[color] += add

    total_now = sum(allocated.values())
    if total_now != target:
        allocated = allocate_by_weights(
            {k: max(v, floor) for k, v in allocated.items()}, target, floor=floor
        )

    plan[:] = [p for p in plan if p["genero"] != genero]

    g_stk = 0
    for color in colors:
        cm = color_meta[color]
        talla_objs = []
        for talla in tallas:
            qty = allocated.get((color, talla), floor)
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
        "method": "proportional_mix_color_talla",
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


def _write_rows(ws, start_row: int, rows: list[list]) -> int:
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            ws.write(start_row + i, j, val)
    return start_row + len(rows)


def export_excel(data: dict, path: Path) -> None:
    summary = data["summary_genero"]
    rango = data["rango_data"]

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        wb = writer.book
        bold = wb.add_format({"bold": True})
        title = wb.add_format({"bold": True, "font_size": 13, "font_color": "#5b6af7"})
        hdr = wb.add_format({"bold": True, "bg_color": "#5b6af7", "font_color": "white"})
        pct = wb.add_format({"num_format": "0.0%"})
        num = wb.add_format({"num_format": "#,##0"})
        dec = wb.add_format({"num_format": "0.00"})

        # ── 1. Producción por Talla ──
        ws = wb.add_worksheet("Producción por Talla")
        row = 0
        ws.write(row, 0, "MAR ORIGINAL — CANTIDADES POR TALLA (MÍN / MÁX)", title)
        row += 2
        for genero in ["CAB", "DAMA", "KIDS"]:
            rd = rango[genero]
            s = summary[genero]
            ws.write(row, 0, f"{genero} · Rotación ajustada {s['v_mes']}/mes · Tela {TELA_NOMBRE} · consumo {TELA_CONSUMO[genero]} m/pieza", bold)
            row += 2
            ws.write_row(row, 0, ["Talla", "Curva %", "Mínimo", "Máximo"], hdr)
            row += 1
            tallas = sort_tallas(genero, list(rd["talla_totals"].keys()))
            tmin = tmax = 0
            for t in tallas:
                td = rd["talla_totals"][t]
                if td["min"] <= 0 and td["max"] <= 0:
                    continue
                ws.write_row(row, 0, [t, td["curve_pct"] / 100, td["min"], td["max"]])
                tmin += td["min"]
                tmax += td["max"]
                row += 1
            ws.write_row(row, 0, ["TOTAL", "", tmin, tmax], bold)
            row += 3

        # ── 2. Cantidades por Colores ──
        ws = wb.add_worksheet("Cantidades por Colores")
        row = 0
        ws.write(row, 0, "CANTIDADES POR COLORES — MAR ORIGINAL", title)
        row += 2
        for genero in ["CAB", "DAMA", "KIDS"]:
            rd = rango[genero]
            s = summary[genero]
            tallas = sort_tallas(genero, list({t for cr in rd["color_rows"] for t in [x["talla"] for x in cr["tallas"]]}))
            ws.write(row, 0, f"MAR ORIGINAL {genero} · Rango {s['produce']} – {s['produce_max']} und", bold)
            row += 1
            ws.write(row, 0, "MÍNIMO — compromiso", bold)
            row += 1
            hdr_row = ["Color", "%"] + tallas + ["Tot"]
            ws.write_row(row, 0, hdr_row, hdr)
            row += 1
            for cr in rd["color_rows"]:
                if cr["min"] <= 0:
                    continue
                by_t = {t["talla"]: t["produce_min"] for t in cr["tallas"]}
                ws.write_row(row, 0, [cr["color"], cr["pct"] / 100] + [by_t.get(t, 0) for t in tallas] + [cr["min"]])
                row += 1
            row += 1
            ws.write(row, 0, "MÁXIMO — techo", bold)
            row += 1
            ws.write_row(row, 0, hdr_row, hdr)
            row += 1
            for cr in rd["color_rows"]:
                if cr["max"] <= 0:
                    continue
                by_t = {t["talla"]: t["produce_max"] for t in cr["tallas"]}
                ws.write_row(row, 0, [cr["color"], cr["pct"] / 100] + [by_t.get(t, 0) for t in tallas] + [cr["max"]])
                row += 1
            row += 2

        # ── 3. Producción Color × Talla ──
        ws = wb.add_worksheet("Producción Color × Talla")
        row = 0
        ws.write(row, 0, "MAR ORIGINAL — PRODUCCIÓN POR COLOR Y TALLA", title)
        row += 2
        for genero in ["CAB", "DAMA", "KIDS"]:
            ws.write(row, 0, f"{genero}", bold)
            row += 1
            for cr in rango[genero]["color_rows"]:
                if cr["min"] <= 0:
                    continue
                ws.write(row, 0, f"{cr['color']} ({cr['pct']}%)", bold)
                row += 1
                ws.write_row(row, 0, ["Talla", "Mín", "Máx", "Vel/mes", "Stock", "Cob (m)"], hdr)
                row += 1
                for t in cr["tallas"]:
                    if t["produce_min"] <= 0:
                        continue
                    ws.write_row(row, 0, [t["talla"], t["produce_min"], t["produce_max"], t["v_mes"], t["stk"], t["cob"]])
                    row += 1
                ws.write_row(row, 0, ["TOTAL color", cr["min"], cr["max"], "", "", ""])
                row += 2
            row += 1

        # ── 4. Compra de Tela Jabón ──
        ws = wb.add_worksheet("Compra de Tela Jabón")
        row = 0
        ws.write(row, 0, f"MAR ORIGINAL — COMPRA DE TELA {TELA_NOMBRE.upper()}", title)
        row += 1
        ws.write(row, 0, f"Consumo promedio · CAB {TELA_CONSUMO['CAB']} m · DAMA {TELA_CONSUMO['DAMA']} m · KIDS {TELA_CONSUMO['KIDS']} m · SS tela +{int(TELA_SS*100)}%", bold)
        row += 2
        ws.write_row(row, 0, ["Género", "Color", "%", "Und Mín", "Und Máx", "Mts consumo Mín", "Mts consumo Máx", "Mts compra Mín (+SS)", "Mts compra Máx (+SS)"], hdr)
        row += 1
        totals = {"min_u": 0, "max_u": 0, "min_m": 0.0, "max_m": 0.0, "min_c": 0.0, "max_c": 0.0}
        for genero in ["CAB", "DAMA", "KIDS"]:
            cons = TELA_CONSUMO[genero]
            for cr in rango[genero]["color_rows"]:
                if cr["min"] <= 0:
                    continue
                mts_min = cr["min"] * cons
                mts_max = cr["max"] * cons
                buy_min = mts_min * (1 + TELA_SS)
                buy_max = mts_max * (1 + TELA_SS)
                ws.write_row(row, 0, [genero, cr["color"], cr["pct"] / 100, cr["min"], cr["max"], round(mts_min, 2), round(mts_max, 2), round(buy_min, 2), round(buy_max, 2)])
                totals["min_u"] += cr["min"]
                totals["max_u"] += cr["max"]
                totals["min_m"] += mts_min
                totals["max_m"] += mts_max
                totals["min_c"] += buy_min
                totals["max_c"] += buy_max
                row += 1
        ws.write_row(row, 0, ["TOTAL TELA", "", "", totals["min_u"], totals["max_u"], round(totals["min_m"], 2), round(totals["max_m"], 2), round(totals["min_c"], 2), round(totals["max_c"], 2)], bold)
        row += 3
        ws.write(row, 0, "Consumo unitario referencia (m/pieza)", bold)
        row += 1
        for g, c in TELA_CONSUMO.items():
            ws.write_row(row, 0, [g, c])
            row += 1

        # ── 5. Distribución por Tienda ──
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
            ws.write(row, 0, f"{genero} · {summary[genero]['produce']} – {summary[genero]['produce_max']} und", bold)
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
            total_row = ["TOTAL"]
            gt_min = gt_max = 0
            for t in active_tallas:
                total_row.extend([col_tot_min[t], col_tot_max[t]])
                gt_min += col_tot_min[t]
            total_row.append(gt_min)
            ws.write_row(row, 0, total_row, bold)
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
        "CAB:{Aguamarina:1,'Amarillo Neón':1,'Azul Lavanda':1,'Azul Marino':1,'Azul Rey':1,Blanco:1,Gris:1,Negro:1,Rojo:1,'Verde Militar':1,Vinotinto:1},"
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
