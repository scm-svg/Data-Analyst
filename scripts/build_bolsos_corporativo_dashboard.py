#!/usr/bin/env python3
"""Genera dashboard HTML + Excel de planes corporativos (bolsos playa / canastas)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = Path("/home/ubuntu/.cursor/projects/workspace/uploads")
TEMPLATE = ROOT / "DAILY 3.0 DASHBOARD PARA ACTUALIZAR.html"
OUT_HTML = ROOT / "DASHBOARD BOLSOS CORPORATIVO CANASTAS.html"
OUT_XLSX = ROOT / "PLANES_PEDIDO_CORPORATIVO_BOLSOS.xlsx"
ARTIFACTS = Path("/opt/cursor/artifacts")

HS = 1.25
VELA_MULT = 1.5
CORP_TOTAL = 2800
TARGET_DAYS_DRY = 75
MAXI_TOTE_PEDIDO_MAX = 700

MODELS = ["DRY BAG 30L", "CAVAPACK 35L", "MAXI TOTE"]
INCOMING = {"DRY BAG 30L": 2350, "CAVAPACK 35L": 1000, "MAXI TOTE": 0}
PLAN_COMERCIAL = {"DRY BAG 30L": 1500, "CAVAPACK 35L": 600, "MAXI TOTE": 700}

MES_MAP = {
    "ENERO": 1,
    "FEBRERO": 2,
    "MARZO": 3,
    "ABRIL": 4,
    "MAYO": 5,
    "JUNIO": 6,
    "JULIO": 7,
    "AGOSTO": 8,
    "SEPTIEMBRE": 9,
    "SETIEMBRE": 9,
    "OCTUBRE": 10,
    "NOVIEMBRE": 11,
    "DICIEMBRE": 12,
}
MES_N = [
    "",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]
RETAIL = ["CERRO VERDE", "CHACAO", "GRANDPLAZ", "GRIE", "SAMBIL", "TOLON", "VELA"]


def norm_tienda(t: str) -> str:
    t = str(t).strip().upper()
    if "GRAND" in t:
        return "GRANDPLAZ"
    if t in ("GRIE", "GRIETA", "LA GRIETA"):
        return "GRIE"
    if "VELA" in t:
        return "VELA"
    if "CHACAO" in t:
        return "CHACAO"
    if "SAMBIL" in t and "CHACAO" not in t:
        return "SAMBIL"
    if "CERRO" in t:
        return "CERRO VERDE"
    if t == "TOLON":
        return "TOLON"
    if t == "WEB":
        return "WEB"
    return t.strip()


def mes_key_sort(key: str) -> tuple[int, int]:
    mes, year = key.split("-")
    return (int(year), MES_MAP[mes.strip().upper()])


def sort_mes_keys(keys: list[str]) -> list[str]:
    return sorted(keys, key=mes_key_sort)


def norm_inv_loc(u: str) -> str:
    u = str(u).strip().upper()
    if u == "GRANDPLAZ" or "GRAND" in u:
        return "GRANDPLAZ"
    if u in ("GRIE", "GRIETA"):
        return "GRIE"
    return u


def load_frames():
    ventas = pd.read_excel(
        UPLOADS / "VENTAS_ACTUALIZADAS_PARA_ANALISIS_CORPORATIVO_115f.xlsx"
    )
    inv_b = pd.read_excel(UPLOADS / "INVENTARIO_BOLSOS_completo_889a.xlsx")
    inv_d = pd.read_excel(UPLOADS / "DRYBAG_30L_completo_6685.xlsx")
    inv = pd.concat([inv_b, inv_d], ignore_index=True)
    return ventas, inv


def prepare_sales(ventas: pd.DataFrame) -> pd.DataFrame:
    v = ventas.copy()
    v["tienda"] = v["tienda / ubicación"].apply(norm_tienda)
    v["modelo"] = v["Producto"].astype(str).str.strip().str.upper()
    v["color"] = v["COLOR"].astype(str).str.strip()
    v["mes_n"] = v["Mes"].astype(str).str.strip().str.upper().map(MES_MAP)
    v["ym"] = v.apply(
        lambda r: f"{int(r['Año'])}-{int(r['mes_n']):02d}"
        if pd.notna(r["mes_n"])
        else None,
        axis=1,
    )
    v["mes_key"] = v.apply(
        lambda r: f"{MES_N[int(r['mes_n'])]}-{int(r['Año'])}"
        if pd.notna(r["mes_n"])
        else None,
        axis=1,
    )
    v["qty"] = v["Cant. ordenada"].astype(float)
    return v


def stock_summary(inv: pd.DataFrame) -> dict:
    inv = inv.copy()
    inv["MODELO"] = inv["MODELO"].astype(str).str.strip().str.upper()
    inv["Ubicación"] = inv["Ubicación"].apply(norm_inv_loc)
    out = {}
    for m in MODELS:
        s = inv[inv["MODELO"] == m]
        out[m] = {
            "tienda": int(s[s["Ubicación"] != "TALLER"]["Cantidad en inventario"].sum()),
            "taller": int(s[s["Ubicación"] == "TALLER"]["Cantidad en inventario"].sum()),
            "total": int(s["Cantidad en inventario"].sum()),
        }
    return out


def calc_velocity(ventas: pd.DataFrame) -> tuple[dict, list[str]]:
    hist_stores = RETAIL + ["WEB"]
    all_months = sorted(
        ventas[ventas["tienda"].isin(hist_stores)]["ym"].dropna().unique()
    )
    complete = [m for m in all_months if m != "2026-09"]
    vel_months = complete[-6:]
    metrics = {}
    for model in MODELS:
        sub = ventas[(ventas["modelo"] == model) & (ventas["tienda"].isin(hist_stores))]
        retail_sub = sub[sub["tienda"].isin(RETAIL)]
        monthly_retail = retail_sub.groupby("ym")["qty"].sum()
        base_retail = sum(monthly_retail.get(m, 0) for m in vel_months) / len(vel_months)

        def store_avg(store: str) -> float:
            s = sub[sub["tienda"] == store].groupby("ym")["qty"].sum()
            return sum(s.get(m, 0) for m in vel_months) / len(vel_months)

        grie_avg = store_avg("GRIE")
        chacao_avg = store_avg("CHACAO")
        tolón_avg = store_avg("TOLON")
        vela_avg = store_avg("VELA")
        web_avg = store_avg("WEB")

        vela_uplift = max(0.0, grie_avg * VELA_MULT - vela_avg)
        web_uplift = web_avg  # Web repotenciado ≈ 1 Chacao adicional
        barquisimeto_uplift = (grie_avg + chacao_avg + tolón_avg) / 3.0

        base = base_retail + web_uplift + barquisimeto_uplift + vela_uplift
        v_mes_adj = base * HS
        metrics[model] = {
            "v_mes_base": round(float(base_retail), 1),
            "web_uplift": round(float(web_uplift), 1),
            "barquisimeto_uplift": round(float(barquisimeto_uplift), 1),
            "vela_uplift": round(float(vela_uplift), 1),
            "v_mes_adj": round(float(v_mes_adj), 1),
            "v_dia_adj": round(float(v_mes_adj / 30), 2),
        }
    return metrics, vel_months


def corp_available(stock: dict) -> dict:
    """Unidades que puede consumir el pedido corporativo (taller + tránsito)."""
    return {
        "DRY BAG 30L": stock["DRY BAG 30L"]["taller"] + INCOMING["DRY BAG 30L"],
        "CAVAPACK 35L": stock["CAVAPACK 35L"]["taller"] + INCOMING["CAVAPACK 35L"],
        "MAXI TOTE": min(stock["MAXI TOTE"]["taller"], MAXI_TOTE_PEDIDO_MAX),
    }


def days_after(qty: dict, stock: dict, metrics: dict) -> dict:
    """Días de inventario sobre red completa (tiendas intactas + remanente taller/tránsito)."""
    out = {}
    for m in MODELS:
        post = stock[m]["tienda"] + max(
            0, stock[m]["taller"] + INCOMING[m] - qty[m]
        )
        v = metrics[m]["v_mes_adj"]
        out[m] = round(post / v * 30, 1) if v > 0 else None
    return out


def plan_is_feasible(qty: dict, avail: dict) -> bool:
    if sum(qty.values()) != CORP_TOTAL:
        return False
    return all(0 <= qty[m] <= avail[m] for m in MODELS)


def optimize_plans(stock: dict, metrics: dict) -> tuple[dict, dict]:
    commercial = PLAN_COMERCIAL.copy()
    avail = corp_available(stock)
    maxi_cap = min(MAXI_TOTE_PEDIDO_MAX, avail["MAXI TOTE"])

    best_b = None
    for dry in range(0, min(1500, avail["DRY BAG 30L"]) + 1, 25):
        for maxi in range(400, maxi_cap + 1, 25):
            cava = CORP_TOTAL - dry - maxi
            if cava < 400 or cava > min(950, avail["CAVAPACK 35L"]):
                continue
            qty = {"DRY BAG 30L": dry, "CAVAPACK 35L": cava, "MAXI TOTE": maxi}
            if not plan_is_feasible(qty, avail):
                continue
            days = days_after(qty, stock, metrics)
            if days["DRY BAG 30L"] is not None and days["DRY BAG 30L"] >= TARGET_DAYS_DRY:
                if best_b is None or days["DRY BAG 30L"] > best_b[1]["DRY BAG 30L"]:
                    best_b = (qty, days)

    if best_b is None:
        qty = {"DRY BAG 30L": 1000, "CAVAPACK 35L": 950, "MAXI TOTE": maxi_cap}
        if sum(qty.values()) != CORP_TOTAL:
            qty["CAVAPACK 35L"] = CORP_TOTAL - qty["DRY BAG 30L"] - qty["MAXI TOTE"]
        best_b = (qty, days_after(qty, stock, metrics))

    best_c = None
    best_score = -1.0
    for dry in range(900, min(1350, avail["DRY BAG 30L"]) + 1, 25):
        for maxi in range(500, min(651, maxi_cap) + 1, 25):
            cava = CORP_TOTAL - dry - maxi
            if cava < 550 or cava > min(950, avail["CAVAPACK 35L"]):
                continue
            qty = {"DRY BAG 30L": dry, "CAVAPACK 35L": cava, "MAXI TOTE": maxi}
            if not plan_is_feasible(qty, avail):
                continue
            days = days_after(qty, stock, metrics)
            md = min(days.values())
            if md < 45:
                continue
            score = md + 0.15 * days["MAXI TOTE"]
            if score > best_score:
                best_score = score
                best_c = (qty, days)

    if best_c is None:
        qty = {"DRY BAG 30L": 1250, "CAVAPACK 35L": 850, "MAXI TOTE": 600}
        best_c = (qty, days_after(qty, stock, metrics))

    plans = {
        "Plan A — Comercial (propuesta actual)": commercial,
        "Plan B — Logística conservador (≥75 días Dry 30L)": best_b[0],
        "Plan C — Logística balanceado (cobertura equilibrada)": best_c[0],
    }
    plan_days = {
        name: days_after(q, stock, metrics) for name, q in plans.items()
    }
    return plans, plan_days


def allocate_sources(qty: int, stock_row: dict, incoming: int) -> dict:
    """Pedido corporativo: solo taller + tránsito (arribo). Stock tienda no se toca."""
    from_taller = min(qty, stock_row["taller"])
    rem = qty - from_taller
    from_incoming = min(rem, incoming)
    rem -= from_incoming
    return {
        "taller": from_taller,
        "tiendas": 0,
        "arribo_compra": from_incoming,
        "pendiente": rem,
    }


def build_data(ventas: pd.DataFrame, inv: pd.DataFrame) -> dict:
    stock = stock_summary(inv)
    metrics, vel_months = calc_velocity(ventas)
    plans, plan_days = optimize_plans(stock, metrics)

    v_retail = ventas[ventas["tienda"].isin(RETAIL)]
    v_chart = ventas[ventas["modelo"].isin(MODELS)]
    meses_order = sort_mes_keys(v_chart["mes_key"].dropna().unique().tolist())
    meses_und = (
        v_retail.groupby("mes_key")["qty"]
        .sum()
        .reindex(meses_order, fill_value=0)
        .astype(int)
        .to_dict()
    )

    raw_rows = []
    grouped = (
        v_retail.groupby(
            ["tienda", "modelo", "color", "mes_key"], as_index=False
        )["qty"]
        .sum()
        .rename(columns={"qty": "v"})
    )
    for _, r in grouped.iterrows():
        if r["v"] == 0:
            continue
        raw_rows.append(
            {
                "tienda": r["tienda"],
                "genero": "UNICO",
                "color": r["color"],
                "talla": "UNICA",
                "mes": r["mes_key"],
                "modelo": r["modelo"],
                "v": int(r["v"]),
            }
        )

    inv_rows = []
    stock_map = {}
    inv = inv.copy()
    inv["MODELO"] = inv["MODELO"].astype(str).str.strip().str.upper()
    inv["Ubicación"] = inv["Ubicación"].apply(norm_inv_loc)
    inv["COLOR"] = inv["COLOR"].astype(str).str.strip()
    for _, r in inv[inv["MODELO"].isin(MODELS)].iterrows():
        qty = int(r["Cantidad en inventario"])
        if qty == 0:
            continue
        modelo = r["MODELO"]
        color = r["COLOR"]
        talla = "UNICA"
        inv_rows.append(
            {
                "modelo": modelo,
                "genero": "UNICO",
                "color": color,
                "talla": talla,
                "ubicacion": r["Ubicación"],
                "qty": qty,
            }
        )
        key = f"{modelo}/UNICO/{color}/{talla}"
        stock_map[key] = stock_map.get(key, 0) + qty

    stock_by_modelo = {m: stock[m]["total"] for m in MODELS}
    colors = sorted({r["color"] for r in raw_rows})
    tiendas = sorted({r["tienda"] for r in raw_rows if r["tienda"] in RETAIL})

    corporate = []
    for name, qty_map in plans.items():
        rows = []
        for m in MODELS:
            src = allocate_sources(qty_map[m], stock[m], INCOMING[m])
            corp_pool = stock[m]["taller"] + INCOMING[m]
            post_total = stock[m]["tienda"] + max(0, corp_pool - qty_map[m])
            rows.append(
                {
                    "modelo": m,
                    "qty_pedido": qty_map[m],
                    "stock_tiendas": stock[m]["tienda"],
                    "stock_taller": stock[m]["taller"],
                    "arribo_compra": INCOMING[m],
                    "pool_corporativo": corp_pool,
                    "stock_post": post_total,
                    "dias_inventario": plan_days[name][m],
                    "v_mes_adj": metrics[m]["v_mes_adj"],
                    "fuente_taller": src["taller"],
                    "fuente_tiendas": src["tiendas"],
                    "fuente_arribo": src["arribo_compra"],
                    "gap": src["pendiente"],
                }
            )
        corporate.append(
            {
                "nombre": name,
                "total": sum(qty_map.values()),
                "rows": rows,
                "dias_min": min(plan_days[name].values()),
                "dias_prom": round(
                    sum(plan_days[name].values()) / len(plan_days[name]), 1
                ),
            }
        )

    return {
        "nombre": "Bolsos Playa · Pedido Corporativo Canastas",
        "periodo": "Oct 2025 — Sep 2026",
        "as_of": "2026-09-17",
        "contexto": "Pedido 2.800 und · Temporada alta ×1.25 · VELA 1.5× GRIE · Barquisimeto prom(GRIE,Chacao,Tolón) · Web ≈ 1 Chacao",
        "maxi_tote_pedido_max": MAXI_TOTE_PEDIDO_MAX,
        "corp_pool": corp_available(stock),
        "high_season_factor": HS,
        "raw_rows": raw_rows,
        "inv_rows": inv_rows,
        "stock": stock_map,
        "stock_by_modelo": stock_by_modelo,
        "stock_taller": sum(stock[m]["taller"] for m in MODELS),
        "meses_order": meses_order,
        "meses_und": meses_und,
        "filtros": {
            "tiendas": tiendas,
            "generos": ["UNICO"],
            "colores": colors,
            "modelos": MODELS,
        },
        "all_stores": RETAIL,
        "decision_exclude_stores": ["PEDIDOS", "CORPORATIVO"],
        "new_store_barquisimeto_label": "Promedio GRIE + Chacao + Tolón",
        "es_parcial": True,
        "stock_total": sum(stock_by_modelo.values()),
        "total": int(v_retail["qty"].sum()),
        "incoming": INCOMING,
        "stock_summary": stock,
        "velocity": metrics,
        "velocity_months": vel_months,
        "corporate_plans": corporate,
        "target_corp_total": CORP_TOTAL,
    }


def write_excel(data: dict, path: Path) -> None:
    stock = data["stock_summary"]
    metrics = data["velocity"]
    rows = []
    for plan in data["corporate_plans"]:
        for r in plan["rows"]:
            rows.append(
                {
                    "Plan": plan["nombre"],
                    "Modelo": r["modelo"],
                    "Cant. pedido corporativo": r["qty_pedido"],
                    "Stock tiendas (no se toca)": r["stock_tiendas"],
                    "Stock taller": r["stock_taller"],
                    "Arribo compra (tránsito)": r["arribo_compra"],
                    "Pool corporativo (taller+tránsito)": r["pool_corporativo"],
                    "Inventario total post-pedido": r["stock_post"],
                    "Rotación mensual ajustada (und/mes)": r["v_mes_adj"],
                    "Días de inventario post-pedido": r["dias_inventario"],
                    "Fuente taller": r["fuente_taller"],
                    "Fuente tiendas": r["fuente_tiendas"],
                    "Fuente arribo compra": r["fuente_arribo"],
                    "Brecha vs stock": r["gap"],
                }
            )
    df = pd.DataFrame(rows)

    summary = []
    for plan in data["corporate_plans"]:
        summary.append(
            {
                "Plan": plan["nombre"],
                "Total und pedido": plan["total"],
                "Días mínimo (modelos)": plan["dias_min"],
                "Días promedio ponderado": plan["dias_prom"],
            }
        )
    df_sum = pd.DataFrame(summary)

    params = pd.DataFrame(
        [
            {"Parámetro": "Temporada alta (factor)", "Valor": HS},
            {"Parámetro": "Proyección tienda VELA", "Valor": "1.5× velocidad GRIE"},
            {"Parámetro": "Tienda nueva Barquisimeto", "Valor": "Promedio mensual GRIE + Chacao + Tolón"},
            {"Parámetro": "Canal Web repotenciado", "Valor": "Equivalente a 1 Chacao adicional"},
            {"Parámetro": "Pedido corporativo", "Valor": "Solo taller + tránsito (stock tienda intacto)"},
            {"Parámetro": "Tope Maxi Tote pedido", "Valor": MAXI_TOTE_PEDIDO_MAX},
            {"Parámetro": "Meses base rotación", "Valor": ", ".join(data["velocity_months"])},
            {"Parámetro": "Pedido corporativo objetivo", "Valor": CORP_TOTAL},
            {"Parámetro": "Meta cobertura Dry 30L Plan B", "Valor": f"≥ {TARGET_DAYS_DRY} días"},
        ]
    )

    with pd.ExcelWriter(path, engine="xlsxwriter") as xw:
        df_sum.to_excel(xw, sheet_name="Resumen", index=False)
        df.to_excel(xw, sheet_name="Detalle_planes", index=False)
        params.to_excel(xw, sheet_name="Metodologia", index=False)
        for m in MODELS:
            s = stock[m]
            metrics[m]
            pd.DataFrame(
                [
                    {"Métrica": "Stock tiendas", "Valor": s["tienda"]},
                    {"Métrica": "Stock taller", "Valor": s["taller"]},
                    {"Métrica": "Arribo compra", "Valor": INCOMING[m]},
                    {"Métrica": "Rotación base und/mes", "Valor": metrics[m]["v_mes_base"]},
                    {"Métrica": "Uplift VELA und/mes", "Valor": metrics[m]["vela_uplift"]},
                    {"Métrica": "Rotación ajustada und/mes", "Valor": metrics[m]["v_mes_adj"]},
                ]
            ).to_excel(xw, sheet_name=m[:31], index=False)


def patch_template(data: dict) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace(
        "<title>Dashboard Daily 3.0 - Clásica</title>",
        "<title>Dashboard Bolsos · Pedido Corporativo Canastas</title>",
    )
    html = html.replace(
        "<h1>Daily 3.0 - <em>Clásica</em></h1>",
        "<h1>Bolsos Playa · <em>Pedido Corporativo</em></h1>",
    )
    html = html.replace(
        "<p>Dashboard de Ventas · Junio 2025 — Julio 2026</p>",
        f"<p>{data['periodo']} · Análisis días de inventario · {data['as_of']}</p>",
    )

    mbar = """<div class="mbar">
  <span class="mbar-lbl">⚡ Modelo:</span>
  <button class="mbtn active" data-m="" onclick="setModelo('')">🗂️ Todos <span class="mcnt" id="mcnt_all">0</span></button>
  <button class="mbtn" data-m="DRY BAG 30L" onclick="setModelo('DRY BAG 30L')">💧 Dry 30L <span class="mcnt" id="mcnt_DRY30">0</span></button>
  <button class="mbtn" data-m="CAVAPACK 35L" onclick="setModelo('CAVAPACK 35L')">🎒 Cavapack <span class="mcnt" id="mcnt_CAVA">0</span></button>
  <button class="mbtn" data-m="MAXI TOTE" onclick="setModelo('MAXI TOTE')">👜 Maxi Tote <span class="mcnt" id="mcnt_MAXI">0</span></button>
