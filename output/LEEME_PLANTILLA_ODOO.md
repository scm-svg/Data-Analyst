# Plantilla ajuste inventario Odoo — TH/Posproducción

Archivo: **`Plantilla_Ajuste_Posproduccion.xlsx`**

Generado desde `data_para_darle_forma_como_plantilla.xlsx` con el mismo formato que **Plantilla Ajuste inventario Odoo** (`product_id`, `inventory_quantity`, `location_id`).

## Ubicación

Todas las filas usan **`TH/Posproducción`**.

## Fuentes de datos (3 hojas)

| Origen | Filas | Cantidad |
|--------|------:|---------|
| SKU No Migrados | 124 | Ya traen `product_id` Odoo (p. ej. RIO ORIGINAL CAB) |
| ENTRADA LIMPIA | 193 | SKU + cantidades de entrada almacén |
| LISTA POR AJUSTE | 242 | Piezas sin orden de producción (se suman duplicados de SKU en esta hoja) |

## Hojas del Excel

1. **`Carga Posproducción`** — **import masivo Odoo**: una fila por SKU, cantidades **sumadas** entre las 3 fuentes. Si un SKU está en *No Migrados* y en otra hoja, gana el **`product_id` de No Migrados** (instancia Odoo correcta).
2. **`Detalle No Migrados` / `Detalle Entrada` / `Detalle Produccion`** — cada fuente en formato plantilla (sin cruzar hojas).
3. **`Trazabilidad`** — origen, SKU, método de `product_id`, cantidad.
4. **`PENDIENTES product_id`** — solo si falta algún nombre (vacía si todo resolvió).

## Regenerar

```bash
cd /workspace/scripts && python3 build_odoo_ajuste_plantilla.py
```

Resolución de `product_id`:

1. **Quants (stock.quant) (5).xlsx** — maestro Odoo (~3 400 SKU), formato con paréntesis `(color/talla, …)`
2. Quants (1)–(4), catálogo global, R2, MLMMJ, etc.

La hoja **`Sin referencia Quants 5`** lista los SKU que no aparecen en el maestro (18); conservan etiqueta de catálogo / No Migrados.
