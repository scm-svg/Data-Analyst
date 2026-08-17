# Data-Analyst

Dashboards de análisis de ventas e inventario por modelo.

## Dashboards disponibles

| Archivo | Modelo |
|---------|--------|
| `dash_explorepants.html` | Explore Pants |
| `Dashboard_Rio_Original_Actualizado (1).html` | Rio Original |

## Explore Pants

Generar o actualizar el dashboard desde los CSV en `data/`:

```bash
python3 build_explore_pants_dashboard.py
```

Abrir `dash_explorepants.html` en el navegador. Las ventas incluyen devoluciones (cantidades negativas) que se netean contra las ventas positivas. WEB y Pedidos entran en el análisis. Gris Claro + Gris Oscuro se unifican como **Gris**.
