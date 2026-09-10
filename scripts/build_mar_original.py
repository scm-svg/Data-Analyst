#!/usr/bin/env python3
"""Build MAR ORIGINAL dashboard + proyecciones Excel from sales/inventory files."""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = Path("/home/ubuntu/.cursor/projects/workspace/uploads")
TEMPLATE = UPLOADS / "DASHBOARD_MAR_ORIGINAL_7340.html"
VENTAS_XLSX = UPLOADS / "VENTAS_ARREGLADAS_MAR_ORIGINAL_ACTUALIZADAS_5e6d.xlsx"
INV_XLSX = UPLOADS / "MAR_ORIGINAL_INVENTARIO_ARREGLADO_b31f.xlsx"
OUT_HTML = ROOT / "DASHBOARD_MAR_ORIGINAL.html"
OUT_XLSX = ROOT / "MAR_ORIGINAL_PROYECCIONES.xlsx"

MESES_NUM = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
    "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
MESES_SLUG = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}
MESES_SHORT = {
    "enero": "Ene", "febrero": "Feb", "marzo": "Mar", "abril": "Abr", "mayo": "May", "junio": "Jun",
    "julio": "Jul", "agosto": "Ago", "septiembre": "Sep", "octubre": "Oct", "noviembre": "Nov", "diciembre": "Dic",
}

STORE_MAP = {
    "SAMBIL VALENCIA": "SAMBIL", "Sambil Valencia": "SAMBIL",
    "SAMBIL CHACAO": "CHACAO", "Sambil Chacao": "CHACAO",
    "GRIETA": "GRIE", "La Grieta": "GRIE",
    "GRAND PLAZ": "GRAND", "Grandplaz": "GRAND", "GRANDPLAZ": "GRAND",
    "LA VELA": "VELA", "La Vela": "VELA",
    "TOLON": "TOLON", "Tolon": "TOLON",
    "CERRO VERDE": "CERRO VERDE", "Cerro Verde": "CERRO VERDE",
    "PEDIDOS": "PEDIDOS", "Pedidos": "PEDIDOS",
    "WEB": "WEB", "CORPORATIVO": "CORPORATIVO",
}
INV_STORE_MAP = {
    "GRIETA": "GRIE", "GRANDPLAZ": "GRAND", "CHACAO": "CHACAO", "SAMBIL": "SAMBIL",
    "TOLON": "TOLON", "VELA": "VELA", "CERRO VERDE": "CERRO VERDE", "TALLER": "TALLER",
}
GEN_MAP = {
    "Caballero": "CAB", "CAB": "CAB", "caballero": "CAB",
    "Dama": "DAMA", "DAMA": "DAMA", "dama": "DAMA",
    "Kids": "KIDS", "KIDS": "KIDS", "kids": "KIDS",
}

COLORES_DISP = {
    "CAB": ["Negro", "Azul Marino", "Blanco", "Verde Militar", "Azul Lavanda", "Azul Rey",
            "Aguamarina", "Rojo", "Vinotinto", "Gris Claro", "Amarillo Neón"],
    "DAMA": ["Negro", "Azul Marino", "Blanco", "Verde Militar", "Azul Lavanda", "Aguamarina",
             "Rojo", "Vinotinto", "Púrpura", "Lila", "Rosado Pastel", "Amarillo Neón"],
    "KIDS": ["Negro", "Azul Marino", "Blanco", "Verde Militar", "Azul Lavanda", "Azul Rey",
             "Aguamarina", "Rojo", "Lila", "Rosado Pastel", "Púrpura", "Amarillo Neón"],
}

RETAIL_STORES = ["SAMBIL", "GRIE", "CERRO VERDE", "CHACAO", "GRAND", "TOLON", "VELA"]
PROJECTED_STORES = ["BARQUISIMETO", "WEB"]

HIGH_SEASON_FACTOR = 1.35
TOLON_BOOST = 1.45
WEB_STRONGEST_RATIO = 0.5
COVERAGE_MONTHS = 3
SAFETY_BUFFER = 1.15
VELOCITY_PERIODS = ["mayo-2026", "junio-2026", "julio-2026"]


