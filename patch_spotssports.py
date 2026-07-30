#!/usr/bin/env python3
"""Build spotssports.html — Colección Spots (Manga Corta / Manga Larga)."""
import json
import re
import shutil
from pathlib import Path

from build_spotssports_data import MODEL_CORTA, MODEL_LARGA, build

SRC = '/workspace/sportlite.html'
DST = '/workspace/spotssports.html'

shutil.copy(SRC, DST)

data = build()
data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

with open(DST, 'r', encoding='utf-8') as f:
    html = f.read()

html = html.replace('Dashboard Sport Lite', 'Dashboard Colección Spots')
html = html.replace(
    '<h1>Sport Lite · <em id="titleModelo">Global</em></h1>',
    '<h1>Colección Spots · <em id="titleModelo">Global</em></h1>',
)
html = html.replace(
    'Sport Lite · Dashboard de Ventas ·',
    'Colección Spots · Dashboard de Ventas ·',
)
html = re.sub(
    r'<div class="footer">Sport Lite · Dashboard de Ventas · [^<]+</div>',
    f'<div class="footer">Colección Spots · Dashboard de Ventas · {data["date_range"]}</div>',
    html,
    count=1,
)
html = re.sub(
    r'<p>Dashboard de Ventas · [^<]+</p>',
    f'<p>Dashboard de Ventas · {data["date_range"]} · Manga Corta &amp; Manga Larga</p>',
    html,
    count=1,
)
html = html.replace("a.download='Sport_Lite.csv'", "a.download='Coleccion_Spots.csv'")

OLD_MBAR = """<div class="mbar">
  <span class="mbar-lbl">⚡ Modelo:</span>
  <button class="mbtn active" data-m="" onclick="setModelo('')">🗂️ Todos <span class="mcnt" id="mcnt_all">0</span></button>
  <button class="mbtn" data-m="MIKA SPORT LITE" onclick="setModelo('MIKA SPORT LITE')">🏃 Mika <span class="mcnt" id="mcnt_MIKA">0</span></button>
  <button class="mbtn" data-m="NOAH SPORT LITE" onclick="setModelo('NOAH SPORT LITE')">🏃 Noah <span class="mcnt" id="mcnt_NOAH">0</span></button>
  <button class="mbtn" data-m="MAYA SPORT LITE" onclick="setModelo('MAYA SPORT LITE')">🏃 Maya <span class="mcnt" id="mcnt_MAYA">0</span></button>
</div>"""
NEW_MBAR = f"""<div class="mbar">
  <span class="mbar-lbl">⚡ Línea:</span>
  <button class="mbtn active" data-m="" onclick="setModelo('')">🗂️ Todos <span class="mcnt" id="mcnt_all">0</span></button>
  <button class="mbtn" data-m="{MODEL_CORTA}" onclick="setModelo('{MODEL_CORTA}')">👕 Manga Corta <span class="mcnt" id="mcnt_SMC">0</span></button>
  <button class="mbtn" data-m="{MODEL_LARGA}" onclick="setModelo('{MODEL_LARGA}')">🧥 Manga Larga <span class="mcnt" id="mcnt_SML">0</span></button>
</div>"""
html = html.replace(OLD_MBAR, NEW_MBAR)

html = html.replace(
    "var MICO={'MIKA SPORT LITE':'🏃','NOAH SPORT LITE':'🏃','MAYA SPORT LITE':'🏃'};",
    f"var MICO={{'{MODEL_CORTA}':'👕','{MODEL_LARGA}':'🧥'}};",
)
html = html.replace(
    "var MODELO_ID={'MIKA SPORT LITE':'MIKA','NOAH SPORT LITE':'NOAH','MAYA SPORT LITE':'MAYA'};",
    f"var MODELO_ID={{'{MODEL_CORTA}':'SMC','{MODEL_LARGA}':'SML'}};",
)
html = html.replace(
    "var sn={'MIKA SPORT LITE':'Mika','NOAH SPORT LITE':'Noah','MAYA SPORT LITE':'Maya'};",
    f"var sn={{'{MODEL_CORTA}':'Manga Corta','{MODEL_LARGA}':'Manga Larga'}};",
)

html = html.replace(
    "if(titleEl){var sn={'MIKA SPORT LITE':'Mika','NOAH SPORT LITE':'Noah','MAYA SPORT LITE':'Maya'};titleEl.textContent=m?(sn[m]||m):'Global';}",
    f"if(titleEl){{var sn={{'{MODEL_CORTA}':'Manga Corta','{MODEL_LARGA}':'Manga Larga'}};titleEl.textContent=m?(sn[m]||m):'Global';}}",
)

html = html.replace(
    "var modelList=_modelo?[_modelo]:['MIKA SPORT LITE','NOAH SPORT LITE','MAYA SPORT LITE'];",
    f"var modelList=_modelo?[_modelo]:['{MODEL_CORTA}','{MODEL_LARGA}'];",
)

