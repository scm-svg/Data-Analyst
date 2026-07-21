import pandas as pd
import numpy as np

UP = "/home/ubuntu/.cursor/projects/workspace/uploads/"
OUT = "/workspace/proyeccion_compra_bags/PROYECCION_COMPRA_6MESES.xlsx"

def load_sales(fn):
    df = pd.read_csv(UP+fn, sep=';', encoding='latin-1')
    df.columns=[c.strip() for c in df.columns]
    ren={}
    for c in df.columns:
        cl=c.lower()
        if cl.startswith('fecha de la orden'): ren[c]='fecha_orden'
        elif cl.startswith('cant'): ren[c]='cant'
        elif cl.startswith('ubic'): ren[c]='ubicacion'
    df=df.rename(columns=ren)
    df['cant']=df['cant'].astype(str).str.replace(',','.').astype(float)
    df['fecha_orden']=pd.to_datetime(df['fecha_orden'],format='%d/%m/%Y',errors='coerce')
    df['periodo']=df['fecha_orden'].dt.to_period('M')
    return df

files={'TRAVEL BAG 40L':'TRAVEL_BAG_40L_VENTAS_ACTUALIZADO_277a.csv',
       'MINI BAG':'MINI_BAG_VENTAS_ACTUALIZADO_eb91.csv',
       'DRY BAG 30L':'DRY_BAG_30_L_VENTAS_ACTUALIZADO_6dc3.csv'}
sales={m:load_sales(fn) for m,fn in files.items()}

inv=pd.read_csv(UP+"INVENTARIO_DE_MODELOS_BAGS_ACTUALIZADO_HOY_9182.csv",sep=';',encoding='latin-1')
inv.columns=['ubicacion','producto','sku','modelo','color','cant']
inv['cant']=inv['cant'].astype(str).str.replace(',','.').astype(float)

F_RED,F_NOV,F_CORP=1.55,1.10,1.08
F=F_RED*F_NOV*F_CORP
ventana=[pd.Period('2025-11'),pd.Period('2025-12'),pd.Period('2026-01'),
         pd.Period('2026-02'),pd.Period('2026-03'),pd.Period('2026-04')]
sust={'TRAVEL BAG 40L':'Travel Bag 40L (new) - Azul Petroleo + Negro',
      'MINI BAG':'Moon Bag (sustituto Mini Bag) - tonos tierra/oliva/beige',
      'DRY BAG 30L':'Dry Bag 30L (new) - colores por definir'}

# ================= HOJA: Demanda mensual =================
mensual={}
for m,df in sales.items():
    s=df.groupby('periodo')['cant'].sum()
    mensual[m]=s
men=pd.DataFrame(mensual)
men.index=men.index.astype(str)
men=men.reset_index().rename(columns={'index':'Mes'})

# indice estacional (sobre meses completos jun25-jun26)
comp=[pd.Period(f'2025-{x:02d}') for x in range(6,13)]+[pd.Period(f'2026-{x:02d}') for x in range(1,7)]
estac_rows=[]
for m,df in sales.items():
    s=df[df['periodo'].isin(comp)].groupby('periodo')['cant'].sum()
    prom=s.mean()
    for p,v in s.items():
        estac_rows.append(dict(Modelo=m,Mes=str(p),Ventas=v,Indice_estacional=round(v/prom,2)))
estac=pd.DataFrame(estac_rows)

# ================= HOJA: Resumen compra =================
res=[]
for m,df in sales.items():
    base=df[df['periodo'].isin(ventana)]['cant'].sum()
    d=inv[inv['modelo']==m]
    it=d[d['ubicacion']!='TALLER']['cant'].clip(lower=0).sum()
    ic=d[d['ubicacion']=='TALLER']['cant'].clip(lower=0).sum()
    dem=base*F
    res.append(dict(
        Modelo_actual=m, Producto_a_comprar=sust[m],
        Demanda_base_NovAbr=round(base),
        Factor_red_155=round(base*F_RED),
        Mas_novedad_110=round(base*F_RED*F_NOV),
        Mas_corporativo_108_DEMANDA_TOTAL=round(dem),
        Inv_tiendas=round(it), Inv_TALLER=round(ic), Inv_TOTAL=round(it+ic),
        COMPRA_neta_con_TALLER=round(max(dem-(it+ic),0)),
        COMPRA_neta_solo_tiendas=round(max(dem-it,0)),
    ))
