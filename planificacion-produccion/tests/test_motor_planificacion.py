#!/usr/bin/env python3
"""Tests del motor de planificación v5.6 (espejo de las reglas en Codigo.gs)."""
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
    if t.get("esMinima"):
        return 0
    return t.get("diaIngreso") or 0


def expandir_por_minima(tareas, mapa_minimas):
    """Fase 1 cubre cantidad minima priorizando colores core; marca esMinima."""
    por_modelo = defaultdict(list)
    orden = []
    for t in tareas:
        if t["modelo"] not in por_modelo:
            orden.append(t["modelo"])
        por_modelo[t["modelo"]].append(dict(t))

    out = []
    for modelo in orden:
        group = por_modelo[modelo]
        min_total = minima_de_modelo(mapa_minimas, modelo)
        if group[0].get("esEspecial") or not min_total:
            for t in group:
                t["fase2"] = False
                t["esMinima"] = False
                out.append(t)
            continue

        vol_faltante = sum(t["cantidad"] for t in group)
        vol_original = sum(t.get("solicitadaOrig", t["cantidad"]) for t in group)
        producido = vol_original - vol_faltante
        min_faltante = max(0, min_total - producido)

        if min_faltante <= 0:
            for t in group:
                t["fase2"] = True
                t["esMinima"] = False
                out.append(t)
            continue
        if min_faltante >= vol_faltante:
            for t in group:
                t["fase2"] = False
                t["esMinima"] = True
                out.append(t)
            continue

        group.sort(key=lambda t: (rango_color(t.get("color")), -t["cantidad"], t["sku"]))
        remaining = min_faltante
        for t in group:
            if remaining <= 0:
                t["fase2"] = True
                t["esMinima"] = False
                out.append(t)
            elif t["cantidad"] <= remaining:
                t["fase2"] = False
                t["esMinima"] = True
                remaining -= t["cantidad"]
                out.append(t)
            else:
                a = dict(t)
                a["cantidad"] = remaining
                a["fase2"] = False
                a["esMinima"] = True
                b = dict(t)
                b["cantidad"] = t["cantidad"] - remaining
                b["fase2"] = True
                b["esMinima"] = False
                out.append(a)
                out.append(b)
                remaining = 0
    return out


def acumular_semanas(por_semana):
    acum, out = 0, []
    for v in por_semana:
        acum += v
        out.append(None if acum == 0 else acum)
    return out


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

    def test_minima_gana_lunes_linea4_aunque_core_diga_martes(self):
        """Réplica del Excel: core colors de RIO arrancan martes; VITA es Urgente el 28/08.
        La banda mínima debe tomar Linea 4 el lunes (130) y VITA espera."""
        tareas = [
            {"sku": "ESP1", "modelo": "MAR CAB (Especial)", "color": "Azul", "cantidad": 130,
             "solicitadaOrig": 130, "esEspecial": True, "mo": "E1", "cap": 130,
             "lineas": ["1", "2"], "prioridadNum": 0, "diaIngreso": 0, "fechaKey": 20260904},
            {"sku": "ESP2", "modelo": "MAR DAMA (Especial)", "color": "Azul", "cantidad": 130,
             "solicitadaOrig": 130, "esEspecial": True, "mo": "E2", "cap": 130,
             "lineas": ["1", "2"], "prioridadNum": 0, "diaIngreso": 0, "fechaKey": 20260904},
            {"sku": "N", "modelo": "RIO DAMA", "color": "Negro", "cantidad": 165,
             "solicitadaOrig": 165, "esEspecial": False, "mo": "R-N", "cap": 130,
             "lineas": ["2", "4"], "prioridadNum": 2, "diaIngreso": 1, "fechaKey": 20260904},
            {"sku": "B", "modelo": "RIO DAMA", "color": "Blanco", "cantidad": 165,
             "solicitadaOrig": 165, "esEspecial": False, "mo": "R-B", "cap": 130,
             "lineas": ["2", "4"], "prioridadNum": 2, "diaIngreso": 1, "fechaKey": 20260904},
            {"sku": "A", "modelo": "RIO DAMA", "color": "Azul Marino", "cantidad": 165,
             "solicitadaOrig": 165, "esEspecial": False, "mo": "R-A", "cap": 130,
             "lineas": ["2", "4"], "prioridadNum": 2, "diaIngreso": 1, "fechaKey": 20260904},
            {"sku": "RO", "modelo": "RIO DAMA", "color": "Rojo", "cantidad": 130,
             "solicitadaOrig": 130, "esEspecial": False, "mo": "R-RO", "cap": 130,
             "lineas": ["2", "4"], "prioridadNum": 2, "diaIngreso": 0, "fechaKey": 20260904},
            {"sku": "V", "modelo": "VITA BIKER DAMA", "color": "Negro", "cantidad": 88,
             "solicitadaOrig": 88, "esEspecial": False, "mo": "V1", "cap": 130,
             "lineas": ["4"], "prioridadNum": 1, "diaIngreso": 0, "fechaKey": 20260828},
        ]
        out = planificar(tareas, {"RIO DAMA": 400}, total_dias=5)
        lunes4 = defaultdict(int)
        for t in out:
            lunes4[t["modelo"]] += t["plan"]["4"][0]
        self.assertGreater(lunes4["RIO DAMA"], 0, "RIO DAMA mínima debe producir el lunes en línea 4")
        self.assertEqual(lunes4["RIO DAMA"], 130)
        self.assertEqual(lunes4["VITA BIKER DAMA"], 0, "VITA no puede comerse el lunes de la línea 4")
        self.assertEqual(sum(t["planificada"] for t in out if t.get("esMinima")), 400)

        por_modelo_linea = defaultdict(lambda: [0] * 5)
        for t in out:
            for lin, arr in t["plan"].items():
                for d, q in enumerate(arr):
                    por_modelo_linea[(lin, t["modelo"])][d] += q
        filas = []
        for (lin, modelo), dias in por_modelo_linea.items():
            if sum(dias) <= 0:
                continue
            filas.append([lin, modelo] + dias)
        filas.sort(key=lambda f: (f[0], next((i for i, q in enumerate(f[2:]) if q > 0), 99)))
        line2 = [f[1] for f in filas if f[0] == "2"]
        self.assertTrue(line2, msg="Linea 2 vacía")
        self.assertTrue(line2[0].endswith("(Especial)"), msg="Especial debe ir primero en línea 2: %s" % line2)


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
    def test_acumulado_plateau(self):
        self.assertEqual(acumular_semanas([901, 704, 0, 0, 0]), [901, 1605, 1605, 1605, 1605])

    def test_vacio(self):
        self.assertEqual(acumular_semanas([0, 0, 0]), [None, None, None])


if __name__ == "__main__":
    unittest.main()
