# Auditoría técnica de la Propuesta de Aumento de Plantilla

**Reestructuración Team Almacén Fábrica — Revisión de planteamiento, datos, aritmética, metodología y riesgos**

*26 de agosto de 2026 — Documento revisado: «Propuesta Aumento de Plantilla — Reestructuración Team Almacén Fábrica» (8 páginas)*

---

## Nota metodológica

Este informe revisa el documento *Propuesta Aumento de Plantilla — Reestructuración Team Almacén Fábrica* (8 páginas). El procedimiento fue el siguiente:

1. Se extrajeron todas las cifras publicadas en el documento original.
2. Cada una se recalculó de forma independiente a partir de los supuestos que el propio documento declara, sin importar valores del original.
3. Se cruzaron las secciones entre sí para detectar contradicciones internas (capacidad contra demanda, demanda contra estructura de células, protocolo contra demanda declarada).
4. Se reconstruyó la asignación día por día a partir de la tabla de tareas, que es información que el documento contiene pero no explota.
5. Se modelaron escenarios alternativos y análisis de sensibilidad sobre los supuestos no verificados.

Los recálculos son reproducibles con los scripts `verificacion_almacen.py` y `analisis_avanzado_almacen.py`, que acompañan a este informe. Toda cifra citada aquí proviene de esa verificación, no del documento original.

---

## 1. Veredicto ejecutivo

**La aritmética está impecable; el modelo no lo está.** Todas las sumas y productos del documento cuadran al centavo: 371.25, 288.75, 287.75, 105.00, 392.75, 104.00 y 2.5 FTE son correctos. El problema no está en la calculadora, está en los supuestos, en la consistencia interna y en la ausencia de datos duros.

En su estado actual, un director financiero o un gerente de operaciones con experiencia desarma la propuesta con tres preguntas. La buena noticia es que **la conclusión —llegar a 12 personas— es probablemente correcta**, pero está sostenida por el razonamiento equivocado. Hay que reconstruir el argumento, no la conclusión.

| Dimensión | Evaluación | Comentario |
|---|---|---|
| Aritmética | 9 / 10 | Correcta; solo errores de redondeo menores |
| Consistencia interna | 3 / 10 | Contradice su propia plantilla, su propia demanda y su propio protocolo |
| Metodología | 4 / 10 | Invoca OEE pero nunca lo calcula; la demanda se mide por presencia, no por volumen |
| Calidad de datos | 2 / 10 | Sin volúmenes, sin tiempos estándar, sin líneas base de KPI, sin dinero |
| Caso de negocio | 2 / 10 | No hay una sola cifra monetaria en las 8 páginas |
| Riesgo legal y control interno | 3 / 10 | Datos de salud identificables, responsabilidad colectiva, autoauditoría |
| Redacción y presentación | 5 / 10 | Tono autopromocional, artefactos de formato, siglas sin definir |

*Evaluación por dimensión*

> **El hallazgo que resume todo: la carga recurrente completa del almacén —incluyendo las tareas hoy desatendidas— requiere 8.55 personas a horas nominales, y la plantilla actual es de 9 o 10. Por tanto el caso NO puede construirse sobre el trabajo del día a día. Se construye sobre otras cuatro cosas: las pérdidas de disponibilidad, la concentración del pico Lunes-Miércoles, la expansión de tiendas y el proyecto REFRESH. El documento actual apunta al lugar equivocado.**

## 2. Los cinco golpes que hay que blindar antes de presentar

Ordenados por gravedad. Si solo se corrige una parte del documento, que sea esta.

### 2.1 El documento se contradice sobre cuánta gente hay

La capacidad se calcula con 9 almacenistas (`9 × 41.25 = 371.25 HH`), pero la tabla de demanda llega hasta *«Almacenistas 9 y 10»*. Contando cabezas nombradas en la tabla salen 10 personas. Y el título de la propuesta implica pasar de 9 a 12, o sea +3.

| Concepto | Con 9 personas (documento) | Con 10 personas (tabla real) |
|---|---|---|
| Capacidad real efectiva | 288.75 HH | 330.00 HH |
| Absorción del día a día | 99.6 % | 87.2 % |
| Brecha total | 104.00 HH | 62.75 HH |
| FTE solicitados | 2.52 | 1.52 |

*Efecto de corregir el conteo de plantilla*

La frase estelar de la propuesta —*«absorbe el 99.6 % de la capacidad real; matemáticamente es imposible realizar las tareas estructurales»*— **se cae sola** si la plantilla es de 10. Hay que resolverlo con la nómina en mano antes de que lo resuelva la junta.

### 2.2 Hoy hay 124.75 horas-hombre nominales sin asignar, y se reclaman 105

Reconstruyendo la asignación día por día desde la propia tabla del documento:

| Concepto | Lun | Mar | Mié | Jue | Vie | Total |
|---|---|---|---|---|---|---|
| Carga asignada (HH) | 80.50 | 80.50 | 75.25 | 25.75 | 25.75 | 287.75 |
| Capacidad nominal, 10 pers. (HH) | 82.50 | 82.50 | 82.50 | 82.50 | 82.50 | 412.50 |
| Horas sin asignar (HH) | 2.00 | 2.00 | 7.25 | 56.75 | 56.75 | 124.75 |
| Utilización | 98 % | 98 % | 91 % | 31 % | 31 % | 70 % |

*Perfil de carga por día reconstruido desde la tabla de tareas*

Los seis almacenistas de PT y Equipamiento tienen **jueves y viernes completos sin asignación** (99 HH). Sumando el resto: 124.75 HH nominales libres por semana, contra 105.0 HH de tareas omitidas que se reclaman. En el papel, **las tareas omitidas caben dentro del tiempo que ya existe**.

