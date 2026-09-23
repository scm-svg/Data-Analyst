#!/usr/bin/env python3
"""Build EXPLORE PANTS dashboard + proyección Excel anclada a justificación Novaktex."""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = Path("/home/ubuntu/.cursor/projects/workspace/uploads")
_TEMPLATE_CANDIDATES = [
    UPLOADS / "dashbboard_explore_pantas_55b9.html",
    UPLOADS / "Explore_Pants_0b91.html",
    ROOT / "dash_explorepants.html",
    ROOT / "DASHBOARD_EXPLORE_PANTS.html",
]
TEMPLATE = next((p for p in _TEMPLATE_CANDIDATES if p.exists()), _TEMPLATE_CANDIDATES[1])
JUSTIF_XLSX = UPLOADS / "DATA_JUSTIFICACI_N_COMPRA_TELA_NOVAKTEX_REPEl_c4ef.xlsx"
OUT_HTML = ROOT / "DASHBOARD_EXPLORE_PANTS.html"
OUT_XLSX = ROOT / "EXPLORE_PANTS_Proyeccion_Produccion.xlsx"

MODELO = "EXPLORE PANTS"
TELA_NOMBRE = "Novaktex Repel"
TELA_UNIDAD = "kg"
TELA_SS = 0.20
# Rango producción MÍN / MÁX (temporada alta — ref. Short Playa)
HIGH_SEASON_FACTOR = 1.2

# Consumo referencial (tela ya comprada — NO define las und a producir)
TELA_CONSUMO = {"CAB": 0.30, "DAMA": 0.25, "KIDS": 0.22}  # KIDS ligeramente sobre 0.20

# Meta explícita KIDS (resto CAB/DAMA se reparte por ventas)
KIDS_TARGET_MIN = 550
KIDS_TARGET_MAX = 620
KIDS_TARGET = 585  # centro del rango pedido

PRODUCTION_EXCLUDE_TALLAS: dict[str, set[str]] = {
    "CAB": {"3XL"},
    "DAMA": {"2XL"},
    "KIDS": {"1", "14"},
}

KIDS_FULL_CURVE_COLORS = {"Gris Oscuro", "Azul Marino"}
KIDS_STD_TALLAS = ["2", "4", "6", "8", "10", "12"]

# CAB / DAMA — ajuste manual aprobado (color × talla)
MANUAL_CAB_DAMA_TALLAS: dict[str, dict[str, dict[str, int]]] = {
    "CAB": {
        "Negro": {"S": 41, "M": 102, "L": 103, "XL": 60, "2XL": 16},
        "Kaki": {"S": 44, "M": 92, "L": 85, "XL": 51, "2XL": 11},
        "Gris Oscuro": {"S": 46, "M": 87, "L": 94, "XL": 44, "2XL": 4},
        "Verde Militar": {"S": 9, "M": 25, "L": 26, "XL": 13, "2XL": 13},
        "Azul Marino": {"S": 23, "M": 66, "L": 64, "XL": 35, "2XL": 35},
    },
    "DAMA": {
        "Negro": {"XS": 45, "S": 83, "M": 94, "L": 55, "XL": 51},
        "Kaki": {"XS": 38, "S": 86, "M": 104, "L": 63, "XL": 43},
        "Gris Oscuro": {"XS": 31, "S": 67, "M": 77, "L": 48, "XL": 41},
        "Azul Marino": {"XS": 23, "S": 38, "M": 66, "L": 30, "XL": 34},
        "Verde Militar": {"XS": 10, "S": 16, "M": 19, "L": 14, "XL": 10},
    },
}

# Al cuadrar kg Explore: recortar primero Kaki CAB/DAMA
FABRIC_TRIM_ORDER: list[tuple[str, str]] = [
    ("CAB", "Kaki"),
    ("DAMA", "Kaki"),
    ("CAB", "Azul Marino"),
    ("DAMA", "Azul Marino"),
    ("CAB", "Gris Oscuro"),
    ("DAMA", "Gris Oscuro"),
    ("CAB", "Verde Militar"),
    ("DAMA", "Verde Militar"),
    ("CAB", "Negro"),
    ("DAMA", "Negro"),
]
# Gris KIDS: ventas históricas muy bajas — piso operativo (7 tallas × curva dashboard)
KIDS_GRIS_MIN_UNITS = 48
KIDS_FULL_CURVE_IDEAL_FACTOR = 0.82
KIDS_TALLA_WEIGHT_MIN_SALES = 30  # bajo esto, curva talla del género (dashboard)
KIDS_KAKI_MIN_TALLAS = 6  # presencia mínima en tallas 2–12
KIDS_KAKI_BOOST = 1.22  # un poco sobre % ventas dashboard
KIDS_KAKI_EXTRA_UND = 10  # und adicionales vs reparto puro ventas

# ── Fuente de verdad: justificación compra tela (Explore Pants) ──
PRODUCE_TOTAL = 2900  # meta Explore Pants con tela en almacén
DEMAND_JUL_DEC = 2228
STOCK_REF = 2988
STOCK_TIENDAS_REF = 1636
STOCK_TALLER_REF = 1352

# kg en almacén (existencias reales TH/Alm. Materia Prima)
TELA_KG_EXISTENCIA = {
    "Azul Marino": 159.9089,
    "Gris Oscuro": 280.4378,
    "Negro": 317.7556,
    "Verde Militar": 58.84222,
    "Kaki": 168.8911,
}
TELA_KG_TOTAL = sum(TELA_KG_EXISTENCIA.values())

# Referencia pedido original (justificación histórica)
TELA_KG_PEDIDO_REF = {
    "Negro": 414.0,
    "Gris Oscuro": 361.0,
    "Kaki": 157.0,
    "Azul Marino": 91.0,
    "Verde Militar": 66.0,
}
COLOR_PURCHASE_SHARE = {c: kg / sum(TELA_KG_PEDIDO_REF.values()) for c, kg in TELA_KG_PEDIDO_REF.items()}

# Short Sport R1 — solo Negro y Gris Oscuro (CAB / DAMA)
SHORTS_MODELO = "SHORT SPORT R1"
SHORTS_COLORES = ["Negro", "Gris Oscuro"]
SHORTS_TARGET = 1550  # meta fija (resto de tela → Explore Pants)
SHORTS_TARGET_MIN = SHORTS_TARGET
SHORTS_CONSUMO = {"CAB": 0.14, "DAMA": 0.12}
SHORTS_GENEROS = ["CAB", "DAMA"]
CAB_2XL_BOOST = 2.8  # ventas 2XL bajas — refuerzo para presencia en producción
CAB_2XL_MIN_COLOR_UNITS = 40  # und mínimas por color para forzar ≥1 en 2XL
CAB_NEGRO_MIN_LEAD_DAMA = 3  # und Negro CAB sobre DAMA cuando kg lo permite

ORDEN1_ITEMS = [
    ("Gris Oscuro — TODO (Explore + Shorts)", 361.2, "CRÍTICA"),
    ("Tela de Shorts — Negro y Azul (completa)", 125.1, "CRÍTICA"),
    ("Negro Explore — mitad", 157.0, "ALTA"),
    ("Kaki Explore — parte", 62.8, "MEDIA"),
]
ORDEN1_SUBTOTAL = 706.1
ORDEN2_ITEMS = [
    ("Negro Explore — la otra mitad", 157.0, "BAJO"),
    ("Kaki Explore — resto", 94.2, "BAJO"),
    ("Verde Militar — TODO", 65.6, "BAJO"),
    ("Azul Marino Explore — TODO", 65.5, "BAJO"),
]
ORDEN2_SUBTOTAL = 382.3
TELA_PEDIDO_TOTAL = 1088.4

DEMAND_MONTHS = [
    ("Resto julio", 42),
    ("Agosto (E −20%)", 261),
    ("Septiembre (D −10%)", 308),
    ("Octubre (C normal)", 421),
    ("Noviembre (B +37%)", 598),
    ("Diciembre (B +37%)", 598),
]

# Dashboard usa "Gris"; justificación usa "Gris Oscuro"
COLOR_SALES_TO_PROD = {"Gris": "Gris Oscuro"}

COLORES_PRODUCCION = ["Negro", "Gris Oscuro", "Kaki", "Azul Marino", "Verde Militar"]

TALLA_ORDER = {
    "CAB": ["XS", "S", "M", "L", "XL", "2XL", "3XL"],
    "DAMA": ["XS", "S", "M", "L", "XL", "2XL"],
    "KIDS": ["2", "4", "6", "8", "10", "12", "14"],
}

GENDER_XL = {"CAB": "CABALLERO", "DAMA": "DAMA", "KIDS": "KIDS"}
GENEROS = ["CAB", "DAMA", "KIDS"]

RETAIL_STORES = ["SAMBIL", "GRIE", "CERRO VERDE", "CHACAO", "GRAND", "TOLON", "VELA", "WEB", "PEDIDOS"]
ALL_DIST_STORES = ["SAMBIL", "GRIE", "CERRO VERDE", "CHACAO", "GRAND", "TOLON", "VELA", "WEB", "PEDIDOS"]


def load_template_data() -> dict:
    html = TEMPLATE.read_text(encoding="utf-8")
    m = re.search(r"(?:var|const)\s+DATA\s*=\s*(\{.*?\});", html, re.DOTALL)
    if not m:
        raise RuntimeError("No DATA block in template")
    return json.loads(m.group(1))


def sales_df(data: dict) -> pd.DataFrame:
    rows = []
    for r in data["raw_rows"]:
        rows.append({**r, "modelo": r.get("modelo") or MODELO})
    df = pd.DataFrame(rows)
    df["prod_color"] = df["color"].map(lambda c: COLOR_SALES_TO_PROD.get(c, c))
    return df


def sort_tallas(genero: str, tallas: list[str]) -> list[str]:
    order = TALLA_ORDER.get(genero, [])
    return sorted(tallas, key=lambda t: (order.index(t) if t in order else 99, t))


def min_max_qty(qty: int) -> tuple[int, int]:
    if qty <= 0:
        return 0, 0
    return qty, int(math.ceil(qty * HIGH_SEASON_FACTOR))


def allocate_by_weights(weights: dict, target: int) -> dict:
    total_w = sum(weights.values())
    if total_w <= 0 or target <= 0:
        return {k: 0 for k in weights}
    keys = list(weights.keys())
    floats = [weights[k] / total_w * target for k in keys]
    ints = [int(math.floor(f)) for f in floats]
    diff = target - sum(ints)
    if diff > 0:
        order = sorted(range(len(keys)), key=lambda i: floats[i] - ints[i], reverse=True)
        for i in range(diff):
            ints[order[i % len(order)]] += 1
    return {keys[i]: ints[i] for i in range(len(keys))}


def store_weights(by_store: dict[str, float]) -> dict[str, float]:
    grie = by_store.get("GRIE", 0)
    weights = {}
    for s in ["SAMBIL", "GRIE", "CERRO VERDE", "CHACAO", "GRAND", "TOLON", "WEB", "PEDIDOS"]:
        weights[s] = by_store.get(s, 0)
    weights["VELA"] = grie * 1.5  # ref: VELA 1.5× GRIETA
    total = sum(weights.values()) or 1
    return {k: v / total for k, v in weights.items()}


