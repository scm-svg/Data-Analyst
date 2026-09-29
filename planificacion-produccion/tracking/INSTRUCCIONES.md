# Tracking de Producción v5.9.2 — envío de correo

El error `No tienes permiso para llamar a MailApp.sendEmail` (scope `script.send_mail`) no es un fallo de la tabla HTML. Google no tiene autorizado el envío de correo para este proyecto. Un **botón/dibujo** de la hoja casi nunca abre el diálogo de OAuth: hay que autorizar **una vez desde el editor**.

## Cómo instalar (borrar y pegar)

En el archivo **Tracking de Producción** (no el de Planificación):

1. Abre **Extensiones → Apps Script**.
2. Reemplaza todo `Codigo.gs` con `planificacion-produccion/tracking/Codigo.gs`.
3. En el editor: **Configuración del proyecto** (engranaje) → activa **Mostrar el archivo de manifiesto appsscript.json**.
4. Abre `appsscript.json` y reemplázalo por `planificacion-produccion/tracking/appsscript.json`. El manifiesto **debe** listar `script.send_mail` y `gmail.send`. Si el manifiesto ya existía sin esos scopes, `MailApp` falla aunque el código esté bien.
5. Guarda el proyecto (Ctrl+S / Cmd+S).

## Autorizar una vez (obligatorio)

1. En el editor, arriba selecciona la función **`autorizarEnvioCorreo`**.
2. Pulsa **Ejecutar**.
3. Elige tu cuenta de Google.
4. Si sale **Aplicación no verificada**: **Avanzado → Ir a [nombre del proyecto] (no seguro) → Permitir**.
5. Acepta **Enviar correo electrónico en tu nombre** y, si aparece, **Enviar correo a través de Gmail**.
6. Vuelve a la hoja, recarga (F5). En el menú **⚙️ Tracking** debe aparecer **🔐 Autorizar envío de correo (una vez)** (ya no hace falta si el paso 5 salió bien).
7. Envía con **⚙️ Tracking → 📧 Enviar Reporte de Producción (Correo)**.

Hasta que el editor muestre la ventana de permisos y tú aceptes, el botón de la hoja seguirá diciendo que no hay permiso. Después de autorizar, el botón sí puede usarse.

## Destinatarios

La pestaña **Correo** debe tener direcciones válidas en la columna A (una por fila).

## Si Workspace bloquea MailApp

El script intenta primero **GmailApp** y, si falla, **MailApp**. Si ambos fallan, un administrador de Google Workspace puede tener desactivado el envío de correo para Apps Script. En ese caso hay que permitir `script.send_mail` / Gmail para tu usuario.
