import pandas as pd
import numpy as np
UP="/home/ubuntu/.cursor/projects/workspace/uploads/"
OUT="/workspace/proyeccion_compra_bags/PROYECCION_COMPRA_MODELOS2.xlsx"

# ---------- Ventas ----------
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
v['modelo']=v['modelo'].str.strip()
v['color']=v['color'].astype(str).str.strip()
v['ubicacion']=v['ubicacion'].astype(str).str.strip()

# ---------- Inventario ----------
i=pd.read_csv(UP+"INVENTARIOS_completo_DE_LOS_SIGUIENTS_MODELOS_A_EVALUAR_58de.csv",sep=';',encoding='latin-1')
i.columns=[c.strip() for c in i.columns]
ren2={}
for c in i.columns:
    cl=c.lower()
    if cl.startswith('ubic'): ren2[c]='ubicacion'
    elif cl.startswith('color'): ren2[c]='color'
    elif cl.startswith('cantidad'): ren2[c]='cant'
    elif cl=='modelo': ren2[c]='modelo'
i=i.rename(columns=ren2)
i['cant']=i['cant'].astype(str).str.replace(',','.').astype(float)
i['modelo']=i['modelo'].str.strip()
i['color']=i['color'].astype(str).str.strip()
# corregir fila mal etiquetada de ECO BAG
i.loc[i['modelo'].str.contains('ECO BAG',case=False),'modelo']='ECO BAG'

# ---------- Factores ----------
F_RED,F_NOV,F_CORP=1.55,1.10,1.08
F=F_RED*F_NOV*F_CORP
F_SIN_NOV=F_RED*F_CORP
ventana=[pd.Period('2025-11'),pd.Period('2025-12'),pd.Period('2026-01'),
         pd.Period('2026-02'),pd.Period('2026-03'),pd.Period('2026-04')]
comp=[pd.Period(f'2025-{x:02d}') for x in range(6,13)]+[pd.Period(f'2026-{x:02d}') for x in range(1,7)]

modelos=['PONCHO KIDS','PONCHO ADULTO','CITYBAG','ECO BAG','BACKPACK FLEX','CAVAPACK 35L']
recientes=[pd.Period('2026-05'),pd.Period('2026-06')]  # meses completos mas recientes
LIMITE_HIST=pd.Period('2025-11')  # si lanzo antes de Nov-2025 => ventana Nov-Abr sirve

res=[]; mensual={}; estac_rows=[]; col_rows=[]
for m in modelos:
    dv=v[v['modelo']==m]
    di=i[i['modelo']==m]
    lanzamiento=dv[dv['cant']>0]['periodo'].min()
    base_win=dv[dv['periodo'].isin(ventana)]['cant'].sum()
    rr_2m=dv[dv['periodo'].isin(recientes)]['cant'].sum()/len(recientes)  # prom May-Jun
    # run-rate robusto: mediana de meses completos post-lanzamiento (excl. Jul-2026 parcial)
    completos=[p for p in dv['periodo'].dropna().unique()
               if p>=lanzamiento and p<=pd.Period('2026-06')]
    serie=dv[dv['periodo'].isin(completos)].groupby('periodo')['cant'].sum()
    med=serie.median() if len(serie) else 0
    # si el prom 2m es mas del doble de la mediana => hay outlier, usar mediana
    rr_mes = med if (med>0 and rr_2m>2*med) else rr_2m
    base_rr=rr_mes*6
    # metodo por modelo
    if lanzamiento <= LIMITE_HIST:
        metodo='Ventana Nov-Abr (historial completo)'; base=base_win
    else:
        metodo=f'Run-rate x6 (lanzo {lanzamiento})'; base=base_rr
    it=di[di['ubicacion']!='TALLER']['cant'].apply(lambda x:max(x,0)).sum()
    ic=di[di['ubicacion']=='TALLER']['cant'].apply(lambda x:max(x,0)).sum()
    dem=base*F; dem_snov=base*F_SIN_NOV
    res.append(dict(Modelo=m, Metodo=metodo, Lanzamiento=str(lanzamiento),
        RunRate_mensual=round(rr_mes), Base_NovAbr_hist=round(base_win),
        Base_usada=round(base),
        Demanda_con_novedad=round(dem), Demanda_sin_novedad=round(dem_snov),
        Inv_tiendas=round(it), Inv_TALLER=round(ic), Inv_TOTAL=round(it+ic),
        Compra_con_TALLER=round(max(dem-(it+ic),0)),
        Compra_solo_tiendas=round(max(dem-it,0))))
    mensual[m]=dv.groupby('periodo')['cant'].sum()
    s=dv[dv['periodo'].isin(comp)].groupby('periodo')['cant'].sum(); prom=s.mean()
    for p,val in s.items():
        estac_rows.append(dict(Modelo=m,Mes=str(p),Ventas=val,Indice=round(val/prom,2) if prom else 0))
    tot=dv['cant'].sum()
    cm=dv.groupby('color')['cant'].sum().sort_values(ascending=False)
    invcol=di.groupby('color')['cant'].apply(lambda s:s.apply(lambda x:max(x,0)).sum())
    for c,val in cm.items():
        col_rows.append(dict(Modelo=m,Color=c,Ventas_hist=round(val),Mix_pct=round(100*val/tot,1),
            Inv_actual=round(invcol.get(c,0))))