def distribute_units(total: int, shares: dict[str, float], stores: list[str]) -> dict[str, int]:
    if total <= 0:
        return {s: 0 for s in stores}
    raw = {s: total * shares.get(s, 0) for s in stores}
    result = {s: int(math.floor(raw[s])) for s in stores}
    diff = total - sum(result.values())
    if diff > 0:
        order = sorted(stores, key=lambda s: raw[s] - result[s], reverse=True)
        for i in range(diff):
            result[order[i % len(order)]] += 1
    return result


def compute_explore_produce_total(df: pd.DataFrame, explore_budget: dict[str, float]) -> int:
    """Und Explore meta cuando shorts son fijos y se consume la tela disponible."""
    cab = float(df[df["genero"] == "CAB"]["v"].sum())
    dama = float(df[df["genero"] == "DAMA"]["v"].sum())
    kids = float(df[df["genero"] == "KIDS"]["v"].sum())
    tot = cab + dama + kids or 1.0
    kg_per_unit = (cab / tot) * TELA_CONSUMO["CAB"] + (dama / tot) * TELA_CONSUMO["DAMA"] + (
        kids / tot
    ) * TELA_CONSUMO["KIDS"]
    kg_explore = sum(explore_budget.get(c, 0.0) for c in COLORES_PRODUCCION)
    est = int(kg_explore / kg_per_unit) if kg_per_unit > 0 else PRODUCE_TOTAL
    return max(PRODUCE_TOTAL, est)


def gender_targets(df: pd.DataFrame, produce_total: int | None = None) -> dict[str, int]:
    """CAB/DAMA reparten el resto por ventas; KIDS meta fija."""
    total = produce_total or PRODUCE_TOTAL
    cab_sales = float(df[df["genero"] == "CAB"]["v"].sum())
    dama_sales = float(df[df["genero"] == "DAMA"]["v"].sum())
    remaining = total - KIDS_TARGET
    cd = allocate_by_weights({"CAB": cab_sales, "DAMA": dama_sales}, remaining)
    return {"CAB": cd["CAB"], "DAMA": cd["DAMA"], "KIDS": KIDS_TARGET}


def kg_needed_gc(gc: dict[tuple[str, str], int], color: str) -> float:
    return sum(gc.get((g, color), 0) * TELA_CONSUMO[g] for g in GENEROS)


def shorts_consumo_blend(df: pd.DataFrame) -> float:
    cab = float(df[df["genero"] == "CAB"]["v"].sum())
    dama = float(df[df["genero"] == "DAMA"]["v"].sum())
    total = cab + dama or 1.0
    return (cab / total) * SHORTS_CONSUMO["CAB"] + (dama / total) * SHORTS_CONSUMO["DAMA"]


def plan_shorts_r1(df: pd.DataFrame, shorts_total: int, kg_negro: float, kg_gris: float) -> dict:
    """Distribuye piezas Short R1 CAB/DAMA por color de tela."""
    cab = float(df[df["genero"] == "CAB"]["v"].sum())
    dama = float(df[df["genero"] == "DAMA"]["v"].sum())
    gshare = allocate_by_weights({"CAB": cab, "DAMA": dama}, shorts_total)

    blend = shorts_consumo_blend(df)
    inv_ng = TELA_KG_EXISTENCIA["Negro"] + TELA_KG_EXISTENCIA["Gris Oscuro"]
    share_negro = TELA_KG_EXISTENCIA["Negro"] / inv_ng
    kg_sn = kg_negro if kg_negro > 0 else (shorts_total * blend * share_negro)
    kg_sg = kg_gris if kg_gris > 0 else (shorts_total * blend - kg_sn)

    pieces_n = int(round(kg_sn / blend)) if blend else 0
    pieces_g = max(0, shorts_total - pieces_n)

    rows = []
    for color, pieces, kg_used in [
        ("Negro", pieces_n, kg_sn),
        ("Gris Oscuro", pieces_g, kg_sg),
    ]:
        if pieces <= 0:
            continue
        by_g = allocate_by_weights({"CAB": cab, "DAMA": dama}, pieces)
        rows.append({
            "color": color,
            "total": pieces,
            "CAB": by_g["CAB"],
            "DAMA": by_g["DAMA"],
            "kg": round(kg_used, 2),
        })

    return {
        "modelo": SHORTS_MODELO,
        "total": shorts_total,
        "consumo_blend_kg": round(blend, 4),
        "kg_total": round(kg_sn + kg_sg, 2),
        "rows": rows,
    }


def solve_fabric_split(df: pd.DataFrame) -> tuple[dict[str, float], dict, dict[tuple[str, str], int]]:
    """
    Reparte tela: Shorts R1 fijos (1550 und) Negro/Gris + Explore con el resto de kg.
    """
    blend = shorts_consumo_blend(df)
    inv = TELA_KG_EXISTENCIA
    inv_ng = inv["Negro"] + inv["Gris Oscuro"]
    shorts_total = SHORTS_TARGET
    kg_shorts = shorts_total * blend
    if kg_shorts >= inv_ng:
        shorts_total = max(1, int(inv_ng / blend) - 1)
        kg_shorts = shorts_total * blend

    share_n = inv["Negro"] / inv_ng
    kg_sn = kg_shorts * share_n
    kg_sg = kg_shorts - kg_sn
    explore_budget = {
        "Kaki": inv["Kaki"],
        "Azul Marino": inv["Azul Marino"],
        "Verde Militar": inv["Verde Militar"],
        "Negro": inv["Negro"] - kg_sn,
        "Gris Oscuro": inv["Gris Oscuro"] - kg_sg,
    }
    produce_total = compute_explore_produce_total(df, explore_budget)
    g_targets = gender_targets(df, produce_total)
    gc = fit_gc_to_budget(
        df, g_targets, explore_budget, fill_all_kg=True, produce_total=produce_total
    )
    shorts = plan_shorts_r1(df, shorts_total, kg_sn, kg_sg)
    return explore_budget, shorts, gc


def fit_gc_to_budget(
    df: pd.DataFrame,
    g_targets: dict[str, int],
    kg_budget: dict[str, float],
    *,
    fill_all_kg: bool = False,
    produce_total: int | None = None,
) -> dict[tuple[str, str], int]:
    """Ranking dashboard por género, tope = kg disponible para Explore por color."""
    meta_total = produce_total or PRODUCE_TOTAL

    def kg_cap(color: str) -> float:
        return kg_budget.get(color, 0.0)

    gc_f = ideal_gc_floats(df, g_targets)

    for _ in range(60):
        for color in COLORES_PRODUCCION:
            kg_max = kg_cap(color)
            kg_need = sum(gc_f[(g, color)] * TELA_CONSUMO[g] for g in GENEROS)
            if kg_need > kg_max and kg_need > 0:
                factor = kg_max / kg_need
                for genero in GENEROS:
                    gc_f[(genero, color)] *= factor
        for genero in GENEROS:
            row = sum(gc_f[(genero, c)] for c in COLORES_PRODUCCION)
            if row <= 0:
                continue
            factor = g_targets[genero] / row
            for color in COLORES_PRODUCCION:
                gc_f[(genero, color)] *= factor

    gc: dict[tuple[str, str], int] = {}
    for genero in GENEROS:
        weights = {c: gc_f[(genero, c)] for c in COLORES_PRODUCCION}
        allocated = allocate_by_weights(weights, g_targets[genero])
        for color in COLORES_PRODUCCION:
            gc[(genero, color)] = allocated.get(color, 0)

    for _ in range(800):
        over = False
        for color in COLORES_PRODUCCION:
            while kg_needed_gc(gc, color) > kg_cap(color) + 0.001:
                genero = max(
                    GENEROS,
                    key=lambda g: (gc.get((g, color), 0), TELA_CONSUMO[g]),
                )
                if gc.get((genero, color), 0) <= 0:
                    break
                gc[(genero, color)] -= 1
                over = True
        if not over:
            break

    target = meta_total if not fill_all_kg else sum(gc.values()) + 5000
    for _ in range(8000):
        if not fill_all_kg and sum(gc.values()) >= meta_total:
            break
        options: list[tuple[float, str, str]] = []
        for genero in GENEROS:
            for color in COLORES_PRODUCCION:
                if sales_weight_gc(df, genero, color) <= 0:
                    continue
                if gris_add_blocked_for_adults(gc, genero, color):
                    continue
                slack = kg_cap(color) - kg_needed_gc(gc, color)
                if slack + 0.001 >= TELA_CONSUMO[genero]:
                    options.append((gc_fill_priority(df, genero, color), genero, color))
        if not options:
            break
        options.sort(reverse=True)
        _, genero, color = options[0]
        gc[(genero, color)] = gc.get((genero, color), 0) + 1
        if fill_all_kg:
            continue
        if sum(gc.values()) > meta_total:
            break

    if fill_all_kg:
        gc = shift_gris_to_kids_floor(gc, kg_budget, df)

    if not fill_all_kg:
        while sum(gc.values()) > meta_total:
            options = [
                (sales_weight_gc(df, g, c), g, c)
                for g in GENEROS
                for c in COLORES_PRODUCCION
                if gc.get((g, c), 0) > 0
            ]
            options.sort()
            _, genero, color = options[0]
            gc[(genero, color)] -= 1

    for genero in GENEROS:
        diff = g_targets[genero] - sum(gc.get((genero, c), 0) for c in COLORES_PRODUCCION)
        for _ in range(abs(diff)):
            if diff > 0:
                options = [
                    (sales_weight_gc(df, genero, c), c)
                    for c in COLORES_PRODUCCION
                    if sales_weight_gc(df, genero, c) > 0
                    and kg_cap(c) - kg_needed_gc(gc, c) + 0.001 >= TELA_CONSUMO[genero]
                ]
                if not options:
                    break
                options.sort(reverse=True)
                gc[(genero, options[0][1])] = gc.get((genero, options[0][1]), 0) + 1
            else:
                options = [
                    (sales_weight_gc(df, genero, c), c)
                    for c in COLORES_PRODUCCION
                    if gc.get((genero, c), 0) > 0
                ]
                if not options:
                    break
                options.sort()
                gc[(genero, options[0][1])] -= 1

    if fill_all_kg:
        gc = shift_gris_to_kids_floor(gc, kg_budget, df)
        for _ in range(5000):
            options: list[tuple[float, str, str]] = []
            for genero in GENEROS:
                for color in COLORES_PRODUCCION:
                    if gris_add_blocked_for_adults(gc, genero, color):
                        continue
                    slack = kg_cap(color) - kg_needed_gc(gc, color)
                    if slack + 0.001 >= TELA_CONSUMO[genero]:
                        options.append((gc_fill_priority(df, genero, color), genero, color))
            if not options:
                break
            options.sort(reverse=True)
            _, genero, color = options[0]
            gc[(genero, color)] = gc.get((genero, color), 0) + 1

    gc = protect_kids_curve_colors(gc, df, kg_budget)
    for genero in GENEROS:
        for _ in range(3):
            gc = enforce_gender_color_ranking(gc, df, genero, kg_budget)
    gc = enforce_negro_cab_over_dama(gc, df, kg_budget)

    for _ in range(400):
        over = False
        for color in COLORES_PRODUCCION:
            cap = kg_budget.get(color, 0.0)
            while kg_needed_gc(gc, color) > cap + 0.001:
                options = [
                    (sales_weight_gc(df, g, color), g)
                    for g in GENEROS
                    if gc.get((g, color), 0) > 0
                ]
                if not options:
                    break
                options.sort()
                _, genero = options[0]
                gc[(genero, color)] -= 1
                over = True
        if not over:
            break

    return gc


