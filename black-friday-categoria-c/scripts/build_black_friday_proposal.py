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
OUT_JS = ROOT / "bf_proposal_data.js"
OUT_HTML = ROOT / "black_friday_propuesta_categoria_c.html"
OUT_XLSX = ROOT / "BLACK_FRIDAY_PROPUESTA_CATEGORIA_C.xlsx"
DASHBOARD_APP_SRC = Path(__file__).resolve().parent / "dashboard_app.js"
DASHBOARD_APP_OUT = ROOT / "dashboard_app.js"

TH_A, TH_B = 0.8, 0.95
MIN_STOCK_UNITS = 29  # stock > 28
EXCLUDED_MATRICES = frozenset({"AA", "BA"})
RETAIL_LOCS = [
    "CERRO VERDE",
    "CHACAO",
    "GRANDPLAZ",
    "GRIETA",
    "SAMBIL",
    "TOLON",
    "VELA",
]


def is_taller_location(loc: str) -> bool:
    return str(loc).upper().strip().startswith("TALLER")
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
    excluded_fragments = (
        "CUADRO BAND",
        "SHORT PLAYA",
        "CLASICA GC SUBLIMADO KIDS",
        "CLÁSICA GC SUBLIMADO KIDS",
        "MOTION LOOP",
        "RIO ORIGINAL",
        "MAR ORIGINAL",
        "EXPLORE PANTS",
        "CUADRO JACKET 2.0",
    )
    return any(x in m for x in excluded_fragments)


PRIORITY_MODELS_EXACT = frozenset(
    {
        "JACKET CAB",
        "JACKET DAMA",
        "JACKET KIDS",
        "ANDRE MOTION DAMA",
        "NOAH SPORT LITE CAB",
        "MAXI TOTE",
        "BASIC LINE SHORT DAMA",
        "MAFE ADVANCE DAMA",
        "CLASICA ADVANCE CAB",
        "RETRO VZLA CAB",
        "RETRO VZLA DAMA",
        "RETRO VZLA KIDS",
    }
)
PRIORITY_MODEL_PREFIXES = ("ANKLE SOCKS", "CREW SOCKS", "NO SHOW SOCKS")


def is_priority_full_variant(modelo: str) -> bool:
    """Modelos con todas las variantes SKU (reglas ABC relajadas)."""
    m = clean_cell(modelo).upper()
    if m in PRIORITY_MODELS_EXACT:
        return True
    return any(m.startswith(p) for p in PRIORITY_MODEL_PREFIXES)


def sales_scope(df: pd.DataFrame) -> tuple[pd.DataFrame, str, int, list[str]]:
    """Todos los meses presentes en el Excel de ventas."""
    df = df.copy()
    df["m"] = df["Mes"].astype(str).str.lower().str.strip().map(MONTH_ORDER)
    df["Año"] = pd.to_numeric(df["Año"], errors="coerce")
    df = df.dropna(subset=["m", "Año"])
    periods = (
        df.groupby(["Año", "m"], as_index=False)
        .agg(mes_label=("Mes", "first"))
        .sort_values(["Año", "m"])
    )
    if periods.empty:
        return df.iloc[0:0], "Sin datos de ventas", 1, []

    def cap_month(s: str) -> str:
        return str(s).strip().capitalize()

    first, last = periods.iloc[0], periods.iloc[-1]
    label = (
        f"{cap_month(first.mes_label)} {int(first.Año)} → "
        f"{cap_month(last.mes_label)} {int(last.Año)}"
    )
    months_list = [f"{cap_month(r.mes_label)} {int(r.Año)}" for r in periods.itertuples()]
    return df, label, len(periods), months_list


def coverage_months(stock: float, monthly_qty: float) -> float:
    if monthly_qty <= 0:
        return 999.0 if stock > 0 else 0.0
    return stock / monthly_qty


