# Planificación de Producción v5.9.51 — códigos listos para pegar

## Cómo instalar (borrar y pegar)

En el editor de **Google Apps Script** del archivo de Planificación:

1. Abre `Codigo.gs`, selecciona **todo**, bórralo y pega el contenido completo de `planificacion-produccion/Codigo.gs`.
2. Abre (o crea) el archivo HTML llamado **`Dashboard`** (sin `.html`). Selecciona **todo**, bórralo y pega el contenido completo de `planificacion-produccion/Dashboard.html`. **Sustituye** el dashboard HTML anterior: este archivo ya no lleva datos embebidos.
3. Guarda el proyecto. Recarga la hoja. Corre **2️⃣ Actualizar Priorización** si hace falta crear/verificar `Priorizacion - SKUs`, y luego **3️⃣ Generar Planificación**.
4. Corre **🔄 Actualizar Dashboard**. Eso publica el snapshot que ve todo el mundo.
5. Publica la app web **una sola vez** (o actualiza la implementación existente para no cambiar el enlace): **Implementar → Implementaciones → Aplicación web**. Ejecutar como *tú*. Acceso: *cualquier persona con el enlace* (o tu dominio). El `doGet` sirve el mismo `Dashboard`.

El botón **Actualizar Dashboard** no regenera el plan: solo lee las pestañas ya calculadas (`Planificacion`, `Semana 2–12`, `Proyeccion`, almacén, pendientes) y las deja en la hoja oculta `_DashboardCache`. El enlace de la app web no cambia.

Los checks de **Impresión Digital** se graban con el botón **Guardar** de esa pestaña, en la hoja oculta `_ImpresionChecks`. La clave es `M|MO|SKU` (la semana no entra). Si al regenerar el plan la orden cambia de semana o de fila, el logo listo sigue. Las claves antiguas `semana|SKU|MO` se siguen leyendo y se reescriben al guardar. **Actualizar Dashboard** no borra esa hoja. Marcar un check no lo envía solo: hay que pulsar Guardar. Si hay cambios sin guardar y alguien sale del dashboard, el navegador avisa.

Esta versión incluye **apoyo L1 que no pisa prendas propias** (**5.9.51**), **columna Lote en Por Hacer** (**5.9.50**), **Calendario Detalle diario con tooltip que se puede bajar** (**5.9.49**), **Impresión Digital con faltante 0** (**5.9.48**), **Impresión Digital sin filtro Prioridad** (**5.9.47**), **Impresión Digital lista fija** en el dashboard en línea (**5.9.46**), **color sin saltos en Proyeccion - SKUS** (**5.9.45**), **Secuencia=No sin lote familiar** (**5.9.44**), **asignar MO sin que Actualizar MOs la borre** (**5.9.43**), **uno o dos modelos a media estación**, cada uno con la cola cuando le toca (**5.9.42**), la selección de dos nombres en el prompt (**5.9.41**), el paralelo automático (**5.9.40**), **lotes / Division / secuencia de color** (**5.9.39**), el **orden de salida de SKUs** en todo drill-down (**5.9.38**), **Produccion Parcial** y KPIs del encabezado (**5.9.37**), **Ya producida** en almacén (**5.9.36**), el almacén del dashboard (**5.9.35**), el registro de logos por orden (**5.9.34**), el motor **5.9.33** (Especial con 2+ líneas produce en todas las asignadas), **5.9.32** (RIO DAMA no suelta L2 a un hermano que aún no llega a su Día de inicio), **5.9.31** (urgente que explota líneas en fecha estimada), **Secuencia=No en Línea 5**, horizonte de **12 semanas** y el dashboard web compartido.

## Motor · Apoyo L1 no pisa prendas propias (5.9.51)

El 50% de la Línea 1 para el modelo de L2 **ya no se reserva a ciegas**.

