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
