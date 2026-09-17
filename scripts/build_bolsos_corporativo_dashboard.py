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
    return t.strip()


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
    all_months = sorted(
        ventas[ventas["tienda"].isin(RETAIL)]["ym"].dropna().unique()
    )
    complete = [m for m in all_months if m != "2026-09"]
    vel_months = complete[-6:]
    metrics = {}
    for model in MODELS:
        sub = ventas[(ventas["modelo"] == model) & (ventas["tienda"].isin(RETAIL))]
        monthly = sub.groupby("ym")["qty"].sum()
        base = sum(monthly.get(m, 0) for m in vel_months) / len(vel_months)
        grie_m = sub[sub["tienda"] == "GRIE"].groupby("ym")["qty"].sum()
        vela_m = sub[sub["tienda"] == "VELA"].groupby("ym")["qty"].sum()
        grie_avg = sum(grie_m.get(m, 0) for m in vel_months) / len(vel_months)
        vela_avg = sum(vela_m.get(m, 0) for m in vel_months) / len(vel_months)
        vela_uplift = max(0.0, grie_avg * VELA_MULT - vela_avg)
        v_mes_adj = (base + vela_uplift) * HS
        metrics[model] = {
            "v_mes_base": round(float(base), 1),
            "vela_uplift": round(float(vela_uplift), 1),
            "v_mes_adj": round(float(v_mes_adj), 1),
            "v_dia_adj": round(float(v_mes_adj / 30), 2),
        }
    return metrics, vel_months


def max_available(stock: dict) -> dict:
    return {m: stock[m]["total"] + INCOMING[m] for m in MODELS}


def days_after(qty: dict, stock: dict, metrics: dict) -> dict:
    out = {}
    for m in MODELS:
        pipe = stock[m]["total"] + INCOMING[m] - qty[m]
        v = metrics[m]["v_mes_adj"]
        out[m] = round(pipe / v * 30, 1) if v > 0 else None
    return out


def plan_is_feasible(qty: dict, avail: dict) -> bool:
    if sum(qty.values()) != CORP_TOTAL:
        return False
    return all(0 <= qty[m] <= avail[m] for m in MODELS)


def optimize_plans(stock: dict, metrics: dict) -> tuple[dict, dict]:
    commercial = PLAN_COMERCIAL.copy()
    avail = max_available(stock)

    best_b = None
    for dry in range(0, min(1500, avail["DRY BAG 30L"]) + 1, 25):
        for maxi in range(700, min(avail["MAXI TOTE"], CORP_TOTAL) + 1, 25):
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
        qty = {"DRY BAG 30L": 1000, "CAVAPACK 35L": 968, "MAXI TOTE": 832}
        best_b = (qty, days_after(qty, stock, metrics))

    best_c = None
    best_score = -1.0
    for dry in range(200, min(1300, avail["DRY BAG 30L"]) + 1, 25):
        for maxi in range(500, min(avail["MAXI TOTE"], 800) + 1, 25):
            cava = CORP_TOTAL - dry - maxi
            if cava < 400 or cava > min(950, avail["CAVAPACK 35L"]):
                continue
            qty = {"DRY BAG 30L": dry, "CAVAPACK 35L": cava, "MAXI TOTE": maxi}
            if not plan_is_feasible(qty, avail):
                continue
            days = days_after(qty, stock, metrics)
            md = min(days.values())
            if md < 0:
                continue
            score = md + 0.25 * days["DRY BAG 30L"]
            if score > best_score:
                best_score = score
                best_c = (qty, days)

    if best_c is None:
        qty = {"DRY BAG 30L": 1150, "CAVAPACK 35L": 900, "MAXI TOTE": 750}
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


def allocate_sources(qty: int, stock: dict, incoming: int, taller: int) -> dict:
    """Prioriza taller, luego tiendas, luego arribos de compra."""
    from_taller = min(qty, taller)
    rem = qty - from_taller
    from_tienda = min(rem, stock["tienda"])
    rem -= from_tienda
    from_incoming = min(rem, incoming)
    rem -= from_incoming
    return {
        "taller": from_taller,
        "tiendas": from_tienda,
        "arribo_compra": from_incoming,
        "pendiente": rem,
    }