- Si L1 tiene piezas planificadas (un modelo asignado a esa línea con faltante), **trabaja al 100%** esas prendas. No comparte el día con L2.
- El apoyo al 50% **solo entra cuando hay espacio**: L1 terminó lo suyo ese día, o ese día no tiene nada propio.
- Si L1 está libre, el modelo de L2 sigue produciendo a media cap en L1 (igual que antes).
- Si el modelo de L2 ya lista y ocupa L1, no se duplica el apoyo.

Al generar el plan, el aviso de “Apoyo Línea 1 al 50%” lo dice así.

## Motor · Columna Lote y nombre de modelo (5.9.50)

En `Por Hacer` el número de lote ya no vive dentro de **Producto**. Va en la columna **Lote** (columna J). El motor arma el **Modelo** así:

- `Producto + Género + "Lote N"` → `MAR KIDS Lote 1`, `MAR DAMA Lote M`
- Si Lote es **0**, `0.0`, vacío o no aplica: **no** se escribe la palabra `Lote` ni el número → `BASIC LINE CROP TEE DAMA`, `MAR CAB`

Ese string se usa en **MO** (columna Modelo), **Priorizacion**, **Planificacion**, **Semana 2–12**, **Proyeccion**, **Entrada de Almacen Modelo** y en todas las tablas/drill-down del dashboard que muestran modelos.

- `Proyeccion - SKUS` y `Entrada de Almacen - Skus` ganan una columna **Lote** (entre Modelo/Producto y el detalle o la cantidad).
- **Historial MO** inserta **Lote** (después de Talla) solo en **registros nuevos**.
- Si Producto todavía trae el texto viejo (`MAR LOTE 1`), se limpia para no duplicar: queda `MAR KIDS Lote 1`, no `MAR LOTE 1 KIDS Lote 1`.
- En el dashboard, las tablas de **variantes / SKU** no duplican columna Lote: el lote ya va en el nombre del modelo.

Tras pegar, corre **1️⃣ Actualizar MOs**, **2️⃣ Actualizar Priorización** y **3️⃣ Generar Planificación**. Las filas viejas de Priorizacion tipo `MAR LOTE 1 KIDS` se reescriben a `MAR KIDS Lote 1`.

## Calendario · recuadro de variantes (5.9.49)

En **📅 Calendario → Detalle diario**, al pasar el cursor sobre un modelo se abre el recuadro de variantes (SKU, color, talla, cantidad de la semana).

- Puedes **entrar al recuadro y bajar** la lista: ya no se cierra al salir un milímetro del modelo.
- **Clic en el modelo** fija el recuadro (útil en listas largas o en táctil).
- **Esc**, clic otra vez en el mismo modelo, o clic fuera lo cierra.
- El orden de variantes sigue siendo por **salida de producción** (prioridad SKU → Negro → Blanco → Marino → resto por volumen → talla).

Tras pegar `Dashboard.html`, corre **🔄 Actualizar Dashboard** (el URL de la app web no cambia).

## Impresión Digital · faltante 0 y cantidades (5.9.48)

En **🖨 Impresión Digital**, una orden con **Faltante 0** (ya no entra al plan de costura) **sigue en el listado** mientras esté en `Por Hacer` / `Por Hacer - Especial`.

- El drill-down modelo → SKU muestra **Solicitada**, **Producida** y **Faltante**.
- El CSV de esa pestaña exporta las mismas tres columnas.
- Solo desaparece si la MO está **Hecho**, **Cerrada** o **Cancelada** (y por eso ya no está en el archivo principal).

## Impresión Digital · lista fija (5.9.47)

La pestaña **🖨 Impresión Digital** del dashboard web **ya no sigue el plan semanal de costura**. El taller puede mover semanas o fechas de almacén y el listado de logos no se reordena.

