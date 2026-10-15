#!/usr/bin/env python3
"""Build advancegeo.html — Dashboard Advance Geo (manufactura)."""
import json
import re
import shutil
from pathlib import Path

from build_advancegeo_data import MODELS, build

SRC = '/workspace/sportlite.html'
DST = '/workspace/advancegeo.html'

M1, M2 = MODELS[0], MODELS[1]

shutil.copy(SRC, DST)
data = build()
data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

html = open(DST, encoding='utf-8').read()

html = html.replace('Dashboard Sport Lite', 'Dashboard Advance Geo')
html = html.replace(
    '<h1>Sport Lite · <em id="titleModelo">Global</em></h1>',
    '<h1>Advance Geo · <em id="titleModelo">Global</em></h1>',
)
html = html.replace(
    'Sport Lite · Dashboard de Ventas ·',
    'Advance Geo · Dashboard de Ventas ·',
)
html = re.sub(
    r'<p>Dashboard de Ventas · [^<]+</p>',
    f'<p>Dashboard de Ventas · {data["date_range"]} · Manufactura</p>',
    html,
    count=1,
)
html = html.replace("a.download='Sport_Lite.csv'", "a.download='Advance_Geo.csv'")

# Model bar: Dominic + Maya
OLD_MBAR = (
    '  <button class="mbtn active" data-m="" onclick="setModelo(\'\')">🗂️ Todos <span class="mcnt" id="mcnt_all">0</span></button>\n'
    '  <button class="mbtn" data-m="MIKA SPORT LITE" onclick="setModelo(\'MIKA SPORT LITE\')">🏃 Mika <span class="mcnt" id="mcnt_MIKA">0</span></button>\n'
    '  <button class="mbtn" data-m="NOAH SPORT LITE" onclick="setModelo(\'NOAH SPORT LITE\')">🏃 Noah <span class="mcnt" id="mcnt_NOAH">0</span></button>\n'
    '  <button class="mbtn" data-m="MAYA SPORT LITE" onclick="setModelo(\'MAYA SPORT LITE\')">🏃 Maya <span class="mcnt" id="mcnt_MAYA">0</span></button>'
)
NEW_MBAR = (
    f'  <button class="mbtn active" data-m="" onclick="setModelo(\'\')">🗂️ Todos <span class="mcnt" id="mcnt_all">0</span></button>\n'
    f'  <button class="mbtn" data-m="{M1}" onclick="setModelo(\'{M1}\')">👕 Dominic <span class="mcnt" id="mcnt_DOMINIC">0</span></button>\n'
    f'  <button class="mbtn" data-m="{M2}" onclick="setModelo(\'{M2}\')">👗 Maya <span class="mcnt" id="mcnt_MAYA">0</span></button>'
)
html = html.replace(OLD_MBAR, NEW_MBAR)

html = html.replace(
    "var MICO={'MIKA SPORT LITE':'🏃','NOAH SPORT LITE':'🏃','MAYA SPORT LITE':'🏃'};",
    f"var MICO={{'{M1}':'👕','{M2}':'👗'}};",
)
html = html.replace(
    "var MODELO_ID={'MIKA SPORT LITE':'MIKA','NOAH SPORT LITE':'NOAH','MAYA SPORT LITE':'MAYA'};",
    f"var MODELO_ID={{'{M1}':'DOMINIC','{M2}':'MAYA'}};",
)
html = html.replace(
    "if(titleEl){var sn={'MIKA SPORT LITE':'Mika','NOAH SPORT LITE':'Noah','MAYA SPORT LITE':'Maya'};titleEl.textContent=m?(sn[m]||m):'Global';}",
    f"if(titleEl){{var sn={{'{M1}':'Dominic CAB','{M2}':'Maya DAMA'}};titleEl.textContent=m?(sn[m]||m):'Global';}}",
)
html = html.replace(
    "var modelList=_modelo?[_modelo]:['MIKA SPORT LITE','NOAH SPORT LITE','MAYA SPORT LITE'];",
    f"var modelList=_modelo?[_modelo]:{json.dumps(MODELS, ensure_ascii=False)};",
)

html = html.replace(
    "function aTab(){var t=document.querySelector('.tab.active');if(!t)return'resumen';var tx=t.textContent;if(tx.indexOf('Resumen')>=0)return'resumen';if(tx.indexOf('Color')>=0)return'colores';if(tx.indexOf('Talla')>=0)return'tallas';if(tx.indexOf('Tienda')>=0)return'tiendas';return'decisiones';}",
    "function aTab(){var t=document.querySelector('.tab.active');if(!t)return'resumen';var tx=t.textContent;if(tx.indexOf('Resumen')>=0)return'resumen';if(tx.indexOf('Color')>=0)return'colores';if(tx.indexOf('Talla')>=0)return'tallas';if(tx.indexOf('Tienda')>=0)return'tiendas';if(tx.indexOf('Inventario')>=0)return'inventario';return'decisiones';}",
)

