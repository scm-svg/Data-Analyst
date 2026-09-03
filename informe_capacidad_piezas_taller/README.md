# Capacidad instalada del taller en piezas y selección de maquinaria — Cuadro

Informe de decisión para Gerencia. Responde tres preguntas, todas en **piezas por mes**:

1. Capacidad actual del taller, teórica y real.
2. Capacidad con maquinaria nueva, en dos configuraciones: una inversión corta y una
   reestructuración ambiciosa.
3. Déficit contra la demanda mensual en período regular, en pico de diciembre y con apertura
   de tiendas nuevas.

## Qué abrir

| Archivo | Para qué |
|---|---|
| `Informe_Capacidad_Piezas_Cuadro.pdf` | **Listo para enviar a Gerencia.** 25 páginas. |
| `INFORME_CAPACIDAD_PIEZAS.html` | El mismo documento en web, con botón de **Imprimir / Guardar PDF** para regenerarlo. |
| `dashboard_capacidad_piezas.html` | Dashboard interactivo para la sesión. Selector de escenario y de período de demanda. Modo claro y oscuro. Funciona sin internet. |
| `anexos/Modelo_Capacidad_Piezas_Cuadro.xlsx` | Memoria de cálculo en 13 hojas. |
| `modelo_capacidad.py` | El modelo ejecutable. Cambiar un supuesto y volver a correrlo regenera Excel, figuras y dashboard. |

## Los números en una línea

| Concepto | Piezas/mes |
|---|---|
| Capacidad **real** hoy, de primera calidad | **7.008** |
| Capacidad **teórica** con las 22 máquinas al 100% | 7.693 |
| Demanda regular | 4.145 · cubierta 1,69× |
| Demanda pico diciembre | 8.576 · **cubierta 0,82×** |
| Propuesta **2.1b** · 12 máquinas | 8.619 · cubre el pico de hoy por 43 piezas |
| Propuesta **2.2b** · 33 máquinas | 11.827 · cubre el pico con una tienda nueva |

El hallazgo central: **la demanda regular está cubierta con holgura y el pico de diciembre no**,
y no se cubre ni siquiera reparando todo el parque. Es un problema de configuración de líneas,
no de estado de máquina.

## Método

La capacidad se calcula por **cuello de botella de línea**, a partir de la tasa de piezas por
línea y día medida en campo. No se calcula dividiendo operaciones entre operaciones por pieza:
ese método sobreestima el techo en **10,1%** porque supone que la capacidad libre del overlock
puede hacer el trabajo del ruedo.

Sobre la capacidad bruta se aplica el **factor neto de primera calidad**, que descuenta la
capacidad que consume el retrabajo:

```
factor neto = 1 / (1 + tasa_reproceso × contenido_retrabajo)
            = 1 / (1 + 0,1614 × 0,35) = 0,9465
```

El modelo reproduce las cifras del tablero en operaciones por un camino independiente
(utilización 90,0% en piezas contra 90,1% en operaciones; 8.940 piezas/mes para las cuatro
líneas en módulo continuo, la misma cifra del dashboard anterior).

## Regenerar

```bash
pip install pandas openpyxl matplotlib numpy
python3 modelo_capacidad.py
```

Todos los parámetros están en la cabecera de `modelo_capacidad.py`, cada uno con su fuente.
Los supuestos declarados como tales son el contenido de retrabajo (35%), el reproceso residual
con parque nuevo (6,0%) y los factores de red nueva. El apartado 10 del informe trae la
sensibilidad y la lista priorizada de datos que faltan para cerrar el capex.

## Fuentes

Máquinas activas · Reporte de máquinas (15-jul a 31-ago 2026) · Muestra de campo ·
Operaciones por línea · Operaciones por producto · Análisis de tasa de retrocesos QA ·
Informe de capacidad instalada y justificación de inversión en maquinaria de costura ·
Justificación técnica de calidad — cambio de maquinaria · dashboard de capacidad de maquinaria ·
correos de Gerencia de Operaciones y de Coordinación de Producción.