def build_data(ventas: pd.DataFrame, inv: pd.DataFrame) -> dict:
    stock = stock_summary(inv)
    metrics, vel_months = calc_velocity(ventas)
    plans, plan_days = optimize_plans(stock, metrics)

    v_retail = ventas[ventas["tienda"].isin(RETAIL)]
    meses_order = sorted(v_retail["mes_key"].dropna().unique())
    meses_und = (
        v_retail.groupby("mes_key")["qty"].sum().reindex(meses_order, fill_value=0).astype(int).to_dict()
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
            src = allocate_sources(
                qty_map[m],
                stock[m],
                INCOMING[m],
                stock[m]["taller"],
            )
            pipe = stock[m]["total"] + INCOMING[m]
            rem = pipe - qty_map[m]
            rows.append(
                {
                    "modelo": m,
                    "qty_pedido": qty_map[m],
                    "stock_actual": stock[m]["total"],
                    "arribo_compra": INCOMING[m],
                    "stock_post": rem,
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
        "contexto": "Pedido 2.800 und · Temporada alta ×1.25 · VELA 1.5× GRIE",
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
        "decision_exclude_stores": ["WEB", "PEDIDOS", "CORPORATIVO"],
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
                    "Stock actual (tiendas+taller)": r["stock_actual"],
                    "Arribo compra estimado": r["arribo_compra"],
                    "Stock disponible pre-pedido": r["stock_actual"] + r["arribo_compra"],
                    "Stock remanente post-pedido": r["stock_post"],
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
    <h3>📋 Pedido corporativo · 2.800 canastas navideñas</h3>
    <div class="sub">Comparativo de planes · días de inventario post-pedido (stock tiendas+taller + arribos compra − pedido)</div>
    <div id="corpPlansGrid"></div>
  </div>"""
    html = html.replace(
        '<div class="g2">\n    <div class="card" style="grid-column:1/-1">\n      <h3>🏭 Curva de Producción por Modelo</h3>',
        corp_block
        + '\n  <div class="g2">\n    <div class="card" style="grid-column:1/-1">\n      <h3>🏭 Curva de Producción por Modelo</h3>',
    )

    html = html.replace(
        "CERRO VERDE excluida",
        "Excluye WEB · PEDIDOS · CORPORATIVO del histórico retail",
    )

    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = re.sub(r"var DATA=\{.*?\};", f"var DATA={data_json};", html, count=1, flags=re.S)

    if "function renderCorporatePlans" not in html:
        inject = """
function renderCorporatePlans(){
  var el=document.getElementById('corpPlansGrid');if(!el||!DATA.corporate_plans)return;
  var h='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;margin-top:8px">';
  DATA.corporate_plans.forEach(function(p,idx){
    var col=idx===0?'#5b6af7':idx===1?'#10b981':'#f59e0b';
    h+='<div style="background:var(--s2);border:1px solid var(--brd);border-radius:12px;padding:14px;border-top:3px solid '+col+'">';
    h+='<div style="font-family:var(--fh);font-weight:800;font-size:0.82rem;margin-bottom:6px">'+p.nombre+'</div>';
    h+='<div style="font-size:0.68rem;color:var(--mu);margin-bottom:10px">Total <strong style="color:var(--tx)">'+p.total+' und</strong> · mín '+p.dias_min+' d · prom '+p.dias_prom+' d</div>';
    h+='<table class="ct" style="font-size:0.72rem"><thead><tr><th>Modelo</th><th>Pedido</th><th>Post stock</th><th>Días</th></tr></thead><tbody>';
    p.rows.forEach(function(r){
      var dc=r.dias_inventario<60?'#ef4444':r.dias_inventario<90?'#f59e0b':'#10b981';
      h+='<tr><td>'+r.modelo.replace('DRY BAG 30L','Dry 30L').replace('CAVAPACK 35L','Cavapack').replace('MAXI TOTE','Maxi Tote')+'</td><td style="font-weight:700">'+r.qty_pedido+'</td><td>'+r.stock_post+'</td><td style="font-weight:800;color:'+dc+'">'+r.dias_inventario+'</td></tr>';
    });
    h+='</tbody></table></div>';
  });
  h+='</div><div style="margin-top:12px;font-size:0.68rem;color:var(--mu);line-height:1.5">Rotación ajustada = promedio retail últimos 6 meses completos + proyección VELA (1.5× GRIE) × factor temporada alta ('+(DATA.high_season_factor||1.25)+'). Arribos: Dry 30L 2.350 · Cavapack 1.000 · Maxi Tote solo stock taller.</div>';
  el.innerHTML=h;
}
"""
        html = html.replace("function rDecisiones(){", inject + "\nfunction rDecisiones(){")
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
