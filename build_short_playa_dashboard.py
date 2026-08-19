#!/usr/bin/env python3
"""Build Short Playa dashboard DATA from CSV files."""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

VENTAS_PATH = Path(__file__).resolve().parent / "data" / "short_playa_ventas.csv"
INV_PATH = Path(__file__).resolve().parent / "data" / "short_playa_inventario.csv"
JACKET_TEMPLATE = Path(__file__).resolve().parent / "Dashboard_Jacket_2_0 (3).html"
TEMPLATE_PATH = Path(__file__).resolve().parent / "dash_shortplaya_template.html"
OUTPUT_PATH = Path(__file__).resolve().parent / "dash_shortplaya.html"

MODELS = ["SHORT PLAYA UNICOLOR", "SHORT PLAYA SUBLIMADO"]
MODEL_SUBLIMADO = "SHORT PLAYA SUBLIMADO"
MODEL_UNICOLOR = "SHORT PLAYA UNICOLOR"
UNICOLOR_ACTIVE_COLORS = {
    "Verde Pino", "Azul Pizarra", "Azul Verdoso", "Marron", "Cereza",
}
SUBLIMADO_ACTIVE_COLORS = {"Playuela", "Sal", "Tucupido", "Sombrero"}
COLOR_ALIASES = {
    "sal": "Sal",
    "playuela": "Playuela",
    "tucupido": "Tucupido",
    "sombrero": "Sombrero",
    "verde pino": "Verde Pino",
    "azul pizarra": "Azul Pizarra",
    "azul verdoso": "Azul Verdoso",
    "marron": "Marron",
    "marrón": "Marron",
    "cereza": "Cereza",
    "aguamarina": "Aguamarina",
    "terracota": "Terracota",
    "gris azulado": "Gris Azulado",
    "azul marino": "Azul Marino",
    "kaki": "Kaki",
    "azul rey": "Azul Rey",
    "rojo": "Rojo",
    "verde oliva": "Verde Oliva",
    "coral": "Coral",
    "royal": "Royal",
}
LINEAS = ["CAB", "KIDS"]
MESES_ORDER = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
MESES_MAP = {m.upper(): m for m in MESES_ORDER}
ME_SHORT = {
    "enero": "Ene", "febrero": "Feb", "marzo": "Mar", "abril": "Abr",
    "mayo": "May", "junio": "Jun", "julio": "Jul", "agosto": "Ago",
    "septiembre": "Sep", "octubre": "Oct", "noviembre": "Nov", "diciembre": "Dic",
}
PARTIAL_MONTH = "agosto-2026"
VELOCITY_MONTHS_COUNT = 6
HIGH_SEASON_FACTOR = 1.25
LEAD_MONTHS = 3
ALL_STORES = [
    "CERRO VERDE", "CHACAO", "GRAND PLAZ", "GRIETA", "SAMBIL",
    "TOLON", "WEB", "PEDIDOS", "CORPORATIVO", "VELA",
]
STORE_ORDER = ALL_STORES + ["BARQUISIMETO", "TALLER"]
DECISION_EXCLUDE_STORES = {"WEB", "PEDIDOS", "CORPORATIVO", "VELA"}
NEW_STORES = ["VELA", "BARQUISIMETO"]
NEW_STORE_CAPS = {
    "VELA": {"base": "GRIETA", "mult": 1.5, "label": "1.5× GRIETA"},
    "BARQUISIMETO": {"base": "GRIETA", "mult": 1, "label": "1× GRIETA"},
}
STORE_ALIASES = {
    "LA GRIETA": "GRIETA",
    "GRIETA": "GRIETA",
    "GRIE": "GRIETA",
    "SAMBIL VALENCIA": "SAMBIL",
    "SAMBIL": "SAMBIL",
    "SAMBIL CHACAO": "CHACAO",
    "Sambil Chacao": "CHACAO",
    "Sambil Valencia": "SAMBIL",
    "CHACAO": "CHACAO",
    "CERRO VERDE": "CERRO VERDE",
    "Cerro Verde": "CERRO VERDE",
    "GRAND PLAZ": "GRAND PLAZ",
    "GRANDPLAZ": "GRAND PLAZ",
    "Grandplaz": "GRAND PLAZ",
    "GRAND PLAZA": "GRAND PLAZ",
    "LA VELA": "VELA",
    "La Vela": "VELA",
    "VELA": "VELA",
    "TOLON": "TOLON",
    "Tolon": "TOLON",
    "TOLÓN": "TOLON",
    "WEB": "WEB",
    "PEDIDOS": "PEDIDOS",
    "Pedidos": "PEDIDOS",
    "CORPORATIVO": "CORPORATIVO",
    "BARQUISIMETO": "BARQUISIMETO",
    "TALLER": "TALLER",
    "TALLER TERMINADO": "TALLER",
}


