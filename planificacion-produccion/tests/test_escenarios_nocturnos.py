#!/usr/bin/env python3
"""Tests del motor de turnos nocturnos y del informe A–D."""
import os
import sys
import unittest
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from escenarios_nocturnos import (  # noqa: E402
    BONO_USD,
    CORTE_ALMACEN,
    EventoLinea,
    ModeloInfo,
    PERSONAS,
    add_business_days,
    cap_nocturna,
    costo_bono,
    es_cobro,
    es_lote_nuevo,
    fechas_nocturno,
    kpis_escenario,
    personas_total,
    simular_nocturnos,
)


NUEVO_XLSX = "/home/ubuntu/.cursor/projects/workspace/uploads/Planificacion_Produccion_LOTE_NUEVO_1678.xlsx"
ACTUAL_XLSX = "/home/ubuntu/.cursor/projects/workspace/uploads/Planificacion_Produccion_ACTUAL_15df.xlsx"


def _plan(eventos, modelos):
    return {"modelos": modelos, "eventos": eventos, "especiales": {}, "proy": {}, "alm": {}}


class FechasYCosto(unittest.TestCase):
    def test_cobro_dia_15_y_ultimo(self):
        self.assertTrue(es_cobro(date(2026, 9, 30)))
        self.assertTrue(es_cobro(date(2026, 10, 15)))
        self.assertTrue(es_cobro(date(2026, 10, 31)))
        self.assertFalse(es_cobro(date(2026, 9, 29)))
        self.assertFalse(es_cobro(date(2026, 10, 2)))
        self.assertFalse(es_cobro(date(2026, 10, 14)))

    def test_semana_1_salta_30_sep(self):
        a = fechas_nocturno(1)
        self.assertEqual(a, [date(2026, 9, 29), date(2026, 10, 2)])
        b = fechas_nocturno(2)
        self.assertEqual(b[0], date(2026, 9, 29))
        self.assertNotIn(date(2026, 9, 30), b)
        self.assertNotIn(date(2026, 10, 15), fechas_nocturno(4))
        self.assertEqual(len(fechas_nocturno(4)), 11)

    def test_costo_22_personas(self):
        self.assertEqual(personas_total(), 22)
        self.assertEqual(PERSONAS["1"], 4)
        self.assertEqual(PERSONAS["4"], 5)
        self.assertEqual(costo_bono(1), 22 * BONO_USD)
        self.assertEqual(costo_bono(2), 660.0)
        self.assertEqual(costo_bono(11), 3630.0)

    def test_cap_nocturna_mitad_entera(self):
        self.assertEqual(cap_nocturna(101), 50)
        self.assertEqual(cap_nocturna(124), 62)
        self.assertEqual(cap_nocturna(40), 20)

    def test_almacen_4_habiles(self):
        self.assertEqual(add_business_days(date(2026, 11, 10)), date(2026, 11, 16))
        self.assertEqual(add_business_days(date(2026, 11, 12)), date(2026, 11, 18))

    def test_lote_nuevo_nombre(self):
        self.assertTrue(es_lote_nuevo("MAR LOTE NUEVO CAB"))
        self.assertFalse(es_lote_nuevo("MAR LOTE 1 CAB"))
        self.assertFalse(es_lote_nuevo("RIO KIDS"))


