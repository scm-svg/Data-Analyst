#!/usr/bin/env python3
"""Build / update DASHBOARD TOALLAS ESTAMPADAS.html from sales + inventory Excel files."""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path("/home/ubuntu/.cursor/projects/workspace/uploads/DASHBOARD_TOALLAS_ESTAMPADAS_29d0.html")
SALES_XLSX = Path("/home/ubuntu/.cursor/projects/workspace/uploads/VENTAS_ACTUALIZADAS_TOALLAS_0a56.xlsx")
INV_XLSX = Path("/home/ubuntu/.cursor/projects/workspace/uploads/TOALLA_ESTAMPADA_INVENTARIO_ACTUAL4_e0fa.xlsx")
OUTPUT = ROOT / "DASHBOARD TOALLAS ESTAMPADAS.html"

MESES_MAP = {
    "ENERO": "enero", "FEBRERO": "febrero", "MARZO": "marzo", "ABRIL": "abril",
    "MAYO": "mayo", "JUNIO": "junio", "JULIO": "julio", "AGOSTO": "agosto",
    "SEPTIEMBRE": "septiembre", "OCTUBRE": "octubre", "NOVIEMBRE": "noviembre", "DICIEMBRE": "diciembre",
    "enero": "enero", "febrero": "febrero", "marzo": "marzo", "abril": "abril",
    "mayo": "mayo", "junio": "junio", "julio": "julio", "agosto": "agosto",
    "septiembre": "septiembre", "octubre": "octubre", "noviembre": "noviembre", "diciembre": "diciembre",
}

STORE_MAP = {
    "GRAND PLAZ": "GRANDPLAZ", "GRANDPLAZ": "GRANDPLAZ", "Grandplaz": "GRANDPLAZ", "Grandplaz ": "GRANDPLAZ",
    "GRIETA": "LA GRIETA", "La Grieta": "LA GRIETA", "LA GRIETA": "LA GRIETA",
    "CERRO VERDE": "CERRO VERDE", "Cerro Verde": "CERRO VERDE", "Cerro Verde ": "CERRO VERDE",
    "SAMBIL CHACAO": "SAMBIL CHACAO", "Sambil Chacao": "SAMBIL CHACAO", "Sambil Chacao ": "SAMBIL CHACAO",
    "CHACAO": "SAMBIL CHACAO",
    "SAMBIL VALENCIA": "SAMBIL VALENCIA", "Sambil Valencia": "SAMBIL VALENCIA", "SAMBIL": "SAMBIL VALENCIA",
    "TOLON": "TOLON", "Tolon": "TOLON",
    "LA VELA": "LA VELA", "La Vela": "LA VELA", "VELA": "LA VELA",
    "WEB": "WEB",
    "PEDIDOS": "PEDIDOS", "Pedidos": "PEDIDOS", "CORPORATIVO": "PEDIDOS",
}

INV_LOC_MAP = {
    "CERRO VERDE": "CERRO VERDE", "CHACAO": "SAMBIL CHACAO", "GRANDPLAZ": "GRANDPLAZ",
    "GRIETA": "LA GRIETA", "SAMBIL": "SAMBIL VALENCIA", "TALLER": "TALLER",
    "TOLON": "TOLON", "VELA": "LA VELA",
}

CUTOVER = "octubre-2025"
TIPOS = ["Dama", "Caballero", "Empresa"]
MODELOS = ["TOALLA ESTAMPADA", "TOALLA ESTAMPADA 2.0"]


def norm_store(raw: str) -> str:
    s = str(raw).strip()
    return STORE_MAP.get(s, STORE_MAP.get(s.upper(), s.upper()))


def norm_mes(mes_raw, year) -> str:
    m = str(mes_raw).strip().upper()
    key = MESES_MAP.get(m, MESES_MAP.get(m.lower(), m.lower()))
    return f"{key}-{int(year)}"


def mes_sort_key(m: str) -> tuple:
    p = m.split("-")
    return (int(p[1]), list(MESES_MAP.values()).index(p[0]) if p[0] in MESES_MAP.values() else 99)


