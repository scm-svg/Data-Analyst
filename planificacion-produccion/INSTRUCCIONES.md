# Planificación de Producción v5.5 — códigos listos para pegar

## Cómo instalar (borrar y pegar)

En el editor de **Google Apps Script** del archivo de Planificación:

1. Abre `Codigo.gs`, selecciona **todo**, bórralo y pega el contenido completo de `planificacion-produccion/Codigo.gs`.
2. Abre (o crea) el archivo HTML llamado **`Dashboard`** (sin `.html`). Selecciona **todo**, bórralo y pega el contenido completo de `planificacion-produccion/Dashboard.html`.
3. Guarda el proyecto. Recarga la hoja de cálculo para ver los menús `⚙️ Producción`, `👁️ Ver Pestañas` y `⚙️ Tracking`.
4. Si usas la Web App del dashboard: **Implementar → Implementación nueva → Aplicación web** (o vuelve a implementar la existente).

No hace falta cambiar la estructura de pestañas. La columna **Cantidad Minima** de `Priorizacion` (columna F) ya es la fuente del cupo de almacén.

## Qué hace esta versión

- **Cantidad mínima reactivada**: si un modelo tiene cupo en `Priorizacion!Cantidad Minima`, primero se programa ese cupo (Fase 1) y después el resto (Fase 2).
- **Colores core primero**: Negro, Blanco y Azul Marino (y parecidos: Negro Aventura, Ivory, Azul marino - Beige) salen antes que el resto de variantes, tanto en el cupo mínimo como en la distribución general.
- **MO atómica**: cada orden/lote entra completa en **una sola línea**. Si el SKU admite `2 / 4`, el motor elige la línea que puede terminar antes y no parte el lote.
- **Proyección acumulada**: en `Proyeccion` y `Proyeccion - SKUS`, Sem 1…5 muestran el acumulado a producir hasta esa semana (901, 1605, 1605…), no el flujo semanal suelto.
- **Bugs**: prioridad `Urgente ` (espacio) ya no cae a “Sin Asignar”; `"2, 4"` ya no se guarda como `2.4`; el cruce de almacén usa `datosM[i]` (antes `datos[i]` reventaba el sync); `doGet` y **Guardar Producción (Corte Diario)** restaurados.

## Cómo usar Cantidad Mínima

En `Priorizacion`, columna **Cantidad Minima**, escribe por modelo el piso de almacén (ej. `200`). Deja vacío o `0` si no aplica.

Al correr **3️⃣ Generar Planificación**, el resumen indica cuántos modelos tenían cupo y cuántas piezas cayeron en Fase 1 vs Fase 2.

## Mejoras que se pueden aplicar después (no incluidas)

1. Semáforo de stock en `Por Hacer` según proyección de ventas vs mínimo.
2. Etapa de **corte** separada de costura (solo programar MOs ya cortadas).
3. Calendario de feriados más allá de “día no laborable” por fila.
4. Traer cantidades mínimas desde Odoo / ERP en lugar de cargarlas a mano.
5. Alerta si el cupo mínimo de un modelo no cabe en la Semana 1.
6. Simulador del dashboard con la misma regla de MO atómica + colores core que el motor real (hoy el simulador ya no parte un SKU entre líneas, pero no replica el cupo mínimo).

Si quieres implementar alguna de estas, dímelo y la metemos en una siguiente versión.
