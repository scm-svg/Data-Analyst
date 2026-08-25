# Revisión crítica: "Propuesta Aumento de Plantilla — Reestructuración Team Almacén Fábrica"

Auditoría de planteamiento, datos, aritmética, metodología y riesgos.
Toda cifra citada aquí fue recalculada de forma independiente con `verificacion_almacen.py`.

---

## 1. Veredicto ejecutivo

**La aritmética está bien; el modelo no.** Todas las sumas y productos del documento cuadran
(371.25 / 288.75 / 287.75 / 105 / 392.75 / 104 / 2.5 FTE). El problema es de **supuestos,
consistencia interna y ausencia de datos duros**, no de calculadora.

En su estado actual, un CFO o un gerente de operaciones con experiencia tumba la propuesta en
menos de diez minutos con tres preguntas. La buena noticia: **la conclusión (llegar a 12
personas) es probablemente correcta**, pero está sostenida por el razonamiento equivocado. Hay
que reconstruir el argumento, no la conclusión.

| Dimensión | Nota | Comentario |
|---|---|---|
| Aritmética | 9/10 | Correcta; solo errores de redondeo menores |
| Consistencia interna | 3/10 | Contradice su propia plantilla, su propia demanda y su propio protocolo |
| Metodología | 4/10 | Invoca OEE pero nunca lo calcula; demanda medida por presencia, no por volumen |
| Calidad de datos | 2/10 | Cero volúmenes, cero tiempos estándar, cero líneas base de KPI, cero dinero |
| Caso de negocio | 2/10 | No hay ni una cifra monetaria en toda la propuesta |
| Riesgo legal / control interno | 3/10 | Datos de salud identificables, responsabilidad colectiva, autoauditoría |
| Redacción / presentación | 5/10 | Tono autopromocional, artefactos de formato, siglas sin definir |

---

## 2. Lo que está bien y hay que conservar

No todo se reescribe. Estos son los activos del documento:

1. **La estructura de células con custodia física por zona.** Es una idea sólida y de verdad
   alineada con buenas prácticas de control de inventario. Vale por sí sola, incluso sin
   contratar a nadie.
2. **Separar carga "del día a día" de carga "estructural omitida".** Es la distinción correcta
   y es lo que hace visible el problema real.
3. **Cuantificar en horas-hombre en lugar de argumentar por percepción.** El instinto es
   correcto: hablar de capacidad y demanda, no de "estamos ahogados".
4. **Ligar cada célula a un KPI propio** (ERI, OTIF, errores de picking). Bien planteado.
5. **Identificar el inventario REFRESH como capital inmovilizado** y no como estorbo. Ese es el
   ángulo financiero que puede vender la propuesta.

---

## 3. Errores e inconsistencias verificadas

### 3.1 La jornada de 8.25 h no coincide con el horario declarado

El documento dice "Jornada teórica diaria: 8.25 horas (8:15 am - 4:45 pm)". Ese horario abarca
**8.50 h**, no 8.25 h.

- Si hay un break de 15 min, hay que declararlo.
- Si hay una hora de comida (lo habitual y en muchos países obligatorio), la jornada neta es
  **7.50 h** y *toda* la base cambia -9%.

Sensibilidad de la capacidad teórica según la jornada real:

| Jornada neta | 9 personas | 10 personas |
|---|---|---|
| 7.50 h (con 1 h de comida) | 337.50 HH | 375.00 HH |
| 8.25 h (documento) | 371.25 HH | 412.50 HH |
| 8.50 h (span literal del horario) | 382.50 HH | 425.00 HH |

Este es el número del que cuelga todo el modelo y es el único que nadie verificó. Hay que
cerrarlo con el reglamento interno y el reloj de asistencia, y declarar el break explícitamente.

### 3.2 Contradicción de plantilla: la capacidad usa 9 personas, la demanda usa 10

- Capacidad: `9 × 41.25 = 371.25 HH` → habla de 9 almacenistas.
- Tabla de demanda: llega hasta **"Almacenistas 9 y 10"** en Materias Primas. Contando cabezas
  nombradas en la tabla salen **10 personas**.

Esto no es un detalle de forma, es el corazón del argumento. Si la plantilla real es 10:

| | Con 9 personas (documento) | Con 10 personas (tabla real) |
|---|---|---|
| Capacidad real efectiva | 288.75 HH | 330.00 HH |
| Absorción del día a día | **99.6%** | **87.2%** |
| Brecha total | 104.00 HH | 62.75 HH |
| FTE solicitados | 2.52 | **1.52** |

La frase estelar de la propuesta ("absorbe el 99.6% ... matemáticamente es imposible") **se cae
sola** si la plantilla es de 10. Y el título dice "de 9 a 12", o sea +3, lo que sugiere que 9 es
la cifra correcta y la tabla está mal numerada. Hay que resolverlo con la nómina en mano antes
de que lo resuelva la junta.

### 3.3 Se compara demanda bruta contra capacidad neta

La demanda (287.75 HH) son horas de presencia asignada de gente trabajando **al 100%**. La
capacidad (288.75 HH) es la misma gente **descontada al 77.8%**. Se están comparando dos cosas
medidas con reglas distintas, y la comparación está construida para que el resultado sea 99.6%.

Peor: la demanda se derivó del **horario que ya tienen asignado**, no de un cálculo
independiente de trabajo requerido. Es circular. "Necesitamos 287.75 HH porque es lo que están
haciendo" no prueba que ese trabajo requiera 287.75 HH; prueba que ocupan ese tiempo. Un
gerente escéptico dirá exactamente eso.

### 3.4 Pérdidas transitorias tratadas como permanentes

Las tres deducciones tienen naturaleza distinta y se suman como si fueran iguales:

| Deducción | HH/semana | ¿Es permanente? |
|---|---|---|
| Vacaciones (1 persona completa) | 41.25 | **No.** Es rotativo. 15 días/año sobre 9 personas = 5.8% estructural, no 11.1% |
| Intermitencia por salud (2 pers., -30%) | 24.75 | Depende. Si hay restricción médica documentada, sí; si es ausentismo, es gestión de RR. HH. |
| Curva de aprendizaje (1 nuevo, -40%) | 16.50 | **No.** Se extingue al madurar el aprendizaje |

Descontar una persona completa de vacaciones **todas las semanas del año** sobrestima el efecto:
9 personas × 15 días = 135 días/año de ausencia, que sobre 2 340 días-persona es **5.8%**, no
el 11.1% que implica la deducción del documento.

La forma correcta y estándar es un **factor de disponibilidad** aplicado uniformemente
(sección 8), no deducciones ad hoc por persona.

### 3.5 Los 3 nuevos se computan al 100% mientras los actuales al 77.8%

Aquí hay un doble estándar que se ve a simple vista:

- Brecha a cubrir: 104 HH.
- Aporte de 3 personas **si sufren las mismas pérdidas** que el resto:
  `3 × 41.25 × 0.778 = 96.25 HH` → **no alcanza**.
- FTE realmente necesarios con ese criterio: `104 / (41.25 × 0.778) = 3.24` → **serían 4**.
- Y si las pérdidas son transitorias (la lectura contraria), la brecha baja a 21.50 HH = **0.52
  FTE** → **sería 1**.

O sea: el mismo modelo, con supuestos internamente coherentes, produce 1 o 4, pero no 3. El
número 3 no se deriva de nada: se afirma. Llamarlo **"el número exacto"** es indefendible y es
la frase que más va a doler en la junta.

### 3.6 El hallazgo más peligroso: hoy hay 124.75 HH nominales sin asignar

Reconstruyendo la asignación día por día desde la propia tabla del documento:

| | Lun | Mar | Mié | Jue | Vie | Total |
|---|---|---|---|---|---|---|
| Carga asignada | 80.50 | 80.50 | 75.25 | 25.75 | 25.75 | 287.75 |
| Capacidad nominal (10 pers.) | 82.50 | 82.50 | 82.50 | 82.50 | 82.50 | 412.50 |
| **Horas sin asignar** | 2.00 | 2.00 | 7.25 | **56.75** | **56.75** | **124.75** |
| Utilización | 98% | 98% | 91% | **31%** | **31%** | 70% |

Los seis almacenistas de PT y Equipamiento tienen **jueves y viernes completos sin asignación**
(99 HH). Sumado al resto: **124.75 HH nominales libres por semana**.

Las tareas omitidas que se reclaman son **105.0 HH**. En el papel, **caben dentro del tiempo que
ya existe**.

