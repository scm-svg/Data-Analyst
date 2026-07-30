#!/usr/bin/env python3
"""Generate DATA JSON for Colección Spots dashboard (Manga Corta / Manga Larga)."""
import json
from collections import defaultdict

import pandas as pd

XLSX = '/home/ubuntu/.cursor/projects/workspace/uploads/SPOTS_SPORTS_COMPLETO_db0d.xlsx'
MESES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]
TALLA_ORDER = ['XS', 'S', 'M', 'L', 'XL', '2XL', '3XL', '4XL']
MODEL_CORTA = 'SPOTS MANGA CORTA'
MODEL_LARGA = 'SPOTS MANGA LARGA'


def mes_sort_key(m):
    p = m.split('-')
    return (int(p[1]), MESES.index(p[0]))


def mes_key_from_str(s):
    mm, yy = str(s).strip().split('/')
    return f'{MESES[int(mm) - 1]}-{yy}'


def norm_genero(g):
    g = str(g).strip().upper()
    if g in ('CABALLERO', 'CAB'):
        return 'CAB'
    if g == 'DAMA':
        return 'DAMA'
    return g


def norm_modelo(raw):
    s = str(raw).strip().upper()
    if 'MANGA CORTA' in s:
        return MODEL_CORTA
    if 'MANGA LARGA' in s:
        return MODEL_LARGA
    return None


def norm_color(c):
    c = str(c).strip()
    if ' - ' in c:
        c = c.split(' - ')[0].strip()
    if '/' in c:
        c = c.split('/')[0].strip()
    return c


def norm_tienda(t):
    t = ' '.join(str(t).strip().upper().split())
    mapping = {
        'LA VELA': 'VELA',
        'VELA': 'VELA',
        'WEB': 'WEB',
        'PEDIDOS': 'PEDIDOS',
        'TALLER PT': 'TALLER',
        'TALLER': 'TALLER',
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
        talla = row['TALLA']
        if pd.isna(talla):
            continue
        rows.append({
            'tienda': norm_tienda(row['tienda / ubicación']),
            'genero': norm_genero(row['GENERO']),
            'color': norm_color(row['COLOR']),
            'talla': str(talla).strip(),
            'mes': mes_key_from_str(row['fecha (mes año)']),
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


def base_months(meses_order, es_parcial):
    m = meses_order[:]
    if es_parcial and len(m) > 1:
        m = m[:-1]
    if not m:
        m = meses_order[-1:]
    return m[-3:]


def compute_prod_curve(raw_rows, stock, stock_by_loc, meses_order, es_parcial):
    base = base_months(meses_order, es_parcial)
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

    n_base = max(len(base), 1)
    for modelo, genero, color, talla in sorted(keys):
        v_base = sales.get((modelo, genero, color, talla), 0)
        v_mes = round(v_base / n_base, 1) if base else 0
        key = f'{modelo}/{genero}/{color}/{talla}'
        stk_total = stock.get(key, 0)
        stk_pt = stk_taller.get(key, 0)
        cobertura = round(stk_total / v_mes, 1) if v_mes > 0 else (99 if stk_total > 0 else 0)
        need = lambda n, vm=v_mes, st=stk_total: max(0, round(vm * n - st))
        curve.append({
            'modelo': modelo,
            'genero': genero,
            'talla': talla,
            'color': color,
            'v3m': v_base,
            'v_mes': v_mes,
            'stk_total': stk_total,
            'stk_pt': stk_pt,
            'cobertura': cobertura,
            'need_1m': need(1),
            'need_2m': need(2),
            'need_3m': need(3),
            'tsort': talla_sort(talla),
        })
    curve.sort(key=lambda r: (r['modelo'], r['genero'], r['color'], r['tsort']))
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


def empty_margarita():
    return {
        'v_mes': 0,
        'need_1m': 0,
        'need_2m': 0,
        'need_3m': 0,
        'nota': '',
        'skus': [],
    }


def build():
    raw_rows = read_ventas()
    stock, stock_by_loc, inv_rows = read_inventario()
    meses_order = sorted({r['mes'] for r in raw_rows}, key=mes_sort_key)
    es_parcial = bool(meses_order and meses_order[-1].startswith('julio-'))
    prod_curve, _ = compute_prod_curve(raw_rows, stock, stock_by_loc, meses_order, es_parcial)
    summary_prod = compute_summary_prod(prod_curve)

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
            'modelos': [MODEL_CORTA, MODEL_LARGA],
        },
        'es_parcial': es_parcial,
        'stock_total': sum(stock.values()),
        'stock_pt_total': stock_pt_total,
        'total': sum(r['v'] for r in raw_rows),
        'all_stores': all_stores,
        'inv_locations': sorted(stock_by_loc.keys()),
        'prod_curve': prod_curve,
        'summary_prod': summary_prod,
        'margarita': empty_margarita(),
        'tolon': {'v_base': 0, 'v_mes': 0},
        'date_range': (
            f"{meses_order[0].split('-')[0].capitalize()} {meses_order[0].split('-')[1]} — "
            f"{meses_order[-1].split('-')[0].capitalize()} {meses_order[-1].split('-')[1]}"
        ),
    }


if __name__ == '__main__':
    data = build()
    import sys
    print(f'Sales: {len(data["raw_rows"])} rows, {data["total"]} units', file=sys.stderr)
    print(f'Stock: {data["stock_total"]}, models: {data["filtros"]["modelos"]}', file=sys.stderr)
    print(f'Range: {data["date_range"]}, es_parcial: {data["es_parcial"]}', file=sys.stderr)
