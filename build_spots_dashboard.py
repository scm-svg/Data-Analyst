#!/usr/bin/env python3
"""Rebuild SPOTS DASHBOARD.html from ventas + inventario CSV."""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

HTML_PATH = Path(__file__).resolve().parent / "SPOTS DASHBOARD.html"
VENTAS_PATH = Path(__file__).resolve().parent / "data" / "spots_ventas.csv"
INV_PATH = Path(__file__).resolve().parent / "data" / "spots_inventario.csv"

HIGH_SEASON_FACTOR = 1.4
LEAD_MONTHS = 3
PARTIAL_MONTH = "septiembre-2026"
VELOCITY_MONTHS_COUNT = 3
BASE_STORE = "VELA"
DECISION_STORES = ["VELA"]
EXPANSION_STORES = ["VALENCIA", "BARQUISIMETO"]
EXPANSION_CAPS = {
    "VALENCIA": {"mult": 1.0, "label": "1× VELA Margarita"},
    "BARQUISIMETO": {"mult": 0.85, "label": "0.85× VELA"},
}
ADDITIONAL_COLOR = "Color adicional"
ADDITIONAL_COLOR_FACTOR = 0.70
MESES_ORDER = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
STORE_MAP = {
    "la vela": "VELA",
    "vela": "VELA",
    "pedidos": "PEDIDOS",
    "web": "WEB",
    "taller": "TALLER",
}


def mes_sort_key(mes: str):
    part, year = mes.rsplit("-", 1)
    return (int(year), MESES_ORDER.index(part))


def norm_store(name: str) -> str:
    key = (name or "").strip().lower()
    return STORE_MAP.get(key, (name or "").strip().upper().replace(" ", "_"))


def norm_diseno(val: str, modelo: str) -> str:
    d = (val or "").strip()
    if not d and "MANGA LARGA" in modelo:
        return "Manga Larga"
    return d or "Sin diseño"


def stock_key(modelo, genero, color, diseno, talla) -> str:
    return f"{modelo}/{genero}/{color}/{diseno}/{talla}"


def load_ventas() -> list:
    rows = []
    with VENTAS_PATH.open(encoding="latin-1") as f:
        for r in csv.DictReader(f, delimiter=";"):
            mes = (r.get("fecha (mes año)") or "").strip()
            if not mes:
                continue
            qty = int(float(r.get("Cant. ordenada") or 0))
            if qty == 0:
                continue
            modelo = (r.get("modelo") or "").strip()
            rows.append({
                "tienda": norm_store(r.get("tienda / ubicación", "")),
                "genero": (r.get("GENERO") or "").strip(),
                "color": (r.get("COLOR") or "").strip(),
                "diseno": norm_diseno(r.get("DISEÑO"), modelo),
                "talla": (r.get("TALLA") or "").strip(),
                "mes": mes,
                "modelo": modelo,
                "sku": (r.get("SKU") or "").strip(),
                "v": qty,
            })
    return rows


def load_inventario() -> list:
    rows = []
    with INV_PATH.open(encoding="latin-1") as f:
        for r in csv.DictReader(f, delimiter=";"):
            qty = int(float(r.get("Cantidad en inventario") or 0))
            if qty <= 0:
                continue
            modelo = (r.get("MODELO") or "").strip()
            rows.append({
                "ubicacion": norm_store(r.get("Ubicación", "")),
                "modelo": modelo,
                "genero": (r.get("GENERO") or "").strip(),
                "color": (r.get("COLOR") or "").strip(),
                "diseno": norm_diseno(r.get("DISEÑO"), modelo),
                "talla": (r.get("TALLA") or "").strip(),
                "qty": qty,
                "sku": (r.get("SKU") or "").strip(),
            })
    return rows


def velocity_months(meses_order: list) -> list:
    if PARTIAL_MONTH in meses_order:
        i = meses_order.index(PARTIAL_MONTH)
        if i >= VELOCITY_MONTHS_COUNT:
            return meses_order[i - VELOCITY_MONTHS_COUNT : i]
    return meses_order[-VELOCITY_MONTHS_COUNT:]


def base_velocity(rows, modelo, genero, color, diseno, talla, vel_months):
    qty = sum(
        r["v"] for r in rows
        if r["modelo"] == modelo and r["genero"] == genero and r["color"] == color
        and r["diseno"] == diseno and r["talla"] == talla and r["mes"] in vel_months
    )
    return qty / len(vel_months) if vel_months else 0.0


