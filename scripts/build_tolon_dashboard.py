#!/usr/bin/env python3
"""Generate TOLON store dashboard from sales + inventory Excel exports."""
from pathlib import Path

from store_dashboard_core import StoreConfig, StoreTheme, build_dashboard

ROOT = Path(__file__).resolve().parents[1]

TOLON_THEME = StoreTheme(
    fonts_url="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap",
    css_root=""":root{
  --bg:#0c0814;--su:#140f1f;--s2:#1c1630;--s3:#241e3c;--bd:#342a52;
  --ac:#a855f7;--a2:#d8b4fe;--coral:#f59e0b;--sand:#fde68a;--gr:#4ade80;--re:#f87171;--am:#fbbf24;
  --mu:#8b7fa8;--m2:#5c5278;--tx:#f3eefc;
  --fh:'Sora',sans-serif;--fm:'JetBrains Mono',monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:radial-gradient(ellipse 120% 80% at 50% -20%,#1e1040 0%,var(--bg) 55%);color:var(--tx);font-family:var(--fh);min-height:100vh}""",
    hdr_bg="rgba(12,8,20,.92)",
    badge_grad="linear-gradient(135deg,#7c3aed,#a855f7 45%,#f59e0b)",
    badge_text="#fff",
    insight_bg="linear-gradient(90deg,rgba(168,85,247,.14),rgba(245,158,11,.1))",
    insight_border="rgba(168,85,247,.3)",
    chip_on_text="#fff",
    rep_border="rgba(168,85,247,.35)",
    rep_bg="linear-gradient(180deg,rgba(168,85,247,.08),var(--su))",
    palette=["#a855f7", "#f59e0b", "#fde68a", "#4ade80", "#38bdf8", "#fb7185", "#c084fc", "#f97316", "#86efac", "#94a3b8"],
    chart_accent="rgba(168,85,247,.9)",
    chart_accent_dim="rgba(168,85,247,.35)",
)

TOLON_CONFIG = StoreConfig(
    store_name="TOLON",
    store_badge="TOLÓN",
    stock_path=Path("/home/ubuntu/.cursor/projects/workspace/uploads/TOLON_INVENTARIO_COMPLETO_a977.xlsx"),
    sales_path=Path("/home/ubuntu/.cursor/projects/workspace/uploads/VENTAS_TOLON_e248.xlsx"),
    stock_sheet="Inventario",
    sales_sheet="VENTAS TOLON",
    sales_model_col="Producto",
    out_html=ROOT / "dashboard_tolon.html",
    meta_suffix="Abr–Jul 2026 · excl. Kraft/Band VZLA",
    footer_sources="VENTAS_TOLON + TOLON_INVENTARIO_COMPLETO",
    page_title="TOLÓN · Dashboard Tienda",
    theme=TOLON_THEME,
)


def main():
    out = build_dashboard(TOLON_CONFIG)
    print(f"Wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
