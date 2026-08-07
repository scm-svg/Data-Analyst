#!/usr/bin/env python3
"""Build ecobags.html — Dashboard Eco Bag."""
import json
import re
import shutil
import subprocess
from pathlib import Path

from build_ecobags_data import MODEL, build

SRC = '/workspace/sportlite.html'
DST = '/workspace/ecobags.html'

# Extract design preview images from COMPRAS xlsx
subprocess.run(['python3', str(Path(__file__).parent / 'extract_ecobags_images.py')], check=True)

shutil.copy(SRC, DST)

data = build()
data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

with open(SRC, 'r', encoding='utf-8') as f:
    html = f.read()

with open(DST, 'w', encoding='utf-8') as f:
    f.write(html)

html = open(DST, encoding='utf-8').read()

html = html.replace('Dashboard Sport Lite', 'Dashboard Eco Bag')
html = html.replace(
    '<h1>Sport Lite · <em id="titleModelo">Global</em></h1>',
    '<h1>Eco Bag · <em id="titleModelo">Eco Bag</em></h1>',
)
html = html.replace(
    'Sport Lite · Dashboard de Ventas ·',
    'Eco Bag · Dashboard de Ventas ·',
)
html = re.sub(
    r'<div class="footer">Sport Lite · Dashboard de Ventas · [^<]+</div>',
    f'<div class="footer">Eco Bag · Dashboard de Ventas · {data["date_range"]}</div>',
    html,
    count=1,
)
html = re.sub(
    r'<p>Dashboard de Ventas · [^<]+</p>',
    f'<p>Dashboard de Ventas · {data["date_range"]} · 5 diseños</p>',
    html,
    count=1,
)
html = html.replace("a.download='Sport_Lite.csv'", "a.download='Eco_Bag.csv'")

# Un solo modelo: ocultar barra de modelos
html = html.replace('<div class="mbar">', '<div class="mbar" style="display:none">')

html = html.replace(
    "var MICO={'MIKA SPORT LITE':'🏃','NOAH SPORT LITE':'🏃','MAYA SPORT LITE':'🏃'};",
    f"var MICO={{'{MODEL}':'👜'}};",
)
html = html.replace(
    "var MODELO_ID={'MIKA SPORT LITE':'MIKA','NOAH SPORT LITE':'NOAH','MAYA SPORT LITE':'MAYA'};",
    f"var MODELO_ID={{'{MODEL}':'ECO'}};",
)
html = html.replace(
    "var sn={'MIKA SPORT LITE':'Mika','NOAH SPORT LITE':'Noah','MAYA SPORT LITE':'Maya'};",
    f"var sn={{'{MODEL}':'Eco Bag'}};",
)
html = html.replace(
    "if(titleEl){var sn={'MIKA SPORT LITE':'Mika','NOAH SPORT LITE':'Noah','MAYA SPORT LITE':'Maya'};titleEl.textContent=m?(sn[m]||m):'Global';}",
    f"if(titleEl)titleEl.textContent='Eco Bag';",
)

html = html.replace(
    "var modelList=_modelo?[_modelo]:['MIKA SPORT LITE','NOAH SPORT LITE','MAYA SPORT LITE'];",
    f"var modelList=['{MODEL}'];",
)

# Ocultar filtro género (producto unisex)
html = html.replace(
    '<div class="fg"><label>Género</label><select id="fG" onchange="af()"><option value="">Todos</option></select></div>',
    '<div class="fg" style="display:none"><label>Género</label><select id="fG" onchange="af()"><option value="">Todos</option></select></div>',
)

# Pestaña Diseños (antes Tallas)
html = html.replace(
    '<button class="tab" onclick="st(\'tallas\')">📐 Tallas</button>',
    '<button class="tab" onclick="st(\'tallas\')">🎨 Diseños</button>',
)
html = html.replace(
    '<div class="g1 card"><h3>Color × Talla</h3><div class="sub">Heatmap</div>',
    '<div class="g1 card"><h3>Diseño × Tienda</h3><div class="sub">Heatmap de ventas por diseño</div>',
)

