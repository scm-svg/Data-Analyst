#!/usr/bin/env python3
"""Tests del motor de planificación v5.9.20 (espejo de las reglas en Codigo.gs)."""
import math
import re
import unittest
from collections import defaultdict


BANDA_ESPECIAL = 0
BANDA_MINIMA = 1
BANDA_URGENTE = 2
BANDA_RESTO = 3
DIAS_LABORALES = 5
DIAS_ENTRADA_ALMACEN = 4
MAX_MODELOS_LINEA5 = 2
MAX_MODELOS_PARALELO = MAX_MODELOS_LINEA5
LOTE_RUEDA_LINEA5 = 5
CAP_POR_LINEA = {"1": 130, "2": 130, "3": 130, "4": 130, "5": 40}


def norm(s):
    return str("" if s is None else s).strip()


def quitar_tildes(s):
    table = str.maketrans("áéíóúñÁÉÍÓÚÑ", "aeiounAEIOUN")
    return str(s).translate(table)


def rango_color(color):
    """0-2 core exacto, 3-5 similares, 50 resto."""
    c = quitar_tildes(norm(color)).lower()
    if not c:
        return 50
    if c == "negro" or c.startswith("negro"):
        return 0
    if c == "blanco" or c.startswith("blanco") or c in ("ivory", "blanco hueso"):
        return 1
    if c.startswith("azul marino") or c.startswith("navy") or c == "marino":
        return 2
    if "negro" in c:
        return 3
    if "blanco" in c or "ivory" in c:
        return 4
    if "marino" in c or "navy" in c:
        return 5
    return 50


def es_token_genero(s):
    g = quitar_tildes(norm(s)).lower()
    if g in ("", "--"):
        return False
    return g in (
        "cab", "hombre", "male", "dama", "mujer", "female", "girl", "boy",
        "kids", "nino", "nina", "ninos", "ninas", "infantil", "unisex",
    ) or g.startswith("caballer")


def orden_genero(g):
    s = quitar_tildes(norm(g)).lower()
    if s in ("cab", "hombre", "male", "boy") or s.startswith("caballer"):
        return 0
    if s in ("dama", "mujer", "female", "girl"):
        return 1
    if s in ("kids", "nino", "nina", "ninos", "ninas", "infantil"):
        return 2
    if s in ("", "--"):
        return 3
    return 4


def familia_de_nombre(modelo):
    n = re.sub(r"\s*\(\s*especial\s*\)\s*$", "", norm(modelo), flags=re.I).strip()
    if not n:
        return ""
    parts = n.split()
    if len(parts) >= 2 and es_token_genero(parts[-1]):
        return " ".join(parts[:-1])
    return n


def familia_de(t):
    if t.get("familia"):
        return t["familia"]
    return familia_de_nombre(t.get("modelo") or "")


def genero_de(t):
    g = t.get("genero")
    if g and norm(g) not in ("", "--"):
        return g
    n = re.sub(r"\s*\(\s*especial\s*\)\s*$", "", norm(t.get("modelo") or ""), flags=re.I).strip()
    parts = n.split()
    if len(parts) >= 2 and es_token_genero(parts[-1]):
        return parts[-1]
    return g or ""


def cap_de_tarea(t, lin, caps_lineas):
    c = t.get("cap")
    try:
        c = float(c)
    except (TypeError, ValueError):
        c = 0
    if c > 0:
        return c
    return caps_lineas.get(str(lin), 130)


SYNC_COSTURA_ESQUEMA = "SYNC-V13"


def clave_lookup_mo(mo):
    s = str("" if mo is None else mo).strip().upper()
    if not s:
        return ""
    m = re.match(r"^0*([0-9]+)(.*)$", s)
    if m:
        return m.group(1) + m.group(2)
    return s


def fusionar_cantida_producida(existente, desde_costura):
    """Compat: suma existente + delta (el 2º arg debe ser el incremento, no el total)."""
    return aplicar_delta_cantida_producida(existente, desde_costura)


def delta_costura_aplicar(costura_ahora, ya_aplicado, primer_sync=False):
    if primer_sync:
        return 0.0
    try:
        ahora = float(costura_ahora or 0)
    except (TypeError, ValueError):
        ahora = 0
    try:
        prev = float(ya_aplicado or 0)
    except (TypeError, ValueError):
        prev = 0
    return max(0.0, ahora - prev)


def texto_fecha_costura(v):
    if v in ("", None):
        return ""
    if hasattr(v, "timestamp"):
        try:
            return str(int(v.timestamp() * 1000))
        except Exception:
            return str(v)
    return str(v).strip()


def huella_fila_costura(f):
    return "||".join([
        clave_lookup_mo(f.get("mo")),
        str(f.get("sku") or "").strip().upper(),
        str(f.get("qty")),
        texto_fecha_costura(f.get("fecha")),
        str(f.get("linea") or "").strip().lower(),
    ])


def es_esquema_sync_actual(v):
    if v in ("", None):
        return False
    if hasattr(v, "year") and not isinstance(v, str):
        return False
    s = str(v).strip().upper()
    return s == SYNC_COSTURA_ESQUEMA or s.startswith("SYNC-V13")


def delta_por_huellas_costura(filas, aplicadas=None):
    aplicadas = aplicadas or {}
    seen = {}
    delta = {}
    n_nuevas = 0
    for f in filas:
        fp = huella_fila_costura(f)
        seen[fp] = seen.get(fp, 0) + 1
        if seen[fp] <= aplicadas.get(fp, 0):
            continue
        k = clave_lookup_mo(f.get("mo"))
        if not k:
            continue
        delta[k] = delta.get(k, 0.0) + float(f.get("qty") or 0)
        n_nuevas += 1
    return delta, n_nuevas


def resolver_delta_costura(filas, esquema_prev, aplicadas=None):
    if not es_esquema_sync_actual(esquema_prev):
        return {}
    delta, _n = delta_por_huellas_costura(filas, aplicadas)
    return delta


def inyectar_cantida_por_hacer(existente, mos_por_hacer, delta_por_mo):
    prod = 0.0
    for mm in str(mos_por_hacer or "").split(","):
        k = clave_lookup_mo(mm)
        if not k:
            continue
        prod += float(delta_por_mo.get(k, 0) or 0)
    return aplicar_delta_cantida_producida(existente, prod)


def aplicar_delta_cantida_producida(existente, delta):
    def n(v):
        try:
            if v in ("", None):
                return 0.0
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    m = n(existente) + max(0.0, n(delta))
    return m if m > 0 else ""


def es_especial_hecho(status):
    return quitar_tildes(norm(status)).lower() == "hecho"


def debe_archivar_mo(tipo, status):
    st = quitar_tildes(norm(status)).lower()
    tp = quitar_tildes(norm(tipo)).lower()
    if st == "cancelada":
        return True
    if st == "hecho" and "especial" in tp:
        return False
    if st == "hecho":
        return True
    return False


def num_celda_dia(v):
    if v in ("--", "", None):
        return 0
    try:
        return float(v) or 0
    except (TypeError, ValueError):
        return 0


def primer_dia_en_rango(row, dia_ini, dia_fin):
    for i in range(dia_ini, dia_fin + 1):
        if num_celda_dia(row[i]) > 0:
            return i
    return 99


def fila_continua_despues(row, primer_dia, dia_ini, dia_fin):
    if primer_dia >= 99:
        return False
    for i in range(primer_dia + 1, dia_fin + 1):
        if num_celda_dia(row[i]) > 0:
            return True
    return False


def cmp_filas_flujo_key(row, dia_ini, dia_fin, idx_nombre=1):
    da = primer_dia_en_rango(row, dia_ini, dia_fin)
    continua = 1 if fila_continua_despues(row, da, dia_ini, dia_fin) else 0
    qty = num_celda_dia(row[da]) if da < 99 else 0
    return (da, continua, qty, str(row[idx_nombre]))


def add_business_days_from_naive(d, days):
    import datetime
    added = 0
    cur = d
    while added < days:
        cur = cur + datetime.timedelta(days=1)
        if cur.weekday() < 5:
            added += 1
    return cur


def prioridad_num(txt):
    p = quitar_tildes(norm(txt)).lower()
    if "urgente" in p:
        return 1
    if "alta" in p:
        return 2
    if "media" in p:
        return 3
    if "baja" in p:
        return 4
    return 5


def clave_modelo_norm(s):
    return " ".join(quitar_tildes(norm(s)).lower().split())


def es_secuencia_no(val):
    if val is True:
        return True
    return quitar_tildes(norm(val)).lower() == "no"


def secuencia_no_de_modelo(mapa, modelo):
    if not mapa or not modelo:
        return False
    if es_secuencia_no(mapa.get(modelo)):
        return True
    alvo = clave_modelo_norm(modelo)
    for k, v in mapa.items():
        if clave_modelo_norm(k) == alvo and es_secuencia_no(v):
            return True
    return False


def minima_de_modelo(mapa, modelo):
    if not mapa:
        return 0
    if mapa.get(modelo, 0) > 0:
        return mapa[modelo]
    alvo = clave_modelo_norm(modelo)
    alvo_base = alvo.replace("(especial)", "").strip()
    for k, v in mapa.items():
        nk = clave_modelo_norm(k)
        if v > 0 and nk in (alvo, alvo_base) or (v > 0 and nk.replace("(especial)", "").strip() == alvo_base):
            return v
    return 0


def fecha_key(txt):
    s = norm(txt)
    if not s:
        return float("inf")
    parts = s.replace("-", "/").split("/")
    if len(parts) != 3:
        return float("inf")
    d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
    if y < 100:
        y += 2000
    return y * 10000 + m * 100 + d


def es_urgente(t):
    return (not t.get("esEspecial")) and int(t.get("prioridadNum", 5) or 5) == 1


def banda_de(t):
    if t.get("esEspecial"):
        return BANDA_ESPECIAL
    if t.get("esMinima"):
        return BANDA_MINIMA
    if es_urgente(t):
        return BANDA_URGENTE
    return BANDA_RESTO


def faltante_de_fila(solicitada, producida=0, faltante=None):
    if producida is None:
        producida = 0
    sol = float(solicitada or 0)
    prod = float(producida or 0)
    if prod or solicitada is not None:
        calc = max(0.0, sol - prod)
        if faltante is None or faltante == "":
            return calc
    if faltante not in (None, ""):
        try:
            return float(faltante)
        except (TypeError, ValueError):
            return calc if "calc" in dir() else 0.0
    return max(0.0, sol - prod)


def modelos_con_faltante(filas):
    """filas: iterable de dicts con modelo, tipo, faltante. Quita totales 0."""
    tot = defaultdict(float)
    for f in filas:
        tot[(f["modelo"], f.get("tipo", "Producción"))] += float(f.get("faltante") or 0)
    return {k for k, v in tot.items() if v > 0}


def dia_inicio_efectivo(t):
    return t.get("diaIngreso") or 0


def clave_sku(s):
    return norm(s).upper()


def min_de_sku(mapa_sku, sku):
    if not mapa_sku:
        return 0
    v = mapa_sku.get(clave_sku(sku), mapa_sku.get(sku))
    if isinstance(v, dict):
        return v.get("min") or 0
    return v or 0


def rec_sku_prio(mapa_sku, sku):
    if not mapa_sku:
        return None
    rec = mapa_sku.get(clave_sku(sku), mapa_sku.get(sku))
    if rec is None:
        return None
    if isinstance(rec, dict):
        if (rec.get("min") or 0) > 0:
            return rec
        return None
    if rec > 0:
        return {"min": rec, "orden": 0}
    return None


def marcar_sku_prio(tareas, mapa_sku):
    for t in tareas:
        rec = rec_sku_prio(mapa_sku, t.get("sku"))
        if rec:
            t["esSkuPrio"] = True
            t["skuPrioOrden"] = rec.get("orden", 0)
        else:
            t["esSkuPrio"] = False
            t.setdefault("skuPrioOrden", 9999)
    return tareas


def cmp_tareas_modelo(t):
    return (
        0 if t.get("esSkuPrio") else 1,
        t.get("skuPrioOrden", 9999) if t.get("esSkuPrio") else 0,
        0 if t.get("esMinima") else 1,
        t.get("colorRank", rango_color(t.get("color"))),
        -(t.get("restante", t.get("cantidad", 0))),
        t.get("sku") or "",
    )


