#!/usr/bin/env python3
"""
Genera el dashboard CLASSIC POLO reutilizando exactamente la estructura del
dashboard EXPLORE PANTS (dash_explorepants.html), cambiando unicamente el
modelo y la data (ventas + inventario de Classic Polo).

- Ventas:     CLASSIC_POLO_VENTAS_ACTUALIZADAS_ORDENADAS_*.csv
- Inventario: classic_polo_inventario_arreglado_*.csv
"""
import csv
import json
import re
from collections import defaultdict

import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _first_existing(*paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return paths[0]


VENTAS = _first_existing(
    os.path.join(_HERE, 'data', 'classic_polo', 'classic_polo_ventas.csv'),
    '/home/ubuntu/.cursor/projects/workspace/uploads/CLASSIC_POLO_VENTAS_ACTUALIZADAS_ORDENADAS_e888.csv',
)
INV = _first_existing(
    os.path.join(_HERE, 'data', 'classic_polo', 'classic_polo_inventario.csv'),
    '/home/ubuntu/.cursor/projects/workspace/uploads/classic_polo_inventario_arreglado_176a.csv',
)
TEMPLATE = os.path.join(_HERE, 'dash_explorepants.html')
OUT = os.path.join(_HERE, 'dash_classicpolo.html')

MODELO = 'CLASSIC POLO'
# Classic Polo no tiene dimension de genero en la data (tallas S-2XL, linea unica).
# Se usa una sola linea "CAB" (caballero/unisex adulto) para mantener identica la
# estructura del template (iconos, colores y filtro de genero siguen funcionando).
LINEA = 'CAB'

# ── Mapeo de nombres de tienda a las claves canonicas del dashboard ──
STORE_MAP_VENTAS = {
    'la grieta': 'GRIE',
    'grieta': 'GRIE',
    'sambil valencia': 'SAMBIL',
    'sambil chacao': 'CHACAO',
    'chacao': 'CHACAO',
    'cerro verde': 'CERRO VERDE',
    'grandplaz': 'GRAND',
    'tolon': 'TOLON',
    'la vela': 'VELA',
    'vela': 'VELA',
    'pedidos': 'PEDIDOS',
    'web': 'WEB',
    'taller': 'TALLER',
}
STORE_MAP_INV = dict(STORE_MAP_VENTAS)
STORE_MAP_INV.update({'grandplaz': 'GRAND'})

MESES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
         'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}
MES_SHORT = {1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
             7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'}


def norm_store(name, mapping):
    key = name.strip().lower()
    if key in mapping:
        return mapping[key]
    return name.strip().upper()


def mkey(mes):
    n, y = mes.split('-')
    return (int(y), MESES[n])


def to_num(s):
    return float(s.replace('.', '').replace(',', '.')) if s.strip() else 0.0


def read_csv(path):
    with open(path, encoding='latin-1') as f:
        rows = list(csv.reader(f, delimiter=';'))
    return rows[0], rows[1:]


def build_data():
    # ── VENTAS ──
    _, vr = read_csv(VENTAS)
    # cols: Fecha;SKU;Variante;MODELO;COLOR;TALLA;Cant;UBIC;FECHA(mes-anio)
    agg = defaultdict(float)  # (tienda,color,talla,mes) -> neto
    meses_set = set()
    for r in vr:
        color = r[4].strip()
        talla = r[5].strip()
        qty = to_num(r[6])
        tienda = norm_store(r[7], STORE_MAP_VENTAS)
        mes = r[8].strip()
        meses_set.add(mes)
        agg[(tienda, color, talla, mes)] += qty

    # raw_rows: solo grupos con neto positivo (netea devoluciones)
    raw_rows = []
    for (tienda, color, talla, mes), v in agg.items():
        vi = int(round(v))
        if vi > 0:
            raw_rows.append({'tienda': tienda, 'genero': LINEA, 'color': color,
                             'talla': talla, 'mes': mes, 'v': vi})
    raw_rows.sort(key=lambda r: (r['tienda'], r['color'], r['talla'], mkey(r['mes'])))

    meses_order = sorted(meses_set, key=mkey)
    meses_labels = [MES_SHORT[mkey(m)[1]] + ' ' + str(mkey(m)[0])[-2:] for m in meses_order]

    meses_und = {m: 0 for m in meses_order}
    for r in raw_rows:
        meses_und[r['mes']] += r['v']

    total = sum(r['v'] for r in raw_rows)

    tiendas = sorted(set(r['tienda'] for r in raw_rows))
    colores = sorted(set(r['color'] for r in raw_rows))

    # ── INVENTARIO ──
    _, ir = read_csv(INV)
    # cols: Ubic;Producto;SKU;MODELO;COLOR;TALLA;Cantidad
    stock = defaultdict(int)
    stock_by_store = defaultdict(lambda: defaultdict(int))
    for r in ir:
        store = norm_store(r[0], STORE_MAP_INV)
        color = r[4].strip()
        talla = r[5].strip()
        qty = int(round(to_num(r[6])))
        if qty == 0:
            continue
        key = f'{color}/{talla}/{LINEA}'
        stock[key] += qty
        stock_by_store[store][key] += qty

    stock_total = sum(stock.values())

    # orden de tiendas para inventario: fisicas por volumen desc, TALLER al final
    inv_stores = [s for s in stock_by_store.keys()]
    phys = [s for s in inv_stores if s != 'TALLER']
    phys.sort(key=lambda s: -sum(stock_by_store[s].values()))
    stores_order = phys + (['TALLER'] if 'TALLER' in inv_stores else [])

    # ── FORECAST line_order (misma metodologia que el template) ──
    # es_parcial=True => ultimo mes (julio-2026) esta incompleto.
    # m1 = ventas del ultimo mes COMPLETO, m2 = mes completo anterior.
    es_parcial = True
    if es_parcial and len(meses_order) >= 3:
        last_full = meses_order[-2]
        prev_full = meses_order[-3]
    else:
        last_full = meses_order[-1]
        prev_full = meses_order[-2] if len(meses_order) >= 2 else meses_order[-1]

    m1 = sum(r['v'] for r in raw_rows if r['mes'] == last_full)
    m2 = sum(r['v'] for r in raw_rows if r['mes'] == prev_full)
    line_order = {LINEA: {'m1': m1, 'm2': m2}}

    # var_pct (no usado por el JS, se incluye por fidelidad de esquema)
    var_pct = round((m1 - m2) / m2 * 100, 1) if m2 else 0.0

    per_first = meses_labels[0]
    per_last = meses_labels[-1]

    data = {
        'nombre': MODELO,
        'periodo': f'{per_first} — {per_last}',
        'total': total,
        'var_pct': var_pct,
        'es_parcial': es_parcial,
        'n_sem': len(meses_order) * 4,
        'meses_order': meses_order,
        'meses_labels': meses_labels,
        'meses_und': meses_und,
        'lineas': [LINEA],
        'tiendas_list': tiendas,
        'filtros': {
            'tiendas': tiendas,
            'generos': [LINEA],
            'colores': colores,
            'meses': meses_order,
        },
        'raw_rows': raw_rows,
        'stock': dict(stock),
        'stock_total': stock_total,
        'line_order': line_order,
        'method': 'proportional',
        'stock_by_store': {s: dict(stock_by_store[s]) for s in stores_order},
        'stores_order': stores_order,
    }
    return data


def main():
    data = build_data()
    html = open(TEMPLATE, encoding='utf-8').read()

    # 1) Titulo
    html = html.replace('<title>Dashboard · EXPLORE PANTS</title>',
                        '<title>Dashboard · CLASSIC POLO</title>')

    # 2) Reemplazar la linea de datos (const DATA = {...};)
    lines = html.split('\n')
    data_idx = None
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith('const DATA'):
            data_idx = i
            break
    assert data_idx is not None, 'No se encontro la linea const DATA'
    lines[data_idx] = 'const DATA = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';'
    html = '\n'.join(lines)

    # 3) Anadir regla de color 'beige' a la funcion cn() (mejora cosmetica del mapeo de colores)
    if "s.indexOf('beige')" not in html:
        html = html.replace(
            "if(s.indexOf('kaki')>=0||s.indexOf('khaki')>=0)return'#a3956b';",
            "if(s.indexOf('beige')>=0)return'#cbb891';if(s.indexOf('kaki')>=0||s.indexOf('khaki')>=0)return'#a3956b';",
            1,
        )

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(html)

    # ── Resumen por consola ──
    print('=== CLASSIC POLO · DATA generada ===')
    print('periodo        :', data['periodo'])
    print('total ventas   :', data['total'])
    print('meses          :', len(data['meses_order']), data['meses_order'][0], '->', data['meses_order'][-1])
    print('tiendas        :', data['tiendas_list'])
    print('colores        :', data['filtros']['colores'])
    print('tallas         :', sorted(set(r['talla'] for r in data['raw_rows'])))
    print('raw_rows       :', len(data['raw_rows']))
    print('stock_total    :', data['stock_total'])
    print('stores_order   :', data['stores_order'])
    print('line_order     :', data['line_order'])
    print('meses_und      :', data['meses_und'])
    print('archivo        :', OUT)


if __name__ == '__main__':
    main()
