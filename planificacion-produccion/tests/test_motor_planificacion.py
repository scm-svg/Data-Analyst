#!/usr/bin/env python3
"""Tests del motor de planificación v5.8.1 (espejo de las reglas en Codigo.gs)."""
import math
import unittest
from collections import defaultdict


BANDA_ESPECIAL = 0
BANDA_MINIMA = 1
BANDA_RESTO = 2
MAX_MODELOS_PARALELO = 2


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


def banda_de(t):
    if t.get("esEspecial"):
        return BANDA_ESPECIAL
    if t.get("esMinima"):
        return BANDA_MINIMA
    return BANDA_RESTO


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


def expandir_por_minima(tareas, mapa_minimas, mapa_minimas_sku=None):
    """SKU mins primero; el resto del piso del modelo con colores core."""
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
        remaining_sku = {}
        seen = set()
        for t in group:
            k = clave_sku(t["sku"])
            if k in seen:
                continue
            seen.add(k)
            remaining_sku[k] = min_de_sku(mapa_minimas_sku, t["sku"])

        prod_por_sku = defaultdict(float)
        vol_faltante = 0
        vol_original = 0
        for t in group:
            vol_faltante += t["cantidad"]
            orig = t.get("solicitadaOrig", t["cantidad"])
            vol_original += orig
            prod_por_sku[clave_sku(t["sku"])] += max(0, orig - t["cantidad"])
        for k in list(remaining_sku):
            if remaining_sku[k] > 0:
                remaining_sku[k] = max(0, remaining_sku[k] - prod_por_sku[k])

        has_sku_min = any(v > 0 for v in remaining_sku.values())
        sum_sku_rest = sum(remaining_sku.values())
        producido = max(0, vol_original - vol_faltante)
        min_modelo_faltante = max(0, min_modelo - producido)
        min_modelo_resto = max(0, min_modelo_faltante - sum_sku_rest)

        if not has_sku_min and min_modelo_faltante <= 0:
            ya = min_modelo > 0
            for t in group:
                t["fase2"] = ya
                t["esMinima"] = False
                out.append(t)
            continue
        if not has_sku_min and min_modelo_faltante >= vol_faltante:
            for t in group:
                t["fase2"] = False
                t["esMinima"] = True
                out.append(t)
            continue

        group.sort(key=lambda t: (
            0 if remaining_sku.get(clave_sku(t["sku"]), 0) > 0 else 1,
            rango_color(t.get("color")),
            -t["cantidad"],
            t["sku"],
        ))
        resto_modelo = min_modelo_resto
        leftovers = []
        for t in group:
            k = clave_sku(t["sku"])
            left = t["cantidad"]
            need = remaining_sku.get(k, 0)
            if need > 0 and left > 0:
                take = min(left, need)
                a = dict(t)
                a["cantidad"] = take
                a["fase2"] = False
                a["esMinima"] = True
                out.append(a)
                remaining_sku[k] -= take
                left -= take
            if left > 0:
                leftovers.append((t, left))
        leftovers.sort(key=lambda it: (rango_color(it[0].get("color")), -it[1], it[0]["sku"]))
        for t, left in leftovers:
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


