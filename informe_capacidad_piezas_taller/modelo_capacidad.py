"""
Modelo de capacidad instalada del taller de costura — Cuadro (Crecoindustrias, C.A.)
Unidad de salida: PIEZAS / MES. Corte: septiembre 2026.

Genera:
  anexos/Modelo_Capacidad_Piezas_Cuadro.xlsx   (memoria de cálculo, 13 hojas)
  anexos/figuras/*.png                          (las 8 figuras del informe)
  datos_modelo.json / datos_modelo.js           (alimentan el dashboard)

Ejecutar:  python3 modelo_capacidad.py
"""

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

BASE = os.path.dirname(os.path.abspath(__file__))
ANEXOS = os.path.join(BASE, "anexos")
FIGS = os.path.join(ANEXOS, "figuras")
os.makedirs(FIGS, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. PARÁMETROS BASE  (todos trazables al expediente)
# ---------------------------------------------------------------------------

DIAS = 20                 # días hábiles/mes — criterio de Gerencia de Operaciones
LINEAS_PUNTO = 4          # L1–L4, flujo Overlock + Collaret

# Mix ponderado de planificación (dashboard de capacidad, pestaña 4)
MIX = {"MAR": 0.50, "RIO": 0.35, "Basic Line": 0.15}
OPS_PIEZA = {"MAR": 7, "RIO": 6, "Basic Line": 12}

# Tasas de producción por LÍNEA y por DÍA, en piezas (Muestra de Campo +
# dashboard, pestaña 4 "Producción diaria por línea").
#   A = parque actual degradado (merma 10% por estado de máquina)
#   B = techo de diseño / sustitución JACK K7 (parque íntegro, mismo layout)
#   C = módulo continuo (5 máquinas por línea, sin mesa de remate)
TASAS = {
    "A_real":   {"MAR": 95,  "RIO": 73,  "Basic Line": 55},
    "B_teor":   {"MAR": 105, "RIO": 82,  "Basic Line": 61},
    "C_modulo": {"MAR": 130, "RIO": 101, "Basic Line": 76},
}

# Línea 5 (shorts / pants: Short Sport 15 ops, R1 Interno 13, R1 Externo 17).
# Muestra de Campo: 45 piezas/día. Sin medición formal de estatus por máquina.
L5_PIEZAS_DIA = 45
L5_MES = L5_PIEZAS_DIA * DIAS          # 900 piezas/mes

# Capacidad en operaciones (dashboard, pestaña 1) — se usa sólo como contraste
OPS_TEORICA_DIA = 2940.0
OPS_REAL_DIA = 2649.5
OPS_TEORICA_MES = OPS_TEORICA_DIA * DIAS
OPS_REAL_MES = OPS_REAL_DIA * DIAS

# Calidad — Analisis_Tasa_Retrocesos_QA (promedio mensual abr–ago 2026)
QA_INSPECCIONADAS = 10502
QA_RECHAZADAS = 1695
TASA_REPROCESO = QA_RECHAZADAS / QA_INSPECCIONADAS      # 16,14%

# Contenido de retrabajo: fracción del contenido de operación original que
# consume una prenda retrabajada. Caso central 35% (los defectos documentados
# se concentran en acabado: ruedo, remate, limpieza de hilo, lavado).
RETRABAJO_CONTENIDO = 0.35
RETRABAJO_SENSIBILIDAD = [0.20, 0.35, 0.50, 1.00]

# Reproceso residual con parque nuevo. Brayan Machado documenta que ondas,
# ruedos abiertos, hilos, aceite, cortes y fruncido son atribuibles a máquina.
# Caso central conservador: 6,0% (≈62% de los defectos se eliminan).
REPROCESO_NUEVO = 0.060

# Demanda mensual de ventas en PIEZAS (dato de Gerencia)
DEM_REGULAR = 4145
DEM_PICO = 8576

# Factores de red nueva, derivados de los escenarios en operaciones del
# expediente: 58.800 → 69.732 (+1 tienda) → 87.166 (+3 tiendas/año)
OPS_RED_ACTUAL = 58800.0
OPS_RED_1T = 69732.0
OPS_RED_3T = 87166.0
F_1T = OPS_RED_1T / OPS_RED_ACTUAL       # 1,18592
F_3T = OPS_RED_3T / OPS_RED_ACTUAL       # 1,48242


# ---------------------------------------------------------------------------
# 2. FUNCIONES DEL MODELO
# ---------------------------------------------------------------------------

def ops_pieza_ponderado():
    """Operaciones por pieza del mix de planificación."""
    return sum(MIX[m] * OPS_PIEZA[m] for m in MIX)


def tasa_ponderada(estado):
    """Piezas por línea y por día al mix 50/35/15, para un estado técnico."""
    return sum(MIX[m] * TASAS[estado][m] for m in MIX)


def piezas_mes(estados_por_linea):
    """
    Capacidad mensual en piezas del bloque de tejido de punto.
    `estados_por_linea` es la lista de estados técnicos, una entrada por línea.
    Cada línea aporta DIAS días-línea; el mix reparte esos días-línea.
    """
    return sum(tasa_ponderada(e) * DIAS for e in estados_por_linea)


def detalle_por_modelo(estados_por_linea):
    """Desglose de la capacidad mensual por modelo del mix."""
    dias_linea = len(estados_por_linea) * DIAS
    out = {}
    for m in MIX:
        dl = dias_linea * MIX[m]
        # tasa media del modelo ponderada por los estados presentes
        tasa = np.mean([TASAS[e][m] for e in estados_por_linea])
        out[m] = {"dias_linea": dl, "tasa": tasa, "piezas": dl * tasa}
    return out


def factor_neto(tasa_reproceso, contenido=RETRABAJO_CONTENIDO):
    """
    Fracción de la capacidad bruta que se convierte en pieza nueva de primera.
    Una prenda retrabajada re-consume `contenido` del contenido original,
    de modo que producir G piezas exige G*(1 + tasa*contenido) de capacidad.
    """
    return 1.0 / (1.0 + tasa_reproceso * contenido)


def reproceso_mezclado(dias_linea_nuevos, dias_linea_total, l5_renovada=False):
    """Tasa de reproceso ponderada por la fracción de días-línea con parque nuevo."""
    total = dias_linea_total + DIAS          # + Línea 5
    nuevos = dias_linea_nuevos + (DIAS if l5_renovada else 0)
    f = nuevos / total
    return f * REPROCESO_NUEVO + (1 - f) * TASA_REPROCESO


# ---------------------------------------------------------------------------
# 3. ESCENARIOS
# ---------------------------------------------------------------------------

OPS_PZA = ops_pieza_ponderado()               # 7,40
TASA_A = tasa_ponderada("A_real")             # 81,30
TASA_B = tasa_ponderada("B_teor")             # 90,35
TASA_C = tasa_ponderada("C_modulo")           # 111,75

ESCENARIOS = [
    # (clave, etiqueta, estados por línea de punto, máquinas nuevas, L5 renovada, nota)
    ("S0",   "0 · Actual REAL",
     ["A_real"] * 4, 0, False,
     "Parque hoy: 4 máquinas inactivas o parciales, merma 10%."),
    ("S0T",  "0T · Actual TEÓRICA",
     ["B_teor"] * 4, 0, False,
     "Mismo layout con las 22 máquinas al 100%. Es el techo que el taller declara."),
    ("S21a", "2.1a · Inversión corta MÍNIMA",
     ["C_modulo"] + ["B_teor"] * 3, 6, False,
     "L3 a módulo continuo JACK (5 máq.) + Overlock L2 (1 máq.). Recupera L4 con kit."),
    ("S21b", "2.1b · Inversión corta RECOMENDADA",
     ["C_modulo"] * 2 + ["B_teor"] * 2, 12, False,
     "L3 y L4 a módulos continuos JACK (10 máq.) + collaretera de ruedo en L1 y L2."),
    ("S22a", "2.2a · Ambiciosa · 4 módulos",
     ["C_modulo"] * 4, 20, False,
     "Las 4 líneas de punto a módulo continuo JACK de 5 máquinas."),
    ("S22b", "2.2b · Ambiciosa · 5 módulos + Línea 5",
     ["C_modulo"] * 5, 33, True,
     "5ª línea de punto + Línea 5 de shorts completada y renovada."),
    ("S22c", "2.2c · Ambiciosa · 6 módulos + Línea 5",
     ["C_modulo"] * 6, 38, True,
     "6ª línea de punto. Dimensionado para 3 tiendas nuevas por año en pico."),
]

filas = []
for clave, etiqueta, estados, maquinas, l5_ren, nota in ESCENARIOS:
    punto = piezas_mes(estados)
    total_bruto = punto + L5_MES
    dias_linea_total = len(estados) * DIAS
    dias_nuevos = sum(DIAS for e in estados if e == "C_modulo")
    # En S0/S0T no hay parque nuevo; la tasa de reproceso medida se mantiene.
    if maquinas == 0:
        tasa_rep = TASA_REPROCESO
    else:
        tasa_rep = reproceso_mezclado(dias_nuevos, dias_linea_total, l5_ren)
    fneto = factor_neto(tasa_rep)
    filas.append({
        "clave": clave,
        "escenario": etiqueta,
        "lineas_punto": len(estados),
        "maquinas_nuevas": maquinas,
        "punto_bruto": round(punto),
        "linea5": L5_MES,
        "total_bruto": round(total_bruto),
        "tasa_reproceso": tasa_rep,
        "factor_neto": fneto,
        "total_neto": round(total_bruto * fneto),
        "nota": nota,
    })

esc = pd.DataFrame(filas)
base_neto = esc.loc[esc["clave"] == "S0", "total_neto"].iloc[0]
base_bruto = esc.loc[esc["clave"] == "S0", "total_bruto"].iloc[0]
esc["delta_neto"] = esc["total_neto"] - base_neto
esc["delta_pct"] = esc["total_neto"] / base_neto - 1
esc["pzas_por_maquina"] = np.where(
    esc["maquinas_nuevas"] > 0, esc["delta_neto"] / esc["maquinas_nuevas"], np.nan
)

# ---------------------------------------------------------------------------
# 4. DEMANDA Y DÉFICIT
# ---------------------------------------------------------------------------

DEMANDAS = [
    ("D1", "Regular · red actual",              DEM_REGULAR),
    ("D2", "Regular · +1 tienda",               round(DEM_REGULAR * F_1T)),
    ("D3", "Regular · +3 tiendas/año",          round(DEM_REGULAR * F_3T)),
    ("D4", "Pico diciembre · red actual",       DEM_PICO),
    ("D5", "Pico diciembre · +1 tienda",        round(DEM_PICO * F_1T)),
    ("D6", "Pico diciembre · +3 tiendas/año",   round(DEM_PICO * F_3T)),
]

def_rows = []
for dk, dl, dv in DEMANDAS:
    fila = {"clave_dem": dk, "demanda": dl, "piezas_dem": dv}
    for _, r in esc.iterrows():
        fila[r["clave"]] = r["total_neto"] - dv
    def_rows.append(fila)
deficit = pd.DataFrame(def_rows)

# Cobertura (capacidad neta / demanda)
cob_rows = []
for dk, dl, dv in DEMANDAS:
    fila = {"clave_dem": dk, "demanda": dl, "piezas_dem": dv}
    for _, r in esc.iterrows():
        fila[r["clave"]] = r["total_neto"] / dv
    cob_rows.append(fila)
cobertura = pd.DataFrame(cob_rows)


# ---------------------------------------------------------------------------
# 5. PARQUE DE MÁQUINAS Y CUELLO DE BOTELLA
# ---------------------------------------------------------------------------

# Estaciones críticas publicadas en el dashboard (ops/día)
CRITICAS = pd.DataFrame([
    ["Línea 3", "Collaretera de ruedo 1", "Parcial 50%", 101, 50.5],
    ["Línea 3", "Collaretera de ruedo 2", "Inactiva",    100, 0.0],
    ["Línea 4", "Collaretera de ruedo 2", "Inactiva",    100, 0.0],
    ["Línea 2", "Overlock Unión/Montaje", "Parcial 80%", 190, 150.0],
], columns=["Línea", "Máquina", "Estatus", "Teórica ops/día", "Real ops/día"])
CRITICAS["Pérdida ops/día"] = CRITICAS["Teórica ops/día"] - CRITICAS["Real ops/día"]

# Totales por línea. Con d2 (ruedo extra) = 100 y total teórico 2.940:
#   4 * base + 2 * 100 = 2.940  ->  base (L1/L2) = 685 ; L3/L4 = 785
BASE_L12 = (OPS_TEORICA_DIA - 2 * 100) / 4
LINEAS_OPS = pd.DataFrame([
    ["Línea 1", BASE_L12,        BASE_L12],
    ["Línea 2", BASE_L12,        BASE_L12 - 40],
    ["Línea 3", BASE_L12 + 100,  BASE_L12 - 50.5],
    ["Línea 4", BASE_L12 + 100,  BASE_L12],
], columns=["Línea", "Teórica ops/día", "Real ops/día"])
LINEAS_OPS["Pérdida"] = LINEAS_OPS["Teórica ops/día"] - LINEAS_OPS["Real ops/día"]
LINEAS_OPS["Utilización"] = LINEAS_OPS["Real ops/día"] / LINEAS_OPS["Teórica ops/día"]

# Contraste de método: sumar operaciones sobrestima la capacidad en piezas
PZAS_POR_OPS_REAL = OPS_REAL_MES / OPS_PZA          # método "suma de ops"
PZAS_MODELO_REAL = piezas_mes(["A_real"] * 4)       # método cuello de botella
SOBREESTIMACION = PZAS_POR_OPS_REAL / PZAS_MODELO_REAL - 1

# Capacidad máxima exclusiva (si una línea corriera un solo modelo)
EXCLUSIVA = pd.DataFrame([
    {
        "Modelo": m,
        "Ops/pieza": OPS_PIEZA[m],
        "Actual /línea/día": TASAS["A_real"][m],
        "Diseño /línea/día": TASAS["B_teor"][m],
        "Módulo /línea/día": TASAS["C_modulo"][m],
        "Actual 4 líneas/mes": TASAS["A_real"][m] * LINEAS_PUNTO * DIAS,
        "Diseño 4 líneas/mes": TASAS["B_teor"][m] * LINEAS_PUNTO * DIAS,
        "Módulo 4 líneas/mes": TASAS["C_modulo"][m] * LINEAS_PUNTO * DIAS,
    }
    for m in ["MAR", "RIO", "Basic Line"]
])

# Sensibilidad del contenido de retrabajo
sens = []
for r in RETRABAJO_SENSIBILIDAD:
    fila = {"Contenido de retrabajo": r}
    for _, row in esc.iterrows():
        fila[row["clave"]] = round(row["total_bruto"] * factor_neto(row["tasa_reproceso"], r))
    sens.append(fila)
SENSIBILIDAD = pd.DataFrame(sens)

# Paquetes de compra
COMPRA = pd.DataFrame([
    ["2.1a", "Módulo continuo JACK para Línea 3", "Overlock unión, Overlock cierre, Collaretera recubrir, Collaretera de ruedo (corte y succión), Recta dedicada", 5,
     "L3 concentra 52% de la pérdida: ruedo 1 al 50% y ruedo 2 inactivo."],
    ["2.1a", "Overlock Unión/Montaje JACK para Línea 2", "Sustituye la máquina al 80%", 1,
     "Recupera 40 ops/día y la calidad de la unión."],
    ["2.1a", "Reactivar 2 Overlock de cuellos", "Sin compra · 2 operarios", 0,
     "Libera la operación 'montar cuello' que hoy carga los overlock de línea."],
    ["2.1a", "Kit de repuestos JACK", "Agujas, cuchillas, diferenciales, loopers · min-max", 0,
     "3 equipos llevan meses esperando piezas (≈40 pzas/día)."],
    ["2.1b", "Módulo continuo JACK para Línea 4", "Igual que L3", 5,
     "L4 tiene el ruedo 2 inactivo: mismo desbalanceo que L3."],
    ["2.1b", "Collaretera de ruedo JACK para Línea 1 y Línea 2", "Segundo ruedo, con corte y succión", 2,
     "L1 y L2 nacen con un solo ruedo (la mitad del overlock). Replica el patrón de diseño de L3/L4."],
    ["2.2a", "Módulos continuos JACK en L1 y L2", "10 máquinas (5 por línea)", 10,
     "Cierra las 4 líneas al mismo estándar de calidad y flujo."],
    ["2.2b", "Línea 5 de punto (nueva)", "Módulo continuo de 5 máquinas", 5,
     "Capacidad incremental para la tienda confirmada."],
    ["2.2b", "Línea de shorts / pants completada", "Ojaladora, presilladora, engomadora, doble aguja, 2 rectas, 2 overlock", 8,
     "Hoy Short Sport / R1 / Explore Pants no tienen techo medido."],
    ["2.2c", "Línea 6 de punto (nueva)", "Módulo continuo de 5 máquinas", 5,
     "Dimensiona el taller para 3 tiendas nuevas por año en pico."],
    ["Paralelo", "Liquidación de parque inactivo", "2 collareteras chatarra (9% del parque) + las sustituidas", 0,
     "Caja que abate el CAPEX y libera metro cuadrado."],
], columns=["Fase", "Ítem", "Detalle", "Máquinas nuevas", "Por qué"])

# Datos que faltan para cerrar el capex
FALTANTES = pd.DataFrame([
    ["P0", "Cotización JACK por tipo + flete, instalación y capacitación",
     "Convierte piezas ganadas en payback", "Proveedor + Brayan Machado", "No está"],
    ["P0", "REPORTE DE MAQUINAS (15-jul a 31-ago 2026): horas de parada por máquina",
     "Sustituye la merma del 10% por disponibilidad medida (MTBF/MTTR)",
     "Mantenimiento", "Archivo no incorporado al modelo"],
    ["P0", "Minutos de retrabajo por prenda y % de defectos atribuibles a máquina",
     "Fija el factor neto; hoy es supuesto (35% de contenido)", "Calidad / Taller", "No medido"],
    ["P0", "Margen bruto por pieza",
     "Dolariza el déficit de 2.420 piezas del pico", "Finanzas", "No está"],
    ["P1", "Maquinas Activas.xlsx a nivel de serie: marca, modelo, año, valor en libros",
     "Cierra las dos estaciones cuya capacidad individual no está publicada (b+c=394 ops/día)",
     "Mantenimiento / Admin", "Pendiente de cargar"],
    ["P1", "Tasa de producción medida de la Línea 5 de shorts",
     "Hoy se usa la muestra de campo de 45 pzas/día sin estatus por máquina",
     "Taller", "Muestra única"],
    ["P1", "Plan comercial: qué tienda, cuándo y de qué tamaño",
     "Pasa los escenarios de red a presupuesto", "Comercial", "1 confirmada, objetivo 3/año"],
    ["P1", "Ops por pieza de Explore Pants, Jacket 2.0 y Active Duo",
     "El pico de 8.576 piezas puede estar subestimado en operaciones", "Ingeniería", "Celdas vacías"],
    ["P2", "Headcount por línea vs estándar de 5 máquinas por módulo",
     "Sin operarios, la máquina nueva repite el caso de los Overlock de cuellos", "RR.HH.", "2 máquinas paradas por gente"],
    ["P2", "Volumen y SLA del taller satélite",
     "Evita duplicar capacidad ya tercerizada", "Operaciones", "Mencionado sin data"],
], columns=["Prioridad", "Dato", "Para qué", "Dueño", "Estado hoy"])


# ---------------------------------------------------------------------------
# 6. EXCEL — MEMORIA DE CÁLCULO
# ---------------------------------------------------------------------------

xlsx = os.path.join(ANEXOS, "Modelo_Capacidad_Piezas_Cuadro.xlsx")
with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:

    portada = pd.DataFrame({
        "Concepto": [
            "CUADRO · Crecoindustrias, C.A.",
            "Modelo de capacidad instalada del taller — unidad: PIEZAS/MES",
            "",
            "Fecha de corte",
            "Días hábiles por mes",
            "Líneas de tejido de punto (L1–L4)",
            "Mix de planificación",
            "Operaciones por pieza del mix",
            "",
            "Piezas/línea/día al mix — Actual (A)",
            "Piezas/línea/día al mix — Diseño / JACK K7 (B)",
            "Piezas/línea/día al mix — Módulo continuo (C)",
            "",
            "Capacidad REAL actual (L1–L4)",
            "Capacidad TEÓRICA actual (L1–L4)",
            "Pérdida por estado del parque",
            "Línea de shorts / pants (muestra de campo)",
            "",
            "Tasa de reproceso QA medida",
            "Contenido de retrabajo supuesto",
            "Factor neto de primera calidad (actual)",
            "",
            "Demanda regular (piezas/mes)",
            "Demanda pico diciembre (piezas/mes)",
            "Factor +1 tienda",
            "Factor +3 tiendas/año",
            "",
            "Fuentes",
        ],
        "Valor": [
            "", "", "",
            "Septiembre 2026",
            DIAS,
            LINEAS_PUNTO,
            "MAR 50% (7 ops) · RIO 35% (6 ops) · Basic Line 15% (12 ops)",
            round(OPS_PZA, 2),
            "",
            round(TASA_A, 2),
            round(TASA_B, 2),
            round(TASA_C, 2),
            "",
            f"{round(piezas_mes(['A_real'] * 4)):,} piezas/mes".replace(",", "."),
            f"{round(piezas_mes(['B_teor'] * 4)):,} piezas/mes".replace(",", "."),
            f"{round(piezas_mes(['B_teor'] * 4) - piezas_mes(['A_real'] * 4)):,} piezas/mes".replace(",", "."),
            f"{L5_MES} piezas/mes ({L5_PIEZAS_DIA}/día)",
            "",
            f"{TASA_REPROCESO:.2%} ({QA_RECHAZADAS:,} de {QA_INSPECCIONADAS:,})".replace(",", "."),
            f"{RETRABAJO_CONTENIDO:.0%} del contenido de operación original",
            round(factor_neto(TASA_REPROCESO), 4),
            "",
            DEM_REGULAR,
            DEM_PICO,
            round(F_1T, 5),
            round(F_3T, 5),
            "",
            "Maquinas Activas; REPORTE DE MAQUINAS; Muestra de Campo; Operaciones Por Linea; "
            "Operaciones por Producto; Analisis_Tasa_Retrocesos_QA; Informe de Capacidad Instalada "
            "y Justificación de Inversión en Maquinaria de Costura; dashboard_capacidad_maquinaria.",
        ],
    })
    portada.to_excel(xw, sheet_name="00_Portada", index=False)

    # Método
    metodo = pd.DataFrame({
        "Paso": [1, 2, 3, 4, 5, 6],
        "Qué se hace": [
            "Se fija el mix de planificación y las operaciones por pieza de cada modelo.",
            "Se toma la tasa de producción por línea y día en PIEZAS, medida en campo, "
            "para tres estados técnicos: parque actual (A), parque íntegro o JACK K7 (B) "
            "y módulo continuo (C).",
            "La tasa al mix es el promedio ponderado: 0,50·MAR + 0,35·RIO + 0,15·Basic.",
            "La capacidad mensual es la tasa al mix × 20 días × número de líneas. "
            "Cada línea aporta 20 días-línea y el mix reparte esos días-línea.",
            "Se descuenta el retrabajo: producir G piezas exige G·(1 + tasa_reproceso × "
            "contenido_retrabajo) de capacidad, de modo que el factor neto es "
            "1 / (1 + tasa × contenido).",
            "El déficit es demanda − capacidad NETA de primera calidad.",
        ],
        "Por qué así": [
            "Gerencia pide el techo en piezas; el mix es lo que convierte operaciones en piezas.",
            "La tasa en piezas ya incorpora el cuello de botella de la línea. Sumar "
            "operaciones de todas las máquinas ignora que el ruedo va a la mitad del overlock.",
            "Evita planificar sobre un promedio plano: MAR, RIO y Basic no cuestan lo mismo.",
            "Es el mismo criterio de 20 días hábiles que ya usa Gerencia de Operaciones.",
            "16 de cada 100 prendas vuelven a ocupar máquina y gente. Esa capacidad no "
            "produce pieza nueva y no puede contarse como techo.",
            "La demanda de ventas está en piezas vendibles, no en piezas que salen de línea.",
        ],
    })
    metodo.to_excel(xw, sheet_name="01_Metodo", index=False)

    # Contraste de método
    contraste = pd.DataFrame({
        "Método": [
            "Suma de operaciones ÷ ops por pieza del mix",
            "Cuello de botella por línea (tasa medida en piezas)",
            "Sobreestimación del método de suma de operaciones",
        ],
        "Cálculo": [
            f"{OPS_REAL_MES:,.0f} ops/mes ÷ {OPS_PZA:.2f} ops/pieza".replace(",", "."),
            f"{TASA_A:.2f} pzas/línea/día × {DIAS} días × {LINEAS_PUNTO} líneas",
            "—",
        ],
        "Piezas/mes": [
            round(PZAS_POR_OPS_REAL),
            round(PZAS_MODELO_REAL),
            round(PZAS_POR_OPS_REAL - PZAS_MODELO_REAL),
        ],
        "Lectura": [
            "Supone que toda operación libre es intercambiable. No lo es.",
            "Es el techo que la línea puede sostener. Este modelo usa este método.",
            f"{SOBREESTIMACION:.1%}. Planificar en operaciones promete piezas que la línea no entrega.",
        ],
    })
    contraste.to_excel(xw, sheet_name="02_Contraste_metodo", index=False)

    # Parque y cuello de botella
    startrow = 0
    LINEAS_OPS.to_excel(xw, sheet_name="03_Parque_y_cuello", index=False, startrow=startrow)
    startrow += len(LINEAS_OPS) + 3
    CRITICAS.to_excel(xw, sheet_name="03_Parque_y_cuello", index=False, startrow=startrow)
    startrow += len(CRITICAS) + 3
    pd.DataFrame({
        "Nota": [
            f"Total teórico L1–L4: {OPS_TEORICA_DIA:,.0f} ops/día · "
            f"real {OPS_REAL_DIA:,.0f} · pérdida {OPS_TEORICA_DIA - OPS_REAL_DIA:,.1f} "
            f"({1 - OPS_REAL_DIA / OPS_TEORICA_DIA:.1%})".replace(",", "."),
            "L1 y L2 tienen 4 posiciones (un solo ruedo). L3 y L4 tienen 5 (dos ruedos), "
            "pero el segundo está inactivo en ambas: prometen 785 y entregan 634,5 y 685.",
            "El ruedo nace a la mitad del overlock (101 vs 190 ops/día). Es el cuello "
            "estructural, no una avería puntual.",
            "Las capacidades individuales de Collaretera recubrir y Overlock montaje/cierre "
            "no están publicadas por máquina; su suma es 394 ops/día. Maquinas Activas.xlsx las cierra.",
            "Fuera del KPI: 2 Overlock de cuellos inactivos por falta de personal y "
            "2 rectas activas compartidas entre 4 líneas.",
            "Parque en el KPI: 22 máquinas · 18 activas (82%) · 4 inactivas o parciales (18%) · "
            "2 son chatarra (9% del parque).",
        ]
    }).to_excel(xw, sheet_name="03_Parque_y_cuello", index=False, startrow=startrow)

    # Tasas por modelo y estado
    tasas_df = pd.DataFrame([
        {
            "Modelo": m,
            "Ops por pieza": OPS_PIEZA[m],
            "Peso en el mix": MIX[m],
            "A · Actual (pzas/línea/día)": TASAS["A_real"][m],
            "B · Diseño o JACK K7": TASAS["B_teor"][m],
            "C · Módulo continuo": TASAS["C_modulo"][m],
            "B vs A": TASAS["B_teor"][m] / TASAS["A_real"][m] - 1,
            "C vs A": TASAS["C_modulo"][m] / TASAS["A_real"][m] - 1,
        }
        for m in ["MAR", "RIO", "Basic Line"]
    ])
    tasas_df.loc[len(tasas_df)] = {
        "Modelo": "MIX PONDERADO", "Ops por pieza": round(OPS_PZA, 2), "Peso en el mix": 1.0,
        "A · Actual (pzas/línea/día)": round(TASA_A, 2),
        "B · Diseño o JACK K7": round(TASA_B, 2),
        "C · Módulo continuo": round(TASA_C, 2),
        "B vs A": TASA_B / TASA_A - 1, "C vs A": TASA_C / TASA_A - 1,
    }
    tasas_df.to_excel(xw, sheet_name="04_Tasas_por_estado", index=False)

    # Escenarios
    esc_out = esc.rename(columns={
        "clave": "Clave", "escenario": "Escenario", "lineas_punto": "Líneas de punto",
        "maquinas_nuevas": "Máquinas nuevas", "punto_bruto": "Punto bruto pzas/mes",
        "linea5": "Shorts pzas/mes", "total_bruto": "TOTAL BRUTO pzas/mes",
        "tasa_reproceso": "Tasa reproceso", "factor_neto": "Factor neto",
        "total_neto": "TOTAL NETO pzas/mes", "delta_neto": "Δ neto vs actual",
        "delta_pct": "Δ %", "pzas_por_maquina": "Piezas ganadas por máquina",
        "nota": "Configuración",
    })
    esc_out.to_excel(xw, sheet_name="05_Escenarios", index=False)

    # Desglose por modelo de cada escenario
    desg = []
    for clave, etiqueta, estados, *_ in ESCENARIOS:
        d = detalle_por_modelo(estados)
        for m, v in d.items():
            desg.append({
                "Clave": clave, "Escenario": etiqueta, "Modelo": m,
                "Días-línea del mes": round(v["dias_linea"], 1),
                "Tasa media pzas/línea/día": round(v["tasa"], 2),
                "Piezas/mes": round(v["piezas"]),
            })
    pd.DataFrame(desg).to_excel(xw, sheet_name="06_Desglose_por_modelo", index=False)

    # Demanda y déficit
    dem_df = pd.DataFrame(
        [{"Clave": k, "Escenario de demanda": l, "Piezas/mes": v} for k, l, v in DEMANDAS]
    )
    dem_df["vs demanda regular"] = dem_df["Piezas/mes"] / DEM_REGULAR
    dem_df.to_excel(xw, sheet_name="07_Demanda", index=False, startrow=0)
    pd.DataFrame({
        "Nota": [
            f"Demanda regular {DEM_REGULAR:,} y pico diciembre {DEM_PICO:,} piezas/mes: dato de Gerencia.".replace(",", "."),
            f"El pico es {DEM_PICO / DEM_REGULAR:.2f}× la demanda regular.",
            f"Factores de red derivados de los escenarios en operaciones del expediente: "
            f"58.800 → 69.732 (+1 tienda, ×{F_1T:.4f}) → 87.166 (+3 tiendas/año, ×{F_3T:.4f}).",
            "La Grieta ≈ 20% del pico de la red. Margarita se modela entre 1× y 2× Grieta.",
        ]
    }).to_excel(xw, sheet_name="07_Demanda", index=False, startrow=len(dem_df) + 3)

    d_out = deficit.rename(columns={"clave_dem": "Clave", "demanda": "Escenario de demanda",
                                    "piezas_dem": "Demanda pzas/mes"})
    d_out.to_excel(xw, sheet_name="08_Deficit", index=False, startrow=0)
    c_out = cobertura.rename(columns={"clave_dem": "Clave", "demanda": "Escenario de demanda",
                                      "piezas_dem": "Demanda pzas/mes"})
    c_out.to_excel(xw, sheet_name="08_Deficit", index=False, startrow=len(d_out) + 3)
    pd.DataFrame({
        "Nota": [
            "Bloque 1: superávit (+) o déficit (−) en piezas de primera calidad por mes.",
            "Bloque 2: cobertura = capacidad neta ÷ demanda. Por debajo de 1,00 no se cubre.",
        ]
    }).to_excel(xw, sheet_name="08_Deficit", index=False, startrow=2 * len(d_out) + 6)

    # Calidad
    cal = pd.DataFrame({
        "Concepto": ["Piezas inspeccionadas", "Piezas rechazadas", "Tasa de reproceso",
                     "Contenido de retrabajo (supuesto central)",
                     "Capacidad consumida por retrabajo", "Factor neto de primera calidad",
                     "Reproceso residual con parque nuevo (supuesto)",
                     "Factor neto con parque nuevo"],
        "Valor": [QA_INSPECCIONADAS, QA_RECHAZADAS, f"{TASA_REPROCESO:.2%}",
                  f"{RETRABAJO_CONTENIDO:.0%}",
                  f"{TASA_REPROCESO * RETRABAJO_CONTENIDO:.2%} de la capacidad bruta",
                  round(factor_neto(TASA_REPROCESO), 4),
                  f"{REPROCESO_NUEVO:.1%}",
                  round(factor_neto(REPROCESO_NUEVO), 4)],
        "Fuente o criterio": [
            "Analisis_Tasa_Retrocesos_QA · promedio mensual abr–ago 2026",
            "Analisis_Tasa_Retrocesos_QA", "1.695 / 10.502",
            "Supuesto: los defectos documentados se concentran en acabado "
            "(ruedo, remate, limpieza de hilo, lavado por aceite)",
            "Tasa × contenido", "1 / (1 + tasa × contenido)",
            "Justificación técnica de calidad (Brayan Machado): ondas, ruedos abiertos, "
            "hilos, aceite, cortes y fruncido son atribuibles a máquina",
            "1 / (1 + 0,060 × 0,35)",
        ],
    })
    cal.to_excel(xw, sheet_name="09_Calidad_y_sensibilidad", index=False, startrow=0)
    SENSIBILIDAD.to_excel(xw, sheet_name="09_Calidad_y_sensibilidad", index=False,
                          startrow=len(cal) + 3)
    pd.DataFrame({
        "Nota": [
            "La tabla de abajo mueve el contenido de retrabajo entre 20% y 100% y muestra "
            "la capacidad NETA resultante de cada escenario. El ranking de escenarios no cambia; "
            "cambia la magnitud del déficit.",
            "Para cerrarlo hace falta el dato P0: minutos de retrabajo por prenda.",
        ]
    }).to_excel(xw, sheet_name="09_Calidad_y_sensibilidad", index=False,
                startrow=len(cal) + len(SENSIBILIDAD) + 6)

    EXCLUSIVA.to_excel(xw, sheet_name="10_Capacidad_exclusiva", index=False)
    COMPRA.to_excel(xw, sheet_name="11_Paquete_de_compra", index=False)
    FALTANTES.to_excel(xw, sheet_name="12_Datos_faltantes", index=False)

    # Autoajuste de anchos
    for ws in xw.book.worksheets:
        for col in ws.columns:
            largo = max((len(str(c.value)) for c in col if c.value is not None), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(max(largo + 2, 12), 70)

print(f"Excel escrito: {xlsx}")


# ---------------------------------------------------------------------------
# 7. FIGURAS
# ---------------------------------------------------------------------------

INK = "#12263A"
AZUL = "#2C6E9B"
VERDE = "#2A9D8F"
ROJO = "#C0392B"
AMBAR = "#D89B2C"
GRIS = "#8A8578"
BG = "#FFFFFF"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.edgecolor": "#CFC8B8",
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "figure.facecolor": BG,
    "axes.facecolor": BG,
})
miles = FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", "."))