def kg_budget_ok(gc: dict[tuple[str, str], int], kg_budget: dict[str, float]) -> bool:
    return all(
        kg_needed_gc(gc, c) <= kg_budget.get(c, 0) + 0.02 for c in COLORES_PRODUCCION
    )


def gc_fill_priority(df: pd.DataFrame, genero: str, color: str) -> float:
    """Mayor = preferir al rellenar kg (KIDS en Gris/Azul ahorra tela → más und)."""
    base = sales_weight_gc(df, genero, color)
    if genero == "CAB" and color == "Negro":
        base += 35_000
    if genero == "KIDS" and color in KIDS_FULL_CURVE_COLORS:
        base += 50_000
    if genero == "KIDS" and color == "Gris Oscuro":
        base += 20_000
    if genero == "KIDS" and color == "Kaki":
        base += 45_000
    return base


def enforce_negro_cab_over_dama(
    gc: dict[tuple[str, str], int],
    df: pd.DataFrame,
    kg_budget: dict[str, float],
) -> dict[tuple[str, str], int]:
    """Negro CAB por encima de Negro DAMA (und), sin romper kg."""
    for _ in range(800):
        cab_n = gc.get(("CAB", "Negro"), 0)
        dama_n = gc.get(("DAMA", "Negro"), 0)
        if cab_n >= dama_n + CAB_NEGRO_MIN_LEAD_DAMA:
            break
        moved = False
        if cab_n < dama_n:
            for dd in [
                c
                for c in sales_color_order(df, "DAMA")
                if c != "Negro" and gc.get(("DAMA", c), 0) > 0
            ]:
                trial = dict(gc)
                trial[("DAMA", "Negro")] -= 1
                trial[("DAMA", dd)] = trial.get(("DAMA", dd), 0) + 1
                if kg_budget_ok(trial, kg_budget):
                    gc = trial
                    moved = True
                    break
        if moved:
            continue
        cab_donors = [
            c
            for c in reversed(sales_color_order(df, "CAB"))
            if c != "Negro" and gc.get(("CAB", c), 0) > 0
        ]
        for cd in cab_donors:
            trial = dict(gc)
            trial[("CAB", "Negro")] = trial.get(("CAB", "Negro"), 0) + 1
            trial[("CAB", cd)] -= 1
            if trial[("CAB", cd)] < 0:
                continue
            if kg_budget_ok(trial, kg_budget):
                gc = trial
                moved = True
                break
        if not moved:
            break
    return gc


def best_cab_recipient_for_gris_swap(
    gc: dict[tuple[str, str], int],
    kg_budget: dict[str, float],
    kid_donor: str,
) -> dict[tuple[str, str], int] | None:
    """Mueve 1 und Gris CAB→KIDS manteniendo totales por género."""
    best: dict[tuple[str, str], int] | None = None
    best_slack = -1.0
    for cab_hi in COLORES_PRODUCCION:
        if cab_hi == "Gris Oscuro":
            continue
        trial = quad_swap_gc(
            gc,
            kg_budget,
            [
                ("KIDS", "Gris Oscuro", 1),
                ("KIDS", kid_donor, -1),
                ("CAB", "Gris Oscuro", -1),
                ("CAB", cab_hi, 1),
            ],
        )
        if not trial:
            continue
        slack = min(
            kg_budget.get(c, 0) - kg_needed_gc(trial, c) for c in COLORES_PRODUCCION
        )
        if slack > best_slack:
            best_slack = slack
            best = trial
    return best


def protect_kids_curve_colors(
    gc: dict[tuple[str, str], int],
    df: pd.DataFrame,
    kg_budget: dict[str, float],
    *,
    kaki_floor: int = 0,
) -> dict[tuple[str, str], int]:
    """Gris/Azul KIDS: presencia en todas las tallas + peso cercano al ranking ventas."""
    g_targets = gender_targets(df)
    ideal = ideal_gc_floats(df, g_targets)
    n_tallas = len([t for t in KIDS_STD_TALLAS if t not in PRODUCTION_EXCLUDE_TALLAS.get("KIDS", set())])
    order = sales_color_order(df, "KIDS")
    donors = list(reversed(order))

    cab_order = sales_color_order(df, "CAB")

    def donor_ok(donor: str) -> bool:
        if donor == "Kaki":
            return gc.get(("KIDS", "Kaki"), 0) > kaki_floor
        return True

    for color in KIDS_FULL_CURVE_COLORS:
        key = ("KIDS", color)
        floor = kids_full_curve_floor(color, ideal, n_tallas)
        while gc.get(key, 0) < floor:
            moved = False
            if color == "Gris Oscuro":
                for kid_donor in donors:
                    if kid_donor == color or not donor_ok(kid_donor):
                        continue
                    if gc.get(("KIDS", kid_donor), 0) <= 1:
                        continue
                    trial = best_cab_recipient_for_gris_swap(gc, kg_budget, kid_donor)
                    if trial:
                        gc = trial
                        moved = True
                        break
            else:
                for kid_donor in donors:
                    if kid_donor == color or not donor_ok(kid_donor):
                        continue
                    kd = ("KIDS", kid_donor)
                    if gc.get(kd, 0) <= n_tallas and kid_donor not in KIDS_FULL_CURVE_COLORS:
                        continue
                    if gc.get(kd, 0) <= 1:
                        continue
                    if gc.get(("CAB", color), 0) <= 0:
                        continue
                    for cab_hi in cab_order:
                        if cab_hi == color:
                            continue
                        trial = quad_swap_gc(
                            gc,
                            kg_budget,
                            [
                                ("KIDS", color, 1),
                                ("KIDS", kid_donor, -1),
                                ("CAB", color, -1),
                                ("CAB", cab_hi, 1),
                            ],
                        )
                        if trial:
                            gc = trial
                            moved = True
                            break
                    if moved:
                        break
            if not moved:
                break
    return gc


def sales_weight_gc(df: pd.DataFrame, genero: str, color: str) -> float:
    return float(df[(df["genero"] == genero) & (df["prod_color"] == color)]["v"].sum())


def sales_color_talla_weights(
    df: pd.DataFrame, genero: str, color: str | None = None
) -> dict[str, float]:
    """Pesos talla del dashboard (opcionalmente filtrado por color)."""
    gdf = df[df["genero"] == genero]
    if color:
        gdf = gdf[gdf["prod_color"] == color]
    excluded = PRODUCTION_EXCLUDE_TALLAS.get(genero, set())
    weights: dict[str, float] = defaultdict(float)
    for _, row in gdf.iterrows():
        t = str(row["talla"])
        if t in excluded:
            continue
        weights[t] += float(row["v"])
    return dict(weights)


def dashboard_talla_weights(df: pd.DataFrame, genero: str, color: str) -> dict[str, float]:
    """Curva talla dashboard: por color; tallas sin venta del color usan curva del género."""
    excluded = PRODUCTION_EXCLUDE_TALLAS.get(genero, set())
    w_color = sales_color_talla_weights(df, genero, color)
    w_gender = sales_color_talla_weights(df, genero, None)
    order = TALLA_ORDER.get(genero, [])
    weights: dict[str, float] = {}
    for t in order:
        if t in excluded:
            continue
        wc = w_color.get(t, 0.0)
        wg = w_gender.get(t, 0.0)
        weights[t] = wc if wc > 0 else wg
    if sum(weights.values()) <= 0:
        weights = {t: 1.0 for t in weights}
    return weights


def enforce_cab_2xl_presence(
    alloc: dict[str, int],
    c_target: int,
    t_weights: dict[str, float],
) -> dict[str, int]:
    if c_target < CAB_2XL_MIN_COLOR_UNITS or t_weights.get("2XL", 0) <= 0:
        return alloc
    out = dict(alloc)
    if out.get("2XL", 0) >= 1:
        return out
    donor = max((t for t in out if t != "2XL"), key=lambda t: out.get(t, 0), default=None)
    if donor is None or out.get(donor, 0) <= 1:
        return out
    out[donor] -= 1
    out["2XL"] = out.get("2XL", 0) + 1
    return out


def ideal_gc_floats(df: pd.DataFrame, g_targets: dict[str, int]) -> dict[tuple[str, str], float]:
    gc: dict[tuple[str, str], float] = {}
    for genero in GENEROS:
        gdf = df[df["genero"] == genero]
        g_sales = float(gdf["v"].sum()) or 1.0
        for color in COLORES_PRODUCCION:
            gc[(genero, color)] = g_targets[genero] * float(
                gdf[gdf["prod_color"] == color]["v"].sum()
            ) / g_sales
    return gc


def sales_color_order(df: pd.DataFrame, genero: str) -> list[str]:
    gdf = df[df["genero"] == genero]
    return sorted(
        COLORES_PRODUCCION,
        key=lambda c: -float(gdf[gdf["prod_color"] == c]["v"].sum()),
    )


def cab_color_ranking_penalty(df: pd.DataFrame, gc: dict[tuple[str, str], int]) -> int:
    """Penaliza und CAB fuera del ranking ventas (sin romper uso de tela)."""
    order = sales_color_order(df, "CAB")
    pen = 0
    for i in range(len(order) - 1):
        hi, lo = order[i], order[i + 1]
        gap = gc.get(("CAB", lo), 0) - gc.get(("CAB", hi), 0)
        if gap > 0:
            pen += gap * 12
    return pen


def kids_full_curve_floor(
    color: str,
    ideal: dict[tuple[str, str], float],
    n_tallas: int,
) -> int:
    if color == "Gris Oscuro":
        return max(n_tallas, KIDS_GRIS_MIN_UNITS)
    return max(n_tallas, int(round(ideal.get(("KIDS", color), 0) * KIDS_FULL_CURVE_IDEAL_FACTOR)))


def quad_swap_gc(
    gc: dict[tuple[str, str], int],
    kg_budget: dict[str, float],
    moves: list[tuple[str, str, int]],
    *,
    kg_margin: float = 0.02,
) -> dict[tuple[str, str], int] | None:
    """Aplica deltas (+/-1) por (género, color); exige totales por género invariantes."""
    trial = dict(gc)
    for genero, color, delta in moves:
        trial[(genero, color)] = trial.get((genero, color), 0) + delta
        if trial[(genero, color)] < 0:
            return None
    for genero in GENEROS:
        if sum(trial.get((genero, c), 0) for c in COLORES_PRODUCCION) != sum(
            gc.get((genero, c), 0) for c in COLORES_PRODUCCION
        ):
            return None
    if not all(
        kg_needed_gc(trial, c) <= kg_budget.get(c, 0) + kg_margin for c in COLORES_PRODUCCION
    ):
        return None
    return trial