Y el propio documento lo admite cuando dice que la Célula 2 "tiene los días jueves y viernes
libres de picking masivo para realizar 5S y conteos cíclicos ABC". Es decir: la propuesta
reconoce el tiempo libre y lo usa como solución, pero el diagnóstico lo omite para poder
declarar un déficit del 99.6%.

**Esta es la pregunta que hunde la propuesta:** *"si tus operadores de PT no tienen asignación
jueves y viernes, ¿por qué necesito contratar a alguien para los conteos cíclicos?"*.
Hay que responderla **de frente y en el cuerpo del documento**, no esperar que no la hagan. Las
respuestas legítimas existen (concentración de ausencias en esos días, jornadas de recuperación
de atrasos del pico Lun-Mié, tareas que requieren perfil o accesos distintos, el pico real de
recepción). Pero hay que sustentarlas con la data de asistencia y de atrasos.

### 3.7 La propuesta reduce el pico de picking mientras afirma que el volumen crece

- Hoy: PT Manufacturado + Equipamiento = 3 + 3 = **6 operadores** los Lun-Mié → `6 × 3 × 8.25 = 148.50 HH`.
- Propuesto (Célula 2): "3 en PT Manufacturado y 2 en Equipamiento Volumétrico" = **5
  operadores** → `5 × 3 × 8.25 = 123.75 HH`.
- Variación: **-24.75 HH en el pico**, justo en el frente donde se dice que el volumen crecerá
  12.5% por trimestre. Y el recorte cae sobre **Equipamiento Volumétrico** (3 → 2), que es
  precisamente el material más difícil de manipular.

Se está pidiendo gente para atender crecimiento y, en el mismo documento, se le quita un
operador al frente que crece. Es autodestructivo.

### 3.8 REFRESH: un proyecto finito contabilizado como carga permanente

Las 40 HH/semana del Proyecto REFRESH son **38% de las 105 HH omitidas** y se usan para
justificar plantilla permanente. Pero son 10 000 piezas: es un trabajo con fin.

| Ritmo supuesto | HH totales | Duración a 40 HH/semana |
|---|---|---|
| 20 piezas/HH | 500 HH | 12.5 semanas |
| 30 piezas/HH | 333 HH | 8.3 semanas |
| 40 piezas/HH | 250 HH | 6.2 semanas |

El documento **no declara el ritmo de procesamiento**, que es justo el dato que convierte
"40 HH/semana" en una cifra auditable. Y financiar una nómina indefinida con un proyecto de
~2-3 meses es exactamente el tipo de cosa que un CFO detecta y castiga. Corresponde **recurso
temporal, horas extra u outsourcing**, no headcount permanente.

Además, la Célula 4 asigna 2 personas fijas (82.5 HH) a devoluciones + REFRESH cuando la
demanda declarada de ese frente es 60 HH. Cuando REFRESH termine, esa célula queda con 20 HH de
trabajo y 82.5 HH de capacidad.

### 3.9 El "12.5% por trimestre" no es constante

Una tienda nueva sobre 8 es 12.5%, pero la base crece:

| Trimestre | Tiendas | Incremento | Carga adicional |
|---|---|---|---|
| T1 | 8 → 9 | 12.5% | +18.56 HH |
| T2 | 9 → 10 | 11.1% | +18.56 HH |
| T3 | 10 → 11 | 10.0% | +18.56 HH |
| T4 | 11 → 12 | 9.1% | +18.56 HH |
| **Total 12 meses** | **8 → 12** | **+50%** | **+74.25 HH/semana** |

Lo importante: en HH la carga es lineal (~18.56 HH por tienda), no porcentual. Usar porcentajes
sobre base móvil es un error conceptual que, encima, **no hace falta**: la cifra en horas es más
sencilla y más defendible.

Y al aplicarla: `104 HH (brecha) + 74.25 HH (expansión) = 178.25 HH = 4.32 FTE`. Con sus propios
supuestos, **3 personas no cubren el año**. La propuesta se sabotea al insistir en que 3 es
exacto.

Detalle relacionado: la línea "Reabastecimiento Tienda Nueva (cada 3 meses) = 16.25 HH" es muy
cercana a los 18.56 HH/tienda del estándar. Eso sugiere que **ya es la tienda 9 en régimen**, no
un evento trimestral. Si es así, la base real es 9 tiendas y la etiqueta "cada 3 meses" induce a
error (y puede leerse como doble conteo).

### 3.10 Conteos cíclicos: dos cifras que no cuadran