def guardar(fig, nombre):
    ruta = os.path.join(FIGS, nombre)
    fig.savefig(ruta, dpi=170, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print("  fig:", nombre)


# F1 — Capacidad actual en piezas: teórica vs real vs neta
fig, ax = plt.subplots(figsize=(9, 4.6))
et = ["Teórica\n(parque íntegro)", "Real\n(parque hoy)", "Neta de primera\n(tras retrabajo QA)"]
teor = piezas_mes(["B_teor"] * 4) + L5_MES
real = piezas_mes(["A_real"] * 4) + L5_MES
neto = real * factor_neto(TASA_REPROCESO)
vals = [teor, real, neto]
cols = [AZUL, AMBAR, ROJO]
b = ax.bar(et, vals, color=cols, width=0.55)
for r, v in zip(b, vals):
    ax.text(r.get_x() + r.get_width() / 2, v + 90, f"{v:,.0f}".replace(",", "."),
            ha="center", fontweight="bold", fontsize=12)
ax.axhline(DEM_PICO, color=INK, ls="--", lw=1.4)
ax.text(2.42, DEM_PICO + 90, f"Pico diciembre {DEM_PICO:,}".replace(",", "."),
        ha="right", fontsize=9, fontweight="bold")
ax.axhline(DEM_REGULAR, color=VERDE, ls=":", lw=1.6)
ax.text(2.42, DEM_REGULAR + 90, f"Demanda regular {DEM_REGULAR:,}".replace(",", "."),
        ha="right", fontsize=9, color=VERDE, fontweight="bold")
ax.set_ylabel("Piezas / mes")
ax.set_title("Capacidad instalada del taller en piezas por mes", fontweight="bold", loc="left")
ax.set_ylim(0, max(vals + [DEM_PICO]) * 1.18)
ax.yaxis.set_major_formatter(miles)
ax.spines[["top", "right"]].set_visible(False)
guardar(fig, "01_capacidad_actual_piezas.png")

# F2 — Escenarios de capacidad neta vs las dos demandas
ETIQ_CORTA = {
    "S0": "Actual\nREAL", "S0T": "Actual\nTEÓRICA",
    "S21a": "2.1a\ncorta mínima\n6 máq.", "S21b": "2.1b\ncorta recom.\n12 máq.",
    "S22a": "2.2a\n4 módulos\n20 máq.", "S22b": "2.2b\n5 mód. + L5\n33 máq.",
    "S22c": "2.2c\n6 mód. + L5\n38 máq.",
}
fig, ax = plt.subplots(figsize=(11, 5.4))
x = np.arange(len(esc))
colores = [AMBAR, GRIS, "#5B8DB8", AZUL, "#3E8F7F", VERDE, "#1E6E5E"]
b = ax.bar(x, esc["total_neto"], color=colores, width=0.62)
for r, v in zip(b, esc["total_neto"]):
    ax.text(r.get_x() + r.get_width() / 2, v + 140, f"{v:,.0f}".replace(",", "."),
            ha="center", fontweight="bold", fontsize=10.5)
ax.axhline(DEM_PICO, color=ROJO, ls="--", lw=1.6)
ax.text(-0.42, DEM_PICO + 190, f"Pico diciembre {DEM_PICO:,}".replace(",", "."),
        ha="left", color=ROJO, fontsize=9.5, fontweight="bold")
ax.axhline(DEM_REGULAR, color="#1E6E5E", ls=":", lw=1.8)
ax.text(-0.42, DEM_REGULAR + 190, f"Demanda regular {DEM_REGULAR:,}".replace(",", "."),
        ha="left", color="#1E6E5E", fontsize=9.5, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels([ETIQ_CORTA[k] for k in esc["clave"]], fontsize=8.8)
ax.set_ylabel("Piezas de primera calidad / mes")
ax.set_title("Capacidad neta por escenario de inversión", fontweight="bold", loc="left")
ax.yaxis.set_major_formatter(miles)
ax.set_ylim(0, esc["total_neto"].max() * 1.14)
ax.spines[["top", "right"]].set_visible(False)
guardar(fig, "02_escenarios_capacidad_neta.png")

# F3 — Mapa de déficit: escenarios × demandas
fig, ax = plt.subplots(figsize=(10.5, 4.6))
M = np.array([[deficit.loc[i, r["clave"]] for _, r in esc.iterrows()]
              for i in range(len(deficit))], dtype=float)
lim = np.abs(M).max()
im = ax.imshow(M, cmap="RdYlGn", vmin=-lim, vmax=lim, aspect="auto")
ax.set_xticks(range(len(esc)))
ax.set_xticklabels(esc["clave"], fontsize=9.5, fontweight="bold")
ax.set_yticks(range(len(deficit)))
ax.set_yticklabels(deficit["demanda"], fontsize=9)
for i in range(M.shape[0]):
    for j in range(M.shape[1]):
        v = M[i, j]
        ax.text(j, i, f"{v:+,.0f}".replace(",", "."), ha="center", va="center",
                fontsize=8.6, fontweight="bold",
                color="#7A1B10" if v < 0 else "#12463A")
ax.set_title("Superávit (+) o déficit (−) de piezas por mes · capacidad neta − demanda",
             fontweight="bold", loc="left")
fig.colorbar(im, ax=ax, shrink=0.85, label="Piezas / mes")
guardar(fig, "03_mapa_deficit.png")

# F4 — Déficit en los tres momentos de demanda para los escenarios clave
fig, ax = plt.subplots(figsize=(10.5, 5))
claves = ["S0", "S0T", "S21a", "S21b", "S22a", "S22b", "S22c"]
etq = {"S0": "Actual real", "S0T": "Actual teórica", "S21a": "2.1a corta mín.",
       "S21b": "2.1b corta rec.", "S22a": "2.2a 4 módulos",
       "S22b": "2.2b 5 mód.+L5", "S22c": "2.2c 6 mód.+L5"}
grupos = [("Regular · red actual", "D1"), ("Pico dic. · red actual", "D4"),
          ("Pico dic. · +1 tienda", "D5"), ("Pico dic. · +3 tiendas", "D6")]
w = 0.2
xg = np.arange(len(claves))
pal = [VERDE, AMBAR, "#D2691E", ROJO]
for gi, (gl, gk) in enumerate(grupos):
    fila = deficit[deficit["clave_dem"] == gk].iloc[0]
    vals = [fila[c] for c in claves]
    ax.bar(xg + (gi - 1.5) * w, vals, width=w, label=gl, color=pal[gi])
ax.axhline(0, color=INK, lw=1.2)
ax.set_xticks(xg)
ax.set_xticklabels([etq[c] for c in claves], fontsize=8.6)
ax.set_ylabel("Superávit (+) / déficit (−) piezas/mes")
ax.set_title("Déficit de capacidad por período de demanda y por escenario",
             fontweight="bold", loc="left")
ax.yaxis.set_major_formatter(miles)
ax.legend(fontsize=8.6, frameon=False, ncol=2)
ax.spines[["top", "right"]].set_visible(False)
guardar(fig, "04_deficit_por_periodo.png")

# F5 — Cuello de botella: ruedo vs overlock
fig, ax = plt.subplots(figsize=(9, 4.4))
est = ["Overlock\nUnión/Montaje", "Overlock\nMontaje/Cierre\n+ Collaret recubrir\n(suma 394)",
       "Collaretera\nde ruedo"]
cap = [190, 394 / 2, 101]
b = ax.bar(est, cap, color=[AZUL, AZUL, ROJO], width=0.5)
for r, v in zip(b, cap):
    ax.text(r.get_x() + r.get_width() / 2, v + 4, f"{v:,.0f}".replace(",", "."),
            ha="center", fontweight="bold")
ax.axhline(101, color=ROJO, ls="--", lw=1.3)
ax.text(2.45, 108, "El ruedo marca el techo de toda la línea", ha="right",
        color=ROJO, fontsize=9, fontweight="bold")
ax.set_ylabel("Operaciones / día por máquina")
ax.set_title("El cuello estructural: el ruedo nace a la mitad del overlock",
             fontweight="bold", loc="left")
ax.spines[["top", "right"]].set_visible(False)
guardar(fig, "05_cuello_ruedo.png")

# F6 — Piezas ganadas por máquina nueva (eficiencia del capex)
fig, ax = plt.subplots(figsize=(9.5, 4.4))
sub = esc[esc["maquinas_nuevas"] > 0]
b = ax.bar(sub["clave"], sub["pzas_por_maquina"],
           color=["#5B8DB8", AZUL, "#3E8F7F", VERDE, "#1E6E5E"], width=0.55)
for r, v, n in zip(b, sub["pzas_por_maquina"], sub["maquinas_nuevas"]):
    ax.text(r.get_x() + r.get_width() / 2, v + 3,
            f"{v:,.0f}".replace(",", ".") + f"\n{n} máq.", ha="center",
            fontweight="bold", fontsize=9)
ax.set_ylabel("Piezas/mes ganadas por máquina nueva")
ax.set_title("Rendimiento marginal de cada paquete de inversión",
             fontweight="bold", loc="left")
ax.set_ylim(0, sub["pzas_por_maquina"].max() * 1.28)
ax.spines[["top", "right"]].set_visible(False)
guardar(fig, "06_piezas_por_maquina.png")

# F7 — Efecto del reproceso
fig, ax = plt.subplots(figsize=(9.5, 4.4))
et2 = ["Actual", "2.1a", "2.1b", "2.2a", "2.2b", "2.2c"]
kk = ["S0", "S21a", "S21b", "S22a", "S22b", "S22c"]
brutos = [esc.loc[esc["clave"] == k, "total_bruto"].iloc[0] for k in kk]
netos = [esc.loc[esc["clave"] == k, "total_neto"].iloc[0] for k in kk]
xx = np.arange(len(kk))
ax.bar(xx - 0.19, brutos, width=0.38, label="Capacidad bruta (sale de línea)", color=GRIS)
ax.bar(xx + 0.19, netos, width=0.38, label="Capacidad neta de primera calidad", color=VERDE)
for i, (bv, nv) in enumerate(zip(brutos, netos)):
    ax.text(i - 0.19, bv + 90, f"{bv:,.0f}".replace(",", "."), ha="center", fontsize=8.4)
    ax.text(i + 0.19, nv + 90, f"{nv:,.0f}".replace(",", "."), ha="center", fontsize=8.4,
            fontweight="bold")
ax.set_xticks(xx)
ax.set_xticklabels(et2)
ax.set_ylabel("Piezas / mes")
ax.set_title(f"Lo que se lleva el retrabajo · tasa QA medida {TASA_REPROCESO:.2%}",
             fontweight="bold", loc="left")
ax.yaxis.set_major_formatter(miles)
ax.legend(fontsize=8.8, frameon=False)
ax.spines[["top", "right"]].set_visible(False)
guardar(fig, "07_efecto_reproceso.png")

# F8 — Escalera de decisión: capacidad vs demanda de red
fig, ax = plt.subplots(figsize=(10.5, 5))
red = ["Red actual", "+1 tienda", "+3 tiendas/año"]
dpico = [DEM_PICO, round(DEM_PICO * F_1T), round(DEM_PICO * F_3T)]
dreg = [DEM_REGULAR, round(DEM_REGULAR * F_1T), round(DEM_REGULAR * F_3T)]
xr = np.arange(3)
ax.bar(xr - 0.2, dreg, width=0.38, color="#BBD8CF", label="Demanda regular")
ax.bar(xr + 0.2, dpico, width=0.38, color="#E9A6A0", label="Demanda pico diciembre")
for k, c, ls in [("S0", AMBAR, "-"), ("S21b", AZUL, "--"), ("S22b", VERDE, "-."),
                 ("S22c", "#1E6E5E", ":")]:
    v = esc.loc[esc["clave"] == k, "total_neto"].iloc[0]
    ax.axhline(v, color=c, ls=ls, lw=1.8,
               label=f"{etq[k]} · {v:,.0f} pzas".replace(",", "."))
for i, (a, p) in enumerate(zip(dreg, dpico)):
    ax.text(i - 0.2, a + 110, f"{a:,.0f}".replace(",", "."), ha="center", fontsize=8.6)
    ax.text(i + 0.2, p + 110, f"{p:,.0f}".replace(",", "."), ha="center", fontsize=8.6,
            fontweight="bold")
ax.set_xticks(xr)
ax.set_xticklabels(red)
ax.set_ylabel("Piezas / mes")
ax.set_title("Escalera de decisión: qué escenario cubre qué red",
             fontweight="bold", loc="left")
ax.yaxis.set_major_formatter(miles)
ax.legend(fontsize=8.2, frameon=False, ncol=2, loc="upper left")
ax.set_ylim(0, max(dpico + [esc["total_neto"].max()]) * 1.3)
ax.spines[["top", "right"]].set_visible(False)
guardar(fig, "08_escalera_decision.png")


# ---------------------------------------------------------------------------
# 8. JSON PARA EL DASHBOARD
# ---------------------------------------------------------------------------

payload = {
    "corte": "Septiembre 2026",
    "dias": DIAS,
    "mix": MIX,
    "ops_pieza": OPS_PIEZA,
    "ops_pieza_mix": round(OPS_PZA, 2),
    "tasas": TASAS,
    "tasa_mix": {"A": round(TASA_A, 2), "B": round(TASA_B, 2), "C": round(TASA_C, 2)},
    "linea5_mes": L5_MES,
    "ops": {
        "teorica_dia": OPS_TEORICA_DIA, "real_dia": OPS_REAL_DIA,
        "teorica_mes": OPS_TEORICA_MES, "real_mes": OPS_REAL_MES,
        "utilizacion": round(OPS_REAL_DIA / OPS_TEORICA_DIA, 4),
        "pzas_metodo_ops": round(PZAS_POR_OPS_REAL),
        "pzas_metodo_cuello": round(PZAS_MODELO_REAL),
        "sobreestimacion": round(SOBREESTIMACION, 4),
    },
    "calidad": {
        "inspeccionadas": QA_INSPECCIONADAS, "rechazadas": QA_RECHAZADAS,
        "tasa": round(TASA_REPROCESO, 4), "contenido": RETRABAJO_CONTENIDO,
        "factor_actual": round(factor_neto(TASA_REPROCESO), 4),
        "reproceso_nuevo": REPROCESO_NUEVO,
    },
    "demanda": {"regular": DEM_REGULAR, "pico": DEM_PICO,
                "f_1t": round(F_1T, 5), "f_3t": round(F_3T, 5),
                "escenarios": [{"clave": k, "label": l, "piezas": v} for k, l, v in DEMANDAS]},
    "escenarios": esc.to_dict(orient="records"),
    "deficit": deficit.to_dict(orient="records"),
    "cobertura": cobertura.to_dict(orient="records"),
    "lineas_ops": LINEAS_OPS.round(2).to_dict(orient="records"),
    "criticas": CRITICAS.to_dict(orient="records"),
    "exclusiva": EXCLUSIVA.to_dict(orient="records"),
    "compra": COMPRA.to_dict(orient="records"),
    "sensibilidad": SENSIBILIDAD.to_dict(orient="records"),
    "faltantes": FALTANTES.to_dict(orient="records"),
}
with open(os.path.join(BASE, "datos_modelo.json"), "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=1)

# El dashboard se abre con file://, donde fetch() está bloqueado por CORS.
# Se emite el mismo payload como script cargable con <script src>.
with open(os.path.join(BASE, "datos_modelo.js"), "w", encoding="utf-8") as f:
    f.write("/* Generado por modelo_capacidad.py — no editar a mano. */\n")
    f.write("const DATA = ")
    json.dump(payload, f, ensure_ascii=False, indent=1)
    f.write(";\n")

# ---------------------------------------------------------------------------
# 9. RESUMEN EN CONSOLA
# ---------------------------------------------------------------------------

print("\n" + "=" * 78)
print("PARÁMETROS")
print("=" * 78)
print(f"Ops por pieza del mix          : {OPS_PZA:.2f}")
print(f"Tasa al mix A / B / C          : {TASA_A:.2f} / {TASA_B:.2f} / {TASA_C:.2f} pzas/línea/día")
print(f"Validación B vs A              : {TASA_B/TASA_A-1:+.1%}  (dashboard: +11,0%)")
print(f"Validación C vs A              : {TASA_C/TASA_A-1:+.1%}  (dashboard: +37,7%)")
print(f"Validación C · 4 líneas        : {piezas_mes(['C_modulo']*4):,.0f} pzas/mes  (dashboard: 8.940)")
print(f"Tasa de reproceso QA           : {TASA_REPROCESO:.2%}")
print(f"Factor neto actual             : {factor_neto(TASA_REPROCESO):.4f}")
print(f"Sobreestimación método de ops  : {SOBREESTIMACION:+.1%} "
      f"({PZAS_POR_OPS_REAL:,.0f} vs {PZAS_MODELO_REAL:,.0f} pzas/mes)")

print("\n" + "=" * 78)
print("ESCENARIOS (piezas/mes)")
print("=" * 78)
print(esc[["clave", "escenario", "maquinas_nuevas", "total_bruto",
           "tasa_reproceso", "total_neto", "delta_neto", "delta_pct"]]
      .to_string(index=False,
                 formatters={"tasa_reproceso": "{:.2%}".format,
                             "delta_pct": "{:+.1%}".format}))

print("\n" + "=" * 78)
print("DÉFICIT (+ superávit / − déficit, piezas/mes de primera calidad)")
print("=" * 78)
print(deficit.to_string(index=False))

print("\n" + "=" * 78)
print("COBERTURA (capacidad neta / demanda)")
print("=" * 78)
print(cobertura.to_string(index=False,
                          formatters={c: "{:.2f}".format for c in esc["clave"]}))
print("\nListo.")

# Reempaqueta el dashboard autocontenido (Chart.js + datos incrustados).
pack = os.path.join(BASE, "empaquetar_dashboard.py")
if os.path.exists(pack):
    import runpy
    runpy.run_path(pack, run_name="__main__")
