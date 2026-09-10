#!/usr/bin/env python3
"""Build EXPLORE PANTS dashboard + proyección Excel anclada a justificación Novaktex."""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = Path("/home/ubuntu/.cursor/projects/workspace/uploads")
TEMPLATE = UPLOADS / "Explore_Pants_0b91.html"
JUSTIF_XLSX = UPLOADS / "DATA_JUSTIFICACI_N_COMPRA_TELA_NOVAKTEX_REPEl_c4ef.xlsx"
OUT_HTML = ROOT / "DASHBOARD_EXPLORE_PANTS.html"
OUT_XLSX = ROOT / "EXPLORE_PANTS_Proyeccion_Produccion.xlsx"

MODELO = "EXPLORE PANTS"
TELA_NOMBRE = "Novaktex Repel"
TELA_UNIDAD = "kg"
TELA_SS = 0.20
MAX_RANGE_PCT = 0.06

# Consumo referencial (tela ya comprada — NO define las und a producir)
TELA_CONSUMO = {"CAB": 0.30, "DAMA": 0.25, "KIDS": 0.22}  # KIDS ligeramente sobre 0.20

# KIDS: peso un poco mayor que la curva pura de ventas
KIDS_GENDER_BOOST = 1.12

PRODUCTION_EXCLUDE_TALLAS: dict[str, set[str]] = {
    "KIDS": {"1"},
}

# ── Fuente de verdad: justificación compra tela (Explore Pants) ──
PRODUCE_TOTAL = 2908  # 80% pendiente sin tela
DEMAND_JUL_DEC = 2228
STOCK_REF = 2988
STOCK_TIENDAS_REF = 1636
STOCK_TALLER_REF = 1352

# kg compra con 20% merma (texto cifras clave del Excel)
TELA_KG_COLOR = {
    "Negro": 414.0,
    "Gris Oscuro": 361.0,
    "Kaki": 157.0,
    "Azul Marino": 91.0,
    "Verde Militar": 66.0,
}
TELA_KG_TOTAL = sum(TELA_KG_COLOR.values())  # 1089

# Proporción color de la compra (usa % del pedido, no convierte kg → und)
COLOR_SHARE = {c: kg / TELA_KG_TOTAL for c, kg in TELA_KG_COLOR.items()}

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
    return qty, int(math.ceil(qty * (1 + MAX_RANGE_PCT)))


def allocate_by_weights(weights: dict[tuple[str, str, str], float], target: int) -> dict[tuple[str, str, str], int]:
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


def color_unit_targets() -> dict[str, int]:
    """Reparte PRODUCE_TOTAL según proporción color de la compra (justificación)."""
    keys = list(COLOR_SHARE.keys())
    floats = [PRODUCE_TOTAL * COLOR_SHARE[c] for c in keys]
    ints = [int(math.floor(f)) for f in floats]
    diff = PRODUCE_TOTAL - sum(ints)
    if diff > 0:
        order = sorted(range(len(keys)), key=lambda i: floats[i] - ints[i], reverse=True)
        for i in range(diff):
            ints[order[i % len(order)]] += 1
    return {keys[i]: ints[i] for i in range(len(keys))}


def stock_for_genero(stock: dict, genero: str) -> int:
    total = 0
    for k, v in stock.items():
        if k.endswith(f"/{genero}"):
            total += int(v)
    return total