def read_csv(path: Path):
    for enc in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            with path.open(encoding=enc, newline="") as f:
                return list(csv.DictReader(f, delimiter=";"))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode {path}")


def parse_num(value) -> float:
    if value is None:
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def get_col_like(row: dict, *patterns: str) -> str:
    for pat in patterns:
        for k, v in row.items():
            if pat.upper() in k.upper() and v is not None:
                return str(v).strip()
    return ""


def normalize_store(name: str) -> str:
    n = re.sub(r"\s+", " ", name.strip())
    key = n.upper()
    if key in STORE_ALIASES:
        return STORE_ALIASES[key]
    if n in STORE_ALIASES:
        return STORE_ALIASES[n]
    return key


def normalize_genero(value: str) -> str:
    g = str(value).strip().upper()
    if g in ("CABALLERO", "CAB"):
        return "CAB"
    if g == "KIDS":
        return "KIDS"
    return g


def normalize_color(value: str) -> str:
    c = str(value).strip()
    if not c:
        return c
    key = c.lower()
    if key in COLOR_ALIASES:
        return COLOR_ALIASES[key]
    return c[0].upper() + c[1:] if len(c) > 1 else c.upper()


def normalize_modelo(producto: str) -> str:
    p = producto.upper().strip()
    if "ESTAMPADO" in p:
        return MODEL_SUBLIMADO
    return MODEL_UNICOLOR


def normalize_modelo_inv(modelo: str) -> str:
    m = modelo.upper().strip()
    if "ESTAMPADO" in m:
        return MODEL_SUBLIMADO
    return MODEL_UNICOLOR


def is_active_color(modelo: str, color: str) -> bool:
    if modelo == MODEL_UNICOLOR:
        return color in UNICOLOR_ACTIVE_COLORS
    if modelo == MODEL_SUBLIMADO:
        return color in SUBLIMADO_ACTIVE_COLORS
    return True


def include_in_dashboard(modelo: str, color: str) -> bool:
    if modelo == MODEL_SUBLIMADO:
        return color in SUBLIMADO_ACTIVE_COLORS
    return True


def mes_sort_key(mes: str):
    part, year = mes.rsplit("-", 1)
    return (int(year), MESES_ORDER.index(part))


def month_label(mes: str) -> str:
    part, year = mes.rsplit("-", 1)
    return f"{ME_SHORT[part]} {year[-2:]}"


def velocity_months(meses_order):
    n = VELOCITY_MONTHS_COUNT
    if PARTIAL_MONTH in meses_order and meses_order.index(PARTIAL_MONTH) >= n:
        i = meses_order.index(PARTIAL_MONTH)
        return meses_order[i - n : i]
    return meses_order[-n:]


def compute_production_plan(raw_rows, stock, stock_taller_by_key):
    vel_months = velocity_months(sorted({r["mes"] for r in raw_rows}, key=mes_sort_key))
    production_rows = []

    for modelo in MODELS:
        model_rows = [r for r in raw_rows if r["modelo"] == modelo]
        if not model_rows:
            continue
        for genero in LINEAS:
            colors = sorted(
                {
                    r["color"] for r in model_rows
                    if r["genero"] == genero and is_active_color(modelo, r["color"])
                }
            )
            for color in colors:
                tallas = sorted(
                    {
                        r["talla"] for r in model_rows
                        if r["genero"] == genero and r["color"] == color
                    },
                    key=lambda t: (len(t), t),
                )
                talla_rows = []
                color_v = 0.0
                color_v_base = 0.0
                color_stk = 0
                color_stk_taller = 0
                color_produce = 0

                for talla in tallas:
                    base_v = sum(
                        r["v"] for r in model_rows
                        if r["genero"] == genero and r["color"] == color and r["talla"] == talla
                        and r["mes"] in vel_months
                    ) / max(len(vel_months), 1)
                    v_mes_base = round(base_v, 1)
                    v_mes = round(base_v * HIGH_SEASON_FACTOR, 1)
                    key = f"{modelo}/{genero}/{color}/{talla}"
                    stk = int(stock.get(key, 0))
                    stk_taller = int(stock_taller_by_key.get(key, 0))
                    cob = round(stk / v_mes, 1) if v_mes > 0 else 999
                    if cob < LEAD_MONTHS:
                        need = max(0, round(v_mes * LEAD_MONTHS - stk))
                    else:
                        need = 0
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

    return production_rows, summary, summary_genero, vel_months


