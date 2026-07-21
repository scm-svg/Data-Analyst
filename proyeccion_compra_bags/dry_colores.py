import pandas as pd

UP = "/home/ubuntu/.cursor/projects/workspace/uploads/"

df = pd.read_csv(UP+"DRY_BAG_30_L_VENTAS_ACTUALIZADO_6dc3.csv", sep=';', encoding='latin-1')
df.columns=[c.strip() for c in df.columns]
df=df.rename(columns={'Cant. ordenada':'cant'})
df['cant']=df['cant'].astype(str).str.replace(',','.').astype(float)

inv=pd.read_csv(UP+"INVENTARIO_DE_MODELOS_BAGS_ACTUALIZADO_HOY_9182.csv",sep=';',encoding='latin-1')
inv.columns=['ubicacion','producto','sku','modelo','color','cant']
inv['cant']=inv['cant'].astype(str).str.replace(',','.').astype(float)
invd=inv[inv['modelo']=='DRY BAG 30L']

# Colores prioritarios (top 6 segun cliente)
top6=['Blanco','Verde Militar','Negro','Azul Rey','Gris Claro','Camu']
ventas=df.groupby('color')['cant'].sum()
v6=ventas[top6]
share=v6/v6.sum()

# Objetivos de compra total (escenarios) para Dry Bag
targets={'Conservador (3.100)':3100,'Base recomendado (3.270)':3270,'Alto (3.470)':3470}

# Inventario por color (red completa)
inv_col=invd.groupby('color')['cant'].apply(lambda s: s.clip(lower=0).sum())

print("MIX Dry Bag (top 6, renormalizado):")
for c in top6:
    print(f"  {c:14s} ventas={int(v6[c]):4d}  share={share[c]*100:5.1f}%  inv_actual={int(inv_col.get(c,0)):3d}")
print(f"  Suma top6 = {int(v6.sum())} uds  (= {v6.sum()/ventas.sum()*100:.1f}% del total Dry Bag)\n")

for name,T in targets.items():
    print(f"=== COMPRA DRY BAG - {name} uds ===")
    tot=0
    for c in top6:
        alloc=T*share[c]
        neto=max(alloc-inv_col.get(c,0),0)
        tot+=neto
        print(f"  {c:14s} {neto:6.0f} uds")
    print(f"  {'TOTAL':14s} {tot:6.0f} uds (neto de inventario)\n")
