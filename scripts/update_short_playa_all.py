#!/usr/bin/env python3
"""Update DASHBOARD SHORTS PLAYA ALL with sales + inventory and seasonal Decisiones.

Velocity: last 6 complete months ending August (Mar–Ago). September is partial:
it appears in charts but is excluded from the 6-month average.

Rotación ajustada is not December-only. Coverage uses a composite factor that
adds the extra demand of Diciembre, Enero, Carnaval (Feb) and Semana Santa
(Mar 2027) on top of a 3-month lead. January uses a planning floor because
ene-26 collapsed after the December peak (stockout), not because January
demand is structurally low.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

try:
    import pandas as pd
except ImportError:  # pragma: no cover - installed in the update environment
    pd = None

ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = Path("/home/ubuntu/.cursor/projects/workspace/uploads")
DEFAULT_SOURCE_HTML = ROOT / "SHORT PLAYA SUBL.html"
OUTPUT_HTML = ROOT / "DASHBOARD SHORTS PLAYA ALL.html"

MESES_NUM = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}
MESES_ABBR = {
    "enero": "Ene", "febrero": "Feb", "marzo": "Mar", "abril": "Abr",
    "mayo": "May", "junio": "Jun", "julio": "Jul", "agosto": "Ago",
    "septiembre": "Sep", "octubre": "Oct", "noviembre": "Nov", "diciembre": "Dic",
}

STORE_MAP = {
    "sambil valencia": "SAMBIL",
    "la vela": "VELA",
    "la grieta": "GRIETA",
    "sambil chacao": "CHACAO",
    "cerro verde": "CERRO VERDE",
    "tolon": "TOLON",
    "grandplaz": "GRAND PLAZ",
    "grand plaz": "GRAND PLAZ",
    "pedidos": "PEDIDOS",
    "vela": "VELA",
    "grieta": "GRIETA",
    "sambil": "SAMBIL",
    "chacao": "CHACAO",
    "taller": "TALLER",
    "web": "WEB",
    "corporativo": "CORPORATIVO",
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
    "GRAND PLAZ": "GRAND PLAZ",
    "WEB": "WEB",
}

MODELO_SALES_MAP = {
    "SHORT PLAYA": "SHORT PLAYA UNICOLOR",
    "SHORT PLAYA UNICOLOR": "SHORT PLAYA UNICOLOR",
    "SHORT PLAYA ESTAMPADO": "SHORT PLAYA SUBLIMADO",
    "SHORT PLAYA SUBLIMADO": "SHORT PLAYA SUBLIMADO",
}

INV_MODELO_MAP = {
    "SHORT PLAYA CAB": ("SHORT PLAYA UNICOLOR", "CAB"),
    "SHORT PLAYA KIDS": ("SHORT PLAYA UNICOLOR", "KIDS"),
    "SHORT PLAYA ESTAMPADO CAB": ("SHORT PLAYA SUBLIMADO", "CAB"),
    "SHORT PLAYA ESTAMPADO KIDS": ("SHORT PLAYA SUBLIMADO", "KIDS"),
    "SHORT PLAYA UNICOLOR CAB": ("SHORT PLAYA UNICOLOR", "CAB"),
    "SHORT PLAYA UNICOLOR KIDS": ("SHORT PLAYA UNICOLOR", "KIDS"),
    "SHORT PLAYA SUBLIMADO CAB": ("SHORT PLAYA SUBLIMADO", "CAB"),
    "SHORT PLAYA SUBLIMADO KIDS": ("SHORT PLAYA SUBLIMADO", "KIDS"),
}

UNICOLOR_ACTIVE = {"Verde Pino", "Azul Pizarra", "Azul Verdoso", "Marron", "Cereza"}
SUBLIMADO_ACTIVE = {"Playuela", "Sal", "Tucupido", "Sombrero"}
MODELS = ["SHORT PLAYA UNICOLOR", "SHORT PLAYA SUBLIMADO"]
LINEAS = ["CAB", "KIDS"]

VELOCITY_MONTHS_COUNT = 6
LEAD_MONTHS = 3
ANCHOR_COMPLETE = "agosto-2026"
PARTIAL_MONTH = "septiembre-2026"

# User floor for December; upcoming-season floors so Carnival / SS / January
# actually move production (historical ene-26 and a high August baseline
# would otherwise cancel them).
DEC_FLOOR = 1.40
ENE_FLOOR = 1.20
CARN_FLOOR = 1.20
SS_FLOOR = 1.20

AS_OF = "2026-09-13"


def find_file(tokens: list[str], extra_dirs: list[Path] | None = None) -> Path | None:
    dirs = [UPLOAD_DIR, ROOT, ROOT / "data", Path("/tmp")]
    if extra_dirs:
        dirs = extra_dirs + dirs
    tokens = [t.lower() for t in tokens]
    candidates: list[Path] = []
    for folder in dirs:
        if not folder.exists():
            continue
        for path in folder.iterdir():
            if not path.is_file():
                continue
            name = path.name.lower().replace(" ", "_")
            if all(tok.lower().replace(" ", "_") in name for tok in tokens):
                candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def title_color(value) -> str:
    if not isinstance(value, str):
        return str(value)
    v = value.strip()
    special = {
        "PLAYUELA": "Playuela", "SAL": "Sal", "TUCUPIDO": "Tucupido",
        "SOMBRERO": "Sombrero",
    }
    if v.upper() in special:
        return special[v.upper()]
    return v.title()


def parse_qty(value) -> float:
    if value is None or (isinstance(value, float) and pd is not None and pd.isna(value)):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def mes_key(year: int, mes: str) -> str:
    return f"{str(mes).strip().lower()}-{int(year)}"


def mes_sort_key(mes: str) -> tuple[int, int]:
    name, year = mes.rsplit("-", 1)
    return (int(year), MESES_NUM[name])


def mes_label(mes: str) -> str:
    name, year = mes.rsplit("-", 1)
    return f"{MESES_ABBR[name]} {year[-2:]}"


def stock_key(modelo: str, genero: str, color: str, talla: str) -> str:
    return f"{modelo}/{genero}/{color}/{talla}"


def is_active(modelo: str, color: str) -> bool:
    if modelo == "SHORT PLAYA UNICOLOR":
        return color in UNICOLOR_ACTIVE
    if modelo == "SHORT PLAYA SUBLIMADO":
        return color in SUBLIMADO_ACTIVE
    return False


def pick_velocity_months(meses_order: list[str], partial_month: str | None = PARTIAL_MONTH) -> list[str]:
    """Last 6 complete months ending at August (user: 'agosto hacia atrás')."""
    complete = [m for m in meses_order if m != partial_month]
    if ANCHOR_COMPLETE in complete:
        idx = complete.index(ANCHOR_COMPLETE)
        start = max(0, idx - (VELOCITY_MONTHS_COUNT - 1))
        return complete[start: idx + 1]
    return complete[-VELOCITY_MONTHS_COUNT:]


def month_avg(meses_und: dict, names: list[str], meses_order: list[str], skip: set[str] | None = None) -> float | None:
    skip = skip or set()
    vals = [
        meses_und[m] for m in meses_order
        if m.split("-")[0] in names and meses_und.get(m, 0) > 0 and m not in skip
    ]
    if not vals:
        return None
    return sum(vals) / len(vals)


def compute_seasonality(meses_und: dict, velocity_months: list[str], meses_order: list[str]) -> dict:
    """Build event factors + composite hs used for cobertura / producción.

    Historical ratio vs the 6-month baseline, then apply planning floors so
    upcoming Enero / Carnaval / Semana Santa are not erased by ene-26 stockout
    or a single strong August.
    Composite: 3 months of base coverage + extra demand of the four peaks.
    """
    baseline_vals = [meses_und[m] for m in velocity_months if meses_und.get(m, 0) > 0]
    baseline = sum(baseline_vals) / len(baseline_vals) if baseline_vals else 1.0
    skip = {PARTIAL_MONTH}

    hist = {
        "diciembre": month_avg(meses_und, ["diciembre"], meses_order, skip),
        "enero": month_avg(meses_und, ["enero"], meses_order, skip),
        "carnaval": month_avg(meses_und, ["febrero"], meses_order, skip),
        "semana_santa": month_avg(meses_und, ["marzo"], meses_order, skip),
    }
    raw_ratios = {
        k: round(v / baseline, 2) if v else None
        for k, v in hist.items()
    }
    floors = {
        "diciembre": DEC_FLOOR,
        "enero": ENE_FLOOR,
        "carnaval": CARN_FLOOR,
        "semana_santa": SS_FLOOR,
    }
    factors = {}
    notes = {}
    for key, floor in floors.items():
        raw = raw_ratios[key]
        if raw is None:
            factors[key] = floor
            notes[key] = f"sin historia; piso {floor}"
        elif key == "enero" and raw < floor:
            factors[key] = floor
            notes[key] = (
                f"hist {raw}× (quiebre post-diciembre); piso planificación {floor}"
            )
        else:
            factors[key] = round(max(raw, floor), 2)
            notes[key] = f"hist {raw}× · piso {floor}"

    # December is the primary high-season factor (user: Base × 1.4 / diciembre).
    # Enero, Carnaval and Semana Santa ADD extra demand on top of that 3-month
    # cover — they do not replace December or get cancelled by a high August.
    other_extras = sum(factors[k] - 1 for k in ("enero", "carnaval", "semana_santa"))
    hs = round(factors["diciembre"] + other_extras / LEAD_MONTHS, 2)
    detail = (
        f"Dic ×{factors['diciembre']} · Ene ×{factors['enero']} · "
        f"Carnaval ×{factors['carnaval']} · Semana Santa ×{factors['semana_santa']}"
    )
    return {
        "baseline": round(baseline, 1),
        "raw_ratios": raw_ratios,
        "factors": factors,
        "notes": notes,
        "high_season_factor": hs,
        "high_season_detail_label": detail,
        "extras": round(other_extras, 2),
    }


def calc_produce(stk: float, v_mes: float, lead: int = LEAD_MONTHS) -> int:
    if v_mes <= 0:
        return 0
    if stk / v_mes >= lead:
        return 0
    return max(0, int(round(lead * v_mes - stk)))


def sku_velocity(rows, velocity_months, modelo, genero, color, talla) -> float:
    total = sum(
        r["v"] for r in rows
        if r["modelo"] == modelo and r["genero"] == genero
        and r["color"] == color and r["talla"] == talla
        and r["mes"] in velocity_months
    )
    return total / len(velocity_months) if velocity_months else 0.0


def load_html_data(html_path: Path) -> tuple[str, dict]:
    html = html_path.read_text(encoding="utf-8")
    match = re.search(r"var DATA=(\{.*?\});", html, re.DOTALL)
    if not match:
        raise ValueError(f"DATA block not found in {html_path}")
    return html, json.loads(match.group(1))


def map_store(raw) -> str | None:
    if not isinstance(raw, str):
        return None
    return STORE_MAP.get(raw.strip().lower())


def parse_sales(path: Path) -> list[dict]:
    if pd is None:
        raise RuntimeError("pandas is required to parse sales Excel")
    df = pd.read_excel(path)
    rows = []
    for _, r in df.iterrows():
        store = map_store(r.get("tienda / ubicación") or r.get("tienda") or r.get("Tienda"))
        if not store:
            continue
        modelo_raw = str(r.get("modelo") or r.get("Producto") or "").strip()
        modelo = MODELO_SALES_MAP.get(modelo_raw.upper() if modelo_raw.upper() in MODELO_SALES_MAP else modelo_raw)
        if not modelo:
            # try prefix match
            up = modelo_raw.upper()
            if "ESTAMPADO" in up or "SUBLIM" in up:
                modelo = "SHORT PLAYA SUBLIMADO"
            elif up.startswith("SHORT PLAYA"):
                modelo = "SHORT PLAYA UNICOLOR"
            else:
                continue
        qty = int(round(parse_qty(r.get("Cant. ordenada") if "Cant. ordenada" in df.columns else r.get("v"))))
        if qty == 0:
            continue
        year = r.get("Año") or r.get("anio") or r.get("year")
        mes = r.get("Mes") or r.get("mes")
        if year is None or mes is None:
            continue
        rows.append({
            "tienda": store,
            "genero": str(r.get("GENERO") or r.get("genero") or "").strip().upper(),
            "color": title_color(r.get("COLOR") or r.get("color")),
            "talla": str(r.get("TALLA") or r.get("talla")).strip(),
            "mes": mes_key(int(year), str(mes)),
            "modelo": modelo,
            "activo": True,
            "v": qty,
        })
    return rows


def parse_inventory(path: Path) -> tuple[dict, dict, dict]:
    if pd is None:
        raise RuntimeError("pandas is required to parse inventory Excel")
    df = pd.read_excel(path)
    stock: dict[str, float] = defaultdict(float)
    stock_by_store: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    stock_by_modelo: dict[str, float] = defaultdict(float)
    loc_col = "Ubicación" if "Ubicación" in df.columns else "Ubicacion"
    for _, r in df.iterrows():
        loc = INV_STORE_MAP.get(str(r.get(loc_col) or "").strip())
        mapped = INV_MODELO_MAP.get(str(r.get("MODELO") or "").strip().upper())
        if not mapped:
            mapped = INV_MODELO_MAP.get(str(r.get("MODELO") or "").strip())
        if not loc or not mapped:
            continue
        modelo, genero = mapped
        qty = max(0.0, parse_qty(r.get("Cantidad en inventario")))
        if qty <= 0:
            continue
        key = stock_key(modelo, genero, title_color(r.get("COLOR")), str(r.get("TALLA")).strip())
        stock[key] += qty
        stock_by_store[loc][key] += qty
        stock_by_modelo[modelo] += qty
    stock_i = {k: int(round(v)) for k, v in stock.items()}
    sbs = {s: {k: int(round(v)) for k, v in items.items()} for s, items in stock_by_store.items()}
    sbm = {m: int(round(v)) for m, v in stock_by_modelo.items()}
    return stock_i, sbs, sbm


def merge_sales(existing: list[dict], new_rows: list[dict]) -> tuple[list[dict], list[str]]:
    replace_months = sorted({r["mes"] for r in new_rows}, key=mes_sort_key)
    kept = [r for r in existing if r["mes"] not in replace_months]
    return kept + new_rows, replace_months


def rebuild_aggregates(raw_rows: list[dict]) -> tuple[list[str], dict]:
    months = sorted({r["mes"] for r in raw_rows}, key=mes_sort_key)
    und = {m: 0 for m in months}
    for r in raw_rows:
        und[r["mes"]] += r["v"]
    return months, und


def compute_production_plan(raw_rows, stock, stock_taller_by_key, vel_months, hs):
    production_rows = []
    for modelo in MODELS:
        model_rows = [r for r in raw_rows if r["modelo"] == modelo]
        if not model_rows:
            continue
        for genero in LINEAS:
            colors = sorted({
                r["color"] for r in model_rows
                if r["genero"] == genero and is_active(modelo, r["color"])
            })
            for color in colors:
                tallas = sorted({
                    r["talla"] for r in model_rows
                    if r["genero"] == genero and r["color"] == color
                }, key=lambda t: (len(str(t)), str(t)))
                talla_rows = []
                color_v = color_v_base = color_stk = color_stk_taller = color_produce = 0.0
                for talla in tallas:
                    base_v = sku_velocity(model_rows, vel_months, modelo, genero, color, talla)
                    v_mes_base = round(base_v, 1)
                    v_mes = round(base_v * hs, 1)
                    key = stock_key(modelo, genero, color, talla)
                    stk = int(stock.get(key, 0))
                    stk_taller = int(stock_taller_by_key.get(key, 0))
                    cob = round(stk / v_mes, 1) if v_mes > 0 else 999
                    need = calc_produce(stk, v_mes)
                    talla_rows.append({
                        "talla": talla,
                        "v_mes_base": v_mes_base,
                        "v_mes": v_mes,
                        "stk": stk,
                        "stk_taller": stk_taller,
                        "cob": cob,
                        "produce": need,
                        "urgente": cob < LEAD_MONTHS,
                    })
                    color_v += v_mes
                    color_v_base += v_mes_base
                    color_stk += stk
                    color_stk_taller += stk_taller
                    color_produce += need
                if not talla_rows:
                    continue
                production_rows.append({
                    "modelo": modelo,
                    "genero": genero,
                    "color": color,
                    "v_mes_base": round(color_v_base, 1),
                    "v_mes": round(color_v, 1),
                    "stk": color_stk,
                    "stk_taller": color_stk_taller,
                    "cob": round(color_stk / color_v, 1) if color_v > 0 else 999,
                    "produce": color_produce,
                    "tallas": talla_rows,
                })

    summary = {}
    for modelo in MODELS:
        rows_m = [r for r in production_rows if r["modelo"] == modelo]
        v_mes = sum(r["v_mes"] for r in rows_m)
        v_mes_base = sum(r["v_mes_base"] for r in rows_m)
        stk = sum(r["stk"] for r in rows_m)
        stk_taller = sum(r["stk_taller"] for r in rows_m)
        produce = sum(r["produce"] for r in rows_m)
        summary[modelo] = {
            "v_mes_base": round(v_mes_base, 1),
            "v_mes": round(v_mes, 1),
            "stk": stk,
            "stk_taller": stk_taller,
            "cob": round(stk / v_mes, 1) if v_mes > 0 else 999,
            "produce": produce,
        }

    summary_genero = {}
    for genero in LINEAS:
        rows_g = [r for r in production_rows if r["genero"] == genero]
        v_mes = sum(r["v_mes"] for r in rows_g)
        v_mes_base = sum(r["v_mes_base"] for r in rows_g)
        stk = sum(r["stk"] for r in rows_g)
        produce = sum(r["produce"] for r in rows_g)
        summary_genero[genero] = {
            "v_mes_base": round(v_mes_base, 1),
            "v_mes": round(v_mes, 1),
            "stk": stk,
            "cob": round(stk / v_mes, 1) if v_mes > 0 else 999,
            "produce": produce,
        }
    return production_rows, summary, summary_genero


def compute_store_projection(raw_rows, stores, mult, meses, hs, label):
    monthly = defaultdict(lambda: defaultdict(float))
    for r in raw_rows:
        if r["tienda"] not in stores or r["mes"] not in meses or not r.get("activo", True):
            continue
        key = (r["modelo"], r["genero"], r["color"], r["talla"])
        monthly[key][r["tienda"]] += r["v"]

    n = max(len(meses), 1)
    skus = []
    total_v = 0.0
    for key in sorted(monthly):
        per_store = [monthly[key][s] / n for s in stores]
        v_mes = round(sum(per_store) / len(stores) * mult * hs, 2)
        total_v += v_mes
        modelo, genero, color, talla = key
        skus.append({
            "Modelo": modelo,
            "Genero": genero,
            "Color": color,
            "Talla": talla,
            "v_mes": v_mes,
            "need_1m": max(0, round(v_mes * 1)),
            "need_2m": max(0, round(v_mes * 2)),
            "need_3m": max(0, round(v_mes * 3)),
        })
    return {
        "v_mes": round(total_v, 1),
        "need_1m": max(0, round(total_v * 1)),
        "need_2m": max(0, round(total_v * 2)),
        "need_3m": max(0, round(total_v * 3)),
        "nota": label,
        "skus": skus,
    }


def rebuild_data(data: dict, season: dict, vel_months: list[str]) -> dict:
    raw_rows = data["raw_rows"]
    stock = data["stock"]
    stock_taller = defaultdict(int)
    for store, items in data.get("stock_by_store", {}).items():
        if store == "TALLER":
            for key, qty in items.items():
                stock_taller[key] += qty

    hs = season["high_season_factor"]
    production_plan, summary_produccion, summary_genero = compute_production_plan(
        raw_rows, stock, stock_taller, vel_months, hs
    )
    data["production_plan"] = production_plan
    data["summary_produccion"] = summary_produccion
    data["summary_genero"] = summary_genero
    data["velocity_months"] = vel_months
    data["velocity_months_label"] = " · ".join(mes_label(m) for m in vel_months)
    data["velocity_months_count"] = len(vel_months)
    data["high_season_factor"] = hs
    data["high_season_detail_label"] = season["high_season_detail_label"]
    data["season_factors"] = season["factors"]
    data["season_notes"] = season["notes"]
    data["season_raw_ratios"] = season["raw_ratios"]
    data["season_baseline"] = season["baseline"]
    data["december_base_factor"] = DEC_FLOOR
    data["lead_months"] = LEAD_MONTHS
    data["as_of"] = AS_OF
    first = mes_label(data["meses_order"][0])
    last = mes_label(data["meses_order"][-1])
    data["periodo"] = f"{first} — {last}"
    data["es_parcial"] = PARTIAL_MONTH in data["meses_order"]
    data["partial_month"] = PARTIAL_MONTH if data["es_parcial"] else None
    data["partial_month_label"] = "Septiembre 2026" if data["es_parcial"] else None
    caps = data.get("new_store_caps") or {}
    caps.setdefault("VELA", {"base": "GRIETA", "mult": 1.5, "label": "1.5× GRIETA"})
    caps.setdefault("BARQUISIMETO", {"base": "GRIETA", "mult": 1, "label": "1× GRIETA"})
    data["new_store_caps"] = caps
    data["high_season_peaks"] = season["factors"]
    data["barquisimeto"] = compute_store_projection(
        raw_rows, ["GRIETA"], 1, vel_months, hs,
        f"1× GRIETA · rotación ajustada ×{hs} · {season['high_season_detail_label']}",
    )
    data["vela"] = compute_store_projection(
        raw_rows, ["GRIETA"], 1.5, vel_months, hs,
        f"1.5× GRIETA · rotación ajustada ×{hs}",
    )
    data["total"] = sum(data["meses_und"].values())
    if data.get("launch_production_plan"):
        data["launch_production_plan"] = rescale_launch(data["launch_production_plan"], hs)
        data["summary_launch"] = summarize_launch(data["launch_production_plan"])
    return data


def rescale_launch(launch_plan: list, hs: float) -> list:
    for row in launch_plan:
        base = float(row.get("v_mes_base") or 0)
        row["v_mes"] = round(base * hs, 1)
        for talla in row.get("tallas") or []:
            t_base = float(talla.get("v_mes_base") or 0)
            talla["v_mes"] = round(t_base * hs, 1)
            talla["produce"] = calc_produce(talla.get("stk") or 0, talla["v_mes"])
            talla["cob"] = 0 if talla["v_mes"] else 999
            talla["urgente"] = True
        row["produce"] = sum(t.get("produce") or 0 for t in row.get("tallas") or [])
        row["cob"] = 0 if row["v_mes"] else 999
    return launch_plan


def summarize_launch(launch_plan: list) -> dict:
    return {
        "v_mes_base": round(sum(r.get("v_mes_base") or 0 for r in launch_plan), 1),
        "v_mes": round(sum(r.get("v_mes") or 0 for r in launch_plan), 1),
        "produce": sum(r.get("produce") or 0 for r in launch_plan),
    }


def patch_html(html: str, data: dict) -> str:
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = re.sub(r"var DATA=\{.*?\};", f"var DATA={data_json};", html, count=1, flags=re.DOTALL)

    periodo = data.get("periodo", "Oct 25 — Sep 26")
    html = re.sub(r"Oct 25 — Ago 26", periodo, html)
    html = re.sub(r"Oct 25 — Sep 26", periodo, html)

    html = html.replace(
        "if(DATA.es_parcial)alerts.push({type:'info',text:'📅 Mayo 2026 con datos parciales'});",
        "if(DATA.es_parcial)alerts.push({type:'info',text:'📅 '+(DATA.partial_month_label||'Mes actual')+' con datos parciales — no entra en el promedio de decisiones'});",
    )

    old_sub = (
        "VELA 1.5× GRIETA · BARQUISIMETO 1× GRIETA · factor temporada alta ×"
        "<span id=\"hsFactorLabel\">1.25</span>"
    )
    new_sub = (
        "VELA 1.5× GRIETA · BARQUISIMETO 1× GRIETA · rotación ajustada ×"
        "<span id=\"hsFactorLabel\">"
        + str(data["high_season_factor"])
        + "</span> · "
        + data["high_season_detail_label"]
    )
    html = html.replace(old_sub, new_sub)
    html = html.replace(
        "VELA 1.5× GRIETA · BARQUISIMETO 1× GRIETA · factor temporada alta ×<span id=\"hsFactorLabel\">1.4</span>",
        "VELA 1.5× GRIETA · BARQUISIMETO 1× GRIETA · rotación ajustada ×<span id=\"hsFactorLabel\">"
        + str(data["high_season_factor"])
        + "</span>",
    )
    html = re.sub(
        r'(id="hsFactorLabel">)[^<]+',
        r"\g<1>" + str(data["high_season_factor"]),
        html,
    )
    html = re.sub(
        r"Diciembre ×[0-9.]+ · Enero ×[0-9.]+ · Carnaval ×[0-9.]+ · Semana Santa ×[0-9.]+",
        data["high_season_detail_label"].replace("Dic ", "Diciembre ").replace("Ene ", "Enero "),
        html,
    )

    html = html.replace(
        "Base × '+hs+' temporada alta",
        "Base × '+hs+' · "+data["high_season_detail_label"].replace("'", "\\'")+"",
    )
    html = html.replace(
        "Base × '+hs+' (temporada alta). Es la velocidad usada para cobertura y producción.",
        "Base × '+hs+' ("+data["high_season_detail_label"].replace("'", "\\'")+"). "
        + "Cobertura de 3 meses más el extra de diciembre, enero, carnaval y Semana Santa. "
        + "Es la velocidad usada para cobertura y producción.",
    )
    html = html.replace(
        "Base × '+hs+' (temporada alta / diciembre). Es la velocidad usada para cobertura y producción.",
        "Base × '+hs+' ("+data["high_season_detail_label"].replace("'", "\\'")+"). "
        + "Cobertura de 3 meses más el extra de diciembre, enero, carnaval y Semana Santa. "
        + "Es la velocidad usada para cobertura y producción.",
    )

    html = html.replace(
        "<h1>Short Playa · <em id=\"titleModelo\">Todas</em></h1>",
        "<h1>Shorts Playa ALL · <em id=\"titleModelo\">Todas</em></h1>",
    )
    html = html.replace("Short Playa · Dashboard de Ventas", "Shorts Playa ALL · Dashboard de Ventas")
    html = html.replace("<title>Dashboard Short Playa</title>", "<title>Dashboard Shorts Playa ALL</title>")
    if "<title>" not in html[:800]:
        html = html.replace(
            "<title>SHORT PLAYA SUBL</title>",
            "<title>Dashboard Shorts Playa ALL</title>",
        )
    return html


def apply_sales_and_inventory(data: dict, sales_path: Path | None, inv_path: Path | None) -> dict:
    replaced = []
    if sales_path and sales_path.exists():
        new_rows = parse_sales(sales_path)
        data["raw_rows"], replaced = merge_sales(data["raw_rows"], new_rows)
        print(f"Sales Excel: {sales_path.name} · rows={len(new_rows)} · months={replaced}")
    else:
        print("Sales Excel: not found — keeping months already in the dashboard")

    if inv_path and inv_path.exists():
        stock, sbs, sbm = parse_inventory(inv_path)
        data["stock"] = stock
        data["stock_by_store"] = sbs
        data["stock_by_modelo"] = sbm
        data["stock_total"] = int(sum(stock.values()))
        data["stock_taller"] = int(sum(sbs.get("TALLER", {}).values()))
        print(f"Inventory Excel: {inv_path.name} · units={data['stock_total']} · taller={data['stock_taller']}")
    else:
        print("Inventory Excel: not found — keeping stock already in the dashboard")

    meses_order, meses_und = rebuild_aggregates(data["raw_rows"])
    data["meses_order"] = meses_order
    data["meses_und"] = meses_und
    data["replaced_months"] = replaced
    return data


def main() -> None:
    source_html = DEFAULT_SOURCE_HTML
    for candidate in [
        find_file(["dashboard", "shorts", "playa"]),
        find_file(["dashboard", "playa", "all"]),
        OUTPUT_HTML if OUTPUT_HTML.exists() else None,
        Path("/tmp/sibling/DASHBOARD_SHORTS_PLAYA_ALL.html"),
        DEFAULT_SOURCE_HTML,
    ]:
        if candidate and candidate.exists() and candidate.suffix.lower() == ".html":
            if "septiembre-2026" in candidate.read_text(encoding="utf-8", errors="ignore"):
                source_html = candidate
                break
            source_html = candidate

    sales_path = find_file(["ventas", "short"])
    inv_path = find_file(["inventario"]) or find_file(["inventario", "sept"])

    print(f"Source HTML: {source_html}")
    print(f"Sales path: {sales_path}")
    print(f"Inventory path: {inv_path}")

    html, data = load_html_data(source_html)
    data = apply_sales_and_inventory(data, sales_path, inv_path)

    vel_months = pick_velocity_months(data["meses_order"])
    season = compute_seasonality(data["meses_und"], vel_months, data["meses_order"])
    data = rebuild_data(data, season, vel_months)

    out_html = patch_html(html, data)
    OUTPUT_HTML.write_text(out_html, encoding="utf-8")

    produce = sum(r["produce"] for r in data["production_plan"])
    print(f"Wrote {OUTPUT_HTML}")
    print(f"Period: {data['periodo']}")
    print(f"Months: {data['meses_und']}")
    print(f"Velocity (6): {data['velocity_months_label']}")
    print(f"Baseline: {season['baseline']}")
    print(f"Raw ratios: {season['raw_ratios']}")
    print(f"Factors: {season['factors']}")
    print(f"Notes: {season['notes']}")
    print(f"high_season_factor: {data['high_season_factor']} | {data['high_season_detail_label']}")
    print(f"Sales rows: {len(data['raw_rows'])} | inventory: {data['stock_total']}")
    print(f"Produce: {produce}")
    print(f"summary: {data['summary_produccion']}")


if __name__ == "__main__":
    main()
