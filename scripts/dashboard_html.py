"""Dashboard HTML — ranking de colores microfibra (Top 5 + ranking)."""

from __future__ import annotations

from pathlib import Path

COLOR_HEX = {
    "NEGRO": "#1C1C1C", "BLANCO": "#FDFDFD", "AZUL MARINO": "#1E3A5F",
    "VERDE MILITAR": "#4E5B3C", "AZUL LAVANDA": "#A9B7E6", "LILA": "#C9A6E4",
    "AZUL REY": "#2B4BD7", "ROJO": "#D63031", "PÚRPURA": "#7D3FB0", "PURPURA": "#7D3FB0",
    "GRIS CLARO": "#CFCFCF", "AGUAMARINA": "#6FD8C8", "VINOTINTO": "#722F37",
    "AMARILLO NEÓN": "#EEF25A", "AMARILLO NEON": "#EEF25A", "ROSADO PASTEL": "#F4B8C8",
}


def _esc(text) -> str:
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _hex(color: str) -> str:
    return COLOR_HEX.get(color.upper().replace("Ó", "O").replace("É", "E").replace("Ú", "U"), "#CCCCCC")


def _swatch(color: str) -> str:
    return f'<span class="sw" style="background:{_hex(color)}"></span>'


def generate_ranking_dashboard_html(ctx: dict, output_path: Path) -> None:
    meta = ctx["meta"]
    top5 = ctx["top5"]
    ranking = ctx["ranking"]
    metodologia = ctx.get("metodologia", [])

    top5_chips = "".join(
        f'<span class="cchip">{_swatch(c["Color"])} {_esc(c["Color"])}</span>' for c in top5
    )

    tags_html = ""
    for c in top5:
        reg = c.get("regularidad") or ""
        cob = c.get("cob_pt") or c.get("autonomia") or 0
        tags_html += f"""
    <div class="tag"><span class="rank">Nº{c['rank']}</span>
      <h3>{_swatch(c['Color'])}{_esc(c['Color'])}</h3>
      <div class="chip" style="background:{_hex(c['Color'])}"></div>
      <div class="facts">{c['ventas_mes']:.0f} u/mes · score {c['score']:.1f} · {cob:.1f} meses stock</div>
      <div class="just">{_esc(c.get('justificacion', c.get('diagnostico', '')))}</div>
    </div>"""

    alt = ctx.get("alterno")
    if alt:
        tags_html += f"""
    <div class="tag alt"><span class="rank">Alt.</span>
      <h3>{_swatch(alt['Color'])}{_esc(alt['Color'])} <span class="pill">suplente</span></h3>
      <div class="chip" style="background:{_hex(alt['Color'])}"></div>
      <div class="facts">{alt.get('ventas_mes', 0):.0f} u/mes</div>
      <div class="just">{_esc(alt.get('diagnostico', 'Alterno del top 5'))}</div>
    </div>"""

    met_html = "".join(
        f'<div class="met"><b>{_esc(m["titulo"])}</b>{_esc(m["texto"])}</div>' for m in metodologia[:5]
    )

    rank_rows = ""
    for r in ranking:
        cls = "row-top5" if r.get("top5") else ""
        badge = '<span class="pill p-ok">Top 5</span>' if r.get("top5") else ""
        just = r.get("justificacion") or r.get("diagnostico") or "—"
        if r.get("top5"):
            just = "—"
        rank_rows += f"""
      <tr class="{cls}">
        <td class="num">{r['rank']}</td>
        <td>{_swatch(r['Color'])}<b>{_esc(r['Color'])}</b> {badge}</td>
        <td class="num">{r['ventas_mes']:.0f}</td>
        <td>{_esc(r.get('regularidad', '—'))}</td>
        <td class="num">{r.get('cob_pt', 0):.1f}</td>
        <td class="num">{r.get('autonomia', r.get('cob_pt', 0)):.1f}</td>
        <td class="num score">{r['score']:.1f}</td>
        <td class="why">{_esc(just if not r.get('top5') else r.get('diagnostico', 'TOP 5'))}</td>
      </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ranking Colores Microfibra</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=Archivo+Expanded:wght@600;700;800&display=swap" rel="stylesheet">
<style>
:root{{
  --paper:#FBFBF9; --ink:#16150F; --muted:#6E6A60; --line:#E4E1DA; --card:#FFFFFF;
  --ok:#2E7D4F; --ok-bg:#EAF4EE; --warn:#B07A1E; --warn-bg:#FBF3E2;
  --neutral-bg:#F1F0EC;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Archivo',system-ui,sans-serif;background:var(--paper);color:var(--ink);line-height:1.45;font-size:15px}}
.wrap{{max-width:1100px;margin:0 auto;padding:0 18px 60px}}
header{{padding:28px 0 16px;border-bottom:2px solid var(--ink)}}
.eyebrow{{font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);margin-bottom:6px}}
h1{{font-family:'Archivo Expanded',sans-serif;font-weight:800;font-size:clamp(20px,4vw,28px);line-height:1.1}}
.sub{{color:var(--muted);margin-top:6px;font-size:13.5px}}
nav{{display:flex;gap:4px;margin:16px 0 24px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--paper);z-index:10;padding-top:6px}}
nav button{{font-family:'Archivo',sans-serif;font-size:14px;font-weight:600;padding:10px 16px;border:none;background:none;color:var(--muted);cursor:pointer;border-bottom:3px solid transparent}}
nav button.active{{color:var(--ink);border-bottom-color:var(--ink)}}
section{{display:none}}section.show{{display:block}}
h2{{font-family:'Archivo Expanded',sans-serif;font-weight:700;font-size:17px;margin:0 0 12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:14px}}
.q{{font-size:15px;font-weight:600;margin-bottom:8px}}
.a{{font-family:'Archivo Expanded';font-weight:800;font-size:22px;color:var(--ok);line-height:1.3}}
.note{{font-size:13px;color:var(--muted);margin-top:10px}}
.sw{{display:inline-block;width:14px;height:14px;border-radius:4px;vertical-align:-2px;margin-right:6px;border:1px solid rgba(0,0,0,.12)}}
.cchip{{display:inline-flex;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 11px;font-size:13px;font-weight:600;margin:3px 4px 3px 0}}
.pill{{display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;background:var(--neutral-bg);color:var(--muted);margin-left:6px}}
.p-ok{{background:var(--ok-bg);color:var(--ok)}}
.tags{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-top:14px}}
.tag{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;position:relative}}
.tag.alt{{border-style:dashed}}
.tag .rank{{position:absolute;top:10px;right:12px;font-family:'Archivo Expanded';font-weight:800;font-size:13px;color:var(--muted)}}
.tag .chip{{width:100%;height:44px;border-radius:8px;border:1px solid rgba(0,0,0,.1);margin:10px 0 8px}}
.tag h3{{font-family:'Archivo Expanded';font-size:15px;font-weight:700}}
.tag .facts{{font-size:12.5px;color:var(--muted)}}
.tag .just{{font-size:13px;margin-top:10px;line-height:1.4}}
.met-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px;margin-top:12px}}
.met{{background:#F6F5F1;border-radius:8px;padding:12px;font-size:13px}}
.met b{{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:4px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:13px}}
th{{font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);text-align:left;padding:10px 10px;border-bottom:1.5px solid var(--ink);background:#F6F5F1;white-space:nowrap}}
td{{padding:10px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
tr:last-child td{{border-bottom:none}}
td.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
td.score{{font-weight:700;color:#1F4E79}}
td.why{{font-size:12.5px;color:var(--muted);max-width:280px}}
tr.row-top5{{background:var(--ok-bg)}}
.tblwrap{{overflow-x:auto;border-radius:12px}}
footer{{margin-top:32px;padding-top:12px;border-top:1px solid var(--line);font-size:11.5px;color:var(--muted)}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="eyebrow">Somos Cuadro · Logística e Inventarios</div>
  <h1>Ranking de colores — Microfibra Jabón</h1>
  <div class="sub">Mejor rotación y menor riesgo de inmovilización · {meta['meses']} meses ({meta['periodo']}) · corte {_esc(meta['fecha'])}</div>
</header>

<nav id="tabs">
  <button class="active" data-t="t1">Top 5</button>
  <button data-t="t2">Ranking completo</button>
</nav>

<section id="t1" class="show">
  <div class="card">
    <div class="q">{_esc(ctx['pregunta'])}</div>
    <div class="a">{_esc(ctx['respuesta'])}</div>
    <div style="margin-top:12px">{top5_chips}</div>
    <div class="note">Estos 5 colores venden mucho, de forma sostenida, en todo el catálogo y sin meses de inventario parado.</div>
  </div>

  <h2>Detalle y justificación del Top 5</h2>
  <div class="tags">{tags_html}</div>

  <h2 style="margin-top:22px">Cómo se calculó el score (0–100)</h2>
  <div class="met-grid">{met_html}</div>
</section>

<section id="t2">
  <h2>Ranking — {len(ranking)} colores activos</h2>
  <p class="note" style="margin-bottom:12px">Ordenados por score total. Los del Top 5 están resaltados en verde. La columna «Por qué no Top 5» explica los que quedaron fuera (ej. Rojo, Lila).</p>
  <div class="tblwrap"><table>
    <thead><tr>
      <th>#</th><th>Color</th><th>Venta/mes</th><th>Regularidad</th>
      <th>Stock PT (m)</th><th>Autonomía (m)</th><th>Score</th><th>Por qué no Top 5 / diagnóstico</th>
    </tr></thead>
    <tbody>{rank_rows}</tbody>
  </table></div>
</section>

<footer>Fuente: {_esc(meta.get('fuente', 'Ranking Colores Microfibra.xlsx'))} · Respaldo técnico: analisis_microfibra_jabon.xlsx</footer>
</div>
<script>
document.querySelectorAll('#tabs button').forEach(b=>b.addEventListener('click',()=>{{
  document.querySelectorAll('#tabs button').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('section').forEach(s=>s.classList.remove('show'));
  b.classList.add('active');document.getElementById(b.dataset.t).classList.add('show');
  window.scrollTo({{top:0}});
}}));
</script>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")


# Compatibilidad con scripts que aún importan generate_dashboard_html
def generate_dashboard_html(ctx: dict, output_path: Path) -> None:
    generate_ranking_dashboard_html(ctx, output_path)