def compute_new_store_projection(raw_rows, base_store, mult, meses):
    grie_monthly = defaultdict(float)
    for r in raw_rows:
        if r["tienda"] == base_store and r["mes"] in meses and r.get("activo", True):
            key = (r["modelo"], r["genero"], r["color"], r["talla"])
            grie_monthly[key] += r["v"]
    n = max(len(meses), 1)
    skus = []
    total_v = 0.0
    for (modelo, genero, color, talla), qty in sorted(grie_monthly.items()):
        v_mes = round(qty / n * mult * HIGH_SEASON_FACTOR, 2)
        total_v += v_mes
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
        "nota": f"{mult}× velocidad {base_store} · factor temporada alta ×{HIGH_SEASON_FACTOR}",
        "skus": skus,
    }


def build_data():
    ventas = read_csv(VENTAS_PATH)
    inv = read_csv(INV_PATH)

    raw_rows = []
    tiendas_set = set()
    colores_set = set()
    generos_set = set()
    returns_units = 0

    for r in ventas:
        qty = parse_num(get_col_like(r, "Cant. ordenada", "Cant ordenada"))
        if qty == 0:
            continue
        mes = f"{MESES_MAP[r["Mes"].strip().upper()]}-{r['Año'].strip()}"
        genero = normalize_genero(get_col_like(r, "GENERO", "Genero"))
        color = normalize_color(get_col_like(r, "COLOR", "Color"))
        talla = get_col_like(r, "TALLA", "Talla")
        tienda = normalize_store(get_col_like(r, "tienda / ubic", "ubic"))
        producto = get_col_like(r, "Producto")
        modelo = normalize_modelo(producto)
        if not include_in_dashboard(modelo, color):
            continue
        v = round(qty)
        if v < 0:
            returns_units += v
        tiendas_set.add(tienda)
        colores_set.add(color)
        generos_set.add(genero)
        raw_rows.append({
            "tienda": tienda,
            "genero": genero,
            "color": color,
            "talla": talla,
            "mes": mes,
            "modelo": modelo,
            "activo": is_active_color(modelo, color),
            "v": v,
        })

    meses_order = sorted({r["mes"] for r in raw_rows}, key=mes_sort_key)
    meses_und = {m: sum(r["v"] for r in raw_rows if r["mes"] == m) for m in meses_order}
    total = sum(r["v"] for r in raw_rows)

    stock = defaultdict(int)
    stock_by_store = defaultdict(lambda: defaultdict(int))
    stock_taller_by_key = defaultdict(int)
    stock_by_modelo = defaultdict(int)
    negative_stock_units = 0

    for r in inv:
        store = normalize_store(get_col_like(r, "Ubicac"))
        genero = normalize_genero(get_col_like(r, "GENERO", "Genero"))
        color = normalize_color(get_col_like(r, "COLOR", "Color"))
        talla = get_col_like(r, "TALLA", "Talla", "talla")
        modelo = normalize_modelo_inv(get_col_like(r, "MODELO", "Modelo"))
        if not include_in_dashboard(modelo, color):
            continue
        qty = round(parse_num(get_col_like(r, "Cantidad")))
        if qty < 0:
            negative_stock_units += qty
            continue
        if qty == 0:
            continue
        key = f"{modelo}/{genero}/{color}/{talla}"
        stock[key] += qty
        stock_by_store[store][key] += qty
        stock_by_modelo[modelo] += qty
        if store == "TALLER":
            stock_taller_by_key[key] += qty

    stock = {k: max(0, v) for k, v in stock.items()}
    stock_by_store = {
        store: {k: v for k, v in items.items() if v > 0}
        for store, items in (
            {s: {k: max(0, v) for k, v in d.items()} for s, d in stock_by_store.items()}
        ).items()
        if any(v > 0 for v in items.values())
    }
    stock_taller_by_key = {k: max(0, v) for k, v in stock_taller_by_key.items()}
    stock_by_modelo = defaultdict(int)
    for key, qty in stock.items():
        stock_by_modelo[key.split("/")[0]] += qty

    stock_total = sum(stock.values())
    stock_taller = sum(stock_by_store.get("TALLER", {}).values())

    production_plan, summary_produccion, summary_genero, vel_months = compute_production_plan(
        raw_rows, stock, stock_taller_by_key
    )
    barquisimeto_proj = compute_new_store_projection(raw_rows, "GRIETA", 1, vel_months)
    vela_proj = compute_new_store_projection(raw_rows, "GRIETA", 1.5, vel_months)

    tiendas_list = [s for s in ALL_STORES if s in tiendas_set]
    for s in sorted(tiendas_set):
        if s not in tiendas_list and s != "TALLER":
            tiendas_list.append(s)

    stores_present = set(stock_by_store.keys())
    stores_order = [s for s in STORE_ORDER if s in stores_present]
    for s in sorted(stores_present):
        if s not in stores_order:
            stores_order.append(s)

    periodo = f"{month_label(meses_order[0])} — {month_label(meses_order[-1])}"
    vel_labels = " · ".join(month_label(m) for m in vel_months)

    return {
        "raw_rows": raw_rows,
        "stock": dict(stock),
        "stock_by_store": {k: dict(v) for k, v in stock_by_store.items()},
        "stock_by_modelo": dict(stock_by_modelo),
        "meses_order": meses_order,
        "meses_und": meses_und,
        "filtros": {
            "tiendas": tiendas_list,
            "generos": [g for g in LINEAS if g in generos_set],
            "colores": sorted(colores_set),
            "modelos": MODELS,
        },
        "es_parcial": PARTIAL_MONTH in meses_order,
        "stock_total": stock_total,
        "stock_taller": stock_taller,
        "total": total,
        "all_stores": ALL_STORES,
        "stores_order": stores_order,
        "production_plan": production_plan,
        "summary_produccion": summary_produccion,
        "summary_genero": summary_genero,
        "barquisimeto": barquisimeto_proj,
        "vela": vela_proj,
        "new_stores": NEW_STORES,
        "new_store_caps": NEW_STORE_CAPS,
        "decision_exclude_stores": sorted(DECISION_EXCLUDE_STORES),
        "decision_stores": [s for s in ALL_STORES if s not in DECISION_EXCLUDE_STORES],
        "lead_months": LEAD_MONTHS,
        "high_season_factor": HIGH_SEASON_FACTOR,
        "velocity_months_count": VELOCITY_MONTHS_COUNT,
        "velocity_months": vel_months,
        "velocity_months_label": vel_labels,
        "periodo": periodo,
        "colores_activos": {
            MODEL_UNICOLOR: sorted(UNICOLOR_ACTIVE_COLORS),
            MODEL_SUBLIMADO: sorted(SUBLIMADO_ACTIVE_COLORS),
        },
        "colores_descontinuados": sorted(
            {r["color"] for r in raw_rows if r["modelo"] == MODEL_UNICOLOR and not r.get("activo", True)}
        ),
        "_meta": {
            "returns_units": returns_units,
            "negative_stock_units": negative_stock_units,
        },
    }


