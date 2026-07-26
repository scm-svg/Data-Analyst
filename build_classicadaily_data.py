#!/usr/bin/env python3
"""Generate embedded DATA JSON for classicadaily.html from Excel."""
import json
from collections import defaultdict

import pandas as pd

XLSX = '/home/ubuntu/.cursor/projects/workspace/uploads/CLASICA_DAILY_COMPLETO_ace7.xlsx'
MESES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]
TALLA_ORDER = ['XS', 'S', 'M', 'L', 'XL', '2XL', '3XL', '6', '8', '10', '12', '14']
BASE_MESES = ['febrero-2026', 'marzo-2026', 'abril-2026']


def mes_sort_key(m):
    p = m.split('-')
    return (int(p[1]), MESES.index(p[0]))


def mes_key_from_parts(month, year):
    return f'{MESES[int(month) - 1]}-{year}'


def parse_mes(row):
    raw = row.get('fecha mes año')
    if pd.notna(raw):
        s = str(raw).strip()
        if '/' in s:
            mm, yy = s.split('/')
            return mes_key_from_parts(mm, yy)
    fecha = row.get('Fecha de la orden')
    if pd.notna(fecha):
        dt = pd.to_datetime(fecha)
        return mes_key_from_parts(dt.month, dt.year)
    return None


def norm_genero(g):
    g = str(g).strip().upper()
    if g in ('CABALLERO', 'CAB'):
        return 'CAB'
    if g == 'DAMA':
        return 'DAMA'
    if g == 'KIDS':
        return 'KIDS'
    return g


def norm_modelo(m):
    s = str(m).strip().upper()
    s = s.replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')
    if 'ELIMINAR' in s:
        return None
    if '3.0' in s or '3,0' in s:
        return 'CLASICA DAILY 3.0'
    if '2.0' in s or '2,0' in s:
        return 'CLASICA DAILY 2.0'
    if 'DAILY' in s or 'CLASICA' in s:
        return 'CLASICA DAILY'
    return None


def norm_color(c):
    c = str(c).strip()
    if ' - ' in c:
        c = c.split(' - ')[0].strip()
    return c


def norm_tienda(t):
    t = ' '.join(str(t).strip().upper().split())
    mapping = {
        'GRIETA': 'GRIE',
        'LA GRIETA': 'GRIE',
        'GRIE': 'GRIE',
        'CERRO VERDE': 'CERRO VERDE',
        'CERRV': 'CERRO VERDE',
        'GRANDPLAZ': 'GRANDPLAZ',
        'GRAND': 'GRANDPLAZ',
        'GRACH': 'GRANDPLAZ',
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
        'TH': 'TALLER',
    }
    return mapping.get(t, t)


def loc_key(name):
    return norm_tienda(name)


def talla_sort(t):
    try:
        return TALLA_ORDER.index(str(t))
    except ValueError:
        return 99


def read_ventas():
    df = pd.read_excel(XLSX, sheet_name='Venta')
    rows = []
    for _, row in df.iterrows():
        modelo = norm_modelo(row['modelo'])
        if not modelo:
            continue
        qty = float(row['Cant. ordenada'])
        if qty == 0:
            continue
        mes = parse_mes(row)
        if not mes:
            continue
        talla = row['talla']
        if pd.isna(talla):
            continue
        rows.append({
            'tienda': norm_tienda(row['Vendedor']),
            'genero': norm_genero(row['genero']),
            'color': norm_color(row['color']),
            'talla': str(talla).strip(),
            'mes': mes,
            'modelo': modelo,
            'v': int(qty) if qty == int(qty) else qty,
        })
    return rows


def read_inventario():
    df = pd.read_excel(XLSX, sheet_name='Inventario')
    stock = defaultdict(int)
    stock_by_loc = defaultdict(lambda: defaultdict(int))
    inv_rows = []
    for _, row in df.iterrows():
        modelo = norm_modelo(row['MODELO'])
        if not modelo:
            continue
        loc = loc_key(row['Ubicación'])
        genero = norm_genero(row['GENERO'])
        color = norm_color(row['COLOR'])
        talla = str(row['TALLA']).strip()
        qty = int(float(row['Cantidad en inventario']))
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
            'sku': str(row['SKU']).strip(),
        })
    return dict(stock), {k: dict(v) for k, v in stock_by_loc.items()}, inv_rows


def compute_prod_curve(raw_rows, stock, stock_by_loc):
    base = [m for m in BASE_MESES if any(r['mes'] == m for r in raw_rows)]
    if not base:
        base = sorted({r['mes'] for r in raw_rows}, key=mes_sort_key)[-3:]

    sales = defaultdict(int)
    for r in raw_rows:
        if r['mes'] in base:
            k = (r['modelo'], r['genero'], r['color'], r['talla'])
            sales[k] += r['v']

    stk_taller = stock_by_loc.get('TALLER', {})
    curve = []
    keys = set(sales.keys())
    for k in stock:
        parts = k.split('/')
        keys.add((parts[0], parts[1], parts[2], parts[3]))

    for modelo, genero, color, talla in sorted(keys):
        v3m = sales.get((modelo, genero, color, talla), 0)
        v_mes = round(v3m / len(base), 1) if base else 0
        key = f'{modelo}/{genero}/{color}/{talla}'
        stk_total = stock.get(key, 0)
        stk_pt = stk_taller.get(key, 0)
        cobertura = round(stk_total / v_mes, 1) if v_mes > 0 else 0
        need = lambda n, vm=v_mes, st=stk_total: max(0, round(vm * n - st))
        curve.append({
            'modelo': modelo,
            'genero': genero,
            'talla': talla,
            'color': color,
            'v3m': v3m,
            'v_mes': v_mes,
            'stk_total': stk_total,
            'stk_pt': stk_pt,
            'cobertura': cobertura,
            'need_1m': need(1),
            'need_2m': need(2),
            'need_3m': need(3),
            'tsort': talla_sort(talla),
        })
    curve.sort(key=lambda r: (r['modelo'], r['color'], r['tsort']))
    return curve, base