def shift_gris_to_kids_floor(
    gc: dict[tuple[str, str], int],
    kg_budget: dict[str, float],
    df: pd.DataFrame,
) -> dict[tuple[str, str], int]:
    """Pasa und Gris de CAB/DAMA a KIDS (menos kg/und) hasta piso operativo."""
    floor = KIDS_GRIS_MIN_UNITS
    kid_donors = list(reversed(sales_color_order(df, "KIDS")))
    for _ in range(400):
        if gc.get(("KIDS", "Gris Oscuro"), 0) >= floor:
            break
        best: dict[tuple[str, str], int] | None = None
        for adult in ["DAMA", "CAB"]:
            if gc.get((adult, "Gris Oscuro"), 0) <= 0:
                continue
            for kid_d in kid_donors:
                if kid_d == "Gris Oscuro" or gc.get(("KIDS", kid_d), 0) <= 0:
                    continue
                for hi in COLORES_PRODUCCION:
                    if hi == "Gris Oscuro":
                        continue
                    trial = quad_swap_gc(
                        gc,
                        kg_budget,
                        [
                            ("KIDS", "Gris Oscuro", 1),
                            ("KIDS", kid_d, -1),
                            (adult, "Gris Oscuro", -1),
                            (adult, hi, 1),
                        ],
                        kg_margin=0.06,
                    )
                    if trial:
                        best = trial
                        break
                if best:
                    break
            if best:
                break
        if not best:
            break
        gc = best
    return gc


def gris_add_blocked_for_adults(gc: dict[tuple[str, str], int], genero: str, color: str) -> bool:
    return (
        color == "Gris Oscuro"
        and genero != "KIDS"
        and gc.get(("KIDS", "Gris Oscuro"), 0) < KIDS_GRIS_MIN_UNITS
    )


def enforce_gender_color_ranking(
    gc: dict[tuple[str, str], int],
    df: pd.DataFrame,
    genero: str,
    kg_budget: dict[str, float],
) -> dict[tuple[str, str], int]:
    """Mantiene ranking de ventas por color dentro del género (sin romper kg)."""
    order = sales_color_order(df, genero)
    for _ in range(3000):
        changed = False
        for i in range(len(order) - 1):
            hi, lo = order[i], order[i + 1]
            if gc.get((genero, hi), 0) >= gc.get((genero, lo), 0):
                continue
            if gc.get((genero, lo), 0) <= 0:
                continue
            trial = dict(gc)
            trial[(genero, lo)] -= 1
            trial[(genero, hi)] = trial.get((genero, hi), 0) + 1
            if all(
                kg_needed_gc(trial, c) <= kg_budget.get(c, 0) + 0.02
                for c in COLORES_PRODUCCION
            ):
                gc = trial
                changed = True
        if not changed:
            break
    return gc


def allocate_tallas_for_color(
    df: pd.DataFrame,
    genero: str,
    color: str,
    c_target: int,
    shares: dict[str, float],
) -> list:
    t_weights = dashboard_talla_weights(df, genero, color)
    if genero == "KIDS" and sum(sales_color_talla_weights(df, genero, color).values()) < KIDS_TALLA_WEIGHT_MIN_SALES:
        t_weights = dashboard_talla_weights(df, genero, color)

    if genero == "CAB":
        t_weights = {t: w * (CAB_2XL_BOOST if t == "2XL" else 1.0) for t, w in t_weights.items()}

    kids_tallas = [t for t in KIDS_STD_TALLAS if t not in PRODUCTION_EXCLUDE_TALLAS.get("KIDS", set())]
    if genero == "KIDS" and color in (KIDS_FULL_CURVE_COLORS | {"Kaki"}):
        for t in kids_tallas:
            t_weights.setdefault(t, t_weights.get(t, 0) or 1.0)
        n_floor = len(kids_tallas)
        if c_target <= 0:
            return []
        if c_target < n_floor:
            alloc = allocate_by_weights({t: t_weights.get(t, 1.0) for t in kids_tallas}, c_target)
        else:
            floor = {t: 1 for t in kids_tallas}
            extra = allocate_by_weights(
                {t: t_weights.get(t, 1.0) for t in kids_tallas}, c_target - n_floor
            )
            alloc = {t: floor[t] + extra.get(t, 0) for t in kids_tallas}
    else:
        tallas = sort_tallas(genero, list(t_weights.keys()))
        alloc = allocate_by_weights({t: t_weights.get(t, 0) for t in tallas}, c_target)
        if genero == "CAB":
            alloc = enforce_cab_2xl_presence(alloc, c_target, t_weights)

    t_total_w = sum(t_weights.get(t, 0) for t in alloc.keys()) or 1.0
    talla_objs = []
    for talla in sort_tallas(genero, list(alloc.keys())):
        qty = alloc.get(talla, 0)
        if qty <= 0:
            continue
        pm, px = min_max_qty(qty)
        talla_objs.append({
            "talla": str(talla),
            "produce": pm,
            "produce_min": pm,
            "produce_max": px,
            "curve_pct": round(t_weights.get(talla, 0) / t_total_w * 100, 1),
            "store_split": distribute_units(pm, shares, ALL_DIST_STORES),
            "store_split_max": distribute_units(px, shares, ALL_DIST_STORES),
        })
    return talla_objs


def production_totals_by_color(plan: list) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for p in plan:
        totals[p["color"]] += p["produce_min"]
    return dict(totals)


def tela_verification(plan: list, shorts: dict | None = None) -> list[dict]:
    """Explore + Shorts vs kg en existencias (delta ≈ 0)."""
    by_color = production_totals_by_color(plan)
    by_gc: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for p in plan:
        by_gc[p["color"]][p["genero"]] += p["produce_min"]

    shorts_kg = {c: 0.0 for c in COLORES_PRODUCCION}
    if shorts:
        for row in shorts.get("rows", []):
            shorts_kg[row["color"]] += float(row["kg"])

    explore_total = sum(p["produce_min"] for p in plan)
    rows = []
    for color in COLORES_PRODUCCION:
        und = by_color.get(color, 0)
        kg_explore = sum(by_gc[color].get(g, 0) * TELA_CONSUMO[g] for g in TELA_CONSUMO)
        kg_shorts = shorts_kg.get(color, 0.0)
        kg_need = kg_explore + kg_shorts
        kg_exist = TELA_KG_EXISTENCIA[color]
        rows.append({
            "color": color,
            "und_explore": und,
            "kg_explore": round(kg_explore, 2),
            "kg_shorts": round(kg_shorts, 2),
            "kg_necesario": round(kg_need, 2),
            "kg_existencia": round(kg_exist, 2),
            "delta_kg": round(kg_exist - kg_need, 2),
            "pct_existencia": round(kg_exist / TELA_KG_TOTAL * 100, 1),
            "pct_produccion": round(und / explore_total * 100, 1) if explore_total else 0,
        })
    return rows


def stock_for_genero(stock: dict, genero: str) -> int:
    total = 0
    for k, v in stock.items():
        if k.endswith(f"/{genero}"):
            total += int(v)
    return total


def refresh_plan_color_totals(plan_entry: dict) -> None:
    c_min = sum(t["produce_min"] for t in plan_entry["tallas"])
    c_max = sum(t["produce_max"] for t in plan_entry["tallas"])
    plan_entry["produce"] = c_min
    plan_entry["produce_min"] = c_min
    plan_entry["produce_max"] = c_max


def talla_objs_from_counts(
    genero: str,
    tallas: dict[str, int],
    shares: dict[str, float],
) -> list[dict]:
    objs: list[dict] = []
    for talla in sort_tallas(genero, list(tallas.keys())):
        qty = int(tallas.get(talla, 0))
        if qty <= 0:
            continue
        pm, px = min_max_qty(qty)
        objs.append({
            "talla": str(talla),
            "produce": pm,
            "produce_min": pm,
            "produce_max": px,
            "curve_pct": 0.0,
            "store_split": distribute_units(pm, shares, ALL_DIST_STORES),
            "store_split_max": distribute_units(px, shares, ALL_DIST_STORES),
        })
    return objs


def build_manual_adult_plan(df: pd.DataFrame, shares: dict[str, float]) -> list[dict]:
    plan: list[dict] = []
    total_sales = float(df["v"].sum()) or 1.0
    for genero in ("CAB", "DAMA"):
        gdf = df[df["genero"] == genero]
        g_sales = float(gdf["v"].sum()) or 1.0
        for color, tallas in MANUAL_CAB_DAMA_TALLAS[genero].items():
            talla_objs = talla_objs_from_counts(genero, tallas, shares)
            if not talla_objs:
                continue
            cdf = gdf[gdf["prod_color"] == color]
            c_sales = float(cdf["v"].sum())
            c_min = sum(t["produce_min"] for t in talla_objs)
            c_max = sum(t["produce_max"] for t in talla_objs)
            color_sales_pct = round(c_sales / g_sales * 100, 1)
            plan.append({
                "genero": genero,
                "color": color,
                "color_pct": color_sales_pct,
                "sales_pct": round(c_sales / total_sales * 100, 1),
                "produce": c_min,
                "produce_min": c_min,
                "produce_max": c_max,
                "tallas": sorted(talla_objs, key=lambda x: -x["produce_min"]),
                "store_split": distribute_units(c_min, shares, ALL_DIST_STORES),
            })
    return plan


def kg_explore_by_color_plan(plan: list) -> dict[str, float]:
    by: dict[str, float] = defaultdict(float)
    for p in plan:
        by[p["color"]] += p["produce_min"] * TELA_CONSUMO[p["genero"]]
    return dict(by)


def remove_one_from_plan_entry(plan_entry: dict) -> bool:
    for t in sorted(plan_entry["tallas"], key=lambda x: -x["produce_min"]):
        if t["produce_min"] <= 0:
            continue
        t["produce_min"] -= 1
        pm, px = min_max_qty(t["produce_min"])
        t["produce"] = pm
        t["produce_max"] = px
        refresh_plan_color_totals(plan_entry)
        return True
    return False


def find_plan_entry(plan: list, genero: str, color: str) -> dict | None:
    for p in plan:
        if p["genero"] == genero and p["color"] == color:
            return p
    return None


def kids_color_units_target(df: pd.DataFrame, color: str, kids_target: int) -> int:
    gdf = df[df["genero"] == "KIDS"]
    sales = float(gdf[gdf["prod_color"] == color]["v"].sum())
    total = float(gdf["v"].sum()) or 1.0
    return int(round(kids_target * sales / total))