def norm_color(c: str) -> str:
    if not isinstance(c, str) or not c.strip():
        return "Sin color"
    c = c.strip()
    repl = {
        "amarillo neon": "Amarillo Neón", "amarillo neón": "Amarillo Neón",
        "verde militar": "Verde Militar", "verde miliar": "Verde Militar",
        "azul marino": "Azul Marino", "azul lavanda": "Azul Lavanda", "azul rey": "Azul Rey",
        "gris claro": "Gris Claro", "rosado pastel": "Rosado Pastel",
        "azul cielo": "Azul Cielo", "azul turquesa": "Azul Turquesa",
        "amarillo pastel": "Amarillo Pastel", "coral neón": "Coral Neón",
        "rosado neón": "Rosado Neón", "morado": "Morado", "purpura": "Púrpura", "púrpura": "Púrpura",
        "fucsia": "Fucsia", "vinotinto": "Vinotinto", "aguamarina": "Aguamarina",
        "negro": "Negro", "blanco": "Blanco", "rojo": "Rojo", "lila": "Lila",
    }
    key = c.lower()
    if key in repl:
        return repl[key]
    return c[0].upper() + c[1:] if len(c) > 1 else c.upper()


def norm_store(raw: str) -> str:
    raw = str(raw).strip()
    return STORE_MAP.get(raw, raw.upper())


def norm_inv_store(raw: str) -> str:
    raw = str(raw).strip()
    return INV_STORE_MAP.get(raw, raw.upper())


def norm_genero(raw: str) -> str:
    return GEN_MAP.get(str(raw).strip(), str(raw).strip().upper())


def period_key(year: int, mes: str) -> tuple[int, int, str]:
    mn = MESES_NUM[mes]
    slug = f"{MESES_SLUG[mn]}-{year}"
    return year, mn, slug


def load_sales() -> pd.DataFrame:
    df = pd.read_excel(VENTAS_XLSX)
    df["tienda"] = df["tienda / ubicación"].map(norm_store)
    df["genero"] = df["GENERO"].map(norm_genero)
    df["color"] = df["COLOR"].map(norm_color)
    df["talla"] = df["TALLA"].astype(str).str.strip()
    df["v"] = df["Cant. ordenada"].astype(float)
    keys = df.apply(lambda r: period_key(int(r["Año"]), r["Mes"]), axis=1)
    df["year"] = keys.map(lambda x: x[0])
    df["mes_num"] = keys.map(lambda x: x[1])
    df["mes"] = keys.map(lambda x: x[2])
    return df


def load_inventory() -> pd.DataFrame:
    df = pd.read_excel(INV_XLSX)
    df["tienda"] = df["Ubicación"].map(norm_inv_store)
    df["genero"] = df["GENERO"].map(norm_genero)
    df["color"] = df["COLOR"].map(norm_color)
    df["talla"] = df["TALLA"].astype(str).str.strip()
    df["v"] = df["Cantidad en inventario"].astype(float)
    return df


def store_weights(by_store: dict[str, float]) -> dict[str, float]:
    grie = by_store.get("GRIE", 0)
    chacao = by_store.get("CHACAO", 0)
    tolon = by_store.get("TOLON", 0)
    strongest = max([by_store.get(s, 0) for s in RETAIL_STORES] + [1])

    weights = {}
    for s in RETAIL_STORES:
        base = by_store.get(s, 0)
        if s == "TOLON":
            base *= TOLON_BOOST
        weights[s] = base
    weights["VELA"] = grie
    weights["BARQUISIMETO"] = (grie + chacao + tolon) / 3
    weights["WEB"] = strongest * WEB_STRONGEST_RATIO

    total = sum(weights.values()) or 1
    return {k: v / total for k, v in weights.items()}


