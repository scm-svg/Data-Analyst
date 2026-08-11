#!/usr/bin/env python3
"""Análisis de planificación: Tela Jabón Microfibra."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

MESES = 10
LEAD_TIME_DIAS = 45
LEAD_TIME_MESES = LEAD_TIME_DIAS / 30.0
DIAS_MES = 30
COBERTURA_MESES = 2


def norm_color(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().upper()
    for src, dst in [("Ó", "O"), ("É", "E"), ("Í", "I"), ("Á", "A"), ("Ú", "U")]:
        text = text.replace(src, dst)
    if text == "AZUL LAVANDO":
        return "AZUL LAVANDA"
    return text


def classify(row: pd.Series) -> tuple[str, str]:
    if row["ventas_unidades"] == 0:
        return "SIN ROTACIÓN", "SIN DEMANDA"
    pct = row["pct_ventas"]
    dias_tela = row["dias_cobertura_tela"]
    dias_fg = row["dias_cobertura_fg"]
    rotacion = "ALTA" if pct >= 8 else ("MEDIA" if pct >= 3 else "BAJA")
    if row["inv_tela_kg"] == 0 and row["ventas_mensual"] > 30:
        riesgo = "CRÍTICO - SIN TELA"
    elif dias_tela < LEAD_TIME_DIAS and row["ventas_mensual"] > 50:
        riesgo = "CRÍTICO - QUIEBRE TELA"
    elif dias_tela < LEAD_TIME_DIAS * 1.5 and row["ventas_mensual"] > 50:
        riesgo = "ALTO - REORDEN URGENTE"
    elif dias_fg < LEAD_TIME_DIAS and row["ventas_mensual"] > 50:
        riesgo = "MEDIO - FG BAJO"
    elif dias_fg > 180 and rotacion in {"BAJA", "MEDIA"}:
        riesgo = "SOBRESTOCK FG"
    elif dias_tela > 180 and rotacion == "BAJA":
        riesgo = "SOBRESTOCK TELA"
    else:
        riesgo = "NORMAL"
    return rotacion, riesgo


def _penalizacion_sobrestock(dias_cobertura: float) -> float:
    if dias_cobertura <= 60:
        return 0
    if dias_cobertura <= 90:
        return 10
    if dias_cobertura <= 120:
        return 25
    if dias_cobertura <= 180:
        return 45
    return 65


def _riesgo_inmovilizacion(dias_cobertura: float) -> str:
    if dias_cobertura <= 90:
        return "Bajo — equilibrado"
    if dias_cobertura <= 150:
        return "Moderado — vigilar niveles"
    return "Elevado — capital inmovilizado"


def build_logistica_analysis(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Ranking logístico: mejor rotación con menor riesgo de inmovilización."""
    active = df[df["ventas_mensual"] >= 50].copy()
    active["rotacion_inventario"] = active["ventas_unidades"] / np.maximum(active["inv_fg_unidades"], 1)
    active["giro_anual_estimado"] = active["rotacion_inventario"] * (12 / MESES)

    for col in ("ventas_mensual", "rotacion_inventario"):
        min_val, max_val = active[col].min(), active[col].max()
        active[f"n_{col}"] = (active[col] - min_val) / (max_val - min_val) * 100 if max_val > min_val else 50

    active["penal_sobrestock"] = active["dias_cobertura_fg"].apply(_penalizacion_sobrestock)
    active["score_logistica"] = (
        active["n_ventas_mensual"] * 0.55 + active["n_rotacion_inventario"] * 0.45 - active["penal_sobrestock"]
    )
    active["riesgo_inmovilizacion"] = active["dias_cobertura_fg"].apply(_riesgo_inmovilizacion)
    active = active.sort_values("score_logistica", ascending=False).reset_index(drop=True)
    active["ranking_logistica"] = active.index + 1
    active["recomendacion"] = np.where(
        active["ranking_logistica"] <= 5,
        "TOP 5 — Mantener/ampliar",
        np.where(active["dias_cobertura_fg"] > 180, "Evitar ampliación inicial", "Evaluar caso por caso"),
    )

    justificaciones = {
        "LILA": "Mejor equilibrio rotación/stock; giro más alto del portafolio",
        "AZUL MARINO": "Tercer mayor volumen con giro sólido y demanda transversal",
        "BLANCO": "Segundo mayor volumen (13.1%); rotación constante",
        "NEGRO": "Mayor rotación absoluta (16.1%); esencial por volumen estratégico",
        "AZUL LAVANDA": "Top 5 en ventas con giro saludable y demanda estable",
        "GRIS CLARO": "Buen giro de inventario, pero volumen por debajo del umbral estratégico (5%)",
    }

    top5_candidates = active[active["pct_ventas"] >= 5].sort_values("score_logistica", ascending=False).head(5)
    top5 = top5_candidates[
        [
            "Color",
            "ventas_unidades",
            "pct_ventas",
            "ventas_mensual",
            "inv_fg_unidades",
            "dias_cobertura_fg",
            "rotacion_inventario",
            "giro_anual_estimado",
            "score_logistica",
            "riesgo_inmovilizacion",
        ]
    ].copy()
    top5.insert(0, "Ranking Top 5", range(1, len(top5) + 1))
    top5["Recomendación"] = "TOP 5 — Mantener/ampliar"
    top5["Justificación"] = top5["Color"].str.upper().apply(
        lambda c: justificaciones.get(
            c.replace("Ó", "O").replace("É", "E"),
            "Alto volumen con balance favorable rotación/inventario",
        )
    )
    top5.columns = [
        "Ranking Top 5",
        "Color",
        "Ventas Total (uds)",
        "% del Total",
        "Ventas/Mes (uds)",
        "Inv FG (uds)",
        "Días Cobertura FG",
        "Giro Inventario (10m)",
        "Giro Anual Estimado",
        "Score Logística",
        "Riesgo Inmovilización",
        "Recomendación",
        "Justificación",
    ]

    ranking = active[
        [
            "ranking_logistica",
            "Color",
            "ventas_unidades",
            "pct_ventas",
            "ventas_mensual",
            "inv_fg_unidades",
            "dias_cobertura_fg",
            "rotacion_inventario",
            "giro_anual_estimado",
            "score_logistica",
            "riesgo_inmovilizacion",
            "recomendacion",
        ]
    ].copy()
    ranking.columns = [
        "Ranking",
        "Color",
        "Ventas Total (uds)",
        "% del Total",
        "Ventas/Mes (uds)",
        "Inv FG (uds)",
        "Días Cobertura FG",
        "Giro Inventario (10m)",
        "Giro Anual Estimado",
        "Score Logística",
        "Riesgo Inmovilización",
        "Recomendación",
    ]

    evitar = ranking[ranking["Días Cobertura FG"] > 180].copy()
    evitar["Motivo Exclusión"] = (
        "Sobrestock: "
        + evitar["Días Cobertura FG"].round(0).astype(int).astype(str)
        + " días de cobertura con solo "
        + evitar["% del Total"].round(1).astype(str)
        + "% de ventas"
    )
    evitar = evitar[
        ["Color", "Ventas/Mes (uds)", "Inv FG (uds)", "Días Cobertura FG", "% del Total", "Motivo Exclusión"]
    ]

    return top5, ranking, evitar