def expandir_por_minima(tareas, mapa_minimas, mapa_minimas_sku=None):
    """Piso de modelo con colores core. SKUs de Priorizacion se marcan pero no cambian la banda."""
    mapa_minimas_sku = mapa_minimas_sku or {}
    por_modelo = defaultdict(list)
    orden = []
    for t in tareas:
        if t["modelo"] not in por_modelo:
            orden.append(t["modelo"])
        por_modelo[t["modelo"]].append(dict(t))

    out = []
    for modelo in orden:
        group = por_modelo[modelo]
        if group[0].get("esEspecial"):
            for t in group:
                t["fase2"] = False
                t["esMinima"] = False
                out.append(t)
            continue

        min_modelo = minima_de_modelo(mapa_minimas, modelo)
        vol_faltante = 0
        vol_original = 0
        for t in group:
            vol_faltante += t["cantidad"]
            orig = t.get("solicitadaOrig", t["cantidad"])
            vol_original += orig
        producido = max(0, vol_original - vol_faltante)
        if min_modelo > 0 and producido >= min_modelo:
            for t in group:
                t["fase2"] = True
                t["esMinima"] = False
                out.append(t)
            continue
        min_modelo_faltante = min(min_modelo, vol_faltante) if min_modelo > 0 else 0

        if min_modelo_faltante <= 0:
            for t in group:
                t["fase2"] = False
                t["esMinima"] = False
                out.append(t)
            continue
        if min_modelo_faltante >= vol_faltante:
            for t in group:
                t["fase2"] = False
                t["esMinima"] = True
                out.append(t)
            continue

        group.sort(key=lambda t: (rango_color(t.get("color")), -t["cantidad"], t["sku"]))
        resto_modelo = min_modelo_faltante
        for t in group:
            left = t["cantidad"]
            if resto_modelo > 0 and left > 0:
                take_m = min(left, resto_modelo)
                b = dict(t)
                b["cantidad"] = take_m
                b["fase2"] = False
                b["esMinima"] = True
                out.append(b)
                resto_modelo -= take_m
                left -= take_m
            if left > 0:
                c = dict(t)
                c["cantidad"] = left
                c["fase2"] = True
                c["esMinima"] = False
                out.append(c)
    marcar_sku_prio(out, mapa_minimas_sku)
    return out


def acumular_semanas(por_semana, meta=0):
    acum, previo, alcanzada, out = 0, 0, False, []
    meta_num = meta or 0
    for v in por_semana:
        acum += v
        if alcanzada or acum == 0 or acum == previo:
            out.append(None)
        else:
            out.append(acum)
            previo = acum
            if meta_num > 0 and acum >= meta_num:
                alcanzada = True
    return out


COLOR_MINIMA_PROY = "#FFE599"
COLOR_META_PROY = "#D9EAD3"
COLOR_META_TEXTO_PROY = "#38761D"
FILA_ENC_PROY = 2
COL_INI_PROY = 2
FILA_DATOS_PROY = FILA_ENC_PROY + 1


def umbrales_semana(acum_arr, minima, meta):
    """Espejo de umbralesSemana_ en Codigo.gs: solo el primer cruce de cada umbral."""
    fondos = ["#FFFFFF"] * len(acum_arr)
    min_hecho = False
    meta_hecho = False
    for w, v in enumerate(acum_arr):
        if v in (None, "--", "", 0):
            continue
        try:
            n = float(v)
        except (TypeError, ValueError):
            continue
        if n <= 0:
            continue
        if not meta_hecho and meta and n >= meta:
            fondos[w] = COLOR_META_PROY
            meta_hecho = True
            min_hecho = True
        elif not min_hecho and minima and n >= minima:
            fondos[w] = COLOR_MINIMA_PROY
            min_hecho = True
    return fondos


def primera_fila_sku(skus, fila_datos=3):
    primera = {}
    for i, sku in enumerate(skus):
        modelo = sku["modelo"]
        if modelo not in primera:
            primera[modelo] = fila_datos + i
    return primera


def link_modelo_sku(gid, fila):
    return "#gid=%s&range=B%s" % (gid, fila)


def primer_dia_fila(fila):
    """fila = [linea, modelo, prio, L, M, X, J, V] con días en índices 3-7."""
    for i in range(3, 8):
        try:
            if float(fila[i] or 0) > 0:
                return i
        except (TypeError, ValueError):
            continue
    return 99


def max_ocupantes(lin):
    return MAX_MODELOS_LINEA5 if str(lin) == "5" else 1


