#!/usr/bin/env python3
"""Regenera análisis y solicitud con data completa de taller (movimientos inventario)."""
import re
import numpy as np
import pandas as pd
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, Reference, PieChart

# --- Rutas ---
TIENDAS_FILE = '/home/ubuntu/.cursor/projects/workspace/uploads/_Solicitudes__TIENDAS__consumibles_2meses_99a4.xlsx'
TALLER_MOV_FILE = '/home/ubuntu/.cursor/projects/workspace/uploads/movimientos_taller_actualizado_0a2c.xlsx'
TALLER_SOL_FILE = '/home/ubuntu/.cursor/projects/workspace/uploads/solicitudes_taller_2_meses_830d.xlsx'
TEMPLATE = '/home/ubuntu/.cursor/projects/workspace/uploads/SOLICITUD_DE_CONSUMIBLES___SUM_AGOSTO_1_2561.xlsx'
ANALISIS_OUT = '/workspace/analisis_pedidos_consumibles_2meses.xlsx'
SOLICITUD_OUT = '/workspace/SOLICITUD_DE_CONSUMIBLES_AGOSTO_2026.xlsx'

MESES = 2.0
SEMANAS_MES = 4.33
BUFFER = 1.10

ALIASES = {
    'BOLSAS BLANCAS PAPELERA': 'BOLSA DE PAPELERA',
    'CAFE': 'CAFÉ',
    'LAPICES': 'LAPIZ',
    'PILAS AA': 'BATERIAS AA',
    'PILAS AAA': 'BATERIAS AAA',
    'PINZA DEVASTADO': 'PINZA DE DEVASTADO',
    'PAÑOS AMARILLOS': 'PAÑO AMARILLO',
    'PAÑO AMARILLO': 'PAÑO AMARILLO',
    'CELOVEN TRANSPARENTE CINTA ADHESIVA': 'CINTA ADHESIVA TRANSPARENTE',
    'CARTUCHO DE TONER 05A/80A': 'TONER 05A/80A',
    'POST IT': 'POST ITS',
    'CUTTERS EXACTOS': 'CUTTERS (EXACTO)',
    'MARCADOR ROJO PUNTA GRUESA': 'MARCADOR PERMANENTE PUNTA GRUESA',
}


def clean_art(x):
    if pd.isna(x):
        return ''
    s = re.sub(r'\s+', ' ', str(x).strip().upper())
    return ALIASES.get(s, s)


def parse_num(val):
    if pd.isna(val) or val in ['-', '—', '']:
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).strip().replace(',', ''))
    except ValueError:
        return 0


def load_tiendas(path):
    xl = pd.ExcelFile(path)
    frames = []
    for sheet in xl.sheet_names:
        if sheet == 'INVENTARIO DE CONSUMIBLES':
            continue
        df = pd.read_excel(path, sheet_name=sheet, header=1)
        df.columns = ['FECHA', 'NOMBRE', 'ARTICULO', 'CARACTER_ADICIONAL', 'CANTIDAD', 'ESTADO', 'SUCURSAL', 'NOTAS']
        df = df[df['FECHA'].notna() & (df['FECHA'].astype(str) != 'FECHA')]
        df['ORIGEN'] = 'TIENDAS'
        df['TIENDA_SHEET'] = sheet
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_taller_movimientos(path):
    df = pd.read_excel(path, sheet_name='Hoja 1')
    df.columns = ['FECHA', 'CODIGO', 'MOVIMIENTO', 'ARTICULO', 'CATEGORIA', 'UND_MED', 'SUCURSAL']
    df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
    df['CANTIDAD'] = df['MOVIMIENTO'].abs()
    df['ORIGEN'] = 'TALLER'
    df['ESTADO'] = 'CONSUMIDO'
    df['SUCURSAL'] = 'TALLER'
    df['NOMBRE'] = 'MOVIMIENTO INVENTARIO'
    df['NOTAS'] = df['CODIGO']
    df['CARACTER_ADICIONAL'] = df['UND_MED']
    return df


def load_taller_solicitudes_old(path):
    df = pd.read_excel(path, sheet_name='CRECO SOLICITUDES', header=1)
    df.columns = ['FECHA', 'NOMBRE', 'ARTICULO', 'CARACTER_ADICIONAL', 'CANTIDAD', 'ESTADO', 'SUCURSAL', 'NOTAS']
    df = df[df['FECHA'].notna() & (df['FECHA'].astype(str) != 'FECHA')]
    df['ORIGEN'] = 'TALLER_SOL_ANTERIOR'
    return df