def build_data(sales: pd.DataFrame, inv: pd.DataFrame) -> dict:
    retail_sales = sales[sales["tienda"].isin(RETAIL_STORES + ["WEB", "PEDIDOS", "CORPORATIVO", "VELA", "TOLON"])].copy()

    meses_sorted = sorted(retail_sales[["year", "mes_num", "mes"]].drop_duplicates().values.tolist())
    meses_order = [m[2] for m in meses_sorted]
    meses_labels = []
    for _, mn, slug in meses_sorted:
        parts = slug.split("-")
        meses_labels.append(f"{MESES_SHORT[parts[0]].title()} {parts[1][-2:]}")

    meses_und = retail_sales.groupby("mes")["v"].sum().to_dict()
    total = int(retail_sales["v"].sum())

    # var_pct: last full month vs previous
    monthly = retail_sales.groupby("mes")["v"].sum()
    ordered = [m for _, _, m in meses_sorted]
    var_pct = 0.0
    if len(ordered) >= 2:
        prev, last = monthly.get(ordered[-2], 0), monthly.get(ordered[-1], 0)
        if prev > 0:
            var_pct = round((last - prev) / prev * 100, 1)

    raw_rows = []
    for _, r in retail_sales.iterrows():
        raw_rows.append({
            "tienda": r["tienda"],
            "genero": r["genero"],
            "color": r["color"],
            "talla": r["talla"],
            "mes": r["mes"],
            "v": int(r["v"]),
        })

    stock = defaultdict(float)
    stock_by_store = defaultdict(lambda: defaultdict(float))
    for _, r in inv.iterrows():
        key = f"{r['color']}/{r['talla']}/{r['genero']}"
        stock[key] += r["v"]
        stock_by_store[r["tienda"]][key] += r["v"]

    stock_dict = {k: int(round(v)) for k, v in stock.items()}
    sbs = {store: {k: int(round(v)) for k, v in items.items()} for store, items in stock_by_store.items()}

    store_totals = {s: sum(items.values()) for s, items in sbs.items()}
    stores_order = sorted(store_totals.keys(), key=lambda s: (-store_totals[s], s))
    if "TALLER" in stores_order:
        stores_order = [s for s in stores_order if s != "TALLER"] + ["TALLER"]

    tiendas_list = ["CERRO VERDE", "CHACAO", "GRAND", "GRIE", "SAMBIL", "TOLON", "VELA", "WEB"]
    colores = sorted({r["color"] for r in raw_rows})
    generos = ["CAB", "DAMA", "KIDS"]

    line_order = {}
    for g in generos:
        vel_base = (
            retail_sales[(retail_sales["genero"] == g) & (retail_sales["mes"].isin(VELOCITY_PERIODS))]["v"].sum()
            / max(len(VELOCITY_PERIODS), 1)
        )
        vel_adj = vel_base * HIGH_SEASON_FACTOR
        line_order[g] = {"m1": int(round(vel_adj)), "m2": int(round(vel_adj * 1.08))}

    production_plan, summary_genero = build_production_plan(retail_sales, inv)

    return {
        "nombre": "MAR ORIGINAL",
        "periodo": f"{meses_labels[0]} — {meses_labels[-1]}",
        "total": total,
        "var_pct": var_pct,
        "es_parcial": False,
        "n_sem": len(meses_order),
        "meses_order": meses_order,
        "meses_labels": meses_labels,
        "meses_und": {k: int(v) for k, v in meses_und.items()},
        "lineas": generos,
        "tiendas_list": tiendas_list,
        "filtros": {
            "tiendas": tiendas_list + ["PEDIDOS", "CORPORATIVO"],
            "generos": generos,
            "colores": colores,
            "meses": meses_order,
        },
        "raw_rows": raw_rows,
        "stock": stock_dict,
        "stock_total": int(sum(stock_dict.values())),
        "stock_by_store": sbs,
        "stores_order": stores_order,
        "stock_taller": int(sum(sbs.get("TALLER", {}).values())),
        "line_order": line_order,
        "method": "velocity_high_season",
        "high_season_factor": HIGH_SEASON_FACTOR,
        "tolon_boost": TOLON_BOOST,
        "velocity_months": VELOCITY_PERIODS,
        "velocity_months_label": "May–Jul 26",
        "velocity_months_count": len(VELOCITY_PERIODS),
        "coverage_months": COVERAGE_MONTHS,
        "safety_buffer": SAFETY_BUFFER,
        "new_stores": ["VELA", "BARQUISIMETO"],
        "production_plan": production_plan,
        "summary_genero": summary_genero,
    }


