#!/usr/bin/env python3
"""Generate DATA JSON for Classic Polo dashboard."""
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

VENTAS_XLSX = '/home/ubuntu/.cursor/projects/workspace/uploads/classic_polo_ventas_actualizada_566a.xlsx'
STOCK_SNAPSHOT = Path(__file__).parent / 'classic_polo_stock_snapshot.json'
MESES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]
MODEL = 'CLASSIC POLO'


def mes_sort_key(m):
    p = m.split('-')
    return (int(p[1]), MESES.index(p[0]))


def mes_key_from_str(s):
    mm, yy = str(s).strip().split('/')
    return f'{MESES[int(mm) - 1]}-{yy}'


def norm_color(c):
    c = str(c).strip()
    if ' - ' in c:
        c = c.split(' - ')[0].strip()
    return c


def norm_tienda(t):
    t = ' '.join(str(t).strip().upper().split())
    mapping = {
        'GRIETA': 'GRIETA',
        'GRIE': 'GRIETA',
        'LA GRIETA': 'GRIETA',
        'SAMBIL CHACAO': 'CHACAO',
        'CHACAO': 'CHACAO',
        'SAMBIL VALENCIA': 'SAMBIL',
        'SAMBIL': 'SAMBIL',
        'GRAND PLAZ': 'GRAND PLAZ',
        'GRANDPLAZ': 'GRAND PLAZ',
        'GRAND PLAZA': 'GRAND PLAZ',
        'LA VELA': 'VELA',
        'VELA': 'VELA',
        'CERRO VERDE': 'CERRO VERDE',
        'CERRV': 'CERRO VERDE',
        'TOLON': 'TOLON',
        'WEB': 'WEB',
        'PEDIDOS': 'PEDIDOS',
    }
    return mapping.get(t, t)


def norm_genero(g):
    if pd.isna(g) or str(g).strip() == '':
        return 'CAB'
    g = str(g).strip().upper()
    if g in ('CABALLERO', 'CAB'):
        return 'CAB'
    if g == 'DAMA':
        return 'DAMA'
    if g == 'KIDS':
        return 'KIDS'
    return g


def read_ventas():
    df = pd.read_excel(VENTAS_XLSX, sheet_name=0)
    rows = []
    for _, row in df.iterrows():
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
            'modelo': MODEL,
            'v': int(qty) if qty == int(qty) else qty,
        })
    return rows


def load_stock():
    snap = json.loads(STOCK_SNAPSHOT.read_text(encoding='utf-8'))
    return snap['stock'], snap['stock_by_store'], snap['stock_by_modelo'], snap['stock_total']


def build():
    raw_rows = read_ventas()
    stock, stock_by_store, stock_by_modelo, stock_total = load_stock()

    meses_order = sorted({r['mes'] for r in raw_rows}, key=mes_sort_key)
    meses_und = {m: sum(r['v'] for r in raw_rows if r['mes'] == m) for m in meses_order}

    tiendas = sorted(set({r['tienda'] for r in raw_rows}) | set(stock_by_store.keys()))
    all_stores = sorted(set(tiendas) - {'TALLER', 'WEB', 'PEDIDOS'})

    return {
        'raw_rows': raw_rows,
        'stock': stock,
        'stock_by_store': stock_by_store,
        'stock_by_modelo': stock_by_modelo,
        'meses_order': meses_order,
        'meses_und': meses_und,
        'filtros': {
            'tiendas': tiendas,
            'generos': sorted({r['genero'] for r in raw_rows}),
            'colores': sorted({r['color'] for r in raw_rows}),
            'modelos': [MODEL],
        },
        'es_parcial': True,
        'stock_total': stock_total,
        'total': sum(r['v'] for r in raw_rows),
        'all_stores': all_stores,
        'date_range': (
            f"{meses_order[0].split('-')[0].capitalize()} {meses_order[0].split('-')[1]} — "
            f"{meses_order[-1].split('-')[0].capitalize()} {meses_order[-1].split('-')[1]}"
        ),
    }


if __name__ == '__main__':
    data = build()
    print(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    import sys
    print(f'\nSales: {len(data["raw_rows"])} rows, {data["total"]} units', file=sys.stderr)
    print(f'Range: {data["date_range"]}', file=sys.stderr)
