#!/usr/bin/env python3
"""Análisis de planificación: Tela Jabón Microfibra (metodología operativa)."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

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
    active = df[df["ventas_mensual"] >= 20].copy()
    max_v = active["ventas_mensual"].max()
    max_m = active["modelos"].max()
    max_cv = active["cv_mensual"].max()

    active["score_rotacion"] = active["ventas_mensual"] / max_v * 100 if max_v else 0
    active["score_regularidad"] = (1 - active["cv_mensual"].fillna(1).clip(0, 2) / max_cv) * 100 if max_cv else 50
    active["score_transversal"] = ((active["modelos"] / max_m * 0.6 + active["generos"] / 3 * 0.4) * 100) if max_m else 0
    active["score_no_inmov"] = active["cob_pt_meses"].apply(score_no_inmovilizacion)
    active["score_total"] = (
        active["score_rotacion"] * 0.40
        + active["score_regularidad"] * 0.25
        + active["score_transversal"] * 0.20
        + active["score_no_inmov"] * 0.15
    ).round(1)
    active = active.sort_values("score_total", ascending=False).reset_index(drop=True)
    active["rank"] = active.index + 1

    justificaciones = {
        "NEGRO": "Mayor volumen; CV bajo; 19 modelos; cobertura PT 7.2 meses",
        "BLANCO": "2do volumen; CV 0.32; vende todos los meses en 3 géneros",
        "AZUL MARINO": "3er volumen; demanda transversal; cobertura PT 5.7 meses",
        "VERDE MILITAR": "CV 0.46; 16 modelos; regular todo el año",
        "AZUL LAVANDA": "Top 5 ventas; 17 modelos; cobertura equilibrada",
        "AZUL REY": "Alterno #6; alta regularidad (CV 0.37)",
        "LILA": "Alto volumen pero CV 1.67 (pico moda Mar-26) — color de temporada",
    }

    top5 = active[active["pct_ventas"] >= 5].nlargest(5, "score_total").copy()
    top5.insert(0, "Top 5 Logística", range(1, len(top5) + 1))
    top5["Justificación"] = top5["color_norm"].map(
        lambda c: justificaciones.get(c, "Alta rotación con bajo riesgo relativo de inmovilización")
    )

    cols_top = [
        "Top 5 Logística", "Color", "ventas_unidades", "pct_ventas", "ventas_mensual", "cv_mensual",
        "modelos", "generos", "cob_pt_meses", "score_rotacion", "score_regularidad",
        "score_transversal", "score_no_inmov", "score_total", "Justificación",
    ]
    top5_out = top5[cols_top].copy()
    top5_out.columns = [
        "Top 5 Logística", "Color", "Ventas 10m (u)", "% Total", "Venta prom (u/mes)", "CV mensual",
        "Modelos", "Géneros", "Cobertura PT (meses)", "Score rotación (40%)", "Score regularidad (25%)",
        "Score transversal (20%)", "Score no-inmov (15%)", "SCORE TOTAL", "Justificación",
    ]

    ranking = active.copy()
    ranking["Recomendación"] = np.where(
        ranking["rank"] <= 5,
        "TOP 5 — Mantener/ampliar catálogo",
        np.where(ranking["cob_pt_meses"] > 12, "Evitar ampliación — sobrestock PT", "Evaluar caso por caso"),
    )
    ranking_out = ranking[
        ["rank", "Color", "ventas_mensual", "pct_ventas", "cv_mensual", "modelos", "generos",
         "cob_pt_meses", "score_total", "Recomendación"]
    ].copy()
    ranking_out.columns = [
        "Ranking", "Color", "Venta prom (u/mes)", "% Total", "CV mensual", "Modelos", "Géneros",
        "Cobertura PT (meses)", "SCORE TOTAL", "Recomendación",
    ]

    evitar = ranking[ranking["cob_pt_meses"] > 12].copy()
    evitar_out = evitar[["Color", "ventas_mensual", "inv_fg", "cob_pt_meses", "pct_ventas"]].copy()
    evitar_out["Motivo"] = (
        "Sobrestock PT: "
        + evitar_out["cob_pt_meses"].round(1).astype(str)
        + " meses con solo "
        + evitar_out["pct_ventas"].round(1).astype(str)
        + "% ventas"
    )
    evitar_out.columns = ["Color", "Venta prom (u/mes)", "Inv PT (u)", "Cobertura PT (meses)", "% Total", "Motivo"]

    return top5_out, ranking_out, evitar_out


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


def run_analysis(mp_path: Path, inv_path: Path, ventas_path: Path, boom_path: Path, output_path: Path) -> None:
    mp = pd.read_excel(mp_path)
    inv = pd.read_excel(inv_path)
    ventas = pd.read_excel(ventas_path)
    boom = pd.read_excel(boom_path)

    ventas_b, color_names, _, _ = prepare_data(mp, inv, ventas, boom)
    consumo, monthly = compute_consumption(ventas_b)
    df = build_color_master(ventas, inv, mp, consumo, color_names)
    df[["riesgo", "accion"]] = df.apply(lambda r: pd.Series(classify_riesgo(r)), axis=1)
    ped = compute_pedido_tela(df)
    log_top5, log_ranking, log_evitar = build_logistica_multicriterio(df)
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

    resumen_rows = [
        ["PLANIFICACIÓN TELA JABÓN MICROFIBRA — RESUMEN EJECUTIVO", ""],
        ["", ""],
        ["Ventas analizadas", f"{ventas['Cant. ordenada'].sum():,.0f} u en {MESES_HIST} meses · {ventas['Producto'].nunique()} productos · {ventas['color_norm'].nunique()} colores"],
        ["Inventario PT actual", f"{inv['Cantidad en inventario'].sum():,.0f} u ≈ {inv['Cantidad en inventario'].sum() / (ventas['Cant. ordenada'].sum()/MESES_HIST):.1f} meses"],
        ["Tela jabón en almacén MP", f"{mp['Cantidad en inventario'].sum():,.1f} kg en {mp['color_norm'].nunique()} colores"],
        ["Lead time tela", f"{LEAD_TIME_DIAS} días ({LEAD_TIME_MESES:.1f} meses)"],
        ["Horizonte pedido", f"Ago-Dic 2026 · MEQ = {ped['horizonte_meq'].iloc[0]:.2f} meses"],
        ["Pedido tela sugerido (total)", f"{ped['pedido_kg'].sum():,.0f} kg"],
        ["Producción PT requerida (total)", f"{ped['prod_requerida_u'].sum():,.0f} u"],
        ["Top 5 Logística (rotación + bajo riesgo inmov.)", ", ".join(log_top5["Color"].tolist())],
        ["Crítico operativo (pedido tela)", ", ".join(ped[ped["pedido_kg"] > 0]["Color"].tolist()) or "Ninguno"],
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
        summary.to_excel(writer, sheet_name="1. Resumen por Color", index=False)
        log_top5.to_excel(writer, sheet_name="2. Top 5 Logística", index=False)
        crit.to_excel(writer, sheet_name="3. Riesgo y Reorden", index=False)
        pedido_out.to_excel(writer, sheet_name="4. Pedido Tela", index=False)
        mod[["Producto", "ventas", "ventas_mes", "inv", "cob_meses", "venta_proy", "prod_requerida"]].rename(
            columns={"Producto": "Modelo", "ventas": "Ventas 10m", "ventas_mes": "Venta prom/mes", "inv": "Inv PT",
                     "cob_meses": "Cob. PT (meses)", "venta_proy": "Venta proy.", "prod_requerida": "Prod. requerida"}
        ).to_excel(writer, sheet_name="5. Resumen Modelos", index=False)
        mcs[["Producto", "Color", "TALLA", "v", "v_mes", "inv", "pedido_u", "kg_u", "kg_tela"]].rename(
            columns={"Producto": "Modelo", "TALLA": "Talla", "v": "Ventas 10m", "v_mes": "Venta prom/mes",
                     "inv": "Inv PT", "pedido_u": "Prod. requerida (u)", "kg_u": "kg/u", "kg_tela": "Kg tela c/merma"}
        ).to_excel(writer, sheet_name="6. Detalle Modelo-Color-Talla", index=False)
        mp.to_excel(writer, sheet_name="7. Inv Materia Prima", index=False)
        trend_out.to_excel(writer, sheet_name="8. Tendencia Mensual")
        estacional.to_excel(writer, sheet_name="8b. Estacionalidad", index=False)

        log_top5.to_excel(writer, sheet_name="9. Respuesta Logística", index=False, startrow=0)
        s1 = len(log_top5) + 3
        pd.DataFrame([["Colores a evitar por inmovilización PT"]]).to_excel(
            writer, sheet_name="9. Respuesta Logística", index=False, header=False, startrow=s1
        )
        log_evitar.to_excel(writer, sheet_name="9. Respuesta Logística", index=False, startrow=s1 + 1)
        s2 = s1 + 1 + len(log_evitar) + 2
        pd.DataFrame([["Ranking completo multicriterio"]]).to_excel(
            writer, sheet_name="9. Respuesta Logística", index=False, header=False, startrow=s2
        )
        log_ranking.to_excel(writer, sheet_name="9. Respuesta Logística", index=False, startrow=s2 + 1)

        semaforo.to_excel(writer, sheet_name="10. Semáforo Integrado", index=False)

        recon = summary[
            ["Color", "Consumo kg/mes", "kg/u pond.", "Cob. tela (meses)", "Prod. requerida (u)", "Pedido sugerido (kg)", "Riesgo", "Acción sugerida"]
        ].copy()
        recon["Notas verificación"] = np.where(
            (recon["Pedido sugerido (kg)"] == 0) & recon["Riesgo"].str.contains("CRÍTICA|SIN TELA", na=False),
            "PT cubre producción pero tela justa — validar escenario pico Nov-Dic",
            np.where(recon["Pedido sugerido (kg)"] > 0, "Pedido activo — priorizar compra", "Cubierto en horizonte base"),
        )
        recon.to_excel(writer, sheet_name="11. Verificación y Notas", index=False)

    print(f"Reporte generado: {output_path}")
    print(f"Pedido total tela: {ped['pedido_kg'].sum():.0f} kg")
    print(f"Producción PT total: {ped['prod_requerida_u'].sum():.0f} u")
    print(f"Top 5 logística: {', '.join(log_top5['Color'].tolist())}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Análisis planificación microfibra jabón")
    parser.add_argument("--mp", type=Path, required=True)
    parser.add_argument("--inv", type=Path, required=True)
    parser.add_argument("--ventas", type=Path, required=True)
    parser.add_argument("--boom", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("analisis_microfibra_jabon.xlsx"))
    args = parser.parse_args()
    run_analysis(args.mp, args.inv, args.ventas, args.boom, args.output)


if __name__ == "__main__":
    main()