def compute_prod_curve(raw_rows, stock, stock_taller, vel_months):
    store_rows = [r for r in raw_rows if r["tienda"] == BASE_STORE]
    prod_rows = []
    combos = sorted({
        (r["modelo"], r["genero"], r["color"], r["diseno"], r["talla"])
        for r in store_rows
    })
    for modelo, genero, color, diseno, talla in combos:
        base_v = base_velocity(store_rows, modelo, genero, color, diseno, talla, vel_months)
        v_mes_base = round(base_v, 1)
        v_mes = round(base_v * HIGH_SEASON_FACTOR, 1)
        key = stock_key(modelo, genero, color, diseno, talla)
        stk = int(stock.get(key, 0))
        stk_pt = int(stock_taller.get(key, 0))
        cob = round(stk / v_mes, 1) if v_mes > 0 else 999
        need_1m = max(0, round(v_mes * 1 - stk))
        need_2m = max(0, round(v_mes * 2 - stk))
        need_3m = max(0, round(v_mes * LEAD_MONTHS - stk))
        prod_rows.append({
            "modelo": modelo,
            "genero": genero,
            "color": color,
            "diseno": diseno,
            "talla": talla,
            "v3m": sum(
                r["v"] for r in store_rows
                if r["modelo"] == modelo and r["genero"] == genero and r["color"] == color
                and r["diseno"] == diseno and r["talla"] == talla and r["mes"] in vel_months
            ),
            "v_mes_base": v_mes_base,
            "v_mes": v_mes,
            "stk_total": stk,
            "stk_pt": stk_pt,
            "cobertura": cob,
            "need_1m": need_1m,
            "need_2m": need_2m,
            "need_3m": need_3m,
        })

    summary = {}
    for modelo in sorted({r["modelo"] for r in prod_rows}):
        rows_m = [r for r in prod_rows if r["modelo"] == modelo]
        v_mes = sum(r["v_mes"] for r in rows_m)
        stk = sum(r["stk_total"] for r in rows_m)
        summary[modelo] = {
            "v_mes_base": round(sum(r["v_mes_base"] for r in rows_m), 1),
            "v_mes": round(v_mes, 1),
            "stk_total": stk,
            "stk_pt": sum(r["stk_pt"] for r in rows_m),
            "need_1m": sum(r["need_1m"] for r in rows_m),
            "need_2m": sum(r["need_2m"] for r in rows_m),
            "need_3m": sum(r["need_3m"] for r in rows_m),
        }
    return prod_rows, summary


def compute_expansion(raw_rows, vel_months, prod_rows):
    """Proyección expansión: Blanco desde VELA + color adicional al 70%."""
    store_rows = [r for r in raw_rows if r["tienda"] == BASE_STORE]
    expansion = {
        "base_store": BASE_STORE,
        "stores": EXPANSION_STORES,
        "additional_color": ADDITIONAL_COLOR,
        "additional_color_factor": ADDITIONAL_COLOR_FACTOR,
        "high_season_factor": HIGH_SEASON_FACTOR,
        "lead_months": LEAD_MONTHS,
        "by_store": [],
        "by_color": [],
        "total_blanco": 0,
        "total_adicional": 0,
        "total_expansion": 0,
    }

    # Agrupar velocidad Blanco por modelo/genero/diseno/talla desde VELA
    groups = defaultdict(float)
    for r in store_rows:
        if r["color"].lower() != "blanco":
            continue
        if r["mes"] not in vel_months:
            continue
        k = (r["modelo"], r["genero"], r["diseno"], r["talla"])
        groups[k] += r["v"] / len(vel_months)

    talla_mix = {}
    total_v = sum(groups.values())
    for k, v in groups.items():
        talla_mix[k] = v / total_v if total_v > 0 else 0

    for store in EXPANSION_STORES:
        cap = EXPANSION_CAPS[store]
        mult = cap.get("mult", 1)
        store_blanco = 0
        store_adicional = 0
        skus = []
        for (modelo, genero, diseno, talla), v_base in sorted(groups.items()):
            v_adj = round(v_base * HIGH_SEASON_FACTOR * mult, 2)
            blanco_3m = max(0, round(v_adj * LEAD_MONTHS))
            adicional_3m = max(0, round(v_adj * ADDITIONAL_COLOR_FACTOR * LEAD_MONTHS))
            store_blanco += blanco_3m
            store_adicional += adicional_3m
            if blanco_3m > 0:
                skus.append({
                    "modelo": modelo,
                    "genero": genero,
                    "diseno": diseno,
                    "talla": talla,
                    "color": "Blanco",
                    "v_mes": v_adj,
                    "need_3m": blanco_3m,
                })
            if adicional_3m > 0:
                skus.append({
                    "modelo": modelo,
                    "genero": genero,
                    "diseno": diseno,
                    "talla": talla,
                    "color": ADDITIONAL_COLOR,
                    "v_mes": round(v_adj * ADDITIONAL_COLOR_FACTOR, 2),
                    "need_3m": adicional_3m,
                })
        expansion["by_store"].append({
            "store": store,
            "label": cap.get("label", ""),
            "blanco": store_blanco,
            "adicional": store_adicional,
            "total": store_blanco + store_adicional,
            "skus": skus,
        })
        expansion["total_blanco"] += store_blanco
        expansion["total_adicional"] += store_adicional

    expansion["total_expansion"] = expansion["total_blanco"] + expansion["total_adicional"]
    expansion["by_color"] = [
        {"color": "Blanco", "need_3m": expansion["total_blanco"]},
        {"color": ADDITIONAL_COLOR, "need_3m": expansion["total_adicional"],
         "note": f"{int(ADDITIONAL_COLOR_FACTOR * 100)}% vs Blanco"},
    ]
    expansion["nota"] = (
        f"Base {BASE_STORE} · vel. {', '.join(velocity_months_label(vel_months))} "
        f"× {HIGH_SEASON_FACTOR} temp. alta · {LEAD_MONTHS}m cobertura · "
        f"{ADDITIONAL_COLOR} al {int(ADDITIONAL_COLOR_FACTOR * 100)}% de Blanco"
    )
    return expansion


