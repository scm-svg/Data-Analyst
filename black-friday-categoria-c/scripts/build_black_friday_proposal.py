#!/usr/bin/env python3
"""
Propuesta Black Friday — Categoría C (Manufactura + Equipamiento).

Fuentes:
  - Inventario y ventas: Excel actualizados (stock y rotación reales).
  - Clasificación margen C + categoría: dashboard ABC embebido (guía).
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = Path("/home/ubuntu/.cursor/projects/workspace/uploads")
ABC_HTML = UPLOADS / "abc_ver_fcbe.html"
INV_XLSX = UPLOADS / "INVENTARIO_TOTAL_CUADRO_PARA_ABC_-_PROPUESTA_1e41.xlsx"
SALES_XLSX = UPLOADS / "VENTAS_CUADRO_ACTUALIZADAS_ARREGLADO_29b1.xlsx"
OUT_JSON = ROOT / "bf_proposal_data.json"
OUT_HTML = ROOT / "black_friday_propuesta_categoria_c.html"
OUT_XLSX = ROOT / "BLACK_FRIDAY_PROPUESTA_CATEGORIA_C.xlsx"

TH_A, TH_B = 0.8, 0.95
SALES_PERIOD_LABEL = "Octubre 2025 → Julio 2026"
SALES_MONTHS = 10
BF_UPLIFT = 4.0
RESERVE_PCT = 0.15
RETAIL_LOCS = [
    "CERRO VERDE",
    "CHACAO",
    "GRANDPLAZ",
    "GRIETA",
    "SAMBIL",
    "TOLON",
    "VELA",
]
def clean_cell(val, fallback: str = "") -> str:
    if val is None:
        return fallback
    try:
        if pd.isna(val):
            return fallback
    except (TypeError, ValueError):
        pass
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return fallback
    text = str(val).strip()
    return fallback if text.lower() == "nan" else text


def sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return obj


MONTH_ORDER = {
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
}


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
    """Clasifica todos los ítems; qty=0 queda en la cola (clase C)."""
    ordered = sorted(values, key=lambda x: (-x[1], x[0]))
    total = sum(v for _, v in ordered) or 1.0
    cum = 0.0
    out: dict[str, str] = {}
    for k, v in ordered:
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


def segment(cat: str) -> str | None:
    if cat.startswith("Equipamiento"):
        return "Equipamiento"
    if cat.startswith("Manufactura"):
        return "Manufactura"
    return None


def is_excluded_model(modelo: str, producto: str = "") -> bool:
    m = f"{modelo} {producto}".upper()
    if "CUADRO BAND" in m:
        return True
    if "SHORT PLAYA" in m:
        return True
    if "CLASICA GC SUBLIMADO KIDS" in m or "CLÁSICA GC SUBLIMADO KIDS" in m:
        return True
    return False


def sales_in_analysis_period(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["m"] = df["Mes"].astype(str).str.lower().str.strip().map(MONTH_ORDER)
    return df[
        ((df["Año"] == 2025) & (df["m"] >= 10))
        | ((df["Año"] == 2026) & (df["m"] <= 7))
    ]


def max_discount_for_margin_floor(unit_price: float, unit_cost: float, floor_rate: float) -> float:
    if unit_price <= 0:
        return 0.0
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


def build_abc_margin_guide(data: dict) -> tuple[dict[str, dict], dict[str, str]]:
    skus = data["skus"]
    sku_master = data["skuMaster"]
    period_keys = {p["key"] for p in data["periods"]}
    metrics: dict[str, dict] = {}
    for row in data["salesRows"]:
        if data["periods"][row[0]]["key"] not in period_keys:
            continue
        sku = skus[row[1]]
        if sku not in metrics:
            meta = sku_master.get(sku, {})
            metrics[sku] = {
                "producto": meta.get("producto") or sku,
                "modelo": meta.get("modelo") or meta.get("producto") or sku,
                "categoria": meta.get("categoria") or "",
                "genero": meta.get("genero") or "",
                "color": meta.get("color") or "",
                "talla": meta.get("talla") or "",
                "qty": 0.0,
                "revenue": 0.0,
                "cost": 0.0,
                "margin": 0.0,
            }
        o = metrics[sku]
        o["qty"] += row[4]
        o["revenue"] += row[5]
        o["cost"] += row[6]
        o["margin"] += row[7]
    margin_abc = pareto_abc([(s, v["margin"]) for s, v in metrics.items() if v["margin"] > 0])
    return metrics, margin_abc


def main() -> None:
    if not INV_XLSX.exists() or not SALES_XLSX.exists():
        raise FileNotFoundError("Faltan Excel actualizados de inventario o ventas en uploads/")

    data = load_embedded_abc(ABC_HTML)
    abc_metrics, margin_abc = build_abc_margin_guide(data)

    inv_df = pd.read_excel(INV_XLSX)
    inv_df["Ubicación"] = inv_df["Ubicación"].astype(str).str.upper().str.strip()
    inv_df["SKU"] = inv_df["SKU"].astype(str).str.strip()
    inv_df["MODELO"] = inv_df["MODELO"].astype(str).str.strip()
    inv_df["Producto"] = inv_df["Producto"].astype(str)

    inv_df = inv_df[~inv_df.apply(lambda r: is_excluded_model(r["MODELO"], r["Producto"]), axis=1)]

    stock_by_sku = inv_df.groupby("SKU").agg(
        stock_total=("Cantidad en inventario", "sum"),
        modelo_inv=("MODELO", "first"),
        producto_inv=("Producto", "first"),
        genero_inv=("GENERO", "first"),
        color_inv=("COLOR", "first"),
        talla_inv=("TALLA", "first"),
    )
    stock_by_sku = stock_by_sku[stock_by_sku["stock_total"] > 0].reset_index()

    stock_by_sku_loc = (
        inv_df.groupby(["SKU", "Ubicación"], as_index=False)["Cantidad en inventario"].sum()
    )
    stock_retail = (
        inv_df[inv_df["Ubicación"].isin(RETAIL_LOCS)]
        .groupby("SKU")["Cantidad en inventario"]
        .sum()
        .to_dict()
    )

    sales_df = pd.read_excel(SALES_XLSX)
    sales_df["SKU"] = sales_df["SKU"].astype(str).str.strip()
    sales_period = sales_in_analysis_period(sales_df)
    qty_by_sku = sales_period.groupby("SKU")["Cant. ordenada"].sum().to_dict()
    modelo_sales = sales_period.groupby("SKU")["modelo"].first().to_dict()

    rot_abc = pareto_abc([(row.SKU, float(qty_by_sku.get(row.SKU, 0))) for row in stock_by_sku.itertuples()])

    candidates: list[dict] = []
    excluded_stats = Counter()

    for row in stock_by_sku.itertuples():
        sku = row.SKU
        stock = float(row.stock_total)
        if stock <= 0:
            continue

        if margin_abc.get(sku) != "C":
            excluded_stats["margen_no_c"] += 1
            continue

        abc = abc_metrics.get(sku)
        if not abc:
            excluded_stats["sin_guia_abc"] += 1
            continue

        seg = segment(abc["categoria"])
        if not seg:
            excluded_stats["fuera_segmento"] += 1
            continue

        rot = rot_abc.get(sku, "C")
        if rot != "C":
            excluded_stats["rotacion_no_c"] += 1
            continue

        matrix = "C" + rot
        qty = float(qty_by_sku.get(sku, 0))
        monthly = qty / SALES_MONTHS
        stock_r = float(stock_retail.get(sku, 0))

        unit_price = abc["revenue"] / abc["qty"] if abc["qty"] > 0 else 0.0
        unit_cost = abc["cost"] / abc["qty"] if abc["qty"] > 0 else 0.0
        unit_margin = abc["margin"] / abc["qty"] if abc["qty"] > 0 else 0.0
        margin_rate = abc["margin"] / abc["revenue"] if abc["revenue"] > 0 else 0.0

        cov = coverage_months(stock, monthly)
        disc_a = option_a_discount(matrix)
        disc_b = option_b_discount(cov, matrix, unit_price, unit_cost)
        exp_bf_units = monthly * BF_UPLIFT
        min_store_need = math.ceil(exp_bf_units * (1 + RESERVE_PCT)) if monthly > 0 else max(1, int(stock_r * 0.1))

        modelo = clean_cell(row.modelo_inv) or clean_cell(abc["modelo"]) or clean_cell(modelo_sales.get(sku), sku)
        candidates.append(
            {
                "sku": sku,
                "producto": clean_cell(row.producto_inv) or clean_cell(abc["producto"], sku),
                "modelo": modelo,
                "categoria": clean_cell(abc["categoria"]),
                "genero": clean_cell(row.genero_inv) or clean_cell(abc["genero"]),
                "color": clean_cell(row.color_inv) or clean_cell(abc["color"]),
                "talla": clean_cell(row.talla_inv) or clean_cell(abc["talla"]),
                "qty": qty,
                "revenue": abc["revenue"],
                "cost": abc["cost"],
                "margin": abc["margin"],
                "segmento": seg,
                "abc_margen": "C",
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
                    100
                    + (min(cov, 24) * 4 if cov < 900 else 0)
                    + (stock_r * 0.08)
                    + (monthly * 0.5 if monthly > 0 else 0),
                    1,
                ),
            }
        )

    candidates.sort(key=lambda x: (-x["prioridad"], -x["stock_total"], -x["margin"]))

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

    supply_rows = []
    for c in candidates:
        sku = c["sku"]
        for loc in RETAIL_LOCS:
            q = float(
                stock_by_sku_loc[
                    (stock_by_sku_loc["SKU"] == sku) & (stock_by_sku_loc["Ubicación"] == loc)
                ]["Cantidad en inventario"].sum()
            )
            if q <= 0:
                continue
            share = q / c["stock_tiendas"] if c["stock_tiendas"] > 0 else 1.0
            need = math.ceil(c["stock_objetivo_tiendas"] * share) if c["stock_tiendas"] > 0 else int(q)
            supply_rows.append(
                {
                    "sku": sku,
                    "modelo": c["modelo"],
                    "tienda": loc,
                    "stock_actual": int(q),
                    "objetivo_bf": need,
                    "brecha": max(0, need - int(q)),
                    "descuento_a": c["descuento_opcion_a"],
                    "descuento_b": c["descuento_opcion_b"],
                }
            )
    supply_rows.sort(key=lambda x: (-x["brecha"], -x["stock_actual"]))

    assert all(c["stock_total"] > 0 for c in candidates), "Hay SKUs sin stock en la propuesta"

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "periodo_ventas": SALES_PERIOD_LABEL,
        "skus_c_total": len(candidates),
        "skus_con_stock": len(candidates),
        "unidades_stock": int(sum(c["stock_total"] for c in candidates)),
        "unidades_tiendas": int(sum(c["stock_tiendas"] for c in candidates)),
        "margen_historico": round(sum(c["margin"] for c in candidates), 2),
        "brecha_total_unidades": int(sum(c["brecha_abastecimiento"] for c in candidates)),
        "manufactura_skus": sum(1 for c in candidates if c["segmento"] == "Manufactura"),
        "equipamiento_skus": sum(1 for c in candidates if c["segmento"] == "Equipamiento"),
        "matriz_cc": sum(1 for c in candidates if c["matriz"] == "CC"),
        "excluidos": dict(excluded_stats),
    }

    payload = {
        "meta": {
            "title": "Propuesta Black Friday · Categoría C",
            "subtitle": "Solo con inventario · baja rotación · Manufactura + Equipamiento",
            "abc_source": str(ABC_HTML.name),
            "inventory_source": str(INV_XLSX.name),
            "sales_source": str(SALES_XLSX.name),
            "rules": [
                "Inventario Excel: solo SKUs con stock > 0",
                "Ventas Excel Oct 2025 – Jul 2026: rotación C (baja salida)",
                "Guía ABC: margen C + categoría Manufactura/Equipamiento",
                "Excluidos: CUADRO BAND, SHORT PLAYA, CLASICA GC SUBLIMADO KIDS",
            ],
            "assumptions": {
                "bf_uplift_vs_mes": BF_UPLIFT,
                "reserve_pct": RESERVE_PCT,
                "margin_floor_opcion_b": 0.08,
            },
        },
        "summary": summary,
        "option_a": {
            "name": "Opción A · Impulso de rotación",
            "description": "CC 40% (listado prioriza matriz CC con stock disponible).",
            "avg_discount": round(
                sum(c["descuento_opcion_a"] for c in candidates) / max(len(candidates), 1), 1
            ),
        },
        "option_b": {
            "name": "Opción B · Equilibrio margen–stock",
            "description": "Descuento por meses de cobertura (stock ÷ venta mensual Excel), tope margen 8%.",
            "avg_discount": round(
                sum(c["descuento_opcion_b"] for c in candidates) / max(len(candidates), 1), 1
            ),
        },
        "models": model_rows[:200],
        "skus": candidates,
        "supply": supply_rows[:5000],
        "retail_locations": RETAIL_LOCS,
    }

    payload = sanitize_for_json(payload)
    OUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    write_excel(payload)
    write_html(payload)

    print(f"SKUs propuesta (stock>0, margen C, rotación C): {len(candidates)}")
    print(f"Excluidos: {dict(excluded_stats)}")
    print(f"JSON: {OUT_JSON}")
    print(f"Excel: {OUT_XLSX}")
    print(f"HTML: {OUT_HTML}")


def write_excel(payload: dict) -> None:
    skus = pd.DataFrame(payload["skus"])
    models = pd.DataFrame(payload["models"])
    supply = pd.DataFrame(payload["supply"])
    summary = pd.DataFrame([payload["summary"]])
    rules = pd.DataFrame({"Regla": payload["meta"]["rules"]})

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
        rules.to_excel(writer, sheet_name="Reglas alcance", index=False)
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
        ws = writer.sheets["Detalle SKU"]
        ws.set_column("A:A", 14)
        ws.set_column("B:D", 22)
        ws.freeze_panes(1, 0)


def write_html(payload: dict) -> None:
    data_json = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    rules_html = "".join(f"<li>{r}</li>" for r in payload["meta"]["rules"])
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
.sub{{color:var(--mu);font-size:.78rem;margin-top:4px;max-width:820px;line-height:1.45}}
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
.diag{{font-size:.72rem;line-height:1.45;color:var(--mu);padding:10px;border-radius:8px;background:var(--s2);border:1px solid var(--brd);margin-top:10px}}
.diag ul{{margin:8px 0 0 18px}}
.footer{{text-align:center;color:var(--mu);font-size:.62rem;padding:14px;border-top:1px solid var(--brd)}}
@media(max-width:960px){{.g2{{grid-template-columns:1fr}}}}
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
      <div class="card"><h3>Alcance corregido</h3><div class="cs">Excel inventario + ventas (actualizados)</div>
        <ul style="font-size:.76rem;line-height:1.55;margin-left:18px;color:var(--tx)">{rules_html}</ul>
        <div class="diag" id="assumptions"></div>
      </div>
      <div class="card"><h3>Comparativo de opciones</h3><div class="cs">Solo productos ofertables (stock &gt; 0)</div>
        <div class="g2" style="grid-template-columns:1fr 1fr;margin-top:8px">
          <div class="opt a" id="cardA"></div>
          <div class="opt b" id="cardB"></div>
        </div>
      </div>
    </div>
    <div class="g2">
      <div class="card"><h3>SKUs por segmento</h3><div class="cw" style="height:220px"><canvas id="cSeg"></canvas></div></div>
      <div class="card"><h3>Período ventas</h3><div class="cs">Fuente: Excel ventas</div>
        <p style="font-size:1.1rem;font-family:var(--fh);font-weight:800;margin-top:12px" id="periodLabel"></p>
        <p style="font-size:.72rem;color:var(--mu);margin-top:8px">Rotación calculada sobre unidades vendidas en este rango (no incluye ago–sep 2026).</p>
      </div>
    </div>
    <div class="card"><h3>Top 15 modelos por stock</h3><div class="tscroll"><table><thead><tr>
      <th>Modelo</th><th>Segmento</th><th>SKUs</th><th>Stock</th><th>Und. vendidas</th><th>Margen guía</th>
    </tr></thead><tbody id="topModels"></tbody></table></div></div>
  </section>
  <section class="sec" id="sec-opcion-a">
    <div class="card"><h3>Opción A · Impulso de rotación</h3><div class="cs">Matriz CC · 40%</div>
      <div class="tscroll"><table><thead><tr>
        <th>SKU</th><th>Modelo</th><th>Stock</th><th>Vta/mes</th><th>Cobertura</th><th>% Desc.</th>
      </tr></thead><tbody id="bodyA"></tbody></table></div>
    </div>
  </section>
  <section class="sec" id="sec-opcion-b">
    <div class="card"><h3>Opción B · Equilibrio margen–stock</h3>
      <div class="tscroll"><table><thead><tr>
        <th>SKU</th><th>Modelo</th><th>Stock</th><th>Cobertura</th><th>% Desc.</th><th>Brecha</th>
      </tr></thead><tbody id="bodyB"></tbody></table></div>
    </div>
  </section>
  <section class="sec" id="sec-abastecimiento">
    <div class="card"><h3>Garantía de abastecimiento</h3><div class="cs">Solo filas con stock en tienda &gt; 0</div>
      <div class="tscroll"><table><thead><tr>
        <th>Tienda</th><th>SKU</th><th>Modelo</th><th>Stock</th><th>Objetivo</th><th>Brecha</th>
      </tr></thead><tbody id="bodySupply"></tbody></table></div>
    </div>
  </section>
  <section class="sec" id="sec-detalle">
    <div class="card"><h3>Listado ofertable</h3><div class="tscroll"><table><thead><tr>
      <th>Prior.</th><th>SKU</th><th>Modelo</th><th>Stock</th><th>Vta 10m</th><th>%A</th><th>%B</th>
    </tr></thead><tbody id="bodyAll"></tbody></table></div></div>
  </section>
</main>
<footer class="footer">Inventario y ventas: Excel · Margen C: guía ABC · Período ventas Oct 2025 – Jul 2026</footer>
<script id="bf-data" type="application/json">{data_json}</script>
<script>
const DATA=JSON.parse(document.getElementById('bf-data').textContent);
const state={{seg:'',search:''}};
function $(id){{return document.getElementById(id);}}
function fmt(n,d=0){{return n==null?'—':Number(n).toLocaleString('es-VE',{{minimumFractionDigits:d,maximumFractionDigits:d}});}}
function filtered(){{
  return DATA.skus.filter(r=>{{
    if(state.seg && r.segmento!==state.seg) return false;
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
  $('periodLabel').textContent=s.periodo_ventas;
  $('kpis').innerHTML=[
    ['SKUs ofertables',s.skus_c_total],['Und. stock',s.unidades_stock],['En tiendas',s.unidades_tiendas],
    ['Manufactura',s.manufactura_skus],['Brecha BF',s.brecha_total_unidades]
  ].map(([l,v])=>'<div class="kpi"><div class="v">'+fmt(v)+'</div><div class="l">'+l+'</div></div>').join('');
  $('cardA').innerHTML='<h4>'+DATA.option_a.name+'</h4><div class="big">'+DATA.option_a.avg_discount+'%</div><p>'+DATA.option_a.description+'</p>';
  $('cardB').innerHTML='<h4>'+DATA.option_b.name+'</h4><div class="big">'+DATA.option_b.avg_discount+'%</div><p>'+DATA.option_b.description+'</p>';
  const as=DATA.meta.assumptions;
  $('assumptions').innerHTML='Uplift BF ×'+as.bf_uplift_vs_mes+' vs venta mensual (Excel). Reserva '+Math.round(as.reserve_pct*100)+'%.';
}}
function renderTables(){{
  const rows=filtered();
  $('bodyA').innerHTML=rows.map(r=>'<tr><td>'+r.sku+'</td><td>'+r.modelo+'</td><td><strong>'+fmt(r.stock_total)+'</strong></td><td>'+fmt(r.venta_mensual_prom,1)+'</td><td>'+(r.meses_cobertura??'—')+'</td><td><strong>'+r.descuento_opcion_a+'%</strong></td></tr>').join('');
  $('bodyB').innerHTML=rows.map(r=>'<tr><td>'+r.sku+'</td><td>'+r.modelo+'</td><td><strong>'+fmt(r.stock_total)+'</strong></td><td>'+(r.meses_cobertura??'—')+'</td><td><strong>'+r.descuento_opcion_b+'%</strong></td><td>'+fmt(r.brecha_abastecimiento)+'</td></tr>').join('');
  $('bodyAll').innerHTML=rows.map(r=>'<tr><td>'+r.prioridad+'</td><td>'+r.sku+'</td><td>'+r.modelo+'</td><td><strong>'+fmt(r.stock_total)+'</strong></td><td>'+fmt(r.qty)+'</td><td>'+r.descuento_opcion_a+'%</td><td>'+r.descuento_opcion_b+'%</td></tr>').join('');
  $('bodySupply').innerHTML=DATA.supply.filter(r=>{{
    if(!state.search) return true;
    const q=state.search.toLowerCase();
    return (r.sku+' '+r.modelo+' '+r.tienda).toLowerCase().includes(q);
  }}).slice(0,800).map(r=>'<tr><td>'+r.tienda+'</td><td>'+r.sku+'</td><td>'+r.modelo+'</td><td>'+fmt(r.stock_actual)+'</td><td>'+fmt(r.objetivo_bf)+'</td><td>'+fmt(r.brecha)+'</td></tr>').join('');
  $('topModels').innerHTML=DATA.models.slice(0,15).map(m=>'<tr><td>'+m.modelo+'</td><td>'+m.segmento+'</td><td>'+m.skus_c+'</td><td>'+fmt(m.stock_total)+'</td><td>'+fmt(m.unidades_vendidas_10m)+'</td><td>'+fmt(m.margen_10m,0)+'</td></tr>').join('');
}}
let charts={{}};
function renderCharts(){{
  const seg={{Manufactura:0,Equipamiento:0}};
  DATA.skus.forEach(r=>{{seg[r.segmento]=(seg[r.segmento]||0)+1;}});
  if(charts.seg) charts.seg.destroy();
  charts.seg=new Chart($('cSeg'),{{type:'doughnut',data:{{labels:Object.keys(seg),datasets:[{{data:Object.values(seg),backgroundColor:['rgba(34,211,238,.8)','rgba(251,191,36,.8)']}}]}},options:{{plugins:{{legend:{{position:'bottom'}}}},maintainAspectRatio:false}}}});
}}
['fSeg'].forEach(id=>$(id).onchange=e=>{{state.seg=e.target.value;renderTables();}});
$('fSearch').oninput=e=>{{state.search=e.target.value;renderTables();}};
renderKpis();renderTables();renderCharts();
</script>
</body>
</html>"""
    OUT_HTML.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
