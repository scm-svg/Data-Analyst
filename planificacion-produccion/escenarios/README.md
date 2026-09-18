# Pedido especial 10K — comparación de escenarios

Informe de decisión gerencial para meter en el taller un pedido especial del cliente **10K**
(1.000 pzas, 18 SKUs, 4 modelos) sin perder de vista lo que le pasa al resto de la producción.

El entregable es **`Dashboard_Pedido_Especial_Escenarios.html`**: un archivo autocontenido
(los datos van embebidos, no necesita internet ni servidor) que se abre con doble clic en
cualquier navegador.

## Qué contiene el dashboard

| Pestaña | Contenido |
| --- | --- |
| **Resumen general** | Tarjeta de veredicto por escenario, línea de tiempo de las cuatro entregas contra el límite, tabla comparativa completa, composición del pedido, recomendación y el calendario del plan actual sin el pedido. |
| **Escenario A / B / C / D** | Fecha en que queda listo el pedido y holgura contra el límite, detalle modelo por modelo, reparto entre líneas, aviso sobre la Línea 1, calendario por línea y día de las semanas afectadas, tabla de modelos aplazados con el cambio de fecha, y pros y contras. |
| **Supuestos** | Cómo se leen las fechas, capacidades por modelo, de dónde salen los datos y la configuración cargada en cada escenario. |

## Datos de partida

- **Pedido:** 1.000 pzas en Clásica Cab (325), Clásica DAMA (235), Mafe DAMA (215) y
  Running Tank Biomove Cab (225).
- **Fecha límite de entrega:** 09/10/2026.
- **Después de costura** las piezas del pedido tardan 3 días hábiles en pasar el resto de
  etapas, así que la **última costura útil es el 06/10/2026**.

## Conclusiones por escenario

| Esc. | Líneas | Pedido listo | Contra el 09/10 | Pzas a tiempo | Modelos aplazados | Atraso máx. |
| --- | --- | --- | --- | --- | --- | --- |
| **A** | solo L4 | 20/10/2026 | **7 días hábiles tarde** | 480 / 1.000 (48 %) | 5 (3.906 pzas) | 15 d |
| **B** | L1+L2 y L4 | 14/10/2026 | **3 días hábiles tarde** | 785 / 1.000 (78 %) | 6 (5.028 pzas) | 8 d |
| **C** | L1+L2 y L3+L4 | 07/10/2026 | **+2 días de margen** | 1.000 / 1.000 (100 %) | 8 (6.831 pzas) | 5 d |
| **D** | L1+L2 y L2+L3+L4 | 06/10/2026 | **+3 días de margen** | 1.000 / 1.000 (100 %) | 8 (6.831 pzas) | 12 d |

- **A** mete todo el pedido por la Línea 4. Es el que menos desordena el plan regular, pero
  ocupa la línea 13 días seguidos y entrega 7 días hábiles tarde. Además carga 250 pzas de RIO
  en la Línea 1 la semana del 28/09, que ya está comprometida con otro pedido: ese arrastre no
  es realizable y el atraso real sería todavía mayor.
- **B** adelanta Running Tank por Líneas 1 y 2 y deja el resto en la Línea 4. Resuelve el modelo
  más difícil, pero Mafe DAMA cierra el 09/10 y el pedido se entrega 3 días hábiles tarde.
- **C** (recomendado) adelanta Running Tank y reparte el resto entre Líneas 3 y 4. Cumple la
  fecha con 2 días hábiles de colchón, solo ocupa 7 días de costura y el atraso al resto del
  taller es el más parejo: ningún modelo se pasa de 5 días hábiles.
- **D** es igual que C pero llevando Mafe DAMA a la Línea 2. Entrega un día antes (06/10) a costa
  de empujar RIO NS DAMA 12 días hábiles y RIO NS CAB 8, hasta noviembre.

**Recomendación: escenario C.** Cumple el 09/10, deja margen y reparte el atraso de forma pareja.
**D** solo conviene si hace falta cerrar el pedido antes de octubre y RIO NS puede esperar a
noviembre. **A** y **B** quedan descartados porque no llegan a la fecha.

## Salvedades

- El escenario **A** se generó con el apoyo del 50 % de la Línea 1 activo desde la semana 2, y
  los escenarios **B**, **C** y **D** sin él. Por eso solo en A aparecen RIO DAMA y RIO KIDS
  produciendo en la Línea 1 durante las semanas 2 y 3, y por eso A choca con el otro pedido que
  ya tiene tomada esa línea la semana del 28/09.
- Los atrasos se miden en días hábiles comparando la fecha estimada de término de cada modelo
  contra la planificación sin el pedido.

## Cómo se regenera

Los cinco `.xlsx` de origen **no están versionados** (pesan ~2,5 MB cada uno). Hay que dejarlos
en esta misma carpeta con estos nombres:

- `Planificacion_sin_pedido_d104.xlsx` — plan de referencia, sin el pedido
- `Escenario_A_8fee.xlsx`, `Escenario_B_499e.xlsx`, `Escenario_C_62ac.xlsx`, `Escenario_D_e947.xlsx`

Después, desde esta carpeta:

```bash
pip install openpyxl                # única dependencia
python3 extraer_datos.py            # .xlsx  -> data.json
python3 compute.py                  # data.json -> metricas.json  (imprime la tabla resumen)
python3 build_dashboard.py          # metricas.json -> Dashboard_Pedido_Especial_Escenarios.html
```

`extraer_datos.py` acepta opcionalmente la carpeta de los `.xlsx` y la ruta de salida:
`python3 extraer_datos.py /ruta/a/los/xlsx /ruta/data.json`. `build_dashboard.py` acepta la
ruta del HTML de salida.

`metricas.json` sí se versiona, así que el HTML se puede regenerar con solo el último paso
sin necesidad de los Excel.

## Archivos

- `extraer_datos.py` — lee de cada libro los tableros semanales (`Planificacion` y `Semana 2` a
  `Semana 12`), la hoja `Proyeccion`, `Entrada de Almacen Modelo` y `Por Hacer - Especial`.
- `compute.py` — calcula fechas de entrega, holgura, piezas dentro de fecha, reparto por línea,
  ocupación y modelos aplazados contra el plan de referencia.
- `build_dashboard.py` — arma el HTML, con los textos de veredicto, pros y contras.
- `metricas.json` — métricas calculadas, entrada del dashboard.
- `Dashboard_Pedido_Especial_Escenarios.html` — el informe para abrir en el navegador.
