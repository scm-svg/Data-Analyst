#!/usr/bin/env python3
"""Create sportmesh.html from sportlite.html template with Sport Mesh data."""
import json
import re
import shutil

from build_sportmesh_data import build

SRC = '/workspace/sportlite.html'
DST = '/workspace/sportmesh.html'

shutil.copy(SRC, DST)

data = build()
data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

with open(DST, 'r', encoding='utf-8') as f:
    html = f.read()

# Branding
html = html.replace('Dashboard Sport Lite', 'Dashboard Sport Mesh')
html = html.replace('Sport Lite · <em id="titleModelo">Global</em>', 'Sport Mesh · <em id="titleModelo">Global</em>')
html = html.replace('Sport Lite · Dashboard de Ventas · Agosto 2025 — Julio 2026', f'Sport Mesh · Dashboard de Ventas · {data["date_range"]}')
html = html.replace('Dashboard de Ventas · Agosto 2025 — Julio 2026', f'Dashboard de Ventas · {data["date_range"]}')
html = html.replace("a.download='Sport_Lite.csv'", "a.download='Sport_Mesh.csv'")

# Model buttons
old_buttons = """  <button class="mbtn" data-m="MIKA SPORT LITE" onclick="setModelo('MIKA SPORT LITE')">🏃 Mika <span class="mcnt" id="mcnt_MIKA">0</span></button>
  <button class="mbtn" data-m="NOAH SPORT LITE" onclick="setModelo('NOAH SPORT LITE')">🏃 Noah <span class="mcnt" id="mcnt_NOAH">0</span></button>
  <button class="mbtn" data-m="MAYA SPORT LITE" onclick="setModelo('MAYA SPORT LITE')">🏃 Maya <span class="mcnt" id="mcnt_MAYA">0</span></button>"""

new_buttons = """  <button class="mbtn" data-m="CLASICA SPORT" onclick="setModelo('CLASICA SPORT')">🏃 Clásica <span class="mcnt" id="mcnt_CLASICA">0</span></button>
  <button class="mbtn" data-m="SABRI SPORT" onclick="setModelo('SABRI SPORT')">🏃 Sabri <span class="mcnt" id="mcnt_SABRI">0</span></button>
  <button class="mbtn" data-m="MAFE SPORT" onclick="setModelo('MAFE SPORT')">🏃 Mafe <span class="mcnt" id="mcnt_MAFE">0</span></button>"""
html = html.replace(old_buttons, new_buttons)

# JS model maps
html = html.replace(
    "var MICO={'MIKA SPORT LITE':'🏃','NOAH SPORT LITE':'🏃','MAYA SPORT LITE':'🏃'};",
    "var MICO={'CLASICA SPORT':'🏃','SABRI SPORT':'🏃','MAFE SPORT':'🏃'};",
)
html = html.replace(
    "var MODELO_ID={'MIKA SPORT LITE':'MIKA','NOAH SPORT LITE':'NOAH','MAYA SPORT LITE':'MAYA'};",
    "var MODELO_ID={'CLASICA SPORT':'CLASICA','SABRI SPORT':'SABRI','MAFE SPORT':'MAFE'};",
)
html = html.replace(
    "var TALLA_ORDER=['XS','S','M','L','XL','2XL','3XL'];",
    "var TALLA_ORDER=['XS','S','M','L','XL','2XL','3XL','6','8','10','12','14'];",
)
html = html.replace(
    "var sn={'MIKA SPORT LITE':'Mika','NOAH SPORT LITE':'Noah','MAYA SPORT LITE':'Maya'};",
    "var sn={'CLASICA SPORT':'Clásica','SABRI SPORT':'Sabri','MAFE SPORT':'Mafe'};",
)

# filterModelButtons for Sport Mesh
html = html.replace(
    "    if(_fg==='CAB') show=(m==='NOAH SPORT LITE');\n    else if(_fg==='DAMA') show=(m==='MIKA SPORT LITE'||m==='MAYA SPORT LITE');",
    "    if(_fg==='CAB') show=(m==='CLASICA SPORT');\n    else if(_fg==='DAMA') show=(m==='SABRI SPORT'||m==='MAFE SPORT');\n    else if(_fg==='KIDS') show=(m==='CLASICA SPORT');",
)

# Reabast subtitle
html = html.replace(
    '🆕 MARGARITA proyectada: 2× velocidad GRIE · VELA: 1.5× GRIE · CERRO VERDE excluida',
    '🆕 VELA proyectada: 1.5× velocidad GRIE · CERRO VERDE excluida',
)

# DATA block
html = re.sub(
    r'var DATA=\{.*?\};\nvar _modelo',
    f'var DATA={data_json};\nvar _modelo',
    html,
    count=1,
    flags=re.DOTALL,
)

with open(DST, 'w', encoding='utf-8') as f:
    f.write(html)

print('sportmesh.html created')
print(f'  Sales: {len(data["raw_rows"])} rows, {data["total"]} units')
print(f'  Stock: {data["stock_total"]} units')
print(f'  Models: {", ".join(data["filtros"]["modelos"])}')
print(f'  Range: {data["date_range"]}')
