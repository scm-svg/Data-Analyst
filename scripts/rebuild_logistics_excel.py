#!/usr/bin/env python3
"""Regenera hojas logísticas en analisis_microfibra_jabon.xlsx."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from excel_format import format_workbook
from logistica_excel import build_logistica_outputs, df_from_summary_sheet, write_logistica_sheets


def _read_sheet(xl: pd.ExcelFile, *names: str) -> pd.DataFrame | None:
    for n in names:
        if n in xl.sheet_names:
            return pd.read_excel(xl, n)
    return None


def rebuild(src: Path, dst: Path | None = None) -> Path:
    dst = dst or src
    tmp = dst.with_suffix(".tmp.xlsx")
    xl = pd.ExcelFile(src)

    summary = _read_sheet(xl, "1. Resumen por Color", "7. Resumen por Color")
    if summary is None:
        raise ValueError("No se encontró hoja Resumen por Color")

    df = df_from_summary_sheet(summary)
    ped = df.copy()
    if "venta_proy_u" not in ped.columns and "Venta proy. horizonte (u)" in summary.columns:
        ped["venta_proy_u"] = summary["Venta proy. horizonte (u)"]
    log = build_logistica_outputs(df, ped)

    top5_nombres = ", ".join(log["top5_detalle"]["Color"].tolist())
    rojo_rank = log["ranking_completo"].loc[
        log["ranking_completo"]["Color"].str.upper() == "ROJO", "Ranking"
    ]
    rojo_rank_txt = f"#{int(rojo_rank.iloc[0])}" if len(rojo_rank) else "—"

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
            "y su inventario fluye sin acumularse. Detalle en hoja '1. Respuesta Logística'.",
        ],
        ["", ""],
        ["PLANIFICACIÓN TELA — DATOS GENERALES", ""],
        ["", ""],
    ]

    old = _read_sheet(xl, "0. Resumen Ejecutivo")
    if old is not None:
        for _, r in old.iterrows():
            c = str(r.iloc[0] or "")
            if any(
                c.startswith(p)
                for p in [
                    "Ventas", "Inventario", "Tela", "Lead", "Horizonte",
                    "Pedido", "Producción", "Crítico", "Metodología", "Supuestos",
                ]
            ):
                resumen_rows.append([c, r.iloc[1]])

    resumen_rows.extend([
        [
            "Nota Lila",
            "No está en el Top 5 (color de moda) pero es prioridad #1 en pedido de tela — ver hoja 4",
        ],
        [
            "Nota Rojo",
            f"Vende bien (rank {rojo_rank_txt}) pero queda fuera del Top 5 por ~14 meses de stock PT — ver hoja 3",
        ],
    ])
    resumen = pd.DataFrame(resumen_rows, columns=["Concepto", "Valor"])

    copies = [
        ("3. Riesgo y Reorden", "8. Riesgo y Reorden"),
        ("4. Pedido Tela", "9. Pedido Tela"),
        ("5. Resumen Modelos", "10. Resumen Modelos"),
        ("6. Detalle Modelo-Color-Talla", "11. Detalle Modelo-Color-Talla"),
        ("7. Inv Materia Prima", "12. Inv Materia Prima"),
        ("8. Tendencia Mensual", "13. Tendencia Mensual"),
        ("8b. Estacionalidad", "14. Estacionalidad"),
        ("10. Semáforo Integrado", "15. Semáforo Integrado"),
        ("11. Verificación y Notas", "16. Verificación y Notas"),
    ]

    with pd.ExcelWriter(tmp, engine="openpyxl") as writer:
        resumen.to_excel(writer, sheet_name="0. Resumen Ejecutivo", index=False)
        write_logistica_sheets(writer, log)
        summary.to_excel(writer, sheet_name="7. Resumen por Color", index=False)
        for old_name, new_name in copies:
            data = _read_sheet(xl, new_name, old_name)
            if data is not None:
                data.to_excel(writer, sheet_name=new_name, index=False)

    format_workbook(str(tmp))
    tmp.replace(dst)
    return dst


if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "analisis_microfibra_jabon.xlsx")
    out = rebuild(path)
    print(f"Excel actualizado: {out}")
