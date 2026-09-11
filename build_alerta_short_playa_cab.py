#!/usr/bin/env python3
"""Alerta de producción SHORT PLAYA CAB — inventario, ventas y tela."""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "short_playa_cab"
OUT_HTML = ROOT / "ALERTA_PRODUCCION_SHORT_PLAYA_CAB.html"
OUT_XLSX = ROOT / "ALERTA_PRODUCCION_SHORT_PLAYA_CAB.xlsx"
OUT_JSON = DATA_DIR / "plan.json"

AS_OF = "2026-09-11"
MODELO = "SHORT PLAYA CAB"
CONSUMO_M = 0.75
TALLAS = ["S", "M", "L", "XL", "2XL"]
COLORES = ["Azul Pizarra", "Azul Verdoso", "Cereza", "Marron", "Verde Pino"]
RETAIL = [
    "CERRO VERDE",
    "GRIETA",
    "SAMBIL CHACAO",
    "SAMBIL VALENCIA",
    "TOLON",
    "VELA",
    "GRAND PLAZ",
]
CHANNELS = ["WEB", "PEDIDOS", "CORPORATIVO"]
WINDOW = [f"2026-{m:02d}" for m in range(2, 9)]  # Feb–Ago completos
SEP = "2026-09"

SKU = {
    ("Cereza", "S"): "SHOUNCA170TS",
    ("Cereza", "M"): "SHOUNCA170TM",
    ("Cereza", "L"): "SHOUNCA170TL",
    ("Cereza", "XL"): "SHOUNCA170TXL",
    ("Cereza", "2XL"): "SHOUNCA170T2XL",
    ("Azul Verdoso", "S"): "SHOUNCA186TS",
    ("Azul Verdoso", "M"): "SHOUNCA186TM",
    ("Azul Verdoso", "L"): "SHOUNCA186TL",
    ("Azul Verdoso", "XL"): "SHOUNCA186TXL",
    ("Azul Verdoso", "2XL"): "SHOUNCA186T2XL",
    ("Azul Pizarra", "S"): "SHOUNCA187TS",
    ("Azul Pizarra", "M"): "SHOUNCA187TM",
    ("Azul Pizarra", "L"): "SHOUNCA187TL",
    ("Azul Pizarra", "XL"): "SHOUNCA187TXL",
    ("Azul Pizarra", "2XL"): "SHOUNCA187T2XL",
    ("Marron", "S"): "SHOUNCA38TS",
    ("Marron", "M"): "SHOUNCA38TM",
    ("Marron", "L"): "SHOUNCA38TL",
    ("Marron", "XL"): "SHOUNCA38TXL",
    ("Marron", "2XL"): "SHOUNCA38T2XL",
    ("Verde Pino", "S"): "SHOUNCA69TS",
    ("Verde Pino", "M"): "SHOUNCA69TM",
    ("Verde Pino", "L"): "SHOUNCA69TL",
    ("Verde Pino", "XL"): "SHOUNCA69TXL",
    ("Verde Pino", "2XL"): "SHOUNCA69T2XL",
}

TELA_MAP = {
    "AZUL PIZZARRA": "Azul Pizarra",
    "AZUL PIZARRA": "Azul Pizarra",
    "AZUL VERDOSO": "Azul Verdoso",
    "VERDE PINO": "Verde Pino",
    "HABANO": "Marron",
    "ROJO": "Cereza",
}
TELA_REMANENTE = {
    "AGUAMARINA": "Aguamarina",
    "VERDE OLIVA": "Verde Oliva",
    "AZUL MARINO": "Azul Marino",
    "GRIS AZULADO": "Gris Azulado",
}

COLOR_HEX = {
    "Azul Pizarra": "#64748b",
    "Azul Verdoso": "#0f766e",
    "Cereza": "#be123c",
    "Marron": "#7c4a2d",
    "Verde Pino": "#14532d",
    "Aguamarina": "#2dd4bf",
    "Verde Oliva": "#4d7c0f",
    "Azul Marino": "#1e3a8a",
    "Gris Azulado": "#475569",
}

SCENARIOS = {
    "recomendado": {
        "label": "Recomendado · temporada alta",
        "hs": 1.30,
        "cov": 4.0,
        "vela_stockout": 1.30,
        "mgta_mult": 2.0,
        "note": "4 meses de cobertura (dic–mar), VELA ×1.30 por quiebres, MGTA 2× GRIETA por ser zona de playa.",
    },
    "conservador": {
        "label": "Conservador",
        "hs": 1.25,
        "cov": 3.0,
        "vela_stockout": 1.00,
        "mgta_mult": 1.5,
        "note": "3 meses de cobertura, sin inflar VELA, MGTA 1.5× GRIETA (misma regla de otras líneas).",
    },
}

MONTH_LABEL = {
    "2025-10": "Oct 25",
    "2025-11": "Nov 25",
    "2025-12": "Dic 25",
    "2026-01": "Ene 26",
    "2026-02": "Feb 26",
    "2026-03": "Mar 26",
    "2026-04": "Abr 26",
    "2026-05": "May 26",
    "2026-06": "Jun 26",
    "2026-07": "Jul 26",
    "2026-08": "Ago 26",
    "2026-09": "Sep 26*",
}

INV_STORE = {
    "CERRO VERDE": "CERRO VERDE",
    "CHACAO": "SAMBIL CHACAO",
    "GRANDPLAZ": "GRAND PLAZ",
    "GRAND PLAZ": "GRAND PLAZ",
    "GRIETA": "GRIETA",
    "SAMBIL": "SAMBIL VALENCIA",
    "TOLON": "TOLON",
    "VELA": "VELA",
}
VEN_STORE = {
    "LA VELA": "VELA",
    "VELA": "VELA",
    "LA GRIETA": "GRIETA",
    "GRIETA": "GRIETA",
    "CERRO VERDE": "CERRO VERDE",
    "SAMBIL CHACAO": "SAMBIL CHACAO",
    "SAMBIL VALENCIA": "SAMBIL VALENCIA",
    "GRAND PLAZ": "GRAND PLAZ",
    "GRANDPLAZ": "GRAND PLAZ",
    "TOLON": "TOLON",
    "CHACAO": "SAMBIL CHACAO",
    "WEB": "WEB",
    "PEDIDOS": "PEDIDOS",
    "CORPORATIVO": "CORPORATIVO",
}


def _up(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().upper())


def month_key(year, mes: str) -> str:
    mes = str(mes).strip().lower()
    months = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }
    return f"{int(year):04d}-{months[mes]:02d}"


def load_frames():
    inv = pd.read_excel(DATA_DIR / "inventario_actual.xlsx")
    ven = pd.read_excel(DATA_DIR / "ventas.xlsx")
    tela = pd.read_excel(DATA_DIR / "inventario_tela.xlsx")
    inv["tienda"] = inv["Ubicación"].map(lambda s: INV_STORE[_up(s)])
    ven["tienda"] = ven["tienda / ubicación"].map(lambda s: VEN_STORE[_up(s)])
    ven["period"] = [month_key(a, b) for a, b in zip(ven["Año"], ven["Mes"])]
    ven["coleccion"] = ven["COLOR"].where(ven["COLOR"].isin(COLORES), "anterior")
    ven.loc[ven["COLOR"].isin(COLORES), "coleccion"] = "actual"
    return inv, ven, tela


def parse_tela(tela: pd.DataFrame):
    rows = []
    for _, r in tela.iterrows():
        prod = str(r["Producto"])
        metros = float(r["Cantidad en inventario"])
        m = re.search(r"/\s*([A-ZÁÉÍÓÚÑ ]+)\s*-\s*(\d+)", prod)
        color_raw = m.group(1).strip() if m else prod
        code = m.group(2) if m else ""
        sku_m = re.search(r"\[([^\]]+)\]", prod)
        sku = sku_m.group(1) if sku_m else ""
        if color_raw in TELA_MAP:
            dest = TELA_MAP[color_raw]
            kind = "activa"
        elif color_raw in TELA_REMANENTE:
            dest = TELA_REMANENTE[color_raw]
            kind = "remanente"
        else:
            dest = color_raw.title()
            kind = "otra"
        rows.append(
            {
                "sku": sku,
                "tela": color_raw.title(),
                "color_prod": dest,
                "metros": round(metros, 2),
                "piezas": int(math.floor(metros / CONSUMO_M + 1e-9)),
                "kind": kind,
                "code": code,
            }
        )
    return rows


def stock_matrix(inv: pd.DataFrame):
    """tienda, color, talla -> qty (can be negative)."""
    g = inv.groupby(["tienda", "COLOR", "TALLA"], as_index=False)["Cantidad en inventario"].sum()
    raw = {}
    phys = {}
    deficit = {}
    for _, r in g.iterrows():
        k = (r["tienda"], r["COLOR"], r["TALLA"])
        q = int(r["Cantidad en inventario"])
        raw[k] = q
        phys[k] = max(0, q)
        deficit[k] = max(0, -q)
    return raw, phys, deficit


