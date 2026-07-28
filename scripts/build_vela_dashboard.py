#!/usr/bin/env python3
"""Process VELA stock/sales Excel files and generate dashboard HTML."""
import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STOCK_PATH = Path("/home/ubuntu/.cursor/projects/workspace/uploads/VELA_STOCK_COMPLETO_d433.xlsx")
SALES_PATH = Path("/home/ubuntu/.cursor/projects/workspace/uploads/Reporte_ventas_VELA_COMPLETO_5bff.xlsx")
OUT_HTML = ROOT / "dashboard_vela.html"

MES_LABELS = {6: "Jun", 7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic", 1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May"}
MES_FULL = {
    6: "Jun 2026", 7: "Jul 2026", 8: "Ago 2026", 9: "Sep 2026", 10: "Oct 2026",
    11: "Nov 2026", 12: "Dic 2026", 1: "Ene 2026", 2: "Feb 2026", 3: "Mar 2026",
    4: "Abr 2026", 5: "May 2026",
}


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


def build_payload():
    stock = pd.read_excel(STOCK_PATH, sheet_name="Ventas")
    sales = pd.read_excel(SALES_PATH, sheet_name="Ventas")

    sales = sales.copy()
    sales["base"] = sales["modelo"].apply(base_model)
    sales["fecha_parsed"] = pd.to_datetime(sales["fecha (mes año)"], format="%m/%Y", errors="coerce")
    sales["mes_num"] = sales["fecha_parsed"].dt.month
    sales["qty"] = sales["Cant. ordenada"].fillna(0).astype(int)

    months_sorted = sorted(sales["mes_num"].dropna().unique().astype(int).tolist())
    mes_labels = [MES_LABELS.get(m, str(m)) for m in months_sorted]
    mon_totals = [int(sales[sales["mes_num"] == m]["qty"].sum()) for m in months_sorted]

    stock = stock.copy()
    stock["base"] = stock["MODELO"].apply(base_model)
    stock["qty"] = stock["Cantidad en inventario"].fillna(0).astype(int)

    all_models = sorted(set(stock["base"].unique()) | set(sales["base"].unique()))
    all_models = [m for m in all_models if m]

    products = []
    n_months = max(len(months_sorted), 1)

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

        products.append({
            "n": model,
            "v": v,
            "s": s,
            "r": r,
            "vel": velocity,
            "mos": min(mos, 999),
            "m": monthly,
            "cat": categorize(model),
            "vars": vars_list[:25],
        })

    products.sort(key=lambda p: (-p["v"], -p["s"]))

    v_total = sum(p["v"] for p in products)
    s_total = sum(p["s"] for p in products)
    m_count = len([p for p in products if p["v"] > 0 or p["s"] > 0])

    top = sorted(products, key=lambda p: -p["v"])[:15]
    rest_v = v_total - sum(p["v"] for p in top)
    tL = [p["n"] for p in top] + (["Resto"] if rest_v > 0 else [])
    tV = [p["v"] for p in top] + ([rest_v] if rest_v > 0 else [])

    cat_sales = defaultdict(int)
    cat_stock = defaultdict(int)
    for p in products:
        cat_sales[p["cat"]] += p["v"]
        cat_stock[p["cat"]] += p["s"]

    gen_sales = defaultdict(int)
    for _, row in sales.iterrows():
        g = norm_str(row.get("GENERO")) or "Sin género"
        gen_sales[g] += int(row["qty"])

    avg_monthly = v_total / n_months
    mom = None
    if len(mon_totals) >= 2 and mon_totals[0]:
        mom = round((mon_totals[-1] - mon_totals[0]) / mon_totals[0] * 100, 1)

    sell_through = round(v_total / (v_total + s_total) * 100, 1) if (v_total + s_total) else 0
    dead_stock = sum(p["s"] for p in products if p["v"] == 0 and p["s"] > 0)
    dead_models = len([p for p in products if p["v"] == 0 and p["s"] > 0])
    high_rot = len([p for p in products if p["r"] >= 60])

    sorted_by_v = sorted([p for p in products if p["v"] > 0], key=lambda p: -p["v"])
    cum = 0
    abc = {"A": [], "B": [], "C": []}
    for p in sorted_by_v:
        cum += p["v"]
        pct = cum / v_total * 100 if v_total else 100
        if pct <= 80:
            abc["A"].append(p["n"])
        elif pct <= 95:
            abc["B"].append(p["n"])
        else:
            abc["C"].append(p["n"])

    coverage_issues = []
    for p in products:
        if p["v"] > 0 and p["s"] > 0 and p["vel"] > 0:
            if p["mos"] > 4:
                coverage_issues.append({"n": p["n"], "months": p["mos"], "s": p["s"], "v": p["v"]})
    coverage_issues.sort(key=lambda x: -x["months"])

    reorder = sorted([p for p in products if p["s"] <= 2 and p["v"] >= 8], key=lambda p: -p["v"])
    fast_movers = sorted([p for p in products if p["vel"] >= 15], key=lambda p: -p["vel"])[:10]

    zero_sales_high_stock = sorted(
        [p for p in products if p["v"] == 0 and p["s"] >= 5], key=lambda p: -p["s"]
    )[:12]

    periodo = (
        f"{MES_FULL.get(months_sorted[0], months_sorted[0])} — {MES_FULL.get(months_sorted[-1], months_sorted[-1])}"
        if months_sorted
        else "Sin período"
    )

    insights = [
        f"Período analizado: {periodo}. Ventas {v_total:,} und vs stock actual {s_total:,} und (sell-through acumulado {sell_through}%).",
        f"Ritmo: {round(avg_monthly):,} und/mes promedio."
        + (f" Jun vs Jul: {mom:+.1f}% en unidades." if mom is not None else ""),
        f"{len(reorder)} modelos con demanda fuerte y stock casi agotado (≤2 und en piso).",
        f"{dead_models} SKUs sin ventas en el período acumulan {dead_stock:,} unidades — revisar exhibición o traslado.",
        f"Clase A (ABC): {len(abc['A'])} modelos concentran el 80% de ventas.",
    ]

    return {
        "store": "LA VELA",
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
        "coverage_issues": coverage_issues[:15],
        "zero_sales_high_stock": [{"n": p["n"], "s": p["s"]} for p in zero_sales_high_stock],
        "reorder": [{"n": p["n"], "v": p["v"], "s": p["s"], "vel": p["vel"]} for p in reorder[:12]],
        "fast_movers": [{"n": p["n"], "vel": p["vel"], "v": p["v"]} for p in fast_movers],
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LA VELA · Dashboard Tienda</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root{
  --bg:#061018;--su:#0a1520;--s2:#0f1e2d;--s3:#152638;--bd:#1e3348;
  --ac:#14b8a6;--a2:#5eead4;--coral:#fb7185;--sand:#fcd34d;--gr:#34d399;--re:#f87171;--am:#fbbf24;
  --mu:#6b8a9e;--m2:#3d5566;--tx:#e8f4fc;
  --fh:'Outfit',sans-serif;--fm:'IBM Plex Mono',monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:radial-gradient(ellipse 120% 80% at 50% -20%,#0d2840 0%,var(--bg) 55%);color:var(--tx);font-family:var(--fh);min-height:100vh}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-thumb{background:var(--bd);border-radius:4px}

.hdr{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:18px 28px 14px;
  border-bottom:1px solid var(--bd);position:sticky;top:0;z-index:300;
  background:rgba(6,16,24,.92);backdrop-filter:blur(12px)}
.brand{display:flex;align-items:center;gap:14px}
.badge{background:linear-gradient(135deg,#0d9488,#14b8a6 40%,#fb7185);border-radius:10px;
  padding:8px 16px;font-size:.72rem;font-weight:800;letter-spacing:.12em;color:#042018;flex-shrink:0}
.hdr h1{font-size:1.15rem;font-weight:800;letter-spacing:-.02em}
.hdr p{font-size:.68rem;color:var(--mu);margin-top:3px;max-width:520px;line-height:1.45}
.meta{font-family:var(--fm);font-size:.62rem;color:var(--a2);margin-top:6px}

.insight-strip{margin:0 28px 0;padding:12px 16px;background:linear-gradient(90deg,rgba(20,184,166,.12),rgba(251,113,133,.08));
  border:1px solid rgba(20,184,166,.25);border-radius:12px;font-size:.72rem;line-height:1.55;color:var(--tx)}
.insight-strip strong{color:var(--a2);font-weight:700}
.insight-strip ul{margin:6px 0 0 18px;color:var(--mu)}
.insight-strip li{margin:3px 0}

.krow{display:flex;gap:10px;padding:14px 28px;overflow-x:auto;flex-wrap:wrap}
.kpi{background:var(--su);border:1px solid var(--bd);border-radius:12px;padding:13px 18px;flex:1;min-width:130px;
  position:relative;overflow:hidden}
.kpi::after{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--ac),transparent);opacity:.6}
.kv{font-size:1.55rem;font-weight:800;font-family:var(--fm);line-height:1}
.kl{font-size:.58rem;color:var(--mu);margin-top:5px;text-transform:uppercase;letter-spacing:.08em}
.ks{font-size:.62rem;color:var(--m2);margin-top:2px;font-family:var(--fm)}
.c-teal .kv{color:var(--a2)}.c-gr .kv{color:var(--gr)}.c-am .kv{color:var(--am)}.c-re .kv{color:var(--re)}.c-cor .kv{color:var(--coral)}

.tabs{display:flex;gap:2px;padding:0 28px;border-bottom:1px solid var(--bd);overflow-x:auto;background:rgba(10,21,32,.6)}
.tab{padding:10px 16px;font-size:.73rem;font-weight:700;color:var(--mu);background:none;border:none;cursor:pointer;
  border-bottom:2px solid transparent;white-space:nowrap;font-family:var(--fh);transition:color .12s}
.tab.on{color:var(--a2);border-bottom-color:var(--ac)}
.tab:hover:not(.on){color:var(--tx)}

.page{padding:20px 28px 40px;max-width:1440px;margin:0 auto}
.sec{display:none}.sec.on{display:block}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.g21{display:grid;grid-template-columns:1.2fr 1fr;gap:14px}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.card{background:var(--su);border:1px solid var(--bd);border-radius:14px;padding:18px}
.ct{font-size:.64rem;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px}
.ct em{color:var(--a2);font-style:normal;font-weight:600}
.cw{position:relative}.h200{height:200px}.h240{height:240px}.h280{height:280px}

.fbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;background:var(--su);border:1px solid var(--bd);
  border-radius:11px;padding:10px 14px;margin-bottom:12px}
.fb-l{font-size:.6rem;color:var(--mu);text-transform:uppercase;letter-spacing:.07em}
.chip{padding:4px 11px;border-radius:20px;font-size:.65rem;font-weight:700;cursor:pointer;border:1px solid var(--bd);
  background:var(--s2);color:var(--mu);font-family:var(--fh);transition:all .12s}
.chip.on{background:var(--ac);border-color:var(--ac);color:#042018}
.srch{flex:1;min-width:140px;padding:7px 12px;background:var(--s2);border:1px solid var(--bd);border-radius:8px;
  color:var(--tx);font-size:.73rem;font-family:var(--fh);outline:none}
.srch:focus{border-color:var(--ac)}
.sbtn{padding:4px 10px;border-radius:6px;font-size:.63rem;font-weight:700;cursor:pointer;border:1px solid var(--bd);
  background:var(--s2);color:var(--mu);font-family:var(--fh)}
.sbtn.on{background:var(--ac);border-color:var(--ac);color:#042018}

.xi{border:1px solid transparent;border-radius:9px;overflow:hidden;cursor:pointer;margin-bottom:4px}
.xi.open{border-color:var(--bd)}
.xh{display:flex;align-items:center;gap:8px;padding:9px 12px;background:var(--s2)}
.xi.open .xh{background:var(--s3)}
.xb{display:none;padding:12px 14px;border-top:1px solid var(--bd);background:var(--su)}
.xi.open .xb{display:block}
.xa{font-size:.57rem;color:var(--m2);flex-shrink:0}
.pnm,.rnm{flex:1;font-size:.74rem;font-weight:700;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.prt{font-size:.58rem;font-weight:700;border-radius:4px;padding:2px 6px}
.pH{background:rgba(52,211,153,.15);color:var(--gr)}.pM{background:rgba(251,191,36,.15);color:var(--am)}
.pL{background:rgba(248,113,113,.12);color:var(--re)}.pZ{background:rgba(107,138,158,.12);color:var(--mu)}

.abc-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.abc-box{background:var(--s2);border-radius:10px;padding:14px;border-top:3px solid}
.abc-box h4{font-size:.78rem;margin-bottom:4px}
.abc-box p{font-size:.62rem;color:var(--mu);margin-bottom:8px}
.tag{display:inline-block;font-size:.58rem;padding:2px 7px;border-radius:4px;background:var(--s3);margin:2px;color:var(--tx)}

.itbl{width:100%;border-collapse:collapse;font-size:.71rem}
.itbl th{padding:8px 10px;text-align:left;color:var(--mu);font-size:.58rem;text-transform:uppercase;border-bottom:1px solid var(--bd);
  position:sticky;top:0;background:var(--su)}
.itbl td{padding:8px 10px;border-bottom:1px solid #0a1520}
.num{text-align:right;font-family:var(--fm)}

.dg{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.dbox{background:var(--s2);border-radius:12px;padding:14px;border-left:3px solid}
.dbox h4{font-size:.74rem;font-weight:800;margin-bottom:3px}
.dbox p{font-size:.6rem;color:var(--mu);margin-bottom:8px}
.di{font-size:.68rem;padding:6px 9px;border-radius:6px;background:var(--su);margin-bottom:4px;display:flex;justify-content:space-between;gap:8px}
.di strong{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.di small{font-family:var(--fm);color:var(--mu);flex-shrink:0}

.footer{text-align:center;padding:20px;font-size:.62rem;color:var(--m2);border-top:1px solid var(--bd);margin-top:24px}

@media(max-width:900px){.g2,.g21,.g3,.dg,.abc-grid{grid-template-columns:1fr}.page,.hdr,.tabs,.krow,.insight-strip{margin-left:0;margin-right:0;padding-left:16px;padding-right:16px}}
</style>
</head>
<body>

<div class="hdr">
  <div class="brand">
    <div class="badge">LA VELA</div>
    <div>
      <h1>Dashboard de Tienda · Análisis Integrado</h1>
      <p>Ventas + inventario en piso · rotación, categorías, ABC y recomendaciones accionables.</p>
      <div class="meta" id="metaLine"></div>
    </div>
  </div>
</div>

<div class="insight-strip" id="insightBox" style="margin:14px 28px 0"></div>

<div class="krow" id="krow"></div>

<div class="tabs">
  <button class="tab on" onclick="GT('resumen',this)">📊 Resumen</button>
  <button class="tab" onclick="GT('analisis',this)">🔬 Análisis</button>
  <button class="tab" onclick="GT('rotacion',this)">🔄 Rotación</button>
  <button class="tab" onclick="GT('productos',this)">🛍️ Productos</button>
  <button class="tab" onclick="GT('inventario',this)">📦 Inventario</button>
  <button class="tab" onclick="GT('decisiones',this)">🎯 Decisiones</button>
</div>

<div class="page">

<div class="sec on" id="sec-resumen">
  <div class="g21" style="margin-bottom:14px">
    <div class="card">
      <div class="ct">📈 Ventas mensuales <em>· unidades</em></div>
      <div class="cw h240"><canvas id="cMon"></canvas></div>
    </div>
    <div class="card">
      <div class="ct">🏷️ Top modelos <em>· participación</em></div>
      <div class="cw h240"><canvas id="cTop"></canvas></div>
    </div>
  </div>
  <div class="g2">
    <div class="card">
      <div class="ct">📂 Ventas por categoría</div>
      <div class="cw h200"><canvas id="cCat"></canvas></div>
    </div>
    <div class="card">
      <div class="ct">👥 Mix de género <em>· ventas</em></div>
      <div class="cw h200"><canvas id="cGen"></canvas></div>
    </div>
  </div>
  <div class="card" style="margin-top:14px">
    <div class="ct">🔄 Matriz de rotación <em>· vendido vs stock en piso</em></div>
    <div id="rotMatrix"></div>
  </div>
</div>

<div class="sec" id="sec-analisis">
  <div class="g3" style="margin-bottom:14px">
    <div class="card">
      <div class="ct">Sell-through global</div>
      <div class="kv" style="font-size:2rem;color:var(--a2);font-family:var(--fm)" id="anSell"></div>
      <p style="font-size:.68rem;color:var(--mu);margin-top:8px">Ventas del período ÷ (ventas + stock actual). Mide qué porción del mix ya se movió.</p>
    </div>
    <div class="card">
      <div class="ct">Stock sin movimiento</div>
      <div class="kv" style="font-size:2rem;color:var(--re);font-family:var(--fm)" id="anDead"></div>
      <p style="font-size:.68rem;color:var(--mu);margin-top:8px" id="anDeadSub"></p>
    </div>
    <div class="card">
      <div class="ct">Variación mensual</div>
      <div class="kv" style="font-size:2rem;font-family:var(--fm)" id="anMom"></div>
      <p style="font-size:.68rem;color:var(--mu);margin-top:8px">Comparación último vs primer mes del reporte.</p>
    </div>
  </div>
  <div class="card" style="margin-bottom:14px">
    <div class="ct">📊 Curva ABC <em>· concentración de ventas</em></div>
    <div class="abc-grid" id="abcGrid"></div>
  </div>
  <div class="g2">
    <div class="card">
      <div class="ct">⚡ Fast movers <em>· und/mes</em></div>
      <div id="fastList"></div>
    </div>
    <div class="card">
      <div class="ct">📦 Exceso de cobertura <em>· &gt;4 meses de stock</em></div>
      <div id="covList"></div>
    </div>
  </div>
</div>

<div class="sec" id="sec-rotacion">
  <div style="display:flex;gap:9px;margin-bottom:14px;flex-wrap:wrap" id="rotKpis"></div>
  <div class="fbar">
    <span class="fb-l">Ordenar</span>
    <button class="sbtn on" id="sb-r" onclick="SS('r')">% Rotación</button>
    <button class="sbtn" id="sb-v" onclick="SS('v')">Ventas</button>
    <button class="sbtn" id="sb-s" onclick="SS('s')">Stock</button>
    <button class="sbtn" id="sb-vel" onclick="SS('vel')">Velocidad</button>
    <input class="srch" id="rSrch" placeholder="Buscar modelo…" oninput="RR()" style="max-width:220px">
  </div>
  <div id="rotList" style="max-height:calc(100vh - 320px);overflow-y:auto"></div>
</div>

<div class="sec" id="sec-productos">
  <div class="fbar">
    <span class="fb-l">Mes</span>
    <div id="pMF" style="display:flex;gap:5px;flex-wrap:wrap"></div>
    <span class="fb-l">Estado</span>
    <span class="chip on" data-rf="" onclick="SPR(this)">Todos</span>
    <span class="chip" data-rf="h" onclick="SPR(this)">Alta</span>
    <span class="chip" data-rf="m" onclick="SPR(this)">Media</span>
    <span class="chip" data-rf="l" onclick="SPR(this)">Baja</span>
    <span class="chip" data-rf="z" onclick="SPR(this)">Sin ventas</span>
    <input class="srch" id="pSrch" placeholder="Buscar…" oninput="RP()">
  </div>
  <div id="pCnt" style="font-size:.65rem;color:var(--mu);margin-bottom:8px"></div>
  <div id="pList" style="max-height:calc(100vh - 300px);overflow-y:auto"></div>
</div>

<div class="sec" id="sec-inventario">
  <div class="fbar">
    <input class="srch" id="iSrch" placeholder="Buscar modelo…" oninput="RI()" style="flex:1">
    <span class="chip on" data-if="" onclick="SIF(this,'')">Todos</span>
    <span class="chip" data-if="v" onclick="SIF(this,'v')">Con ventas</span>
    <span class="chip" data-if="n" onclick="SIF(this,'n')">Sin ventas</span>
  </div>
  <div class="card" style="padding:0;overflow:hidden">
    <div style="overflow:auto;max-height:calc(100vh - 260px)">
      <table class="itbl">
        <thead><tr><th>#</th><th>Modelo</th><th>Categoría</th><th class="num">Vendido</th><th class="num">Stock</th><th class="num">Und/mes</th><th class="num">Meses stock</th><th>Estado</th></tr></thead>
        <tbody id="iBdy"></tbody>
      </table>
    </div>
  </div>
</div>

<div class="sec" id="sec-decisiones">
  <div class="dg" style="margin-bottom:14px">
    <div class="dbox" style="border-color:var(--gr)"><h4 style="color:var(--gr)">🟢 REPONER</h4><p>Alta venta y stock ≤2 — riesgo de quiebre.</p><div id="dBuy"></div></div>
    <div class="dbox" style="border-color:var(--ac)"><h4 style="color:var(--a2)">🔵 MANTENER</h4><p>Rotación equilibrada (35–75%).</p><div id="dHold"></div></div>
    <div class="dbox" style="border-color:var(--am)"><h4 style="color:var(--am)">🟡 ACTIVAR</h4><p>Stock alto, rotación baja — visibilidad/promo.</p><div id="dAct"></div></div>
    <div class="dbox" style="border-color:var(--re)"><h4 style="color:var(--re)">🔴 SIN MOVIMIENTO</h4><p>Cero ventas en el período.</p><div id="dLiq"></div></div>
  </div>
  <div class="card"><div class="ct">📊 Ventas vs stock · todos los modelos</div><div style="max-height:380px;overflow-y:auto" id="dBar"></div></div>
</div>

</div>
<div class="footer">Generado desde Reporte_ventas_VELA + VELA_STOCK · Datos embebidos · __GENERATED__</div>

<script>
const D=__DATA_JSON__;
const P=D.P, MES=D.mes;

function rc(r){return r>=60?'var(--gr)':r>=30?'var(--am)':r>0?'var(--re)':'var(--mu)'}
function rb(r){const c=r>=60?'pH':r>=30?'pM':r>0?'pL':'pZ';return`<span class="prt ${c}">${r}%</span>`}

function TG(el){
  const was=el.classList.contains('open');
  el.parentElement.querySelectorAll('.xi.open').forEach(x=>x.classList.remove('open'));
  if(!was) el.classList.add('open');
}

function VP(p){
  if(!p.vars||!p.vars.length) return'<div style="font-size:.66rem;color:var(--mu)">Sin desglose por color/talla en ventas.</div>';
  return p.vars.slice(0,18).map(v=>{
    const pct=p.v>0?Math.round(v.v/p.v*100):0;
    const ts=v.tallas&&v.tallas.length?v.tallas.map(t=>`<span style="font-size:.58rem;background:var(--s3);padding:2px 6px;border-radius:4px;margin:2px">${t.talla} ${t.v}</span>`).join(''):'';
    return`<div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:6px 0;border-bottom:1px solid var(--bd)">
      ${v.genero?`<span style="font-size:.56rem;color:var(--mu)">${v.genero}</span>`:''}
      <strong style="font-size:.7rem">${v.color}</strong>
      <span style="font-family:var(--fm);font-size:.62rem;color:var(--a2)">${v.v} und (${pct}%)</span>${ts}
    </div>`;
  }).join('');
}

function GT(id,el){
  document.querySelectorAll('.sec').forEach(s=>s.classList.remove('on'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));
  document.getElementById('sec-'+id).classList.add('on');
  if(el) el.classList.add('on');
  ({rotacion:RR,productos:RP,inventario:RI})[id]?.();
}

document.getElementById('metaLine').textContent=D.periodo+' · '+D.n_meses+' mes(es) · '+D.M+' modelos activos';
document.getElementById('insightBox').innerHTML='<strong>Insights clave</strong><ul>'+D.insights.map(i=>'<li>'+i+'</li>').join('')+'</ul>';

(function(){
  const x=D.kpis_extra;
  const items=[
    {v:D.V.toLocaleString('es'),l:'Unidades vendidas',c:'c-teal',s:'Período completo'},
    {v:D.S.toLocaleString('es'),l:'Stock en piso',c:'',s:'Snapshot actual'},
    {v:x.avg_monthly+'/mes',l:'Ritmo promedio',c:'c-gr',s:'Ventas mensuales'},
    {v:x.sell_through+'%',l:'Sell-through',c:'c-cor',s:'V÷(V+S)'},
    {v:D.M,l:'Modelos',c:'',s:'Con venta o stock'},
  ];
  if(x.mom!=null) items.push({v:(x.mom>0?'+':'')+x.mom+'%',l:'Var. mensual',c:x.mom>=0?'c-gr':'c-re',s:'Último vs primero'});
  items.forEach(k=>{
    const d=document.createElement('div');
    d.className='kpi '+k.c;
    d.innerHTML=`<div class="kv">${k.v}</div><div class="kl">${k.l}</div><div class="ks">${k.s}</div>`;
    document.getElementById('krow').appendChild(d);
  });
})();

const CG={color:'#152638'}, CT={color:'#6b8a9e',font:{size:10}};
const PAL=['#14b8a6','#fb7185','#fcd34d','#34d399','#38bdf8','#a78bfa','#f97316','#4ade80','#f472b6','#94a3b8'];

new Chart(document.getElementById('cMon'),{type:'bar',data:{labels:MES,datasets:[{data:D.mon,
  backgroundColor:D.mon.map((v,i)=>i===D.mon.length-1?'rgba(20,184,166,.9)':'rgba(20,184,166,.35)'),
  borderRadius:8}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},
  scales:{x:{grid:{color:CG.color},ticks:CT},y:{grid:{color:CG.color},ticks:CT}}}});

new Chart(document.getElementById('cTop'),{type:'doughnut',data:{labels:D.tL,datasets:[{data:D.tV,backgroundColor:PAL,borderWidth:0}]},
  options:{responsive:true,maintainAspectRatio:false,cutout:'58%',plugins:{legend:{position:'right',labels:{color:'#6b8a9e',font:{size:8},boxWidth:8}}}}});

const catLabels=Object.keys(D.cat_sales);
new Chart(document.getElementById('cCat'),{type:'bar',data:{labels:catLabels,datasets:[
  {label:'Ventas',data:catLabels.map(c=>D.cat_sales[c]),backgroundColor:'rgba(20,184,166,.75)',borderRadius:6},
  {label:'Stock',data:catLabels.map(c=>D.cat_stock[c]||0),backgroundColor:'rgba(107,138,158,.35)',borderRadius:6}
]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#6b8a9e',font:{size:9}}}},
  scales:{x:{grid:{display:false},ticks:{color:'#6b8a9e',font:{size:9},maxRotation:45}},y:{grid:{color:CG.color},ticks:CT}}}});

const gL=Object.keys(D.gen_sales);
new Chart(document.getElementById('cGen'),{type:'polarArea',data:{labels:gL,datasets:[{data:gL.map(g=>D.gen_sales[g]),backgroundColor:PAL}]},
  options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'right',labels:{color:'#6b8a9e',font:{size:9}}}}}});

document.getElementById('anSell').textContent=D.kpis_extra.sell_through+'%';
document.getElementById('anDead').textContent=D.kpis_extra.dead_stock.toLocaleString('es')+' und';
document.getElementById('anDeadSub').textContent=D.kpis_extra.dead_models+' modelos sin ventas en el período';
const mom=D.kpis_extra.mom;
document.getElementById('anMom').textContent=mom==null?'—':(mom>0?'+':'')+mom+'%';
document.getElementById('anMom').style.color=mom==null?'var(--mu)':mom>=0?'var(--gr)':'var(--re)';

document.getElementById('abcGrid').innerHTML=['A','B','C'].map((k,i)=>{
  const cols=['var(--gr)','var(--am)','var(--mu)'];
  const desc={'A':'~80% ventas','B':'~15% ventas','C':'Cola larga'};
  const tags=(k==='A'?D.abc_top_a:[]).map(t=>`<span class="tag">${t}</span>`).join('');
  return`<div class="abc-box" style="border-color:${cols[i]}"><h4>Clase ${k} · ${D.abc_counts[k]} modelos</h4><p>${desc[k]}</p>${tags||'<span style="font-size:.65rem;color:var(--m2)">Ver listado en productos</span>'}</div>`;
}).join('');

document.getElementById('fastList').innerHTML=(D.fast_movers||[]).map((p,i)=>`<div class="di"><strong>${i+1}. ${p.n}</strong><small>${p.vel} und/mes · ${p.v} total</small></div>`).join('')||'<p style="color:var(--mu);font-size:.68rem">—</p>';
document.getElementById('covList').innerHTML=(D.coverage_issues||[]).map(p=>`<div class="di"><strong>${p.n}</strong><small>${p.months} meses · ${p.s}s</small></div>`).join('')||'<p style="color:var(--mu);font-size:.68rem">Sin excesos marcados</p>';

const RG={h:P.filter(p=>p.r>=60),m:P.filter(p=>p.r>=30&&p.r<60),l:P.filter(p=>p.r>0&&p.r<30),z:P.filter(p=>p.r===0)};
document.getElementById('rotKpis').innerHTML=[
  {k:'h',l:'Rota bien >60%',c:'c-gr',n:RG.h.length},
  {k:'m',l:'Media 30–60%',c:'c-am',n:RG.m.length},
  {k:'l',l:'Baja <30%',c:'c-re',n:RG.l.length},
  {k:'z',l:'Sin ventas',c:'',n:RG.z.length},
].map(x=>`<div class="kpi ${x.c}" style="min-width:120px;flex:1"><div class="kv">${x.n}</div><div class="kl">${x.l}</div></div>`).join('');

let _srt='r';
function SS(m){_srt=m;document.querySelectorAll('.sbtn').forEach(b=>b.classList.remove('on'));document.getElementById('sb-'+m.replace('vel','vel'))?.classList.add('on');document.getElementById('sb-'+m)?.classList.add('on');RR();}

function RR(){
  const q=(document.getElementById('rSrch').value||'').toLowerCase();
  let prods=P.filter(p=>!q||p.n.toLowerCase().includes(q));
  const sortKey={r:'r',v:'v',s:'s',vel:'vel'}[_srt]||'r';
  prods=[...prods].sort((a,b)=>b[sortKey]-a[sortKey]);
  const mx=Math.max(...prods.map(p=>p.v+p.s),1);
  const segs=[
    {lb:'Rota bien',col:'var(--gr)',fl:p=>p.r>=60},
    {lb:'Rotación media',col:'var(--am)',fl:p=>p.r>=30&&p.r<60},
    {lb:'Baja rotación',col:'var(--re)',fl:p=>p.r>0&&p.r<30},
    {lb:'Sin ventas',col:'var(--mu)',fl:p=>p.r===0},
  ];
  document.getElementById('rotList').innerHTML=segs.map(seg=>{
    const items=prods.filter(seg.fl);
    if(!items.length) return '';
    return`<div style="margin-bottom:12px"><div style="font-size:.72rem;font-weight:800;color:${seg.col};margin-bottom:6px">${seg.lb} · ${items.length}</div>`+
      items.map(p=>{
        const vW=Math.round(p.v/mx*100),sW=Math.round(p.s/mx*100);
        return`<div class="xi" onclick="TG(this)"><div class="xh"><span class="rnm">${p.n}</span>
          <div style="display:flex;height:7px;flex:1;max-width:180px;background:var(--bd);border-radius:4px;overflow:hidden">
            <div style="width:${vW}%;background:${seg.col}"></div><div style="width:${sW}%;background:${seg.col};opacity:.25"></div></div>
          <span style="font-family:var(--fm);font-size:.68rem;color:${seg.col}">${p.r}%</span>
          <span style="font-family:var(--fm);font-size:.6rem;color:var(--mu)">${p.v}v · ${p.s}s · ${p.vel}/m</span><span class="xa">▾</span></div>
          <div class="xb">${VP(p)}</div></div>`;
      }).join('')+'</div>';
  }).join('');
}

let _pM='',_pR='';
document.getElementById('pMF').innerHTML=`<span class="chip on" data-m="" onclick="SPM(this)">Todos</span>`+MES.map(m=>`<span class="chip" data-m="${m}" onclick="SPM(this)">${m}</span>`).join('');
function SPM(el){document.querySelectorAll('#pMF .chip').forEach(c=>c.classList.remove('on'));el.classList.add('on');_pM=el.dataset.m;RP();}
function SPR(el){document.querySelectorAll('[data-rf]').forEach(c=>c.classList.remove('on'));el.classList.add('on');_pR=el.dataset.rf;RP();}

function RP(){
  const q=(document.getElementById('pSrch').value||'').toLowerCase();
  const mi=_pM?MES.indexOf(_pM):-1;
  let prods=P.filter(p=>{
    const mq=!q||p.n.toLowerCase().includes(q);
    const mr=!_pR||(_pR==='h'&&p.r>=60)||(_pR==='m'&&p.r>=30&&p.r<60)||(_pR==='l'&&p.r>0&&p.r<30)||(_pR==='z'&&p.r===0);
    return mq&&mr;
  }).map(p=>({...p,_t:mi>=0?p.m[mi]:p.v}));
  if(mi>=0) prods=prods.filter(p=>p._t>0);
  prods.sort((a,b)=>b._t-a._t);
  document.getElementById('pCnt').textContent=prods.length+' modelos · '+prods.reduce((a,p)=>a+p._t,0)+' und';
  document.getElementById('pList').innerHTML=prods.map(p=>`<div class="xi" onclick="TG(this)"><div class="xh">
    <span class="pnm">${p.n}</span><span style="font-size:.58rem;color:var(--mu)">${p.cat}</span>${mi<0?rb(p.r):''}
    <span style="font-family:var(--fm);font-size:.68rem;color:var(--a2)">${p._t}</span>
    <span style="font-family:var(--fm);font-size:.6rem;color:var(--mu)">${p.s} stk</span><span class="xa">▾</span></div>
    <div class="xb">${mi>=0?'<div style="font-size:.67rem;color:var(--mu)">Mes '+MES[mi]+'</div>':VP(p)}</div></div>`).join('');
}

let _iF='';
function SIF(el,f){document.querySelectorAll('[data-if]').forEach(c=>c.classList.remove('on'));el.classList.add('on');_iF=f;RI();}
function RI(){
  const q=(document.getElementById('iSrch').value||'').toLowerCase();
  const rows=P.filter(p=>p.s>0||p.v>0).filter(p=>{
    const mq=!q||p.n.toLowerCase().includes(q);
    const mf=!_iF||(_iF==='v'&&p.v>0)||(_iF==='n'&&p.v===0);
    return mq&&mf;
  }).sort((a,b)=>b.s-a.s);
  document.getElementById('iBdy').innerHTML=rows.map((p,i)=>`<tr>
    <td style="color:var(--m2);font-family:var(--fm);font-size:.58rem">${i+1}</td>
    <td><strong>${p.n}</strong></td><td style="font-size:.62rem;color:var(--mu)">${p.cat}</td>
    <td class="num" style="color:var(--a2)">${p.v||'—'}</td>
    <td class="num">${p.s}</td><td class="num">${p.vel||'—'}</td>
    <td class="num">${p.mos>=999?'—':p.mos}</td>
    <td style="font-size:.62rem">${p.v>0?'<span style="color:var(--gr)">Activo</span>':'<span style="color:var(--re)">Sin ventas</span>'}</td>
  </tr>`).join('');
}

(function(){
  const buy=(D.reorder||[]);
  const hold=P.filter(p=>p.r>=35&&p.r<75&&p.s>0&&p.v>5).slice(0,10);
  const act=P.filter(p=>p.r>0&&p.r<35&&p.s>=5).sort((a,b)=>b.s-a.s).slice(0,10);
  const liq=P.filter(p=>p.r===0&&p.s>0).sort((a,b)=>b.s-a.s).slice(0,12);
  const fi=l=>l.map(p=>`<div class="di"><strong>${p.n}</strong><small>${p.v||0}v · ${p.s||0}s ${p.vel?p.vel+'/m':''} ${p.r!=null?p.r+'%':''}</small></div>`).join('')||'<p style="color:var(--mu);font-size:.68rem">—</p>';
  document.getElementById('dBuy').innerHTML=fi(buy);
  document.getElementById('dHold').innerHTML=fi(hold);
  document.getElementById('dAct').innerHTML=fi(act);
  document.getElementById('dLiq').innerHTML=fi(liq);
  const mx=Math.max(...P.map(p=>p.v+p.s),1);
  document.getElementById('dBar').innerHTML=P.filter(p=>p.v+p.s>0).sort((a,b)=>b.v-a.v).map(p=>{
    const col=rc(p.r);
    return`<div style="margin-bottom:8px"><div style="display:flex;justify-content:space-between;font-size:.67rem;margin-bottom:3px">
      <span>${p.n}</span><span style="font-family:var(--fm);color:var(--mu)">${p.v}v · ${p.s}s</span></div>
      <div style="display:flex;height:6px;border-radius:3px;overflow:hidden;gap:1px">
        <div style="width:${Math.round(p.v/mx*100)}%;background:${col}"></div>
        <div style="width:${Math.round(p.s/mx*100)}%;background:${col};opacity:.2"></div></div></div>`;
  }).join('');
})();

(function buildRotMatrix(){
  const segs=[
    {lb:'🟢 Rota bien',sub:'>60% vendido',col:'var(--gr)',fl:p=>p.r>=60},
    {lb:'🟡 Media',sub:'30–60%',col:'var(--am)',fl:p=>p.r>=30&&p.r<60},
    {lb:'🔴 Baja',sub:'<30%',col:'var(--re)',fl:p=>p.r>0&&p.r<30},
    {lb:'⚫ Sin ventas',sub:'solo stock',col:'var(--mu)',fl:p=>p.r===0},
  ];
  const mx=Math.max(...P.map(p=>p.v+p.s),1);
  document.getElementById('rotMatrix').innerHTML=segs.map(seg=>{
    const items=P.filter(seg.fl).sort((a,b)=>b.v-a.v).slice(0,12);
    if(!items.length) return '';
    return`<div style="margin-bottom:10px;padding:10px;background:var(--s2);border-radius:10px">
      <div style="font-size:.74rem;font-weight:800;color:${seg.col}">${seg.lb} <span style="font-weight:400;color:var(--mu);font-size:.62rem">${seg.sub}</span></div>
      ${items.map(p=>`<div style="display:flex;align-items:center;gap:8px;padding:5px 0;font-size:.7rem">
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${p.n}</span>
        <div style="width:100px;height:6px;background:var(--bd);border-radius:3px;display:flex;overflow:hidden">
          <div style="width:${Math.round(p.v/mx*100)}%;background:${seg.col}"></div></div>
        <span style="font-family:var(--fm);font-size:.62rem;color:${seg.col}">${p.r}%</span></div>`).join('')}
    </div>`;
  }).join('');
})();

RR(); RP(); RI();
</script>
</body>
</html>
"""


def main():
    from datetime import datetime

    payload = build_payload()
    generated = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    html = HTML_TEMPLATE.replace("__DATA_JSON__", json.dumps(payload, ensure_ascii=False))
    html = html.replace("__GENERATED__", generated)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT_HTML} ({OUT_HTML.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
