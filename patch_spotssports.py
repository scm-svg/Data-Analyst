#!/usr/bin/env python3
"""Build spotssports.html — Colección Spots (Manga Corta / Manga Larga)."""
import json
import re
import shutil

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

# Inventario: totales netos (como Daily)
html = html.replace(
    "  invRows.forEach(function(r){\n    if(r.qty<=0)return;\n    tot+=r.qty;",
    "  invRows.forEach(function(r){\n    tot+=r.qty;",
)
html = html.replace(
    "    byLoc[r.ubicacion].total+=r.qty;\n    if(!byLoc[r.ubicacion].colors[r.color])",
    "    if(!byLoc[r.ubicacion].colors[r.color])",
)
html = html.replace(
    "    byLoc[r.ubicacion].colors[r.color][r.talla]=(byLoc[r.ubicacion].colors[r.color][r.talla]||0)+r.qty;\n  });\n  document.getElementById('invSummary')",
    "    byLoc[r.ubicacion].colors[r.color][r.talla]=(byLoc[r.ubicacion].colors[r.color][r.talla]||0)+r.qty;\n  });\n  Object.keys(byLoc).forEach(function(loc){\n    var ld=byLoc[loc],lt=0;\n    Object.keys(ld.colors).forEach(function(col){\n      Object.keys(ld.colors[col]).forEach(function(t){lt+=(ld.colors[col][t]||0);});\n    });\n    ld.total=lt;\n  });\n  document.getElementById('invSummary')",
)
html = html.replace('<div class="kl">Stock PT</div>', '<div class="kl">Stock Total</div>')

with open(DST, 'w', encoding='utf-8') as f:
    f.write(html)

print('spotssports.html created')
print(f'  Sales: {len(data["raw_rows"])} rows, {data["total"]} units')
print(f'  Stock: {data["stock_total"]} units')
print(f'  Models: {", ".join(data["filtros"]["modelos"])}')
print(f'  Range: {data["date_range"]}')