def kids_kaki_units_target(df: pd.DataFrame, kids_target: int) -> int:
    base = kids_color_units_target(df, "Kaki", kids_target)
    boosted = int(round(base * KIDS_KAKI_BOOST)) + KIDS_KAKI_EXTRA_UND
    return max(boosted, KIDS_KAKI_MIN_TALLAS)


def reserve_kaki_kg_for_kids(
    adult_plan: list,
    explore_budget: dict[str, float],
    kaki_kids_units: int,
) -> list:
    """Recorta Kaki CAB/DAMA hasta dejar kg para KIDS Kaki (dashboard)."""
    need_kg = kaki_kids_units * TELA_CONSUMO["KIDS"] + 0.08
    plan = [dict(p, tallas=[dict(t) for t in p["tallas"]]) for p in adult_plan]
    toggle = 0
    for _ in range(15_000):
        used = kg_explore_by_color_plan(plan).get("Kaki", 0.0)
        slack = explore_budget.get("Kaki", 0.0) - used
        if slack + 0.001 >= need_kg:
            break
        order = [("CAB", "Kaki"), ("DAMA", "Kaki")] if toggle % 2 == 0 else [("DAMA", "Kaki"), ("CAB", "Kaki")]
        toggle += 1
        removed = False
        for genero, color in order:
            entry = find_plan_entry(plan, genero, color)
            if entry and remove_one_from_plan_entry(entry):
                removed = True
                break
        if not removed:
            break
    return plan


def protect_kids_kaki(
    gc: dict[tuple[str, str], int],
    df: pd.DataFrame,
    kg_slack: dict[str, float],
    floor: int,
) -> dict[tuple[str, str], int]:
    if floor <= 0:
        return gc
    order = sales_color_order(df, "KIDS")
    donors = list(reversed(order))
    while gc.get(("KIDS", "Kaki"), 0) < floor:
        moved = False
        for donor in donors:
            if donor == "Kaki":
                continue
            if gc.get(("KIDS", donor), 0) <= 1:
                continue
            trial = dict(gc)
            trial[("KIDS", "Kaki")] = trial.get(("KIDS", "Kaki"), 0) + 1
            trial[("KIDS", donor)] -= 1
            need_k = trial[("KIDS", "Kaki")] * TELA_CONSUMO["KIDS"]
            if need_k <= kg_slack.get("Kaki", 0.0) + 0.02 and all(
                trial.get(("KIDS", c), 0) >= 0 for c in COLORES_PRODUCCION
            ):
                gc = trial
                moved = True
                break
        if not moved:
            break
    return gc


def balance_plan_to_explore_budget(plan: list, explore_budget: dict[str, float]) -> list:
    """Recorta und (prioridad Kaki CAB/DAMA) hasta kg Explore ≤ presupuesto por color."""
    plan = [dict(p, tallas=[dict(t) for t in p["tallas"]]) for p in plan]
    for _ in range(80_000):
        by = kg_explore_by_color_plan(plan)
        over_color = None
        for color in COLORES_PRODUCCION:
            cap = explore_budget.get(color, 0.0)
            if by.get(color, 0.0) > cap + 0.015:
                over_color = color
                break
        if not over_color:
            break
        removed = False
        for genero, color in FABRIC_TRIM_ORDER:
            if color != over_color:
                continue
            entry = find_plan_entry(plan, genero, color)
            if entry and remove_one_from_plan_entry(entry):
                removed = True
                break
        if not removed:
            for p in plan:
                if p["color"] != over_color or p["genero"] == "KIDS":
                    continue
                if remove_one_from_plan_entry(p):
                    removed = True
                    break
        if not removed:
            break
    return plan


def fit_kids_gc_to_slack(
    df: pd.DataFrame,
    kids_target: int,
    kg_slack: dict[str, float],
) -> dict[tuple[str, str], int]:
    """Asigna und KIDS (incl. Kaki) respetando kg restante por color tras CAB/DAMA."""
    kaki_floor = kids_kaki_units_target(df, kids_target)
    kaki_cap = int(kg_slack.get("Kaki", 0.0) / TELA_CONSUMO["KIDS"])
    kaki_floor = min(kaki_floor, kaki_cap)
    rest_target = max(0, kids_target - kaki_floor)

    gc: dict[tuple[str, str], int] = {("KIDS", c): 0 for c in COLORES_PRODUCCION}
    gc[("KIDS", "Kaki")] = kaki_floor

    ideal = ideal_gc_floats(df, {"KIDS": rest_target, "CAB": 0, "DAMA": 0})
    weights = {
        c: ideal.get(("KIDS", c), 0.0) for c in COLORES_PRODUCCION if c != "Kaki"
    }
    allocated = allocate_by_weights(weights, rest_target)
    for color in COLORES_PRODUCCION:
        if color == "Kaki":
            continue
        gc[("KIDS", color)] = allocated.get(color, 0)

    for _ in range(4000):
        over = False
        for color in COLORES_PRODUCCION:
            need = gc.get(("KIDS", color), 0) * TELA_CONSUMO["KIDS"]
            floor = kaki_floor if color == "Kaki" else 0
            if (
                need > kg_slack.get(color, 0.0) + 0.001
                and gc.get(("KIDS", color), 0) > floor
            ):
                gc[("KIDS", color)] -= 1
                over = True
        if not over:
            break

    for _ in range(4000):
        options: list[tuple[float, str]] = []
        for color in COLORES_PRODUCCION:
            if sales_weight_gc(df, "KIDS", color) <= 0:
                continue
            slack = kg_slack.get(color, 0.0) - gc.get(("KIDS", color), 0) * TELA_CONSUMO["KIDS"]
            if slack + 0.001 >= TELA_CONSUMO["KIDS"]:
                options.append((gc_fill_priority(df, "KIDS", color), color))
        if not options:
            break
        options.sort(reverse=True)
        color = options[0][1]
        gc[("KIDS", color)] = gc.get(("KIDS", color), 0) + 1

    for _ in range(3):
        gc = protect_kids_curve_colors(gc, df, kg_slack, kaki_floor=kaki_floor)
        gc = enforce_gender_color_ranking(gc, df, "KIDS", kg_slack)
    gc = protect_kids_kaki(gc, df, kg_slack, kaki_floor)

    diff = kids_target - sum(gc.get(("KIDS", c), 0) for c in COLORES_PRODUCCION)
    for _ in range(abs(diff)):
        if diff > 0:
            opts = [
                (sales_weight_gc(df, "KIDS", c), c)
                for c in COLORES_PRODUCCION
                if sales_weight_gc(df, "KIDS", c) > 0
                and kg_slack.get(c, 0) - gc.get(("KIDS", c), 0) * TELA_CONSUMO["KIDS"]
                >= TELA_CONSUMO["KIDS"] - 0.001
            ]
            if not opts:
                break
            opts.sort(reverse=True)
            gc[("KIDS", opts[0][1])] = gc.get(("KIDS", opts[0][1]), 0) + 1
        else:
            opts = [
                (sales_weight_gc(df, "KIDS", c), c)
                for c in COLORES_PRODUCCION
                if gc.get(("KIDS", c), 0) > (kaki_floor if c == "Kaki" else 0)
            ]
            if not opts:
                break
            opts.sort()
            gc[("KIDS", opts[0][1])] -= 1
    gc = protect_kids_kaki(gc, df, kg_slack, kaki_floor)
    return gc


def build_kids_plan(
    df: pd.DataFrame,
    shares: dict[str, float],
    gc_kids: dict[tuple[str, str], int],
) -> list[dict]:
    plan: list[dict] = []
    total_sales = float(df["v"].sum()) or 1.0
    gdf = df[df["genero"] == "KIDS"]
    g_sales = float(gdf["v"].sum()) or 1.0
    for color in sales_color_order(df, "KIDS"):
        c_target = gc_kids.get(("KIDS", color), 0)
        if c_target <= 0:
            continue
        talla_objs = allocate_tallas_for_color(df, "KIDS", color, c_target, shares)
        if not talla_objs:
            continue
        cdf = gdf[gdf["prod_color"] == color]
        c_sales = float(cdf["v"].sum())
        c_min = sum(t["produce_min"] for t in talla_objs)
        c_max = sum(t["produce_max"] for t in talla_objs)
        plan.append({
            "genero": "KIDS",
            "color": color,
            "color_pct": round(c_sales / g_sales * 100, 1),
            "sales_pct": round(c_sales / total_sales * 100, 1),
            "produce": c_min,
            "produce_min": c_min,
            "produce_max": c_max,
            "tallas": sorted(talla_objs, key=lambda x: -x["produce_min"]),
            "store_split": distribute_units(c_min, shares, ALL_DIST_STORES),
        })
    return plan


def build_rango_summary_from_plan(
    df: pd.DataFrame,
    plan: list,
    stock: dict,
    shares: dict[str, float],
) -> tuple[dict, dict]:
    summary: dict = {}
    rango: dict = {}
    for genero in GENEROS:
        gdf = df[df["genero"] == genero]
        color_rows = []
        talla_totals: dict = defaultdict(lambda: {"min": 0, "max": 0, "curve_pct": 0.0})
        for p in plan:
            if p["genero"] != genero:
                continue
            talla_objs = p["tallas"]
            for t in talla_objs:
                talla_totals[t["talla"]]["min"] += t["produce_min"]
                talla_totals[t["talla"]]["max"] += t["produce_max"]
            color_rows.append({
                "color": p["color"],
                "pct": p["color_pct"],
                "sales_pct": p["color_pct"],
                "min": p["produce_min"],
                "max": p["produce_max"],
                "tallas": talla_objs,
            })
        g_prod = sum(p["produce_min"] for p in plan if p["genero"] == genero)
        g_prod_max = sum(p["produce_max"] for p in plan if p["genero"] == genero)
        excluded = PRODUCTION_EXCLUDE_TALLAS.get(genero, set())
        t_sales = gdf.groupby("talla")["v"].sum()
        if excluded:
            t_sales = t_sales.drop(labels=list(excluded), errors="ignore")
        t_sales_total = float(t_sales.sum()) or 1.0
        for t, td in talla_totals.items():
            ref_pct = float(t_sales.get(t, 0)) / t_sales_total * 100
            td["curve_pct"] = round(ref_pct, 1)
            td["sales_pct"] = round(ref_pct, 1)
        summary[genero] = {
            "produce": g_prod,
            "produce_max": g_prod_max,
            "stk": stock_for_genero(stock, genero),
        }
        sales_order = {c: i for i, c in enumerate(sales_color_order(df, genero))}
        rango[genero] = {
            "color_rows": sorted(color_rows, key=lambda x: sales_order.get(x["color"], 99)),
            "talla_totals": dict(talla_totals),
            "shares": shares,
        }
    return summary, rango


