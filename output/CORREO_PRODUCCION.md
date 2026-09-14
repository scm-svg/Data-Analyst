# Correo — Plan de corte Mar / Rio (Nov–Dic)

**Asunto:** Plan de corte Mar/Rio Nov–Dic — cantidades sugeridas con tela Jabón disponible (prioridad KIDS)

---

Estimado equipo de Producción,

Les comparto el **plan de corte sugerido para noviembre–diciembre**, armado con el inventario actual de tela Jabón y las metas de proyección de venta. El objetivo es cubrir aproximadamente el **50% de la meta máxima** por línea, respetando un orden de **prioridades** y la **flexibilidad de tela por color** entre modelos Mar y Rio.

---

## 1. Contexto del plan

| Concepto | Detalle |
|----------|---------|
| **Período** | Noviembre – Diciembre 2026 |
| **Meta operativa** | ~50% de las cantidades máximas del Excel de proyección |
| **Tela** | Jabón (inventario foto actual — ver adjunto / hoja PARAMETROS) |
| **Lote en curso** | **Mar KIDS ya cortado: 1.300 und** (producción WIP; no resta kg del inventario) |
| **Corte adicional sugerido** | **6.126 und** · **~2.653 kg** de tela |

### Orden de prioridad (P1 → P6)

| P | Línea | Und a cortar | Kg tela |
|---|-------|-------------:|--------:|
| **P1** | **RIO KIDS** | 1.344 | 430 |
| **P2** | **MAR KIDS** *(adicional al lote ya cortado)* | 988 | 257 |
| P3 | MAR CABALLERO | 1.209 | 605 |
| P4 | MAR DAMA | 874 | 350 |
| P5 | RIO CABALLERO | 872 | 576 |
| P6 | RIO DAMA | 839 | 436 |

**Importante:** La tela se asigna **por color**, no por modelo. Si un color tiene stock limitado, primero se satisface la línea de mayor prioridad (Rio KIDS antes que Mar KIDS, KIDS antes que adultos). Por eso algunos colores pueden quedar en 0 und en líneas de menor prioridad (ej.: **Rojo** — inventario ~0,18 kg).

---

## 2. Archivos adjuntos — qué es cada uno

### A) Excel originales de proyección (referencia / metas)

Estos son los archivos que recibimos al inicio como **alerta de planificación**:

1. **`MAR_PROYECCION_CANTIDADES_SUGERIDAS.xlsx`**
   - Proyección de venta modelo **Mar** (Caballero, Dama, Kids).
   - Define las **metas máximas por color** y las **curvas de talla** (mín/máx) por línea.
   - **No es orden de corte directo** — es el techo de referencia.

2. **`RIO_PROYECCION_CANTIDADES_SUGERIDAS.xlsx`**
   - Igual estructura para modelo **Rio**.
   - Mismas hojas útiles: *Cantidades por Colores*, *Compra de Tela* (consumo kg/und), curvas por talla.

> Estos dos archivos responden: *“¿Cuánto podríamos vender si tuviéramos stock?”*  
> El plan operativo los usa como **meta máxima**, no como cantidad a cortar al 100%.

---

### B) Excel de plan operativo (este es el que deben usar para cortar)

**`PLAN_PRIORIDADES_MAR_RIO_KIDS.xlsx`**

Archivo editable generado con inventario actual, lote Mar KIDS ya cortado y prioridades. Resumen de hojas:

| Hoja | Uso |
|------|-----|
| **INSTRUCCIONES** | Guía rápida del archivo |
| **PARAMETROS** | % objetivo (50%), consumo kg/und, **inventario tela actual**, und ya cortadas |
| **METAS** | Metas máximas por línea (copiadas de proyección) |
| **MAR KIDS CORTADO** | Detalle real del lote **ya cortado** (1.300 und por color/talla 8-10-12-14) |
| **MIX TALLAS** | Curva de tallas por color (referencia del Excel proyección) |
| **PLAN COLORES** | **Und FINAL por color** — resultado del plan (meta × 50% − ya cortado, limitado por tela) |
| **CURVAS REFERENCIA** | Curvas mín/máx del Excel original (todas las líneas) |
| **CURVAS A CORTAR** | **→ HOJA OPERATIVA:** cantidades por color **y talla** a cortar ahora |
| **RESUMEN** | Totales por prioridad y línea |

