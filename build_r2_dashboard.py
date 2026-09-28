#!/usr/bin/env python3
"""Generate R2 DASHBOARD.html from ventas + inventario Excel files."""
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
VENT_PATH = ROOT / "data/R2_VENTAS_ARREGLADO.xlsx"
INV_PATH = ROOT / "data/R2_INVENTARIO_completo.xlsx"
TEMPLATE = ROOT / "SHORT PLAYA SUBL.html"
OUT = ROOT / "R2 DASHBOARD.html"

MES_NUM = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
    "ENERO": 1,
    "FEBRERO": 2,
    "MARZO": 3,
    "ABRIL": 4,
    "MAYO": 5,
    "JUNIO": 6,
    "JULIO": 7,
    "AGOSTO": 8,
    "SEPTIEMBRE": 9,
    "OCTUBRE": 10,
    "NOVIEMBRE": 11,
    "DICIEMBRE": 12,
}
MES_SHORT = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}

STORE_MAP = {
    "Cerro Verde": "CERRO VERDE",
    "La Grieta": "GRIETA",
    "LA VELA": "VELA",
    "La Vela": "VELA",
    "Pedidos": "PEDIDOS",
    "Sambil Chacao": "CHACAO",
    "Sambil Valencia": "SAMBIL",
    "Tolon": "TOLON",
    "TOLON": "TOLON",
    "CERRO VERDE": "CERRO VERDE",
    "CHACAO": "CHACAO",
    "GRIETA": "GRIETA",
    "SAMBIL": "SAMBIL",
    "TH": "TALLER",
    "TALLER": "TALLER",
    "VELA": "VELA",
    "WEB": "WEB",
}


def norm_modelo(m):
    if not isinstance(m, str):
        return m
    m = re.sub(r"\s+", " ", m.strip())
    if "SPORT" in m.upper():
        return 'R2 SPORT 5"'
    if "RUNNING" in m.upper():
        return 'R2 RUNNING 3,5"'
    return m


def mes_key(mes, anio):
    m = str(mes).strip()
    mk = MES_NUM.get(m) or MES_NUM.get(m.lower())
    if not mk:
        mk = 1
    name = next(k for k, v in MES_NUM.items() if v == mk and k.islower())
    return f"{name}-{int(anio)}"


def round1(x):
    return round(x + 1e-9, 1)


