# Ajuste SKU — piezas sin orden de producción

Archivo generado: **`por_ajuste_sku_con_sku.xlsx`**

## Qué se hizo

Se cruzó la hoja **LISTA POR AJUSTE producción** con el catálogo **MANUFACTURADO** del cuadro global de SKU, usando:

- Tipo de producto (con equivalencias de nombres, p. ej. `MIKA` → `MIKA SPORT LITE`, `SHORT SUBLIMADO` → `SHORT PLAYA ESTAMPADO`)
- Talla, género (`CABALLERO` → `CAB`, `KIDS` → `KIDS`) y color (normalización de acentos y abreviaturas como `G OSCURO` → `GRIS OSCURO`)

Columnas nuevas en la hoja principal:

| Columna | Descripción |
|--------|-------------|
| **SKU** | Código encontrado en catálogo |
| **PRODUCTO CATALOGO** | Nombre del producto en MANUFACTURADO |
| **MATCH_STATUS** | `ok` si hubo match; otro valor si falta revisión |

Hoja **PENDIENTES REVISION**: solo filas sin SKU (2 de 244).

## Pendientes (2 filas)

1. **SHORT SPORT** talla **16** KIDS (2 filas): en catálogo las tallas KIDS van hasta **14**; no hay SKU para talla 16.

## Urban Cotton

Las filas **URBAN COTTON** se resolvieron con la base **`urban_cotton_ACTX1.xlsx`** (hoja `BASE DATOS URBAN COTTON`), eligiendo el SKU más frecuente por género + talla + color cuando hay varias referencias (p. ej. CAB / AZUL MARINO → `URBAN COTTON OVERSIZED OUTSIDE`; DAMA / AZUL MARINO → `URBAN COTTON TOP SAY YES`). `MATCH_STATUS` = `ok_urban_cotton`.

## Pendientes anteriores (resuelto)

- ~~URBAN COTTON~~ — cubierto con la base ACTX1.

Para regenerar el archivo:

```bash
python3 /workspace/scripts/match_sku_ajuste.py
```