def prepare_solicitudes(df):
    out = df.copy()
    out['FECHA'] = pd.to_datetime(out['FECHA'], errors='coerce')
    out['CANTIDAD'] = pd.to_numeric(out['CANTIDAD'], errors='coerce').fillna(0)
    out['ESTADO_NORM'] = out['ESTADO'].astype(str).str.strip().str.upper()
    out['ARTICULO_NORM'] = out['ARTICULO'].apply(clean_art)
    out['PRODUCTO_KEY'] = out['ARTICULO_NORM']
    out['MES'] = out['FECHA'].dt.to_period('M').astype(str)

    def clasificar(estado):
        if estado == 'NO DISPONIBLE':
            return 'NO ATENDIDA'
        if estado in {'RECIBIDO', 'ENTRGADO', 'ENTREGADO', 'ENVIADO', 'CONSUMIDO'}:
            return 'ATENDIDA - Entregada/Consumida'
        if estado == 'SOLICITADO':
            return 'ATENDIDA - Solicitada/Pendiente'
        return 'OTRO'

    out['CLASIFICACION'] = out['ESTADO_NORM'].apply(clasificar)
    out['ES_ATENDIDA'] = out['CLASIFICACION'].str.startswith('ATENDIDA')
    out['ES_NO_DISPONIBLE'] = out['ESTADO_NORM'] == 'NO DISPONIBLE'
    return out


def agg_producto(df, origen_label=None):
    rows = []
    for key, sub in df.groupby('ARTICULO_NORM'):
        total_sol = len(sub)
        und_total = sub['CANTIDAD'].sum()
        und_atend = sub.loc[sub['ES_ATENDIDA'], 'CANTIDAD'].sum()
        und_no = sub.loc[sub['ES_NO_DISPONIBLE'], 'CANTIDAD'].sum()
        und_entreg = sub.loc[sub['CLASIFICACION'] == 'ATENDIDA - Entregada/Consumida', 'CANTIDAD'].sum()
        und_pend = sub.loc[sub['CLASIFICACION'] == 'ATENDIDA - Solicitada/Pendiente', 'CANTIDAD'].sum()
        sol_atend = sub['ES_ATENDIDA'].sum()
        sol_no = sub['ES_NO_DISPONIBLE'].sum()
        und_med = sub['CARACTER_ADICIONAL'].mode().iloc[0] if 'CARACTER_ADICIONAL' in sub.columns and len(sub['CARACTER_ADICIONAL'].mode()) else 'UND'
        if pd.isna(und_med):
            und_med = 'UND'

        pct_sol_atend = round(100 * sol_atend / total_sol, 1) if total_sol else 0
        pct_sol_no = round(100 * sol_no / total_sol, 1) if total_sol else 0
        pct_und_atend = round(100 * und_atend / und_total, 1) if und_total else 0
        pct_und_no = round(100 * und_no / und_total, 1) if und_total else 0
        dem_mensual = und_total / MESES
        dem_semanal = dem_mensual / SEMANAS_MES
        dem_quincenal = dem_mensual / 2
        ped_mensual = int(np.ceil(dem_mensual * BUFFER))
        min_sug = max(1, int(np.ceil(dem_semanal * 1.5))) if und_total > 0 else 0
        max_sug = max(min_sug, int(np.ceil(min_sug + dem_mensual)))

        rows.append({
            'Producto': key,
            'Und medida': und_med,
            'Movimientos/Solicitudes': total_sol,
            'Und total (2 meses)': int(und_total),
            'Und atendidas/consumidas': int(und_atend),
            'Und entregadas/consumidas': int(und_entreg),
            'Und pendientes': int(und_pend),
            'Und NO DISPONIBLE': int(und_no),
            '% Sol. atendidas': pct_sol_atend,
            '% Sol. NO DISPONIBLE': pct_sol_no,
            '% Und atendidas': pct_und_atend,
            '% Und NO DISPONIBLE': pct_und_no,
            'Prom mensual (und)': round(dem_mensual, 2),
            'Pedido SEMANAL (+buffer)': int(np.ceil(dem_semanal * BUFFER)),
            'Pedido QUINCENAL (+buffer)': int(np.ceil(dem_quincenal * BUFFER)),
            'Pedido MENSUAL (+buffer)': ped_mensual,
            'MIN sugerido': min_sug,
            'MAX sugerido': max_sug,
        })
    res = pd.DataFrame(rows)
    if origen_label:
        res.insert(0, 'Origen', origen_label)
    return res.sort_values('Und total (2 meses)', ascending=False)


