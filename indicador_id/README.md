# Indicador de Operatividad I+D (quincenal)

Archivo generado: `Indicador_Operatividad_ID_Quincenal.xlsx`

## Qué mide

**IOI (Índice de Operatividad I+D)** por responsable, cada quincena, a partir de:

- Fecha de inicio
- Fecha de finalización
- Nivel de prioridad
- Responsable / estado

## Cómo renovar datos

1. Pegar operaciones actualizadas en la hoja `1_Datos` (sin borrar encabezados).
2. Ajustar Año / Mes / Quincena en `2_Parametros`.
3. Revisar `4_KPI_Responsables` y `5_Ranking` (se recalculan con fórmulas).

## Regenerar el libro

```bash
python3 indicador_id/generar_indicador_operatividad.py
```

Si más adelante se dispone del archivo fuente `KPIS I+D.xlsx`, pegar sus columnas mapeadas a `1_Datos` o adaptar el script de importación.