def planificar(tareas, mapa_minimas, total_dias=10, caps_lineas=None, mapa_minimas_sku=None, mapa_secuencia=None):
    """Motor v5.9.20: 5.9.19 + Especial no desborda a L1."""
    if caps_lineas is None:
        caps_lineas = dict(CAP_POR_LINEA)
    mapa_secuencia = mapa_secuencia or {}

    tareas = expandir_por_minima(tareas, mapa_minimas, mapa_minimas_sku)
    for t in tareas:
        t["restante"] = t["cantidad"]
        t["planificada"] = 0
        t["plan"] = defaultdict(lambda: [0] * total_dias)
        t["lineaFija"] = None
        t.setdefault("diaIngreso", 0)
        t.setdefault("diaNoLaborable", -1)
        t.setdefault("prioridadNum", 5)
        t.setdefault("fechaKey", 0)
        t.setdefault("colorRank", rango_color(t.get("color")))
        t.setdefault("lineas", [])
        t["lineas"] = [str(x) for x in t["lineas"]]
        t["familia"] = familia_de(t)
        t["genero"] = genero_de(t)

    modelos = {}
    orden = []
    for t in tareas:
        if t["modelo"] not in modelos:
            modelos[t["modelo"]] = {
                "nombre": t["modelo"],
                "tareas": [],
                "fechaMin": t.get("fechaKey", float("inf")),
                "prioMin": t.get("prioridadNum", 5),
                "esEspecial": bool(t.get("esEspecial")),
                "banda": banda_de(t),
                "familia": familia_de(t),
                "genero": genero_de(t),
                "secuenciaNo": secuencia_no_de_modelo(mapa_secuencia, t["modelo"]),
            }
            orden.append(t["modelo"])
        m = modelos[t["modelo"]]
        m["tareas"].append(t)
        if t.get("fechaKey", float("inf")) < m["fechaMin"]:
            m["fechaMin"] = t.get("fechaKey", float("inf"))
        if t.get("prioridadNum", 5) < m["prioMin"]:
            m["prioMin"] = t.get("prioridadNum", 5)
        b = banda_de(t)
        if b < m["banda"]:
            m["banda"] = b

    lista = [modelos[n] for n in orden]
    lista.sort(key=lambda m: (
        m["banda"], m["fechaMin"], m["prioMin"], -sum(t["cantidad"] for t in m["tareas"]), m["nombre"]
    ))
    for m in lista:
        m["tareas"].sort(key=cmp_tareas_modelo)

    carga = {lin: [0.0] * total_dias for lin in caps_lineas}
    linea_por_mo = {}
    ultimo_modelo = {lin: "" for lin in caps_lineas}

    def restante_modelo(m):
        return sum(t["restante"] for t in m["tareas"])

    def restante_minima(m):
        return sum(t["restante"] for t in m["tareas"] if t.get("esMinima"))

    def tuvo_minima(m):
        return any(t.get("esMinima") for t in m["tareas"])

    def banda_viva(m):
        b = 9
        for t in m["tareas"]:
            if t["restante"] > 0:
                bt = banda_de(t)
                if bt < b:
                    b = bt
        return b

    def refrescar_cola():
        for m in lista:
            m["banda"] = banda_viva(m)
        lista.sort(key=lambda m: (
            m["banda"], m["fechaMin"], m["prioMin"], -sum(t["cantidad"] for t in m["tareas"]), m["nombre"]
        ))

    def familia_modelo(m):
        return m.get("familia") or familia_de_nombre(m["nombre"])

    def cap_modelo(m, lin):
        cap = 0
        for t in m["tareas"]:
            if t["restante"] > 0 and (t.get("cap") or 0) > cap:
                cap = t["cap"]
        if cap > 0:
            return cap
        for t in m["tareas"]:
            if (t.get("cap") or 0) > cap:
                cap = t["cap"]
        return cap if cap > 0 else caps_lineas.get(str(lin), 130)

    def nativos_linea1_pendientes(d):
        for m in lista:
            if not m["esEspecial"] or restante_modelo(m) <= 0:
                continue
            ocupando_otra = any(
                l2 != "1" and m["nombre"] in (ocupante.get(l2) or [])
                for l2 in ocupante
            )
            if ocupando_otra:
                continue
            for t in m["tareas"]:
                if t["restante"] <= 0 or "1" not in t["lineas"]:
                    continue
                if d < dia_inicio_efectivo(t):
                    continue
                if d < DIAS_LABORALES and (d % DIAS_LABORALES) == t.get("diaNoLaborable", -1):
                    continue
                mo = t.get("mo") or t["sku"]
                if mo in linea_por_mo and linea_por_mo[mo] != "1":
                    continue
                if t.get("lineaFija") and t["lineaFija"] != "1":
                    continue
                return True
        return False

    def elegibles(t, overflow):
        ls = list(t["lineas"])
        return [l for l in ls if l in carga]

    def runnable(t, d, lin, overflow):
        if t["restante"] <= 0 or d < dia_inicio_efectivo(t):
            return False
        if d < DIAS_LABORALES and (d % DIAS_LABORALES) == t.get("diaNoLaborable", -1):
            return False
        mo = t.get("mo") or t["sku"]
        if mo in linea_por_mo and linea_por_mo[mo] != lin:
            return False
        if t.get("lineaFija") and t["lineaFija"] != lin:
            return False
        return lin in elegibles(t, overflow)

    def modelo_puede(m, d, lin, overflow):
        return any(runnable(t, d, lin, overflow) for t in m["tareas"])

    def cap_restante_semana(lin, d, cap_ref=None):
        week = d // DIAS_LABORALES
        end = min(total_dias, (week + 1) * DIAS_LABORALES)
        piezas = 0
        cap = cap_ref if cap_ref and cap_ref > 0 else caps_lineas[lin]
        for dd in range(d, end):
            piezas += max(0.0, 1.0 - carga[lin][dd]) * cap
        return piezas

    def familia_ocupa_linea(fam, lin, except_nom=None):
        if not fam:
            return False
        return any(
            nom != except_nom and familia_modelo(modelos[nom]) == fam
            for nom in (ocupante.get(lin) or [])
        )

    def lineas_donde_esta(nombre):
        return [lin for lin, noms in ocupante.items() if nombre in noms]

    def lineas_modelo(m, overflow):
        seen = []
        for t in m["tareas"]:
            if t["restante"] <= 0:
                continue
            for lin in elegibles(t, overflow):
                if lin not in seen:
                    seen.append(lin)
        return seen

    def lineas_clave_modelo(m, overflow):
        return ",".join(sorted(lineas_modelo(m, overflow)))

    def comparten_lineas(a, b, overflow):
        if not a or not b:
            return False
        return bool(set(lineas_modelo(a, overflow)) & set(lineas_modelo(b, overflow)))

    def lote_familia_activo(fam, overflow):
        if not fam:
            return None
        best = None
        for m in lista:
            if familia_modelo(m) != fam or restante_modelo(m) <= 0:
                continue
            if m.get("esEspecial"):
                continue
            solo_min = restante_minima(m) > 0
            for t in m["tareas"]:
                if t["restante"] <= 0:
                    continue
                if solo_min and not t.get("esMinima"):
                    continue
                rank = rango_color(t.get("color"))
                g = orden_genero(m.get("genero"))
                key = (rank, g, m["nombre"])
                if best is None or key < best[0]:
                    best = (key, {
                        "modelo": m["nombre"], "m": m,
                        "colorRank": rank, "genero": g,
                    })
        return None if best is None else best[1]

    def lineas_libres_para_modelo(m, overflow):
        out = []
        seen = set()
        fam = familia_modelo(m)
        for t in m["tareas"]:
            if t["restante"] <= 0:
                continue
            for lin in elegibles(t, overflow):
                if lin in seen:
                    continue
                seen.add(lin)
                occ = ocupante.get(lin) or []
                if m["nombre"] in occ:
                    continue
                if len(occ) >= max_ocupantes(lin):
                    continue
                if fam and familia_ocupa_linea(fam, lin, m["nombre"]):
                    continue
                out.append(lin)
        return out

    def hermano_sin_linea_puede_usar(m, lin, overflow):
        fam = familia_modelo(m)
        if not fam:
            return False
        for h in lista:
            if h["nombre"] == m["nombre"] or familia_modelo(h) != fam:
                continue
            if h.get("esEspecial") or restante_modelo(h) <= 0:
                continue
            if lineas_donde_esta(h["nombre"]):
                continue
            if lin in lineas_modelo(h, overflow):
                return True
        return False

    def color_rank_vivo(m):
        best = 99
        solo_min = restante_minima(m) > 0
        for t in m["tareas"]:
            if t["restante"] <= 0:
                continue
            if solo_min and not t.get("esMinima"):
                continue
            r = rango_color(t.get("color"))
            if r < best:
                best = r
        return best

    def debe_esperar_lote_familia(m, overflow):
        if not m or m.get("esEspecial"):
            return False
        fam = familia_modelo(m)
        if not fam:
            return False
        if lineas_donde_esta(m["nombre"]):
            return False
        lote = lote_familia_activo(fam, overflow)
        if not lote or lote["modelo"] == m["nombre"]:
            return False
        if lote["m"].get("esEspecial"):
            return False
        if not comparten_lineas(m, lote["m"], overflow):
            return False
        if lineas_donde_esta(lote["modelo"]):
            return False
        if m.get("secuenciaNo"):
            return lote["colorRank"] < color_rank_vivo(m)
        libres_lote = lineas_libres_para_modelo(lote["m"], overflow)
        libres_mias = lineas_libres_para_modelo(m, overflow)
        if len(libres_lote) >= 2 and len(libres_mias) > 0:
            return False
        return True

    def debe_ceder_al_lote_familia(m, overflow):
        if not m or m.get("esEspecial"):
            return False
        fam = familia_modelo(m)
        if not fam:
            return False
        lote = lote_familia_activo(fam, overflow)
        if not lote or lote["modelo"] == m["nombre"]:
            return False
        if lote["m"].get("esEspecial"):
            return False
        if not comparten_lineas(m, lote["m"], overflow):
            return False
        if m.get("secuenciaNo"):
            if lote["colorRank"] < color_rank_vivo(m):
                return not lineas_donde_esta(lote["modelo"])
            return False
        return not lineas_donde_esta(lote["modelo"])

    def debe_esperar_hermano(m, overflow):
        return debe_esperar_lote_familia(m, overflow)

    def hay_genero_anterior_misma_linea(m, overflow, d_hoy):
        return debe_esperar_lote_familia(m, overflow)

    def hermanos_pendientes(lin, d, overflow, skip, fam):
        if not fam:
            return []
        out = []
        for mC in lista:
            if familia_modelo(mC) != fam or restante_modelo(mC) <= 0:
                continue
            if skip.get(mC["nombre"]):
                continue
            if mC["nombre"] in (ocupante.get(lin) or []):
                continue
            if any(l2 != lin and mC["nombre"] in (ocupante.get(l2) or []) for l2 in ocupante):
                continue
            if not modelo_puede(mC, d, lin, overflow):
                continue
            out.append(mC)
        out.sort(key=lambda x: (orden_genero(x.get("genero")), x["nombre"]))
        return out

    def lineas_libres_de(m, overflow):
        return lineas_libres_para_modelo(m, overflow)

    def reclamar_lineas(d, ocupante, overflow):
        if d % DIAS_LABORALES == 0:
            for lin in list(ocupante):
                ocupante[lin] = []
        for lin, mods in list(ocupante.items()):
            kept = []
            for mod in mods:
                m_occ = modelos[mod]
                if restante_modelo(m_occ) <= 0 or not modelo_puede(m_occ, d, lin, overflow):
                    continue
                if debe_esperar_lote_familia(m_occ, overflow):
                    continue
                if debe_ceder_al_lote_familia(m_occ, overflow):
                    continue
                kept.append(mod)
            ocupante[lin] = kept

        for lin in list(ocupante):
            if ocupante[lin]:
                continue
            last_nom = ultimo_modelo.get(lin) or ""
            last_m = modelos.get(last_nom)
            if last_m and restante_modelo(last_m) > 0 and modelo_puede(last_m, d, lin, overflow) and not lineas_donde_esta(last_nom):
                if not debe_esperar_lote_familia(last_m, overflow) and not debe_ceder_al_lote_familia(last_m, overflow):
                    ocupante[lin].append(last_nom)
                    continue
            fam_last = familia_modelo(last_m) if last_m else familia_de_nombre(last_nom)
            lote = lote_familia_activo(fam_last, overflow)
            if lote and modelo_puede(lote["m"], d, lin, overflow) and len(ocupante[lin]) < max_ocupantes(lin):
                if lote["modelo"] not in (ocupante.get(lin) or []) and not lineas_donde_esta(lote["modelo"]):
                    ocupante[lin].append(lote["modelo"])
                    continue
            hermanos = hermanos_pendientes(lin, d, overflow, {}, fam_last)
            if hermanos and len(ocupante[lin]) < max_ocupantes(lin):
                ocupante[lin].append(hermanos[0]["nombre"])

        vivos = [m for m in lista if restante_modelo(m) > 0]
        for m in vivos:
            if any(m["nombre"] in (ocupante.get(lin) or []) for lin in ocupante):
                continue
            if debe_esperar_lote_familia(m, overflow):
                continue
            libres = lineas_libres_de(m, overflow)
            if not libres:
                continue
            fam = familia_modelo(m)
            libres.sort(key=lambda lin: (
                0 if fam and familia_de_nombre(ultimo_modelo.get(lin) or "") == fam else 1,
                carga[lin][d],
                lin,
            ))
            ocupante[libres[0]].append(m["nombre"])
        for m in vivos:
            if m["banda"] not in (BANDA_ESPECIAL, BANDA_MINIMA, BANDA_URGENTE):
                continue
            owned = [lin for lin, mods in ocupante.items() if m["nombre"] in mods]
            if not owned:
                continue
            cap_owned = sum(cap_restante_semana(lin, d, cap_modelo(m, lin)) for lin in owned)
            if restante_modelo(m) <= cap_owned + 1e-6:
                continue
            for lin in lineas_libres_de(m, overflow):
                if hermano_sin_linea_puede_usar(m, lin, overflow):
                    continue
                ocupante[lin].append(m["nombre"])
                cap_owned += cap_restante_semana(lin, d, cap_modelo(m, lin))
                if restante_modelo(m) <= cap_owned + 1e-6:
                    break

    def producir_lote(m, lin, d, overflow, max_lote=0, solo_minima=False, color_rank=None):
        for t in m["tareas"]:
            if t["restante"] <= 0 or d < dia_inicio_efectivo(t):
                continue
            if d < DIAS_LABORALES and (d % DIAS_LABORALES) == t.get("diaNoLaborable", -1):
                continue
            if solo_minima and not t.get("esMinima"):
                continue
            if color_rank is not None and rango_color(t.get("color")) != color_rank:
                continue
            mo = t.get("mo") or t["sku"]
            if mo in linea_por_mo:
                t["lineaFija"] = linea_por_mo[mo]
            if t.get("lineaFija") and t["lineaFija"] != lin:
                continue
            if lin not in elegibles(t, overflow):
                continue
            avail = 1.0 - carga[lin][d]
            if avail <= 0.001:
                return 0
            cap_lin = cap_de_tarea(t, lin, caps_lineas)
            piezas = min(t["restante"], math.floor(avail * cap_lin + 1e-9))
            if max_lote > 0:
                piezas = min(piezas, max_lote)
            if piezas <= 0:
                continue
            t["lineaFija"] = lin
            linea_por_mo[mo] = lin
            t["plan"][lin][d] += piezas
            carga[lin][d] += piezas / cap_lin
            t["restante"] -= piezas
            t["planificada"] += piezas
            ultimo_modelo[lin] = m["nombre"]
            return piezas
        return 0

    def producir_modelo_dia(m, lin, d, overflow):
        while carga[lin][d] < 0.999:
            solo_minima = restante_minima(m) > 0
            rank = None
            for t in m["tareas"]:
                if t["restante"] <= 0:
                    continue
                if solo_minima and not t.get("esMinima"):
                    continue
                mo = t.get("mo") or t["sku"]
                fija = linea_por_mo.get(mo) or t.get("lineaFija")
                if fija and fija != lin:
                    continue
                if lin not in elegibles(t, overflow):
                    continue
                rank = rango_color(t.get("color"))
                break
            if producir_lote(m, lin, d, overflow, 0, solo_minima, rank) <= 0:
                break
            if restante_minima(m) <= 0 and tuvo_minima(m):
                break
            if debe_ceder_al_lote_familia(m, overflow):
                break

    def producir_rueda_linea5(noms, d, overflow):
        lin = "5"
        i = 0
        estancado = 0
        while carga[lin][d] < 0.999 and estancado < len(noms):
            nom = noms[i % len(noms)]
            i += 1
            solo_minima = restante_minima(modelos[nom]) > 0
            p = producir_lote(modelos[nom], lin, d, overflow, LOTE_RUEDA_LINEA5, solo_minima)
            estancado = 0 if p > 0 else estancado + 1

    def siguiente_candidato(lin, d, overflow, skip):
        last_nom = ultimo_modelo.get(lin) or ""
        last_m = modelos.get(last_nom)
        fam_ref = familia_modelo(last_m) if last_m else familia_de_nombre(last_nom)
        if not fam_ref and ocupante.get(lin):
            fam_ref = familia_modelo(modelos[ocupante[lin][0]])
        para_paralelo = bool(ocupante.get(lin))
        if fam_ref and not para_paralelo:
            lote = lote_familia_activo(fam_ref, overflow)
            if (lote and lote["modelo"] != last_nom and not skip.get(lote["modelo"])
                    and not lote["m"].get("esEspecial")
                    and not lineas_donde_esta(lote["modelo"])
                    and modelo_puede(lote["m"], d, lin, overflow)):
                if lote["modelo"] not in (ocupante.get(lin) or []):
                    return lote["modelo"]
        genero_terminado = bool(last_m) and restante_modelo(last_m) <= 0
        if fam_ref and not para_paralelo and genero_terminado:
            hermanos = [h for h in hermanos_pendientes(lin, d, overflow, skip, fam_ref) if h["nombre"] != last_nom]
            if hermanos:
                return hermanos[0]["nombre"]
        for m in lista:
            if restante_modelo(m) <= 0:
                continue
            if skip.get(m["nombre"]):
                continue
            if m["nombre"] in (ocupante.get(lin) or []):
                continue
            ya_otra = any(
                l2 != lin and m["nombre"] in (ocupante.get(l2) or [])
                for l2 in ocupante
            )
            if ya_otra:
                continue
            if para_paralelo and fam_ref and familia_modelo(m) == fam_ref:
                continue
            if debe_esperar_hermano(m, overflow):
                continue
            if not modelo_puede(m, d, lin, overflow):
                continue
            return m["nombre"]
        return None

    def producir_linea_dia(lin, d):
        skip = {}
        guard = 0
        while carga[lin][d] < 0.999 and guard < 40:
            guard += 1
            overflow_now = not nativos_linea1_pendientes(d)
            ocupante[lin] = [
                nom for nom in ocupante[lin]
                if not skip.get(nom) and modelo_puede(modelos[nom], d, lin, overflow_now)
                and not debe_ceder_al_lote_familia(modelos[nom], overflow_now)
            ]
            noms = ocupante[lin]
            before = carga[lin][d]
            if str(lin) == "5" and len(noms) >= 2:
                fam0 = familia_modelo(modelos[noms[0]])
                paralelos = [nom for i, nom in enumerate(noms) if i == 0 or familia_modelo(modelos[nom]) != fam0]
                if len(paralelos) >= 2:
                    producir_rueda_linea5(paralelos, d, overflow_now)
                else:
                    producir_modelo_dia(modelos[noms[0]], lin, d, overflow_now)
            elif noms:
                producir_modelo_dia(modelos[noms[0]], lin, d, overflow_now)
            if carga[lin][d] >= 0.999:
                break
            ocupante[lin] = [
                nom for nom in ocupante[lin]
                if not skip.get(nom) and modelo_puede(modelos[nom], d, lin, overflow_now)
                and not (tuvo_minima(modelos[nom]) and restante_minima(modelos[nom]) <= 0)
                and not debe_ceder_al_lote_familia(modelos[nom], overflow_now)
            ]
            if carga[lin][d] <= before + 1e-6:
                for nom in list(ocupante[lin]):
                    skip[nom] = True
                ocupante[lin] = [nom for nom in ocupante[lin] if not skip.get(nom)]
            refrescar_cola()
            overflow_now = not nativos_linea1_pendientes(d)
            if len(ocupante[lin]) >= max_ocupantes(lin):
                break
            nxt = siguiente_candidato(lin, d, overflow_now, skip)
            if not nxt:
                break
            ocupante[lin].append(nxt)

    ocupante = {lin: [] for lin in caps_lineas}
    for d in range(total_dias):
        refrescar_cola()
        overflow = not nativos_linea1_pendientes(d)
        reclamar_lineas(d, ocupante, overflow)
        overflow = not nativos_linea1_pendientes(d)
        for m in lista:
            owned = [lin for lin, mods in ocupante.items() if m["nombre"] in mods]
            if len(owned) < 2:
                continue
            unfixed = [t for t in m["tareas"] if t["restante"] > 0 and not t.get("lineaFija")
                       and d >= dia_inicio_efectivo(t)]
            unfixed.sort(key=cmp_tareas_modelo)
            load = {lin: carga[lin][d] for lin in owned}
            for t in unfixed:
                cands = [lin for lin in owned if lin in elegibles(t, overflow)] or owned
                cands.sort(key=lambda lin: (load[lin], lin))
                t["lineaFija"] = cands[0]
                linea_por_mo[t.get("mo") or t["sku"]] = cands[0]
                load[cands[0]] += 0.01
        for lin in list(ocupante):
            producir_linea_dia(lin, d)
    return tareas


class TestColorYPrioridad(unittest.TestCase):
    def test_core_colors(self):
        self.assertEqual(rango_color("Negro"), 0)
        self.assertEqual(rango_color("NEGRO AVENTURA"), 0)
        self.assertEqual(rango_color("Blanco"), 1)
        self.assertEqual(rango_color("Ivory"), 1)
        self.assertEqual(rango_color("Azul Marino"), 2)
        self.assertEqual(rango_color("Azul marino - Beige"), 2)

    def test_similares_y_otros(self):
        self.assertEqual(rango_color("Beige - Negro"), 3)
        self.assertEqual(rango_color("Blanco Roto Extra"), 1)
        self.assertEqual(rango_color("Rojo"), 50)
        self.assertEqual(rango_color("Azul Rey"), 50)
        self.assertEqual(rango_color("Azul Lavanda"), 50)

    def test_prioridad_con_espacios(self):
        self.assertEqual(prioridad_num("Urgente "), 1)
        self.assertEqual(prioridad_num("URGENT"), 5)
        self.assertEqual(prioridad_num("Alta"), 2)
        self.assertEqual(prioridad_num(""), 5)