html = html.replace(
    'Sugerencia proporcional por color y talla · Clic en color para detalle',
    'Cobertura y producción neta por diseño',
)
html = html.replace(
    '🆕 MARGARITA proyectada: 2× velocidad GRIE · CERRO VERDE excluida de reabastecimiento',
    'Reabastecimiento por tienda según ventas del período',
)

html = html.replace(
    "function aTab(){var t=document.querySelector('.tab.active');if(!t)return'resumen';var tx=t.textContent;if(tx.indexOf('Resumen')>=0)return'resumen';if(tx.indexOf('Color')>=0)return'colores';if(tx.indexOf('Talla')>=0)return'tallas';if(tx.indexOf('Tienda')>=0)return'tiendas';return'decisiones';}",
    "function aTab(){var t=document.querySelector('.tab.active');if(!t)return'resumen';var tx=t.textContent;if(tx.indexOf('Resumen')>=0)return'resumen';if(tx.indexOf('Color')>=0)return'colores';if(tx.indexOf('Dise')>=0||tx.indexOf('Talla')>=0)return'tallas';if(tx.indexOf('Tienda')>=0)return'tiendas';if(tx.indexOf('Inventario')>=0)return'inventario';return'decisiones';}",
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
.dhp{cursor:help;border-bottom:1px dotted var(--mu);transition:color .15s}
.dhp:hover{color:var(--ac)}
#designPreview{position:fixed;display:none;pointer-events:none;z-index:10000;background:var(--surf);border:2px solid var(--ac);border-radius:12px;padding:8px;box-shadow:0 12px 40px rgba(0,0,0,.55)}
#designPreview img{display:block;max-width:260px;max-height:320px;border-radius:8px;object-fit:contain}
#designPreview .dp-title{font-family:var(--fh);font-size:0.72rem;font-weight:700;margin-top:6px;text-align:center;color:var(--tx)}
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

html = html.replace(
    "        +'<div style=\"font-size:.67rem;color:var(--mu2);margin-bottom:8px\">📦 PT global: '+smry.stk_pt+' und &nbsp;·&nbsp; Velocidad base: Feb–Mar–Abr 2026</div>'",
    "        +'<div style=\"font-size:.67rem;color:var(--mu2);margin-bottom:8px\">📦 PT taller: '+smry.stk_pt+' und &nbsp;·&nbsp; Velocidad: meses cerrados recientes</div>'",
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
    "    var EXCLUIR_RESTOCK=['CERRO VERDE'];",
    "    var EXCLUIR_RESTOCK=[];",
)

# rTallas → diseños
old_rtallas = html[html.index('function rTallas'):html.index('function rTiendas')]
new_rtallas = Path(__file__).parent.joinpath('ecobags_tallas.js').read_text(encoding='utf-8') + '\n\n'
html = html.replace(old_rtallas, new_rtallas)

inv_js = Path(__file__).parent.joinpath('ecobags_inventario.js').read_text(encoding='utf-8')
hover_js = Path(__file__).parent.joinpath('ecobags_hover.js').read_text(encoding='utf-8')
html = html.replace(
    '\n\n// ── DECISIONES ──',
    '\n\n' + hover_js + '\n\n' + inv_js + '\n\n// ── DECISIONES ──',
    1,
)

# Hover preview on design names in ranking tables (Colores ranking)
html = html.replace(
    "colorFn(x.k)+'\"></span>':'')+x.k+'</td><td><div class=\"rb\">",
    "colorFn(x.k)+'\"></span>':'')+dLbl(x.k,x.k)+'</td><td><div class=\"rb\">",
)

html = html.replace(
    "return'<tr><td><span style=\"font-family:var(--fh);font-weight:800;color:var(--ac);font-size:0.82rem\">#'+(i+1)+'</span></td><td><span class=\"chip\" style=\"background:'+cn(col)+'\"></span>'+kv[0]+'</td><td style=\"font-weight:700;font-family:var(--fh)\">'+kv[1]+'</td><td style=\"color:var(--ac);font-size:0.7rem;font-weight:700\">'+pct+'%</td></tr>';",
    "var rest=kv[0].slice(col.length);return'<tr><td><span style=\"font-family:var(--fh);font-weight:800;color:var(--ac);font-size:0.82rem\">#'+(i+1)+'</span></td><td><span class=\"chip\" style=\"background:'+cn(col)+'\"></span>'+dLbl(col,col)+rest+'</td><td style=\"font-weight:700;font-family:var(--fh)\">'+kv[1]+'</td><td style=\"color:var(--ac);font-size:0.7rem;font-weight:700\">'+pct+'%</td></tr>';",
)

html = html.replace(
    "h+='<tr><td class=\"rl\"><span class=\"chip\" style=\"background:'+cn(c)+'\"></span>'+c+'</td>'+tiendas.map(function(t){var v=(m2ct[c]&&m2ct[c][t])||0;return'<td style=\"background:'+hb(v,mxCT)+';color:'+ht(v,mxCT)+'\" title=\"'+c+' · '+t+': '+v+' und\">'+v+'</td>';}).join('')+'</tr>';",
    "h+='<tr><td class=\"rl\"><span class=\"chip\" style=\"background:'+cn(c)+'\"></span>'+dLbl(c,c)+'</td>'+tiendas.map(function(t){var v=(m2ct[c]&&m2ct[c][t])||0;return'<td style=\"background:'+hb(v,mxCT)+';color:'+ht(v,mxCT)+'\" title=\"'+c+' · '+t+': '+v+' und\">'+v+'</td>';}).join('')+'</tr>';",
)

html = html.replace(
    "  if(DATA.es_parcial)alerts.push({type:'info',text:'📅 Mayo 2026 con datos parciales'});\n",
    "",
)

html = html.replace(
    "  mc('cCol','doughnut',{labels:byColor.map(function(x){return x.k;}),datasets:[{data:byColor.map(function(x){return x.v;}),backgroundColor:byColor.map(function(x){return cn(x.k)+'cc';}),borderColor:byColor.map(function(x){return cn(x.k);}),borderWidth:1.5,hoverOffset:8}]},pieOpts());",
    "  bindChartDesignPreview(mc('cCol','doughnut',{labels:byColor.map(function(x){return x.k;}),datasets:[{data:byColor.map(function(x){return x.v;}),backgroundColor:byColor.map(function(x){return cn(x.k)+'cc';}),borderColor:byColor.map(function(x){return cn(x.k);}),borderWidth:1.5,hoverOffset:8}]},pieOpts()));",
)

html = html.replace(
    "updateColorFilter();filterModelButtons();buildPeriodBtns();updateModeloCounts();updateKPIs();renderAlertas();rResumen();",
    "updateColorFilter();filterModelButtons();buildPeriodBtns();updateModeloCounts();updateKPIs();renderAlertas();initDesignPreview();rResumen();",
)

html = re.sub(
    r'var DATA=\{.*?\};\nvar _modelo',
    f'var DATA={data_json};\nvar _modelo',
    html,
    count=1,
    flags=re.DOTALL,
)

# Colores diseño Eco Bag
html = html.replace(
    "  if(s.indexOf('kaki')>=0)return'#a16207';",
    "  if(s.indexOf('kaki')>=0)return'#a16207';\n"
    "  if(s.indexOf('daily')>=0)return'#27272a';\n"
    "  if(s.indexOf('ovalo')>=0)return'#2563eb';\n"
    "  if(s.indexOf('ondas')>=0)return'#4caf76';\n"
    "  if(s.indexOf('palmeras')>=0)return'#0284c7';\n"
    "  if(s.indexOf('venezuela')>=0)return'#16a34a';",
)

# Auto-seleccionar modelo único
html = html.replace(
    "var _modelo='',_per='all',_theme='dark';",
    f"var _modelo='{MODEL}',_per='all',_theme='dark';",
)

html = re.sub(
    r'<div class="footer">Eco Bag · Dashboard de Ventas · [^<]+</div>',
    f'<div class="footer">Eco Bag · Dashboard de Ventas · {data["date_range"]}</div>',
    html,
    count=1,
)

with open(DST, 'w', encoding='utf-8') as f:
    f.write(html)

print('ecobags.html created')
print(f'  Sales: {len(data["raw_rows"])} rows, {data["total"]} units')
print(f'  Stock: {data["stock_total"]} units')
print(f'  Range: {data["date_range"]}')
