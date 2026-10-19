/* Generado por modelo_capacidad.py — no editar a mano. */
const DATA = {
 "corte": "Septiembre 2026",
 "dias": 20,
 "mix": {
  "MAR": 0.5,
  "RIO": 0.35,
  "Basic Line": 0.15
 },
 "ops_pieza": {
  "MAR": 7,
  "RIO": 6,
  "Basic Line": 12
 },
 "ops_pieza_mix": 7.4,
 "tasas": {
  "A_real": {
   "MAR": 95,
   "RIO": 73,
   "Basic Line": 55
  },
  "B_teor": {
   "MAR": 105,
   "RIO": 82,
   "Basic Line": 61
  },
  "C_modulo": {
   "MAR": 130,
   "RIO": 101,
   "Basic Line": 76
  }
 },
 "tasa_mix": {
  "A": 81.3,
  "B": 90.35,
  "C": 111.75
 },
 "linea5_mes": 900,
 "ops": {
  "teorica_dia": 2940.0,
  "real_dia": 2649.5,
  "teorica_mes": 58800.0,
  "real_mes": 52990.0,
  "utilizacion": 0.9012,
  "pzas_metodo_ops": 7161,
  "pzas_metodo_cuello": 6504,
  "sobreestimacion": 0.101
 },
 "calidad": {
  "inspeccionadas": 10502,
  "rechazadas": 1695,
  "tasa": 0.1614,
  "contenido": 0.35,
  "factor_actual": 0.9465,
  "reproceso_nuevo": 0.06
 },
 "demanda": {
  "regular": 4145,
  "pico": 8576,
  "f_1t": 1.18592,
  "f_3t": 1.48241,
  "escenarios": [
   {
    "clave": "D1",
    "label": "Regular · red actual",
    "piezas": 4145
   },
   {
    "clave": "D2",
    "label": "Regular · +1 tienda",
    "piezas": 4916
   },
   {
    "clave": "D3",
    "label": "Regular · +3 tiendas/año",
    "piezas": 6145
   },
   {
    "clave": "D4",
    "label": "Pico diciembre · red actual",
    "piezas": 8576
   },
   {
    "clave": "D5",
    "label": "Pico diciembre · +1 tienda",
    "piezas": 10170
   },
   {
    "clave": "D6",
    "label": "Pico diciembre · +3 tiendas/año",
    "piezas": 12713
   }
  ]
 },
 "escenarios": [
  {
   "clave": "S0",
   "escenario": "0 · Actual REAL",
   "lineas_punto": 4,
   "maquinas_nuevas": 0,
   "punto_bruto": 6504,
   "linea5": 900,
   "total_bruto": 7404,
   "tasa_reproceso": 0.16139782898495525,
   "factor_neto": 0.9465311732498141,
   "total_neto": 7008,
   "nota": "Parque hoy: 4 máquinas inactivas o parciales, merma 10%.",
   "delta_neto": 0,
   "delta_pct": 0.0,
   "pzas_por_maquina": NaN
  },
  {
   "clave": "S0T",
   "escenario": "0T · Actual TEÓRICA",
   "lineas_punto": 4,
   "maquinas_nuevas": 0,
   "punto_bruto": 7228,
   "linea5": 900,
   "total_bruto": 8128,
   "tasa_reproceso": 0.16139782898495525,
   "factor_neto": 0.9465311732498141,
   "total_neto": 7693,
   "nota": "Mismo layout con las 22 máquinas al 100%. Es el techo que el taller declara.",
   "delta_neto": 685,
   "delta_pct": 0.09774543378995437,
   "pzas_por_maquina": NaN
  },
  {
   "clave": "S21a",
   "escenario": "2.1a · Inversión corta MÍNIMA",
   "lineas_punto": 4,
   "maquinas_nuevas": 6,
   "punto_bruto": 7656,
   "linea5": 900,
   "total_bruto": 8556,
   "tasa_reproceso": 0.14111826318796422,
   "factor_neto": 0.9529332978268438,
   "total_neto": 8153,
   "nota": "L3 a módulo continuo JACK (5 máq.) + Overlock L2 (1 máq.). Recupera L4 con kit.",
   "delta_neto": 1145,
   "delta_pct": 0.16338470319634713,
   "pzas_por_maquina": 190.83333333333334
  },
  {
   "clave": "S21b",
   "escenario": "2.1b · Inversión corta RECOMENDADA",
   "lineas_punto": 4,
   "maquinas_nuevas": 12,
   "punto_bruto": 8084,
   "linea5": 900,
   "total_bruto": 8984,
   "tasa_reproceso": 0.12083869739097314,
   "factor_neto": 0.9594226172398542,
   "total_neto": 8619,
   "nota": "L3 y L4 a módulos continuos JACK (10 máq.) + collaretera de ruedo en L1 y L2.",
   "delta_neto": 1611,
   "delta_pct": 0.22988013698630128,
   "pzas_por_maquina": 134.25
  },
  {
   "clave": "S22a",
   "escenario": "2.2a · Ambiciosa · 4 módulos",
   "lineas_punto": 4,
   "maquinas_nuevas": 20,
   "punto_bruto": 8940,
   "linea5": 900,
   "total_bruto": 9840,
   "tasa_reproceso": 0.08027956579699105,
   "factor_neto": 0.972670064349599,
   "total_neto": 9571,
   "nota": "Las 4 líneas de punto a módulo continuo JACK de 5 máquinas.",
   "delta_neto": 2563,
   "delta_pct": 0.3657248858447488,
   "pzas_por_maquina": 128.15
  },
  {
   "clave": "S22b",
   "escenario": "2.2b · Ambiciosa · 5 módulos + Línea 5",
   "lineas_punto": 5,
   "maquinas_nuevas": 33,
   "punto_bruto": 11175,
   "linea5": 900,
   "total_bruto": 12075,
   "tasa_reproceso": 0.06,
   "factor_neto": 0.9794319294809012,
   "total_neto": 11827,
   "nota": "5ª línea de punto + Línea 5 de shorts completada y renovada.",
   "delta_neto": 4819,
   "delta_pct": 0.6876426940639269,
   "pzas_por_maquina": 146.03030303030303
  },
  {
   "clave": "S22c",
   "escenario": "2.2c · Ambiciosa · 6 módulos + Línea 5",
   "lineas_punto": 6,
   "maquinas_nuevas": 38,
   "punto_bruto": 13410,
   "linea5": 900,
   "total_bruto": 14310,
   "tasa_reproceso": 0.06,
   "factor_neto": 0.9794319294809012,
   "total_neto": 14016,
   "nota": "6ª línea de punto. Dimensionado para 3 tiendas nuevas por año en pico.",
   "delta_neto": 7008,
   "delta_pct": 1.0,
   "pzas_por_maquina": 184.42105263157896
  }
 ],
 "deficit": [
  {
   "clave_dem": "D1",
   "demanda": "Regular · red actual",
   "piezas_dem": 4145,
   "S0": 2863,
   "S0T": 3548,
   "S21a": 4008,
   "S21b": 4474,
   "S22a": 5426,
   "S22b": 7682,
   "S22c": 9871
  },
  {
   "clave_dem": "D2",
   "demanda": "Regular · +1 tienda",
   "piezas_dem": 4916,
   "S0": 2092,
   "S0T": 2777,
   "S21a": 3237,
   "S21b": 3703,
   "S22a": 4655,
   "S22b": 6911,
   "S22c": 9100
  },
  {
   "clave_dem": "D3",
   "demanda": "Regular · +3 tiendas/año",
   "piezas_dem": 6145,
   "S0": 863,
   "S0T": 1548,
   "S21a": 2008,
   "S21b": 2474,
   "S22a": 3426,
   "S22b": 5682,
   "S22c": 7871
  },
  {
   "clave_dem": "D4",
   "demanda": "Pico diciembre · red actual",
   "piezas_dem": 8576,
   "S0": -1568,
   "S0T": -883,
   "S21a": -423,
   "S21b": 43,
   "S22a": 995,
   "S22b": 3251,
   "S22c": 5440
  },
  {
   "clave_dem": "D5",
   "demanda": "Pico diciembre · +1 tienda",
   "piezas_dem": 10170,
   "S0": -3162,
   "S0T": -2477,
   "S21a": -2017,
   "S21b": -1551,
   "S22a": -599,
   "S22b": 1657,
   "S22c": 3846
  },
  {
   "clave_dem": "D6",
   "demanda": "Pico diciembre · +3 tiendas/año",
   "piezas_dem": 12713,
   "S0": -5705,
   "S0T": -5020,
   "S21a": -4560,
   "S21b": -4094,
   "S22a": -3142,
   "S22b": -886,
   "S22c": 1303
  }
 ],
 "cobertura": [
  {
   "clave_dem": "D1",
   "demanda": "Regular · red actual",
   "piezas_dem": 4145,
   "S0": 1.6907117008443908,
   "S0T": 1.8559710494571773,
   "S21a": 1.9669481302774428,
   "S21b": 2.079372738238842,
   "S22a": 2.309047044632087,
   "S22b": 2.853317249698432,
   "S22c": 3.3814234016887816
  },
  {
   "clave_dem": "D2",
   "demanda": "Regular · +1 tienda",
   "piezas_dem": 4916,
   "S0": 1.4255492270138324,
   "S0T": 1.5648901545972336,
   "S21a": 1.6584621643612694,
   "S21b": 1.7532546786004881,
   "S22a": 1.9469080553295361,
   "S22b": 2.4058177379983725,
   "S22c": 2.8510984540276647
  },
  {
   "clave_dem": "D3",
   "demanda": "Regular · +3 tiendas/año",
   "piezas_dem": 6145,
   "S0": 1.1404393816110658,
   "S0T": 1.2519121236777868,
   "S21a": 1.3267697314890154,
   "S21b": 1.4026037428803906,
   "S22a": 1.557526444263629,
   "S22b": 1.9246541903986982,
   "S22c": 2.2808787632221317
  },
  {
   "clave_dem": "D4",
   "demanda": "Pico diciembre · red actual",
   "piezas_dem": 8576,
   "S0": 0.8171641791044776,
   "S0T": 0.8970382462686567,
   "S21a": 0.9506763059701493,
   "S21b": 1.0050139925373134,
   "S22a": 1.1160214552238805,
   "S22b": 1.3790811567164178,
   "S22c": 1.6343283582089552
  },
  {
   "clave_dem": "D5",
   "demanda": "Pico diciembre · +1 tienda",
   "piezas_dem": 10170,
   "S0": 0.6890855457227139,
   "S0T": 0.7564405113077679,
   "S21a": 0.8016715830875123,
   "S21b": 0.8474926253687316,
   "S22a": 0.9411012782694199,
   "S22b": 1.162930186823992,
   "S22c": 1.3781710914454277
  },
  {
   "clave_dem": "D6",
   "demanda": "Pico diciembre · +3 tiendas/año",
   "piezas_dem": 12713,
   "S0": 0.5512467552898608,
   "S0T": 0.605128608510973,
   "S21a": 0.641312042790844,
   "S21b": 0.6779674349091481,
   "S22a": 0.7528514119405333,
   "S22b": 0.9303075591913789,
   "S22c": 1.1024935105797216
  }
 ],
 "lineas_ops": [
  {
   "Línea": "Línea 1",
   "Teórica ops/día": 685.0,
   "Real ops/día": 685.0,
   "Pérdida": 0.0,
   "Utilización": 1.0
  },
  {
   "Línea": "Línea 2",
   "Teórica ops/día": 685.0,
   "Real ops/día": 645.0,
   "Pérdida": 40.0,
   "Utilización": 0.94
  },
  {
   "Línea": "Línea 3",
   "Teórica ops/día": 785.0,
   "Real ops/día": 634.5,
   "Pérdida": 150.5,
   "Utilización": 0.81
  },
  {
   "Línea": "Línea 4",
   "Teórica ops/día": 785.0,
   "Real ops/día": 685.0,
   "Pérdida": 100.0,
   "Utilización": 0.87
  }
 ],
 "criticas": [
  {
   "Línea": "Línea 3",
   "Máquina": "Collaretera de ruedo 1",
   "Estatus": "Parcial 50%",
   "Teórica ops/día": 101,
   "Real ops/día": 50.5,
   "Pérdida ops/día": 50.5
  },
  {
   "Línea": "Línea 3",
   "Máquina": "Collaretera de ruedo 2",
   "Estatus": "Inactiva",
   "Teórica ops/día": 100,
   "Real ops/día": 0.0,
   "Pérdida ops/día": 100.0
  },
  {
   "Línea": "Línea 4",
   "Máquina": "Collaretera de ruedo 2",
   "Estatus": "Inactiva",
   "Teórica ops/día": 100,
   "Real ops/día": 0.0,
   "Pérdida ops/día": 100.0
  },
  {
   "Línea": "Línea 2",
   "Máquina": "Overlock Unión/Montaje",
   "Estatus": "Parcial 80%",
   "Teórica ops/día": 190,
   "Real ops/día": 150.0,
   "Pérdida ops/día": 40.0
  }
 ],
 "exclusiva": [
  {
   "Modelo": "MAR",
   "Ops/pieza": 7,
   "Actual /línea/día": 95,
   "Diseño /línea/día": 105,
   "Módulo /línea/día": 130,
   "Actual 4 líneas/mes": 7600,
   "Diseño 4 líneas/mes": 8400,
   "Módulo 4 líneas/mes": 10400
  },
  {
   "Modelo": "RIO",
   "Ops/pieza": 6,
   "Actual /línea/día": 73,
   "Diseño /línea/día": 82,
   "Módulo /línea/día": 101,
   "Actual 4 líneas/mes": 5840,
   "Diseño 4 líneas/mes": 6560,
   "Módulo 4 líneas/mes": 8080
  },
  {
   "Modelo": "Basic Line",
   "Ops/pieza": 12,
   "Actual /línea/día": 55,
   "Diseño /línea/día": 61,
   "Módulo /línea/día": 76,
   "Actual 4 líneas/mes": 4400,
   "Diseño 4 líneas/mes": 4880,
   "Módulo 4 líneas/mes": 6080
  }
 ],
 "compra": [
  {
   "Fase": "2.1a",
   "Ítem": "Módulo continuo JACK para Línea 3",
   "Detalle": "Overlock unión, Overlock cierre, Collaretera recubrir, Collaretera de ruedo (corte y succión), Recta dedicada",
   "Máquinas nuevas": 5,
   "Por qué": "L3 concentra 52% de la pérdida: ruedo 1 al 50% y ruedo 2 inactivo."
  },
  {
   "Fase": "2.1a",
   "Ítem": "Overlock Unión/Montaje JACK para Línea 2",
   "Detalle": "Sustituye la máquina al 80%",
   "Máquinas nuevas": 1,
   "Por qué": "Recupera 40 ops/día y la calidad de la unión."
  },
  {
   "Fase": "2.1a",
   "Ítem": "Reactivar 2 Overlock de cuellos",
   "Detalle": "Sin compra · 2 operarios",
   "Máquinas nuevas": 0,
   "Por qué": "Libera la operación 'montar cuello' que hoy carga los overlock de línea."
  },
  {
   "Fase": "2.1a",
   "Ítem": "Kit de repuestos JACK",
   "Detalle": "Agujas, cuchillas, diferenciales, loopers · min-max",
   "Máquinas nuevas": 0,
   "Por qué": "3 equipos llevan meses esperando piezas (≈40 pzas/día)."
  },
  {
   "Fase": "2.1b",
   "Ítem": "Módulo continuo JACK para Línea 4",
   "Detalle": "Igual que L3",
   "Máquinas nuevas": 5,
   "Por qué": "L4 tiene el ruedo 2 inactivo: mismo desbalanceo que L3."
  },
  {
   "Fase": "2.1b",
   "Ítem": "Collaretera de ruedo JACK para Línea 1 y Línea 2",
   "Detalle": "Segundo ruedo, con corte y succión",
   "Máquinas nuevas": 2,
   "Por qué": "L1 y L2 nacen con un solo ruedo (la mitad del overlock). Replica el patrón de diseño de L3/L4."
  },
  {
   "Fase": "2.2a",
   "Ítem": "Módulos continuos JACK en L1 y L2",
   "Detalle": "10 máquinas (5 por línea)",
   "Máquinas nuevas": 10,
   "Por qué": "Cierra las 4 líneas al mismo estándar de calidad y flujo."
  },
  {
   "Fase": "2.2b",
   "Ítem": "Línea 5 de punto (nueva)",
   "Detalle": "Módulo continuo de 5 máquinas",
   "Máquinas nuevas": 5,
   "Por qué": "Capacidad incremental para la tienda confirmada."
  },
  {
   "Fase": "2.2b",
   "Ítem": "Línea de shorts / pants completada",
   "Detalle": "Ojaladora, presilladora, engomadora, doble aguja, 2 rectas, 2 overlock",
   "Máquinas nuevas": 8,
   "Por qué": "Hoy Short Sport / R1 / Explore Pants no tienen techo medido."
  },
  {
   "Fase": "2.2c",
   "Ítem": "Línea 6 de punto (nueva)",
   "Detalle": "Módulo continuo de 5 máquinas",
   "Máquinas nuevas": 5,
   "Por qué": "Dimensiona el taller para 3 tiendas nuevas por año en pico."
  },
  {
   "Fase": "Paralelo",
   "Ítem": "Liquidación de parque inactivo",
   "Detalle": "2 collareteras chatarra (9% del parque) + las sustituidas",
   "Máquinas nuevas": 0,
   "Por qué": "Caja que abate el CAPEX y libera metro cuadrado."
  }
 ],
 "sensibilidad": [
  {
   "Contenido de retrabajo": 0.2,
   "S0": 7172,
   "S0T": 7874,
   "S21a": 8321,
   "S21b": 8772,
   "S22a": 9685,
   "S22b": 11932,
   "S22c": 14140
  },
  {
   "Contenido de retrabajo": 0.35,
   "S0": 7008,
   "S0T": 7693,
   "S21a": 8153,
   "S21b": 8619,
   "S22a": 9571,
   "S22b": 11827,
   "S22c": 14016
  },
  {
   "Contenido de retrabajo": 0.5,
   "S0": 6851,
   "S0T": 7521,
   "S21a": 7992,
   "S21b": 8472,
   "S22a": 9460,
   "S22b": 11723,
   "S22c": 13893
  },
  {
   "Contenido de retrabajo": 1.0,
   "S0": 6375,
   "S0T": 6998,
   "S21a": 7498,
   "S21b": 8015,
   "S22a": 9109,
   "S22b": 11392,
   "S22c": 13500
  }
 ],
 "faltantes": [
  {
   "Prioridad": "P0",
   "Dato": "Cotización JACK por tipo + flete, instalación y capacitación",
   "Para qué": "Convierte piezas ganadas en payback",
   "Dueño": "Proveedor + Brayan Machado",
   "Estado hoy": "No está"
  },
  {
   "Prioridad": "P0",
   "Dato": "REPORTE DE MAQUINAS (15-jul a 31-ago 2026): horas de parada por máquina",
   "Para qué": "Sustituye la merma del 10% por disponibilidad medida (MTBF/MTTR)",
   "Dueño": "Mantenimiento",
   "Estado hoy": "Archivo no incorporado al modelo"
  },
  {
   "Prioridad": "P0",
   "Dato": "Minutos de retrabajo por prenda y % de defectos atribuibles a máquina",
   "Para qué": "Fija el factor neto; hoy es supuesto (35% de contenido)",
   "Dueño": "Calidad / Taller",
   "Estado hoy": "No medido"
  },
  {
   "Prioridad": "P0",
   "Dato": "Margen bruto por pieza",
   "Para qué": "Dolariza el déficit de 2.420 piezas del pico",
   "Dueño": "Finanzas",
   "Estado hoy": "No está"
  },
  {
   "Prioridad": "P1",
   "Dato": "Maquinas Activas.xlsx a nivel de serie: marca, modelo, año, valor en libros",
   "Para qué": "Cierra las dos estaciones cuya capacidad individual no está publicada (b+c=394 ops/día)",
   "Dueño": "Mantenimiento / Admin",
   "Estado hoy": "Pendiente de cargar"
  },
  {
   "Prioridad": "P1",
   "Dato": "Tasa de producción medida de la Línea 5 de shorts",
   "Para qué": "Hoy se usa la muestra de campo de 45 pzas/día sin estatus por máquina",
   "Dueño": "Taller",
   "Estado hoy": "Muestra única"
  },
  {
   "Prioridad": "P1",
   "Dato": "Plan comercial: qué tienda, cuándo y de qué tamaño",
   "Para qué": "Pasa los escenarios de red a presupuesto",
   "Dueño": "Comercial",
   "Estado hoy": "1 confirmada, objetivo 3/año"
  },
  {
   "Prioridad": "P1",
   "Dato": "Ops por pieza de Explore Pants, Jacket 2.0 y Active Duo",
   "Para qué": "El pico de 8.576 piezas puede estar subestimado en operaciones",
   "Dueño": "Ingeniería",
   "Estado hoy": "Celdas vacías"
  },
  {
   "Prioridad": "P2",
   "Dato": "Headcount por línea vs estándar de 5 máquinas por módulo",
   "Para qué": "Sin operarios, la máquina nueva repite el caso de los Overlock de cuellos",
   "Dueño": "RR.HH.",
   "Estado hoy": "2 máquinas paradas por gente"
  },
  {
   "Prioridad": "P2",
   "Dato": "Volumen y SLA del taller satélite",
   "Para qué": "Evita duplicar capacidad ya tercerizada",
   "Dueño": "Operaciones",
   "Estado hoy": "Mencionado sin data"
  }
 ]
};
