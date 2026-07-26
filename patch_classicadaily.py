#!/usr/bin/env python3
"""Create classicadaily.html from full sportlite template (inventario + decisiones BIOMOVE)."""
import json
import re
import subprocess
import sys

from build_classicadaily_data import build

SRC = '/workspace/.sportlite_template.html'
DST = '/workspace/classicadaily.html'

# Use fully-patched sportlite from dashboard branch as template
subprocess.run(
    ['git', 'show', 'origin/cursor/sportlite-dashboard-update-e823:sportlite.html'],
    check=True,
    stdout=open(SRC, 'w', encoding='utf-8'),
)

data = build()
data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

with open(SRC, 'r', encoding='utf-8') as f:
    html = f.read()

# Branding
html = html.replace('Dashboard Sport Lite', 'Dashboard Clásica Daily')
html = html.replace('Sport Lite · <em id="titleModelo">Global</em>', 'Clásica Daily · <em id="titleModelo">Global</em>')
html = html.replace('Sport Lite · Dashboard de Ventas ·', 'Clásica Daily · Dashboard de Ventas ·')
html = re.sub(
    r'Dashboard de Ventas · [^<]+',
    f'Dashboard de Ventas · {data["date_range"]}',
    html,
    count=1,
)
html = re.sub(
    r'Sport Lite · Dashboard de Ventas · [^<]+',
    f'Clásica Daily · Dashboard de Ventas · {data["date_range"]}',
    html,
    count=1,
)
html = html.replace("a.download='Sport_Lite.csv'", "a.download='Clasica_Daily.csv'")

old_buttons = """  <button class="mbtn" data-m="MIKA SPORT LITE" onclick="setModelo('MIKA SPORT LITE')">🏃 Mika <span class="mcnt" id="mcnt_MIKA">0</span></button>
  <button class="mbtn" data-m="NOAH SPORT LITE" onclick="setModelo('NOAH SPORT LITE')">🏃 Noah <span class="mcnt" id="mcnt_NOAH">0</span></button>
  <button class="mbtn" data-m="MAYA SPORT LITE" onclick="setModelo('MAYA SPORT LITE')">🏃 Maya <span class="mcnt" id="mcnt_MAYA">0</span></button>"""

new_buttons = """  <button class="mbtn" data-m="CLASICA DAILY 3.0" onclick="setModelo('CLASICA DAILY 3.0')">👔 Daily 3.0 <span class="mcnt" id="mcnt_V30">0</span></button>
  <button class="mbtn" data-m="CLASICA DAILY 2.0" onclick="setModelo('CLASICA DAILY 2.0')">👔 Daily 2.0 <span class="mcnt" id="mcnt_V20">0</span></button>
  <button class="mbtn" data-m="CLASICA DAILY" onclick="setModelo('CLASICA DAILY')">👔 Daily <span class="mcnt" id="mcnt_DAILY">0</span></button>"""
html = html.replace(old_buttons, new_buttons)

html = html.replace(
    "var MICO={'MIKA SPORT LITE':'🏃','NOAH SPORT LITE':'🏃','MAYA SPORT LITE':'🏃'};",
    "var MICO={'CLASICA DAILY 3.0':'👔','CLASICA DAILY 2.0':'👔','CLASICA DAILY':'👔'};",
)
html = html.replace(
    "var MODELO_ID={'MIKA SPORT LITE':'MIKA','NOAH SPORT LITE':'NOAH','MAYA SPORT LITE':'MAYA'};",
    "var MODELO_ID={'CLASICA DAILY 3.0':'V30','CLASICA DAILY 2.0':'V20','CLASICA DAILY':'DAILY'};",
)
html = html.replace(
    "var sn={'MIKA SPORT LITE':'Mika','NOAH SPORT LITE':'Noah','MAYA SPORT LITE':'Maya'};",
    "var sn={'CLASICA DAILY 3.0':'Daily 3.0','CLASICA DAILY 2.0':'Daily 2.0','CLASICA DAILY':'Daily'};",
)

html = html.replace(
    "    if(_fg==='CAB') show=(m==='NOAH SPORT LITE');\n    else if(_fg==='DAMA') show=(m==='MIKA SPORT LITE'||m==='MAYA SPORT LITE');",
    """    if(_fg){
      var has=DATA.raw_rows.some(function(r){return r.modelo===m&&r.genero===_fg;});
      show=has;
    }""",
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

print('classicadaily.html created (full template)')
print(f'  Sales: {len(data["raw_rows"])} rows, {data["total"]} units')
print(f'  Stock: {data["stock_total"]} units')
print(f'  Models: {", ".join(data["filtros"]["modelos"])}')
print(f'  Range: {data["date_range"]}')
