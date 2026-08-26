# Planificación de Producción v5.6 — códigos listos para pegar

## Cómo instalar (borrar y pegar)

En el editor de **Google Apps Script** del archivo de Planificación:

1. Abre `Codigo.gs`, selecciona **todo**, bórralo y pega el contenido completo de `planificacion-produccion/Codigo.gs`.
2. Abre (o crea) el archivo HTML llamado **`Dashboard`** (sin `.html`). Selecciona **todo**, bórralo y pega el contenido completo de `planificacion-produccion/Dashboard.html`.
3. Guarda el proyecto. Recarga la hoja de cálculo para ver los menús `⚙️ Producción`, `👁️ Ver Pestañas` y `⚙️ Tracking`.
4. Si usas la Web App del dashboard: **Implementar → Implementación nueva → Aplicación web** (o vuelve a implementar la existente).

No hace falta cambiar la estructura de pestañas. La columna **Cantidad Minima** de `Priorizacion` (columna F) es la fuente del cupo de almacén. Los modelos especiales salen de `Por Hacer - Especial`.

## Orden de carga v5.6

1. **Especial** — todo lo de `Por Hacer - Especial`.
2. **Cantidad mínima (prioridad máxima)** — si el modelo tiene cupo en `Priorizacion!Cantidad Minima`, esas piezas salen con máxima urgencia, **antes** que Urgente/Alta/Media/Baja y **antes** que cualquier modelo sin mínima, aunque la fecha objetivo sea más lejana. El cupo **no espera** el “día de inicio” del SKU (en el archivo actual Negro/Blanco/Azul Marino de RIO DAMA arrancaban el martes y por eso VITA se comía el lunes de la línea 4).
3. **Resto del paneo** — fecha de salida + prioridad, con colores núcleo primero.

## Tableros semanales

En `Planificacion`, `Semana 2`, `Semana 3`, `Semana 4` y `Semana 5` los modelos se listan **por línea** y, dentro de cada línea, por el **primer día de esa semana con unidades** (flujo real), no por fecha objetivo. El resumen de cada hoja sigue el mismo orden de bandas: Especial → Mínima → Resto.

## Qué más conserva esta versión (v5.5)

- **Colores núcleo primero**: Negro, Blanco y Azul Marino (y parecidos: Negro Aventura, Ivory, Azul marino - Beige).
- **MO atómica**: cada orden/lote entra completa en **una sola línea**.
- **Proyección acumulada**: en `Proyeccion` y `Proyeccion - SKUS`, Sem 1…5 muestran el acumulado hasta esa semana.
- **Bugs**: prioridad `Urgente ` (espacio) ya no cae a “Sin Asignar”; `"2, 4"` ya no se guarda como `2.4`; el cruce de almacén usa `datosM[i]`; `doGet` y **Guardar Producción (Corte Diario)** restaurados.

## Cómo usar Cantidad Mínima

En `Priorizacion`, columna **Cantidad Minima**, escribe por modelo el piso de almacén (ej. `400` en RIO DAMA). Deja vacío o `0` si no aplica.

Al correr **3️⃣ Generar Planificación**, el aviso indica el orden de carga, los cupos leídos y cuántas piezas cayeron en la banda mínima.