</div>"""
    html = re.sub(
        r'<div class="mbar" style="display:none">.*?</div>',
        mbar,
        html,
        count=1,
        flags=re.S,
    )

    corp_block = """
  <div class="card g1" style="margin-bottom:14px;border-color:#5b6af766">
    <h3>📋 Pedido corporativo · 2.800 und</h3>
    <div class="sub">Asignación desde <strong>taller + tránsito</strong> · stock tienda intacto · cobertura sobre inventario total de red</div>
    <div id="corpPlansGrid"></div>
  </div>"""
    html = html.replace(
        '<div class="g2">\n    <div class="card" style="grid-column:1/-1">\n      <h3>🏭 Curva de Producción por Modelo</h3>',
        corp_block
        + '\n  <div class="g2">\n    <div class="card" style="grid-column:1/-1">\n      <h3>🛒 Compra sugerida</h3>',
    )
    html = html.replace(
        "Sugerencia proporcional por color y talla · Clic en color para detalle",
        "Reposición sugerida por color · clic en color para detalle de talla",
    )

    html = html.replace(
        "CERRO VERDE excluida",
        "🆕 VELA 1.5× GRIE · Barquisimeto prom(GRIE+Chacao+Tolón) · Web ≈ 1 Chacao",
    )

    html = re.sub(
        r'\s*<button class="tab"[^>]*onclick="st\(\'tallas\'\)"[^>]*>.*?</button>\s*',
        "\n  ",
        html,
        count=1,
        flags=re.S,
    )
    html = re.sub(
        r'<div class="sec" id="sec-tallas">.*?</div>\s*\n<div class="sec" id="sec-tiendas">',
        '<div class="sec" id="sec-tiendas">',
        html,
        count=1,
        flags=re.S,
    )
    html = html.replace(
        "var TABS=['resumen','colores','tallas','tiendas','inventario','decisiones'];",
        "var TABS=['resumen','colores','tiendas','inventario','decisiones'];",
    )
    html = html.replace(
        "if(tx.indexOf('Talla')>=0)return'tallas';",
        "",
    )
    html = html.replace(
        "else if(n==='tallas')rTallas();",
        "",
    )

    html = re.sub(
        r"var NEW_STORES=\[[^\]]*\];",
        "var NEW_STORES=['VELA','BARQUISIMETO'];",
        html,
        flags=re.S,
    )
    html = re.sub(
        r"var NEW_STORE_CAPS=\{.*?\};",
        "var NEW_STORE_CAPS={'VELA':{base:'GRIE',mult:1.5,label:'1.5× capacidad GRIE (La Grieta)'},'BARQUISIMETO':{base:'BARQUISIMETO',mult:1,label:'Promedio GRIE + Chacao + Tolón (tienda nueva)'}};",
        html,
        flags=re.S,
    )
    html = html.replace(
        "function getNewStoreShare(store,realShares){\n  var cap=NEW_STORE_CAPS[store];if(!cap)return 0;\n  return(realShares[cap.base]||0)*cap.mult;\n}",
        "function getNewStoreShare(store,realShares){\n  var cap=NEW_STORE_CAPS[store];if(!cap)return 0;\n  if(store==='BARQUISIMETO'){return((realShares['GRIE']||0)+(realShares['CHACAO']||0)+(realShares['TOLON']||0))/3;}\n  return(realShares[cap.base]||0)*cap.mult;\n}",
    )

    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = re.sub(r"var DATA=\{.*?\};", f"var DATA={data_json};", html, count=1, flags=re.S)

    corp_fn = """
