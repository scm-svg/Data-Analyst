# Data-Analyst

## Matriz ABC (inventario + ventas Odoo)

1. Colocar Excel en `data/` (ventas e inventario).
2. Regenerar: `python3 scripts/build_abc_dashboard.py`
3. Abrir en el navegador **`Matriz_ABC_Inventario.html`** (un solo archivo, ~2,5 MB; incluye data + lógica; no necesita internet salvo gráficos Chart.js).

Copia equivalente: `abc_inventario_completo.html`

**No uses** la plantilla vacía `abc_inventario_dashboard.html` (solo sirve para regenerar el build).

Dependencias Python (solo para regenerar): `pip install -r requirements-abc.txt`
