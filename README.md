# Data-Analyst
<<<<<<< Updated upstream
Data Analyst
=======

Dashboards de análisis de ventas e inventario por modelo.

## Dashboards disponibles

| Archivo | Modelo |
|---------|--------|
| `dash_explorepants.html` | Explore Pants |
| `Dashboard_Rio_Original_Actualizado (1).html` | Rio Original |
| `dash_classicpolo.html` | Classic Polo |

## Explore Pants

Generar o actualizar el dashboard desde los CSV en `data/`:

```bash
python3 build_explore_pants_dashboard.py
```

Abrir `dash_explorepants.html` en el navegador. Las ventas incluyen devoluciones (cantidades negativas) que se netean contra las ventas positivas.

## Classic Polo

Generar o actualizar el dashboard desde los CSV en `data/`:

```bash
python3 build_classic_polo_dashboard.py
```

Abrir `dash_classicpolo.html` en el navegador.
>>>>>>> Stashed changes