class TestCantidadMinima(unittest.TestCase):
    def _t(self, sku, color, cant, modelo="RIO DAMA", **kw):
        d = {
            "sku": sku, "color": color, "cantidad": cant, "modelo": modelo,
            "solicitadaOrig": cant, "esEspecial": False, "mo": sku, "cap": 130,
            "lineas": ["2", "4"], "prioridadNum": 1, "diaIngreso": 0, "fechaKey": 20260904,
        }
        d.update(kw)
        return d

    def test_fase1_prioriza_colores_core(self):
        tareas = [
            self._t("R", "Rojo", 80),
            self._t("N", "Negro", 80),
            self._t("B", "Blanco", 80),
            self._t("A", "Azul Marino", 80),
        ]
        out = expandir_por_minima(tareas, {"RIO DAMA": 200})
        fase1 = [t for t in out if t["esMinima"]]
        fase2 = [t for t in out if not t["esMinima"]]
        self.assertEqual(sum(t["cantidad"] for t in fase1), 200)
        colores_f1 = {t["color"] for t in fase1}
        self.assertIn("Negro", colores_f1)
        self.assertIn("Blanco", colores_f1)
        self.assertIn("Azul Marino", colores_f1)
        self.assertNotIn("Rojo", colores_f1)
        self.assertTrue(any(t["color"] == "Rojo" for t in fase2))

    def test_sin_minima_no_parte(self):
        tareas = [self._t("N", "Negro", 50)]
        out = expandir_por_minima(tareas, {})
        self.assertEqual(len(out), 1)
        self.assertFalse(out[0]["esMinima"])

    def test_minima_ya_cubierta_va_a_fase2(self):
        t = self._t("N", "Negro", 10)
        t["solicitadaOrig"] = 100
        out = expandir_por_minima([t], {"RIO DAMA": 50})
        self.assertFalse(out[0]["esMinima"])
        self.assertTrue(out[0]["fase2"])

    def test_cupo_minima_no_resta_lo_ya_producido(self):
        """Excel (12): 33 ya hechas, mínima 100 → cupo 100 del faltante, no 67."""
        t = self._t("ML", "Azul Marino", 479, modelo="MOTION LOOP CLASICA CAB")
        t["solicitadaOrig"] = 512
        out = expandir_por_minima([t], {"MOTION LOOP CLASICA CAB": 100})
        self.assertEqual(sum(x["cantidad"] for x in out if x["esMinima"]), 100)
        self.assertEqual(sum(x["cantidad"] for x in out if not x["esMinima"]), 379)
        self.assertNotEqual(sum(x["cantidad"] for x in out if x["esMinima"]), 67)

    def test_sku_minima_sale_antes_que_core(self):
        """Priorizacion - SKUs marca el SKU; no lo mete en banda mínima del modelo."""
        tareas = [
            self._t("R", "Rojo", 80),
            self._t("N", "Negro", 80),
            self._t("B", "Blanco", 80),
            self._t("A", "Azul Marino", 80),
        ]
        out = expandir_por_minima(tareas, {"RIO DAMA": 200}, {"R": 50})
        self.assertTrue(any(t["esSkuPrio"] and t["sku"] == "R" for t in out))
        self.assertFalse(any(t.get("esSkuPrio") and t["sku"] == "N" for t in out))
        fase1 = [t for t in out if t["esMinima"]]
        self.assertEqual(sum(t["cantidad"] for t in fase1), 200)
        self.assertIn("Negro", {t["color"] for t in fase1})

    def test_sku_minima_sin_cupo_de_modelo(self):
        tareas = [
            self._t("R", "Rojo", 80),
            self._t("N", "Negro", 80),
        ]
        out = expandir_por_minima(tareas, {}, {"R": 40})
        self.assertTrue(any(t.get("esSkuPrio") and t["sku"] == "R" for t in out))
        self.assertFalse(any(t.get("esMinima") for t in out))
        self.assertFalse(any(t.get("esSkuPrio") and t["sku"] == "N" for t in out))


    def test_match_case_insensitive(self):
        self.assertEqual(minima_de_modelo({"RIO DAMA": 400}, "rio dama"), 400)
        self.assertEqual(minima_de_modelo({"RIO DAMA": 400}, "RIO DAMA"), 400)


class TestPriorizacionSkus(unittest.TestCase):
    def test_skus_listados_salen_primero_cuando_entra_el_modelo(self):
        """Al entrar RIO, Gris/Marino de Priorizacion - SKUs salen antes que Negro/Blanco."""
        tareas = [
            {"sku": "N", "modelo": "RIO CAB", "mo": "MO-N", "cantidad": 130, "cap": 130,
             "lineas": ["4"], "color": "Negro", "prioridadNum": 1, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 20260914, "solicitadaOrig": 130},
            {"sku": "B", "modelo": "RIO CAB", "mo": "MO-B", "cantidad": 130, "cap": 130,
             "lineas": ["4"], "color": "Blanco", "prioridadNum": 1, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 20260914, "solicitadaOrig": 130},
            {"sku": "RIOMICA12TM", "modelo": "RIO CAB", "mo": "MO-NAVY", "cantidad": 80, "cap": 130,
             "lineas": ["4"], "color": "Azul Marino", "prioridadNum": 1, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 20260914, "solicitadaOrig": 80},
            {"sku": "RIOMICA30TS", "modelo": "RIO CAB", "mo": "MO-GRIS", "cantidad": 20, "cap": 130,
             "lineas": ["4"], "color": "Gris Claro", "prioridadNum": 1, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 20260914, "solicitadaOrig": 20},
        ]
        out = planificar(tareas, {}, total_dias=5, mapa_minimas_sku={
            "RIOMICA12TM": {"min": 80, "orden": 0},
            "RIOMICA30TS": {"min": 20, "orden": 1},
        })
        por = defaultdict(int)
        for t in out:
            por[t["sku"]] += t["plan"]["4"][0]
        self.assertEqual(por["RIOMICA12TM"], 80)
        self.assertEqual(por["RIOMICA30TS"], 20)
        self.assertEqual(por["N"], 30)
        self.assertEqual(por["B"], 0)
        self.assertEqual(sum(t["plan"]["4"][0] for t in out), 130)

    def test_sku_prio_no_adelanta_el_modelo(self):
        """Listar un SKU no quita la línea al modelo que ya toca por prioridad."""
        tareas = [
            {"sku": "V", "modelo": "VITA BIKER DAMA", "mo": "MO-V", "cantidad": 88, "cap": 130,
             "lineas": ["4"], "color": "Negro", "prioridadNum": 1, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 20260828, "solicitadaOrig": 88},
            {"sku": "R", "modelo": "BASIC LINE CROP TEE DAMA", "mo": "MO-R", "cantidad": 200, "cap": 130,
             "lineas": ["4"], "color": "Rojo", "prioridadNum": 2, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 20260926, "solicitadaOrig": 200},
            {"sku": "BN", "modelo": "BASIC LINE CROP TEE DAMA", "mo": "MO-BN", "cantidad": 200, "cap": 130,
             "lineas": ["4"], "color": "Negro", "prioridadNum": 2, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 20260926, "solicitadaOrig": 200},
        ]
        out = planificar(tareas, {}, total_dias=5, mapa_minimas_sku={"R": {"min": 50, "orden": 0}})
        lunes = defaultdict(int)
        lunes_sku = defaultdict(int)
        for t in out:
            lunes[t["modelo"]] += t["plan"]["4"][0]
            lunes_sku[t["sku"]] += t["plan"]["4"][0]
        self.assertEqual(lunes["VITA BIKER DAMA"], 88)
        self.assertEqual(lunes["BASIC LINE CROP TEE DAMA"], 42)
        self.assertEqual(lunes_sku["V"], 88)
        self.assertEqual(lunes_sku["R"], 42, "el sobrante del día debe ir al SKU priorizado de BASIC, no adelantar BASIC sobre VITA")
        self.assertEqual(lunes_sku["BN"], 0)
        self.assertEqual(sum(lunes.values()), 130)
        martes_sku = defaultdict(int)
        for t in out:
            if t["modelo"] == "BASIC LINE CROP TEE DAMA":
                martes_sku[t["sku"]] += t["plan"]["4"][1]
        self.assertEqual(martes_sku["R"], 130)
        self.assertEqual(martes_sku["BN"], 0)


