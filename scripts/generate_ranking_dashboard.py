#!/usr/bin/env python3
"""Genera dashboard HTML de ranking desde Excel."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard_html import generate_ranking_dashboard_html
from ranking_dashboard import build_ranking_dashboard_context


def main() -> None:
    parser = argparse.ArgumentParser(description="Dashboard ranking colores microfibra")
    parser.add_argument(
        "excel",
        type=Path,
        nargs="?",
        default=Path("analisis_microfibra_jabon.xlsx"),
        help="Excel fuente (Ranking Colores o analisis_microfibra_jabon)",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("dashboard_ranking_colores.html"),
    )
    args = parser.parse_args()
    if not args.excel.exists():
        # buscar ranking subido
        uploads = Path("/home/ubuntu/.cursor/projects/workspace/uploads")
        for name in ["Ranking_Colores_Microfibra_79e5.xlsx", "Ranking_Colores_Microfibra_b8da.xlsx"]:
            p = uploads / name
            if p.exists():
                args.excel = p
                break
    ctx = build_ranking_dashboard_context(args.excel)
    generate_ranking_dashboard_html(ctx, args.output)
    print(f"Dashboard: {args.output}")
    print(f"Top 5: {ctx['respuesta']}")


if __name__ == "__main__":
    main()