INV_CSS = """
.inv-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:14px}
@media(max-width:780px){.inv-summary{grid-template-columns:1fr}}
.inv-sum-card{background:var(--s2);border:1px solid var(--brd);border-radius:12px;padding:20px 16px;text-align:center}
.inv-sum-card .num{font-family:var(--fh);font-size:2rem;font-weight:800;line-height:1;color:var(--ac)}
.inv-sum-card .lbl{font-size:0.68rem;color:var(--mu);text-transform:uppercase;letter-spacing:0.6px;margin-top:6px}
.inv-sum-card.tiendas .num{color:#00bcd4}
.inv-sum-card.taller{border-color:#f9731644;background:rgba(249,115,22,.06)}
.inv-sum-card.taller .num{color:#f97316}
.inv-loc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:14px}
.inv-loc-card{background:var(--surf);border:1px solid var(--brd);border-radius:12px;padding:14px 16px}
.inv-loc-hdr{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:10px;gap:8px}
.inv-loc-hdr h4{font-family:var(--fh);font-size:0.82rem;font-weight:800;margin:0}
.inv-loc-hdr .sub2{font-size:0.64rem;color:var(--mu);margin-top:2px}
.inv-loc-tot{font-family:var(--fh);font-size:0.9rem;font-weight:800;color:var(--ac);white-space:nowrap}
.inv-matrix-wrap{overflow-x:auto;padding-bottom:4px}
.inv-matrix{border-collapse:separate;border-spacing:3px;width:100%}
.inv-matrix th{font-size:0.62rem;color:var(--mu);padding:2px 5px;text-align:center;font-weight:600;white-space:nowrap}
.inv-matrix .color-cell{text-align:left;font-size:0.71rem;white-space:nowrap;padding-right:8px;color:var(--tx);font-weight:500}
.inv-matrix .qty-pill{display:inline-block;background:var(--ac);color:#fff;border-radius:5px;padding:3px 8px;font-size:0.7rem;font-weight:700;min-width:24px;text-align:center}
.inv-matrix .qty-pill.nomove{background:rgba(239,68,68,.12);border:1px solid #ef444466;color:#ef4444}
.inv-matrix .qty-ventas{font-size:0.62rem;display:block;margin-top:2px;line-height:1}
.inv-matrix .qty-ventas.zero{color:#ef4444;font-weight:700}
.inv-matrix .qty-empty{color:var(--mu2);font-size:0.65rem}
"""
html = html.replace(
    '.tkpi .ts{font-size:0.68rem;color:var(--mu2);margin-top:1px}\n.nodata{',
    '.tkpi .ts{font-size:0.68rem;color:var(--mu2);margin-top:1px}\n' + INV_CSS + '.nodata{',
)

html = html.replace(
    '  <button class="tab" onclick="st(\'tiendas\')">🏪 Tiendas</button>\n'
    '  <button class="tab" onclick="st(\'decisiones\')">💡 Decisiones</button>',
    '  <button class="tab" onclick="st(\'tiendas\')">🏪 Tiendas</button>\n'
    '  <button class="tab" onclick="st(\'inventario\')">📦 Inventario</button>\n'
    '  <button class="tab" onclick="st(\'decisiones\')">💡 Decisiones</button>',
)
html = html.replace(
    '</div>\n\n<!-- DECISIONES -->',
    '</div>\n\n<div class="sec" id="sec-inventario">\n'
    '  <div class="inv-summary" id="invSummary"></div>\n'
    '  <div class="inv-loc-grid" id="invLocGrid"></div>\n'
    '</div>\n\n<!-- DECISIONES -->',
)
html = html.replace(
    "var TABS=['resumen','colores','tallas','tiendas','decisiones'];",
    "var TABS=['resumen','colores','tallas','tiendas','inventario','decisiones'];",
)
html = html.replace(
    "else if(n==='tiendas')rTiendas();else if(n==='decisiones')rDecisiones();",
    "else if(n==='tiendas')rTiendas();else if(n==='inventario')rInventario();else if(n==='decisiones')rDecisiones();",
)

inv_js = Path(__file__).parent.joinpath('advancegeo_inventario.js').read_text(encoding='utf-8')
html = html.replace(
    '\n\n// ── DECISIONES ──',
    '\n\n' + inv_js + '\n\n// ── DECISIONES ──',
    1,
)

old_rtallas = html[html.index('function rTallas'):html.index('function rTiendas')]
new_rtallas = Path(__file__).parent.joinpath('advancegeo_tallas.js').read_text(encoding='utf-8') + '\n\n'
html = html.replace(old_rtallas, new_rtallas)

html = html.replace(
    "        +'<div style=\"font-size:.67rem;color:var(--mu2);margin-bottom:8px\">📦 PT global: '+smry.stk_pt+' und &nbsp;·&nbsp; Velocidad base: Feb–Mar–Abr 2026</div>'",
    "        +'<div style=\"font-size:.67rem;color:var(--mu2);margin-bottom:8px\">📦 PT taller: '+smry.stk_pt+' und &nbsp;·&nbsp; Velocidad: últimos meses cerrados</div>'",
)

html = html.replace(
    "    var EXCLUIR_RESTOCK=['CERRO VERDE'];",
    "    var EXCLUIR_RESTOCK=['CORPORATIVO','WEB'];",
)

