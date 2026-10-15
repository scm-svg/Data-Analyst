# Verificación chequeo vs plantilla

Archivo: **`verificacion.xlsx`**

Compara **`data_para_chequeo.xlsx`** (No Migrados + Hoja4 entrada + Reporte piezas producción) contra **`Plantilla_Ajuste_Posproduccion.xlsx`**.

## Regenerar

```bash
cd /workspace/scripts && python3 verify_chequeo_plantilla.py
```

## Hojas

| Hoja | Contenido |
|------|-----------|
| **Resumen** | Conteos y totales |
| **No Migrados vs plantilla** | SKU a SKU vs trazabilidad `SKU No Migrados` |
| **Entrada vs plantilla** | Hoja4 vs `ENTRADA LIMPIA` (con remapeos CLASPCA→CLAMECA, etc.) |
| **Produccion detalle** | Cada fila del reporte → SKU resuelto |
| **Produccion SKU vs plantilla** | Cantidades agregadas vs `LISTA POR AJUSTE` |
| **Consolidado chequeo vs carga** | Todos los SKUs del chequeo vs hoja **Carga Posproducción** |
| **Pendientes revision** | Solo filas con discrepancia |
| **Solo en plantilla** | SKUs en plantilla que no vienen del chequeo (p. ej. más líneas de producción que en el reporte resumido) |
| **Produccion sin SKU** | Filas sin match (SHORT SPORT KIDS 16) |
