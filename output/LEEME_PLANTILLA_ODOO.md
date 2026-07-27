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

## SHORT SPORT R1 (Quants 6 + Ventas)

Los SKU **`SHOSPBFCA*` / `SHOSPBFDA*`** del catálogo global **no existen en Odoo**.  
Para líneas **R1** se usan **`SHUNTCA*` / `SHUNTDA*`** desde **Quants (6)** y, si falta una variante (p. ej. **SHUNTCA157TM** CAB Gris M), desde **`Reporte_ventas_UNIFICADO_COMPLETO.xlsx`**.

Remapeos de SKU erróneo en lista de producción (ventas / Odoo):

| SKU en lista | SKU correcto |
|--------------|--------------|
| CLASPCA16TS | CLAMECA16TS |
| CLMSUCA152TM | MLCMJCA66TM |

Hoja **`R1 SKU corregidos Q6`**: reemplazos R1 y remapeos anteriores.  
Hoja **`R1 sin match Quants 6`**: combinaciones sin SKU en Odoo (no se inventan).

## Reporte de ventas (validación)

**`Reporte_ventas_UNIFICADO_COMPLETO_eb79.xlsx`** (hoja Ventas, columna *Variante del producto*) tiene prioridad sobre catálogo para el texto Odoo cuando el SKU aparece en ventas.

- **`Validacion vs Ventas`**: discrepancias en la hoja de carga consolidada.
- **`Etiquetas distintas ventas`**: SKUs en la carga cuyo texto no coincide con ventas (revisión manual; a veces ventas trae códigos de color extra).

1. **Ventas unificado** — etiqueta Odoo en producción real
2. **Quants (stock.quant) (5).xlsx** — maestro Odoo (~3 400 SKU), formato con paréntesis `(color/talla, …)`
3. Quants (1)–(4), catálogo global, R2, MLMMJ, etc.

La hoja **`Sin referencia Quants 5`** lista los SKU que no aparecen en el maestro (18); conservan etiqueta de catálogo / No Migrados.
