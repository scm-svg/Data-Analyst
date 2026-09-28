#!/usr/bin/env python3
"""Propuesta Black Friday — categoría C, manufactura y equipamiento.

Lee el dashboard ABC (precios, costos y categorías), el cuadro de ventas
actualizado y el inventario de la propuesta. Escribe un dashboard HTML
autocontenido y un Excel para directiva.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.series import DataPoint
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.drawing.fill import PatternFillProperties, ColorChoice

ROOT = Path("/workspace/propuesta-black-friday")
HTML_TEMPLATE = ROOT / "dashboard.template.html"
HTML_OUT = ROOT / "propuesta-black-friday-categoria-c.html"
XLSX_OUT = ROOT / "Propuesta_Black_Friday_Categoria_C.xlsx"
ABC_HTML = Path("/home/ubuntu/.cursor/projects/workspace/uploads/abc_ver_5c4b.html")
INV_XLSX = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/INVENTARIO_TOTAL_CUADRO_PARA_ABC_-_PROPUESTA_dc6f.xlsx"
)
VEN_XLSX = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/VENTAS_CUADRO_ACTUALIZADAS_ARREGLADO_4e9d.xlsx"
)

STORES = [
    "La Grieta",
    "Sambil Valencia",
    "Cerro Verde",
    "Sambil Chacao",
    "La Vela",
    "Grandplaz",
    "Tolon",
]
STORE_MAP = {
    "CERRO VERDE": "Cerro Verde",
    "CHACAO": "Sambil Chacao",
    "SAMBIL": "Sambil Valencia",
    "GRIETA": "La Grieta",
    "VELA": "La Vela",
    "GRANDPLAZ": "Grandplaz",
    "TOLON": "Tolon",
}
PERIODS = [
    "2025-10",
    "2025-11",
    "2025-12",
    "2026-01",
    "2026-02",
    "2026-03",
    "2026-04",
    "2026-05",
    "2026-06",
    "2026-07",
    "2026-08",
    "2026-09",
]
PERIOD_LABELS = ["Oct 25", "Nov 25", "Dic 25", "Ene 26", "Feb 26", "Mar 26", "Abr 26", "May 26", "Jun 26", "Jul 26", "Ago 26", "Sep 26"]
RECENT = ["2026-07", "2026-08", "2026-09"]
FLOOR = 1.10  # precio promo mínimo = costo × 1.10
MIN_STOCK = 5
MIN_DISC = 0.10

# Escaleras. El tramo sale de la cobertura de decisión, no del promedio crudo.
TIERS_IMPULSO = [
    ("6-12", "6 a 12 meses", 0.20),
    ("12-18", "12 a 18 meses", 0.25),
    ("18-24", "18 a 24 meses", 0.30),
    ("24+", "Más de 24 meses", 0.35),
    ("dormido", "Sin salida reciente", 0.40),
]
TIERS_DESATASCO = [
    ("18-24", "18 a 24 meses", 0.35),
    ("24+", "Más de 24 meses", 0.40),
    ("dormido", "Sin salida reciente", 0.45),
]
RANGO_IMPULSO = {t[0] for t in TIERS_IMPULSO}
RANGO_DESATASCO = {t[0] for t in TIERS_DESATASCO}


def load_abc():
    text = ABC_HTML.read_text(encoding="utf-8", errors="replace")
    start = text.find(">", text.find('id="abc-embedded-data"')) + 1
    end = text.find("</script>", start)
    data = json.loads(text[start:end])
    skus = data["skus"]
    rows = []
    for r in data["salesRows"]:
        rows.append((skus[r[1]].upper(), float(r[4]), float(r[5]), float(r[6])))
    pos = pd.DataFrame(rows, columns=["sku", "qty", "rev", "cost"])
    pos = pos[pos.qty > 0]
    eco = pos.groupby("sku").agg(qty=("qty", "sum"), rev=("rev", "sum"), cost=("cost", "sum"))
    eco = eco[eco.qty > 0].copy()
    eco["uprice"] = eco.rev / eco.qty
    eco["ucost"] = eco.cost / eco.qty
    eco.loc[eco.uprice <= 0, "uprice"] = np.nan
    eco.loc[eco.ucost < 0, "ucost"] = np.nan
    sm = pd.DataFrame.from_dict(data["skuMaster"], orient="index").reset_index().rename(columns={"index": "sku"})
    sm["sku"] = sm.sku.str.upper()
    return eco, sm, data["meta"]


def macro_of(cat: str | None):
    if cat is None or (isinstance(cat, float) and math.isnan(cat)):
        return None
    s = str(cat)
    if s.startswith("Manufactura"):
        return "Manufactura"
    if s.startswith("Equipamiento"):
        return "Equipamiento"
    if s.startswith("Materia"):
        return "Materia Prima"
    return None


def infer_category(modelo: str):
    name = str(modelo or "").upper()
    if re.search(r"STICKER|BOLSA|CINTA|KRAFT|NAVIDAD", name):
        return None, None
    if "PELOTA" in name:
        return "Equipamiento", "Equipamiento / Pelotas"
    if re.search(r"VITA |MOTION LOOP|BASIC LINE|MANGA LARGA|FALDA |VESTIDO|SHORT |PANT|BIKER|LEGGING|BIKINI|TOP |HOODIE|JACKET|POLO ", name):
        return "Manufactura", "Manufactura / General"
    return None, None


def step5(p: float) -> float:
    if p <= 0:
        return 0.0
    return math.floor(p * 20 + 1e-9) / 20.0


def max_discount(price, cost) -> float:
    if price is None or not np.isfinite(price) or price <= 0:
        return 0.0
    if cost is None or not np.isfinite(cost) or cost < 0:
        return 0.0
    if cost == 0:
        return 0.70
    return max(0.0, 1.0 - FLOOR * float(cost) / float(price))


def pareto(df: pd.DataFrame, value: str, outcol: str) -> pd.DataFrame:
    df = df.copy()
    df[outcol] = "C"
    pos = df[df[value] > 0].sort_values([value, "modelo"], ascending=[False, True])
    total = pos[value].sum()
    if total <= 0:
        return df
    cum = pos[value].cumsum() / total
    cls = np.where(cum <= 0.80, "A", np.where(cum <= 0.95, "B", "C"))
    df.loc[pos.index, outcol] = cls
    return df


def rango_of(estado: str, cover: float) -> str:
    if estado in ("frenado", "sin salida"):
        return "dormido"
    if cover < 6:
        return "<6"
    if cover < 12:
        return "6-12"
    if cover < 18:
        return "12-18"
    if cover < 24:
        return "18-24"
    return "24+"


def num(x, nd=2):
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(v):
        return None
    return round(v, nd)


def build_frames():
    eco, sm, abc_meta = load_abc()
    inv = pd.read_excel(INV_XLSX)
    ven = pd.read_excel(VEN_XLSX)
    for df, cols in (
        (inv, ["SKU", "MODELO", "GENERO", "COLOR", "TALLA", "Ubicación"]),
        (ven, ["SKU", "modelo", "GENERO", "COLOR", "TALLA", "tienda / ubicación"]),
    ):
        for c in cols:
            df[c] = df[c].astype(str).str.strip()
    inv["SKU"] = inv.SKU.str.upper()
    ven["SKU"] = ven.SKU.str.upper()
    inv["MODELO"] = inv.MODELO.replace({"None": np.nan, "nan": np.nan})
    ven["modelo"] = ven["modelo"].replace({"None": np.nan, "nan": np.nan})

    months = {
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
    }
    ven["mes_n"] = ven["Mes"].str.lower().map(months)
    ven["period"] = ven["Año"].astype(str) + "-" + ven["mes_n"].astype(int).astype(str).str.zfill(2)
    ven["canal"] = np.where(ven["tienda / ubicación"].isin(["Pedidos", "CORPORATIVO"]), "mayor", "consumo")
    ven["tienda"] = ven["tienda / ubicación"].where(ven["tienda / ubicación"].isin(STORES))

    sm = sm.copy()
    sm["macro_real"] = sm.categoria.map(macro_of)
    attr_inv = inv.groupby("SKU").agg(
        modelo=("MODELO", "first"), genero=("GENERO", "first"), color=("COLOR", "first"), talla=("TALLA", "first")
    )
    attr_ven = ven.groupby("SKU").agg(
        modelo=("modelo", "first"), genero=("GENERO", "first"), color=("COLOR", "first"), talla=("TALLA", "first")
    )
    sm_i = sm.set_index("sku")
    all_skus = sorted(set(attr_inv.index) | set(attr_ven.index) | set(sm_i.index))
    base = pd.DataFrame(index=pd.Index(all_skus, name="sku"))
    base["modelo"] = attr_inv["modelo"].reindex(base.index).fillna(attr_ven["modelo"]).fillna(sm_i["modelo"])
    base["genero"] = attr_inv["genero"].reindex(base.index).fillna(attr_ven["genero"]).fillna(sm_i["genero"])
    base["color"] = attr_inv["color"].reindex(base.index).fillna(attr_ven["color"]).fillna(sm_i["color"])
    base["talla"] = attr_inv["talla"].reindex(base.index).fillna(attr_ven["talla"]).fillna(sm_i["talla"])
    base["categoria"] = sm_i["categoria"].reindex(base.index)
    base["macro"] = base["categoria"].map(macro_of)
    base["origen_cat"] = np.where(base["macro"].notna(), "maestro", None)

    known = base[base["macro"].notna()]
    mode_cat = known.groupby("modelo")["categoria"].agg(lambda s: s.value_counts().index[0])
    mode_macro = known.groupby("modelo")["macro"].agg(lambda s: s.value_counts().index[0])
    inherit = base["macro"].isna() & base["modelo"].isin(mode_macro.index)
    base.loc[inherit, "categoria"] = base.loc[inherit, "modelo"].map(mode_cat)
    base.loc[inherit, "macro"] = base.loc[inherit, "modelo"].map(mode_macro)
    base.loc[inherit, "origen_cat"] = "heredada"

    still = base["macro"].isna()
    inferred_macro = []
    inferred_cat = []
    for modelo in base.loc[still, "modelo"]:
        m, c = infer_category(modelo)
        inferred_macro.append(m)
        inferred_cat.append(c)
    base.loc[still, "macro"] = inferred_macro
    base.loc[still, "categoria"] = inferred_cat
    base.loc[still & base["macro"].notna(), "origen_cat"] = "inferida"
    base["macro"] = base["macro"].fillna("Fuera de alcance")
    base["categoria"] = base["categoria"].fillna("Sin categoría")

    base["uprice"] = eco["uprice"].reindex(base.index)
    base["ucost"] = eco["ucost"].reindex(base.index)
    base["precio_origen"] = np.where(base.uprice.notna(), "sku", "faltante")
    med_p = base.groupby("modelo")["uprice"].transform("median")
    med_c = base.groupby("modelo")["ucost"].transform("median")
    fill_p = base.uprice.isna() & med_p.notna()
    base.loc[fill_p, "uprice"] = med_p[fill_p]
    base.loc[fill_p, "precio_origen"] = "modelo"
    fill_c = base.ucost.isna() & med_c.notna()
    base.loc[fill_c, "ucost"] = med_c[fill_c]

    cons = ven[ven.canal == "consumo"]
    base["qty_12"] = cons.groupby("SKU")["Cant. ordenada"].sum().reindex(base.index).fillna(0)
    base["qty_mayor"] = ven[ven.canal == "mayor"].groupby("SKU")["Cant. ordenada"].sum().reindex(base.index).fillna(0)
    base["qty_3m"] = cons[cons.period.isin(RECENT)].groupby("SKU")["Cant. ordenada"].sum().reindex(base.index).fillna(0)
    monthly = (
        cons.groupby(["SKU", "period"])["Cant. ordenada"].sum().unstack(fill_value=0).reindex(columns=PERIODS, fill_value=0)
    )
    monthly = monthly.reindex(base.index).fillna(0)

    inv["tienda"] = inv["Ubicación"].map(STORE_MAP)
    inv["pool"] = np.where(inv["Ubicación"].isin(["TALLER MANUFACTURADO", "TALLER EQUIPAMIENTO"]), "taller", "tienda")
    base["stock_tienda"] = inv[inv.pool == "tienda"].groupby("SKU")["Cantidad en inventario"].sum().reindex(base.index).fillna(0)
    base["stock_taller_m"] = (
        inv[inv["Ubicación"] == "TALLER MANUFACTURADO"].groupby("SKU")["Cantidad en inventario"].sum().reindex(base.index).fillna(0)
    )
    base["stock_taller_e"] = (
        inv[inv["Ubicación"] == "TALLER EQUIPAMIENTO"].groupby("SKU")["Cantidad en inventario"].sum().reindex(base.index).fillna(0)
    )
    base["stock_taller"] = base["stock_taller_m"] + base["stock_taller_e"]
    base["stock"] = base["stock_tienda"] + base["stock_taller"]

    store_stock = (
        inv[inv.pool == "tienda"].pivot_table(index="SKU", columns="tienda", values="Cantidad en inventario", aggfunc="sum", fill_value=0)
    )
    store_sales = (
        cons[cons.tienda.notna()].pivot_table(index="SKU", columns="tienda", values="Cant. ordenada", aggfunc="sum", fill_value=0)
    )
    for col in STORES:
        if col not in store_stock.columns:
            store_stock[col] = 0
        if col not in store_sales.columns:
            store_sales[col] = 0
    store_stock = store_stock.reindex(base.index).fillna(0)
    store_sales = store_sales.reindex(base.index).fillna(0)

    base["priced"] = base.uprice.notna() & base.ucost.notna() & (base.uprice > 0) & (base.ucost < base.uprice)
    base["rev"] = np.where(base.priced, base.qty_12 * base.uprice, 0.0)
    base["cogs"] = np.where(base.priced, base.qty_12 * base.ucost, 0.0)
    base["margin"] = base.rev - base.cogs
    base["stock_cost"] = np.where(base.ucost.notna(), base.stock * base.ucost, 0.0)
    base["stock_retail"] = np.where(base.uprice.notna(), base.stock * base.uprice, 0.0)

    scope_mask = base.macro.isin(["Manufactura", "Equipamiento"])
    scope = base[scope_mask].copy()
    return {
        "base": base,
        "scope": scope,
        "monthly": monthly,
        "store_stock": store_stock,
        "store_sales": store_sales,
        "ven": ven,
        "abc_meta": abc_meta,
    }


def model_table(scope: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    g = scope.reset_index().groupby(["modelo", "macro"], as_index=False)
    mod = g.agg(
        categoria=("categoria", lambda s: s.value_counts().index[0]),
        origen_cat=("origen_cat", lambda s: s.value_counts().index[0]),
        skus=("sku", "nunique"),
        qty_12=("qty_12", "sum"),
        qty_3m=("qty_3m", "sum"),
        qty_mayor=("qty_mayor", "sum"),
        rev=("rev", "sum"),
        cogs=("cogs", "sum"),
        margin=("margin", "sum"),
        stock=("stock", "sum"),
        stock_tienda=("stock_tienda", "sum"),
        stock_taller=("stock_taller", "sum"),
        stock_cost=("stock_cost", "sum"),
        stock_retail=("stock_retail", "sum"),
        skus_precio=("priced", "sum"),
    )
    # stock-weighted price and cost on priced units
    priced = scope[scope.priced]
    w = priced.reset_index().groupby("modelo").apply(
        lambda d: pd.Series(
            {
                "pvp": np.average(d.uprice, weights=d.stock) if d.stock.sum() > 0 else d.uprice.median(),
                "costo_u": np.average(d.ucost, weights=d.stock) if d.stock.sum() > 0 else d.ucost.median(),
            }
        ),
        include_groups=False,
    )
    mod = mod.merge(w, on="modelo", how="left")
    mod = pareto(mod, "margin", "abc_m")
    mod = pareto(mod, "qty_12", "abc_r")
    mod["matriz"] = mod.abc_m + mod.abc_r
    rate12 = mod.qty_12 / 12.0
    rate3 = mod.qty_3m / 3.0
    estado = []
    rate = []
    cover = []
    for r12, r3, qty12, qty3, stock in zip(rate12, rate3, mod.qty_12, mod.qty_3m, mod.stock):
        if qty12 < 0:
            est, rt = "devolucion", max(r12, 0)
        elif stock <= 0:
            est, rt = "sin stock", r12
        elif qty12 <= 0 and qty3 <= 0:
            est, rt = "sin salida", 0.0
        elif qty3 <= 0:
            est, rt = "frenado", r12
        elif r12 <= 0:
            est, rt = "despertando", r3
        elif r3 > r12 * 1.5:
            est, rt = "despertando", r3
        elif r3 < r12 * 0.5:
            est, rt = "enfriando", r3
        else:
            est, rt = "estable", r12
        estado.append(est)
        rate.append(float(rt))
        if stock <= 0:
            cover.append(0.0)
        elif est in ("sin salida",):
            cover.append(999.0)
        elif est == "frenado":
            cover.append(999.0 if stock >= MIN_STOCK else (stock / r12 if r12 > 0 else 999.0))
        elif rt > 0:
            cover.append(float(stock) / float(rt))
        else:
            cover.append(999.0)
    mod["estado"] = estado
    mod["rate"] = rate
    mod["cover"] = cover
    mod["rango"] = [rango_of(e, c) if e != "devolucion" else "devolucion" for e, c in zip(mod.estado, mod.cover)]
    # dust: frenado with tiny stock should not look "dormido"
    tiny = (mod.estado == "frenado") & (mod.stock < MIN_STOCK)
    mod.loc[tiny, "rango"] = "<6"
    mod["capital6"] = [
        max(0.0, (st - 6.0 * rt) * (cost if pd.notna(cost) else 0.0))
        for st, rt, cost in zip(mod.stock, mod.rate, mod.costo_u)
    ]
    mod["mg_pct"] = np.where(mod.rev > 0, mod.margin / mod.rev, np.where(mod.pvp > 0, (mod.pvp - mod.costo_u) / mod.pvp, np.nan))
    # monthly by model
    scope_idx = scope.copy()
    m2 = monthly.reindex(scope_idx.index).fillna(0)
    m2["modelo"] = scope_idx["modelo"].values
    bym = m2.groupby("modelo")[PERIODS].sum()
    mod = mod.merge(bym, on="modelo", how="left")
    return mod


def sku_discount(price, cost, tier: float):
    cap = max_discount(price, cost)
    applied = step5(min(tier, cap))
    if applied + 1e-9 < MIN_DISC:
        return 0.0, True
    return applied, applied + 1e-9 < tier - 1e-9


def assign_options(mod: pd.DataFrame, scope: pd.DataFrame):
    """Return sku-level frame for candidate models and option flags."""
    cc = mod[(mod.abc_m == "C") & (mod.abc_r == "C")].copy()
    eligible_models = set(
        cc[(cc.stock >= MIN_STOCK) & (cc.rango.isin(RANGO_IMPULSO)) & (cc.skus_precio > 0) & (cc.estado != "devolucion")][
            "modelo"
        ]
    )
    sk = scope.reset_index()
    sk = sk[sk.modelo.isin(eligible_models)].copy()
    tier_map = {t[0]: t[2] for t in TIERS_IMPULSO}
    tier_i = {m: tier_map[r] for m, r in zip(cc.modelo, cc.rango) if m in eligible_models}
    di, topi = [], []
    for modelo, price, cost, priced in zip(sk.modelo, sk.uprice, sk.ucost, sk.priced):
        if not priced or not (price > cost):
            di.append(0.0)
            topi.append(False)
            continue
        a, t = sku_discount(price, cost, tier_i[modelo])
        di.append(a)
        topi.append(t)
    sk["tier_impulso"] = sk.modelo.map(tier_i)
    sk["d_impulso"] = di
    sk["tope_impulso"] = topi
    # La opción amplia usa el mismo porcentaje en la cola C y suma los B lentos.
    sk["d_desatasco"] = sk["d_impulso"]
    sk["tope_desatasco"] = sk["tope_impulso"]
    sk["en_impulso"] = sk.d_impulso >= MIN_DISC
    sk["en_desatasco"] = sk.en_impulso
    sk["clase"] = "C"
    ok_i = set(sk.loc[sk.en_impulso, "modelo"])
    sk = sk[sk.modelo.isin(ok_i)].copy()
    sk_b, ok_b = addon_b(mod, scope, tier_map)
    if len(sk_b):
        sk = pd.concat([sk, sk_b], ignore_index=True)
    ok_d = set(sk.loc[sk.en_desatasco, "modelo"])
    return sk, ok_i, ok_d, ok_b


def addon_b(mod: pd.DataFrame, scope: pd.DataFrame, tier_map: dict):
    """Clase B de margen y C de rotación, con 18 meses o más. No son categoría C."""
    bmod = mod[
        (mod.abc_m == "B")
        & (mod.abc_r == "C")
        & (mod.stock >= MIN_STOCK)
        & (mod.rango.isin(["18-24", "24+", "dormido"]))
        & (mod.skus_precio > 0)
        & (mod.estado != "devolucion")
    ]
    if bmod.empty:
        return pd.DataFrame(), set()
    tiers = {m: tier_map[r] for m, r in zip(bmod.modelo, bmod.rango)}
    sk = scope.reset_index()
    sk = sk[sk.modelo.isin(set(bmod.modelo))].copy()
    di, topi = [], []
    for modelo, price, cost, priced in zip(sk.modelo, sk.uprice, sk.ucost, sk.priced):
        if not priced or not (price > cost):
            di.append(0.0)
            topi.append(False)
            continue
        a, t = sku_discount(price, cost, tiers[modelo])
        di.append(a)
        topi.append(t)
    sk["tier_impulso"] = sk.modelo.map(tiers)
    sk["d_impulso"] = 0.0
    sk["tope_impulso"] = False
    sk["d_desatasco"] = di
    sk["tope_desatasco"] = topi
    sk["en_impulso"] = False
    sk["en_desatasco"] = sk.d_desatasco >= MIN_DISC
    sk["clase"] = "B"
    sk = sk[sk.en_desatasco].copy()
    return sk, set(sk.modelo)


def plan_sku(store_stock: dict, taller: float, store_sales: dict, model_sales: dict):
    total = int(round(sum(store_stock.values()) + taller))
    if total <= 0:
        return [], {s: 0 for s in STORES}
    own = {s: store_sales.get(s, 0) for s in STORES if store_sales.get(s, 0) > 0}
    seeded = False
    if own:
        demand = sorted(own, key=lambda s: own[s], reverse=True)
    else:
        seeded = True
        ranked = sorted(STORES, key=lambda s: model_sales.get(s, 0), reverse=True)
        demand = [s for s in ranked if model_sales.get(s, 0) > 0][:3] or ranked[:3]
    if len(demand) > total:
        demand = demand[:total]
    targets = {s: 0 for s in STORES}
    remaining = total
    for s in demand:
        if remaining <= 0:
            break
        targets[s] += 1
        remaining -= 1
    for s in demand:
        if remaining <= 0:
            break
        ann = store_sales.get(s, 0)
        cap = 2 if seeded or ann <= 0 else max(2, int(round(ann / 6.0)))
        room = max(0, cap - targets[s])
        give = min(room, remaining)
        targets[s] += give
        remaining -= give
    need = {}
    surplus = {}
    for s in STORES:
        cur = store_stock.get(s, 0)
        tgt = targets[s]
        if cur + 1e-9 < tgt:
            need[s] = tgt - cur
        elif cur > tgt + 1e-9:
            surplus[s] = cur - tgt
    moves = []
    tall = float(taller)
    for s, n in sorted(need.items(), key=lambda kv: -kv[1]):
        take = min(n, tall)
        if take >= 0.5:
            q = int(round(take))
            if q > 0:
                moves.append({"desde": "Taller", "hacia": s, "unidades": q})
            tall -= q
            need[s] -= q
    donors = sorted(surplus.items(), key=lambda kv: -kv[1])
    for s in list(need):
        n = need[s]
        if n < 0.5:
            continue
        new_donors = []
        for d, sup in donors:
            if n < 0.5 or sup < 0.5:
                new_donors.append((d, sup))
                continue
            take = min(n, sup)
            q = int(round(take))
            if q > 0:
                moves.append({"desde": d, "hacia": s, "unidades": q})
            n -= q
            new_donors.append((d, sup - q))
        donors = new_donors
        need[s] = n
    return moves, targets


def supply_for(sk: pd.DataFrame, scope: pd.DataFrame, store_stock: pd.DataFrame, store_sales: pd.DataFrame, models: set, flag: str):
    sub = sk[(sk.modelo.isin(models)) & (sk[flag])].copy()
    model_sales = (
        scope.reset_index()
        .groupby("modelo")
        .apply(lambda d: pd.Series({s: float(store_sales.reindex(d.sku).fillna(0)[s].sum()) for s in STORES}), include_groups=False)
    )
    moves = []
    for sku, row in sub.set_index("sku").iterrows():
        ss = {s: float(store_stock.at[sku, s]) if sku in store_stock.index else 0.0 for s in STORES}
        sv = {s: float(store_sales.at[sku, s]) if sku in store_sales.index else 0.0 for s in STORES}
        ms = model_sales.loc[row.modelo].to_dict() if row.modelo in model_sales.index else {s: 0 for s in STORES}
        mv, _targets = plan_sku(ss, float(row.stock_taller), sv, ms)
        for m in mv:
            moves.append(
                {
                    "sku": sku,
                    "modelo": row.modelo,
                    "macro": row.macro,
                    "desde": m["desde"],
                    "hacia": m["hacia"],
                    "unidades": m["unidades"],
                }
            )
    return pd.DataFrame(moves)


def option_economics(sk: pd.DataFrame, mod: pd.DataFrame, models: set, dcol: str):
    sub = sk[(sk.modelo.isin(models)) & (sk[dcol] >= MIN_DISC)].copy()
    if sub.empty:
        return {}
    sub["promo"] = sub.uprice * (1 - sub[dcol])
    sub["give_unit"] = sub.uprice - sub.promo
    # natural month at the model rate, allocated by sku share of qty_12, else by stock
    mrate = mod.set_index("modelo")["rate"]
    mq = sub.groupby("modelo")["qty_12"].transform("sum")
    mstock = sub.groupby("modelo")["stock"].transform("sum")
    share = np.where(mq > 0, sub.qty_12 / mq, np.where(mstock > 0, sub.stock / mstock, 0))
    sub["rate_sku"] = sub.modelo.map(mrate).fillna(0) * share
    sub["natural_give"] = sub.rate_sku * sub.give_unit
    sub["trapped_u"] = np.maximum(0, sub.stock - 6 * sub.rate_sku)
    # trapped at sku using sku's own rate would mis-state; use share of model trapped units
    m_trapped = np.maximum(0, mstock - 6 * sub.modelo.map(mrate).fillna(0))
    # recompute model trapped on full model stock, then allocate by stock share among discounted skus
    full_stock = mod.set_index("modelo")["stock"]
    full_trap = np.maximum(0, full_stock - 6 * mrate)
    sub["trap_model"] = sub.modelo.map(full_trap).fillna(0) * np.where(mstock > 0, sub.stock / mstock, 0)
    sub["trap_margin"] = sub.trap_model * (sub.promo - sub.ucost)
    sub["trap_cost"] = sub.trap_model * sub.ucost
    sub["stock_cost"] = sub.stock * sub.ucost
    sub["stock_pvp"] = sub.stock * sub.uprice
    sub["promo_val"] = sub.stock * sub.promo
    wdisc = 1 - sub.promo_val.sum() / sub.stock_pvp.sum() if sub.stock_pvp.sum() else 0
    full_margin = (sub.stock_pvp - sub.stock_cost).sum()
    promo_margin = (sub.promo_val - sub.stock_cost).sum()
    return {
        "modelos": int(sub.modelo.nunique()),
        "skus": int(sub.sku.nunique()),
        "unidades": num(sub.stock.sum(), 0),
        "tienda": num(sub.stock_tienda.sum(), 0),
        "taller": num(sub.stock_taller.sum(), 0),
        "costo": num(sub.stock_cost.sum(), 0),
        "pvp": num(sub.stock_pvp.sum(), 0),
        "desc_efectivo": num(wdisc, 4),
        "margen_conservado": num(promo_margin / full_margin, 4) if full_margin else None,
        "costo_mes": num(sub.natural_give.sum(), 0),
        "margen_atrapado": num(sub.trap_margin.sum(), 0),
        "capital6": num(sub.trap_cost.sum(), 0),
        "topados": int(sub.modelo.nunique() and (sub["tope_" + ("impulso" if "impulso" in dcol else "desatasco")].groupby(sub.modelo).any().sum())),
    }


def store_rollup(moves: pd.DataFrame, sk: pd.DataFrame, store_stock, store_sales, models: set, flag: str):
    sub = sk[(sk.modelo.isin(models)) & (sk[flag])].copy()
    rows = []
    mv = moves if moves is not None and len(moves) else pd.DataFrame(columns=["desde", "hacia", "unidades", "modelo"])
    for s in STORES:
        stock = float(store_stock.reindex(sub.sku).fillna(0)[s].sum()) if len(sub) else 0
        venta = float(store_sales.reindex(sub.sku).fillna(0)[s].sum()) if len(sub) else 0
        entrar = float(mv.loc[mv.hacia == s, "unidades"].sum()) if len(mv) else 0
        salir = float(mv.loc[mv.desde == s, "unidades"].sum()) if len(mv) else 0
        desde_taller = float(mv.loc[(mv.hacia == s) & (mv.desde == "Taller"), "unidades"].sum()) if len(mv) else 0
        # model quiebre: model sold in store, stock of model in store is 0
        if len(sub):
            st = store_stock.reindex(sub.sku).fillna(0)[s]
            sa = store_sales.reindex(sub.sku).fillna(0)[s]
            tmp = sub[["modelo"]].copy()
            tmp["st"] = st.values
            tmp["sa"] = sa.values
            g = tmp.groupby("modelo").agg(st=("st", "sum"), sa=("sa", "sum"))
            quiebre = int(((g.sa > 0) & (g.st <= 0)).sum())
        else:
            quiebre = 0
        rows.append(
            {
                "tienda": s,
                "stock": num(stock, 0),
                "venta": num(venta, 0),
                "entrar": num(entrar, 0),
                "salir": num(salir, 0),
                "desdeTaller": num(desde_taller, 0),
                "quiebres": quiebre,
            }
        )
    bajar = num(mv.loc[mv.desde == "Taller", "unidades"].sum(), 0) if len(mv) else 0
    mover = num(mv.loc[mv.desde != "Taller", "unidades"].sum(), 0) if len(mv) else 0
    # model-level pull
    if len(mv):
        pull = (
            mv[mv.desde == "Taller"]
            .groupby("modelo", as_index=False)
            .agg(unidades=("unidades", "sum"), destinos=("hacia", "nunique"))
            .sort_values("unidades", ascending=False)
        )
    else:
        pull = pd.DataFrame(columns=["modelo", "unidades", "destinos"])
    return rows, bajar, mover, pull


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    frames = build_frames()
    scope = frames["scope"]
    base = frames["base"]
    monthly = frames["monthly"]
    store_stock = frames["store_stock"]
    store_sales = frames["store_sales"]
    mod = model_table(scope, monthly)
    sk, ok_i, ok_d, ok_b = assign_options(mod, scope)

    # economics use discounted skus only
    eco_i = option_economics(sk, mod, ok_i, "d_impulso")
    eco_d = option_economics(sk, mod, ok_d, "d_desatasco")

    moves_i = supply_for(sk, scope, store_stock, store_sales, ok_i, "en_impulso")
    moves_d = supply_for(sk, scope, store_stock, store_sales, ok_d, "en_desatasco")
    roll_i, bajar_i, mover_i, pull_i = store_rollup(moves_i, sk, store_stock, store_sales, ok_i, "en_impulso")
    roll_d, bajar_d, mover_d, pull_d = store_rollup(moves_d, sk, store_stock, store_sales, ok_d, "en_desatasco")
    eco_i["bajar"] = bajar_i
    eco_i["mover"] = mover_i
    eco_d["bajar"] = bajar_d
    eco_d["mover"] = mover_d

    rec_id = "impulso"
    b_cost = float(mod.loc[mod.modelo.isin(ok_b), "stock_cost"].sum()) if ok_b else 0.0
    b_names = ", ".join(mod.loc[mod.modelo.isin(ok_b)].sort_values("stock_cost", ascending=False)["modelo"].tolist()) if ok_b else ""

    # ---------- JSON ----------
    def pack_model(r):
        mensual = [num(r[p], 1) or 0 for p in PERIODS]
        return {
            "modelo": r.modelo,
            "macro": r.macro,
            "categoria": r.categoria,
            "matriz": r.matriz,
            "estado": r.estado,
            "rango": r.rango,
            "qty12": num(r.qty_12, 1),
            "qty3": num(r.qty_3m, 1),
            "rate": num(r.rate, 2),
            "cover": None if r.estado == "sin salida" or (r.estado == "frenado" and r.cover >= 900) else num(min(float(r.cover), 120), 1),
            "stock": num(r.stock, 0),
            "tienda": num(r.stock_tienda, 0),
            "taller": num(r.stock_taller, 0),
            "costo": num(r.stock_cost, 0),
            "pvp": num(r.stock_retail, 0),
            "precio": num(r.pvp, 2),
            "costoU": num(r.costo_u, 2),
            "margenPct": num(r.mg_pct, 3),
            "skus": int(r.skus),
            "mensual": mensual,
            "impulso": r.modelo in ok_i,
            "desatasco": r.modelo in ok_d,
            "clase": r.abc_m,
        }

    modelos_out = [pack_model(r) for _, r in mod.sort_values("stock_cost", ascending=False).iterrows() if r.modelo in ok_d]

    # sku lines for dashboard (compact)
    lineas = []
    show = sk[sk.en_desatasco].copy()
    for rec in show.itertuples(index=False):
        lineas.append(
            {
                "sku": rec.sku,
                "modelo": rec.modelo,
                "gen": None if pd.isna(rec.genero) or rec.genero in ("None", "nan") else str(rec.genero),
                "color": None if pd.isna(rec.color) or str(rec.color) in ("None", "nan") else str(rec.color),
                "talla": None if pd.isna(rec.talla) or str(rec.talla) in ("None", "nan") else str(rec.talla),
                "stock": num(rec.stock, 0),
                "tienda": num(rec.stock_tienda, 0),
                "taller": num(rec.stock_taller, 0),
                "precio": num(rec.uprice, 2),
                "costo": num(rec.ucost, 2),
                "dI": num(rec.d_impulso, 2),
                "dD": num(rec.d_desatasco, 2) if rec.en_desatasco else None,
                "topeI": bool(rec.tope_impulso),
                "topeD": bool(rec.tope_desatasco) if rec.en_desatasco else False,
            }
        )

    # no tocar: margin C but rotation A/B, with stock
    no = mod[(mod.abc_m == "C") & (mod.abc_r != "C") & (mod.stock > 0)].sort_values("qty_12", ascending=False)
    no_tocar = [
        {
            "modelo": r.modelo,
            "macro": r.macro,
            "rot": r.abc_r,
            "qty12": num(r.qty_12, 0),
            "stock": num(r.stock, 0),
            "taller": num(r.stock_taller, 0),
            "precio": num(r.pvp, 2),
            "costo": num(r.stock_cost, 0),
        }
        for _, r in no.iterrows()
    ]
    sana = mod[(mod.abc_m == "C") & (mod.abc_r == "C") & (mod.stock >= 1) & (~mod.modelo.isin(ok_i)) & (mod.rango == "<6")]
    sana_out = [
        {
            "modelo": r.modelo,
            "cover": num(r.cover, 1),
            "stock": num(r.stock, 0),
            "qty12": num(r.qty_12, 0),
            "estado": r.estado,
        }
        for _, r in sana.sort_values("stock", ascending=False).iterrows()
    ]
    # sin precio: in scope, stock >= MIN_STOCK, no priced sku, slow or unknown
    priced_models = set(scope[scope.priced].modelo)
    sinp = mod[(~mod.modelo.isin(priced_models)) & (mod.stock >= MIN_STOCK) & (mod.qty_12 < 40)].sort_values("stock", ascending=False)
    # also models not in mod? pelotas inferred are in scope so in mod
    sin_precio = [
        {
            "modelo": r.modelo,
            "macro": r.macro,
            "categoria": r.categoria,
            "origen": r.origen_cat,
            "stock": num(r.stock, 0),
            "taller": num(r.stock_taller, 0),
            "tienda": num(r.stock_tienda, 0),
            "qty12": num(r.qty_12, 0),
        }
        for _, r in sinp.iterrows()
    ]

    def agg_moves(df):
        if df is None or df.empty:
            return []
        g = df.groupby(["modelo", "desde", "hacia"], as_index=False)["unidades"].sum().sort_values("unidades", ascending=False)
        return [
            {"modelo": r.modelo, "desde": r.desde, "hacia": r.hacia, "unidades": int(r.unidades)}
            for _, r in g.iterrows()
            if r.unidades > 0
        ]

    clase = {}
    for cls, part in mod.groupby("abc_m"):
        clase[cls] = {
            "modelos": int(len(part)),
            "margen": num(part.margin.sum(), 0),
            "qty": num(part.qty_12.sum(), 0),
            "stock": num(part.stock.sum(), 0),
            "costo": num(part.stock_cost.sum(), 0),
        }
    matriz = {f"{a}{b}": int(n) for (a, b), n in mod.groupby(["abc_m", "abc_r"]).size().items()}

    # concentration
    solo = [m for m in modelos_out if m["impulso"]]
    top_modelo = max(solo, key=lambda m: m["costo"] or 0) if solo else None

    rec_texto = (
        "Recomendamos Solo categoría C. Es la cola que el ABC ya marca como C de margen y C de rotación: "
        f"{eco_i['modelos']} modelos y ${eco_i['costo']:,.0f} a costo. El descuento sube con los meses de inventario, "
        "del 20% al 40%, y el precio no baja de costo × 1,10. "
        f"La otra opción suma ${b_cost:,.0f} de clase B que tampoco rota y ya pasa de 18 meses de cobertura"
        + (f" ({b_names})" if b_names else "")
        + ". Ahí está el capital dormido más grande, pero no es categoría C. No entra en la recomendación "
        "principal: si la meta se amplía de la cola C a todo lo que no rota, esa es la segunda opción."
    )

    payload = {
        "meta": {
            "periodo": "Octubre 2025 – septiembre 2026",
            "meses": PERIOD_LABELS,
            "tiendas": STORES,
            "unidadesConsumo": num(scope.qty_12.sum(), 0),
            "unidadesMayor": num(scope.qty_mayor.sum(), 0),
            "modelos": int(len(mod)),
            "clase": clase,
            "matriz": matriz,
            "margenTotal": num(mod.loc[mod.margin > 0, "margin"].sum(), 0),
        },
        "recomendacion": {"id": rec_id, "texto": rec_texto},
        "opciones": {
            "impulso": {
                "id": "impulso",
                "nombre": "Solo categoría C",
                "corta": "La cola C de margen y de rotación",
                "frase": "Solo lo que el ABC clasifica como C en margen y C en rotación. El porcentaje sube con los meses de inventario.",
                "tiers": [{"id": a, "label": b, "pct": c} for a, b, c in TIERS_IMPULSO],
                "resumen": eco_i,
                "tiendas": roll_i,
            },
            "desatasco": {
                "id": "desatasco",
                "nombre": "C + lentos de clase B",
                "corta": "La cola C, más la clase B que no rota",
                "frase": "Todo lo de la opción anterior, más los clase B de margen que son C de rotación y ya superan 18 meses de cobertura. Misma escalera de descuento.",
                "tiers": [{"id": a, "label": b, "pct": c} for a, b, c in TIERS_IMPULSO],
                "resumen": eco_d,
                "tiendas": roll_d,
            },
        },
        "modelos": modelos_out,
        "lineas": lineas,
        "noTocar": no_tocar,
        "sana": sana_out,
        "sinPrecio": sin_precio,
        "movimientos": {"impulso": agg_moves(moves_i), "desatasco": agg_moves(moves_d)},
        "pull": {
            "impulso": [{"modelo": r.modelo, "unidades": int(r.unidades), "destinos": int(r.destinos)} for _, r in pull_i.head(12).iterrows()],
            "desatasco": [{"modelo": r.modelo, "unidades": int(r.unidades), "destinos": int(r.destinos)} for _, r in pull_d.head(12).iterrows()],
        },
        "extra": {"modelosB": len(ok_b), "capitalB": num(b_cost, 0)},
        "top": {"modelo": top_modelo["modelo"], "costo": top_modelo["costo"], "macro": top_modelo["macro"]} if top_modelo else None,
    }

    # attach per-model discount + supply highlights for the list
    mod_i = mod.set_index("modelo")
    disc_by = {}
    for modelo, part in sk[sk.en_desatasco].groupby("modelo"):
        part_i = part[part.en_impulso]
        part_d = part[part.en_desatasco]
        pvp = float((part_i.stock * part_i.uprice).sum()) if len(part_i) else 0.0
        promo_i = float((part_i.stock * part_i.uprice * (1 - part_i.d_impulso)).sum()) if len(part_i) else 0.0
        pvp_d = float((part_d.stock * part_d.uprice).sum()) if len(part_d) else 0.0
        promo_d = float((part_d.stock * part_d.uprice * (1 - part_d.d_desatasco)).sum()) if len(part_d) else 0.0
        disc_by[modelo] = {
            "dI": num(1 - promo_i / pvp, 3) if pvp else None,
            "tierI": num(part.tier_impulso.iloc[0], 2),
            "topeI": bool(part_i.tope_impulso.any()) if len(part_i) else False,
            "pvpI": num(promo_i / part_i.stock.sum(), 2) if len(part_i) and part_i.stock.sum() else None,
            "dD": num(1 - promo_d / pvp_d, 3) if pvp_d else None,
            "topeD": bool(part_d.tope_desatasco.any()) if len(part_d) else False,
            "pvpD": num(promo_d / part_d.stock.sum(), 2) if len(part_d) and part_d.stock.sum() else None,
        }
    for m in payload["modelos"]:
        m.update(disc_by.get(m["modelo"], {}))

    # asserts
    assert ok_i <= ok_d
    assert ok_b.isdisjoint(ok_i)
    bad = sk[sk.en_impulso & ((sk.uprice * (1 - sk.d_impulso) + 1e-6) < (sk.ucost * FLOOR))]
    # allow 2 cent rounding from step
    bad = bad[(sk.loc[bad.index, "uprice"] * (1 - sk.loc[bad.index, "d_impulso"])) + 0.05 < sk.loc[bad.index, "ucost"] * FLOOR]
    assert bad.empty, bad[["sku", "uprice", "ucost", "d_impulso"]].head()
    bad_b = sk[sk.en_desatasco & ((sk.uprice * (1 - sk.d_desatasco)) + 0.05 < sk.ucost * FLOOR)]
    assert bad_b.empty, bad_b[["sku", "uprice", "ucost", "d_desatasco"]].head()
    assert eco_i["modelos"] == len(ok_i)
    assert eco_d["modelos"] == len(ok_d)

    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    template = HTML_TEMPLATE.read_text(encoding="utf-8")
    if "__DATA__" not in template:
        raise SystemExit("template sin marcador __DATA__")
    HTML_OUT.write_text(template.replace("__DATA__", data_json), encoding="utf-8")

    write_excel(mod, sk, ok_i, ok_d, moves_i, moves_d, payload, store_stock, store_sales)
    print_summary(payload, mod, ok_i, ok_d, ok_b, rec_id)
    print("HTML", HTML_OUT, "bytes", HTML_OUT.stat().st_size)
    print("XLSX", XLSX_OUT)


def print_summary(payload, mod, ok_i, ok_d, ok_b, rec_id):
    print("\n=== CLASE MARGEN ===")
    print(payload["meta"]["clase"])
    print("matriz", payload["meta"]["matriz"])
    print("REC", rec_id, "addon B", sorted(ok_b))
    for k in ("impulso", "desatasco"):
        print(k, payload["opciones"][k]["resumen"])
    print("sin precio")
    for s in payload["sinPrecio"]:
        print(" ", s)
    print("no tocar", len(payload["noTocar"]), "sana", len(payload["sana"]))
    print("top", payload["top"])
    cc = mod[(mod.abc_m == "C") & (mod.abc_r == "C")]
    print("CC models", len(cc), "in solo C", len(ok_i), "in C+B", len(ok_d), "addon B", ok_b)
    print(cc[cc.modelo.isin(ok_i)].groupby("rango").agg(n=("modelo", "count"), stock=("stock", "sum"), cost=("stock_cost", "sum")).round(0))


def write_excel(mod, sk, ok_i, ok_d, moves_i, moves_d, payload, store_stock, store_sales):
    wb = Workbook()
    navy = PatternFill("solid", fgColor="1B2430")
    white = Font(color="FFFFFF", bold=True, name="Calibri", size=11)
    green = PatternFill("solid", fgColor="0F6E56")
    amber = PatternFill("solid", fgColor="8A5A00")
    pink = PatternFill("solid", fgColor="8C3A62")
    ice = PatternFill("solid", fgColor="F4F7FB")
    soft = PatternFill("solid", fgColor="E7F6F1")
    sand = PatternFill("solid", fgColor="FFF6E8")
    thin = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )
    title_font = Font(name="Calibri", size=18, bold=True, color="1B2430")
    h2 = Font(name="Calibri", size=13, bold=True, color="1B2430")
    body = Font(name="Calibri", size=11, color="1B2430")
    muted = Font(name="Calibri", size=11, color="526072")

    def style_header(ws, row, cols, fill):
        for c in range(1, cols + 1):
            cell = ws.cell(row, c)
            cell.fill = fill
            cell.font = white
            cell.alignment = Alignment(wrap_text=True, vertical="center")

    def autosize(ws, widths):
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.auto_filter.ref = ws.dimensions
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.oddHeader.left.text = "Black Friday · Categoría C"
        ws.oddFooter.right.text = "Página &P"

    def paint(ws):
        ws.sheet_view.showGridLines = False
        ws.page_setup.horizontalCentered = True
        ws.sheet_properties.tabColor = "1B2430"

    # ----- portada
    ws = wb.active
    ws.title = "01_Decision"
    paint(ws)
    ws.sheet_properties.tabColor = "0F6E56"
    ws.merge_cells("B2:G2")
    ws["B2"] = "Propuesta Black Friday · Categoría C"
    ws["B2"].font = title_font
    ws.merge_cells("B3:G3")
    ws["B3"] = "Manufactura y equipamiento de baja rotación  ·  Octubre 2025 a septiembre 2026"
    ws["B3"].font = muted
    ws.merge_cells("B5:G5")
    ws["B5"] = payload["recomendacion"]["texto"]
    ws["B5"].font = body
    ws["B5"].alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[5].height = 60

    headers = ["", "Solo categoría C", "C + lentos de clase B"]
    for i, h in enumerate(headers, 2):
        ws.cell(7, i, h).font = white
        ws.cell(7, i).fill = green if i == 2 else (amber if i == 3 else navy)
        ws.cell(7, i).alignment = Alignment(horizontal="center")
    ri = payload["opciones"]["impulso"]["resumen"]
    rd = payload["opciones"]["desatasco"]["resumen"]
    rows = [
        ("Modelos", ri["modelos"], rd["modelos"]),
        ("SKUs con descuento", ri["skus"], rd["skus"]),
        ("Unidades en inventario", ri["unidades"], rd["unidades"]),
        ("En tienda", ri["tienda"], rd["tienda"]),
        ("En taller", ri["taller"], rd["taller"]),
        ("Capital a costo (USD)", ri["costo"], rd["costo"]),
        ("Inventario a precio actual (USD)", ri["pvp"], rd["pvp"]),
        ("Capital que sobra sobre 6 meses (USD costo)", ri["capital6"], rd["capital6"]),
        ("Descuento efectivo sobre el inventario", ri["desc_efectivo"], rd["desc_efectivo"]),
        ("Margen del inventario que se conserva", ri["margen_conservado"], rd["margen_conservado"]),
        ("Margen que se entrega en un mes de venta normal (USD)", ri["costo_mes"], rd["costo_mes"]),
        ("Margen promo del inventario que sobra (USD)", ri["margen_atrapado"], rd["margen_atrapado"]),
        ("Unidades a bajar de taller antes del evento", ri["bajar"], rd["bajar"]),
        ("Unidades a mover entre tiendas", ri["mover"], rd["mover"]),
    ]
    for i, (lab, a, b) in enumerate(rows, 8):
        ws.cell(i, 2, lab).font = body
        ws.cell(i, 3, a).font = Font(name="Calibri", size=12, bold=True, color="1B2430")
        ws.cell(i, 4, b).font = Font(name="Calibri", size=12, bold=True, color="1B2430")
        if i % 2 == 0:
            for col in range(2, 5):
                ws.cell(i, col).fill = ice
        ws.cell(i, 2).alignment = Alignment(wrap_text=True)
    for r in range(15, 17):
        ws.cell(r, 3).number_format = "0.0%"
        ws.cell(r, 4).number_format = "0.0%"
    for r in list(range(8, 15)) + list(range(17, 22)):
        ws.cell(r, 3).number_format = "#,##0"
        ws.cell(r, 4).number_format = "#,##0"

    ws["B24"] = "Cómo leer las dos opciones"
    ws["B24"].font = h2
    notes = [
        "Solo categoría C: clase C de margen y clase C de rotación, con 5 unidades o más, y cobertura de 6 meses o más (o sin venta reciente). El descuento es 20%, 25%, 30%, 35% o 40% según ese plazo. Lo que no vendió en el trimestre entra al 40%.",
        "C + lentos de clase B: todo lo anterior, más los modelos clase B de margen y C de rotación con 18 meses o más de cobertura. Usan la misma escalera. Zenit y Maxi Tote están aquí porque no son C, y concentran capital dormido.",
        "En las dos, el precio promocional no baja de costo × 1.10. Si el margen no alcanza, el porcentaje se recorta de 5 en 5. Por eso el descuento efectivo puede ser menor que el de la escalera.",
        "No entra la clase A ni la B. Tampoco entra la clase C de margen que sí rota (lanyard, cuadro band, overgrip, medias): son baratos, no lentos. Esos se reponen; no se descuentan.",
        "El ritmo sale de las tiendas y de la web. Pedidos y Corporativo quedan fuera porque son bultos mayoristas y cambian la foto de rotación.",
        "Cobertura: si los últimos 3 meses se aceleraron, se usa ese ritmo para no castigar un producto que está despertando. Si se frenaron a menos de la mitad, se usa el ritmo nuevo. Si no hubo venta en el trimestre, queda dormido.",
        "Precios y costos son el promedio ponderado del dashboard ABC (octubre 2025–julio 2026). El cuadro de ventas nuevo trae unidades, no precios.",
        "CHACAO del inventario se lee como Sambil Chacao y SAMBIL como Sambil Valencia, igual que las ubicaciones del dashboard ABC.",
    ]
    for i, t in enumerate(notes):
        ws.merge_cells(start_row=25 + i, start_column=2, end_row=25 + i, end_column=7)
        ws.cell(25 + i, 2, t).font = body
        ws.cell(25 + i, 2).alignment = Alignment(wrap_text=True, vertical="center")
        ws.row_dimensions[25 + i].height = 32
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 62
    ws.column_dimensions["C"].width = 28
    ws.column_dimensions["D"].width = 28
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 18
    ws.column_dimensions["G"].width = 18
    ws.row_dimensions[2].height = 26
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID
    ws.print_title_rows = "1:3"
    ws.oddHeader.left.text = "Propuesta directiva"
    ws.oddFooter.left.text = "Categoría C · manufactura y equipamiento"
    ws.oddFooter.right.text = "Confidencial interno"

    # mark recommendation
    mark_row = 6
    ws.cell(mark_row, 3, "RECOMENDADA" if payload["recomendacion"]["id"] == "impulso" else "Alternativa")
    ws.cell(mark_row, 4, "RECOMENDADA" if payload["recomendacion"]["id"] == "desatasco" else "Alternativa")
    for col, fid in ((3, "impulso"), (4, "desatasco")):
        ws.cell(mark_row, col).font = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
        ws.cell(mark_row, col).fill = green if payload["recomendacion"]["id"] == fid else PatternFill("solid", fgColor="94A3B8")
        ws.cell(mark_row, col).alignment = Alignment(horizontal="center")

    write_option_sheet(wb, "02_Solo_C", sk, mod, ok_i, "d_impulso", "en_impulso", green, white, thin, body, ice)
    write_option_sheet(wb, "03_C_mas_B", sk, mod, ok_d, "d_desatasco", "en_desatasco", amber, white, thin, body, sand)
    write_sku_sheet(wb, sk, mod, white, navy, thin, body, ice)
    write_moves_sheet(wb, moves_i, moves_d, white, navy, thin, body)
    write_notocar(wb, payload, mod, white, pink, thin, body, ice)
    write_sinprecio(wb, payload, white, navy, thin, body)
    write_matriz(wb, mod, white, navy, thin, body, ice)
    write_abasto_tienda(wb, payload, white, navy, thin, body, ice)

    # chart data already on decision sheet — add a small bar via a helper sheet
    add_chart(wb, payload)

    wb.save(XLSX_OUT)


def write_option_sheet(wb, name, sk, mod, models, dcol, flag, fill, white, thin, body, zebra):
    ws = wb.create_sheet(name)
    ws.sheet_view.showGridLines = False
    headers = [
        "Modelo",
        "Línea",
        "Categoría",
        "Estado",
        "Cobertura (meses)",
        "Venta 12 meses",
        "Venta últimos 3 meses",
        "Ritmo usado (u/mes)",
        "Stock total",
        "Stock tienda",
        "Stock taller",
        "Precio promedio",
        "Costo unitario",
        "Descuento",
        "Precio Black Friday",
        "Tope de costo",
        "Capital a costo",
        "Inventario a precio",
        "SKUs en promo",
    ]
    for i, h in enumerate(headers, 1):
        ws.cell(1, i, h)
    for c in range(1, len(headers) + 1):
        ws.cell(1, c).fill = fill
        ws.cell(1, c).font = white
        ws.cell(1, c).alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 32
    m = mod.set_index("modelo")
    sub = sk[(sk.modelo.isin(models)) & (sk[flag])].copy()
    recs = []
    for modelo, part in sub.groupby("modelo"):
        r = m.loc[modelo]
        pvp = float((part.stock * part.uprice).sum())
        promo = float((part.stock * part.uprice * (1 - part[dcol])).sum())
        costo = float((part.stock * part.ucost).sum())
        recs.append((costo, [
            modelo,
            r.macro,
            r.categoria,
            r.estado,
            None if r.cover >= 900 else round(float(r.cover), 1),
            round(float(r.qty_12), 1),
            round(float(r.qty_3m), 1),
            round(float(r.rate), 2),
            round(float(part.stock.sum()), 0),
            round(float(part.stock_tienda.sum()), 0),
            round(float(part.stock_taller.sum()), 0),
            round(pvp / part.stock.sum(), 2) if part.stock.sum() else None,
            round(costo / part.stock.sum(), 2) if part.stock.sum() else None,
            round(1 - promo / pvp, 4) if pvp else None,
            round(promo / part.stock.sum(), 2) if part.stock.sum() else None,
            "Sí" if bool(part["tope_impulso" if "impulso" in dcol else "tope_desatasco"].any()) else "No",
            round(costo, 0),
            round(pvp, 0),
            int(part.sku.nunique()),
        ]))
    recs.sort(key=lambda x: -x[0])
    for i, (_, vals) in enumerate(recs, 2):
        for c, v in enumerate(vals, 1):
            cell = ws.cell(i, c, v)
            cell.font = body
            cell.border = thin
            if i % 2 == 0:
                cell.fill = zebra
        ws.cell(i, 14).number_format = "0%"
        for col in (5, 6, 7, 8, 12, 13, 15):
            ws.cell(i, col).number_format = "#,##0.00"
        for col in (9, 10, 11, 17, 18, 19):
            ws.cell(i, col).number_format = "#,##0"
    widths = [38, 16, 38, 14, 16, 16, 18, 16, 14, 14, 14, 16, 14, 12, 18, 14, 16, 18, 14]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(1, len(recs)+1)}"
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID
    ws.page_setup.horizontalCentered = True
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = "1:1"
    ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID
    ws.oddHeader.left.text = name
    last = max(1, len(recs) + 1)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{last}"
    if "Solo" in name:
        ws.sheet_properties.tabColor = "0F6E56"
    else:
        ws.sheet_properties.tabColor = "8A5A00"


def write_sku_sheet(wb, sk, mod, white, navy, thin, body, zebra):
    ws = wb.create_sheet("04_Detalle_SKU")
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "334155"
    headers = [
        "Modelo", "Línea", "SKU", "Género", "Color", "Talla",
        "Stock total", "Stock tienda", "Stock taller", "Precio", "Costo",
        "En Solo C", "Descuento Solo C", "Precio Solo C",
        "En C+B", "Descuento C+B", "Precio C+B",
        "Venta 12 meses", "Venta 3 meses", "Origen precio",
    ]
    for i, h in enumerate(headers, 1):
        cell = ws.cell(1, i, h)
        cell.fill = navy
        cell.font = white
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 30
    show = sk.sort_values(["modelo", "stock"], ascending=[True, False])
    for i, r in enumerate(show.itertuples(index=False), 2):
        promo_i = round(r.uprice * (1 - r.d_impulso), 2) if r.en_impulso else None
        promo_d = round(r.uprice * (1 - r.d_desatasco), 2) if r.en_desatasco else None
        vals = [
            r.modelo, r.macro, r.sku,
            None if str(r.genero) in ("nan", "None") else r.genero,
            None if str(r.color) in ("nan", "None") else r.color,
            None if str(r.talla) in ("nan", "None") else r.talla,
            round(r.stock, 0), round(r.stock_tienda, 0), round(r.stock_taller, 0),
            round(r.uprice, 2), round(r.ucost, 2),
            "Sí" if r.en_impulso else "No",
            round(r.d_impulso, 4) if r.en_impulso else None,
            promo_i,
            "Sí" if r.en_desatasco else "No",
            round(r.d_desatasco, 4) if r.en_desatasco else None,
            promo_d,
            round(r.qty_12, 1), round(r.qty_3m, 1), r.precio_origen,
        ]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(i, c, v)
            cell.font = body
            cell.border = thin
            if i % 2 == 0:
                cell.fill = zebra
        ws.cell(i, 13).number_format = "0%"
        ws.cell(i, 16).number_format = "0%"
    widths = [32, 16, 20, 12, 18, 10, 12, 12, 12, 12, 12, 12, 16, 14, 14, 18, 16, 14, 12, 14]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:T{max(1, len(show)+1)}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID
    ws.print_title_rows = "1:1"
    ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID


def write_moves_sheet(wb, moves_i, moves_d, white, navy, thin, body):
    ws = wb.create_sheet("05_Movimientos")
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "1D4ED8"
    headers = ["Aplica a", "Modelo", "Línea", "SKU", "Desde", "Hacia", "Unidades"]
    for i, h in enumerate(headers, 1):
        cell = ws.cell(1, i, h)
        cell.fill = navy
        cell.font = white
    # tag
    a = moves_i.copy() if len(moves_i) else pd.DataFrame(columns=["sku", "modelo", "macro", "desde", "hacia", "unidades"])
    b = moves_d.copy() if len(moves_d) else pd.DataFrame(columns=["sku", "modelo", "macro", "desde", "hacia", "unidades"])
    a["op"] = "Solo C"
    b["op"] = "C + B"
    # SKUs in both: mark Desatasco rows as such and Impulso-only stays Impulso.
    # A warehouse executing the recommended option filters this column.
    both = pd.concat([a, b], ignore_index=True)
    both = both.sort_values(["op", "unidades"], ascending=[True, False])
    for i, r in enumerate(both.itertuples(index=False), 2):
        vals = [r.op, r.modelo, r.macro, r.sku, r.desde, r.hacia, int(r.unidades)]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(i, c, v)
            cell.font = body
            cell.border = thin
    ws.cell(1, 1).alignment = Alignment(wrap_text=True)
    note_row = len(both) + 3
    ws.cell(note_row, 1, "Regla: primero se baja del taller. Entre tiendas solo se mueve lo que sobra por encima de la meta. Cada tienda que ya vendió el SKU queda con al menos 1 unidad. El tope por tienda es cerca de 2 meses de su propia venta. Si el SKU nunca se vendió, se siembran hasta 2 unidades en las 3 tiendas que más venden el modelo.")
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=7)
    ws.cell(note_row, 1).alignment = Alignment(wrap_text=True)
    ws.row_dimensions[note_row].height = 48
    for i, w in enumerate([18, 36, 16, 20, 20, 20, 12], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:G{max(1, len(both)+1)}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID
    ws.print_title_rows = "1:1"


def write_notocar(wb, payload, mod, white, fill, thin, body, zebra):
    ws = wb.create_sheet("06_No_descontar")
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "8C3A62"
    headers = ["Modelo", "Línea", "Rotación", "Venta 12 meses", "Stock", "En taller", "Precio", "Capital a costo", "Por qué no"]
    for i, h in enumerate(headers, 1):
        cell = ws.cell(1, i, h)
        cell.fill = fill
        cell.font = white
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 30
    row = 2
    for r in payload["noTocar"]:
        why = "Clase C de margen porque el precio es bajo, pero la rotación es alta. Descontarlo no sube la rotación: ya sale. Si el taller está lleno, la acción es repartir, no bajar el precio."
        vals = [r["modelo"], r["macro"], r["rot"], r["qty12"], r["stock"], r["taller"], r["precio"], r["costo"], why]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row, c, v)
            cell.font = body
            cell.border = thin
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        row += 1
    for r in payload["sana"]:
        vals = [r["modelo"], "", "", r["qty12"], r["stock"], None, None, None, f"Sí es baja rotación histórica, pero la cobertura real es {r['cover']} meses ({r['estado']}). No necesita descuento."]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row, c, v)
            cell.font = body
            cell.border = thin
            cell.alignment = Alignment(wrap_text=True)
        row += 1
    for i, w in enumerate([36, 16, 12, 16, 12, 12, 12, 18, 70], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:I{max(1, row-1)}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID
    ws.page_setup.fitToPage = True


def write_sinprecio(wb, payload, white, navy, thin, body):
    ws = wb.create_sheet("07_Sin_precio")
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "B45309"
    headers = ["Modelo", "Línea", "Categoría", "Cómo se clasificó", "Stock", "En tienda", "En taller", "Venta 12 meses", "Nota"]
    amber = PatternFill("solid", fgColor="B45309")
    for i, h in enumerate(headers, 1):
        cell = ws.cell(1, i, h)
        cell.fill = amber
        cell.font = white
    for i, r in enumerate(payload["sinPrecio"], 2):
        nota = "Hay inventario y casi no hay salida, pero el ABC no trae precio ni costo de este modelo. No se propone un porcentaje hasta cargar el precio. Si se aprueba la campaña, este bulto se decide aparte."
        vals = [r["modelo"], r["macro"], r["categoria"], r["origen"], r["stock"], r["tienda"], r["taller"], r["qty12"], nota]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(i, c, v)
            cell.font = body
            cell.border = thin
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.row_dimensions[i].height = 32
    for i, w in enumerate([28, 16, 32, 18, 12, 12, 12, 16, 78], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    last = max(1, len(payload["sinPrecio"]) + 1)
    ws.auto_filter.ref = f"A1:I{last}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID
    ws.page_setup.fitToPage = True


def write_matriz(wb, mod, white, navy, thin, body, zebra):
    ws = wb.create_sheet("08_Matriz_ABC")
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "64748B"
    headers = ["Modelo", "Línea", "Categoría", "Clase margen", "Clase rotación", "Matriz", "Venta 12 meses", "Margen USD", "Stock", "Capital costo", "Cobertura", "Estado"]
    for i, h in enumerate(headers, 1):
        cell = ws.cell(1, i, h)
        cell.fill = navy
        cell.font = white
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ordered = mod.sort_values(["abc_m", "margin"], ascending=[True, False])
    fills = {"A": PatternFill("solid", fgColor="CFFAFE"), "B": PatternFill("solid", fgColor="FEF3C7"), "C": PatternFill("solid", fgColor="FCE7F3")}
    for i, r in enumerate(ordered.itertuples(index=False), 2):
        vals = [
            r.modelo, r.macro, r.categoria, r.abc_m, r.abc_r, r.matriz,
            round(float(r.qty_12), 1), round(float(r.margin), 0), round(float(r.stock), 0),
            round(float(r.stock_cost), 0), None if r.cover >= 900 else round(float(r.cover), 1), r.estado,
        ]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(i, c, v)
            cell.font = body
            cell.border = thin
        ws.cell(i, 4).fill = fills.get(r.abc_m, zebra)
        ws.cell(i, 5).fill = fills.get(r.abc_r, zebra)
    for i, w in enumerate([36, 16, 40, 14, 14, 12, 16, 14, 12, 16, 12, 14], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:L{len(ordered)+1}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID
    ws.page_setup.fitToPage = True
    ws.print_title_rows = "1:1"


def write_abasto_tienda(wb, payload, white, navy, thin, body, zebra):
    ws = wb.create_sheet("09_Abasto_tiendas")
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "1D4ED8"
    ws["A1"] = "Tienda"
    ws["B1"] = "Solo C · stock hoy"
    ws["C1"] = "Solo C · venta 12m"
    ws["D1"] = "Solo C · entran"
    ws["E1"] = "Solo C · salen"
    ws["F1"] = "Solo C · desde taller"
    ws["G1"] = "Solo C · modelos en quiebre"
    ws["H1"] = "C+B · stock hoy"
    ws["I1"] = "C+B · entran"
    ws["J1"] = "C+B · desde taller"
    ws["K1"] = "C+B · modelos en quiebre"
    for c in range(1, 12):
        ws.cell(1, c).fill = navy
        ws.cell(1, c).font = white
        ws.cell(1, c).alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 32
    ti_i = {t["tienda"]: t for t in payload["opciones"]["impulso"]["tiendas"]}
    ti_d = {t["tienda"]: t for t in payload["opciones"]["desatasco"]["tiendas"]}
    for i, s in enumerate(STORES, 2):
        a, b = ti_i[s], ti_d[s]
        vals = [s, a["stock"], a["venta"], a["entrar"], a["salir"], a["desdeTaller"], a["quiebres"], b["stock"], b["entrar"], b["desdeTaller"], b["quiebres"]]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(i, c, v)
            cell.font = body
            cell.border = thin
            if i % 2 == 0:
                cell.fill = zebra
            if c > 1:
                cell.number_format = "#,##0"
    ws.cell(10, 1, "Quiebre = la tienda vendió el modelo en el año y hoy no tiene ninguna unidad de los SKU en promo.")
    ws.merge_cells("A10:K10")
    for i, w in enumerate([20, 18, 18, 16, 16, 18, 22, 20, 16, 20, 24], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID
    ws.page_setup.fitToPage = True
    ws.freeze_panes = "B2"


def add_chart(wb, payload):
    ws = wb.create_sheet("10_Grafico", 1)
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "0F6E56"
    ws["A1"] = "Concepto"
    ws["B1"] = "Impulso"
    ws["C1"] = "Desatasco"
    ri = payload["opciones"]["impulso"]["resumen"]
    rd = payload["opciones"]["desatasco"]["resumen"]
    data = [
        ("Unidades", ri["unidades"], rd["unidades"]),
        ("Capital a costo", ri["costo"], rd["costo"]),
        ("Capital sobre 6 meses", ri["capital6"], rd["capital6"]),
        ("Bajar de taller", ri["bajar"], rd["bajar"]),
    ]
    for i, row in enumerate(data, 2):
        for c, v in enumerate(row, 1):
            ws.cell(i, c, v)
    chart = BarChart()
    chart.type = "col"
    chart.grouping = "clustered"
    chart.title = "Las dos opciones, en la misma escala de cada indicador"
    chart.y_axis.title = None
    chart.style = 10
    chart.y_axis.majorGridlines = None
    data_ref = Reference(ws, min_col=2, max_col=3, min_row=1, max_row=5)
    cats = Reference(ws, min_col=1, min_row=2, max_row=5)
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats)
    chart.shape = 4
    chart.legend.position = "b"
    chart.y_axis.numFmt = "#,##0"
    chart.dataLabels = DataLabelList()
    chart.dataLabels.showVal = False
    chart.width = 18
    chart.height = 8
    # Two different units on one axis would lie. Split: units chart and money chart.
    ws["A8"] = "Unidades y movimientos"
    ws["B8"] = "Impulso"
    ws["C8"] = "Desatasco"
    for i, key in enumerate(["unidades", "bajar", "mover"], 9):
        labels = {"unidades": "Unidades en inventario", "bajar": "Bajar de taller", "mover": "Mover entre tiendas"}
        ws.cell(i, 1, labels[key])
        ws.cell(i, 2, ri[key])
        ws.cell(i, 3, rd[key])
    chart1 = BarChart()
    chart1.type = "col"
    chart1.grouping = "clustered"
    chart1.title = "Unidades"
    chart1.style = 10
    chart1.add_data(Reference(ws, min_col=2, max_col=3, min_row=8, max_row=11), titles_from_data=True)
    chart1.set_categories(Reference(ws, min_col=1, min_row=9, max_row=11))
    chart1.shape = 4
    chart1.legend.position = "b"
    chart1.y_axis.numFmt = "#,##0"
    chart1.width = 15
    chart1.height = 7
    ws.add_chart(chart1, "E8")

    ws["A16"] = "Dólares a costo"
    ws["B16"] = "Impulso"
    ws["C16"] = "Desatasco"
    for i, (lab, key) in enumerate([
        ("Capital a costo", "costo"),
        ("Sobra sobre 6 meses", "capital6"),
        ("Margen que se entrega en 1 mes", "costo_mes"),
        ("Margen promo de lo que sobra", "margen_atrapado"),
    ], 17):
        ws.cell(i, 1, lab)
        ws.cell(i, 2, ri[key])
        ws.cell(i, 3, rd[key])
    chart2 = BarChart()
    chart2.type = "bar"
    chart2.grouping = "clustered"
    chart2.title = "Capital y margen (USD)"
    chart2.style = 10
    chart2.add_data(Reference(ws, min_col=2, max_col=3, min_row=16, max_row=20), titles_from_data=True)
    chart2.set_categories(Reference(ws, min_col=1, min_row=17, max_row=20))
    chart2.shape = 4
    chart2.legend.position = "b"
    chart2.y_axis.numFmt = "$#,##0"
    chart2.width = 18
    chart2.height = 8
    ws.add_chart(chart2, "E16")
    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 16
    # The first combined chart would mix scales; do not add it.
    ws["A1"] = "Respaldo de gráficos. La lectura para directiva está en 01_Decision y en el dashboard."
    ws.merge_cells("A1:C1")


if __name__ == "__main__":
    main()
