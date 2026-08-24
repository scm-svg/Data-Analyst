# Tracking de Producción — Google Apps Script

Copia estos archivos al editor de Apps Script del Google Sheet de pedidos (`Por Hacer - Especial`).

## Archivos

| Archivo | Dónde va en Apps Script |
|---|---|
| `Code.gs` | Archivo de script (reemplaza `Code.gs` o pégalo como nuevo) |
| `Dashboard.html` | Archivo HTML (Archivo → Nuevo → Archivo HTML, nombre exacto: `Dashboard`) |
| `appsscript.json` | Manifest opcional (Proyecto → Configuración → mostrar manifest) |

## Instalación

1. Abre el Google Sheet (el equivalente a `Tracking - Pedidos.xlsx`).
2. **Extensiones → Apps Script**.
3. Pega `Code.gs` y crea el archivo HTML `Dashboard` con el contenido de `Dashboard.html`.
4. Guarda el proyecto. Recarga la hoja: aparece el menú **Tracking Producción**.
5. Primera vez: **Tracking Producción → Crear / actualizar hoja Config**.
6. **Tracking Producción → Recalcular fechas estimadas** escribe `Dia Estimado de Salida`, `Linea Asignada` y `Dias Habiles`.
7. **Tracking Producción → Abrir dashboard** (diálogo) o **Implementar → Aplicación web** para usarlo a pantalla completa.

Al implementar como Web App:
- Ejecutar como: tú
- Quién tiene acceso: tu cuenta, o “Cualquier persona de la organización” si el equipo debe verlo

## Cómo se estima la fecha de salida

La simulación arranca en `FECHA_INICIO` (hoy si está vacío) y solo cuenta días de `DIAS_LABORABLES` (lunes a sábado por defecto).

1. Toma cada fila con **faltante > 0**.
2. Ordena la cola:
   - primero **En Confeccion** (ya ocupan línea)
   - después **A espera de Confeccion** (listas para entrar)
   - luego el resto de etapas productivas
   - al final **Terminado** si todavía hay faltante
3. Cada SKU se asigna a la línea habilitada con menor carga (`1, 2` → elige 1 o 2).
4. La línea produce hasta `Cap Produccion por Dia` piezas/día (o `CAPACIDAD_DEFAULT` / `CAPACIDAD_LINEA_X`).
5. Varios SKUs pueden compartir el mismo día si cabe la capacidad.
6. La fecha de salida es el último día hábil en el que se completa el faltante.

## Hoja Config Tracking

| Parámetro | Uso |
|---|---|
| `HOJA_DATOS` | Nombre de la hoja. Vacío = detectar (busca columnas MO + SKU) |
| `FILA_ENCABEZADOS` | Fila de encabezados (en el archivo original es 2) |
| `DIAS_LABORABLES` | `1,2,3,4,5,6` = lun–sáb. `1,2,3,4,5` = lun–vie |
| `FECHA_INICIO` | `YYYY-MM-DD`. Vacío = hoy |
| `ETAPAS_EN_LINEA` | Ya en máquina |
| `ETAPAS_LISTAS` | Cola lista para confección |
| `ETAPAS_TERMINADO` | Cierre |
| `CAPACIDAD_DEFAULT` | Piezas/día si el SKU no trae capacidad |
| `CAPACIDAD_LINEA_1` | Override opcional por línea (también `_2`, `_3`, `_Estampado`) |

## Columnas esperadas

MO, Tipo, SKU, Producto, Genero, Color, Talla, Linea de Produccion, Cantidad Solicitada, Cantida Producida, Faltante, Cap Produccion por Dia, Dia Estimado de Salida, Etapa, MO STATUS, Clientes.

La fila 1 puede quedar vacía. Los encabezados van en la fila 2.

## Dashboard

Filtros por producto, tipo, línea, etapa, estatus, género, color, talla y cliente. Muestra solicitado / producido / faltante, avance, fecha estimada, carga por línea y calendario de salidas.