def build_sku_candidate(
    sku: str,
    stock: float,
    modelo: str,
    inv_row,
    abc: dict | None,
    *,
    sales_months: int,
    qty_by_sku: dict,
    stock_retail: dict,
    stock_taller: dict,
    margin_abc: dict,
    rot_abc: dict,
    priority: bool,
) -> dict | None:
    if stock <= 0:
        return None
    if not priority and stock < MIN_STOCK_UNITS:
        return None
    if not abc:
        return None
    seg = segment(abc.get("categoria") or "")
    if not seg:
        return None
    mcls = margin_abc.get(sku, "C")
    if mcls != "C" and not priority:
        return None
    rot = rot_abc.get(sku, "C")
    if rot != "C" and not priority:
        return None
    qty = float(qty_by_sku.get(sku, 0))
    rotacion_mes = qty / sales_months
    stock_r = float(stock_retail.get(sku, 0))
    stock_t = float(stock_taller.get(sku, 0))
    cov = coverage_months(stock, rotacion_mes)
    matriz = mcls + rot
    if matriz in EXCLUDED_MATRICES:
        return None
    return {
        "sku": sku,
        "producto": clean_cell(getattr(inv_row, "producto_inv", "")) or clean_cell(abc.get("producto"), sku),
        "modelo": modelo,
        "categoria": clean_cell(abc.get("categoria")),
        "genero": clean_cell(getattr(inv_row, "genero_inv", "")) or clean_cell(abc.get("genero")),
        "color": clean_cell(getattr(inv_row, "color_inv", "")) or clean_cell(abc.get("color")),
        "talla": clean_cell(getattr(inv_row, "talla_inv", "")) or clean_cell(abc.get("talla")),
        "qty": qty,
        "margin": abc.get("margin", 0),
        "segmento": seg,
        "abc_margen": mcls,
        "abc_rotacion": rot,
        "matriz": matriz,
        "stock_total": stock,
        "stock_tiendas": stock_r,
        "stock_taller": stock_t,
        "rotacion_mes": round(rotacion_mes, 2),
        "meses_cobertura": round(cov, 2) if cov < 900 else None,
        "prioridad": round(
            100 + (min(cov, 24) * 4 if cov < 900 else 0) + (stock_r * 0.08) + (rotacion_mes * 0.5 if rotacion_mes > 0 else 0),
            1,
        ),
        "priority_line": priority,
    }


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

    stock_retail = (
        inv_df[inv_df["Ubicación"].isin(RETAIL_LOCS)]
        .groupby("SKU")["Cantidad en inventario"]
        .sum()
        .to_dict()
    )
    stock_taller = (
        inv_df[inv_df["Ubicación"].apply(is_taller_location)]
        .groupby("SKU")["Cantidad en inventario"]
        .sum()
        .to_dict()
    )

    sales_df = pd.read_excel(SALES_XLSX)
    sales_df["SKU"] = sales_df["SKU"].astype(str).str.strip()
    sales_period, period_label, sales_months, months_list = sales_scope(sales_df)
    qty_by_sku = sales_period.groupby("SKU")["Cant. ordenada"].sum().to_dict()
    modelo_sales = sales_period.groupby("SKU")["modelo"].first().to_dict()

    rot_abc = pareto_abc([(row.SKU, float(qty_by_sku.get(row.SKU, 0))) for row in stock_by_sku.itertuples()])

    candidates: list[dict] = []
    excluded_stats = Counter()

    stock_lookup = {r.SKU: r for r in stock_by_sku.itertuples()}

    for row in stock_by_sku.itertuples():
        sku = row.SKU
        stock = float(row.stock_total)
        abc = abc_metrics.get(sku)
        modelo = (
            clean_cell(row.modelo_inv)
            or (clean_cell(abc["modelo"]) if abc else "")
            or clean_cell(modelo_sales.get(sku), sku)
        )
        priority = is_priority_full_variant(modelo)
        if is_excluded_model(modelo, row.producto_inv):
            excluded_stats["modelo_excluido"] += 1
            continue
        if stock < MIN_STOCK_UNITS and not priority:
            excluded_stats["stock_bajo_28"] += 1
            continue
        if margin_abc.get(sku) != "C" and not priority:
            excluded_stats["margen_no_c"] += 1
            continue
        if not abc:
            excluded_stats["sin_guia_abc"] += 1
            continue
        if not segment(abc["categoria"]):
            excluded_stats["fuera_segmento"] += 1
            continue
        if rot_abc.get(sku, "C") != "C" and not priority:
            excluded_stats["rotacion_no_c"] += 1
            continue
        rec = build_sku_candidate(
            sku,
            stock,
            modelo,
            row,
            abc,
            sales_months=sales_months,
            qty_by_sku=qty_by_sku,
            stock_retail=stock_retail,
            stock_taller=stock_taller,
            margin_abc=margin_abc,
            rot_abc=rot_abc,
            priority=priority,
        )
        if rec:
            candidates.append(rec)

    # Prioridad: sumar SKUs faltantes del inventario (todas las variantes del modelo)
    have = {c["sku"] for c in candidates}
    for mod in inv_df["MODELO"].astype(str).unique():
        mod_clean = clean_cell(mod)
        if not is_priority_full_variant(mod_clean) or is_excluded_model(mod_clean):
            continue
        mod_skus = inv_df[inv_df["MODELO"] == mod].groupby("SKU", as_index=False).agg(
            stock=("Cantidad en inventario", "sum"),
            producto=("Producto", "first"),
            genero=("GENERO", "first"),
            color=("COLOR", "first"),
            talla=("TALLA", "first"),
        )
        for ms in mod_skus.itertuples():
            if ms.SKU in have:
                continue
            if ms.stock <= 0:
                continue
            inv_row = type("R", (), {"producto_inv": ms.producto, "genero_inv": ms.genero, "color_inv": ms.color, "talla_inv": ms.talla})()
            abc = abc_metrics.get(ms.SKU)
            rec = build_sku_candidate(
                ms.SKU,
                float(ms.stock),
                mod_clean,
                inv_row,
                abc,
                sales_months=sales_months,
                qty_by_sku=qty_by_sku,
                stock_retail=stock_retail,
                stock_taller=stock_taller,
                margin_abc=margin_abc,
                rot_abc=rot_abc,
                priority=True,
            )
            if rec:
                candidates.append(rec)
                have.add(ms.SKU)

    # Modelos ya en catálogo: completar variantes desde inventario (stock > 0)
    models_active = {c["modelo"] for c in candidates}
    for mod in models_active:
        mod_inv = inv_df[inv_df["MODELO"].astype(str).str.upper() == mod.upper()]
        for sku, grp in mod_inv.groupby("SKU"):
            if sku in have:
                continue
            st = float(grp["Cantidad en inventario"].sum())
            if st <= 0:
                continue
            row = stock_lookup.get(sku)
            if row is None:
                inv_row = type(
                    "R",
                    (),
                    {
                        "producto_inv": grp["Producto"].iloc[0],
                        "genero_inv": grp["GENERO"].iloc[0],
                        "color_inv": grp["COLOR"].iloc[0],
                        "talla_inv": grp["TALLA"].iloc[0],
                    },
                )()
            else:
                inv_row = row
            abc = abc_metrics.get(sku)
            rec = build_sku_candidate(
                sku,
                st,
                mod,
                inv_row,
                abc,
                sales_months=sales_months,
                qty_by_sku=qty_by_sku,
                stock_retail=stock_retail,
                stock_taller=stock_taller,
                margin_abc=margin_abc,
                rot_abc=rot_abc,
                priority=True,
            )
            if rec:
                candidates.append(rec)
                have.add(sku)

    candidates.sort(key=lambda x: (-x["prioridad"], -x["stock_total"], -x["margin"]))

    by_model: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        by_model[c["modelo"]].append(c)

    catalog: list[dict] = []
    model_rows: list[dict] = []
    for mod, variants in by_model.items():
        variants = [v for v in variants if v["matriz"] not in EXCLUDED_MATRICES]
        if not variants:
            continue
        variants.sort(key=lambda x: (-x["stock_total"], x["sku"]))
        matriz_dom = Counter(v["matriz"] for v in variants).most_common(1)[0][0]
        stock_total = sum(v["stock_total"] for v in variants)
        stock_tiendas = sum(v["stock_tiendas"] for v in variants)
        stock_taller_sum = sum(v["stock_taller"] for v in variants)
        qty_periodo = sum(v["qty"] for v in variants)
        rotacion_mes = sum(v["rotacion_mes"] for v in variants)
        margin_sum = sum(v["margin"] for v in variants)
        cov_model = coverage_months(stock_total, rotacion_mes)

        variant_rows = [
            {
                "sku": v["sku"],
                "genero": v["genero"],
                "color": v["color"],
                "talla": v["talla"],
                "matriz": v["matriz"],
                "rotacion_mes": v["rotacion_mes"],
                "stock_total": v["stock_total"],
                "stock_tiendas": v["stock_tiendas"],
                "stock_taller": v["stock_taller"],
                "meses_cobertura": v["meses_cobertura"],
                "qty_periodo": v["qty"],
            }
            for v in variants
        ]
        entry = {
            "modelo": mod,
            "segmento": variants[0]["segmento"],
            "matriz": matriz_dom,
            "skus_count": len(variants),
            "stock_total": int(stock_total),
            "stock_tiendas": int(stock_tiendas),
            "stock_taller": int(stock_taller_sum),
            "rotacion_mes": round(rotacion_mes, 2),
            "qty_periodo": int(qty_periodo),
            "meses_cobertura": round(cov_model, 2) if cov_model < 900 else None,
            "variants": variant_rows,
        }
        catalog.append(entry)
        model_rows.append(
            {
                "modelo": mod,
                "segmento": variants[0]["segmento"],
                "skus_c": len(variants),
                "stock_total": int(stock_total),
                "stock_tiendas": int(stock_tiendas),
                "stock_taller": int(stock_taller_sum),
                "rotacion_mes": round(rotacion_mes, 2),
                "unidades_vendidas_periodo": int(qty_periodo),
                "margen_periodo": round(margin_sum, 2),
                "matriz_dominante": matriz_dom,
            }
        )

    # Vista inventario: ocultar modelos con stock total ≤ 28 (excepto ya filtrados en SKUs)
    catalog = [
        c
        for c in catalog
        if c["stock_total"] >= MIN_STOCK_UNITS or is_priority_full_variant(c["modelo"])
    ]
    catalog.sort(key=lambda x: (-(x["stock_tiendas"] + x["stock_taller"]), -x["stock_total"]))
    model_rows = [
        m
        for m in model_rows
        if m["stock_total"] >= MIN_STOCK_UNITS or is_priority_full_variant(m["modelo"])
    ]
    model_rows.sort(key=lambda x: (-(x["stock_tiendas"] + x["stock_taller"]), -x["stock_total"]))

    assert all(c["stock_total"] > 0 for c in candidates), "Hay SKUs sin stock en la propuesta"

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "periodo_ventas": period_label,
        "meses_analisis": sales_months,
        "skus_c_total": len(candidates),
        "skus_con_stock": len(candidates),
        "unidades_stock": int(sum(c["stock_total"] for c in candidates)),
        "unidades_tiendas": int(sum(c["stock_tiendas"] for c in candidates)),
        "unidades_taller": int(sum(c["stock_taller"] for c in candidates)),
        "margen_historico": round(sum(c["margin"] for c in candidates), 2),
        "manufactura_skus": sum(1 for c in candidates if c["segmento"] == "Manufactura"),
        "equipamiento_skus": sum(1 for c in candidates if c["segmento"] == "Equipamiento"),
        "matriz_cc": sum(1 for c in candidates if c["matriz"] == "CC"),
        "excluidos": dict(excluded_stats),
    }

    in_catalog = {c["modelo"] for c in catalog}
    sugeridos: list[dict] = []
    for row in stock_by_sku.itertuples():
        sku = row.SKU
        stock = float(row.stock_total)
        if stock < MIN_STOCK_UNITS:
            continue
        abc = abc_metrics.get(sku)
        if not abc:
            continue
        mod = clean_cell(row.modelo_inv) or clean_cell(abc.get("modelo"), sku)
        if mod in in_catalog or is_excluded_model(mod) or is_priority_full_variant(mod):
            continue
        if margin_abc.get(sku) != "C" or rot_abc.get(sku, "C") != "C":
            continue
        if not segment(abc.get("categoria") or ""):
            continue
        qty = float(qty_by_sku.get(sku, 0))
        sugeridos.append(
            {
                "modelo": mod,
                "sku": sku,
                "stock": int(stock),
                "rotacion_mes": round(qty / sales_months, 2),
            }
        )
    sugeridos.sort(key=lambda x: (-x["stock"], x["rotacion_mes"]))
    seen_mod: set[str] = set()
    sugeridos_modelos: list[dict] = []
    for s in sugeridos:
        if s["modelo"] in seen_mod:
            continue
        seen_mod.add(s["modelo"])
        sugeridos_modelos.append(s)
        if len(sugeridos_modelos) >= 15:
            break

    payload = {
        "meta": {
            "title": "Propuesta Black Friday · Categoría C",
            "subtitle": "Solo con inventario · baja rotación · Manufactura + Equipamiento",
            "abc_source": str(ABC_HTML.name),
            "inventory_source": str(INV_XLSX.name),
            "sales_source": str(SALES_XLSX.name),
            "meses_incluidos": months_list,
            "priority_models": sorted(PRIORITY_MODELS_EXACT) + list(PRIORITY_MODEL_PREFIXES),
            "sugeridos_revision": sugeridos_modelos,
        },
        "summary": summary,
        "inventario_view": {
            "name": "Inventario baja rotación",
            "description": "Modelos con stock en tiendas + taller. Expandí ▶ para ver variantes SKU.",
            "sort": "stock_desc",
        },
        "catalog": catalog,
        "models": model_rows[:200],
        "skus": candidates,
    }

    payload = sanitize_for_json(payload)
    OUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    write_excel(payload)
    write_js(payload)
    write_html(payload)

    print(f"SKUs propuesta (stock>0, margen C, rotación C): {len(candidates)}")
    print(f"Período ventas: {period_label} ({sales_months} meses)")
    print(f"Excluidos: {dict(excluded_stats)}")
    print(f"JSON: {OUT_JSON}")
    print(f"Excel: {OUT_XLSX}")
    print(f"HTML: {OUT_HTML}")