def velocity_months_label(vel_months):
    short = {
        "enero": "Jun", "febrero": "Feb", "marzo": "Mar", "abril": "Abr",
        "mayo": "May", "junio": "Jun", "julio": "Jul", "agosto": "Ago",
        "septiembre": "Sep", "octubre": "Oct", "noviembre": "Nov", "diciembre": "Dic",
    }
    return [f"{short.get(m.split('-')[0], m[:3])} {m[-2:]}" for m in vel_months]


def rebuild_data() -> dict:
    raw_rows = load_ventas()
    inv_rows = load_inventario()

    meses_order = sorted({r["mes"] for r in raw_rows}, key=mes_sort_key)
    meses_und = defaultdict(int)
    for r in raw_rows:
        meses_und[r["mes"]] += r["v"]

    stock = defaultdict(int)
    stock_by_loc = defaultdict(lambda: defaultdict(int))
    stock_taller = defaultdict(int)
    for r in inv_rows:
        key = stock_key(r["modelo"], r["genero"], r["color"], r["diseno"], r["talla"])
        stock[key] += r["qty"]
        stock_by_loc[r["ubicacion"]][key] += r["qty"]
        if r["ubicacion"] == "TALLER":
            stock_taller[key] += r["qty"]

    vel_months = velocity_months(meses_order)
    prod_curve, summary_prod = compute_prod_curve(raw_rows, stock, stock_taller, vel_months)
    expansion = compute_expansion(raw_rows, vel_months, prod_curve)

    tiendas = sorted({r["tienda"] for r in raw_rows})
    real_stores = sorted({r["tienda"] for r in raw_rows if r["tienda"] not in {"PEDIDOS", "WEB", "TALLER"}})
    stock_by_modelo = defaultdict(int)
    for r in inv_rows:
        stock_by_modelo[r["modelo"]] += r["qty"]

    first_m = meses_order[0].split("-")[0].capitalize() if meses_order else ""
    last_m = meses_order[-1].split("-")[0].capitalize() if meses_order else ""
    date_range = f"{first_m} 2026 — {last_m} 2026"

    return {
        "nombre": "SPOTS",
        "periodo": date_range,
        "raw_rows": raw_rows,
        "inv_rows": inv_rows,
        "stock": dict(stock),
        "stock_by_loc": {k: dict(v) for k, v in stock_by_loc.items()},
        "stock_by_modelo": dict(stock_by_modelo),
        "meses_order": meses_order,
        "meses_und": dict(meses_und),
        "filtros": {
            "tiendas": tiendas,
            "generos": sorted({r["genero"] for r in raw_rows}),
            "colores": sorted({r["color"] for r in raw_rows}),
            "disenos": sorted({r["diseno"] for r in raw_rows}),
            "modelos": sorted({r["modelo"] for r in raw_rows}),
        },
        "es_parcial": PARTIAL_MONTH in meses_order,
        "partial_month": PARTIAL_MONTH,
        "stock_total": sum(stock.values()),
        "stock_pt_total": sum(stock_taller.values()),
        "total": sum(r["v"] for r in raw_rows),
        "all_stores": real_stores,
        "decision_stores": DECISION_STORES,
        "inv_locations": sorted(stock_by_loc.keys()),
        "prod_curve": prod_curve,
        "summary_prod": summary_prod,
        "high_season_factor": HIGH_SEASON_FACTOR,
        "velocity_months": vel_months,
        "velocity_months_label": " · ".join(velocity_months_label(vel_months)),
        "expansion": expansion,
        "expansion_stores": EXPANSION_STORES,
        "expansion_caps": EXPANSION_CAPS,
        "additional_color": ADDITIONAL_COLOR,
        "additional_color_factor": ADDITIONAL_COLOR_FACTOR,
        "date_range": date_range,
    }


