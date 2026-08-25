"""Verificacion independiente de la aritmetica y la consistencia interna
de la 'PROPUESTA AUMENTO DE PLANTILLA - REESTRUCTURACION TEAM ALMACEN FABRICA'.

Cada bloque reproduce una cifra publicada en el documento y la compara con el
calculo derivado de los supuestos declarados en el mismo documento.
"""

from datetime import datetime, timedelta


def chk(etiqueta, doc, calc, tol=0.005, unidad="HH"):
    ok = abs(doc - calc) <= tol
    estado = "OK  " if ok else "FALLA"
    print(f"[{estado}] {etiqueta}: documento={doc:,.2f} {unidad} | calculado={calc:,.2f} {unidad} | delta={doc-calc:+,.2f}")
    return ok


def titulo(t):
    print("\n" + "=" * 100)
    print(t)
    print("=" * 100)


titulo("1. JORNADA Y CAPACIDAD TEORICA")

inicio = datetime(2026, 1, 1, 8, 15)
fin = datetime(2026, 1, 1, 16, 45)
span_h = (fin - inicio) / timedelta(hours=1)
print(f"Horario declarado 8:15 am - 4:45 pm  ->  span real = {span_h:.2f} h")
chk("Jornada diaria declarada vs. span del horario", 8.25, span_h, unidad="h")
print("      Nota: la diferencia (0.25 h) solo cuadra si se descuenta un break de 15 min NO declarado.")
print(f"      Si la jornada real fuese {span_h:.2f} h, toda la base cambia +3.03%.")

JORNADA = 8.25
SEMANA_FTE = JORNADA * 5
print(f"\nHoras nominales por persona/semana = {JORNADA} x 5 = {SEMANA_FTE:.2f} HH")

teoricas_9 = 9 * SEMANA_FTE
chk("Horas teoricas semanales (9 almacenistas)", 371.25, teoricas_9)

titulo("2. PERDIDAS DE EFICIENCIA")

vacaciones = 1 * SEMANA_FTE
salud = 2 * SEMANA_FTE * 0.30
curva = 1 * SEMANA_FTE * 0.40
chk("Vacaciones PT Manufacturado (1 almacenista)", 41.25, vacaciones)
chk("Intermitencia por salud (2 almacenistas, -30%)", 24.75, salud)
chk("Curva de aprendizaje MP (1 nuevo, -40%)", 16.50, curva)

perdidas = vacaciones + salud + curva
capacidad_real = teoricas_9 - perdidas
chk("Perdidas totales", 82.50, perdidas)
chk("Capacidad REAL efectiva", 288.75, capacidad_real)
chk("Utilizacion real (%)", 77.7, 100 * capacidad_real / teoricas_9, tol=0.05, unidad="%")
print(f"      Nota: el valor correcto redondeado es {100*capacidad_real/teoricas_9:.1f}%, no 77.7%.")

titulo("3. DEMANDA OPERATIVA ACTUAL (tabla del documento)")

tareas = [
    ("Pedidos Web + Cuadro Chat (Alm. 1, 3 h/dia L-V)", 15.00, 3.00 * 5, 1),
    ("Reabast. Tienda Nueva (Alm. 1, 3.25 h/dia L-V)", 16.25, 3.25 * 5, 0),  # mismo Alm. 1
    ("Consumibles (Alm. 2: L-M full + Mi-V 9-12)", 25.50, 2 * JORNADA + 3 * 3.00, 1),
    ("Reabast. PT Manufacturado (Alm. 3,4,5)", 74.25, 3 * 3 * JORNADA, 3),
    ("Reabast. PT Equipamiento (Alm. 6,7,8)", 74.25, 3 * 3 * JORNADA, 3),
    ("Materias Primas e Insumos (Alm. 9 y 10)", 82.50, 2 * 5 * JORNADA, 2),
]

total_doc = 0.0
total_calc = 0.0
cabezas = 0
for nombre, doc, calc, heads in tareas:
    chk(nombre, doc, calc)
    total_doc += doc
    total_calc += calc
    cabezas += heads

chk("SUBTOTAL carga diaria operativa", 287.75, total_calc)
print(f"\n  >>> PERSONAS NOMBRADAS EN LA TABLA DE DEMANDA: {cabezas}")
print("  >>> PERSONAS USADAS EN EL CALCULO DE CAPACIDAD: 9")
print("  >>> INCONSISTENCIA DE PLANTILLA: la tabla llega hasta 'Almacenista 10'.")

titulo("4. LA CONCLUSION DEL 99.6% Y LA BRECHA")