def ensure_template():
    if TEMPLATE_PATH.exists():
        return
    if not JACKET_TEMPLATE.exists():
        raise FileNotFoundError("Missing jacket template for Short Playa adaptation")

    html = JACKET_TEMPLATE.read_text(encoding="utf-8")
    html = re.sub(
        r"var DATA=\{.*?\};\s*\nvar _modelo",
        "var DATA=__DATA__;\nvar _modelo",
        html,
        count=1,
        flags=re.DOTALL,
    )

    replacements = [
        ("Jacket 2.0", "Short Playa"),
        ("Cuadro Jacket 2.0", "Short Playa"),
        ("Cuadro", "Short Playa"),
        ("JACKET 2.0", "SHORT PLAYA"),
        ("🧥 Modelo:", "🩳 Línea:"),
        ("🧥 Cuadro Jacket 2.0", "🩳 Todas las líneas"),
        ("CUADRO JACKET 2.0", "SHORT PLAYA UNICOLOR"),
        ("var MICO={'CUADRO JACKET 2.0':'🧥'};",
         "var MICO={'SHORT PLAYA UNICOLOR':'🩳','SHORT PLAYA ESTAMPADO':'🌴'};"),
        ("var MODELO_ID={'CUADRO JACKET 2.0':'CUADRO_JACKET_2_0'};",
         "var MODELO_ID={'SHORT PLAYA UNICOLOR':'UNICOLOR','SHORT PLAYA ESTAMPADO':'ESTAMPADO'};"),
        ("var sn={'CUADRO JACKET 2.0':'Cuadro'};",
         "var sn={'SHORT PLAYA UNICOLOR':'Unicolor','SHORT PLAYA ESTAMPADO':'Estampado'};"),
        ("if(titleEl){var sn={'CUADRO JACKET 2.0':'Cuadro'};titleEl.textContent='Cuadro';}",
         "if(titleEl){var sn={'SHORT PLAYA UNICOLOR':'Unicolor','SHORT PLAYA ESTAMPADO':'Estampado'};titleEl.textContent=sn[m]||'Short Playa';}"),
        ("titleEl.textContent='Global'",
         "titleEl.textContent='Short Playa'"),
        ("CAB vs DAMA", "CAB vs KIDS"),
        ("['CAB','DAMA','KIDS']", "['CAB','KIDS']"),
        ("var GICO={CAB:'👔',DAMA:'👗',KIDS:'👶'};",
         "var GICO={CAB:'👔',KIDS:'👶'};"),
        ("🛒 Compra Sugerida por Variante", "🏭 Producción Sugerida por Variante"),
        ("Sugerencia proporcional por color y talla · Clic en color para detalle",
         "¿Necesita fabricar? · Desglose por color y talla · Manufacturado"),
        ("Distribución sugerida · <span style=\"color:#f97316\">VELA y BARQUISIMETO proyectadas como 1× GRIETA · factor temporada alta ×<span id=\"hsFactorLabel\">1.25</span></span>",
         "Distribución sugerida por tienda · factor temporada alta ×<span id=\"hsFactorLabel\">1.25</span>"),
        ("DATA.purchase_plan", "DATA.production_plan"),
        ("DATA.summary_compra", "DATA.summary_produccion"),
        (".buy", ".produce"),
        ("+r.buy", "+r.produce"),
        ("smry.buy", "smry.produce"),
        ("cp.buy", "cp.produce"),
        ("t.buy", "t.produce"),
        ("totalBuy", "totalProduce"),
        ("Comprar ", "Producir "),
        ("comprar", "producir"),
        ("Compra sugerida", "Producción sugerida"),
        ("compra ahora", "producción ahora"),
        ("Unidades a comprar", "Unidades a producir"),
        ("Lead 3m · Cubre 9 meses", "Tiempo prod. 3m · Cubre 9 meses"),
        ("Lead 3m · Cubre 9 meses", "Tiempo prod. 3m · Cubre 9 meses"),
        ("Lead time = 90 días (3 meses). 2 compras/año → cada compra debe cubrir 6 meses de venta + 3 meses de tránsito = <strong style=\"color:var(--tx)\">9 meses de cobertura total</strong>. ",
         "Tiempo de producción = 90 días (3 meses). Planificar lotes para cubrir 6 meses de venta + 3 meses de tránsito = <strong style=\"color:var(--tx)\">9 meses de cobertura total</strong>. "),
        ("Metodología — rotación y compras", "Metodología — rotación y producción"),
        ("Es la velocidad usada para cobertura y compra.", "Es la velocidad usada para cobertura y producción."),
        ("Compra sugerida", "Producción sugerida"),
        ("var NEW_STORES=['VELA','BARQUISIMETO'];", "var NEW_STORES=[];"),
        ("var NEW_STORE_CAPS={'VELA':{base:'GRIETA',mult:1,label:'1× GRIETA'},'BARQUISIMETO':{base:'GRIETA',mult:1,label:'1× GRIETA'}};",
         "var NEW_STORE_CAPS={};"),
        ("'Jacket_2_0.csv'", "'ShortPlaya.csv'"),
    ]

    for old, new in replacements:
        html = html.replace(old, new)

    # Model selector buttons
    html = html.replace(
        '<div class="mbar"><span class="mbar-lbl">🩳 Línea:</span><button class="mbtn active" data-m="" onclick="setModelo(\'\')">🩳 Todas las líneas <span class="mcnt" id="mcnt_all">0</span></button></div>',
        '<div class="mbar"><span class="mbar-lbl">🩳 Línea:</span>'
        '<button class="mbtn active" data-m="" onclick="setModelo(\'\')">🩳 Todas <span class="mcnt" id="mcnt_all">0</span></button>'
        '<button class="mbtn" data-m="SHORT PLAYA UNICOLOR" onclick="setModelo(\'SHORT PLAYA UNICOLOR\')">🩳 Unicolor <span class="mcnt" id="mcnt_UNICOLOR">0</span></button>'
        '<button class="mbtn" data-m="SHORT PLAYA ESTAMPADO" onclick="setModelo(\'SHORT PLAYA ESTAMPADO\')">🌴 Estampado <span class="mcnt" id="mcnt_ESTAMPADO">0</span></button>'
        '</div>',
    )

    # Add inventario tab if missing
    if "st('inventario')" not in html:
        html = html.replace(
            '<button class="tab" onclick="st(\'tiendas\')">🏪 Tiendas</button>',
            '<button class="tab" onclick="st(\'tiendas\')">🏪 Tiendas</button>\n'
            '  <button class="tab" onclick="st(\'inventario\')">📦 Inventario</button>',
        )
        html = html.replace(
            '<!-- DECISIONES -->',
            '<div class="sec" id="sec-inventario">\n'
            '  <div class="tkpis" id="invKpis"></div>\n'
            '  <div class="g1 card"><h3>📦 Inventario por Tienda</h3>'
            '<div class="sub">Stock disponible por punto de venta y taller · clic en tienda para ver colores, clic en color para ver tallas</div>'
            '<div id="invByStore" style="margin-top:10px"></div></div>\n'
            '  <div class="g1 card"><h3>Color × Tienda (Inventario)</h3>'
            '<div class="sub">Heatmap de stock disponible</div>'
            '<div class="hmw" id="invColorTiendaHM"></div></div>\n'
            '</div>\n\n<!-- DECISIONES -->',
        )
        inv_js = """
function stockKeyParts(key){var p=key.split('/');return{modelo:p[0]||'',genero:p[1]||'',color:p[2]||'',talla:p[3]||''};}
function stockMatchesFilters(key,f){var p=stockKeyParts(key);if(_modelo&&p.modelo!==_modelo)return false;if(f.genero&&p.genero!==f.genero)return false;if(f.color&&p.color!==f.color)return false;return true;}
function getFilteredStockByStore(){var f=gf(),sbs=DATA.stock_by_store||{},out={};Object.keys(sbs).forEach(function(store){if(f.tienda&&store!==f.tienda)return;var data=sbs[store]||{},filtered={};Object.entries(data).forEach(function(kv){if(stockMatchesFilters(kv[0],f))filtered[kv[0]]=kv[1];});if(Object.keys(filtered).length)out[store]=filtered;});return out;}
function getStockTotals(sbs){var storeTotals={},grand=0,tallerTotal=0;Object.keys(sbs).forEach(function(s){var t=0;Object.values(sbs[s]||{}).forEach(function(q){t+=q;});storeTotals[s]=t;grand+=t;if(s==='TALLER')tallerTotal=t;});return{storeTotals:storeTotals,grand:grand,tiendaTotal:grand-tallerTotal,tallerTotal:tallerTotal};}
function toggleInv(uid){var d=document.getElementById(uid);if(!d)return;var open=d.style.display!=='block';d.style.display=open?'block':'none';var arr=document.getElementById('arr_'+uid);if(arr)arr.style.transform=open?'rotate(90deg)':'rotate(0deg)';}
function toggleInvCol(uid){var d=document.getElementById(uid);if(d)d.style.display=d.style.display==='block'?'none':'block';}
var STORE_LABELS={'CERRO VERDE':'C.Verde','GRAND PLAZ':'Grand Plaz','GRIETA':'Grieta','SAMBIL':'Sambil','CHACAO':'Chacao','TOLON':'Tolón','WEB':'Web','PEDIDOS':'Pedidos','CORPORATIVO':'Corporativo','VELA':'Vela','TALLER':'Taller'};
function rInventario(){
  var sbs=getFilteredStockByStore(),tot=getStockTotals(sbs),order=(DATA.stores_order||[]).filter(function(s){return sbs[s];});
  document.getElementById('invKpis').innerHTML='<div class="tkpi"><div class="tv">'+tot.grand.toLocaleString()+'</div><div class="tl">Stock total</div></div><div class="tkpi"><div class="tv">'+tot.tiendaTotal.toLocaleString()+'</div><div class="tl">En Tiendas</div></div><div class="tkpi" style="border-color:#f97316"><div class="tv" style="color:#f97316">'+tot.tallerTotal.toLocaleString()+'</div><div class="tl">🏭 En Taller</div></div>';
  var h='',colorGrand={};order.forEach(function(store){Object.entries(sbs[store]||{}).forEach(function(kv){var c=stockKeyParts(kv[0]).color;colorGrand[c]=(colorGrand[c]||0)+kv[1];});});
  order.forEach(function(store){
    var storeTotals=tot.storeTotals,isTaller=store==='TALLER';
    var colorMap={};Object.entries(sbs[store]||{}).forEach(function(kv){var p=stockKeyParts(kv[0]);colorMap[p.color]=(colorMap[p.color]||0)+kv[1];});
    var colorItems=Object.entries(colorMap).sort(function(a,b){return b[1]-a[1];}).map(function(ce){
      var col=ce[0],colV=ce[1],tA={};Object.entries(sbs[store]||{}).forEach(function(kv){var p=stockKeyParts(kv[0]);if(p.color===col)tA[p.talla]=(tA[p.talla]||0)+kv[1];});
      var tRows=Object.entries(tA).sort(function(a,b){return b[1]-a[1];}).map(function(tv){return'<div style="display:flex;gap:6px;padding:2px 0;font-size:0.68rem"><div style="width:70px;font-weight:700;color:#c0c0e8">'+tv[0]+'</div><div style="color:var(--mu)">'+tv[1]+' und</div></div>';}).join('');
      var cUid='inv_'+store.replace(/[^a-z0-9]/gi,'_')+'_'+col.replace(/[^a-z0-9]/gi,'_');
      return'<div style="padding:2px 0"><div onclick="toggleInvCol(\\''+cUid+'\\')" style="display:flex;align-items:center;gap:6px;cursor:pointer;padding:3px 4px;border-radius:5px;font-size:0.73rem"><span style="width:8px;height:8px;border-radius:50%;background:'+cn(col)+'"></span><span style="flex:1;color:#e0e0f5">'+col+'</span><span style="color:var(--yw);font-weight:700;font-size:0.68rem">'+colV+'</span><span style="color:var(--ac);font-size:0.55rem">▶</span></div><div id="'+cUid+'" style="display:none;margin-left:16px;padding:2px 6px;border-left:2px solid '+cn(col)+'33">'+tRows+'</div></div>';
    }).join('');
    var sUid='inv_'+store.replace(/[^a-z0-9]/gi,'_'),ico=isTaller?'🏭':'🏪',bg=isTaller?'rgba(249,115,22,.08)':'var(--s2)',bdr=isTaller?'#f9731633':'var(--brd)';
    h+='<div style="background:'+bg+';border:1px solid '+bdr+';border-radius:12px;margin-bottom:10px"><div onclick="toggleInv(\\''+sUid+'\\')" style="display:flex;align-items:center;gap:10px;padding:14px 16px;cursor:pointer"><span id="arr_'+sUid+'" style="color:var(--ac);font-size:0.7rem">▶</span><div style="flex:1"><div style="font-family:var(--fh);font-weight:800;font-size:0.85rem">'+ico+' '+(STORE_LABELS[store]||store)+'</div>'+(isTaller?'<div style="font-size:0.6rem;color:#f97316">Recién producido · pendiente por distribuir</div>':'')+'</div><div style="text-align:right"><div style="font-family:var(--fh);font-weight:800;color:'+(isTaller?'#f97316':'var(--yw)')+';font-size:1.1rem">'+storeTotals[store]+'</div><div style="font-size:0.6rem;color:var(--mu)">und</div></div></div><div id="'+sUid+'" style="display:none;padding:0 16px 14px">'+(colorItems||'<div class="nodata">Sin stock</div>')+'</div></div>';
  });
  document.getElementById('invByStore').innerHTML=h;
  var colores=Object.keys(colorGrand).sort(function(a,b){return colorGrand[b]-colorGrand[a];}),allV=[],mx=1;
  colores.forEach(function(c){order.forEach(function(s){var v=0;Object.entries(sbs[s]||{}).forEach(function(kv){if(stockKeyParts(kv[0]).color===c)v+=kv[1];});allV.push(v);});});
  mx=Math.max.apply(null,allV.concat([1]));
  document.getElementById('invColorTiendaHM').innerHTML=colores.length?'<table class="hmt"><thead><tr><th></th>'+order.map(function(s){return'<th>'+(STORE_LABELS[s]||s)+'</th>';}).join('')+'</tr></thead><tbody>'+colores.map(function(c){return'<tr><td class="rl"><span class="chip" style="background:'+cn(c)+'"></span>'+c+'</td>'+order.map(function(s){var v=0;Object.entries(sbs[s]||{}).forEach(function(kv){if(stockKeyParts(kv[0]).color===c)v+=kv[1];});return'<td style="background:'+hb(v,mx)+';color:'+ht(v,mx)+'">'+(v||'—')+'</td>';}).join('')+'</tr>';}).join('')+'</tbody></table>':'<div class="nodata">Sin datos</div>';
}
"""
        html = html.replace("function aTab(){", inv_js + "\nfunction aTab(){")
        html = html.replace(
            "var TABS=['resumen','colores','tallas','tiendas','decisiones'];",
            "var TABS=['resumen','colores','tallas','tiendas','inventario','decisiones'];",
        )
        html = html.replace(
            "else if(n==='tiendas')rTiendas();else if(n==='decisiones')rDecisiones();",
            "else if(n==='tiendas')rTiendas();else if(n==='inventario')rInventario();else if(n==='decisiones')rDecisiones();",
        )
        html = html.replace(
            "if(tx.indexOf('Tienda')>=0)return'tiendas';return'decisiones';",
            "if(tx.indexOf('Tienda')>=0)return'tiendas';if(tx.indexOf('Inventario')>=0)return'inventario';return'decisiones';",
        )
        # KPI header stock
        if "stk.grand" not in html:
            html = html.replace(
                "'<div class=\"kpib\"><div class=\"kv\">'+mA.length+'</div><div class=\"kl\">Meses</div></div>'+",
                "'<div class=\"kpib\"><div class=\"kv\">'+mA.length+'</div><div class=\"kl\">Meses</div></div>'+\n"
                "    '<div class=\"kpib\"><div class=\"kv\" style=\"color:var(--yw)\">'+stk.grand.toLocaleString()+'</div><div class=\"kl\">📦 Stock</div></div>'+\n"
                "    '<div class=\"kpib\"><div class=\"kv\">'+stk.tiendaTotal.toLocaleString()+'</div><div class=\"kl\">En Tiendas</div></div>'+\n"
                "    '<div class=\"kpib\"><div class=\"kv\" style=\"color:#f97316\">'+stk.tallerTotal.toLocaleString()+'</div><div class=\"kl\">🏭 Taller</div></div>'+",
            )
            html = html.replace(
                "function updateKPIs(){\n  var rows=fr(),total=0,ts={},cs={};",
                "function updateKPIs(){\n  var rows=fr(),total=0,ts={},cs={};\n  var stk=getStockTotals(getFilteredStockByStore());",
            )

    # Decisiones layout: flex column propGrid + base/adjusted rotation if missing
    html = html.replace(
        'id="propGrid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px;margin-top:10px"',
        'id="propGrid" style="display:flex;flex-direction:column;gap:14px;margin-top:10px"',
    )

    TEMPLATE_PATH.write_text(html, encoding="utf-8")