def build_production_plan(sales: pd.DataFrame, inv: pd.DataFrame) -> tuple[list, dict]:
    vel_sales = sales[sales["mes"].isin(VELOCITY_PERIODS)]
    plan = []
    summary = {}

    for genero in ["CAB", "DAMA", "KIDS"]:
        g_vel = vel_sales[vel_sales["genero"] == genero]
        by_store = g_vel.groupby("tienda")["v"].sum().to_dict()
        shares = store_weights(by_store)

        g_stk = 0
        g_prod = 0
        g_vel_base = 0
        g_vel_adj = 0

        colors = sorted(g_vel.groupby("color")["v"].sum().sort_values(ascending=False).index.tolist())
        for color in colors:
            c_vel = g_vel[g_vel["color"] == color]
            v_base = c_vel["v"].sum() / max(len(VELOCITY_PERIODS), 1)
            v_adj = v_base * HIGH_SEASON_FACTOR
            stk_rows = inv[(inv["genero"] == genero) & (inv["color"] == color)]
            stk = int(stk_rows["v"].sum())
            stk_taller = int(stk_rows[stk_rows["tienda"] == "TALLER"]["v"].sum())
            cob = round(stk / v_adj, 1) if v_adj > 0 else 99.0

            tallas = []
            c_prod = 0
            for talla, tdf in c_vel.groupby("talla"):
                tv_base = tdf["v"].sum() / max(len(VELOCITY_PERIODS), 1)
                tv_adj = tv_base * HIGH_SEASON_FACTOR
                t_stk = int(inv[(inv["genero"] == genero) & (inv["color"] == color) & (inv["talla"] == talla)]["v"].sum())
                t_stk_taller = int(
                    inv[(inv["genero"] == genero) & (inv["color"] == color) & (inv["talla"] == talla) & (inv["tienda"] == "TALLER")]["v"].sum()
                )
                t_cob = round(t_stk / tv_adj, 1) if tv_adj > 0 else 99.0
                need = max(0.0, tv_adj * COVERAGE_MONTHS - t_stk)
                if t_cob < COVERAGE_MONTHS:
                    produce = int(math.ceil(need * SAFETY_BUFFER))
                else:
                    produce = 0
                c_prod += produce
                tallas.append({
                    "talla": str(talla),
                    "v_mes_base": round(tv_base, 1),
                    "v_mes": round(tv_adj, 1),
                    "stk": t_stk,
                    "stk_taller": t_stk_taller,
                    "cob": t_cob,
                    "produce": produce,
                    "urgente": bool(t_cob < 3),
                })

            if cob < COVERAGE_MONTHS:
                color_produce = int(math.ceil(max(0.0, v_adj * COVERAGE_MONTHS - stk) * SAFETY_BUFFER))
            else:
                color_produce = 0
            color_produce = max(color_produce, c_prod)

            store_split = {s: int(round(color_produce * shares.get(s, 0))) for s in list(RETAIL_STORES) + PROJECTED_STORES}
            diff = color_produce - sum(store_split.values())
            if diff and store_split:
                top = max(store_split, key=store_split.get)
                store_split[top] += diff

            plan.append({
                "genero": genero,
                "color": color,
                "v_mes_base": round(v_base, 1),
                "v_mes": round(v_adj, 1),
                "stk": stk,
                "stk_taller": stk_taller,
                "cob": cob,
                "produce": color_produce,
                "tallas": sorted(tallas, key=lambda x: x["produce"], reverse=True),
                "store_split": store_split,
            })

            g_stk += stk
            g_prod += color_produce
            g_vel_base += v_base
            g_vel_adj += v_adj

        summary[genero] = {
            "v_mes_base": round(g_vel_base, 1),
            "v_mes": round(g_vel_adj, 1),
            "stk": g_stk,
            "produce": g_prod,
            "cob": round(g_stk / g_vel_adj, 1) if g_vel_adj > 0 else 99.0,
        }

    return plan, summary