def resumen_general(df, nombre, nota=''):
    total_sol = len(df)
    und_total = df['CANTIDAD'].sum()
    sol_atend = df['ES_ATENDIDA'].sum()
    sol_no = df['ES_NO_DISPONIBLE'].sum()
    und_atend = df.loc[df['ES_ATENDIDA'], 'CANTIDAD'].sum()
    und_no = df.loc[df['ES_NO_DISPONIBLE'], 'CANTIDAD'].sum()
    und_entreg = df.loc[df['CLASIFICACION'] == 'ATENDIDA - Entregada/Consumida', 'CANTIDAD'].sum()
    und_pend = df.loc[df['CLASIFICACION'] == 'ATENDIDA - Solicitada/Pendiente', 'CANTIDAD'].sum()
    return pd.DataFrame([
        {'Indicador': 'Área', 'Valor': nombre},
        {'Indicador': 'Fuente de datos', 'Valor': nota},
        {'Indicador': 'Período desde', 'Valor': df['FECHA'].min().strftime('%Y-%m-%d')},
        {'Indicador': 'Período hasta', 'Valor': df['FECHA'].max().strftime('%Y-%m-%d')},
        {'Indicador': 'Meses analizados', 'Valor': MESES},
        {'Indicador': 'Productos distintos', 'Valor': df['ARTICULO_NORM'].nunique()},
        {'Indicador': 'Registros (líneas)', 'Valor': total_sol},
        {'Indicador': 'Und totales', 'Valor': int(und_total)},
        {'Indicador': 'Líneas atendidas/consumidas', 'Valor': int(sol_atend)},
        {'Indicador': 'Líneas NO DISPONIBLE', 'Valor': int(sol_no)},
        {'Indicador': '% Líneas atendidas', 'Valor': f"{round(100 * sol_atend / total_sol, 1)}%"},
        {'Indicador': '% Líneas NO DISPONIBLE', 'Valor': f"{round(100 * sol_no / total_sol, 1)}%"},
        {'Indicador': 'Und atendidas/consumidas', 'Valor': int(und_atend)},
        {'Indicador': 'Und NO DISPONIBLE', 'Valor': int(und_no)},
        {'Indicador': '% Und atendidas', 'Valor': f"{round(100 * und_atend / und_total, 1)}%"},
        {'Indicador': '% Und NO DISPONIBLE', 'Valor': f"{round(100 * und_no / und_total, 1)}%"},
        {'Indicador': 'Pedido mensual sugerido (sum)', 'Valor': int(agg_producto(df)['Pedido MENSUAL (+buffer)'].sum())},
    ])


def build_unified_pedido(prod_tiendas, prod_taller):
    t = prod_tiendas.set_index('Producto')
    m = prod_taller.set_index('Producto')
    all_prods = sorted(set(t.index) | set(m.index))
    rows = []
    for p in all_prods:
        pt = t.loc[p] if p in t.index else None
        pm = m.loc[p] if p in m.index else None
        und_t = pt['Und total (2 meses)'] if pt is not None else 0
        und_m = pm['Und total (2 meses)'] if pm is not None else 0
        ped_t = pt['Pedido MENSUAL (+buffer)'] if pt is not None else 0
        ped_m = pm['Pedido MENSUAL (+buffer)'] if pm is not None else 0
        rows.append({
            'Producto': p,
            'Und Tiendas (2m)': int(und_t),
            'Und Taller (2m)': int(und_m),
            'Und Total (2m)': int(und_t + und_m),
            'Pedido Mensual Tiendas': int(ped_t),
            'Pedido Mensual Taller': int(ped_m),
            'Pedido Mensual UNIFICADO': int(ped_t + ped_m),
            'Pedido Semanal UNIFICADO': int(np.ceil((ped_t + ped_m) / SEMANAS_MES)),
            'Pedido Quincenal UNIFICADO': int(np.ceil((ped_t + ped_m) / 2)),
            'MIN unificado': int(max(1, np.ceil((ped_t + ped_m) / SEMANAS_MES * 1.5))) if (ped_t + ped_m) > 0 else 0,
            'MAX unificado': int(max(1, np.ceil((ped_t + ped_m) / SEMANAS_MES * 1.5) + (ped_t + ped_m))) if (ped_t + ped_m) > 0 else 0,
        })
    return pd.DataFrame(rows).sort_values('Pedido Mensual UNIFICADO', ascending=False)