def build_production_plan(
    df: pd.DataFrame, shares: dict[str, float], stock: dict
) -> tuple[list, dict, dict]:
    color_targets = color_unit_targets()
    plan: list = []
    summary: dict = {}
    rango: dict = {}
    total_sales = df["v"].sum() or 1

    # género × color: curva de ventas por color, con boost moderado en KIDS
    gc_targets: dict[tuple[str, str], int] = {}
    for color, c_total in color_targets.items():
        cdf = df[df["prod_color"] == color]
        g_weights: dict[str, float] = {}
        for genero in ["CAB", "DAMA", "KIDS"]:
            gcv = float(cdf[cdf["genero"] == genero]["v"].sum())
            if genero == "KIDS" and gcv > 0:
                gcv *= KIDS_GENDER_BOOST
            g_weights[genero] = gcv
        g_total = sum(g_weights.values()) or 1.0
        allocated = allocate_by_weights(
            {(genero, color): g_weights[genero] for genero in g_weights},
            c_total,
        )
        gc_targets.update(allocated)

    # cuadrar total exacto
    current = sum(gc_targets.values())
    if current != PRODUCE_TOTAL and current > 0:
        factor = PRODUCE_TOTAL / current
        keys = list(gc_targets.keys())
        floats = [gc_targets[k] * factor for k in keys]
        ints = [int(math.floor(f)) for f in floats]
        diff = PRODUCE_TOTAL - sum(ints)
        if diff > 0:
            order = sorted(range(len(keys)), key=lambda i: floats[i] - ints[i], reverse=True)
            for i in range(diff):
                ints[order[i % len(order)]] += 1
        gc_targets = {keys[i]: ints[i] for i in range(len(keys))}

    for genero in ["CAB", "DAMA", "KIDS"]:
        gdf = df[df["genero"] == genero]
        color_rows = []
        talla_totals: dict = defaultdict(lambda: {"min": 0, "max": 0, "curve_pct": 0.0})

        for color in COLORES_PRODUCCION:
            c_target = gc_targets.get((genero, color), 0)
            if c_target <= 0:
                continue
            cdf = gdf[gdf["prod_color"] == color]
            excluded = PRODUCTION_EXCLUDE_TALLAS.get(genero, set())
            t_sales = cdf.groupby("talla")["v"].sum()
            if excluded:
                t_sales = t_sales.drop(labels=list(excluded), errors="ignore")
            if t_sales.sum() <= 0:
                tallas = sort_tallas(
                    genero,
                    [t for t in TALLA_ORDER[genero][:5] if t not in excluded],
                )
                t_mix = {t: 1 / len(tallas) for t in tallas}
            else:
                tallas = sort_tallas(genero, list(t_sales.index.astype(str)))
                t_mix = (t_sales / t_sales.sum()).to_dict()

            allocated = allocate_by_weights({t: t_mix.get(t, 0) for t in tallas}, c_target)
            talla_objs = []
            for t in tallas:
                qty = allocated.get(t, 0)
                if qty <= 0:
                    continue
                pm, px = min_max_qty(qty)
                t_obj = {
                    "talla": str(t),
                    "produce": pm,
                    "produce_min": pm,
                    "produce_max": px,
                    "curve_pct": round(t_mix.get(t, 0) * 100, 1),
                    "store_split": distribute_units(pm, shares, ALL_DIST_STORES),
                    "store_split_max": distribute_units(px, shares, ALL_DIST_STORES),
                }
                talla_objs.append(t_obj)
                talla_totals[t]["min"] += pm
                talla_totals[t]["max"] += px

            c_min = sum(t["produce_min"] for t in talla_objs)
            c_max = sum(t["produce_max"] for t in talla_objs)
            sales_pct = cdf["v"].sum() / total_sales
            plan.append({
                "genero": genero,
                "color": color,
                "color_pct": round(cdf["v"].sum() / total_sales * 100, 1),
                "sales_pct": sales_pct,
                "produce": c_min,
                "produce_min": c_min,
                "produce_max": c_max,
                "tallas": sorted(talla_objs, key=lambda x: -x["produce_min"]),
                "store_split": distribute_units(c_min, shares, ALL_DIST_STORES),
            })
            color_rows.append({
                "color": color,
                "pct": round(c_min / color_targets[color] * 100, 1) if color_targets[color] else 0,
                "sales_pct": sales_pct,
                "min": c_min,
                "max": c_max,
                "tallas": talla_objs,
            })

        g_prod = sum(p["produce_min"] for p in plan if p["genero"] == genero)
        g_prod_max = sum(p["produce_max"] for p in plan if p["genero"] == genero)
        for td in talla_totals.values():
            td["curve_pct"] = round(td["min"] / g_prod * 100, 1) if g_prod else 0.0

        summary[genero] = {
            "produce": g_prod,
            "produce_max": g_prod_max,
            "stk": stock_for_genero(stock, genero),
        }
        rango[genero] = {
            "color_rows": sorted(color_rows, key=lambda x: x["min"], reverse=True),
            "talla_totals": dict(talla_totals),
            "shares": shares,
        }

    return plan, summary, rango


