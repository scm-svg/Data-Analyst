"""Calcula las métricas del pedido especial 10K por escenario (base + A/B/C/D).

Lee data.json (lo produce extraer_datos.py) y escribe metricas.json, que es lo que
consume build_dashboard.py. Ambos archivos se buscan en la carpeta del script.
"""
import json
import datetime
import os
from collections import defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
ENTRADA = os.path.join(AQUI, "data.json")
SALIDA = os.path.join(AQUI, "metricas.json")

DATA = json.load(open(ENTRADA))
LIMITE = datetime.date(2026, 10, 9)
DIAS_POST_COSTURA = 3
ESCENARIOS = ["A", "B", "C", "D"]
LINEAS = ["1", "2", "3", "4", "5"]

DESCRIPCION = {
    "A": "Todo el pedido entra por la Línea 4 cuando estén cortadas y sublimadas todas las piezas.",
    "B": "Running Tank arranca antes por Líneas 1 y 2. El resto entra por Línea 4.",
    "C": "Running Tank arranca antes por Líneas 1 y 2. El resto entra por Líneas 3 y 4.",
    "D": "Running Tank arranca antes por Líneas 1 y 2. El resto entra por Líneas 2, 3 y 4.",
}


def d(s):
    return datetime.date(*[int(x) for x in s.split("-")]) if s else None


def habiles(fecha, n):
    f = fecha
    add = 0
    while add < n:
        f += datetime.timedelta(days=1)
        if f.weekday() < 5:
            add += 1
    return f


def dias_habiles_entre(a, b):
    """Positivo si b es posterior a a."""
    signo = 1 if b >= a else -1
    ini, fin = (a, b) if b >= a else (b, a)
    n = 0
    f = ini
    while f < fin:
        f += datetime.timedelta(days=1)
        if f.weekday() < 5:
            n += 1
    return signo * n


def fechas_semana(sc, sem):
    w = sc["semanas"].get(sem)
    if not w:
        return []
    return [d(x) for x in w["fechas"]]


def es_especial(modelo):
    return "(Especial)" in modelo


def dias_pedido(sc):
    """[(fecha, linea, modelo, piezas)] del pedido especial."""
    out = []
    for sem, w in sc["semanas"].items():
        fechas = [d(x) for x in w["fechas"]]
        for fila in w["filas"]:
            if not es_especial(fila["modelo"]):
                continue
            for i, q in enumerate(fila["dias"]):
                if q > 0:
                    out.append((fechas[i], fila["linea"], fila["modelo"], int(q)))
    out.sort(key=lambda x: (x[0], x[1]))
    return out


def resumen_pedido(sc):
    detalle = dias_pedido(sc)
    por_modelo = defaultdict(lambda: {"piezas": 0, "ini": None, "fin": None, "lineas": set()})
    por_linea = defaultdict(int)
    por_fecha = defaultdict(int)
    for fecha, lin, mod, q in detalle:
        m = por_modelo[mod]
        m["piezas"] += q
        m["lineas"].add(lin)
        if m["ini"] is None or fecha < m["ini"]:
            m["ini"] = fecha
        if m["fin"] is None or fecha > m["fin"]:
            m["fin"] = fecha
        por_linea[lin] += q
        por_fecha[fecha] += q
    modelos = []
    for mod, m in por_modelo.items():
        entrega = habiles(m["fin"], DIAS_POST_COSTURA)
        modelos.append({
            "modelo": mod.replace(" (Especial)", ""),
            "piezas": m["piezas"],
            "lineas": sorted(m["lineas"]),
            "inicio": m["ini"].isoformat(),
            "fin": m["fin"].isoformat(),
            "entrega": entrega.isoformat(),
            "holgura": dias_habiles_entre(entrega, LIMITE),
        })
    modelos.sort(key=lambda x: x["fin"])
    fin = max(x["fin"] for x in modelos)
    ini = min(x["inicio"] for x in modelos)
    entrega = habiles(d(fin), DIAS_POST_COSTURA)
    return {
        "modelos": modelos,
        **piezas_tarde(detalle),
        "piezas": sum(x["piezas"] for x in modelos),
        "inicio": ini,
        "fin": fin,
        "entrega": entrega.isoformat(),
        "holgura": dias_habiles_entre(entrega, LIMITE),
        "a_tiempo": entrega <= LIMITE,
        "por_linea": {k: v for k, v in sorted(por_linea.items())},
        "dias_costura": len(por_fecha),
        "calendario": [{"fecha": f.isoformat(), "linea": l, "modelo": m.replace(" (Especial)", ""), "piezas": q}
                       for f, l, m, q in detalle],
    }