def run_analysis(
    mp_path: Path,
    inv_path: Path,
    ventas_path: Path,
    boom_path: Path,
    output_path: Path,
) -> None:
    mp = pd.read_excel(mp_path)
    inv = pd.read_excel(inv_path)
    ventas = pd.read_excel(ventas_path)
    boom = pd.read_excel(boom_path)

    for frame, column in [(mp, "color"), (inv, "COLOR"), (ventas, "COLOR"), (boom, "Color")]:
        frame["color_norm"] = frame[column].apply(norm_color)

    inv["modelo_key"] = inv["MODELO"] + " ORIGINAL " + inv["GENERO"]
    special = inv[~inv["Producto"].str.contains("ORIGINAL", na=False)]
    if len(special):
        inv.loc[special.index, "modelo_key"] = (
            special["Producto"].str.extract(r"\]\s*(.+?)\s*\(")[0].fillna(special["Producto"])
        )

    v_color = ventas.groupby("color_norm").agg(
        ventas_unidades=("Cant. ordenada", "sum"),
        ventas_mensual=("Cant. ordenada", lambda x: x.sum() / MESES),
    ).reset_index()
    inv_color = inv.groupby("color_norm").agg(inv_fg_unidades=("Cantidad en inventario", "sum")).reset_index()
    mp_color = mp.groupby("color_norm").agg(
        inv_tela_kg=("Cantidad en inventario", "sum"),
        producto_tela=("Producto", "first"),
    ).reset_index()
    boom_color = boom.groupby("color_norm").agg(kg_por_unidad=("Cantidad", "mean")).reset_index()

    colors = set(v_color["color_norm"]) | set(inv_color["color_norm"]) | set(mp_color["color_norm"])
    df = pd.DataFrame({"color_norm": sorted(colors)})
    df = df.merge(v_color, on="color_norm", how="left").fillna(0)
    df = df.merge(inv_color, on="color_norm", how="left").fillna(0)
    df = df.merge(mp_color, on="color_norm", how="left").fillna(0)
    df = df.merge(boom_color, on="color_norm", how="left")
    df["kg_por_unidad"] = df["kg_por_unidad"].fillna(0.42)

    color_names = ventas.groupby("color_norm")["COLOR"].first().to_dict()
    mp_names = mp.groupby("color_norm")["color"].first().to_dict()
    df["Color"] = df["color_norm"].map(color_names).fillna(df["color_norm"].map(mp_names)).fillna(df["color_norm"])

    df["ventas_diarias"] = df["ventas_mensual"] / DIAS_MES
    df["dias_cobertura_fg"] = np.where(df["ventas_diarias"] > 0, df["inv_fg_unidades"] / df["ventas_diarias"], 999)
    df["consumo_tela_mensual_kg"] = df["ventas_mensual"] * df["kg_por_unidad"]
    df["consumo_tela_diario_kg"] = df["consumo_tela_mensual_kg"] / DIAS_MES
    df["dias_cobertura_tela"] = np.where(
        df["consumo_tela_diario_kg"] > 0, df["inv_tela_kg"] / df["consumo_tela_diario_kg"], 999
    )
    df["consumo_leadtime_kg"] = df["consumo_tela_diario_kg"] * LEAD_TIME_DIAS
    df["consumo_cobertura_kg"] = df["consumo_tela_mensual_kg"] * COBERTURA_MESES
    df["stock_objetivo_kg"] = df["consumo_leadtime_kg"] + df["consumo_cobertura_kg"]
    df["necesidad_produccion_kg"] = np.maximum(0, df["stock_objetivo_kg"] - df["inv_tela_kg"])
    df["necesidad_fg_unidades"] = np.maximum(
        0, (df["ventas_mensual"] * (LEAD_TIME_MESES + COBERTURA_MESES)) - df["inv_fg_unidades"]
    )
    df["pct_ventas"] = df["ventas_unidades"] / df["ventas_unidades"].sum() * 100
    df[["rotacion", "riesgo"]] = df.apply(lambda row: pd.Series(classify(row)), axis=1)
    df = df.sort_values("ventas_unidades", ascending=False)

    v_modelo = ventas.groupby("Producto").agg(
        ventas=("Cant. ordenada", "sum"),
        ventas_mes=("Cant. ordenada", lambda x: x.sum() / MESES),
    ).reset_index()
    inv_modelo = (
        inv.groupby("modelo_key")
        .agg(inv=("Cantidad en inventario", "sum"))
        .reset_index()
        .rename(columns={"modelo_key": "Producto"})
    )
    mod = v_modelo.merge(inv_modelo, on="Producto", how="outer").fillna(0)
    mod["dias_cob"] = np.where(mod["ventas_mes"] > 0, mod["inv"] / (mod["ventas_mes"] / DIAS_MES), 999)
    mod["pedido_uds"] = np.maximum(0, mod["ventas_mes"] * (LEAD_TIME_MESES + COBERTURA_MESES) - mod["inv"])
    mod = mod.sort_values("ventas", ascending=False)

    ventas_mcs = ventas.groupby(["Producto", "color_norm", "TALLA"]).agg(
        ventas=("Cant. ordenada", "sum"),
        ventas_mes=("Cant. ordenada", lambda x: x.sum() / MESES),
    ).reset_index()
    inv_mcs = (
        inv.groupby(["modelo_key", "color_norm", "TALLA"])
        .agg(inv=("Cantidad en inventario", "sum"))
        .reset_index()
        .rename(columns={"modelo_key": "Producto"})
    )
    boom_mcs = (
        boom.groupby(["Modelo", "color_norm", "Talla"])
        .agg(kg_unidad=("Cantidad", "sum"))
        .reset_index()
        .rename(columns={"Modelo": "Producto", "Talla": "TALLA"})
    )
    mcs = ventas_mcs.merge(inv_mcs, on=["Producto", "color_norm", "TALLA"], how="outer").fillna(0)
    mcs = mcs.merge(boom_mcs, on=["Producto", "color_norm", "TALLA"], how="left")
    mcs["kg_unidad"] = mcs["kg_unidad"].fillna(0.42)
    mcs["pedido_uds"] = np.maximum(0, mcs["ventas_mes"] * (LEAD_TIME_MESES + COBERTURA_MESES) - mcs["inv"])
    mcs["kg_necesario"] = mcs["pedido_uds"] * mcs["kg_unidad"]
    mcs["dias_cob"] = np.where(mcs["ventas_mes"] > 0, mcs["inv"] / (mcs["ventas_mes"] / DIAS_MES), 999)

    talla_order = {
        "XS": 0, "S": 1, "M": 2, "L": 3, "XL": 4, "2XL": 5, "3XL": 6,
        "2": 0, "4": 1, "6": 2, "8": 3, "10": 4, "12": 5, "14": 6,
    }
    mcs["talla_ord"] = mcs["TALLA"].map(talla_order).fillna(99)
    top_models = mod.head(8)["Producto"].tolist()
    mcs_top = mcs[mcs["Producto"].isin(top_models) & (mcs["pedido_uds"] > 0)].sort_values(
        ["Producto", "color_norm", "talla_ord"]
    )
    color_display = df.set_index("color_norm")["Color"].to_dict()
    mcs_top = mcs_top.copy()
    mcs_top["Color"] = mcs_top["color_norm"].map(color_display)

    mes_order = {
        "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12, "ENERO": 1, "FEBRERO": 2,
        "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6, "JULIO": 7,
    }
    ventas["mes_num"] = ventas["Mes"].str.upper().map(mes_order)
    ventas["periodo"] = ventas.apply(
        lambda row: f"{int(row['Año'])}-{int(row['mes_num']):02d}", axis=1
    )
    ventas_trend = ventas.groupby(["periodo", "color_norm"])["Cant. ordenada"].sum().unstack(fill_value=0)

    ped = df[df["necesidad_produccion_kg"] > 0].sort_values("necesidad_produccion_kg", ascending=False)
    crit = df[df["riesgo"].str.contains("CRÍTICO|URGENTE|ALTO|SIN TELA", na=False)]
    log_top5, log_ranking, log_evitar = build_logistica_analysis(df)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary = df[
            [
                "Color", "ventas_unidades", "pct_ventas", "ventas_mensual", "inv_fg_unidades",
                "dias_cobertura_fg", "inv_tela_kg", "consumo_tela_mensual_kg", "dias_cobertura_tela",
                "rotacion", "riesgo", "stock_objetivo_kg", "necesidad_produccion_kg", "necesidad_fg_unidades",
            ]
        ].copy()
        summary.columns = [
            "Color", "Ventas Total (uds)", "% del Total", "Ventas/Mes (uds)", "Inv FG (uds)",
            "Días Cobertura FG", "Inv Tela (kg)", "Consumo Tela/Mes (kg)", "Días Cobertura Tela",
            "Rotación", "Riesgo", "Stock Objetivo Tela (kg)", "Pedido Tela (kg)", "Pedido FG (uds)",
        ]
        summary.to_excel(writer, sheet_name="1. Resumen por Color", index=False)
        df.nlargest(5, "ventas_unidades").to_excel(writer, sheet_name="2. Top 5 Colores", index=False)
        crit.to_excel(writer, sheet_name="3. Riesgo y Reorden", index=False)
        ped.to_excel(writer, sheet_name="4. Pedido Tela", index=False)
        mod.to_excel(writer, sheet_name="5. Resumen Modelos", index=False)
        mcs_top.to_excel(writer, sheet_name="6. Detalle Modelo-Color-Talla", index=False)
        mp.to_excel(writer, sheet_name="7. Inv Materia Prima", index=False)
        ventas_trend.to_excel(writer, sheet_name="8. Tendencia Mensual Color")

        log_top5.to_excel(writer, sheet_name="9. Respuesta Logística", index=False, startrow=0)
        start_evitar = len(log_top5) + 3
        log_evitar.to_excel(writer, sheet_name="9. Respuesta Logística", index=False, startrow=start_evitar)
        start_ranking = start_evitar + len(log_evitar) + 3
        log_ranking.to_excel(writer, sheet_name="9. Respuesta Logística", index=False, startrow=start_ranking)

        ws = writer.sheets["9. Respuesta Logística"]
        ws.cell(row=start_evitar, column=1, value="Colores a evitar por riesgo de inmovilización")
        ws.cell(row=start_ranking, column=1, value="Ranking completo (rotación + riesgo inmovilización)")

    print(f"Reporte generado: {output_path}")
    print(f"Pedido total tela: {ped['necesidad_produccion_kg'].sum():.1f} kg")


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