def load_template_parts():
    html = TEMPLATE.read_text(encoding="utf-8")
    m = re.search(r"var DATA=(\{.*?\});", html, re.DOTALL)
    if not m:
        raise RuntimeError("Could not find var DATA= in template")
    before = html[: m.start()]
    after = html[m.end() :]
    old_data = json.loads(m.group(1))
    return before, after, old_data


def build_gender_ratios(rows):
    ratios = defaultdict(Counter)
    overall = Counter()
    for r in rows:
        ratios[(r["o"], r["c"])][r["g"]] += r["v"]
        overall[r["g"]] += r["v"]
    default = {g: overall[g] / sum(overall.values()) for g in TIPOS}
    out = {"__default__": default}
    for k, c in ratios.items():
        t = sum(c.values())
        out[k] = {g: c[g] / t for g in TIPOS}
    return out


def split_qty(qty, ratios):
    """Split integer qty across genders by ratio."""
    if qty <= 0:
        return []
    order = sorted(TIPOS, key=lambda g: ratios.get(g, 0), reverse=True)
    parts = []
    rem = qty
    for i, g in enumerate(order):
        if i == len(order) - 1:
            n = rem
        else:
            n = int(round(qty * ratios.get(g, 0)))
            n = min(n, rem)
        if n > 0:
            parts.append((g, n))
            rem -= n
    return parts


def rows_from_sales(df, gender_ratios, cl_start):
    rows = []
    cl = cl_start
    for _, r in df.iterrows():
        store = norm_store(r["tienda / ubicación"])
        modelo = str(r["Producto"]).strip()
        color = str(r["COLOR"]).strip()
        mes = norm_mes(r["Mes"], r["Año"])
        qty = int(r["Cant. ordenada"])
        if qty <= 0:
            continue
        if store == "PEDIDOS":
            parts = [("Empresa", qty)]
        else:
            parts = split_qty(qty, gender_ratios.get((modelo, color), gender_ratios["__default__"]))
        for g, v in parts:
            rows.append({"t": store, "g": g, "c": color, "m": mes, "o": modelo, "v": v, "cl": cl})
            cl += 1
    return rows, cl


def build_inventory():
    inv = pd.read_excel(INV_XLSX)
    stock = defaultdict(int)
    stock_by_loc = defaultdict(lambda: defaultdict(int))
    stock_by_modelo = defaultdict(int)
    inv_rows = []
    stock_taller = 0

    for _, r in inv.iterrows():
        loc = str(r["Ubicación"]).strip()
        modelo = str(r["MODELO"]).strip()
        color = str(r["COLOR"]).strip()
        qty = int(r["Cantidad en inventario"])
        sku = str(r["SKU"]).strip()
        if qty <= 0:
            continue
        key = f"{modelo}/{color}"
        stock[key] += qty
        stock_by_modelo[modelo] += qty
        mapped = INV_LOC_MAP.get(loc, loc)
        stock_by_loc[mapped][key] += qty
        inv_rows.append({
            "ubicacion": mapped,
            "modelo": modelo,
            "color": color,
            "qty": qty,
            "sku": sku,
        })
        if mapped == "TALLER":
            stock_taller += qty

    return {
        "stock": dict(stock),
        "stock_by_loc": {k: dict(v) for k, v in stock_by_loc.items()},
        "stock_by_modelo": dict(stock_by_modelo),
        "stock_total": sum(stock.values()),
        "stock_taller": stock_taller,
        "inv_rows": inv_rows,
        "inv_locations": sorted(stock_by_loc.keys()),
    }


