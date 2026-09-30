# Inventario S.S.G.G. — Mejoras aplicadas

Archivo entregable principal: **`INVENTARIO_SERV_JOSE_MEJORADO.xlsx`**

Panel web complementario (solo lectura): **`dashboard_inventario.html`**

## Qué tenía el archivo original

| Hoja | Función |
|------|---------|
| **PRODUCTOS** | Catálogo con códigos automáticos por categoría |
| **STOCK** | Existencias = entradas − salidas |
| **ENTRADA** / **SALIDA** | Kardex de movimientos |
| **INVENTARIO ABC** | Resumen de salidas (pivot) |
| **Hoja1** | Listas sueltas de pintura (sin integrar al kardex) |

## Problemas detectados

1. **Error en fórmula de ENTRADAS (STOCK)**  
   La columna usaba `SUMIFS(..., STOCK!B16:B18)` en lugar del código de la fila actual. Eso distorsionaba las entradas en varios productos.  
   **Corregido a:** `SUMIFS(ENTRADAS[CANTIDAD], ENTRADAS[CODIGO], PRODUCTOS[[#This Row],[CODIGO]])`

2. **132 productos con stock negativo** (más salidas que entradas registradas).  
   Requieren auditoría de movimientos o ajuste de inventario.

3. **Typo** en ENTRADA: "COSTO UNTARIO" → **UNITARIO**.

4. **Hoja1** mezclaba solicitudes de material sin código ni enlace al catálogo.

5. **Salidas** sin listas desplegables unificadas para tienda/responsable.

## Mejoras en el Excel mejorado

### Nuevas hojas (orden sugerido)

1. **DASHBOARD** — KPIs, totales y enlaces a ENTRADA, SALIDA, STOCK, etc.
2. **INSTRUCCIONES** — Guía de uso paso a paso.
3. **ALERTAS** — Vista dinámica (Excel 365) de ítems NEGATIVO / SIN STOCK / BAJO.
4. **CONFIG** — Listas maestras de **tiendas** y **técnicos** extraídas de SALIDA.

### STOCK ampliado

| Columna nueva | Uso |
|---------------|-----|
| **STOCK MÍN.** | Punto de reorden (editable; por defecto 0) |
| **ESTADO** | OK / BAJO / SIN STOCK / NEGATIVO |
| **OBSERVACIÓN** | Mensaje automático de reposición o revisión |

**Formato condicional:** rojo (negativo), amarillo (cero), verde/ámbar en ESTADO.

### SALIDA

- Validación de datos en **TIENDA** y **RESPONSABLE** contra listas en CONFIG.

### PINTURAS_AUX

- `Hoja1` renombrada; se recomienda cargar esos ítems al catálogo con código.

## Cómo usar después de abrir el archivo

1. Abrir en **Microsoft Excel** (365 o 2021+ recomendado por tablas y `XLOOKUP`).
2. Pulsar **Guardar** una vez para recalcular fórmulas (al regenerar el archivo, Excel recalcula al abrir).
3. En **STOCK**, asignar **STOCK MÍN.** a productos críticos.
4. Revisar **ALERTAS** y corregir movimientos o hacer ajustes de entrada.
5. Registrar nuevas operaciones solo en **ENTRADA** y **SALIDA**.

## Regenerar archivos

```bash
cd inventario
python3 mejorar_inventario.py
python3 generar_dashboard_html.py
```

## Próximos pasos recomendados (opcional)

- Migrar **PINTURAS_AUX** al catálogo LISTADO.
- Definir stock mínimo por categoría en CONFIG.
- Añadir columna **N° DOCUMENTO** único por movimiento (trazabilidad).
- Revisión mensual: filtrar ESTADO = NEGATIVO y cuadrar con conteo físico.
