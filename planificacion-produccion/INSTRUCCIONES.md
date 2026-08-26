# Planificación de Producción v5.7 — códigos listos para pegar

## Cómo instalar (borrar y pegar)

En el editor de **Google Apps Script** del archivo de Planificación:

1. Abre `Codigo.gs`, selecciona **todo**, bórralo y pega el contenido completo de `planificacion-produccion/Codigo.gs`.
2. Abre (o crea) el archivo HTML llamado **`Dashboard`** (sin `.html`). Selecciona **todo**, bórralo y pega el contenido completo de `planificacion-produccion/Dashboard.html`.
3. Guarda el proyecto. Recarga la hoja de cálculo para ver los menús `⚙️ Producción`, `👁️ Ver Pestañas` y `⚙️ Tracking`.
4. Si usas la Web App del dashboard: **Implementar → Implementación nueva → Aplicación web** (o vuelve a implementar la existente).

## Orden de carga

1. **Especial** — `Por Hacer - Especial`.
2. **Cantidad mínima** — cupo de `Priorizacion!Cantidad Minima`, con máxima urgencia **después** de Especial, pero **sin adelantar** el **Día de inicio** de `Por Hacer` (columna R).
3. **Resto del paneo** — fecha de salida + prioridad, colores núcleo primero.

## Proyección

En `Proyeccion` y `Proyeccion - SKUS` cada semana muestra el **acumulado**. Cuando el modelo/SKU llega a su meta (o deja de producir), **no se vuelve a escribir el mismo número** en las semanas siguientes: esas celdas quedan en `--`.

## Tableros semanales

`Planificacion` y `Semana 2`–`Semana 5` listan por línea y, dentro de cada línea, por el primer día de esa semana con unidades.
