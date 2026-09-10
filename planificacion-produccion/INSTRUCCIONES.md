# Planificación de Producción v5.9.16 — códigos listos para pegar

## Cómo instalar (borrar y pegar)

En el editor de **Google Apps Script** del archivo de Planificación:

1. Abre `Codigo.gs`, selecciona **todo**, bórralo y pega el contenido completo de `planificacion-produccion/Codigo.gs`.
2. Abre (o crea) el archivo HTML llamado **`Dashboard`** (sin `.html`). Selecciona **todo**, bórralo y pega el contenido completo de `planificacion-produccion/Dashboard.html`.
3. Guarda el proyecto. Recarga la hoja. Corre **2️⃣ Actualizar Priorización** si hace falta crear/verificar `Priorizacion - SKUs`, y luego **3️⃣ Generar Planificación**.

## Priorizacion - SKUs

Hoja: `Priorizacion - SKUs`. Columnas (fila 2): SKU, Producto, Genero, Color, Talla, Cantidad Minima, Fecha de Salida Estimada, Lineas.

- SKU, Producto, Genero, Color, Talla, Cantidad Minima y Fecha se llenan **a mano**.
- **Lineas** es fórmula (VLOOKUP a `Por Hacer`); no la borres.

Esos SKUs **no adelantan el modelo** en la cola. Cuando al modelo le toca entrar a la línea, salen primero (todo su faltante). Después sigue la distribución habitual (colores núcleo y el resto). Se refleja en `Proyeccion - SKUS` y `Entrada de Almacen - Skus`.

## Motor v5.9.16

- **Faltante sin línea:** una fila de `Por Hacer` con unidades faltantes y `Linea de Produccion` vacía **sí entra** a proyección y a los tableros semanales. La línea se toma de `Priorizacion`, si no de la hoja `BS` (columna Lineas de Produccion del MODELO) y si no un respaldo (cap ≤ 40 → línea 5; resto → 2 / 3 / 4). Antes esas filas (RIO KIDS, MAR ORIGINAL, VITA, VESTIDO ARYNA, etc.) desaparecían del conteo.
- **Lotes por color y género:** si el mismo producto (ej. RIO CAB y RIO DAMA) está asignado a **2 líneas y esas líneas están libres**, los géneros trabajan **en paralelo** (uno por línea). Si solo queda **una** línea libre, secuencian ahí **por color** (Negro → Blanco → Marino → resto) y **dentro de cada color por género** (CAB → DAMA → KIDS). El sobrante del día pasa al siguiente lote de la familia. Los Especiales no usan esta regla.
- **Horizonte 10 semanas:** `Proyeccion` y `Proyeccion - SKUS` proyectan 10 semanas (la actual + 9), con los mismos formatos, acumulados y umbrales. Las pestañas `Semana 6` a `Semana 10` reciben tablero, resumen ejecutivo y alerta de pendientes igual que `Planificacion` / `Semana 2`–`Semana 5`. El menú **Ver Pestañas** las incluye.
- **Fix de sintaxis:** Apps Script ya no falla con `Unexpected token '}'`. Se restauró `familiaOcupaLinea_` (un recorte de v5.9.7 dejaba un `}` suelto).
- **Capacidad diaria por producto:** no se usa un techo fijo 130/40. Al planificar se lee `Cap Produccion por Dia` (Por Hacer col. N, Por Hacer - Especial col. O) y esa cifra es el cupo del día mientras el modelo ocupa la línea. Si cambia de modelo a media jornada, el sobrante se calcula con la cap del que entra. Si la celda viene vacía, respaldo L1-4=130 / L5=40.
- **Almacén:** `Fecha Entrada de Almacen` = **4 días hábiles** después de salir de costura.
- **Sincronizar Producción:** `Cantida Producida` en Por Hacer es la **base**. Cada fila **nueva** de `Produccion - Costura` (huella MO+SKU+cantidad+fecha+línea) se suma a esa MO. La hoja oculta `Sync Costura Aplicada` guarda esas huellas con el sello de texto `SYNC-V13` (ya no `5.9.12`, que Google convertía en fecha y dejaba de detectar filas nuevas).
- **Tableros por flujo:** el remanente (lote chico que cierra el día) va primero; el modelo que sigue el resto de la semana va después.
- **Actualizar MOs:** las MO en **Hecho** de `Por Hacer - Especial` **no** se archivan ni se borran, y **no entran al backlog** ni a la planificación. Cancelada sí se archiva. Producción regular sigue igual.
- **Línea 1 y cambio de modelo:** si el ocupante termina a media jornada, el sobrante pasa al siguiente especial. Un modelo que lista L1 pero ya está trabajando en otra línea **no bloquea** ese desborde. Dos modelos en L1 el mismo día van **en secuencia**, no en paralelo.
- **Cantidad mínima** (columna en `Priorizacion`): máxima prioridad **después de Especial**. El cupo es la cantidad pedida (ej. 100) tomada del **faltante**; lo ya producido **no recorta** ese cupo (no convierte 100 en 67). Solo si el piso ya está cubierto (producido ≥ mínima) el modelo no entra a esa banda. El cupo sale antes que Urgente / Alta / fecha. Cuando se cubre, el modelo **cede la línea** (el sobrante del día pasa al siguiente) y el resto de su pedido vuelve a la cola normal.
- **Urgente** después de Especial y de la cantidad mínima, luego la fecha de salida más próxima. Un modelo Urgente con dos líneas (ej. `2, 4`) usa las dos.
- **Líneas 1-4:** un modelo a la vez (**no en paralelo**). Si el modelo termina o no puede seguir, el **sobrante del mismo día** pasa al siguiente de la cola.
- **Línea 5** es la única que puede trabajar **dos familias** en paralelo. Si va un modelo solo, usa su cap del día (típico 40). Si hay dos familias, se turnan en lotes de 5. El mismo producto en distinto género **no** corre en paralelo: va en secuencia por color y género.
- **Especial:** se respeta `Linea de Produccion`. La línea 1 es la casa: si no hay línea, se usa 1. Cuando L1 termina los Especiales que sí la listan, los Especiales de otras líneas desbordan a L1. `Fecha de Salida Estimada` en `Por Hacer - Especial` ordena esos modelos.
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
