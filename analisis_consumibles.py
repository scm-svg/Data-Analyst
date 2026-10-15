#!/usr/bin/env python3
"""
Análisis de solicitudes de consumibles - TALLER y TIENDAS.
Genera Excel con recomendaciones de pedido (semanal, quincenal, mensual).
"""

import re
import warnings
from datetime import datetime
from math import ceil

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Rutas ──────────────────────────────────────────────────────────────────
TALLER_FILE = "/home/ubuntu/.cursor/projects/workspace/uploads/Solicitudes__TALLER__consumibles_feeb.xlsx"
TIENDAS_FILE = "/home/ubuntu/.cursor/projects/workspace/uploads/Solicitudes__TIENDAS__consumibles_8818.xlsx"
OUTPUT_FILE = "/workspace/Analisis_Pedido_Consumibles.xlsx"

FECHA_INICIO = pd.Timestamp("2025-09-01")
FECHA_FIN = pd.Timestamp("2026-08-31")
SEMANAS_POR_MES = 52 / 12  # ≈ 4.33

STORE_SHEETS = [
    "GRIETA",
    "SAMBIL VALENCIA",
    "GRAND PLAZ",
    "CERRO VERDE",
    "SAMBIL CHACAO",
    "TOLON",
    "MARGARITA",
]


# ── Normalización de productos ─────────────────────────────────────────────
PRODUCT_ALIASES = {
    "CAFÉ AMANECER": "CAFÉ",
    "CAFE": "CAFÉ",
    "CAFÉ ": "CAFÉ",
    "CINTA DE EMBALAR": "CINTA DE EMBALAJE",
    "CINTA PLASTICA": "CINTA DE EMBALAJE",
    "BOLSAS GRANDES": "BOLSA DE ENVIO GRANDE",
    "BOLSAS MEDIANAS": "BOLSA DE ENVIO MEDIANA",
    "BOLSAS PEQUEÑAS": "BOLSA DE ENVIO PEQUEÑA",
    "BOLSAS DE ENVIO": "BOLSA DE ENVIO",
    "PAPEL SANITARIO INDUSTRIAL ": "PAPEL SANITARIO INDUSTRIAL",
    "PAPEL SANITARIO INDUSTRIAL  ": "PAPEL SANITARIO INDUSTRIAL",
}


def normalize_product(name):
    if pd.isna(name):
        return None
    s = str(name).upper().strip()
    s = re.sub(r"\s+", " ", s)
    return PRODUCT_ALIASES.get(s, s)


def normalize_estado(estado):
    if pd.isna(estado):
        return "SIN ESTADO"
    e = str(estado).upper().strip()
    mapping = {"ENTRGADO": "ENTREGADO"}
    return mapping.get(e, e)


def safe_ceil(value):
    if pd.isna(value) or value <= 0:
        return 0
    return int(ceil(value))


# ── Carga de datos ─────────────────────────────────────────────────────────
def load_taller():
    frames = []

    df = pd.read_excel(TALLER_FILE, sheet_name="SOLICITUDES TALLER")
    df = df[
        ["FECHA", "Nombre", "Articulo", "Cantidad", "Estado", "SUCURSAL", "Notas y Comentarios"]
    ].copy()
    df.columns = [
        "fecha",
        "nombre",
        "articulo",
        "cantidad",
        "estado",
        "sucursal",
        "notas",
    ]
    df["fuente_hoja"] = "SOLICITUDES TALLER"
    frames.append(df)

    creco = pd.read_excel(TALLER_FILE, sheet_name="CRECO SOLICITUDES", header=1)
    creco = creco.rename(
        columns={
            "FECHA": "fecha",
            "NOMBRE": "nombre",
            "ARTICULO": "articulo",
            "CANTIDAD": "cantidad",
            "ESTADO": "estado",
            "SUCURSAL": "sucursal",
            "Notas y Comentarios": "notas",
            "CARACTER ADICIONAL": "caracter_adicional",
        }
    )
    creco["fuente_hoja"] = "CRECO SOLICITUDES"
    frames.append(creco)

    out = pd.concat(frames, ignore_index=True)
    out["origen"] = "TALLER"
    out["tienda"] = out["sucursal"]
    return out


