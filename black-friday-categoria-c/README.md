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

1. **Clasificación ABC y ventas/márgenes** — dashboard `abc ver.html` (Oct 2025 → Jul 2026, margen de contribución, umbrales 80/15/5).
2. **Inventario por tienda** — `INVENTARIO TOTAL CUADRO PARA ABC - PROPUESTA.xlsx`.

## Alcance

- Clase **C por margen** (SKUs con margen positivo en el período).
- Segmentos **Manufactura** y **Equipamiento** únicamente.
- **1.640 SKUs** en alcance; **896** con stock (**41.013** unidades en red).

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

## Regenerar

```bash
python3 scripts/build_black_friday_proposal.py
```

Colocar en `uploads/` los mismos nombres de archivo ABC e inventario, o editar rutas al inicio del script.