R=pd.DataFrame(res)
pd.set_option('display.width',220,'display.max_columns',30)
print("FACTORES: Red x1.55 | Novedad x1.10 | Corp x1.08 | COMBINADO x{:.3f}  (sin novedad x{:.3f})".format(F,F_SIN_NOV))
print("Ventana: Nov-Abr (6 meses)\n")
print(R.to_string(index=False))

# ---------- Excel ----------
men=pd.DataFrame(mensual); men.index=men.index.astype(str); men=men.reset_index().rename(columns={'index':'Mes'})
estac=pd.DataFrame(estac_rows); colores=pd.DataFrame(col_rows)
invdet=i[i['modelo'].isin(modelos)].groupby(['modelo','ubicacion','color'])['cant'].sum().reset_index()

notas=pd.DataFrame({'GUIA':[
 "PROYECCION DE COMPRA - 6 MESES (Nov-Abr) - MODELOS: Poncho Kids, Poncho Adulto, Citybag, Eco Bag, Backpack Flex, Cavapack 35L",
 "",
 "METODOLOGIA (misma que la 1a entrega, con un ajuste por lanzamiento):",
 " - Poncho Kids: historial completo -> base = ventas reales Nov-Abr (captura estacionalidad).",
 " - Citybag, Backpack Flex, Cavapack, Eco Bag, Poncho Adulto: LANZARON en 2026 (no tienen Nov-Abr)",
 "   -> base = run-rate mensual reciente (prom. May-Jun 2026) x 6 meses.",
 " - Factores: Red x1.55 (Margarita+Tienda nueva), Novedad x1.10, Corporativo x1.08 => x1.841 combinado.",
 " - Compra neta = Demanda proyectada - Inventario disponible.",
 "",
 "IMPORTANTE - factor NOVEDAD (+10%): aplica a rediseno/lanzamiento nuevo. Para reposicion pura usar",
 "   'Demanda_sin_novedad' (x1.674).",
 "",
 "DECISION CLAVE - inventario TALLER (almacen central): casi todos tienen mucho stock en TALLER",
 " (Poncho Adulto 1.227, Backpack Flex 1.154, Citybag 1.069, Poncho Kids 770, Cavapack 357, Eco Bag 161).",
 " 'Compra_con_TALLER' descuenta ese stock. 'Compra_solo_tiendas' asume que TALLER se reserva/liquida.",
 "",
 "ALERTAS:",
 " - CITYBAG: unico con necesidad real de compra fuerte (lanzamiento potente, poco stock vs demanda).",
 "   Solo tiene 2 meses de historia -> validar que el ritmo se sostenga (no sea solo hype de lanzamiento).",
 " - ECO BAG: pico atipico en Jun-2026 (272 uds, posible pedido corporativo). Revisar antes de proyectar.",
 " - PONCHOS: productos estacionales de lluvia (pico Ago-Oct). Nov-Abr es temporada baja para ellos.",
 " - Confirmar naturaleza del stock TALLER (disponible vs reservado).",
]})

# ---------- Citybag por color (modelo prioritario) ----------
dcb=v[v['modelo']=='CITYBAG']; icb=i[i['modelo']=='CITYBAG']
cbv=dcb.groupby('color')['cant'].sum().sort_values(ascending=False)
cbshare=cbv/cbv.sum()
cbinv=icb.groupby('color')['cant'].apply(lambda s:s.apply(lambda x:max(x,0)).sum())
cb_rows=[]
for c in cbv.index:
    cb_rows.append(dict(Color=c, Ventas_hist=int(cbv[c]), Mix_pct=round(cbshare[c]*100,1),
        Inv_actual=int(cbinv.get(c,0)),
        Compra_con_TALLER_1303=round(max(1303*cbshare[c]-0,0)),
        Compra_solo_tiendas_2372=round(max(2372*cbshare[c]-0,0))))
citybag=pd.DataFrame(cb_rows)
citybag.loc['TOTAL']=['TOTAL',int(cbv.sum()),100.0,int(cbinv.sum()),
    citybag['Compra_con_TALLER_1303'].sum(),citybag['Compra_solo_tiendas_2372'].sum()]

with pd.ExcelWriter(OUT,engine='openpyxl') as xl:
    notas.to_excel(xl,sheet_name='Guia',index=False)
    R.to_excel(xl,sheet_name='Compra_recomendada',index=False)
    citybag.to_excel(xl,sheet_name='Citybag_colores',index=False)
    men.to_excel(xl,sheet_name='Ventas_mensuales',index=False)
    estac.to_excel(xl,sheet_name='Estacionalidad',index=False)
    colores.to_excel(xl,sheet_name='Colores_mix',index=False)
    invdet.to_excel(xl,sheet_name='Inventario_detalle',index=False)
    for ws in xl.book.worksheets:
        for col in ws.columns:
            ml=max((len(str(c.value)) for c in col if c.value is not None),default=10)
            ws.column_dimensions[col[0].column_letter].width=min(ml+2,70)
print("\nGenerado:",OUT)
R.to_csv("/workspace/proyeccion_compra_bags/resultado_modelos2.csv",index=False)
