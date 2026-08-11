#!/usr/bin/env python3
"""Análisis de planificación: Tela Jabón Microfibra (metodología operativa)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard_html import generate_dashboard_html
from excel_format import format_workbook
from logistica_excel import TOP5_CANONICAL, build_logistica_outputs, df_from_summary_sheet, write_logistica_sheets

MESES_HIST = 10
LEAD_TIME_DIAS = 45
LEAD_TIME_MESES = LEAD_TIME_DIAS / 30.0
DIAS_MES = 30
COBERTURA_PT_MESES = 1.5
MERMA = 0.05
UPLIFT_TIENDA = 0.10
PEDIDO_MINIMO_KG = 50
REDONDEO_KG = 10
Z_ABC = {"A": 1.65, "B": 1.28, "C": 0.84}

MES_ORDER = {
    "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12, "ENERO": 1, "FEBRERO": 2,
    "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9,
}

# Horizonte de pedido: Ago-Dic 2026 (índices estacionales + uplift tienda desde oct)
HORIZONTE = [
    ("AGO-26", 0.75, 0.67, 0, 1),
    ("SEP-26", 0.90, 1.00, 0, 1),
    ("OCT-26", 0.91, 1.00, 1, 1),
    ("NOV-26", 1.20, 1.00, 1, 1),  # ajustado vs 0.855 observado en 2025
    ("DIC-26", 1.96, 1.00, 1, 1),
]


def norm_color(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().upper()
    for src, dst in [("Ó", "O"), ("É", "E"), ("Í", "I"), ("Á", "A"), ("Ú", "U")]:
        text = text.replace(src, dst)
    if text == "AZUL LAVANDO":
        return "AZUL LAVANDA"
    return text


def display_color(color_norm: str, names: dict[str, str]) -> str:
    return names.get(color_norm, color_norm.title())


def prepare_data(mp: pd.DataFrame, inv: pd.DataFrame, ventas: pd.DataFrame, boom: pd.DataFrame):
    for frame, column in [(mp, "color"), (inv, "COLOR"), (ventas, "COLOR"), (boom, "Color")]:
        frame["color_norm"] = frame[column].apply(norm_color)

    inv["modelo_key"] = inv["MODELO"] + " ORIGINAL " + inv["GENERO"]
    special = inv[~inv["Producto"].str.contains("ORIGINAL", na=False)]
    if len(special):
        inv.loc[special.index, "modelo_key"] = (
            special["Producto"].str.extract(r"\]\s*(.+?)\s*\(")[0].fillna(special["Producto"])
        )

    ventas["mes_num"] = ventas["Mes"].str.upper().map(MES_ORDER)
    ventas["periodo"] = ventas.apply(
        lambda r: f"{int(r['Año'])}-{int(r['mes_num']):02d}" if pd.notna(r["mes_num"]) else None,
        axis=1,
    )

    color_names = ventas.groupby("color_norm")["COLOR"].first().to_dict()
    for k, v in mp.groupby("color_norm")["color"].first().to_dict().items():
        color_names.setdefault(k, v)

    boom_kg = (
        boom.groupby(["Modelo", "color_norm", "Talla"])
        .agg(kg_boom=("Cantidad", "sum"))
        .reset_index()
        .rename(columns={"Modelo": "Producto", "Talla": "TALLA"})
    )
    ventas_b = ventas.merge(boom_kg, on=["Producto", "color_norm", "TALLA"], how="left")

    # kg/u ponderado por color: ventas con BOOM + fallback al promedio del color
    color_kg_avg = (
        ventas_b.dropna(subset=["kg_boom"])
        .groupby("color_norm")
        .apply(lambda g: np.average(g["kg_boom"], weights=g["Cant. ordenada"]))
        .to_dict()
    )
    global_avg = ventas_b["kg_boom"].mean()
    ventas_b["kg_u"] = ventas_b.apply(
        lambda r: r["kg_boom"] if pd.notna(r["kg_boom"]) else color_kg_avg.get(r["color_norm"], global_avg or 0.42),
        axis=1,
    )
    ventas_b["kg_consumo"] = ventas_b["Cant. ordenada"] * ventas_b["kg_u"]

    return ventas_b, color_names, color_kg_avg, global_avg or 0.42


def compute_consumption(ventas_b: pd.DataFrame) -> pd.DataFrame:
    monthly = (
        ventas_b.groupby(["color_norm", "periodo"])
        .agg(unidades=("Cant. ordenada", "sum"), kg=("kg_consumo", "sum"))
        .reset_index()
    )
    summary = ventas_b.groupby("color_norm").agg(
        unidades=("Cant. ordenada", "sum"),
        kg_total=("kg_consumo", "sum"),
    ).reset_index()
    summary["kg_prom_mes"] = summary["kg_total"] / MESES_HIST
    summary["kg_u_pond"] = summary["kg_total"] / summary["unidades"].replace(0, np.nan)
    summary["kg_u_pond"] = summary["kg_u_pond"].fillna(0.42)

    cv = monthly.groupby("color_norm")["unidades"].agg(lambda s: s.std() / s.mean() if s.mean() > 0 else np.nan)
    sigma_u = monthly.groupby("color_norm")["unidades"].std()
    summary = summary.merge(cv.rename("cv_mensual"), on="color_norm", how="left")
    summary = summary.merge(sigma_u.rename("sigma_u_mes"), on="color_norm", how="left")
    # σ consumo (kg/mes) = σ(unidades/mes) × kg/u ponderado (misma lógica del planificador)
    summary["sigma_kg_mes"] = summary["sigma_u_mes"] * summary["kg_u_pond"]
    summary["sigma_kg_mes"] = summary["sigma_kg_mes"].fillna(0)
    return summary, monthly


def classify_abc(pct_acum: float) -> str:
    if pct_acum <= 0.80:
        return "A"
    if pct_acum <= 0.95:
        return "B"
    return "C"


def build_color_master(
    ventas: pd.DataFrame,
    inv: pd.DataFrame,
    mp: pd.DataFrame,
    consumo: pd.DataFrame,
    color_names: dict[str, str],
) -> pd.DataFrame:
    v = ventas.groupby("color_norm").agg(
        ventas_unidades=("Cant. ordenada", "sum"),
        ventas_mensual=("Cant. ordenada", lambda x: x.sum() / MESES_HIST),
        modelos=("Producto", "nunique"),
        generos=("GENERO", "nunique"),
    ).reset_index()
    fg = inv.groupby("color_norm").agg(inv_fg=("Cantidad en inventario", "sum")).reset_index()
    tela = mp.groupby("color_norm").agg(inv_tela=("Cantidad en inventario", "sum"), sku_tela=("Producto", "first")).reset_index()

    df = v.merge(fg, on="color_norm", how="outer").merge(tela, on="color_norm", how="outer")
    df = df.merge(consumo[["color_norm", "kg_prom_mes", "kg_u_pond", "cv_mensual", "sigma_kg_mes"]], on="color_norm", how="left")
    df = df.fillna({"ventas_unidades": 0, "ventas_mensual": 0, "inv_fg": 0, "inv_tela": 0, "modelos": 0, "generos": 0})
    df["Color"] = df["color_norm"].map(lambda c: display_color(c, color_names))
    df["pct_ventas"] = df["ventas_unidades"] / df["ventas_unidades"].sum() * 100
    df = df.sort_values("ventas_unidades", ascending=False).reset_index(drop=True)
    df["pct_acum"] = df["pct_ventas"].cumsum() / 100
    df["abc"] = df["pct_acum"].apply(classify_abc)

    df["cob_pt_meses"] = np.where(df["ventas_mensual"] > 0, df["inv_fg"] / df["ventas_mensual"], np.nan)
    df["cob_tela_meses"] = np.where(df["kg_prom_mes"] > 0, df["inv_tela"] / df["kg_prom_mes"], np.nan)
    df["dias_cob_pt"] = df["cob_pt_meses"] * DIAS_MES
    df["dias_cob_tela"] = df["cob_tela_meses"] * DIAS_MES

    return df


def score_no_inmovilizacion(cob_meses: float) -> float:
    if pd.isna(cob_meses) or cob_meses <= 0:
        return 100
    if cob_meses <= 8:
        return 100
    if cob_meses <= 12:
        return 70
    if cob_meses <= 18:
        return 40
    return 10


def build_logistica_multicriterio(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compatibilidad: delega en logistica_excel."""
    log = build_logistica_outputs(df)
    ranking_out = log["ranking_completo"][
        ["Ranking", "Color", "Venta prom (u/mes)", "% ventas", "Regularidad",
         "Meses stock PT", "SCORE TOTAL", "Veredicto"]
    ].copy()
    ranking_out.columns = [
        "Ranking", "Color", "Venta prom (u/mes)", "% Total", "Regularidad",
        "Cobertura PT (meses)", "SCORE TOTAL", "Recomendación",
    ]
    return log["top5_tecnico"], ranking_out, log["evitar"]