**Para el taller:** usar la hoja **`CURVAS A CORTAR`**. Ahí está el desglose por modelo/género, color y tallas (8, 10, 12, 14 en KIDS; según curva en adultos), calculado como *Und FINAL × mix de talla*.

---

## 3. Mar KIDS — lote ya en producción

El corte de **Mar KIDS** que ya realizaron quedó registrado en la hoja **MAR KIDS CORTADO**:

- **Total: 1.300 und** (260 talla 8 · 260 talla 10 · 260 talla 12 · 520 talla 14)
- Colores: Negro, Azul Marino, Rojo, Aguamarina, Rosado Pastel, Azul Lavanda, Lila, Azul Rey, Verde Militar, Vinotinto, Gris Claro
- Este lote **solo descuenta unidades de la meta Mar KIDS**; **no resta kilos** del inventario de tela (la tela ya salió del stock cuando se cortó).
- Vinotinto y Gris Claro se cortaron pero **no están en la meta Excel Mar KIDS** — son unidades extra en producción, no afectan el descuento de meta.

El plan sugiere **988 und adicionales** de Mar KIDS para completar ~50% de meta con la tela que queda.

---

## 4. Inventario tela Jabón (foto actual)

Actualizado en hoja **PARAMETROS** del plan:

| Color | kg |
|-------|---:|
| Azul Marino | 689,9 |
| Negro | 657,2 |
| Aguamarina | 348,3 |
| Azul Rey | 271,5 |
| Azul Lavanda | 221,0 |
| Lila | 228,4 |
| Vinotinto | 215,4 |
| Blanco | 202,0 |
| Morado | 94,2 |
| Gris Claro | 87,7 |
| Amarillo Neón | 57,9 |
| Verde Militar | 46,0 |
| Rosado Pastel | 31,4 |
| Rojo | 0,2 |

Colores con stock muy bajo (Rojo, Rosado Pastel, Verde Militar) limitan fuertemente lo que el plan puede asignar en esas líneas.

---

## 5. Flexibilidad operativa

- **Misma tela, varios modelos:** un kg de Azul Marino puede servir Rio KIDS, Mar KIDS, Cab o Dama; el plan ya optimizó el reparto según prioridad.
- **Si cambia el inventario** o entra tela nueva: editar columna de kg en **PARAMETROS** — **PLAN COLORES** y **CURVAS A CORTAR** se recalculan (fórmulas).
- **Si quieren otro %** (ej. 40% o 60%): cambiar columna “% Objetivo” en **PARAMETROS** por línea.

---

## 6. Resumen ejecutivo para Producción

1. **Continuar** con el lote Mar KIDS ya cortado (1.300 und) — no re-cortar esas cantidades.
2. **Priorizar cortes nuevos** en este orden: **Rio KIDS → Mar KIDS → adultos Mar → adultos Rio**.
3. **Cantidades exactas por talla:** hoja **CURVAS A CORTAR** del archivo `PLAN_PRIORIDADES_MAR_RIO_KIDS.xlsx`.
4. **Total nuevo a programar:** ~**6.126 und** / ~**2.653 kg** tela Jabón.
5. Los Excel de proyección Mar/Rio son **referencia de metas**; el plan operativo es el **documento de trabajo**.

Quedo atento/a a dudas sobre colores, prioridades o si necesitan reordenar alguna línea según capacidad del taller.

Saludos cordiales,

[Tu nombre]  
Planificación / Comercial

---

*Generado: septiembre 2026 · Script: `planificacion_mar_rio.py`*
