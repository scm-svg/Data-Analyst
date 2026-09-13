#!/usr/bin/env python3
"""Invariants for the generated Shorts Playa ALL dashboard."""

import json
import re
import unittest
from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "DASHBOARD SHORTS PLAYA ALL.html"

KEPT_MONTHS = {
    "octubre-2025": 251,
    "noviembre-2025": 192,
    "diciembre-2025": 470,
    "enero-2026": 133,
    "febrero-2026": 324,
    "marzo-2026": 356,
    "abril-2026": 256,
    "mayo-2026": 200,
    "junio-2026": 251,
}


def load_data():
    text = HTML.read_text(encoding="utf-8")
    match = re.search(r"var DATA=(\{.*?\});", text, re.DOTALL)
    return text, json.loads(match.group(1))


class DashboardHtmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text, cls.data = load_data()

    def test_kept_months_unchanged(self):
        for month, units in KEPT_MONTHS.items():
            self.assertEqual(self.data["meses_und"][month], units, month)

    def test_excel_months_present(self):
        self.assertEqual(self.data["meses_und"]["julio-2026"], 236)
        self.assertEqual(self.data["meses_und"]["agosto-2026"], 557)
        self.assertEqual(self.data["meses_und"]["septiembre-2026"], 224)

    def test_september_is_partial_and_out_of_velocity(self):
        self.assertTrue(self.data["es_parcial"])
        self.assertEqual(self.data["partial_month"], "septiembre-2026")
        self.assertEqual(self.data["velocity_months"], [
            "marzo-2026", "abril-2026", "mayo-2026",
            "junio-2026", "julio-2026", "agosto-2026",
        ])

    def test_seasonality_includes_upcoming_events(self):
        peaks = self.data["high_season_peaks"]
        self.assertGreaterEqual(peaks["diciembre"], 1.4)
        self.assertGreaterEqual(peaks["enero"], 1.2)
        self.assertGreaterEqual(peaks["carnaval"], 1.2)
        self.assertGreaterEqual(peaks["semana_santa"], 1.2)
        self.assertGreater(self.data["high_season_factor"], peaks["diciembre"])
        self.assertLess(self.data["season_raw_ratios"]["enero"], 1.0)

    def test_inventory_and_produce(self):
        self.assertEqual(self.data["stock_total"], 2755)
        self.assertEqual(self.data["stock_taller"], 891)
        produce = sum(r["produce"] for r in self.data["production_plan"])
        self.assertGreater(produce, 0)
        self.assertEqual(self.data["total"], 3450)

    def test_ui_shows_new_methodology(self):
        self.assertIn("Oct 25 — Sep 26", self.text)
        self.assertIn(str(self.data["high_season_factor"]), self.text)
        self.assertIn("Carnaval", self.text)
        self.assertIn("Semana Santa", self.text)
        self.assertNotIn("Mayo 2026 con datos parciales", self.text)
        self.assertIn("no entra en el promedio de Decisiones", self.text)
        self.assertIn("skipMom", self.text)


if __name__ == "__main__":
    unittest.main()