def sales_cube(ven: pd.DataFrame):
    cur = ven[(ven["coleccion"] == "actual") & (ven["TALLA"].isin(TALLAS))].copy()
    cube = defaultdict(lambda: defaultdict(int))  # store -> period -> qty at color/size too
    by = defaultdict(int)
    for _, r in cur.iterrows():
        key = (r["tienda"], r["COLOR"], r["TALLA"], r["period"])
        by[key] += int(r["Cant. ordenada"])
    return by, cur


def first_month(store: str, by_keys) -> str | None:
    months = [p for (s, c, t, p), v in by_keys.items() if s == store and p in WINDOW and v != 0]
    return min(months) if months else None


def op_months(store: str, by_keys):
    fm = first_month(store, by_keys)
    if not fm:
        return []
    return [m for m in WINDOW if m >= fm]


def vel_store_sku(by_keys, store, color, talla, months, factor=1.0):
    if not months:
        return 0.0
    total = sum(by_keys.get((store, color, talla, p), 0) for p in months)
    return (total / len(months)) * factor


def round_to_total(weights: list[float], total: int) -> list[int]:
    if total <= 0 or not weights:
        return [0] * len(weights)
    s = sum(weights)
    if s <= 0:
        return [0] * len(weights)
    raw = [w / s * total for w in weights]
    floors = [int(math.floor(x)) for x in raw]
    leftover = total - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in order[: max(0, leftover)]:
        floors[i] += 1
    return floors


def severity(cob: float | None):
    if cob is None:
        return "ok"
    if cob < 1:
        return "crit"
    if cob < 2:
        return "alta"
    if cob < 3:
        return "media"
    return "ok"


def build_plan(inv, ven, tela_rows, sc):
    raw, phys, deficit = stock_matrix(inv)
    by_keys, cur = sales_cube(ven)

    store_months = {s: op_months(s, by_keys) for s in RETAIL}
    channel_months = WINDOW[:]

    v_base = defaultdict(float)  # store,color,talla
    for store in RETAIL:
        months = store_months[store]
        f = sc["vela_stockout"] if store == "VELA" else 1.0
        for c in COLORES:
            for t in TALLAS:
                v_base[(store, c, t)] = vel_store_sku(by_keys, store, c, t, months, f)
    for store in CHANNELS:
        for c in COLORES:
            for t in TALLAS:
                v_base[(store, c, t)] = vel_store_sku(by_keys, store, c, t, channel_months, 1.0)

    v_hs = {k: v * sc["hs"] for k, v in v_base.items()}

    grieta_base = sum(v_base[( "GRIETA", c, t)] for c in COLORES for t in TALLAS)
    mgta_month = grieta_base * sc["mgta_mult"] * sc["hs"]
    # Mix MGTA: proporción nacional de ventas Feb–Ago (colección actual)
    mix = defaultdict(float)
    for c in COLORES:
        for t in TALLAS:
            mix[(c, t)] = sum(by_keys.get((s, c, t, p), 0) for s in RETAIL + CHANNELS for p in WINDOW)
    mix_total = sum(mix.values()) or 1
    v_mgta = {(c, t): mgta_month * mix[(c, t)] / mix_total for c in COLORES for t in TALLAS}

    cov = sc["cov"]
    rows = []
    for c in COLORES:
        for t in TALLAS:
            stk = sum(phys.get((s, c, t), 0) for s in RETAIL)
            defi = sum(deficit.get((s, c, t), 0) for s in RETAIL)
            vel_exist = sum(v_hs[(s, c, t)] for s in RETAIL + CHANNELS)
            vel_total = vel_exist + v_mgta[(c, t)]
            target = vel_exist * cov + v_mgta[(c, t)] * cov + defi
            need = max(0.0, target - stk)
            cob_now = (stk / vel_exist) if vel_exist > 0.05 else (99 if stk else 0)
            cob_with_mgta = (stk / vel_total) if vel_total > 0.05 else (99 if stk else 0)
            store_need = {}
            for s in RETAIL:
                tgt_s = v_hs[(s, c, t)] * cov + deficit.get((s, c, t), 0)
                store_need[s] = max(0.0, tgt_s - phys.get((s, c, t), 0))
            store_need["MGTA"] = v_mgta[(c, t)] * cov
            rows.append(
                {
                    "color": c,
                    "talla": t,
                    "sku": SKU[(c, t)],
                    "stk": stk,
                    "deficit": defi,
                    "v_base": sum(v_base[(s, c, t)] for s in RETAIL + CHANNELS),
                    "v_hs": vel_exist,
                    "v_mgta": v_mgta[(c, t)],
                    "v_total": vel_total,
                    "target": target,
                    "need": need,
                    "cob": round(cob_now, 2),
                    "cob_mgta": round(cob_with_mgta, 2),
                    "sev": severity(cob_now),
                    "store_need": store_need,
                    "store_stk": {s: phys.get((s, c, t), 0) for s in RETAIL},
                    "store_def": {s: deficit.get((s, c, t), 0) for s in RETAIL},
                    "store_vhs": {s: v_hs[(s, c, t)] for s in RETAIL},
                }
            )

    # Fabric cap per color
    cap = {c: 0 for c in COLORES}
    tela_det = []
    for tr in tela_rows:
        if tr["kind"] == "activa":
            cap[tr["color_prod"]] += tr["piezas"]
        tela_det.append(tr)

    produce = {}
    tela_alert = []
    for c in COLORES:
        subset = [r for r in rows if r["color"] == c]
        need_sum = sum(r["need"] for r in subset)
        piezas_cap = cap.get(c, 0)
        take = min(need_sum, piezas_cap)
        if need_sum > piezas_cap + 0.4:
            tela_alert.append(
                {
                    "color": c,
                    "need": round(need_sum),
                    "cap": piezas_cap,
                    "faltan": int(math.ceil(need_sum - piezas_cap)),
                    "metros_faltan": round((need_sum - piezas_cap) * CONSUMO_M, 1),
                }
            )
        weights = [r["need"] for r in subset]
        allocated = round_to_total(weights, int(round(take)))
        for r, q in zip(subset, allocated):
            # No producir S si cobertura S >= 3 y la necesidad es solo "relleno de curva"
            r["produce_unconst"] = int(round(r["need"]))
            r["produce"] = q
            produce[(c, r["talla"])] = q

    # Distribution of produced units by store_need (priority VELA, then L/M, then MGTA)
    dist_rows = []
    for r in rows:
        q = r["produce"]
        stores = RETAIL + ["MGTA"]
        weights = []
        for s in stores:
            w = r["store_need"].get(s, 0)
            if s == "VELA":
                w *= 1.6
            elif s == "MGTA":
                w *= 1.35
            if r["talla"] in ("L", "M"):
                w *= 1.25
            if r["talla"] == "S" and s != "MGTA":
                w *= 0.45  # no mandar más S a tiendas saturadas
            weights.append(w)
        alloc = round_to_total(weights, q)
        r["dist"] = dict(zip(stores, alloc))
        for s, a in zip(stores, alloc):
            if a:
                dist_rows.append(
                    {
                        "tienda": s,
                        "color": r["color"],
                        "talla": r["talla"],
                        "sku": r["sku"],
                        "und": a,
                    }
                )

    totals = {
        "produce": sum(r["produce"] for r in rows),
        "produce_unconst": sum(r["produce_unconst"] for r in rows),
        "stk": sum(r["stk"] for r in rows),
        "deficit": sum(r["deficit"] for r in rows),
        "v_base": sum(r["v_base"] for r in rows),
        "v_hs": sum(r["v_hs"] for r in rows),
        "v_mgta": sum(r["v_mgta"] for r in rows),
        "v_total": sum(r["v_total"] for r in rows),
        "metros": round(sum(r["produce"] for r in rows) * CONSUMO_M, 1),
    }
    totals["cob"] = round(totals["stk"] / totals["v_hs"], 2) if totals["v_hs"] else 0
    totals["cob_post"] = round(
        (totals["stk"] + totals["produce"]) / totals["v_total"], 2
    ) if totals["v_total"] else 0

    by_color = []
    for c in COLORES:
        subset = [r for r in rows if r["color"] == c]
        metros_disp = next((tr["metros"] for tr in tela_rows if tr["color_prod"] == c and tr["kind"] == "activa"), 0)
        piezas = next((tr["piezas"] for tr in tela_rows if tr["color_prod"] == c and tr["kind"] == "activa"), 0)
        p = sum(x["produce"] for x in subset)
        by_color.append(
            {
                "color": c,
                "stk": sum(x["stk"] for x in subset),
                "v_hs": sum(x["v_hs"] for x in subset),
                "v_mgta": sum(x["v_mgta"] for x in subset),
                "need": round(sum(x["need"] for x in subset)),
                "produce": p,
                "produce_unconst": sum(x["produce_unconst"] for x in subset),
                "cob": round(
                    sum(x["stk"] for x in subset) / max(0.01, sum(x["v_hs"] for x in subset)),
                    2,
                ),
                "tela_m": metros_disp,
                "tela_pcs": piezas,
                "tela_uso": round(p * CONSUMO_M, 1),
                "tela_sobra": round(metros_disp - p * CONSUMO_M, 1),
                "tallas": {x["talla"]: x["produce"] for x in subset},
            }
        )

    by_talla = []
    sales_t = {t: mix[("Azul Pizarra", t)] for t in TALLAS}  # placeholder
    sales_t = {t: sum(mix[(c, t)] for c in COLORES) for t in TALLAS}
    stk_t = {t: sum(r["stk"] for r in rows if r["talla"] == t) for t in TALLAS}
    prod_t = {t: sum(r["produce"] for r in rows if r["talla"] == t) for t in TALLAS}
    st = sum(sales_t.values()) or 1
    sk = sum(stk_t.values()) or 1
    sp = sum(prod_t.values()) or 1
    for t in TALLAS:
        by_talla.append(
            {
                "talla": t,
                "ventas": sales_t[t],
                "ventas_pct": round(100 * sales_t[t] / st, 1),
                "stk": stk_t[t],
                "stk_pct": round(100 * stk_t[t] / sk, 1),
                "produce": prod_t[t],
                "produce_pct": round(100 * prod_t[t] / sp, 1),
                "cob": round(
                    stk_t[t]
                    / max(0.01, sum(r["v_hs"] for r in rows if r["talla"] == t)),
                    2,
                ),
            }
        )

    return {
        "rows": rows,
        "totals": totals,
        "by_color": by_color,
        "by_talla": by_talla,
        "tela_alert": tela_alert,
        "tela": tela_rows,
        "cap": cap,
        "dist_rows": dist_rows,
        "store_months": {s: store_months[s] for s in RETAIL},
        "grieta_base": grieta_base,
        "mgta_month": mgta_month,
        "mix_total": mix_total,
    }