Peor aún: el propio documento lo admite cuando dice que la Célula 2 *«tiene los días jueves y viernes libres de picking masivo para realizar 5S y conteos cíclicos ABC»*. El diagnóstico omite el tiempo libre para poder declarar un déficit del 99.6 %, y la solución lo usa como recurso. No se puede sostener las dos cosas.

> **Esta es la pregunta que hunde la propuesta: «si tus operadores de PT no tienen asignación jueves y viernes, ¿por qué necesito contratar a alguien para los conteos cíclicos?». Hay que responderla de frente y en el cuerpo del documento. Las respuestas legítimas existen —concentración de ausencias, recuperación de atrasos del pico, tareas que exigen perfil o accesos distintos, pico real de recepción— pero hay que sustentarlas con data de asistencia y de atrasos.**

### 2.3 El número 3 no se deriva de nada

El documento afirma que 3 contrataciones son *«el número exacto»*. Con sus propios supuestos, el mismo modelo produce 1 o 4, nunca 3:

| Lectura de los supuestos | Cálculo | Resultado |
|---|---|---|
| Los nuevos sufren las mismas pérdidas (77.8 %) | 104 / (41.25 × 0.778) | 3.24 FTE → harían falta 4 |
| Las pérdidas son transitorias (vacaciones rotativas, curva que se extingue) | (392.75 − 371.25) / 41.25 | 0.52 FTE → haría falta 1 |
| Se aplica la expansión declarada del 12.5 % trimestral | (104 + 74.25) / 41.25 | 4.32 FTE → harían falta 4 o 5 |
| Se corrige la plantilla a 10 personas | 62.75 / 41.25 | 1.52 FTE → harían falta 2 |

*El mismo modelo, cuatro lecturas, ningún resultado igual a 3*

Hay además un doble estándar visible a simple vista: los 9 actuales se computan al 77.8 % de rendimiento y los 3 nuevos al 100 %. Si los nuevos rinden como el resto, aportan `3 × 41.25 × 0.778 = 96.25 HH` y **no cubren las 104 HH requeridas**.

### 2.4 No hay una sola cifra monetaria, y el ROI tiene un error de concepto

Se pide plantilla permanente sin decir cuánto cuesta ni cuánto devuelve. Para una junta directiva, eso solo es motivo suficiente de rechazo. Y el párrafo de retorno dice:

```
«La incorporación de 3 operadores se autofinancia liberando las 10.000 piezas
 del Proyecto Refresh»
```

Liberar inventario genera **caja una sola vez**. Los salarios son **gasto recurrente**. Un ingreso único no puede financiar un costo permanente. Esa frase, tal como está, le entrega al director financiero el argumento para devolver la propuesta.

### 2.5 La propuesta reduce el pico de picking mientras afirma que el volumen crece

| Escenario | Operadores PT + Equipamiento | Capacidad Lun-Mié |
|---|---|---|
| Hoy | 3 + 3 = 6 | 148.50 HH |
| Propuesto (Célula 2) | 3 + 2 = 5 | 123.75 HH |
| Variación | −1 operador | −24.75 HH |

*La Célula 2 recorta el frente que se declara en crecimiento*

El recorte cae precisamente sobre **Equipamiento Volumétrico** (de 3 a 2), que es el material más difícil de manipular, y en el pico Lunes-Miércoles. Se pide gente para atender crecimiento y, en el mismo documento, se le quita un operador al frente que crece.

---

## 3. Lo que está bien y hay que conservar

No todo se reescribe. Estos son los activos reales del documento:

1. **La estructura de células con custodia física por zona.** Es una idea sólida y genuinamente alineada con buenas prácticas de control de inventario. Vale por sí sola, incluso sin contratar a nadie.
2. **Separar carga «del día a día» de carga «estructural omitida».** Es la distinción correcta y es lo que hace visible el problema real.
3. **Cuantificar en horas-hombre en lugar de argumentar por percepción.** El instinto es el correcto: hablar de capacidad y demanda, no de «estamos ahogados».
4. **Ligar cada célula a un KPI propio** (ERI, OTIF, errores de picking). Bien planteado; solo faltan las líneas base.
5. **Identificar el inventario REFRESH como capital inmovilizado** y no como estorbo. Ese es el ángulo financiero que puede vender toda la propuesta.

## 4. Inconsistencias verificadas, una por una

### 4.1 La jornada de 8.25 h no coincide con el horario declarado

El documento dice *«Jornada teórica diaria: 8.25 horas (8:15 am - 4:45 pm)»*. Ese horario abarca **8.50 h**, no 8.25 h. Si hay un break de 15 minutos hay que declararlo; si hay una hora de comida (lo habitual, y obligatorio en muchas jurisdicciones), la jornada neta es 7.50 h y toda la base cambia un 9 %.

| Jornada neta | 9 personas | 10 personas |
|---|---|---|
| 7.50 h (con 1 h de comida) | 337.50 HH | 375.00 HH |
| 8.25 h (documento) | 371.25 HH | 412.50 HH |
| 8.50 h (span literal del horario) | 382.50 HH | 425.00 HH |

*Sensibilidad de la capacidad teórica a la jornada*

Es el número del que cuelga todo el modelo y es el único que nadie verificó. Hay que cerrarlo con el reglamento interno y el reloj de asistencia, y declarar el break de forma explícita.

### 4.2 Se compara demanda bruta contra capacidad neta

La demanda (287.75 HH) son horas de presencia asignada de gente trabajando **al 100 %**. La capacidad (288.75 HH) es la misma gente **descontada al 77.8 %**. Se comparan dos magnitudes medidas con reglas distintas, y la comparación está construida para que el resultado sea 99.6 %.

Más de fondo: la demanda se derivó del **horario que ya tienen asignado**, no de un cálculo independiente del trabajo requerido. Es circular. «Necesitamos 287.75 HH porque es lo que están haciendo» no prueba que ese trabajo requiera 287.75 HH; prueba que ocupan ese tiempo.

