import pandas as pd
import numpy as np

UP = "/home/ubuntu/.cursor/projects/workspace/uploads/"

# ---------- Cargar ventas ----------
def load_sales(fn):
    df = pd.read_csv(UP+fn, sep=';', encoding='latin-1')
    df.columns = [c.strip() for c in df.columns]
    ren = {}
    for c in df.columns:
        cl = c.lower()
        if cl.startswith('fecha de la orden'): ren[c]='fecha_orden'
        elif cl.startswith('cant'): ren[c]='cant'
        elif cl.startswith('ubic'): ren[c]='ubicacion'
    df = df.rename(columns=ren)
    df['cant'] = df['cant'].astype(str).str.replace(',','.').astype(float)
    df['fecha_orden'] = pd.to_datetime(df['fecha_orden'], format='%d/%m/%Y', errors='coerce')
    df['periodo'] = df['fecha_orden'].dt.to_period('M')
    return df

files = {
    'TRAVEL BAG 40L':'TRAVEL_BAG_40L_VENTAS_ACTUALIZADO_277a.csv',
    'MINI BAG':'MINI_BAG_VENTAS_ACTUALIZADO_eb91.csv',
    'DRY BAG 30L':'DRY_BAG_30_L_VENTAS_ACTUALIZADO_6dc3.csv',
}
sales = {m: load_sales(fn) for m,fn in files.items()}

# ---------- Inventario ----------
inv = pd.read_csv(UP+"INVENTARIO_DE_MODELOS_BAGS_ACTUALIZADO_HOY_9182.csv", sep=';', encoding='latin-1')
inv.columns = ['ubicacion','producto','sku','modelo','color','cant']
inv['cant'] = inv['cant'].astype(str).str.replace(',','.').astype(float)

# ---------- Factores ----------
F_RED   = 1.55   # expansion de red (Margarita 1.5x Grieta + tienda nueva 1x Grieta)
F_NOV   = 1.10   # migracion / efecto novedad (rediseno)
F_CORP  = 1.08   # pedidos corporativos / mayoristas
F_TOTAL = F_RED * F_NOV * F_CORP

# Ventana de cobertura: Nov-Abr (1a compra, temporada alta/media)
ventana = [pd.Period('2025-11'), pd.Period('2025-12'), pd.Period('2026-01'),
           pd.Period('2026-02'), pd.Period('2026-03'), pd.Period('2026-04')]

sustituto = {
    'TRAVEL BAG 40L':'Travel Bag 40L (new)  [Azul Petroleo + Negro]',
    'MINI BAG':'Moon Bag (posible sustituto Mini Bag) [tonos tierra/oliva/beige]',
    'DRY BAG 30L':'Dry Bag 30L (new) [colores por definir]',
}

rows = []
for m, df in sales.items():
    # Base 1: ventana Nov-Abr real (mismo periodo ano anterior)
    base_ventana = df[df['periodo'].isin(ventana)]['cant'].sum()
    # Base 2: cross-check run-rate ultimos 12 meses completos (jul25-jun26)
    m12 = [pd.Period(f'2025-{x:02d}') for x in range(7,13)] + [pd.Period(f'2026-{x:02d}') for x in range(1,7)]
    tot12 = df[df['periodo'].isin(m12)]['cant'].sum()
    rr_6m = tot12/2.0  # medio ano a run-rate
    # Inventario
    d = inv[inv['modelo']==m]
    inv_taller = d[d['ubicacion']=='TALLER']['cant'].clip(lower=0).sum()
    inv_tiendas = d[d['ubicacion']!='TALLER']['cant'].clip(lower=0).sum()
    inv_total = inv_taller + inv_tiendas
    # Demanda proyectada con factores
    dem_ventana = base_ventana * F_TOTAL
    dem_rr = rr_6m * F_TOTAL
    rows.append(dict(modelo=m, sustituto=sustituto[m],
        base_ventana=base_ventana, dem_ventana=dem_ventana,
        base_runrate6m=rr_6m, dem_runrate=dem_rr,
        inv_tiendas=inv_tiendas, inv_taller=inv_taller, inv_total=inv_total,
        neto_con_taller=max(dem_ventana-inv_total,0),
        neto_sin_taller=max(dem_ventana-inv_tiendas,0)))

R = pd.DataFrame(rows)
pd.set_option('display.width', 200, 'display.max_columns', 30)

print("FACTORES:  Red x1.55  |  Novedad x1.10  |  Corporativo x1.08  |  COMBINADO x{:.3f}".format(F_TOTAL))
print("Ventana de cobertura: Nov 2025 - Abr 2026 (6 meses, guia = ventas reales mismo periodo)\n")

print(">>> DEMANDA BASE Y PROYECTADA (6 meses Nov-Abr)")
print(R[['modelo','base_ventana','dem_ventana','base_runrate6m','dem_runrate']]
      .round(0).to_string(index=False))
print()
print(">>> INVENTARIO ACTUAL")
print(R[['modelo','inv_tiendas','inv_taller','inv_total']].round(0).to_string(index=False))
print()
print(">>> COMPRA NETA SUGERIDA (demanda proyectada - inventario)")
print(R[['modelo','dem_ventana','neto_con_taller','neto_sin_taller']].round(0).to_string(index=False))
print()
print("neto_con_taller = descuenta TODO el inventario (incl. almacen central TALLER)")
print("neto_sin_taller = descuenta solo inventario en tiendas (TALLER se liquida aparte)")

R.to_csv('/workspace/resultado_proyeccion.csv', index=False)