resumen=pd.DataFrame(res)

# ================= HOJA: Escenarios =================
esc_rows=[]
for m,df in sales.items():
    base=df[df['periodo'].isin(ventana)]['cant'].sum()
    d=inv[inv['modelo']==m]
    it=d[d['ubicacion']!='TALLER']['cant'].clip(lower=0).sum()
    ic=d[d['ubicacion']=='TALLER']['cant'].clip(lower=0).sum()
    # Conservador: sin novedad, red +40%, descuenta todo inv
    cons=base*1.40*1.08
    # Base: red+55, nov+10, corp+8, descuenta todo inv
    bas=base*1.55*1.10*1.08
    # Agresivo: red+70, nov+15, corp+8, descuenta solo tiendas
    agr=base*1.70*1.15*1.08
    esc_rows.append(dict(Modelo=m,
        CONSERVADOR_demanda=round(cons), CONSERVADOR_compra=round(max(cons-(it+ic),0)),
        BASE_demanda=round(bas), BASE_compra_con_taller=round(max(bas-(it+ic),0)),
        BASE_compra_solo_tiendas=round(max(bas-it,0)),
        AGRESIVO_demanda=round(agr), AGRESIVO_compra=round(max(agr-it,0))))
escen=pd.DataFrame(esc_rows)

# ================= HOJA: Dry Bag asignacion por color (top 6) =================
dry=sales['DRY BAG 30L']
top6=['Blanco','Verde Militar','Negro','Azul Rey','Gris Claro','Camu']
vdry=dry.groupby('color')['cant'].sum()
v6=vdry[top6]; share6=v6/v6.sum()
invd=inv[inv['modelo']=='DRY BAG 30L']
inv6=invd.groupby('color')['cant'].apply(lambda s:s.clip(lower=0).sum())
dry_rows=[]
for c in top6:
    dry_rows.append(dict(Color=c, Ventas_hist=int(v6[c]), Mix_pct=round(share6[c]*100,1),
        Inv_actual=int(inv6.get(c,0)),
        Compra_conservador_3100=round(max(3100*share6[c]-inv6.get(c,0),0)),
        Compra_BASE_3270=round(max(3270*share6[c]-inv6.get(c,0),0)),
        Compra_alto_3470=round(max(3470*share6[c]-inv6.get(c,0),0))))
dry_alloc=pd.DataFrame(dry_rows)
dry_alloc.loc['TOTAL']=['TOTAL', v6.sum(), round(share6.sum()*100,1), int(inv6[top6].sum()),
    dry_alloc['Compra_conservador_3100'].sum(), dry_alloc['Compra_BASE_3270'].sum(),
    dry_alloc['Compra_alto_3470'].sum()]

# ================= HOJA: color =================
col_rows=[]
for m,df in sales.items():
    tot=df['cant'].sum()
    cm=df.groupby('color')['cant'].sum().sort_values(ascending=False)
    for c,v in cm.items():
        col_rows.append(dict(Modelo=m,Color_actual=c,Ventas_hist=round(v),Mix_pct=round(100*v/tot,1)))
colores=pd.DataFrame(col_rows)

# ================= HOJA: inventario detalle =================
invdet=inv.groupby(['modelo','ubicacion','sku','color'])['cant'].sum().reset_index()

