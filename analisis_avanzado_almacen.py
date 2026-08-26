"""Analisis complementario de la propuesta de plantilla del Almacen Fabrica.

Cubre lo que el documento original no modela:
  A. Sensibilidad cruzada: jornada neta x factor de disponibilidad.
  B. Punto de saturacion de la estructura de 12 personas.
  C. Modelo de acumulacion de atraso (cuantifica el 'riesgo de no actuar').
  D. Escenario de nivelacion de carga Lun-Mie -> Lun-Vie.
  E. Plantilla del caso financiero con formulas explicitas.
  F. Umbral de rentabilidad del Proyecto REFRESH.
"""

JORNADA_DOC = 8.25
SEMANA_DOC = JORNADA_DOC * 5
DEMANDA_DIA_A_DIA = 287.75
OMITIDAS_RECURRENTES = 30 + 15 + 20   # conteos + 5S + devoluciones
REFRESH_HH = 40                        # carga semanal declarada, proyecto finito
HH_POR_TIENDA = (74.25 + 74.25) / 8


def titulo(t):
    print("\n" + "=" * 100)
    print(t)
    print("=" * 100)


# ---------------------------------------------------------------- A
titulo("A. SENSIBILIDAD CRUZADA: FTE REQUERIDOS SEGUN JORNADA Y DISPONIBILIDAD")

print("""La demanda del documento esta medida por PRESENCIA asignada, asi que la parte
'dia a dia' (287.75 HH) escala con la jornada; las tareas omitidas (65 HH recurrentes)
son trabajo absoluto y no escalan. El cuadro muestra los FTE totales requeridos.
""")

jornadas = [7.50, 8.00, 8.25, 8.50]
disponibilidades = [0.78, 0.82, 0.85, 0.88, 1.00]

print(f"{'Jornada neta':>14s} |" + "".join(f"{int(d*100):>10d}%" for d in disponibilidades))
print("-" * 14 + "-+" + "-" * (11 * len(disponibilidades)))
for j in jornadas:
    semana = j * 5
    # el dia a dia se re-expresa a la nueva jornada; lo omitido es fijo
    demanda = DEMANDA_DIA_A_DIA * (j / JORNADA_DOC) + OMITIDAS_RECURRENTES
    fila = f"{j:>10.2f} h   |"
    for d in disponibilidades:
        fila += f"{demanda / (semana * d):>11.2f}"
    print(fila)

vals = [
    (DEMANDA_DIA_A_DIA * (j / JORNADA_DOC) + OMITIDAS_RECURRENTES) / (j * 5 * d)
    for j in jornadas for d in disponibilidades
]
print(f"\n  Rango de resultados: de {min(vals):.2f} a {max(vals):.2f} FTE.")
print(f"  Amplitud = {max(vals)-min(vals):.2f} FTE  ->  mas de 2 personas y media de diferencia solo por")
print("  definir la jornada y la disponibilidad. Por eso hay que fijarlos con evidencia antes")
print("  de discutir cualquier numero de contrataciones.")
print("\n  Observacion clave: la jornada casi no mueve el resultado (0.27 FTE entre 7.50 h y")
print("  8.50 h) porque afecta a demanda y capacidad a la vez. El factor de disponibilidad SI")
print("  lo mueve (2.4 FTE entre 78% y 100%). Ese es el supuesto que hay que blindar con la")
print("  data real de asistencia de los ultimos 12 meses.")

# ---------------------------------------------------------------- B
titulo("B. PUNTO DE SATURACION DE LA ESTRUCTURA PROPUESTA (12 PERSONAS)")

DISP = 0.85
hh_fte = SEMANA_DOC * DISP
print(f"  Capacidad efectiva por persona = {SEMANA_DOC:.2f} x {DISP:.2f} = {hh_fte:.2f} HH/semana")

for plantilla in (9, 10, 12, 13, 14):
    cap = plantilla * hh_fte
    base = DEMANDA_DIA_A_DIA + OMITIDAS_RECURRENTES
    tiendas_extra = (cap - base) / HH_POR_TIENDA
    print(f"  Plantilla {plantilla:2d}: capacidad {cap:6.2f} HH -> soporta {8 + tiendas_extra:5.1f} tiendas "
          f"({tiendas_extra:+5.1f} sobre las 8 actuales)")

