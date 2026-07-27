# Entrada almacén — completar PRODUCTO por SKU

Archivo generado: **`SKU_ENTRADA_ALMACEN_completado.xlsx`**

## Fuentes (orden de prioridad)

1. **Quants Odoo** — exports `(1)` … **`(4)`** (`stock.quant`)
2. **Etiquetas Odoo confirmadas** — p. ej. `MLMMJDA66TS`
3. **Patrón R2** — SKU `SSR2VIU…` / `SRR2VIU…` sin quant
4. **Cuadro global** — MANUFACTURADO y hojas relacionadas

## Quants (3) — `ok_r2_inferred` actualizado

| SKU | Producto Odoo |
|-----|----------------|
| `SRR2VIU123…` | R2 RUNNING 3,5" **(Verde Manzana, …)** — no azul marino |
| `SRR2VIU43TS` | R2 RUNNING 3,5" (Negro, S) |

## Quants (4) — R2 negro L / M / XS

Confirmados en Odoo: `SRR2VIU43TL`, `SRR2VIU43TM`, `SRR2VIU43TXS` → R2 RUNNING 3,5" (Negro, …).

Todos los SKU fuera de catálogo global quedan **`ok_quants_odoo`** o **`ok_odoo_known`** (MLMMJ); ya no hay `ok_r2_inferred`.

## MLMMJDA66TS

**No** es MILA. Producto Odoo:

`[MLMMJDA66TS] MOTION LOOP MAFE DAMA (Verde Militar, S)`

Columna **PRODUCTO**: **MOTION LOOP MAFE DAMA** (`ok_odoo_known`).

## Corrección importante (R2)

Los SKU `SSR2VIU…` y `SRR2VIU…` **no** son Serenity (`SERVIDA…`) del cuadro global. En Odoo son:

| Prefijo SKU | Producto (columna PRODUCTO) | Ejemplo en Quants |
|-------------|----------------------------|-------------------|
| `SSR2VIU…` | **R2 SPORT 5"** | `[SSR2VIU43TL] R2 SPORT 5" (Negro, L)` |
| `SRR2VIU…` | **R2 RUNNING 3,5"** | `[SRR2VIU13TS] R2 RUNNING 3,5" (Azul Rey, S)` |

La hoja **`R2 VALIDADO QUANTS`** lista esas filas con `PRODUCTO_ODOO` (texto completo de Odoo).

SKUs R2 vistos en Quants pero no en catálogo global: **13** referencias (Sport + Running Azul Rey).

SKUs R2: todos confirmados vía Quants (1)–(4) salvo inferencia obsoleta.

`MLMMJDA66TS` → **MOTION LOOP MAFE DAMA** (etiqueta Odoo confirmada; no MILA).

## Regenerar

```bash
cd /workspace/scripts && python3 fill_entrada_almacen.py
```