class TestTresBandas(unittest.TestCase):
    def test_especial_luego_minima_luego_resto(self):
        especial = {"modelo": "CLÁSICA CAB", "esEspecial": True, "esMinima": False, "fechaKey": 20260901, "prioridadNum": 1}
        minima = {"modelo": "RIO DAMA", "esEspecial": False, "esMinima": True, "fechaKey": 20260904, "prioridadNum": 2}
        resto = {"modelo": "VITA DAMA", "esEspecial": False, "esMinima": False, "fechaKey": 20260828, "prioridadNum": 1}
        orden = sorted([resto, minima, especial], key=lambda t: (banda_de(t), t["fechaKey"], t["prioridadNum"]))
        self.assertEqual([t["modelo"] for t in orden], ["CLÁSICA CAB", "RIO DAMA", "VITA DAMA"])

    def test_tablero_ordena_por_primer_dia(self):
        filas = [
            ["2", "VITA DAMA", "Urgente", 0, 80, 80, 80, 80],
            ["2", "CLÁSICA CAB", "Especial", 60, 60, 0, 0, 0],
            ["4", "RIO DAMA", "Alta", 100, 100, 100, 100, 0],
        ]
        orden = sorted(filas, key=lambda f: (f[0], primer_dia_fila(f)))
        self.assertEqual([f[1] for f in orden if f[0] == "2"], ["CLÁSICA CAB", "VITA DAMA"])
        self.assertEqual(primer_dia_fila(filas[2]), 3)

    def test_tablero_flujo_remanente_primero(self):
        """El lote chico que cierra el día va antes del modelo que sigue toda la semana."""
        filas = [
            ["3", "COTTON KIDS", 16, 480, "--", "--", 130, 130, 130, 390],
            ["3", "MOTION LOOP CLASICA CAB", 16, 436, "--", "--", 28, 130, 130, 288],
        ]
        orden = sorted(filas, key=lambda f: cmp_filas_flujo_key(f, 4, 8, 1))
        self.assertEqual([f[1] for f in orden], ["MOTION LOOP CLASICA CAB", "COTTON KIDS"])

    def test_minima_respeta_dia_de_inicio(self):
        """La banda mínima no puede producir antes del Día de inicio (columna R)."""
        tareas = [
            {"sku": "ESP1", "modelo": "MAR CAB (Especial)", "color": "Azul", "cantidad": 130,
             "solicitadaOrig": 130, "esEspecial": True, "mo": "E1", "cap": 130,
             "lineas": ["1", "2"], "prioridadNum": 0, "diaIngreso": 0, "fechaKey": 20260904},
            {"sku": "ESP2", "modelo": "MAR DAMA (Especial)", "color": "Azul", "cantidad": 130,
             "solicitadaOrig": 130, "esEspecial": True, "mo": "E2", "cap": 130,
             "lineas": ["1", "2"], "prioridadNum": 0, "diaIngreso": 0, "fechaKey": 20260904},
            {"sku": "N", "modelo": "RIO DAMA", "color": "Negro", "cantidad": 165,
             "solicitadaOrig": 165, "esEspecial": False, "mo": "R-N", "cap": 130,
             "lineas": ["2", "4"], "prioridadNum": 2, "diaIngreso": 2, "fechaKey": 20260904},
            {"sku": "B", "modelo": "RIO DAMA", "color": "Blanco", "cantidad": 165,
             "solicitadaOrig": 165, "esEspecial": False, "mo": "R-B", "cap": 130,
             "lineas": ["2", "4"], "prioridadNum": 2, "diaIngreso": 2, "fechaKey": 20260904},
            {"sku": "A", "modelo": "RIO DAMA", "color": "Azul Marino", "cantidad": 70,
             "solicitadaOrig": 70, "esEspecial": False, "mo": "R-A", "cap": 130,
             "lineas": ["2", "4"], "prioridadNum": 2, "diaIngreso": 2, "fechaKey": 20260904},
            {"sku": "V", "modelo": "VITA BIKER DAMA", "color": "Negro", "cantidad": 88,
             "solicitadaOrig": 88, "esEspecial": False, "mo": "V1", "cap": 130,
             "lineas": ["4"], "prioridadNum": 1, "diaIngreso": 0, "fechaKey": 20260828},
        ]
        out = planificar(tareas, {"RIO DAMA": 400}, total_dias=5)
        lunes4 = defaultdict(int)
        miercoles4 = defaultdict(int)
        for t in out:
            lunes4[t["modelo"]] += t["plan"]["4"][0]
            miercoles4[t["modelo"]] += t["plan"]["4"][2]
        lunes_rio = 0
        miercoles_rio = 0
        for t in out:
            if t["modelo"] != "RIO DAMA":
                continue
            for lin, arr in t["plan"].items():
                lunes_rio += arr[0]
                miercoles_rio += arr[2]
        self.assertEqual(lunes4["RIO DAMA"], 0, "RIO DAMA no puede arrancar antes del día de inicio")
        self.assertEqual(lunes_rio, 0, "RIO DAMA no puede arrancar antes del día de inicio")
        self.assertEqual(lunes4["VITA BIKER DAMA"], 88)
        self.assertGreater(miercoles_rio, 0, "RIO DAMA mínima debe salir el miércoles (día de inicio)")
        self.assertGreaterEqual(sum(t["planificada"] for t in out if t.get("esMinima")), 390)

    def test_minima_gana_sobre_urgente_el_mismo_dia(self):
        """Cantidad mínima entra justo después de Especial, antes que Urgente."""
        tareas = [
            {"sku": "ESP1", "modelo": "MAR CAB (Especial)", "color": "Azul", "cantidad": 130,
             "solicitadaOrig": 130, "esEspecial": True, "mo": "E1", "cap": 130,
             "lineas": ["1", "2"], "prioridadNum": 0, "diaIngreso": 0, "fechaKey": 20260904},
            {"sku": "ESP2", "modelo": "MAR DAMA (Especial)", "color": "Azul", "cantidad": 130,
             "solicitadaOrig": 130, "esEspecial": True, "mo": "E2", "cap": 130,
             "lineas": ["1", "2"], "prioridadNum": 0, "diaIngreso": 0, "fechaKey": 20260904},
            {"sku": "N", "modelo": "RIO DAMA", "color": "Negro", "cantidad": 400,
             "solicitadaOrig": 400, "esEspecial": False, "mo": "R-N", "cap": 130,
             "lineas": ["2", "4"], "prioridadNum": 2, "diaIngreso": 0, "fechaKey": 20260904},
            {"sku": "V", "modelo": "VITA BIKER DAMA", "color": "Negro", "cantidad": 88,
             "solicitadaOrig": 88, "esEspecial": False, "mo": "V1", "cap": 130,
             "lineas": ["4"], "prioridadNum": 1, "diaIngreso": 0, "fechaKey": 20260828},
        ]
        out = planificar(tareas, {"RIO DAMA": 400}, total_dias=5)
        lunes4 = defaultdict(int)
        for t in out:
            lunes4[t["modelo"]] += t["plan"]["4"][0]
        self.assertEqual(lunes4["RIO DAMA"], 130)
        self.assertEqual(lunes4["VITA BIKER DAMA"], 0)
        self.assertEqual(sum(lunes4.values()), 130)

    def test_minima_gana_aunque_el_modelo_tambien_sea_urgente(self):
        """Regresión Excel (12): MOTION LOOP con mínima 100 debe salir antes que RIO urgente."""
        tareas = [
            {"sku": "ESP1", "modelo": "MAR CAB (Especial)", "color": "Azul", "cantidad": 130,
             "solicitadaOrig": 130, "esEspecial": True, "mo": "E1", "cap": 130,
             "lineas": ["1"], "prioridadNum": 0, "diaIngreso": 0, "fechaKey": 20260904},
            {"sku": "ESP2", "modelo": "MAR DAMA (Especial)", "color": "Azul", "cantidad": 130,
             "solicitadaOrig": 130, "esEspecial": True, "mo": "E2", "cap": 130,
             "lineas": ["2"], "prioridadNum": 0, "diaIngreso": 0, "fechaKey": 20260904},
            {"sku": "ESP3", "modelo": "DOMINIC CAB (Especial)", "color": "Azul", "cantidad": 130,
             "solicitadaOrig": 130, "esEspecial": True, "mo": "E3", "cap": 130,
             "lineas": ["3"], "prioridadNum": 0, "diaIngreso": 0, "fechaKey": 20260828},
            {"sku": "M1", "modelo": "MOTION LOOP CLASICA CAB", "color": "Negro", "cantidad": 479,
             "solicitadaOrig": 479, "esEspecial": False, "mo": "MO-ML", "cap": 130,
             "lineas": ["2", "4"], "prioridadNum": 1, "diaIngreso": 0, "fechaKey": 20260918},
            {"sku": "R1", "modelo": "RIO CAB", "color": "Negro", "cantidad": 400,
             "solicitadaOrig": 400, "esEspecial": False, "mo": "MO-RIO", "cap": 130,
             "lineas": ["2", "4"], "prioridadNum": 1, "diaIngreso": 0, "fechaKey": 20260914},
        ]
        out = planificar(tareas, {"MOTION LOOP CLASICA CAB": 100}, total_dias=5)
        lunes4 = defaultdict(int)
        for t in out:
            lunes4[t["modelo"]] += t["plan"]["4"][0]
        self.assertEqual(lunes4["MOTION LOOP CLASICA CAB"], 100)
        self.assertEqual(lunes4["RIO CAB"], 30)
        self.assertEqual(sum(lunes4.values()), 130)
        self.assertEqual(sum(t["planificada"] for t in out if t["modelo"] == "MOTION LOOP CLASICA CAB" and t.get("esMinima")), 100)

    def test_minima_programa_100_aunque_ya_hayan_33(self):
        """Excel (12): MOTION LOOP con 33 producidas y mínima 100 sigue programando 100, no 67."""
        tareas = [
            {"sku": "ESP1", "modelo": "MAR CAB (Especial)", "color": "Azul", "cantidad": 130,
             "solicitadaOrig": 130, "esEspecial": True, "mo": "E1", "cap": 130,
             "lineas": ["1"], "prioridadNum": 0, "diaIngreso": 3, "fechaKey": 20260904},
            {"sku": "ESP2", "modelo": "MAR DAMA (Especial)", "color": "Azul", "cantidad": 130,
             "solicitadaOrig": 130, "esEspecial": True, "mo": "E2", "cap": 130,
             "lineas": ["2"], "prioridadNum": 0, "diaIngreso": 3, "fechaKey": 20260904},
            {"sku": "ESP3", "modelo": "DOMINIC CAB (Especial)", "color": "Azul", "cantidad": 130,
             "solicitadaOrig": 130, "esEspecial": True, "mo": "E3", "cap": 130,
             "lineas": ["3"], "prioridadNum": 0, "diaIngreso": 3, "fechaKey": 20260828},
            {"sku": "M1", "modelo": "MOTION LOOP CLASICA CAB", "color": "Azul Marino", "cantidad": 479,
             "solicitadaOrig": 512, "esEspecial": False, "mo": "MO-ML", "cap": 130,
             "lineas": ["2", "4"], "prioridadNum": 1, "diaIngreso": 3, "fechaKey": 20260918},
            {"sku": "R1", "modelo": "RIO CAB", "color": "Negro", "cantidad": 400,
             "solicitadaOrig": 400, "esEspecial": False, "mo": "MO-RIO", "cap": 130,
             "lineas": ["2", "4"], "prioridadNum": 1, "diaIngreso": 3, "fechaKey": 20260914},
        ]
        out = planificar(tareas, {"MOTION LOOP CLASICA CAB": 100}, total_dias=5)
        jueves4 = defaultdict(int)
        for t in out:
            jueves4[t["modelo"]] += t["plan"]["4"][3]
        self.assertEqual(jueves4["MOTION LOOP CLASICA CAB"], 100)
        self.assertEqual(jueves4["RIO CAB"], 30)
        self.assertEqual(sum(jueves4.values()), 130)
        self.assertEqual(
            sum(t["planificada"] for t in out if t["modelo"] == "MOTION LOOP CLASICA CAB" and t.get("esMinima")),
            100,
        )
        self.assertEqual(sum(t["plan"]["4"][0] for t in out), 0, "antes del día de inicio no hay carga")