def build_designs(raw_rows, meses_order, stock):
    by_design = defaultdict(lambda: {"total": 0, "tc": Counter(), "tiendas": Counter(), "mensual": Counter(), "o": "", "first_mes": None})
    for r in raw_rows:
        d = by_design[r["c"]]
        d["total"] += r["v"]
        d["tc"][r["g"]] += r["v"]
        d["tiendas"][r["t"]] += r["v"]
        d["mensual"][r["m"]] += r["v"]
        d["o"] = r["o"]
        if d["first_mes"] is None or mes_sort_key(r["m"]) < mes_sort_key(d["first_mes"]):
            d["first_mes"] = r["m"]

    closed = meses_order[:-1] if len(meses_order) > 1 else meses_order
    last3 = closed[-3:] if len(closed) >= 3 else closed

    designs = []
    for nombre, d in by_design.items():
        modelo = d["o"]
        g2 = modelo == "TOALLA ESTAMPADA 2.0"
        stk = stock.get(f"{modelo}/{nombre}", 0)
        stk_taller = 0  # optional detail
        mensual = [d["mensual"].get(m, 0) for m in meses_order]
        v3 = sum(d["mensual"].get(m, 0) for m in last3)
        v_mes = round(v3 / max(1, len(last3)), 1)
        rot = round(d["total"] / (d["total"] + stk) * 100) if (d["total"] + stk) > 0 else 100
        cob = round(stk / v_mes, 1) if v_mes > 0 else 0.0
        fm = d["first_mes"]
        mo, y = fm.split("-")
        mo_i = list(MESES_MAP.values()).index(mo) + 1
        launch_date = f"{int(y):04d}-{mo_i:02d}-01"
        designs.append({
            "nombre": nombre,
            "gen": modelo,
            "g2": g2,
            "launch_date": launch_date,
            "launch_mes": fm,
            "total": d["total"],
            "stk": stk,
            "stk_taller": stk_taller,
            "v_mes": v_mes,
            "cob": cob,
            "rot": rot,
            "mensual": mensual,
            "tc": dict(d["tc"]),
            "tiendas": dict(d["tiendas"]),
            "meses_vida": len([x for x in mensual if x > 0]),
        })
    designs.sort(key=lambda x: x["total"], reverse=True)
    return designs


def build_production_plan(raw_rows, meses_order, stock, hs_factor, velocity_months=3):
    closed = meses_order[:-1] if len(meses_order) > 1 else meses_order
    base_months = closed[-velocity_months:] if len(closed) >= velocity_months else closed
    plan = []
    prod_curve = []
    summary = {}

    for modelo in MODELOS:
        sm_v_base = 0
        sm_stk = 0
        sm_need = {1: 0, 2: 0, 3: 0}
        sm_pt = 0

        colors = sorted({r["c"] for r in raw_rows if r["o"] == modelo})
        for color in colors:
            key = f"{modelo}/{color}"
            stk_total = stock.get(key, 0)
            v_base = sum(r["v"] for r in raw_rows if r["o"] == modelo and r["c"] == color and r["m"] in base_months)
            v_mes_base = v_base / max(1, len(base_months))
            v_mes = round(v_mes_base * hs_factor, 1)
            cob = round(stk_total / v_mes, 1) if v_mes > 0 else 99
            needs = {}
            for m in (1, 2, 3):
                need = max(0, int(round(v_mes * m - stk_total)))
                needs[m] = need
                sm_need[m] += need

            sm_v_base += v_mes_base
            sm_stk += stk_total

            prod_curve.append({
                "modelo": modelo,
                "color": color,
                "v_mes_base": round(v_mes_base, 1),
                "v_mes": v_mes,
                "stk_total": stk_total,
                "stk_pt": 0,
                "cobertura": min(cob, 99),
                "need_1m": needs[1],
                "need_2m": needs[2],
                "need_3m": needs[3],
            })

            if cob < 3 and v_mes > 0:
                plan.append({
                    "modelo": modelo,
                    "color": color,
                    "v_mes_base": round(v_mes_base, 1),
                    "v_mes": v_mes,
                    "stk": stk_total,
                    "cobertura": cob,
                    "produce": needs[2],
                })

        summary[modelo] = {
            "v_mes_base": round(sm_v_base, 1),
            "v_mes": round(sm_v_base * hs_factor, 1),
            "stk_total": sm_stk,
            "need_1m": sm_need[1],
            "need_2m": sm_need[2],
            "need_3m": sm_need[3],
            "stk_pt": sm_pt,
        }

    plan.sort(key=lambda x: x["produce"], reverse=True)
    return plan, prod_curve, summary, base_months


def compute_high_season_factor(meses_order, meses_und):
    dec_keys = [m for m in meses_order if m.startswith("diciembre-")]
    if not dec_keys:
        return 1.25
    dec_avg = sum(meses_und.get(k, 0) for k in dec_keys) / len(dec_keys)
    others = [m for m in meses_order if not m.startswith("diciembre-") and meses_und.get(m, 0) > 0]
    if not others:
        return 1.25
    # exclude launch month (low volume)
    mature = [m for m in others if meses_und.get(m, 0) > 100] or others
    base_avg = sum(meses_und[m] for m in mature) / len(mature)
    if base_avg <= 0:
        return 1.25
    factor = dec_avg / base_avg
    return round(max(1.25, min(2.0, factor)), 2)