- Drill-down **modelo → SKU**.
- Orden de modelos: **Especial → Urgente → Alta → Media → Baja → Sin Asignar**, luego fecha de salida, luego volumen.
- Dos bloques: **Líneas 1–4** y **Línea 5** (si el modelo lista la 5, va a L5).
- Órdenes **PD** con etiqueta. Esperan crearse en Odoo; el check del logo se guarda igual.
- Tabla de modelos: **Modelo, MOs, Faltante, Logo**. En el desglose SKU: **Solicitada, Producida, Faltante**. En la pestaña solo queda el filtro **PD**. El CSV sí exporta la prioridad y las tres cantidades.
- Variantes: Priorizacion - SKUs, **Negro → Blanco → Marino**, resto por volumen, talla. El día de arranque **no parte** un color.
- Checks: botón **Guardar**, clave `M|MO|SKU` (sin semana). El filtro de **semana** del encabezado no vacía esta pestaña. Calendario, Salida semanal, Seguimiento y Almacén siguen siendo semanales.
- Tras pegar `Codigo.gs` + `Dashboard.html`, corre **🔄 Actualizar Dashboard** (no hace falta redesplegar el URL).

## Listado por color, sin saltos (5.9.45)

En `Proyeccion - SKUS`, Entrada de almacén y los drill-downs del dashboard, las variantes de un modelo **no se intercalan por el día en que cada SKU arrancó**.

- Primero los SKUs de **Priorizacion - SKUs**.
- Luego **Negro → Blanco → Azul Marino**.
- El resto de colores **por volumen** del color en el modelo (el de más piezas primero).
- Dentro del color, por **talla** (XS→XL o 2→14).

Así, con **Division=Si** (1ª vuelta de todas las variantes al 50% y luego la 2ª), Lila 14 ya no aparece entre Azul Rey 4 y Azul Rey 6. El motor también filtra el lote del día por **color exacto** (no por el rango 50 de “otros”), para no mezclar Lila / Azul Rey / Aguamarina en la misma pasada.

## Motor · Secuencia=No sin lote familiar (5.9.44)

En Priorizacion columna H, **No** saca al modelo del lote familiar (color → género) en **todas** las líneas, no solo en L5.

- **RIO KIDS** con `H=No` no espera ni cede L2 a **RIO DAMA** a mitad de semana (tampoco si KIDS tiene `Division=Si` y acaba la 1ª vuelta de Negro).
- El modelo corre **solo** en su línea hasta terminar. El sobrante del día pasa a la **cola de prioridad**, no al hermano.
- El orden Negro → Blanco → Marino de **sus propias** variantes se mantiene.
- En **Línea 5** sigue siendo ocupante exclusivo (sin rueda en paralelo).
- No reclama líneas extra ni parte MOs. Vacío u otro valor deja la secuencia normal de familia.

## Actualizar MOs · asignar número a un SKU (5.9.43)

Al escribir una MO en la hoja `MO` (o en `Por Hacer`) y pulsar **Actualizar MOs**, el cruce ya no exige que los dos lados tengan el mismo número. El mismo lote se reconoce por **SKU + tipo + modelo**. Se conserva la MO recién puesta y se copia a la otra lista. Si el SKU tiene dos lotes (`MAR LOTE 1` y `MAR LOTE 2`), cada uno sigue con su MO. Una fila que ya no está en Por Hacer sí se elimina como huérfana.

## Motor · Modelo a media estación en L1-4 (5.9.42)

Al pulsar **Generar Planificación**, después del apoyo de L1, el script pregunta:

1. **¿Hay un modelo planificado que no use el 100% de las estaciones en L1-4?** Sí / No.
2. Si Sí: escribe **uno o dos modelos** (número o nombre), **separados por coma**. Ejemplos: `1, 3` o `RIO DAMA, VITA BIKER DAMA`. Vale el nombre de Priorizacion (`MAR KIDS`) aunque en Por Hacer sea `MAR LOTE 1 KIDS`.
3. Si escribiste **solo uno**, un segundo prompt pregunta si hay **otro** que tampoco use el 100%. Vacío = solo ese.
4. **¿Qué % de las estaciones usa cada marcado cuando le toca?** Vacío = 50. El resto queda para el siguiente de la cola.

Efecto:

- Solo aplica a **líneas 1 a 4**. La Línea 5 no cambia (sigue con su rueda de 2 familias).
- Elegir **dos** no los obliga a coincidir en la misma línea ni el mismo día.
- Cuando le toca producir a **cada** modelo marcado, en su línea y su momento, entra el **siguiente de la cola** (otra familia) en paralelo.
- El compañero **no es de la misma familia** (RIO CAB + RIO DAMA siguen en secuencia de color/género; el compañero es p. ej. VITA).
- Se reparte la capacidad del día: el marcado usa el % indicado (50% → 65 pzas si su cap es 130) y el de la cola el resto.
- Si no hay compañero disponible, el modelo marcado usa **toda** su cap del día (no se deja la línea a medias).
- Sin marcar ningún modelo, L1-4 siguen **un modelo a la vez** (si termina, el sobrante del día pasa al siguiente).

## Motor · Lotes, Division y secuencia (5.9.39)

- **Mismo SKU, distinto lote:** ya no se bloquea repetir un SKU en `Por Hacer` / `Por Hacer - Especial`. La identidad es **MO + modelo**. Desde **5.9.50** el número va en la columna **Lote** y el modelo queda `MAR KIDS Lote 1` (lote 0 se omite). Cada lote tiene su propia prioridad, fecha, líneas y secuencia. Solo se revierte la celda si coinciden SKU + MO + modelo.
- **Actualizar MOs** ya no pisa un lote con la MO de otro: la hoja `MO` guarda también **Modelo** y cruza por MO o por lote. Asignar el número en un solo lado (hoja `MO` o Por Hacer) ya no borra la fila ni vacía la MO.
- **Actualizar Priorización** reescribe el modelo canónico (`MAR KIDS Lote 1`). Lote 0 se muestra solo como producto + género (`MAR CAB`).
- **Division (columna I):** escribe **Si** (vale `SI` / `Sí`) para partir las variantes a la **mitad** y producirlas en **vueltas**: primero todas las variantes al 50% (el impar va a la 1ª), en el orden de color/talla; después la otra mitad en el mismo orden. Vacío u otro valor = flujo normal. No aplica a Especial ni a la banda de cantidad mínima.
- **Secuencia de color:** Negro → Blanco → Azul Marino, y el resto **por volumen del color en el modelo**. Ese orden es el del plan, `Proyeccion - SKUS` y Entrada de almacén.
- **Géneros en una línea:** si RIO CAB y RIO DAMA (o MAR) comparten una línea, se sigue el color y se **alternan géneros** dentro de ese color (CAB → DAMA → KIDS). Si hay dos líneas libres, cada género toma una. Una MO regular **no se parte** entre líneas.
- **Especial** sigue siendo la excepción: con 2+ líneas asignadas puede usarlas todas.

## Dashboard · Drill-down SKU por salida (5.9.38)

Al abrir un modelo, las variantes se listan **como van a salir de costura**, no por MO ni alfabético. Vale para:

- **Calendario → Detalle diario** (recuadro de variantes: se entra, se baja y se puede fijar)
- **Salida semanal** (semana → modelo → SKU)
- **Seguimiento** (clic en el modelo)
- **Almacén** (tabla Entrada de almacén y calendario de ingresos)

**Impresión Digital** (desde **5.9.46**) no usa este listado semanal: es una **lista fija** por prioridad, partida en L1–4 vs L5. Las variantes de cada modelo sí siguen el orden de color/talla de arriba.

Criterio, el mismo del motor:

1. SKUs de **Priorizacion - SKUs** (salen primero cuando el modelo entra a la línea).
2. Color núcleo: **Negro → Blanco → Marino**; el resto por **volumen del color** en el modelo.
3. Talla (XS → S → M → L → XL, o número).
4. Empate: semana/día de arranque, más cantidad, luego el código SKU.

El día en que cada variante arrancó **no parte** un color (un Lila 14 no se lista entre tallas de Azul Rey).

## Dashboard · Almacén y encabezado (5.9.37)

Después de pegar los dos archivos, corre **🔄 Actualizar Dashboard**. El enlace de la app web no cambia.