### 4.3 Pérdidas transitorias tratadas como permanentes

| Deducción | HH/semana | ¿Es realmente permanente? |
|---|---|---|
| Vacaciones (1 persona completa) | 41.25 | No. Es rotativo: 15 días/año sobre 9 personas equivale al 5.8 % estructural, no al 11.1 % |
| Intermitencia por salud (2 pers., −30 %) | 24.75 | Depende. Si hay restricción médica documentada, sí; si es ausentismo, es gestión de RR. HH. |
| Curva de aprendizaje (1 nuevo, −40 %) | 16.50 | No. Se extingue al madurar el aprendizaje |

*Naturaleza de las tres deducciones, que se suman como si fueran iguales*

Descontar una persona completa de vacaciones **todas las semanas del año** sobrestima el efecto: 9 personas × 15 días = 135 días/año de ausencia, que sobre 2 340 días-persona es el **5.8 %**, no el 11.1 % que implica la deducción. La forma correcta y estándar es un factor de disponibilidad aplicado uniformemente, no deducciones ad hoc por persona.

### 4.4 REFRESH: un proyecto finito contabilizado como carga permanente

Las 40 HH/semana del Proyecto REFRESH son el **38 % de las 105 HH omitidas** y se usan para justificar plantilla permanente. Pero son 10 000 piezas: es un trabajo con fin.

| Ritmo supuesto | HH totales | Duración a 40 HH/semana |
|---|---|---|
| 20 piezas/HH | 500 HH | 12.5 semanas |
| 30 piezas/HH | 333 HH | 8.3 semanas |
| 40 piezas/HH | 250 HH | 6.2 semanas |

*El proyecto REFRESH es finito; su duración depende de un ritmo que no se declara*

El documento **no declara el ritmo de procesamiento**, que es justo el dato que convierte «40 HH/semana» en una cifra auditable. Y financiar nómina indefinida con un proyecto de dos o tres meses es exactamente lo que un director financiero detecta y castiga. Corresponde recurso temporal, horas extra u outsourcing, no plantilla permanente.

Además la Célula 4 asigna 2 personas fijas (82.5 HH) a devoluciones más REFRESH cuando la demanda declarada de ese frente es 60 HH. Cuando REFRESH termine, esa célula queda con 20 HH de trabajo y 82.5 HH de capacidad.

### 4.5 El «12.5 % por trimestre» no es constante

| Trimestre | Tiendas | Incremento porcentual | Carga adicional |
|---|---|---|---|
| T1 | 8 → 9 | 12.5 % | +18.56 HH |
| T2 | 9 → 10 | 11.1 % | +18.56 HH |
| T3 | 10 → 11 | 10.0 % | +18.56 HH |
| T4 | 11 → 12 | 9.1 % | +18.56 HH |
| Total 12 meses | 8 → 12 | +50 % | +74.25 HH/semana |

*El porcentaje decrece porque la base crece; la carga en horas es lineal*

En horas-hombre la carga es lineal (unos 18.56 HH por tienda), no porcentual. Usar porcentajes sobre base móvil es un error conceptual que además **no hace falta**: la cifra en horas es más simple y más defendible.

Detalle relacionado: la línea *«Reabastecimiento Tienda Nueva (cada 3 meses) = 16.25 HH»* es muy cercana a los 18.56 HH/tienda del estándar. Eso sugiere que **ya es la tienda 9 en régimen**, no un evento trimestral. Si es así, la base real es 9 tiendas y la etiqueta «cada 3 meses» induce a error, o puede leerse como doble conteo.

### 4.6 Consumibles está asignado a dos células, y la Célula 3 queda sobredimensionada

La Célula 1 aparece en la tabla de custodia como responsable de la *«Jaula de Consumibles (Empaques/Taller)»*, mientras la Célula 3 dice en su justificación que *«unifica los pedidos de la web, cuadro chat y la entrega de consumibles»*. El mismo frente está en dos células, y eso define si la Célula 3 tiene trabajo:

| Célula | Ops | Capacidad nominal | Demanda mapeada | Utilización |
|---|---|---|---|---|
| 1: MP + Insumos + Consumibles | 3 | 123.75 HH | 108.00 HH | 87 % |
| 2: PT + Equipamiento + Rampa | 5 | 206.25 HH | 164.75 HH | 80 % |
| 3: E-commerce + Chat (+ Consumibles?) | 2 | 82.50 HH | 15.00 – 40.50 HH | 18 – 49 % |
| 4: Logística Inversa + REFRESH | 2 | 82.50 HH | 60.00 HH | 73 % |

*Utilización de cada célula según los propios números del documento*

La Célula 3 usa entre el 18 % y el 49 % de su capacidad según dónde se cuenten los consumibles. Es la célula más fácil de recortar para quien quiera rechazar la propuesta, y encima es la que carga el SLA más agresivo (menos de 24 h). Hay que sustentarla con volúmenes de pedidos web y proyección del canal digital, que hoy no aparecen en ninguna parte, o redistribuir su alcance.

También conviene notar que la línea «Reabastecimiento Tienda Nueva» (16.25 HH) **no queda asignada explícitamente a ninguna célula** en la estructura nueva. Cada hora-hombre de la demanda debe tener un dueño en el organigrama propuesto; si no, la tabla de demanda y la de células no son comparables.

### 4.7 Conteos cíclicos: dos cifras que no cuadran

- Demanda declarada en la tabla de tareas omitidas: **30.0 HH/semana**.
- Protocolo declarado en la sección de gobernanza: «cada viernes las células dedican las últimas 2 horas» = `12 × 2 = 24.0 HH/semana`.

