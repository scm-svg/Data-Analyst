#!/usr/bin/env python3
"""
Genera alertas y plan de producción CAB para Short Playa.

Fuentes (opcionales — si no existen, usa DATA embebido en short_playa.html):
  - INVENTARIO ACTUAL CABALLERO.xlsx
  - VENTAS SHORTS ACTUALIZADA CABALLERO.xlsx
  - INVENTARIO TELA SHORT PLAYA.xlsx

Uso:
  python build_short_playa_produccion.py
  python build_short_playa_produccion.py --inv inv.xlsx --ventas ventas.xlsx --tela tela.xlsx
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("Instala dependencias: pip install pandas openpyxl", file=sys.stderr)
    sys.exit(1)

HTML_PATH = Path("short_playa.html")
HIGH_SEASON = 1.25
TARGET_COB_MONTHS = 3
FABRIC_M_PER_UNIT = 0.75
VELOCITY_MONTHS = 6
MGTA_STORES = ("GRIETA", "LA VELA")
MGTA_PRODUCTION_BOOST = 1.35  # prioridad playa / Margarita

COLORES_ACTIVOS = {
    "Short Playa": ["Verde Pino", "Azul Pizarra", "Azul Verdoso", "Marron", "Cereza"],
    "Short Playa Estampado": ["Playuela", "Sal", "Tucupido", "Sombrero"],
}

TALLAS_CAB = ["XS", "S", "M", "L", "XL", "2XL", "3XL"]


def norm_col(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def find_col(cols, *candidates):
    normed = {norm_col(c): c for c in cols}
    for cand in candidates:
        key = norm_col(cand)
        if key in normed:
            return normed[key]
    for cand in candidates:
        key = norm_col(cand)
        for nk, orig in normed.items():
            if key in nk:
                return orig
    return None


def load_html_data(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"var DATA = (\{.*?\});\s*\nvar", text, re.DOTALL)
    if not m:
        raise SystemExit("No se encontró var DATA en short_playa.html")
    return json.loads(m.group(1))


def velocity_months(meses_order: list[str], count: int = VELOCITY_MONTHS) -> list[str]:
    if len(meses_order) <= count:
        return meses_order[:]
    return meses_order[-count:]


def monthly_velocity(sku: dict, months: list[str]) -> float:
    by_m = sku.get("ventas_by_mes") or {}
    total = sum(by_m.get(m, 0) for m in months)
    return total / max(len(months), 1)


def mgta_share(sku: dict) -> float:
    by_store = sku.get("ventas_by_store") or {}
    total = sum(by_store.values())
    if total <= 0:
        return 0.0
    mgta = sum(by_store.get(st, 0) for st in MGTA_STORES)
    return mgta / total


def mgta_cob(sku: dict, v_mes: float) -> float:
    by_store = sku.get("inv_by_store") or {}
    stk = sum(by_store.get(st, 0) for st in MGTA_STORES)
    if v_mes <= 0:
        return 99.0 if stk > 0 else 0.0
    return stk / v_mes


def is_active_color(modelo: str, color: str) -> bool:
    return color in COLORES_ACTIVOS.get(modelo, [])


def compute_production(data: dict) -> dict:
    months = velocity_months(data.get("meses_order", []))
    months_label = ", ".join(months[-3:]) if len(months) >= 3 else ", ".join(months)

    cab_skus = [s for s in data.get("sku_master", []) if s.get("genero") == "CAB"]
    production_plan = []
    alerts = []
    stock = {}
    stock_taller = 0

    for s in cab_skus:
        stk = int(s.get("inv_total") or 0)
        stk_pp = int(s.get("inv_pp") or 0)
        stock_taller += stk_pp
        key = f"{s['modelo']}/CAB/{s['color']}/{s['talla']}"
        stock[key] = stk

    # Agrupar por modelo + color
    groups: dict[tuple, list] = defaultdict(list)
    for s in cab_skus:
        groups[(s["modelo"], s["color"])].append(s)

    summary: dict[str, dict] = {}
    fabric_need_by_color: dict[str, float] = defaultdict(float)
    total_produce = 0

    for (modelo, color), skus in sorted(groups.items()):
        if not is_active_color(modelo, color):
            continue

        talla_rows = []
        color_v_base = color_v = color_stk = color_prod = 0

        for s in sorted(skus, key=lambda x: TALLAS_CAB.index(x["talla"]) if x["talla"] in TALLAS_CAB else 99):
            v_base = monthly_velocity(s, months)
            v_mes = round(v_base * HIGH_SEASON, 1)
            stk = int(s.get("inv_total") or 0)
            stk_t = int(s.get("inv_pp") or 0)
            cob = round(stk / v_mes, 1) if v_mes > 0 else (99.0 if stk > 0 else 0.0)

            produce = 0
            if v_mes > 0 and cob < TARGET_COB_MONTHS:
                produce = max(0, int(round(TARGET_COB_MONTHS * v_mes - stk)))

            # Boost playa / MGTA: más unidades si vende fuerte en GRIETA + LA VELA
            mshare = mgta_share(s)
            mgta_c = mgta_cob(s, v_mes)
            if produce > 0 and (mshare >= 0.2 or mgta_c < TARGET_COB_MONTHS):
                boosted = int(round(produce * (1 + (MGTA_PRODUCTION_BOOST - 1) * max(mshare, 0.25))))
                produce = max(produce, boosted)

            urgent = cob < 1.5 or (stk <= 0 and v_base >= 1.0)

            if urgent and v_mes > 0:
                mgta_stk = sum((s.get("inv_by_store") or {}).get(st, 0) for st in MGTA_STORES)
                alerts.append(
                    {
                        "type": "danger" if cob < 1 else "warn",
                        "text": (
                            f"{'🔴' if cob < 1 else '⚠️'} {modelo} · {color} T{s['talla']}: "
                            f"cob {cob:.1f}m · MGTA stk {mgta_stk} · producir +{produce or '—'}"
                        ),
                        "modelo": modelo,
                        "color": color,
                        "talla": s["talla"],
                        "cob": cob,
                        "produce": produce,
                    }
                )

            talla_rows.append(
                {
                    "talla": s["talla"],
                    "sku": s.get("sku"),
                    "v_mes_base": round(v_base, 1),
                    "v_mes": v_mes,
                    "stk": stk,
                    "stk_taller": stk_t,
                    "cob": cob,
                    "produce": produce,
                    "urgente": urgent,
                    "mgta_share": round(mshare * 100, 1),
                    "mgta_cob": round(mgta_c, 1),
                }
            )
            color_v_base += v_base
            color_v += v_mes
            color_stk += stk
            color_prod += produce
            if produce > 0:
                fabric_need_by_color[color] += produce * FABRIC_M_PER_UNIT
                total_produce += produce

        if not talla_rows:
            continue

        color_cob = round(color_stk / color_v, 1) if color_v > 0 else 99.0
        production_plan.append(
            {
                "modelo": modelo,
                "genero": "CAB",
                "color": color,
                "v_mes_base": round(color_v_base, 1),
                "v_mes": round(color_v, 1),
                "stk": color_stk,
                "cob": color_cob,
                "produce": color_prod,
                "tallas": talla_rows,
            }
        )

        sm = summary.setdefault(
            modelo,
            {"v_mes_base": 0.0, "v_mes": 0.0, "stk": 0, "cob": 0.0, "produce": 0},
        )
        sm["v_mes_base"] += color_v_base
        sm["v_mes"] += color_v
        sm["stk"] += color_stk
        sm["produce"] += color_prod

    for modelo, sm in summary.items():
        sm["v_mes_base"] = round(sm["v_mes_base"], 1)
        sm["v_mes"] = round(sm["v_mes"], 1)
        sm["cob"] = round(sm["stk"] / sm["v_mes"], 1) if sm["v_mes"] > 0 else 99.0

    # Alertas MGTA agregadas
    mgta_inv = mgta_sales = 0
    for s in cab_skus:
        for st in MGTA_STORES:
            mgta_inv += (s.get("inv_by_store") or {}).get(st, 0)
            mgta_sales += (s.get("ventas_by_store") or {}).get(st, 0)
    mgta_vel = mgta_sales / max(len(months), 1) * HIGH_SEASON
    mgta_cob_global = round(mgta_inv / mgta_vel, 1) if mgta_vel > 0 else 99.0

    if mgta_cob_global < TARGET_COB_MONTHS:
        alerts.insert(
            0,
            {
                "type": "danger",
                "text": (
                    f"🏖️ MGTA (GRIETA + LA VELA): cobertura {mgta_cob_global}m "
                    f"con temporada alta ×{HIGH_SEASON} — priorizar producción playa"
                ),
            },
        )

    vela_inv = sum((s.get("inv_by_store") or {}).get("LA VELA", 0) for s in cab_skus)
    vela_sales = sum((s.get("ventas_by_store") or {}).get("LA VELA", 0) for s in cab_skus)
    vela_zero = [
        s
        for s in cab_skus
        if (s.get("ventas_by_store") or {}).get("LA VELA", 0) >= 2
        and (s.get("inv_by_store") or {}).get("LA VELA", 0) <= 1
        and is_active_color(s["modelo"], s["color"])
    ]
    if vela_zero:
        alerts.append(
            {
                "type": "warn",
                "text": (
                    f"🆕 LA VELA: {len(vela_zero)} variantes activas con quiebre "
                    f"(ventas perdidas en playa)"
                ),
            },
        )

    if total_produce > 0:
        alerts.append(
            {
                "type": "info",
                "text": (
                    f"🧵 Producción CAB sugerida: {total_produce} und · "
                    f"{round(total_produce * FABRIC_M_PER_UNIT, 1)} m tela "
                    f"(@ {FABRIC_M_PER_UNIT} m/pza)"
                ),
            },
        )

    # Ordenar alertas críticas primero
    alerts.sort(key=lambda a: (0 if a.get("type") == "danger" else 1 if a.get("type") == "warn" else 2))

    return {
        "high_season_factor": HIGH_SEASON,
        "target_cob_months": TARGET_COB_MONTHS,
        "fabric_m_per_unit": FABRIC_M_PER_UNIT,
        "velocity_months": months,
        "velocity_months_count": len(months),
        "velocity_months_label": months_label,
        "mgta_stores": list(MGTA_STORES),
        "mgta_production_boost": MGTA_PRODUCTION_BOOST,
        "mgta_cob_global": mgta_cob_global,
        "mgta_stock": mgta_inv,
        "mgta_sales_period": mgta_sales,
        "colores_activos": COLORES_ACTIVOS,
        "production_plan": production_plan,
        "summary_produccion": summary,
        "production_alerts": alerts[:24],
        "stock": stock,
        "stock_taller": stock_taller,
        "fabric_need_by_color": {k: round(v, 1) for k, v in sorted(fabric_need_by_color.items())},
        "total_produce": total_produce,
        "total_fabric_m": round(total_produce * FABRIC_M_PER_UNIT, 1),
        "produccion_as_of": date.today().isoformat(),
    }


def load_tela_inventory(path: Path) -> dict:
    """Lee INVENTARIO TELA SHORT PLAYA.xlsx → {color: metros}."""
    xl = pd.ExcelFile(path)
    sheet = xl.sheet_names[0]
    df = pd.read_excel(path, sheet_name=sheet)
    df.columns = [str(c).strip() for c in df.columns]
    col_color = find_col(df.columns, "color", "tela", "nombre", "descripcion")
    col_m = find_col(df.columns, "metros", "metraje", "cantidad", "stock", "disponible", "m")
    if not col_color or not col_m:
        raise ValueError(f"No se detectaron columnas color/metros en {path}")

    tela = {}
    for _, row in df.iterrows():
        color = str(row[col_color]).strip()
        if not color or color.lower() in ("nan", "none", "color"):
            continue
        try:
            m = float(row[col_m])
        except (TypeError, ValueError):
            continue
        if m > 0:
            tela[color] = tela.get(color, 0) + m
    return tela


def merge_tela(production: dict, tela: dict) -> None:
    production["tela_disponible"] = tela
    fabric_need = production.get("fabric_need_by_color") or {}
    fabric_status = {}
    for color, need in fabric_need.items():
        avail = tela.get(color, 0)
        fabric_status[color] = {
            "need_m": need,
            "avail_m": round(avail, 1),
            "gap_m": round(max(0, need - avail), 1),
            "ok": avail >= need,
        }
    production["fabric_status"] = fabric_status
    gaps = [c for c, st in fabric_status.items() if not st["ok"]]
    if gaps:
        production["production_alerts"].append(
            {
                "type": "danger",
                "text": f"🧵 Falta tela para: {', '.join(gaps[:5])}{'…' if len(gaps) > 5 else ''}",
            }
        )


def patch_html(path: Path, data: dict) -> None:
    text = path.read_text(encoding="utf-8")
    new_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    text, n = re.subn(r"var DATA = \{.*?\};\s*\nvar", f"var DATA = {new_json};\nvar", text, count=1, flags=re.DOTALL)
    if n != 1:
        raise SystemExit("No se pudo actualizar var DATA en HTML")
    path.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build producción CAB Short Playa")
    parser.add_argument("--html", default=str(HTML_PATH))
    parser.add_argument("--inv", help="INVENTARIO ACTUAL CABALLERO.xlsx")
    parser.add_argument("--ventas", help="VENTAS SHORTS ACTUALIZADA CABALLERO.xlsx")
    parser.add_argument("--tela", help="INVENTARIO TELA SHORT PLAYA.xlsx")
    args = parser.parse_args()

    html_path = Path(args.html)
    data = load_html_data(html_path)

    if args.inv or args.ventas:
        print("Nota: lectura Excel de inventario/ventas pendiente de mapeo de columnas.")
        print("      Usando sku_master embebido en short_playa.html.")

    production = compute_production(data)
    for k, v in production.items():
        data[k] = v

    if args.tela and Path(args.tela).exists():
        tela = load_tela_inventory(Path(args.tela))
        merge_tela(production, tela)
        data["tela_disponible"] = production["tela_disponible"]
        data["fabric_status"] = production["fabric_status"]
        data["production_alerts"] = production["production_alerts"]

    patch_html(html_path, data)

    print(f"✓ Actualizado {html_path}")
    print(f"  Producción CAB sugerida: {production['total_produce']} und")
    print(f"  Tela requerida: {production['total_fabric_m']} m")
    print(f"  Cobertura MGTA: {production['mgta_cob_global']} meses")
    print(f"  Alertas: {len(production['production_alerts'])}")


if __name__ == "__main__":
    main()
