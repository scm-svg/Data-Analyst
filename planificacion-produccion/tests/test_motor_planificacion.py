#!/usr/bin/env python3
"""Tests del motor de planificación v5.9.2 (espejo de las reglas en Codigo.gs)."""
import math
import unittest
from collections import defaultdict


BANDA_ESPECIAL = 0
BANDA_URGENTE = 1
BANDA_MINIMA = 2
BANDA_RESTO = 3
DIAS_LABORALES = 5
MAX_MODELOS_LINEA5 = 2
MAX_MODELOS_PARALELO = MAX_MODELOS_LINEA5
LOTE_RUEDA_LINEA5 = 5


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
    if es_urgente(t):
        return BANDA_URGENTE
    if t.get("esMinima"):
        return BANDA_MINIMA
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
        min_modelo_faltante = max(0, min_modelo - producido)

        if min_modelo_faltante <= 0:
            ya = min_modelo > 0
            for t in group:
                t["fase2"] = ya
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


def planificar(tareas, mapa_minimas, total_dias=10, caps_lineas=None, mapa_minimas_sku=None):
    """Motor v5.9.2: L1-4 un modelo; L5 hasta 2; SKUs de Priorizacion primero dentro del modelo."""
    if caps_lineas is None:
        caps_lineas = {"1": 130, "2": 130, "3": 130, "4": 130, "5": 40}

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

    def restante_modelo(m):
        return sum(t["restante"] for t in m["tareas"])

    def nativos_linea1_pendientes():
        for m in lista:
            if not m["esEspecial"] or restante_modelo(m) <= 0:
                continue
            for t in m["tareas"]:
                if t["restante"] > 0 and "1" in t["lineas"]:
                    return True
        return False

    def elegibles(t, overflow):
        ls = list(t["lineas"])
        if t.get("esEspecial") and overflow and "1" not in ls:
            ls.append("1")
        return [l for l in ls if l in carga]

    def runnable(t, d, lin, overflow):
        if t["restante"] <= 0 or d < dia_inicio_efectivo(t):
            return False
        if t.get("lineaFija") and t["lineaFija"] != lin:
            return False
        return lin in elegibles(t, overflow)

    def modelo_puede(m, d, lin, overflow):
        return any(runnable(t, d, lin, overflow) for t in m["tareas"])

    def cap_restante_semana(lin, d):
        week = d // DIAS_LABORALES
        end = min(total_dias, (week + 1) * DIAS_LABORALES)
        piezas = 0
        cap = caps_lineas[lin]
        for dd in range(d, end):
            piezas += max(0.0, 1.0 - carga[lin][dd]) * cap
        return piezas

    def reclamar_lineas(d, ocupante, overflow):
        if d % DIAS_LABORALES == 0:
            for lin in list(ocupante):
                ocupante[lin] = []
        for lin, mods in list(ocupante.items()):
            ocupante[lin] = [
                mod for mod in mods
                if restante_modelo(modelos[mod]) > 0 and modelo_puede(modelos[mod], d, lin, overflow)
            ]

        def lineas_libres_de(m):
            out = []
            seen = set()
            for t in m["tareas"]:
                if t["restante"] <= 0:
                    continue
                for lin in elegibles(t, overflow):
                    if lin in seen:
                        continue
                    occ = ocupante.get(lin) or []
                    if m["nombre"] in occ:
                        continue
                    if len(occ) >= max_ocupantes(lin):
                        continue
                    seen.add(lin)
                    out.append(lin)
            return out

        vivos = [m for m in lista if restante_modelo(m) > 0]
        # Pase 1: una línea por modelo (L5 puede recibir un segundo modelo)
        for m in vivos:
            if any(m["nombre"] in (ocupante.get(lin) or []) for lin in ocupante):
                continue
            libres = lineas_libres_de(m)
            if not libres:
                continue
            libres.sort(key=lambda lin: (carga[lin][d], lin))
            ocupante[libres[0]].append(m["nombre"])
        # Pase 2: líneas extra para especial/urgente si no caben en una semana
        for m in vivos:
            if m["banda"] not in (BANDA_ESPECIAL, BANDA_URGENTE):
                continue
            owned = [lin for lin, mods in ocupante.items() if m["nombre"] in mods]
            if not owned:
                continue
            cap_owned = sum(cap_restante_semana(lin, d) for lin in owned)
            if restante_modelo(m) <= cap_owned + 1e-6:
                continue
            for lin in lineas_libres_de(m):
                ocupante[lin].append(m["nombre"])
                cap_owned += cap_restante_semana(lin, d)
                if restante_modelo(m) <= cap_owned + 1e-6:
                    break
        # Pase 3: Especiales de otras líneas pasan a L1 cuando L1 ya terminó lo nativo
        if overflow and len(ocupante.get("1") or []) == 0:
            for m in vivos:
                if not m["esEspecial"]:
                    continue
                if not any(t["restante"] > 0 and (not t.get("lineaFija") or t.get("lineaFija") == "1")
                           for t in m["tareas"]):
                    continue
                if "1" in elegibles(m["tareas"][0], True) or overflow:
                    ocupante["1"].append(m["nombre"])
                    break

    def producir_lote(m, lin, d, overflow, max_lote=0):
        cap_lin = caps_lineas[lin]
        for t in m["tareas"]:
            if t["restante"] <= 0 or d < dia_inicio_efectivo(t):
                continue
            if d < DIAS_LABORALES and (d % DIAS_LABORALES) == t.get("diaNoLaborable", -1):
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
            return piezas
        return 0

    def producir_modelo_dia(m, lin, d, overflow):
        while carga[lin][d] < 0.999:
            if producir_lote(m, lin, d, overflow, 0) <= 0:
                break

    def producir_rueda_linea5(noms, d, overflow):
        lin = "5"
        i = 0
        estancado = 0
        while carga[lin][d] < 0.999 and estancado < len(noms):
            nom = noms[i % len(noms)]
            i += 1
            p = producir_lote(modelos[nom], lin, d, overflow, LOTE_RUEDA_LINEA5)
            estancado = 0 if p > 0 else estancado + 1

    ocupante = {lin: [] for lin in caps_lineas}
    for d in range(total_dias):
        overflow = not nativos_linea1_pendientes()
        reclamar_lineas(d, ocupante, overflow)
        # balancear MOs nuevos del modelo entre líneas que ya ocupa
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
        for lin, noms in ocupante.items():
            if not noms:
                continue
            if str(lin) == "5" and len(noms) >= 2:
                producir_rueda_linea5(noms, d, overflow)
                continue
            for nom in noms:
                producir_modelo_dia(modelos[nom], lin, d, overflow)
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
        for t in out:
            lunes[t["modelo"]] += t["plan"]["4"][0]
        self.assertEqual(lunes["VITA BIKER DAMA"], 88)
        self.assertEqual(lunes["BASIC LINE CROP TEE DAMA"], 0)
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
        self.assertEqual([t["modelo"] for t in orden], ["CLÁSICA CAB", "VITA DAMA", "RIO DAMA"])

    def test_tablero_ordena_por_primer_dia(self):
        filas = [
            ["2", "VITA DAMA", "Urgente", 0, 80, 80, 80, 80],
            ["2", "CLÁSICA CAB", "Especial", 60, 60, 0, 0, 0],
            ["4", "RIO DAMA", "Alta", 100, 100, 100, 100, 0],
        ]
        orden = sorted(filas, key=lambda f: (f[0], primer_dia_fila(f)))
        self.assertEqual([f[1] for f in orden if f[0] == "2"], ["CLÁSICA CAB", "VITA DAMA"])
        self.assertEqual(primer_dia_fila(filas[2]), 3)

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

    def test_urgente_gana_el_mismo_dia_sobre_minima(self):
        """Urgente (VITA) tiene la línea; la mínima no urgente espera."""
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
        self.assertEqual(lunes4["VITA BIKER DAMA"], 88)
        self.assertEqual(lunes4["RIO DAMA"], 0)


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

    def test_un_modelo_por_linea_por_dia(self):
        tareas = [
            {"sku": "R1", "modelo": "RIO DAMA", "mo": "MO-R", "cantidad": 400, "cap": 130,
             "lineas": ["4"], "color": "Negro", "prioridadNum": 1, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 20260914, "solicitadaOrig": 400},
            {"sku": "V1", "modelo": "VITA BIKER DAMA", "mo": "MO-V", "cantidad": 88, "cap": 130,
             "lineas": ["4"], "color": "Negro", "prioridadNum": 2, "esEspecial": False,
             "diaIngreso": 0, "fechaKey": 20260828, "solicitadaOrig": 88},
        ]
        out = planificar(tareas, {}, total_dias=5)
        for d in range(5):
            modelos_hoy = set()
            for t in out:
                if t["plan"]["4"][d] > 0:
                    modelos_hoy.add(t["modelo"])
            self.assertLessEqual(len(modelos_hoy), 1, "día %s mezcló %s" % (d, modelos_hoy))

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

    def test_linea5_dos_modelos_comparten_el_dia(self):
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
            self.assertEqual(len(vivos), 2, "día %s modelos %s" % (d, dict(por)))
            self.assertEqual(por["SHORT SPORT R1 DAMA"], 20)
            self.assertEqual(por["SHORT SPORT R1 CAB"], 20)

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

    def test_especial_overflow_a_linea1(self):
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
        self.assertGreater(en_l1, 0, "DOMINIC debía desbordar a línea 1 cuando MAR terminó")

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


if __name__ == "__main__":
    unittest.main()