Faltan 6 HH. Quien cruce las dos secciones encuentra que el protocolo propuesto no cubre la demanda que el mismo documento definió.

### 4.8 Errores menores de redondeo y de formato

| Cifra del documento | Valor correcto | Observación |
|---|---|---|
| 77.7 % de utilización | 77.8 % | 288.75 / 371.25 = 77.78 % |
| 99.6 % de absorción | 99.65 % | El documento trunca en lugar de redondear |
| 2.5 operadores | 2.52 | Conviene mostrar el decimal |
| `$\times$` en dos filas | × | Artefacto de LaTeX sin renderizar |
| Tablas desmaquetadas | — | Encabezados partidos a media palabra al exportar |
| «utilización real utilizable» | — | Redundancia de redacción |

*Correcciones puntuales*

---

## 5. Debilidades metodológicas

### 5.1 Se invoca OEE y nunca se calcula

El documento define OEE = Disponibilidad × Desempeño × Calidad y después **no presenta ni un solo valor de los tres factores**. El único número que aparece (77.8 %) es utilización de horas, es decir apenas una aproximación a Disponibilidad. Prometer una metodología y no ejecutarla es peor que no mencionarla: invita a preguntar por lo que falta.

Hay además un error de traducción. La portada dice *«OEE (Overall Equipment Effectiveness / Eficiencia General de **Personal**)»* y el marco teórico dice *«Eficiencia General de los **Equipos**»*. Se contradice a sí mismo en dos páginas. Para personas la métrica correcta es **OLE (Overall Labor Effectiveness)**:

```
OLE = Disponibilidad × Desempeño × Calidad
    = (horas trabajadas / horas contratadas)
    × (producción real / estándar esperado)
    × (1 − tasa de error)

Ejemplo con valores plausibles: 0.85 × 0.90 × 0.97 = 74 %
```

Nota terminológica adicional: «Capacidad Instalada» es vocabulario de planta y maquinaria. Para personas corresponde «capacidad de mano de obra» o «modelo de dotación».

### 5.2 La demanda no está construida sobre generadores de volumen

Esta es la falla metodológica de fondo. Una demanda defendible se construye así:

```
HH requeridas   = Σ (volumen_i × tiempo_estándar_i)
FTE requeridos  = HH requeridas / (horas_semana × factor_disponibilidad)
```

El documento no tiene ni volúmenes ni tiempos estándar. Sin ellos no se puede responder la pregunta obvia: **¿el equipo actual es productivo?** Y sin esa respuesta, la contrapropuesta natural de la gerencia es «mejora la productividad antes de pedir gente».

Vale la pena notar que los 18.56 HH por tienda por semana equivalen a más de dos jornadas completas de una persona **por tienda**. Puede ser correcto, pero es una cifra alta que exige sustento en unidades movidas.

### 5.3 El promedio semanal esconde el problema real

El modelo es un promedio semanal y por eso no ve que el problema real es de **pico y distribución**, no de volumen total: Lunes a Miércoles al 91-98 % y Jueves-Viernes al 31 %. Un modelo así puede mostrar capacidad suficiente mientras los lunes se caen. Y abre la alternativa que el documento no menciona: nivelar la carga (sección 6.4).

### 5.4 No se verifica si la restricción es realmente la gente

Se asume que el cuello de botella es mano de obra. Puede no serlo. Si hay un solo montacargas, dos andenes o escáneres insuficientes, **contratar tres personas no aumenta el throughput**: solo agrega gente esperando. Antes de pedir plantilla hay que descartar restricciones de equipo, andén, espacio y sistema. Si el cuello de botella es equipo, la propuesta correcta es otra y probablemente más barata.

### 5.5 No hay análisis de alternativas ni escenarios

Ninguna junta aprueba plantilla permanente sin ver las opciones descartadas. Faltan, como mínimo: horas extra, personal temporal, nivelación de carga, cambio de frecuencia de reparto, tercerización del REFRESH, mejoras de WMS, picking por olas y cross-docking. Cada una con su costo y con la razón por la que no resuelve, o por la que resuelve solo en parte. Tampoco hay escenarios base, optimista y pesimista sobre los dos supuestos que mueven todo: jornada neta y ritmo de apertura.

---

## 6. Análisis complementario: lo que el documento no modela

Esta sección aporta los cálculos que la propuesta necesita y no tiene. Todos son reproducibles con `analisis_avanzado_almacen.py`.

### 6.1 Sensibilidad cruzada: jornada contra disponibilidad

La demanda del documento está medida por presencia, así que la parte del día a día escala con la jornada, mientras las tareas omitidas recurrentes (65 HH) son trabajo absoluto y no escalan. FTE totales requeridos:

| Jornada neta | 78 % | 82 % | 85 % | 88 % | 100 % |
|---|---|---|---|---|---|
| 7.50 h | 11.17 | 10.62 | 10.25 | 9.90 | 8.71 |
| 8.00 h | 11.03 | 10.49 | 10.12 | 9.77 | 8.60 |
| 8.25 h (documento) | 10.96 | 10.43 | 10.06 | 9.72 | 8.55 |
| 8.50 h | 10.90 | 10.37 | 10.01 | 9.66 | 8.51 |

*FTE requeridos según jornada neta (filas) y factor de disponibilidad (columnas)*

El resultado oscila entre **8.51 y 11.17 FTE**: una amplitud de 2.66 personas producida solo por dos supuestos que nadie verificó. Y hay un hallazgo fino: **la jornada casi no mueve el resultado** (entre 0.20 y 0.27 FTE al pasar de 7.50 h a 8.50 h, porque afecta a demanda y capacidad a la vez), mientras **la disponibilidad lo mueve 2.41 FTE**. El supuesto que hay que blindar con data de asistencia real es la disponibilidad, no la jornada.