def compute_summary_prod(prod_curve):
    summary = {}
    for modelo in sorted({r['modelo'] for r in prod_curve}):
        rows = [r for r in prod_curve if r['modelo'] == modelo]
        summary[modelo] = {
            'v_mes': round(sum(r['v_mes'] for r in rows), 1),
            'stk_total': sum(r['stk_total'] for r in rows),
            'need_1m': sum(r['need_1m'] for r in rows),
            'need_2m': sum(r['need_2m'] for r in rows),
            'need_3m': sum(r['need_3m'] for r in rows),
            'stk_pt': sum(r['stk_pt'] for r in rows),
        }
    return summary


def compute_margarita(raw_rows, mult=2.0):
    base = [m for m in BASE_MESES if any(r['mes'] == m for r in raw_rows)]
    if not base:
        base = sorted({r['mes'] for r in raw_rows}, key=mes_sort_key)[-3:]

    grie_sales = defaultdict(float)
    for r in raw_rows:
        if r['tienda'] == 'GRIE' and r['mes'] in base:
            k = (r['modelo'], r['genero'], r['color'], r['talla'])
            grie_sales[k] += r['v']

    skus = []
    v_mes_total = 0
    for (modelo, genero, color, talla), v3m in sorted(grie_sales.items()):
        v_mes = round(v3m / len(base) * mult, 4)
        if v_mes <= 0:
            continue
        need = lambda n, vm=v_mes: max(0, round(vm * n))
        skus.append({
            'MODELO': modelo,
            'GENERO': genero,
            'COLOR': color,
            'TALLA': talla,
            'need_1m': need(1),
            'need_2m': need(2),
            'need_3m': need(3),
            'v_mes': v_mes,
        })
        v_mes_total += v_mes

    return {
        'v_mes': round(v_mes_total, 1),
        'need_1m': sum(s['need_1m'] for s in skus),
        'need_2m': sum(s['need_2m'] for s in skus),
        'need_3m': sum(s['need_3m'] for s in skus),
        'nota': f'{mult:.0f}× velocidad GRIE (tienda nueva proyectada)'.replace('.0×', '×'),
        'skus': skus,
    }


def compute_tolon(raw_rows):
    base = [m for m in BASE_MESES if any(r['mes'] == m for r in raw_rows)]
    if not base:
        base = sorted({r['mes'] for r in raw_rows}, key=mes_sort_key)[-3:]
    v = sum(r['v'] for r in raw_rows if r['tienda'] == 'TOLON' and r['mes'] in base)
    return {'v_base': v, 'v_mes': round(v / len(base), 1) if base else 0}


def build():
    raw_rows = read_ventas()
    stock, stock_by_loc, inv_rows = read_inventario()
    prod_curve, _ = compute_prod_curve(raw_rows, stock, stock_by_loc)
    summary_prod = compute_summary_prod(prod_curve)
    margarita = compute_margarita(raw_rows, mult=2.0)

    meses_order = sorted({r['mes'] for r in raw_rows}, key=mes_sort_key)
    meses_und = {m: sum(r['v'] for r in raw_rows if r['mes'] == m) for m in meses_order}

    stock_by_modelo = defaultdict(int)
    for k, v in stock.items():
        stock_by_modelo[k.split('/')[0]] += v

    tiendas = sorted(set({r['tienda'] for r in raw_rows}) | set(stock_by_loc.keys()))
    all_stores = sorted(set(tiendas) - {'TALLER', 'WEB', 'PEDIDOS'})
    stock_pt_total = sum(stock_by_loc.get('TALLER', {}).values())

    return {
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
        'es_parcial': False,
        'stock_total': sum(stock.values()),
        'stock_pt_total': stock_pt_total,
        'total': sum(r['v'] for r in raw_rows),
        'all_stores': all_stores,
        'inv_locations': sorted(stock_by_loc.keys()),
        'prod_curve': prod_curve,
        'summary_prod': summary_prod,
        'margarita': margarita,
        'tolon': compute_tolon(raw_rows),
        'date_range': (
            f"{meses_order[0].split('-')[0].capitalize()} {meses_order[0].split('-')[1]} — "
            f"{meses_order[-1].split('-')[0].capitalize()} {meses_order[-1].split('-')[1]}"
        ),
    }


if __name__ == '__main__':
    data = build()
    print(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    import sys
    print('\n--- stats ---', file=sys.stderr)
    print(f'Sales rows: {len(data["raw_rows"])}, units: {data["total"]}', file=sys.stderr)
    print(f'Stock: {data["stock_total"]}, models: {data["filtros"]["modelos"]}', file=sys.stderr)
    print(f'Range: {data["date_range"]}', file=sys.stderr)
