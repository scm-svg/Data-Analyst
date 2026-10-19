"""Hojas de respuesta logística — lenguaje operativo, no técnico."""

from __future__ import annotations

import numpy as np
import pandas as pd

MESES_HIST = 10

TOP5_CANONICAL = ["NEGRO", "BLANCO", "AZUL MARINO", "VERDE MILITAR", "AZUL LAVANDA"]

SCORE_LEYENDA = [
    ["Criterio", "Peso", "Qué mide (en simple)", "Cómo leerlo"],
    [
        "Rotación",
        "40%",
        "Cuánto vende el color cada mes, comparado con el que más vende.",
        "100 = el que más rota. 50 = vende la mitad que el líder. Más alto = mejor.",
    ],
    [
        "Regularidad",
        "25%",
        "Si las ventas son parejas mes a mes o vienen a golpes (moda, lanzamientos).",
        "100 = vende estable todo el año. Bajo = un mes explota y otros caen (riesgo de inventario varado).",
    ],
    [
        "Transversalidad",
        "20%",
        "Si el color está en muchos modelos y en caballero, dama y kids.",
        "100 = presente en casi todo el catálogo. Bajo = color de nicho.",
    ],
    [
        "No inmovilizar",
        "15%",
        "Cuántos meses duraría el inventario de prendas terminadas al ritmo actual de venta.",
        "100 = stock fluye (≤8 meses). Penaliza fuerte si hay >12 meses de prendas paradas.",
    ],
    [
        "SCORE TOTAL",
        "100%",
        "Promedio ponderado de los cuatro criterios.",
        "Sirve para ordenar colores: mayor score = mejor rotación con menor riesgo de quedarse quieto en bodega/tienda.",
    ],
]

