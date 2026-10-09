# Tracking de Producción v5.9.8 — correo diario y resumen semanal de gerencia

## Cómo instalar (borrar y pegar)

En el archivo **Tracking de Producción** (no el de Planificación):

1. Abre **Extensiones → Apps Script**.
2. Reemplaza todo `Codigo.gs` con `planificacion-produccion/tracking/Codigo.gs`.
3. En el editor: **Configuración del proyecto** → **Mostrar el archivo de manifiesto appsscript.json**.
4. Reemplaza `appsscript.json` con `planificacion-produccion/tracking/appsscript.json`.
5. Guarda. Si aún no autorizaste el envío: ejecuta **`autorizarEnvioCorreo`** una vez.
6. Recarga la hoja y usa **Tracking → Actualizar Tablero (Costura)** para llenar ambos tableros.

## Pestaña Correo (dos columnas)

| Columna | Encabezado fila 1 | Quién recibe | Qué se envía |
|---|---|---|---|
| A | `Correos Diario` | Operación / almacén / taller | Solo **cantidades nuevas** desde el último correo diario |
| B | `Correos Gerencia` | Gerencia | **Toda la semana productiva** (cierre de semana) |

No mezclar las columnas. El reporte diario ya no toma correos de la columna B.

## Turnos

- En **Unidades Producidas - Costura**, la columna **I (Turno)** debe decir `Diurno` o `Nocturno`. Si queda vacía, cuenta como Diurno.
- **Tracking → Actualizar Tablero (Costura)** reparte el Real (Unds) al tablero de arriba (diurno) o al de abajo (nocturno, marcado `NOCTURNO`).
- **Detalle Tracking - Produccion** incluye **Turno** en la columna E.
- Pedidos sin columna Turno siguen yendo a Línea 1 del diurno.

## Correo diario — Tracking → Enviar Reporte Diario

- Destinatarios: columna **Correos Diario**.
- Asunto: `Reporte de Producción Diaria y Proyección a Almacén` (sin emojis; Gmail los rompía).
- El **Resumen General** copia los tableros **diurno**, **nocturno** y el **Total del día**.
- El **detalle** sí sale solo con **modelos y cantidades nuevas**, con Dia, Fecha, Linea, Turno, MO, SKU, Producto, Genero, Color, Talla, Cantidad.
- Lo ya enviado se guarda en `_Correo Enviado`. Si no hay nada nuevo, no manda correo.
- Para reenviar todo: **Tracking → Reiniciar historial de correo diario**.

## Correo gerencia — Tracking → Enviar Resumen Semanal (Gerencia)

- Destinatarios: columna **Correos Gerencia**.
- Pensado para el **viernes o sábado** (cierre de semana). Si se envía otro día, el script avisa y pide confirmación.
- Asunto: `Resumen semanal de producción — piezas en proceso hacia almacén y tienda`.
- El mensaje indica que las prendas **ya salieron de producción**, están **en proceso** y **próximas a almacén** (~3 días hábiles) y luego **a tienda**.
- El detalle **no** usa el historial diario: resume **toda la semana**.
- Columnas del detalle: **MO-SKU**, **Producto**, **Genero**, **Color**, **Talla**, **Cantidad**.
- Si el mismo MO coincide (mismo SKU, producto, color y talla en varios días/líneas/turnos), las cantidades se **suman** en una sola fila.
- Este envío **no** marca `_Correo Enviado`; el diario sigue restando solo lo que ya avisó operación.

## Destinatarios (Excel 5)

Ejemplo: operación en **Correos Diario**; gerencia (p. ej. `analistaprocesoscuadro@gmail.com`) en **Correos Gerencia**.
