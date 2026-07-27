#!/usr/bin/env python3
"""Patch Classic Polo dashboard: new ventas + inventario filter fix."""
import json
import re
import shutil

from build_classicpolo_data import build
from classicpolo_decisiones_patches import (
    MAKE_ROW_NEW,
    MAKE_ROW_OLD,
    PROD_BLOCK_NEW,
    PROD_BLOCK_OLD,
)

SRC = '/home/ubuntu/.cursor/projects/workspace/uploads/index__2__3d1e.html'
DST = '/workspace/classicpolo.html'

shutil.copy(SRC, DST)

data = build()
data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

with open(DST, 'r', encoding='utf-8') as f:
    html = f.read()

html = re.sub(
    r'var DATA=\{.*?\};\nvar _modelo',
    f'var DATA={data_json};\nvar _modelo',
    html,
    count=1,
    flags=re.DOTALL,
)

# Fix: al cambiar filtros en pestaña Inventario, aTab() devolvía 'decisiones'
html = html.replace(
    "function aTab(){var t=document.querySelector('.tab.active');if(!t)return'resumen';var tx=t.textContent;if(tx.indexOf('Resumen')>=0)return'resumen';if(tx.indexOf('Color')>=0)return'colores';if(tx.indexOf('Talla')>=0)return'tallas';if(tx.indexOf('Tienda')>=0)return'tiendas';return'decisiones';}",
    "function aTab(){var t=document.querySelector('.tab.active');if(!t)return'resumen';var tx=t.textContent;if(tx.indexOf('Resumen')>=0)return'resumen';if(tx.indexOf('Color')>=0)return'colores';if(tx.indexOf('Talla')>=0)return'tallas';if(tx.indexOf('Tienda')>=0)return'tiendas';if(tx.indexOf('Inventario')>=0)return'inventario';return'decisiones';}",
)

# Inventario: totales netos (negativos descontados)
html = html.replace(
    "  stores.forEach(function(st){var t=entries(st).reduce(function(a,x){return a+x.v;},0);totAll+=t;if(st==='TALLER')totT+=t;});",
    "  stores.forEach(function(st){entries(st).forEach(function(x){totAll+=x.v;if(st==='TALLER')totT+=x.v;});});",
)

# Update date in header if present
html = re.sub(
    r'<p>Dashboard de Ventas · [^<]+</p>',
    f'<p>Dashboard de Ventas · {data["date_range"]}</p>',
    html,
    count=1,
)

# Decisiones: VELA duplicada, producción neta vs stock
html = html.replace(
    'var storeList=ALL_STORES.concat(NEW_STORES);',
    "var storeList=[],seen={};"
    "ALL_STORES.forEach(function(s){if(seen[s])return;if(NEW_STORES.indexOf(s)>=0)return;seen[s]=1;storeList.push(s);});"
    "NEW_STORES.forEach(function(s){if(!seen[s]){seen[s]=1;storeList.push(s);}});",
)
html = html.replace(
    '<div class="sub">Sugerencia proporcional por color y talla · Clic en color para detalle · Basado en meses completos (excluye el mes en curso)</div>',
    '<div class="sub">Demanda proporcional menos stock PT · Verde = unidades netas a producir · STK rojo = posible sobrestock en esa talla</div>',
)
html = html.replace(
    '<div class="sub">Distribución sugerida · <span style="color:#f97316">🆕 VELA (1.5× GRIETA) es tienda nueva proyectada</span> · TOLON ya opera con histórico propio</div>',
    '<div class="sub">Distribución sugerida · <span style="color:#f97316">🆕 VELA: una sola fila con proyección 1.5× GRIETA</span> (ventas recién arrancando) · TOLON con histórico propio</div>',
)
if MAKE_ROW_OLD in html:
    html = html.replace(MAKE_ROW_OLD, MAKE_ROW_NEW)
if PROD_BLOCK_OLD in html:
    html = html.replace(PROD_BLOCK_OLD, PROD_BLOCK_NEW)

with open(DST, 'w', encoding='utf-8') as f:
    f.write(html)

print('classicpolo.html updated')
print(f'  Sales: {len(data["raw_rows"])} rows, {data["total"]} units')
print(f'  Range: {data["date_range"]}')