def ultima_costura_util():
    """Último día de costura que todavía llega al límite con +3 hábiles."""
    f = LIMITE
    n = 0
    while n < DIAS_POST_COSTURA:
        f -= datetime.timedelta(days=1)
        if f.weekday() < 5:
            n += 1
    return f


CORTE_COSTURA = ultima_costura_util()


def piezas_tarde(detalle):
    tarde = sum(q for fecha, _, _, q in detalle if fecha > CORTE_COSTURA)
    total = sum(q for _, _, _, q in detalle)
    return {"pzas_tarde": tarde, "pzas_a_tiempo": total - tarde,
            "pct_a_tiempo": round(100.0 * (total - tarde) / total) if total else 0}


def linea1_semana3(sc):
    """Piezas que el plan carga en la Línea 1 durante la semana del 28/09."""
    w = sc["semanas"].get("S3")
    if not w:
        return {"piezas": 0, "modelos": []}
    filas = [f for f in w["filas"] if f["linea"] == "1"]
    return {"piezas": int(sum(f["total"] for f in filas)),
            "modelos": [f["modelo"] for f in filas]}


def termino_por_modelo(sc):
    out = {}
    for row in sc["proyeccion"]:
        mod = row["modelo"]
        fin = row.get("Fecha Estim. Término")
        if fin and fin != "--":
            out[mod] = fin
    return out


def almacen_por_modelo(sc):
    return {r["modelo"]: r for r in sc["almacen"]}


def impacto(sc_base, sc):
    base_fin = termino_por_modelo(sc_base)
    esc_fin = termino_por_modelo(sc)
    base_alm = almacen_por_modelo(sc_base)
    esc_alm = almacen_por_modelo(sc)
    filas = []
    for mod, fin_base in base_fin.items():
        if mod not in esc_fin:
            continue
        fb, fe = d(fin_base), d(esc_fin[mod])
        dias = dias_habiles_entre(fb, fe)
        alm_b = base_alm.get(mod, {}).get("entrada")
        alm_e = esc_alm.get(mod, {}).get("entrada")
        filas.append({
            "modelo": mod,
            "piezas": base_alm.get(mod, {}).get("cantidad", 0),
            "fin_base": fin_base,
            "fin_esc": esc_fin[mod],
            "dias": dias,
            "almacen_base": alm_b,
            "almacen_esc": alm_e,
        })
    filas.sort(key=lambda x: (-x["dias"], x["modelo"]))
    aplazados = [f for f in filas if f["dias"] > 0]
    adelantados = [f for f in filas if f["dias"] < 0]
    return {
        "filas": filas,
        "aplazados": aplazados,
        "adelantados": adelantados,
        "n_aplazados": len(aplazados),
        "piezas_aplazadas": int(sum(f["piezas"] for f in aplazados)),
        "max_dias": max([f["dias"] for f in aplazados], default=0),
        "suma_dias": sum(f["dias"] for f in aplazados),
    }


def uso_lineas(sc, semanas=("S2", "S3", "S4")):
    """Piezas y día-slots ocupados por línea en las semanas del pedido."""
    piezas = defaultdict(int)
    slots = defaultdict(set)
    detalle = {}
    for sem in semanas:
        w = sc["semanas"].get(sem)
        if not w:
            continue
        por_linea = defaultdict(int)
        for fila in w["filas"]:
            lin = fila["linea"]
            piezas[lin] += int(fila["total"])
            por_linea[lin] += int(fila["total"])
            for i, q in enumerate(fila["dias"]):
                if q > 0:
                    slots[lin].add((sem, i))
        detalle[sem] = dict(por_linea)
    n_sem = len([s for s in semanas if sc["semanas"].get(s)])
    return {
        "piezas": {l: piezas.get(l, 0) for l in LINEAS},
        "dias_ocupados": {l: len(slots.get(l, set())) for l in LINEAS},
        "dias_posibles": 5 * n_sem,
        "por_semana": detalle,
    }


def ocupacion_pedido(sc):
    """Qué parte de cada línea usa el pedido en las semanas que lo tocan."""
    slots = defaultdict(set)
    for sem, w in sc["semanas"].items():
        for fila in w["filas"]:
            if not es_especial(fila["modelo"]):
                continue
            for i, q in enumerate(fila["dias"]):
                if q > 0:
                    slots[fila["linea"]].add((sem, i))
    return {l: len(slots.get(l, set())) for l in LINEAS}


