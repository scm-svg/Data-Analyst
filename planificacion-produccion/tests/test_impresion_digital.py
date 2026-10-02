#!/usr/bin/env python3
"""Lista fija de Impresión Digital (prioridad, L1-4 vs L5, PD, checks)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from impresion_digital import (
    Numberish,
    agrupar_impresion,
    clave_check,
    es_pd,
    escribir_html,
    extraer_desde_xlsx,
    grupo_linea,
    mo_cerrada,
    ordenar_skus,
    parsear_lineas,
    payload_para_html,
    prioridad_num,
    resumen,
)

XLSX43 = Path("/home/ubuntu/.cursor/projects/workspace/uploads/Planificacion_Produccion__43__9374.xlsx")
XLSX44 = Path("/home/ubuntu/.cursor/projects/workspace/uploads/Planificacion_Produccion__44__5ea0.xlsx")
XLSX = XLSX44 if XLSX44.exists() else XLSX43


def sku(**kw):
    row = {
        "sku": "SKU1",
        "modelo": "RIO KIDS",
        "detalle": "RIO - KIDS - Negro - S",
        "mo": "01000",
        "color": "Negro",
        "talla": "S",
        "linea": "2",
        "solicitada": 10,
        "producida": 0,
        "faltante": 10,
        "prioridad": "Urgente",
        "fechaSalida": "29/09/2026",
        "moStatus": "Confirmada",
        "especial": False,
        "tipo": "Producción",
    }
    row.update(kw)
    return row


class TestReglasId(unittest.TestCase):
    def test_parsear_lineas_float_excel(self):
        self.assertEqual(parsear_lineas(1.0), ["1"])
        self.assertEqual(parsear_lineas("3, 4"), ["3", "4"])
        self.assertEqual(parsear_lineas("5"), ["5"])

    def test_es_pd(self):
        self.assertTrue(es_pd("PD-500"))
        self.assertTrue(es_pd("pd-281"))
        self.assertFalse(es_pd("01310"))
        self.assertFalse(es_pd("00393"))

    def test_grupo_linea(self):
        self.assertEqual(grupo_linea(["5"]), "linea5")
        self.assertEqual(grupo_linea(["3", "4"]), "lineas14")
        self.assertEqual(grupo_linea(["2", "5"]), "linea5")
        self.assertEqual(grupo_linea([]), "lineas14")

    def test_prioridad_orden(self):
        self.assertLess(prioridad_num("Especial"), prioridad_num("Urgente"))
        self.assertLess(prioridad_num("Urgente "), prioridad_num("Alta"))
        self.assertLess(prioridad_num("Alta"), prioridad_num("Media"))
        self.assertLess(prioridad_num("Media"), prioridad_num("Baja"))

    def test_clave_check_sin_semana(self):
        self.assertEqual(clave_check("00393", "VARBADA12TXS"), "M|00393|VARBADA12TXS")
        self.assertEqual(clave_check("", "X"), "S|X")

    def test_skus_negro_antes_que_lila(self):
        filas = [
            {"sku": "LILA", "color": "Lila", "talla": "S", "faltante": 8},
            {"sku": "NEG", "color": "Negro", "talla": "M", "faltante": 4},
            {"sku": "BLA", "color": "Blanco", "talla": "S", "faltante": 4},
        ]
        orden = [s["sku"] for s in ordenar_skus(filas)]
        self.assertEqual(orden, ["NEG", "BLA", "LILA"])

    def test_agrupa_prioridad_y_lineas(self):
        backlog = [
            sku(modelo="LITE PANT DAMA", linea="5", prioridad="Baja", faltante=40, sku="L1", mo="PD-1"),
            sku(modelo="SHORT PLAYA CAB", linea="5", prioridad="Urgente", faltante=20, sku="S1", mo="02000"),
            sku(modelo="RIO KIDS", linea="2", prioridad="Urgente", faltante=50, sku="R1", mo="01000"),
            sku(modelo="Clásica DAMA (Especial)", linea="2, 3", prioridad="", especial=True, tipo="Especial",
                faltante=15, sku="C1", mo="PD-500", color="Blanco"),
            sku(modelo="BASIC LINE", linea="3, 4", prioridad="Baja", faltante=10, sku="B1", mo="01310"),
        ]
        lista = agrupar_impresion(backlog)
        l5 = [m["modelo"] for m in lista["linea5"]]
        l14 = [m["modelo"] for m in lista["lineas14"]]
        self.assertEqual(l5, ["SHORT PLAYA CAB", "LITE PANT DAMA"])
        self.assertEqual(l14[0], "Clásica DAMA (Especial)")
        self.assertEqual(l14[1], "RIO KIDS")
        self.assertEqual(l14[-1], "BASIC LINE")
        lite = lista["linea5"][-1]
        self.assertEqual(lite["nPd"], 1)
        self.assertTrue(lite["skus"][0]["pd"])
        clas = lista["lineas14"][0]
        self.assertEqual(clas["prioridad"], "Especial")
        self.assertTrue(clas["especial"])

    def test_faltante_cero_sigue_y_cerrada_sale(self):
        self.assertTrue(mo_cerrada("Hecho"))
        self.assertTrue(mo_cerrada("CANCELADA"))
        self.assertTrue(mo_cerrada("Cerrada"))
        self.assertFalse(mo_cerrada("Confirmada"))
        self.assertFalse(mo_cerrada("En Progreso"))
        backlog = [
            sku(modelo="RIO KIDS", sku="RK-OK", mo="01000", faltante=12, solicitada=12, producida=0),
            sku(modelo="RIO KIDS", sku="RK-0", mo="01001", faltante=0, solicitada=20, producida=20,
                moStatus="Confirmada"),
            sku(modelo="RIO KIDS", sku="RK-HECHO", mo="01002", faltante=0, solicitada=8, producida=8,
                moStatus="Hecho"),
            sku(modelo="RIO KIDS", sku="RK-CANC", mo="01003", faltante=5, solicitada=5, producida=0,
                moStatus="Cancelada"),
        ]
        lista = agrupar_impresion(backlog)
        skus = {s["sku"]: s for m in lista["modelos"] for s in m["skus"]}
        self.assertIn("RK-OK", skus)
        self.assertIn("RK-0", skus)
        self.assertEqual(skus["RK-0"]["solicitada"], 20)
        self.assertEqual(skus["RK-0"]["producida"], 20)
        self.assertEqual(skus["RK-0"]["faltante"], 0)
        self.assertNotIn("RK-HECHO", skus)
        self.assertNotIn("RK-CANC", skus)
        rio = [m for m in lista["lineas14"] if m["modelo"] == "RIO KIDS"][0]
        self.assertEqual(rio["solicitada"], 32)
        self.assertEqual(rio["producida"], 20)
        self.assertEqual(rio["faltante"], 12)

    def test_html_plantilla_y_checks(self):
        backlog = [
            sku(modelo="SHORT PLAYA CAB", linea="5", prioridad="Urgente", sku="SP1", mo="02000"),
            sku(modelo="RIO KIDS", linea="2", prioridad="Urgente", sku="RK1", mo="PD-9"),
        ]
        extraido = {
            "backlog": backlog,
            "checks": {clave_check("02000", "SP1"): 1},
            "lista": agrupar_impresion(backlog),
            "version": "test",
        }
        payload = payload_para_html(extraido)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "id.html"
            escribir_html(payload, dest, ROOT / "impresion_digital_template.html")
            html = dest.read_text(encoding="utf-8")
        self.assertIn("Líneas 1–4", html)
        self.assertIn("Línea 5", html)
        self.assertIn("SHORT PLAYA CAB", html)
        self.assertIn("RIO KIDS", html)
        self.assertIn("PD-9", html)
        self.assertIn("imp-grupo-l5", html)
        self.assertIn("imp-grupo-l14", html)
        self.assertIn("b-pd", html)
        self.assertNotIn("imp-mod-pd", html)
        self.assertNotIn("<th>Prioridad</th>", html)
        self.assertNotIn("<th>Línea</th>", html)
        self.assertNotIn("<th>Variantes</th>", html)
        self.assertNotIn("<th>Fecha</th>", html)
        self.assertNotIn('id="f-prio"', html)
        self.assertNotIn("<label>Prioridad</label>", html)
        self.assertIn("<th>MOs</th>", html)
        self.assertIn("<th>Solicitada</th>", html)
        self.assertIn("<th>Producida</th>", html)
        self.assertIn("<th>Faltante</th>", html)
        self.assertNotIn("__DASH_JSON__", html)
        data = json.loads(html.split('id="dash-data">')[1].split("</script>")[0])
        self.assertEqual(data["lista"]["linea5"][0]["modelo"], "SHORT PLAYA CAB")
        self.assertTrue(data["checks"]["M|02000|SP1"])


@unittest.skipUnless(XLSX43.exists(), "Falta el Excel 43 de Planificación")
class TestExcelReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.extraido = extraer_desde_xlsx(str(XLSX43))
        cls.lista = cls.extraido["lista"]
        cls.kpis = resumen(cls.lista)

    def test_no_vacio_y_partido_por_linea(self):
        self.assertGreaterEqual(self.kpis["l5"], 4)
        self.assertGreaterEqual(self.kpis["l14"], 20)
        self.assertGreater(self.kpis["pd"], 100)
        self.assertGreater(self.kpis["skus"], 500)

    def test_l5_urgente_antes_que_baja(self):
        nombres = [m["modelo"] for m in self.lista["linea5"]]
        self.assertIn("SHORT PLAYA CAB", nombres)
        self.assertIn("LITE PANT DAMA", nombres)
        self.assertLess(nombres.index("SHORT PLAYA CAB"), nombres.index("LITE PANT DAMA"))
        self.assertTrue(all(m["grupo"] == "linea5" for m in self.lista["linea5"]))
        self.assertTrue(all("5" in m["lineas"] for m in self.lista["linea5"]))
        self.assertTrue(all("5" not in m["lineas"] for m in self.lista["lineas14"]))

    def test_especial_encabeza_l14(self):
        top = self.lista["lineas14"][0]
        self.assertTrue(top["especial"])
        self.assertEqual(top["prioridad"], "Especial")
        rios = [m for m in self.lista["lineas14"] if m["modelo"] == "RIO KIDS"]
        self.assertEqual(len(rios), 1)
        self.assertEqual(rios[0]["prioridad"], "Urgente")

    def test_pd_en_variantes(self):
        pd = [s for m in self.lista["modelos"] for s in m["skus"] if s["pd"]]
        self.assertTrue(any(s["mo"].upper().startswith("PD") for s in pd))
        no_pd = [s for m in self.lista["modelos"] for s in m["skus"] if not s["pd"]]
        self.assertTrue(any(s["mo"] for s in no_pd))

    def test_checks_sin_semana(self):
        self.assertGreater(len(self.extraido["checks"]), 50)
        self.assertTrue(all(k.startswith("M|") or k.startswith("S|") for k in self.extraido["checks"]))

    def test_html_real_descargable(self):
        payload = payload_para_html(self.extraido)
        dest = ROOT / "impresion-digital-prueba.html"
        escribir_html(payload, dest)
        html = dest.read_text(encoding="utf-8")
        self.assertGreater(dest.stat().st_size, 50_000)
        self.assertIn("SHORT PLAYA CAB", html)
        self.assertIn("lista fija", html)
        self.assertIn("M|", html)
        self.assertNotIn("imp-mod-pd", html)
        self.assertNotIn("<th>Prioridad</th>", html)
        self.assertNotIn("<th>Línea</th>", html)
        self.assertNotIn("<th>Variantes</th>", html)
        self.assertNotIn("<th>Fecha</th>", html)
        self.assertNotIn('id="f-prio"', html)
        self.assertNotIn("<label>Prioridad</label>", html)
        self.assertIn("<th>Solicitada</th>", html)
        self.assertIn("<th>Producida</th>", html)


@unittest.skipUnless(XLSX44.exists(), "Falta el Excel 44 de Planificación")
class TestXlsx44FaltanteCero(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.extraido = extraer_desde_xlsx(str(XLSX44))
        cls.lista = cls.extraido["lista"]
        cls.kpis = resumen(cls.lista)

    def test_incluye_faltante_cero_abiertas(self):
        skus = [s for m in self.lista["modelos"] for s in m["skus"]]
        ceros = [s for s in skus if Numberish(s.get("faltante")) == 0]
        self.assertGreater(len(ceros), 0, "El Excel 44 debe traer órdenes con faltante 0 aún abiertas")
        self.assertTrue(all((s.get("solicitada") or 0) > 0 or (s.get("producida") or 0) > 0 for s in ceros))
        self.assertFalse(any(mo_cerrada(s.get("moStatus")) for s in skus))
        self.assertGreater(self.kpis["skus"], 500)
        self.assertGreater(self.kpis["l14"], 10)

    def test_html_actual_con_columnas(self):
        payload = payload_para_html(self.extraido)
        dest = ROOT / "impresion-digital-prueba.html"
        escribir_html(payload, dest)
        html = dest.read_text(encoding="utf-8")
        self.assertIn("<th>Solicitada</th>", html)
        self.assertIn("<th>Producida</th>", html)
        self.assertIn("<th>Faltante</th>", html)
        self.assertIn("faltante 0", html)


class TestDashboardAppsScript(unittest.TestCase):
    def test_dashboard_html_lista_fija(self):
        html = (ROOT / "Dashboard.html").read_text(encoding="utf-8")
        gs = (ROOT / "Codigo.gs").read_text(encoding="utf-8")
        self.assertIn("function agruparImpresionFija(", html)
        self.assertIn("function listaImpresionFija()", html)
        self.assertIn("Lista fija de Impresión Digital", html)
        self.assertIn("imp-grupo-l14", html)
        self.assertIn("imp-grupo-l5", html)
        self.assertIn("b-pd", html)
        self.assertNotIn("imp-mod-pd", html)
        self.assertNotIn("<th>Prioridad</th>", html)
        self.assertNotIn("<th>Variantes</th>", html)
        self.assertNotIn("window.chkImpSemana", html)
        self.assertNotIn("function cargaImp(", html)
        self.assertNotIn("function filasImp(", html)
        self.assertIn("window.chkImpGrupo", html)
        self.assertIn("guardarChecksImpresion", html)
        self.assertIn('var VERSION_SISTEMA = "5.9.48"', gs)
        self.assertIn("IMPRESIÓN DIGITAL FALTANTE 0", gs)
        self.assertIn("IMPRESIÓN DIGITAL SIN FILTRO PRIORIDAD", gs)
        self.assertIn("IMPRESIÓN DIGITAL LISTA FIJA", gs)
        self.assertIn("function moCerradaImp(", html)
        self.assertIn("<th>Solicitada</th>", html)
        self.assertIn("<th>Producida</th>", html)
        self.assertNotIn("if(!(Number(row.faltante)>0)) return;", html)
        self.assertIn("moStatus:", gs)
        i_imp = html.find("function renderImp()")
        j_imp = html.find("window.onImpFiltro")
        self.assertGreater(j_imp, i_imp)
        self.assertNotIn("fSem()", html[i_imp:j_imp])
        self.assertNotIn("f-imp-prio", html)
        self.assertNotIn("_impPrio", html)
        self.assertNotIn("optsImpSelect_", html)
        self.assertNotIn("<label>Prioridad</label>", html)
        self.assertIn('id="f-imp-pd"', html)


if __name__ == "__main__":
    unittest.main()
