#!/usr/bin/env python3
"""Tests del motor de planificación v5.5 (espejo de las reglas en Codigo.gs)."""
import unittest
import math
from collections import defaultdict


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


def expandir_por_minima(tareas, mapa_minimas):
    """Fase 1 cubre cantidad minima priorizando colores core; el resto es fase 2."""
    por_modelo = defaultdict(list)
    for t in tareas:
        por_modelo[t["modelo"]].append(dict(t))

    out = []
    for modelo, group in por_modelo.items():
        min_total = mapa_minimas.get(modelo)
        if group[0].get("esEspecial") or not min_total:
            for t in group:
                t["fase2"] = False
                out.append(t)
            continue

        vol_faltante = sum(t["cantidad"] for t in group)
        vol_original = sum(t.get("solicitadaOrig", t["cantidad"]) for t in group)
        producido = vol_original - vol_faltante
        min_faltante = max(0, min_total - producido)

        if min_faltante <= 0:
            for t in group:
                t["fase2"] = True
                out.append(t)
            continue
        if min_faltante >= vol_faltante:
            for t in group:
                t["fase2"] = False
                out.append(t)
            continue

        group.sort(key=lambda t: (rango_color(t.get("color")), -t["cantidad"], t["sku"]))
        remaining = min_faltante
        for t in group:
            if remaining <= 0:
                t["fase2"] = True
                out.append(t)
            elif t["cantidad"] <= remaining:
                t["fase2"] = False
                remaining -= t["cantidad"]
                out.append(t)
            else:
                a = dict(t)
                a["cantidad"] = remaining
                a["fase2"] = False
                b = dict(t)
                b["cantidad"] = t["cantidad"] - remaining
                b["fase2"] = True
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


def asignar_atomico(tareas, total_dias=25, caps_lineas=None):
    """Cada MO se fija a UNA linea. No se parte el lote entre lineas."""
    if caps_lineas is None:
        caps_lineas = {"1": 1, "2": 1, "3": 1, "4": 1, "5": 1}
    carga = {lin: [0.0] * total_dias for lin in caps_lineas}
    linea_por_mo = {}

    def estimar_fin(t, lin, from_day):
        rest = t["cantidad"]
        for d in range(from_day, total_dias):
            avail = 1 - carga[lin][d]
            piezas = math.floor(avail * t["cap"] + 1e-9)
            rest -= piezas
            if rest <= 0:
                return d
        return total_dias + rest

    def elegir(t, d):
        mo = t["mo"]
        if mo in linea_por_mo:
            return linea_por_mo[mo]
        cands = [l for l in t["lineas"] if l in carga]
        if not cands:
            return None
        cands.sort(key=lambda lin: (estimar_fin(t, lin, d), carga[lin][d], lin))
        linea_por_mo[mo] = cands[0]
        return cands[0]

    tareas_ord = sorted(tareas, key=lambda t: (t.get("fase2", False), t.get("prioridadNum", 5), rango_color(t.get("color"))))
    for t in tareas_ord:
        t = dict(t)
        t["restante"] = t["cantidad"]
        t["plan"] = defaultdict(lambda: [0] * total_dias)
        for d in range(total_dias):
            if t["restante"] <= 0:
                break
            lin = elegir(t, d)
            if not lin:
                continue
            avail = 1 - carga[lin][d]
            piezas = min(t["restante"], math.floor(avail * t["cap"] + 1e-9))
            if piezas <= 0:
                continue
            t["plan"][lin][d] += piezas
            carga[lin][d] += piezas / t["cap"]
            t["restante"] -= piezas
        t["_linea"] = linea_por_mo.get(t["mo"])
        yield t


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
        self.assertEqual(rango_color("Blanco Roto Extra"), 1)  # startswith blanco
        self.assertEqual(rango_color("Rojo"), 50)
        self.assertEqual(rango_color("Azul Rey"), 50)
        self.assertEqual(rango_color("Azul Lavanda"), 50)

    def test_prioridad_con_espacios(self):
        self.assertEqual(prioridad_num("Urgente "), 1)
        self.assertEqual(prioridad_num("URGENT"), 5)  # no es el token en español
        self.assertEqual(prioridad_num("Alta"), 2)
        self.assertEqual(prioridad_num(""), 5)


class TestCantidadMinima(unittest.TestCase):
    def _t(self, sku, color, cant, modelo="RIO DAMA"):
        return {
            "sku": sku, "color": color, "cantidad": cant, "modelo": modelo,
            "solicitadaOrig": cant, "esEspecial": False, "mo": sku, "cap": 130,
            "lineas": ["2", "4"], "prioridadNum": 1,
        }

    def test_fase1_prioriza_colores_core(self):
        tareas = [
            self._t("R", "Rojo", 80),
            self._t("N", "Negro", 80),
            self._t("B", "Blanco", 80),
            self._t("A", "Azul Marino", 80),
        ]
        out = expandir_por_minima(tareas, {"RIO DAMA": 200})
        fase1 = [t for t in out if not t["fase2"]]
        fase2 = [t for t in out if t["fase2"]]
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
        self.assertFalse(out[0]["fase2"])

    def test_minima_ya_cubierta_va_a_fase2(self):
        t = self._t("N", "Negro", 10)
        t["solicitadaOrig"] = 100  # ya se produjeron 90
        out = expandir_por_minima([t], {"RIO DAMA": 50})
        self.assertTrue(out[0]["fase2"])


class TestMOAtomica(unittest.TestCase):
    def test_una_mo_una_linea(self):
        tareas = [
            {"sku": "A", "mo": "MO1", "cantidad": 200, "cap": 130, "lineas": ["2", "4"],
             "color": "Negro", "prioridadNum": 1, "fase2": False},
            {"sku": "B", "mo": "MO2", "cantidad": 200, "cap": 130, "lineas": ["2", "4"],
             "color": "Rojo", "prioridadNum": 2, "fase2": False},
        ]
        results = list(asignar_atomico(tareas))
        for r in results:
            lineas_usadas = [lin for lin, arr in r["plan"].items() if sum(arr) > 0]
            self.assertEqual(len(lineas_usadas), 1, msg=r["mo"] + " se partio: " + str(lineas_usadas))
            self.assertEqual(lineas_usadas[0], r["_linea"])

    def test_fase1_y_fase2_misma_linea(self):
        tareas = [
            {"sku": "A", "mo": "MO9", "cantidad": 50, "cap": 130, "lineas": ["2", "4"],
             "color": "Negro", "prioridadNum": 1, "fase2": False},
            {"sku": "A", "mo": "MO9", "cantidad": 80, "cap": 130, "lineas": ["2", "4"],
             "color": "Negro", "prioridadNum": 1, "fase2": True},
        ]
        results = list(asignar_atomico(tareas))
        lineas = {r["_linea"] for r in results}
        self.assertEqual(len(lineas), 1)


class TestAcumulado(unittest.TestCase):
    def test_acumulado_plateau(self):
        self.assertEqual(acumular_semanas([901, 704, 0, 0, 0]), [901, 1605, 1605, 1605, 1605])

    def test_vacio(self):
        self.assertEqual(acumular_semanas([0, 0, 0]), [None, None, None])


if __name__ == "__main__":
    unittest.main()