def load_tiendas():
    frames = []
    for sheet in STORE_SHEETS:
        df = pd.read_excel(TIENDAS_FILE, sheet_name=sheet, header=2)
        df = df.rename(
            columns={
                "FECHA": "fecha",
                "NOMBRE": "nombre",
                "ARTICULO": "articulo",
                "CANTIDAD": "cantidad",
                "ESTADO": "estado",
                "SUCURSAL": "sucursal",
                "Notas y Comentarios": "notas",
                "CARACTER ADICIONAL": "caracter_adicional",
            }
        )
        df["fuente_hoja"] = sheet
        df["origen"] = "TIENDAS"
        df["tienda"] = sheet
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_inventario():
    inv_taller = pd.read_excel(TALLER_FILE, sheet_name="INVENTARIO DE CONSUMIBLES")
    inv_taller = inv_taller.rename(
        columns={
            "CÓDIGO": "codigo",
            "PRODUCTO": "producto",
            "CATEGORÍA / FAMILIA": "categoria",
            "UND": "unidad",
            "EXISTENCIA ACTUAL": "existencia",
            "ESTADO": "estado_inv",
        }
    )
    inv_taller["origen_inv"] = "TALLER"

    inv_tiendas = pd.read_excel(TIENDAS_FILE, sheet_name="INVENTARIO DE CONSUMIBLES")
    inv_tiendas = inv_tiendas.rename(
        columns={
            "ID": "codigo",
            "PRODUNTOS": "producto",
            "CATEGORIA": "categoria",
            "STOCK INICIAL": "stock_inicial",
            "CONSUMIDO": "consumido",
            "STOCK ACTUAL": "existencia",
        }
    )
    inv_tiendas["origen_inv"] = "TIENDAS"

    inv = pd.concat([inv_taller, inv_tiendas], ignore_index=True)
    inv["producto_norm"] = inv["producto"].apply(normalize_product)
    return inv


def clean_solicitudes(df):
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce")
    df["estado"] = df["estado"].apply(normalize_estado)
    df["articulo_norm"] = df["articulo"].apply(normalize_product)
    df["es_prueba"] = df["notas"].astype(str).str.contains("PRUEBA", case=False, na=False)

    df = df.dropna(subset=["fecha", "articulo_norm", "cantidad"])
    df = df[(df["cantidad"] > 0) & (df["fecha"] >= FECHA_INICIO) & (df["fecha"] <= FECHA_FIN)]

    return df


# ── Métricas por producto ──────────────────────────────────────────────────
def build_product_metrics(df, segment_label):
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["mes"] = df["fecha"].dt.to_period("M").astype(str)

    months_in_period = pd.period_range(FECHA_INICIO, FECHA_FIN, freq="M")
    n_months_period = len(months_in_period)

    monthly = (
        df.groupby(["articulo_norm", "mes"], as_index=False)["cantidad"]
        .sum()
        .rename(columns={"cantidad": "consumo_mes"})
    )

    summary = (
        df.groupby("articulo_norm")
        .agg(
            total_historico=("cantidad", "sum"),
            n_solicitudes=("cantidad", "count"),
            n_meses_con_demanda=("mes", "nunique"),
            primera_solicitud=("fecha", "min"),
            ultima_solicitud=("fecha", "max"),
            qty_min_por_solicitud=("cantidad", "min"),
            qty_max_por_solicitud=("cantidad", "max"),
            qty_prom_por_solicitud=("cantidad", "mean"),
        )
        .reset_index()
    )

    monthly_stats = (
        monthly.groupby("articulo_norm")["consumo_mes"]
        .agg(
            consumo_min_mensual="min",
            consumo_max_mensual="max",
            consumo_prom_mensual_activo="mean",
            desv_std_mensual="std",
        )
        .reset_index()
    )

    summary = summary.merge(monthly_stats, on="articulo_norm", how="left")
    summary["desv_std_mensual"] = summary["desv_std_mensual"].fillna(0)

    # Promedio mensual sobre todo el periodo (meses sin demanda = 0)
    summary["consumo_prom_mensual_periodo"] = summary["total_historico"] / n_months_period

    # Promedio mensual sobre meses con demanda (más representativo si es esporádico)
    summary["consumo_prom_mensual_demanda"] = np.where(
        summary["n_meses_con_demanda"] > 0,
        summary["total_historico"] / summary["n_meses_con_demanda"],
        0,
    )

    # Base de cálculo para pedidos: promedio del periodo (conservador y estable)
    summary["base_mensual_pedido"] = summary["consumo_prom_mensual_periodo"]

    # MIN / MAX de inventario sugerido (unidades)
    summary["min_stock_sugerido"] = summary.apply(
        lambda r: safe_ceil(max(r["consumo_min_mensual"], r["base_mensual_pedido"] * 0.5)),
        axis=1,
    )
    summary["max_stock_sugerido"] = summary.apply(
        lambda r: safe_ceil(max(r["consumo_max_mensual"], r["base_mensual_pedido"] * 1.5)),
        axis=1,
    )

    # Tres opciones de pedido
    summary["pedido_mensual"] = summary["base_mensual_pedido"].apply(safe_ceil)
    summary["pedido_quincenal"] = (summary["base_mensual_pedido"] / 2).apply(safe_ceil)
    summary["pedido_semanal"] = (summary["base_mensual_pedido"] / SEMANAS_POR_MES).apply(safe_ceil)

    # Verificación: pedido mensual ≈ suma de 4 semanas
    summary["verif_4_semanas"] = summary["pedido_semanal"] * 4
    summary["verif_2_quincenas"] = summary["pedido_quincenal"] * 2

    summary["segmento"] = segment_label
    summary = summary.sort_values("total_historico", ascending=False)
    return summary