class TestLineasExclusivas(unittest.TestCase):
    def test_urgente_usa_dos_lineas(self):
        tareas = []
        for i in range(8):
            tareas.append({
                "sku": "R%d" % i, "modelo": "RIO DAMA", "mo": "MO-R%d" % i,
                "cantidad": 130, "cap": 130, "lineas": ["2", "4"],
                "color": "Negro", "prioridadNum": 1, "esEspecial": False,
                "diaIngreso": 0, "fechaKey": 20260914, "solicitadaOrig": 130,
            })
        out = planificar(tareas, {}, total_dias=5)
        por_linea = defaultdict(int)
        for t in out:
            for lin, arr in t["plan"].items():
                por_linea[lin] += sum(arr)
        self.assertGreater(por_linea["2"], 0)
        self.assertGreater(por_linea["4"], 0)

    def test_no_paralelo_mientras_ocupante_sigue(self):
        """L1-4: si el ocupante aún llena el día, el siguiente espera. Al terminar, el sobrante sí cambia de modelo."""
        tareas = [
            {"sku": "R1", "modelo": "RIO DAMA", "mo": "MO-R", "cantidad": 400, "cap": 130,
             "lineas": ["4"], "color": "Negro", "prioridadNum": 1, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 20260914, "solicitadaOrig": 400},
            {"sku": "V1", "modelo": "VITA BIKER DAMA", "mo": "MO-V", "cantidad": 400, "cap": 130,
             "lineas": ["4"], "color": "Negro", "prioridadNum": 2, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 20260828, "solicitadaOrig": 400},
        ]
        out = planificar(tareas, {}, total_dias=5)
        por_dia = []
        for d in range(5):
            modelos_hoy = defaultdict(int)
            for t in out:
                if t["plan"]["4"][d] > 0:
                    modelos_hoy[t["modelo"]] += t["plan"]["4"][d]
            por_dia.append(dict(modelos_hoy))
            self.assertEqual(sum(modelos_hoy.values()), 130, "día %s ocioso: %s" % (d, dict(modelos_hoy)))
        for d in range(3):
            self.assertEqual(por_dia[d], {"RIO DAMA": 130}, "día %s mezcló en paralelo: %s" % (d, por_dia[d]))
        self.assertEqual(por_dia[3]["RIO DAMA"], 10)
        self.assertEqual(por_dia[3]["VITA BIKER DAMA"], 120)
        self.assertEqual(por_dia[4], {"VITA BIKER DAMA": 130})

    def test_cambio_modelo_llena_sobrante_del_dia(self):
        """Al terminar un modelo a media jornada, el siguiente usa el resto de la capacidad ese mismo día."""
        tareas = [
            {"sku": "V1", "modelo": "VITA BIKER DAMA", "mo": "MO-V", "cantidad": 88, "cap": 130,
             "lineas": ["4"], "color": "Negro", "prioridadNum": 1, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 20260828, "solicitadaOrig": 88},
            {"sku": "B1", "modelo": "BASIC LINE CROP TEE DAMA", "mo": "MO-B", "cantidad": 200, "cap": 130,
             "lineas": ["4"], "color": "Rojo", "prioridadNum": 2, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 20260926, "solicitadaOrig": 200},
        ]
        out = planificar(tareas, {}, total_dias=5)
        lunes = defaultdict(int)
        for t in out:
            lunes[t["modelo"]] += t["plan"]["4"][0]
        self.assertEqual(lunes["VITA BIKER DAMA"], 88)
        self.assertEqual(lunes["BASIC LINE CROP TEE DAMA"], 42)
        self.assertEqual(sum(lunes.values()), 130)

    def test_linea1_cambio_secuencial_llena_sobrante(self):
        """L1 no queda a 80/130 cuando el nativo termina; el siguiente especial que SÍ lista L1 usa el sobrante."""
        tareas = [
            {"sku": "MD1", "modelo": "MAR DAMA (Especial)", "color": "Blanco", "cantidad": 80,
             "solicitadaOrig": 80, "esEspecial": True, "mo": "MO-MD", "cap": 130,
             "lineas": ["1"], "prioridadNum": 0, "diaIngreso": 0, "fechaKey": 20260828},
            {"sku": "BC1", "modelo": "BASIC CAB (Especial)", "color": "Blanco", "cantidad": 96,
             "solicitadaOrig": 96, "esEspecial": True, "mo": "MO-BC", "cap": 130,
             "lineas": ["1"], "prioridadNum": 0, "diaIngreso": 0, "fechaKey": 20260904},
            {"sku": "CD1", "modelo": "CLÁSICA DAMA (Especial)", "color": "Negro", "cantidad": 149,
             "solicitadaOrig": 149, "esEspecial": True, "mo": "MO-CD", "cap": 130,
             "lineas": ["3"], "prioridadNum": 0, "diaIngreso": 0, "fechaKey": 20260904},
        ]
        out = planificar(tareas, {}, total_dias=5)
        lunes1 = defaultdict(int)
        lunes3 = defaultdict(int)
        for t in out:
            lunes1[t["modelo"]] += t["plan"]["1"][0]
            lunes3[t["modelo"]] += t["plan"]["3"][0]
        self.assertEqual(sum(lunes1.values()), 130, "L1 lunes incompleto: %s" % dict(lunes1))
        self.assertEqual(lunes1["MAR DAMA (Especial)"], 80)
        self.assertEqual(lunes1["BASIC CAB (Especial)"], 50)
        self.assertEqual(lunes1.get("CLÁSICA DAMA (Especial)", 0), 0)
        self.assertGreater(lunes3["CLÁSICA DAMA (Especial)"], 0)

    def test_especial_no_desborda_a_linea1(self):
        """Un especial de L3 no se redirige a L1 aunque L1 quede libre."""
        tareas = [
            {"sku": "M1", "modelo": "MAR CAB (Especial)", "mo": "MO-M", "cantidad": 50, "cap": 130,
             "lineas": ["1"], "color": "Azul", "prioridadNum": 0, "esEspecial": True,
             "diaIngreso": 0, "fechaKey": 20260904, "solicitadaOrig": 50},
            {"sku": "D1", "modelo": "DOMINIC CAB (Especial)", "mo": "MO-D1", "cantidad": 80, "cap": 130,
             "lineas": ["3"], "color": "Blanco", "prioridadNum": 0, "esEspecial": True,
             "diaIngreso": 0, "fechaKey": 20260828, "solicitadaOrig": 80},
            {"sku": "D2", "modelo": "DOMINIC CAB (Especial)", "mo": "MO-D2", "cantidad": 80, "cap": 130,
             "lineas": ["3"], "color": "Blanco", "prioridadNum": 0, "esEspecial": True,
             "diaIngreso": 0, "fechaKey": 20260828, "solicitadaOrig": 80},
            {"sku": "D3", "modelo": "DOMINIC CAB (Especial)", "mo": "MO-D3", "cantidad": 80, "cap": 130,
             "lineas": ["3"], "color": "Blanco", "prioridadNum": 0, "esEspecial": True,
             "diaIngreso": 0, "fechaKey": 20260828, "solicitadaOrig": 80},
        ]
        out = planificar(tareas, {}, total_dias=10)
        en_l1 = sum(sum(t["plan"]["1"]) for t in out if t["modelo"].startswith("DOMINIC"))
        en_l3 = sum(sum(t["plan"]["3"]) for t in out if t["modelo"].startswith("DOMINIC"))
        self.assertEqual(en_l1, 0, "DOMINIC no debe salir de la línea 3")
        self.assertEqual(en_l3, 240)

    def test_linea5_sola_usa_capacidad_40(self):
        tareas = [{
            "sku": "V1", "modelo": "VITA LEGGINGS DAMA", "mo": "MO-V",
            "cantidad": 88, "cap": 40, "lineas": ["5"],
            "color": "Negro", "prioridadNum": 1, "esEspecial": False,
            "diaIngreso": 0, "fechaKey": 20260828, "solicitadaOrig": 88,
        }]
        out = planificar(tareas, {}, total_dias=5)
        dias = out[0]["plan"]["5"]
        self.assertEqual(list(dias[:3]), [40, 40, 8])

    def test_linea5_cambio_secuencial_llena_sobrante(self):
        """Si el único ocupante de L5 termina a media jornada, el siguiente usa las piezas que quedan."""
        tareas = [
            {"sku": "V1", "modelo": "VITA LEGGINGS DAMA", "mo": "MO-V",
             "cantidad": 8, "cap": 40, "lineas": ["5"], "color": "Negro",
             "prioridadNum": 1, "esEspecial": False, "diaIngreso": 0,
             "fechaKey": 20260828, "solicitadaOrig": 8},
            {"sku": "D1", "modelo": "SHORT SPORT R1 DAMA", "mo": "MO-D",
             "cantidad": 200, "cap": 40, "lineas": ["5"], "color": "Negro",
             "prioridadNum": 2, "esEspecial": False, "diaIngreso": 0,
             "fechaKey": 20260910, "solicitadaOrig": 200},
        ]
        out = planificar(tareas, {}, total_dias=5)
        lunes = defaultdict(int)
        for t in out:
            lunes[t["modelo"]] += t["plan"]["5"][0]
        self.assertEqual(lunes["VITA LEGGINGS DAMA"], 8)
        self.assertEqual(lunes["SHORT SPORT R1 DAMA"], 32)
        self.assertEqual(sum(lunes.values()), 40)

    def test_linea5_dos_modelos_comparten_el_dia(self):
        """Familias distintas en L5 sí van en paralelo; misma familia (R1 CAB/DAMA) va en secuencia."""
        tareas = [
            {"sku": "D1", "modelo": "SHORT SPORT R1 DAMA", "mo": "MO-D",
             "cantidad": 200, "cap": 40, "lineas": ["5"], "color": "Negro",
             "prioridadNum": 1, "esEspecial": False, "diaIngreso": 0,
             "fechaKey": 20260910, "solicitadaOrig": 200},
            {"sku": "C1", "modelo": "SHORT SPORT R1 CAB", "mo": "MO-C",
             "cantidad": 185, "cap": 40, "lineas": ["5"], "color": "Negro",
             "prioridadNum": 2, "esEspecial": False, "diaIngreso": 0,
             "fechaKey": 20260912, "solicitadaOrig": 185},
        ]
        out = planificar(tareas, {}, total_dias=5)
        for d in range(5):
            por = defaultdict(int)
            for t in out:
                por[t["modelo"]] += t["plan"]["5"][d]
            self.assertEqual(sum(por.values()), 40, "día %s total %s" % (d, dict(por)))
            vivos = [m for m, v in por.items() if v > 0]
            self.assertLessEqual(len(vivos), 2)
            if d < 4:
                self.assertEqual(por["SHORT SPORT R1 CAB"], 40)
                self.assertEqual(por.get("SHORT SPORT R1 DAMA", 0), 0)
            else:
                self.assertEqual(por["SHORT SPORT R1 CAB"], 25)
                self.assertEqual(por["SHORT SPORT R1 DAMA"], 15)

    def test_linea5_familias_distintas_en_paralelo(self):
        tareas = [
            {"sku": "A", "modelo": "MODELO A", "mo": "MO-A", "cantidad": 400, "cap": 40,
             "lineas": ["5"], "color": "Negro", "prioridadNum": 1, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 1, "solicitadaOrig": 400},
            {"sku": "B", "modelo": "MODELO B", "mo": "MO-B", "cantidad": 400, "cap": 40,
             "lineas": ["5"], "color": "Negro", "prioridadNum": 2, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 1, "solicitadaOrig": 400},
        ]
        out = planificar(tareas, {}, total_dias=1)
        por = defaultdict(int)
        for t in out:
            por[t["modelo"]] += t["plan"]["5"][0]
        self.assertEqual(por["MODELO A"], 20)
        self.assertEqual(por["MODELO B"], 20)

    def test_linea5_maximo_dos_modelos(self):
        tareas = [
            {"sku": "A", "modelo": "MODELO A", "mo": "MO-A", "cantidad": 400, "cap": 40,
             "lineas": ["5"], "color": "Negro", "prioridadNum": 1, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 1, "solicitadaOrig": 400},
            {"sku": "B", "modelo": "MODELO B", "mo": "MO-B", "cantidad": 400, "cap": 40,
             "lineas": ["5"], "color": "Negro", "prioridadNum": 2, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 1, "solicitadaOrig": 400},
            {"sku": "C", "modelo": "MODELO C", "mo": "MO-C", "cantidad": 400, "cap": 40,
             "lineas": ["5"], "color": "Negro", "prioridadNum": 3, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 1, "solicitadaOrig": 400},
        ]
        out = planificar(tareas, {}, total_dias=1)
        modelos_hoy = {t["modelo"] for t in out if t["plan"]["5"][0] > 0}
        self.assertEqual(modelos_hoy, {"MODELO A", "MODELO B"})
        self.assertEqual(sum(t["plan"]["5"][0] for t in out), 40)

    def test_linea5_varios_mos_no_quedan_en_lote_5(self):
        """Regresión v5.9: el lote de 5 no puede ser techo diario cuando L5 va sola."""
        tareas = [{
            "sku": "D%d" % i, "modelo": "SHORT SPORT R1 DAMA", "mo": "MO-D%d" % i,
            "cantidad": 30, "cap": 40, "lineas": ["5"], "color": "Negro",
            "prioridadNum": 1, "esEspecial": False, "diaIngreso": 0,
            "fechaKey": 20260910, "solicitadaOrig": 30,
        } for i in range(6)]
        out = planificar(tareas, {}, total_dias=5)
        self.assertEqual(sum(t["plan"]["5"][0] for t in out), 40)

    def test_linea5_reparte_varios_modelos_en_horizonte(self):
        tareas = [
            {"sku": "VL", "modelo": "VITA LEGGINGS DAMA", "mo": "MO-VL", "cantidad": 88,
             "cap": 40, "lineas": ["5"], "color": "Negro", "prioridadNum": 1,
             "esEspecial": False, "diaIngreso": 0, "fechaKey": 20260828, "solicitadaOrig": 88},
            {"sku": "RD", "modelo": "SHORT SPORT R1 DAMA", "mo": "MO-RD", "cantidad": 268,
             "cap": 40, "lineas": ["5"], "color": "Negro", "prioridadNum": 2,
             "esEspecial": False, "diaIngreso": 0, "fechaKey": 20260910, "solicitadaOrig": 268},
            {"sku": "RC", "modelo": "SHORT SPORT R1 CAB", "mo": "MO-RC", "cantidad": 185,
             "cap": 40, "lineas": ["5"], "color": "Negro", "prioridadNum": 2,
             "esEspecial": False, "diaIngreso": 0, "fechaKey": 20260912, "solicitadaOrig": 185},
            {"sku": "VA", "modelo": "VESTIDO ARYNA DAMA", "mo": "MO-VA", "cantidad": 192,
             "cap": 40, "lineas": ["5"], "color": "Negro", "prioridadNum": 3,
             "esEspecial": False, "diaIngreso": 0, "fechaKey": 20260918, "solicitadaOrig": 192},
            {"sku": "SC", "modelo": "SHORT SPORT CAB", "mo": "MO-SC", "cantidad": 784,
             "cap": 40, "lineas": ["5"], "color": "Negro", "prioridadNum": 3,
             "esEspecial": False, "diaIngreso": 0, "fechaKey": 20260920, "solicitadaOrig": 784},
        ]
        out = planificar(tareas, {}, total_dias=25)
        por_modelo = defaultdict(int)
        for t in out:
            por_modelo[t["modelo"]] += t["planificada"]
        self.assertEqual(por_modelo["VITA LEGGINGS DAMA"], 88)
        self.assertGreater(por_modelo["SHORT SPORT R1 DAMA"], 0)
        self.assertGreater(por_modelo["SHORT SPORT R1 CAB"], 0)
        programados = [m for m, v in por_modelo.items() if v > 0]
        self.assertGreaterEqual(len(programados), 3, programados)
        for d in range(25):
            modelos_hoy = {t["modelo"] for t in out if t["plan"]["5"][d] > 0}
            self.assertLessEqual(len(modelos_hoy), 2, "día %s mezcló %s" % (d, modelos_hoy))
            self.assertEqual(sum(t["plan"]["5"][d] for t in out), 40)

    def test_especial_ordena_por_fecha(self):
        a = {"modelo": "CLÁSICA CAB", "esEspecial": True, "esMinima": False, "fechaKey": 20260904, "prioridadNum": 0}
        b = {"modelo": "DOMINIC CAB", "esEspecial": True, "esMinima": False, "fechaKey": 20260828, "prioridadNum": 0}
        orden = sorted([a, b], key=lambda t: (banda_de(t), t["fechaKey"]))
        self.assertEqual([t["modelo"] for t in orden], ["DOMINIC CAB", "CLÁSICA CAB"])

    def test_priorizacion_quita_faltante_cero(self):
        filas = [
            {"modelo": "CLÁSICA STRETCH CAB", "tipo": "Especial", "faltante": 0},
            {"modelo": "RIO DAMA", "tipo": "Producción", "faltante": 1605},
            {"modelo": "MAR CAB", "tipo": "Especial", "faltante": 10},
            {"modelo": "MAR CAB", "tipo": "Especial", "faltante": 0},
        ]
        vivos = modelos_con_faltante(filas)
        self.assertNotIn(("CLÁSICA STRETCH CAB", "Especial"), vivos)
        self.assertIn(("RIO DAMA", "Producción"), vivos)
        self.assertIn(("MAR CAB", "Especial"), vivos)


class TestMOAtomica(unittest.TestCase):
    def test_una_mo_una_linea(self):
        tareas = [
            {"sku": "A", "modelo": "X", "mo": "MO1", "cantidad": 200, "cap": 130, "lineas": ["2", "4"],
             "color": "Negro", "prioridadNum": 1, "esEspecial": False, "diaIngreso": 0, "fechaKey": 1},
            {"sku": "B", "modelo": "Y", "mo": "MO2", "cantidad": 200, "cap": 130, "lineas": ["2", "4"],
             "color": "Rojo", "prioridadNum": 2, "esEspecial": False, "diaIngreso": 0, "fechaKey": 1},
        ]
        results = planificar(tareas, {}, total_dias=10)
        for r in results:
            lineas_usadas = [lin for lin, arr in r["plan"].items() if sum(arr) > 0]
            self.assertEqual(len(lineas_usadas), 1, msg=r["mo"] + " se partio: " + str(lineas_usadas))

    def test_fase1_y_fase2_misma_linea(self):
        tareas = [
            {"sku": "A", "modelo": "RIO DAMA", "mo": "MO9", "cantidad": 50, "cap": 130, "lineas": ["2", "4"],
             "color": "Negro", "prioridadNum": 1, "esEspecial": False, "diaIngreso": 0, "fechaKey": 1,
             "solicitadaOrig": 130},
            {"sku": "A2", "modelo": "RIO DAMA", "mo": "MO9", "cantidad": 80, "cap": 130, "lineas": ["2", "4"],
             "color": "Negro", "prioridadNum": 1, "esEspecial": False, "diaIngreso": 0, "fechaKey": 1,
             "solicitadaOrig": 80},
        ]
        results = planificar(tareas, {"RIO DAMA": 50}, total_dias=10)
        lineas = set()
        for r in results:
            for lin, arr in r["plan"].items():
                if sum(arr) > 0:
                    lineas.add(lin)
        self.assertEqual(len(lineas), 1)


