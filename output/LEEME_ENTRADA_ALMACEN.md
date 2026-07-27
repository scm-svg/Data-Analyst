# Entrada almacén — completar PRODUCTO por SKU

Archivo generado: **`SKU_ENTRADA_ALMACEN_completado.xlsx`**

## Fuentes (orden de prioridad)

1. **Quants Odoo** — `Quants (stock.quant) (1).xlsx` y `(2).xlsx` (export `stock.quant`)
2. **Patrón R2** — SKU `SSR2VIU…` / `SRR2VIU…` sin quant (inferencia por código de color/talla)
3. **Cuadro global** — MANUFACTURADO y hojas relacionadas
4. **Urban Cotton ACTX1** — si aplica

## Corrección importante (R2)

Los SKU `SSR2VIU…` y `SRR2VIU…` **no** son Serenity (`SERVIDA…`) del cuadro global. En Odoo son:

| Prefijo SKU | Producto (columna PRODUCTO) | Ejemplo en Quants |
|-------------|----------------------------|-------------------|
| `SSR2VIU…` | **R2 SPORT 5"** | `[SSR2VIU43TL] R2 SPORT 5" (Negro, L)` |
| `SRR2VIU…` | **R2 RUNNING 3,5"** | `[SRR2VIU13TS] R2 RUNNING 3,5" (Azul Rey, S)` |

La hoja **`R2 VALIDADO QUANTS`** lista esas filas con `PRODUCTO_ODOO` (texto completo de Odoo).

SKUs R2 vistos en Quants pero no en catálogo global: **13** referencias (Sport + Running Azul Rey).

SKUs R2 solo inferidos (no aparecen en los 2 Quants): `SRR2VIU123…`, `SRR2VIU43…` — mismo lineamiento Running + color/talla del código SKU.

`MLMMJDA66TS` → **MILA** vía alias de catálogo (`MILMIDA66TS`); no está en los Quants exportados.

## Regenerar

```bash
cd /workspace/scripts && python3 fill_entrada_almacen.py
```