def compare_taller_old_new(taller_old, taller_new):
    old = taller_old.groupby('ARTICULO_NORM')['CANTIDAD'].sum().reset_index().rename(columns={'CANTIDAD': 'Und solicitudes (ant)'})
    new = taller_new.groupby('ARTICULO_NORM')['CANTIDAD'].sum().reset_index().rename(columns={'CANTIDAD': 'Und movimientos (act)'})
    cmp = pd.merge(old, new, on='ARTICULO_NORM', how='outer').fillna(0)
    cmp['Diferencia'] = cmp['Und movimientos (act)'] - cmp['Und solicitudes (ant)']
    cmp['% Cambio'] = np.where(cmp['Und solicitudes (ant)'] > 0,
                               round(100 * cmp['Diferencia'] / cmp['Und solicitudes (ant)'], 1), np.nan)
    cmp = cmp.sort_values('Und movimientos (act)', ascending=False)
    cmp.rename(columns={'ARTICULO_NORM': 'Producto'}, inplace=True)
    return cmp


# --- Excel styling helpers ---
def get_workbook_styles(wb):
    return {
        'title': wb.add_format({'bold': True, 'font_size': 14, 'bg_color': '#1F4E79', 'font_color': 'white'}),
        'header': wb.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1, 'text_wrap': True}),
        'note': wb.add_format({'italic': True, 'text_wrap': True, 'font_color': '#444444'}),
        'warn': wb.add_format({'bg_color': '#FCE4D6', 'text_wrap': True}),
    }


def write_sheet(writer, name, df, intro=None, startrow=0):
    df.to_excel(writer, sheet_name=name, index=False, startrow=3 if intro else startrow)
    ws = writer.sheets[name]
    fmt = get_workbook_styles(writer.book)
    ws.write(0, 0, name, fmt['title'])
    row = 1
    if intro:
        for line in intro:
            ws.write(row, 0, line, fmt['note'])
            row += 1
    sr = 3 if intro else startrow
    for col_num, col in enumerate(df.columns):
        ws.write(sr, col_num, col, fmt['header'])
        w = 40 if col in ('Producto', 'Observación', 'OBSERVACION') else 16
        ws.set_column(col_num, col_num, w)
    ws.freeze_panes(sr + 1, 0)


def format_qty_solicitud(qty, articulo, template_ref):
    art = clean_art(articulo)
    qty = float(qty)
    if qty <= 0:
        return None
    for t_art, t_data in template_ref.items():
        mapped = ALIASES.get(t_art, t_art)
        if mapped == art or art in mapped or mapped in art:
            unit = t_data['unit']
            if unit in ('BULTOS', 'BULTO'):
                return f'{max(1, int(np.ceil(qty / 7)))} BULTOS'
            if unit == 'GAL':
                return f'{max(1, int(np.ceil(qty)))} GAL'
            if unit in ('CAJAS', 'CAJA'):
                n = max(1, int(np.ceil(qty / 6)))
                return f'{n} {"CAJAS" if n > 1 else "CAJA"}'
            if unit == 'PAQ':
                return f'{max(1, int(np.ceil(qty / 10)))} PAQ'
            return f'{max(1, int(np.ceil(qty)))} UND'
    rules = [
        (lambda a: 'CAFÉ' in a, lambda q: (max(1, int(np.ceil(q / 7))), 'BULTOS')),
        (lambda a: a in {'DESINFECTANTE', 'CLORO', 'ALCOHOL', 'GEL DE BAÑO', 'LAVATODO', 'VENSOL'}, lambda q: (max(1, int(np.ceil(q))), 'GAL')),
        (lambda a: 'SERVILLETAS' in a, lambda q: (max(1, int(np.ceil(q / 10))), 'PAQ')),
        (lambda a: 'RESMA' in a, lambda q: (max(1, int(np.ceil(q / 5))), 'PAQ')),
        (lambda a: a in {'BOLIGRAFOS', 'LAPIZ', 'GRAPAS', 'CINTA DE EMBALAJE', 'CINTA TERMICA'}, lambda q: (max(1, int(np.ceil(q / 6))), 'CAJAS')),
        (lambda a: 'BATERIAS' in a, lambda q: (max(1, int(np.ceil(q / 4))), 'CAJA')),
    ]
    for pred, conv in rules:
        if pred(art):
            n, unit = conv(qty)
            return f'{n} {unit}' if unit != 'CAJAS' or n > 1 else '1 CAJA'
    return f'{max(1, int(np.ceil(qty)))} UND'