def classify_riesgo(row: pd.Series) -> tuple[str, str]:
    if row["ventas_mensual"] == 0:
        return "SIN DEMANDA", "Sin acción"
    if row["inv_tela"] == 0 and row["ventas_mensual"] >= 30:
        return "SIN TELA", "Incluir en pedido — sin capacidad de reacción"
    if pd.notna(row["cob_tela_meses"]) and row["cob_tela_meses"] < LEAD_TIME_MESES * 2:
        return "TELA CRÍTICA", "Incluir en pedido o priorizar consumo"
    if pd.notna(row["cob_pt_meses"]) and row["cob_pt_meses"] > 12:
        return "SOBRE-STOCK PT", "No producir; redistribuir entre tiendas"
    if pd.notna(row["cob_pt_meses"]) and row["cob_pt_meses"] < 2 and row["ventas_mensual"] >= 5:
        return "QUIEBRE PT", "Producir/reponer de inmediato"
    return "SALUDABLE", "Mantener; monitoreo mensual"


def compute_pedido_tela(df: pd.DataFrame) -> pd.DataFrame:
    meq = sum(frac * idx * (1 + UPLIFT_TIENDA if uplift else 1) for _, idx, frac, uplift, inc in HORIZONTE if inc)
    out = df.copy()
    out["venta_proy_u"] = out["ventas_mensual"] * meq
    out["stock_pt_obj_u"] = out["ventas_mensual"] * COBERTURA_PT_MESES
    out["prod_requerida_u"] = np.maximum(0, out["venta_proy_u"] + out["stock_pt_obj_u"] - out["inv_fg"])
    out["kg_prod_merma"] = out["prod_requerida_u"] * out["kg_u_pond"] * (1 + MERMA)
    z = out["abc"].map(Z_ABC).fillna(1.28)
    out["ss_tela_kg"] = z * out["sigma_kg_mes"] * np.sqrt(LEAD_TIME_MESES)
    out["necesidad_neta_kg"] = np.maximum(0, out["kg_prod_merma"] + out["ss_tela_kg"] - out["inv_tela"])

    def calc_pedido(row):
        if row["abc"] == "C" and row["necesidad_neta_kg"] <= 0:
            return 0.0
        if row["abc"] == "C" and row["necesidad_neta_kg"] > 0:
            return 0.0  # decisión comercial manual
        need = row["necesidad_neta_kg"]
        if need <= 0:
            return 0.0
        if 0 < need < PEDIDO_MINIMO_KG and row["inv_tela"] == 0:
            need = PEDIDO_MINIMO_KG
        return float(np.ceil(need / REDONDEO_KG) * REDONDEO_KG)

    out["pedido_kg"] = out.apply(calc_pedido, axis=1)
    out["cob_tela_post_meses"] = np.where(
        out["kg_prom_mes"] > 0,
        (out["inv_tela"] + out["pedido_kg"]) / out["kg_prom_mes"],
        np.nan,
    )
    out["horizonte_meq"] = meq
    return out


