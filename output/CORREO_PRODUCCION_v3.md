# Correo v3 — Plan de corte Mar / Rio (Nov–Dic)

**Asunto:** Mar/Rio Nov–Dic — plan 50% · qué ver en cada archivo · curvas a cortar

---

Estimado equipo de Producción,

Les envío **3 archivos Excel** para el plan de corte **noviembre–diciembre** en tela Jabón. Abajo les indico **exactamente qué van a ver en cada uno** y cuál usar para cortar.

**Regla del plan:** cada línea apunta al **50% de la meta máxima** de proyección, en este orden de prioridad:

| P | Línea | % objetivo | Und nuevas | Kg tela |
|:-:|-------|:----------:|-----------:|--------:|
| 1 | RIO KIDS | 50% | 1.344 | 430 |
| 2 | MAR KIDS | 50% | 988 *(+ 1.300 ya cortadas)* | 257 |
| 3 | MAR CAB | 50% | 1.209 | 605 |
| 4 | MAR DAMA | 50% | 874 | 350 |
| 5 | RIO CAB | 50% | 872 | 576 |
| 6 | RIO DAMA | 50% | 839 | 436 |

**Total corte nuevo: 6.126 und · ~2.653 kg.**

Donde la tela no alcanza, el % real baja del 50% (Rio KIDS consume primero por color). En **PLAN COLORES** la columna **Estado** indica `OK`, `PARCIAL` o `SIN TELA`.

**Curva óptima:** el total por color sale del plan; el reparto por talla debe seguir la **curva MÁXIMA (óptima)** del Excel de proyección. **Producción debe adoptar las cantidades totales a esa curva** — la hoja **CURVAS A CORTAR** ya lo calcula; si ajustan redondeos, mantengan las proporciones.

---

## ARCHIVO 1 — `MAR_PROYECCION_CANTIDADES_SUGERIDAS.xlsx`

*(Alerta de planificación Mar — referencia al 100%, no es orden de corte)*

Al abrirlo verán **6 pestañas**:

| Pestaña | Qué verán |
|---------|-----------|
| **Resumen** | Vista general de la proyección Mar |
| **Cantidades por Colores** | Tablas por **Caballero / Dama / Kids**: color → **cantidad máxima sugerida** (columna total). Es el **100% de referencia** que usamos como meta |
| **Producción por Talla** | Curva de tallas agregada por línea (cuánto iría en cada talla al 100%) |
| **Producción Color × Talla** | **Curva óptima detallada**: cada color con desglose **talla a talla** (mínimo y máximo). Aquí está la proporción que deben respetar al cortar |
| **Compra de Tela** | Consumo **kg/und** por línea (Kids Mar ≈ 0,26 · Cab ≈ 0,50 · Dama ≈ 0,40) |
| **Distribución por Tienda** | Reparto comercial por tienda — **no usar para corte** |

**Para Producción:** consultar **Producción Color × Talla** para entender la **curva óptima** Mar. No cortar al 100% de estas cantidades.

---

## ARCHIVO 2 — `RIO_PROYECCION_CANTIDADES_SUGERIDAS.xlsx`

*(Misma estructura que Mar, para modelo Rio)*

Mismas **6 pestañas** con la misma lógica:

| Pestaña | Qué verán |
|---------|-----------|
| **Cantidades por Colores** | Metas máximas Rio por color (Kids meta total ≈ 2.952 und) |
| **Producción Color × Talla** | Curva óptima Rio por color y talla |
| **Compra de Tela** | Consumo Rio (Kids ≈ 0,32 · Cab ≈ 0,66 · Dama ≈ 0,52 kg/und) |
| *(Resto)* | Resumen, Producción por Talla, Distribución por Tienda — igual que Mar |

**Para Producción:** curva óptima Rio en **Producción Color × Talla**. Tampoco es orden de corte al 100%.

---

## ARCHIVO 3 — `PLAN_PRIORIDADES_MAR_RIO_KIDS.xlsx`

*(Plan operativo — **este es el documento de trabajo**)*