def build_data():
    before, after, old = load_template_parts()
    gender_ratios = build_gender_ratios([r for r in old["raw_rows"] if r["m"] >= CUTOVER])
    max_cl = max((r.get("cl", 0) for r in old["raw_rows"]), default=0) + 1

    kept = [r for r in old["raw_rows"] if r["m"] < CUTOVER]
    sales = pd.read_excel(SALES_XLSX)
    new_rows, _ = rows_from_sales(sales, gender_ratios, max_cl)
    raw_rows = kept + new_rows

    meses_order = sorted({r["m"] for r in raw_rows}, key=mes_sort_key)
    meses_und = Counter()
    for r in raw_rows:
        meses_und[r["m"]] += r["v"]
    meses_und = dict(meses_und)

    inv = build_inventory()
    designs = build_designs(raw_rows, meses_order, inv["stock"])

    tipo_stats = {}
    for t in TIPOS:
        und = sum(r["v"] for r in raw_rows if r["g"] == t)
        cli = len({r["cl"] for r in raw_rows if r["g"] == t})
        tipo_stats[t] = {"und": und, "cli": cli}

    tiendas = sorted({r["t"] for r in raw_rows if r["t"] != "PEDIDOS"})
    colores = sorted({r["c"] for r in raw_rows})
    all_stores = sorted(set(tiendas))

    total = sum(r["v"] for r in raw_rows)
    corp = sum(r["v"] for r in raw_rows if r["t"] == "PEDIDOS")
    corp_pct = round(corp / total * 1000) / 10 if total else 0

    hs_factor = compute_high_season_factor(meses_order, meses_und)
    plan, prod_curve, summary_prod, vel_months = build_production_plan(
        raw_rows, meses_order, inv["stock"], hs_factor
    )

    gen1 = sum(1 for d in designs if not d["g2"])
    gen2 = sum(1 for d in designs if d["g2"])

    first_lbl = meses_order[0].split("-")
    last_lbl = meses_order[-1].split("-")
    date_range = f"{first_lbl[0].capitalize()} {first_lbl[1]} — {last_lbl[0].capitalize()} {last_lbl[1]}"

    data = {
        "raw_rows": raw_rows,
        "clientes": old.get("clientes", {}),
        "stock": inv["stock"],
        "stock_by_loc": inv["stock_by_loc"],
        "stock_by_modelo": inv["stock_by_modelo"],
        "stock_total": inv["stock_total"],
        "stock_taller": inv["stock_taller"],
        "inv_rows": inv["inv_rows"],
        "inv_locations": inv["inv_locations"],
        "meses_order": meses_order,
        "meses_und": meses_und,
        "filtros": {
            "tiendas": sorted(set(list(all_stores) + ["PEDIDOS"])),
            "tipos": TIPOS,
            "colores": colores,
            "modelos": MODELOS,
        },
        "all_stores": all_stores,
        "total": total,
        "clientes_total": len({r["cl"] for r in raw_rows}),
        "tipo_stats": tipo_stats,
        "designs": designs,
        "gen1_count": gen1,
        "gen2_count": gen2,
        "es_parcial": True,
        "high_season_factor": hs_factor,
        "high_season_label": "Diciembre · temporada alta",
        "corp_total": corp,
        "corp_pct": corp_pct,
        "production_plan": plan,
        "prod_curve": prod_curve,
        "summary_prod": summary_prod,
        "velocity_months": vel_months,
        "velocity_months_count": len(vel_months),
        "velocity_months_label": ", ".join(m.replace("-", " ").title() for m in vel_months),
        "new_stores": ["BARQUISIMETO"],
        "new_store_caps": {
            "BARQUISIMETO": {"base": "LA GRIETA", "mult": 1, "label": "1× LA GRIETA"},
        },
        "date_range": date_range,
    }
    return before, after, data