chk("Absorcion de la capacidad real (%)", 99.6, 100 * 287.75 / capacidad_real, tol=0.06, unidad="%")

omitidas = {
    "Conteos Ciclicos ABC": 30.0,
    "Protocolo 5S y reordenamiento": 15.0,
    "Control de Devoluciones": 20.0,
    "Proyecto REFRESH (10.000 piezas)": 40.0,
}
chk("Total tareas omitidas", 105.0, sum(omitidas.values()))

demanda_total = 287.75 + sum(omitidas.values())
chk("Demanda total real", 392.75, demanda_total)
brecha = demanda_total - capacidad_real
chk("Brecha operativa", 104.00, brecha)
chk("Brecha en FTE nominales", 2.5, brecha / SEMANA_FTE, tol=0.03, unidad="FTE")

print("\n  --- Prueba de coherencia del salto de 2.5 a 3 contrataciones ---")
factor = capacidad_real / teoricas_9
print(f"  Si los 3 nuevos sufren el MISMO factor de perdida ({factor:.3f}):")
print(f"    aporte efectivo = 3 x {SEMANA_FTE:.2f} x {factor:.3f} = {3*SEMANA_FTE*factor:.2f} HH < 104 HH requeridas")
print(f"    FTE realmente necesarios = 104 / ({SEMANA_FTE:.2f} x {factor:.3f}) = {brecha/(SEMANA_FTE*factor):.2f}  ->  se requeririan 4, no 3")
print("  Si las perdidas son transitorias (vacaciones, curva de aprendizaje), la capacidad base")
print(f"    es {teoricas_9:.2f} HH y la brecha cae a {demanda_total - teoricas_9:.2f} HH = {(demanda_total-teoricas_9)/SEMANA_FTE:.2f} FTE  ->  se requeriria 1, no 3")

titulo("5. EFECTO DE CORREGIR LA PLANTILLA A 10 PERSONAS")

teoricas_10 = 10 * SEMANA_FTE
capacidad_real_10 = teoricas_10 - perdidas
print(f"  Teoricas (10 pers.)      = {teoricas_10:.2f} HH")
print(f"  Capacidad real (10 pers.) = {capacidad_real_10:.2f} HH")
print(f"  Absorcion del dia a dia   = {100*287.75/capacidad_real_10:.1f}%  (no 99.6%)")
brecha_10 = demanda_total - capacidad_real_10
print(f"  Brecha                    = {brecha_10:.2f} HH = {brecha_10/SEMANA_FTE:.2f} FTE  ->  la peticion pasa de 2.5 a {brecha_10/SEMANA_FTE:.1f} FTE")

titulo("6. PERFIL DE CARGA POR DIA (lo que el promedio semanal oculta)")

dias = ["Lun", "Mar", "Mie", "Jue", "Vie"]
# Asignacion diaria por persona, derivada literalmente de la tabla del documento
plan = {
    "Alm. 1 (Web + Tienda Nueva)": [6.25, 6.25, 6.25, 6.25, 6.25],
    "Alm. 2 (Consumibles)": [JORNADA, JORNADA, 3.0, 3.0, 3.0],
    "Alm. 3 (PT Manuf.)": [JORNADA, JORNADA, JORNADA, 0, 0],
    "Alm. 4 (PT Manuf.)": [JORNADA, JORNADA, JORNADA, 0, 0],
    "Alm. 5 (PT Manuf.)": [JORNADA, JORNADA, JORNADA, 0, 0],
    "Alm. 6 (Equipamiento)": [JORNADA, JORNADA, JORNADA, 0, 0],
    "Alm. 7 (Equipamiento)": [JORNADA, JORNADA, JORNADA, 0, 0],
    "Alm. 8 (Equipamiento)": [JORNADA, JORNADA, JORNADA, 0, 0],
    "Alm. 9 (MP)": [JORNADA, JORNADA, JORNADA, JORNADA, JORNADA],
    "Alm. 10 (MP)": [JORNADA, JORNADA, JORNADA, JORNADA, JORNADA],
}

print(f"{'':30s}" + "".join(f"{d:>8s}" for d in dias) + f"{'Total':>10s}")
carga_dia = [0.0] * 5
for k, v in plan.items():
    print(f"{k:30s}" + "".join(f"{x:8.2f}" for x in v) + f"{sum(v):10.2f}")
    carga_dia = [a + b for a, b in zip(carga_dia, v)]