- **Estado del SKU:** `Ya producida` si `Cantida Producida > 0` y Faltante = 0. `Produccion Parcial` (badge amarillo) si hay piezas hechas y aún falta. En blanco si no hay producción.
- **Estado del modelo:** `Ya producida` solo si **todos** los SKUs del desglose (Por Hacer) están completos. Si el modelo no está desglosado del todo, o mezcla SKUs listos con pendientes, el modelo queda en `Produccion Parcial`. No se marca listo cuando aún falta variante.
- **Plan 12 sem:** piezas planificadas dentro del horizonte (suma del plan semanal).
- **Pendiente:** lo que quedó fuera de esas 12 semanas (`A producir − Plan`).
- **A producir:** Faltante de `Por Hacer` y `Por Hacer - Especial`.
- **Planificado vs producido:** Planificado = `Cantidad Solicitada`, Producido = `Cantida Producida` del archivo.

## Dashboard · Almacén (5.9.36)

- **Cantidad producida** en Entrada de almacén es `Cantida Producida` de `Por Hacer` y `Por Hacer - Especial`: piezas que ya salieron de costura y están en remate o validación.
- Si la MO **no está en el plan** porque el Faltante ya es 0 (ya se produjo todo), **igual entra** a la tabla y a los gráficos. Completa = **Ya producida**; parcial = **Produccion Parcial**.
- La orden y el SKU **salen de la tabla** cuando el MO STATUS es Hecho, Cerrada o Cancelada, o cuando esa orden ya no está en esas pestañas.
- Arriba de la tabla: torta **producido vs por producir**, y barras **quincenales** de lo esperado por recibir frente a lo ya producido. La quincena usa la fecha esperada de entrada a almacén.
- Los chips de semana filtran los modelos que ingresarían esa semana (lunes de la fecha de entrada).
- El calendario de ingresos lista piezas por modelo y semana de entrada. Clic en el modelo abre los SKUs.
- En **Calendario → Detalle diario**, el recuadro de variantes se puede **entrar y bajar**. Clic en el modelo lo fija; Esc o clic fuera lo cierra.

## Priorizacion — columna I (Division)

Encabezado en I2: `Division`.

- Escribe **Si** en el modelo que debe salir en dos vueltas al 50% (todas las variantes primero a la mitad, luego el resto en el mismo orden).
- Vacío, `No` u otro valor: producción continua, sin partir.
- **Actualizar Priorización** conserva la columna I.
- El cruce ignora el texto `LOTE n` del producto: `MAR KIDS` + `Si` aplica a `MAR LOTE 1 KIDS`.

Ejemplo: `MAR KIDS` con `I=Si` y 80 Negro + 80 Rojo → 40 Negro, 40 Rojo, 40 Negro, 40 Rojo.

## Priorizacion — columna H (Secuencia)

Encabezado en H2: `Secuencia`.

- Escribe **No** (también vale `NO` / `no`) en el modelo que **no** debe compartir secuencia con la familia (CAB → DAMA → KIDS ni el lote de color entre hermanos).
- En **todas las líneas** ese modelo corre solo: no espera ni cede a un hermano. El Negro → Blanco → Marino de **sus** variantes se mantiene.
- En **Línea 5**, `No` además significa que el modelo **no trabaja en paralelo**: es el único que corre en L5.
- No reclama la segunda línea ni parte una MO. Urgente con 2+ líneas sigue la regla de 5.9.15 (una línea por género de la familia).
- Vacío u otro valor: secuencia normal de 5.9.15.
- **Actualizar Priorización** conserva la columna H.

Ejemplo L1–4: `RIO KIDS` con `H=No` en Línea 2 no cede a `RIO DAMA` a mitad de lote; el sobrante del día va a la cola, no al hermano.
Ejemplo L5: `SHORT SPORT R1 CAB` con `H=No` usa toda la Línea 5; no comparte rueda con otro modelo.

## Priorizacion - SKUs

Hoja: `Priorizacion - SKUs`. Columnas (fila 2): SKU, Producto, Genero, Color, Talla, Cantidad Minima, Fecha de Salida Estimada, Lineas.