Obsérvese también la columna del 100 %: a horas nominales bastan **8.55 personas** para todo el trabajo recurrente, incluidas las tareas hoy desatendidas. Con 9 o 10 personas en nómina, eso confirma que el caso no puede apoyarse en la carga del día a día.

### 6.2 Punto de saturación de la estructura de 12 personas

Con un factor de disponibilidad del 85 % (35.06 HH efectivas por persona):

| Plantilla | Capacidad efectiva | Tiendas que soporta |
|---|---|---|
| 9 personas | 315.56 HH | 6.0 |
| 10 personas | 350.62 HH | 7.9 |
| 12 personas | 420.75 HH | 11.7 |
| 13 personas | 455.81 HH | 13.6 |
| 14 personas | 490.88 HH | 15.4 |

*Cobertura de red de tiendas por nivel de plantilla*

Con 12 personas la capacidad se agota en la tienda 11.7: cubre con holgura hasta la 11ª y queda al límite al abrir la 12ª. A razón de una tienda por trimestre, **la 13ª persona se necesita al abrir la tienda 12, es decir al cierre del mismo año que cubre el plan**.

O sea que 12 no es «la solución del año», es la solución hasta la tienda 11 o 12. Decirlo de frente da credibilidad y evita volver a pedir plantilla sin aviso. Mejor aún: convertirlo en política, con el ratio de **una persona por cada 1.9 tiendas nuevas** aprobado de antemano.

### 6.3 Modelo de atraso acumulado: cómo cuantificar el «riesgo de no actuar»

El documento afirma que el OTIF colapsará por debajo del 75 %, pero no lo modela. Un modelo de atraso es simple y auditable: si la demanda excede la capacidad, el trabajo no hecho no desaparece, se acumula.

| Escenario de déficit | HH/semana | 4 semanas | 13 semanas | 26 semanas | 52 semanas |
|---|---|---|---|---|---|
| Déficit del documento (9 pers.) | 104.00 | 416 HH | 1 352 HH | 2 704 HH | 5 408 HH |
| Déficit corregido (10 pers.) | 62.75 | 251 HH | 816 HH | 1 632 HH | 3 263 HH |
| Déficit recurrente sin REFRESH (10 pers.) | 22.75 | 91 HH | 296 HH | 592 HH | 1 183 HH |

*Atraso acumulado según el escenario de déficit*

Uso recomendado: presentar el atraso acumulado en horas-hombre y traducirlo a una consecuencia medible —días de retraso en reposición, SKU sin contar, devoluciones sin procesar—. Eso reemplaza la afirmación «el OTIF colapsará» por una proyección que se puede auditar y verificar después.

### 6.4 Nivelación de carga: la alternativa que falta

El reabastecimiento de PT y Equipamiento son 148.50 HH/semana concentradas en tres días:

| Distribución | HH por día | Operadores por día |
|---|---|---|
| 3 días (situación actual) | 49.50 | 6.00 |
| 4 días | 37.12 | 4.50 |
| 5 días | 29.70 | 3.60 |

*Efecto de nivelar el reabastecimiento a lo largo de la semana*

Pasar de 3 a 5 días baja el pico de 6.00 a 3.60 operadores por día y libera 19.80 HH diarias en el cuello de botella. **No crea horas nuevas** —el total semanal es el mismo— pero elimina el atasco del lunes y vuelve utilizable el tiempo de jueves y viernes.

Es la primera contrapropuesta que hará la gerencia, y hay que responderla con la restricción real que lo impide: calendario de transporte, ventanas de recepción en tienda, o días de corte de producción. Si esa restricción no existe, la nivelación debe hacerse **antes** de pedir plantilla.

### 6.5 Umbral de rentabilidad del REFRESH, sin necesidad de moneda

El umbral se puede expresar sin unidades monetarias, lo que lo vuelve universalmente válido: el costo de recuperar una pieza es `1 / ritmo` horas de mano de obra.

| Ritmo | HH totales | Semanas a 40 HH | Umbral por pieza |
|---|---|---|---|
| 20 piezas/HH | 500.0 | 12.5 | 3.0 min de mano de obra |
| 30 piezas/HH | 333.3 | 8.3 | 2.0 min de mano de obra |
| 40 piezas/HH | 250.0 | 6.2 | 1.5 min de mano de obra |

*Valor mínimo por pieza para que el proyecto REFRESH empate*

A 30 piezas por hora-hombre, el proyecto empata si cada pieza recupera el valor de **2 minutos de mano de obra**. Cualquier pieza de inventario de una empresa de retail vale muchísimo más que eso, incluso vendida con descuento profundo o como material.

> **El REFRESH es, con enorme margen, el componente más rentable y más fácil de aprobar de toda la propuesta, y hoy está enterrado como una línea de tabla. Debería ser una petición separada, autofinanciada y con recurso temporal. Sacarlo del pedido de plantilla permanente fortalece ambas peticiones a la vez.**

---

## 7. El caso de negocio que falta

No hay ninguna cifra monetaria en las 8 páginas. Esta es la estructura mínima, con las fórmulas listas para rellenar con valores reales:

| # | Concepto | Fórmula | Tipo |
|---|---|---|---|
| 1 | Costo total por almacenista/año | salario × 12 × (1 + carga social) + dotación | Costo recurrente |
| 2 | Costo de la propuesta | (1) × número de contrataciones | Costo recurrente |
| 3 | Horas extra evitadas | HH extra actuales/año × tarifa hora extra | Ahorro recurrente |
| 4 | Reducción de merma | ajuste de inventario anual × % de reducción | Ahorro recurrente |
| 5 | Venta recuperada por quiebre | eventos de quiebre × ticket × margen | Ingreso recurrente |
| 6 | Beneficio recurrente total | (3) + (4) + (5) | Beneficio |
| 7 | Beneficio neto recurrente | (6) − (2) | Indicador |
| 8 | Payback en meses | (2) / ((6) / 12) | Indicador |
| 9 | Liberación REFRESH | 10 000 piezas × costo unitario × % recuperación | Caja única |
| 10 | Payback ajustado | ((2) − (9)) / ((6) / 12) | Indicador |