cap_dia = [len(plan) * JORNADA] * 5
print("-" * 88)
print(f"{'CARGA ASIGNADA':30s}" + "".join(f"{x:8.2f}" for x in carga_dia) + f"{sum(carga_dia):10.2f}")
print(f"{'CAPACIDAD NOMINAL (10 pers.)':30s}" + "".join(f"{x:8.2f}" for x in cap_dia) + f"{sum(cap_dia):10.2f}")
holgura = [c - a for c, a in zip(cap_dia, carga_dia)]
print(f"{'HORAS NO ASIGNADAS':30s}" + "".join(f"{x:8.2f}" for x in holgura) + f"{sum(holgura):10.2f}")
print(f"{'UTILIZACION (%)':30s}" + "".join(f"{100*a/c:7.1f}%" for a, c in zip(carga_dia, cap_dia)))

print(f"\n  >>> Horas nominales NO asignadas hoy: {sum(holgura):.2f} HH/semana")
print(f"  >>> Tareas 'omitidas' reclamadas:     {sum(omitidas.values()):.2f} HH/semana")
print("  >>> Es decir: en el papel las tareas omitidas CABEN dentro del tiempo no asignado")
print("      (concentrado en Jue-Vie de las celulas de PT). El propio documento lo admite")
print("      cuando dice que la Celula 2 hara 5S y conteos los jueves y viernes.")

titulo("7. LA PROPUESTA DE 12 PERSONAS CONTRA SU PROPIA DEMANDA")

celulas = {
    "Celula 1: MP + Insumos + Consumibles": (3, 82.50 + 25.50),
    "Celula 2: PT Manuf. + Equipamiento + Rampa": (5, 74.25 + 74.25 + 16.25),
    "Celula 3: Fulfillment E-commerce + Chat": (2, 15.00),
    "Celula 4: Logistica Inversa + REFRESH": (2, 20.00 + 40.00),
}
tot_ops, tot_dem, tot_cap = 0, 0.0, 0.0
for nombre, (ops, dem) in celulas.items():
    cap = ops * SEMANA_FTE
    tot_ops += ops
    tot_dem += dem
    tot_cap += cap
    print(f"  {nombre:45s} ops={ops}  capacidad={cap:7.2f}  demanda asignable={dem:7.2f}  holgura={cap-dem:+7.2f} ({100*dem/cap:5.1f}% util.)")
print(f"\n  Total ops = {tot_ops} (el documento dice 12: 3+5+2+2 = {3+5+2+2})")
print(f"  Capacidad nominal total = {tot_cap:.2f} HH | Demanda total mapeada = {tot_dem:.2f} HH | Holgura = {tot_cap-tot_dem:.2f} HH")
print("  Nota: 'Consumibles' aparece en la Celula 1 (custodia de la jaula) y tambien en la")
print("        justificacion de la Celula 3 -> doble asignacion del mismo frente.")

print("\n  --- Capacidad de picking Lun-Mie para PT + Equipamiento ---")
print(f"  Hoy:      6 ops x 3 dias x {JORNADA} h = {6*3*JORNADA:.2f} HH")
print(f"  Propuesto: 5 ops x 3 dias x {JORNADA} h = {5*3*JORNADA:.2f} HH")
print(f"  Variacion: {5*3*JORNADA - 6*3*JORNADA:+.2f} HH  ->  se REDUCE el pico de picking mientras se")
print("             afirma que el volumen crece 12.5% por trimestre.")

print("\n  --- Conteos ciclicos: dos cifras incompatibles ---")
print(f"  Demanda declarada: {omitidas['Conteos Ciclicos ABC']:.1f} HH/semana")
print(f"  Protocolo declarado: 12 ops x 2 h cada viernes = {12*2:.1f} HH/semana")
print(f"  Deficit del protocolo frente a su propia demanda: {12*2 - omitidas['Conteos Ciclicos ABC']:+.1f} HH")

titulo("8. LA EXPANSION: 12.5% POR TRIMESTRE")

base_tiendas = 8
carga_tienda = (74.25 + 74.25) / base_tiendas
print(f"  Carga de reabastecimiento por tienda = (74.25 + 74.25) / {base_tiendas} = {carga_tienda:.2f} HH/tienda/semana")
print(f"  Comparar con la linea 'Reabast. Tienda Nueva' = 16.25 HH  ->  coherente ({16.25/carga_tienda*100:.0f}% del estandar),")
print("  lo que sugiere que esa linea ya es la tienda 9 en regimen, no un evento trimestral.")
print("\n  El '12.5% por trimestre' NO es constante (la base crece):")
t = base_tiendas
acum = 0.0
for q in range(1, 5):
    inc_pct = 100 / t
    inc_hh = carga_tienda
    acum += inc_hh
    print(f"    T{q}: {t} -> {t+1} tiendas | incremento = {inc_pct:5.1f}% | +{inc_hh:.2f} HH/semana | acumulado +{acum:.2f} HH")
    t += 1
