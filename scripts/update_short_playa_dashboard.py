#!/usr/bin/env python3
"""Update DASHBOARD SHORTS PLAYA ALL.html with sales + inventory Excel files."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE_HTML = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/DASHBOARD_SHORTS_PLAYA_ALL_360f.html"
)
SALES_XLSX = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/VENTAS_SHORT_ACTUALIZADAS_SEPT_f2be.xlsx"
)
INV_XLSX = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/SHORT_INVENTARIO_COMPLETO_ACTUALIZADO_SEPTIEMBRE_07c9.xlsx"
)
OUTPUT_HTML = ROOT / "DASHBOARD SHORTS PLAYA ALL.html"

MESES_NUM = {
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
MESES_ABBR = {
    "enero": "Ene",
    "febrero": "Feb",
    "marzo": "Mar",
    "abril": "Abr",
    "mayo": "May",
    "junio": "Jun",
    "julio": "Jul",
    "agosto": "Ago",
    "septiembre": "Sep",
    "octubre": "Oct",
    "noviembre": "Nov",
    "diciembre": "Dic",
}

STORE_MAP = {
    "sambil valencia": "SAMBIL",
    "la vela": "VELA",
    "la grieta": "GRIETA",
    "sambil chacao": "CHACAO",
    "cerro verde": "CERRO VERDE",
    "tolon": "TOLON",
    "grandplaz": "GRAND PLAZ",
    "pedidos": "PEDIDOS",
    "vela": "VELA",
    "grieta": "GRIETA",
    "sambil": "SAMBIL",
    "chacao": "CHACAO",
    "cerro verde": "CERRO VERDE",
    "grand plaz": "GRAND PLAZ",
    "taller": "TALLER",
}

INV_STORE_MAP = {
    "VELA": "VELA",
    "GRIETA": "GRIETA",
    "SAMBIL": "SAMBIL",
    "TALLER": "TALLER",
    "TOLON": "TOLON",
    "CHACAO": "CHACAO",
    "CERRO VERDE": "CERRO VERDE",
    "GRANDPLAZ": "GRAND PLAZ",
}

MODELO_SALES_MAP = {
    "SHORT PLAYA": "SHORT PLAYA UNICOLOR",
    "SHORT PLAYA ESTAMPADO": "SHORT PLAYA SUBLIMADO",
}

INV_MODELO_MAP = {
    "SHORT PLAYA CAB": ("SHORT PLAYA UNICOLOR", "CAB"),
    "SHORT PLAYA KIDS": ("SHORT PLAYA UNICOLOR", "KIDS"),
    "SHORT PLAYA ESTAMPADO CAB": ("SHORT PLAYA SUBLIMADO", "CAB"),
    "SHORT PLAYA ESTAMPADO KIDS": ("SHORT PLAYA SUBLIMADO", "KIDS"),
}

PEAK_GROUPS = {
    "diciembre": ["diciembre"],
    "enero": ["enero"],
    "carnaval": ["febrero"],
    "semana_santa": ["marzo", "abril"],
}

LEAD_MONTHS = 3
LAUNCH_NEW_STORE_UPTAKE = 0.93
NEW_STORES = ["VELA", "BARQUISIMETO"]
NEW_STORE_CAPS = {
    "BARQUISIMETO": {
        "type": "avg",
        "bases": ["CHACAO", "GRIETA"],
        "label": "prom. CHACAO + GRIETA",
    }
}


def title_color(value: str) -> str:
    if not isinstance(value, str):
        return value
    v = value.strip()
    special = {
        "PLAYUELA": "Playuela",
        "SAL": "Sal",
        "TUCUPIDO": "Tucupido",
        "SOMBRERO": "Sombrero",
    }
    upper = v.upper()
    if upper in special:
        return special[upper]
    return v.title()


def map_store(raw: str) -> str | None:
    if not isinstance(raw, str):
        return None
    key = raw.strip().lower()
    return STORE_MAP.get(key)


def mes_key(year: int, mes: str) -> str:
    return f"{mes.strip().lower()}-{year}"


def mes_sort_key(m: str) -> tuple[int, int]:
    name, year = m.rsplit("-", 1)
    return (int(year), MESES_NUM[name])


def mes_label(m: str) -> str:
    name, year = m.rsplit("-", 1)
    return f"{MESES_ABBR[name]} {year[-2:]}"


def stock_key(modelo: str, genero: str, color: str, talla: str) -> str:
    return f"{modelo}/{genero}/{color}/{talla}"


def load_data(html_path: Path) -> tuple[str, dict]:
    html = html_path.read_text(encoding="utf-8")
    match = re.search(r"var DATA=(\{.*?\});", html, re.DOTALL)
    if not match:
        raise ValueError("DATA block not found in HTML")
    return html, json.loads(match.group(1))


def parse_sales(path: Path) -> list[dict]:
    df = pd.read_excel(path)
    rows: list[dict] = []
    for _, r in df.iterrows():
        store = map_store(r["tienda / ubicación"])
        if not store:
            continue
        modelo = MODELO_SALES_MAP.get(str(r["modelo"]).strip())
        if not modelo:
            continue
        genero = str(r["GENERO"]).strip().upper()
        color = title_color(str(r["COLOR"]))
        talla = str(r["TALLA"]).strip()
        mes = mes_key(int(r["Año"]), str(r["Mes"]))
        qty = int(r["Cant. ordenada"])
        if qty <= 0:
            continue
        rows.append(
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
    return rows


def parse_inventory(path: Path) -> tuple[dict, dict, dict]:
    df = pd.read_excel(path)
    stock: dict[str, float] = defaultdict(float)
    stock_by_store: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    stock_by_modelo: dict[str, float] = defaultdict(float)

    for _, r in df.iterrows():
        loc = INV_STORE_MAP.get(str(r["Ubicación"]).strip())
        if not loc:
            continue
        mapped = INV_MODELO_MAP.get(str(r["MODELO"]).strip())
        if not mapped:
            continue
        modelo, genero = mapped
        color = title_color(str(r["COLOR"]))
        talla = str(r["TALLA"]).strip()
        qty = max(0, float(r["Cantidad en inventario"]))
        if qty <= 0:
            continue
        key = stock_key(modelo, genero, color, talla)
        stock[key] += qty
        stock_by_store[loc][key] += qty
        stock_by_modelo[modelo] += qty

    return (
        {k: v for k, v in stock.items()},
        {s: dict(v) for s, v in stock_by_store.items()},
        dict(stock_by_modelo),
    )


def merge_sales(existing: list[dict], new_rows: list[dict], replace_months: set[str]) -> list[dict]:
    kept = [r for r in existing if r["mes"] not in replace_months]
    return kept + new_rows


def compute_meses_order(rows: list[dict]) -> list[str]:
    months = sorted({r["mes"] for r in rows}, key=mes_sort_key)
    return months


def compute_meses_und(rows: list[dict], meses_order: list[str]) -> dict[str, int]:
    totals = defaultdict(int)
    for r in rows:
        totals[r["mes"]] += r["v"]
    return {m: int(totals.get(m, 0)) for m in meses_order}


def pick_velocity_months(meses_order: list[str], partial_month: str | None) -> list[str]:
    """Last 6 complete months ending at agosto (exclude partial tail month)."""
    complete = [m for m in meses_order if m != partial_month]
    if "agosto-2026" in complete:
        idx = complete.index("agosto-2026")
        start = max(0, idx - 5)
        return complete[start : idx + 1]
    return complete[-6:]


def compute_peak_factor(
    meses_und: dict[str, int], velocity_months: list[str], meses_order: list[str]
) -> tuple[float, dict[str, float], str]:
    baseline_vals = [meses_und[m] for m in velocity_months if meses_und.get(m, 0) > 0]
    baseline = sum(baseline_vals) / len(baseline_vals) if baseline_vals else 1.0

    peak_factors: dict[str, float] = {}
    for label, month_names in PEAK_GROUPS.items():
        vals = []
        for m in meses_order:
            month_name = m.split("-")[0]
            if month_name in month_names and meses_und.get(m, 0) > 0:
                vals.append(meses_und[m])
        if vals:
            peak_factors[label] = round((sum(vals) / len(vals)) / baseline, 2)

    # Floor diciembre at historical planning factor; use max peak for production safety
    if "diciembre" in peak_factors:
        peak_factors["diciembre"] = max(peak_factors["diciembre"], 1.4)

    hs = max(peak_factors.values()) if peak_factors else 1.4
    hs = round(max(hs, 1.4), 2)

    parts = []
    for key in ["diciembre", "enero", "carnaval", "semana_santa"]:
        if key in peak_factors:
            parts.append(f"{key.replace('_', ' ').title()} ×{peak_factors[key]}")
    label = " · ".join(parts) if parts else f"×{hs}"
    return hs, peak_factors, label


def sku_velocity(
    rows: list[dict], velocity_months: list[str], modelo: str, genero: str, color: str, talla: str
) -> float:
    total = sum(
        r["v"]
        for r in rows
        if r["modelo"] == modelo
        and r["genero"] == genero
        and r["color"] == color
        and r["talla"] == talla
        and r["mes"] in velocity_months
    )
    return round(total / len(velocity_months), 1) if velocity_months else 0.0


def get_stk(stock: dict[str, float], modelo: str, genero: str, color: str, talla: str) -> int:
    return int(stock.get(stock_key(modelo, genero, color, talla), 0))


def get_stk_taller(stock_by_store: dict, modelo: str, genero: str, color: str, talla: str) -> int:
    key = stock_key(modelo, genero, color, talla)
    return int(stock_by_store.get("TALLER", {}).get(key, 0))


def calc_produce(stk: int, v_mes: float, lead: int = LEAD_MONTHS) -> int:
    if v_mes <= 0:
        return 0
    cob = stk / v_mes
    if cob >= lead:
        return 0
    need = lead * v_mes - stk
    return max(0, int(round(need)))


def build_production_plan(
    rows: list[dict],
    stock: dict[str, float],
    stock_by_store: dict,
    colores_activos: dict[str, list[str]],
    velocity_months: list[str],
    hs: float,
) -> list[dict]:
    plan: list[dict] = []
    for modelo, colors in colores_activos.items():
        for color in colors:
            for genero in ["CAB", "KIDS"]:
                talla_rows = []
                talla_names = sorted(
                    {
                        r["talla"]
                        for r in rows
                        if r["modelo"] == modelo
                        and r["genero"] == genero
                        and r["color"] == color
                    },
                    key=lambda t: (0 if t.isdigit() else 1, t),
                )
                if not talla_names:
                    # still include if stock exists
                    prefix = f"{modelo}/{genero}/{color}/"
                    talla_names = sorted({k.split("/")[-1] for k in stock if k.startswith(prefix)})

                for talla in talla_names:
                    base = sku_velocity(rows, velocity_months, modelo, genero, color, talla)
                    adj = round(base * hs, 1)
                    stk = get_stk(stock, modelo, genero, color, talla)
                    stk_taller = get_stk_taller(stock_by_store, modelo, genero, color, talla)
                    cob = round(stk / adj, 1) if adj > 0 else 999.0
                    produce = calc_produce(stk, adj)
                    if base > 0 or stk > 0:
                        talla_rows.append(
                            {
                                "talla": talla,
                                "v_mes_base": base,
                                "v_mes": adj,
                                "stk": stk,
                                "stk_taller": stk_taller,
                                "cob": cob,
                                "produce": produce,
                                "urgente": cob < LEAD_MONTHS,
                            }
                        )

                if not talla_rows:
                    continue

                v_base = round(sum(t["v_mes_base"] for t in talla_rows), 1)
                v_adj = round(sum(t["v_mes"] for t in talla_rows), 1)
                stk_sum = float(sum(t["stk"] for t in talla_rows))
                stk_taller_sum = float(sum(t["stk_taller"] for t in talla_rows))
                cob = round(stk_sum / v_adj, 1) if v_adj > 0 else 999.0
                produce = float(sum(t["produce"] for t in talla_rows))
                plan.append(
                    {
                        "modelo": modelo,
                        "genero": genero,
                        "color": color,
                        "v_mes_base": v_base,
                        "v_mes": v_adj,
                        "stk": stk_sum,
                        "stk_taller": stk_taller_sum,
                        "cob": cob,
                        "produce": produce,
                        "tallas": talla_rows,
                    }
                )
    return plan


def summarize_plan(plan: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for modelo in {p["modelo"] for p in plan}:
        items = [p for p in plan if p["modelo"] == modelo]
        v_base = round(sum(p["v_mes_base"] for p in items), 1)
        v_adj = round(sum(p["v_mes"] for p in items), 1)
        stk = round(sum(p["stk"] for p in items), 1)
        stk_taller = round(sum(p["stk_taller"] for p in items), 1)
        cob = round(stk / v_adj, 1) if v_adj > 0 else 0.0
        produce = round(sum(p["produce"] for p in items), 1)
        out[modelo] = {
            "v_mes_base": v_base,
            "v_mes": v_adj,
            "stk": stk,
            "stk_taller": stk_taller,
            "cob": cob,
            "produce": produce,
        }
    return out


def summarize_genero(plan: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for genero in ["CAB", "KIDS"]:
        items = [p for p in plan if p["genero"] == genero]
        if not items:
            continue
        v_adj = round(sum(p["v_mes"] for p in items), 1)
        stk = round(sum(p["stk"] for p in items), 1)
        out[genero] = {"v_mes": v_adj, "stk": stk, "cob": round(stk / v_adj, 1) if v_adj else 0}
    return out


def store_shares(rows: list[dict], modelo: str, genero: str, stores: list[str]) -> dict[str, float]:
    filtered = [r for r in rows if r["modelo"] == modelo and r["genero"] == genero]
    total = sum(r["v"] for r in filtered)
    shares = {s: 0.0 for s in stores}
    if total <= 0:
        return shares
    for s in stores:
        shares[s] = sum(r["v"] for r in filtered if r["tienda"] == s) / total
    return shares


def new_store_share(store: str, shares: dict[str, float]) -> float:
    cap = NEW_STORE_CAPS.get(store)
    if not cap:
        return shares.get(store, 0.0)
    if cap.get("type") == "avg" and cap.get("bases"):
        return sum(shares.get(b, 0.0) for b in cap["bases"]) / len(cap["bases"])
    return shares.get(cap.get("base", store), 0.0) * cap.get("mult", 1.0)


def build_launch_plan(
    rows: list[dict],
    plan: list[dict],
    velocity_months: list[str],
    hs: float,
    launch_config: list[dict],
    all_stores: list[str],
) -> tuple[list[dict], list[dict], dict[str, dict], list[dict]]:
    launch_plan: list[dict] = []
    launch_distribution: list[dict] = []
    summary_launch: dict[str, dict] = {}

    real_stores = [s for s in all_stores if s not in ["WEB", "PEDIDOS", "CORPORATIVO"]]

    for cfg in launch_config:
        modelo = cfg["modelo"]
        launch_color = cfg["color"]
        top_n = cfg.get("benchmark_top_n", 3)
        display_after = cfg.get("display_after", "Sombrero")

        for genero in ["CAB", "KIDS"]:
            color_items = [
                p
                for p in plan
                if p["modelo"] == modelo and p["genero"] == genero and p["color"] != launch_color
            ]
            color_items.sort(key=lambda p: p["v_mes_base"], reverse=True)
            benchmark = color_items[:top_n]
            if not benchmark:
                continue

            bench_names = [b["color"] for b in benchmark]
            talla_map: dict[str, list[float]] = defaultdict(list)
            for b in benchmark:
                for t in b["tallas"]:
                    talla_map[t["talla"]].append(t["v_mes_base"])

            talla_rows = []
            for talla, refs in sorted(talla_map.items(), key=lambda x: x[0]):
                base = round(sum(refs) / len(refs), 1)
                adj = round(base * hs, 1)
                produce = max(0, int(round(LEAD_MONTHS * adj)))
                talla_rows.append(
                    {
                        "talla": talla,
                        "v_mes_base": base,
                        "v_mes": adj,
                        "stk": 0,
                        "stk_taller": 0,
                        "cob": 0,
                        "produce": produce,
                        "urgente": True,
                        "benchmark_refs": [round(x, 2) for x in refs],
                    }
                )

            if not talla_rows:
                continue

            v_base = round(sum(t["v_mes_base"] for t in talla_rows), 1)
            v_adj = round(sum(t["v_mes"] for t in talla_rows), 1)
            produce_total = float(sum(t["produce"] for t in talla_rows))

            launch_plan.append(
                {
                    "modelo": modelo,
                    "genero": genero,
                    "color": launch_color,
                    "is_launch": True,
                    "display_after": display_after,
                    "benchmark_colors": bench_names,
                    "benchmark_note": f"Prom. top {top_n}: {' · '.join(bench_names)} · red completa (benchmark × participación × 3m; VELA 1.5× GRIETA · BARQUISIMETO prom. CHACAO+GRIETA)",
                    "v_mes_base": v_base,
                    "v_mes": v_adj,
                    "stk": 0,
                    "stk_taller": 0,
                    "cob": 0,
                    "produce": produce_total,
                    "tallas": talla_rows,
                }
            )

            shares = store_shares(rows, modelo, genero, real_stores)
            store_list = list(real_stores) + [s for s in NEW_STORES if s not in real_stores]
            store_targets: dict[str, float] = {}
            for store in store_list:
                if store == "VELA":
                    sh = (shares.get("GRIETA", 0.0)) * 1.5
                elif store in NEW_STORES:
                    sh = new_store_share(store, shares) * LAUNCH_NEW_STORE_UPTAKE
                else:
                    sh = shares.get(store, 0.0)
                store_targets[store] = sh * v_adj * LEAD_MONTHS

            total_target = sum(store_targets.values()) or 1.0
            for store, target in store_targets.items():
                if target < 0.5:
                    continue
                total = max(1, int(round(target)))
                # distribute by talla velocity weights
                weights = [t["v_mes"] for t in talla_rows]
                wsum = sum(weights) or 1.0
                dist_tallas = []
                allocated = 0
                for i, t in enumerate(talla_rows):
                    if i == len(talla_rows) - 1:
                        qty = total - allocated
                    else:
                        qty = int(round(total * (t["v_mes"] / wsum)))
                    allocated += qty
                    if qty > 0:
                        dist_tallas.append({"talla": t["talla"], "qty": qty})
                if not dist_tallas:
                    continue
                launch_distribution.append(
                    {
                        "store": store,
                        "modelo": modelo,
                        "genero": genero,
                        "color": launch_color,
                        "is_launch": True,
                        "is_new_store": store in NEW_STORES,
                        "total": sum(t["qty"] for t in dist_tallas),
                        "tallas": dist_tallas,
                        "share_pct": round(target / total_target * 100, 1),
                    }
                )

        if launch_plan:
            modelo_items = [p for p in launch_plan if p["modelo"] == modelo]
            summary_launch[modelo] = {
                "produce": round(sum(p["produce"] for p in modelo_items), 1),
                "v_mes": round(sum(p["v_mes"] for p in modelo_items), 1),
            }

    return launch_plan, launch_distribution, summary_launch, launch_plan


def build_new_store_projection(
    rows: list[dict],
    plan: list[dict],
    hs: float,
    velocity_months: list[str],
    store: str,
    label: str,
) -> dict:
    skus = []
    total_v = 0.0
    real_stores = ["CERRO VERDE", "CHACAO", "GRAND PLAZ", "GRIETA", "SAMBIL", "TOLON", "VELA"]

    for p in plan:
        shares = store_shares(rows, p["modelo"], p["genero"], real_stores)
        if store == "VELA":
            sh = shares.get("GRIETA", 0.0) * 1.5
        else:
            sh = new_store_share(store, shares)
        for t in p["tallas"]:
            v = round(t["v_mes_base"] * sh * hs, 2)
            if v <= 0:
                continue
            skus.append(
                {
                    "Modelo": p["modelo"],
                    "Genero": p["genero"],
                    "Color": p["color"],
                    "Talla": t["talla"],
                    "v_mes": v,
                    "need_1m": max(0, int(round(v))),
                    "need_2m": max(0, int(round(v * 2))),
                    "need_3m": max(0, int(round(v * 3))),
                }
            )
            total_v += v

    return {
        "v_mes": round(total_v, 1),
        "need_1m": int(round(total_v)),
        "need_2m": int(round(total_v * 2)),
        "need_3m": int(round(total_v * 3)),
        "nota": label,
        "skus": skus,
    }


def update_filtros(rows: list[dict], data: dict) -> dict:
    filtros = data.get("filtros", {})
    filtros["tiendas"] = sorted({r["tienda"] for r in rows})
    filtros["generos"] = sorted({r["genero"] for r in rows})
    filtros["colores"] = sorted({r["color"] for r in rows})
    filtros["modelos"] = sorted({r["modelo"] for r in rows})
    return filtros


def patch_html(html: str, data: dict, periodo: str, partial_label: str, hs_label: str) -> str:
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = re.sub(r"var DATA=\{.*?\};", f"var DATA={data_json};", html, count=1, flags=re.DOTALL)

    html = html.replace("Dashboard de Ventas · Oct 25 — Ago 26", f"Dashboard de Ventas · {periodo}")
    html = html.replace("Short Playa · Dashboard de Ventas · Oct 25 — Ago 26", f"Short Playa · Dashboard de Ventas · {periodo}")

    html = html.replace(
        "if(DATA.es_parcial)alerts.push({type:'info',text:'📅 Mayo 2026 con datos parciales'});",
        "if(DATA.es_parcial)alerts.push({type:'info',text:'📅 '+(DATA.partial_month_label||'Mes actual')+' con datos parciales'});",
    )

    html = html.replace(
        "temporada alta ×<span id=\"hsFactorLabel\">1.4</span> · diciembre base ×1.4",
        f"temporada alta ×<span id=\"hsFactorLabel\">{data['high_season_factor']}</span> · {hs_label}",
    )

    # Dynamic methodology strings in rDecisiones
    html = html.replace(
        "+kpiCard(Math.round(totalVelBase)+' → '+Math.round(totalVel),'Rotación ajustada','Base × '+hs+' temporada alta','var(--a2)')",
        "+kpiCard(Math.round(totalVelBase)+' → '+Math.round(totalVel),'Rotación ajustada','Base × '+hs+' · '+((DATA.high_season_detail_label)||'temporada alta'),'var(--a2)')",
    )
    html = html.replace(
        "'<div><strong style=\"color:var(--tx)\">Rotación ajustada</strong><br>Base × '+hs+' (temporada alta / diciembre). Es la velocidad usada para cobertura y producción.</div>'",
        "'<div><strong style=\"color:var(--tx)\">Rotación ajustada</strong><br>Base × '+hs+' ('+((DATA.high_season_detail_label)||'temporada alta')+'). Cubre picos de <strong style=\"color:var(--tx)\">Diciembre, Enero, Carnaval y Semana Santa</strong>. Es la velocidad usada para cobertura y producción.</div>'",
    )

    return html


def main() -> None:
    html, data = load_data(SOURCE_HTML)
    new_sales = parse_sales(SALES_XLSX)
    replace_months = {r["mes"] for r in new_sales}

    merged_rows = merge_sales(data["raw_rows"], new_sales, replace_months)
    stock, stock_by_store, stock_by_modelo = parse_inventory(INV_XLSX)

    meses_order = compute_meses_order(merged_rows)
    partial_month = "septiembre-2026" if "septiembre-2026" in meses_order else None
    meses_und = compute_meses_und(merged_rows, meses_order)
    velocity_months = pick_velocity_months(meses_order, partial_month)
    hs, peak_factors, hs_detail = compute_peak_factor(meses_und, velocity_months, meses_order)

    colores_activos = data.get("colores_activos", {})
    production_plan = build_production_plan(
        merged_rows, stock, stock_by_store, colores_activos, velocity_months, hs
    )
    summary_produccion = summarize_plan(production_plan)
    summary_genero = summarize_genero(production_plan)

    launch_config = data.get("launch_colors_config", [])
    all_stores = sorted(set(data.get("all_stores", [])) | {r["tienda"] for r in merged_rows})
    launch_plan, launch_distribution, summary_launch, _ = build_launch_plan(
        merged_rows, production_plan, velocity_months, hs, launch_config, all_stores
    )

    stores_order = [
        s
        for s in ["CERRO VERDE", "CHACAO", "GRAND PLAZ", "GRIETA", "SAMBIL", "TOLON", "VELA", "TALLER"]
        if s in stock_by_store
    ]

    periodo = f"{mes_label(meses_order[0])} — {mes_label(meses_order[-1])}"
    velocity_label = " · ".join(mes_label(m) for m in velocity_months)

    data.update(
        {
            "raw_rows": merged_rows,
            "stock": stock,
            "stock_by_store": stock_by_store,
            "stock_by_modelo": stock_by_modelo,
            "meses_order": meses_order,
            "meses_und": meses_und,
            "filtros": update_filtros(merged_rows, data),
            "es_parcial": partial_month is not None,
            "partial_month": partial_month,
            "stock_total": int(sum(stock.values())),
            "stock_taller": int(sum(stock_by_store.get("TALLER", {}).values())),
            "total": int(sum(r["v"] for r in merged_rows)),
            "all_stores": all_stores,
            "stores_order": stores_order,
            "production_plan": production_plan,
            "summary_produccion": summary_produccion,
            "summary_genero": summary_genero,
            "high_season_factor": hs,
            "december_base_factor": peak_factors.get("diciembre", 1.4),
            "high_season_peaks": peak_factors,
            "high_season_detail_label": hs_detail,
            "velocity_months": velocity_months,
            "velocity_months_count": len(velocity_months),
            "velocity_months_label": velocity_label,
            "periodo": periodo.replace(" — ", " — "),
            "launch_production_plan": launch_plan,
            "launch_store_distribution": launch_distribution,
            "summary_launch": summary_launch,
            "lead_months": LEAD_MONTHS,
            "launch_new_store_uptake": LAUNCH_NEW_STORE_UPTAKE,
        }
    )

    hs_note = f"picos Dic/Ene/Carnaval/Sem.Santa ×{hs} · diciembre base ×{peak_factors.get('diciembre', 1.4)}"
    data["barquisimeto"] = build_new_store_projection(
        merged_rows,
        production_plan,
        hs,
        velocity_months,
        "BARQUISIMETO",
        f"prom. CHACAO + GRIETA · factor temporada alta {hs_note}",
    )
    data["vela"] = build_new_store_projection(
        merged_rows,
        production_plan,
        hs,
        velocity_months,
        "VELA",
        f"1.5× GRIETA · factor temporada alta {hs_note}",
    )

    partial_label = "Septiembre 2026" if partial_month else "Mes actual"
    data["partial_month_label"] = partial_label
    updated_html = patch_html(html, data, periodo.replace(" — ", " — "), partial_label, hs_detail)

    OUTPUT_HTML.write_text(updated_html, encoding="utf-8")

    print(f"Written: {OUTPUT_HTML}")
    print(f"Period: {periodo}")
    print(f"Months updated: {sorted(replace_months, key=mes_sort_key)}")
    print(f"Velocity months ({len(velocity_months)}): {velocity_label}")
    print(f"High season factor: {hs} | peaks: {peak_factors}")
    print(f"Total sales rows: {len(merged_rows)} | inventory units: {data['stock_total']}")
    print(f"Production to make: {sum(p['produce'] for p in production_plan):.0f} + launch {sum(p['produce'] for p in launch_plan):.0f}")


if __name__ == "__main__":
    main()
