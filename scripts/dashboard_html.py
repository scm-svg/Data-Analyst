"""Dashboard HTML ejecutivo — Tela Jabón Microfibra."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def _esc(text) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_dashboard_html(ctx: dict, output_path: Path) -> None:
    kpis = ctx["kpis"]
    top5 = ctx["top5"]
    pedidos = ctx["pedidos"]
    acciones = ctx["acciones"]
    modelos = ctx["modelos"]
    alertas = ctx["alertas"]
    chart_labels = ctx["chart_labels"]
    chart_values = ctx["chart_values"]
    hoy = date.today().strftime("%d/%m/%Y")

    top5_cards = ""
    for i, row in enumerate(top5, 1):
        top5_cards += f"""
        <div class="color-card">
          <div class="rank">#{i}</div>
          <h3>{_esc(row['Color'])}</h3>
          <p class="stat">{row['Venta prom (u/mes)']:.0f} uds/mes · {row['% Total']:.1f}% ventas</p>
          <p class="why">{_esc(row.get('Justificación', ''))}</p>
        </div>"""

    pedido_cards = ""
    for p in pedidos:
        pedido_cards += f"""
        <div class="action-card urgent">
          <div class="action-head">
            <span class="badge">Pedir tela</span>
            <strong>{p['Pedido sugerido (kg)']:.0f} kg</strong>
          </div>
          <h3>{_esc(p['Color'])}</h3>
          <ul>
            <li>Producir <strong>{p['Prod. requerida (u)']:.0f}</strong> unidades</li>
            <li>Tela actual: {p['Tela actual (kg)']:.0f} kg</li>
            <li>{_esc(p.get('Acción sugerida', ''))}</li>
          </ul>
        </div>"""

    accion_cards = ""
    for a in acciones:
        cls = "warn" if a.get("tipo") == "validar" else "info"
        accion_cards += f"""
        <div class="action-card {cls}">
          <div class="action-head"><span class="badge">{_esc(a['tipo_label'])}</span></div>
          <h3>{_esc(a['titulo'])}</h3>
          <p>{_esc(a['texto'])}</p>
        </div>"""

    modelo_rows = ""
    for m in modelos:
        modelo_rows += f"""
        <tr>
          <td>{_esc(m['Modelo'])}</td>
          <td class="num">{m['Prod. requerida']:.0f}</td>
          <td class="num">{m['Inv PT']:.0f}</td>
          <td class="num">{m['Cob. PT (meses)']:.1f}</td>
        </tr>"""

    alerta_items = "".join(f"<li>{_esc(a)}</li>" for a in alertas)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Planificación Tela Jabón Microfibra</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Syne:wght@600;700;800&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root {{
  --bg:#f4f6fb; --card:#fff; --text:#1a2340; --muted:#5c6478; --line:#dde3ef;
  --blue:#2563eb; --blue-soft:#eff6ff; --green:#059669; --green-soft:#ecfdf5;
  --amber:#d97706; --amber-soft:#fffbeb; --red:#dc2626; --red-soft:#fef2f2;
}}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:'DM Sans',sans-serif; background:var(--bg); color:var(--text); line-height:1.5; }}
.wrap {{ max-width:1180px; margin:0 auto; padding:24px 20px 48px; }}
.hero {{
  background:linear-gradient(135deg,#1e3a8a 0%,#2563eb 55%,#3b82f6 100%);
  color:#fff; border-radius:20px; padding:28px 32px; margin-bottom:24px;
  box-shadow:0 10px 30px rgba(37,99,235,.25);
}}
.hero h1 {{ font-family:'Syne',sans-serif; font-size:1.85rem; font-weight:800; }}
.hero p {{ opacity:.9; margin-top:8px; max-width:720px; }}
.hero .meta {{ margin-top:14px; font-size:.85rem; opacity:.8; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:24px; }}
.kpi {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px; }}
.kpi .label {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); }}
.kpi .value {{ font-family:'Syne',sans-serif; font-size:1.55rem; font-weight:800; color:var(--blue); margin-top:4px; }}
.kpi .sub {{ font-size:.78rem; color:var(--muted); margin-top:2px; }}
.section {{ margin-bottom:28px; }}
.section h2 {{ font-family:'Syne',sans-serif; font-size:1.15rem; margin-bottom:6px; }}
.section .lead {{ color:var(--muted); font-size:.92rem; margin-bottom:16px; }}
.grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
.grid-3 {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; }}
@media(max-width:800px) {{ .grid-2 {{ grid-template-columns:1fr; }} }}
.color-card, .action-card {{
  background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px;
}}
.color-card .rank {{
  display:inline-block; background:var(--blue-soft); color:var(--blue);
  font-weight:700; font-size:.75rem; padding:2px 8px; border-radius:999px; margin-bottom:8px;
}}
.color-card h3 {{ font-size:1.05rem; margin-bottom:4px; }}
.color-card .stat {{ color:var(--muted); font-size:.85rem; }}
.color-card .why {{ margin-top:10px; font-size:.88rem; }}
.action-card.urgent {{ border-color:#86efac; background:var(--green-soft); }}
.action-card.warn {{ border-color:#fcd34d; background:var(--amber-soft); }}
.action-card.info {{ border-color:#93c5fd; background:var(--blue-soft); }}
.action-head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }}
.badge {{
  font-size:.7rem; font-weight:700; text-transform:uppercase; letter-spacing:.04em;
  background:#fff; border:1px solid var(--line); padding:3px 8px; border-radius:999px;
}}
.action-card ul {{ margin-top:8px; padding-left:18px; font-size:.88rem; }}
.action-card li {{ margin-bottom:4px; }}
.chart-box {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px; }}
table {{ width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line); border-radius:14px; overflow:hidden; }}
th {{ background:#eef2ff; color:#3730a3; font-size:.72rem; text-transform:uppercase; letter-spacing:.04em; text-align:left; padding:10px 12px; }}
td {{ padding:10px 12px; border-top:1px solid var(--line); font-size:.88rem; }}
td.num {{ text-align:right; font-weight:600; }}
.note-box {{ background:var(--amber-soft); border:1px solid #fcd34d; border-radius:14px; padding:16px 18px; }}
.note-box h3 {{ font-size:.95rem; margin-bottom:8px; color:#92400e; }}
.note-box ul {{ padding-left:18px; color:#78350f; font-size:.88rem; }}
.note-box li {{ margin-bottom:6px; }}
.footer {{ text-align:center; color:var(--muted); font-size:.78rem; margin-top:32px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <h1>Planificación Tela Jabón Microfibra</h1>
    <p>Resumen ejecutivo para decidir qué colores mantener, cuánta tela pedir y qué producir antes del pico Nov–Dic.</p>
    <div class="meta">Datos: Oct 2025 – Jul 2026 · Actualizado {_esc(hoy)} · Lead time tela: 45 días</div>
  </div>

  <div class="kpis">
    <div class="kpi"><div class="label">Ventas analizadas</div><div class="value">{kpis['ventas']:,.0f}</div><div class="sub">uds en 10 meses</div></div>
    <div class="kpi"><div class="label">Inventario PT</div><div class="value">{kpis['inv_pt']:,.0f}</div><div class="sub">≈ {kpis['meses_pt']:.1f} meses</div></div>
    <div class="kpi"><div class="label">Tela en almacén</div><div class="value">{kpis['inv_tela']:,.0f}</div><div class="sub">kg disponibles</div></div>
    <div class="kpi"><div class="label">Pedido sugerido</div><div class="value" style="color:var(--green)">{kpis['pedido_kg']:,.0f}</div><div class="sub">kg de tela a comprar</div></div>
    <div class="kpi"><div class="label">Producción PT</div><div class="value">{kpis['prod_pt']:,.0f}</div><div class="sub">uds a montar (Ago–Dic)</div></div>
  </div>

  <div class="section">
    <h2>Qué hacer ahora</h2>
    <p class="lead">Acciones concretas derivadas del inventario, la demanda proyectada y el lead time de 45 días.</p>
    <div class="grid-2">{pedido_cards}{accion_cards}</div>
  </div>

  <div class="section">
    <h2>Top 5 colores — visión Logística</h2>
    <p class="lead">Colores con mejor rotación y menor riesgo de quedar inmovilizados en inventario (venden parejo, en todo el catálogo).</p>
    <div class="grid-3">{top5_cards}</div>
    <p style="margin-top:12px;font-size:.85rem;color:var(--muted)">
      <strong>Nota:</strong> Lila no entra en este top 5 porque tuvo un pico puntual (lanzamiento moda), pero sí requiere pedido urgente de tela.
    </p>
  </div>

  <div class="section grid-2">
    <div class="chart-box">
      <h2 style="margin-bottom:12px">Ventas por color (top 8)</h2>
      <canvas id="chartColores" height="220"></canvas>
    </div>
    <div>
      <h2 style="margin-bottom:12px">Modelos a producir (prioridad)</h2>
      <table>
        <thead><tr><th>Modelo</th><th>Prod. req.</th><th>Inv PT</th><th>Meses cob.</th></tr></thead>
        <tbody>{modelo_rows}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <div class="note-box">
      <h3>Puntos a tener en cuenta</h3>
      <ul>{alerta_items}</ul>
    </div>
  </div>

  <div class="footer">Generado automáticamente · analisis_microfibra_jabon.xlsx contiene el detalle técnico</div>
</div>
<script>
const labels = {json.dumps(chart_labels, ensure_ascii=False)};
const values = {json.dumps(chart_values)};
new Chart(document.getElementById('chartColores'), {{
  type: 'bar',
  data: {{
    labels,
    datasets: [{{
      label: 'Unidades vendidas',
      data: values,
      backgroundColor: ['#2563eb','#3b82f6','#60a5fa','#818cf8','#6366f1','#4f46e5','#4338ca','#3730a3'],
      borderRadius: 8
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ beginAtZero: true, grid: {{ color: '#eef2ff' }} }},
      x: {{ grid: {{ display: false }} }}
    }}
  }}
}});
</script>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
