# Planificación de Producción v5.9.22 — códigos listos para pegar

## Cómo instalar (borrar y pegar)

En el editor de **Google Apps Script** del archivo de Planificación:

1. Abre `Codigo.gs`, selecciona **todo**, bórralo y pega el contenido completo de `planificacion-produccion/Codigo.gs`.
2. Abre (o crea) el archivo HTML llamado **`Dashboard`** (sin `.html`). Selecciona **todo**, bórralo y pega el contenido completo de `planificacion-produccion/Dashboard.html`.
3. Guarda el proyecto. Recarga la hoja. Corre **2️⃣ Actualizar Priorización** si hace falta crear/verificar `Priorizacion - SKUs`, y luego **3️⃣ Generar Planificación**.

Esta versión parte del motor bueno **5.9.15**. En 5.9.22, si un modelo de **mayor prioridad** (Urgente, mínima, Especial) tiene **Día de inicio** más adelante, el otro corre normal en la línea y, al llegar esa fecha, cede el puesto. L5 no echa a nadie. No rellena líneas vacías desde `BS`.

## Priorizacion — columna H (Secuencia)

Encabezado en H2: `Secuencia`.

- Escribe **No** (también vale `NO` / `no`) en el modelo que **no** debe seguir el orden de género CAB → DAMA → KIDS.
- Ese modelo **sí** respeta el lote de color: Negro → Blanco → Marino → resto.
- No reclama la segunda línea ni parte una MO. Urgente con 2+ líneas sigue la regla de 5.9.15 (una línea por género de la familia).
- Vacío u otro valor: secuencia normal de 5.9.15.
- **Actualizar Priorización** conserva la columna H.

Ejemplo: `RIO KIDS` con `H=No` y líneas `3 / 4` no espera a RIO CAB/DAMA del mismo color; si en la familia aún hay Negro, no arranca Blanco.

## Priorizacion - SKUs

Hoja: `Priorizacion - SKUs`. Columnas (fila 2): SKU, Producto, Genero, Color, Talla, Cantidad Minima, Fecha de Salida Estimada, Lineas.

- SKU, Producto, Genero, Color, Talla, Cantidad Minima y Fecha se llenan **a mano**.
- **Lineas** es fórmula (VLOOKUP a `Por Hacer`); no la borres.

Esos SKUs **no adelantan el modelo** en la cola. Cuando al modelo le toca entrar a la línea, salen primero (todo su faltante). Después sigue la distribución habitual (colores núcleo y el resto). Se refleja en `Proyeccion - SKUS` y `Entrada de Almacen - Skus`.

## Motor v5.9.22 (base 5.9.15 + Secuencia=No)

