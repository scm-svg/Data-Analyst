import pandas as pd
UP="/home/ubuntu/.cursor/projects/workspace/uploads/"

v=pd.read_csv(UP+"VENTAS_completo_MODELOS_POR_ANALIZAR_067e.csv",sep=';',encoding='latin-1')
v.columns=[c.strip() for c in v.columns]
ren={}
for c in v.columns:
    cl=c.lower()
    if cl.startswith('fecha de la orden'): ren[c]='fecha_orden'
    elif cl.startswith('cant'): ren[c]='cant'
    elif cl=='vendedor': ren[c]='ubicacion'
    elif cl=='modelo': ren[c]='modelo'
    elif cl=='color': ren[c]='color'
    elif cl=='sku': ren[c]='sku'
v=v.rename(columns=ren)
v['cant']=v['cant'].astype(str).str.replace(',','.').astype(float)
v['fecha_orden']=pd.to_datetime(v['fecha_orden'],format='%d/%m/%Y',errors='coerce')
v['periodo']=v['fecha_orden'].dt.to_period('M')
print("=== VENTAS ===  columnas:",list(v.columns))
print("Rango:",v['fecha_orden'].min().date(),"->",v['fecha_orden'].max().date())
print("\nUnidades netas por MODELO:")
print(v.groupby('modelo')['cant'].sum().sort_values(ascending=False).to_string())
print("\nUbicaciones:",sorted(v['ubicacion'].dropna().unique()))

i=pd.read_csv(UP+"INVENTARIOS_completo_DE_LOS_SIGUIENTS_MODELOS_A_EVALUAR_58de.csv",sep=';',encoding='latin-1')
i.columns=[c.strip() for c in i.columns]
ren2={}
for c in i.columns:
    cl=c.lower()
    if cl.startswith('ubic'): ren2[c]='ubicacion'
    elif cl=='modelo': ren2[c]='modelo'
    elif cl.startswith('color'): ren2[c]='color'
    elif cl=='sku': ren2[c]='sku'
    elif cl.startswith('cantidad'): ren2[c]='cant'
i=i.rename(columns=ren2)
i['cant']=i['cant'].astype(str).str.replace(',','.').astype(float)
print("\n\n=== INVENTARIO ===  columnas:",list(i.columns))
print("Ubicaciones:",sorted(i['ubicacion'].dropna().unique()))
print("\nInventario por MODELO (total y TALLER):")
g=i.groupby('modelo')['cant'].sum()
tal=i[i['ubicacion']=='TALLER'].groupby('modelo')['cant'].sum()
for m in g.index:
    print(f"  {m:20s} total={g[m]:8.0f}   TALLER={tal.get(m,0):8.0f}")