def build_html(data: dict) -> str:
    html = HTML_PATH.read_text(encoding="utf-8")
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = re.sub(
        r"var DATA=\{.*?\};",
        f"var DATA={data_json};",
        html,
        count=1,
        flags=re.DOTALL,
    )
    return html


def patch_html(html: str, data: dict) -> str:
    dr = data["date_range"]
    html = html.replace(
        "<p>Dashboard de Ventas · Junio 2026 — Julio 2026 · Manga Corta &amp; Manga Larga</p>",
        f"<p>Dashboard de Ventas · {dr} · Manga Corta &amp; Manga Larga · foco tienda {BASE_STORE}</p>",
    )
    html = html.replace(
        '<div class="footer">Colección Spots · Dashboard de Ventas · Junio 2026 — Julio 2026</div>',
        f'<div class="footer">Colección Spots · Dashboard de Ventas · {dr}</div>',
    )

    # Diseño filter in fbar
    if 'id="fD"' not in html:
        html = html.replace(
            '<div class="fg"><label>Color</label><select id="fC" onchange="af()"><option value="">Todos</option></select></div>',
            '<div class="fg"><label>Color</label><select id="fC" onchange="af()"><option value="">Todos</option></select></div>\n'
            '  <div class="fg"><label>Diseño</label><select id="fD" onchange="af()"><option value="">Todos</option></select></div>',
        )

    # Replace NEW_STORES config
    html = re.sub(
        r"var NEW_STORES=\['MARGARITA','TOLON'\];",
        "var NEW_STORES=DATA.expansion_stores||['VALENCIA','BARQUISIMETO'];",
        html,
    )
    html = re.sub(
        r"var NEW_STORE_CAPS=\{[^;]+\};",
        "var NEW_STORE_CAPS=DATA.expansion_caps||{};",
        html,
        count=2,
    )

    # gf() add diseno
    html = html.replace(
        "function gf(){return{tienda:document.getElementById('fT').value,genero:document.getElementById('fG').value,color:document.getElementById('fC').value};}",
        "function gf(){return{tienda:document.getElementById('fT').value,genero:document.getElementById('fG').value,color:document.getElementById('fC').value,diseno:(document.getElementById('fD')||{}).value||''};}",
    )

    # fr() add diseno filter
    html = html.replace(
        "(!f.color||r.color===f.color)&&mA.indexOf(r.mes)>=0;",
        "(!f.color||r.color===f.color)&&(!f.diseno||r.diseno===f.diseno)&&mA.indexOf(r.mes)>=0;",
    )

    # af() badge
    html = html.replace(
        "var active=f.tienda||f.genero||f.color||_per!=='all'||_modelo;",
        "var active=f.tienda||f.genero||f.color||f.diseno||_per!=='all'||_modelo;",
    )

    # rf() reset diseno
    html = html.replace(
        "document.getElementById('fC').value='';_modelo='';",
        "document.getElementById('fC').value='';if(document.getElementById('fD'))document.getElementById('fD').value='';_modelo='';",
    )

    # getFilteredInvRows diseno
    html = html.replace(
        "(!f.color||r.color===f.color);",
        "(!f.color||r.color===f.color)&&(!f.diseno||r.diseno===f.diseno);",
    )

    # tallasScope diseno (both occurrences)
    diseno_guard = (
        "if(f.color&&r.color!==f.color)return;\n"
        "    if(f.diseno&&r.diseno!==f.diseno)return;"
    )
    html = html.replace("if(f.color&&r.color!==f.color)return;", diseno_guard, 2)

    # salesTallaMap diseno - use diseno in key
    html = html.replace(
        "var k=r.genero+'|'+r.color+'|'+r.talla;",
        "var k=r.genero+'|'+r.color+'|'+(r.diseno||'')+'|'+r.talla;",
    )

    # inv matrix row key includes diseno
    html = html.replace(
        "var rowKey=r.genero+' · '+r.color;",
        "var rowKey=r.genero+' · '+r.color+' · '+(r.diseno||'');",
    )
    html = html.replace(
        "if(!byLoc[r.ubicacion].rows[rowKey])byLoc[r.ubicacion].rows[rowKey]={genero:r.genero,color:r.color,tallas:{}};",
        "if(!byLoc[r.ubicacion].rows[rowKey])byLoc[r.ubicacion].rows[rowKey]={genero:r.genero,color:r.color,diseno:r.diseno,tallas:{}};",
    )
    html = html.replace(
        "var sv=salesMap[rd.genero+'|'+rd.color+'|'+t]||0;",
        "var sv=salesMap[rd.genero+'|'+rd.color+'|'+(rd.diseno||'')+'|'+t]||0;",
    )

    # getLF with HS factor
    html = html.replace(
        "function getLF(genero,meses,modelo){\n"
        "  var mO=DATA.meses_order.slice(-meses);\n"
        "  var r=DATA.raw_rows.filter(function(r){return r.genero===genero&&r.modelo===modelo&&mO.indexOf(r.mes)>=0;});\n"
        "  return Math.round(r.reduce(function(a,x){return a+x.v;},0)/meses);\n"
        "}",
        "function getLF(genero,meses,modelo){\n"
        "  var mO=DATA.meses_order.slice(-meses);\n"
        "  var hs=DATA.high_season_factor||1.4;\n"
        "  var r=DATA.raw_rows.filter(function(r){return r.tienda==='VELA'&&r.genero===genero&&r.modelo===modelo&&mO.indexOf(r.mes)>=0;});\n"
        "  return Math.round(r.reduce(function(a,x){return a+x.v;},0)/meses*hs);\n"
        "}",
    )

    # getNewStoreShare for expansion caps
    html = html.replace(
        "function getNewStoreShare(store,realShares){\n"
        "  var cap=NEW_STORE_CAPS[store];if(!cap)return 0;\n"
        "  return(realShares[cap.base]||0)*cap.mult;\n"
        "}",
        "function getNewStoreShare(store,realShares){\n"
        "  var cap=NEW_STORE_CAPS[store];if(!cap)return 0;\n"
        "  if(cap.mult!=null)return(realShares['VELA']||0)*cap.mult;\n"
        "  return(realShares[cap.base]||0)*(cap.mult||1);\n"
        "}",
    )

    # Init diseno filter options from DATA
    html = html.replace(
        "DATA.filtros.generos.forEach(function(g){document.getElementById('fG').innerHTML+='<option value=\"'+g+'\">'+g+'</option>';});",
        "DATA.filtros.generos.forEach(function(g){document.getElementById('fG').innerHTML+='<option value=\"'+g+'\">'+g+'</option>';});\n"
        "(DATA.filtros.disenos||[]).forEach(function(d){var el=document.getElementById('fD');if(el)el.innerHTML+='<option value=\"'+d+'\">'+d+'</option>';});",
    )

    html = html.replace(
        "updateColorFilter();filterModelButtons();",
        "updateColorFilter();updateDisenoFilter();filterModelButtons();",
    )

    if "function updateDisenoFilter" not in html:
        html = html.replace(
            "function updateColorFilter(){",
            "function updateDisenoFilter(){var sel=document.getElementById('fD');if(!sel)return;var cur=sel.value;sel.innerHTML='<option value=\"\">Todos</option>';var rows=DATA.raw_rows.filter(function(r){return(!_modelo||r.modelo===_modelo);});var ds={};rows.forEach(function(r){ds[r.diseno]=1;});Object.keys(ds).sort().forEach(function(d){sel.innerHTML+='<option value=\"'+d+'\">'+d+'</option>';});if(cur&&ds[cur])sel.value=cur;}\n"
            "function updateColorFilter(){",
        )
        html = html.replace(
            "function updateColorFilter(){var sel=document.getElementById('fC'),cur=sel.value;",
            "function updateColorFilter(){updateDisenoFilter();var sel=document.getElementById('fC'),cur=sel.value;",
        )

    # Decisiones sub text
    html = html.replace(
        '<div class="sub">Reabastecimiento por tienda (VELA, WEB, PEDIDOS) según ventas del período</div>',
        '<div class="sub">Foco tienda <strong style="color:var(--tx)">VELA Margarita</strong> · expansión <strong style="color:#f97316">Valencia</strong> y <strong style="color:#f97316">Barquisimeto</strong> · temp. alta ×<span id="hsFactorLabel">1.4</span></div>',
    )

    # export CSV with diseno
    html = html.replace(
        "var lines=['Tienda,Modelo,Género,Color,Talla,Mes,Unidades'];rows.forEach(function(r){lines.push([r.tienda,r.modelo,r.genero,r.color,r.talla,r.mes,r.v].join(','));});",
        "var lines=['Tienda,Modelo,Género,Color,Diseño,Talla,Mes,Unidades'];rows.forEach(function(r){lines.push([r.tienda,r.modelo,r.genero,r.color,r.diseno||'',r.talla,r.mes,r.v].join(','));});",
    )

    # Decisiones: methodology + expansion + diseno grouping
    html = html.replace(
        "function rDecisiones(){\n  var meses=_decMeses||2;",
        "function rDecisiones(){\n  var meses=_decMeses||2;\n"
        "  var hs=DATA.high_season_factor||1.4;\n"
        "  var hsLbl=document.getElementById('hsFactorLabel');if(hsLbl)hsLbl.textContent=hs;\n"
        "  var decHdr=document.getElementById('decMethodology');\n"
        "  if(decHdr){\n"
        "    var velLbl=DATA.velocity_months_label||'';\n"
        "    var exp=DATA.expansion||{};\n"
        "    var addPct=Math.round((DATA.additional_color_factor||0.7)*100);\n"
        "    decHdr.innerHTML='<div style=\"background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.22);border-radius:12px;padding:14px 16px;font-size:.71rem;color:var(--mu);line-height:1.55;margin-bottom:14px\">'\n"
        "      +'<div style=\"font-family:var(--fh);font-weight:800;color:var(--a2);margin-bottom:10px;font-size:.78rem\">📋 Metodología — rotación y producción</div>'\n"
        "      +'<div style=\"display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px 16px\">'\n"
        "      +'<div><strong style=\"color:var(--tx)\">Foco tienda</strong><br>Velocidad base = ventas <strong style=\"color:var(--tx)\">VELA Margarita</strong> en '+velLbl+' (sin '+((DATA.partial_month||'mes parcial').split('-')[0])+').</div>'\n"
        "      +'<div><strong style=\"color:var(--tx)\">Temporada alta</strong><br>Rotación ajustada = base × <strong style=\"color:var(--tx)\">'+hs+'</strong> para cobertura y producción.</div>'\n"
        "      +'<div><strong style=\"color:var(--tx)\">🆕 Expansión Valencia + Barquisimeto</strong><br>Proyección 3 meses desde movimiento Blanco en VELA. <strong style=\"color:var(--tx)\">'+((DATA.additional_color)||'Color adicional')+'</strong> al <strong style=\"color:var(--tx)\">'+addPct+'%</strong> de Blanco (30% menos).</div>'\n"
        "      +'</div></div>'\n"
        "      +'<div style=\"background:rgba(249,115,22,.08);border:1px solid rgba(249,115,22,.28);border-radius:12px;padding:14px 16px;margin-bottom:14px\">'\n"
        "      +'<div style=\"font-family:var(--fh);font-weight:800;color:#f97316;margin-bottom:8px;font-size:.78rem\">🚀 Proyección expansión — 3 meses</div>'\n"
        "      +'<div style=\"display:flex;gap:16px;flex-wrap:wrap;margin-bottom:10px\">'\n"
        "      +'<div><span style=\"font-family:var(--fm);font-size:1.2rem;font-weight:800;color:var(--tx)\">'+(exp.total_expansion||0)+'</span> <span style=\"font-size:.65rem;color:var(--mu)\">und total</span></div>'\n"
        "      +'<div><span style=\"font-family:var(--fm);font-size:1rem;font-weight:700;color:#e4e4e7\">'+(exp.total_blanco||0)+'</span> <span style=\"font-size:.65rem;color:var(--mu)\">Blanco</span></div>'\n"
        "      +'<div><span style=\"font-family:var(--fm);font-size:1rem;font-weight:700;color:#a5b4fc\">'+(exp.total_adicional||0)+'</span> <span style=\"font-size:.65rem;color:var(--mu)\">'+((DATA.additional_color)||'Color adicional')+'</span></div>'\n"
        "      +'</div><div style=\"font-size:.65rem;color:var(--mu2)\">'+(exp.nota||'')+'</div></div>';\n"
        "  }\n",
    )

    html = html.replace(
        "      // group by color\n      var byColor={};\n      rows.forEach(function(r){\n        if(!byColor[r.color]) byColor[r.color]={rows:[],totalStk:0,totalNeed1:0,totalNeed2:0,totalNeed3:0,v_mes:0};\n        byColor[r.color].rows.push(r);\n        byColor[r.color].totalStk+=r.stk_total;\n        byColor[r.color].totalNeed1+=r.need_1m;\n        byColor[r.color].totalNeed2+=r.need_2m;\n        byColor[r.color].totalNeed3+=r.need_3m;\n        byColor[r.color].v_mes+=r.v_mes;\n      });\n      var colorKeys=Object.keys(byColor).sort(function(a,b){return byColor[b].v_mes-byColor[a].v_mes;});",
        "      // group by diseño\n      var byColor={};\n      rows.forEach(function(r){\n        var dk=r.diseno||r.color;\n        if(!byColor[dk]) byColor[dk]={rows:[],totalStk:0,totalNeed1:0,totalNeed2:0,totalNeed3:0,v_mes:0};\n        byColor[dk].rows.push(r);\n        byColor[dk].totalStk+=r.stk_total;\n        byColor[dk].totalNeed1+=r.need_1m;\n        byColor[dk].totalNeed2+=r.need_2m;\n        byColor[dk].totalNeed3+=r.need_3m;\n        byColor[dk].v_mes+=r.v_mes;\n      });\n      var colorKeys=Object.keys(byColor).sort(function(a,b){return byColor[b].v_mes-byColor[a].v_mes;});",
    )

    html = html.replace(
        "'<div style=\"font-size:.67rem;color:var(--mu2);margin-bottom:8px\">📦 PT taller: '+smry.stk_pt+' und &nbsp;·&nbsp; Velocidad: meses cerrados (Jul parcial excluido)</div>'",
        "'<div style=\"font-size:.67rem;color:var(--mu2);margin-bottom:8px\">📦 PT taller: '+smry.stk_pt+' und &nbsp;·&nbsp; Base VELA × '+hs+' temp. alta · '+((DATA.velocity_months_label)||'')+'</div>'",
    )

    # Replace old MARGARITA reabast with expansion stores
    old_reabast = """  // ── REABASTECIMIENTO incluyendo MARGARITA y TOLON proyectadas
  var reabastGrid=document.getElementById('reabastGrid');
  if(reabastGrid){
    var mesesActivos=getMesesActivos();
    var nMeses=Math.min(meses,mesesActivos.length)||1;

    // Real stores (excl. CERRO VERDE in restock display)
    var EXCLUIR_RESTOCK=[];
    var tiendaData={};
    DATA.raw_rows.forEach(function(r){
      if(EXCLUIR_RESTOCK.indexOf(r.tienda)>=0) return;
      if(mesesActivos.slice(-nMeses).indexOf(r.mes)<0) return;
      if(!tiendaData[r.tienda]) tiendaData[r.tienda]={v:0,items:{},proyectada:false,nota:''};
      tiendaData[r.tienda].v+=r.v;
      var k=r.modelo+'<br><span style="font-size:.6rem;color:var(--mu)">'+r.color+' / '+r.talla+'</span>';
      tiendaData[r.tienda].items[r.color+'/'+r.talla]=(tiendaData[r.tienda].items[r.color+'/'+r.talla]||0)+r.v;
    });

    // Add MARGARITA as projected store
    var marNeed=meses===1?DATA.margarita.need_1m:meses===2?DATA.margarita.need_2m:DATA.margarita.need_3m;
    if(marNeed>0)tiendaData['MARGARITA 🆕']={v:marNeed,items:{},proyectada:true,nota:DATA.margarita.nota};
    // build items from margarita SKUs sorted by talla
    if(marNeed>0){DATA.margarita.skus.forEach(function(s){
      var need=meses===1?s.need_1m:meses===2?s.need_2m:s.need_3m;
      if(need>0){
        var k=s.COLOR+' / '+s.TALLA;
        tiendaData['MARGARITA 🆕'].items[k]=(tiendaData['MARGARITA 🆕'].items[k]||0)+need;
      }
    });tiendaData['MARGARITA 🆕'].nota=DATA.margarita.nota;}

    // Enrich TOLON with note
    if(tiendaData['TOLON']) tiendaData['TOLON'].nota='';

    var tiendas=Object.keys(tiendaData).sort(function(a,b){
      return tiendaData[b].v-tiendaData[a].v;
    });

    reabastGrid.innerHTML='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px">'
      +tiendas.map(function(t){
        var td=tiendaData[t];
        // sort items by talla within color
        var itemKeys=Object.keys(td.items).sort(function(a,b){
          var ta=a.split(' / ')[1]||'', tb=b.split(' / ')[1]||'';
          return (TORD[ta]||99)-(TORD[tb]||99);
        });
        var topItems=itemKeys.slice(0,8);
        var isNew=td.proyectada;
        return '<div style="background:var(--s2);border-radius:10px;padding:12px;border:1px solid '+(isNew?'rgba(249,115,22,.3)':'var(--brd)')+';">'
          +'<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">'
          +'<span style="font-weight:700;font-size:.8rem">🏪 '+t+'</span>'
          +(isNew?'<span style="background:rgba(249,115,22,.15);color:#f97316;border-radius:4px;padding:1px 6px;font-size:.61rem">Proyectada</span>':'')
          +'</div>'
          +(td.nota?'<div style="font-size:.62rem;color:var(--mu2);margin-bottom:6px;font-style:italic">'+td.nota+'</div>':'')
          +'<div style="font-family:var(--fm);font-size:.68rem;color:var(--mu);margin-bottom:8px">'+td.v+' und sugeridas / '+nMeses+' mes(es)</div>'
          +topItems.map(function(k){
            return '<div style="display:flex;justify-content:space-between;align-items:center;font-size:.69rem;padding:3px 0;border-bottom:1px solid var(--brd)">'
              +'<span style="color:var(--tx)">'+k+'</span>'
              +'<span style="color:var(--a2);font-family:var(--fm);font-weight:700">'+td.items[k]+'</span></div>';
          }).join('')
          +(itemKeys.length>8?'<div style="font-size:.61rem;color:var(--mu2);margin-top:5px">+ '+(itemKeys.length-8)+' variantes más</div>':'')
          +'</div>';
      }).join('')
      +'</div>';
  }"""

    new_reabast = """  // ── REABASTECIMIENTO VELA + expansión Valencia / Barquisimeto
  var reabastGrid=document.getElementById('reabastGrid');
  if(reabastGrid){
    var tiendaData={};
    // VELA histórico (solo tienda física)
    var velaRows=DATA.raw_rows.filter(function(r){return r.tienda==='VELA';});
    var swVela=getSW(velaRows,'CAB','SPOTS MANGA CORTA');
    tiendaData['VELA']={v:velaRows.reduce(function(a,r){return a+r.v;},0),items:{},proyectada:false,nota:'Tienda ancla · Margarita'};
    velaRows.forEach(function(r){
      var k=(r.diseno||r.color)+' / '+r.talla+' · '+r.genero;
      tiendaData['VELA'].items[k]=(tiendaData['VELA'].items[k]||0)+r.v;
    });
    // Tiendas expansión desde DATA.expansion
    (DATA.expansion&&DATA.expansion.by_store||[]).forEach(function(es){
      var items={};
      es.skus.forEach(function(s){
        var k=s.color+' / '+s.talla+' · '+s.genero+' · '+(s.diseno||'');
        items[k]=(items[k]||0)+s.need_3m;
      });
      tiendaData[es.store+' 🆕']={v:es.total,blanco:es.blanco,adicional:es.adicional,items:items,proyectada:true,nota:es.label};
    });
    var tiendas=Object.keys(tiendaData).sort(function(a,b){return tiendaData[b].v-tiendaData[a].v;});
    reabastGrid.innerHTML='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px">'
      +tiendas.map(function(t){
        var td=tiendaData[t];
        var itemKeys=Object.keys(td.items).sort();
        var topItems=itemKeys.slice(0,10);
        var isNew=td.proyectada;
        return '<div style="background:var(--s2);border-radius:10px;padding:12px;border:1px solid '+(isNew?'rgba(249,115,22,.3)':'var(--brd)')+';">'
          +'<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;flex-wrap:wrap">'
          +'<span style="font-weight:700;font-size:.8rem">🏪 '+t+'</span>'
          +(isNew?'<span style="background:rgba(249,115,22,.15);color:#f97316;border-radius:4px;padding:1px 6px;font-size:.61rem">Expansión</span>':'')
          +'</div>'
          +(td.nota?'<div style="font-size:.62rem;color:var(--mu2);margin-bottom:6px">'+td.nota+'</div>':'')
          +(isNew?'<div style="font-size:.64rem;color:var(--mu);margin-bottom:8px">'+td.v+' und · Blanco <strong>'+td.blanco+'</strong> + '+((DATA.additional_color)||'adicional')+' <strong>'+td.adicional+'</strong></div>'
            :'<div style="font-family:var(--fm);font-size:.68rem;color:var(--mu);margin-bottom:8px">'+td.v+' und vendidas (histórico)</div>')
          +topItems.map(function(k){
            return '<div style="display:flex;justify-content:space-between;font-size:.69rem;padding:3px 0;border-bottom:1px solid var(--brd)">'
              +'<span style="color:var(--tx)">'+k+'</span>'
              +'<span style="color:var(--a2);font-family:var(--fm);font-weight:700">'+td.items[k]+'</span></div>';
          }).join('')
          +(itemKeys.length>10?'<div style="font-size:.61rem;color:var(--mu2);margin-top:5px">+ '+(itemKeys.length-10)+' más</div>':'')
          +'</div>';
      }).join('')
      +'</div>';
  }"""

    if old_reabast in html:
        html = html.replace(old_reabast, new_reabast)
    else:
        print("WARN: reabast block not found for replacement")

    # Add decMethodology container
    if 'id="decMethodology"' not in html:
        html = html.replace(
            '  <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap">',
            '  <div id="decMethodology"></div>\n  <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap">',
            1,
        )

    # Inv matrix show diseno in cell label
    html = html.replace(
        "h+='<tr><td class=\"color-cell\"><span class=\"chip\" style=\"background:'+cn(rd.color)+'\"></span>'+(GICO[rd.genero]||'')+' '+rd.genero+' · '+rd.color+'</td>';",
        "h+='<tr><td class=\"color-cell\"><span class=\"chip\" style=\"background:'+cn(rd.color)+'\"></span>'+(GICO[rd.genero]||'')+' '+rd.genero+' · '+rd.color+(rd.diseno?' · '+rd.diseno:'')+'</td>';",
    )

    return html


def main():
    data = rebuild_data()
    html = patch_html(build_html(data), data)
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote {HTML_PATH}")
    print(f"ventas: {data['total']} und | meses: {data['meses_order']}")
    print(f"vel months: {data['velocity_months']}")
    print(f"expansion total: {data['expansion']['total_expansion']} (blanco {data['expansion']['total_blanco']} + adicional {data['expansion']['total_adicional']})")
    for s in data["expansion"]["by_store"]:
        print(f"  {s['store']}: {s['total']} und (B{s['blanco']} + A{s['adicional']})")


if __name__ == "__main__":
    main()