cap12 = 12 * hh_fte
base = DEMANDA_DIA_A_DIA + OMITIDAS_RECURRENTES
sat = (cap12 - base) / HH_POR_TIENDA
print(f"\n  >>> Con 12 personas la capacidad se agota en la tienda {8 + sat:.1f}: cubre con holgura")
print(f"      hasta la tienda 11 y queda al limite al abrir la 12a.")
print(f"  >>> A razon de 1 tienda por trimestre, la 13a persona se necesita al abrir la tienda")
print(f"      12, es decir al cierre del mismo ano que cubre el plan.")
print(f"  >>> Conclusion: 12 no es la solucion 'del ano', es la solucion HASTA la tienda 11-12.")
print(f"      Decirlo de frente da credibilidad y evita volver a pedir plantilla sin aviso.")
print(f"      Mejor aun: convertirlo en politica -> 1 almacenista por cada {HH_POR_TIENDA/hh_fte:.2f} FTE/tienda")
print(f"      = 1 persona por cada {hh_fte/HH_POR_TIENDA:.1f} tiendas nuevas, aprobado de antemano.")

# ---------------------------------------------------------------- C
titulo("C. MODELO DE ACUMULACION DE ATRASO (CUANTIFICA EL 'RIESGO DE NO ACTUAR')")

print("""El documento afirma que el OTIF colapsara por debajo del 75%, pero no lo modela.
Un modelo de atraso acumulado es simple y verificable: si la demanda excede la
capacidad, el trabajo no hecho no desaparece, se acumula.
""")

escenarios_deficit = {
    "Deficit del documento (9 pers.)": 104.00,
    "Deficit corregido (10 pers.)": 62.75,
    "Deficit recurrente sin REFRESH (10 pers.)": (DEMANDA_DIA_A_DIA + OMITIDAS_RECURRENTES) - 330.00,
}

for nombre, deficit in escenarios_deficit.items():
    print(f"\n  {nombre}: {deficit:+.2f} HH/semana")
    if deficit <= 0:
        print("    Sin deficit: no hay acumulacion de atraso. El argumento debe apoyarse en el")
        print("    pico Lun-Mie y en la expansion, no en un deficit agregado.")
        continue
    for semanas in (4, 13, 26, 52):
        acum = deficit * semanas
        print(f"    A {semanas:2d} semanas: {acum:8.2f} HH de atraso = "
              f"{acum/SEMANA_DOC:6.2f} semanas-persona de trabajo pendiente")

print("\n  Uso recomendado: presentar el atraso acumulado en HH y traducirlo a consecuencia")
print("  medible (dias de retraso en reposicion, SKU sin contar, devoluciones sin procesar).")
print("  Eso reemplaza la afirmacion 'el OTIF colapsara' por una proyeccion auditable.")

# ---------------------------------------------------------------- D
titulo("D. ESCENARIO DE NIVELACION DE CARGA (LA ALTERNATIVA QUE FALTA)")

carga_pt = 74.25 + 74.25
print(f"  Reabastecimiento PT + Equipamiento = {carga_pt:.2f} HH/semana")
for dias in (3, 4, 5):
    hh_dia = carga_pt / dias
    ops = hh_dia / JORNADA_DOC
    print(f"    Repartido en {dias} dias: {hh_dia:5.2f} HH/dia = {ops:4.2f} operadores/dia "
          f"(hoy se usan 6.00 los Lun-Mie)")

ops_5d = (carga_pt / 5) / JORNADA_DOC
print(f"\n  Al pasar de 3 a 5 dias, el pico baja de 6.00 a {ops_5d:.2f} operadores/dia.")
print(f"  Capacidad liberada en el pico = {(6 - ops_5d) * JORNADA_DOC:.2f} HH/dia")
print("  Esto NO crea horas nuevas (el total es el mismo), pero elimina el cuello de botella")
print("  del lunes y hace utilizable el tiempo de Jue-Vie. Es la primera contrapropuesta que")
print("  hara la gerencia, y hay que responderla con la restriccion real que lo impide:")
print("  calendario de transporte, ventanas de recepcion en tienda o dias de corte de produccion.")

# ---------------------------------------------------------------- E
titulo("E. PLANTILLA DEL CASO FINANCIERO (LO QUE FALTA POR COMPLETO)")