DECISIONES_HTML = """
<!-- ══ DECISIONES ══ -->
<div class="sec" id="sec-decisiones">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap">
    <div style="font-family:var(--fh);font-size:0.82rem;font-weight:700;color:var(--mu)">📅 Meses base para proyección:</div>
    <div style="display:flex;gap:6px">
      <button onclick="setDecMeses(1)" id="dm1" class="dmb" style="background:var(--s2);color:var(--mu);border:1px solid var(--brd);border-radius:20px;padding:4px 12px;font-size:0.73rem;cursor:pointer;font-family:var(--fb)">1 mes</button>
      <button onclick="setDecMeses(2)" id="dm2" class="dmb" style="background:var(--ac);color:#fff;border:1px solid var(--ac);border-radius:20px;padding:4px 12px;font-size:0.73rem;cursor:pointer;font-family:var(--fb)">2 meses</button>
      <button onclick="setDecMeses(3)" id="dm3" class="dmb" style="background:var(--s2);color:var(--mu);border:1px solid var(--brd);border-radius:20px;padding:4px 12px;font-size:0.73rem;cursor:pointer;font-family:var(--fb)">3 meses</button>
    </div>
    <div style="font-size:0.7rem;color:var(--mu2)">Rotación × <strong style="color:var(--a2)" id="hsFactorLabel">1.25</strong> temporada alta · 🏢 Corporativo: <strong id="corpPctLabel">0%</strong></div>
  </div>
  <div class="tkpis" id="decKpis"></div>
  <div class="g2">
    <div class="card" style="grid-column:1/-1">
      <h3>🏭 Curva de Producción por Colección</h3>
      <div class="sub">Cobertura (meses) y producción neta por diseño · ajustado temporada alta Diciembre</div>
      <div id="propGrid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px;margin-top:10px"></div>
    </div>
  </div>
  <div class="card g1">
    <h3>🏪 Reabastecimiento por Tienda</h3>
    <div class="sub">Distribución sugerida · <span style="color:#f97316">BARQUISIMETO 1× LA GRIETA · factor temporada alta ×<span id="hsFactorLabel2">1.25</span></span></div>
    <div id="reabastGrid" style="margin-top:10px"></div>
  </div>
</div>
"""

