#!/usr/bin/env python3
"""Unit tests for Short Playa ALL seasonality and Decisiones math."""

import unittest

from update_short_playa_all import (
    ANCHOR_COMPLETE,
    COLOR_CATALOG,
    COLORES_DESCONTINUADOS,
    DEC_FLOOR,
    ENE_FLOOR,
    LEAD_MONTHS,
    PARTIAL_MONTH,
    calc_produce,
    compute_production_plan,
    compute_seasonality,
    merge_sales,
    mes_sort_key,
    pick_velocity_months,
    prune_to_original_colors,
)


class VelocityMonthsTests(unittest.TestCase):
    def test_six_months_ending_august_excludes_partial_september(self):
        months = [
            "octubre-2025", "noviembre-2025", "diciembre-2025",
            "enero-2026", "febrero-2026", "marzo-2026", "abril-2026",
            "mayo-2026", "junio-2026", "julio-2026", "agosto-2026",
            "septiembre-2026",
        ]
        got = pick_velocity_months(months)
        self.assertEqual(got, [
            "marzo-2026", "abril-2026", "mayo-2026",
            "junio-2026", "julio-2026", "agosto-2026",
        ])
        self.assertNotIn(PARTIAL_MONTH, got)
        self.assertEqual(got[-1], ANCHOR_COMPLETE)

    def test_without_september_still_anchors_on_august(self):
        months = [
            "febrero-2026", "marzo-2026", "abril-2026",
            "mayo-2026", "junio-2026", "julio-2026", "agosto-2026",
        ]
        self.assertEqual(pick_velocity_months(months)[0], "marzo-2026")


class SeasonalityTests(unittest.TestCase):
    def setUp(self):
        self.meses_und = {
            "octubre-2025": 251, "noviembre-2025": 192, "diciembre-2025": 470,
            "enero-2026": 133, "febrero-2026": 324, "marzo-2026": 356,
            "abril-2026": 256, "mayo-2026": 200, "junio-2026": 251,
            "julio-2026": 218, "agosto-2026": 281,
        }
        self.order = list(self.meses_und)
        self.vel = pick_velocity_months(self.order)

    def test_december_uses_historical_when_above_floor(self):
        season = compute_seasonality(self.meses_und, self.vel, self.order)
        # baseline Mar–Ago = (356+256+200+251+218+281)/6 = 260.3
        self.assertAlmostEqual(season["baseline"], 260.3, places=1)
        self.assertGreaterEqual(season["factors"]["diciembre"], DEC_FLOOR)
        self.assertGreater(season["factors"]["diciembre"], DEC_FLOOR)

    def test_january_uses_planning_floor_not_stockout_ratio(self):
        season = compute_seasonality(self.meses_und, self.vel, self.order)
        self.assertLess(season["raw_ratios"]["enero"], 1.0)
        self.assertEqual(season["factors"]["enero"], ENE_FLOOR)
        self.assertIn("quiebre", season["notes"]["enero"])

    def test_carnival_and_semana_santa_raise_the_composite(self):
        season = compute_seasonality(self.meses_und, self.vel, self.order)
        self.assertGreaterEqual(season["factors"]["carnaval"], 1.20)
        self.assertGreaterEqual(season["factors"]["semana_santa"], 1.20)
        other = sum(season["factors"][k] - 1 for k in ("enero", "carnaval", "semana_santa"))
        expected_hs = round(season["factors"]["diciembre"] + other / LEAD_MONTHS, 2)
        self.assertEqual(season["high_season_factor"], expected_hs)
        # Including Enero / Carnaval / SS must beat December-only
        self.assertGreater(season["high_season_factor"], season["factors"]["diciembre"])

    def test_september_partial_is_ignored_in_ratios(self):
        und = dict(self.meses_und)
        und["septiembre-2026"] = 10
        order = self.order + ["septiembre-2026"]
        season = compute_seasonality(und, self.vel, order)
        season_no_sep = compute_seasonality(self.meses_und, self.vel, self.order)
        self.assertEqual(season["factors"], season_no_sep["factors"])