def explore_tela_usage_rows(plan: list, explore_budget: dict[str, float]) -> list[dict]:
    by_gc: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for p in plan:
        by_gc[p["color"]][p["genero"]] += p["produce_min"]
    rows = []
    for color in COLORES_PRODUCCION:
        und = {g: by_gc[color].get(g, 0) for g in GENEROS}
        kg = {g: und[g] * TELA_CONSUMO[g] for g in GENEROS}
        kg_total = sum(kg.values())
        cap = explore_budget.get(color, 0.0)
        rows.append({
            "color": color,
            "und_cab": und["CAB"],
            "und_dama": und["DAMA"],
            "und_kids": und["KIDS"],
            "und_total": sum(und.values()),
            "kg_cab": round(kg["CAB"], 2),
            "kg_dama": round(kg["DAMA"], 2),
            "kg_kids": round(kg["KIDS"], 2),
            "kg_explore": round(kg_total, 2),
            "kg_presupuesto": round(cap, 2),
            "delta_kg": round(cap - kg_total, 2),
        })
    return rows


def build_production_plan(
    df: pd.DataFrame,
    shares: dict[str, float],
    stock: dict,
    gc: dict[tuple[str, str], int],
) -> tuple[list, dict, dict]:
    plan: list = []
    summary: dict = {}
    rango: dict = {}

    for genero in GENEROS:
        gdf = df[df["genero"] == genero]
        g_sales = float(gdf["v"].sum()) or 1.0
        color_rows = []
        talla_totals: dict = defaultdict(lambda: {"min": 0, "max": 0, "curve_pct": 0.0})

        for color in sales_color_order(df, genero):
            c_target = gc.get((genero, color), 0)
            if c_target <= 0:
                continue

            talla_objs = allocate_tallas_for_color(df, genero, color, c_target, shares)

            for t in talla_objs:
                talla_totals[t["talla"]]["min"] += t["produce_min"]
                talla_totals[t["talla"]]["max"] += t["produce_max"]

            if not talla_objs:
                continue

            cdf = gdf[gdf["prod_color"] == color]
            c_sales = float(cdf["v"].sum())
            c_min = sum(t["produce_min"] for t in talla_objs)
            c_max = sum(t["produce_max"] for t in talla_objs)
            color_sales_pct = round(c_sales / g_sales * 100, 1)
            plan.append({
                "genero": genero,
                "color": color,
                "color_pct": color_sales_pct,
                "sales_pct": round(c_sales / (df["v"].sum() or 1) * 100, 1),
                "produce": c_min,
                "produce_min": c_min,
                "produce_max": c_max,
                "tallas": sorted(talla_objs, key=lambda x: -x["produce_min"]),
                "store_split": distribute_units(c_min, shares, ALL_DIST_STORES),
            })
            color_rows.append({
                "color": color,
                "pct": color_sales_pct,
                "sales_pct": color_sales_pct,
                "min": c_min,
                "max": c_max,
                "tallas": talla_objs,
            })

        g_prod = sum(p["produce_min"] for p in plan if p["genero"] == genero)
        g_prod_max = sum(p["produce_max"] for p in plan if p["genero"] == genero)

        excluded = PRODUCTION_EXCLUDE_TALLAS.get(genero, set())
        t_sales = gdf.groupby("talla")["v"].sum()
        if excluded:
            t_sales = t_sales.drop(labels=list(excluded), errors="ignore")
        t_sales_total = float(t_sales.sum()) or 1.0
        for t, td in talla_totals.items():
            ref_pct = float(t_sales.get(t, 0)) / t_sales_total * 100
            td["curve_pct"] = round(ref_pct, 1)
            td["sales_pct"] = round(ref_pct, 1)

        summary[genero] = {
            "produce": g_prod,
            "produce_max": g_prod_max,
            "stk": stock_for_genero(stock, genero),
        }
        sales_order = {c: i for i, c in enumerate(sales_color_order(df, genero))}
        rango[genero] = {
            "color_rows": sorted(color_rows, key=lambda x: sales_order.get(x["color"], 99)),
            "talla_totals": dict(talla_totals),
            "shares": shares,
        }

    return plan, summary, rango


def build_data(template: dict, df: pd.DataFrame) -> dict:
    stock = template.get("stock") or {}
    stock_total = sum(stock.values())
    sbs = template.get("stock_by_store") or {}
    shares = store_weights(df.groupby("tienda")["v"].sum().to_dict())
    explore_budget, shorts_plan, _gc = solve_fabric_split(df)
    adult_plan = build_manual_adult_plan(df, shares)
    kaki_kids_target = kids_kaki_units_target(df, KIDS_TARGET)
    adult_plan = reserve_kaki_kg_for_kids(adult_plan, explore_budget, kaki_kids_target)
    kg_adult = kg_explore_by_color_plan(adult_plan)
    kg_slack = {
        c: max(0.0, explore_budget.get(c, 0.0) - kg_adult.get(c, 0.0)) for c in COLORES_PRODUCCION
    }
    gc_kids = fit_kids_gc_to_slack(df, KIDS_TARGET, kg_slack)
    kids_plan = build_kids_plan(df, shares, gc_kids)
    plan = balance_plan_to_explore_budget(adult_plan + kids_plan, explore_budget)
    summary, rango = build_rango_summary_from_plan(df, plan, stock, shares)
    explore_tela = explore_tela_usage_rows(plan, explore_budget)

    explore_total = sum(summary[g]["produce"] for g in summary)
    color_targets = production_totals_by_color(plan)
    tela_check = tela_verification(plan, shorts_plan)
    tela_rows = list(tela_check)

    data = {**template}
    data.update({
        "nombre": MODELO,
        "method": "existencias_explore_shorts_r1",
        "tela_consumo_ref": TELA_CONSUMO,
        "kids_target": KIDS_TARGET,
        "kids_target_range": [KIDS_TARGET_MIN, KIDS_TARGET_MAX],
        "production_exclude_tallas": {g: sorted(t) for g, t in PRODUCTION_EXCLUDE_TALLAS.items()},
        "high_season_factor": HIGH_SEASON_FACTOR,
        "shorts_r1": shorts_plan,
        "explore_kg_budget": explore_budget,
        "explore_tela_usage": explore_tela,
        "target_produce_min": {"TOTAL": explore_total, **{g: summary[g]["produce"] for g in summary}},
        "production_plan": plan,
        "summary_genero": summary,
        "rango_data": rango,
        "justificacion": {
            "fuente": JUSTIF_XLSX.name,
            "produce_total": explore_total,
            "produce_total_ref": PRODUCE_TOTAL,
            "shorts_target": SHORTS_TARGET,
            "demand_jul_dec": DEMAND_JUL_DEC,
            "stock_ref": STOCK_REF,
            "stock_actual": stock_total,
            "tela_kg_existencia": TELA_KG_EXISTENCIA,
            "tela_kg_total": TELA_KG_TOTAL,
            "shorts_r1": shorts_plan,
            "tela_pedido_total": TELA_PEDIDO_TOTAL,
            "orden1_subtotal": ORDEN1_SUBTOTAL,
            "orden2_subtotal": ORDEN2_SUBTOTAL,
            "demand_months": DEMAND_MONTHS,
            "fin_dic_sin_compra_ref": 760,
            "fin_dic_con_produccion_ref": 3668,
            "fin_dic_sin_compra_actual": stock_total - DEMAND_JUL_DEC,
            "fin_dic_con_produccion_actual": stock_total + PRODUCE_TOTAL - DEMAND_JUL_DEC,
            "tela_rows": tela_rows,
            "tela_verificacion": tela_check,
        },
        "stock_total": stock_total,
        "tolon_boost": 1.0,
        "velocity_months_label": "Justificación Jul–Dic (escenarios A–G)",
    })
    return data


def patch_html(template: str, data: dict) -> str:
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    html = re.sub(
        r"(?:var|const)\s+DATA\s*=\s*\{.*?\};",
        f"const DATA={data_json};",
        template,
        count=1,
        flags=re.DOTALL,
    )

    note = (
        " · <span style=\"color:#f97316\">Producción: "
        f"{PRODUCE_TOTAL:,} und (ranking dashboard · tela comprada · KIDS {KIDS_TARGET_MIN:,}–{KIDS_TARGET_MAX:,}) "
        f"· demanda Jul–Dic {DEMAND_JUL_DEC:,}</span>"
    )
    if "justificación Novaktex" not in html:
        html = html.replace(
            "Proyección basada en ventas históricas",
            "Proyección basada en ventas históricas" + note,
        )

    # VELA 1.5× GRIETA en pesos tienda
    html = html.replace(
        "w['VELA']=grie;",
        "w['VELA']=Math.round(grie*1.5);",
    )
    return html


