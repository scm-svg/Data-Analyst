#!/usr/bin/env python3
"""Build VELA store analytics dashboard from stock + sales Excel files."""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STOCK_PATH = ROOT / "data" / "VELA_STOCK_COMPLETO.xlsx"
SALES_PATH = ROOT / "data" / "Reporte_ventas_VELA_COMPLETO.xlsx"
OUT_HTML = ROOT / "VELA.html"
OUT_JSON = ROOT / "vela_data.json"

GENDER_RE = re.compile(r"\s+(CAB|DAMA|KIDS|UNISEX)$", re.I)
SKU_PREFIX_RE = re.compile(r"^\[.*?\]\s*")
MONTH_LABELS = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}


def clean_text(v) -> str:
    if pd.isna(v):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def base_model(name: str) -> str:
    n = clean_text(name)
    n = SKU_PREFIX_RE.sub("", n)
    n = GENDER_RE.sub("", n).strip()
    return n.upper() if n else "SIN MODELO"


def parse_month(v):
    s = clean_text(v)
    if not s:
        return None
    for fmt in ("%m/%Y", "%Y-%m", "%m-%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def month_key(dt: datetime) -> str:
    return f"{dt.year}-{dt.month:02d}"


def month_label(dt: datetime) -> str:
    return f"{MONTH_LABELS[dt.month]} {dt.year}"


def rot_pct(sold: float, stock: float) -> int:
    total = sold + stock
    if total <= 0:
        return 0
    return int(round(100.0 * sold / total))


def safe_int(v) -> int:
    try:
        if pd.isna(v):
            return 0
        return int(round(float(v)))
    except Exception:
        return 0


def load_frames():
    stock = pd.read_excel(STOCK_PATH)
    sales = pd.read_excel(SALES_PATH)

    stock = stock.rename(columns={
        "MODELO": "modelo_raw",
        "GENERO": "genero",
        "COLOR": "color",
        "TALLA": "talla",
        "Cantidad en inventario": "stock",
        "SKU": "sku",
        "Producto": "producto",
    })
    sales = sales.rename(columns={
        "modelo": "modelo_raw",
        "GENERO": "genero",
        "COLOR": "color",
        "TALLA": "talla",
        "Cant. ordenada": "qty",
        "SKU": "sku",
        "fecha (mes año)": "fecha",
        "Variante del producto": "variante",
    })

    for df in (stock, sales):
        df["modelo"] = df["modelo_raw"].map(base_model)
        df["genero"] = df["genero"].map(lambda x: clean_text(x).upper() or "—")
        df["color"] = df["color"].map(lambda x: clean_text(x) or "Sin color")
        df["talla"] = df["talla"].map(lambda x: clean_text(x) or "U")
        df["sku"] = df["sku"].map(clean_text)

    stock["stock"] = stock["stock"].map(safe_int)
    sales["qty"] = sales["qty"].map(safe_int)
    sales["dt"] = sales["fecha"].map(parse_month)
    sales = sales[sales["dt"].notna()].copy()
    sales["mk"] = sales["dt"].map(month_key)
    sales["ml"] = sales["dt"].map(month_label)

    # Drop packaging noise from core merch KPIs but keep available
    stock["is_pack"] = stock["modelo"].str.contains(r"BOLSAS?\s+KRAFT", regex=True)
    sales["is_pack"] = sales["modelo"].str.contains(r"BOLSAS?\s+KRAFT", regex=True)

    return stock, sales


def build_payload(stock: pd.DataFrame, sales: pd.DataFrame) -> dict:
    months = sorted(sales["dt"].unique())
    month_meta = [{"k": month_key(m), "l": month_label(m), "y": m.year, "m": m.month} for m in months]
    month_keys = [m["k"] for m in month_meta]

    # Aggregate sales by model x month and variants
    sales_model_month = defaultdict(lambda: defaultdict(int))
    sales_model_total = defaultdict(int)
    sales_returns = defaultdict(int)
    sales_gross = defaultdict(int)

    # variant key: genero|color|talla
    var_sales = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # model -> var -> month -> qty
    var_sales_tot = defaultdict(lambda: defaultdict(int))
    var_meta = {}  # model -> varKey -> meta

    for _, r in sales.iterrows():
        model = r["modelo"]
        mk = r["mk"]
        q = int(r["qty"])
        sales_model_month[model][mk] += q
        sales_model_total[model] += q
        if q < 0:
            sales_returns[model] += abs(q)
        else:
            sales_gross[model] += q
        vk = f"{r['genero']}|{r['color']}|{r['talla']}"
        var_sales[model][vk][mk] += q
        var_sales_tot[model][vk] += q
        var_meta.setdefault(model, {})[vk] = {
            "g": r["genero"], "c": r["color"], "t": r["talla"], "sku": r["sku"]
        }

    # Stock by model and variants
    stock_model = defaultdict(int)
    var_stock = defaultdict(lambda: defaultdict(int))
    stock_skus = defaultdict(set)
    is_pack_model = {}

    for _, r in stock.iterrows():
        model = r["modelo"]
        q = int(r["stock"])
        stock_model[model] += q
        vk = f"{r['genero']}|{r['color']}|{r['talla']}"
        var_stock[model][vk] += q
        stock_skus[model].add(r["sku"])
        is_pack_model[model] = bool(r["is_pack"])
        var_meta.setdefault(model, {}).setdefault(vk, {
            "g": r["genero"], "c": r["color"], "t": r["talla"], "sku": r["sku"]
        })

    all_models = sorted(set(stock_model) | set(sales_model_total))

    products = []
    for model in all_models:
        sold = int(sales_model_total.get(model, 0))
        stk = int(stock_model.get(model, 0))
        monthly = [int(sales_model_month[model].get(mk, 0)) for mk in month_keys]
        # weeks estimated: month / 4.3
        weekly = [round(v / 4.3, 1) for v in monthly]
        r = rot_pct(max(sold, 0), stk)
        # cover weeks based on avg weekly sales of available months
        avg_week = (sum(max(x, 0) for x in monthly) / max(len(monthly), 1)) / 4.3
        cover = round(stk / avg_week, 1) if avg_week > 0 else (999 if stk > 0 else 0)

        # MoM
        mom = None
        if len(monthly) >= 2 and monthly[-2] != 0:
            mom = round(100.0 * (monthly[-1] - monthly[-2]) / abs(monthly[-2]), 1)
        elif len(monthly) >= 2:
            mom = 100.0 if monthly[-1] > 0 else 0.0

        # Variants
        vkeys = set(var_stock[model]) | set(var_sales[model])
        vars_out = []
        for vk in vkeys:
            meta = var_meta[model][vk]
            vs = int(var_sales_tot[model].get(vk, 0))
            vst = int(var_stock[model].get(vk, 0))
            vm = [int(var_sales[model][vk].get(mk, 0)) for mk in month_keys]
            vars_out.append({
                "g": meta["g"],
                "c": meta["c"],
                "t": meta["t"],
                "v": vs,
                "s": vst,
                "r": rot_pct(max(vs, 0), vst),
                "m": vm,
                "sku": meta.get("sku", ""),
            })
        vars_out.sort(key=lambda x: (-x["v"], -x["s"], x["c"], x["t"]))

        # Color rollup for quick view
        color_map = defaultdict(lambda: {"v": 0, "s": 0, "tallas": defaultdict(int), "generos": set()})
        for vv in vars_out:
            cm = color_map[vv["c"]]
            cm["v"] += vv["v"]
            cm["s"] += vv["s"]
            if vv["t"] and vv["t"] != "U":
                cm["tallas"][vv["t"]] += vv["v"]
            if vv["g"] and vv["g"] != "—":
                cm["generos"].add(vv["g"])

        colors = []
        for c, cm in color_map.items():
            tallas = [{"t": t, "v": v} for t, v in sorted(cm["tallas"].items(), key=lambda x: -x[1])]
            colors.append({
                "c": c,
                "v": cm["v"],
                "s": cm["s"],
                "r": rot_pct(max(cm["v"], 0), cm["s"]),
                "g": sorted(cm["generos"]),
                "tallas": tallas,
            })
        colors.sort(key=lambda x: (-x["v"], -x["s"], x["c"]))

        products.append({
            "n": model,
            "v": sold,
            "s": stk,
            "r": r,
            "m": monthly,
            "w": weekly,
            "mom": mom,
            "cover": cover if cover < 999 else None,
            "ret": int(sales_returns.get(model, 0)),
            "gross": int(sales_gross.get(model, 0)),
            "skus": len(stock_skus.get(model, set()) | {v.get("sku") for v in vars_out if v.get("sku")}),
            "pack": bool(is_pack_model.get(model, False)),
            "vars": vars_out,
            "colors": colors,
        })

    products.sort(key=lambda p: (-p["v"], -p["s"], p["n"]))

    # Store-level monthly + weekly estimate
    mon = []
    for mk in month_keys:
        mon.append(int(sum(sales_model_month[m].get(mk, 0) for m in all_models)))
    weekly_store = [round(v / 4.3, 1) for v in mon]

    # Top models for doughnut
    top = products[:12]
    rest_v = sum(p["v"] for p in products[12:])
    tL = [p["n"] for p in top] + (["Resto"] if rest_v else [])
    tV = [p["v"] for p in top] + ([rest_v] if rest_v else [])

    # Pareto
    total_v = sum(max(p["v"], 0) for p in products) or 1
    cum = 0
    pareto80 = 0
    for p in products:
        if p["v"] <= 0:
            continue
        cum += p["v"]
        pareto80 += 1
        if cum / total_v >= 0.8:
            break

    # Insights
    merch = [p for p in products if not p["pack"]]
    sold_units = sum(p["v"] for p in merch)
    stock_units = sum(p["s"] for p in merch)
    active = sum(1 for p in merch if p["v"] > 0)
    dead = [p for p in merch if p["v"] <= 0 and p["s"] > 0]
    stockout = [p for p in merch if p["s"] == 0 and p["v"] > 0]
    high_rot = [p for p in merch if p["r"] >= 60]
    low_rot = [p for p in merch if 0 < p["r"] < 30 and p["s"] > 0]

    returns_total = sum(p["ret"] for p in merch)
    gross_total = sum(p["gross"] for p in merch)

    payload = {
        "store": "VELA",
        "subtitle": "Análisis de tienda · ventas + inventario",
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "period": {
            "from": month_meta[0]["l"] if month_meta else "",
            "to": month_meta[-1]["l"] if month_meta else "",
            "months": month_meta,
            "note": "Las ventas vienen a nivel mes; el ritmo semanal se estima como mes÷4.3",
        },
        "kpi": {
            "V": sold_units,
            "S": stock_units,
            "M": len(merch),
            "A": active,
            "avgM": round(sold_units / max(len(month_keys), 1), 1),
            "avgW": round((sold_units / max(len(month_keys), 1)) / 4.3, 1),
            "rot": rot_pct(max(sold_units, 0), stock_units),
            "ret": returns_total,
            "retRate": round(100.0 * returns_total / gross_total, 1) if gross_total else 0,
            "pareto": pareto80,
            "dead": len(dead),
            "stockout": len(stockout),
            "high": len(high_rot),
            "low": len(low_rot),
        },
        "mon": mon,
        "weekEst": weekly_store,
        "tL": tL,
        "tV": tV,
        "P": products,
    }
    return payload


def html_template(data_json: str) -> str:
    # Large self-contained dashboard
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VELA · Dashboard de Tienda</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{{
  --bg:#071018; --su:#0c1822; --s2:#122433; --s3:#183044; --bd:#234056;
  --ac:#14b8a6; --a2:#2dd4bf; --a3:#5eead4;
  --gr:#34d399; --re:#fb7185; --am:#fbbf24; --bl:#38bdf8;
  --mu:#7f9bb0; --m2:#4d6b80; --tx:#e7f2f7; --tx2:#c5d9e4;
  --fh:'Syne',sans-serif; --fb:'Outfit',sans-serif; --fm:'IBM Plex Mono',monospace;
  --r:14px; --glow:rgba(20,184,166,.18);
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font-family:var(--fb);min-height:100vh;
  background-image:
    radial-gradient(1200px 500px at 10% -10%, rgba(20,184,166,.14), transparent 55%),
    radial-gradient(900px 420px at 90% 0%, rgba(56,189,248,.10), transparent 50%),
    linear-gradient(180deg,#061018 0%,#071820 40%,#061018 100%);
}}
::-webkit-scrollbar{{width:5px;height:5px}}
::-webkit-scrollbar-track{{background:var(--s2)}}
::-webkit-scrollbar-thumb{{background:var(--bd);border-radius:4px}}

.hdr{{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;
  padding:22px 28px 18px;border-bottom:1px solid var(--bd);
  background:linear-gradient(180deg,rgba(12,24,34,.92),rgba(7,16,24,.75));
  backdrop-filter:blur(10px);position:sticky;top:0;z-index:50}}
.brand{{display:flex;align-items:center;gap:14px}}
.logo{{width:48px;height:48px;border-radius:14px;display:grid;place-items:center;
  background:linear-gradient(145deg,#0f766e,#14b8a6 55%,#38bdf8);box-shadow:0 0 0 1px rgba(255,255,255,.08),0 10px 30px var(--glow);
  font-family:var(--fh);font-weight:800;font-size:1.05rem;letter-spacing:.04em;color:#042f2e}}
.brand h1{{font-family:var(--fh);font-size:1.7rem;font-weight:800;letter-spacing:-.03em;line-height:1}}
.brand h1 span{{color:var(--a2)}}
.brand p{{color:var(--mu);font-size:.78rem;margin-top:4px}}
.hdr-meta{{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}}
.pill{{padding:6px 11px;border-radius:999px;border:1px solid var(--bd);background:rgba(18,36,51,.8);
  font-size:.68rem;color:var(--tx2);font-family:var(--fm)}}
.pill em{{color:var(--a2);font-style:normal}}

.fwrap{{padding:14px 28px;border-bottom:1px solid var(--bd);background:rgba(12,24,34,.55)}}
.fbar{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.fg{{display:flex;align-items:center;gap:7px;flex-wrap:wrap}}
.fl{{font-size:.62rem;text-transform:uppercase;letter-spacing:.08em;color:var(--mu);font-weight:700}}
.sep{{width:1px;height:22px;background:var(--bd)}}
.chip{{padding:5px 11px;border-radius:999px;border:1px solid var(--bd);background:var(--s2);
  color:var(--mu);font-size:.72rem;font-weight:600;cursor:pointer;transition:.15s;font-family:var(--fb)}}
.chip:hover{{border-color:var(--ac);color:var(--a2)}}
.chip.on{{background:linear-gradient(135deg,#0f766e,#14b8a6);border-color:transparent;color:#042f2e}}
.srch,.sel{{padding:7px 11px;border-radius:10px;border:1px solid var(--bd);background:var(--s2);
  color:var(--tx);font-size:.8rem;font-family:var(--fb);outline:none;min-width:160px}}
.srch:focus,.sel:focus{{border-color:var(--ac);box-shadow:0 0 0 3px var(--glow)}}
.msel{{position:relative;min-width:220px}}
.msel-btn{{width:100%;text-align:left;padding:7px 11px;border-radius:10px;border:1px solid var(--bd);
  background:var(--s2);color:var(--tx);font-size:.8rem;cursor:pointer;font-family:var(--fb)}}
.msel-panel{{display:none;position:absolute;top:calc(100% + 6px);left:0;width:min(340px,90vw);
  max-height:280px;overflow:auto;background:var(--su);border:1px solid var(--bd);border-radius:12px;
  padding:8px;z-index:80;box-shadow:0 18px 40px rgba(0,0,0,.35)}}
.msel.open .msel-panel{{display:block}}
.msel-item{{display:flex;gap:8px;align-items:center;padding:6px 8px;border-radius:8px;cursor:pointer;font-size:.76rem}}
.msel-item:hover{{background:var(--s2)}}
.msel-item input{{accent-color:var(--ac)}}
.fnote{{margin-top:8px;font-size:.68rem;color:var(--m2);font-family:var(--fm)}}

.krow{{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:10px;padding:16px 28px}}
@media(max-width:1100px){{.krow{{grid-template-columns:repeat(3,1fr)}}}}
@media(max-width:680px){{.krow{{grid-template-columns:repeat(2,1fr)}}}}
.kpi{{background:linear-gradient(180deg,rgba(18,36,51,.95),rgba(12,24,34,.9));border:1px solid var(--bd);
  border-radius:14px;padding:13px 14px;position:relative;overflow:hidden}}
.kpi::after{{content:'';position:absolute;inset:auto -20% -40% 40%;height:80px;background:radial-gradient(circle,var(--glow),transparent 70%)}}
.kv{{font-family:var(--fm);font-size:1.45rem;font-weight:600;line-height:1;position:relative}}
.kl{{font-size:.62rem;color:var(--mu);text-transform:uppercase;letter-spacing:.07em;margin-top:5px;position:relative}}
.ks{{font-size:.66rem;color:var(--m2);margin-top:3px;font-family:var(--fm);position:relative}}
.c-ac .kv{{color:var(--a2)}}.c-gr .kv{{color:var(--gr)}}.c-am .kv{{color:var(--am)}}.c-re .kv{{color:var(--re)}}.c-bl .kv{{color:var(--bl)}}

.tabs{{display:flex;gap:2px;padding:0 28px;border-bottom:1px solid var(--bd);overflow-x:auto;background:rgba(7,16,24,.4)}}
.tab{{padding:11px 16px;border:none;background:none;color:var(--mu);font-family:var(--fh);font-size:.78rem;
  font-weight:700;cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap}}
.tab.on{{color:var(--a2);border-bottom-color:var(--ac)}}
.tab:hover:not(.on){{color:var(--tx)}}

.page{{padding:18px 28px 40px;max-width:1500px;margin:0 auto}}
.sec{{display:none;animation:fade .25s ease}}.sec.on{{display:block}}
@keyframes fade{{from{{opacity:0;transform:translateY(4px)}}to{{opacity:1;transform:none}}}}
.g2{{display:grid;grid-template-columns:1.3fr .9fr;gap:13px}}
.g3{{display:grid;grid-template-columns:repeat(3,1fr);gap:13px}}
.g21{{display:grid;grid-template-columns:1fr 1fr;gap:13px}}
@media(max-width:980px){{.g2,.g3,.g21{{grid-template-columns:1fr}}}}
.card{{background:rgba(12,24,34,.88);border:1px solid var(--bd);border-radius:16px;padding:16px 17px}}
.ct{{font-size:.66rem;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px}}
.ct em{{color:var(--a2);font-style:normal}}
.sub{{font-size:.74rem;color:var(--m2);margin-bottom:12px}}
.cw{{position:relative;height:230px}}.cw.h180{{height:180px}}

.insight{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:13px}}
@media(max-width:980px){{.insight{{grid-template-columns:1fr 1fr}}}}
.ibox{{background:var(--s2);border:1px solid var(--bd);border-radius:12px;padding:12px 13px;border-left:3px solid var(--ac)}}
.ibox h4{{font-size:.78rem;font-weight:700;margin-bottom:3px}}
.ibox p{{font-size:.7rem;color:var(--mu);line-height:1.35}}

.xi{{border:1px solid transparent;border-radius:11px;overflow:hidden;margin-bottom:4px;transition:.12s}}
.xi:hover:not(.open){{border-color:rgba(20,184,166,.25)}}
.xi.open{{border-color:var(--bd);background:rgba(18,36,51,.35)}}
.xh{{display:flex;align-items:center;gap:8px;padding:9px 11px;background:var(--s2);cursor:pointer}}
.xi.open .xh{{background:var(--s3)}}
.xb{{display:none;padding:12px 13px;border-top:1px solid var(--bd);background:rgba(7,16,24,.55)}}
.xi.open .xb{{display:block}}
.xa{{font-size:.6rem;color:var(--m2);margin-left:auto;transition:transform .15s}}
.xi.open .xa{{transform:rotate(180deg)}}
.rk{{font-family:var(--fm);font-size:.6rem;color:var(--m2);width:22px;text-align:right}}
.nm{{flex:1;font-size:.8rem;font-weight:700;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.trk{{display:flex;height:6px;border-radius:4px;overflow:hidden;gap:1px;width:90px;flex-shrink:0;background:rgba(255,255,255,.04)}}
.trk i{{display:block;height:100%;border-radius:3px}}
.badge{{font-family:var(--fm);font-size:.62rem;font-weight:600;padding:2px 7px;border-radius:6px;flex-shrink:0}}
.bH{{background:rgba(52,211,153,.14);color:var(--gr)}}.bM{{background:rgba(251,191,36,.12);color:var(--am)}}
.bL{{background:rgba(251,113,133,.12);color:var(--re)}}.bZ{{background:rgba(127,155,176,.12);color:var(--mu)}}
.num{{font-family:var(--fm);font-size:.72rem;font-weight:600;flex-shrink:0}}
.muted{{color:var(--mu);font-size:.64rem}}

.vgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:8px}}
.vcard{{background:var(--s2);border:1px solid var(--bd);border-radius:10px;padding:9px 10px}}
.vcard .t{{font-size:.74rem;font-weight:700;margin-bottom:3px}}
.vcard .m{{font-size:.62rem;color:var(--mu);font-family:var(--fm)}}
.gbar{{height:4px;background:var(--bd);border-radius:3px;margin-top:6px;overflow:hidden}}
.gbar>i{{display:block;height:100%;background:var(--a2)}}
.tchips{{display:flex;flex-wrap:wrap;gap:4px;margin-top:7px}}
.tchips span{{background:var(--s3);border-radius:5px;padding:2px 6px;font-size:.6rem;font-family:var(--fm)}}
.tchips b{{color:var(--a2)}}

.rseg{{margin-bottom:8px}}
.rseg-h{{display:flex;align-items:center;gap:10px;padding:11px 13px;border-radius:12px;cursor:pointer;
  border:1px solid transparent;user-select:none}}
.rseg-b{{display:none;flex-direction:column;gap:3px;padding:6px 0 4px 8px}}
.rseg.open .rseg-b{{display:flex}}

.tblwrap{{overflow:auto;max-height:calc(100vh - 320px);border-radius:12px}}
table.dt{{width:100%;border-collapse:collapse;font-size:.78rem}}
table.dt th{{position:sticky;top:0;background:var(--su);z-index:2;text-align:left;padding:9px 10px;
  font-size:.62rem;text-transform:uppercase;letter-spacing:.06em;color:var(--mu);border-bottom:1px solid var(--bd)}}
table.dt td{{padding:8px 10px;border-bottom:1px solid rgba(35,64,86,.55)}}
table.dt tr:hover td{{background:rgba(18,36,51,.65)}}
table.dt .n{{text-align:right;font-family:var(--fm)}}
.tr-exp{{cursor:pointer}}
.tr-var td{{background:rgba(7,16,24,.65);font-size:.72rem;color:var(--tx2)}}

.dg{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
@media(max-width:900px){{.dg{{grid-template-columns:1fr}}}}
.dbox{{background:var(--s2);border-radius:14px;padding:14px;border-left:3px solid}}
.dbox h4{{font-size:.8rem;font-weight:800;margin-bottom:2px}}
.dbox p{{font-size:.68rem;color:var(--mu);margin-bottom:9px}}
.di{{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:6px 8px;
  border-radius:8px;background:rgba(7,16,24,.55);margin-bottom:4px;font-size:.74rem}}
.di strong{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.di small{{font-family:var(--fm);color:var(--mu);flex-shrink:0}}

.empty{{padding:28px;text-align:center;color:var(--mu);font-size:.85rem}}
.foot{{padding:8px 28px 24px;color:var(--m2);font-size:.68rem;font-family:var(--fm)}}
</style>
</head>
<body>
<header class="hdr">
  <div class="brand">
    <div class="logo">VELA</div>
    <div>
      <h1><span>VELA</span> Dashboard</h1>
      <p id="hdrSub">Análisis de tienda</p>
    </div>
  </div>
  <div class="hdr-meta">
    <div class="pill" id="pillPeriod"></div>
    <div class="pill">Fuente: ventas + stock · <em>sin categorías</em></div>
  </div>
</header>

<div class="fwrap">
  <div class="fbar">
    <div class="fg">
      <span class="fl">Tiempo</span>
      <button class="chip on" data-grain="all" onclick="setGrain(this)">Todo</button>
      <button class="chip" data-grain="month" onclick="setGrain(this)">Mes</button>
      <button class="chip" data-grain="week" onclick="setGrain(this)">Semana est.</button>
    </div>
    <div class="sep"></div>
    <div class="fg" id="monthChips"></div>
    <div class="sep"></div>
    <div class="fg">
      <span class="fl">Modelos</span>
      <div class="msel" id="modelSel">
        <button class="msel-btn" type="button" onclick="toggleModelSel(event)">Todos los modelos ▾</button>
        <div class="msel-panel" id="modelPanel"></div>
      </div>
      <input class="srch" id="modelSearch" placeholder="Buscar modelo..." oninput="filterModelPanel()">
    </div>
    <div class="sep"></div>
    <div class="fg">
      <span class="fl">Estado</span>
      <button class="chip on" data-rot="" onclick="setRot(this)">Todos</button>
      <button class="chip" data-rot="h" onclick="setRot(this)">Alta</button>
      <button class="chip" data-rot="m" onclick="setRot(this)">Media</button>
      <button class="chip" data-rot="l" onclick="setRot(this)">Baja</button>
      <button class="chip" data-rot="z" onclick="setRot(this)">Sin ventas</button>
    </div>
    <button class="chip" onclick="resetFilters()" style="margin-left:auto">Reset</button>
  </div>
  <div class="fnote" id="filterNote"></div>
</div>

<div class="krow" id="krow"></div>

<div class="tabs">
  <button class="tab on" onclick="goto('resumen',this)">Resumen</button>
  <button class="tab" onclick="goto('productos',this)">Productos</button>
  <button class="tab" onclick="goto('rotacion',this)">Rotación</button>
  <button class="tab" onclick="goto('inventario',this)">Inventario</button>
  <button class="tab" onclick="goto('decisiones',this)">Decisiones</button>
  <button class="tab" onclick="goto('insights',this)">Insights</button>
</div>

<div class="page">
  <section class="sec on" id="sec-resumen">
    <div class="insight" id="insightRow"></div>
    <div class="g2" style="margin-bottom:13px">
      <div class="card">
        <div class="ct">Tendencia de ventas <em id="trendLabel">· unidades</em></div>
        <div class="sub" id="trendSub">Comparativo del período filtrado</div>
        <div class="cw"><canvas id="cTrend"></canvas></div>
      </div>
      <div class="card">
        <div class="ct">Concentración <em>· top modelos</em></div>
        <div class="sub">Participación de ventas netas</div>
        <div class="cw"><canvas id="cShare"></canvas></div>
      </div>
    </div>
    <div class="g21">
      <div class="card">
        <div class="ct">Matriz de rotación <em>· expandir segmentos</em></div>
        <div class="sub">Azul/verde = vendido · gris = stock remanente</div>
        <div id="rotMatrix"></div>
      </div>
      <div class="card">
        <div class="ct">Top movimiento <em>· click para variantes</em></div>
        <div class="sub">Modelos con mayor tracción en el filtro actual</div>
        <div id="topList"></div>
      </div>
    </div>
  </section>

  <section class="sec" id="sec-productos">
    <div class="card" style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:center">
        <div>
          <div class="ct">Catálogo analítico <em>· expandir modelo → variantes</em></div>
          <div class="sub" id="pCnt" style="margin:0">—</div>
        </div>
        <div class="fg">
          <span class="fl">Orden</span>
          <button class="chip on" data-psort="v" onclick="setPSort(this)">Ventas</button>
          <button class="chip" data-psort="r" onclick="setPSort(this)">Rotación</button>
          <button class="chip" data-psort="s" onclick="setPSort(this)">Stock</button>
          <button class="chip" data-psort="mom" onclick="setPSort(this)">MoM</button>
        </div>
      </div>
    </div>
    <div id="pList"></div>
  </section>

  <section class="sec" id="sec-rotacion">
    <div class="g3" style="margin-bottom:12px" id="rotKpis"></div>
    <div class="card">
      <div class="ct">Detalle por banda de rotación</div>
      <div class="sub">Expandí cada modelo para ver género · color · talla</div>
      <div id="rotList"></div>
    </div>
  </section>

  <section class="sec" id="sec-inventario">
    <div class="card" style="padding:0;overflow:hidden">
      <div style="padding:14px 16px;border-bottom:1px solid var(--bd);display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        <div class="ct" style="margin:0">Stock vs demanda</div>
        <span class="muted" id="iCnt"></span>
        <input class="srch" id="iSrch" placeholder="Filtrar en tabla..." oninput="renderInventario()" style="margin-left:auto">
      </div>
      <div class="tblwrap">
        <table class="dt">
          <thead>
            <tr>
              <th></th><th>Modelo</th><th class="n">Vendido</th><th class="n">Stock</th>
              <th class="n">Rotación</th><th class="n">Cover sem.</th><th class="n">MoM</th><th>Estado</th>
            </tr>
          </thead>
          <tbody id="iBody"></tbody>
        </table>
      </div>
    </div>
  </section>

  <section class="sec" id="sec-decisiones">
    <div class="dg" id="decisions"></div>
  </section>

  <section class="sec" id="sec-insights">
    <div class="g21" style="margin-bottom:13px">
      <div class="card">
        <div class="ct">Pareto 80/20</div>
        <div class="sub">Cuántos modelos concentran el 80% de las ventas</div>
        <div class="cw h180"><canvas id="cPareto"></canvas></div>
      </div>
      <div class="card">
        <div class="ct">Salud del surtido</div>
        <div class="sub">Distribución por banda de rotación</div>
        <div class="cw h180"><canvas id="cHealth"></canvas></div>
      </div>
    </div>
    <div class="card">
      <div class="ct">Hallazgos accionables</div>
      <div class="sub">Se recalculan con los filtros activos</div>
      <div class="insight" id="findings" style="margin:0"></div>
    </div>
  </section>
</div>

<div class="foot" id="foot"></div>

<script>
const RAW = {data_json};

const STATE = {{
  grain: 'all', // all | month | week
  months: new Set(RAW.period.months.map(m => m.k)),
  models: new Set(), // empty = all
  rot: '',
  psort: 'v',
  openInv: new Set(),
}};

let charts = {{ trend:null, share:null, pareto:null, health:null }};

function fmt(n){{
  if(n==null || Number.isNaN(n)) return '—';
  return Number(n).toLocaleString('es-ES');
}}
function rc(r){{ return r>=60?'var(--gr)':r>=30?'var(--am)':r>0?'var(--re)':'var(--mu)'; }}
function rb(r){{
  const c=r>=60?'bH':r>=30?'bM':r>0?'bL':'bZ';
  return `<span class="badge ${{c}}">${{r}}%</span>`;
}}
function rotBand(r){{
  if(r>=60) return 'h';
  if(r>=30) return 'm';
  if(r>0) return 'l';
  return 'z';
}}

function selectedMonths(){{
  const all = RAW.period.months.map(m=>m.k);
  if(STATE.grain==='all') return all;
  return all.filter(k => STATE.months.has(k));
}}

function monthIndex(k){{
  return RAW.period.months.findIndex(m=>m.k===k);
}}

function productPeriodStats(p){{
  const mks = selectedMonths();
  let sold = 0;
  const series = [];
  mks.forEach(k => {{
    const i = monthIndex(k);
    const v = i>=0 ? (p.m[i]||0) : 0;
    sold += v;
    series.push({{k, v, label: RAW.period.months[i]?.l || k}});
  }});
  // week estimate view: convert monthly to weekly rate points
  let weekSeries = series.map(s => ({{...s, v: Math.round((s.v/4.3)*10)/10}}));
  const stock = p.s;
  const rot = (()=>{{
    const tot = Math.max(sold,0)+stock;
    return tot>0 ? Math.round(100*Math.max(sold,0)/tot) : 0;
  }})();
  const avgW = (series.reduce((a,s)=>a+Math.max(s.v,0),0) / Math.max(series.length,1)) / 4.3;
  const cover = avgW>0 ? Math.round((stock/avgW)*10)/10 : (stock>0?null:0);
  let mom = null;
  if(series.length>=2){{
    const a=series[series.length-2].v, b=series[series.length-1].v;
    mom = a!==0 ? Math.round(1000*(b-a)/Math.abs(a))/10 : (b>0?100:0);
  }}
  return {{sold, stock, rot, series, weekSeries, cover, mom, avgW}};
}}

function variantPeriodSold(v){{
  const mks = selectedMonths();
  return mks.reduce((a,k)=>{{
    const i=monthIndex(k);
    return a + (i>=0 ? (v.m[i]||0) : 0);
  }},0);
}}

function filteredProducts(){{
  return RAW.P.filter(p => {{
    if(p.pack) return false; // packaging out of merch analysis
    if(STATE.models.size && !STATE.models.has(p.n)) return false;
    const st = productPeriodStats(p);
    if(STATE.rot){{
      const b = rotBand(st.rot);
      // when filtering by period with 0 sales, treat as z if stock>0 else maybe exclude
      if(STATE.rot==='z') return st.sold<=0 && st.stock>0;
      if(b!==STATE.rot) return false;
      if(STATE.rot!=='z' && st.sold<=0) return false;
    }}
    return true;
  }}).map(p => {{
    const st = productPeriodStats(p);
    return {{...p, _st:st}};
  }});
}}

function toggleModelSel(e){{
  e.stopPropagation();
  document.getElementById('modelSel').classList.toggle('open');
}}
document.addEventListener('click', ()=> document.getElementById('modelSel').classList.remove('open'));

function buildModelPanel(){{
  const panel = document.getElementById('modelPanel');
  const models = RAW.P.filter(p=>!p.pack).map(p=>p.n).sort();
  panel.innerHTML = `<div class="msel-item" onclick="event.stopPropagation()"><label style="display:flex;gap:8px;align-items:center;width:100%;cursor:pointer">
    <input type="checkbox" id="allModels" ${{STATE.models.size===0?'checked':''}} onchange="clearModels(this)"> <strong>Todos</strong></label></div>` +
    models.map(n=>`<div class="msel-item" data-name="${{n}}" onclick="event.stopPropagation()">
      <label style="display:flex;gap:8px;align-items:center;width:100%;cursor:pointer">
        <input type="checkbox" value="${{n}}" ${{STATE.models.has(n)?'checked':''}} onchange="toggleModel(this)"> ${{n}}
      </label></div>`).join('');
  updateModelBtn();
}}

function filterModelPanel(){{
  const q = (document.getElementById('modelSearch').value||'').toLowerCase();
  document.querySelectorAll('#modelPanel .msel-item[data-name]').forEach(el=>{{
    el.style.display = !q || el.dataset.name.toLowerCase().includes(q) ? '' : 'none';
  }});
}}
function clearModels(el){{
  if(el.checked){{ STATE.models.clear(); buildModelPanel(); renderAll(); }}
}}
function toggleModel(el){{
  if(el.checked) STATE.models.add(el.value); else STATE.models.delete(el.value);
  const all = document.getElementById('allModels');
  if(all) all.checked = STATE.models.size===0;
  updateModelBtn();
  renderAll();
}}
function updateModelBtn(){{
  const btn = document.querySelector('#modelSel .msel-btn');
  if(!STATE.models.size) btn.textContent = 'Todos los modelos ▾';
  else if(STATE.models.size===1) btn.textContent = [...STATE.models][0] + ' ▾';
  else btn.textContent = STATE.models.size + ' modelos ▾';
}}

function setGrain(el){{
  document.querySelectorAll('[data-grain]').forEach(c=>c.classList.remove('on'));
  el.classList.add('on');
  STATE.grain = el.dataset.grain;
  if(STATE.grain==='all'){{
    STATE.months = new Set(RAW.period.months.map(m=>m.k));
  }} else if([...STATE.months].length===0){{
    STATE.months = new Set([RAW.period.months.at(-1).k]);
  }}
  syncMonthChips();
  renderAll();
}}
function setMonth(el){{
  const k = el.dataset.month;
  if(STATE.grain==='all'){{
    STATE.grain='month';
    document.querySelectorAll('[data-grain]').forEach(c=>c.classList.toggle('on', c.dataset.grain==='month'));
    STATE.months = new Set([k]);
  }} else {{
    if(STATE.months.has(k) && STATE.months.size>1) STATE.months.delete(k);
    else {{ STATE.months.add(k); }}
  }}
  syncMonthChips();
  renderAll();
}}
function syncMonthChips(){{
  document.querySelectorAll('#monthChips .chip').forEach(c=>{{
    c.classList.toggle('on', STATE.grain!=='all' && STATE.months.has(c.dataset.month));
  }});
}}
function setRot(el){{
  document.querySelectorAll('[data-rot]').forEach(c=>c.classList.remove('on'));
  el.classList.add('on');
  STATE.rot = el.dataset.rot;
  renderAll();
}}
function setPSort(el){{
  document.querySelectorAll('[data-psort]').forEach(c=>c.classList.remove('on'));
  el.classList.add('on');
  STATE.psort = el.dataset.psort;
  renderProductos();
}}
function resetFilters(){{
  STATE.grain='all'; STATE.rot=''; STATE.models.clear();
  STATE.months = new Set(RAW.period.months.map(m=>m.k));
  document.querySelectorAll('[data-grain]').forEach(c=>c.classList.toggle('on', c.dataset.grain==='all'));
  document.querySelectorAll('[data-rot]').forEach(c=>c.classList.toggle('on', c.dataset.rot===''));
  document.getElementById('modelSearch').value='';
  buildModelPanel(); syncMonthChips(); renderAll();
}}

function goto(id, el){{
  document.querySelectorAll('.sec').forEach(s=>s.classList.remove('on'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));
  document.getElementById('sec-'+id).classList.add('on');
  el.classList.add('on');
  if(id==='productos') renderProductos();
  if(id==='rotacion') renderRotacion();
  if(id==='inventario') renderInventario();
  if(id==='decisiones') renderDecisiones();
  if(id==='insights') renderInsights();
}}

function TG(el, ev){{
  if(ev) ev.stopPropagation();
  const was = el.classList.contains('open');
  const parent = el.parentElement;
  parent.querySelectorAll(':scope > .xi.open').forEach(x=>x.classList.remove('open'));
  if(!was) el.classList.add('open');
}}

function buildMonthChips(){{
  const box = document.getElementById('monthChips');
  box.innerHTML = `<span class="fl">Mes</span>` + RAW.period.months.map(m =>
    `<button class="chip" data-month="${{m.k}}" onclick="setMonth(this)">${{m.l}}</button>`
  ).join('');
}}

function filterNote(){{
  const mks = selectedMonths().map(k => RAW.period.months.find(m=>m.k===k)?.l).join(', ');
  const g = STATE.grain==='week' ? 'Vista semanal estimada (mes÷4.3). ' : STATE.grain==='month' ? 'Vista mensual. ' : 'Período completo. ';
  const md = STATE.models.size ? STATE.models.size+' modelos seleccionados. ' : 'Todos los modelos. ';
  document.getElementById('filterNote').textContent = g + 'Meses: ' + mks + '. ' + md + RAW.period.note;
}}

function renderKPIs(list){{
  const sold = list.reduce((a,p)=>a+p._st.sold,0);
  const stock = list.reduce((a,p)=>a+p._st.stock,0);
  const rot = (()=>{{const t=Math.max(sold,0)+stock; return t?Math.round(100*Math.max(sold,0)/t):0;}})();
  const avgW = list.reduce((a,p)=>a+p._st.avgW,0);
  const stockout = list.filter(p=>p._st.stock===0 && p._st.sold>0).length;
  const dead = list.filter(p=>p._st.sold<=0 && p._st.stock>0).length;
  const weeks = selectedMonths().length * 4.3;
  const pace = weeks>0 ? Math.round((sold/weeks)*10)/10 : 0;
  const items = [
    {{v:fmt(sold), l:'Unidades vendidas', s:'neto del filtro', c:'c-ac'}},
    {{v:fmt(stock), l:'Stock en piso', s:list.length+' modelos', c:''}},
    {{v:rot+'%', l:'Sell-through', s:'vendido / (vendido+stock)', c:'c-gr'}},
    {{v:pace, l:'Ritmo / semana', s:'estimado', c:'c-bl'}},
    {{v:stockout, l:'Quiebres', s:'con demanda y stock 0', c:'c-am'}},
    {{v:dead, l:'Sin movimiento', s:'stock sin ventas', c:'c-re'}},
  ];
  document.getElementById('krow').innerHTML = items.map(k=>`
    <div class="kpi ${{k.c}}"><div class="kv">${{k.v}}</div><div class="kl">${{k.l}}</div><div class="ks">${{k.s}}</div></div>
  `).join('');
}}

function renderInsightsRow(list){{
  const sold = list.reduce((a,p)=>a+Math.max(p._st.sold,0),0)||1;
  let cum=0, n80=0;
  [...list].sort((a,b)=>b._st.sold-a._st.sold).forEach(p=>{{
    if(cum/sold>=0.8 || p._st.sold<=0) return;
    cum+=p._st.sold; n80++;
  }});
  const high = list.filter(p=>p._st.rot>=60).length;
  const low = list.filter(p=>p._st.rot>0 && p._st.rot<30).length;
  const ret = list.reduce((a,p)=>a+(p.ret||0),0);
  document.getElementById('insightRow').innerHTML = `
    <div class="ibox"><h4>Pareto</h4><p><b>${{n80}}</b> modelos concentran ~80% de las ventas del filtro.</p></div>
    <div class="ibox" style="border-color:var(--gr)"><h4>Alta rotación</h4><p><b>${{high}}</b> modelos sobre 60% sell-through.</p></div>
    <div class="ibox" style="border-color:var(--am)"><h4>Arrastre de stock</h4><p><b>${{low}}</b> modelos con rotación baja y stock vivo.</p></div>
    <div class="ibox" style="border-color:var(--re)"><h4>Devoluciones</h4><p><b>${{ret}}</b> und. marcadas como retorno en el período total.</p></div>`;
}}

function destroyChart(key){{ if(charts[key]){{ charts[key].destroy(); charts[key]=null; }} }}

function renderCharts(list){{
  const mks = selectedMonths();
  const labels = mks.map(k => RAW.period.months.find(m=>m.k===k)?.l || k);
  let values = mks.map(k => {{
    const i = monthIndex(k);
    return list.reduce((a,p)=> a + (p.m[i]||0), 0);
  }});
  let label = 'Unidades / mes';
  if(STATE.grain==='week'){{
    values = values.map(v => Math.round((v/4.3)*10)/10);
    label = 'Ritmo estimado und / semana';
  }}
  document.getElementById('trendLabel').textContent = '· ' + label;
  document.getElementById('trendSub').textContent = STATE.grain==='week'
    ? 'Estimación: cada mes se traduce a ritmo semanal (÷4.3). No hay fecha diaria en el reporte.'
    : 'Ventas netas del filtro actual';

  destroyChart('trend');
  charts.trend = new Chart(document.getElementById('cTrend'), {{
    type:'bar',
    data:{{ labels, datasets:[{{ data:values,
      backgroundColor: values.map((_,i)=> i===values.length-1 ? 'rgba(20,184,166,.85)' : 'rgba(20,184,166,.25)'),
      borderColor: values.map((_,i)=> i===values.length-1 ? '#2dd4bf' : 'rgba(20,184,166,.4)'),
      borderWidth:1, borderRadius:8 }}] }},
    options:{{ responsive:true, maintainAspectRatio:false,
      plugins:{{legend:{{display:false}}, tooltip:{{callbacks:{{label:c=>` ${{c.raw}} und`}}}}}},
      scales:{{ x:{{grid:{{color:'#183044'}},ticks:{{color:'#7f9bb0'}}}},
               y:{{grid:{{color:'#183044'}},ticks:{{color:'#7f9bb0'}}}} }}
    }}
  }});

  const ranked = [...list].sort((a,b)=>b._st.sold-a._st.sold);
  const top = ranked.slice(0,10);
  const rest = ranked.slice(10).reduce((a,p)=>a+Math.max(p._st.sold,0),0);
  const tL = top.map(p=>p.n).concat(rest>0?['Resto']:[]);
  const tV = top.map(p=>Math.max(p._st.sold,0)).concat(rest>0?[rest]:[]);
  const PAL = ['#14b8a6','#2dd4bf','#38bdf8','#34d399','#fbbf24','#fb7185','#818cf8','#22d3ee','#a3e635','#f97316','#64748b'];
  destroyChart('share');
  charts.share = new Chart(document.getElementById('cShare'), {{
    type:'doughnut',
    data:{{ labels:tL, datasets:[{{ data:tV, backgroundColor:PAL, borderWidth:0, hoverOffset:4 }}] }},
    options:{{ responsive:true, maintainAspectRatio:false, cutout:'62%',
      plugins:{{ legend:{{position:'right', labels:{{color:'#7f9bb0', font:{{size:9}}, boxWidth:8, padding:4}}}},
        tooltip:{{callbacks:{{label:c=>` ${{c.label}}: ${{c.raw}} und`}}}} }}
    }}
  }});
}}

function variantPanel(p){{
  const colors = {{}};
  (p.vars||[]).forEach(v=>{{
    const sold = variantPeriodSold(v);
    const key = v.c + ' · ' + (v.g && v.g!=='—' ? v.g : 'GEN');
    if(!colors[key]) colors[key] = {{c:v.c, g:v.g, v:0, s:0, tallas:[]}};
    colors[key].v += sold;
    colors[key].s += v.s;
    if(v.t && v.t!=='U') colors[key].tallas.push({{t:v.t, v:sold, s:v.s}});
  }});
  const rows = Object.values(colors).sort((a,b)=>b.v-a.v || b.s-a.s).slice(0,24);
  if(!rows.length) return `<div class="muted">Sin desglose de variantes</div>`;
  const max = Math.max(...rows.map(r=>Math.max(r.v,0)),1);
  return `<div class="muted" style="margin-bottom:8px">Variantes del período · ${{p._st.sold}} und · ${{rows.length}} grupos color/género</div>
    <div class="vgrid">${{rows.map(r=>{{
      const pct = Math.round(100*Math.max(r.v,0)/max);
      const tallas = r.tallas.filter(t=>t.v>0 || t.s>0).sort((a,b)=>b.v-a.v).slice(0,8);
      return `<div class="vcard">
        <div class="t">${{r.c}} ${{r.g && r.g!=='—' ? `<span class="muted">${{r.g}}</span>`:''}}</div>
        <div class="m">${{r.v}}v · ${{r.s}}s · ${{(()=>{{const t=Math.max(r.v,0)+r.s; return t?Math.round(100*Math.max(r.v,0)/t):0;}})()}}%</div>
        <div class="gbar"><i style="width:${{pct}}%"></i></div>
        ${{tallas.length?`<div class="tchips">${{tallas.map(t=>`<span><b>${{t.t}}</b> ${{t.v}}v/${{t.s}}s</span>`).join('')}}</div>`:''}}
      </div>`;
    }}).join('')}}</div>`;
}}

function renderTopList(list){{
  const ranked = [...list].sort((a,b)=>b._st.sold-a._st.sold).slice(0,12);
  const mx = Math.max(...ranked.map(p=>p._st.sold + p._st.stock),1);
  document.getElementById('topList').innerHTML = ranked.map((p,i)=>`
    <div class="xi" onclick="TG(this,event)">
      <div class="xh">
        <span class="rk">${{i+1}}</span>
        <span class="nm">${{p.n}}</span>
        <div class="trk"><i style="width:${{Math.round(100*p._st.sold/mx)}}%;background:${{rc(p._st.rot)}}"></i>
          <i style="width:${{Math.round(100*p._st.stock/mx)}}%;background:${{rc(p._st.rot)}};opacity:.25"></i></div>
        ${{rb(p._st.rot)}}
        <span class="num" style="color:${{rc(p._st.rot)}}">${{p._st.sold}}</span>
        <span class="xa">▾</span>
      </div>
      <div class="xb">${{variantPanel(p)}}</div>
    </div>`).join('') || `<div class="empty">Sin datos para el filtro</div>`;
}}

function renderRotMatrix(list){{
  renderRotBands(list, 'rotMatrix', true);
}}

function renderProductos(){{
  let list = filteredProducts();
  const key = STATE.psort;
  list = [...list].sort((a,b)=>{{
    if(key==='r') return b._st.rot-a._st.rot;
    if(key==='s') return b._st.stock-a._st.stock;
    if(key==='mom') return (b._st.mom??-999)-(a._st.mom??-999);
    return b._st.sold-a._st.sold;
  }});
  const mx = Math.max(...list.map(p=>p._st.sold + (STATE.grain==='all'?p._st.stock:0)),1);
  document.getElementById('pCnt').textContent = `${{list.length}} modelos · click para expandir variantes (género · color · talla)`;
  document.getElementById('pList').innerHTML = list.map((p,i)=>`
    <div class="xi" onclick="TG(this,event)">
      <div class="xh">
        <span class="rk">${{i+1}}</span>
        <span class="nm">${{p.n}}</span>
        <div class="trk">
          <i style="width:${{Math.round(100*p._st.sold/mx)}}%;background:${{rc(p._st.rot)}}"></i>
          <i style="width:${{Math.round(100*p._st.stock/mx)}}%;background:${{rc(p._st.rot)}};opacity:.22"></i>
        </div>
        ${{rb(p._st.rot)}}
        <span class="num" style="min-width:42px;text-align:right;color:${{rc(p._st.rot)}}">${{p._st.sold}}</span>
        <span class="muted" style="min-width:46px;text-align:right">${{p._st.stock}}s</span>
        <span class="muted" style="min-width:54px;text-align:right">${{p._st.mom==null?'—':(p._st.mom>0?'+':'')+p._st.mom+'%'}}</span>
        <span class="xa">▾</span>
      </div>
      <div class="xb">
        <div class="muted" style="margin-bottom:8px">
          Cover: ${{p._st.cover==null?'∞':p._st.cover+' sem'}} · SKUs/variantes: ${{p.vars.length}} · Ritmo: ${{Math.round(p._st.avgW*10)/10}} und/sem
        </div>
        ${{variantPanel(p)}}
      </div>
    </div>`).join('') || `<div class="empty">Sin modelos para este filtro</div>`;
}}

function renderRotBands(list, targetId, openFirst=true){{
  const segs = [
    {{lb:'Rota bien', sub:'>60% sell-through', col:'var(--gr)', bg:'rgba(52,211,153,.10)', fl:p=>p._st.rot>=60}},
    {{lb:'Rotación media', sub:'30–60%', col:'var(--am)', bg:'rgba(251,191,36,.08)', fl:p=>p._st.rot>=30&&p._st.rot<60}},
    {{lb:'Baja rotación', sub:'<30% con movimiento', col:'var(--re)', bg:'rgba(251,113,133,.08)', fl:p=>p._st.rot>0&&p._st.rot<30}},
    {{lb:'Sin ventas', sub:'stock sin demanda en filtro', col:'var(--mu)', bg:'rgba(127,155,176,.08)', fl:p=>p._st.sold<=0&&p._st.stock>0}},
  ];
  const mx = Math.max(...list.map(p=>p._st.sold+p._st.stock),1);
  document.getElementById(targetId).innerHTML = segs.map((seg,si)=>{{
    const items = list.filter(seg.fl).sort((a,b)=>b._st.sold-a._st.sold);
    if(!items.length) return '';
    const tv = items.reduce((a,p)=>a+p._st.sold,0), ts=items.reduce((a,p)=>a+p._st.stock,0);
    return `<div class="rseg ${{openFirst && si===0?'open':''}}">
      <div class="rseg-h" style="background:${{seg.bg}};border-color:${{seg.col}}33" onclick="this.parentElement.classList.toggle('open')">
        <div style="flex:1"><b style="color:${{seg.col}}">${{seg.lb}}</b> <span class="muted" style="margin-left:6px">${{seg.sub}}</span></div>
        <span class="num" style="color:${{seg.col}}">${{items.length}} · ${{tv}}v · ${{ts}}s</span>
        <span class="xa">▾</span>
      </div>
      <div class="rseg-b">
        ${{items.map(p=>`
          <div class="xi" onclick="TG(this,event)">
            <div class="xh">
              <span class="nm">${{p.n}}</span>
              <div class="trk"><i style="width:${{Math.round(100*p._st.sold/mx)}}%;background:${{seg.col}}"></i>
                <i style="width:${{Math.round(100*p._st.stock/mx)}}%;background:${{seg.col}};opacity:.22"></i></div>
              <span class="num" style="color:${{seg.col}}">${{p._st.rot}}%</span>
              <span class="muted">${{p._st.sold}}v · ${{p._st.stock}}s</span>
              <span class="xa">▾</span>
            </div>
            <div class="xb">${{variantPanel(p)}}</div>
          </div>`).join('')}}
      </div>
    </div>`;
  }}).join('') || `<div class="empty">Sin datos</div>`;
}}

function renderRotacion(){{
  const list = filteredProducts();
  const bands = [
    {{k:'h', l:'Alta >60%', c:'c-gr', n:list.filter(p=>p._st.rot>=60).length}},
    {{k:'m', l:'Media 30–60%', c:'c-am', n:list.filter(p=>p._st.rot>=30&&p._st.rot<60).length}},
    {{k:'l', l:'Baja <30%', c:'c-re', n:list.filter(p=>p._st.rot>0&&p._st.rot<30).length}},
    {{k:'z', l:'Sin ventas', c:'', n:list.filter(p=>p._st.sold<=0&&p._st.stock>0).length}},
  ];
  document.getElementById('rotKpis').style.gridTemplateColumns = 'repeat(4,1fr)';
  document.getElementById('rotKpis').innerHTML = bands.map(b=>`
    <div class="kpi ${{b.c}}"><div class="kv">${{b.n}}</div><div class="kl">${{b.l}}</div></div>`).join('');
  renderRotBands(list, 'rotList', true);
}}

function renderInventario(){{
  const q = (document.getElementById('iSrch').value||'').toLowerCase();
  let list = filteredProducts().filter(p=>p._st.stock>0 || p._st.sold>0);
  if(q) list = list.filter(p=>p.n.toLowerCase().includes(q));
  list.sort((a,b)=>b._st.stock-a._st.stock);
  document.getElementById('iCnt').textContent = list.length + ' filas';
  document.getElementById('iBody').innerHTML = list.map((p,i)=>{{
    const open = STATE.openInv.has(p.n);
    const mom = p._st.mom==null?'—':((p._st.mom>0?'+':'')+p._st.mom+'%');
    const stLabel = p._st.sold>0 ? `<span style="color:var(--gr)">Con ventas</span>` : `<span style="color:var(--re)">Sin ventas</span>`;
    const vars = (p.vars||[]).map(v=>{{
      const sold = variantPeriodSold(v);
      if(sold===0 && v.s===0) return '';
      return `<tr class="tr-var"><td></td><td>${{v.g!=='—'?'['+v.g+'] ':''}}${{v.c}} · ${{v.t}}</td>
        <td class="n">${{sold}}</td><td class="n">${{v.s}}</td>
        <td class="n">${{rb((()=>{{const t=Math.max(sold,0)+v.s;return t?Math.round(100*Math.max(sold,0)/t):0;}})())}}</td>
        <td class="n">—</td><td class="n">—</td><td></td></tr>`;
    }}).join('');
    return `<tr class="tr-exp" onclick="toggleInvRow('${{p.n}}')">
      <td class="muted">${{open?'▴':'▾'}}</td>
      <td><strong>${{p.n}}</strong></td>
      <td class="n" style="color:var(--a2)">${{p._st.sold}}</td>
      <td class="n"><b>${{p._st.stock}}</b></td>
      <td class="n">${{rb(p._st.rot)}}</td>
      <td class="n">${{p._st.cover==null?'∞':p._st.cover}}</td>
      <td class="n">${{mom}}</td>
      <td>${{stLabel}}</td>
    </tr>${{open?vars:''}}`;
  }}).join('') || `<tr><td colspan="8" class="empty">Sin filas</td></tr>`;
}}
function toggleInvRow(n){{
  if(STATE.openInv.has(n)) STATE.openInv.delete(n); else STATE.openInv.add(n);
  renderInventario();
}}

function renderDecisiones(){{
  const list = filteredProducts();
  const buy = list.filter(p=>p._st.stock===0 && p._st.sold>=3).sort((a,b)=>b._st.sold-a._st.sold).slice(0,10);
  const hold = list.filter(p=>p._st.rot>=40 && p._st.rot<=75 && p._st.stock>0 && p._st.sold>0).slice(0,10);
  const act = list.filter(p=>p._st.rot>0 && p._st.rot<30 && p._st.stock>=5).sort((a,b)=>b._st.stock-a._st.stock).slice(0,10);
  const liq = list.filter(p=>p._st.sold<=0 && p._st.stock>0).sort((a,b)=>b._st.stock-a._st.stock).slice(0,10);
  const over = list.filter(p=>p._st.cover!=null && p._st.cover>16 && p._st.sold>0).sort((a,b)=>b._st.cover-a._st.cover).slice(0,10);
  const fi = (arr, extra) => arr.map(p=>`<div class="di"><strong>${{p.n}}</strong><small>${{extra(p)}}</small></div>`).join('') || '<p class="muted">—</p>';
  document.getElementById('decisions').innerHTML = `
    <div class="dbox" style="border-color:var(--gr)"><h4 style="color:var(--gr)">Reponer</h4>
      <p>Demanda activa y stock agotado</p>${{fi(buy,p=>p._st.sold+'v · 0s')}}</div>
    <div class="dbox" style="border-color:var(--ac)"><h4 style="color:var(--a2)">Mantener</h4>
      <p>Rotación saludable — monitoreo</p>${{fi(hold,p=>p._st.rot+'% · '+p._st.sold+'v/'+p._st.stock+'s')}}</div>
    <div class="dbox" style="border-color:var(--am)"><h4 style="color:var(--am)">Activar / promover</h4>
      <p>Stock alto con baja salida</p>${{fi(act,p=>p._st.stock+'s · '+p._st.rot+'%')}}</div>
    <div class="dbox" style="border-color:var(--re)"><h4 style="color:var(--re)">Sin movimiento</h4>
      <p>Evaluar traslado o liquidación</p>${{fi(liq,p=>p._st.stock+'s')}}</div>
    <div class="dbox" style="border-color:var(--bl);grid-column:1/-1"><h4 style="color:var(--bl)">Sobre-stock (cover &gt; 16 semanas)</h4>
      <p>Inventario supera ~4 meses de ritmo actual</p>${{fi(over,p=>p._st.cover+' sem · '+p._st.stock+'s')}}</div>`;
}}

function renderInsights(){{
  const list = filteredProducts();
  const sold = list.reduce((a,p)=>a+Math.max(p._st.sold,0),0)||1;
  const ranked = [...list].sort((a,b)=>b._st.sold-a._st.sold);
  let cum=0; const cumShare=[];
  ranked.forEach((p,i)=>{{ cum+=Math.max(p._st.sold,0); cumShare.push({{x:i+1, y:Math.round(1000*cum/sold)/10, n:p.n}}); }});

  destroyChart('pareto');
  charts.pareto = new Chart(document.getElementById('cPareto'), {{
    type:'line',
    data:{{ labels: cumShare.slice(0,30).map(d=>d.x),
      datasets:[{{ data:cumShare.slice(0,30).map(d=>d.y), borderColor:'#2dd4bf', backgroundColor:'rgba(20,184,166,.15)',
        fill:true, tension:.25, pointRadius:2 }}] }},
    options:{{ responsive:true, maintainAspectRatio:false,
      plugins:{{legend:{{display:false}}, tooltip:{{callbacks:{{title:c=>ranked[c[0].dataIndex]?.n||'', label:c=>` ${{c.raw}}% acum.`}}}}}},
      scales:{{ x:{{title:{{display:true,text:'# modelos',color:'#7f9bb0'}}, ticks:{{color:'#7f9bb0'}}, grid:{{color:'#183044'}}}},
               y:{{min:0,max:100, ticks:{{color:'#7f9bb0'}}, grid:{{color:'#183044'}}}} }}
    }}
  }});

  const health = [
    list.filter(p=>p._st.rot>=60).length,
    list.filter(p=>p._st.rot>=30&&p._st.rot<60).length,
    list.filter(p=>p._st.rot>0&&p._st.rot<30).length,
    list.filter(p=>p._st.sold<=0&&p._st.stock>0).length,
  ];
  destroyChart('health');
  charts.health = new Chart(document.getElementById('cHealth'), {{
    type:'bar',
    data:{{ labels:['Alta','Media','Baja','Sin ventas'],
      datasets:[{{ data:health, backgroundColor:['#34d399','#fbbf24','#fb7185','#64748b'], borderRadius:8 }}] }},
    options:{{ responsive:true, maintainAspectRatio:false, plugins:{{legend:{{display:false}}}},
      scales:{{ x:{{ticks:{{color:'#7f9bb0'}}, grid:{{display:false}}}}, y:{{ticks:{{color:'#7f9bb0'}}, grid:{{color:'#183044'}}}} }}
    }}
  }});

  const top = ranked[0];
  const worstCover = [...list].filter(p=>p._st.cover!=null).sort((a,b)=>b._st.cover-a._st.cover)[0];
  const bestMom = [...list].filter(p=>p._st.mom!=null).sort((a,b)=>b._st.mom-a._st.mom)[0];
  const worstMom = [...list].filter(p=>p._st.mom!=null).sort((a,b)=>a._st.mom-b._st.mom)[0];
  document.getElementById('findings').innerHTML = `
    <div class="ibox"><h4>Motor de ventas</h4><p>${{top?`<b>${{top.n}}</b> lidera con ${{top._st.sold}} und (${{Math.round(100*top._st.sold/sold)}}%).`: '—'}}</p></div>
    <div class="ibox" style="border-color:var(--am)"><h4>Mayor cover</h4><p>${{worstCover?`<b>${{worstCover.n}}</b> ≈ ${{worstCover._st.cover}} semanas de stock.`: '—'}}</p></div>
    <div class="ibox" style="border-color:var(--gr)"><h4>Mejor MoM</h4><p>${{bestMom?`<b>${{bestMom.n}}</b> ${{bestMom._st.mom>0?'+':''}}${{bestMom._st.mom}}%.`: 'Se necesitan ≥2 meses.'}}</p></div>
    <div class="ibox" style="border-color:var(--re)"><h4>Peor MoM</h4><p>${{worstMom?`<b>${{worstMom.n}}</b> ${{worstMom._st.mom>0?'+':''}}${{worstMom._st.mom}}%.`: '—'}}</p></div>`;
}}

function renderResumen(){{
  const list = filteredProducts();
  renderKPIs(list);
  renderInsightsRow(list);
  renderCharts(list);
  renderRotMatrix(list);
  renderTopList(list);
}}

function renderAll(){{
  filterNote();
  document.getElementById('pillPeriod').innerHTML = `<em>${{RAW.period.from}}</em> → <em>${{RAW.period.to}}</em>`;
  document.getElementById('hdrSub').textContent = RAW.subtitle + ' · ' + RAW.period.from + '–' + RAW.period.to;
  document.getElementById('foot').textContent = `Generado ${{RAW.generated}} · ${{RAW.P.filter(p=>!p.pack).length}} modelos merch · packaging excluido del análisis principal`;
  renderResumen();
  // refresh open tabs content lazily
  if(document.getElementById('sec-productos').classList.contains('on')) renderProductos();
  if(document.getElementById('sec-rotacion').classList.contains('on')) renderRotacion();
  if(document.getElementById('sec-inventario').classList.contains('on')) renderInventario();
  if(document.getElementById('sec-decisiones').classList.contains('on')) renderDecisiones();
  if(document.getElementById('sec-insights').classList.contains('on')) renderInsights();
}}

// init
buildMonthChips();
buildModelPanel();
renderAll();
</script>
</body>
</html>
"""


def main():
    stock, sales = load_frames()
    payload = build_payload(stock, sales)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    html = html_template(data_json)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT_HTML} ({OUT_HTML.stat().st_size:,} bytes)")
    print(f"Wrote {OUT_JSON} ({OUT_JSON.stat().st_size:,} bytes)")
    print("Models:", len(payload["P"]), "Sold:", payload["kpi"]["V"], "Stock:", payload["kpi"]["S"])
    print("Months:", payload["period"]["months"])


if __name__ == "__main__":
    main()