- SKU, Producto, Genero, Color, Talla, Cantidad Minima y Fecha se llenan **a mano**.
- **Lineas** es fórmula (VLOOKUP a `Por Hacer`); no la borres.

Esos SKUs **no adelantan el modelo** en la cola. Cuando al modelo le toca entrar a la línea, salen primero (todo su faltante). Después sigue la distribución habitual (colores núcleo y el resto). Se refleja en `Proyeccion - SKUS` y `Entrada de Almacen - Skus`.

## Motor v5.9.33 (base 5.9.32 + Especial en todas las líneas asignadas)

- **Especial en todas las asignadas:** un modelo de `Por Hacer - Especial` con 2+ líneas (Running Tank Biomove en `1, 2`; Clásica Cab/DAMA en `3, 4`) es **prioridad 1** en cada línea listada. Al llegar su **Día de inicio** toma **sí o sí** todas esas líneas (desaloja a RIO u otro de peor banda). Ya no se queda en una sola porque “alcanza la semana”. El faltante se reparte entre las asignadas (la MO no se clava a una). Dos Especiales que comparten líneas: el de más volumen (o mejor fecha) usa ambas hasta terminar; el otro entra después. **No** desborda a una línea que no esté en `Linea de Produccion`.
- **Encabezado Producto:** si en `Por Hacer` la celda de Producto/Modelo de la fila 2 viene vacía, se usa la columna siguiente a SKU o el título de la fila 1. Generar Planificación ya no se bloquea por eso.
- **RIO DAMA no suelta L2:** el lote de familia (Negro → Blanco → Marino, CAB → DAMA → KIDS) **ignora** hermanos que todavía no llegan a su Día de inicio. Si RIO KIDS está en la misma línea pero arranca el 29/09, RIO DAMA sigue en Línea 2 en la semana 2. Al llegar ese día, la secuencia de color/género vuelve a aplicar. El apoyo 50% de L1 no deja a DAMA como ocupante fantasma de una L2 vacía.
- **Dashboard web compartido:** menú **Producción → Actualizar Dashboard** publica un snapshot. `doGet` / la app web leen `_DashboardCache` (no recorren las hojas en cada visita). **Impresión Digital** es una lista fija por prioridad (L1–4 vs L5) y guarda los checks con el botón **Guardar**, por MO+SKU, en `_ImpresionChecks`. Actualizar el dashboard no los borra ni reordena esa pestaña.
- **Urgente en fecha estimada:** un modelo Urgente/mínima con 2+ líneas toma **sí o sí** todas las asignadas el día de Fecha de Salida Estimada y el hábil anterior. Fuera de esa ventana, la segunda línea solo si está libre.
- **Secuencia=No en Línea 5:** en Priorizacion col. H, `No` hace que ese modelo sea el **único ocupante de L5**. No comparte la rueda en paralelo. Desde **5.9.44**, `No` también saca al modelo del lote familiar en L1–4 (no espera/cede color ni género a un hermano).
- **Horizonte 12 semanas:** `Proyeccion` y `Proyeccion - SKUS` proyectan 12 semanas (la actual + 11), con los mismos formatos, acumulados y umbrales. Las pestañas `Semana 11` y `Semana 12` reciben tablero, resumen ejecutivo y alerta de pendientes igual que `Planificacion` / `Semana 2`–`Semana 10`. El menú **Ver Pestañas** las incluye.
- **Dashboard de información:** menú **Producción → Dashboard de información** (modal en la hoja) y el mismo HTML en la app web. Pestañas: calendario, salida semanal, seguimiento, pendientes, almacén, supuestos e **Impresión Digital**. Lee el snapshot publicado.
- **Meta = columna Faltante:** `Proyeccion` y el backlog usan el número de **Faltante** en `Por Hacer`. No se recorta a `Cantidad Solicitada − Cantida Producida` (eso dejaba RIO CAB en 1834 en vez de 1871, y SHORT SPORT R1 CAB+DAMA en 195 en vez de 202). Si Faltante está vacío, sí se usa sol−prod. Si Faltante es 0, la MO no entra.
- **Conteo por semana (MOs y cantidades):** en `Planificacion` / `Semana 2`–`Semana 12` las columnas **MOs** y **Solicitada** son de esa semana (MOs con producción > 0). El resumen ejecutivo solo lista modelos que fabrican esa semana. Las pestañas `Linea 1`–`Linea 5` omiten MOs que solo salen en semanas futuras. `Proyeccion` / `Proyeccion - SKUS` omiten filas con faltante 0.
- **Apoyo L1 50% al modelo de L2:** al pulsar **Generar Planificación** el sistema pregunta si quieres disponer del 50% de la Línea 1. Si aceptas, pide la semana de inicio (1 = actual). Desde esa semana, el modelo que está corriendo en L2 también produce en L1 a la **mitad** de su `Cap Produccion por Dia` (p. ej. 65 si la cap es 130). El ocupante nativo de L1 se queda con el otro 50%. No hace falta que L2 liste la línea 1 en Por Hacer. La MO sigue anclada a L2; L1 es solo apoyo. Si ese modelo ya ocupa L1 (Urgente con 1 y 2), no se duplica.
- **Remanente corto en L2:** si al modelo de L2 le quedan **menos de 2 días** de producción, termina (el apoyo L1 acelera el cierre) y L2 pasa al **siguiente programado**. No se queda ocupando la línea por un lote chico.
- **Día de inicio reclama L1-4:** si MAR KIDS (Urgente) y RIO CAB (Media) comparten línea, RIO corre hasta el Día de inicio de MAR; ese día MAR entra y RIO cede. Vale para Especial, mínima, Urgente o mejor fecha/prioridad. **L5** no echa a nadie (sigue en paralelo).
- **Especial con Día de inicio:** al llegar esa fecha, el modelo de `Por Hacer - Especial` toma su `Linea de Produccion` aunque otro (RIO, etc.) la esté usando. Antes se quedaba en 0 hasta que el ocupante terminara.
- **Especial sin desborde a L1:** cada fila de `Por Hacer - Especial` se queda en su `Linea de Produccion`. Si L1 está libre, no se redirigen ahí modelos de L2–L5. Celda vacía sigue siendo 1.
- **Secuencia=No:** saca al modelo del lote familiar en L1–4 y L5. No espera ni cede color/género a un hermano; el Negro→Blanco de sus propias variantes se mantiene. En **Línea 5**, `No` = ese modelo corre **solo** (sin paralelo). La MO atómica y “un modelo a la vez en L1-4” no cambian.
- **Lotes por color y género:** si el mismo producto (ej. RIO CAB y RIO DAMA) está asignado a **2 líneas y esas líneas están libres**, los géneros trabajan **en paralelo** (uno por línea). Si solo queda **una** línea libre, secuencian ahí **por color** (Negro → Blanco → Marino → resto) y **dentro de cada color por género** (CAB → DAMA → KIDS). El sobrante del día pasa al siguiente lote de la familia. Los Especiales no usan esta regla.
- **Fix de sintaxis:** Apps Script ya no falla con `Unexpected token '}'`. Se restauró `familiaOcupaLinea_` (un recorte de v5.9.7 dejaba un `}` suelto).
- **Capacidad diaria por producto:** no se usa un techo fijo 130/40. Al planificar se lee `Cap Produccion por Dia` (Por Hacer col. N, Por Hacer - Especial col. O) y esa cifra es el cupo del día mientras el modelo ocupa la línea. Si cambia de modelo a media jornada, el sobrante se calcula con la cap del que entra. Si la celda viene vacía, respaldo L1-4=130 / L5=40.
- **Almacén:** `Fecha Entrada de Almacen` = **4 días hábiles** después de salir de costura.
- **Sincronizar Producción:** `Cantida Producida` en Por Hacer es la **base**. Cada fila **nueva** de `Produccion - Costura` (huella MO+SKU+cantidad+fecha+línea) se suma a esa MO. La hoja oculta `Sync Costura Aplicada` guarda esas huellas con el sello de texto `SYNC-V13` (ya no `5.9.12`, que Google convertía en fecha y dejaba de detectar filas nuevas).
- **Tableros por flujo:** el remanente (lote chico que cierra el día) va primero; el modelo que sigue el resto de la semana va después.
- **Actualizar MOs:** las MO en **Hecho** de `Por Hacer - Especial` **no** se archivan ni se borran, y **no entran al backlog** ni a la planificación. Cancelada sí se archiva. Producción regular sigue igual.
- **Línea 1 y cambio de modelo:** si el ocupante termina a media jornada, el sobrante pasa al siguiente que **sí lista L1** (igual que L2-4). Un especial de otra línea **no** se redirige a L1. Dos modelos en L1 el mismo día van **en secuencia**, no en paralelo.
- **Cantidad mínima** (columna en `Priorizacion`): máxima prioridad **después de Especial**. El cupo es la cantidad pedida (ej. 100) tomada del **faltante**; lo ya producido **no recorta** ese cupo (no convierte 100 en 67). Solo si el piso ya está cubierto (producido ≥ mínima) el modelo no entra a esa banda. El cupo sale antes que Urgente / Alta / fecha. Cuando se cubre, el modelo **cede la línea** (el sobrante del día pasa al siguiente) y el resto de su pedido vuelve a la cola normal.
- **Urgente** después de Especial y de la cantidad mínima, luego la fecha de salida más próxima. Un modelo Urgente con dos líneas (ej. `2, 4`) usa las dos.
- **Líneas 1-4:** un modelo a la vez (**no en paralelo**), salvo **uno o dos modelos a media estación** elegidos al generar. Si el modelo termina o no puede seguir, el **sobrante del mismo día** pasa al siguiente de la cola.
- **Línea 5** es la única que puede trabajar **dos familias** en paralelo. Si va un modelo solo, usa su cap del día (típico 40). Si hay dos familias, se turnan en lotes de 5. El mismo producto en distinto género **no** corre en paralelo: va en secuencia por color y género. Si el modelo tiene **Secuencia=No**, L5 no admite segundo ocupante.
- **Especial:** se respeta `Linea de Produccion`. Si hay **2 o más** líneas, el modelo las usa **todas** (prioridad 1) desde su Día de inicio. Si la celda viene vacía, se usa 1 (dato faltante, no desborde). Si L1 queda libre, **no** se redirigen ahí modelos/cantidades de otras líneas. Al llegar **Día de inicio**, el Especial (y cualquier modelo de mejor prioridad en L1-4) desaloja al ocupante peor y entra ese día. `Fecha de Salida Estimada` en `Por Hacer - Especial` ordena esos modelos.
- **Priorización:** al actualizar, se eliminan modelos con faltante total 0.