class TestAcumulado(unittest.TestCase):
    def test_acumulado_hasta_meta_sin_repetir(self):
        self.assertEqual(acumular_semanas([88, 0, 0, 0, 0], 88), [88, None, None, None, None])
        self.assertEqual(acumular_semanas([390, 93, 0, 0, 0], 483), [390, 483, None, None, None])
        self.assertEqual(acumular_semanas([16, 100, 131, 21, 0], 268), [16, 116, 247, 268, None])
        self.assertEqual(acumular_semanas([107, 325, 325, 325, 325], 2010), [107, 432, 757, 1082, 1407])
        self.assertEqual(acumular_semanas([0, 0, 31, 0, 0], 31), [None, None, 31, None, None])

    def test_vacio(self):
        self.assertEqual(acumular_semanas([0, 0, 0]), [None, None, None])

    def test_colores_umbral_primer_cruce(self):
        # BASIC LINE CROP TEE DAMA: 250 amarillo, 339 blanco, 357 verde
        self.assertEqual(
            umbrales_semana([250, "--", "--", 339, 357], 250, 357),
            ["#FFE599", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#D9EAD3"],
        )
        # CLÁSICA CAB: 390 blanco, 483 verde (meta)
        self.assertEqual(
            umbrales_semana([390, 483, "--", "--", "--"], 0, 483),
            ["#FFFFFF", "#D9EAD3", "#FFFFFF", "#FFFFFF", "#FFFFFF"],
        )
        # Misma semana mínima y meta → gana verde
        self.assertEqual(umbrales_semana([408, "--"], 250, 408), ["#D9EAD3", "#FFFFFF"])
        self.assertEqual(umbrales_semana(["--", "--"], 100, 400), ["#FFFFFF", "#FFFFFF"])

    def test_origen_tabla_b2_y_enlace_sku(self):
        self.assertEqual(FILA_ENC_PROY, 2)
        self.assertEqual(COL_INI_PROY, 2)
        self.assertEqual(FILA_DATOS_PROY, 3)
        skus = [
            {"sku": "CLA1", "modelo": "CLÁSICA CAB (Especial)"},
            {"sku": "CLA2", "modelo": "CLÁSICA CAB (Especial)"},
            {"sku": "BL1", "modelo": "BASIC LINE CROP TEE DAMA"},
        ]
        primera = primera_fila_sku(skus, FILA_DATOS_PROY)
        self.assertEqual(primera["CLÁSICA CAB (Especial)"], 3)
        self.assertEqual(primera["BASIC LINE CROP TEE DAMA"], 5)
        self.assertEqual(link_modelo_sku(123, primera["BASIC LINE CROP TEE DAMA"]), "#gid=123&range=B5")


class TestV597CapFamiliaSyncAlmacen(unittest.TestCase):
    def test_cap_diaria_sale_del_producto_no_del_techo_fijo(self):
        tareas = [{
            "sku": "X1", "modelo": "TEST CAP CAB", "mo": "MO-X", "cantidad": 200,
            "cap": 50, "lineas": ["1"], "color": "Negro", "prioridadNum": 3,
            "esEspecial": False, "diaIngreso": 0, "fechaKey": 1, "solicitadaOrig": 200,
        }]
        out = planificar(tareas, {}, total_dias=5)
        self.assertEqual(list(out[0]["plan"]["1"][:4]), [50, 50, 50, 50])
        self.assertEqual(sum(t["planificada"] for t in out), 200)

    def test_sobrante_usa_cap_del_siguiente_modelo(self):
        tareas = [
            {"sku": "A", "modelo": "ALPHA CAB", "mo": "MO-A", "cantidad": 20, "cap": 100,
             "lineas": ["2"], "color": "Negro", "prioridadNum": 1, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 1, "solicitadaOrig": 20},
            {"sku": "B", "modelo": "BETA KIDS", "mo": "MO-B", "cantidad": 200, "cap": 50,
             "lineas": ["2"], "color": "Negro", "prioridadNum": 2, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 2, "solicitadaOrig": 200},
        ]
        out = planificar(tareas, {}, total_dias=5)
        lunes = defaultdict(int)
        for t in out:
            lunes[t["modelo"]] += t["plan"]["2"][0]
        self.assertEqual(lunes["ALPHA CAB"], 20)
        self.assertEqual(lunes["BETA KIDS"], 40)
        self.assertEqual(sum(lunes.values()), 60)

    def test_secuencia_genero_misma_linea(self):
        tareas = []
        for gen, sku, cant in (("CAB", "RC", 130), ("DAMA", "RD", 130), ("KIDS", "RK", 130)):
            tareas.append({
                "sku": sku, "modelo": "RIO " + gen, "mo": "MO-" + sku, "cantidad": cant,
                "cap": 130, "lineas": ["4"], "color": "Negro", "prioridadNum": 3,
                "esEspecial": False, "diaIngreso": 0, "fechaKey": 20260920,
                "solicitadaOrig": cant, "genero": gen, "familia": "RIO",
            })
        out = planificar(tareas, {}, total_dias=5)
        por_dia = []
        for d in range(3):
            mods = {t["modelo"]: t["plan"]["4"][d] for t in out if t["plan"]["4"][d] > 0}
            por_dia.append(mods)
            self.assertEqual(sum(mods.values()), 130)
            self.assertEqual(len(mods), 1, "día %s mezcló géneros: %s" % (d, mods))
        self.assertEqual(list(por_dia[0].keys()), ["RIO CAB"])
        self.assertEqual(list(por_dia[1].keys()), ["RIO DAMA"])
        self.assertEqual(list(por_dia[2].keys()), ["RIO KIDS"])

    def test_familia_no_fuerza_misma_linea_si_hay_otra(self):
        tareas = [
            {"sku": "MD", "modelo": "MAR DAMA (Especial)", "mo": "MO-MD", "cantidad": 80, "cap": 130,
             "lineas": ["1"], "color": "Blanco", "prioridadNum": 0, "esEspecial": True,
             "diaIngreso": 0, "fechaKey": 20260828, "solicitadaOrig": 80},
            {"sku": "MC", "modelo": "MAR CAB (Especial)", "mo": "MO-MC", "cantidad": 96, "cap": 130,
             "lineas": ["1", "2"], "color": "Blanco", "prioridadNum": 0, "esEspecial": True,
             "diaIngreso": 0, "fechaKey": 20260904, "solicitadaOrig": 96},
        ]
        out = planificar(tareas, {}, total_dias=5)
        lunes1 = sum(t["plan"]["1"][0] for t in out if t["modelo"] == "MAR DAMA (Especial)")
        self.assertEqual(lunes1, 80)

    def test_almacen_son_4_dias_habiles(self):
        import datetime
        # Viernes 4 sep 2026 → +4 hábiles = jueves 10
        viernes = datetime.datetime(2026, 9, 4)
        self.assertEqual(add_business_days_from_naive(viernes, 4).date(), datetime.date(2026, 9, 10))
        self.assertEqual(add_business_days_from_naive(viernes, 2).date(), datetime.date(2026, 9, 8))
        self.assertEqual(DIAS_ENTRADA_ALMACEN, 4)

    def test_sync_suma_solo_el_delta(self):
        import datetime
        filas = [
            {"mo": "00071", "sku": "A", "qty": 40, "fecha": "d1", "linea": "2"},
            {"mo": "00071", "sku": "A", "qty": 10, "fecha": "d2", "linea": "2"},
            {"mo": "82-002", "sku": "B", "qty": 25, "fecha": "d3", "linea": "1"},
        ]
        # "5.9.12" lo convierte Google en fecha: no es esquema válido → no suma
        self.assertFalse(es_esquema_sync_actual(datetime.datetime(2012, 9, 5)))
        self.assertEqual(resolver_delta_costura(filas, datetime.datetime(2012, 9, 5), {}), {})
        # Primera vez sin SYNC-V13: Por Hacer es la base
        self.assertEqual(resolver_delta_costura(filas, "", {}), {})
        self.assertEqual(inyectar_cantida_por_hacer(100, "00071", {}), 100)
        aplicadas = {}
        for f in filas:
            fp = huella_fila_costura(f)
            aplicadas[fp] = aplicadas.get(fp, 0) + 1
        nueva = {"mo": "00071", "sku": "C", "qty": 8, "fecha": "d4", "linea": "2"}
        delta = resolver_delta_costura(filas + [nueva], "SYNC-V13", aplicadas)
        self.assertEqual(delta, {"71": 8.0})
        self.assertEqual(inyectar_cantida_por_hacer(100, "00071", delta), 108)
        self.assertEqual(fusionar_cantida_producida(100, 20), 120)

    def test_sync_invalida_baseline_vieja_y_padding_mo(self):
        self.assertEqual(clave_lookup_mo("00071"), "71")
        self.assertEqual(clave_lookup_mo(71), "71")
        self.assertEqual(clave_lookup_mo("00082-002"), "82-002")
        self.assertTrue(es_esquema_sync_actual("SYNC-V13"))
        # Misma huella dos veces: la segunda ocurrencia sí se suma
        f = {"mo": "00071", "sku": "X", "qty": 12, "fecha": "d", "linea": "5"}
        aplicadas = {huella_fila_costura(f): 1}
        delta = resolver_delta_costura([f, f], "SYNC-V13", aplicadas)
        self.assertEqual(delta, {"71": 12.0})
        self.assertEqual(inyectar_cantida_por_hacer(22, "00071", delta), 34)

    def test_especial_hecho_no_entra_al_backlog(self):
        self.assertTrue(es_especial_hecho("Hecho"))
        self.assertTrue(es_especial_hecho("hecho"))
        self.assertFalse(es_especial_hecho("Confirmada"))
        self.assertFalse(es_especial_hecho("Cancelada"))

    def test_especial_hecho_no_se_archiva(self):
        self.assertFalse(debe_archivar_mo("Especial", "Hecho"))
        self.assertTrue(debe_archivar_mo("Especial", "Cancelada"))
        self.assertTrue(debe_archivar_mo("Producción", "Hecho"))
        self.assertTrue(debe_archivar_mo("Producción", "cancelada"))


class TestLotesGeneroColor(unittest.TestCase):
    def _t(self, sku, modelo, color, cant, lineas, **kw):
        d = {
            "sku": sku, "modelo": modelo, "mo": "MO-" + sku, "cantidad": cant,
            "cap": 130, "lineas": lineas, "color": color, "prioridadNum": 1,
            "esEspecial": False, "diaIngreso": 0, "fechaKey": 20260910,
            "solicitadaOrig": cant, "genero": modelo.split()[-1],
        }
        d.update(kw)
        return d

    def _por_dia_linea(self, out, lin, d):
        por = defaultdict(int)
        for t in out:
            por[t["modelo"]] += t["plan"][lin][d]
        return dict((k, v) for k, v in por.items() if v > 0)

    def test_familia_dos_lineas_libres_en_paralelo(self):
        """Dos géneros asignados a 2 líneas libres: uno por línea el mismo día."""
        tareas = [
            self._t("CB", "DAILY CAB", "Blanco", 400, ["3", "4"], fechaKey=20260912, prioridadNum=2),
            self._t("DB", "DAILY DAMA", "Blanco", 400, ["3", "4"], fechaKey=20260910, prioridadNum=1),
        ]
        out = planificar(tareas, {}, total_dias=10)
        d0_3 = self._por_dia_linea(out, "3", 0)
        d0_4 = self._por_dia_linea(out, "4", 0)
        modelos_hoy = set(list(d0_3.keys()) + list(d0_4.keys()))
        self.assertEqual(modelos_hoy, {"DAILY CAB", "DAILY DAMA"}, "3=%s 4=%s" % (d0_3, d0_4))
        self.assertEqual(sum(d0_3.values()) + sum(d0_4.values()), 260)
        self.assertEqual(sum(t["planificada"] for t in out if t["modelo"] == "DAILY CAB"), 400)
        self.assertEqual(sum(t["planificada"] for t in out if t["modelo"] == "DAILY DAMA"), 400)

    def test_familia_una_linea_libre_secuencia(self):
        """Si una de las dos líneas está ocupada, secuencian por color/género en la libre."""
        tareas = [
            self._t("CK", "COTTON KIDS", "Rojo", 800, ["3"], fechaKey=20260801, prioridadNum=1),
            self._t("CB", "RIO CAB", "Negro", 200, ["3", "4"], fechaKey=20260912, prioridadNum=2),
            self._t("DB", "RIO DAMA", "Negro", 200, ["3", "4"], fechaKey=20260910, prioridadNum=2),
        ]
        out = planificar(tareas, {}, total_dias=5)
        d0_3 = self._por_dia_linea(out, "3", 0)
        d0_4 = self._por_dia_linea(out, "4", 0)
        self.assertEqual(d0_3.get("COTTON KIDS", 0), 130, d0_3)
        self.assertEqual(d0_4, {"RIO CAB": 130}, d0_4)
        d1_4 = self._por_dia_linea(out, "4", 1)
        self.assertEqual(d1_4.get("RIO CAB", 0), 70)
        self.assertEqual(d1_4.get("RIO DAMA", 0), 60)

    def test_familia_segunda_linea_se_libera_en_paralelo(self):
        """RIO CAB/DAMA en 2 y 4: mientras COTTON ocupa la 2 van solo en la 4; al liberarse, un género por línea."""
        tareas = [
            self._t("CK", "COTTON KIDS", "Rojo", 130, ["2"], fechaKey=20260801, prioridadNum=1),
            self._t("CB", "RIO CAB", "Negro", 400, ["2", "4"], fechaKey=20260912, prioridadNum=2),
            self._t("DB", "RIO DAMA", "Negro", 400, ["2", "4"], fechaKey=20260910, prioridadNum=2),
        ]
        out = planificar(tareas, {}, total_dias=5)
        d0_2 = self._por_dia_linea(out, "2", 0)
        d0_4 = self._por_dia_linea(out, "4", 0)
        self.assertEqual(d0_2, {"COTTON KIDS": 130}, d0_2)
        self.assertEqual(d0_4, {"RIO CAB": 130}, d0_4)
        d1_2 = self._por_dia_linea(out, "2", 1)
        d1_4 = self._por_dia_linea(out, "4", 1)
        modelos_d1 = set(list(d1_2.keys()) + list(d1_4.keys()))
        self.assertEqual(modelos_d1, {"RIO CAB", "RIO DAMA"}, "2=%s 4=%s" % (d1_2, d1_4))
        self.assertEqual(len(d1_2), 1, d1_2)
        self.assertEqual(len(d1_4), 1, d1_4)
        self.assertEqual(sum(d1_2.values()) + sum(d1_4.values()), 260)

    def test_familia_cotton_libera_linea2_rio_paralelo(self):
        """Excel (4): COTTON KIDS en 2; RIO CAB/DAMA en 2 y 4. Al terminar COTTON, cada género toma una línea."""
        tareas = [
            self._t("CK", "COTTON KIDS", "Rojo", 800, ["2"], fechaKey=20260801, prioridadNum=1),
            self._t("CB", "RIO CAB", "Negro", 2000, ["2", "4"], fechaKey=20260912, prioridadNum=2),
            self._t("DB", "RIO DAMA", "Negro", 2000, ["2", "4"], fechaKey=20260910, prioridadNum=2),
        ]
        out = planificar(tareas, {}, total_dias=15)
        for d in range(6):
            d2 = self._por_dia_linea(out, "2", d)
            d4 = self._por_dia_linea(out, "4", d)
            self.assertEqual(d2.get("COTTON KIDS", 0), 130, "día %s L2=%s" % (d, d2))
            self.assertTrue(set(d4.keys()) <= {"RIO CAB", "RIO DAMA"}, d4)
            self.assertNotIn("RIO CAB", d2)
            self.assertNotIn("RIO DAMA", d2)
        d6_2 = self._por_dia_linea(out, "2", 6)
        self.assertEqual(d6_2.get("COTTON KIDS", 0), 20, d6_2)
        self.assertEqual(d6_2.get("RIO DAMA", 0), 110, d6_2)
        d6_4 = self._por_dia_linea(out, "4", 6)
        self.assertEqual(d6_4, {"RIO CAB": 130}, d6_4)
        for d in range(7, 12):
            d2 = self._por_dia_linea(out, "2", d)
            d4 = self._por_dia_linea(out, "4", d)
            self.assertEqual(d2, {"RIO DAMA": 130}, "día %s L2=%s" % (d, d2))
            self.assertEqual(d4, {"RIO CAB": 130}, "día %s L4=%s" % (d, d4))

    def test_familia_urgente_no_acapara_segunda_linea(self):
        """Urgente con 2 líneas no toma las dos si el otro género de la familia aún no tiene línea."""
        tareas = [
            self._t("CB", "RIO CAB", "Negro", 400, ["2", "4"], fechaKey=20260912, prioridadNum=1),
            self._t("DB", "RIO DAMA", "Negro", 400, ["2", "4"], fechaKey=20260910, prioridadNum=1),
        ]
        out = planificar(tareas, {}, total_dias=5)
        d0_2 = self._por_dia_linea(out, "2", 0)
        d0_4 = self._por_dia_linea(out, "4", 0)
        modelos_hoy = set(list(d0_2.keys()) + list(d0_4.keys()))
        self.assertEqual(modelos_hoy, {"RIO CAB", "RIO DAMA"}, "2=%s 4=%s" % (d0_2, d0_4))
        self.assertEqual(len(d0_2), 1, d0_2)
        self.assertEqual(len(d0_4), 1, d0_4)
        self.assertEqual(sum(d0_2.values()) + sum(d0_4.values()), 260)

    def test_lote_color_luego_genero_en_lineas_compartidas(self):
        """Dentro de la familia, Negro (cualquier género) sale antes que Blanco; CAB antes que DAMA del mismo color."""
        tareas = [
            self._t("CB", "RIO CAB", "Blanco", 130, ["4"]),
            self._t("CN", "RIO CAB", "Negro", 130, ["4"]),
            self._t("DB", "RIO DAMA", "Blanco", 130, ["4"], fechaKey=20260901, prioridadNum=1),
            self._t("DN", "RIO DAMA", "Negro", 20, ["4"], fechaKey=20260901, prioridadNum=1),
        ]
        out = planificar(tareas, {}, total_dias=10)
        orden = []
        for d in range(10):
            por = self._por_dia_linea(out, "4", d)
            for modelo in ("RIO CAB", "RIO DAMA"):
                if por.get(modelo, 0) > 0 and (not orden or orden[-1] != modelo):
                    orden.append(modelo)
        # Negro CAB llena el día 0; día 1: Negro DAMA (20) y sobrante a Blanco CAB.
        d0 = self._por_dia_linea(out, "4", 0)
        self.assertEqual(d0, {"RIO CAB": 130}, d0)
        negro_cab_d0 = sum(
            t["plan"]["4"][0] for t in out
            if t["modelo"] == "RIO CAB" and t["color"] == "Negro"
        )
        self.assertEqual(negro_cab_d0, 130)
        d1 = self._por_dia_linea(out, "4", 1)
        self.assertEqual(d1.get("RIO DAMA", 0), 20, d1)
        blanco_cab_d1 = sum(
            t["plan"]["4"][1] for t in out
            if t["modelo"] == "RIO CAB" and t["color"] == "Blanco"
        )
        self.assertEqual(blanco_cab_d1, 110, d1)

    def test_lineas_distintas_pueden_ir_en_paralelo(self):
        """RIO CAB en 2 y RIO DAMA en 4 no comparten línea: pueden correr el mismo día."""
        tareas = [
            self._t("C", "RIO CAB", "Negro", 400, ["2"]),
            self._t("D", "RIO DAMA", "Negro", 400, ["4"]),
        ]
        out = planificar(tareas, {}, total_dias=5)
        d0c = self._por_dia_linea(out, "2", 0)
        d0d = self._por_dia_linea(out, "4", 0)
        self.assertEqual(d0c.get("RIO CAB", 0), 130)
        self.assertEqual(d0d.get("RIO DAMA", 0), 130)

    def test_secuencia_genero_una_linea_ignora_fecha(self):
        """Aunque DAMA tenga mejor fecha, CAB del mismo color sale primero en la línea compartida."""
        tareas = [
            self._t("D", "MAR DAMA", "Negro", 200, ["4"], fechaKey=20260901, prioridadNum=1),
            self._t("C", "MAR CAB", "Negro", 200, ["4"], fechaKey=20260920, prioridadNum=3),
        ]
        out = planificar(tareas, {}, total_dias=5)
        d0 = self._por_dia_linea(out, "4", 0)
        self.assertEqual(d0, {"MAR CAB": 130})
        d1 = self._por_dia_linea(out, "4", 1)
        self.assertEqual(d1.get("MAR CAB", 0), 70)
        self.assertEqual(d1.get("MAR DAMA", 0), 60)

    def test_secuencia_no_no_espera_genero(self):
        """Secuencia=No en DAMA: no espera a CAB del mismo color (sale por fecha/urgente)."""
        tareas = [
            self._t("D", "MAR DAMA", "Negro", 200, ["4"], fechaKey=20260901, prioridadNum=1),
            self._t("C", "MAR CAB", "Negro", 200, ["4"], fechaKey=20260920, prioridadNum=3),
        ]
        out = planificar(tareas, {}, total_dias=5, mapa_secuencia={"MAR DAMA": "No"})
        d0 = self._por_dia_linea(out, "4", 0)
        self.assertEqual(d0, {"MAR DAMA": 130}, d0)

    def test_secuencia_no_sigue_cediendo_color(self):
        """Secuencia=No no arranca Blanco si en la familia todavía hay Negro."""
        tareas = [
            self._t("D", "RIO DAMA", "Blanco", 200, ["4"], fechaKey=20260901, prioridadNum=1),
            self._t("C", "RIO CAB", "Negro", 200, ["4"], fechaKey=20260920, prioridadNum=3),
        ]
        out = planificar(tareas, {}, total_dias=5, mapa_secuencia={"RIO DAMA": "NO"})
        d0 = self._por_dia_linea(out, "4", 0)
        self.assertEqual(d0, {"RIO CAB": 130}, d0)
        negro_d0 = sum(
            t["plan"]["4"][0] for t in out
            if t["modelo"] == "RIO CAB" and t["color"] == "Negro"
        )
        self.assertEqual(negro_d0, 130)

    def test_secuencia_no_no_toma_ambas_lineas(self):
        """Secuencia=No no reclama las dos líneas: un género por línea, MO atómica."""
        tareas = [
            self._t("CB", "RIO CAB", "Negro", 400, ["2", "4"], fechaKey=20260912, prioridadNum=1),
            self._t("DB", "RIO DAMA", "Negro", 400, ["2", "4"], fechaKey=20260910, prioridadNum=1),
        ]
        out = planificar(tareas, {}, total_dias=5, mapa_secuencia={"RIO CAB": "No"})
        d0_2 = self._por_dia_linea(out, "2", 0)
        d0_4 = self._por_dia_linea(out, "4", 0)
        modelos_hoy = set(list(d0_2.keys()) + list(d0_4.keys()))
        self.assertEqual(modelos_hoy, {"RIO CAB", "RIO DAMA"}, "2=%s 4=%s" % (d0_2, d0_4))
        self.assertEqual(len(d0_2), 1, d0_2)
        self.assertEqual(len(d0_4), 1, d0_4)
        self.assertEqual(sum(d0_2.values()) + sum(d0_4.values()), 260)

    def test_secuencia_no_mo_atomica(self):
        """Una MO de un modelo con Secuencia=No no se parte en dos líneas."""
        tareas = [
            self._t("S1", "RIO CAB", "Negro", 200, ["2", "4"], mo="M1"),
            self._t("S2", "RIO CAB", "Negro", 200, ["2", "4"], mo="M1"),
        ]
        out = planificar(tareas, {}, total_dias=5, mapa_secuencia={"RIO CAB": "No"})
        lineas_usadas = set()
        for t in out:
            for lin, arr in t["plan"].items():
                if sum(arr) > 0:
                    lineas_usadas.add(lin)
        self.assertEqual(len(lineas_usadas), 1, lineas_usadas)

    def test_secuencia_no_negro_dama_antes_que_blanco_cab(self):
        """CAB=No con Negro+Blanco y DAMA Negro en una línea: Negro CAB, Negro DAMA, luego Blanco CAB."""
        tareas = [
            self._t("CN", "RIO CAB", "Negro", 130, ["4"]),
            self._t("CB", "RIO CAB", "Blanco", 130, ["4"]),
            self._t("DN", "RIO DAMA", "Negro", 130, ["4"], fechaKey=20260901, prioridadNum=1),
        ]
        out = planificar(tareas, {}, total_dias=5, mapa_secuencia={"RIO CAB": "No"})
        d0 = self._por_dia_linea(out, "4", 0)
        self.assertEqual(d0, {"RIO CAB": 130}, d0)
        negro_cab_d0 = sum(
            t["plan"]["4"][0] for t in out
            if t["modelo"] == "RIO CAB" and t["color"] == "Negro"
        )
        self.assertEqual(negro_cab_d0, 130)
        d1 = self._por_dia_linea(out, "4", 1)
        self.assertEqual(d1, {"RIO DAMA": 130}, d1)
        d2 = self._por_dia_linea(out, "4", 2)
        self.assertEqual(d2, {"RIO CAB": 130}, d2)
        blanco_cab_d2 = sum(
            t["plan"]["4"][2] for t in out
            if t["modelo"] == "RIO CAB" and t["color"] == "Blanco"
        )
        self.assertEqual(blanco_cab_d2, 130)

    def test_acumulado_diez_semanas(self):
        vals = [100] * 10
        out = acumular_semanas(vals, 250)
        self.assertEqual(len(out), 10)
        self.assertEqual(out[0], 100)
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 300)
        self.assertTrue(all(x is None for x in out[3:]))


class TestSecuenciaFlag(unittest.TestCase):
    def test_es_secuencia_no(self):
        self.assertTrue(es_secuencia_no("No"))
        self.assertTrue(es_secuencia_no("NO"))
        self.assertTrue(es_secuencia_no(" no "))
        self.assertTrue(es_secuencia_no(True))
        self.assertFalse(es_secuencia_no(""))
        self.assertFalse(es_secuencia_no("Si"))
        self.assertFalse(es_secuencia_no("CAB"))

    def test_secuencia_no_de_modelo_normaliza_nombre(self):
        self.assertTrue(secuencia_no_de_modelo({"RIO KIDS": "No"}, "RIO KIDS"))
        self.assertTrue(secuencia_no_de_modelo({"rio kids": "NO"}, "RIO KIDS"))
        self.assertFalse(secuencia_no_de_modelo({"RIO KIDS": ""}, "RIO KIDS"))
        self.assertFalse(secuencia_no_de_modelo({}, "RIO KIDS"))


if __name__ == "__main__":
    unittest.main()
