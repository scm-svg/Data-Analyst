"""Shared store dashboard data pipeline and HTML renderer."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import FrozenSet

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = Path(__file__).resolve().parent / "dashboard_template.html"

TARGET_COVERAGE_MONTHS = 2.5
URGENT_COVERAGE_MAX = 2.0

MES_LABELS = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}
MES_FULL = {
    1: "Ene 2026", 2: "Feb 2026", 3: "Mar 2026", 4: "Abr 2026", 5: "May 2026",
    6: "Jun 2026", 7: "Jul 2026", 8: "Ago 2026", 9: "Sep 2026", 10: "Oct 2026",
    11: "Nov 2026", 12: "Dic 2026",
}


@dataclass
class StoreTheme:
    fonts_url: str
    css_root: str
    hdr_bg: str
    badge_grad: str
    badge_text: str
    insight_bg: str
    insight_border: str
    chip_on_text: str
    rep_border: str
    rep_bg: str
    palette: list[str]
    chart_accent: str
    chart_accent_dim: str


@dataclass
class StoreConfig:
    store_name: str
    store_badge: str
    stock_path: Path
    sales_path: Path
    stock_sheet: str
    sales_sheet: str
    sales_model_col: str = "modelo"
    out_html: Path = field(default_factory=lambda: ROOT / "dashboard.html")
    exclude_models: FrozenSet[str] = frozenset({
        "BOLSAS KRAFT NAVIDAD",
        "BOLSAS KRAFT",
        "CUADRO BAND VENEZUELA",
    })
    meta_suffix: str = "excl. Kraft/Band VZLA"
    footer_sources: str = "Ventas + Inventario"
    page_title: str = ""
    theme: StoreTheme | None = None


def norm_str(x):
    if pd.isna(x):
        return ""
    return str(x).strip()


def base_model(name):
    n = norm_str(name).upper()
    n = re.sub(r"^\[.*?\]\s*", "", n)
    for suf in (" CAB", " DAMA", " KIDS"):
        if n.endswith(suf):
            return n[: -len(suf)].strip()
    return n


def categorize(model):
    m = model.upper()
    rules = [
        ("Toallas", ["TOALLA"]),
        ("Bolsos & Mochilas", ["BAG", "BACKPACK", "TOTE", "CITYBAG", "DRY BAG", "TRAVEL", "PACKING", "MINI BAG", "ECO BAG", "MAXI"]),
        ("Gorras & Sombreros", ["CAP", "HAT", "VISERA", "BUCKET", "HEADBAND"]),
        ("Ropa inferior", ["PANTS", "SHORT", "FALDA", "LEGGING"]),
        ("Ropa superior", [
            "MAR ORIGINAL", "RIO ORIGINAL", "JACKET", "POLO", "SOCKS", "TOP ", "TEE", "OVERSIZED",
            "CROP", "PONCHO", "VESTIDO", "SPORT LITE", "BIO MOVE", "MOTION", "ACTIVE", "CLASICA",
            "CLÁSICA", "SPOTS", "CUADRO JACKET", "BASIC LINE",
        ]),
        ("Accesorios", ["LLAVERO", "LANYARD", "CORD", "GRIP", "PORTAVASOS", "CUADRO BAND", "CUADRO TAG", "ZENIT"]),
    ]
    for cat, kws in rules:
        if any(k in m for k in kws):
            return cat
    return "Otros"


def is_excluded(name, exclude_models):
    n = base_model(name)
    if n in exclude_models:
        return True
    return norm_str(name).upper() in exclude_models


def stock_line_key(row):
    modelo = norm_str(row.get("MODELO")).upper()
    gen = norm_str(row.get("GENERO")).upper()
    if gen:
        return f"{modelo} {gen}"
    return modelo


def sales_line_key(row):
    return norm_str(row.get("modelo")).upper()


def inventory_status(v, s, vel, mos, r):
    if v == 0 and s > 0:
        return "sin_venta"
    if v > 0 and s == 0:
        return "quiebre"
    if v > 0 and vel > 0 and mos < URGENT_COVERAGE_MAX:
        return "critico"
    if v > 0 and vel > 0 and mos > 6:
        return "exceso"
    if v > 0 and ((vel > 0 and mos > 4 and r < 30) or (s >= 10 and v > 0 and r < 15)):
        return "lento"
    if v > 0:
        return "saludable"
    return "sin_venta"


def build_payload(cfg: StoreConfig) -> dict:
    stock = pd.read_excel(cfg.stock_path, sheet_name=cfg.stock_sheet)
    sales = pd.read_excel(cfg.sales_path, sheet_name=cfg.sales_sheet)

    if cfg.sales_model_col != "modelo":
        sales = sales.rename(columns={cfg.sales_model_col: "modelo"})

    excl = cfg.exclude_models
    stock = stock[~stock["MODELO"].apply(lambda x: is_excluded(x, excl))]
    sales = sales[~sales["modelo"].apply(lambda x: is_excluded(x, excl))]

    sales = sales.copy()
    sales["base"] = sales["modelo"].apply(base_model)
    sales["fecha_parsed"] = pd.to_datetime(sales["fecha (mes año)"], format="%m/%Y", errors="coerce")
    sales["mes_num"] = sales["fecha_parsed"].dt.month
    sales["qty"] = sales["Cant. ordenada"].fillna(0).astype(int)

    months_sorted = sorted(sales["mes_num"].dropna().unique().astype(int).tolist())
    mes_labels = [MES_LABELS.get(m, str(m)) for m in months_sorted]
    mon_totals = [int(sales[sales["mes_num"] == m]["qty"].sum()) for m in months_sorted]
    n_months = max(len(months_sorted), 1)

    stock = stock.copy()
    stock["base"] = stock["MODELO"].apply(base_model)
    stock["qty"] = stock["Cantidad en inventario"].fillna(0).astype(int)

    all_models = sorted(set(stock["base"].unique()) | set(sales["base"].unique()))
    all_models = [m for m in all_models if m]

    products = []
    for model in all_models:
        s_rows = sales[sales["base"] == model]
        st_rows = stock[stock["base"] == model]
        v = int(s_rows["qty"].sum())
        s = int(st_rows["qty"].sum())
        total = v + s
        r = round(v / total * 100) if total > 0 else 0
        velocity = round(v / n_months, 1)
        monthly = [int(s_rows[s_rows["mes_num"] == m]["qty"].sum()) for m in months_sorted]

        vars_map = defaultdict(lambda: {"v": 0, "tallas": defaultdict(int), "genero": ""})
        for _, row in s_rows.iterrows():
            color = norm_str(row.get("COLOR")) or "Sin color"
            gen = norm_str(row.get("GENERO")) or ""
            key = (color, gen)
            vars_map[key]["v"] += int(row["qty"])
            vars_map[key]["genero"] = gen
            t = norm_str(row.get("TALLA"))
            if t:
                vars_map[key]["tallas"][t] += int(row["qty"])

        vars_list = []
        for (color, gen), data in sorted(vars_map.items(), key=lambda x: -x[1]["v"]):
            tallas = [{"talla": t, "v": c} for t, c in sorted(data["tallas"].items(), key=lambda x: -x[1])]
            vars_list.append({"color": color, "genero": gen, "v": data["v"], "tallas": tallas[:12]})

        mos = round(s / velocity, 1) if velocity > 0 else (999 if s > 0 else 0)
        est = inventory_status(v, s, velocity, min(mos, 999), r)
        products.append({
            "n": model, "v": v, "s": s, "r": r, "vel": velocity,
            "mos": min(mos, 999), "est": est, "m": monthly,
            "cat": categorize(model), "vars": vars_list[:25], "srch": model.lower(),
        })

    products.sort(key=lambda p: (-p["v"], -p["s"]))

    line_sales = defaultdict(lambda: {"v": 0, "colors": set(), "skus": set(), "base": ""})
    for _, row in sales.iterrows():
        lk = sales_line_key(row)
        if is_excluded(lk, excl):
            continue
        line_sales[lk]["v"] += int(row["qty"])
        line_sales[lk]["base"] = base_model(row["modelo"])
        c = norm_str(row.get("COLOR"))
        if c:
            line_sales[lk]["colors"].add(c.lower())
        sku = norm_str(row.get("SKU"))
        if sku:
            line_sales[lk]["skus"].add(sku.lower())

    line_stock = defaultdict(int)
    for _, row in stock.iterrows():
        lk = stock_line_key(row)
        if is_excluded(lk, excl):
            continue
        line_stock[lk] += int(row["qty"])

    lines = []
    for lk in sorted(set(line_sales.keys()) | set(line_stock.keys())):
        v = int(line_sales[lk]["v"]) if lk in line_sales else 0
        s = int(line_stock.get(lk, 0))
        base = line_sales[lk]["base"] if lk in line_sales else base_model(lk)
        vel = round(v / n_months, 1)
        total = v + s
        r = round(v / total * 100) if total > 0 else 0
        mos = round(s / vel, 1) if vel > 0 else (999 if s > 0 else 0)
        mos_c = min(mos, 999)
        est = inventory_status(v, s, vel, mos_c, r)
        reponer = max(0, int(round(vel * TARGET_COVERAGE_MONTHS - s))) if vel > 0 else 0
        srch_parts = [lk.lower()]
        if lk in line_sales:
            srch_parts += list(line_sales[lk]["colors"]) + list(line_sales[lk]["skus"])
        lines.append({
            "n": lk, "v": v, "s": s, "r": r, "vel": vel, "mos": mos_c, "est": est,
            "cat": categorize(base), "reponer": reponer, "srch": " ".join(srch_parts),
        })

    lines.sort(key=lambda x: (-x["v"], -x["s"]))

    v_lines = sum(l["v"] for l in lines)
    abc_line = {}
    cum_l = 0
    for l in sorted([x for x in lines if x["v"] > 0], key=lambda x: -x["v"]):
        cum_l += l["v"]
        pct = cum_l / v_lines * 100 if v_lines else 100
        abc_line[l["n"]] = "A" if pct <= 80 else ("B" if pct <= 95 else "C")
    for l in lines:
        l["abc"] = abc_line.get(l["n"], "—" if l["v"] == 0 else "C")

    urgent_replenish = sorted(
        [
            l for l in lines
            if l["abc"] in ("A", "B") and l["v"] > 0 and l["vel"] > 0
            and l["mos"] < URGENT_COVERAGE_MAX and l["reponer"] > 0
        ],
        key=lambda x: (-x["reponer"], x["mos"]),
    )

    v_total = sum(p["v"] for p in products)
    s_total = sum(p["s"] for p in products)
    m_count = len([p for p in products if p["v"] > 0 or p["s"] > 0])

    top = sorted(products, key=lambda p: -p["v"])[:15]
    rest_v = v_total - sum(p["v"] for p in top)
    tL = [p["n"] for p in top] + (["Resto"] if rest_v > 0 else [])
    tV = [p["v"] for p in top] + ([rest_v] if rest_v > 0 else [])

    cat_sales, cat_stock = defaultdict(int), defaultdict(int)
    for p in products:
        cat_sales[p["cat"]] += p["v"]
        cat_stock[p["cat"]] += p["s"]

    gen_sales = defaultdict(int)
    for _, row in sales.iterrows():
        gen_sales[norm_str(row.get("GENERO")) or "Sin género"] += int(row["qty"])

    avg_monthly = v_total / n_months
    mom = None
    if len(mon_totals) >= 2 and mon_totals[0]:
        mom = round((mon_totals[-1] - mon_totals[0]) / mon_totals[0] * 100, 1)

    sell_through = round(v_total / (v_total + s_total) * 100, 1) if (v_total + s_total) else 0
    dead_stock = sum(p["s"] for p in products if p["v"] == 0 and p["s"] > 0)
    dead_models = len([p for p in products if p["v"] == 0 and p["s"] > 0])
    high_rot = len([p for p in products if p["r"] >= 60])

    abc = {"A": [], "B": [], "C": []}
    cum = 0
    for p in sorted([x for x in products if x["v"] > 0], key=lambda x: -x["v"]):
        cum += p["v"]
        pct = cum / v_total * 100 if v_total else 100
        letter = "A" if pct <= 80 else ("B" if pct <= 95 else "C")
        abc[letter].append(p["n"])
        p["abc"] = letter
    for p in products:
        if "abc" not in p:
            p["abc"] = "—" if p["v"] == 0 else "C"

    coverage_issues = sorted(
        [
            {"n": p["n"], "months": p["mos"], "s": p["s"], "v": p["v"]}
            for p in products if p["v"] > 0 and p["s"] > 0 and p["vel"] > 0 and p["mos"] > 4
        ],
        key=lambda x: -x["months"],
    )[:15]

    reorder = sorted([p for p in products if p["s"] <= 2 and p["v"] >= 8], key=lambda p: -p["v"])
    fast_movers = sorted([p for p in products if p["vel"] >= 15], key=lambda p: -p["vel"])[:10]
    zero_sales_high_stock = sorted(
        [p for p in products if p["v"] == 0 and p["s"] >= 5], key=lambda p: -p["s"]
    )[:12]

    periodo = (
        f"{MES_FULL.get(months_sorted[0], months_sorted[0])} — {MES_FULL.get(months_sorted[-1], months_sorted[-1])}"
        if months_sorted else "Sin período"
    )

    mom_label = ""
    if mom is not None and len(mes_labels) >= 2:
        mom_label = f" {mes_labels[0]}→{mes_labels[-1]}: {mom:+.1f}% en unidades."

    insights = [
        f"Período analizado: {periodo}. Ventas {v_total:,} und vs stock actual {s_total:,} und (sell-through acumulado {sell_through}%).",
        f"Ritmo: {round(avg_monthly):,} und/mes promedio.{mom_label}",
        f"Reposición urgente: {len(urgent_replenish)} líneas A/B con cobertura <{URGENT_COVERAGE_MAX} meses (+{sum(l['reponer'] for l in urgent_replenish):,} und sugeridas a {TARGET_COVERAGE_MONTHS} meses).",
        f"{dead_models} SKUs sin ventas en el período acumulan {dead_stock:,} unidades — revisar exhibición o traslado.",
    ]
    if excl:
        insights.insert(1, f"Excluidos del análisis: {', '.join(sorted(excl))}.")

    theme = cfg.theme
    return {
        "store": cfg.store_name,
        "periodo": periodo,
        "n_meses": n_months,
        "V": v_total,
        "S": s_total,
        "M": m_count,
        "mes": mes_labels,
        "mon": mon_totals,
        "tL": tL,
        "tV": tV,
        "P": products,
        "L": lines,
        "cats": sorted({p["cat"] for p in products} | {l["cat"] for l in lines}),
        "urgent_replenish": [
            {"n": l["n"], "cat": l["cat"], "abc": l["abc"], "v": l["v"], "s": l["s"], "mos": l["mos"], "reponer": l["reponer"]}
            for l in urgent_replenish
        ],
        "urgent_total_units": sum(l["reponer"] for l in urgent_replenish),
        "target_mos": TARGET_COVERAGE_MONTHS,
        "cat_sales": dict(cat_sales),
        "cat_stock": dict(cat_stock),
        "gen_sales": dict(gen_sales),
        "insights": insights,
        "kpis_extra": {
            "sell_through": sell_through,
            "mom": mom,
            "dead_stock": dead_stock,
            "dead_models": dead_models,
            "avg_monthly": round(avg_monthly),
            "high_rot": high_rot,
        },
        "abc_counts": {k: len(v) for k, v in abc.items()},
        "abc_top_a": abc["A"][:10],
        "coverage_issues": coverage_issues,
        "zero_sales_high_stock": [{"n": p["n"], "s": p["s"]} for p in zero_sales_high_stock],
        "reorder": [{"n": p["n"], "v": p["v"], "s": p["s"], "vel": p["vel"]} for p in reorder[:12]],
        "fast_movers": [{"n": p["n"], "vel": p["vel"], "v": p["v"]} for p in fast_movers],
        "palette": theme.palette if theme else ["#a855f7"],
        "chart_accent": theme.chart_accent if theme else "rgba(168,85,247,.9)",
        "chart_accent_dim": theme.chart_accent_dim if theme else "rgba(168,85,247,.35)",
    }


def render_html(cfg: StoreConfig, payload: dict) -> str:
    theme = cfg.theme
    if theme is None:
        raise ValueError("StoreConfig.theme is required")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    title = cfg.page_title or f"{cfg.store_badge} · Dashboard Tienda"
    generated = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    html = template
    html = html.replace("__PAGE_TITLE__", title)
    html = html.replace("__STORE_BADGE__", cfg.store_badge)
    html = html.replace("__META_SUFFIX__", cfg.meta_suffix)
    html = html.replace("__FOOTER_SOURCES__", cfg.footer_sources)
    html = html.replace("__THEME_CSS__", theme.css_root)
    html = html.replace("__HDR_BG__", theme.hdr_bg)
    html = html.replace("__BADGE_GRAD__", theme.badge_grad)
    html = html.replace("__BADGE_TEXT__", theme.badge_text)
    html = html.replace("__INSIGHT_BG__", theme.insight_bg)
    html = html.replace("__INSIGHT_BORDER__", theme.insight_border)
    html = html.replace("__CHIP_ON_TEXT__", theme.chip_on_text)
    html = html.replace("__REP_BORDER__", theme.rep_border)
    html = html.replace("__REP_BG__", theme.rep_bg)
    html = html.replace("__FONTS_URL__", theme.fonts_url)
    html = html.replace("__DATA_JSON__", json.dumps(payload, ensure_ascii=False))
    html = html.replace("__GENERATED__", generated)
    return html


def build_dashboard(cfg: StoreConfig) -> Path:
    payload = build_payload(cfg)
    html = render_html(cfg, payload)
    cfg.out_html.write_text(html, encoding="utf-8")
    return cfg.out_html