DECISIONES_JS = r"""
// ── DECISIONES ──
var _decMeses=2;
var _pgX={};
var REAL_STORES=DATA.all_stores;
var NEW_STORES=DATA.new_stores||['BARQUISIMETO'];
var NEW_STORE_CAPS=DATA.new_store_caps||{'BARQUISIMETO':{base:'LA GRIETA',mult:1,label:'1× LA GRIETA'}};

function setDecMeses(n){
  _decMeses=n;
  ['dm1','dm2','dm3'].forEach(function(id,i){
    var b=document.getElementById(id);if(!b)return;
    var a=(i+1)===n;b.style.background=a?'var(--ac)':'var(--s2)';b.style.color=a?'#fff':'var(--mu)';b.style.borderColor=a?'var(--ac)':'var(--brd)';
  });
  rDecisiones();
}
function getBaseMonths(meses){
  var m=DATA.meses_order.slice();
  if(DATA.es_parcial)m=m.slice(0,-1);
  return m.slice(-meses);
}
function getLF(modelo,meses){
  var mO=getBaseMonths(meses);
  var r=DATA.raw_rows.filter(function(r){return r.o===modelo&&mO.indexOf(r.m)>=0;});
  var hs=DATA.high_season_factor||1.25;
  return mO.length?Math.round(r.reduce(function(a,x){return a+x.v;},0)/mO.length*hs):0;
}
function getSW(rows,modelo,meses){
  var mO=getBaseMonths(meses||_decMeses||2);
  var f=rows.filter(function(r){return r.o===modelo&&mO.indexOf(r.m)>=0;});
  var tot=f.reduce(function(a,r){return a+r.v;},0),shares={};
  REAL_STORES.forEach(function(s){var sv=f.filter(function(r){return r.t===s;}).reduce(function(a,r){return a+r.v;},0);shares[s]=tot>0?sv/tot:0;});
  NEW_STORES.forEach(function(ns){shares[ns]=getNewStoreShare(ns,shares);});
  return{total:tot,shares:shares};
}
function getNewStoreShare(store,realShares){
  var cap=NEW_STORE_CAPS[store];if(!cap)return 0;
  return(realShares[cap.base]||0)*cap.mult;
}
function gDesignStk(modelo,color){return DATA.stock[modelo+'/'+color]||0;}
document.addEventListener('click',function(e){
  var pg=e.target.closest('[data-pguid]');
  if(pg){var uid=pg.getAttribute('data-pguid');_pgX[uid]=!_pgX[uid];var d=document.getElementById(uid);if(d)d.style.display=_pgX[uid]?'block':'none';}
});

function rDecisiones(){
  var meses=_decMeses||2;
  var hs=DATA.high_season_factor||1.25;
  var hsLbl=document.getElementById('hsFactorLabel');if(hsLbl)hsLbl.textContent=hs;
  var hsLbl2=document.getElementById('hsFactorLabel2');if(hsLbl2)hsLbl2.textContent=hs;
  var corpLbl=document.getElementById('corpPctLabel');if(corpLbl)corpLbl.textContent=(DATA.corp_pct||0)+'% ('+(DATA.corp_total||0).toLocaleString()+' und)';

  var plan=(DATA.production_plan||[]).filter(function(r){return(!_modelo||r.modelo===_modelo);});
  var totalProduce=plan.reduce(function(a,r){return a+r.produce;},0);
  var totalVel=plan.reduce(function(a,r){return a+r.v_mes;},0);
  var totalStk=plan.reduce(function(a,r){return a+r.stk;},0);
  var cobGen=totalVel>0?Math.round(totalStk/totalVel*10)/10:0;
  var velLbl=DATA.velocity_months_label||'últimos meses cerrados';

  document.getElementById('decKpis').innerHTML=
    '<div class="tkpi"><div class="tv">'+Math.round(totalVel)+'</div><div class="tl">Rotación ajustada</div><div class="ts">Base × '+hs+' · '+velLbl+'</div></div>'
    +'<div class="tkpi"><div class="tv" style="color:#ffc107">'+totalStk.toLocaleString()+'</div><div class="tl">Stock actual</div><div class="ts">Taller: '+(DATA.stock_taller||0).toLocaleString()+' und</div></div>'
    +'<div class="tkpi"><div class="tv">'+cobGen+'m</div><div class="tl">Cobertura prom.</div><div class="ts">Meses hasta agotarse</div></div>'
    +'<div class="tkpi"><div class="tv" style="color:'+(totalProduce>0?'#f59e0b':'#10b981')+'">'+totalProduce+'</div><div class="tl">Producir ('+meses+'m)</div><div class="ts">Diseños con cob &lt; 3m</div></div>'
    +'<div class="tkpi"><div class="tv" style="color:#f75b8a">'+(DATA.corp_pct||0)+'%</div><div class="tl">Pedidos corp.</div><div class="ts">'+(DATA.corp_total||0).toLocaleString()+' und histórico</div></div>'
    +'<div class="tkpi"><div class="tv" style="color:#f97316">🆕 BQTO</div><div class="tl">Barquisimeto</div><div class="ts">Proyección 1× LA GRIETA</div></div>';

  var pgEl=document.getElementById('propGrid');
  if(pgEl){
    pgEl.innerHTML='';
    var modelList=_modelo?[_modelo]:DATA.filtros.modelos;
    modelList.forEach(function(mod){
      var smry=DATA.summary_prod[mod];if(!smry)return;
      var rows=DATA.prod_curve.filter(function(r){return r.modelo===mod;});
      var totalNeed=meses===1?smry.need_1m:meses===2?smry.need_2m:smry.need_3m;
      var cob=smry.v_mes>0?(smry.stk_total/smry.v_mes).toFixed(1):0;
      var cobColor=cob<1?'#ef4444':cob<2?'#f59e0b':cob<3?'#3b82f6':'#10b981';
      var sorted=rows.slice().sort(function(a,b){return b.v_mes-a.v_mes;});
      var colorsHtml=sorted.map(function(r){
        var need=meses===1?r.need_1m:meses===2?r.need_2m:r.need_3m;
        var tc=r.cobertura<1?'#ef4444':r.cobertura<2?'#f59e0b':r.cobertura<3?'#3b82f6':'#10b981';
        return '<div style="display:flex;align-items:center;gap:6px;padding:3px 8px;background:rgba(0,0,0,.15);border-radius:5px;margin-bottom:2px">'
          +'<span class="chip" style="background:'+cn(r.color)+'"></span>'
          +'<span style="font-size:.72rem;font-weight:600;width:90px">'+r.color+'</span>'
          +'<span style="font-size:.65rem;color:var(--mu2)">'+r.v_mes.toFixed(1)+'/mes</span>'
          +'<span style="font-size:.65rem;color:var(--mu2)">stk '+r.stk_total+'</span>'
          +'<span style="font-size:.65rem;color:'+tc+';font-weight:700">'+r.cobertura.toFixed(1)+'m</span>'
          +(need>0?'<span style="margin-left:auto;background:rgba(245,158,11,.15);color:#f59e0b;border-radius:4px;padding:1px 7px;font-size:.63rem;font-weight:700">+'+need+' prod</span>':'<span style="margin-left:auto;font-size:.63rem;color:#10b981">✓ OK</span>')
          +'</div>';
      }).join('');
      var card=document.createElement('div');
      card.className='card';
      card.innerHTML='<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">'
        +'<h3 style="margin:0">'+(MSHORT[mod]||mod)+'</h3>'
        +'<span style="font-size:.72rem;color:var(--mu2)">'+smry.v_mes.toFixed(0)+'/mes · stk '+smry.stk_total+'</span>'
        +'<span style="margin-left:auto;font-size:.78rem;font-weight:800;color:'+cobColor+'">'+cob+' meses cobertura</span></div>'
        +'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px">'
        +'<div style="text-align:center;background:rgba(99,102,241,.1);border-radius:8px;padding:8px"><div style="font-size:1.1rem;font-weight:800;color:#818cf8">'+smry.need_1m+'</div><div style="font-size:.63rem;color:var(--mu)">Producir 1 mes</div></div>'
        +'<div style="text-align:center;background:rgba(245,158,11,.1);border-radius:8px;padding:8px"><div style="font-size:1.1rem;font-weight:800;color:#f59e0b">'+smry.need_2m+'</div><div style="font-size:.63rem;color:var(--mu)">Producir 2 meses</div></div>'
        +'<div style="text-align:center;background:rgba(244,63,94,.1);border-radius:8px;padding:8px"><div style="font-size:1.1rem;font-weight:800;color:#f43f5e">'+smry.need_3m+'</div><div style="font-size:.63rem;color:var(--mu)">Producir 3 meses</div></div></div>'
        +'<div style="font-size:.67rem;color:var(--mu2);margin-bottom:8px">📦 PT taller: '+(DATA.stock_taller||0).toLocaleString()+' und · Velocidad: '+velLbl+' × '+hs+' (temporada alta)</div>'
        +'<div>'+colorsHtml+'</div>';
      pgEl.appendChild(card);
    });
  }

  var reEl=document.getElementById('reabastGrid');
  if(reEl){
    var allRows=DATA.raw_rows.filter(function(r){return(!_modelo||r.o===_modelo);});
    var stores=REAL_STORES.concat(NEW_STORES);
    var modelList2=_modelo?[_modelo]:DATA.filtros.modelos;
    var h='<table class="ct"><thead><tr><th>Tienda</th><th>% hist.</th><th>Und/mes proj.</th><th>Top diseños</th></tr></thead><tbody>';
    modelList2.forEach(function(mod){
      var lf=getLF(mod,meses);
      var sw=getSW(allRows,mod,meses);
      h+='<tr><td colspan="4" style="background:var(--s2);font-weight:700;color:var(--ac);padding:8px">'+(MSHORT[mod]||mod)+' · forecast '+lf+' und/mes</td></tr>';
      stores.forEach(function(s){
        var sh=sw.shares[s]||0;
        var proj=Math.round(lf*sh);
        if(proj<=0&&NEW_STORES.indexOf(s)<0)return;
        var isNew=NEW_STORES.indexOf(s)>=0;
        var top=allRows.filter(function(r){return r.t===s&&r.o===mod;});
        var cM={};top.forEach(function(r){cM[r.c]=(cM[r.c]||0)+r.v;});
        var topC=Object.keys(cM).sort(function(a,b){return cM[b]-cM[a];}).slice(0,3).join(', ')||'—';
        h+='<tr><td>'+(isNew?'🆕 ':'')+s+(isNew?' <span style="color:#f97316;font-size:.62rem">'+((NEW_STORE_CAPS[s]||{}).label||'')+'</span>':'')+'</td>'
          +'<td>'+(Math.round(sh*1000)/10)+'%</td><td class="rn">'+proj+'</td><td style="font-size:.68rem">'+topC+'</td></tr>';
      });
    });
    reEl.innerHTML=h+'</tbody></table>';
  }
}
"""


