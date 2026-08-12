"""Contexto y generación del dashboard de ranking de colores (sin pedido ni semáforo)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

COLOR_HEX = {
    "NEGRO": "#1C1C1C", "BLANCO": "#FDFDFD", "AZUL MARINO": "#1E3A5F",
    "VERDE MILITAR": "#4E5B3C", "AZUL LAVANDA": "#A9B7E6", "LILA": "#C9A6E4",
    "AZUL REY": "#2B4BD7", "ROJO": "#D63031", "PÚRPURA": "#7D3FB0", "PURPURA": "#7D3FB0",
    "GRIS CLARO": "#CFCFCF", "AGUAMARINA": "#6FD8C8", "VINOTINTO": "#722F37",
    "AMARILLO NEÓN": "#EEF25A", "AMARILLO NEON": "#EEF25A", "ROSADO PASTEL": "#F4B8C8",
}


def _fecha_hoy() -> str:
    h = date.today()
    return f"{h.day} de {MESES[h.month - 1]} de {h.year}"


def _norm(s: object) -> str:
    if pd.isna(s):
        return ""
    t = str(s).strip().upper()
    for a, b in [("Ó", "O"), ("É", "E"), ("Ú", "U"), ("Í", "I"), ("Á", "A")]:
        t = t.replace(a, b)
    return t


def _parse_ranking_workbook(path: Path) -> dict:
    xl = pd.ExcelFile(path)
    resumen = pd.read_excel(xl, "RESUMEN", header=None)
    rank = pd.read_excel(xl, "RANKING (14 COLORES)", header=None)
    just = pd.read_excel(xl, "JUSTIFICACIÓN POR COLOR", header=None)

    pregunta = (
        "¿Cuáles son los 5 colores con mejor rotación y menor riesgo "
        "de quedar inmovilizados en inventario?"
    )
    respuesta_line = str(resumen.iloc[2, 0] or "")
    if "(alterno" in respuesta_line.lower():
        respuesta_line = respuesta_line[: respuesta_line.lower().index("(alterno")].strip()
    respuesta = respuesta_line.replace("1.", "").replace("2.", ",").replace("3.", ",")
    respuesta = respuesta.replace("4.", ",").replace("5.", ",").strip(" ·,")
    parts = []
    for p in respuesta.replace("·", ",").split(","):
        name = p.strip().title()
        if name:
            parts.append(name)
    respuesta = ", ".join(dict.fromkeys(parts))

    metodologia = []
    for i in range(len(resumen)):
        c0 = str(resumen.iloc[i, 0] or "")
        c1 = str(resumen.iloc[i, 1] or "")
        if c0.startswith("Criterio") or c0 == "Score total":
            metodologia.append({"titulo": c0, "texto": c1})

    hdr = 2
    cols = rank.iloc[hdr].tolist()
    df = rank.iloc[hdr + 1 :].copy()
    df.columns = cols
    df = df[df["#"].apply(lambda x: str(x).isdigit())].copy()
    df["#"] = df["#"].astype(int)

    top5 = []
    ranking = []
    for _, r in df.iterrows():
        color = str(r["Color"]).strip().title()
        if _norm(color) == "LECTURA":
            continue
        item = {
            "rank": int(r["#"]),
            "Color": color,
            "ventas_mes": float(r["Venta prom (u/mes) — ROTACIÓN"]),
            "regularidad": str(r["Regularidad — CV"]),
            "modelos": int(r["Modelos donde vende"]),
            "generos": int(r["Géneros"]),
            "cob_pt": float(r["Cob. PT (m)"]),
            "cob_tela": float(r["Cob. tela (m)"]),
            "autonomia": float(r["AUTONOMÍA TOTAL (m) — INMOVILIZACIÓN"]),
            "score": float(r["SCORE TOTAL"]),
            "diagnostico": str(r["Diagnóstico"]),
            "top5": str(r["Diagnóstico"]).upper().startswith("TOP"),
        }
        ranking.append(item)
        if item["top5"]:
            # justification from resumen rows 5-9
            just_row = resumen[(resumen[0].astype(str).str.contains(color.split()[0], case=False, na=False))]
            just_text = str(just_row.iloc[0, 1]) if len(just_row) else item["diagnostico"]
            top5.append({**item, "justificacion": just_text})

    # sort top5 by rank
    top5.sort(key=lambda x: x["rank"])

    alterno = next((r for r in ranking if "alterno" in r["diagnostico"].lower()), None)

    # justificaciones sheet: row 3+ 
    just_rows = []
    for i in range(3, len(just)):
        row = just.iloc[i]
        if pd.isna(row.iloc[0]):
            continue
        color = str(row.iloc[0]).strip().title()
        if not color or color == "Color":
            continue
        chunks = [str(x).strip() for x in row.iloc[1:] if pd.notna(x) and str(x).strip()]
        just_rows.append({"Color": color, "texto": " · ".join(chunks)})
    just_map = {r["Color"]: r["texto"] for r in just_rows}
    for t in top5:
        if t["Color"] in just_map and len(t.get("justificacion", "")) < 20:
            t["justificacion"] = just_map[t["Color"]]

    for r in ranking:
        r["justificacion"] = just_map.get(r["Color"], r["diagnostico"])
        if r.get("top5"):
            r["justificacion"] = "—"

    return {
        "meta": {
            "fecha": _fecha_hoy(),
            "meses": 10,
            "periodo": "oct-25 a jul-26",
            "fuente": path.name,
        },
        "pregunta": pregunta,
        "respuesta": respuesta or ", ".join(t["Color"] for t in top5),
        "metodologia": metodologia,
        "top5": top5,
        "ranking": ranking,
        "alterno": alterno,
    }


def _parse_analisis_workbook(path: Path) -> dict:
    xl = pd.ExcelFile(path)
    resumen = pd.read_excel(xl, "0. Resumen Ejecutivo")
    top5_df = pd.read_excel(xl, "2. Top 5 Detalle")
    rank_df = pd.read_excel(xl, "3. Ranking Colores")

    pregunta_row = resumen[resumen["Concepto"].astype(str).str.startswith("Pregunta", na=False)]
    resp_row = resumen[resumen["Concepto"].astype(str).str.startswith("Respuesta", na=False)]
    pregunta = str(pregunta_row.iloc[0]["Valor"]) if len(pregunta_row) else ""
    respuesta = str(resp_row.iloc[0]["Valor"]) if len(resp_row) else ""

    top5 = []
    for _, r in top5_df.iterrows():
        top5.append({
            "rank": int(r["#"]),
            "Color": str(r["Color"]),
            "ventas_mes": float(r["Venta prom (u/mes)"]),
            "regularidad": str(r.get("Regularidad", "")),
            "modelos": str(r.get("Modelos / Géneros", "")).split("/")[0].strip() if "Modelos" in r else "",
            "generos": "",
            "cob_pt": float(r["Meses de stock PT"]),
            "cob_tela": 0.0,
            "autonomia": float(r["Meses de stock PT"]),
            "score": float(r["SCORE TOTAL"]),
            "diagnostico": "TOP 5",
            "top5": True,
            "justificacion": str(r["Por qué está en el Top 5"]),
            "pct": float(r.get("% del total", 0)),
            "inv_pt": int(r.get("Inventario PT (u)", 0)),
        })

    ranking = []
    for _, r in rank_df.iterrows():
        ranking.append({
            "rank": int(r["Ranking"]),
            "Color": str(r["Color"]),
            "ventas_mes": float(r["Venta prom (u/mes)"]),
            "regularidad": str(r.get("Regularidad", "")),
            "modelos": "",
            "generos": "",
            "cob_pt": float(r["Meses stock PT"]),
            "cob_tela": 0.0,
            "autonomia": float(r["Meses stock PT"]),
            "score": float(r["SCORE TOTAL"]),
            "diagnostico": str(r["Veredicto"]),
            "top5": str(r.get("¿Top 5?", "")).upper().startswith("S"),
            "justificacion": str(r.get("Por qué NO está en el Top 5", "—")),
            "pct": float(r.get("% ventas", 0)),
            "inv_pt": int(r.get("Inv PT (u)", 0)),
        })
        if ranking[-1]["top5"]:
            ranking[-1]["justificacion"] = next(
                (t["justificacion"] for t in top5 if t["Color"] == ranking[-1]["Color"]), "—"
            )

    casos = pd.read_excel(xl, "4. Casos Fuera del Top 5") if "4. Casos Fuera del Top 5" in xl.sheet_names else None
    alterno = None
    if casos is not None:
        ar = casos[casos["Color"].str.contains("Azul Rey", case=False, na=False)]
        if len(ar):
            r = ar.iloc[0]
            alterno = {"Color": r["Color"], "ventas_mes": float(r["Venta prom (u/mes)"]), "diagnostico": str(r["Veredicto"])}

    metodologia = [
        {"titulo": "Rotación (40%)", "texto": "Cuánto vende el color cada mes vs. el líder del catálogo."},
        {"titulo": "Regularidad (25%)", "texto": "Si vende parejo todo el año o a golpes (moda/lanzamientos)."},
        {"titulo": "Presencia en catálogo (20%)", "texto": "Cuántos modelos y géneros lo incluyen."},
        {"titulo": "No inmovilizar (15%)", "texto": "Meses de stock parado — penaliza si hay mucho inventario quieto."},
    ]

    return {
        "meta": {"fecha": _fecha_hoy(), "meses": 10, "periodo": "oct-25 a jul-26", "fuente": path.name},
        "pregunta": pregunta,
        "respuesta": respuesta,
        "metodologia": metodologia,
        "top5": top5,
        "ranking": ranking,
        "alterno": alterno,
    }


def build_ranking_dashboard_context(path: Path | str) -> dict:
    path = Path(path)
    xl = pd.ExcelFile(path)
    if "RANKING (14 COLORES)" in xl.sheet_names:
        return _parse_ranking_workbook(path)
    return _parse_analisis_workbook(path)