def planificar(tareas, mapa_minimas, total_dias=10, caps_lineas=None):
    """Espejo compacto: 3 bandas, MO atómica, mínima ignora día de inicio."""
    if caps_lineas is None:
        caps_lineas = {"1": 130, "2": 130, "3": 130, "4": 130, "5": 40}

    tareas = expandir_por_minima(tareas, mapa_minimas)
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

    tareas.sort(key=lambda t: (
        banda_de(t),
        t["fechaKey"] if banda_de(t) == BANDA_RESTO else 0,
        t["prioridadNum"] if banda_de(t) == BANDA_RESTO else 0,
        t["colorRank"],
        -t["cantidad"],
        t["modelo"],
        t["sku"],
    ))

    carga = {lin: [0.0] * total_dias for lin in caps_lineas}
    linea_por_mo = {}

    grupos = []
    idx_grupo = {}
    for t in tareas:
        banda = banda_de(t)
        clave = "B%s|%s" % (banda, "ESP" if banda == BANDA_ESPECIAL else ("MIN" if banda == BANDA_MINIMA else str(t["fechaKey"])))
        if clave not in idx_grupo:
            idx_grupo[clave] = len(grupos)
            grupos.append({"clave": clave, "banda": banda, "modelos": [], "idx": {}})
        g = grupos[idx_grupo[clave]]
        if t["modelo"] not in g["idx"]:
            g["idx"][t["modelo"]] = len(g["modelos"])
            g["modelos"].append({"nombre": t["modelo"], "tareas": []})
        g["modelos"][g["idx"][t["modelo"]]]["tareas"].append(t)

    grupos.sort(key=lambda g: (g["banda"], g["clave"]))

    def estimar_fin(t, lin, from_day):
        rest = t["restante"]
        cap_lin = caps_lineas[lin]
        for d in range(from_day, total_dias):
            if d < dia_inicio_efectivo(t):
                continue
            avail = max(0.0, 1.0 - carga[lin][d])
            piezas = math.floor(avail * cap_lin + 1e-9)
            rest -= piezas
            if rest <= 0:
                return d
        return total_dias + max(0, rest)

    def fijar_linea(t, d):
        mo = t.get("mo") or t["sku"]
        if mo in linea_por_mo:
            t["lineaFija"] = linea_por_mo[mo]
            return linea_por_mo[mo]
        cands = [l for l in t["lineas"] if l in carga]
        if not cands:
            return None
        cands.sort(key=lambda lin: (estimar_fin(t, lin, d), carga[lin][d], lin))
        linea_por_mo[mo] = cands[0]
        t["lineaFija"] = cands[0]
        return cands[0]

    for g in grupos:
        modelos = g["modelos"]
        for c in range(0, len(modelos), MAX_MODELOS_PARALELO):
            chunk = modelos[c:c + MAX_MODELOS_PARALELO]
            for d in range(total_dias):
                activos = [m for m in chunk if sum(t["restante"] for t in m["tareas"]) > 0]
                if not activos:
                    break
                for m in activos:
                    for t in m["tareas"]:
                        if t["restante"] <= 0 or d < dia_inicio_efectivo(t):
                            continue
                        lin = fijar_linea(t, d)
                        if not lin:
                            continue
                        cap_lin = caps_lineas[lin]
                        avail = 1.0 - carga[lin][d]
                        if avail <= 0.001:
                            continue
                        piezas = min(t["restante"], math.floor(avail * cap_lin + 1e-9))
                        if piezas <= 0:
                            continue
                        t["plan"][lin][d] += piezas
                        carga[lin][d] += piezas / cap_lin
                        t["restante"] -= piezas
                        t["planificada"] += piezas
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
        """Priorizacion - SKUs fuerza Rojo aunque no sea color núcleo."""
        tareas = [
            self._t("R", "Rojo", 80),
            self._t("N", "Negro", 80),
            self._t("B", "Blanco", 80),
            self._t("A", "Azul Marino", 80),
        ]
        out = expandir_por_minima(tareas, {"RIO DAMA": 200}, {"R": 50})
        fase1 = [t for t in out if t["esMinima"]]
        self.assertEqual(sum(t["cantidad"] for t in fase1), 200)
        rojo = [t for t in fase1 if t["color"] == "Rojo"]
        self.assertEqual(sum(t["cantidad"] for t in rojo), 50)
        self.assertIn("Negro", {t["color"] for t in fase1})

    def test_sku_minima_sin_cupo_de_modelo(self):
        tareas = [
            self._t("R", "Rojo", 80),
            self._t("N", "Negro", 80),
        ]
        out = expandir_por_minima(tareas, {}, {"R": 40})
        self.assertEqual(sum(t["cantidad"] for t in out if t["esMinima"] and t["sku"] == "R"), 40)
        self.assertFalse(any(t["esMinima"] and t["sku"] == "N" for t in out))


    def test_match_case_insensitive(self):
        self.assertEqual(minima_de_modelo({"RIO DAMA": 400}, "rio dama"), 400)
        self.assertEqual(minima_de_modelo({"RIO DAMA": 400}, "RIO DAMA"), 400)


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
        self.assertEqual(lunes4["RIO DAMA"], 0, "RIO DAMA no puede arrancar antes del día de inicio")
        self.assertEqual(lunes4["VITA BIKER DAMA"], 88)
        self.assertGreater(miercoles4["RIO DAMA"], 0, "RIO DAMA mínima debe salir el miércoles (día de inicio)")
        self.assertEqual(sum(t["planificada"] for t in out if t.get("esMinima")), 400)

    def test_minima_gana_el_mismo_dia_si_ya_puede_iniciar(self):
        """Si mínima y VITA pueden iniciar el mismo día, mínima toma la capacidad primero."""
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