def pivot_monthly(df, segment_label):
    if df.empty:
        return pd.DataFrame()
    tmp = df.copy()
    tmp["mes"] = tmp["fecha"].dt.to_period("M").astype(str)
    pivot = (
        tmp.pivot_table(
            index="articulo_norm",
            columns="mes",
            values="cantidad",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
    )
    pivot.insert(0, "segmento", segment_label)
    pivot["TOTAL"] = pivot.select_dtypes(include="number").sum(axis=1)
    return pivot.sort_values("TOTAL", ascending=False)


def store_breakdown(df):
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby(["tienda", "articulo_norm"], as_index=False)
        .agg(
            total=("cantidad", "sum"),
            n_solicitudes=("cantidad", "count"),
            ultima_fecha=("fecha", "max"),
        )
        .sort_values(["tienda", "total"], ascending=[True, False])
    )


def frequency_comparison(metrics_df):
    cols = [
        "articulo_norm",
        "total_historico",
        "consumo_prom_mensual_periodo",
        "consumo_min_mensual",
        "consumo_max_mensual",
        "min_stock_sugerido",
        "max_stock_sugerido",
        "pedido_semanal",
        "pedido_quincenal",
        "pedido_mensual",
        "verif_4_semanas",
        "verif_2_quincenas",
    ]
    out = metrics_df[cols].copy()
    out["equiv_mensual_desde_semanal"] = out["pedido_semanal"] * 4
    out["equiv_mensual_desde_quincenal"] = out["pedido_quincenal"] * 2
    out["diferencia_vs_mensual"] = out["pedido_mensual"] - out["consumo_prom_mensual_periodo"].apply(safe_ceil)
    return out


def attach_inventory(metrics, inventario):
    inv = inventario.copy()
    inv["producto_norm"] = inv["producto"].apply(normalize_product)
    inv_agg = (
        inv.groupby("producto_norm", as_index=False)
        .agg(
            codigo=("codigo", "first"),
            categoria=("categoria", "first"),
            unidad=("unidad", "first"),
        )
    )
    return metrics.merge(inv_agg, left_on="articulo_norm", right_on="producto_norm", how="left")


