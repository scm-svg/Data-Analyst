#!/usr/bin/env python3
"""Create classicadaily.html from sportlite.html template."""
import json
import re
import shutil

from build_classicadaily_data import build

SRC = '/workspace/sportlite.html'
DST = '/workspace/classicadaily.html'

shutil.copy(SRC, DST)

data = build()
data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

with open(DST, 'r', encoding='utf-8') as f:
    html = f.read()

# Branding
html = html.replace('Dashboard Sport Lite', 'Dashboard Clásica Daily')
html = html.replace('Sport Lite · <em id="titleModelo">Global</em>', 'Clásica Daily · <em id="titleModelo">Global</em>')
html = html.replace('Sport Lite · Dashboard de Ventas · Agosto 2025 — Julio 2026', f'Clásica Daily · Dashboard de Ventas · {data["date_range"]}')
html = html.replace('Dashboard de Ventas · Agosto 2025 — Julio 2026', f'Dashboard de Ventas · {data["date_range"]}')
html = html.replace("a.download='Sport_Lite.csv'", "a.download='Clasica_Daily.csv'")

# Single model buttons
old_buttons = """  <button class="mbtn" data-m="MIKA SPORT LITE" onclick="setModelo('MIKA SPORT LITE')">🏃 Mika <span class="mcnt" id="mcnt_MIKA">0</span></button>
  <button class="mbtn" data-m="NOAH SPORT LITE" onclick="setModelo('NOAH SPORT LITE')">🏃 Noah <span class="mcnt" id="mcnt_NOAH">0</span></button>
  <button class="mbtn" data-m="MAYA SPORT LITE" onclick="setModelo('MAYA SPORT LITE')">🏃 Maya <span class="mcnt" id="mcnt_MAYA">0</span></button>"""

new_buttons = """  <button class="mbtn" data-m="CLASICA DAILY" onclick="setModelo('CLASICA DAILY')">👔 Clásica Daily <span class="mcnt" id="mcnt_DAILY">0</span></button>"""
html = html.replace(old_buttons, new_buttons)

html = html.replace(
    "var MICO={'MIKA SPORT LITE':'🏃','NOAH SPORT LITE':'🏃','MAYA SPORT LITE':'🏃'};",
    "var MICO={'CLASICA DAILY':'👔'};",
)
html = html.replace(
    "var MODELO_ID={'MIKA SPORT LITE':'MIKA','NOAH SPORT LITE':'NOAH','MAYA SPORT LITE':'MAYA'};",
    "var MODELO_ID={'CLASICA DAILY':'DAILY'};",
)
html = html.replace(
    "var TALLA_ORDER=['XS','S','M','L','XL','2XL','3XL'];",
    "var TALLA_ORDER=['XS','S','M','L','XL','2XL','3XL','6','8','10','12','14'];",
)
html = html.replace(
    "var sn={'MIKA SPORT LITE':'Mika','NOAH SPORT LITE':'Noah','MAYA SPORT LITE':'Maya'};",
    "var sn={'CLASICA DAILY':'Clásica Daily'};",
)

html = html.replace(
    "    if(_fg==='CAB') show=(m==='NOAH SPORT LITE');\n    else if(_fg==='DAMA') show=(m==='MIKA SPORT LITE'||m==='MAYA SPORT LITE');",
    "    if(_fg==='CAB'||_fg==='DAMA'||_fg==='KIDS') show=(m==='CLASICA DAILY');",
)

html = html.replace(
    '🆕 MARGARITA proyectada: 2× velocidad GRIE · VELA: 1.5× GRIE · CERRO VERDE excluida',
    '🆕 VELA proyectada: 1.5× velocidad GRIE · CERRO VERDE excluida',
)

html = re.sub(
    r'var DATA=\{.*?\};\nvar _modelo',
    f'var DATA={data_json};\nvar _modelo',
    html,
    count=1,
    flags=re.DOTALL,
)

with open(DST, 'w', encoding='utf-8') as f:
    f.write(html)

print('classicadaily.html created')
print(f'  Sales: {len(data["raw_rows"])} rows, {data["total"]} units')
print(f'  Stock: {data["stock_total"]} units')
print(f'  Models: {", ".join(data["filtros"]["modelos"])}')
print(f'  Range: {data["date_range"]}')