*Plantilla del caso financiero*

> **Regla que hay que respetar: el gasto recurrente (2) se justifica con el beneficio recurrente (6). La partida (9) es un ingreso de una sola vez y no puede sostener nómina indefinida; sirve para acelerar el payback. Presentarlas mezcladas es exactamente el error del párrafo de ROI actual.**

Con esa tabla se puede afirmar algo aprobable: «el costo recurrente se paga con ahorros recurrentes, y la liberación del REFRESH acorta el payback en X meses». Hoy la propuesta no puede afirmar nada de eso.

## 8. Riesgos legales, laborales y de control interno

### 8.1 Datos de salud de personas identificables

*«Intermitencia por Salud en Equipamiento (2 Almacenistas): −30 % de disponibilidad»*. En un almacén de nueve personas eso identifica a individuos concretos y expone información médica en un documento que circulará por la junta. Es un riesgo de protección de datos y de discriminación laboral.

Corrección: *«2 posiciones con restricciones operativas documentadas por medicina laboral (−30 % de disponibilidad efectiva)»*, y el detalle en un anexo confidencial de Recursos Humanos.

### 8.2 Responsabilidad colectiva y «guardián legal»

El documento dice que cada célula *«es el guardián legal y operativo»* y que *«la responsabilidad recae directamente sobre la célula custodia»*. En la mayoría de las legislaciones laborales de la región **no se puede imponer responsabilidad patrimonial colectiva** ni descontar diferencias de inventario del salario sin un procedimiento formal.

- Cambiar «guardián legal» por **«responsable operativo y administrativo»**.
- Definir un procedimiento documentado de investigación de diferencias con debido proceso.
- Validar la redacción con Recursos Humanos y con el área legal **antes** de presentarla.

### 8.3 La responsabilidad por célula también es responsabilidad diluida

El párrafo de cierre promete *«eliminamos la responsabilidad diluida»*, pero el modelo asigna la responsabilidad a un **grupo de 3 a 5 personas**. Responsabilidad de grupo *es* responsabilidad diluida: cuando falte una pieza en la Célula 2 habrá cinco personas y ningún responsable.

Corrección: **custodio nombrado por ubicación y por turno**, con acta de relevo firmada en cada cambio y control dual —dos firmas— en las transferencias entre células. Eso sí elimina la dilución.

### 8.4 La autoauditoría rompe la segregación de funciones

*«Cada célula dedica las últimas 2 horas a auditar su propia ubicación (Self-Audit)»*. El custodio contando su propio stock es un control débil: quien puede causar la diferencia no debe ser quien la reporta. Cualquier auditor lo marca de inmediato.

Corrección: **conteo cruzado** —la Célula 1 cuenta a la 2 y viceversa— con validación y muestreo independiente por el Analista de Inventarios. El autoconteo sirve como control interno de la célula, pero no como el conteo cíclico oficial.

### 8.5 El acceso restringido choca con la cobertura de ausencias

*«Acceso restringido únicamente para los almacenistas asignados a esa Célula»* entra en conflicto directo con el argumento de la Célula 2 (*«se absorben las bajas por ausentismo y vacaciones»*) y crea puntos únicos de falla cuando la célula completa está ausente. También hay que revisar accesos de emergencia y rutas de evacuación.

Corrección: matriz de delegación de custodia con acta de traspaso temporal, más un plan de polivalencia documentado.

### 8.6 Juicios subjetivos sobre el personal

*«Aliviar la lenta curva del nuevo elemento y la baja responsabilidad reportada»*. Esto es subjetivo, no está sustentado y **le da a la gerencia un argumento en contra**: si el problema es desempeño o responsabilidad, la respuesta es gestión de desempeño, no contratar más gente. Eliminar o reemplazar por métricas: líneas por hora, tasa de error, cumplimiento de conteos.

### 8.7 Metas absolutas no medibles y sin línea base

«Cero Averías en Carga» no es una meta gestionable; corresponde «menos del 0.1 % de unidades dañadas en carga». Y ninguno de los KPI tiene línea base: se piden ERI mayor al 98 %, OTIF mayor al 95 % y errores de picking menores al 0.5 % sin decir en cuánto están hoy, con lo cual es imposible demostrar mejora ni medir el retorno.

---

## 9. Datos que hay que levantar antes de presentar

Sin esto la propuesta es opinión bien formateada. Con esto es irrebatible de verdad.

### 9.1 Generadores de volumen (últimas 8 a 13 semanas, del WMS o ERP)

- Líneas y pedidos por día, por canal: tienda, web, chat, corporativo.
- Unidades y bultos despachados por tienda por semana.
- Recepciones por día: contenedores, pallets, bultos, órdenes de compra.
- Devoluciones recibidas por semana y su antigüedad de proceso.
- Órdenes de producción atendidas por día en Materias Primas.

### 9.2 Tiempos estándar (estudio de tiempos o timestamps del WMS)

- Minutos por línea de picking, por tipo de producto: manufacturado contra volumétrico.
- Minutos por bulto en recepción, conteo y control de calidad.
- Minutos por SKU en conteo cíclico.

### 9.3 Personas

- Asistencia y ausentismo real de los últimos 12 meses. Esto reemplaza el supuesto del −30 %.
- Horas extra pagadas y su costo. Es el argumento monetario más fácil de conseguir.
- Rotación y tiempo real de maduración de un almacenista nuevo. Esto sustenta o descarta el −40 %.
- **Nómina de plantilla actual firmada: ¿son 9 o son 10?**