## Proyección

`Proyeccion` y `Proyeccion - SKUS` se dibujan desde **B2** (fila 1 vacía; encabezado en la fila 2; datos desde la fila 3). Encabezado navy `#20124D` con letras blancas. Filas con borde negro exterior y líneas internas suaves. Hay **12 columnas de acumulado semanal** (`Acum Sem 1` … `Acum Sem 12`).

Resaltado de acumulados (solo la **primera** semana que cruza cada umbral):

- Amarillo `#FFE599` al llegar a la cantidad mínima.
- Verde `#D9EAD3` (texto `#38761D` en negrita) al llegar a la meta.
- Valores intermedios se quedan en blanco. Después de la meta el resto de semanas es `--`.

En `Proyeccion`, cada nombre de modelo es un enlace a la primera fila de ese modelo en `Proyeccion - SKUS`.

## Tableros Semana 6 a Semana 12

Las pestañas `Semana 6` … `Semana 12` deben existir con el mismo formato (encabezados desde **B3**: Linea, Modelo, MOs, Solicitada, Lunes, Martes, Miercoles, Jueves, Viernes, Total Semana (SKU), Total Semana (Linea)). Al generar la planificación se escriben tablero, resumen ejecutivo y alerta de pendientes. Si una pestaña no está, se omite sin error. `Semana 11` y `Semana 12` se tratan igual que `Semana 10`.