html = html.replace(
    'Sugerencia proporcional por color y talla · Clic en color para detalle',
    'Cobertura (meses) y producción neta por color/talla · CAB y DAMA',
)
html = html.replace(
    '🆕 MARGARITA proyectada: 2× velocidad GRIE · CERRO VERDE excluida de reabastecimiento',
    'Reabastecimiento por tienda (VELA, WEB, PEDIDOS) según ventas del período',
)

html = html.replace(
    '🆕 MARGARITA proyectada: 2× velocidad GRIE · VELA: 1.5× GRIE · CERRO VERDE excluida',
    'Producción por cobertura (venta/mes vs stock) · VELA y TALLER PT · Julio parcial excluido de velocidad base',
)

html = html.replace(
    "function aTab(){var t=document.querySelector('.tab.active');if(!t)return'resumen';var tx=t.textContent;if(tx.indexOf('Resumen')>=0)return'resumen';if(tx.indexOf('Color')>=0)return'colores';if(tx.indexOf('Talla')>=0)return'tallas';if(tx.indexOf('Tienda')>=0)return'tiendas';return'decisiones';}",
    "function aTab(){var t=document.querySelector('.tab.active');if(!t)return'resumen';var tx=t.textContent;if(tx.indexOf('Resumen')>=0)return'resumen';if(tx.indexOf('Color')>=0)return'colores';if(tx.indexOf('Talla')>=0)return'tallas';if(tx.indexOf('Tienda')>=0)return'tiendas';if(tx.indexOf('Inventario')>=0)return'inventario';return'decisiones';}",
)

# ── Inventario (pestaña + sección + render) ──
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
html = html.replace(
    f"var MODELO_ID={{'{MODEL_CORTA}':'SMC','{MODEL_LARGA}':'SML'}};",
    f"var MODELO_ID={{'{MODEL_CORTA}':'SMC','{MODEL_LARGA}':'SML'}};\n"
    "var TALLA_ORDER=['XS','S','M','L','XL','2XL','3XL','4XL'];\n"
    "function tallaIdx(t){var i=TALLA_ORDER.indexOf(t);return i>=0?i:999;}\n"
    "function sortTallaKeys(keys){return keys.slice().sort(function(a,b){return tallaIdx(a)-tallaIdx(b);});}",
)
inv_js = Path(__file__).parent.joinpath('spotssports_inventario.js').read_text(encoding='utf-8')
html = html.replace(
    '\n\n// ── DECISIONES ──',
    '\n\n' + inv_js + '\n\n// ── DECISIONES ──',
    1,
)

# No ocultar botones de línea por género
html = html.replace(
    "      if(m===''||m==='MIKA SPORT LITE'||m==='MAYA SPORT LITE')b.style.display='';else b.style.display='none';",
    "      b.style.display='';",
)

html = html.replace(
"""  if(_fg==='CAB'){
    document.querySelectorAll('.mbtn[data-m]').forEach(function(b){
      var m=b.dataset.m;
      if(m===''||m==='NOAH SPORT LITE')b.style.display='';else b.style.display='none';
    });
  } else if(_fg==='DAMA')""",
"""  if(_fg==='CAB'){
    document.querySelectorAll('.mbtn[data-m]').forEach(function(b){b.style.display='';});
  } else if(_fg==='DAMA')""",
)

html = html.replace(
    "        +'<div style=\"font-size:.67rem;color:var(--mu2);margin-bottom:8px\">📦 PT global: '+smry.stk_pt+' und &nbsp;·&nbsp; Velocidad base: Feb–Mar–Abr 2026</div>'",
    "        +'<div style=\"font-size:.67rem;color:var(--mu2);margin-bottom:8px\">📦 PT taller: '+smry.stk_pt+' und &nbsp;·&nbsp; Velocidad: meses cerrados (Jul parcial excluido)</div>'",
)

# Reabastecimiento: omitir MARGARITA si no hay proyección
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

html = re.sub(
    r'var DATA=\{.*?\};\nvar _modelo',
    f'var DATA={data_json};\nvar _modelo',
    html,
    count=1,
    flags=re.DOTALL,
)

html = re.sub(
    r'<div class="footer">Colección Spots · Dashboard de Ventas · [^<]+</div>',
    f'<div class="footer">Colección Spots · Dashboard de Ventas · {data["date_range"]}</div>',
    html,
    count=1,
)

with open(DST, 'w', encoding='utf-8') as f:
    f.write(html)

print('spotssports.html created')
print(f'  Sales: {len(data["raw_rows"])} rows, {data["total"]} units')
print(f'  Stock: {data["stock_total"]} units')
print(f'  Models: {", ".join(data["filtros"]["modelos"])}')
print(f'  Range: {data["date_range"]}')
