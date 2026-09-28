#!/usr/bin/env python3
"""
Genera propuesta Black Friday — Categoría C (Manufactura + Equipamiento)
a partir del dashboard ABC embebido y el inventario actualizado en Excel.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = Path("/home/ubuntu/.cursor/projects/workspace/uploads")
ABC_HTML = UPLOADS / "abc_ver_fcbe.html"
INV_XLSX = UPLOADS / "INVENTARIO_TOTAL_CUADRO_PARA_ABC_-_PROPUESTA_aeec.xlsx"
OUT_JSON = ROOT / "bf_proposal_data.json"
OUT_HTML = ROOT / "black_friday_propuesta_categoria_c.html"
OUT_XLSX = ROOT / "BLACK_FRIDAY_PROPUESTA_CATEGORIA_C.xlsx"

TH_A, TH_B = 0.8, 0.95
PERIOD_MONTHS = 10  # Oct 2025 – Jul 2026 en dashboard ABC
BF_UPLIFT = 4.0  # multiplicador vs venta mensual promedio (hipótesis campaña)
RETAIL_LOCS = [
    "CERRO VERDE",
    "CHACAO",
    "GRANDPLAZ",
    "GRIETA",
    "SAMBIL",
    "TOLON",
    "VELA",
]
RESERVE_PCT = 0.15  # colchón post-BF en tienda


def load_embedded_abc(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    part = text.split('id="abc-embedded-data"')[1]
    json_start = part.find("{")
    depth = 0
    in_str = False
    esc = False
    end = None
    for j, ch in enumerate(part[json_start:], json_start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    if end is None:
        raise RuntimeError("No se pudo parsear JSON embebido del dashboard ABC")
    return json.loads(part[json_start:end])


def pareto_abc(values: list[tuple[str, float]]) -> dict[str, str]:
    pos = [(k, v) for k, v in values if v > 0]
    pos.sort(key=lambda x: -x[1])
    total = sum(v for _, v in pos) or 1.0
    cum = 0.0
    out: dict[str, str] = {}
    for k, v in pos:
        cum += v
        cp = cum / total
        if cp <= TH_A:
            cls = "A"
        elif cp <= TH_B:
            cls = "B"
        else:
            cls = "C"
        out[k] = cls
    return out


def segment(cat: str) -> str:
    if cat.startswith("Equipamiento"):
        return "Equipamiento"
    if cat.startswith("Manufactura"):
        return "Manufactura"
    return "Otro"


def max_discount_for_margin_floor(unit_price: float, unit_cost: float, floor_rate: float) -> float:
    """Descuento máximo para mantener margen/contribución >= floor_rate sobre precio lista."""
    if unit_price <= 0:
        return 0.0
    # (P*(1-d) - C) / P >= floor_rate  =>  d <= 1 - C/P - floor_rate
    d = 1.0 - (unit_cost / unit_price) - floor_rate
    return max(0.0, min(0.55, d))


def coverage_months(stock: float, monthly_qty: float) -> float:
    if monthly_qty <= 0:
        return 999.0 if stock > 0 else 0.0
    return stock / monthly_qty


def option_a_discount(matrix: str) -> float:
    rot = matrix[1] if len(matrix) > 1 else "C"
    if rot == "C":
        return 0.40
    if rot == "B":
        return 0.30
    if rot == "A":
        return 0.20
    return 0.35


def option_b_discount(cov: float, matrix: str, unit_price: float, unit_cost: float) -> float:
    if cov >= 6:
        base = 0.45
    elif cov >= 3:
        base = 0.35
    elif cov >= 1:
        base = 0.25
    else:
        base = 0.15
    if matrix.endswith("C"):
        base += 0.05
    cap = max_discount_for_margin_floor(unit_price, unit_cost, floor_rate=0.08)
    return min(base, cap) if cap > 0 else base * 0.7


def main() -> None:
    data = load_embedded_abc(ABC_HTML)
    skus = data["skus"]
    sku_master = data["skuMaster"]
    period_keys = {p["key"] for p in data["periods"]}

    sku_metrics: dict[str, dict] = {}
    for row in data["salesRows"]:
        pkey = data["periods"][row[0]]["key"]
        if pkey not in period_keys:
            continue
        sku = skus[row[1]]
        cat = data["categories"][row[3]]
        meta = sku_master.get(sku, {})
        if sku not in sku_metrics:
            sku_metrics[sku] = {
                "sku": sku,
                "producto": meta.get("producto") or sku,
                "modelo": meta.get("modelo") or meta.get("producto") or sku,
                "categoria": meta.get("categoria") or cat,
                "genero": meta.get("genero") or "",
                "color": meta.get("color") or "",
                "talla": meta.get("talla") or "",
                "qty": 0.0,
                "revenue": 0.0,
                "cost": 0.0,
                "margin": 0.0,
            }
        o = sku_metrics[sku]
        o["qty"] += row[4]
        o["revenue"] += row[5]
        o["cost"] += row[6]
        o["margin"] += row[7]

    margin_abc = pareto_abc([(s, v["margin"]) for s, v in sku_metrics.items() if v["margin"] > 0])
    rot_abc = pareto_abc([(s, v["qty"]) for s, v in sku_metrics.items() if v["qty"] > 0])

    inv_df = pd.read_excel(INV_XLSX)
    inv_df["Ubicación"] = inv_df["Ubicación"].astype(str).str.upper().str.strip()
    inv_df["SKU"] = inv_df["SKU"].astype(str).str.strip()
    stock_by_sku_loc = (
        inv_df.groupby(["SKU", "Ubicación"], as_index=False)["Cantidad en inventario"]
        .sum()
    )
    stock_total = inv_df.groupby("SKU")["Cantidad en inventario"].sum().to_dict()
    stock_retail = (
        inv_df[inv_df["Ubicación"].isin(RETAIL_LOCS)]
        .groupby("SKU")["Cantidad en inventario"]
        .sum()
        .to_dict()
    )

    candidates: list[dict] = []
    for sku, m in sku_metrics.items():
        if m["margin"] <= 0:
            continue
        if margin_abc.get(sku) != "C":
            continue
        seg = segment(m["categoria"])
        if seg not in ("Manufactura", "Equipamiento"):
            continue
        qty = m["qty"]
        monthly = qty / PERIOD_MONTHS
        stock = float(stock_total.get(sku, 0))
        stock_r = float(stock_retail.get(sku, 0))
        unit_price = m["revenue"] / qty if qty > 0 else 0.0
        unit_cost = m["cost"] / qty if qty > 0 else 0.0
        unit_margin = m["margin"] / qty if qty > 0 else 0.0
        margin_rate = m["margin"] / m["revenue"] if m["revenue"] > 0 else 0.0
        rot = rot_abc.get(sku, "C")
        matrix = margin_abc.get(sku, "C") + rot
        cov = coverage_months(stock, monthly)
        disc_a = option_a_discount(matrix)
        disc_b = option_b_discount(cov, matrix, unit_price, unit_cost)
        exp_bf_units = monthly * BF_UPLIFT
        min_store_need = math.ceil(exp_bf_units * (1 + RESERVE_PCT))
        candidates.append(
            {
                **m,
                "segmento": seg,
                "abc_margen": margin_abc.get(sku, "C"),
                "abc_rotacion": rot,
                "matriz": matrix,
                "stock_total": stock,
                "stock_tiendas": stock_r,
                "venta_mensual_prom": round(monthly, 2),
                "meses_cobertura": round(cov, 2) if cov < 900 else None,
                "precio_unit": round(unit_price, 2),
                "costo_unit": round(unit_cost, 2),
                "margen_unit": round(unit_margin, 2),
                "margen_pct": round(margin_rate * 100, 1),
                "descuento_opcion_a": round(disc_a * 100, 1),
                "descuento_opcion_b": round(disc_b * 100, 1),
                "unidades_bf_estimadas": round(exp_bf_units, 1),
                "stock_objetivo_tiendas": min_store_need,
                "brecha_abastecimiento": max(0, min_store_need - int(stock_r)),
                "prioridad": round(
                    (100 if matrix == "CC" else 55 if matrix == "CB" else 15 if matrix == "CA" else 0)
                    + (min(cov, 24) * 4 if cov < 900 else 0)
                    + (stock_r * 0.08)
                    + (monthly * 0.5 if monthly > 0 else 0),
                    1,
                ),
            }
        )

    candidates.sort(key=lambda x: (-x["prioridad"], -x["stock_total"], -x["margin"]))

    # Model rollup
    models: dict[str, dict] = defaultdict(
        lambda: {
            "skus": 0,
            "stock": 0.0,
            "margin": 0.0,
            "qty": 0.0,
            "segmento": "",
            "matriz_dominante": Counter(),
        }
    )
    for c in candidates:
        mod = c["modelo"]
        models[mod]["skus"] += 1
        models[mod]["stock"] += c["stock_total"]
        models[mod]["margin"] += c["margin"]
        models[mod]["qty"] += c["qty"]
        models[mod]["segmento"] = c["segmento"]
        models[mod]["matriz_dominante"][c["matriz"]] += 1

    model_rows = []
    for mod, v in models.items():
        dom = v["matriz_dominante"].most_common(1)[0][0]
        model_rows.append(
            {
                "modelo": mod,
                "segmento": v["segmento"],
                "skus_c": v["skus"],
                "stock_total": int(v["stock"]),
                "unidades_vendidas_10m": int(v["qty"]),
                "margen_10m": round(v["margin"], 2),
                "matriz_dominante": dom,
            }
        )
    model_rows.sort(key=lambda x: (-x["stock_total"], -x["margen_10m"]))

    # Store supply matrix
    supply_rows = []
    cand_skus = {c["sku"] for c in candidates if c["stock_total"] > 0 or c["stock_tiendas"] > 0}
    for sku in cand_skus:
        meta = next(c for c in candidates if c["sku"] == sku)
        for loc in RETAIL_LOCS:
            q = float(
                stock_by_sku_loc[
                    (stock_by_sku_loc["SKU"] == sku) & (stock_by_sku_loc["Ubicación"] == loc)
                ]["Cantidad en inventario"].sum()
            )
            if q <= 0 and meta["brecha_abastecimiento"] <= 0:
                continue
            share = q / meta["stock_tiendas"] if meta["stock_tiendas"] > 0 else 0
            need = math.ceil(meta["stock_objetivo_tiendas"] * share) if share > 0 else 0
            supply_rows.append(
                {
                    "sku": sku,
                    "modelo": meta["modelo"],
                    "tienda": loc,
                    "stock_actual": int(q),
                    "objetivo_bf": need,
                    "brecha": max(0, need - int(q)),
                    "descuento_a": meta["descuento_opcion_a"],
                    "descuento_b": meta["descuento_opcion_b"],
                }
            )

    supply_rows.sort(key=lambda x: (-x["brecha"], -x["stock_actual"]))

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "periodo_ventas": data["meta"].get("stats", {}).get("rango", "Oct 2025 – Jul 2026"),
        "skus_c_total": len(candidates),
        "skus_con_stock": sum(1 for c in candidates if c["stock_total"] > 0),
        "unidades_stock": int(sum(c["stock_total"] for c in candidates)),
        "unidades_tiendas": int(sum(c["stock_tiendas"] for c in candidates)),
        "margen_historico": round(sum(c["margin"] for c in candidates), 2),
        "brecha_total_unidades": int(sum(c["brecha_abastecimiento"] for c in candidates)),
        "manufactura_skus": sum(1 for c in candidates if c["segmento"] == "Manufactura"),
        "equipamiento_skus": sum(1 for c in candidates if c["segmento"] == "Equipamiento"),
        "matriz_cc": sum(1 for c in candidates if c["matriz"] == "CC"),
    }

    payload = {
        "meta": {
            "title": "Propuesta Black Friday · Categoría C",
            "subtitle": "Manufactura + Equipamiento · baja rotación",
            "abc_source": str(ABC_HTML.name),
            "inventory_source": str(INV_XLSX.name),
            "assumptions": {
                "bf_uplift_vs_mes": BF_UPLIFT,
                "reserve_pct": RESERVE_PCT,
                "margin_floor_opcion_b": 0.08,
            },
        },
        "summary": summary,
        "option_a": {
            "name": "Opción A · Impulso de rotación",
            "description": "Descuentos fijos por matriz margen×rotación (CC 40%, CB 30%, CA 20%). Prioriza vaciar lastre con stock.",
            "avg_discount": round(
                sum(c["descuento_opcion_a"] for c in candidates) / max(len(candidates), 1), 1
            ),
        },
        "option_b": {
            "name": "Opción B · Equilibrio margen–stock",
            "description": "Descuento según meses de cobertura + ajuste CC, con tope para no caer bajo 8% de margen sobre precio.",
            "avg_discount": round(
                sum(c["descuento_opcion_b"] for c in candidates) / max(len(candidates), 1), 1
            ),
        },
        "models": model_rows[:200],
        "skus": candidates,
        "supply": supply_rows[:5000],
        "retail_locations": RETAIL_LOCS,
    }

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    write_excel(payload)
    write_html(payload)

    print(f"SKUs C elegibles: {len(candidates)}")
    print(f"JSON: {OUT_JSON}")
    print(f"Excel: {OUT_XLSX}")
    print(f"HTML: {OUT_HTML}")


def write_excel(payload: dict) -> None:
    skus = pd.DataFrame(payload["skus"])
    models = pd.DataFrame(payload["models"])
    supply = pd.DataFrame(payload["supply"])
    summary = pd.DataFrame([payload["summary"]])

    col_order = [
        "sku",
        "modelo",
        "producto",
        "segmento",
        "categoria",
        "matriz",
        "abc_margen",
        "abc_rotacion",
        "stock_total",
        "stock_tiendas",
        "venta_mensual_prom",
        "meses_cobertura",
        "precio_unit",
        "margen_pct",
        "descuento_opcion_a",
        "descuento_opcion_b",
        "unidades_bf_estimadas",
        "stock_objetivo_tiendas",
        "brecha_abastecimiento",
        "prioridad",
        "genero",
        "color",
        "talla",
    ]
    for c in col_order:
        if c not in skus.columns:
            skus[c] = None
    skus = skus[col_order]

    with pd.ExcelWriter(OUT_XLSX, engine="xlsxwriter") as writer:
        summary.to_excel(writer, sheet_name="Resumen", index=False)
        pd.DataFrame(
            [
                {
                    "Opción": payload["option_a"]["name"],
                    "Descripción": payload["option_a"]["description"],
                    "Descuento prom. %": payload["option_a"]["avg_discount"],
                },
                {
                    "Opción": payload["option_b"]["name"],
                    "Descripción": payload["option_b"]["description"],
                    "Descuento prom. %": payload["option_b"]["avg_discount"],
                },
            ]
        ).to_excel(writer, sheet_name="Opciones BF", index=False)
        models.to_excel(writer, sheet_name="Modelos prioritarios", index=False)
        skus.to_excel(writer, sheet_name="Detalle SKU", index=False)
        supply.to_excel(writer, sheet_name="Abastecimiento tiendas", index=False)

        wb = writer.book
        fmt_pct = wb.add_format({"num_format": "0.0%"})
        for sheet in ("Detalle SKU",):
            ws = writer.sheets[sheet]
            ws.set_column("A:A", 14)
            ws.set_column("B:D", 22)
            ws.freeze_panes(1, 0)


def write_html(payload: dict) -> None:
    data_json = json.dumps(payload, ensure_ascii=False)
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Black Friday · Propuesta Categoría C</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{{
  --bg:#0a0b10;--surf:#12131a;--s2:#1a1b24;--brd:#2e3040;--tx:#eef0f8;--mu:#8b8da8;
  --a:#22d3ee;--b:#fbbf24;--c:#f472b6;--gr:#34d399;--ac:#6366f1;--bf:#ff6b35;
  --fh:'Syne',sans-serif;--fb:'DM Sans',sans-serif;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font-family:var(--fb);min-height:100vh;
  background-image:radial-gradient(ellipse 70% 45% at 50% -15%,rgba(255,107,53,.15),transparent);}}
.hdr{{border-bottom:1px solid var(--brd);padding:18px 28px;display:flex;flex-wrap:wrap;gap:14px;justify-content:space-between;align-items:flex-start}}
.hdr h1{{font-family:var(--fh);font-size:1.45rem;font-weight:800}}
.hdr h1 em{{color:var(--bf);font-style:normal}}
.sub{{color:var(--mu);font-size:.78rem;margin-top:4px;max-width:720px;line-height:1.45}}
.kpis{{display:flex;flex-wrap:wrap;gap:8px}}
.kpi{{background:var(--s2);border:1px solid var(--brd);border-radius:10px;padding:8px 12px;min-width:88px;text-align:center}}
.kpi .v{{font-family:var(--fh);font-size:1.05rem;font-weight:800;color:var(--a)}}
.kpi .l{{font-size:.58rem;color:var(--mu);text-transform:uppercase;margin-top:2px}}
.tabs{{display:flex;gap:0;padding:10px 28px 0;border-bottom:1px solid var(--brd);background:var(--surf);overflow:auto}}
.tab{{padding:8px 14px;font-family:var(--fh);font-size:.72rem;font-weight:700;color:var(--mu);background:transparent;border:none;border-bottom:2px solid transparent;cursor:pointer;white-space:nowrap}}
.tab.active{{color:var(--tx);border-bottom-color:var(--bf)}}
.content{{padding:18px 28px;max-width:1680px;margin:0 auto}}
.sec{{display:none}}.sec.active{{display:block}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}}
.g3{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px}}
.card{{background:var(--surf);border:1px solid var(--brd);border-radius:12px;padding:14px}}
.card h3{{font-family:var(--fh);font-size:.85rem;margin-bottom:4px}}
.card .cs{{font-size:.66rem;color:var(--mu);margin-bottom:10px}}
.opt{{border-radius:10px;padding:12px;border:1px solid var(--brd);background:var(--s2)}}
.opt.a{{border-color:rgba(255,107,53,.45)}}
.opt.b{{border-color:rgba(99,102,241,.45)}}
.opt h4{{font-family:var(--fh);font-size:.82rem;margin-bottom:6px}}
.opt p{{font-size:.72rem;color:var(--mu);line-height:1.45}}
.big{{font-family:var(--fh);font-size:1.6rem;font-weight:800;color:var(--bf)}}
.fbar{{padding:8px 28px;background:var(--surf);border-bottom:1px solid var(--brd);display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
.fbar select,.fbar input{{background:var(--s2);color:var(--tx);border:1px solid var(--brd);border-radius:6px;padding:6px 8px;font-size:.76rem}}
table{{width:100%;border-collapse:collapse;font-size:.73rem}}
th{{text-align:left;font-size:.58rem;text-transform:uppercase;color:var(--mu);padding:6px;border-bottom:1px solid var(--brd);position:sticky;top:0;background:var(--surf)}}
td{{padding:6px;border-bottom:1px solid var(--brd);vertical-align:middle}}
.tscroll{{max-height:520px;overflow:auto}}
.tag{{display:inline-block;padding:2px 7px;border-radius:6px;font-size:.65rem;font-weight:700;font-family:var(--fh)}}
.tag.C{{background:rgba(244,114,182,.15);color:var(--c);border:1px solid rgba(244,114,182,.35)}}
.tag.M{{background:rgba(34,211,238,.12);color:var(--a);border:1px solid rgba(34,211,238,.3)}}
.tag.E{{background:rgba(251,191,36,.12);color:var(--b);border:1px solid rgba(251,191,36,.3)}}
.diag{{font-size:.72rem;line-height:1.45;color:var(--mu);padding:10px;border-radius:8px;background:var(--s2);border:1px solid var(--brd);margin-top:10px}}
.footer{{text-align:center;color:var(--mu);font-size:.62rem;padding:14px;border-top:1px solid var(--brd)}}
@media(max-width:960px){{.g2,.g3{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<header class="hdr">
  <div>
    <h1>Black Friday · <em>Categoría C</em></h1>
    <p class="sub" id="subtitle"></p>
  </div>
  <div class="kpis" id="kpis"></div>
</header>
<div class="fbar">
  <label>Segmento</label><select id="fSeg"><option value="">Todos</option><option>Manufactura</option><option>Equipamiento</option></select>
  <label>Matriz</label><select id="fMat"><option value="">Todas</option><option>CC</option><option>CB</option><option>CA</option></select>
  <label>Buscar</label><input id="fSearch" placeholder="SKU, modelo…">
</div>
<nav class="tabs">
  <button class="tab active" data-tab="resumen">Resumen directiva</button>
  <button class="tab" data-tab="opcion-a">Opción A · Rotación</button>
  <button class="tab" data-tab="opcion-b">Opción B · Equilibrio</button>
  <button class="tab" data-tab="abastecimiento">Abastecimiento tiendas</button>
  <button class="tab" data-tab="detalle">Detalle SKU</button>
</nav>
<main class="content">
  <section class="sec active" id="sec-resumen">
    <div class="g2">
      <div class="card"><h3>Objetivo de campaña</h3><div class="cs">Activación post-aprobación directiva</div>
        <p style="font-size:.78rem;line-height:1.5">Elevar rotación de SKUs clase <strong>C</strong> (margen) en <strong>Manufactura</strong> y <strong>Equipamiento</strong>, liberando capital inmovilizado y garantizando stock en tiendas para el pico de Black Friday.</p>
        <div class="diag" id="assumptions"></div>
      </div>
      <div class="card"><h3>Comparativo de opciones</h3><div class="cs">Dos estrategias de descuento</div>
        <div class="g2" style="grid-template-columns:1fr 1fr;margin-top:8px">
          <div class="opt a" id="cardA"></div>
          <div class="opt b" id="cardB"></div>
        </div>
      </div>
    </div>
    <div class="g2">
      <div class="card"><h3>SKUs por segmento</h3><div class="cw" style="height:220px"><canvas id="cSeg"></canvas></div></div>
      <div class="card"><h3>Matriz margen × rotación</h3><div class="cw" style="height:220px"><canvas id="cMat"></canvas></div></div>
    </div>
    <div class="card"><h3>Top 15 modelos por stock (prioridad)</h3><div class="tscroll"><table><thead><tr>
      <th>Modelo</th><th>Segmento</th><th>SKUs C</th><th>Stock</th><th>Matriz</th><th>Margen 10m</th>
    </tr></thead><tbody id="topModels"></tbody></table></div></div>
  </section>
  <section class="sec" id="sec-opcion-a">
    <div class="card"><h3>Opción A · Impulso de rotación</h3><div class="cs">CC 40% · CB 30% · CA 20%</div>
      <div class="tscroll"><table><thead><tr>
        <th>SKU</th><th>Modelo</th><th>Matriz</th><th>Stock</th><th>Vta/mes</th><th>Cobertura</th><th>% Desc.</th><th>Und. BF est.</th>
      </tr></thead><tbody id="bodyA"></tbody></table></div>
    </div>
  </section>
  <section class="sec" id="sec-opcion-b">
    <div class="card"><h3>Opción B · Equilibrio margen–stock</h3><div class="cs">Por meses de cobertura + tope de margen mínimo 8%</div>
      <div class="tscroll"><table><thead><tr>
        <th>SKU</th><th>Modelo</th><th>Matriz</th><th>Stock</th><th>Cobertura</th><th>Margen %</th><th>% Desc.</th><th>Brecha stock</th>
      </tr></thead><tbody id="bodyB"></tbody></table></div>
    </div>
  </section>
  <section class="sec" id="sec-abastecimiento">
    <div class="card"><h3>Garantía de abastecimiento en tiendas</h3><div class="cs">Stock actual vs objetivo BF (venta mensual × {BF_UPLIFT} + reserva {int(RESERVE_PCT*100)}%)</div>
      <div class="tscroll"><table><thead><tr>
        <th>Tienda</th><th>SKU</th><th>Modelo</th><th>Stock</th><th>Objetivo</th><th>Brecha</th><th>Desc. A</th><th>Desc. B</th>
      </tr></thead><tbody id="bodySupply"></tbody></table></div>
    </div>
  </section>
  <section class="sec" id="sec-detalle">
    <div class="card"><h3>Listado completo · Categoría C</h3><div class="tscroll"><table><thead><tr>
      <th>Prior.</th><th>SKU</th><th>Modelo</th><th>Categoría</th><th>Matriz</th><th>Stock</th><th>%A</th><th>%B</th>
    </tr></thead><tbody id="bodyAll"></tbody></table></div></div>
  </section>
</main>
<footer class="footer">Propuesta generada automáticamente · Base: ABC + inventario actualizado · Uso interno directiva</footer>
<script id="bf-data" type="application/json">{data_json}</script>
<script>
const DATA=JSON.parse(document.getElementById('bf-data').textContent);
const state={{seg:'',mat:'',search:''}};
function $(id){{return document.getElementById(id);}}
function fmt(n,d=0){{return n==null?'—':Number(n).toLocaleString('es-VE',{{minimumFractionDigits:d,maximumFractionDigits:d}});}}
function filtered(){{
  return DATA.skus.filter(r=>{{
    if(state.seg && r.segmento!==state.seg) return false;
    if(state.mat && r.matriz!==state.mat) return false;
    if(state.search){{
      const q=state.search.toLowerCase();
      if(!(r.sku+' '+r.modelo+' '+r.producto).toLowerCase().includes(q)) return false;
    }}
    return true;
  }});
}}
function tab(name){{
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.dataset.tab===name));
  document.querySelectorAll('.sec').forEach(s=>s.classList.toggle('active',s.id==='sec-'+name));
}}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>tab(t.dataset.tab));
function renderKpis(){{
  const s=DATA.summary;
  $('subtitle').textContent=DATA.meta.subtitle+' · '+s.periodo_ventas;
  $('kpis').innerHTML=[
    ['SKUs C',s.skus_c_total],['Con stock',s.skus_con_stock],['Und. stock',s.unidades_stock],
    ['Brecha tiendas',s.brecha_total_unidades],['Matriz CC',s.matriz_cc]
  ].map(([l,v])=>'<div class="kpi"><div class="v">'+fmt(v)+'</div><div class="l">'+l+'</div></div>').join('');
  const a=DATA.option_a,b=DATA.option_b;
  $('cardA').innerHTML='<h4>'+a.name+'</h4><div class="big">'+a.avg_discount+'%</div><p>'+a.description+'</p>';
  $('cardB').innerHTML='<h4>'+b.name+'</h4><div class="big">'+b.avg_discount+'%</div><p>'+b.description+'</p>';
  const as=DATA.meta.assumptions;
  $('assumptions').innerHTML='Hipótesis: uplift BF ×'+as.bf_uplift_vs_mes+' vs venta mensual promedio ('+s.periodo_ventas+'). Reserva post-campaña '+Math.round(as.reserve_pct*100)+'%. Opción B piso margen '+(as.margin_floor_opcion_b*100)+'% sobre precio lista.';
}}
function renderTables(){{
  const rows=filtered();
  $('bodyA').innerHTML=rows.slice(0,400).map(r=>'<tr><td>'+r.sku+'</td><td>'+r.modelo+'</td><td><span class="tag C">'+r.matriz+'</span></td><td>'+fmt(r.stock_total)+'</td><td>'+fmt(r.venta_mensual_prom,1)+'</td><td>'+(r.meses_cobertura??'—')+'</td><td><strong>'+r.descuento_opcion_a+'%</strong></td><td>'+fmt(r.unidades_bf_estimadas,1)+'</td></tr>').join('');
  $('bodyB').innerHTML=rows.slice(0,400).map(r=>'<tr><td>'+r.sku+'</td><td>'+r.modelo+'</td><td>'+r.matriz+'</td><td>'+fmt(r.stock_total)+'</td><td>'+(r.meses_cobertura??'—')+'</td><td>'+r.margen_pct+'%</td><td><strong>'+r.descuento_opcion_b+'%</strong></td><td>'+fmt(r.brecha_abastecimiento)+'</td></tr>').join('');
  $('bodyAll').innerHTML=rows.map(r=>'<tr><td>'+r.prioridad+'</td><td>'+r.sku+'</td><td>'+r.modelo+'</td><td>'+r.categoria+'</td><td>'+r.matriz+'</td><td>'+fmt(r.stock_total)+'</td><td>'+r.descuento_opcion_a+'%</td><td>'+r.descuento_opcion_b+'%</td></tr>').join('');
  $('bodySupply').innerHTML=DATA.supply.filter(r=>{{
    if(!state.search) return true;
    const q=state.search.toLowerCase();
    return (r.sku+' '+r.modelo+' '+r.tienda).toLowerCase().includes(q);
  }}).slice(0,500).map(r=>'<tr><td>'+r.tienda+'</td><td>'+r.sku+'</td><td>'+r.modelo+'</td><td>'+fmt(r.stock_actual)+'</td><td>'+fmt(r.objetivo_bf)+'</td><td>'+fmt(r.brecha)+'</td><td>'+r.descuento_a+'%</td><td>'+r.descuento_b+'%</td></tr>').join('');
  $('topModels').innerHTML=DATA.models.slice(0,15).map(m=>'<tr><td>'+m.modelo+'</td><td>'+m.segmento+'</td><td>'+m.skus_c+'</td><td>'+fmt(m.stock_total)+'</td><td>'+m.matriz_dominante+'</td><td>'+fmt(m.margen_10m,0)+'</td></tr>').join('');
}}
let charts={{}};
function renderCharts(){{
  const seg={{Manufactura:0,Equipamiento:0}};
  const mat={{CC:0,CB:0,CA:0,Other:0}};
  DATA.skus.forEach(r=>{{seg[r.segmento]=(seg[r.segmento]||0)+1; if(mat[r.matriz]!=null) mat[r.matriz]++; else mat.Other++;}});
  if(charts.seg) charts.seg.destroy();
  charts.seg=new Chart($('cSeg'),{{type:'doughnut',data:{{labels:Object.keys(seg),datasets:[{{data:Object.values(seg),backgroundColor:['rgba(34,211,238,.8)','rgba(251,191,36,.8)']}}]}},options:{{plugins:{{legend:{{position:'bottom'}}}},maintainAspectRatio:false}}}});
  if(charts.mat) charts.mat.destroy();
  charts.mat=new Chart($('cMat'),{{type:'bar',data:{{labels:['CC','CB','CA','Otros'],datasets:[{{label:'SKUs',data:[mat.CC,mat.CB,mat.CA,mat.Other],backgroundColor:['rgba(244,114,182,.75)','rgba(251,191,36,.65)','rgba(34,211,238,.55)','rgba(120,120,140,.4)']}}]}},options:{{plugins:{{legend:{{display:false}}}},scales:{{x:{{grid:{{display:false}}}},y:{{grid:{{color:'rgba(255,255,255,.06)'}}}}}},maintainAspectRatio:false}}}});
}}
function refresh(){{renderTables();}}
['fSeg','fMat'].forEach(id=>$(id).onchange=e=>{{state[id==='fSeg'?'seg':'mat']=e.target.value;refresh();}});
$('fSearch').oninput=e=>{{state.search=e.target.value;refresh();}};
renderKpis();renderTables();renderCharts();
</script>
</body>
</html>"""
    OUT_HTML.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