- **Día de inicio reclama L1-4:** si MAR KIDS (Urgente) y RIO CAB (Media) comparten línea, RIO corre hasta el Día de inicio de MAR; ese día MAR entra y RIO cede. Vale para Especial, mínima, Urgente o mejor fecha/prioridad. **L5** no echa a nadie (sigue en paralelo).
- **Especial con Día de inicio:** al llegar esa fecha, el modelo de `Por Hacer - Especial` toma su `Linea de Produccion` aunque otro (RIO, etc.) la esté usando. Antes se quedaba en 0 hasta que el ocupante terminara.
- **Especial sin desborde a L1:** cada fila de `Por Hacer - Especial` se queda en su `Linea de Produccion`. Si L1 está libre, no se redirigen ahí modelos de L2–L5. Celda vacía sigue siendo 1.
- **Secuencia=No:** desactiva solo el orden de género. El lote de color, la MO atómica y “un modelo a la vez en L1-4” no cambian.
- **Lotes por color y género:** si el mismo producto (ej. RIO CAB y RIO DAMA) está asignado a **2 líneas y esas líneas están libres**, los géneros trabajan **en paralelo** (uno por línea). Si solo queda **una** línea libre, secuencian ahí **por color** (Negro → Blanco → Marino → resto) y **dentro de cada color por género** (CAB → DAMA → KIDS). El sobrante del día pasa al siguiente lote de la familia. Los Especiales no usan esta regla.
- **Horizonte 10 semanas:** `Proyeccion` y `Proyeccion - SKUS` proyectan 10 semanas (la actual + 9), con los mismos formatos, acumulados y umbrales. Las pestañas `Semana 6` a `Semana 10` reciben tablero, resumen ejecutivo y alerta de pendientes igual que `Planificacion` / `Semana 2`–`Semana 5`. El menú **Ver Pestañas** las incluye.
- **Fix de sintaxis:** Apps Script ya no falla con `Unexpected token '}'`. Se restauró `familiaOcupaLinea_` (un recorte de v5.9.7 dejaba un `}` suelto).
- **Capacidad diaria por producto:** no se usa un techo fijo 130/40. Al planificar se lee `Cap Produccion por Dia` (Por Hacer col. N, Por Hacer - Especial col. O) y esa cifra es el cupo del día mientras el modelo ocupa la línea. Si cambia de modelo a media jornada, el sobrante se calcula con la cap del que entra. Si la celda viene vacía, respaldo L1-4=130 / L5=40.
- **Almacén:** `Fecha Entrada de Almacen` = **4 días hábiles** después de salir de costura.
- **Sincronizar Producción:** `Cantida Producida` en Por Hacer es la **base**. Cada fila **nueva** de `Produccion - Costura` (huella MO+SKU+cantidad+fecha+línea) se suma a esa MO. La hoja oculta `Sync Costura Aplicada` guarda esas huellas con el sello de texto `SYNC-V13` (ya no `5.9.12`, que Google convertía en fecha y dejaba de detectar filas nuevas).
- **Tableros por flujo:** el remanente (lote chico que cierra el día) va primero; el modelo que sigue el resto de la semana va después.
- **Actualizar MOs:** las MO en **Hecho** de `Por Hacer - Especial` **no** se archivan ni se borran, y **no entran al backlog** ni a la planificación. Cancelada sí se archiva. Producción regular sigue igual.
- **Línea 1 y cambio de modelo:** si el ocupante termina a media jornada, el sobrante pasa al siguiente que **sí lista L1** (igual que L2-4). Un especial de otra línea **no** se redirige a L1. Dos modelos en L1 el mismo día van **en secuencia**, no en paralelo.
- **Cantidad mínima** (columna en `Priorizacion`): máxima prioridad **después de Especial**. El cupo es la cantidad pedida (ej. 100) tomada del **faltante**; lo ya producido **no recorta** ese cupo (no convierte 100 en 67). Solo si el piso ya está cubierto (producido ≥ mínima) el modelo no entra a esa banda. El cupo sale antes que Urgente / Alta / fecha. Cuando se cubre, el modelo **cede la línea** (el sobrante del día pasa al siguiente) y el resto de su pedido vuelve a la cola normal.
- **Urgente** después de Especial y de la cantidad mínima, luego la fecha de salida más próxima. Un modelo Urgente con dos líneas (ej. `2, 4`) usa las dos.
- **Líneas 1-4:** un modelo a la vez (**no en paralelo**). Si el modelo termina o no puede seguir, el **sobrante del mismo día** pasa al siguiente de la cola.
- **Línea 5** es la única que puede trabajar **dos familias** en paralelo. Si va un modelo solo, usa su cap del día (típico 40). Si hay dos familias, se turnan en lotes de 5. El mismo producto en distinto género **no** corre en paralelo: va en secuencia por color y género.
- **Especial:** se respeta `Linea de Produccion`. Si la celda viene vacía, se usa 1 (dato faltante, no desborde). Si L1 queda libre, **no** se redirigen ahí modelos/cantidades de otras líneas. Al llegar **Día de inicio**, el Especial (y cualquier modelo de mejor prioridad en L1-4) desaloja al ocupante peor y entra ese día. `Fecha de Salida Estimada` en `Por Hacer - Especial` ordena esos modelos.
- **Priorización:** al actualizar, se eliminan modelos con faltante total 0.

## Proyección

`Proyeccion` y `Proyeccion - SKUS` se dibujan desde **B2** (fila 1 vacía; encabezado en la fila 2; datos desde la fila 3). Encabezado navy `#20124D` con letras blancas. Filas con borde negro exterior y líneas internas suaves. Hay **10 columnas de acumulado semanal** (`Acum Sem 1` … `Acum Sem 10`).

Resaltado de acumulados (solo la **primera** semana que cruza cada umbral):

- Amarillo `#FFE599` al llegar a la cantidad mínima.
- Verde `#D9EAD3` (texto `#38761D` en negrita) al llegar a la meta.
- Valores intermedios se quedan en blanco. Después de la meta el resto de semanas es `--`.

En `Proyeccion`, cada nombre de modelo es un enlace a la primera fila de ese modelo en `Proyeccion - SKUS`.

## Tableros Semana 6 a Semana 10

Las pestañas `Semana 6` … `Semana 10` deben existir con el mismo formato (encabezados desde **B3**: Linea, Modelo, MOs, Solicitada, Lunes, Martes, Miercoles, Jueves, Viernes, Total Semana (SKU), Total Semana (Linea)). Al generar la planificación se escriben tablero, resumen ejecutivo y alerta de pendientes. Si una pestaña no está, se omite sin error.
