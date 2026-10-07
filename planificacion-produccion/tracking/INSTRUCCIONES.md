# Tracking de Producción v5.9.5 — turnos diurno y nocturno

## Cómo instalar (borrar y pegar)

En el archivo **Tracking de Producción** (no el de Planificación):

1. Abre **Extensiones → Apps Script**.
2. Reemplaza todo `Codigo.gs` con `planificacion-produccion/tracking/Codigo.gs`.
3. En el editor: **Configuración del proyecto** → **Mostrar el archivo de manifiesto appsscript.json**.
4. Reemplaza `appsscript.json` con `planificacion-produccion/tracking/appsscript.json`.
5. Guarda. Si aún no autorizaste el envío: ejecuta **`autorizarEnvioCorreo`** una vez.
6. Recarga la hoja y usa **Tracking → Actualizar Tablero (Costura)** para llenar ambos tableros.

## Turnos

- En **Unidades Producidas - Costura**, la columna **I (Turno)** debe decir `Diurno` o `Nocturno`. Si queda vacía, cuenta como Diurno.
- **Tracking → Actualizar Tablero (Costura)** reparte el Real (Unds) al tablero de arriba (diurno) o al de abajo (nocturno, marcado `NOCTURNO`).
- **Detalle Tracking - Produccion** incluye **Turno** en la columna E.
- Pedidos sin columna Turno siguen yendo a Línea 1 del diurno.

## Qué hace el correo diario

- Asunto: `Reporte de Producción Diaria y Proyección a Almacén` (sin emojis; Gmail los rompía).
- La nota de almacén también va sin emoji.
- El **Resumen General** copia **ambos** tableros (diurno y nocturno) tal cual están en la hoja (sin cuadrícula).
- El **detalle** sí sale solo con **modelos y cantidades nuevas**, ahora con columna Turno. Lo ya enviado se guarda en `_Correo Enviado`. Un mismo SKU en diurno y nocturno no se mezcla.
- Claves viejas del historial (sin turno) se leen como Diurno.
- Si no hay nada nuevo, el script avisa y no manda correo.
- Para reenviar todo (por un correo de prueba): menú **Tracking → Reiniciar historial de correo diario**.

## Destinatarios

La pestaña **Correo** debe tener direcciones válidas en la columna A.