function corpCobertura(d){
  if(d==null||isNaN(d))return'—';
  var m=Math.round(d/30*10)/10;
  return d+' d <span style="color:var(--mu2);font-weight:500">(~'+m+' m)</span>';
}
function renderCorporatePlans(){
  var el=document.getElementById('corpPlansGrid');if(!el||!DATA.corporate_plans)return;
  var h='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px;margin-top:8px">';
  DATA.corporate_plans.forEach(function(p,idx){
    var col=idx===0?'#5b6af7':idx===1?'#10b981':'#f59e0b';
    var dmin=p.dias_min,dpro=p.dias_prom;
    h+='<div style="background:var(--s2);border:1px solid var(--brd);border-radius:12px;padding:14px;border-top:3px solid '+col+'">';
    h+='<div style="font-family:var(--fh);font-weight:800;font-size:0.82rem;margin-bottom:6px">'+p.nombre+'</div>';
    h+='<div style="font-size:0.68rem;color:var(--mu);margin-bottom:10px">Total pedido <strong style="color:var(--tx)">'+p.total+' und</strong> · cobertura mín. '+corpCobertura(dmin)+' · prom. '+corpCobertura(dpro)+'</div>';
    h+='<div style="overflow-x:auto"><table class="ct" style="font-size:0.68rem;min-width:100%"><thead><tr><th>Modelo</th><th>Taller+Tránsito</th><th>Rot. und/mes</th><th>Pedido</th><th>Inv. post red</th><th>Cobertura</th></tr></thead><tbody>';
    p.rows.forEach(function(r){
      var dc=r.dias_inventario<60?'#ef4444':r.dias_inventario<90?'#f59e0b':'#10b981';
      var nm=r.modelo.replace('DRY BAG 30L','Dry 30L').replace('CAVAPACK 35L','Cavapack').replace('MAXI TOTE','Maxi Tote');
      h+='<tr><td style="white-space:nowrap">'+nm+'</td><td style="font-weight:700;color:#22d3ee">'+(r.pool_corporativo!=null?r.pool_corporativo:'—')+'</td><td style="color:#a5b4fc">'+(r.v_mes_adj!=null?Math.round(r.v_mes_adj*10)/10:'—')+'</td><td style="font-weight:700">'+r.qty_pedido+'</td><td>'+r.stock_post+'</td><td style="font-weight:800;color:'+dc+'">'+corpCobertura(r.dias_inventario)+'</td></tr>';
    });
    h+='</tbody></table></div></div>';
  });
  h+='</div><div style="margin-top:12px;font-size:0.68rem;color:var(--mu);line-height:1.5"><strong>Taller+Tránsito</strong> = pool disponible para corporativo (sin tiendas). <strong>Rot. und/mes</strong> = consumo mensual ajustado (temporada alta ×'+(DATA.high_season_factor||1.25)+', VELA, Barquisimeto, Web≈Chacao). <strong>Cobertura</strong> = inventario total post-pedido ÷ rotación (días y meses ~30 d).</div>';
  el.innerHTML=h;
}
"""
    if "function renderCorporatePlans" in html:
        html = re.sub(
            r"function renderCorporatePlans\(\)\{.*?\n\}\n",
            corp_fn.strip() + "\n",
            html,
            count=1,
            flags=re.S,
        )
    else:
        html = html.replace("function rDecisiones(){", corp_fn + "\nfunction rDecisiones(){")
        html = html.replace(
            "  renderReabast(allRows);\n}",
            "  renderCorporatePlans();\n  renderReabast(allRows);\n}",
        )
    if "renderCorporatePlans();" not in html.split("function rDecisiones")[1][:800]:
        html = html.replace(
            "  renderReabast(allRows);\n}",
            "  renderCorporatePlans();\n  renderReabast(allRows);\n}",
        )

    html = re.sub(
        r"var MODELO_ID=\{.*?\};",
        "var MODELO_ID={'DRY BAG 30L':'DRY30','CAVAPACK 35L':'CAVA','MAXI TOTE':'MAXI'};",
        html,
        count=1,
    )
    html = re.sub(
        r"var MICO=\{.*?\};",
        "var MICO={'DRY BAG 30L':'💧','CAVAPACK 35L':'🎒','MAXI TOTE':'👜'};",
        html,
        count=1,
    )
    html = html.replace(
        "📋 Pedido corporativo · 2.800 canastas navideñas",
        "📋 Pedido corporativo · 2.800 und",
    )
    return html


def main():
    ventas, inv = load_frames()
    ventas = prepare_sales(ventas)
    data = build_data(ventas, inv)
    OUT_HTML.write_text(patch_template(data), encoding="utf-8")
    write_excel(data, OUT_XLSX)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    write_excel(data, ARTIFACTS / OUT_XLSX.name)
    (ARTIFACTS / OUT_HTML.name).write_text(OUT_HTML.read_text(encoding="utf-8"), encoding="utf-8")
    print("Wrote", OUT_HTML)
    print("Wrote", OUT_XLSX)


if __name__ == "__main__":
    main()