def build_data(template: dict, df: pd.DataFrame) -> dict:
    stock = template.get("stock") or {}
    stock_total = sum(stock.values())
    sbs = template.get("stock_by_store") or {}
    shares = store_weights(df.groupby("tienda")["v"].sum().to_dict())
    plan, summary, rango = build_production_plan(df, shares, stock)

    color_targets = color_unit_targets()
    tela_rows = []
    for color, kg in TELA_KG_COLOR.items():
        und = color_targets[color]
        net = kg / (1 + TELA_SS)
        tela_rows.append({
            "color": color,
            "und": und,
            "share_pct": round(COLOR_SHARE[color] * 100, 2),
            "kg_compra": kg,
            "kg_consumo": round(net, 1),
        })

    data = {**template}
    data.update({
        "nombre": MODELO,
        "method": "justificacion_novaktex_unidades",
        "tela_consumo_ref": TELA_CONSUMO,
        "kids_gender_boost": KIDS_GENDER_BOOST,
        "target_produce_min": {"TOTAL": PRODUCE_TOTAL, **{g: summary[g]["produce"] for g in summary}},
        "production_plan": plan,
        "summary_genero": summary,
        "rango_data": rango,
        "justificacion": {
            "fuente": JUSTIF_XLSX.name,
            "produce_total": PRODUCE_TOTAL,
            "demand_jul_dec": DEMAND_JUL_DEC,
            "stock_ref": STOCK_REF,
            "stock_actual": stock_total,
            "tela_kg_color": TELA_KG_COLOR,
            "tela_kg_total": TELA_KG_TOTAL,
            "tela_pedido_total": TELA_PEDIDO_TOTAL,
            "orden1_subtotal": ORDEN1_SUBTOTAL,
            "orden2_subtotal": ORDEN2_SUBTOTAL,
            "demand_months": DEMAND_MONTHS,
            "fin_dic_sin_compra_ref": 760,
            "fin_dic_con_produccion_ref": 3668,
            "fin_dic_sin_compra_actual": stock_total - DEMAND_JUL_DEC,
            "fin_dic_con_produccion_actual": stock_total + PRODUCE_TOTAL - DEMAND_JUL_DEC,
            "tela_rows": tela_rows,
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
        f"{PRODUCE_TOTAL:,} und (proporción color compra · talla ventas · KIDS +{int((KIDS_GENDER_BOOST - 1) * 100)}%) "
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
    color_targets = color_unit_targets()

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
            f"Producción objetivo (80% pendiente): {PRODUCE_TOTAL:,} und",
            f"Demanda proyectada Jul–Dic: {DEMAND_JUL_DEC:,} und",
            f"Stock referencia justificación: {STOCK_REF:,} und ({STOCK_TIENDAS_REF:,} tiendas + {STOCK_TALLER_REF:,} taller)",
            f"Stock actual dashboard: {j['stock_actual']:,} und",
            f"Tela ya comprada (referencia): {TELA_KG_TOTAL:.0f} kg Explore",
            f"Pedido total archivo (Explore + Shorts): {TELA_PEDIDO_TOTAL:.0f} kg · split 65% / 35%",
            "Color: proporción del pedido (Negro 38% · Gris Oscuro 33% · Kaki 14% · Azul 8% · Verde 6%)",
            "Talla/género: curva de ventas del dashboard · KIDS con boost moderado (+12%)",
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

        # ── Cantidades por Colores ──
        ws = wb.add_worksheet("Cantidades por Colores")
        row = 0
        ws.write(row, 0, "EXPLORE PANTS — UNIDADES A PRODUCIR POR COLOR", title)
        row += 2
        ws.write_row(
            row, 0,
            ["Color", "Und a producir", "% compra (color)", "Kg tela comprada (ref.)", "Kg neto (ref.)"],
            hdr,
        )
        row += 1
        for color in COLORES_PRODUCCION:
            und = color_targets[color]
            kg = TELA_KG_COLOR[color]
            ws.write(row, 0, color)
            ws.write(row, 1, und, num)
            ws.write(row, 2, COLOR_SHARE[color], pct2)
            ws.write(row, 3, kg, dec)
            ws.write(row, 4, round(kg / (1 + TELA_SS), 1), dec)
            row += 1
        ws.write(row, 0, "TOTAL", bold)
        ws.write(row, 1, PRODUCE_TOTAL, num)
        ws.write(row, 2, 1, pct)
        ws.write(row, 3, TELA_KG_TOTAL, dec)

        # ── Producción por Talla ──
        ws = wb.add_worksheet("Producción por Talla")
        row = 0
        ws.write(row, 0, "EXPLORE PANTS — CURVA DE TALLA POR GÉNERO", title)
        row += 2
        for genero in ["CAB", "DAMA", "KIDS"]:
            rd = rango[genero]
            ws.write(row, 0, f"{GENDER_XL[genero]} — TALLAS", section)
            row += 1
            ws.write_row(row, 0, ["Talla", "%", "Mínimo", "Máximo"], hdr)
            row += 1
            g_prod = summary[genero]["produce"]
            for t in sort_tallas(genero, list(rd["talla_totals"].keys())):
                td = rd["talla_totals"][t]
                ws.write(row, 0, t)
                ws.write(row, 1, round(td["curve_pct"]) / 100, pct)
                ws.write(row, 2, td["min"], num)
                ws.write(row, 3, td["max"], num)
                row += 1
            ws.write(row, 0, "TOTAL", bold)
            ws.write(row, 1, 1 if g_prod else 0, pct)
            ws.write(row, 2, g_prod, num)
            row += 2

        # ── Tela comprada (referencia) ──
        ws = wb.add_worksheet("Tela Comprada (ref.)")
        row = 0
        ws.write(row, 0, f"EXPLORE PANTS — TELA {TELA_NOMBRE.upper()} YA COMPRADA", title)
        row += 2
        ws.write(row, 0, "La tela ya está pedida. Esta hoja es referencia del pedido, no recalcula las und.")
        row += 2
        ws.write_row(row, 0, ["Color", "Und a producir", "% color compra", "Kg compra (+20% SS)", "Kg neto"], hdr)
        row += 1
        for tr in j["tela_rows"]:
            ws.write(row, 0, tr["color"])
            ws.write(row, 1, tr["und"], num)
            ws.write(row, 2, tr["share_pct"] / 100, pct2)
            ws.write(row, 3, tr["kg_compra"], dec)
            ws.write(row, 4, tr["kg_consumo"], dec)
            row += 1
        ws.write(row, 0, "TOTAL EXPLORE", bold)
        ws.write(row, 1, PRODUCE_TOTAL, num)
        ws.write(row, 2, 1, pct)
        ws.write(row, 3, TELA_KG_TOTAL, dec)
        row += 2
        ws.write(row, 0, "Consumo referencial por género (kg/und)", section)
        row += 1
        ws.write_row(row, 0, ["Género", "Consumo ref."], hdr)
        row += 1
        for g in ["CAB", "DAMA", "KIDS"]:
            ws.write_row(row, 0, [GENDER_XL[g], TELA_CONSUMO[g]])
            row += 1

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
            "1. TOTAL a producir: 2,908 und (80% pendiente, justificación Novaktex). La tela ya está comprada.",
            "2. COLOR: proporción del pedido de tela — Negro 38.0% · Gris Oscuro 33.1% · Kaki 14.4% · Azul Marino 8.4% · Verde Militar 6.1%.",
            "3. GÉNERO y TALLA: curva de ventas del dashboard dentro de cada color; KIDS con boost +12% sobre su share de ventas.",
            f"4. Consumo referencial (no define und): CAB {TELA_CONSUMO['CAB']} · DAMA {TELA_CONSUMO['DAMA']} · KIDS {TELA_CONSUMO['KIDS']} kg/und.",
            "5. KIDS excluye talla 1 en producción (venta marginal). Gris (ventas) → Gris Oscuro (producción).",
            "6. Demanda Jul–Dic (2,228 und) y escenarios mensuales del archivo de justificación.",
            "7. Hoja 'Compra en 2 Órdenes': réplica del pedido de tela aprobado (referencia logística).",
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

    ct = color_unit_targets()
    print(f"Dashboard: {OUT_HTML}")
    print(f"Excel: {OUT_XLSX}")
    print(f"Producir total: {PRODUCE_TOTAL:,} und (justificación · tela ya comprada)")
    print("Por color (und / % compra):")
    for c in COLORES_PRODUCCION:
        print(f"  {c}: {ct[c]:>4} und · {COLOR_SHARE[c]*100:.1f}%")
    for g in ["CAB", "DAMA", "KIDS"]:
        s = data["summary_genero"][g]["produce"]
        pct = s / PRODUCE_TOTAL * 100 if PRODUCE_TOTAL else 0
        print(f"  {g}: {s} und ({pct:.1f}%)")


if __name__ == "__main__":
    main()
