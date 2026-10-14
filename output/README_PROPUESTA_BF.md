# Propuesta Black Friday · ABC · Categoría C · Equipamiento

## Archivos

| Archivo | Descripción |
|---------|-------------|
| `PROPUESTA_BLACK_FRIDAY_ABC_C_EQUIPAMIENTO.xlsx` | Libro principal para directiva |
| `dashboard_bf_abc_data.json` | Datos del dashboard HTML |

## Hojas del Excel

- **00_RESUMEN** — KPIs del cruce inventario/ventas
- **00_METODOLOGIA** — Reglas ABC y definición de equipamiento manufacturado
- **ABC_MODELOS** — Clasificación ABC por modelo (unidades vendidas)
- **BF_LISTADO_C_EQUIP** — 25 modelos C · equipamiento · manufacturado
- **BF_SKUS_C_EQUIP_STOCK** — Detalle SKU con stock para activación
- **DETALLE_SKU** — Universo completo por SKU
- **INV_POR_TIENDA** — Inventario por ubicación y modelo

## Regenerar

```bash
python3 scripts/black_friday_abc_analysis.py
```

Abrir dashboard: `DASHBOARD_BLACK_FRIDAY_ABC_C_EQUIPAMIENTO.html`