- Demanda declarada: **30.0 HH/semana**.
- Protocolo declarado: "cada viernes las células dedican las últimas 2 horas" = `12 × 2 = **24.0
  HH/semana**`.

Faltan 6 HH. Si alguien cruza las dos secciones, encuentra que el protocolo propuesto no cubre
la demanda que el mismo documento definió.

### 3.11 Consumibles está asignado a dos células, y la Célula 3 queda sobredimensionada

- La **Célula 1** aparece en la tabla de custodia como responsable de la "Jaula de Consumibles
  (Empaques/Taller)".
- La **Célula 3** dice en su justificación que "unifica los pedidos de la web, cuadro chat **y la
  entrega de consumibles** a tiendas y backoffice".

El mismo frente está en dos células. Y eso importa porque define si la Célula 3 tiene trabajo:

| Célula | Ops | Capacidad nominal | Demanda mapeada | Utilización |
|---|---|---|---|---|
| 1: MP + Insumos + Consumibles | 3 | 123.75 HH | 108.00 HH | 87% |
| 2: PT + Equipamiento + Rampa | 5 | 206.25 HH | 164.75 HH | 80% |
| 3: E-commerce + Chat (+ Consumibles?) | 2 | 82.50 HH | 15.00 - 40.50 HH | **18% - 49%** |
| 4: Logística Inversa + REFRESH | 2 | 82.50 HH | 60.00 HH | 73% |

Con los propios números del documento, la Célula 3 usa entre el 18% y el 49% de su capacidad,
según dónde se cuenten los consumibles. Es la célula más fácil de recortar para quien quiera
rechazar la propuesta, y encima es la que tiene el SLA más agresivo (< 24 h). Hay que sustentarla
con volúmenes de pedidos web y proyección de crecimiento del canal digital, que hoy no aparecen
en ninguna parte, o redistribuir el alcance.

También conviene notar que la línea "Reabastecimiento Tienda Nueva" (16.25 HH) **no queda
asignada explícitamente a ninguna célula** en la estructura nueva. Cada HH de la demanda debe
tener un dueño en el organigrama propuesto; si no, la tabla de demanda y la de células no son
comparables.

### 3.12 Errores menores de redondeo y formato

- `288.75 / 371.25 = 77.78%` → el documento dice **77.7%**, debe ser **77.8%**.
- `287.75 / 288.75 = 99.65%` → el documento lo trunca a "99.6%".
- `104 / 41.25 = 2.52` → "2.5" es aceptable, pero conviene mostrar el decimal.
- Aparece el artefacto de LaTeX **`$\times$`** en dos filas de la tabla (debe ser "×").
- Las tablas quedaron desmaquetadas al exportar; los encabezados se parten a media palabra.
- "Solo 77.7% de utilización real utilizable" — redundancia ("real utilizable").

---

## 4. Debilidades metodológicas

### 4.1 Se invoca OEE y nunca se calcula

El documento define OEE = Disponibilidad × Desempeño × Calidad, y después **no presenta ni un
solo valor de los tres factores**. El único número que aparece (77.8%) es *utilización de
horas*, es decir apenas una aproximación a Disponibilidad. Prometer una metodología y no
ejecutarla es peor que no mencionarla: invita a que pregunten por los factores que faltan.

Además hay un error de traducción: la portada dice *"OEE (Overall Equipment Effectiveness /
**Eficiencia General de Personal**)"* y en el marco teórico dice *"Eficiencia General de los
**Equipos**"*. Se contradice a sí mismo en dos páginas. Para personas la métrica correcta es
**OLE (Overall Labor Effectiveness)**. Usar OLE, definirla bien y calcularla:

```
OLE = Disponibilidad × Desempeño × Calidad
    = (horas trabajadas / horas contratadas)
    × (producción real / estándar esperado)
    × (1 - tasa de error)
```

Con datos plausibles: `0.85 × 0.90 × 0.97 = 74%`. Ese sí es un número que sostiene una
conversación.

Nota terminológica: "Capacidad Instalada" es vocabulario de planta y maquinaria. Para personas,
"capacidad de mano de obra" o "modelo de dotación".

### 4.2 La demanda no está construida sobre generadores de volumen

Esta es la falla metodológica de fondo. Una demanda defendible se construye así:

```
HH requeridas = Σ (volumen_i × tiempo_estándar_i)
FTE requeridos = HH requeridas / (h_semana × factor_disponibilidad)
```

El documento no tiene ni volúmenes ni tiempos estándar. Sin ellos no se puede responder la
pregunta obvia: **¿el equipo actual es productivo?** Y sin esa respuesta, la contrapropuesta
natural de la gerencia es *"mejora la productividad antes de pedir gente"*.

Vale la pena notar que los 18.56 HH por tienda por semana equivalen a más de dos jornadas
completas de una persona **por tienda**. Puede ser correcto, pero es una cifra alta que exige
sustento en unidades movidas.

### 4.3 El promedio semanal esconde el problema real

El modelo es un promedio semanal, y por eso no ve que el problema real es de **pico y
distribución**, no de volumen total: Lun-Mié al 91-98% y Jue-Vie al 31%. Un modelo así puede
mostrar capacidad suficiente mientras los lunes se caen.

Esto abre además la alternativa más obvia y que el documento no menciona: **nivelar la carga**.
Repartir las 148.5 HH de reabastecimiento de PT y Equipamiento en 5 días en lugar de 3 baja el
requerimiento de 6 operadores/día a ~3.6 operadores/día en ese frente. Si hay una restricción
que lo impide (calendario de transporte, ventanas de recepción en tienda, días de corte de
producción), **hay que declararla explícitamente**, porque es la primera cosa que va a proponer
cualquiera que lea el perfil por día.

### 4.4 No se verifica si la restricción es la gente

Se asume que el cuello de botella es mano de obra. Puede no serlo. Si hay un solo montacargas,
dos andenes o escáneres insuficientes, **contratar tres personas no aumenta el throughput**, solo
agrega gente esperando. Antes de pedir plantilla hay que descartar restricciones de equipo,
andén, espacio y sistema (WMS/ERP). Si el cuello de botella es equipo, la propuesta correcta es
otra y es más barata.

### 4.5 No hay análisis de alternativas

Ninguna junta aprueba plantilla permanente sin ver las opciones descartadas. Faltan como mínimo:
horas extra, personal temporal, nivelación de carga, cambio de frecuencia de reparto,
tercerización del REFRESH, mejoras de WMS/picking por olas, cross-docking. Hay que ponerlas en
una tabla con costo y por qué no resuelven (o sí resuelven parcialmente).

### 4.6 No hay escenarios ni sensibilidad

Un solo escenario puntual. Falta base/optimista/pesimista sobre los dos supuestos que mueven
todo: jornada neta y ritmo de apertura de tiendas.

---

## 5. El caso de negocio: el hueco más grande

**No hay una sola cifra monetaria en las 8 páginas.** Se pide plantilla permanente sin decir
cuánto cuesta ni cuánto devuelve. Eso, para una junta directiva, es motivo suficiente de
rechazo.

Y el párrafo de ROI tiene un error financiero de concepto:

> "La incorporación de 3 operadores **se autofinancia** liberando las 10.000 piezas del Proyecto
> Refresh"

Liberar inventario genera **caja una sola vez**. Los salarios son **gasto recurrente**. Un
ingreso único no financia un costo permanente. Esa frase, tal como está, le da al CFO la
oportunidad de rechazar la propuesta usando su propio argumento.

La estructura correcta separa las dos cosas:

| Concepto | Tipo | Cómo cuantificarlo |
|---|---|---|
| 3 almacenistas (salario + carga social + dotación) | Costo recurrente | Nómina × 12 |
| Horas extra evitadas | Ahorro recurrente | HH extra actuales × tarifa |
| Reducción de merma por conteos cíclicos | Ahorro recurrente | Merma anual × % de reducción esperada |
| Venta perdida evitada por quiebre de stock | Ingreso recurrente | Quiebres × ticket × margen |
| Liberación de las 10 000 piezas REFRESH | **Caja única** | Piezas × costo × % recuperación |

Solo con esa tabla se puede decir "el costo recurrente se paga con ahorros recurrentes, y el
REFRESH acelera el payback en X meses". Ese es un argumento aprobable.

---

## 6. Riesgos legales, laborales y de control interno

### 6.1 Datos de salud de personas identificables