def export_excel(data: dict, path: Path) -> None:
    j = data["justificacion"]
    summary = data["summary_genero"]
    rango = data["rango_data"]
    color_targets = production_totals_by_color(data["production_plan"])
    tela_check = j.get("tela_verificacion") or tela_verification(
        data["production_plan"], j.get("shorts_r1")
    )

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        wb = writer.book
        bold = wb.add_format({"bold": True})
        title = wb.add_format({"bold": True, "font_size": 14, "font_color": "#1F3864"})
        section = wb.add_format({"bold": True, "font_size": 11, "font_color": "#1F3864"})
        hdr = wb.add_format({"bold": True, "bg_color": "#4472C4", "font_color": "white", "border": 1})
        num = wb.add_format({"num_format": "#,##0"})
        dec = wb.add_format({"num_format": "0.0"})
        pct = wb.add_format({"num_format": "0%"})
        pct2 = wb.add_format({"num_format": "0.00%"})

        # ── Resumen / Justificación ──
        ws = wb.add_worksheet("Resumen")
        ws.set_column("A:A", 48)
        ws.set_column("B:D", 18)
        row = 0
        ws.merge_range(row, 0, row, 3, "EXPLORE PANTS — PROYECCIÓN ANCLADA A JUSTIFICACIÓN NOVAKTEX", title)
        row += 2
        bullets = [
            f"Fuente: {JUSTIF_XLSX.name}",
            f"Meta Explore Pants: tela completa · Shorts R1 = {SHORTS_TARGET:,} und",
            f"Demanda proyectada Jul–Dic: {DEMAND_JUL_DEC:,} und",
            f"Stock referencia justificación: {STOCK_REF:,} und ({STOCK_TIENDAS_REF:,} tiendas + {STOCK_TALLER_REF:,} taller)",
            f"Stock actual dashboard: {j['stock_actual']:,} und",
            f"Tela en almacén (existencias): {TELA_KG_TOTAL:.1f} kg · uso total Explore + Shorts",
            f"Shorts R1: Negro/Gris · CAB {SHORTS_CONSUMO['CAB']} · DAMA {SHORTS_CONSUMO['DAMA']} kg/und",
            f"Rango producción ×{HIGH_SEASON_FACTOR} (MÍN/MÁX) · ranking color/talla dashboard",
            f"KIDS {KIDS_TARGET_MIN:,}–{KIDS_TARGET_MAX:,} und · CAB sin 3XL · DAMA sin 2XL",
            "KIDS: tallas 2–12 (sin 14) · incluye Kaki · CAB/DAMA manual",
            f"Consumo referencial: CAB {TELA_CONSUMO['CAB']} · DAMA {TELA_CONSUMO['DAMA']} · KIDS {TELA_CONSUMO['KIDS']} kg/und",
            "Gris (ventas) → Gris Oscuro (producción)",
        ]
        for b in bullets:
            ws.write(row, 0, b)
            row += 1

        row += 1
        ws.write(row, 0, "Demanda mensual (justificación)", section)
        row += 1
        ws.write_row(row, 0, ["Mes", "Demanda (und)"], hdr)
        row += 1
        for label, und in DEMAND_MONTHS:
            ws.write(row, 0, label)
            ws.write(row, 1, und, num)
            row += 1
        ws.write(row, 0, "TOTAL JUL–DIC", bold)
        ws.write(row, 1, DEMAND_JUL_DEC, num)
        row += 2

        ws.write(row, 0, "Escenarios fin de año", section)
        row += 1
        ws.write(row, 0, "Fin dic SIN compra (ref / actual)")
        ws.write(row, 1, j["fin_dic_sin_compra_ref"], num)
        ws.write(row, 2, j["fin_dic_sin_compra_actual"], num)
        row += 1
        ws.write(row, 0, "Fin dic CON producción 80% (ref / actual)")
        ws.write(row, 1, j["fin_dic_con_produccion_ref"], num)
        ws.write(row, 2, j["fin_dic_con_produccion_actual"], num)
        row += 2

        ws.write_row(row, 0, ["Género", "Producir Mín", "Producir Máx"], hdr)
        row += 1
        tmin = tmax = 0
        for g in ["CAB", "DAMA", "KIDS"]:
            s = summary[g]
            ws.write_row(row, 0, [GENDER_XL[g], s["produce"], s["produce_max"]])
            tmin += s["produce"]
            tmax += s["produce_max"]
            row += 1
        ws.write_row(row, 0, ["TOTAL", tmin, tmax], bold)

        # ── Color por Género (vs dashboard) ──
        ws = wb.add_worksheet("Color por Género")
        row = 0
        ws.write(row, 0, "EXPLORE PANTS — COLOR POR GÉNERO (PRODUCCIÓN vs VENTAS)", title)
        row += 2
        for genero in ["CAB", "DAMA", "KIDS"]:
            rd = rango[genero]
            ws.write(row, 0, GENDER_XL[genero], section)
            row += 1
            ws.write_row(
                row, 0,
                ["# ventas", "Color", "Und Mín", "Und Máx", "% prod.", "% ventas dash."],
                hdr,
            )
            row += 1
            for rank, cr in enumerate(rd["color_rows"], start=1):
                ws.write(row, 0, rank)
                ws.write(row, 1, cr["color"])
                ws.write(row, 2, cr["min"], num)
                ws.write(row, 3, cr["max"], num)
                prod_pct = cr["min"] / summary[genero]["produce"] if summary[genero]["produce"] else 0
                ws.write(row, 4, prod_pct, pct2)
                ws.write(row, 5, cr["pct"] / 100, pct2)
                row += 1
            ws.write(row, 0, "TOTAL", bold)
            ws.write(row, 1, summary[genero]["produce"], num)
            ws.write(row, 2, 1, pct)
            row += 2

        # ── Cantidades por Colores (total + desglose género) ──
        by_gc: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for p in data["production_plan"]:
            by_gc[p["color"]][p["genero"]] += p["produce_min"]

        ws = wb.add_worksheet("Cantidades por Colores")
        row = 0
        ws.write(row, 0, "EXPLORE PANTS — UNIDADES A PRODUCIR POR COLOR (TOTAL)", title)
        row += 1
        ws.write(row, 0, f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        row += 2
        ws.write_row(
            row,
            0,
            [
                "Color",
                "Und CAB",
                "Und DAMA",
                "Und KIDS",
                "Und total",
                "% producción",
                "% compra tela",
                "Kg tela comprada",
            ],
            hdr,
        )
        row += 1
        explore_total = sum(summary[g]["produce"] for g in summary)
        for color in COLORES_PRODUCCION:
            und_c = by_gc[color].get("CAB", 0)
            und_d = by_gc[color].get("DAMA", 0)
            und_k = by_gc[color].get("KIDS", 0)
            und = und_c + und_d + und_k
            kg = TELA_KG_EXISTENCIA[color]
            ws.write(row, 0, color)
            ws.write(row, 1, und_c, num)
            ws.write(row, 2, und_d, num)
            ws.write(row, 3, und_k, num)
            ws.write(row, 4, und, num)
            ws.write(row, 5, und / explore_total if explore_total else 0, pct2)
            ws.write(row, 6, kg / TELA_KG_TOTAL if TELA_KG_TOTAL else 0, pct2)
            ws.write(row, 7, kg, dec)
            row += 1
        ws.write(row, 0, "TOTAL", bold)
        ws.write(row, 1, summary["CAB"]["produce"], num)
        ws.write(row, 2, summary["DAMA"]["produce"], num)
        ws.write(row, 3, summary["KIDS"]["produce"], num)
        ws.write(row, 4, explore_total, num)
        ws.write(row, 5, 1, pct)
        ws.write(row, 6, 1, pct)
        ws.write(row, 7, TELA_KG_TOTAL, dec)
        row += 2
        ws.write(row, 0, "KIDS Kaki (referencia rápida)", section)
        row += 1
        ws.write_row(
            row,
            0,
            ["KIDS · Kaki", by_gc["Kaki"].get("KIDS", 0), "und · tallas 2–12 · sin 14"],
        )

        # ── KIDS — matriz color × talla (incl. Kaki) ──
        ws = wb.add_worksheet("KIDS Color x Talla")
        row = 0
        ws.write(row, 0, "EXPLORE PANTS — KIDS (COLOR × TALLA)", title)
        row += 2
        rd_k = rango["KIDS"]
        tallas_k = sort_tallas(
            "KIDS",
            list({t["talla"] for cr in rd_k["color_rows"] for t in cr["tallas"]}),
        )
        ws.write_row(row, 0, ["Color / Talla"] + tallas_k + ["Total"], hdr)
        row += 1
        for cr in rd_k["color_rows"]:
            by_min = {t["talla"]: t["produce_min"] for t in cr["tallas"]}
            ws.write_row(row, 0, [cr["color"]] + [by_min.get(t, 0) for t in tallas_k] + [cr["min"]])
            row += 1
        ws.write(row, 0, "TOTAL KIDS", bold)
        ws.write(row, len(tallas_k) + 1, summary["KIDS"]["produce"], num)

        # ── Rango MÍN / MÁX por género ──
        ws = wb.add_worksheet("Rango Min Max")
        row = 0
        ws.write(
            row, 0,
            f"RANGO DE PRODUCCIÓN MÍNIMO / MÁXIMO — EXPLORE PANTS (×{HIGH_SEASON_FACTOR})",
            title,
        )
        row += 2
        ws.write_row(row, 0, ["Género", "MÍNIMO", "MÁXIMO", "Rango"], hdr)
        row += 1
        tmin = tmax = 0
        for g in ["CAB", "DAMA", "KIDS"]:
            s = summary[g]
            ws.write_row(row, 0, [GENDER_XL[g], s["produce"], s["produce_max"], s["produce_max"] - s["produce"]])
            tmin += s["produce"]
            tmax += s["produce_max"]
            row += 1
        ws.write_row(row, 0, ["TOTAL", tmin, tmax, tmax - tmin], bold)
        row += 3
        for genero in ["CAB", "DAMA", "KIDS"]:
            rd = rango[genero]
            ws.write(row, 0, f"{GENDER_XL[genero]} — RANGO MÍN / MÁX POR COLOR", section)
            row += 1
            tallas = sort_tallas(
                genero,
                list({t["talla"] for cr in rd["color_rows"] for t in cr["tallas"]}),
            )
            if not tallas:
                continue
            ws.write_row(row, 0, ["Color"] + tallas + ["Total"], hdr)
            row += 1
            tmin = {t: 0 for t in tallas}
            tmax = {t: 0 for t in tallas}
            for cr in rd["color_rows"]:
                by_min = {t["talla"]: t["produce_min"] for t in cr["tallas"]}
                by_max = {t["talla"]: t["produce_max"] for t in cr["tallas"]}
                ws.write_row(row, 0, [f"{cr['color']} — MÍN"] + [by_min.get(t, 0) for t in tallas] + [cr["min"]])
                row += 1
                ws.write_row(row, 0, [f"{cr['color']} — MÁX"] + [by_max.get(t, 0) for t in tallas] + [cr["max"]])
                row += 1
                for t in tallas:
                    tmin[t] += by_min.get(t, 0)
                    tmax[t] += by_max.get(t, 0)
            ws.write_row(row, 0, ["TOTAL — MÍN"] + [tmin[t] for t in tallas] + [sum(tmin.values())], bold)
            row += 1
            ws.write_row(row, 0, ["TOTAL — MÁX"] + [tmax[t] for t in tallas] + [sum(tmax.values())], bold)
            row += 2

        # ── Producción por Talla ──
        ws = wb.add_worksheet("Producción por Talla")
        row = 0
        ws.write(row, 0, "EXPLORE PANTS — CURVA DE TALLA POR GÉNERO (vs dashboard)", title)
        row += 2
        for genero in ["CAB", "DAMA", "KIDS"]:
            rd = rango[genero]
            ws.write(row, 0, f"{GENDER_XL[genero]} — TALLAS", section)
            row += 1
            ws.write_row(row, 0, ["Talla", "% prod.", "% ventas dash.", "Mínimo", "Máximo"], hdr)
            row += 1
            g_prod = summary[genero]["produce"]
            for t in sort_tallas(genero, list(rd["talla_totals"].keys())):
                td = rd["talla_totals"][t]
                ws.write(row, 0, t)
                ws.write(row, 1, td["min"] / g_prod if g_prod else 0, pct2)
                ws.write(row, 2, td.get("sales_pct", td["curve_pct"]) / 100, pct2)
                ws.write(row, 3, td["min"], num)
                ws.write(row, 4, td["max"], num)
                row += 1
            ws.write(row, 0, "TOTAL", bold)
            ws.write(row, 1, 1 if g_prod else 0, pct)
            ws.write(row, 2, 1, pct)
            ws.write(row, 3, g_prod, num)
            row += 2

        # ── Verificación tela comprada ──
        ws = wb.add_worksheet("Verificación Tela")
        row = 0
        ws.write(row, 0, f"EXPLORE PANTS — VERIFICACIÓN TELA {TELA_NOMBRE.upper()} COMPRADA", title)
        row += 2
        ws.write(row, 0, "Explore + Shorts R1 vs kg en existencias (objetivo: delta ≈ 0).")
        row += 2
        ws.write_row(
            row, 0,
            ["Color", "Und Explore", "Kg Explore", "Kg Shorts", "Kg total", "Kg existencia", "Delta"],
            hdr,
        )
        row += 1
        tot_need = tot_net = 0.0
        shorts = j.get("shorts_r1") or {}
        explore_total = sum(summary[g]["produce"] for g in summary)
        for tr in tela_check:
            ws.write(row, 0, tr["color"])
            ws.write(row, 1, tr["und_explore"], num)
            ws.write(row, 2, tr["kg_explore"], dec)
            ws.write(row, 3, tr["kg_shorts"], dec)
            ws.write(row, 4, tr["kg_necesario"], dec)
            ws.write(row, 5, tr["kg_existencia"], dec)
            ws.write(row, 6, tr["delta_kg"], dec)
            tot_need += tr["kg_necesario"]
            tot_net += tr["kg_existencia"]
            row += 1
        ws.write(row, 0, "TOTAL", bold)
        ws.write(row, 1, explore_total, num)
        ws.write(row, 4, round(tot_need, 2), dec)
        ws.write(row, 5, round(tot_net, 2), dec)
        ws.write(row, 6, round(tot_net - tot_need, 2), dec)
        row += 2
        ws.write(row, 0, f"Shorts R1 total: {shorts.get('total', 0):,} und · {shorts.get('kg_total', 0)} kg", section)
        row += 2
        ws.write(row, 0, "Consumo referencial por género (kg/und)", section)
        row += 1
        ws.write_row(row, 0, ["Género", "Consumo ref."], hdr)
        row += 1
        for g in ["CAB", "DAMA", "KIDS"]:
            ws.write_row(row, 0, [GENDER_XL[g], TELA_CONSUMO[g]])
            row += 1

        # ── Shorts R1 ──
        ws = wb.add_worksheet("Shorts R1")
        row = 0
        ws.write(row, 0, "SHORT SPORT R1 — NEGRO / GRIS OSCURO (CAB · DAMA)", title)
        row += 2
        ws.write_row(row, 0, ["Color tela", "Total und", "CAB", "DAMA", "Kg tela"], hdr)
        row += 1
        for sr in shorts.get("rows", []):
            ws.write_row(row, 0, [sr["color"], sr["total"], sr["CAB"], sr["DAMA"], sr["kg"]])
            row += 1
        ws.write(row, 0, "TOTAL", bold)
        ws.write(row, 1, shorts.get("total", 0), num)
        ws.write(row, 4, shorts.get("kg_total", 0), dec)

        # ── Tela solo Explore Pants ──
        ws = wb.add_worksheet("Tela Explore Pants")
        row = 0
        ws.write(row, 0, f"USO DE TELA — SOLO EXPLORE PANTS (sin Shorts R1)", title)
        row += 2
        ws.write(
            row,
            0,
            f"Consumo ref.: CAB {TELA_CONSUMO['CAB']} · DAMA {TELA_CONSUMO['DAMA']} · "
            f"KIDS {TELA_CONSUMO['KIDS']} kg/und · presupuesto = existencia − shorts",
        )
        row += 2
        etu = data.get("explore_tela_usage") or explore_tela_usage_rows(
            data["production_plan"], data.get("explore_kg_budget") or {}
        )
        ws.write_row(
            row,
            0,
            [
                "Color",
                "Und CAB",
                "Und DAMA",
                "Und KIDS",
                "Und total",
                "Kg CAB",
                "Kg DAMA",
                "Kg KIDS",
                "Kg Explore",
                "Kg presup.",
                "Delta kg",
            ],
            hdr,
        )
        row += 1
        t_kg = t_cap = 0.0
        t_und = 0
        for er in etu:
            ws.write_row(
                row,
                0,
                [
                    er["color"],
                    er["und_cab"],
                    er["und_dama"],
                    er["und_kids"],
                    er["und_total"],
                    er["kg_cab"],
                    er["kg_dama"],
                    er["kg_kids"],
                    er["kg_explore"],
                    er["kg_presupuesto"],
                    er["delta_kg"],
                ],
            )
            t_und += er["und_total"]
            t_kg += er["kg_explore"]
            t_cap += er["kg_presupuesto"]
            row += 1
        ws.write(row, 0, "TOTAL", bold)
        ws.write(row, 4, t_und, num)
        ws.write(row, 8, round(t_kg, 2), dec)
        ws.write(row, 9, round(t_cap, 2), dec)
        ws.write(row, 10, round(t_cap - t_kg, 2), dec)

        # ── Compra en 2 Órdenes (réplica justificación) ──
        ws = wb.add_worksheet("Compra en 2 Órdenes")
        row = 0
        ws.write(row, 0, "PROPUESTA COMPRA 65% AHORA / 35% SEPTIEMBRE (archivo justificación)", title)
        row += 2
        ws.write(row, 0, "ORDEN 1 — INMEDIATA (65%)", section)
        row += 1
        ws.write_row(row, 0, ["Ítem", "Kg", "Prioridad"], hdr)
        row += 1
        for item, kg, pri in ORDEN1_ITEMS:
            ws.write(row, 0, item)
            ws.write(row, 1, kg, dec)
            ws.write(row, 2, pri)
            row += 1
        ws.write(row, 0, "SUBTOTAL ORDEN 1", bold)
        ws.write(row, 1, ORDEN1_SUBTOTAL, dec)
        row += 2
        ws.write(row, 0, "ORDEN 2 — COMIENZOS SEPTIEMBRE (35%)", section)
        row += 1
        ws.write_row(row, 0, ["Ítem", "Kg", "Riesgo"], hdr)
        row += 1
        for item, kg, risk in ORDEN2_ITEMS:
            ws.write(row, 0, item)
            ws.write(row, 1, kg, dec)
            ws.write(row, 2, risk)
            row += 1
        ws.write(row, 0, "SUBTOTAL ORDEN 2", bold)
        ws.write(row, 1, ORDEN2_SUBTOTAL, dec)
        row += 2
        ws.write(row, 0, "TELA TOTAL (Explore + Shorts)", bold)
        ws.write(row, 1, TELA_PEDIDO_TOTAL, dec)

        # ── Producción Color × Talla ──
        ws = wb.add_worksheet("Producción Color × Talla")
        row = 0
        ws.write(row, 0, "EXPLORE PANTS — MATRIZ COLOR × TALLA", title)
        row += 2
        for genero in ["CAB", "DAMA", "KIDS"]:
            rd = rango[genero]
            tallas = sort_tallas(
                genero,
                list({t["talla"] for cr in rd["color_rows"] for t in cr["tallas"] if t["produce_min"] > 0}),
            )
            if not tallas:
                continue
            ws.write(row, 0, f"{GENDER_XL[genero]}", section)
            row += 1
            ws.write_row(row, 0, ["Color / Talla"] + tallas + ["Total"], hdr)
            row += 1
            for cr in rd["color_rows"]:
                by_min = {t["talla"]: t["produce_min"] for t in cr["tallas"]}
                ws.write_row(row, 0, [cr["color"]] + [by_min.get(t, 0) for t in tallas] + [cr["min"]])
                row += 1
            row += 1

        # ── Metodología ──
        ws = wb.add_worksheet("Metodología")
        ws.set_column("A:A", 100)
        row = 0
        ws.write(row, 0, "METODOLOGÍA — EXPLORE PANTS", title)
        row += 2
        lines = [
            f"1. Tela en almacén: {TELA_KG_TOTAL:.1f} kg — se usa completa (Explore + Shorts R1).",
            f"2. Explore Pants: und según tela restante · Shorts R1 = {SHORTS_TARGET:,} und (Negro/Gris, CAB/DAMA).",
            f"3. Rango MÍN/MÁX Explore: factor temporada alta ×{HIGH_SEASON_FACTOR}.",
            "4. COLOR: ranking ventas por género; si CAB Negro queda bajo vs Gris es por kg "
            "Negro/Gris en Shorts R1 + consumo de existencia Gris (no por mezcla de compra).",
            f"5. KIDS: tallas 2–12 (sin 14), incluye Kaki; Gris/Azul curva dashboard. "
            "CAB/DAMA: matriz manual (Kaki recortable para cuadrar tela).",
            "CAB sin 3XL · DAMA sin 2XL.",
            f"6. Shorts R1: CAB {SHORTS_CONSUMO['CAB']} · DAMA {SHORTS_CONSUMO['DAMA']} kg/und.",
            f"7. Explore: CAB {TELA_CONSUMO['CAB']} · DAMA {TELA_CONSUMO['DAMA']} · KIDS {TELA_CONSUMO['KIDS']} kg/und.",
            "8. Demanda Jul–Dic (2,228 und) y escenarios mensuales del archivo de justificación.",
            "9. Hoja 'Compra en 2 Órdenes': réplica del pedido de tela aprobado (referencia logística).",
        ]
        for line in lines:
            ws.write(row, 0, line)
            row += 1


def main() -> None:
    template = load_template_data()
    df = sales_df(template)
    data = build_data(template, df)

    html = patch_html(TEMPLATE.read_text(encoding="utf-8"), data)
    OUT_HTML.write_text(html, encoding="utf-8")
    export_excel(data, OUT_XLSX)

    ct = production_totals_by_color(data["production_plan"])
    print(f"Dashboard: {OUT_HTML}")
    print(f"Excel: {OUT_XLSX}")
    ex_total = data["target_produce_min"]["TOTAL"]
    shorts = data["shorts_r1"]
    print(f"Explore Pants: {ex_total:,} und (meta tela · ref {PRODUCE_TOTAL:,})")
    print(f"Shorts R1: {shorts['total']:,} und (meta {SHORTS_TARGET:,}) · {shorts['kg_total']} kg")
    for g in ["CAB", "DAMA", "KIDS"]:
        s = data["summary_genero"][g]["produce"]
        print(f"  {g}: {s} und")
    print("Verificación tela existencias (delta kg):")
    for tr in data["justificacion"]["tela_verificacion"]:
        print(f"  {tr['color']}: {tr['delta_kg']:+.2f} kg (explore {tr['kg_explore']} + shorts {tr['kg_shorts']})")
    for g in ["CAB", "KIDS"]:
        print(f"Ranking {g}:", [cr["color"] for cr in data["rango_data"][g]["color_rows"]])
    for color in ["Gris Oscuro", "Azul Marino"]:
        p = next(x for x in data["production_plan"] if x["genero"] == "KIDS" and x["color"] == color)
        tallas = {t["talla"]: t["produce_min"] for t in p["tallas"]}
        print(f"KIDS {color} ({p['produce_min']} und): tallas {tallas}")
    cab = sorted(
        [p for p in data["production_plan"] if p["genero"] == "CAB"],
        key=lambda x: -x["produce_min"],
    )
    print("CAB und (tela/shorts pueden cambiar vs ranking ventas):", [(p["color"], p["produce_min"]) for p in cab])
    cab2xl = sum(
        t["produce_min"]
        for p in data["production_plan"]
        if p["genero"] == "CAB"
        for t in p["tallas"]
        if t["talla"] == "2XL"
    )
    print(f"CAB 2XL total: {cab2xl} und")
    n_cab = next((p["produce_min"] for p in data["production_plan"] if p["genero"] == "CAB" and p["color"] == "Negro"), 0)
    n_dama = next((p["produce_min"] for p in data["production_plan"] if p["genero"] == "DAMA" and p["color"] == "Negro"), 0)
    print(f"Negro und CAB vs DAMA: {n_cab} vs {n_dama}")


if __name__ == "__main__":
    main()