def build_methodology_text(stats):
    return [
        ["ANÁLISIS DE PEDIDO DE CONSUMIBLES — METODOLOGÍA Y GUÍA DE USO"],
        [""],
        ["1. OBJETIVO"],
        ["Establecer cantidades justificadas para pedidos de consumibles basadas en el historial"],
        ["de solicitudes de TALLER (operaciones internas) y TIENDAS (7 sucursales)."],
        [""],
        ["2. FUENTES DE DATOS"],
        [f"  • Archivo TALLER: hojas SOLICITUDES TALLER + CRECO SOLICITUDES"],
        [f"  • Archivo TIENDAS: hojas {', '.join(STORE_SHEETS)}"],
        [f"  • Periodo analizado: {FECHA_INICIO.date()} al {FECHA_FIN.date()}"],
        [f"  • Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
        [""],
        ["3. LIMPIEZA APLICADA"],
        ["  • Normalización de nombres de producto (mayúsculas, espacios, alias comunes)"],
        ["  • Exclusión de fechas fuera del periodo y registros sin cantidad válida"],
        ["  • Unificación de estados (ENTRGADO → ENTREGADO)"],
        ["  • Registros marcados *PRUEBA* se incluyen pero están identificados en DATOS LIMPIOS"],
        [""],
        ["4. ESTADÍSTICAS CALCULADAS (por producto y segmento)"],
        ["  • Total histórico: suma de unidades solicitadas en el periodo"],
        ["  • Consumo prom. mensual (periodo): total ÷ 12 meses — base principal para pedidos"],
        ["  • Consumo prom. mensual (demanda): total ÷ meses con al menos 1 solicitud"],
        ["  • Min/Max mensual: menor y mayor consumo en un mes calendario"],
        ["  • Desv. estándar mensual: variabilidad del consumo"],
        [""],
        ["5. MIN / MAX DE STOCK SUGERIDO (unidades)"],
        ["  • MIN stock = MAX(consumo mínimo mensual histórico, 50% del consumo mensual promedio)"],
        ["  • MAX stock = MAX(consumo máximo mensual histórico, 150% del consumo mensual promedio)"],
        ["  • Nota: no se aplicaron lead times por producto (como se indicó). Ajustar manualmente"],
        ["    si algún producto tiene proveedor lento o alta variabilidad."],
        [""],
        ["6. TRES OPCIONES DE FRECUENCIA DE PEDIDO"],
        ["  OPCIÓN A — SEMANAL:   Pedido = REDONDEAR ARRIBA(consumo mensual promedio ÷ 4.33)"],
        ["  OPCIÓN B — QUINCENAL: Pedido = REDONDEAR ARRIBA(consumo mensual promedio ÷ 2)"],
        ["  OPCIÓN C — MENSUAL:   Pedido = REDONDEAR ARRIBA(consumo mensual promedio)"],
        ["  • 4.33 = semanas promedio por mes (52 semanas / 12 meses)"],
        ["  • Columnas de verificación: 4×semanal y 2×quincenal deben aproximar el mensual"],
        [""],
        ["7. HOJAS DEL ARCHIVO"],
        ["  • RESUMEN EJECUTIVO — KPIs globales"],
        ["  • PEDIDO UNIFICADO / TALLER / TIENDAS — tablas maestras de pedido"],
        ["  • COMPARATIVO FRECUENCIAS — las 3 opciones lado a lado"],
        ["  • DETALLE MENSUAL — consumo mes a mes por producto"],
        ["  • POR TIENDA — desglose de tiendas individuales"],
        ["  • DATOS LIMPIOS — base de datos procesada"],
        [""],
        ["8. RESUMEN DE DATOS PROCESADOS"],
        [f"  • Total registros válidos: {stats['total_registros']:,}"],
        [f"  • Registros TALLER: {stats['registros_taller']:,}"],
        [f"  • Registros TIENDAS: {stats['registros_tiendas']:,}"],
        [f"  • Productos únicos (unificado): {stats['productos_unicos']:,}"],
        [f"  • Unidades totales solicitadas: {stats['unidades_totales']:,.0f}"],
        [f"  • Registros de prueba (*PRUEBA*): {stats['registros_prueba']:,}"],
        [""],
        ["9. RECOMENDACIÓN DE USO"],
        ["  • Para la mayoría de consumibles regulares → OPCIÓN C (MENSUAL) es la más práctica"],
        ["  • Para productos de alta rotación o perecederos → OPCIÓN A (SEMANAL)"],
        ["  • Para balance entre frecuencia y volumen → OPCIÓN B (QUINCENAL)"],
        ["  • Revisar productos con alta desv. estándar: considerar MAX stock más alto"],
        ["  • Productos con pocas solicitudes (<3): validar manualmente antes de automatizar"],
    ]


def build_executive_summary(all_df, metrics_unificado, metrics_taller, metrics_tiendas):
    rows = [
        {"Indicador": "Periodo analizado", "Valor": f"{FECHA_INICIO.date()} a {FECHA_FIN.date()}"},
        {"Indicador": "Total solicitudes procesadas", "Valor": len(all_df)},
        {"Indicador": "Solicitudes TALLER", "Valor": len(all_df[all_df["origen"] == "TALLER"])},
        {"Indicador": "Solicitudes TIENDAS", "Valor": len(all_df[all_df["origen"] == "TIENDAS"])},
        {"Indicador": "Productos distintos (unificado)", "Valor": all_df["articulo_norm"].nunique()},
        {"Indicador": "Unidades totales solicitadas", "Valor": int(all_df["cantidad"].sum())},
        {"Indicador": "Unidades TALLER", "Valor": int(all_df.loc[all_df["origen"] == "TALLER", "cantidad"].sum())},
        {"Indicador": "Unidades TIENDAS", "Valor": int(all_df.loc[all_df["origen"] == "TIENDAS", "cantidad"].sum())},
        {"Indicador": "Tiendas analizadas", "Valor": ", ".join(STORE_SHEETS)},
        {"Indicador": "Productos con pedido mensual > 0 (unificado)", "Valor": int((metrics_unificado["pedido_mensual"] > 0).sum())},
        {"Indicador": "Top producto por volumen", "Valor": metrics_unificado.iloc[0]["articulo_norm"] if len(metrics_unificado) else "N/A"},
        {"Indicador": "Volumen top producto", "Valor": int(metrics_unificado.iloc[0]["total_historico"]) if len(metrics_unificado) else 0},
    ]

    # Top 10 products table
    top10 = metrics_unificado.head(10)[
        ["articulo_norm", "total_historico", "pedido_semanal", "pedido_quincenal", "pedido_mensual"]
    ].copy()
    top10.columns = ["Producto", "Total Histórico", "Pedido Semanal", "Pedido Quincenal", "Pedido Mensual"]

    return pd.DataFrame(rows), top10


def format_pedido_sheet(metrics, inventario):
    m = attach_inventory(metrics, inventario)
    cols = [
        "articulo_norm",
        "codigo",
        "categoria",
        "unidad",
        "total_historico",
        "n_solicitudes",
        "n_meses_con_demanda",
        "consumo_prom_mensual_periodo",
        "consumo_prom_mensual_demanda",
        "consumo_min_mensual",
        "consumo_max_mensual",
        "desv_std_mensual",
        "min_stock_sugerido",
        "max_stock_sugerido",
        "pedido_semanal",
        "pedido_quincenal",
        "pedido_mensual",
        "primera_solicitud",
        "ultima_solicitud",
    ]
    out = m[cols].copy()
    out.columns = [
        "Producto",
        "Código",
        "Categoría",
        "Unidad",
        "Total Histórico (und)",
        "N° Solicitudes",
        "Meses con Demanda",
        "Cons. Prom. Mensual (periodo)",
        "Cons. Prom. Mensual (meses activos)",
        "Cons. Mín. Mensual",
        "Cons. Máx. Mensual",
        "Desv. Std. Mensual",
        "MIN Stock Sugerido",
        "MAX Stock Sugerido",
        "PEDIDO Semanal",
        "PEDIDO Quincenal",
        "PEDIDO Mensual",
        "Primera Solicitud",
        "Última Solicitud",
    ]
    return out


def write_excel(output_path, sheets_dict, methodology_rows):
    with pd.ExcelWriter(output_path, engine="xlsxwriter", engine_kwargs={"options": {"nan_inf_to_errors": True}}) as writer:
        workbook = writer.book

        # Formats
        fmt_header = workbook.add_format(
            {"bold": True, "bg_color": "#1F4E79", "font_color": "white", "border": 1, "text_wrap": True}
        )
        fmt_title = workbook.add_format({"bold": True, "font_size": 14, "font_color": "#1F4E79"})
        fmt_subtitle = workbook.add_format({"bold": True, "font_size": 11, "bg_color": "#D9E2F3"})
        fmt_number = workbook.add_format({"num_format": "#,##0.00", "border": 1})
        fmt_int = workbook.add_format({"num_format": "#,##0", "border": 1})
        fmt_text = workbook.add_format({"border": 1, "text_wrap": True})
        fmt_date = workbook.add_format({"num_format": "yyyy-mm-dd", "border": 1})

        def write_df(ws_name, df, number_cols=None, int_cols=None, date_cols=None):
            df.to_excel(writer, sheet_name=ws_name, index=False, startrow=1)
            ws = writer.sheets[ws_name]
            ws.write(0, 0, ws_name, fmt_title)
            if df.empty:
                return
            for col_idx, col_name in enumerate(df.columns):
                ws.write(1, col_idx, col_name, fmt_header)
                width = max(len(str(col_name)), min(df[col_name].astype(str).str.len().max(), 45))
                ws.set_column(col_idx, col_idx, width + 2)
            number_cols = number_cols or []
            int_cols = int_cols or []
            date_cols = date_cols or []
            for row in range(2, len(df) + 2):
                for col_idx, col_name in enumerate(df.columns):
                    val = df.iloc[row - 2, col_idx]
                    if pd.isna(val):
                        val = ""
                    if col_name in date_cols:
                        ws.write(row, col_idx, val, fmt_date)
                    elif col_name in int_cols:
                        ws.write(row, col_idx, val, fmt_int)
                    elif col_name in number_cols:
                        ws.write(row, col_idx, val, fmt_number)
                    else:
                        ws.write(row, col_idx, val, fmt_text)
            ws.freeze_panes(2, 1)

        # Methodology sheet (manual)
        ws = workbook.add_worksheet("METODOLOGÍA")
        ws.set_column(0, 0, 100)
        for i, row in enumerate(methodology_rows):
            fmt = fmt_title if i == 0 else fmt_text
            ws.write(i, 0, row[0] if row else "", fmt)

        # Write all data sheets
        pedido_num = [
            "Total Histórico (und)",
            "Cons. Prom. Mensual (periodo)",
            "Cons. Prom. Mensual (meses activos)",
            "Cons. Mín. Mensual",
            "Cons. Máx. Mensual",
            "Desv. Std. Mensual",
        ]
        pedido_int = [
            "N° Solicitudes",
            "Meses con Demanda",
            "MIN Stock Sugerido",
            "MAX Stock Sugerido",
            "PEDIDO Semanal",
            "PEDIDO Quincenal",
            "PEDIDO Mensual",
        ]
        pedido_date = ["Primera Solicitud", "Última Solicitud"]

        for name, df in sheets_dict.items():
            if name == "METODOLOGÍA":
                continue
            if name.startswith("PEDIDO"):
                write_df(name, df, number_cols=pedido_num, int_cols=pedido_int, date_cols=pedido_date)
            elif name.startswith("DETALLE MENSUAL"):
                int_cols = [c for c in df.columns if c not in ("segmento", "articulo_norm")]
                write_df(name, df, int_cols=int_cols)
            elif name == "COMPARATIVO FRECUENCIAS":
                write_df(
                    name,
                    df,
                    number_cols=["consumo_prom_mensual_periodo"],
                    int_cols=[
                        "total_historico",
                        "consumo_min_mensual",
                        "consumo_max_mensual",
                        "min_stock_sugerido",
                        "max_stock_sugerido",
                        "pedido_semanal",
                        "pedido_quincenal",
                        "pedido_mensual",
                        "verif_4_semanas",
                        "verif_2_quincenas",
                        "equiv_mensual_desde_semanal",
                        "equiv_mensual_desde_quincenal",
                        "diferencia_vs_mensual",
                    ],
                )
            elif name == "RESUMEN EJECUTIVO":
                write_df(name, df)
            elif name == "TOP 10 PRODUCTOS":
                write_df(name, df, int_cols=["Total Histórico", "Pedido Semanal", "Pedido Quincenal", "Pedido Mensual"])
            elif name == "POR TIENDA":
                write_df(name, df, int_cols=["total", "n_solicitudes"], date_cols=["ultima_fecha"])
            elif name == "DATOS LIMPIOS":
                write_df(name, df, int_cols=["cantidad"], date_cols=["fecha"])
            elif name == "ESTADO SOLICITUDES":
                write_df(name, df, int_cols=["cantidad", "registros"])
            else:
                write_df(name, df)


def main():
    print("Cargando datos...")
    taller = load_taller()
    tiendas = load_tiendas()
    inventario = load_inventario()

    all_raw = pd.concat([taller, tiendas], ignore_index=True)
    all_df = clean_solicitudes(all_raw)

    taller_df = all_df[all_df["origen"] == "TALLER"].copy()
    tiendas_df = all_df[all_df["origen"] == "TIENDAS"].copy()

    print(f"Registros procesados: {len(all_df)}")

    metrics_unificado = build_product_metrics(all_df, "UNIFICADO")
    metrics_taller = build_product_metrics(taller_df, "TALLER")
    metrics_tiendas = build_product_metrics(tiendas_df, "TIENDAS")

    stats = {
        "total_registros": len(all_df),
        "registros_taller": len(taller_df),
        "registros_tiendas": len(tiendas_df),
        "productos_unicos": all_df["articulo_norm"].nunique(),
        "unidades_totales": all_df["cantidad"].sum(),
        "registros_prueba": int(all_df["es_prueba"].sum()),
    }

    methodology = build_methodology_text(stats)
    resumen, top10 = build_executive_summary(all_df, metrics_unificado, metrics_taller, metrics_tiendas)

    pedido_unificado = format_pedido_sheet(metrics_unificado, inventario)
    pedido_taller = format_pedido_sheet(metrics_taller, inventario)
    pedido_tiendas = format_pedido_sheet(metrics_tiendas, inventario)

    comparativo = frequency_comparison(metrics_unificado)
    comparativo = comparativo.rename(
        columns={
            "articulo_norm": "Producto",
            "total_historico": "Total Histórico",
            "consumo_prom_mensual_periodo": "Cons. Prom. Mensual",
            "consumo_min_mensual": "Cons. Mín. Mensual",
            "consumo_max_mensual": "Cons. Máx. Mensual",
            "min_stock_sugerido": "MIN Stock",
            "max_stock_sugerido": "MAX Stock",
            "pedido_semanal": "Pedido Semanal",
            "pedido_quincenal": "Pedido Quincenal",
            "pedido_mensual": "Pedido Mensual",
            "verif_4_semanas": "Verif. 4×Semanal",
            "verif_2_quincenas": "Verif. 2×Quincenal",
            "equiv_mensual_desde_semanal": "Equiv. Mensual (4 sem)",
            "equiv_mensual_desde_quincenal": "Equiv. Mensual (2 quin)",
            "diferencia_vs_mensual": "Dif. vs Promedio",
        }
    )

    detalle_uni = pivot_monthly(all_df, "UNIFICADO")
    detalle_taller = pivot_monthly(taller_df, "TALLER")
    detalle_tiendas = pivot_monthly(tiendas_df, "TIENDAS")

    por_tienda = store_breakdown(tiendas_df)

    estado_summary = (
        all_df.groupby(["origen", "estado"], as_index=False)
        .agg(registros=("cantidad", "count"), cantidad=("cantidad", "sum"))
        .sort_values(["origen", "cantidad"], ascending=[True, False])
    )

    datos_limpios = all_df[
        [
            "fecha",
            "origen",
            "tienda",
            "articulo",
            "articulo_norm",
            "cantidad",
            "estado",
            "nombre",
            "fuente_hoja",
            "es_prueba",
            "notas",
        ]
    ].sort_values(["fecha", "origen", "articulo_norm"])

    sheets = {
        "METODOLOGÍA": pd.DataFrame(),
        "RESUMEN EJECUTIVO": resumen,
        "TOP 10 PRODUCTOS": top10,
        "PEDIDO UNIFICADO": pedido_unificado,
        "PEDIDO TALLER": pedido_taller,
        "PEDIDO TIENDAS": pedido_tiendas,
        "COMPARATIVO FRECUENCIAS": comparativo,
        "DETALLE MENSUAL UNIFICADO": detalle_uni,
        "DETALLE MENSUAL TALLER": detalle_taller,
        "DETALLE MENSUAL TIENDAS": detalle_tiendas,
        "POR TIENDA": por_tienda,
        "ESTADO SOLICITUDES": estado_summary,
        "DATOS LIMPIOS": datos_limpios,
    }

    print(f"Generando Excel: {OUTPUT_FILE}")
    write_excel(OUTPUT_FILE, sheets, methodology)

    print("\n=== RESUMEN ===")
    print(f"Productos analizados (unificado): {len(metrics_unificado)}")
    print(f"Unidades totales: {stats['unidades_totales']:,.0f}")
    print(f"Pedido mensual total sugerido: {metrics_unificado['pedido_mensual'].sum():,.0f} und")
    print(f"Pedido quincenal total sugerido: {metrics_unificado['pedido_quincenal'].sum():,.0f} und")
    print(f"Pedido semanal total sugerido: {metrics_unificado['pedido_semanal'].sum():,.0f} und")
    print("\nTop 5 productos:")
    for _, r in metrics_unificado.head(5).iterrows():
        print(
            f"  {r['articulo_norm']}: total={r['total_historico']:.0f}, "
            f"mensual={r['pedido_mensual']}, quincenal={r['pedido_quincenal']}, semanal={r['pedido_semanal']}"
        )


if __name__ == "__main__":
    main()