### 9.4 Desempeño actual (líneas base de los KPI)

- OTIF a tiendas, ERI por familia, exactitud de picking, dock-to-stock, atraso acumulado en HH.

### 9.5 Dinero

- Valuación del inventario REFRESH y escenarios de recuperación.
- Merma y ajustes de inventario de los últimos 12 meses.
- Costo total anual de un almacenista: salario más cargas más dotación.

### 9.6 Restricciones físicas

- Montacargas, escáneres, andenes, ventanas de recepción, metros de rack disponibles.

## 10. Modelo recomendado: mismo objetivo, argumento defendible

Sustituir las deducciones ad hoc por un **factor de disponibilidad** estándar aplicado de forma uniforme:

| Componente | Porcentaje |
|---|---|
| Vacaciones (15 días / 260) | 5.77 % |
| Feriados (11 días / 260) | 4.23 % |
| Ausentismo | 3.00 % |
| Formación y reuniones | 2.00 % |
| Factor de disponibilidad resultante | 85.0 % |

*Construcción del factor de disponibilidad*

```
HH efectivas por FTE = 41.25 × 0.85 = 35.06 HH/semana

Demanda recurrente (sin REFRESH, que es proyecto):
  287.75 (día a día) + 30 (conteos) + 15 (5S) + 20 (devoluciones) = 352.75 HH
```

| Escenario | Cálculo | FTE requeridos |
|---|---|---|
| Situación actual | 352.75 / 35.06 | 10.06 |
| A 12 meses, con 4 tiendas nuevas | 427.00 / 35.06 | 12.18 |

*Dotación requerida con el modelo recomendado*

> **Conclusión: 12 personas es el número correcto, pero por razones distintas a las del documento. El modelo así construido sobrevive el escrutinio; el actual no.**

El costo marginal por tienda queda además en una cifra limpia y reutilizable: `18.56 HH / 35.06 HH = 0.53 FTE por tienda nueva`, es decir **un almacenista por cada dos tiendas que se abran**. Ese ratio convierte la propuesta en una política aprobada de antemano, en lugar de una pelea recurrente en cada apertura.

### 10.1 Petición recomendada, por fases y con disparadores objetivos

1. **Un almacenista ahora**, que es lo que el modelo sostiene contra una plantilla de 9 (10.06 requeridos menos 9 actuales = 1.06 FTE), para arrancar conteos cíclicos, 5S y devoluciones de forma sostenible.
2. **Uno por cada dos tiendas nuevas** (0.53 FTE por tienda), con disparador por KPI —OTIF por debajo del 95 % o atraso acumulado sobre X HH— y no por calendario. Con cuatro aperturas: dos personas más, llegando a **12 al cabo de las cuatro aperturas**, que es exactamente el objetivo de la propuesta original.
3. **Recurso temporal dedicado al REFRESH** (6 a 13 semanas según el ritmo real), financiado contra la caja liberada del propio inventario. Es el componente más fácil de aprobar porque se autofinancia de verdad.
4. **Nivelar la carga de Lunes-Miércoles a Lunes-Viernes** antes o en paralelo, y reportar el resultado. Demuestra que se agotó la eficiencia antes de pedir plantilla, que es exactamente lo que la gerencia quiere ver.
5. **No reducir Equipamiento de 3 a 2 operadores.** Si el frente volumétrico crece, la Célula 2 debe mantener 3 + 3 y crecer, no redistribuirse a 3 + 2.

> **Advertencia honesta: si la plantilla real es 10 y no 9, el déficit de hoy es apenas 0.06 FTE y la contratación inmediata no se sostiene por sí sola; todo el caso pasa a descansar en la expansión y en el pico Lunes-Miércoles. Es otra razón para resolver primero el conteo de cabezas: define si la petición es «necesitamos gente ya» o «necesitamos un plan de contratación atado a las aperturas». Las dos son aprobables; sostener la primera con datos de la segunda, no.**

---

## 11. Reestructuración sugerida del documento

El documento actual mezcla dos propuestas distintas —aumento de plantilla y modelo de gobierno de custodia— y arranca por la metodología en lugar de por la petición. Estructura recomendada:

1. **Resumen ejecutivo (media página).** La petición, el costo, el beneficio, el payback y el riesgo de no actuar. En números. Una junta decide aquí; el resto es respaldo.
2. **Situación actual con datos duros.** Volúmenes, KPI actuales contra objetivo, perfil de carga por día. El gráfico del perfil semanal es la pieza más persuasiva disponible.
3. **Modelo de dotación.** Fórmula, supuestos declarados en tabla, factor de disponibilidad, demanda por generador de volumen, escenarios y sensibilidad.
4. **Alternativas evaluadas y por qué no bastan.** Incluyendo nivelación de carga y horas extra, con costo.
5. **Petición por fases con disparadores**, vinculada a KPI y no a calendario.
6. **Caso financiero.** Costo recurrente contra ahorro recurrente; el REFRESH como caja única.
7. **Plan de implementación.** Células, RACI, hitos, quién mide qué y con qué frecuencia.
8. **Anexos.** Metodología OLE, data cruda, glosario y modelo de custodia.

> **Presentar el modelo de custodia como propuesta separada o como anexo. No requiere presupuesto y demuestra que el equipo ya está mejorando el control con los recursos que tiene. Mezclado con la petición de plantilla se lee como relleno; separado, construye credibilidad para la petición.**

## 12. Correcciones de redacción y presentación