def build_obs_solicitud(row):
    parts = []
    if row['Und Taller (2m)'] > 0 and row['Und Tiendas (2m)'] > 0:
        parts.append(f"DEMANDA TIENDAS {int(row['Und Tiendas (2m)'])} + TALLER {int(row['Und Taller (2m)'])} UND (2 MESES)")
    elif row['Und Tiendas (2m)'] > 0:
        parts.append(f"DEMANDA TIENDAS {int(row['Und Tiendas (2m)'])} UND (2 MESES)")
    elif row['Und Taller (2m)'] > 0:
        parts.append(f"CONSUMO TALLER {int(row['Und Taller (2m)'])} UND (MOVIMIENTOS INVENTARIO)")
    parts.append(f"PEDIDO MENSUAL JUSTIFICADO: {int(row['Pedido Mensual UNIFICADO'])} UND (+10% BUFFER)")
    if row.get('_cambio_taller', 0) > 50:
        parts.append(f"⚠ AJUSTADO: taller subió {row['_cambio_taller']:.0f}% vs solicitudes incompletas")
    return '. '.join(parts)


def generate_solicitud(unified, cmp_taller, template_ref):
    wb = Workbook()
    header_font = Font(bold=True)
    header_fill = PatternFill('solid', fgColor='D9E1F2')
    title_fill = PatternFill('solid', fgColor='1F4E79')
    title_font = Font(bold=True, size=14, color='FFFFFF')
    thin = Side(style='thin', color='CCCCCC')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    wrap = Alignment(wrap_text=True, vertical='top')

    cambio_map = cmp_taller.set_index('Producto')['% Cambio'].to_dict()

    records = []
    for _, r in unified.iterrows():
        if r['Pedido Mensual UNIFICADO'] <= 0:
            continue
        cambio = cambio_map.get(r['Producto'], 0)
        if pd.isna(cambio):
            cambio = 0
        row = r.to_dict()
        row['_cambio_taller'] = cambio
        cant = format_qty_solicitud(r['Pedido Mensual UNIFICADO'], r['Producto'], template_ref)
        records.append({
            'CANTIDAD': cant,
            'ARTICULO': r['Producto'],
            'OBSERVACION': build_obs_solicitud(row),
            '_PED': r['Pedido Mensual UNIFICADO'],
        })

    records.sort(key=lambda x: -x['_PED'])

    ws = wb.active
    ws.title = '05082026'
    for rn, val in [
        (2, 'DPTO: CADENA DE SUMINISTROS-LOGISTICA'),
        (3, 'SOLICITANTE:  SAMUEL GRISANTI / SUPERVISOR LOGÍSTICA & INVENTARIOS'),
        (4, 'FECHA PEDIDO: 06/08/2026'),
        (5, ' FECHA ENTREGA:  (según lead time proveedor)'),
        (6, 'NOTA: Taller recalculado con movimientos inventario completos (Jun–Ago 2026)'),
    ]:
        ws.merge_cells(f'A{rn}:F{rn}')
        c = ws.cell(row=rn, column=1, value=val)
        c.font = Font(bold=True, italic=(rn == 6))

    headers = ['CANTIDAD', 'ARTICULO', 'CODIGO (OPCIONAL)', 'IMAGEN MUESTRA/LINK', 'OBSERVACION', 'ENTREGADO']
    hr = 8
    for i, h in enumerate(headers, 1):
        ws.cell(row=hr, column=i, value=h).font = header_font
    row = hr + 1
    for rec in records:
        ws.cell(row=row, column=1, value=rec['CANTIDAD'])
        ws.cell(row=row, column=2, value=rec['ARTICULO'])
        ws.cell(row=row, column=5, value=rec['OBSERVACION'])
        for c in range(1, 7):
            ws.cell(row=row, column=c).alignment = wrap
            ws.cell(row=row, column=c).border = border
        row += 1
    ws.column_dimensions['A'].width = 14
    ws.column_dimensions['B'].width = 42
    ws.column_dimensions['E'].width = 75
    ws.freeze_panes = f'A{hr + 1}'

    # Ajuste taller
    ws2 = wb.create_sheet('AJUSTE TALLER')
    ws2['A1'] = 'COMPARATIVO TALLER: SOLICITUDES INCOMPLETAS vs MOVIMIENTOS ACTUALIZADOS'
    ws2['A1'].font = title_font
    ws2['A1'].fill = title_fill
    ws2.merge_cells('A1:F1')
    for c, h in enumerate(cmp_taller.columns, 1):
        ws2.cell(row=3, column=c, value=h).font = header_font
    for ri, rd in enumerate(cmp_taller.itertuples(index=False), 4):
        for ci, v in enumerate(rd, 1):
            cell = ws2.cell(row=ri, column=ci, value=v)
            if ci == 5 and isinstance(v, (int, float)) and v > 50:
                cell.fill = PatternFill('solid', fgColor='FCE4D6')

    # Unified reference
    ws3 = wb.create_sheet('PEDIDO UNIFICADO')
    ws3['A1'] = 'DETALLE PEDIDO UNIFICADO (TIENDAS + TALLER CORREGIDO)'
    ws3['A1'].font = title_font
    ws3['A1'].fill = title_fill
    ws3.merge_cells('A1:K1')
    for c, h in enumerate(unified.columns, 1):
        ws3.cell(row=3, column=c, value=h).font = header_font
    for ri, rd in enumerate(unified.itertuples(index=False), 4):
        for ci, v in enumerate(rd, 1):
            ws3.cell(row=ri, column=ci, value=v)

    ws4 = wb.create_sheet('METODOLOGIA')
    ws4['A1'] = 'METODOLOGÍA ACTUALIZADA'
    ws4['A1'].font = title_font
    notes = [
        ('Cambio principal', 'Taller ahora usa movimientos_taller_actualizado.xlsx (370 movimientos, consumo real)'),
        ('Tiendas', 'Sin cambio — solicitudes 2 meses por sucursal'),
        ('Taller anterior', 'solicitudes_taller_2_meses.xlsx tenía solo 157 líneas / 461 und (INCOMPLETA)'),
        ('Taller actual', f'{int(cmp_taller["Und movimientos (act)"].sum())} und consumidas en 2 meses'),
        ('Fórmula pedido', 'Promedio mensual × 1.10 buffer, redondeado al entero superior'),
        ('Items solicitud', f'{len(records)} artículos'),
        ('Total und/mes', f'{sum(r["_PED"] for r in records):,.0f}'),
    ]
    for i, (k, v) in enumerate(notes, 3):
        ws4.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws4.cell(row=i, column=2, value=v)

    wb.save(SOLICITUD_OUT)
    return records


