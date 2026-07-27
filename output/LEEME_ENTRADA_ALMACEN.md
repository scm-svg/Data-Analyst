# Entrada almacén — completar PRODUCTO por SKU

Archivo generado: **`SKU_ENTRADA_ALMACEN_completado.xlsx`**

## Entrada

`SKU POR ARREGLAR ENTRADA ALMACEN.xlsx` — 193 filas con **SKU** y **CANT**, columna **PRODUCTO** vacía.

## Fuentes

- Cuadro global (`Coopia de Cuadro - SKU Productos (Global).xlsx`): hojas MANUFACTURADO, CLASFSKUSYSGRIETA, EQUIPAMIENTO, etc.
- Urban Cotton ACTX1 (por si aplica; esta lista no traía SKUs `TALG…`)

## Resultado

| Estado | Filas |
|--------|------:|
| `ok` — SKU exacto en catálogo | 175 |
| `ok_sku_corregido` — SKU con alias/typo | 18 |
| **Total con PRODUCTO** | **193** |

## Hojas del Excel

1. **ENTRADA LIMPIA** — solo `SKU`, `PRODUCTO`, `CANT` (lista para cargar)
2. **Hoja1** — incluye `SKU_CATALOGO`, `FUENTE`, `ESTADO` (auditoría)
3. **PENDIENTES** — solo si queda algo sin match (vacía en esta corrida)

## SKUs corregidos (18)

Patrones detectados en entrada de almacén:

| Patrón en archivo | SKU catálogo | Producto |
|-------------------|--------------|----------|
| `SSR2VIU…` / `SRR2VIU…` | `SERVIDA…` | SUMMER COOL 2.0 SERENITY |
| `…123T…` (color azul marino mal digitado) | `…12T…` | SUMMER COOL 2.0 SERENITY |
| `SRR2VIU13T…` (truncó `123`) | `SERVIDA12T…` | SUMMER COOL 2.0 SERENITY |
| `MLMMJDA…` | `MILMIDA…` | MILA |

Regenerar:

```bash
cd /workspace/scripts && python3 fill_entrada_almacen.py
```
