#!/usr/bin/env python3
"""Generate DATA JSON for Advance Geo dashboard (manufactura)."""
import json
from collections import defaultdict

import pandas as pd

VENTAS_XLSX = '/home/ubuntu/.cursor/projects/workspace/uploads/VENTA_ADVANCE_GEO_1f53.xlsx'
INVENTARIO_XLSX = '/home/ubuntu/.cursor/projects/workspace/uploads/DATA_INVENTARIO_ADVANCE_GEO_48a5.xlsx'
MESES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]
MES_UPPER = {m.upper(): m for m in MESES}
MODELS = ['ADVANCE GEO DOMINIC CAB', 'ADVANCE GEO MAYA DAMA']


def mes_sort_key(m):
    p = m.split('-')
    return (int(p[1]), MESES.index(p[0]))


def norm_tienda(t):
    t = ' '.join(str(t).strip().upper().split())
    mapping = {
        'SAMBIL CHACAO': 'CHACAO',
        'CHACAO': 'CHACAO',
        'SAMBIL VALENCIA': 'SAMBIL',
        'SAMBIL': 'SAMBIL',
        'LA VELA': 'VELA',
        'VELA': 'VELA',
        'GRAND PLAZ': 'GRANDPLAZ',
        'GRAND PLAZA': 'GRANDPLAZ',
        'GRANDPLAZ': 'GRANDPLAZ',
        'GRIETA': 'GRIETA',
        'GRIE': 'GRIETA',
        'CERRO VERDE': 'CERRO VERDE',
        'TOLON': 'TOLON',
        'WEB': 'WEB',
        'CORPORATIVO': 'CORPORATIVO',
        'PEDIDOS': 'PEDIDOS',
        'TALLER PT': 'TALLER',
        'TALLER': 'TALLER',
    }
    return mapping.get(t, t)


def norm_modelo(name, genero=None):
    n = ' '.join(str(name).strip().upper().split())
    g = str(genero).strip().upper() if genero is not None and pd.notna(genero) else ''
    if n in MODELS:
        return n
    if n == 'ADVANCE GEO DOMINIC' or (n.endswith('DOMINIC') and g == 'CAB'):
        return 'ADVANCE GEO DOMINIC CAB'
    if n == 'ADVANCE GEO MAYA' or (n.endswith('MAYA') and g == 'DAMA'):
        return 'ADVANCE GEO MAYA DAMA'
    if 'DOMINIC' in n:
        return 'ADVANCE GEO DOMINIC CAB'
    if 'MAYA' in n:
        return 'ADVANCE GEO MAYA DAMA'
    return n


def norm_genero(g):
    g = str(g).strip().upper()
    return g if g in ('CAB', 'DAMA', 'KIDS') else g


def norm_color(c):
    return str(c).strip()


def norm_talla(t):
    return str(t).strip().upper()


def mes_key_from_row(row):
    mes_raw = str(row.get('Mes', '')).strip().upper()
    año = row.get('Año')
    if mes_raw in MES_UPPER and pd.notna(año):
        return f'{MES_UPPER[mes_raw]}-{int(año)}'
    fecha = row.get('Fecha de la orden')
    if pd.notna(fecha):
        dt = pd.to_datetime(fecha)
        return f'{MESES[dt.month - 1]}-{dt.year}'
    return None


def variant_key(modelo, genero, color, talla):
    return f'{modelo}/{genero}/{color}/{talla}'


def parse_variant_key(k):
    parts = k.split('/')
    if len(parts) < 4:
        return None
    return parts[0], parts[1], '/'.join(parts[2:-1]), parts[-1]


def read_ventas():
    df = pd.read_excel(VENTAS_XLSX, sheet_name=0)
    rows = []
    for _, row in df.iterrows():
        qty = float(row['Cant. ordenada'])
        if qty == 0:
            continue
        mes = mes_key_from_row(row)
        if not mes:
            continue
        genero = norm_genero(row['GENERO'])
        modelo = norm_modelo(row.get('Producto', ''), genero)
        if modelo not in MODELS:
            continue
        rows.append({
            'tienda': norm_tienda(row['tienda / ubicación']),
            'genero': genero,
            'color': norm_color(row['COLOR']),
            'talla': norm_talla(row['TALLA']),
            'mes': mes,
            'modelo': modelo,
            'v': int(qty) if qty == int(qty) else qty,
            'sku': str(row.get('SKU', '')).strip(),
        })
    return rows


def read_inventario():
    df = pd.read_excel(INVENTARIO_XLSX, sheet_name=0)
    stock = defaultdict(int)
    stock_by_loc = defaultdict(lambda: defaultdict(int))
    inv_rows = []
    for _, row in df.iterrows():
        genero = norm_genero(row['GENERO'])
        modelo = norm_modelo(row['MODELO'], genero)
        if modelo not in MODELS:
            continue
        loc = norm_tienda(row['Ubicación'])
        color = norm_color(row['COLOR'])
        talla = norm_talla(row['TALLA'])
        qty = int(float(row['Cantidad en inventario']))
        key = variant_key(modelo, genero, color, talla)
        stock[key] += qty
        stock_by_loc[loc][key] += qty
        inv_rows.append({
            'ubicacion': loc,
            'modelo': modelo,
            'genero': genero,
            'color': color,
            'talla': talla,
            'qty': qty,
            'sku': str(row.get('SKU', '')).strip(),
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
    keys = set(sales.keys())
    for k in stock:
        parsed = parse_variant_key(k)
        if parsed:
            keys.add(parsed)

    n_base = max(len(base), 1)
    curve = []
    for modelo, genero, color, talla in sorted(keys):
        v_base = sales.get((modelo, genero, color, talla), 0)
        v_mes = round(v_base / n_base, 1) if base else 0
        key = variant_key(modelo, genero, color, talla)
        stk_total = stock.get(key, 0)
        stk_pt = stk_taller.get(key, 0)
        cobertura = round(stk_total / v_mes, 1) if v_mes > 0 else 0
        need = lambda n, vm=v_mes, st=stk_total: max(0, round(vm * n - st)) if vm > 0 else 0
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
            'tsort': 0,
        })
    curve.sort(key=lambda r: (r['modelo'], r['color'], r['talla']))
    return curve, base


def compute_summary_prod(prod_curve):
    summary = {}
    for modelo in MODELS:
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
    all_stores = sorted(
        set(tiendas) - {'TALLER', 'WEB', 'PEDIDOS', 'CORPORATIVO'}
    )
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
            'modelos': MODELS,
        },
        'es_parcial': es_parcial,
        'stock_total': sum(stock.values()),
        'stock_pt_total': stock_pt_total,
        'total': sum(r['v'] for r in raw_rows),
        'all_stores': all_stores,
        'inv_locations': sorted(stock_by_loc.keys()),
        'prod_curve': prod_curve,
        'summary_prod': summary_prod,
        'margarita': {'v_mes': 0, 'need_1m': 0, 'need_2m': 0, 'need_3m': 0, 'nota': '', 'skus': []},
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
