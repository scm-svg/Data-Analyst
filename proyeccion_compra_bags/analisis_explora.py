import pandas as pd
import numpy as np

UP = "/home/ubuntu/.cursor/projects/workspace/uploads/"

def load_sales(fn):
    df = pd.read_csv(UP+fn, sep=';', encoding='latin-1')
    df.columns = [c.strip() for c in df.columns]
    # rename
    df = df.rename(columns={
        'Fecha de la orden':'fecha_orden',
        'Cant. ordenada':'cant',
        'ubicaci\ufffdn':'ubicacion',
    })
    # find ubicacion col
    for c in df.columns:
        if c.lower().startswith('ubic'):
            df = df.rename(columns={c:'ubicacion'})
    df['cant'] = df['cant'].astype(str).str.replace(',','.').astype(float)
    df['fecha_orden'] = pd.to_datetime(df['fecha_orden'], format='%d/%m/%Y', errors='coerce')
    return df

files = {
    'TRAVEL BAG 40L':'TRAVEL_BAG_40L_VENTAS_ACTUALIZADO_277a.csv',
    'MINI BAG':'MINI_BAG_VENTAS_ACTUALIZADO_eb91.csv',
    'DRY BAG 30L':'DRY_BAG_30_L_VENTAS_ACTUALIZADO_6dc3.csv',
}

for model, fn in files.items():
    df = load_sales(fn)
    print("="*70)
    print("MODELO:", model, "| filas:", len(df))
    print("Rango fechas:", df['fecha_orden'].min().date(), "->", df['fecha_orden'].max().date())
    print("Total unidades netas (suma cant):", df['cant'].sum())
    print("\nVentas por mes (suma cant):")
    m = df.groupby(df['fecha_orden'].dt.to_period('M'))['cant'].sum()
    print(m.to_string())
    print("\nVentas por ubicacion:")
    print(df.groupby('ubicacion')['cant'].sum().sort_values(ascending=False).to_string())
    print("\nVentas por color (sku):")
    print(df.groupby(['sku','color'])['cant'].sum().sort_values(ascending=False).to_string())
