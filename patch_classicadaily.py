#!/usr/bin/env python3
"""Create classicadaily.html — solo CLASICA DAILY 3.0."""
import json
import re
import subprocess

from build_classicadaily_data import build

SRC = '/workspace/.sportlite_template.html'
DST = '/workspace/classicadaily.html'

subprocess.run(
    ['git', 'show', 'origin/cursor/sportlite-dashboard-update-e823:sportlite.html'],
    check=True,
    stdout=open(SRC, 'w', encoding='utf-8'),
)

data = build()
data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

with open(SRC, 'r', encoding='utf-8') as f:
    html = f.read()

html = html.replace('Dashboard Sport Lite', 'Dashboard Daily 3.0 - Clásica')
html = html.replace(
    '<h1>Sport Lite · <em id="titleModelo">Global</em></h1>',
    '<h1>Daily 3.0 - <em>Clásica</em></h1>',
)
html = html.replace(
    'Sport Lite · Dashboard de Ventas ·',
    'Daily 3.0 - Clásica · Dashboard de Ventas ·',
)
html = re.sub(
    r'<div class="footer">Sport Lite · Dashboard de Ventas · [^<]+</div>',
    f'<div class="footer">Daily 3.0 - Clásica · Dashboard de Ventas · {data["date_range"]}</div>',
    html,
    count=1,
)
html = re.sub(
    r'<p>Dashboard de Ventas · [^<]+</p>',
    f'<p>Dashboard de Ventas · {data["date_range"]}</p>',
    html,
    count=1,
)
html = html.replace("a.download='Sport_Lite.csv'", "a.download='Clasica_Daily_3.0.csv'")

# Ocultar barra de modelos (un solo modelo en los datos)
html = html.replace('<div class="mbar">', '<div class="mbar" style="display:none">')

html = html.replace(
    "var MICO={'MIKA SPORT LITE':'🏃','NOAH SPORT LITE':'🏃','MAYA SPORT LITE':'🏃'};",
    "var MICO={'CLASICA DAILY 3.0':'👔'};",
)
html = html.replace(
    "var MODELO_ID={'MIKA SPORT LITE':'MIKA','NOAH SPORT LITE':'NOAH','MAYA SPORT LITE':'MAYA'};",
    "var MODELO_ID={'CLASICA DAILY 3.0':'V30'};",
)
html = html.replace(
    "var sn={'MIKA SPORT LITE':'Mika','NOAH SPORT LITE':'Noah','MAYA SPORT LITE':'Maya'};",
    "var sn={'CLASICA DAILY 3.0':'Daily 3.0'};",
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

print('classicadaily.html created (solo Daily 3.0)')
print(f'  Sales: {len(data["raw_rows"])} rows, {data["total"]} units')
print(f'  Stock: {data["stock_total"]} units')
print(f'  Models: {", ".join(data["filtros"]["modelos"])}')
print(f'  Range: {data["date_range"]}')
