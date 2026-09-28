# Propuesta Black Friday · Categoría C (Manufactura + Equipamiento)

Entregables para presentación a directiva y operación de tiendas.

## Archivos

| Archivo | Uso |
|---------|-----|
| `black_friday_propuesta_categoria_c.html` | Dashboard interactivo (resumen, 2 opciones de descuento, abastecimiento) |
| `BLACK_FRIDAY_PROPUESTA_CATEGORIA_C.xlsx` | Misma información en hojas para análisis y distribución |
| `bf_proposal_data.json` | Datos embebidos / integraciones |
| `scripts/build_black_friday_proposal.py` | Regenera todo a partir de fuentes |

## Fuentes de datos

1. **Inventario (Excel)** — stock real por SKU/tienda; **solo se listan SKUs con stock > 0**.
2. **Ventas (Excel)** — rotación **Oct 2025 → Jul 2026** (sin ago–sep 2026).
3. **Guía ABC** (`abc ver.html`) — margen C y categoría Manufactura/Equipamiento.

## Alcance (reglas)

- Margen **C** (guía ABC) + rotación **C** (ventas Excel) = baja salida con inventario disponible.
- **Excluidos:** CUADRO BAND, SHORT PLAYA (otra estrategia), CLASICA GC SUBLIMADO KIDS.
- Matriz ABC es **referencia**; stock y ventas mandan en la propuesta.

## Dos opciones de descuento

### Opción A · Impulso de rotación

Descuento fijo según matriz **margen × rotación**:

- **CC** → 40%
- **CB** → 30%
- **CA** → 20%

Enfoque agresivo para liquidar lastre (matriz CC).

### Opción B · Equilibrio margen–stock

Descuento según **meses de cobertura** (stock ÷ venta mensual promedio), con bonus en CC y **tope** para no bajar de **8%** de margen sobre precio lista.

## Garantía de abastecimiento (post-aprobación)

Por tienda retail (Cerro Verde, Chacao, Grandplaz, Grieta, Sambil, Tolon, Vela):

- **Objetivo** = venta mensual promedio × **4** (hipótesis pico BF) × **1,15** (reserva).
- **Brecha** = max(0, objetivo − stock en tienda).

## Ver el dashboard

Descargá **`black_friday_propuesta_categoria_c.html`**: es **autocontenido** (toda la data va embebida). Abrilo con doble clic en Chrome/Edge/Firefox; no necesitás archivos extra.

Opcional: `bf_proposal_data.js` + `dashboard_app.js` en la misma carpeta si preferís datos separados.

## Regenerar

```bash
python3 scripts/build_black_friday_proposal.py
```

Colocar en `uploads/` los Excel actualizados, o editar rutas al inicio del script.