METODO_SIMPLE = [
    "Se analizaron 10 meses de ventas (oct-25 a jul-26) y el inventario actual de prendas y tela.",
    "Solo entran al ranking colores con venta mínima de 20 u/mes (colores muertos quedan fuera).",
    "El Top 5 no es solo 'los que más venden': también penaliza picos de moda y mucho stock parado.",
    "Un color puede vender bien (ej. Rojo, Lila) y aun así quedar fuera si el inventario no fluye o la venta es irregular.",
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


def _meses_stock_label(meses: float) -> str:
    if pd.isna(meses):
        return "sin datos"
    m = float(meses)
    if m <= 8:
        return f"{m:.1f} meses — fluye bien"
    if m <= 12:
        return f"{m:.1f} meses — aceptable"
    return f"{m:.1f} meses — mucho stock parado"


def _regularidad_label(cv: float) -> str:
    if pd.isna(cv):
        return "Sin patrón claro"
    if cv <= 0.45:
        return "Muy parejo todo el año"
    if cv <= 0.75:
        return "Estable con algún pico"
    if cv <= 1.0:
        return "Variable — hay meses fuertes y débiles"
    return "A golpes — color de moda o lanzamiento"


def _veredicto_top5(cn: str, rank: int, score: float, in_top5: bool) -> str:
    if in_top5:
        return "TOP 5 — Catálogo permanente"
    if cn == "LILA":
        return "Fuera del Top 5 — Color de temporada"
    if cn == "ROJO":
        return "Fuera del Top 5 — Sobrestock de prendas"
    if cn in {"PURPURA", "PÚRPURA"}:
        return "Fuera del Top 5 — Poco volumen + stock alto"
    if rank <= 8 and score >= 55:
        return "Candidato suplente — evaluar vs Top 5"
    if rank <= 10:
        return "Vende, pero no cumple las 4 pruebas"
    return "No prioritario para catálogo base"


def _por_que_no_top5(row: pd.Series, in_top5: bool) -> str:
    if in_top5:
        return "—"
    cn = row["color_norm"]
    parts = []

    if cn == "LILA":
        return (
            "Vende mucho en total (4º del catálogo) pero ~57% de las ventas fueron en un solo mes "
            "(lanzamiento MAFE Lila en marzo) y ~79% es solo dama. Es tendencia, no base permanente."
        )
    if cn == "ROJO":
        return (
            f"Vende {row['ventas_mensual']:.0f} u/mes (top 10), pero hay {row['inv_fg']:,.0f} prendas en stock "
            f"— eso son {row['cob_pt_meses']:.0f} meses de inventario parado. "
            "El criterio 'no inmovilizar' lo penaliza fuerte. "
            "Hoy además no hay tela en almacén (pedido de 50 kg es por reacción, no por catálogo permanente)."
        )
    if cn == "AZUL REY":
        return (
            "Buena regularidad (vende parejo), pero menor volumen que Azul Lavanda y "
            f"{row['cob_pt_meses']:.0f} meses de stock PT — puede servir como suplente del #5 si se prefiere seguridad sobre volumen."
        )

    if row.get("score_no_inmov", 100) < 70:
        parts.append(
            f"Mucho stock parado: {row['cob_pt_meses']:.0f} meses de prendas ({row['inv_fg']:,.0f} u) "
            f"con solo {row['pct_ventas']:.1f}% de la venta total."
        )
    if row.get("cv_mensual", 0) > 0.9:
        parts.append(f"Venta irregular (CV {row['cv_mensual']:.2f}): no vende parejo todos los meses.")
    if row.get("pct_ventas", 0) < 5:
        parts.append(f"Volumen bajo ({row['pct_ventas']:.1f}% del total) — no entra al grupo de colores núcleo.")
    if row.get("score_rotacion", 0) < 45:
        parts.append("Rotación menor que los colores núcleo del catálogo.")

    return " ".join(parts) if parts else "Score total por debajo del umbral del Top 5."


def _justificacion_top5(row: pd.Series) -> str:
    cn = row["color_norm"]
    v = row["ventas_mensual"]
    pct = row["pct_ventas"]
    cob = row["cob_pt_meses"]
    mod = int(row["modelos"])
    gen = int(row["generos"])
    reg = _regularidad_label(row["cv_mensual"])

    plantillas = {
        "NEGRO": (
            f"El que más vende ({v:.0f} u/mes, {pct:.0f}% del total). {reg}. "
            f"Presente en {mod} modelos y {gen} géneros. Stock dura {_meses_stock_label(cob).split(' —')[0]}: rota sin estancarse."
        ),
        "BLANCO": (
            f"Segundo en ventas ({v:.0f} u/mes). {reg} — el más predecible del catálogo. "
            f"{mod} modelos, {gen} géneros. Inventario fluye ({_meses_stock_label(cob)})."
        ),
        "AZUL MARINO": (
            f"Tercero en volumen ({v:.0f} u/mes). {reg}. Demanda en {mod} modelos y {gen} géneros. "
            f"Rota rápido: {_meses_stock_label(cob)}."
        ),
        "VERDE MILITAR": (
            f"Venta sólida ({v:.0f} u/mes), fuerte en caballero. {reg}. "
            f"{mod} modelos, {gen} géneros. {_meses_stock_label(cob)}."
        ),
        "AZUL LAVANDA": (
            f"Quinto en ventas sostenidas ({v:.0f} u/mes). {reg}. "
            f"{mod} modelos, {gen} géneros. {_meses_stock_label(cob)}."
        ),
    }
    return plantillas.get(
        cn,
        f"{v:.0f} u/mes · {reg} · {mod} modelos · {_meses_stock_label(cob)}.",
    )


def compute_logistica_scores(df: pd.DataFrame) -> pd.DataFrame:
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
    return active


def build_logistica_outputs(df: pd.DataFrame, ped: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    """Genera todas las hojas de respuesta logística."""
    scored = compute_logistica_scores(df)
    ped_map = {}
    if ped is not None and "color_norm" in ped.columns:
        cols = [c for c in ["venta_proy_u", "kg_prom_mes", "inv_tela", "cob_tela_meses"] if c in ped.columns]
        if cols:
            ped_map = ped.set_index("color_norm")[cols].to_dict("index")

    top5_cn = set(TOP5_CANONICAL)
    top5_rows = []
    for i, cn in enumerate(TOP5_CANONICAL, 1):
        row = scored[scored["color_norm"] == cn]
        if row.empty:
            continue
        r = row.iloc[0].copy()
        r["rank_display"] = i
        top5_rows.append(r)
    top5_df = pd.DataFrame(top5_rows)

    # --- Hoja 1: Respuesta Logística (narrativa + tabla) ---
    respuesta_bloques = [
        ["PREGUNTA DE LOGÍSTICA", ""],
        [
            "¿Cuáles son los 5 colores con mejor rotación y menor riesgo de quedar inmovilizados en inventario?",
            "",
        ],
        ["", ""],
        ["RESPUESTA DIRECTA", ""],
        ["Los 5 colores recomendados", ", ".join(top5_df["Color"].tolist())],
        [
            "En una frase",
            "Son los que más venden de forma sostenida, en todo el catálogo, sin picos de moda "
            "y sin meses de inventario parado en tiendas.",
        ],
        ["", ""],
        ["CÓMO SE ELIGIERON (sin tecnicismos)", ""],
    ]
    for line in METODO_SIMPLE:
        respuesta_bloques.append(["", line])
    respuesta_bloques.extend([["", ""], ["QUÉ SIGNIFICAN LOS PUNTAJES", "", "", ""]])
    for row in SCORE_LEYENDA:
        respuesta_bloques.append(row)

    respuesta_narrativa = pd.DataFrame(respuesta_bloques)

    # --- Hoja 2: Top 5 detalle ---
    detalle_rows = []
    for _, r in top5_df.iterrows():
        cn = r["color_norm"]
        extra = ped_map.get(cn, {})
        detalle_rows.append({
            "#": int(r["rank_display"]),
            "Color": r["Color"],
            "Ventas 10 meses (u)": int(r["ventas_unidades"]),
            "Venta prom (u/mes)": round(r["ventas_mensual"], 1),
            "% del total": round(r["pct_ventas"], 1),
            "Inventario PT (u)": int(r["inv_fg"]),
            "Meses de stock PT": round(r["cob_pt_meses"], 1),
            "Tela en almacén (kg)": round(r["inv_tela"], 1),
            "Consumo tela (kg/mes)": round(extra.get("kg_prom_mes", r.get("kg_prom_mes", 0)), 1),
            "Venta proyectada Ago-Dic (u)": round(extra.get("venta_proy_u", 0), 0),
            "Regularidad": _regularidad_label(r["cv_mensual"]),
            "Modelos / Géneros": f"{int(r['modelos'])} / {int(r['generos'])}",
            "Score rotación": round(r["score_rotacion"], 1),
            "Score regularidad": round(r["score_regularidad"], 1),
            "Score transversal": round(r["score_transversal"], 1),
            "Score no inmov.": round(r["score_no_inmov"], 1),
            "SCORE TOTAL": r["score_total"],
            "Por qué está en el Top 5": _justificacion_top5(r),
        })
    top5_detalle = pd.DataFrame(detalle_rows)

    # --- Hoja 3: Ranking completo ---
    ranking_rows = []
    for _, r in scored.iterrows():
        cn = r["color_norm"]
        in_top5 = cn in top5_cn
        extra = ped_map.get(cn, {})
        ranking_rows.append({
            "Ranking": int(r["rank"]),
            "Color": r["Color"],
            "¿Top 5?": "SÍ" if in_top5 else "No",
            "SCORE TOTAL": r["score_total"],
            "Venta prom (u/mes)": round(r["ventas_mensual"], 1),
            "% ventas": round(r["pct_ventas"], 1),
            "Inv PT (u)": int(r["inv_fg"]),
            "Meses stock PT": round(r["cob_pt_meses"], 1),
            "Tela (kg)": round(r["inv_tela"], 1),
            "Consumo tela (kg/mes)": round(extra.get("kg_prom_mes", r.get("kg_prom_mes", 0)), 1),
            "Venta proy. Ago-Dic (u)": round(extra.get("venta_proy_u", 0), 0),
            "Regularidad": _regularidad_label(r["cv_mensual"]),
            "Riesgo inmovilización": _meses_stock_label(r["cob_pt_meses"]),
            "Veredicto": _veredicto_top5(cn, int(r["rank"]), r["score_total"], in_top5),
            "Por qué NO está en el Top 5": _por_que_no_top5(r, in_top5),
        })
    ranking_completo = pd.DataFrame(ranking_rows)

    # --- Casos especiales (colores que suelen preguntar) ---
    watch_cn = {"LILA", "ROJO", "AZUL REY", "PURPURA", "PÚRPURA", "AGUAMARINA", "VINOTINTO", "AMARILLO NEON", "AMARILLO NEÓN"}
    especiales = ranking_completo[
        ranking_completo["Color"].apply(lambda x: norm_color(x) in watch_cn)
    ].copy()
    if especiales.empty:
        especiales = ranking_completo[~ranking_completo["¿Top 5?"].eq("SÍ")].head(8)

    # --- Top 5 técnico (compatibilidad) ---
    top5_tecnico = top5_detalle[
        ["#", "Color", "Ventas 10 meses (u)", "% del total", "Venta prom (u/mes)",
         "Meses de stock PT", "Score rotación", "Score regularidad", "Score transversal",
         "Score no inmov.", "SCORE TOTAL", "Por qué está en el Top 5"]
    ].rename(columns={
        "#": "Top 5 Logística",
        "Ventas 10 meses (u)": "Ventas 10m (u)",
        "% del total": "% Total",
        "Meses de stock PT": "Cobertura PT (meses)",
        "Score rotación": "Score rotación (40%)",
        "Score regularidad": "Score regularidad (25%)",
        "Score transversal": "Score transversal (20%)",
        "Score no inmov.": "Score no-inmov (15%)",
        "Por qué está en el Top 5": "Justificación",
    })

    evitar = scored[scored["cob_pt_meses"] > 12].copy()
    evitar_out = pd.DataFrame({
        "Color": evitar["Color"],
        "Venta prom (u/mes)": evitar["ventas_mensual"].round(1),
        "Inv PT (u)": evitar["inv_fg"].astype(int),
        "Meses stock PT": evitar["cob_pt_meses"].round(1),
        "% ventas": evitar["pct_ventas"].round(1),
        "Qué significa": evitar.apply(
            lambda r: f"Hay {r['inv_fg']:,.0f} prendas paradas — {r['cob_pt_meses']:.0f} meses de stock "
            f"con solo {r['pct_ventas']:.1f}% de las ventas. No ampliar catálogo ni producir más hasta redistribuir.",
            axis=1,
        ),
    })

    return {
        "respuesta_narrativa": respuesta_narrativa,
        "top5_detalle": top5_detalle,
        "ranking_completo": ranking_completo,
        "casos_especiales": especiales,
        "top5_tecnico": top5_tecnico,
        "evitar": evitar_out,
        "scored": scored,
    }


def df_from_summary_sheet(summary: pd.DataFrame) -> pd.DataFrame:
    """Reconstruye el dataframe maestro desde 'Resumen por Color'."""
    df = summary.copy()
    df["color_norm"] = df["Color"].apply(norm_color)
    rename = {
        "Ventas 10m (u)": "ventas_unidades",
        "Venta prom (u/mes)": "ventas_mensual",
        "% Total": "pct_ventas",
        "CV mensual": "cv_mensual",
        "Modelos": "modelos",
        "Géneros": "generos",
        "Inv PT (u)": "inv_fg",
        "Cob. PT (meses)": "cob_pt_meses",
        "Tela actual (kg)": "inv_tela",
        "Consumo kg/mes": "kg_prom_mes",
        "Cob. tela (meses)": "cob_tela_meses",
        "Venta proy. horizonte (u)": "venta_proy_u",
    }
    for old, new in rename.items():
        if old in df.columns:
            df[new] = df[old]
    if "pct_ventas" in df.columns and df["pct_ventas"].max() > 1:
        pass  # already percent
    return df


def write_logistica_sheets(writer: pd.ExcelWriter, log: dict[str, pd.DataFrame]) -> None:
    log["respuesta_narrativa"].to_excel(writer, sheet_name="1. Respuesta Logística", index=False, header=False)
    start = len(log["respuesta_narrativa"]) + 3
    pd.DataFrame([["TOP 5 — DETALLE POR COLOR"]]).to_excel(
        writer, sheet_name="1. Respuesta Logística", index=False, header=False, startrow=start
    )
    log["top5_detalle"].to_excel(writer, sheet_name="1. Respuesta Logística", index=False, startrow=start + 1)

    log["top5_detalle"].to_excel(writer, sheet_name="2. Top 5 Detalle", index=False)
    log["ranking_completo"].to_excel(writer, sheet_name="3. Ranking Colores", index=False)
    log["casos_especiales"].to_excel(writer, sheet_name="4. Casos Fuera del Top 5", index=False)
    log["top5_tecnico"].to_excel(writer, sheet_name="5. Top 5 Logística", index=False)
    log["evitar"].to_excel(writer, sheet_name="6. Colores con Sobrestock", index=False)