def monthly_series(ven: pd.DataFrame):
    ven2 = ven.copy()
    order = sorted(ven2["period"].unique())
    all_m = []
    act_m = []
    for p in order:
        all_m.append(int(ven2.loc[ven2["period"] == p, "Cant. ordenada"].sum()))
        act_m.append(
            int(
                ven2.loc[
                    (ven2["period"] == p) & (ven2["coleccion"] == "actual"),
                    "Cant. ordenada",
                ].sum()
            )
        )
    store_month = defaultdict(lambda: defaultdict(int))
    cur = ven2[ven2["coleccion"] == "actual"]
    for _, r in cur.iterrows():
        store_month[r["tienda"]][r["period"]] += int(r["Cant. ordenada"])
    color_month = defaultdict(lambda: defaultdict(int))
    for _, r in cur.iterrows():
        if r["COLOR"] in COLORES:
            color_month[r["COLOR"]][r["period"]] += int(r["Cant. ordenada"])
    return {
        "order": order,
        "labels": [MONTH_LABEL.get(p, p) for p in order],
        "all": all_m,
        "actual": act_m,
        "store": {s: [store_month[s].get(p, 0) for p in order] for s in RETAIL},
        "color": {c: [color_month[c].get(p, 0) for p in order] for c in COLORES},
    }


def store_snapshot(inv, ven, plan_rec):
    raw, phys, deficit = stock_matrix(inv)
    by_keys, _ = sales_cube(ven)
    out = []
    for s in RETAIL:
        stk = sum(phys.get((s, c, t), 0) for c in COLORES for t in TALLAS)
        defi = sum(deficit.get((s, c, t), 0) for c in COLORES for t in TALLAS)
        recent = sum(by_keys.get((s, c, t, p), 0) for c in COLORES for t in TALLAS for p in ["2026-07", "2026-08", "2026-09"])
        aug = sum(by_keys.get((s, c, t, "2026-08"), 0) for c in COLORES for t in TALLAS)
        vel = sum(r["store_vhs"].get(s, 0) for r in plan_rec["rows"])
        size_stk = {t: sum(phys.get((s, c, t), 0) for c in COLORES) for t in TALLAS}
        size_def = {t: sum(deficit.get((s, c, t), 0) for c in COLORES) for t in TALLAS}
        holes = []
        for c in COLORES:
            for t in TALLAS:
                q = phys.get((s, c, t), 0)
                d = deficit.get((s, c, t), 0)
                if d or (q == 0 and t in ("M", "L", "XL")):
                    holes.append({"color": c, "talla": t, "stk": q, "def": d})
        cob = round(stk / vel, 2) if vel > 0.05 else 0
        out.append(
            {
                "tienda": s,
                "stk": stk,
                "deficit": defi,
                "vel_hs": round(vel, 1),
                "cob": cob,
                "aug": aug,
                "recent3": recent,
                "size_stk": size_stk,
                "size_def": size_def,
                "holes": holes[:12],
                "n_holes": len(holes),
                "produce_in": sum(
                    r["dist"].get(s, 0) for r in plan_rec["rows"]
                ),
            }
        )
    # MGTA
    vel_m = plan_rec["totals"]["v_mgta"]
    out.append(
        {
            "tienda": "MGTA",
            "stk": 0,
            "deficit": 0,
            "vel_hs": round(vel_m, 1),
            "cob": 0,
            "aug": 0,
            "recent3": 0,
            "size_stk": {t: 0 for t in TALLAS},
            "size_def": {t: 0 for t in TALLAS},
            "holes": [],
            "n_holes": 0,
            "produce_in": sum(r["dist"].get("MGTA", 0) for r in plan_rec["rows"]),
            "nueva": True,
            "nota": "Tienda nueva zona de playa · 2× velocidad GRIETA · sin stock actual",
        }
    )
    return out


def clean_rows(rows):
    out = []
    for r in rows:
        o = {
            k: r[k]
            for k in [
                "color",
                "talla",
                "sku",
                "stk",
                "deficit",
                "cob",
                "cob_mgta",
                "sev",
                "produce",
                "produce_unconst",
            ]
        }
        o["v_base"] = round(r["v_base"], 2)
        o["v_hs"] = round(r["v_hs"], 2)
        o["v_mgta"] = round(r["v_mgta"], 2)
        o["v_total"] = round(r["v_total"], 2)
        o["need"] = round(r["need"], 1)
        o["dist"] = r["dist"]
        o["store_stk"] = r["store_stk"]
        o["store_vhs"] = {k: round(v, 2) for k, v in r["store_vhs"].items()}
        out.append(o)
    return out


