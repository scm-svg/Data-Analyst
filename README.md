# Data-Analyst

## Matriz ABC (inventario + ventas Odoo)

1. Colocar Excel en `data/` (ventas e inventario).
2. Regenerar datos: `python3 scripts/build_abc_dashboard.py`
3. Abrir **`abc_inventario_completo.html`** en el navegador (un solo archivo: script + data incluidos).
   También existe `abc_inventario_standalone.html` (mismo contenido).

Dependencias: `pip install -r requirements-abc.txt`