class MotorSintetico(unittest.TestCase):
    def test_n0_identidad_y_l1_sigue_l2(self):
        seq = 0
        eventos = []
        # L2: 80 el martes 29, 80 el miércoles 30, 80 el viernes 2 (modelo A luego B)
        for d, modelo, q in [
            (date(2026, 9, 29), "RIO DAMA", 80.0),
            (date(2026, 9, 30), "RIO DAMA", 20.0),
            (date(2026, 9, 30), "RIO KIDS", 60.0),
            (date(2026, 10, 2), "RIO KIDS", 80.0),
        ]:
            eventos.append(EventoLinea(d, "2", modelo, q, False, seq))
            seq += 1
        modelos = {
            "RIO DAMA": ModeloInfo("RIO DAMA", faltante=100, cap=100, lineas="2"),
            "RIO KIDS": ModeloInfo("RIO KIDS", faltante=140, cap=100, lineas="2", lote_nuevo=False),
        }
        plan = _plan(eventos, modelos)
        s0 = simular_nocturnos(plan, 0)
        by0 = {r.modelo: r for r in s0["resultados"]}
        self.assertEqual(by0["RIO DAMA"].termino_esc, date(2026, 9, 30))
        self.assertEqual(by0["RIO KIDS"].termino_esc, date(2026, 10, 2))
        self.assertEqual(s0["pzas_nocturno"], 0)

        s1 = simular_nocturnos(plan, 1)
        by1 = {r.modelo: r for r in s1["resultados"]}
        # 29/09 noche L2 50 + L1 50 sobre cola L2; 30/09 cobro sin noche; 02/10 noche otra vez.
        self.assertEqual(s1["n_noches"], 2)
        self.assertGreater(s1["pzas_nocturno"], 0)
        self.assertGreater(s1["pzas_por_linea"].get("1", 0), 0)
        self.assertGreater(s1["pzas_por_linea"].get("2", 0), 0)
        self.assertLessEqual(by1["RIO KIDS"].termino_esc, by0["RIO KIDS"].termino_esc)
        self.assertTrue((by1["RIO KIDS"].dias_ganados or 0) >= 0)

    def test_especial_no_entra_a_la_cola(self):
        eventos = [
            EventoLinea(date(2026, 9, 29), "2", "Clásica Cab (Especial)", 80.0, True, 0),
            EventoLinea(date(2026, 9, 29), "2", "RIO DAMA", 50.0, False, 1),
            EventoLinea(date(2026, 10, 2), "2", "RIO DAMA", 50.0, False, 2),
        ]
        modelos = {"RIO DAMA": ModeloInfo("RIO DAMA", faltante=100, cap=100, lineas="2")}
        s1 = simular_nocturnos(_plan(eventos, modelos), 1)
        self.assertGreater(s1["pzas_nocturno"], 0)
        self.assertTrue(all(r.modelo != "Clásica Cab (Especial)" for r in s1["resultados"]))

    def test_listas_salen_por_calendario(self):
        eventos = [
            EventoLinea(date(2026, 10, 2), "3", "MAR LOTE NUEVO CAB", 50.0, False, 1),
            EventoLinea(date(2026, 9, 29), "3", "MAR LOTE 1 KIDS", 50.0, False, 0),
        ]
        modelos = {
            "MAR LOTE NUEVO CAB": ModeloInfo("MAR LOTE NUEVO CAB", faltante=50, cap=100, lote_nuevo=True),
            "MAR LOTE 1 KIDS": ModeloInfo("MAR LOTE 1 KIDS", faltante=50, cap=100),
        }
        rows = simular_nocturnos(_plan(eventos, modelos), 0)["resultados"]
        fechas = [r.termino_esc for r in rows]
        self.assertEqual(fechas, sorted(fechas, key=lambda d: d or date.max))


@unittest.skipUnless(os.path.isfile(NUEVO_XLSX), "Excel lote nuevo no disponible")
class IntegracionExcel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from escenarios_nocturnos import cargar_plan

        cls.nuevo = cargar_plan(NUEVO_XLSX)
        cls.actual = cargar_plan(ACTUAL_XLSX) if os.path.isfile(ACTUAL_XLSX) else None
        cls.sims = {n: simular_nocturnos(cls.nuevo, n) for n in range(5)}

    def test_n0_identidad_tablero(self):
        s0 = self.sims[0]
        k = kpis_escenario(s0)
        self.assertEqual(k["pzas_nocturno"], 0)
        self.assertEqual(k["extra_alm16"], 0)
        self.assertEqual(k["modelos_adelantados"], 0)
        self.assertEqual(k["cubre_almacen_base"], k["cubre_almacen_esc"])

    def test_lotes_nuevos_y_corte_almacen(self):
        lotes = [m for m in self.nuevo["modelos"].values() if m.lote_nuevo]
        self.assertEqual(len(lotes), 6)
        self.assertGreater(sum(m.faltante for m in lotes), 8000)
        for m in lotes:
            self.assertTrue(m.entrada_plan is None or m.entrada_plan > CORTE_ALMACEN)

    def test_escenarios_monotonos(self):
        prev_p = 0
        prev_c = 0
        for n in range(1, 5):
            k = kpis_escenario(self.sims[n])
            self.assertGreaterEqual(k["pzas_nocturno"], prev_p)
            self.assertGreaterEqual(k["costo_usd"], prev_c)
            self.assertGreaterEqual(k["extra_alm16"], prev_p - 1)
            prev_p = k["pzas_nocturno"]
            prev_c = k["costo_usd"]
        kd = kpis_escenario(self.sims[4])
        self.assertEqual(kd["n_noches"], 11)
        self.assertEqual(kd["costo_usd"], 3630.0)
        self.assertGreater(kd["pzas_por_linea"].get("1", 0), 0)

    def test_listas_orden_salida(self):
        rows = self.sims[4]["resultados"]
        keys = [(r.termino_esc or date.max, r.modelo) for r in rows]
        self.assertEqual(keys, sorted(keys))
        from escenarios_nocturnos import modelos_a_dict

        dicts = modelos_a_dict(rows)
        iso = [d["termino_esc_iso"] for d in dicts]
        self.assertEqual(iso, sorted(iso))
        self.assertLess(iso[0], "2026-10-01")


if __name__ == "__main__":
    unittest.main()
