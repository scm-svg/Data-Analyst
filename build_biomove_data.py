#!/usr/bin/env python3
"""Generate embedded DATA JSON for BIOMOVE.html from sales and inventory CSVs."""
import csv
import json
import re
from collections import defaultdict

VENTAS = '/home/ubuntu/.cursor/projects/workspace/uploads/BIOMOVE_VENTAS_COMPLETO_c140.csv'
INV = '/home/ubuntu/.cursor/projects/workspace/uploads/BIOMOVE_INV_COMPELTO_8c4a.csv'

MESES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
]


def parse_num(s):
    return float(str(s).replace(',', '.'))


def mes_key(y, m):
    return f'{MESES[m - 1]}-{y}'


def mes_sort_key(m):
    p = m.split('-')
    return (int(p[1]), MESES.index(p[0]))


def norm_genero(g):
    g = g.strip().upper()
    if g in ('CABALLERO', 'CAB'):
        return 'CAB'
    if g in ('DAMA',):
        return 'DAMA'
    return g


def norm_modelo(m):
    u = m.strip().upper()
    if 'DOMINIC' in u:
        return 'DOMINIC BIO MOVE'
    if 'HELEN' in u:
        return 'HELEN BIO MOVE'
    if 'RUNNING TANK' in u:
        return 'RUNNING TANK BIO MOVE'
    return m.strip()


def norm_color(c):
    c = c.strip()
    c = re.sub(r'Azul Gris[^\w]*ceo', 'Azul Grisáceo', c, flags=re.I)
    c = c.replace('ï¿½', 'á').replace('Ã¡', 'á').replace('Ã©', 'é')
    if 'azul gris' in c.lower():
        return 'Azul Grisáceo'
    return c


def norm_tienda(t):
    t = ' '.join(t.strip().upper().split())
    mapping = {
        'GRIETA': 'GRIE',
        'GRIE': 'GRIE',
        'CERRO VERDE': 'CERRO VERDE',
        'GRANDPLAZ': 'GRANDPLAZ',
        'GRAND': 'GRANDPLAZ',
        'SAMBIL CHACAO': 'SAMBIL CHACAO',
        'CHACAO': 'SAMBIL CHACAO',
        'SAMBIL VALENCIA': 'SAMBIL VALENCIA',
        'SAMBIL': 'SAMBIL VALENCIA',
        'PEDIDOS': 'PEDIDOS',
        'WEB': 'WEB',
        'TOLON': 'TOLON',
        'LA VELA': 'VELA',
        'VELA': 'VELA',
        'TALLER': 'TALLER',
    }
    return mapping.get(t, t)


def loc_key(name):
    t = norm_tienda(name)
    inv_map = {
        'CHACAO': 'SAMBIL CHACAO',
        'SAMBIL': 'SAMBIL VALENCIA',
    }
    return inv_map.get(t, t)


def read_ventas():
    rows = []
    with open(VENTAS, encoding='latin-1') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            fecha = row.get('Fecha de la orden') or row[list(row.keys())[0]]
            d, m, y = fecha.split('/')
            y, m, d = int(y), int(m), int(d)
            qty = parse_num(row['Cant. ordenada'])
            if qty == 0:
                continue
            loc_col = next(k for k in row if 'ubic' in k.lower())
            rows.append({
                'tienda': norm_tienda(row[loc_col]),
                'genero': norm_genero(row['genero']),
                'color': norm_color(row['color']),
                'talla': row['talla'].strip(),
                'mes': mes_key(y, m),
                'modelo': norm_modelo(row['modelo']),
                'v': int(qty) if qty == int(qty) else qty,
            })
    return rows


def read_inventario():
    stock = defaultdict(int)
    stock_by_loc = defaultdict(lambda: defaultdict(int))
    inv_rows = []
    with open(INV, encoding='latin-1') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            loc_col = next(k for k in row if 'ubic' in k.lower())
            loc = loc_key(row[loc_col])
            modelo = norm_modelo(row['MODELO'])
            genero = norm_genero(row['GENERO'])
            color = norm_color(row['COLOR'])
            talla = row['TALLA'].strip()
            qty = int(parse_num(row['Cantidad en inventario']))
            key = f'{modelo}/{genero}/{color}/{talla}'
            stock[key] += qty
            stock_by_loc[loc][key] += qty
            inv_rows.append({
                'ubicacion': loc,
                'modelo': modelo,
                'genero': genero,
                'color': color,
                'talla': talla,
                'qty': qty,
                'sku': row['SKU'].strip(),
            })
    return dict(stock), {k: dict(v) for k, v in stock_by_loc.items()}, inv_rows


def build():
    raw_rows = read_ventas()
    stock, stock_by_loc, inv_rows = read_inventario()

    meses_order = sorted({r['mes'] for r in raw_rows}, key=mes_sort_key)
    meses_und = {m: sum(r['v'] for r in raw_rows if r['mes'] == m) for m in meses_order}

    stock_by_modelo = defaultdict(int)
    for k, v in stock.items():
        stock_by_modelo[k.split('/')[0]] += v

    tiendas = sorted(set({r['tienda'] for r in raw_rows}) | set(stock_by_loc.keys()))
    all_stores = sorted(set(tiendas) - {'TALLER', 'WEB', 'PEDIDOS'})
    inv_locations = sorted(stock_by_loc.keys())

    last_mes = meses_order[-1] if meses_order else ''
    es_parcial = True

    data = {
        'raw_rows': raw_rows,
        'stock': stock,
        'stock_by_loc': stock_by_loc,
        'inv_rows': inv_rows,
        'stock_by_modelo': dict(stock_by_modelo),
        'meses_order': meses_order,
        'meses_und': meses_und,
        'filtros': {
            'tiendas': tiendas,
            'generos': sorted({r['genero'] for r in raw_rows}),
            'colores': sorted({r['color'] for r in raw_rows}),
            'modelos': sorted({r['modelo'] for r in raw_rows}),
        },
        'es_parcial': es_parcial,
        'stock_total': sum(stock.values()),
        'total': sum(r['v'] for r in raw_rows),
        'all_stores': all_stores,
        'inv_locations': inv_locations,
        'date_range': f"{meses_order[0].split('-')[0].capitalize()} {meses_order[0].split('-')[1]} — {meses_order[-1].split('-')[0].capitalize()} {meses_order[-1].split('-')[1]}",
    }
    return data


if __name__ == '__main__':
    data = build()
    print(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