def build_payload(inv, ven, tela):
    tela_rows = parse_tela(tela)
    plans = {}
    for key, sc in SCENARIOS.items():
        plans[key] = build_plan(inv, ven, tela_rows, sc)

    rec = plans["recomendado"]
    monthly = monthly_series(ven)
    stores = store_snapshot(inv, ven, rec)

    # sales size x color heatmap
    by_keys, cur = sales_cube(ven)
    heat_sales = {
        c: {t: int(sum(by_keys.get((s, c, t, p), 0) for s in RETAIL + CHANNELS for p in WINDOW)) for t in TALLAS}
        for c in COLORES
    }
    heat_stk = {
        c: {t: int(sum((stock_matrix(inv)[1]).get((s, c, t), 0) for s in RETAIL)) for t in TALLAS}
        for c in COLORES
    }

    vela_detail = []
    _, phys, deficit = stock_matrix(inv)
    for c in COLORES:
        for t in TALLAS:
            vela_detail.append(
                {
                    "color": c,
                    "talla": t,
                    "sku": SKU[(c, t)],
                    "stk": phys.get(("VELA", c, t), 0),
                    "deficit": deficit.get(("VELA", c, t), 0),
                    "aug": int(sum(by_keys.get(("VELA", c, t, "2026-08"), 0) for _ in [0])),
                    "recent": int(
                        sum(by_keys.get(("VELA", c, t, p), 0) for p in ["2026-07", "2026-08", "2026-09"])
                    ),
                    "produce": rec["rows"][
                        next(i for i, r in enumerate(rec["rows"]) if r["color"] == c and r["talla"] == t)
                    ]["dist"].get("VELA", 0),
                }
            )

    sep_pace = int(ven.loc[(ven["period"] == SEP) & (ven["coleccion"] == "actual"), "Cant. ordenada"].sum())
    alerts = [
        {
            "lvl": "crit",
            "title": "Talla L en quiebre nacional",
            "txt": "L es el 30% de la venta y solo el 6% del stock. Cobertura ~0,4 meses. Es la alerta #1 de corte.",
        },
        {
            "lvl": "crit",
            "title": "La Vela: quiebres reales y venta perdida",
            "txt": "Inventario negativo en L Azul Pizarra (−2) y XL Azul Verdoso (−1). Agosto vendió 45 und con 27 en piso, casi todas S. No hay M/L/XL en 4 de 5 colores.",
        },
        {
            "lvl": "alta",
            "title": "Temporada alta de playa",
            "txt": "Agosto 2026 = 194 und de colección actual (el doble de un mes normal). Septiembre ya lleva 63 und en 11 días (~172/mes). Dic–mar requiere cobertura, no reposición tardía.",
        },
        {
            "lvl": "alta",
            "title": "MGTA (Margarita) sin stock · zona de playa",
            "txt": "No hay inventario ni histórico. Se abre con 2× la velocidad de GRIETA en este modelo (más que otras líneas) porque MGTA es destino de playa.",
        },
        {
            "lvl": "alta",
            "title": "Sambil Chacao y Valencia desbalanceados",
            "txt": "Chacao: 0 L y 0 M. Valencia: 0 M y 0 XL. Son las dos tiendas que más venden el modelo.",
        },
        {
            "lvl": "media",
            "title": "Sobre-stock de S",
            "txt": "S es 13% de la venta y 45% del inventario (120 und). No cortar S salvo cupo mínimo para MGTA.",
        },
        {
            "lvl": "media",
            "title": "Tela limita Cereza y Verde Pino",
            "txt": "Consumo 0,75 m/pieza. Rojo→Cereza 65 m (86 pzas) y Verde Pino 76,3 m (101 pzas) no cubren la necesidad comercial. Habano/Marrón, Pizarra y Verdoso sí alcanzan.",
        },
    ]

    payload = {
        "as_of": AS_OF,
        "modelo": MODELO,
        "consumo": CONSUMO_M,
        "tallas": TALLAS,
        "colores": COLORES,
        "retail": RETAIL,
        "scenarios": {
            k: {
                "label": SCENARIOS[k]["label"],
                "hs": SCENARIOS[k]["hs"],
                "cov": SCENARIOS[k]["cov"],
                "vela_stockout": SCENARIOS[k]["vela_stockout"],
                "mgta_mult": SCENARIOS[k]["mgta_mult"],
                "note": SCENARIOS[k]["note"],
                "totals": plans[k]["totals"],
                "rows": clean_rows(plans[k]["rows"]),
                "by_color": plans[k]["by_color"],
                "by_talla": plans[k]["by_talla"],
                "tela_alert": plans[k]["tela_alert"],
                "grieta_base": round(plans[k]["grieta_base"], 2),
                "mgta_month": round(plans[k]["mgta_month"], 2),
            }
            for k in SCENARIOS
        },
        "monthly": monthly,
        "stores": stores,
        "heat_sales": heat_sales,
        "heat_stk": heat_stk,
        "tela": tela_rows,
        "vela": vela_detail,
        "alerts": alerts,
        "sep_und": sep_pace,
        "sep_pace": round(sep_pace / 11 * 30, 0),
        "assumptions": [
            "Colección activa: Azul Pizarra, Azul Verdoso, Cereza, Marrón, Verde Pino. Colores anteriores no se reproducen.",
            "Rotación base: promedio mensual Feb–Ago 2026 (meses completos). Sep 2026 es parcial (corte 11-sep) y no entra al promedio.",
            "VELA y Tolón se promedian solo por meses operativos (VELA jun–ago, Tolón may–ago) para no diluir tiendas nuevas.",
            "Escenario recomendado: ×1,30 temporada alta, 4 meses de cobertura, VELA ×1,30 por quiebres reportados, MGTA = 2× GRIETA.",
            "Inventario CHACAO → Sambil Chacao y SAMBIL → Sambil Valencia. Negativos se tratan como 0 físico + déficit a reponer.",
            "Tela: Habano → Marrón, Rojo (191955) → Cereza. Consumo 0,75 m/pieza. El lote se recorta al cupo de tela y conserva proporción de talla de la necesidad.",
            "Proporción de talla = mix real de ventas de la colección actual (no el mix del inventario). MGTA usa ese mix nacional.",
        ],
        "colors_hex": COLOR_HEX,
    }
    return payload, plans


def write_xlsx(payload, plans):
    wb = Workbook()
    thin = Border(
        left=Side(style="thin", color="D0D5DD"),
        right=Side(style="thin", color="D0D5DD"),
        top=Side(style="thin", color="D0D5DD"),
        bottom=Side(style="thin", color="D0D5DD"),
    )
    fill_h = PatternFill("solid", fgColor="1F2A44")
    font_h = Font(color="FFFFFF", bold=True, name="Calibri")
    fills = {
        "crit": PatternFill("solid", fgColor="FECACA"),
        "alta": PatternFill("solid", fgColor="FED7AA"),
        "media": PatternFill("solid", fgColor="FDE68A"),
        "ok": PatternFill("solid", fgColor="D1FAE5"),
    }

    def paint(ws, headers, rows, col_widths=None):
        ws.append(headers)
        for cell in ws[1]:
            cell.fill = fill_h
            cell.font = font_h
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
        for row in rows:
            ws.append(row)
        for r in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=ws.max_column):
            for c in r:
                c.border = thin
                c.font = Font(name="Calibri", size=10)
        for c in ws[1]:
            c.border = thin
        if col_widths:
            for i, w in enumerate(col_widths, 1):
                ws.column_dimensions[get_column_letter(i)].width = w

    rec = payload["scenarios"]["recomendado"]
    tot = rec["totals"]

    ws = wb.active
    ws.title = "Resumen"
    paint(
        ws,
        ["Indicador", "Valor", "Nota"],
        [
            ["Modelo", MODELO, "Caballero · unicolor"],
            ["Corte", AS_OF, "Septiembre parcial excluido del promedio"],
            ["Stock físico", tot["stk"], "Negativos VELA tratados como 0 + déficit"],
            ["Rotación base und/mes", round(tot["v_base"], 1), "Meses operativos Feb–Ago"],
            ["Rotación alta und/mes", round(tot["v_hs"], 1), "Base × 1,30"],
            ["Demanda MGTA und/mes", round(tot["v_mgta"], 1), "2× GRIETA × temporada alta"],
            ["Cobertura actual (meses)", tot["cob"], "Stock / rotación alta (sin MGTA)"],
            ["Producir (con tela)", tot["produce"], "Lote recortado a tela disponible"],
            ["Necesidad comercial", tot["produce_unconst"], "Sin tope de tela"],
            ["Metros a consumir", tot["metros"], "0,75 m por pieza"],
            ["Cobertura post lote + MGTA", tot["cob_post"], "Incluye demanda de Margarita"],
        ],
        [28, 18, 55],
    )
    ws["A14"] = "Alertas"
    ws["A14"].font = Font(bold=True, size=13, name="Calibri")
    r0 = 15
    for i, a in enumerate(payload["alerts"]):
        ws.cell(r0 + i, 1, a["lvl"].upper())
        ws.cell(r0 + i, 2, a["title"])
        ws.cell(r0 + i, 3, a["txt"])
        ws.cell(r0 + i, 1).fill = fills.get(a["lvl"] if a["lvl"] != "crit" else "crit", fills["alta"])

    ws2 = wb.create_sheet("Plan produccion")
    headers = [
        "SKU",
        "Color",
        "Talla",
        "Stock",
        "Déficit",
        "Vel. base",
        "Vel. alta",
        "Vel. MGTA",
        "Cob. meses",
        "Severidad",
        "Necesidad",
        "Producir",
        "VELA",
        "MGTA",
        "C.Verde",
        "Grieta",
        "Sambil Chacao",
        "Sambil Valencia",
        "Tolón",
        "Grand Plaz",
    ]
    rows = []
    for r in rec["rows"]:
        d = r["dist"]
        rows.append(
            [
                r["sku"],
                r["color"],
                r["talla"],
                r["stk"],
                r["deficit"],
                r["v_base"],
                r["v_hs"],
                r["v_mgta"],
                r["cob"],
                r["sev"],
                r["produce_unconst"],
                r["produce"],
                d.get("VELA", 0),
                d.get("MGTA", 0),
                d.get("CERRO VERDE", 0),
                d.get("GRIETA", 0),
                d.get("SAMBIL CHACAO", 0),
                d.get("SAMBIL VALENCIA", 0),
                d.get("TOLON", 0),
                d.get("GRAND PLAZ", 0),
            ]
        )
    rows.append(
        [
            "TOTAL",
            "",
            "",
            tot["stk"],
            tot["deficit"],
            round(tot["v_base"], 1),
            round(tot["v_hs"], 1),
            round(tot["v_mgta"], 1),
            tot["cob"],
            "",
            tot["produce_unconst"],
            tot["produce"],
            sum(r["dist"].get("VELA", 0) for r in rec["rows"]),
            sum(r["dist"].get("MGTA", 0) for r in rec["rows"]),
            sum(r["dist"].get("CERRO VERDE", 0) for r in rec["rows"]),
            sum(r["dist"].get("GRIETA", 0) for r in rec["rows"]),
            sum(r["dist"].get("SAMBIL CHACAO", 0) for r in rec["rows"]),
            sum(r["dist"].get("SAMBIL VALENCIA", 0) for r in rec["rows"]),
            sum(r["dist"].get("TOLON", 0) for r in rec["rows"]),
            sum(r["dist"].get("GRAND PLAZ", 0) for r in rec["rows"]),
        ]
    )
    paint(ws2, headers, rows, [16, 14, 8, 10, 10, 11, 11, 11, 11, 12, 12, 12, 10, 10, 10, 10, 14, 16, 10, 12])
    for i, r in enumerate(rec["rows"], 2):
        ws2.cell(i, 10).fill = fills.get(r["sev"], fills["ok"])
        if r["talla"] == "L" or r["sev"] == "crit":
            ws2.cell(i, 12).fill = fills["crit"]

    ws3 = wb.create_sheet("Tela")
    paint(
        ws3,
        ["SKU tela", "Tela", "Color producto", "Tipo", "Metros", "Piezas (0,75m)", "Uso lote m", "Sobra m"],
        [
            [
                t["sku"],
                t["tela"],
                t["color_prod"],
                t["kind"],
                t["metros"],
                t["piezas"],
                next((c["tela_uso"] for c in rec["by_color"] if c["color"] == t["color_prod"]), 0)
                if t["kind"] == "activa"
                else 0,
                next((c["tela_sobra"] for c in rec["by_color"] if c["color"] == t["color_prod"]), t["metros"])
                if t["kind"] == "activa"
                else t["metros"],
            ]
            for t in payload["tela"]
        ],
        [22, 16, 16, 12, 12, 16, 14, 12],
    )
    ws3.append([])
    ws3.append(["Alertas de tela (lote recortado)"])
    for a in rec["tela_alert"]:
        ws3.append([a["color"], f"Necesidad {a['need']}", f"Cupo {a['cap']}", f"Faltan {a['faltan']} pzas / {a['metros_faltan']} m"])

    ws4 = wb.create_sheet("Tallas")
    paint(
        ws4,
        ["Talla", "Ventas Feb-Ago", "% ventas", "Stock", "% stock", "Producir", "% producir", "Cobertura"],
        [
            [t["talla"], t["ventas"], t["ventas_pct"], t["stk"], t["stk_pct"], t["produce"], t["produce_pct"], t["cob"]]
            for t in rec["by_talla"]
        ],
        [10, 16, 12, 10, 12, 12, 14, 12],
    )

    ws5 = wb.create_sheet("La Vela")
    paint(
        ws5,
        ["SKU", "Color", "Talla", "Stock Vela", "Déficit", "Venta ago", "Venta jul-sep", "Enviar del lote"],
        [
            [v["sku"], v["color"], v["talla"], v["stk"], v["deficit"], v["aug"], v["recent"], v["produce"]]
            for v in payload["vela"]
        ],
        [16, 14, 10, 14, 10, 12, 16, 16],
    )

    ws6 = wb.create_sheet("Tiendas")
    paint(
        ws6,
        ["Tienda", "Stock", "Déficit", "Vel. alta/mes", "Cobertura", "Ago", "Jul-Sep", "Recibir lote", "Nota"],
        [
            [
                s["tienda"],
                s["stk"],
                s["deficit"],
                s["vel_hs"],
                s["cob"],
                s["aug"],
                s["recent3"],
                s["produce_in"],
                s.get("nota", ""),
            ]
            for s in payload["stores"]
        ],
        [18, 10, 10, 14, 12, 10, 12, 14, 55],
    )

    ws7 = wb.create_sheet("Metodologia")
    paint(ws7, ["#", "Supuesto"], [[i + 1, a] for i, a in enumerate(payload["assumptions"])], [6, 110])

    wb.save(OUT_XLSX)