Al abrirlo verán **9 pestañas**. Flujo recomendado: **PARAMETROS → PLAN COLORES → CURVAS A CORTAR**.

### Pestaña **INSTRUCCIONES**
Guía rápida de una página con el mapa del archivo.

### Pestaña **PARAMETROS**
Tres bloques:

1. **Tabla superior (filas amarillas editables)**  
   Modelo · Género · **% Objetivo (50%)** · Consumo kg/und · Prioridad P1–P6  
   → Aquí está el **50% por línea** y el orden de prioridad.

2. **Inventario tela Jabón (kg)**  
   Lista de 14 colores con stock actual (foto reciente). Ej.: Azul Marino 689,9 · Negro 657,2 · Rojo 0,2.

3. **Und ya cortadas**  
   Solo Mar KIDS tiene valores (descuentan meta, **no restan kg**). Resto en cero.

### Pestaña **METAS**
Listado plano: Modelo · Género · Color · **Meta máx Excel** (copiado de los archivos de proyección).

### Pestaña **MAR KIDS CORTADO**
Tabla verde **Color × tallas 8 / 10 / 12 / 14 → Total**  
→ Lo que **ya cortaron** (1.300 und). **No volver a cortar.**  
Totales por talla: 260 · 260 · 260 · 520. Incluye Vinotinto y Gris Claro (fuera de meta Excel).

### Pestaña **MIX TALLAS**
Por modelo/género/color: cada talla con **Und máx Excel** y total del color.  
→ Referencia de la **curva óptima** en formato tabular (equivale a la curva MÁX del Excel proyección).

### Pestaña **PLAN COLORES** *(corazón del plan)*
Una fila por color y línea. Columnas clave:

| Columna | Qué significa |
|---------|---------------|
| **P** | Prioridad 1–6 |
| **Meta máx** | Techo del Excel proyección (100%) |
| **Ya cortado** | Und Mar KIDS ya en producción |
| **Pendiente** | Meta − ya cortado |
| **% Obj** | 50% (desde PARAMETROS) |
| **Und objetivo** | Pendiente × 50% |
| **Inventario kg** | Tela disponible del color |
| **Saldo kg** | Lo que queda después de líneas de mayor prioridad |
| **Und FINAL** | **Cantidad a cortar por color** (objetivo limitado por tela) |
| **Estado** | OK / PARCIAL / SIN TELA |

Filas KIDS van con fondo verde claro.

### Pestaña **CURVAS REFERENCIA**
Por bloque (RIO KIDS, MAR KIDS, MAR CAB…): cada color con dos filas — **MÍNIMO** (azul) y **MÁXIMO** (negrita) por talla.  
→ Rango de referencia. El objetivo operativo es la fila **MÁXIMO = curva óptima**.

### Pestaña **CURVAS A CORTAR** ★ **USAR PARA CORTAR**
Por bloque modelo/género. Cada color muestra:

- Columna **Und FINAL** (enlazada a PLAN COLORES)  
- Columnas de **tallas** con cantidades calculadas = Und FINAL × proporción curva óptima  
- Fila **TOTAL — A CORTAR** al final de cada bloque  

**Esta es la hoja que deben llevar al taller.**

### Pestaña **RESUMEN**
Totales por línea (Und FINAL y Kg) + gran total 6.126 und / ~2.653 kg.

---

## Instrucciones finales para Producción

1. **No cortar** desde los Excel de proyección Mar/Rio al 100%.
2. **Sí cortar** desde **CURVAS A CORTAR** del plan operativo.
3. **Adaptar** el total de cada color a la **curva óptima (MÁX)** — no cambiar el mix de tallas arbitrariamente.
4. **Mar KIDS:** 1.300 und ya en producción (ver **MAR KIDS CORTADO**); solo programar las **988 und nuevas** del plan.
5. **Tela compartida por color:** si un color aparece en `SIN TELA` o `PARCIAL`, es porque P1/P2 ya lo consumieron — respetar el orden P1→P6.

Quedo atento/a si necesitan aclarar alguna pestaña o color.

Saludos,

[Tu nombre]
