#!/usr/bin/env python3
"""
Exporta SHORT PLAYA CAB — Cantidades Sugeridas Proyecciones.xlsx
(estilo Chaqueta Lite).

Reglas:
  · Agotar tela existente: Aguamarina, Verde Oliva, Azul Marino, Gris Azulado,
    Rojo (→ producto Cereza), Verde Pino → und = floor(metros / 0,75)
  · Otros colores activos: producción reforzada (+70% vs plan base, cobertura 4m)
  · Curva tallas por historial de ventas CAB
  · Distribución tienda con boost MGTA (LA VELA 1,5× GRIETA)

Uso:
  python scripts/export_short_playa_proyecciones.py
  python scripts/export_short_playa_proyecciones.py --tela ../INVENTARIO\\ TELA\\ SHORT\\ PLAYA.xlsx
  python scripts/export_short_playa_proyecciones.py --tela-json scripts/short_playa_tela_metros.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "short_playa.html"
TELA_JSON = Path(__file__).resolve().parent / "short_playa_tela_metros.json"
OUT_XLSX = ROOT / "SHORT_PLAYA_CAB_Cantidades_Sugeridas_Proyecciones.xlsx"

HIGH_SEASON = 1.25
TARGET_COB_BOOST = 4
OTHER_BOOST = 2.0
ESTAMPADO_BOOST = 1.35  # extra sobre reforzado para sublimado
FABRIC_M = 0.75
MAX_RANGE_PCT = 0.06
TELA_SS = 0.20
VELOCITY_MONTHS = 6

TELA_AGOTAR = {
    "Aguamarina": ("Short Playa", "Aguamarina"),
    "Verde Oliva": ("Short Playa", "Verde Oliva"),
    "Azul Marino": ("Short Playa", "Azul Marino"),
    "Gris Azulado": ("Short Playa", "Gris Azulado"),
    "Rojo": ("Short Playa", "Cereza"),
    "Verde Pino": ("Short Playa", "Verde Pino"),
}

BOOST_LISO = ["Azul Pizarra", "Azul Verdoso", "Marron"]
BOOST_ESTAMPADO = ["Playuela", "Sal", "Tucupido", "Sombrero"]

TALLAS = ["XS", "S", "M", "L", "XL", "2XL", "3XL"]
TALLA_ORDER = {t: i for i, t in enumerate(TALLAS)}

DIST_STORES = [
    "GRIETA", "LA VELA", "SAMBIL CHACAO", "SAMBIL VALENCIA",
    "CERRO VERDE", "GRAND PLAZ", "TOLON",
]
STORE_LABELS = {
    "GRIETA": "GRIETA",
    "LA VELA": "LA VELA ★",
    "SAMBIL CHACAO": "SAMBIL CHACAO",
    "SAMBIL VALENCIA": "SAMBIL VALENCIA",
    "CERRO VERDE": "CERRO VERDE",
    "GRAND PLAZ": "GRAND PLAZ",
    "TOLON": "TOLON ★",
}


def load_data() -> dict:
    text = HTML.read_text(encoding="utf-8")
    m = re.search(r"var DATA = (\{.*?\});\s*\nvar", text, re.DOTALL)
    if not m:
        raise SystemExit("No DATA en short_playa.html")
    return json.loads(m.group(1))


def norm_col(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def find_col(cols, *candidates):
    normed = {norm_col(c): c for c in cols}
    for cand in candidates:
        key = norm_col(cand)
        if key in normed:
            return normed[key]
        for nk, orig in normed.items():
            if key in nk:
                return orig
    return None


def load_tela_meters(path: Path | None, json_path: Path | None) -> dict[str, float]:
    meters: dict[str, float] = {}
    if json_path and json_path.exists():
        raw = json.loads(json_path.read_text(encoding="utf-8"))
        for k, v in raw.items():
            if k.startswith("_"):
                continue
            meters[k] = float(v)

    if path and path.exists():
        df = pd.read_excel(path)
        df.columns = [str(c).strip() for c in df.columns]
        col_color = find_col(df.columns, "color", "tela", "nombre", "descripcion", "articulo")
        col_m = find_col(df.columns, "metros", "metraje", "cantidad", "stock", "disponible", "existencia", "m")
        if col_color and col_m:
            for _, row in df.iterrows():
                name = str(row[col_color]).strip()
                if not name or name.lower() in ("nan", "color"):
                    continue
                try:
                    val = float(row[col_m])
                except (TypeError, ValueError):
                    continue
                if val <= 0:
                    continue
                key = name.title() if name.islower() else name
                for tela_key in TELA_AGOTAR:
                    if norm_col(tela_key) in norm_col(name) or norm_col(name) in norm_col(tela_key):
                        meters[tela_key] = meters.get(tela_key, 0) + val
                        break
                else:
                    meters[key] = meters.get(key, 0) + val
    return meters


def velocity_months(meses_order: list[str]) -> list[str]:
    return meses_order[-VELOCITY_MONTHS:] if len(meses_order) >= VELOCITY_MONTHS else meses_order[:]


def min_max(qty: int) -> tuple[int, int]:
    if qty <= 0:
        return 0, 0
    return qty, int(math.ceil(qty * (1 + MAX_RANGE_PCT)))


def largest_remainder(weights: dict[str, float], total: int) -> dict[str, int]:
    if total <= 0:
        return {k: 0 for k in weights}
    s = sum(weights.values()) or 1
    raw = {k: weights[k] / s * total for k in weights}
    floor = {k: int(math.floor(raw[k] + 1e-9)) for k in weights}
    used = sum(floor.values())
    frac = sorted(weights.keys(), key=lambda k: raw[k] - floor[k], reverse=True)
    i = 0
    while used < total and frac:
        floor[frac[i % len(frac)]] += 1
        used += 1
        i += 1
    return floor


def cab_skus(data: dict, modelo: str | None = None, color: str | None = None) -> list[dict]:
    out = []
    for s in data.get("sku_master", []):
        if s.get("genero") != "CAB":
            continue
        if modelo and s.get("modelo") != modelo:
            continue
        if color and s.get("color") != color:
            continue
        out.append(s)
    return out


def talla_curve(skus: list[dict], tallas: list[str]) -> dict[str, float]:
    counts = defaultdict(float)
    for s in skus:
        if s["talla"] in tallas:
            counts[s["talla"]] += s.get("ventas") or 0
    if not sum(counts.values()):
        for t in tallas:
            counts[t] = 1.0
    return dict(counts)


def distribute_tallas(total: int, curve: dict[str, float], tallas: list[str]) -> dict[str, int]:
    weights = {t: curve.get(t, 0) for t in tallas}
    return largest_remainder(weights, total)


def store_weights(data: dict, modelo: str | None = None) -> dict[str, float]:
    skus = cab_skus(data, modelo)
    by_store = defaultdict(float)
    for s in skus:
        for st, q in (s.get("ventas_by_store") or {}).items():
            if st in ("WEB", "PEDIDOS", "CORPORATIVO"):
                continue
            by_store[st] += q
    grie = by_store.get("GRIETA", 0)
    w = dict(by_store)
    w["LA VELA"] = max(w.get("LA VELA", 0), grie * 1.5)
    if "TOLON" in w:
        w["TOLON"] *= 1.2
    total = sum(w.values()) or 1
    return {k: v / total for k, v in w.items() if k in DIST_STORES}


def boosted_qty(skus: list[dict], months: list[str], extra_mult: float = 1.0) -> int:
    total = 0
    color_v_mes = 0.0
    color_stk = 0
    for s in skus:
        by_m = s.get("ventas_by_mes") or {}
        vel = sum(by_m.get(m, 0) for m in months) / max(len(months), 1)
        v_mes = vel * HIGH_SEASON * extra_mult
        color_v_mes += v_mes
        stk = int(s.get("inv_total") or 0)
        color_stk += stk
        need = max(0, TARGET_COB_BOOST * v_mes * OTHER_BOOST - stk)
        total += int(round(need))
    # Temporada alta: mínimo 2 meses extra si el color sigue vendiendo
    if color_v_mes > 0:
        floor = int(round(color_v_mes * 2))
        total = max(total, max(0, floor - color_stk // max(len(skus), 1)))
    return total


def build_color_row(
    modelo: str,
    color: str,
    qty_min: int,
    qty_max: int,
    skus: list[dict],
    months: list[str],
    strategy: str,
    tela_m: float | None = None,
) -> dict:
    color_skus = [s for s in skus if s.get("modelo") == modelo and s.get("color") == color]
    curve = talla_curve(color_skus, TALLAS)
    t_min = distribute_tallas(qty_min, curve, TALLAS)
    t_max = distribute_tallas(qty_max, curve, TALLAS)
    talla_rows = []
    for t in TALLAS:
        if t_min[t] <= 0 and t_max[t] <= 0:
            continue
        sku = next((s for s in color_skus if s["talla"] == t), None)
        vel = 0.0
        stk = 0
        if sku:
            by_m = sku.get("ventas_by_mes") or {}
            vel = sum(by_m.get(m, 0) for m in months) / max(len(months), 1) * HIGH_SEASON
            stk = int(sku.get("inv_total") or 0)
        cob = round(stk / vel, 1) if vel > 0 else 99.0
        talla_rows.append({
            "talla": t,
            "min": t_min[t],
            "max": t_max[t],
            "v_mes": round(vel, 1),
            "stk": stk,
            "cob": cob,
        })
    return {
        "modelo": modelo,
        "color": color,
        "strategy": strategy,
        "tela_fabric": next((k for k, v in TELA_AGOTAR.items() if v == (modelo, color)), None),
        "tela_m": tela_m,
        "min": qty_min,
        "max": qty_max,
        "tallas": talla_rows,
        "talla_totals_min": t_min,
        "talla_totals_max": t_max,
    }


def build_rango(data: dict, tela_meters: dict[str, float]) -> dict:
    months = velocity_months(data.get("meses_order", []))
    all_cab = cab_skus(data)
    color_rows: list[dict] = []

    for tela_name, (modelo, color) in TELA_AGOTAR.items():
        meters = tela_meters.get(tela_name, 0)
        if meters <= 0:
            continue
        units_max = int(math.floor(meters / FABRIC_M))
        units_min, units_max = min_max(units_max)
        if units_max <= 0:
            continue
        color_rows.append(
            build_color_row(modelo, color, units_min, units_max, all_cab, months, "agotar_tela", meters)
        )

    for color in BOOST_LISO:
        sk = cab_skus(data, "Short Playa", color)
        q = boosted_qty(sk, months)
        qmin, qmax = min_max(q)
        if qmax <= 0:
            continue
        color_rows.append(build_color_row("Short Playa", color, qmin, qmax, all_cab, months, "reforzado"))

    for color in BOOST_ESTAMPADO:
        sk = cab_skus(data, "Short Playa Estampado", color)
        q = boosted_qty(sk, months, ESTAMPADO_BOOST)
        qmin, qmax = min_max(q)
        if qmax <= 0:
            continue
        color_rows.append(
            build_color_row("Short Playa Estampado", color, qmin, qmax, all_cab, months, "reforzado")
        )

    talla_totals_min = defaultdict(int)
    talla_totals_max = defaultdict(int)
    for cr in color_rows:
        for t in TALLAS:
            talla_totals_min[t] += cr["talla_totals_min"].get(t, 0)
            talla_totals_max[t] += cr["talla_totals_max"].get(t, 0)

    total_min = sum(cr["min"] for cr in color_rows)
    total_max = sum(cr["max"] for cr in color_rows)

    store_talla: dict[str, dict[str, dict[str, int]]] = {}
    sw_global = store_weights(data)
    for store in DIST_STORES:
        store_talla[store] = {}
        sh = sw_global.get(store, 0)
        for t in TALLAS:
            mn = talla_totals_min[t]
            mx = talla_totals_max[t]
            if mn <= 0:
                continue
            store_talla[store][t] = {
                "min": max(0, int(round(mn * sh))),
                "max": max(0, int(round(mx * sh))),
            }

    curve_pct = {}
    if total_min > 0:
        for t in TALLAS:
            curve_pct[t] = round(talla_totals_min[t] / total_min * 100, 1)

    return {
        "months_label": ", ".join(months[-3:]),
        "color_rows": color_rows,
        "talla_totals": {
            t: {"min": talla_totals_min[t], "max": talla_totals_max[t], "curve_pct": curve_pct.get(t, 0)}
            for t in TALLAS
            if talla_totals_min[t] > 0 or talla_totals_max[t] > 0
        },
        "total_min": total_min,
        "total_max": total_max,
        "store_talla": store_talla,
        "tela_meters": tela_meters,
    }


def export_excel(rango: dict, path: Path) -> None:
    import xlsxwriter

    path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(path))
    bold = wb.add_format({"bold": True})
    title = wb.add_format({"bold": True, "font_size": 13, "font_color": "#f97316"})
    hdr = wb.add_format({"bold": True, "bg_color": "#f97316", "font_color": "white"})
    note = wb.add_format({"italic": True, "font_color": "#666666"})
    pct = wb.add_format({"num_format": "0.0%"})
    dec = wb.add_format({"num_format": "0.00"})

    active_tallas = [t for t in TALLAS if rango["talla_totals"].get(t, {}).get("min", 0) > 0]

    # ── 1. Cantidades por Colores ──
    ws = wb.add_worksheet("Cantidades por Colores")
    row = 0
    ws.write(row, 0, "CANTIDADES POR COLORES", title)
    row += 1
    ws.write(
        row, 0,
        "SHORT PLAYA CAB · Agotar tela: Aguamarina, Verde Oliva, Azul Marino, Gris Azulado, "
        f"Verde Pino · Tela ROJO = producto CEREZA · Otros colores reforzados ×{OTHER_BOOST}",
        note,
    )
    row += 1
    ws.write(row, 0, f"Rango producción: {rango['total_min']} – {rango['total_max']} und", bold)
    row += 2
    ws.write(row, 0, f"MÍNIMO — {rango['total_min']} und", bold)
    row += 1
    ws.write_row(row, 0, ["SHORT PLAYA CAB"] + active_tallas + ["Tot"], hdr)
    row += 1
    for cr in rango["color_rows"]:
        if cr["min"] <= 0:
            continue
        label = cr["color"]
        if cr.get("tela_fabric"):
            label += f" · tela {cr['tela_fabric']}"
        if cr["strategy"] == "reforzado":
            label += " · REF ↑"
        ws.write_row(
            row, 0,
            [label] + [cr["talla_totals_min"].get(t, 0) for t in active_tallas] + [cr["min"]],
        )
        row += 1
    ws.write_row(
        row, 0,
        ["TOTAL GENERAL"] + [rango["talla_totals"][t]["min"] for t in active_tallas] + [rango["total_min"]],
        bold,
    )
    row += 2
    ws.write(row, 0, f"MÁXIMO — {rango['total_max']} und (tope)", bold)
    row += 1
    ws.write_row(row, 0, ["SHORT PLAYA CAB"] + active_tallas + ["Tot"], hdr)
    row += 1
    for cr in rango["color_rows"]:
        if cr["max"] <= 0:
            continue
        label = cr["color"]
        if cr.get("tela_fabric"):
            label += f" · tela {cr['tela_fabric']}"
        ws.write_row(
            row, 0,
            [label] + [cr["talla_totals_max"].get(t, 0) for t in active_tallas] + [cr["max"]],
        )
        row += 1
    ws.write_row(
        row, 0,
        ["TOTAL GENERAL"] + [rango["talla_totals"][t]["max"] for t in active_tallas] + [rango["total_max"]],
        bold,
    )

    # ── 2. Producción por Talla ──
    ws = wb.add_worksheet("Producción por Talla")
    row = 0
    ws.write(row, 0, "SHORT PLAYA CAB — CANTIDADES POR TALLA (MÍN / MÁX)", title)
    row += 2
    ws.write_row(row, 0, ["Talla", "Curva %", "Mínimo", "Máximo"], hdr)
    row += 1
    for t in active_tallas:
        td = rango["talla_totals"][t]
        ws.write_row(row, 0, [t, td["curve_pct"] / 100, td["min"], td["max"]])
        row += 1
    ws.write_row(row, 0, ["TOTAL", "", rango["total_min"], rango["total_max"]], bold)

    # ── 3. Producción Color × Talla ──
    ws = wb.add_worksheet("Producción Color × Talla")
    row = 0
    ws.write(row, 0, "SHORT PLAYA CAB — PRODUCCIÓN POR COLOR Y TALLA", title)
    row += 1
    ws.write(row, 0, f"Rango global: {rango['total_min']} – {rango['total_max']} und · Rotación últimos 6 meses × {HIGH_SEASON}", note)
    row += 2
    for cr in rango["color_rows"]:
        if cr["min"] <= 0:
            continue
        strat = "AGOTAR TELA" if cr["strategy"] == "agotar_tela" else "REFORZADO"
        extra = ""
        if cr.get("tela_fabric"):
            extra = f" · Tela {cr['tela_fabric']} ({cr.get('tela_m', 0):.1f} m)"
        ws.write(row, 0, f"{cr['modelo']} · {cr['color']} [{strat}{extra}]", bold)
        row += 1
        ws.write_row(row, 0, ["Talla", "Mín", "Máx", "Vel/mes", "Stock", "Cob (m)"], hdr)
        row += 1
        for t in cr["tallas"]:
            ws.write_row(row, 0, [t["talla"], t["min"], t["max"], t["v_mes"], t["stk"], t["cob"]])
            row += 1
        ws.write_row(row, 0, ["TOTAL color", cr["min"], cr["max"], "", "", ""], bold)
        row += 2

    # ── 4. Distribución por Tienda ──
    ws = wb.add_worksheet("Distribución por Tienda")
    row = 0
    ws.write(row, 0, "SHORT PLAYA CAB — DISTRIBUCIÓN POR TIENDA Y TALLA", title)
    row += 1
    ws.write(row, 0, "★ LA VELA / TOLON · MGTA playa priorizada (VELA 1,5× GRIETA)", note)
    row += 2
    hdr_cells = ["Tienda"] + [x for t in active_tallas for x in (t, "")]
    hdr_cells.append("Tot")
    ws.write_row(row, 0, hdr_cells, hdr)
    row += 1
    sub = [""] + ["Mín", "Máx"] * len(active_tallas) + [""]
    ws.write_row(row, 0, sub, hdr)
    row += 1
    col_tot_min = defaultdict(int)
    for store in DIST_STORES:
        st = rango["store_talla"].get(store, {})
        vals = [STORE_LABELS.get(store, store)]
        st_min = st_max = 0
        for t in active_tallas:
            mn = st.get(t, {}).get("min", 0)
            mx = st.get(t, {}).get("max", 0)
            vals.extend([mn, mx])
            st_min += mn
            st_max += mx
            col_tot_min[t] += mn
        if st_min <= 0:
            continue
        vals.append(st_min)
        ws.write_row(row, 0, vals)
        row += 1
    total_row = ["TOTAL"]
    gt = 0
    for t in active_tallas:
        total_row.extend([col_tot_min[t], rango["talla_totals"][t]["max"]])
        gt += col_tot_min[t]
    total_row.append(gt)
    ws.write_row(row, 0, total_row, bold)

    # ── 5. Uso de Tela Short Playa ──
    ws = wb.add_worksheet("Uso de Tela Short Playa")
    row = 0
    ws.write(row, 0, "SHORT PLAYA CAB — TELA EXISTENTE A AGOTAR + COMPRA REFUERZO", title)
    row += 1
    ws.write(row, 0, f"Consumo ficha técnica: {FABRIC_M} m/pieza · SS tela +{int(TELA_SS*100)}% en compra nueva", note)
    row += 2
    ws.write_row(
        row, 0,
        ["Tela", "Producto", "Estrategia", "Mts existentes", "Und Mín", "Und Máx",
         "Mts uso Mín", "Mts uso Máx", "Notas"],
        hdr,
    )
    row += 1
    tot_min = tot_max = 0.0
    for cr in rango["color_rows"]:
        mts_min = cr["min"] * FABRIC_M
        mts_max = cr["max"] * FABRIC_M
        nota = ""
        if cr["strategy"] == "agotar_tela":
            nota = "Agotar existencia de tela"
            if cr["color"] == "Cereza":
                nota += " · Tela ROJO"
        else:
            nota = f"Compra/refuerzo ×{OTHER_BOOST} · cobertura {TARGET_COB_BOOST}m"
        ws.write_row(
            row, 0,
            [
                cr.get("tela_fabric") or "—",
                f"{cr['modelo']} · {cr['color']}",
                "AGOTAR" if cr["strategy"] == "agotar_tela" else "REF ↑",
                cr.get("tela_m") or "",
                cr["min"], cr["max"],
                round(mts_min, 2), round(mts_max, 2),
                nota,
            ],
        )
        tot_min += mts_min
        tot_max += mts_max
        row += 1
    ws.write_row(row, 0, ["TOTAL", "", "", "", rango["total_min"], rango["total_max"], round(tot_min, 2), round(tot_max, 2), ""], bold)
    row += 3
    ws.write(row, 0, "Metros existentes configurados (agotar):", bold)
    row += 1
    for tela_name, meters in rango["tela_meters"].items():
        if tela_name.startswith("_"):
            continue
        prod = TELA_AGOTAR.get(tela_name, ("", ""))[1]
        ws.write_row(row, 0, [tela_name, prod, meters, int(math.floor(meters / FABRIC_M)) if meters else 0])
        row += 1

    wb.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", default=str(HTML))
    parser.add_argument("--out", default=str(OUT_XLSX))
    parser.add_argument("--tela", help="INVENTARIO TELA SHORT PLAYA.xlsx")
    parser.add_argument("--tela-json", default=str(TELA_JSON))
    args = parser.parse_args()

    data = load_data()
    tela_meters = load_tela_meters(
        Path(args.tela) if args.tela else None,
        Path(args.tela_json) if args.tela_json else None,
    )

    missing = [k for k in TELA_AGOTAR if tela_meters.get(k, 0) <= 0]
    if missing:
        print("⚠ Sin metros de tela para:", ", ".join(missing), file=sys.stderr)
        print("  Edita scripts/short_playa_tela_metros.json o pasa --tela", file=sys.stderr)

    rango = build_rango(data, tela_meters)
    export_excel(rango, Path(args.out))

    print(f"✓ {args.out}")
    print(f"  Rango: {rango['total_min']} – {rango['total_max']} und")
    print(f"  Colores: {len(rango['color_rows'])}")
    agotar = [cr for cr in rango["color_rows"] if cr["strategy"] == "agotar_tela"]
    ref = [cr for cr in rango["color_rows"] if cr["strategy"] == "reforzado"]
    print(f"  Agotar tela: {sum(c['min'] for c in agotar)} und ({len(agotar)} colores)")
    print(f"  Reforzados: {sum(c['min'] for c in ref)} und ({len(ref)} colores)")


if __name__ == "__main__":
    main()
