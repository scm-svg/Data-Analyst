# Data-Analyst

## Matriz ABC (inventario + ventas Odoo)

1. Colocar Excel en `data/` (ventas e inventario).
2. Regenerar datos: `python3 scripts/build_abc_dashboard.py`
3. Abrir **`abc_inventario_standalone.html`** en el navegador (doble clic), o servir la carpeta:
   `python3 -m http.server 8765` → `abc_inventario_dashboard.html`

Dependencias: `pip install -r requirements-abc.txt`