def main():
    # Cargar datos
    tiendas_raw = load_tiendas(TIENDAS_FILE)
    taller_mov_raw = load_taller_movimientos(TALLER_MOV_FILE)
    taller_sol_old = prepare_solicitudes(load_taller_solicitudes_old(TALLER_SOL_FILE))

    tiendas = prepare_solicitudes(tiendas_raw)
    taller = prepare_solicitudes(taller_mov_raw)
    total = pd.concat([tiendas, taller], ignore_index=True)

    prod_tiendas = agg_producto(tiendas, 'TIENDAS')
    prod_taller = agg_producto(taller, 'TALLER')
    unified = build_unified_pedido(prod_tiendas, prod_taller)
    cmp_taller = compare_taller_old_new(taller_sol_old, taller)

    # --- Generar análisis Excel ---
    writer = pd.ExcelWriter(ANALISIS_OUT, engine='xlsxwriter')

    metodologia = pd.DataFrame({
        'Sección': [
            'ACTUALIZACIÓN TALLER', 'Fuente tiendas', 'Fuente taller (NUEVA)', 'Fuente taller (ANTERIOR)',
            'Período', 'Fórmula pedido', 'Nota',
        ],
        'Descripción': [
            'Data de taller reemplazada por movimientos de inventario completos.',
            'Solicitudes tiendas 2 meses (7 sucursales) — sin cambios.',
            'movimientos_taller_actualizado.xlsx — 370 movimientos, consumo real de almacén.',
            'solicitudes_taller_2_meses.xlsx — 157 líneas INCOMPLETAS (solo referencia).',
            f"{total['FECHA'].min().date()} a {total['FECHA'].max().date()}",
            'Prom mensual = und/2 meses; pedido = prom × 1.10 buffer',
            'Taller: % atendidas = 100% (movimientos = consumo efectivo). Tiendas: estados RECIBIDO/NO DISP.',
        ],
    })
    write_sheet(writer, '0-METODOLOGIA', metodologia)

    exec_rows = []
    for name, df, nota in [
        ('TIENDAS', tiendas, 'Solicitudes por sucursal'),
        ('TALLER (movimientos)', taller, 'Movimientos inventario — consumo real'),
        ('UNIFICADO', total, 'Tiendas + Taller corregido'),
    ]:
        r = resumen_general(df, name, nota)
        r.insert(0, 'Segmento', name)
        exec_rows.append(r)
    write_sheet(writer, '1-RESUMEN EJECUTIVO', pd.concat(exec_rows, ignore_index=True))

    write_sheet(writer, '2-AJUSTE TALLER', cmp_taller,
                intro=['Comparativo solicitudes incompletas vs movimientos actualizados. Filas en naranja = cambio >50%.'])

    write_sheet(writer, '3-Productos TIENDAS', prod_tiendas.drop(columns=['Origen'], errors='ignore'))
    write_sheet(writer, '4-Productos TALLER', prod_taller.drop(columns=['Origen'], errors='ignore'))
    write_sheet(writer, '5-Productos UNIFICADO', unified,
                intro=['Pedido unificado = mensual tiendas + mensual taller (c/u con +10% buffer).'])

    # Detalle movimientos taller
    det_taller = taller[['FECHA', 'ARTICULO_NORM', 'CANTIDAD', 'CATEGORIA', 'CARACTER_ADICIONAL', 'CODIGO' if 'CODIGO' in taller.columns else 'NOTAS']].copy()
    det_taller.columns = ['FECHA', 'PRODUCTO', 'CANTIDAD', 'CATEGORIA', 'UND_MED', 'CODIGO']
    write_sheet(writer, '6-Detalle MOV TALLER', det_taller.sort_values('FECHA', ascending=False))

    det_tiendas = tiendas[['FECHA', 'ORIGEN', 'SUCURSAL', 'ARTICULO_NORM', 'CANTIDAD', 'ESTADO_NORM', 'CLASIFICACION']].copy()
    det_tiendas.columns = ['FECHA', 'ORIGEN', 'SUCURSAL', 'PRODUCTO', 'CANTIDAD', 'ESTADO', 'CLASIFICACION']
    write_sheet(writer, '7-Detalle TIENDAS', det_tiendas.sort_values('FECHA', ascending=False))

    writer.close()

    # --- Generar solicitud ---
    template_items = pd.read_excel(TEMPLATE, sheet_name='25052026', header=5)
    template_ref = {}
    for _, row in template_items.iterrows():
        if pd.notna(row.get('ARTICULO')) and pd.notna(row.get('CANTIDAD')):
            art = clean_art(row['ARTICULO'])
            cant = str(row['CANTIDAD']).strip()
            m_u = re.match(r'^([\d.,]+)\s*(.+)$', cant, re.I)
            if m_u:
                template_ref[art] = {'qty': float(m_u.group(1)), 'unit': m_u.group(2).strip().upper()}

    records = generate_solicitud(unified, cmp_taller, template_ref)

    # Resumen consola
    print('=' * 60)
    print('ANÁLISIS ACTUALIZADO — TALLER CORREGIDO')
    print('=' * 60)
    print(f"Taller anterior (solicitudes): {int(taller_sol_old['CANTIDAD'].sum())} und / {len(taller_sol_old)} líneas")
    print(f"Taller actual (movimientos):   {int(taller['CANTIDAD'].sum())} und / {len(taller)} movimientos")
    print(f"Tiendas (sin cambio):          {int(tiendas['CANTIDAD'].sum())} und / {len(tiendas)} líneas")
    print(f"Pedido mensual unificado:      {int(unified['Pedido Mensual UNIFICADO'].sum())} und")
    print(f"Items en solicitud:            {len(records)}")
    print(f"\nArchivos generados:")
    print(f"  {ANALISIS_OUT}")
    print(f"  {SOLICITUD_OUT}")
    print('\nTop 5 cambios taller:')
    print(cmp_taller.head(5).to_string(index=False))


if __name__ == '__main__':
    main()