def build_semaforo(df: pd.DataFrame, ped: pd.DataFrame) -> pd.DataFrame:
    merged = df.merge(ped[["color_norm", "prod_requerida_u", "pedido_kg", "necesidad_neta_kg"]], on="color_norm")

    def sem_rot(pct):
        if pct >= 8:
            return "ALTA"
        if pct >= 3:
            return "MEDIA"
        return "BAJA"

    def sem_reg(cv):
        if pd.isna(cv) or cv <= 0.5:
            return "REGULAR"
        if cv <= 1.0:
            return "VARIABLE"
        return "MODA/PIco"

    def sem_pt(cob):
        if pd.isna(cob):
            return "N/A"
        if cob > 12:
            return "SOBRESTOCK"
        if cob < 2:
            return "QUIEBRE"
        return "OK"

    def sem_tela(cob, inv_tela):
        if inv_tela == 0 and cob == 0:
            return "SIN TELA"
        if pd.isna(cob):
            return "N/A"
        if cob < LEAD_TIME_MESES * 2:
            return "CRÍTICO"
        if cob < 4:
            return "BAJO"
        return "OK"

    def accion(row):
        parts = []
        if row["pedido_kg"] > 0:
            parts.append(f"Pedir {row['pedido_kg']:.0f} kg tela")
        elif row["sem_tela"] in {"CRÍTICO", "SIN TELA"} and row["prod_requerida_u"] <= 0:
            parts.append("Validar tela de reserva (PT cubre pero tela justa)")
        if row["prod_requerida_u"] > 0:
            parts.append(f"Producir {row['prod_requerida_u']:.0f} u PT")
        if row["sem_pt"] == "SOBRESTOCK":
            parts.append("Redistribuir, no producir")
        if row["sem_pt"] == "QUIEBRE":
            parts.append("Reponer PT urgente")
        return " · ".join(parts) if parts else "Monitorear"

    merged["sem_rotacion"] = merged["pct_ventas"].apply(sem_rot)
    merged["sem_regularidad"] = merged["cv_mensual"].apply(sem_reg)
    merged["sem_pt"] = merged["cob_pt_meses"].apply(sem_pt)
    merged["sem_tela"] = merged.apply(lambda r: sem_tela(r["cob_tela_meses"], r["inv_tela"]), axis=1)
    merged["accion_integrada"] = merged.apply(accion, axis=1)

    out = merged[
        ["Color", "abc", "ventas_mensual", "pct_ventas", "cv_mensual", "cob_pt_meses", "cob_tela_meses",
         "sem_rotacion", "sem_regularidad", "sem_pt", "sem_tela", "prod_requerida_u", "pedido_kg", "accion_integrada"]
    ].copy()
    out.columns = [
        "Color", "ABC", "Venta prom (u/mes)", "% Total", "CV mensual", "Cob. PT (meses)", "Cob. tela (meses)",
        "Rotación", "Regularidad", "Riesgo PT", "Riesgo Tela", "Prod. requerida (u)", "Pedido tela (kg)", "Acción integrada",
    ]
    return out.sort_values("Pedido tela (kg)", ascending=False)