print(f"\n  Carga adicional a 12 meses = {acum:.2f} HH/semana = {acum/SEMANA_FTE:.2f} FTE nominales")
print(f"  Brecha declarada (104 HH) + expansion ({acum:.2f} HH) = {104+acum:.2f} HH = {(104+acum)/SEMANA_FTE:.2f} FTE")
print("  >>> Con sus propios supuestos, 3 personas NO son 'el numero exacto': quedan cortas.")

titulo("9. MODELO ALTERNATIVO RECOMENDADO (factor de disponibilidad estandar)")

vac_dias, fer_dias, dias_ano = 15, 11, 260
f_vac = vac_dias / dias_ano
f_fer = fer_dias / dias_ano
f_aus, f_form = 0.03, 0.02
disp = 1 - (f_vac + f_fer + f_aus + f_form)
hh_efectivas = SEMANA_FTE * disp
print(f"  Vacaciones {vac_dias} d/ano   = {f_vac*100:5.2f}%")
print(f"  Feriados   {fer_dias} d/ano   = {f_fer*100:5.2f}%")
print(f"  Ausentismo             = {f_aus*100:5.2f}%")
print(f"  Formacion/reuniones    = {f_form*100:5.2f}%")
print(f"  -> Factor de disponibilidad = {disp*100:.1f}%  ->  {hh_efectivas:.2f} HH efectivas por FTE/semana")

recurrente = 287.75 + 30 + 15 + 20  # REFRESH excluido: es un proyecto finito
fte_hoy = recurrente / hh_efectivas
print(f"\n  Demanda RECURRENTE (sin REFRESH) = 287.75 + 30 + 15 + 20 = {recurrente:.2f} HH")
print(f"  FTE necesarios hoy = {recurrente:.2f} / {hh_efectivas:.2f} = {fte_hoy:.2f}")
fte_ano = (recurrente + acum) / hh_efectivas
print(f"  FTE necesarios a 12 meses (con +4 tiendas) = {(recurrente+acum):.2f} / {hh_efectivas:.2f} = {fte_ano:.2f}")
print(f"\n  Costo marginal por tienda nueva = {carga_tienda:.2f} HH / {hh_efectivas:.2f} = {carga_tienda/hh_efectivas:.2f} FTE/tienda")
print(f"    -> aprox. 1 almacenista por cada {1/(carga_tienda/hh_efectivas):.1f} tiendas abiertas")
print(f"  Deficit inmediato si la plantilla es  9: {fte_hoy - 9:+.2f} FTE")
print(f"  Deficit inmediato si la plantilla es 10: {fte_hoy - 10:+.2f} FTE")
print(f"\n  REFRESH como proyecto finito: 40 HH/semana durante N semanas.")
for ritmo in (20, 30, 40):
    hh_tot = 10000 / ritmo
    print(f"    a {ritmo:2d} piezas/HH -> {hh_tot:7.1f} HH totales -> {hh_tot/40:5.1f} semanas a 40 HH/semana")
print("  >>> Tratarlo como demanda permanente infla la peticion; corresponde recurso temporal.")

titulo("10. RESUMEN DE HALLAZGOS ARITMETICOS")
print("""
  Aritmetica interna: CORRECTA en todas las sumas y productos verificados
  (371.25 / 288.75 / 287.75 / 105 / 392.75 / 104 / 2.5 FTE cuadran).

  Los problemas NO son de calculo, son de supuestos y consistencia:
   1. 8.25 h no coincide con el horario 8:15-16:45 (8.50 h): break no declarado.
   2. Capacidad con 9 personas vs. demanda con 10 personas nombradas.
   3. Demanda medida por 'presencia asignada', no por volumen x tiempo estandar.
   4. Perdidas transitorias tratadas como permanentes.
   5. Los 3 nuevos se computan al 100% mientras los actuales al 77.8%.
   6. 105 HH omitidas < 124.75 HH nominales hoy sin asignar (Jue-Vie).
   7. REFRESH (proyecto finito) contabilizado como carga permanente.
   8. La propuesta reduce el pico de picking de 6 a 5 operadores.
   9. 12.5%/trimestre no es constante y, si se aplica, 3 personas no alcanzan.
  10. Conteos: 30 HH de demanda vs. 24 HH de protocolo.
  11. 77.7% deberia ser 77.8%.
""")