| Texto actual | Problema | Corrección |
|---|---|---|
| «propuesta **irrebatible** de Clase Mundial» | Autopromoción; invita a refutarla | Eliminar. Que lo diga la data |
| «**he procesado** la data… transformar **tu** panorama» | Voz personal y consultiva; parece dirigido al solicitante, no a la junta | Voz institucional: «El área de Almacén presenta…» |
| «Clase Mundial», «blindado», «irrebatible» | Adjetivación repetida sin sustento | Reemplazar por cifras |
| «Eficiencia General de Personal» contra «de los Equipos» | Se contradice; traducción incorrecta de OEE | Usar OLE (Overall Labor Effectiveness) |
| «Capacidad Instalada» | Vocabulario de maquinaria | «Capacidad de mano de obra» o «modelo de dotación» |
| OTIF, ERI, SLA, MP, PT, 5S, ABC, WMS | Siglas sin definir; ERI se define solo en la última página | Definir en el primer uso, más glosario |
| «10.000 piezas muertas» | Informal | «inventario obsoleto y de baja rotación» |
| «el nuevo **elemento**», «los 12 **elementos**» | Deshumanizante | «almacenista», «integrantes del equipo» |
| `$\times$` | Artefacto de LaTeX sin renderizar | × |
| Tablas desmaquetadas | Encabezados partidos, ilegibles al exportar | Rehacer maquetación y verificar el PDF final |
| Sin fecha, autor, versión ni fuente | No es citable ni auditable | Portada con fecha, autor, versión, fuente (WMS/ERP) y periodo medido |
| «Horas-Hombre» | Lenguaje no inclusivo (opcional) | «horas-persona (HP)» |

*Correcciones de redacción*

---

## 13. Anexo: verificación cifra por cifra

Resultado del recálculo independiente de cada cifra publicada en el documento original.

| Cifra del documento | Valor publicado | Valor recalculado | Resultado |
|---|---|---|---|
| Jornada diaria contra horario 8:15-16:45 | 8.25 h | 8.50 h | Discrepancia |
| Horas teóricas semanales (9 pers.) | 371.25 HH | 371.25 HH | Correcto |
| Vacaciones (1 almacenista) | 41.25 HH | 41.25 HH | Correcto |
| Intermitencia por salud (2 pers., −30 %) | 24.75 HH | 24.75 HH | Correcto |
| Curva de aprendizaje (1 nuevo, −40 %) | 16.50 HH | 16.50 HH | Correcto |
| Pérdidas totales | 82.50 HH | 82.50 HH | Correcto |
| Capacidad real efectiva | 288.75 HH | 288.75 HH | Correcto |
| Utilización real | 77.7 % | 77.78 % | Redondeo |
| Pedidos web más cuadro chat | 15.00 HH | 15.00 HH | Correcto |
| Reabastecimiento tienda nueva | 16.25 HH | 16.25 HH | Correcto |
| Consumibles | 25.50 HH | 25.50 HH | Correcto |
| Reabastecimiento PT Manufacturado | 74.25 HH | 74.25 HH | Correcto |
| Reabastecimiento PT Equipamiento | 74.25 HH | 74.25 HH | Correcto |
| Materias primas e insumos | 82.50 HH | 82.50 HH | Correcto |
| Subtotal carga operativa | 287.75 HH | 287.75 HH | Correcto |
| Absorción de la capacidad real | 99.6 % | 99.65 % | Truncamiento |
| Total tareas omitidas | 105.00 HH | 105.00 HH | Correcto |
| Demanda total real | 392.75 HH | 392.75 HH | Correcto |
| Brecha operativa | 104.00 HH | 104.00 HH | Correcto |
| Brecha en FTE | 2.5 | 2.52 | Correcto |
| Personas en la tabla de demanda | 9 (implícito) | 10 nombradas | Contradicción |
| Suma de las células propuestas | 12 | 3+5+2+2 = 12 | Correcto |
| Conteos cíclicos: demanda contra protocolo | 30.0 HH | 24.0 HH | Contradicción |
| Incremento por tienda nueva | 12.5 % constante | 12.5 → 9.1 % decreciente | Error conceptual |

*Verificación completa. Toda la aritmética publicada es correcta; los problemas están en los supuestos y en la consistencia entre secciones.*

![Perfil de carga por día reconstruido desde la tabla del documento (izquierda) y rango de respuestas que la misma data soporta según el supuesto elegido (derecha).](/opt/cursor/artifacts/auditoria_carga_almacen_v4.png)

*Perfil de carga por día reconstruido desde la tabla del documento (izquierda) y rango de respuestas que la misma data soporta según el supuesto elegido (derecha).*

## 14. Resumen de acción

Los tres pasos con mayor impacto sobre la probabilidad de aprobación, en orden:

1. **Resolver «¿son 9 o son 10?» con la nómina firmada.** Define si la petición es «necesitamos gente ya» o «necesitamos un plan atado a las aperturas», y determina si la frase del 99.6 % puede seguir en el documento.
2. **Responder de frente la pregunta de jueves y viernes.** Hay 124.75 HH nominales sin asignar contra 105 HH de tareas omitidas. Hay que explicar con data de asistencia y de atrasos por qué la nivelación de carga no basta.
3. **Rehacer el número con el factor de disponibilidad.** Reemplaza el «3 es el número exacto» por 10.06 FTE hoy y 12.18 a doce meses, con el ratio de una persona por cada dos tiendas como política.

Y eliminar «se autofinancia» del párrafo de retorno hasta tener la tabla de costo recurrente contra ahorro recurrente. Es la frase que un director financiero usará para devolver la propuesta.

---

### Reproducibilidad

- `verificacion_almacen.py` — recálculo independiente de cada cifra publicada, con pruebas de consistencia interna y escenarios alternativos.
- `analisis_avanzado_almacen.py` — sensibilidad cruzada, punto de saturación, atraso acumulado, nivelación de carga y umbral del REFRESH.
- `grafico_carga_almacen.py` — perfil de carga por día y escenarios de dotación.
- `informe_contenido.py` + `generar_informe.py` — fuente única del informe; generan la versión Word y la versión Markdown.