def semanas_afectadas(sc):
    out = []
    for sem, w in sorted(sc["semanas"].items(), key=lambda x: int(x[0][1:])):
        if any(es_especial(f["modelo"]) for f in w["filas"]):
            out.append({"semana": sem, "desde": w["fechas"][0], "hasta": w["fechas"][4]})
    return out


def tablero_semanal(sc, sem):
    w = sc["semanas"].get(sem)
    if not w:
        return None
    filas = []
    for f in w["filas"]:
        filas.append({
            "linea": f["linea"],
            "modelo": f["modelo"],
            "especial": es_especial(f["modelo"]),
            "dias": [int(x) for x in f["dias"]],
            "total": int(f["total"]),
        })
    filas.sort(key=lambda x: (x["linea"], -x["total"]))
    return {"fechas": w["fechas"], "filas": filas}


base = DATA["BASE"]
resultado = {
    "limite": LIMITE.isoformat(),
    "dias_post_costura": DIAS_POST_COSTURA,
    "corte_costura": CORTE_COSTURA.isoformat(),
    "pedido": [],
    "base": {
        "uso": uso_lineas(base),
        "linea1_s3": linea1_semana3(base),
        "termino": termino_por_modelo(base),
        "almacen": base["almacen"],
        "semanas": {s: tablero_semanal(base, s) for s in ["S1", "S2", "S3", "S4", "S5"]},
    },
    "escenarios": {},
}

# Composición del pedido (igual en todos los escenarios; se toma de A)
comp = defaultdict(lambda: {"piezas": 0, "skus": 0, "cap": 0})
for fila in DATA["A"]["especial"]:
    nombre = fila["producto"] + " " + (fila["genero"] or "")
    c = comp[nombre.strip()]
    c["piezas"] += int(fila["cant"])
    c["skus"] += 1
    c["cap"] = int(fila["cap"])
resultado["pedido"] = [{"modelo": k, **v} for k, v in comp.items()]
resultado["pedido_total"] = sum(x["piezas"] for x in resultado["pedido"])

for k in ESCENARIOS:
    sc = DATA[k]
    lineas_cfg = sorted({l.strip() for fila in sc["especial"]
                         for l in str(fila["lineas"]).replace(".0", "").split(",") if l.strip()})
    resultado["escenarios"][k] = {
        "id": k,
        "descripcion": DESCRIPCION[k],
        "lineas": lineas_cfg,
        "pedido": resumen_pedido(sc),
        "impacto": impacto(base, sc),
        "uso": uso_lineas(sc),
        "linea1_s3": linea1_semana3(sc),
        "ocupacion_pedido": ocupacion_pedido(sc),
        "semanas_afectadas": semanas_afectadas(sc),
        "semanas": {s: tablero_semanal(sc, s) for s in ["S1", "S2", "S3", "S4", "S5"]},
        "config": [{"modelo": f["producto"] + " " + (f["genero"] or ""),
                    "lineas": str(f["lineas"]).replace(".0", ""),
                    "inicio": f["inicio"]} for f in sc["especial"]],
    }

json.dump(resultado, open(SALIDA, "w"), ensure_ascii=False, indent=1)

print("Pedido especial 10K:", resultado["pedido_total"], "pzas")
for p in resultado["pedido"]:
    print("  %-28s %4d pzas  (%d SKUs, cap %d/día)" % (p["modelo"], p["piezas"], p["skus"], p["cap"]))
print()
print("%-3s %-11s %-11s %-11s %7s %7s %10s %9s" %
      ("ESC", "1ª costura", "fin costura", "entrega", "holgura", "aplaz.", "pzas aplaz", "máx días"))
for k in ESCENARIOS:
    e = resultado["escenarios"][k]
    p, im = e["pedido"], e["impacto"]
    print("%-3s %-11s %-11s %-11s %+7d %7d %10d %9d" %
          (k, p["inicio"], p["fin"], p["entrega"], p["holgura"],
           im["n_aplazados"], im["piezas_aplazadas"], im["max_dias"]))
print()
print("Última costura que llega al límite:", CORTE_COSTURA.isoformat())
for k in ESCENARIOS:
    e = resultado["escenarios"][k]
    print("%s piezas por línea: %-42s días costura: %2d  a tiempo: %4d/1000 (%3d%%)  tarde: %4d  L1 sem3: %d pzas" %
          (k, e["pedido"]["por_linea"], e["pedido"]["dias_costura"],
           e["pedido"]["pzas_a_tiempo"], e["pedido"]["pct_a_tiempo"],
           e["pedido"]["pzas_tarde"], e["linea1_s3"]["piezas"]))
print("BASE L1 sem3:", resultado["base"]["linea1_s3"])