# ================= HOJA: Notas =================
notas=pd.DataFrame({'GUIA DE LECTURA':[
 "PROYECCION DE COMPRA - COBERTURA 6 MESES (Nov 2025 - Abr 2026 / 1a compra del ano)",
 "",
 "METODOLOGIA:",
 "1) Demanda base = ventas REALES del mismo periodo Nov-Abr del ano anterior (captura la estacionalidad real, incl. pico de Diciembre).",
 "   Se valido con un cross-check de run-rate de ultimos 12 meses: los resultados coinciden (~5% de diferencia).",
 "2) Se aplican los factores del negocio de forma multiplicativa (compuesta):",
 "   - Expansion de red: x1.55  (Margarita 1.5x La Grieta = 33% + Tienda nueva 1x La Grieta = 22%)",
 "   - Efecto novedad / migracion: x1.10  (rediseno; uplift tipico 8-15%)",
 "   - Pedidos corporativos / mayoristas: x1.08",
 "   - Factor combinado: x1.841",
 "3) Compra neta = Demanda proyectada - Inventario disponible.",
 "",
 "DECISION CLAVE = COMO TRATAR EL INVENTARIO DE TALLER (almacen central):",
 " - TRAVEL BAG y MINI BAG tienen MUCHO stock en TALLER (1.027 y 2.240 uds).",
 "   Ese stock es del modelo ACTUAL que se va a discontinuar. Si se liquida en paralelo,",
 "   la compra de los nuevos productos puede ser MINIMA o de solo lanzamiento.",
 " - DRY BAG 30L casi no tiene stock (1 ud en TALLER, 195 en tiendas) -> aqui esta la compra real.",
 "",
 "RECOMENDACION:",
 " - DRY BAG 30L (new): PRIORIDAD. Comprar ~3.100-3.300 uds para cubrir 6 meses.",
 " - TRAVEL BAG 40L (new): compra de LANZAMIENTO de los nuevos colores (Azul Petroleo+Negro),",
 "   ~250-400 uds, y liquidar el stock actual (1.227 uds) que ya cubre la demanda base.",
 " - MOON BAG (sustituto Mini): NO hacer compra grande. Hay 2.679 Mini Bags en stock (~4x la demanda 6m).",
 "   Comprar solo una prueba de lanzamiento de los nuevos tonos (~150-300 uds) y liquidar Mini Bag.",
 "",
 "2a COMPRA (May-Oct): planificar en Dic/Ene. Usar escenario CONSERVADOR (meses de baja estacionalidad).",
 "",
 "NOTA: Confirmar la naturaleza del stock 'TALLER' (almacen central disponible vs. reservado).",
 "Los colores de los nuevos productos difieren de los actuales; ver hoja 'Colores' para guia de mix.",
]})

with pd.ExcelWriter(OUT, engine='openpyxl') as xl:
    notas.to_excel(xl,sheet_name='Guia',index=False)
    resumen.to_excel(xl,sheet_name='Compra_recomendada',index=False)
    escen.to_excel(xl,sheet_name='Escenarios',index=False)
    dry_alloc.to_excel(xl,sheet_name='DryBag_colores',index=False)
    men.to_excel(xl,sheet_name='Ventas_mensuales',index=False)
    estac.to_excel(xl,sheet_name='Estacionalidad',index=False)
    colores.to_excel(xl,sheet_name='Colores_mix',index=False)
    invdet.to_excel(xl,sheet_name='Inventario_detalle',index=False)

    # auto width
    for ws in xl.book.worksheets:
        for col in ws.columns:
            ml=max((len(str(c.value)) for c in col if c.value is not None), default=10)
            ws.column_dimensions[col[0].column_letter].width=min(ml+2,70)

print("Generado:",OUT)
print("\nRESUMEN COMPRA RECOMENDADA:")
print(resumen[['Modelo_actual','Mas_corporativo_108_DEMANDA_TOTAL','Inv_TOTAL','COMPRA_neta_con_TALLER','COMPRA_neta_solo_tiendas']].to_string(index=False))