print("""  Ninguna cifra monetaria aparece en el documento. Esta es la estructura minima,
  con las formulas listas para que solo se rellenen los valores reales:

  COSTO RECURRENTE ANUAL
    (1) Costo total por almacenista/ano = salario x 12 x (1 + carga social) + dotacion
    (2) Costo de la propuesta           = (1) x numero de contrataciones

  AHORRO / BENEFICIO RECURRENTE ANUAL
    (3) Horas extra evitadas            = HH extra actuales/ano x tarifa hora extra
    (4) Reduccion de merma              = ajuste de inventario anual x % de reduccion
    (5) Venta recuperada por quiebre    = eventos de quiebre x ticket promedio x margen
    (6) Beneficio recurrente total      = (3) + (4) + (5)

  INDICADORES
    (7) Beneficio neto recurrente       = (6) - (2)
    (8) Payback (meses)                 = (2) / ((6) / 12)      [solo si (6) > 0]

  CAJA UNICA (NO financia nomina, acelera el payback)
    (9) Liberacion REFRESH              = 10.000 piezas x costo unitario x % recuperacion
   (10) Payback ajustado                = ((2) - (9)) / ((6) / 12)

  Regla que hay que respetar: el gasto recurrente (2) se justifica con el beneficio
  recurrente (6). La partida (9) es un ingreso de una sola vez y NO puede sostener nomina
  indefinida. Presentarlas mezcladas es el error del parrafo de ROI actual.
""")

# ---------------------------------------------------------------- F
titulo("F. UMBRAL DE RENTABILIDAD DEL PROYECTO REFRESH")

print("""  El REFRESH es el unico componente que se autofinancia de verdad, pero hay que
  demostrarlo con el umbral: cuanto tiene que valer la pieza recuperada para pagar
  el esfuerzo de recuperarla.
""")

print("  El umbral se puede expresar SIN moneda, lo que lo hace universalmente valido:")
print("  costo por pieza = (1 / ritmo) horas de trabajo -> equivalente en minutos de mano de obra.\n")

print(f"{'Ritmo':>12s} {'HH totales':>12s} {'Semanas a 40 HH':>17s} {'Umbral por pieza':>22s}")
print("-" * 66)
for ritmo in (20, 30, 40):
    hh_tot = 10000 / ritmo
    minutos = 60 / ritmo
    print(f"{ritmo:>7d} p/HH {hh_tot:>12.1f} {hh_tot/40:>17.1f} {minutos:>15.1f} min de MO")

print("\n  Lectura: a 30 piezas/HH, el proyecto empata si cada pieza recupera el valor de")
print("  2 minutos de mano de obra. Cualquier pieza de inventario de una empresa de retail")
print("  vale muchisimo mas que eso, incluso vendida con descuento profundo o como material.")
print("\n  >>> Por tanto el REFRESH es, con enorme margen, el componente mas rentable y facil")
print("      de aprobar de toda la propuesta, y hoy esta enterrado como una linea de tabla.")
print("      Deberia ser una peticion separada, autofinanciada y con recurso temporal.")
print("      Sacarlo del pedido de plantilla permanente fortalece AMBAS peticiones.")

titulo("SINTESIS DE LOS APORTES DE ESTE ANALISIS COMPLEMENTARIO")
print(f"""
  1. La respuesta oscila entre {min(vals):.2f} y {max(vals):.2f} FTE solo por definir jornada y
     disponibilidad. El factor critico es la DISPONIBILIDAD (mueve 2.4 FTE), no la jornada
     (mueve 0.27 FTE). Hay que fijarla con la data de asistencia de 12 meses.
  2. La estructura de 12 personas agota su capacidad en la tienda {8+sat:.1f}: cubre hasta la 11a
     y queda al limite en la 12a. Conviene decirlo ahora y proponer el ratio de 1 persona
     por cada {hh_fte/HH_POR_TIENDA:.1f} tiendas como POLITICA aprobada de antemano.
  3. El 'riesgo de no actuar' es modelable como atraso acumulado en HH, en lugar de afirmar
     sin sustento que el OTIF colapsara por debajo del 75%.
  4. Nivelar la carga de 3 a 5 dias baja el pico de 6.00 a {ops_5d:.2f} operadores/dia. Es la
     contrapropuesta obvia de la gerencia y hay que responderla de frente con la
     restriccion real que lo impide.
  5. Falta el caso financiero completo; aqui esta la plantilla con formulas para rellenar.
  6. El REFRESH empata recuperando ~2 minutos de mano de obra por pieza: es el componente
     mas rentable de la propuesta y deberia pedirse por separado, con recurso temporal.
""")