"Intermitencia por Salud en Equipamiento (2 Almacenistas): -30% de disponibilidad". En un
almacén con 9 personas, eso identifica a individuos concretos y expone información médica en un
documento que circulará por la junta. Es un riesgo de protección de datos y de discriminación
laboral. Reemplazar por: *"2 posiciones con restricciones operativas documentadas por medicina
laboral (-30% de disponibilidad efectiva)"*, y llevar el detalle en un anexo confidencial de
RR. HH.

### 6.2 Responsabilidad colectiva y "guardián legal"

"Es el **guardián legal** y operativo" / "la responsabilidad recae directamente sobre la célula
custodia". En la mayoría de legislaciones laborales de la región **no se puede imponer
responsabilidad patrimonial colectiva** ni descontar diferencias de inventario del salario sin
un procedimiento formal. Hay que:

- cambiar "guardián legal" por **"responsable operativo y administrativo"**;
- definir un procedimiento documentado de investigación de diferencias con debido proceso;
- validar la redacción con RR. HH. y con el área legal **antes** de presentarla.

### 6.3 Contradicción: la responsabilidad por célula también es responsabilidad diluida

El párrafo de cierre promete *"eliminamos la 'responsabilidad diluida'"*, pero el modelo asigna
la responsabilidad a un **grupo de 3 a 5 personas**. Responsabilidad de grupo *es*
responsabilidad diluida: cuando falte una pieza en la Célula 2, hay cinco personas y ningún
responsable.

Corrección: **custodio nombrado por ubicación y por turno**, con acta de relevo firmada en cada
cambio, y control dual (dos firmas) en las transferencias entre células. Eso sí elimina la
dilución.

### 6.4 La autoauditoría rompe la segregación de funciones

"Cada célula dedica las últimas 2 horas a auditar **su propia ubicación** (Self-Audit)". El
custodio contando su propio stock es un control débil: quien puede causar la diferencia no debe
ser quien la reporta. Cualquier auditor lo marca de inmediato.

Corrección: **conteo cruzado** (la Célula 1 cuenta a la 2 y viceversa), con validación y
muestreo independiente por el Analista de Inventarios. El autoconteo sirve como control interno
de la célula, pero no como el conteo cíclico oficial.

### 6.5 El acceso restringido choca con la cobertura de ausencias

"Acceso restringido únicamente para los almacenistas asignados a esa Célula" entra en conflicto
directo con el argumento de la Célula 2 ("se absorben las bajas por ausentismo y vacaciones") y
crea puntos únicos de falla cuando la célula completa está ausente. También hay que revisar
accesos de emergencia y evacuación.

Corrección: matriz de delegación de custodia con acta de traspaso temporal, más un plan de
polivalencia (cross-training) documentado.

### 6.6 Juicios subjetivos sobre el personal

"Aliviar la lenta curva del nuevo elemento y **la baja responsabilidad reportada**". Esto es
subjetivo, no está sustentado, y **le da a la gerencia un argumento en contra**: si el problema
es desempeño o responsabilidad, la respuesta es gestión de desempeño, no contratar más gente.
Eliminar o reemplazar por métricas (líneas/hora, tasa de error, cumplimiento de conteos).

### 6.7 Metas absolutas no medibles

"**Cero Averías** en Carga" no es una meta gestionable. Usar "< 0.1% de unidades dañadas en
carga". Y ninguno de los KPI tiene **línea base**: se piden ERI > 98%, OTIF > 95% y errores de
picking < 0.5% sin decir en cuánto están hoy, con lo cual es imposible demostrar mejora ni medir
el retorno.

---

## 7. Datos que faltan y hay que levantar antes de presentar

Sin esto la propuesta es opinión bien formateada. Con esto es irrebatible de verdad.

**Generadores de volumen (últimas 8-13 semanas, del WMS/ERP)**
- Líneas y pedidos por día, por canal (tienda, web, chat, corporativo).
- Unidades y bultos despachados por tienda por semana.
- Recepciones por día: contenedores, pallets, bultos, órdenes de compra.
- Devoluciones recibidas por semana y su antigüedad de proceso.
- Órdenes de producción atendidas por día (MP).

**Tiempos estándar** (estudio de tiempos o timestamps del WMS)
- Minutos por línea de picking, por tipo de producto (manufacturado vs. volumétrico).
- Minutos por bulto en recepción, conteo y control de calidad.
- Minutos por SKU en conteo cíclico.