def build_html(data: dict) -> str:
    ensure_template()
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    payload = {k: v for k, v in data.items() if not k.startswith("_")}
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    html = template.replace("var DATA=__DATA__;", f"var DATA={data_json};", 1)
    periodo = data.get("periodo", "")
    html = re.sub(
        r"<p>Dashboard de Ventas · .*?</p>",
        f"<p>Dashboard de Ventas · {periodo}</p>",
        html,
        count=1,
    )
    html = re.sub(
        r'<div class="footer">.*?</div>',
        f'<div class="footer">Short Playa · Dashboard de Ventas · {periodo}</div>',
        html,
        count=1,
    )
    return html


def main():
    data = build_data()
    OUTPUT_PATH.write_text(build_html(data), encoding="utf-8")
    meta = data.get("_meta", {})
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Total ventas: {data['total']}")
    print(f"Devoluciones netas: {meta.get('returns_units', 0)}")
    print(f"Periodo: {data['periodo']}")
    print(f"Stock total: {data['stock_total']} (Taller: {data['stock_taller']})")
    print(f"Inventario negativo excluido: {meta.get('negative_stock_units', 0)} und")
    print(f"Velocity months: {data['velocity_months_label']}")
    for m in MODELS:
        s = data["summary_produccion"].get(m, {})
        print(f"  {m}: produce={s.get('produce',0)} v_base={s.get('v_mes_base',0)} v_adj={s.get('v_mes',0)}")
    print(f"Producción total sugerida: {sum(r['produce'] for r in data['production_plan'])}")


if __name__ == "__main__":
    main()