def build_modelo_pedido(ventas: pd.DataFrame, inv: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    meq = df["horizonte_meq"].iloc[0] if len(df) else 5.88
    v = ventas.groupby("Producto").agg(ventas=("Cant. ordenada", "sum"), ventas_mes=("Cant. ordenada", lambda x: x.sum() / MESES_HIST)).reset_index()
    i = inv.groupby("modelo_key").agg(inv=("Cantidad en inventario", "sum")).reset_index().rename(columns={"modelo_key": "Producto"})
    mod = v.merge(i, on="Producto", how="outer").fillna(0)
    mod["venta_proy"] = mod["ventas_mes"] * meq
    mod["stock_obj"] = mod["ventas_mes"] * COBERTURA_PT_MESES
    mod["prod_requerida"] = np.maximum(0, mod["venta_proy"] + mod["stock_obj"] - mod["inv"])
    mod["cob_meses"] = np.where(mod["ventas_mes"] > 0, mod["inv"] / mod["ventas_mes"], np.nan)
    mod = mod.sort_values("prod_requerida", ascending=False)
    return mod


def build_mcs_detalle(ventas: pd.DataFrame, inv: pd.DataFrame, boom: pd.DataFrame, df: pd.DataFrame, color_names: dict):
    meq = df["horizonte_meq"].iloc[0] if len(df) else 5.88
    boom_m = boom.groupby(["Modelo", "color_norm", "Talla"]).agg(kg_u=("Cantidad", "sum")).reset_index().rename(
        columns={"Modelo": "Producto", "Talla": "TALLA"}
    )
    v = ventas.groupby(["Producto", "color_norm", "TALLA"]).agg(v=("Cant. ordenada", "sum"), v_mes=("Cant. ordenada", lambda x: x.sum() / MESES_HIST)).reset_index()
    i = inv.groupby(["modelo_key", "color_norm", "TALLA"]).agg(inv=("Cantidad en inventario", "sum")).reset_index().rename(columns={"modelo_key": "Producto"})
    m = v.merge(i, on=["Producto", "color_norm", "TALLA"], how="outer").fillna(0)
    m = m.merge(boom_m, on=["Producto", "color_norm", "TALLA"], how="left")
    kg_map = df.set_index("color_norm")["kg_u_pond"].to_dict()
    m["kg_u"] = m["kg_u"].fillna(m["color_norm"].map(kg_map)).fillna(0.42)
    m["venta_proy"] = m["v_mes"] * meq
    m["stock_obj"] = m["v_mes"] * COBERTURA_PT_MESES
    m["pedido_u"] = np.maximum(0, m["venta_proy"] + m["stock_obj"] - m["inv"])
    m["kg_tela"] = m["pedido_u"] * m["kg_u"] * (1 + MERMA)
    m["Color"] = m["color_norm"].map(lambda c: display_color(c, color_names))
    return m[m["pedido_u"] > 0].sort_values("kg_tela", ascending=False)


def run_analysis(
    mp_path: Path,
    inv_path: Path,
    ventas_path: Path,
    boom_path: Path,
    output_path: Path,
    dashboard_path: Path | None = None,
) -> None:
    mp = pd.read_excel(mp_path)
    inv = pd.read_excel(inv_path)
    ventas = pd.read_excel(ventas_path)
    boom = pd.read_excel(boom_path)

    ventas_b, color_names, _, _ = prepare_data(mp, inv, ventas, boom)
    consumo, monthly = compute_consumption(ventas_b)
    df = build_color_master(ventas, inv, mp, consumo, color_names)
    df[["riesgo", "accion"]] = df.apply(lambda r: pd.Series(classify_riesgo(r)), axis=1)
    ped = compute_pedido_tela(df)
    log = build_logistica_outputs(df, ped)
    log_top5 = log["top5_tecnico"]
    log_ranking = log["ranking_completo"]
    log_evitar = log["evitar"]
    semaforo = build_semaforo(df, ped)
    mod = build_modelo_pedido(ventas, inv, ped)
    mcs = build_mcs_detalle(ventas, inv, boom, ped, color_names)

    ventas_trend = ventas.groupby(["periodo", "color_norm"])["Cant. ordenada"].sum().unstack(fill_value=0)
    trend_out = ventas_trend.copy()
    trend_out.columns = [display_color(c, color_names) for c in trend_out.columns]

    total_mes = ventas.groupby("periodo")["Cant. ordenada"].sum()
    base_no_pico = total_mes.drop(["2025-11", "2025-12"], errors="ignore").mean()
    estacional = (total_mes / base_no_pico).reset_index()
    estacional.columns = ["Periodo", "Indice estacional"]

    top5_nombres = ", ".join(log["top5_detalle"]["Color"].tolist())
    resumen_rows = [
        ["RESPUESTA LOGÍSTICA — TOP 5 COLORES", ""],
        ["", ""],
        [
            "Pregunta",
            "¿Cuáles son los 5 colores con mejor rotación y menor riesgo de quedar inmovilizados en inventario?",
        ],
        ["Respuesta", top5_nombres],
        [
            "Por qué estos 5",
            "Venden mucho y de forma pareja, están en todo el catálogo (cab/dama/kids) "
            "y su inventario fluye sin acumularse meses en tienda. Detalle en hoja '1. Respuesta Logística'.",
        ],
        ["", ""],
        ["PLANIFICACIÓN TELA — DATOS GENERALES", ""],
        ["", ""],
        ["Ventas analizadas", f"{ventas['Cant. ordenada'].sum():,.0f} u en {MESES_HIST} meses · {ventas['Producto'].nunique()} productos · {ventas['color_norm'].nunique()} colores"],
        ["Inventario PT actual", f"{inv['Cantidad en inventario'].sum():,.0f} u ≈ {inv['Cantidad en inventario'].sum() / (ventas['Cant. ordenada'].sum()/MESES_HIST):.1f} meses"],
        ["Tela jabón en almacén MP", f"{mp['Cantidad en inventario'].sum():,.1f} kg en {mp['color_norm'].nunique()} colores"],
        ["Lead time tela", f"{LEAD_TIME_DIAS} días ({LEAD_TIME_MESES:.1f} meses)"],
        ["Horizonte pedido", f"Ago-Dic 2026 · MEQ = {ped['horizonte_meq'].iloc[0]:.2f} meses"],
        ["Pedido tela sugerido (total)", f"{ped['pedido_kg'].sum():,.0f} kg"],
        ["Producción PT requerida (total)", f"{ped['prod_requerida_u'].sum():,.0f} u"],
        ["Crítico operativo (pedido tela)", ", ".join(ped[ped["pedido_kg"] > 0]["Color"].tolist()) or "Ninguno"],
        ["Nota Lila", "No está en el Top 5 (color de moda) pero es prioridad #1 en pedido de tela hoy — ver hoja 4"],
        ["Nota Rojo", "Vende bien pero queda fuera del Top 5 por 14 meses de stock PT — ver hoja 3 ranking #12"],
        ["", ""],
        ["Metodología pedido", "Prod = Venta proy + Stock PT obj (1.5m) − Inv PT · Tela = kg prod × 1.05 + SS(z×σ×√LT) − Inv tela"],
        ["Supuestos", f"Nov 1.20× · Dic 1.96× · tienda +{UPLIFT_TIENDA:.0%} desde oct · merma {MERMA:.0%} · pedido min {PEDIDO_MINIMO_KG} kg"],
    ]
    resumen = pd.DataFrame(resumen_rows, columns=["Concepto", "Valor"])

    summary = ped[
        ["Color", "abc", "ventas_unidades", "pct_ventas", "ventas_mensual", "cv_mensual", "modelos", "generos",
         "inv_fg", "cob_pt_meses", "inv_tela", "kg_prom_mes", "kg_u_pond", "cob_tela_meses", "riesgo", "accion",
         "venta_proy_u", "prod_requerida_u", "kg_prod_merma", "ss_tela_kg", "necesidad_neta_kg", "pedido_kg", "cob_tela_post_meses"]
    ].copy()
    summary.columns = [
        "Color", "ABC", "Ventas 10m (u)", "% Total", "Venta prom (u/mes)", "CV mensual", "Modelos", "Géneros",
        "Inv PT (u)", "Cob. PT (meses)", "Tela actual (kg)", "Consumo kg/mes", "kg/u pond.", "Cob. tela (meses)",
        "Riesgo", "Acción sugerida", "Venta proy. horizonte (u)", "Prod. requerida (u)", "Kg prod. c/merma",
        "SS tela (kg)", "Necesidad neta (kg)", "Pedido sugerido (kg)", "Cob. tela post-pedido (meses)",
    ]

    pedido_out = summary[summary["Pedido sugerido (kg)"] > 0][
        ["Color", "ABC", "Tela actual (kg)", "Consumo kg/mes", "Prod. requerida (u)", "Necesidad neta (kg)", "Pedido sugerido (kg)", "Cob. tela post-pedido (meses)", "Acción sugerida"]
    ]

    crit = summary[summary["Riesgo"].str.contains("CRÍTICA|SIN TELA|QUIEBRE", na=False)]

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        resumen.to_excel(writer, sheet_name="0. Resumen Ejecutivo", index=False)
        write_logistica_sheets(writer, log)
        summary.to_excel(writer, sheet_name="7. Resumen por Color", index=False)
        crit.to_excel(writer, sheet_name="8. Riesgo y Reorden", index=False)
        pedido_out.to_excel(writer, sheet_name="9. Pedido Tela", index=False)
        mod[["Producto", "ventas", "ventas_mes", "inv", "cob_meses", "venta_proy", "prod_requerida"]].rename(
            columns={"Producto": "Modelo", "ventas": "Ventas 10m", "ventas_mes": "Venta prom/mes", "inv": "Inv PT",
                     "cob_meses": "Cob. PT (meses)", "venta_proy": "Venta proy.", "prod_requerida": "Prod. requerida"}
        ).to_excel(writer, sheet_name="10. Resumen Modelos", index=False)
        mcs[["Producto", "Color", "TALLA", "v", "v_mes", "inv", "pedido_u", "kg_u", "kg_tela"]].rename(
            columns={"Producto": "Modelo", "TALLA": "Talla", "v": "Ventas 10m", "v_mes": "Venta prom/mes",
                     "inv": "Inv PT", "pedido_u": "Prod. requerida (u)", "kg_u": "kg/u", "kg_tela": "Kg tela c/merma"}
        ).to_excel(writer, sheet_name="11. Detalle Modelo-Color-Talla", index=False)
        mp.to_excel(writer, sheet_name="12. Inv Materia Prima", index=False)
        trend_out.to_excel(writer, sheet_name="13. Tendencia Mensual")
        estacional.to_excel(writer, sheet_name="14. Estacionalidad", index=False)
        semaforo.to_excel(writer, sheet_name="15. Semáforo Integrado", index=False)

        recon = summary[
            ["Color", "Consumo kg/mes", "kg/u pond.", "Cob. tela (meses)", "Prod. requerida (u)", "Pedido sugerido (kg)", "Riesgo", "Acción sugerida"]
        ].copy()
        recon["Notas verificación"] = np.where(
            (recon["Pedido sugerido (kg)"] == 0) & recon["Riesgo"].str.contains("CRÍTICA|SIN TELA", na=False),
            "PT cubre producción pero tela justa — validar escenario pico Nov-Dic",
            np.where(recon["Pedido sugerido (kg)"] > 0, "Pedido activo — priorizar compra", "Cubierto en horizonte base"),
        )
        recon.to_excel(writer, sheet_name="16. Verificación y Notas", index=False)

    format_workbook(str(output_path))

    dash_path = dashboard_path or output_path.parent / "dashboard_tela_jabon_microfibra.html"

    ctx = _build_dashboard_context(ventas, inv, mp, summary, ped, pedido_out, log_top5, semaforo)
    generate_dashboard_html(ctx, dash_path)

    print(f"Reporte generado: {output_path}")
    print(f"Dashboard HTML: {dash_path}")
    print(f"Pedido total tela: {ped['pedido_kg'].sum():.0f} kg")
    print(f"Producción PT total: {ped['prod_requerida_u'].sum():.0f} u")
    print(f"Top 5 logística: {', '.join(log_top5['Color'].tolist())}")


def _build_dashboard_context(
    ventas: pd.DataFrame,
    inv: pd.DataFrame,
    mp: pd.DataFrame,
    summary: pd.DataFrame,
    ped: pd.DataFrame,
    pedido_out: pd.DataFrame,
    log_top5: pd.DataFrame,
    semaforo: pd.DataFrame,
) -> dict:
    from datetime import date

    ventas = ventas.copy()
    ventas["cn"] = ventas["COLOR"].apply(norm_color)
    lila_v = ventas[ventas["cn"] == "LILA"]
    mes_map = {"OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12, "ENERO": 1, "FEBRERO": 2, "MARZO": 3}
    ventas["mn"] = ventas["Mes"].str.upper().map(mes_map)
    ventas["periodo"] = ventas.apply(
        lambda r: f"{int(r['Año'])}-{int(r['mn']):02d}" if pd.notna(r.get("mn")) else None, axis=1
    )
    lila_mes = lila_v.groupby("periodo")["Cant. ordenada"].sum()
    lila_total = float(lila_v["Cant. ordenada"].sum())
    pico_mes = float(lila_mes.max()) if len(lila_mes) else 0
    pct_dama = float(lila_v[lila_v["GENERO"] == "DAMA"]["Cant. ordenada"].sum() / lila_total * 100) if lila_total else 0

    sku_map = mp.groupby("color_norm")["Producto"].first().to_dict()
    motivos = {
        "LILA": "MAFE Lila agotada con demanda viva; en almacén solo quedan ~188 kg. Es el urgente.",
        "ROJO": "Tela en cero. Sin tela no hay forma de reaccionar: cualquier faltante tarda 45 días.",
        "PÚRPURA": "Tela en cero. Pedido mínimo para recuperar capacidad de reacción.",
        "PURPURA": "Tela en cero. Pedido mínimo para recuperar capacidad de reacción.",
    }

    pedidos = []
    for _, row in pedido_out.iterrows():
        cn = norm_color(row["Color"])
        pedidos.append({
            "Color": row["Color"],
            "kg": float(row["Pedido sugerido (kg)"]),
            "sku": sku_map.get(cn, ""),
            "sin_codigo": cn in {"ROJO", "PURPURA", "PÚRPURA"} and not sku_map.get(cn),
            "motivo": motivos.get(cn, row.get("Acción sugerida", "Incluir en pedido de tela")),
        })

    top5_order = ["NEGRO", "BLANCO", "AZUL MARINO", "VERDE MILITAR", "AZUL LAVANDA"]
    checks_map = {
        "NEGRO": [
            "El que más vende de todo el catálogo",
            "Vendió bien los 10 meses, sin excepción",
            "Presente en 19 modelos y 3 géneros",
            "Lo que hay en stock dura ~7 meses: fluye",
        ],
        "BLANCO": [
            "Segundo en ventas",
            "El más parejo de todos: CV bajo",
            "Vende en 18 modelos y 3 géneros",
            "Stock rota en ~6,6 meses",
        ],
        "AZUL MARINO": [
            "Tercero en ventas",
            "Vende todos los meses",
            "Vende en 18 modelos y 3 géneros",
            "El que más rápido rota del top: ~5,7 meses",
        ],
        "VERDE MILITAR": [
            "Venta sólida y sin picos artificiales",
            "Parejo todo el año",
            "Vende en 16 modelos y 3 géneros",
            "Rota en ~8 meses, dentro de lo sano",
        ],
        "AZUL LAVANDA": [
            "Quinto en ventas sostenidas",
            "Vende todos los meses",
            "Vende en 17 modelos y 3 géneros",
            "Stock rota en ~6,7 meses",
        ],
    }
    sm = summary.copy()
    sm["cn"] = sm["Color"].apply(norm_color)
    top5 = []
    for cn in top5_order:
        row = sm[sm["cn"] == cn]
        if row.empty:
            continue
        r = row.iloc[0]
        top5.append({
            "Color": r["Color"],
            "ventas_mes": float(r["Venta prom (u/mes)"]),
            "pct": float(r["% Total"]),
            "checks": checks_map.get(cn, []),
        })

    azul_rey = summary[summary["Color"].str.upper().str.contains("AZUL REY", na=False)]
    alterno = None
    if len(azul_rey):
        r = azul_rey.iloc[0]
        alterno = {
            "Color": r["Color"],
            "ventas_mes": float(r["Venta prom (u/mes)"]),
            "nota": "Si se prefiere seguridad sobre volumen, puede intercambiarse con Azul Lavanda",
        }

    cubiertos = []
    for _, r in summary[(summary["Pedido sugerido (kg)"] == 0) & (summary["ABC"].isin(["A", "B"]))].iterrows():
        if float(r["Inv PT (u)"]) <= 0:
            continue
        nota = f"{r['Tela actual (kg)']:.0f} kg en almacén" if r["Tela actual (kg)"] > 0 else f"{r['Cob. PT (meses)']:.0f} meses PT"
        if "SOBRE" in str(r["Riesgo"]):
            nota = f"{r['Cob. PT (meses)']:.0f} meses de stock"
        cubiertos.append({"Color": r["Color"], "nota": nota})

    pedir_items = [{"Color": p["Color"], "nota": f"{p['kg']:.0f} kg"} for p in pedidos]
    vigilar = semaforo[
        (semaforo["Pedido tela (kg)"] == 0) & semaforo["Riesgo Tela"].isin(["CRÍTICO", "BAJO"])
    ][["Color", "Acción integrada"]].head(5)
    vigilar_items = [{"Color": r["Color"], "nota": "tela justa"} for _, r in vigilar.iterrows()]
    ok_items = [
        {"Color": r["Color"], "nota": f"{r['Cob. PT (meses)']:.0f} meses PT"}
        for _, r in summary[summary["Riesgo"].str.contains("SOBRE", na=False)].head(6).iterrows()
    ]
    decidir_items = [
        {"Color": r["Color"], "nota": r["Riesgo"]}
        for _, r in summary[summary["Riesgo"].str.contains("QUIEBRE|SIN DEMANDA", na=False)].head(8).iterrows()
    ]

    return {
        "meta": {
            "fecha": date.today().strftime("%d/%m/%Y"),
            "meses": MESES_HIST,
            "ventas_total": float(ventas["Cant. ordenada"].sum()),
            "inv_pt": float(inv["Cantidad en inventario"].sum()),
            "inv_tela": float(mp["Cantidad en inventario"].sum()),
        },
        "top5": top5,
        "alterno": alterno,
        "pedidos": pedidos,
        "cubiertos": cubiertos,
        "lila": {
            "ventas_total": lila_total,
            "pct_mes_pico": pico_mes / lila_total * 100 if lila_total else 0,
            "pct_dama": pct_dama,
        },
        "pendientes": [
            " 1) Crear en Odoo los códigos de tela de Rojo y Púrpura (nunca se les ha comprado tela).",
            " 2) Confirmar si Clásica Dama y Kids siguen vigentes: venden pero no tienen inventario ni receta.",
            " 3) Decidir qué hacer con Azul Cielo (se vende y está agotado) y con los 90 kg de tela Fucsia sin movimiento.",
        ],
        "semaforo": {
            "pedir": {"desc": "La tela en almacén no alcanza para lo necesario antes de diciembre.", "items": pedir_items},
            "vigilar": {"desc": "El PT cubre por ahora, pero la tela está justa para un pico Nov–Dic.", "items": vigilar_items},
            "ok": {"desc": "Hay tela y/o prendas de sobra. No comprar más tela; redistribuir entre tiendas.", "items": ok_items},
            "decidir": {"desc": "Antes de asignarles tela, comercial debe confirmar si van o no.", "items": decidir_items},
        },
    }


def refresh_logistics_excel(excel_path: Path) -> None:
    """Actualiza hojas logísticas en un Excel existente."""
    from rebuild_logistics_excel import rebuild

    rebuild(excel_path)


def _sheet(excel_path: Path, *candidates: str) -> str:
    xl = pd.ExcelFile(excel_path)
    for c in candidates:
        if c in xl.sheet_names:
            return c
    raise KeyError(f"Ninguna hoja encontrada: {candidates}")


def build_dashboard_context_from_excel(excel_path: Path, ventas_path: Path | None = None) -> dict:
    """Reconstruye el contexto del dashboard desde analisis_microfibra_jabon.xlsx."""
    from datetime import date

    summary = pd.read_excel(excel_path, _sheet(excel_path, "7. Resumen por Color", "1. Resumen por Color"))
    pedido_out = pd.read_excel(excel_path, _sheet(excel_path, "9. Pedido Tela", "4. Pedido Tela"))
    semaforo = pd.read_excel(excel_path, _sheet(excel_path, "15. Semáforo Integrado", "10. Semáforo Integrado"))
    mp = pd.read_excel(excel_path, _sheet(excel_path, "12. Inv Materia Prima", "7. Inv Materia Prima"))
    tend = pd.read_excel(excel_path, _sheet(excel_path, "13. Tendencia Mensual", "8. Tendencia Mensual"))
    resumen = pd.read_excel(excel_path, "0. Resumen Ejecutivo", header=None)

    def _cell(row: int, col: int = 1) -> str:
        v = resumen.iloc[row, col] if col < len(resumen.columns) else None
        return "" if pd.isna(v) else str(v)

    ventas_total = inv_pt = inv_tela = 0.0
    for i in range(len(resumen)):
        label = str(resumen.iloc[i, 0] or "")
        val = str(resumen.iloc[i, 1] or "")
        if "Ventas analizadas" in label:
            ventas_total = float(val.split(" u")[0].replace(",", ""))
        elif "Inventario PT" in label:
            inv_pt = float(val.split(" u")[0].replace(",", ""))
        elif "Tela jabón" in label or "Tela jab" in label:
            inv_tela = float(val.split(" kg")[0].replace(",", ""))

    lila_total = float(summary.loc[summary["Color"].str.upper() == "LILA", "Ventas 10m (u)"].iloc[0])
    lila_mes = tend["Lila"]
    pico_mes = float(lila_mes.max())
    pct_mes_pico = pico_mes / lila_total * 100 if lila_total else 0

    pct_dama = 79.0
    if ventas_path and ventas_path.exists():
        ventas = pd.read_excel(ventas_path)
        ventas["color_norm"] = ventas["COLOR"].apply(norm_color)
        lila_v = ventas[ventas["color_norm"] == "LILA"]
        tot = float(lila_v["Cant. ordenada"].sum())
        if tot:
            pct_dama = float(lila_v[lila_v["GENERO"] == "DAMA"]["Cant. ordenada"].sum() / tot * 100)

    mp = mp.copy()
    mp["color_norm"] = mp["color"].apply(norm_color) if "color_norm" not in mp.columns else mp["color_norm"]
    sku_map = mp.groupby("color_norm")["Producto"].first().to_dict()
    motivos = {
        "LILA": "MAFE Lila agotada con demanda viva; en almacén solo quedan ~188 kg. Es el urgente.",
        "ROJO": "Tela en cero. Sin tela no hay forma de reaccionar: cualquier faltante tarda 45 días.",
        "PÚRPURA": "Tela en cero. Pedido mínimo para recuperar capacidad de reacción.",
        "PURPURA": "Tela en cero. Pedido mínimo para recuperar capacidad de reacción.",
    }

    pedidos = []
    for _, row in pedido_out.iterrows():
        cn = norm_color(row["Color"])
        pedidos.append({
            "Color": row["Color"],
            "kg": float(row["Pedido sugerido (kg)"]),
            "sku": sku_map.get(cn, ""),
            "sin_codigo": cn in {"ROJO", "PURPURA", "PÚRPURA"} and not sku_map.get(cn),
            "motivo": motivos.get(cn, row.get("Acción sugerida", "Incluir en pedido de tela")),
        })

    top5_order = ["NEGRO", "BLANCO", "AZUL MARINO", "VERDE MILITAR", "AZUL LAVANDA"]
    checks_map = {
        "NEGRO": [
            "El que más vende de todo el catálogo",
            "Vendió bien los 10 meses, sin excepción",
            "Presente en 19 modelos y 3 géneros",
            "Lo que hay en stock dura ~7 meses: fluye",
        ],
        "BLANCO": [
            "Segundo en ventas",
            "El más parejo de todos: CV bajo",
            "Vende en 18 modelos y 3 géneros",
            "Stock rota en ~6,6 meses",
        ],
        "AZUL MARINO": [
            "Tercero en ventas",
            "Vende todos los meses",
            "Vende en 18 modelos y 3 géneros",
            "El que más rápido rota del top: ~5,7 meses",
        ],
        "VERDE MILITAR": [
            "Venta sólida y sin picos artificiales",
            "Parejo todo el año",
            "Vende en 16 modelos y 3 géneros",
            "Rota en ~8 meses, dentro de lo sano",
        ],
        "AZUL LAVANDA": [
            "Quinto en ventas sostenidas",
            "Vende todos los meses",
            "Vende en 17 modelos y 3 géneros",
            "Stock rota en ~6,7 meses",
        ],
    }
    sm = summary.copy()
    sm["cn"] = sm["Color"].apply(norm_color)
    top5 = []
    for cn in top5_order:
        row = sm[sm["cn"] == cn]
        if row.empty:
            continue
        r = row.iloc[0]
        top5.append({
            "Color": r["Color"],
            "ventas_mes": float(r["Venta prom (u/mes)"]),
            "pct": float(r["% Total"]),
            "checks": checks_map.get(cn, []),
        })

    azul_rey = summary[summary["Color"].str.upper().str.contains("AZUL REY", na=False)]
    alterno = None
    if len(azul_rey):
        r = azul_rey.iloc[0]
        alterno = {
            "Color": r["Color"],
            "ventas_mes": float(r["Venta prom (u/mes)"]),
            "nota": "Si se prefiere seguridad sobre volumen, puede intercambiarse con Azul Lavanda",
        }

    cubiertos = []
    for _, r in summary[(summary["Pedido sugerido (kg)"] == 0) & (summary["ABC"].isin(["A", "B"]))].iterrows():
        if float(r["Inv PT (u)"]) <= 0:
            continue
        nota = f"{r['Tela actual (kg)']:.0f} kg en almacén" if r["Tela actual (kg)"] > 0 else f"{r['Cob. PT (meses)']:.0f} meses PT"
        if "SOBRE" in str(r["Riesgo"]):
            nota = f"{r['Cob. PT (meses)']:.0f} meses de stock"
        cubiertos.append({"Color": r["Color"], "nota": nota})

    pedir_items = [{"Color": p["Color"], "nota": f"{p['kg']:.0f} kg"} for p in pedidos]
    vigilar = semaforo[
        (semaforo["Pedido tela (kg)"] == 0) & semaforo["Riesgo Tela"].isin(["CRÍTICO", "BAJO"])
    ][["Color", "Acción integrada"]].head(5)
    vigilar_items = [{"Color": r["Color"], "nota": "tela justa"} for _, r in vigilar.iterrows()]
    ok_items = [
        {"Color": r["Color"], "nota": f"{r['Cob. PT (meses)']:.0f} meses PT"}
        for _, r in summary[summary["Riesgo"].str.contains("SOBRE", na=False)].head(6).iterrows()
    ]
    decidir_items = [
        {"Color": r["Color"], "nota": r["Riesgo"]}
        for _, r in summary[summary["Riesgo"].str.contains("QUIEBRE|SIN DEMANDA", na=False)].head(8).iterrows()
    ]

    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    hoy = date.today()
    fecha = f"{hoy.day} de {meses[hoy.month - 1]} de {hoy.year}"

    return {
        "meta": {
            "fecha": fecha,
            "meses": MESES_HIST,
            "ventas_total": ventas_total,
            "inv_pt": inv_pt,
            "inv_tela": inv_tela,
        },
        "top5": top5,
        "alterno": alterno,
        "pedidos": pedidos,
        "cubiertos": cubiertos,
        "lila": {
            "ventas_total": lila_total,
            "pct_mes_pico": pct_mes_pico,
            "pct_dama": pct_dama,
        },
        "pendientes": [
            " 1) Crear en Odoo los códigos de tela de Rojo y Púrpura (nunca se les ha comprado tela).",
            " 2) Confirmar si Clásica Dama y Kids siguen vigentes: venden pero no tienen inventario ni receta.",
            " 3) Decidir qué hacer con Azul Cielo (se vende y está agotado) y con los 90 kg de tela Fucsia sin movimiento.",
        ],
        "semaforo": {
            "pedir": {"desc": "La tela en almacén no alcanza para lo necesario antes de diciembre.", "items": pedir_items},
            "vigilar": {"desc": "El PT cubre por ahora, pero la tela está justa para un pico Nov–Dic.", "items": vigilar_items},
            "ok": {"desc": "Hay tela y/o prendas de sobra. No comprar más tela; redistribuir entre tiendas.", "items": ok_items},
            "decidir": {"desc": "Antes de asignarles tela, comercial debe confirmar si van o no.", "items": decidir_items},
        },
    }


def _build_acciones_dashboard(semaforo: pd.DataFrame, summary: pd.DataFrame) -> list[dict]:
    acciones = []
    watch = semaforo[
        (semaforo["Pedido tela (kg)"] == 0)
        & semaforo["Riesgo Tela"].isin(["CRÍTICO", "SIN TELA"])
    ].head(3)
    for _, r in watch.iterrows():
        acciones.append({
            "tipo": "validar",
            "tipo_label": "Validar",
            "titulo": f"{r['Color']} — tela justa",
            "texto": r["Acción integrada"],
        })
    clasic = summary[summary["Color"].str.contains("CLASICA", case=False, na=False)]
    if len(clasic):
        acciones.append({
            "tipo": "info",
            "tipo_label": "Confirmar",
            "titulo": "Clásica DAMA/KIDS",
            "texto": "Venden sin inventario ni BOOM vigente. Confirmar con producción si siguen activos.",
        })
    return acciones


def _build_alertas_dashboard(summary: pd.DataFrame, ped: pd.DataFrame, log_top5: pd.DataFrame) -> list[str]:
    alertas = [
        "Diciembre vende casi el doble del mes promedio — planificar con índice 1,96×.",
        "Noviembre 2025 fue bajo (0,85×) probablemente por falta de stock; se planifica Nov-26 al 1,20×.",
        f"Top 5 catálogo permanente: {', '.join(log_top5['Color'].tolist())}.",
    ]
    crit = ped[ped["pedido_kg"] > 0]["Color"].tolist()
    if crit:
        alertas.insert(0, f"Pedido de tela prioritario: {', '.join(crit)}.")
    sob = summary[summary["Riesgo"].str.contains("SOBRE", na=False)]["Color"].head(3).tolist()
    if sob:
        alertas.append(f"Sobrestock PT (no producir): {', '.join(sob)}.")
    return alertas


def main() -> None:
    parser = argparse.ArgumentParser(description="Análisis planificación microfibra jabón")
    parser.add_argument("--mp", type=Path)
    parser.add_argument("--inv", type=Path)
    parser.add_argument("--ventas", type=Path, help="Ventas Odoo (requerido salvo --from-excel)")
    parser.add_argument("--boom", type=Path)
    parser.add_argument("--output", type=Path, default=Path("analisis_microfibra_jabon.xlsx"))
    parser.add_argument("--dashboard", type=Path, default=None, help="Ruta del dashboard HTML")
    parser.add_argument(
        "--from-excel",
        type=Path,
        default=None,
        help="Regenerar solo el dashboard HTML desde un Excel ya generado",
    )
    parser.add_argument(
        "--refresh-logistics",
        action="store_true",
        help="Actualizar solo las hojas de respuesta logística en un Excel existente",
    )
    args = parser.parse_args()
    if args.refresh_logistics:
        target = args.from_excel or args.output
        refresh_logistics_excel(target)
        return
    if args.from_excel:
        dash = args.dashboard or args.from_excel.parent / "dashboard_tela_jabon_microfibra.html"
        ctx = build_dashboard_context_from_excel(args.from_excel, args.ventas)
        generate_dashboard_html(ctx, dash)
        print(f"Dashboard HTML: {dash}")
        return
    for name, val in [("mp", args.mp), ("inv", args.inv), ("ventas", args.ventas), ("boom", args.boom)]:
        if val is None:
            parser.error(f"argument --{name} is required unless --from-excel is used")
    run_analysis(args.mp, args.inv, args.ventas, args.boom, args.output, args.dashboard)


if __name__ == "__main__":
    main()