def export_excel(data: dict, path: Path) -> None:
    plan = data["production_plan"]
    summary = data["summary_genero"]

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#5b6af7", "font_color": "white", "border": 1})
        num_fmt = workbook.add_format({"num_format": "#,##0", "border": 1})
        dec_fmt = workbook.add_format({"num_format": "0.0", "border": 1})
        txt_fmt = workbook.add_format({"border": 1})
        title_fmt = workbook.add_format({"bold": True, "font_size": 14, "font_color": "#5b6af7"})

        # Resumen
        res_rows = [
            ["MAR ORIGINAL — Proyección de Producción"],
            [f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
            [""],
            ["Parámetro", "Valor"],
            ["Temporada alta (factor)", data["high_season_factor"]],
            ["Boost Tolón", data["tolon_boost"]],
            ["Meses base velocidad", data["velocity_months_label"]],
            ["Cobertura objetivo (meses)", data["coverage_months"]],
            ["Colchón best-seller", f"{int((data['safety_buffer']-1)*100)}%"],
            ["Stock total", data["stock_total"]],
            ["Stock taller", data["stock_taller"]],
            [""],
            ["Género", "Vel. base/mes", "Vel. ajustada/mes", "Stock", "Cobertura (m)", "Producir"],
        ]
        for g in ["CAB", "DAMA", "KIDS"]:
            s = summary[g]
            res_rows.append([g, s["v_mes_base"], s["v_mes"], s["stk"], s["cob"], s["produce"]])
        res_rows.append(["TOTAL", "", "", data["stock_total"], "", sum(summary[g]["produce"] for g in summary)])
        pd.DataFrame(res_rows).to_excel(writer, sheet_name="Resumen", index=False, header=False)

        store_cols = RETAIL_STORES + PROJECTED_STORES
        for genero in ["CAB", "DAMA", "KIDS"]:
            rows = []
            for item in [p for p in plan if p["genero"] == genero]:
                for t in item["tallas"]:
                    if t["produce"] <= 0 and t["cob"] >= COVERAGE_MONTHS:
                        continue
                    row = {
                        "Color": item["color"],
                        "Talla": t["talla"],
                        "Vel. base/mes": t["v_mes_base"],
                        "Vel. ajustada/mes": t["v_mes"],
                        "Stock actual": t["stk"],
                        "Stock taller": t["stk_taller"],
                        "Cobertura (meses)": t["cob"],
                        "Demanda 3m": round(t["v_mes"] * COVERAGE_MONTHS, 1),
                        "Producir sugerido": t["produce"],
                        "Urgente": "SÍ" if t["urgente"] else "NO",
                    }
                    split = item["store_split"]
                    total_split = sum(split.values()) or 1
                    for store in store_cols:
                        row[f"Dist {store}"] = int(round(t["produce"] * (split.get(store, 0) / total_split)))
                    rows.append(row)

            if not rows:
                rows.append({"Color": "—", "Talla": "—", "Producir sugerido": 0})

            df = pd.DataFrame(rows)
            df.to_excel(writer, sheet_name=genero, index=False)
            ws = writer.sheets[genero]
            ws.set_column(0, 1, 16)
            ws.set_column(2, 8, 14)
            for col_idx, _ in enumerate(df.columns):
                ws.write(0, col_idx, df.columns[col_idx], header_fmt)

        # Notas metodología
        notes = pd.DataFrame([
            ["Consideraciones aplicadas"],
            ["VELA", "Proyectada como 1× Grieta (tienda nueva)"],
            ["TOLON", f"Histórico × {TOLON_BOOST} (crecimiento)"],
            ["BARQUISIMETO", "Promedio Grieta + Chacao + Tolón"],
            ["WEB", f"50% de la tienda más fuerte"],
            ["Temporada alta", f"Factor ×{HIGH_SEASON_FACTOR} sobre velocidad base"],
            ["Best seller", f"Colchón adicional {int((SAFETY_BUFFER-1)*100)}% en producción"],
        ])
        notes.to_excel(writer, sheet_name="Metodología", index=False, header=False)


def patch_html(template: str, data: dict) -> str:
    def _json_default(obj):
        if isinstance(obj, (bool,)):
            return obj
        if hasattr(obj, "item"):
            return obj.item()
        raise TypeError(f"Not serializable: {type(obj)}")

    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=_json_default)

    html = re.sub(r"const DATA = \{.*?\};", f"const DATA = {data_json};", template, count=1, flags=re.DOTALL)

    # Tabs: add inventario
    html = html.replace(
        '<button class="tab" onclick="st(\'tiendas\')">🏪 Tiendas</button>\n  <button class="tab" onclick="st(\'decisiones\')">💡 Decisiones</button>',
        '<button class="tab" onclick="st(\'tiendas\')">🏪 Tiendas</button>\n  <button class="tab" onclick="st(\'inventario\')">📦 Inventario</button>\n  <button class="tab" onclick="st(\'decisiones\')">💡 Decisiones</button>',
    )

    inv_section = """
<div class="sec" id="sec-inventario">
  <div class="tkpis" id="invKpis"></div>
  <div class="g1 card"><h3>📦 Inventario por Tienda</h3><div class="sub">Unidades disponibles en cada punto de venta y en taller (recién llegado, pendiente de distribuir) · clic en tienda para ver colores, clic en color para ver tallas</div><div id="invByStore" style="margin-top:10px"></div></div>
  <div class="g1 card"><h3>Color × Tienda (Inventario)</h3><div class="sub">Heatmap de stock disponible</div><div class="hmw" id="invColorTiendaHM"></div></div>
</div>
"""
    html = html.replace(
        '<div class="sec" id="sec-decisiones">',
        inv_section + '<div class="sec" id="sec-decisiones">',
    )

    html = html.replace(
        '<div class="sub">Orden sugerida − stock actual = producir · cobertura: <span id="propMesesLabel">2 meses</span></div>',
        '<div class="sub">Orden sugerida − stock actual = producir · cobertura: <span id="propMesesLabel">2 meses</span> · '
        '<span style="color:#f97316">VELA 1× GRIETA · TOLON ×1.45 · BARQUISIMETO prom(GRIETA+CHACAO+TOLON) · WEB 50% tienda líder · temporada alta ×<span id="hsFactorLabel">1.35</span></span></div>',
    )

    html = html.replace(
        "if(tx.indexOf('Tienda')>=0)return'tiendas';return'decisiones';",
        "if(tx.indexOf('Tienda')>=0)return'tiendas';if(tx.indexOf('Inventario')>=0)return'inventario';return'decisiones';",
    )
    html = html.replace(
        "var TABS=['resumen','colores','tallas','tiendas','decisiones'];",
        "var TABS=['resumen','colores','tallas','tiendas','inventario','decisiones'];",
    )
    html = html.replace(
        "else if(n==='tiendas')rTiendas();else if(n==='decisiones')rDecisiones();",
        "else if(n==='tiendas')rTiendas();else if(n==='inventario')rInventario();else if(n==='decisiones')rDecisiones();",
    )

    # COLORES_DISP add KIDS
    html = re.sub(
        r"var COLORES_DISP=\{.*?\};",
        "var COLORES_DISP={"
        "CAB:{Negro:1,'Azul Marino':1,Blanco:1,'Verde Militar':1,'Azul Lavanda':1,'Azul Rey':1,Aguamarina:1,Rojo:1,Vinotinto:1,'Gris Claro':1,'Amarillo Neón':1},"
        "DAMA:{Negro:1,'Azul Marino':1,Blanco:1,'Verde Militar':1,'Azul Lavanda':1,Aguamarina:1,Rojo:1,Vinotinto:1,'Púrpura':1,Lila:1,'Rosado Pastel':1,'Amarillo Neón':1},"
        "KIDS:{Negro:1,'Azul Marino':1,Blanco:1,'Verde Militar':1,'Azul Lavanda':1,'Azul Rey':1,Aguamarina:1,Rojo:1,Lila:1,'Rosado Pastel':1,'Púrpura':1,'Amarillo Neón':1}"
        "};",
        html,
        count=1,
        flags=re.DOTALL,
    )

    # Replace getStoreWeights and store constants
    old_weights = re.search(
        r"// Store weights:.*?\nfunction getStoreWeights\(rows,l\)\{.*?\n\}",
        html,
        re.DOTALL,
    )
    new_weights = """// Store weights — VELA=GRIE, TOLON boost, BARQUISIMETO avg, WEB=50% líder
function getStoreWeights(rows,l){
  var byT={};rows.filter(function(r){return r.genero===l;}).forEach(function(r){byT[r.tienda]=(byT[r.tienda]||0)+r.v;});
  var grie=byT['GRIE']||0,chacao=byT['CHACAO']||0,tolon=byT['TOLON']||0;
  var strongest=Math.max(byT['SAMBIL']||0,grie,byT['CERRO VERDE']||0,chacao,byT['GRAND']||0,1);
  var tb=DATA.tolon_boost||1.45, w={};
  var stores=['SAMBIL','GRIE','CERRO VERDE','CHACAO','GRAND','TOLON'];
  for(var i=0;i<stores.length;i++){var base=byT[stores[i]]||0;if(stores[i]==='TOLON')base=Math.round(base*tb);w[stores[i]]=base;}
  w['VELA']=grie; w['BARQUISIMETO']=Math.round((grie+chacao+tolon)/3); w['WEB']=Math.round(strongest*0.5);
  var total=0;for(var k in w)total+=w[k];
  var shares={};for(var k in w)shares[k]=total>0?w[k]/total:0;
  return{weights:w,shares:shares,total:total};
}"""
    if old_weights:
        html = html[: old_weights.start()] + new_weights + html[old_weights.end() :]

    html = re.sub(
        r"var STORE_LABELS=\{.*?\};",
        "var STORE_LABELS={all:'📊 Producción Total',SAMBIL:'Sambil',GRIE:'Grieta','CERRO VERDE':'C.Verde',CHACAO:'Chacao',GRAND:'Grand',TOLON:'Tolón',VELA:'Vela ★',BARQUISIMETO:'Barquisimeto ★',WEB:'Web ★',TALLER:'Taller'};",
        html,
        count=1,
    )
    html = re.sub(
        r"var ALL_STORES=\[.*?\];",
        "var ALL_STORES=['SAMBIL','GRIE','CERRO VERDE','CHACAO','GRAND','TOLON','VELA','BARQUISIMETO','WEB'];",
        html,
        count=1,
    )

    # Update isNew checks in renderReabast and rDecisiones store tabs
    html = html.replace(
        "var isNew=_decTienda==='MARGARITA'||_decTienda==='TOLOM';",
        "var isNew=_decTienda==='VELA'||_decTienda==='BARQUISIMETO'||_decTienda==='WEB';",
    )
    html = html.replace(
        "var isNew=s==='MARGARITA'||s==='TOLOM';",
        "var isNew=s==='VELA'||s==='BARQUISIMETO'||s==='WEB';",
    )
    html = html.replace(
        "(store==='MARGARITA'?'2× capacidad GRIE':'1× capacidad CHACAO')",
        "(store==='VELA'?'1× Grieta':store==='BARQUISIMETO'?'Prom(Grieta+Chacao+Tolón)':'50% tienda líder')",
    )
    html = html.replace(
        "((_decTienda==='MARGARITA')?'2× GRIE':'1× CHACAO')",
        "(_decTienda==='VELA'?'1× Grieta':_decTienda==='BARQUISIMETO'?'Prom(G+Ch+T)':'50% líder')",
    )
    html = html.replace(
        "var isNew=store==='MARGARITA'||store==='TOLOM';",
        "var isNew=store==='VELA'||store==='BARQUISIMETO'||store==='WEB';",
    )
    html = html.replace(
        "'+ico+' '+store+'</div>'+(isNew?",
        "'+ico+' '+(STORE_LABELS[store]||store)+'</div>'+(isNew?",
    )

    # Insert rInventario before DECISIONES section if missing
    if "function rInventario" not in html:
        inv_js = """
// ══ INVENTARIO ══
var _invX={},_invColX={};
function toggleInv(uid){_invX[uid]=!_invX[uid];var d=document.getElementById(uid);if(!d)return;d.style.display=_invX[uid]?'block':'none';var arr=document.getElementById('arr_'+uid);if(arr)arr.style.transform=_invX[uid]?'rotate(90deg)':'rotate(0deg)';}
function toggleInvCol(uid){_invColX[uid]=!_invColX[uid];var d=document.getElementById(uid);if(!d)return;d.style.display=_invColX[uid]?'block':'none';}

function rInventario(){
  var sbs=DATA.stock_by_store||{},order=DATA.stores_order||Object.keys(sbs);
  var storeTotals={},grand=0;
  order.forEach(function(s){var t=0;Object.values(sbs[s]||{}).forEach(function(v){t+=v;});storeTotals[s]=t;grand+=t;});
  var tallerTotal=storeTotals['TALLER']||0,tiendaTotal=grand-tallerTotal;
  var colorGrand={};order.forEach(function(s){Object.entries(sbs[s]||{}).forEach(function(kv){var col=kv[0].split('/')[0];colorGrand[col]=(colorGrand[col]||0)+kv[1];});});
  var topColor=Object.entries(colorGrand).sort(function(a,b){return b[1]-a[1];})[0];
  document.getElementById('invKpis').innerHTML=
    '<div class="tkpi"><div class="tv">'+grand.toLocaleString()+'</div><div class="tl">Stock Total</div></div>'+
    '<div class="tkpi"><div class="tv">'+tiendaTotal.toLocaleString()+'</div><div class="tl">En Tiendas</div></div>'+
    '<div class="tkpi" style="border-color:#f97316"><div class="tv" style="color:#f97316">'+tallerTotal.toLocaleString()+'</div><div class="tl">🏭 En Taller</div></div>'+
    (topColor?'<div class="tkpi"><div class="tv"><span class="chip" style="background:'+cn(topColor[0])+'"></span>'+topColor[1].toLocaleString()+'</div><div class="tl">'+topColor[0]+'</div></div>':'');
  var h='';
  order.forEach(function(store){
    var isTaller=store==='TALLER';
    var data=sbs[store]||{};
    var cM={};Object.entries(data).forEach(function(kv){var p=kv[0].split('/'),col=p[0];cM[col]=(cM[col]||0)+kv[1];});
    var cA=Object.entries(cM).sort(function(a,b){return b[1]-a[1];});
    var colorItems=cA.map(function(ce){
      var col=ce[0],colV=ce[1];
      var tM={};Object.entries(data).forEach(function(kv){var p=kv[0].split('/');if(p[0]===col)tM[p[1]+' · '+p[2]]=(tM[p[1]+' · '+p[2]]||0)+kv[1];});
      var tA=Object.entries(tM).sort(function(a,b){return b[1]-a[1];});
      var tRows=tA.map(function(tv){return'<div style="display:flex;gap:6px;padding:2px 0;font-size:0.68rem"><div style="width:70px;font-weight:700;color:#c0c0e8">'+tv[0]+'</div><div style="color:var(--mu)">'+tv[1]+' und</div></div>';}).join('');
      var cUid='inv_'+store.replace(/[^a-z0-9]/gi,'_')+'_'+col.replace(/[^a-z0-9]/gi,'_');
      return'<div style="padding:2px 0"><div onclick="toggleInvCol(\\''+cUid+'\\')" style="display:flex;align-items:center;gap:6px;cursor:pointer;padding:3px 4px;border-radius:5px;font-size:0.73rem" onmouseover="this.style.background=\\'rgba(255,255,255,.04)\\'" onmouseout="this.style.background=\\'transparent\\'"><span style="width:8px;height:8px;border-radius:50%;background:'+cn(col)+'"></span><span style="flex:1;color:#e0e0f5">'+col+'</span><span style="color:var(--yw);font-weight:700;font-size:0.68rem">'+colV+'</span><span style="color:var(--ac);font-size:0.55rem">▶</span></div><div id="'+cUid+'" style="display:none;margin-left:16px;padding:2px 6px;border-left:2px solid '+cn(col)+'33">'+tRows+'</div></div>';
    }).join('');
    var sUid='inv_'+store.replace(/[^a-z0-9]/gi,'_');
    var ico=isTaller?'🏭':'🏪';
    var bg=isTaller?'rgba(249,115,22,.08)':'var(--s2)';
    var bdr=isTaller?'#f9731633':'var(--brd)';
    h+='<div style="background:'+bg+';border:1px solid '+bdr+';border-radius:12px;margin-bottom:10px"><div onclick="toggleInv(\\''+sUid+'\\')" style="display:flex;align-items:center;gap:10px;padding:14px 16px;cursor:pointer" onmouseover="this.style.opacity=\\'0.85\\'" onmouseout="this.style.opacity=\\'1\\'"><span id="arr_'+sUid+'" style="color:var(--ac);font-size:0.7rem;transition:transform .2s;flex-shrink:0">▶</span><div style="flex:1"><div style="font-family:var(--fh);font-weight:800;font-size:0.85rem">'+ico+' '+(STORE_LABELS[store]||store)+'</div>'+(isTaller?'<div style="font-size:0.6rem;color:#f97316">Recién llegado · pendiente por distribuir</div>':'')+'</div><div style="text-align:right"><div style="font-family:var(--fh);font-weight:800;color:'+(isTaller?'#f97316':'var(--yw)')+';font-size:1.1rem">'+storeTotals[store]+'</div><div style="font-size:0.6rem;color:var(--mu)">und</div></div></div>';
    h+='<div id="'+sUid+'" style="display:none;padding:0 16px 14px">'+(colorItems||'<div class="nodata">Sin stock</div>')+'</div></div>';
  });
  document.getElementById('invByStore').innerHTML=h;
  var colores=Object.keys(colorGrand).sort(function(a,b){return colorGrand[b]-colorGrand[a];});
  var allV=[];colores.forEach(function(c){order.forEach(function(s){var v=0;Object.entries(sbs[s]||{}).forEach(function(kv){if(kv[0].split('/')[0]===c)v+=kv[1];});allV.push(v);});});
  var mx=Math.max.apply(null,allV.concat([1]));
  document.getElementById('invColorTiendaHM').innerHTML=colores.length?'<table class="hmt"><thead><tr><th></th>'+order.map(function(s){return'<th>'+(STORE_LABELS[s]||s)+'</th>';}).join('')+'</tr></thead><tbody>'+colores.map(function(c){return'<tr><td class="rl"><span class="chip" style="background:'+cn(c)+'"></span>'+c+'</td>'+order.map(function(s){var v=0;Object.entries(sbs[s]||{}).forEach(function(kv){if(kv[0].split('/')[0]===c)v+=kv[1];});return'<td style="background:'+hb(v,mx)+';color:'+ht(v,mx)+'">'+(v||'—')+'</td>';}).join('')+'</tr>';}).join('')+'</tbody></table>':'<div class="nodata">Sin datos</div>';
}

"""
        html = html.replace("// ══ DECISIONES ══", inv_js + "// ══ DECISIONES ══", 1)

    # hs factor label update in rDecisiones
    if "hsFactorLabel" not in html.split("function rDecisiones")[1][:500]:
        html = html.replace(
            "function rDecisiones(){\n  var rows=fr();",
            "function rDecisiones(){\n  var hsLbl=document.getElementById('hsFactorLabel');if(hsLbl)hsLbl.textContent=DATA.high_season_factor||1.35;\n  var rows=fr();",
            1,
        )

    return html


def main() -> None:
    sales = load_sales()
    inv = load_inventory()
    data = build_data(sales, inv)

    template = TEMPLATE.read_text(encoding="utf-8")
    html = patch_html(template, data)
    OUT_HTML.write_text(html, encoding="utf-8")
    export_excel(data, OUT_XLSX)

    summary = data["summary_genero"]
    total_prod = sum(summary[g]["produce"] for g in summary)
    print(f"Dashboard: {OUT_HTML}")
    print(f"Excel: {OUT_XLSX}")
    print(f"Ventas total: {data['total']:,} | Stock: {data['stock_total']:,} | Producir: {total_prod:,}")
    for g in ["CAB", "DAMA", "KIDS"]:
        s = summary[g]
        print(f"  {g}: vel {s['v_mes']}/mes · stk {s['stk']} · cob {s['cob']}m · producir {s['produce']}")


if __name__ == "__main__":
    main()