def build_data():
    vent = pd.read_excel(VENT_PATH)
    inv = pd.read_excel(INV_PATH)

    raw_rows = []
    for _, r in vent.iterrows():
        qty = int(r["Cant. ordenada"])
        if qty == 0:
            continue
        store = STORE_MAP.get(
            str(r["tienda / ubicación"]).strip(),
            str(r["tienda / ubicación"]).strip().upper(),
        )
        modelo = norm_modelo(r["modelo"])
        color = str(r["COLOR"]).strip()
        talla = str(r["TALLA"]).strip()
        genero = "CAB"
        if pd.notna(r.get("GENERO")) and str(r["GENERO"]).strip():
            genero = str(r["GENERO"]).strip().upper()
        mes = mes_key(r["Mes"], r["Año"])
        raw_rows.append(
            {
                "tienda": store,
                "genero": genero,
                "color": color,
                "talla": talla,
                "mes": mes,
                "modelo": modelo,
                "activo": True,
                "v": qty,
            }
        )

    stock = defaultdict(int)
    stock_by_store = defaultdict(lambda: defaultdict(int))
    for _, r in inv.iterrows():
        q = int(r["Cantidad en inventario"])
        if q <= 0:
            continue
        store = STORE_MAP.get(str(r["Ubicación"]).strip(), str(r["Ubicación"]).strip().upper())
        modelo = norm_modelo(r["MODELO"])
        color = str(r["COLOR"]).strip()
        talla = str(r["TALLA"]).strip()
        genero = "CAB"
        if pd.notna(r.get("GENERO")) and str(r["GENERO"]).strip():
            genero = str(r["GENERO"]).strip().upper()
        key = f"{modelo}/{genero}/{color}/{talla}"
        stock[key] += q
        stock_by_store[store][key] += q

    stock = dict(stock)
    stock_by_store = {s: dict(v) for s, v in stock_by_store.items()}

    meses_order = sorted(
        {r["mes"] for r in raw_rows},
        key=lambda k: (int(k.split("-")[1]), MES_NUM.get(k.split("-")[0], 99)),
    )
    meses_und = {m: sum(r["v"] for r in raw_rows if r["mes"] == m) for m in meses_order}

    modelos = sorted({r["modelo"] for r in raw_rows} | {norm_modelo(x) for x in inv["MODELO"].unique()})
    tiendas = sorted({r["tienda"] for r in raw_rows} | set(stock_by_store.keys()))
    generos = sorted({r["genero"] for r in raw_rows})
    colores = sorted({r["color"] for r in raw_rows} | set(inv["COLOR"].astype(str)))

    es_parcial = bool(meses_order and meses_order[-1].startswith("septiembre-2026"))
    vel_meses = meses_order[:-1] if es_parcial and len(meses_order) > 1 else meses_order[:]
    if len(vel_meses) > 6:
        vel_meses = vel_meses[-6:]
    vel_count = max(len(vel_meses), 1)
    hs = 1.25
    lead = 3

    def stk_for(modelo, genero, color, talla=None):
        prefix = f"{modelo}/{genero}/{color}/"
        total = 0
        for k, v in stock.items():
            if not k.startswith(prefix):
                continue
            if talla and not k.endswith("/" + talla):
                continue
            total += v
        return total

    def stk_taller(modelo, genero, color, talla):
        key = f"{modelo}/{genero}/{color}/{talla}"
        return stock_by_store.get("TALLER", {}).get(key, 0)

    production_plan = []
    colores_activos = {m: sorted({r["color"] for r in raw_rows if r["modelo"] == m}) for m in modelos}

    for modelo in modelos:
        active_colors = set(colores_activos.get(modelo, []))
        for genero in generos:
            for color in sorted(active_colors):
                talla_rows = [
                    r
                    for r in raw_rows
                    if r["modelo"] == modelo
                    and r["genero"] == genero
                    and r["color"] == color
                    and r["mes"] in vel_meses
                ]
                if not talla_rows and stk_for(modelo, genero, color) <= 0:
                    continue
                tallas = sorted(
                    {r["talla"] for r in talla_rows}
                    | {k.split("/")[3] for k in stock if k.startswith(f"{modelo}/{genero}/{color}/")}
                )
                talla_plan = []
                color_v_base = 0.0
                color_v = 0.0
                color_stk = 0
                color_stk_t = 0
                color_prod = 0
                for talla in tallas:
                    by_m = defaultdict(int)
                    for r in talla_rows:
                        if r["talla"] == talla:
                            by_m[r["mes"]] += r["v"]
                    v_base = sum(by_m.values()) / vel_count if vel_count else 0
                    v_mes = round1(v_base * hs)
                    stk = stk_for(modelo, genero, color, talla)
                    stk_t = stk_taller(modelo, genero, color, talla)
                    if v_mes > 0:
                        cob = round(stk / v_mes, 1)
                    elif stk > 0:
                        cob = 999
                    else:
                        cob = 999
                    produce = 0
                    urgent = False
                    if v_mes > 0 and cob < lead:
                        produce = max(0, int(math.ceil(lead * v_mes - stk)))
                        urgent = cob < 3
                    talla_plan.append(
                        {
                            "talla": talla,
                            "v_mes_base": round1(v_base),
                            "v_mes": v_mes,
                            "stk": stk,
                            "stk_taller": stk_t,
                            "cob": cob,
                            "produce": produce,
                            "urgente": urgent,
                        }
                    )
                    color_v_base += v_base
                    color_v += v_mes
                    color_stk += stk
                    color_stk_t += stk_t
                    color_prod += produce
                if not talla_plan:
                    continue
                color_v_base = round1(color_v_base)
                color_v = round1(color_v)
                color_cob = round(color_stk / color_v, 1) if color_v > 0 else 999
                production_plan.append(
                    {
                        "modelo": modelo,
                        "genero": genero,
                        "color": color,
                        "v_mes_base": color_v_base,
                        "v_mes": color_v,
                        "stk": color_stk,
                        "stk_taller": color_stk_t,
                        "cob": color_cob,
                        "produce": color_prod,
                        "tallas": talla_plan,
                    }
                )

    summary_produccion = {}
    for modelo in modelos:
        rows = [p for p in production_plan if p["modelo"] == modelo]
        if not rows:
            continue
        v_base = sum(p["v_mes_base"] for p in rows)
        v_mes = sum(p["v_mes"] for p in rows)
        stk = sum(p["stk"] for p in rows)
        prod = sum(p["produce"] for p in rows)
        cob = round(stk / v_mes, 1) if v_mes > 0 else 999
        summary_produccion[modelo] = {
            "v_mes_base": round1(v_base),
            "v_mes": round1(v_mes),
            "stk": stk,
            "cob": cob,
            "produce": prod,
        }

    summary_genero = {}
    for g in generos:
        rows = [p for p in production_plan if p["genero"] == g]
        if rows:
            v_mes = sum(p["v_mes"] for p in rows)
            summary_genero[g] = {
                "v_mes": round1(v_mes),
                "stk": sum(p["stk"] for p in rows),
                "produce": sum(p["produce"] for p in rows),
            }

    stock_by_modelo = {}
    for k, q in stock.items():
        mod = k.split("/")[0]
        stock_by_modelo[mod] = stock_by_modelo.get(mod, 0) + q

    store_order_pref = [
        "CERRO VERDE",
        "CHACAO",
        "GRIETA",
        "SAMBIL",
        "TOLON",
        "VELA",
        "BARQUISIMETO",
        "WEB",
        "PEDIDOS",
        "TALLER",
    ]
    stores_with_stock = list(stock_by_store.keys())
    stores_order = [s for s in store_order_pref if s in stores_with_stock] + sorted(
        set(stores_with_stock) - set(store_order_pref)
    )

    all_stores = sorted(
        set(tiendas) | set(stores_with_stock) | {"BARQUISIMETO", "VELA", "GRIETA", "CERRO VERDE", "CHACAO", "SAMBIL", "TOLON"}
    )
    decision_exclude = ["CORPORATIVO", "PEDIDOS", "VELA", "WEB"]
    decision_stores = [s for s in all_stores if s not in decision_exclude and s not in ("BARQUISIMETO", "TALLER")]

    if meses_order:
        p0 = meses_order[0].split("-")
        p1 = meses_order[-1].split("-")
        periodo = f"{MES_SHORT[MES_NUM[p0[0]]]} {p0[1][-2:]} — {MES_SHORT[MES_NUM[p1[0]]]} {p1[1][-2:]}"
    else:
        periodo = "—"

    vel_label = " · ".join(
        MES_SHORT[MES_NUM[m.split("-")[0]]] + " " + m.split("-")[1][-2:] for m in vel_meses
    )

    return {
        "raw_rows": raw_rows,
        "stock": stock,
        "stock_by_store": stock_by_store,
        "stock_by_modelo": stock_by_modelo,
        "meses_order": meses_order,
        "meses_und": meses_und,
        "filtros": {"tiendas": tiendas, "generos": generos, "colores": colores, "modelos": modelos},
        "es_parcial": es_parcial,
        "stock_total": sum(stock.values()),
        "stock_taller": sum(stock_by_store.get("TALLER", {}).values()),
        "total": sum(r["v"] for r in raw_rows),
        "all_stores": all_stores,
        "stores_order": stores_order,
        "production_plan": production_plan,
        "summary_produccion": summary_produccion,
        "summary_genero": summary_genero,
        "new_stores": ["VELA", "BARQUISIMETO"],
        "new_store_caps": {
            "VELA": {"base": "GRIETA", "mult": 1.5, "label": "1.5× GRIETA"},
            "BARQUISIMETO": {"base": "GRIETA", "mult": 1, "label": "1× GRIETA"},
        },
        "decision_exclude_stores": decision_exclude,
        "decision_stores": decision_stores,
        "lead_months": lead,
        "high_season_factor": hs,
        "velocity_months_count": vel_count,
        "velocity_months": vel_meses,
        "velocity_months_label": vel_label,
        "periodo": periodo,
        "colores_activos": colores_activos,
        "colores_descontinuados": [],
    }