def write_excel(payload: dict) -> None:
    skus = pd.DataFrame(payload["skus"])
    models = pd.DataFrame(payload["models"])
    summary = pd.DataFrame([payload["summary"]])
    rules = pd.DataFrame({"Regla": payload["meta"].get("rules", [])})
    if rules.empty:
        rules = pd.DataFrame({"Modelo prioridad": payload["meta"].get("priority_models", [])})

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
        "stock_taller",
        "rotacion_mes",
        "meses_cobertura",
        "qty",
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
                    "Vista": payload["inventario_view"]["name"],
                    "Descripción": payload["inventario_view"]["description"],
                },
            ]
        ).to_excel(writer, sheet_name="Vista propuesta", index=False)
        models.to_excel(writer, sheet_name="Modelos prioritarios", index=False)
        skus.to_excel(writer, sheet_name="Detalle SKU", index=False)
        ws = writer.sheets["Detalle SKU"]
        ws.set_column("A:A", 14)
        ws.set_column("B:D", 22)
        ws.freeze_panes(1, 0)


def write_js(payload: dict) -> None:
    blob = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    OUT_JS.write_text(f"window.BF_PROPOSAL_DATA={blob};\n", encoding="utf-8")


def json_for_script_tag(payload: dict) -> str:
    """JSON seguro dentro de <script type=\"application/json\">."""
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    return raw.replace("</script>", "<\\/script>")