**Personas**
- Asistencia y ausentismo real de los últimos 12 meses (esto reemplaza los supuestos del -30%).
- Horas extra pagadas y su costo (este es el argumento monetario más fácil de conseguir).
- Rotación y tiempo real de maduración de un almacenista nuevo (esto sustenta o descarta el -40%).
- Nómina de plantilla actual firmada: **¿son 9 o son 10?**

**Desempeño actual (líneas base)**
- OTIF a tiendas, ERI por familia, exactitud de picking, dock-to-stock, backlog en HH.

**Dinero**
- Valuación del inventario REFRESH y escenarios de recuperación.
- Merma / ajustes de inventario de los últimos 12 meses.
- Costo total anual de un almacenista (salario + cargas + dotación).

**Restricciones físicas**
- Montacargas, escáneres, andenes, ventanas de recepción, metros de rack disponibles.

---

## 8. Modelo recomendado (mismo objetivo, argumento defendible)

Sustituir las deducciones ad hoc por un **factor de disponibilidad** estándar:

| Componente | % |
|---|---|
| Vacaciones (15 días / 260) | 5.77 |
| Feriados (11 días / 260) | 4.23 |
| Ausentismo | 3.00 |
| Formación y reuniones | 2.00 |
| **Factor de disponibilidad** | **85.0** |

`HH efectivas por FTE = 41.25 × 0.85 = 35.06 HH/semana`

**Demanda recurrente** (excluyendo REFRESH, que es proyecto):
`287.75 + 30 (conteos) + 15 (5S) + 20 (devoluciones) = 352.75 HH`

| Escenario | Cálculo | FTE requeridos |
|---|---|---|
| Situación actual | 352.75 / 35.06 | **10.06** |
| A 12 meses (+4 tiendas, +74.25 HH) | 427.00 / 35.06 | **12.18** |

**Conclusión: 12 personas es el número correcto, pero por razones distintas a las del
documento.** El modelo así construido sobrevive el escrutinio, mientras el actual no.

El costo marginal por tienda queda además en una cifra limpia y fácil de defender:
`18.56 HH / 35.06 HH = 0.53 FTE por tienda nueva`, es decir **un almacenista por cada dos
tiendas que se abran**. Ese ratio es reutilizable en cada apertura futura y convierte la
propuesta en una política, no en una pelea recurrente.

Eso permite una petición mucho más vendible, por fases y con disparadores objetivos:

1. **+1 almacenista ahora**, que es lo que el modelo sostiene contra una plantilla de 9
   (10.06 requeridos - 9 actuales = 1.06 FTE), para arrancar conteos cíclicos, 5S y devoluciones
   de forma sostenible.
2. **+1 por cada dos tiendas nuevas** (0.53 FTE/tienda), con gatillo por KPI (OTIF < 95% o
   backlog > X HH) y no por calendario. Con 4 aperturas: +2 adicionales → **12 personas al cabo
   de las 4 aperturas**, que es exactamente el objetivo de la propuesta original.
3. **Recurso temporal dedicado al REFRESH** (6 a 13 semanas según el ritmo real), financiado
   contra la caja liberada del propio inventario. Este es el punto más fuerte de la propuesta y
   el más fácil de aprobar, porque se autofinancia de verdad.
4. **Nivelar la carga Lun-Mié → Lun-Vie** antes o en paralelo, y reportar el resultado. Muestra
   que se agotó la eficiencia antes de pedir plantilla, que es exactamente lo que la gerencia
   quiere ver.

Advertencia honesta sobre este modelo: **si la plantilla real es 10 y no 9**, el déficit de hoy
es apenas 0.06 FTE y la contratación inmediata no se sostiene por sí sola; todo el caso pasa a
descansar en la expansión y en el pico Lun-Mié. Es otra razón para resolver primero el conteo de
cabezas: define si la petición es "necesitamos gente ya" o "necesitamos un plan de contratación
atado a las aperturas". Las dos son aprobables; sostener la primera con datos de la segunda, no.

Además: **no reducir Equipamiento de 3 a 2**. Si el frente volumétrico crece, la Célula 2 debe
mantener 3 + 3 y crecer, no redistribuirse a 3 + 2.

---

## 9. Reestructuración sugerida del documento

El documento actual mezcla dos propuestas distintas (aumento de plantilla + modelo de gobierno
de custodia) y arranca por la metodología en lugar de por la petición. Estructura recomendada:

1. **Resumen ejecutivo (media página).** La petición, el costo, el beneficio, el payback y el
   riesgo de no actuar. En números. Una junta decide aquí; el resto es respaldo.
2. **Situación actual con datos duros.** Volúmenes, KPI actuales vs. objetivo, perfil de carga
   por día (el gráfico del perfil semanal es la pieza más persuasiva que tienes).
3. **Modelo de dotación.** Fórmula, supuestos declarados en tabla, factor de disponibilidad,
   demanda por generador de volumen, escenarios y sensibilidad.
4. **Alternativas evaluadas y por qué no bastan.** Incluyendo nivelación de carga y horas extra,
   con costo.
5. **Petición por fases con disparadores.** Vinculada a KPI, no a calendario.
6. **Caso financiero.** Costo recurrente vs. ahorro recurrente; el REFRESH como caja única.
7. **Plan de implementación.** Células, RACI, hitos, quién mide qué y cada cuánto.
8. **Anexos.** Metodología OLE, data cruda, glosario, modelo de custodia.

**Presentar el modelo de custodia como propuesta separada (o anexo).** No requiere presupuesto y
demuestra que el equipo ya está mejorando el control con los recursos que tiene. Mezclado con la
petición de plantilla, se lee como relleno; separado, construye credibilidad para la petición.

---

## 10. Correcciones de redacción y presentación

| Actual | Problema | Corrección |
|---|---|---|
| "propuesta **irrebatible** de Clase Mundial" | Autopromoción; invita a refutarla | Eliminar. Que lo diga la data |
| "**he procesado** la data... transformar **tu** panorama" | Voz personal/consultiva; parece dirigido al solicitante, no a la junta | Voz institucional: "El área de Almacén presenta..." |
| "Clase Mundial", "blindado", "irrebatible" (repetidos) | Adjetivación sin sustento | Reemplazar por cifras |
| "Eficiencia General de Personal" vs. "de los Equipos" | Se contradice; traducción incorrecta de OEE | Usar **OLE (Overall Labor Effectiveness)** |
| "Capacidad Instalada" | Vocabulario de maquinaria | "Capacidad de mano de obra" / "modelo de dotación" |
| OTIF, ERI, SLA, MP, PT, 5S, ABC, WMS | Siglas sin definir; ERI se define solo en la última página | Definir en el primer uso + glosario |
| "10.000 piezas muertas" | Informal | "inventario obsoleto y de baja rotación" |
| "el nuevo **elemento**", "los 12 **elementos**" | Deshumanizante | "almacenista", "integrantes del equipo" |
| "$\times$" | Artefacto de LaTeX sin renderizar | "×" |
| Tablas desmaquetadas | Encabezados partidos, ilegibles al exportar | Rehacer maquetación y verificar el PDF final |
| Sin fecha, autor, versión, fuente ni periodo de datos | No es citable ni auditable | Portada con fecha, autor, versión, fuente (WMS/ERP) y periodo medido |
| "Horas-Hombre" | Lenguaje no inclusivo (opcional) | "horas-persona (HP)" |

---

## 11. Los tres golpes que hay que blindar antes de presentar

Si solo se corrige una cosa, que sean estas tres, en este orden:

1. **"¿Son 9 o son 10?"** Tu capacidad dice 9 y tu tabla dice 10. Con 10, tu propia brecha baja
   de 2.5 a 1.5 FTE y la frase del 99.6% desaparece. Resuélvelo con la nómina.
2. **"Tus operadores de PT no tienen nada asignado jueves y viernes: 124.75 HH libres contra
   105 HH de tareas omitidas."** Contéstalo en el documento, con la data de asistencia y de
   atrasos, y explica por qué la nivelación de carga no basta.
3. **"¿Por qué 3 y no 1 o 4?"** Hoy el 3 no se deriva de nada. Con el modelo de disponibilidad
   del punto 8 sí se deriva, y encima llega a 12 personas, que es lo que quieres.

Y elimina "se autofinancia" del párrafo de ROI hasta que tengas la tabla de costo recurrente
contra ahorro recurrente. Es la frase que un CFO usará para devolverte la propuesta.

---

### Reproducibilidad

- `verificacion_almacen.py` — recálculo independiente de las 30+ cifras del documento, con
  pruebas de consistencia y escenarios alternativos.
- `grafico_carga_almacen.py` — perfil de carga por día y comparación de escenarios de dotación.