def customize_html(head: str, tail: str, data: dict) -> str:
    periodo = data["periodo"]
    head = head.replace("<title>Dashboard Short Playa</title>", "<title>Dashboard R2 Collection</title>")
    head = head.replace(
        "<h1>Short Playa · <em id=\"titleModelo\">Todas</em></h1>",
        "<h1>R2 Collection · <em id=\"titleModelo\">Todas</em></h1>",
    )
    head = head.replace(
        "<p>Dashboard de Ventas · Oct 25 — Ago 26</p>",
        f"<p>Dashboard de Ventas · {periodo}</p>",
    )
    mbar = (
        '<div class="mbar"><span class="mbar-lbl">🏃 Línea:</span>'
        '<button class="mbtn active" data-m="" onclick="setModelo(\'\')">🏃 Todas <span class="mcnt" id="mcnt_all">0</span></button>'
        '<button class="mbtn" data-m="R2 SPORT 5\\"" onclick="setModelo(\'R2 SPORT 5\\"\')">⚡ Sport 5\\" <span class="mcnt" id="mcnt_SPORT5">0</span></button>'
        '<button class="mbtn" data-m="R2 RUNNING 3,5\\"" onclick="setModelo(\'R2 RUNNING 3,5\\"\')">🏃 Running 3,5\\" <span class="mcnt" id="mcnt_RUNNING35">0</span></button></div>\n<div class="fbar">'
    )
    head = re.sub(r"<div class=\"mbar\">.*?</div>\n<div class=\"fbar\">", mbar, head, count=1, flags=re.DOTALL)
    head = head.replace(
        "Short Playa · Dashboard de Ventas · Oct 25 — Ago 26",
        f"R2 Collection · Dashboard de Ventas · {periodo}",
    )

    replacements = [
        (
            "var MICO={'SHORT PLAYA UNICOLOR':'🩳','SHORT PLAYA SUBLIMADO':'🌴'};",
            "var MICO={'R2 SPORT 5\"':'⚡','R2 RUNNING 3,5\"':'🏃'};",
        ),
        (
            "var MODELO_ID={'SHORT PLAYA UNICOLOR':'UNICOLOR','SHORT PLAYA SUBLIMADO':'SUBLIMADO'};",
            "var MODELO_ID={'R2 SPORT 5\"':'SPORT5','R2 RUNNING 3,5\"':'RUNNING35'};",
        ),
        (
            "function modeloLabel(m){return{'SHORT PLAYA UNICOLOR':'Unicolor','SHORT PLAYA SUBLIMADO':'Sublimado'}[m]||(m||'').replace('SHORT PLAYA ','');}",
            "function modeloLabel(m){return{'R2 SPORT 5\"':'Sport 5\"','R2 RUNNING 3,5\"':'Running 3,5\"'}[m]||m;}",
        ),
        (
            "  var sn={'SHORT PLAYA UNICOLOR':'Unicolor','SHORT PLAYA SUBLIMADO':'Sublimado'};",
            "  var sn={'R2 SPORT 5\"':'Sport 5\"','R2 RUNNING 3,5\"':'Running 3,5\"'};",
        ),
        ("a.download='ShortPlaya.csv';", "a.download='R2_Collection.csv';"),
        (
            "Unicolor activo: Verde Pino, Azul Pizarra, Azul Verdoso, Marron, Cereza. Sublimado: Playuela, Sal, Tucupido, Sombrero. Descontinuados excluidos de producción.",
            "Línea R2 · colores del inventario/ventas cargados. BARQUISIMETO 1× Grieta · VELA 1.5× Grieta · rotación con factor temporada alta.",
        ),
        (
            "if(DATA.es_parcial)alerts.push({type:'info',text:'📅 Mayo 2026 con datos parciales'});",
            "if(DATA.es_parcial)alerts.push({type:'info',text:'📅 Último mes con datos parciales — excluido de rotación base'});",
        ),
    ]
    for old, new in replacements:
        tail = tail.replace(old, new)
    return head, tail


def main():
    data = build_data()
    content = TEMPLATE.read_text(encoding="utf-8")
    m = re.search(r"(.*?<script>\n)var DATA=\{.*?\};(\n.*?</html>)", content, re.DOTALL)
    if not m:
        raise SystemExit("template parse failed")
    head, tail = customize_html(m.group(1), m.group(2), data)
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(head + "var DATA=" + data_json + ";" + tail, encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
    print("Modelos:", data["filtros"]["modelos"])
    print("Ventas netas:", data["total"], "Stock:", data["stock_total"])


if __name__ == "__main__":
    main()