class ProduceTests(unittest.TestCase):
    def test_no_produce_when_coverage_meets_lead(self):
        self.assertEqual(calc_produce(30, 10), 0)

    def test_produce_fills_three_month_gap(self):
        self.assertEqual(calc_produce(5, 10), 25)

    def test_zero_velocity(self):
        self.assertEqual(calc_produce(10, 0), 0)


class MergeSalesTests(unittest.TestCase):
    def test_replaces_only_months_present_in_excel(self):
        existing = [
            {"mes": "junio-2026", "v": 1, "tienda": "GRIETA"},
            {"mes": "julio-2026", "v": 1, "tienda": "GRIETA"},
            {"mes": "agosto-2026", "v": 1, "tienda": "GRIETA"},
        ]
        new_rows = [
            {"mes": "julio-2026", "v": 9, "tienda": "GRIETA"},
            {"mes": "septiembre-2026", "v": 4, "tienda": "GRIETA"},
        ]
        merged, replaced = merge_sales(existing, new_rows)
        self.assertEqual(sorted(replaced, key=mes_sort_key), ["julio-2026", "septiembre-2026"])
        months = [r["mes"] for r in merged]
        self.assertIn("junio-2026", months)
        self.assertIn("agosto-2026", months)
        self.assertEqual(sum(r["v"] for r in merged if r["mes"] == "julio-2026"), 9)
        self.assertNotIn(1, [r["v"] for r in merged if r["mes"] == "julio-2026"])


class CatalogColorTests(unittest.TestCase):
    def test_prune_drops_excel_only_colors_and_keeps_original_order(self):
        data = {
            "raw_rows": [
                {"color": "Cereza", "mes": "julio-2026", "v": 10, "modelo": "SHORT PLAYA UNICOLOR"},
                {"color": "Honey", "mes": "julio-2026", "v": 2, "modelo": "SHORT PLAYA SUBLIMADO"},
                {"color": "Santa Teresa", "mes": "agosto-2026", "v": 9, "modelo": "SHORT PLAYA SUBLIMADO"},
            ],
            "stock": {
                "SHORT PLAYA UNICOLOR/CAB/Cereza/M": 20,
                "SHORT PLAYA SUBLIMADO/CAB/Honey/M": 5,
                "SHORT PLAYA SUBLIMADO/CAB/Crasqui/L": 3,
            },
            "stock_by_store": {
                "TALLER": {
                    "SHORT PLAYA UNICOLOR/CAB/Cereza/M": 8,
                    "SHORT PLAYA SUBLIMADO/CAB/Honey/M": 5,
                },
                "GRIETA": {"SHORT PLAYA UNICOLOR/CAB/Cereza/M": 12},
            },
            "filtros": {"colores": ["Honey", "Cereza", "Crasqui"]},
        }
        pruned = prune_to_original_colors(data)
        self.assertEqual([r["color"] for r in pruned["raw_rows"]], ["Cereza"])
        self.assertEqual(list(pruned["stock"]), ["SHORT PLAYA UNICOLOR/CAB/Cereza/M"])
        self.assertEqual(pruned["filtros"]["colores"], COLOR_CATALOG)
        self.assertNotIn("Honey", pruned["filtros"]["colores"])
        self.assertEqual(pruned["colores_descontinuados"], COLORES_DESCONTINUADOS)

    def test_production_plan_includes_active_stock_without_sales(self):
        rows = [{
            "modelo": "SHORT PLAYA UNICOLOR",
            "genero": "CAB",
            "color": "Cereza",
            "talla": "M",
            "mes": "agosto-2026",
            "v": 6,
            "activo": True,
        }]
        stock = {
            "SHORT PLAYA UNICOLOR/CAB/Cereza/M": 10,
            "SHORT PLAYA UNICOLOR/KIDS/Marron/12": 30,
        }
        taller = {"SHORT PLAYA UNICOLOR/KIDS/Marron/12": 30}
        plan, summary, _ = compute_production_plan(
            rows, stock, taller, ["agosto-2026"], 1.0
        )
        colors = {(r["genero"], r["color"]) for r in plan}
        self.assertIn(("CAB", "Cereza"), colors)
        self.assertIn(("KIDS", "Marron"), colors)
        self.assertEqual(summary["SHORT PLAYA UNICOLOR"]["stk"], 40)


if __name__ == "__main__":
    unittest.main()