def patch_html(before: str, after: str, data: dict) -> str:
    # Header date range
    dr = data["date_range"]
    before = before.replace(
        "May 2025 — Jul 2026",
        dr.replace("Mayo", "May").replace("Septiembre", "Sep").replace("Agosto", "Ago").replace("Julio", "Jul").replace("Junio", "Jun"),
    )
    before = re.sub(
        r"Dashboard de Ventas &nbsp;·&nbsp; [^<]+",
        f"Dashboard de Ventas &nbsp;·&nbsp; {dr} &nbsp;·&nbsp; Incluye género del cliente",
        before,
        count=1,
    )

    # Add Decisiones tab
    before = before.replace(
        '<button class="tab" onclick="st(\'cliente\')">👥 Tipo Cliente</button>',
        '<button class="tab" onclick="st(\'cliente\')">👥 Tipo Cliente</button>\n  <button class="tab" onclick="st(\'decisiones\')">💡 Decisiones</button>',
    )

    # Insert decisiones section inside .content, before its closing tag
    before = before.replace(
        '</div>\n\n</div>\n<div class="footer">Toallas Estampadas',
        '</div>\n\n' + DECISIONES_HTML + '\n</div>\n<div class="footer">Toallas Estampadas',
    )

    # Update footer
    before = re.sub(
        r'<div class="footer">Toallas Estampadas · Dashboard de Ventas con Género del Cliente · [^<]+</div>',
        f'<div class="footer">Toallas Estampadas · Dashboard de Ventas con Género del Cliente · {dr} · Somos Cuadro</div>',
        before,
    )

    # Patch JS: TABS and rs()
    after = after.replace(
        "var TABS=['resumen','colores','tiendas','lanzamientos','cliente'];",
        "var TABS=['resumen','colores','tiendas','lanzamientos','cliente','decisiones'];",
    )
    after = after.replace(
        "else if(n==='cliente')rCliente();",
        "else if(n==='cliente')rCliente();else if(n==='decisiones')rDecisiones();",
    )

    # Update renderAlertas partial month message
    last_m = data["meses_order"][-1].replace("-", " ").title()
    after = after.replace(
        "alerts.push({type:'info',text:'📅 Julio 2026 con datos parciales'});",
        f"alerts.push({{type:'info',text:'📅 {last_m} con datos parciales'}});",
    )
    after = after.replace(
        "'<div class=\"ksub\">sin cambios</div></div>'+",
        "'<div class=\"ksub\">actualizado</div></div>'+",
    )

    # Add corporate alert
    after = after.replace(
        "alerts.push({type:'info',text:'📦 Stock Taller:",
        f"alerts.push({{type:'warn',text:'🏢 Pedidos corporativos: '+(DATA.corp_pct||0)+'% del histórico ('+(DATA.corp_total||0).toLocaleString()+' und) — picos en Ago 2026'}});\n  alerts.push({{type:'info',text:'📦 Stock Taller:",
    )

    # Insert decisiones JS before export section
    after = after.replace("/* ── EXPORT / FULLSCREEN ── */", DECISIONES_JS + "\n/* ── EXPORT / FULLSCREEN ── */")

    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return before + "var DATA=" + data_json + ";" + after


def main():
    before, after, data = build_data()
    html = patch_html(before, after, data)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(f"  rows: {len(data['raw_rows'])}")
    print(f"  months: {data['meses_order'][0]} → {data['meses_order'][-1]}")
    print(f"  stock: {data['stock_total']}")
    print(f"  corp: {data['corp_pct']}%")
    print(f"  hs_factor: {data['high_season_factor']}")


if __name__ == "__main__":
    main()
