# Planificación de Producción v5.8 — códigos listos para pegar

## Cómo instalar (borrar y pegar)

En el editor de **Google Apps Script** del archivo de Planificación:

1. Abre `Codigo.gs`, selecciona **todo**, bórralo y pega el contenido completo de `planificacion-produccion/Codigo.gs`.
2. Abre (o crea) el archivo HTML llamado **`Dashboard`** (sin `.html`). Selecciona **todo**, bórralo y pega el contenido completo de `planificacion-produccion/Dashboard.html`.
3. Guarda el proyecto. Recarga la hoja. Corre **2️⃣ Actualizar Priorización** si hace falta crear/verificar `Priorizacion - SKUs`, y luego **3️⃣ Generar Planificación**.

## Priorizacion - SKUs

Hoja: `Priorizacion - SKUs`. Columnas (fila 2): SKU, Producto, Genero, Color, Talla, Cantidad Minima, Fecha de Salida Estimada, Lineas.

- SKU, Producto, Genero, Color, Talla, Cantidad Minima y Fecha se llenan **a mano**.
- **Lineas** es fórmula (VLOOKUP a `Por Hacer`); no la borres.

Esos SKUs entran en la banda de cantidad mínima **justo después de Especial**. Si el modelo también tiene cupo en `Priorizacion!Cantidad Minima`, primero se cubren los SKUs listados y el resto del piso del modelo se llena con colores núcleo.

## Proyección

`Proyeccion` y `Proyeccion - SKUS`: encabezado azul con letras blancas, filas con borde negro exterior y líneas internas suaves, sin texto encima de la tabla. Amarillo suave al llegar a la mínima; verde suave al llegar a la meta. El acumulado no se repite después de la meta.