html = html.replace(
    "    var marNeed=meses===1?DATA.margarita.need_1m:meses===2?DATA.margarita.need_2m:DATA.margarita.need_3m;\n    tiendaData['MARGARITA 🆕']={v:marNeed,items:{},proyectada:true,nota:DATA.margarita.nota};",
    "    var marNeed=meses===1?DATA.margarita.need_1m:meses===2?DATA.margarita.need_2m:DATA.margarita.need_3m;\n    if(marNeed>0)tiendaData['MARGARITA 🆕']={v:marNeed,items:{},proyectada:true,nota:DATA.margarita.nota};",
)

html = html.replace(
    "    DATA.margarita.skus.forEach(function(s){\n      var need=meses===1?s.need_1m:meses===2?s.need_2m:s.need_3m;\n      if(need>0){\n        var k=s.COLOR+' / '+s.TALLA;\n        tiendaData['MARGARITA 🆕'].items[k]=(tiendaData['MARGARITA 🆕'].items[k]||0)+need;\n      }\n    });\n    tiendaData['MARGARITA 🆕'].nota=DATA.margarita.nota;",
    "    if(marNeed>0){DATA.margarita.skus.forEach(function(s){\n      var need=meses===1?s.need_1m:meses===2?s.need_2m:s.need_3m;\n      if(need>0){\n        var k=s.COLOR+' / '+s.TALLA;\n        tiendaData['MARGARITA 🆕'].items[k]=(tiendaData['MARGARITA 🆕'].items[k]||0)+need;\n      }\n    });tiendaData['MARGARITA 🆕'].nota=DATA.margarita.nota;}",
)

html = html.replace(
    "var NEW_STORES=['MARGARITA','TOLON'];",
    "var NEW_STORES=[];",
)

html = html.replace(
    "  if(DATA.es_parcial)alerts.push({type:'info',text:'📅 Mayo 2026 con datos parciales'});\n",
    "  if(DATA.es_parcial)alerts.push({type:'info',text:'📅 Último mes con datos parciales'});\n",
)

html = re.sub(
    r'var DATA=\{.*?\};\nvar _modelo',
    f'var DATA={data_json};\nvar _modelo',
    html,
    count=1,
    flags=re.DOTALL,
)

# Colores Advance Geo
html = html.replace(
    "  if(s.indexOf('kaki')>=0)return'#a16207';",
    "  if(s.indexOf('kaki')>=0)return'#a16207';\n"
    "  if(s.indexOf('amarillo')>=0)return'#eab308';\n"
    "  if(s.indexOf('cobalto')>=0)return'#2563eb';\n"
    "  if(s.indexOf('negro')>=0)return'#27272a';",
)

html = html.replace(
    "function exportCSV(){var rows=fr();var lines=['Tienda,Modelo,Género,Color,Talla,Mes,Unidades'];rows.forEach(function(r){lines.push([r.tienda,r.modelo,r.genero,r.color,r.talla,r.mes,r.v].join(','));});var blob=new Blob(['\uFEFF'+lines.join('\n')],{type:'text/csv;charset=utf-8;'});var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='Sport_Lite.csv';a.click();}",
    "function exportCSV(){var rows=fr();var lines=['Tienda,Modelo,Género,Color,Talla,Mes,Unidades'];rows.forEach(function(r){lines.push([r.tienda,r.modelo,r.genero,r.color,r.talla,r.mes,r.v].join(','));});var blob=new Blob(['\uFEFF'+lines.join('\n')],{type:'text/csv;charset=utf-8;'});var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='Advance_Geo.csv';a.click();}",
)

html = html.replace(
    "if(m===''||m==='NOAH SPORT LITE')b.style.display='';else b.style.display='none';",
    f"if(m===''||m==='{M1}')b.style.display='';else b.style.display='none';",
)
html = html.replace(
    "if(m===''||m==='MIKA SPORT LITE'||m==='MAYA SPORT LITE')b.style.display='';else b.style.display='none';",
    f"if(m===''||m==='{M2}')b.style.display='';else b.style.display='none';",
)

html = html.replace(
    "  // original function body follows:\n  return;\n",
    "",
)

html = re.sub(
    r'<div class="footer">Advance Geo · Dashboard de Ventas · [^<]+</div>',
    f'<div class="footer">Advance Geo · Dashboard de Ventas · {data["date_range"]}</div>',
    html,
    count=1,
)

html = re.sub(
    r'<div class="footer">Sport Lite · Dashboard de Ventas · [^<]+</div>',
    f'<div class="footer">Advance Geo · Dashboard de Ventas · {data["date_range"]}</div>',
    html,
    count=1,
)

with open(DST, 'w', encoding='utf-8') as f:
    f.write(html)

print('advancegeo.html created')
print(f'  Sales: {len(data["raw_rows"])} rows, {data["total"]} units')
print(f'  Stock: {data["stock_total"]} units')
print(f'  Models: {", ".join(MODELS)}')
print(f'  Range: {data["date_range"]}')
