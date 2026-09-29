# Tracking de Producción v5.9.3 — correo diario

## Cómo instalar (borrar y pegar)

En el archivo **Tracking de Producción** (no el de Planificación):

1. Abre **Extensiones → Apps Script**.
2. Reemplaza todo `Codigo.gs` con `planificacion-produccion/tracking/Codigo.gs`.
3. En el editor: **Configuración del proyecto** → **Mostrar el archivo de manifiesto appsscript.json**.
4. Reemplaza `appsscript.json` con `planificacion-produccion/tracking/appsscript.json`.
5. Guarda. Si aún no autorizaste el envío: ejecuta **`autorizarEnvioCorreo`** una vez.

## Qué hace el correo diario

- Asunto: `Reporte de Producción Diaria y Proyección a Almacén` (sin emojis; Gmail los rompía).
- La nota de almacén también va sin emoji.
- El **Resumen General (Tracking)** se arma sin líneas de cuadrícula.
- Solo salen **modelos y cantidades nuevas**. Lo ya enviado se guarda en la hoja oculta `_Correo Enviado`. Si un SKU pasa de 20 a 35, el siguiente correo lleva 15.
- Si no hay nada nuevo, el script avisa y no manda correo.
- Para reenviar todo (por un correo de prueba): menú **Tracking → Reiniciar historial de correo diario**.

## Destinatarios

La pestaña **Correo** debe tener direcciones válidas en la columna A.