def write_html(payload: dict) -> None:
    embedded = json_for_script_tag(payload)
    app_js = DASHBOARD_APP_SRC.read_text(encoding="utf-8")
    html_head = f"""<!DOCTYPE html>
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
.cat-table{{table-layout:fixed;width:100%;border-spacing:0}}
.cat-table col.col-expand{{width:36px}}
.cat-table col.col-model{{width:24%}}
.cat-table col.col-mat{{width:56px}}
.cat-table col.col-n{{width:96px}}
.cat-table th.mat,.cat-table td.mat{{text-align:center;font-weight:700;font-family:var(--fh);padding-left:4px;padding-right:4px}}
.cat-table th.num,.cat-table td.num{{text-align:right;font-variant-numeric:tabular-nums;font-feature-settings:"tnum";white-space:nowrap;padding-left:6px;padding-right:10px}}
.cat-table thead th.num{{text-align:right}}
th{{text-align:left;font-size:.58rem;text-transform:uppercase;color:var(--mu);padding:6px 8px;border-bottom:1px solid var(--brd);position:sticky;top:0;background:var(--surf)}}
td{{padding:6px 8px;border-bottom:1px solid var(--brd);vertical-align:middle}}
.tscroll{{max-height:520px;overflow:auto}}
.tag{{display:inline-block;padding:2px 7px;border-radius:6px;font-size:.65rem;font-weight:700;font-family:var(--fh)}}
.tag.C{{background:rgba(244,114,182,.15);color:var(--c);border:1px solid rgba(244,114,182,.35)}}
.diag{{font-size:.72rem;line-height:1.45;color:var(--mu);padding:10px;border-radius:8px;background:var(--s2);border:1px solid var(--brd);margin-top:10px}}
.diag ul{{margin:8px 0 0 18px}}
#loadErr{{display:none;margin:12px 28px;padding:12px;border-radius:8px;background:rgba(244,114,182,.12);border:1px solid rgba(244,114,182,.4);color:#f472b6;font-size:.78rem}}
.expander{{cursor:pointer;color:var(--a);font-weight:800;width:24px;display:inline-block;user-select:none}}
.row-model td{{background:rgba(255,255,255,.03);font-weight:600}}
.row-variant td{{font-size:.72rem}}
.row-variant .sku{{color:var(--tx);font-weight:600}}
.row-variant .var-meta{{color:var(--mu);font-size:.66rem;margin-top:2px}}
.footer{{text-align:center;color:var(--mu);font-size:.62rem;padding:14px;border-top:1px solid var(--brd)}}
@media(max-width:960px){{.g2{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div id="loadErr"></div>
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
  <button class="tab active" data-tab="resumen">Resumen</button>
  <button class="tab" data-tab="inventario">Inventario baja rotación</button>
  <button class="tab" data-tab="detalle">Detalle SKU</button>
</nav>
<main class="content">
  <section class="sec active" id="sec-resumen">
    <div class="g2">
      <div class="card"><h3>SKUs por segmento</h3><div class="cw" style="height:240px"><canvas id="cSeg"></canvas></div></div>
      <div class="card"><h3>Período de ventas</h3><div class="cs">Excel ventas (todos los meses)</div>
        <p style="font-size:1.1rem;font-family:var(--fh);font-weight:800;margin-top:12px" id="periodLabel"></p>
        <p style="font-size:.72rem;color:var(--mu);margin-top:8px" id="monthsList"></p>
      </div>
    </div>
    <div class="card" id="sugeridosCard" style="margin-top:12px;display:none"><h3>Otros candidatos a revisar</h3><div class="cs">Margen C · rotación C · stock ≥29 · aún no en lista prioritaria</div>
      <div class="tscroll"><table><thead><tr><th>Modelo</th><th>SKU ejemplo</th><th class="num">Stock</th><th class="num">Rotación/mes</th></tr></thead><tbody id="bodySugeridos"></tbody></table></div>
    </div>
  </section>
  <section class="sec" id="sec-inventario">
    <div class="card"><h3 id="titleInv">Inventario baja rotación</h3><div class="cs" id="subInv"></div>
      <div class="tscroll"><table class="cat-table"><colgroup>
        <col class="col-expand"><col class="col-model"><col class="col-mat"><col class="col-n"><col class="col-n"><col class="col-n"><col class="col-n"><col class="col-n"><col class="col-n">
      </colgroup><thead><tr>
        <th scope="col" class="col-expand">&nbsp;</th><th scope="col">Modelo</th><th scope="col" class="mat">Matriz</th><th scope="col" class="num">SKUs</th><th scope="col" class="num">Rotación/mes</th><th scope="col" class="num">Stock total</th><th scope="col" class="num">Stock tiendas</th><th scope="col" class="num">Stock taller</th><th scope="col" class="num">Cobertura (meses)</th>
      </tr></thead><tbody id="bodyInv"></tbody></table></div>
    </div>
  </section>
  <section class="sec" id="sec-detalle">
    <div class="card"><h3>Listado SKU (plano)</h3><div class="tscroll"><table><thead><tr>
      <th>SKU</th><th>Modelo</th><th>Variante</th><th>Rotación/mes</th><th>Stock total</th><th>Stock tiendas</th><th>Stock taller</th>
    </tr></thead><tbody id="bodyAll"></tbody></table></div></div>
  </section>
</main>
<footer class="footer">Archivo autocontenido · datos embebidos · {payload["summary"]["skus_c_total"]} SKUs</footer>
"""
    html_tail = (
        '<script type="application/json" id="bf-embedded-data">'
        + embedded
        + "</script>\n<script>\n"
        + app_js
        + "\n</script>\n</body>\n</html>"
    )
    OUT_HTML.write_text(html_head + html_tail, encoding="utf-8")
    DASHBOARD_APP_OUT.write_text(app_js, encoding="utf-8")


if __name__ == "__main__":
    main()
