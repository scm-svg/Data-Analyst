import pandas as pd
import numpy as np

UP = "/home/ubuntu/.cursor/projects/workspace/uploads/"

inv = pd.read_csv(UP+"INVENTARIO_DE_MODELOS_BAGS_ACTUALIZADO_HOY_9182.csv", sep=';', encoding='latin-1')
inv.columns = ['ubicacion','producto','sku','modelo','color','cant']
inv['cant'] = inv['cant'].astype(str).str.replace(',','.').astype(float)

print("Ubicaciones en inventario:", sorted(inv['ubicacion'].unique()))
print()

for model in ['TRAVEL BAG 40L','MINI BAG','DRY BAG 30L']:
    d = inv[inv['modelo']==model]
    taller = d[d['ubicacion']=='TALLER']['cant'].sum()
    tiendas = d[d['ubicacion']!='TALLER']['cant'].sum()
    total = d['cant'].sum()
    print("="*60)
    print(f"MODELO: {model}")
    print(f"  Inventario TIENDAS (excl. TALLER): {tiendas:.0f}")
    print(f"  Inventario TALLER (almacen central): {taller:.0f}")
    print(f"  TOTAL disponible: {total:.0f}")
    print("  Detalle por color (TALLER):")
    t = d[d['ubicacion']=='TALLER'].groupby(['sku','color'])['cant'].sum()
    print(t.to_string())
    print("  Detalle por color (TOTAL red):")
    tot = d.groupby(['sku','color'])['cant'].sum().sort_values(ascending=False)
    print(tot.to_string())