def js_data(payload) -> str:
    # Drop bulky store_vhs if needed; keep as is.
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


HTML_HEAD = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Alerta de producción · Short Playa Cab</title>
<script src="vendor/chart.umd.min.js"></script>
<style>
:root{--bg:#0e0f14;--surf:#16171f;--s2:#1e1f2b;--s3:#252637;--brd:#2a2b3a;--tx:#f0f0f5;--mu:#7a7b95;--mu2:#4a4b65;--ac:#14b8a6;--a2:#f97316;--gr:#4caf76;--rd:#ef4444;--yw:#ffc107;--or:#f97316;--fh:ui-sans-serif,system-ui,sans-serif;--fb:ui-sans-serif,system-ui,sans-serif;--r:14px}
body.light{--bg:#f4f6f8;--surf:#fff;--s2:#eef1f4;--s3:#e5e8ee;--brd:#d5d9e3;--tx:#1a1a2e;--mu:#5c5d73;--mu2:#8a8ba3}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--tx);font-family:var(--fb);min-height:100vh}
.hdr{background:linear-gradient(135deg,#0b1c1a 0%,#191a2d 55%,#1a120c 100%);border-bottom:1px solid var(--brd);padding:18px 36px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}
body.light .hdr{background:linear-gradient(135deg,#e6f4f1,#f5f6fa 50%,#f8eee6)}
.hdr-l h1{font-family:var(--fh);font-size:1.45rem;font-weight:800;letter-spacing:-.4px}
.hdr-l h1 em{color:var(--or);font-style:normal}
.hdr-l p{color:var(--mu);font-size:.8rem;margin-top:2px}
.kpi-bar{display:flex;gap:8px;flex-wrap:wrap}
.kpib{background:var(--s2);border:1px solid var(--brd);border-radius:10px;padding:8px 12px;text-align:center;min-width:78px}
.kpib .kv{font-family:var(--fh);font-size:1.22rem;font-weight:800;color:var(--ac);line-height:1}
.kpib .kl{font-size:.62rem;color:var(--mu);text-transform:uppercase;letter-spacing:.4px;margin-top:2px}
.theme-btn,.vbtn{background:var(--s2);border:1px solid var(--brd);color:var(--tx);border-radius:8px;padding:6px 12px;cursor:pointer;font-size:.76rem;font-family:var(--fb)}
.vbtn.on{background:var(--or);color:#fff;border-color:var(--or);font-weight:700}
.abar{padding:10px 36px;display:flex;gap:8px;flex-wrap:wrap;border-bottom:1px solid var(--brd);background:var(--surf)}
.achip{border-radius:10px;padding:7px 10px;font-size:.72rem;line-height:1.35;max-width:340px}
.achip b{display:block;font-size:.73rem;margin-bottom:2px}
.crit{background:rgba(239,68,68,.14);border:1px solid rgba(239,68,68,.35);color:#fecaca}
.alta{background:rgba(249,115,22,.12);border:1px solid rgba(249,115,22,.32);color:#fdba74}
.media{background:rgba(255,193,7,.1);border:1px solid rgba(255,193,7,.28);color:#fde68a}
body.light .crit{color:#9f1239}body.light .alta{color:#9a3412}body.light .media{color:#854d0e}
.tabs{display:flex;gap:2px;padding:10px 36px 0;border-bottom:1px solid var(--brd);background:var(--surf);overflow-x:auto}
.tab{padding:8px 14px;font-family:var(--fh);font-size:.78rem;font-weight:700;color:var(--mu);border:none;background:transparent;cursor:pointer;white-space:nowrap;border-bottom:3px solid transparent}
.tab.active{color:var(--tx);border-bottom-color:var(--or);background:var(--s2)}
.content{padding:20px 36px 40px;max-width:1580px;margin:0 auto}
.sec{display:none}.sec.active{display:block}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.g3{display:grid;grid-template-columns:1.2fr .8fr;gap:14px;margin-bottom:14px}
.g1{margin-bottom:14px}
@media(max-width:900px){.g2,.g3{grid-template-columns:1fr}.content,.hdr,.abar,.tabs{padding-left:14px;padding-right:14px}}
.card{background:var(--surf);border:1px solid var(--brd);border-radius:var(--r);padding:16px}
.card h3{font-family:var(--fh);font-size:.9rem;font-weight:700;margin-bottom:4px}
.sub{font-size:.72rem;color:var(--mu);margin-bottom:12px}
.cw{position:relative;height:240px}
.ct{width:100%;border-collapse:collapse;font-size:.78rem}
.ct th{color:var(--mu);padding:7px 8px;text-align:left;border-bottom:1px solid var(--brd);font-size:.63rem;text-transform:uppercase;position:sticky;top:0;background:var(--surf)}
.ct td{padding:6px 8px;border-bottom:1px solid var(--brd)}
.ct tr:hover td{background:rgba(20,184,166,.05)}
.num{text-align:right;font-family:var(--fh);font-weight:700;font-variant-numeric:tabular-nums}
.sku{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.7rem}
.chip{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px;border:1.5px solid rgba(255,255,255,.12);vertical-align:middle}
.badge{display:inline-block;font-size:.62rem;font-weight:700;padding:1px 7px;border-radius:99px}
.b-crit{background:rgba(239,68,68,.18);color:#fca5a5}
.b-alta{background:rgba(249,115,22,.18);color:#fdba74}
.b-media{background:rgba(255,193,7,.16);color:#fde68a}
.b-ok{background:rgba(16,185,129,.16);color:#6ee7b7}
.hmt{border-collapse:separate;border-spacing:3px}
.hmt th{font-size:.67rem;color:var(--mu);padding:3px 6px;text-align:center}
.hmt td{padding:8px 6px;text-align:center;border-radius:6px;font-size:.77rem;font-weight:700;min-width:48px}
.hmt .rl{text-align:left;background:transparent!important;font-weight:500}
.method{background:rgba(20,184,166,.08);border:1px solid rgba(20,184,166,.22);border-radius:12px;padding:14px;font-size:.74rem;color:var(--mu);line-height:1.55}
.method b{color:var(--tx)}
.storebox{background:var(--s2);border:1px solid var(--brd);border-radius:12px;padding:12px;margin-bottom:8px}
.storebox.hot{border-color:#f9731655;background:rgba(249,115,22,.08)}
.storebox.new{border-color:#14b8a655;background:rgba(20,184,166,.08)}
.footer{text-align:center;color:var(--mu);font-size:.68rem;padding:16px;border-top:1px solid var(--brd)}
.cscroll{max-height:520px;overflow:auto}
.bar{height:8px;background:var(--s3);border-radius:99px;overflow:hidden}
.bar>i{display:block;height:100%;border-radius:99px}
</style>
</head>
<body>
<div class="hdr">
  <div class="hdr-l">
    <h1>Alerta de producción · <em>Short Playa Cab</em></h1>
    <p>Inventario actual × ventas × tela (0,75 m/pza) · corte 11 sep 2026 · temporada alta + MGTA playa</p>
  </div>
  <div class="hdr-r" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <div class="kpi-bar" id="kpiBar"></div>
    <button class="vbtn on" id="btnRec" onclick="setSc('recomendado')">Recomendado</button>
    <button class="vbtn" id="btnCon" onclick="setSc('conservador')">Conservador</button>
    <button class="theme-btn" onclick="exportCSV()">CSV lote</button>
    <button class="theme-btn" onclick="document.body.classList.toggle('light')">Tema</button>
  </div>
</div>
<div class="abar" id="alertBar"></div>
<div class="tabs">
  <button class="tab active" onclick="st('resumen')">Alertas</button>
  <button class="tab" onclick="st('produccion')">Producción</button>
  <button class="tab" onclick="st('tallas')">Tallas</button>
  <button class="tab" onclick="st('tiendas')">Tiendas · VELA · MGTA</button>
  <button class="tab" onclick="st('tela')">Tela</button>
  <button class="tab" onclick="st('dist')">Distribución</button>
</div>
<div class="content">
  <div class="sec active" id="sec-resumen">
    <div class="g3">
      <div class="card"><h3>Ventas mensuales</h3><div class="sub">Colección actual vs total · Sep 26 es parcial (11 días)</div><div class="cw"><canvas id="cMes"></canvas></div></div>
      <div class="card"><h3>Qué está pasando</h3><div class="sub" id="storySub"></div><div id="story"></div></div>
    </div>
    <div class="g2">
      <div class="card"><h3>Cobertura por talla</h3><div class="sub">Stock actual vs rotación de temporada alta</div><div class="cw"><canvas id="cCobT"></canvas></div></div>
      <div class="card"><h3>Mix de venta vs mix de inventario</h3><div class="sub">El piso está lleno de S y vacío de L — al revés de lo que se vende</div><div class="cw"><canvas id="cMix"></canvas></div></div>
    </div>
    <div class="card method" id="methodBox"></div>
  </div>
  <div class="sec" id="sec-produccion">
    <div class="g1 card" id="prodKpis"></div>
    <div class="g1 card"><h3>Lote a cortar · color × talla</h3><div class="sub">Enteros recortados a tela disponible · proporción según necesidad comercial (ventas, no stock)</div><div class="cscroll"><table class="ct" id="prodTable"></table></div></div>
  </div>
  <div class="sec" id="sec-tallas">
    <div class="g2">
      <div class="card"><h3>Heatmap ventas Feb–Ago</h3><div id="hmSales"></div></div>
      <div class="card"><h3>Heatmap inventario actual</h3><div id="hmStk"></div></div>
    </div>
    <div class="card"><table class="ct" id="tallaTable"></table></div>
  </div>
  <div class="sec" id="sec-tiendas">
    <div class="g2">
      <div class="card"><h3>La Vela — quiebre y venta perdida</h3><div class="sub">Abierta en junio · agosto 45 und · 30 físicas (21 son S) · L y XL en negativo</div><div class="cscroll"><table class="ct" id="velaTable"></table></div></div>
      <div class="card"><h3>Velocidad por tienda</h3><div class="sub">Ago 26 vs ritmo ajustado de temporada alta</div><div class="cw t"><canvas id="cStore"></canvas></div></div>
    </div>
    <div id="storeList"></div>
  </div>
  <div class="sec" id="sec-tela">
    <div class="g2">
      <div class="card"><h3>Cupo de tela vs lote</h3><div class="sub">0,75 metros por pieza · Habano = Marrón · Rojo 191955 = Cereza</div><div class="cw"><canvas id="cTela"></canvas></div></div>
      <div class="card"><h3>Detalle de materia prima</h3><div id="telaBox"></div></div>
    </div>
  </div>
  <div class="sec" id="sec-dist">
    <div class="card"><h3>Distribución del lote</h3><div class="sub">Prioridad: VELA (quiebres) → L/M → MGTA playa → resto. S se restringe salvo cupo MGTA.</div><div class="cscroll"><table class="ct" id="distTable"></table></div></div>
  </div>
</div>
<div class="footer">Short Playa Cab · alerta de producción · datos de inventario, ventas y tela cargados el 11 sep 2026</div>
<script>
"""


HTML_TAIL = r"""
const TALLAS=DATA.tallas, COLORES=DATA.colores, HEX=DATA.colors_hex;
let SC='recomendado', CI={};
const fmt=n=>Math.round(n).toLocaleString('es-VE');
const f1=n=>(Math.round(n*10)/10).toLocaleString('es-VE');
function P(){return DATA.scenarios[SC];}
function st(n){
  document.querySelectorAll('.tab').forEach((t,i)=>{t.classList.toggle('active',['resumen','produccion','tallas','tiendas','tela','dist'][i]===n);});
  document.querySelectorAll('.sec').forEach(s=>s.classList.remove('active'));
  document.getElementById('sec-'+n).classList.add('active');
  document.getElementById('alertBar').style.display=n==='resumen'?'flex':'none';
  if(location.hash.slice(1)!==n) history.replaceState(null,'','#'+n);
  render();
}
function setSc(s){
  SC=s;
  render();
}
function sevBadge(s){
  const m={crit:'b-crit',alta:'b-alta',media:'b-media',ok:'b-ok'};
  const l={crit:'QUIEBRE',alta:'ALTA',media:'MEDIA',ok:'OK'};
  return '<span class="badge '+m[s]+'">'+l[s]+'</span>';
}
function killCharts(){Object.values(CI).forEach(c=>{try{c.destroy()}catch(e){}});CI={};}
function kpis(){
  const t=P().totals;
  const items=[
    [fmt(t.stk),'Stock','und físicas'],
    [f1(t.v_hs),'Rot. alta','und / mes'],
    [f1(t.cob)+' m','Cobertura','sin MGTA'],
    [fmt(t.produce),'Producir','lote con tela'],
    [f1(t.v_mgta),'MGTA','und / mes playa'],
  ];
  document.getElementById('kpiBar').innerHTML=items.map(x=>'<div class="kpib"><div class="kv">'+x[0]+'</div><div class="kl">'+x[1]+'</div><div class="kl" style="text-transform:none;font-size:.58rem;color:var(--mu2)">'+x[2]+'</div></div>').join('');
}
function alerts(){
  document.getElementById('alertBar').innerHTML=DATA.alerts.map(a=>'<div class="achip '+a.lvl+'"><b>'+a.title+'</b>'+a.txt+'</div>').join('');
}
function story(){
  const t=P().totals, sc=P();
  document.getElementById('storySub').textContent=sc.label+' · '+sc.note;
  const L=P().by_talla.find(x=>x.talla==='L');
  const S=P().by_talla.find(x=>x.talla==='S');
  document.getElementById('story').innerHTML=`
    <div style="display:flex;flex-direction:column;gap:10px;font-size:.8rem;line-height:1.45">
      <div><b style="color:var(--rd)">1. Cortar L ya.</b> Ventas ${L.ventas_pct}% en L vs stock ${L.stk_pct}% (${L.stk} und, cobertura ${L.cob} meses). Cada semana sin L es venta perdida — La Vela ya lo confirmó.</div>
      <div><b style="color:var(--or)">2. No reponer S.</b> Stock ${S.stk} und (${S.stk_pct}% del piso) contra ${S.ventas_pct}% de la venta. El lote manda S solo a MGTA.</div>
      <div><b style="color:#2dd4bf">3. Abrir MGTA como tienda de playa.</b> GRIETA corre ~${f1(P().grieta_base)} und/mes. MGTA entra a ${f1(P().mgta_month)} und/mes (×${sc.mgta_mult}). Lote de apertura ${fmt(P().rows.reduce((a,r)=>a+(r.dist.MGTA||0),0))} und.</div>
      <div><b>4. Tela.</b> El corte usa ${t.metros} m. Cereza y Verde Pino se quedan cortos respecto a la necesidad comercial; Marrón/Habano, Pizarra y Verdoso cubren.</div>
      <div style="color:var(--mu)">Sep 26: ${DATA.sep_und} und en 11 días (ritmo ~${fmt(DATA.sep_pace)}/mes). El promedio Feb–Ago no incluye este mes para no mezclar parciales; el escenario recomendado sí infla ×${sc.hs} por temporada.</div>
    </div>`;
  document.getElementById('methodBox').innerHTML='<b>Metodología</b><ul style="margin:8px 0 0 18px">'+DATA.assumptions.map(a=>'<li style="margin-bottom:4px">'+a+'</li>').join('')+'</ul>';
}
function chartsResumen(){
  const m=DATA.monthly;
  CI.mes=new Chart(document.getElementById('cMes'),{type:'bar',data:{labels:m.labels,datasets:[
    {label:'Total',data:m.all,backgroundColor:'#334155',borderRadius:4},
    {label:'Colección actual',data:m.actual,backgroundColor:'#14b8a6',borderRadius:4}
  ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#94a3b8',boxWidth:10}}},scales:{x:{ticks:{color:'#94a3b8',font:{size:10}}},y:{ticks:{color:'#94a3b8'},grid:{color:'rgba(255,255,255,.04)'}}}}});
  const bt=P().by_talla;
  CI.cob=new Chart(document.getElementById('cCobT'),{type:'bar',data:{labels:bt.map(x=>x.talla),datasets:[{label:'Meses de cobertura',data:bt.map(x=>x.cob),backgroundColor:bt.map(x=>x.cob<1?'#ef4444':x.cob<2?'#f97316':x.cob<3?'#eab308':'#14b8a6'),borderRadius:6}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#94a3b8'},grid:{color:'rgba(255,255,255,.04)'}},y:{ticks:{color:'#e2e8f0',font:{weight:700}}}}}});
  CI.mix=new Chart(document.getElementById('cMix'),{type:'bar',data:{labels:bt.map(x=>x.talla),datasets:[
    {label:'% ventas',data:bt.map(x=>x.ventas_pct),backgroundColor:'#14b8a6'},
    {label:'% stock',data:bt.map(x=>x.stk_pct),backgroundColor:'#f97316'},
    {label:'% lote',data:bt.map(x=>x.produce_pct),backgroundColor:'#64748b'}
  ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#94a3b8',boxWidth:10}}},scales:{x:{ticks:{color:'#94a3b8'}},y:{ticks:{color:'#94a3b8',callback:v=>v+'%'},grid:{color:'rgba(255,255,255,.04)'}}}}});
}
function prod(){
  const t=P().totals, sc=P();
  document.getElementById('prodKpis').innerHTML=`<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px">
    <div class="kpib"><div class="kv">${fmt(t.produce_unconst)}</div><div class="kl">Necesidad</div></div>
    <div class="kpib"><div class="kv">${fmt(t.produce)}</div><div class="kl">Lote con tela</div></div>
    <div class="kpib"><div class="kv">${t.metros} m</div><div class="kl">Consumo</div></div>
    <div class="kpib"><div class="kv">${f1(t.cob_post)} m</div><div class="kl">Cob. post lote</div></div>
  </div>
  <p class="sub" style="margin-top:12px">${sc.note} Tela recorta ${fmt(t.produce_unconst-t.produce)} und de la necesidad comercial.</p>`;
  let h='<thead><tr><th>SKU</th><th>Color</th><th>Talla</th><th class="num">Stock</th><th class="num">Vel. alta</th><th class="num">MGTA</th><th>Cob</th><th class="num">Necesidad</th><th class="num">Producir</th></tr></thead><tbody>';
  P().rows.forEach(r=>{
    h+=`<tr><td class="sku">${r.sku}</td><td><span class="chip" style="background:${HEX[r.color]}"></span>${r.color}</td><td>${r.talla}</td>
      <td class="num">${r.stk}${r.deficit? ' <span class="b-crit badge">−'+r.deficit+'</span>':''}</td>
      <td class="num">${f1(r.v_hs)}</td><td class="num">${f1(r.v_mgta)}</td>
      <td>${sevBadge(r.sev)} <span style="font-size:.7rem;color:var(--mu)">${r.cob}m</span></td>
      <td class="num">${r.produce_unconst}</td>
      <td class="num" style="color:${r.produce?'#fdba74':'#6ee7b7'}">${r.produce||'—'}</td></tr>`;
  });
  h+=`<tfoot><tr><td colspan="3">Total</td><td class="num">${t.stk}</td><td class="num">${f1(t.v_hs)}</td><td class="num">${f1(t.v_mgta)}</td><td></td><td class="num">${t.produce_unconst}</td><td class="num">${t.produce}</td></tr></tfoot></tbody>`;
  document.getElementById('prodTable').innerHTML=h;
}
function hm(el,mat,kind){
  const mx=Math.max(...COLORES.flatMap(c=>TALLAS.map(t=>mat[c][t])),1);
  let h='<table class="hmt"><thead><tr><th></th>'+TALLAS.map(t=>'<th>'+t+'</th>').join('')+'</tr></thead><tbody>';
  COLORES.forEach(c=>{
    h+='<tr><td class="rl"><span class="chip" style="background:'+HEX[c]+'"></span>'+c+'</td>';
    TALLAS.forEach(t=>{
      const v=mat[c][t]; const p=v/mx;
      const bg=kind==='stk'
        ? (t==='L' && v<8? 'rgba(239,68,68,.55)':`rgba(249,115,22,${.12+p*.7})`)
        : `rgba(20,184,166,${.12+p*.75})`;
      h+='<td style="background:'+bg+'">'+v+'</td>';
    });
    h+='</tr>';
  });
  document.getElementById(el).innerHTML=h+'</tbody></table>';
}
function tallas(){
  hm('hmSales',DATA.heat_sales,'sales');
  hm('hmStk',DATA.heat_stk,'stk');
  let h='<thead><tr><th>Talla</th><th class="num">Ventas</th><th class="num">% venta</th><th class="num">Stock</th><th class="num">% stock</th><th class="num">Producir</th><th class="num">% lote</th><th>Cobertura</th></tr></thead><tbody>';
  P().by_talla.forEach(t=>{
    h+=`<tr><td><b>${t.talla}</b></td><td class="num">${t.ventas}</td><td class="num">${t.ventas_pct}%</td><td class="num">${t.stk}</td><td class="num">${t.stk_pct}%</td><td class="num">${t.produce}</td><td class="num">${t.produce_pct}%</td><td>${sevBadge(t.cob<1?'crit':t.cob<2?'alta':t.cob<3?'media':'ok')} ${t.cob} m</td></tr>`;
  });
  document.getElementById('tallaTable').innerHTML=h+'</tbody>';
}
function tiendas(){
  let h='<thead><tr><th>SKU</th><th>Color</th><th>Talla</th><th class="num">Stock</th><th class="num">Ago</th><th class="num">Jul–Sep</th><th class="num">Enviar</th></tr></thead><tbody>';
  DATA.vela.forEach(v=>{
    const rec=P().rows.find(r=>r.sku===v.sku);
    const send=rec? (rec.dist.VELA||0):v.produce;
    const danger=v.deficit|| (v.stk===0 && ['M','L','XL'].includes(v.talla));
    h+=`<tr style="${danger?'background:rgba(239,68,68,.08)':''}"><td class="sku">${v.sku}</td><td>${v.color}</td><td>${v.talla}</td><td class="num">${v.stk}${v.deficit?' −'+v.deficit:''}</td><td class="num">${v.aug}</td><td class="num">${v.recent}</td><td class="num">${send||'—'}</td></tr>`;
  });
  document.getElementById('velaTable').innerHTML=h+'</tbody>';
  const labs=DATA.stores.map(s=>s.tienda.replace('SAMBIL ','S. '));
  CI.store=new Chart(document.getElementById('cStore'),{type:'bar',data:{labels:labs,datasets:[
    {label:'Venta agosto',data:DATA.stores.map(s=>s.aug),backgroundColor:'#f97316'},
    {label:'Vel. alta / mes',data:DATA.stores.map(s=>s.vel_hs),backgroundColor:'#14b8a6'}
  ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#94a3b8',boxWidth:10}}},scales:{x:{ticks:{color:'#94a3b8',font:{size:10}}},y:{ticks:{color:'#94a3b8'},grid:{color:'rgba(255,255,255,.04)'}}}}});
  const ordered=DATA.stores.slice().sort(function(a,b){const r=s=>s.tienda==='VELA'?0:s.nueva?1:2;return r(a)-r(b);});
  document.getElementById('storeList').innerHTML=ordered.map(s=>{
    const cls=s.tienda==='VELA'?'hot':s.nueva?'new':'';
    const recv=P().rows.reduce((a,r)=>a+(r.dist[s.tienda]||0),0);
    const vel=s.tienda==='MGTA'?P().totals.v_mgta:P().rows.reduce((a,r)=>a+(r.store_vhs[s.tienda]||0),0);
    const sizes=TALLAS.map(t=>`<span style="margin-right:8px">${t} <b>${s.size_stk[t]||0}</b></span>`).join('');
    return `<div class="storebox ${cls}"><div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap">
      <div><b>${s.nueva?'🏝️ ':s.tienda==='VELA'?'🚨 ':''}${s.tienda}</b> <span style="color:var(--mu);font-size:.72rem">${s.nota||('cob '+s.cob+' m · vel '+f1(vel)+'/mes')}</span></div>
      <div>stock <b>${s.stk}</b> · recibir <b style="color:#fdba74">${recv}</b></div>
    </div><div style="margin-top:8px;font-size:.74rem;color:var(--mu)">${sizes}</div></div>`;
  }).join('');
}
function tela(){
  const bc=P().by_color;
  CI.tela=new Chart(document.getElementById('cTela'),{type:'bar',data:{labels:bc.map(c=>c.color),datasets:[
    {label:'Cupo piezas',data:bc.map(c=>c.tela_pcs),backgroundColor:'#334155'},
    {label:'Lote',data:bc.map(c=>c.produce),backgroundColor:bc.map(c=>HEX[c.color])}
  ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#94a3b8',boxWidth:10}}},scales:{x:{ticks:{color:'#94a3b8'}},y:{ticks:{color:'#94a3b8'},grid:{color:'rgba(255,255,255,.04)'}}}}});
  let html='';
  DATA.tela.forEach(t=>{
    const c=bc.find(x=>x.color===t.color_prod);
    const uso=t.kind==='activa'&&c?c.tela_uso:0;
    html+=`<div style="display:flex;justify-content:space-between;gap:8px;padding:8px 0;border-bottom:1px solid var(--brd);font-size:.78rem">
      <div><span class="chip" style="background:${HEX[t.color_prod]||'#64748b'}"></span><b>${t.tela}</b> → ${t.color_prod}<div class="sku">${t.sku} · ${t.kind}</div></div>
      <div class="num">${t.metros} m<br><span style="color:var(--mu);font-size:.7rem">${t.piezas} pzas · usa ${uso} m</span></div></div>`;
  });
  const alerts=P().tela_alert;
  if(alerts.length){
    html+='<div style="margin-top:12px">'+alerts.map(a=>`<div class="achip alta" style="max-width:none;margin-bottom:6px"><b>Falta tela ${a.color}</b>Necesidad ${a.need} · cupo ${a.cap} · comprar ${a.faltan} pzas (${a.metros_faltan} m)</div>`).join('')+'</div>';
  }
  document.getElementById('telaBox').innerHTML=html;
}
function dist(){
  const stores=['VELA','MGTA','CERRO VERDE','GRIETA','SAMBIL CHACAO','SAMBIL VALENCIA','TOLON','GRAND PLAZ'];
  let h='<thead><tr><th>SKU</th><th>Color</th><th>Talla</th>'+stores.map(s=>'<th class="num">'+s.replace('SAMBIL ','S.')+'</th>').join('')+'<th class="num">Total</th></tr></thead><tbody>';
  P().rows.forEach(r=>{
    if(!r.produce) return;
    h+=`<tr><td class="sku">${r.sku}</td><td>${r.color}</td><td>${r.talla}</td>`+stores.map(s=>'<td class="num">'+(r.dist[s]||'')+'</td>').join('')+`<td class="num">${r.produce}</td></tr>`;
  });
  const tot=s=>P().rows.reduce((a,r)=>a+(r.dist[s]||0),0);
  h+=`<tfoot><tr><td colspan="3">Total</td>`+stores.map(s=>'<td class="num">'+tot(s)+'</td>').join('')+`<td class="num">${P().totals.produce}</td></tr></tfoot></tbody>`;
  document.getElementById('distTable').innerHTML=h;
}
function exportCSV(){
  const stores=['VELA','MGTA','CERRO VERDE','GRIETA','SAMBIL CHACAO','SAMBIL VALENCIA','TOLON','GRAND PLAZ'];
  const lines=['SKU,Color,Talla,Stock,Cobertura,Necesidad,Producir,'+stores.join(',')];
  P().rows.forEach(r=>{
    lines.push([r.sku,r.color,r.talla,r.stk,r.cob,r.produce_unconst,r.produce].concat(stores.map(s=>r.dist[s]||0)).join(','));
  });
  const blob=new Blob(['\uFEFF'+lines.join('\n')],{type:'text/csv;charset=utf-8;'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='lote_short_playa_cab.csv';a.click();
}
function render(){
  document.getElementById('btnRec').classList.toggle('on',SC==='recomendado');
  document.getElementById('btnCon').classList.toggle('on',SC==='conservador');
  killCharts();
  kpis(); alerts(); story(); chartsResumen(); prod(); tallas(); tiendas(); tela(); dist();
}
if(new URLSearchParams(location.search).get('sc')==='conservador') SC='conservador';
const _init=(location.hash||'#resumen').slice(1);
st(['resumen','produccion','tallas','tiendas','tela','dist'].indexOf(_init)>=0?_init:'resumen');
</script>
</body>
</html>
"""


def write_html(payload):
    html = HTML_HEAD + "const DATA=" + js_data(payload) + ";\n" + HTML_TAIL
    OUT_HTML.write_text(html, encoding="utf-8")


def validate(payload):
    rec = payload["scenarios"]["recomendado"]
    tot = rec["totals"]
    bt = {t["talla"]: t for t in rec["by_talla"]}
    assert tot["produce"] <= tot["produce_unconst"]
    assert tot["stk"] == 270
    assert bt["L"]["cob"] < 1
    assert bt["S"]["cob"] > 5
    assert bt["L"]["produce"] > bt["M"]["produce"] > bt["S"]["produce"]
    assert bt["S"]["produce"] <= 10
    assert sum(r["dist"].get("VELA", 0) for r in rec["rows"] if r["talla"] == "S") == 0
    assert sum(r["dist"].get("MGTA", 0) for r in rec["rows"]) >= 150
    assert sum(r["dist"].get("VELA", 0) for r in rec["rows"] if r["talla"] == "L") >= 40
    for c in rec["by_color"]:
        assert c["produce"] <= c["tela_pcs"]
    assert abs(sum(r["produce"] for r in rec["rows"]) - tot["produce"]) == 0
    assert abs(sum(sum(r["dist"].values()) for r in rec["rows"]) - tot["produce"]) == 0


def main():
    inv, ven, tela = load_frames()
    payload, plans = build_payload(inv, ven, tela)
    validate(payload)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_xlsx(payload, plans)
    write_html(payload)
    rec = payload["scenarios"]["recomendado"]["totals"]
    con = payload["scenarios"]["conservador"]["totals"]
    print("HTML", OUT_HTML, "bytes", OUT_HTML.stat().st_size)
    print("XLSX", OUT_XLSX)
    print("REC produce", rec["produce"], "need", rec["produce_unconst"], "stk", rec["stk"], "cob", rec["cob"], "vhs", round(rec["v_hs"], 1), "mgta", round(rec["v_mgta"], 1))
    print("CON produce", con["produce"], "need", con["produce_unconst"], "cob", con["cob"])
    print("Tela alerts rec", payload["scenarios"]["recomendado"]["tela_alert"])
    print("By talla rec", payload["scenarios"]["recomendado"]["by_talla"])
    print("By color rec")
    for c in payload["scenarios"]["recomendado"]["by_color"]:
        print(" ", c["color"], "stk", c["stk"], "prod", c["produce"], "need", c["produce_unconst"], "tela", c["tela_pcs"], "cob", c["cob"])


if __name__ == "__main__":
    main()
