"""Dashboard HTML — estilo planificación tela jabón microfibra."""

from __future__ import annotations

import json
from pathlib import Path


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


COLOR_HEX = {
    "NEGRO": "#1C1C1C",
    "BLANCO": "#FDFDFD",
    "AZUL MARINO": "#1E3A5F",
    "VERDE MILITAR": "#4E5B3C",
    "AZUL LAVANDA": "#A9B7E6",
    "LILA": "#C9A6E4",
    "AZUL REY": "#2B4BD7",
    "ROJO": "#D63031",
    "PÚRPURA": "#7D3FB0",
    "PURPURA": "#7D3FB0",
    "GRIS CLARO": "#CFCFCF",
    "AGUAMARINA": "#6FD8C8",
    "VINOTINTO": "#722F37",
    "AMARILLO NEÓN": "#EEF25A",
    "AMARILLO NEON": "#EEF25A",
    "ROSADO PASTEL": "#F4B8C8",
    "FUCSIA": "#E91E8C",
    "AZUL CIELO": "#87CEEB",
}


def _swatch(color: str) -> str:
    key = color.upper().replace("Ó", "O").replace("É", "E").replace("Ú", "U")
    hex_c = COLOR_HEX.get(key, "#CCCCCC")
    return f'<span class="sw" style="background:{hex_c}"></span>'


def _sku_code(producto: str) -> str:
    if not producto:
        return "—"
    text = str(producto)
    if text.startswith("[") and "]" in text:
        return text[1 : text.index("]")]
    return text


def generate_dashboard_html(ctx: dict, output_path: Path) -> None:
    meta = ctx["meta"]
    top5 = ctx["top5"]
    pedidos = ctx["pedidos"]
    cubiertos = ctx["cubiertos"]
    semaforo = ctx["semaforo"]
    lila = ctx["lila"]
    pendientes = ctx["pendientes"]

    top5_chips = "".join(
        f'<span class="cchip">{_swatch(c["Color"])} {_esc(c["Color"])}</span>' for c in top5
    )

    pedido_pills = ""
    for i, p in enumerate(pedidos):
        cls = "p-bad" if i == 0 else ("p-warn" if i < 4 else "p-n")
        pedido_pills += f'<span class="pill {cls}">{_esc(p["Color"])} {p["kg"]:.0f} kg</span> '

    pedido_rows = ""
    total_kg = 0
    for p in pedidos:
        total_kg += p["kg"]
        sku = p.get("sku") or "—"
        sku_html = f'<span class="pill p-bad">crear código</span>' if p.get("sin_codigo") else _esc(_sku_code(sku))
        pedido_rows += f"""
      <tr><td>{_swatch(p['Color'])}<b>{_esc(p['Color'])}</b></td><td>{sku_html}</td>
      <td class="num">{p['kg']:.0f}</td><td>{_esc(p['motivo'])}</td></tr>"""

    pedido_rows += f"""
      <tr class="total"><td colspan="2">TOTAL</td><td class="num">{total_kg:.0f}</td>
      <td>≈ {total_kg / meta['inv_tela'] * 100:.0f}% del inventario de tela actual ({meta['inv_tela']:,.0f} kg)</td></tr>"""

    cubiertos_html = "".join(
        f'<span class="cchip">{_swatch(c["Color"])} {_esc(c["Color"])}<small>{_esc(c["nota"])}</small></span>'
        for c in cubiertos
    )

    tags_html = ""
    for i, c in enumerate(top5, 1):
        checks = "".join(f'<div><span class="c">✓</span>{_esc(line)}</div>' for line in c.get("checks", []))
        tags_html += f"""
    <div class="tag"><span class="rank">Nº{i}</span>
      <h3>{_esc(c['Color'])}</h3><div class="chip" style="background:{COLOR_HEX.get(c['Color'].upper(), '#ccc')}"></div>
      <div class="facts">{c['ventas_mes']:.0f} prendas/mes · {c['pct']:.0f}% de la venta</div>
      <div class="checks">{checks}</div>
    </div>"""

    alt = ctx.get("alterno")
    if alt:
        tags_html += f"""
    <div class="tag" style="border-style:dashed"><span class="rank">Alt.</span>
      <h3>{_esc(alt['Color'])} <span class="pill p-n" style="margin-left:4px">suplente</span></h3>
      <div class="chip" style="background:{COLOR_HEX.get(alt['Color'].upper(), '#ccc')}"></div>
      <div class="facts">{alt['ventas_mes']:.0f} prendas/mes</div>
      <div class="checks"><div><span class="c">✓</span>{_esc(alt.get('nota', ''))}</div></div>
    </div>"""

    def bucket(name, cls, title, desc, items):
        chips = "".join(
            f'<span class="cchip">{_swatch(it["Color"])} {_esc(it["Color"])}<small>{_esc(it.get("nota",""))}</small></span>'
            for it in items
        )
        if not chips:
            return ""
        return f"""
  <div class="bucket {cls}">
    <h3>{title}</h3><p>{desc}</p><div class="crow">{chips}</div>
  </div>"""

    sem_html = (
        bucket("pedir", "b-bad", "🔴 Pedir tela ya", semaforo["pedir"]["desc"], semaforo["pedir"]["items"])
        + bucket("vigilar", "b-warn", "🟠 Vigilar — tela justa", semaforo["vigilar"]["desc"], semaforo["vigilar"]["items"])
        + bucket("ok", "b-ok", "🟢 No comprar más tela", semaforo["ok"]["desc"], semaforo["ok"]["items"])
        + bucket("decidir", "b-n", "⚪ Decidir si siguen en catálogo", semaforo["decidir"]["desc"], semaforo["decidir"]["items"])
    )

    pend_html = "".join(f" {_esc(p)}" for p in pendientes)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tela Jabón Microfibra · Planificación</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=Archivo+Expanded:wght@600;700;800&display=swap" rel="stylesheet">
<style>
:root{{
  --paper:#FBFBF9; --ink:#16150F; --muted:#6E6A60; --line:#E4E1DA; --card:#FFFFFF;
  --ok:#2E7D4F; --ok-bg:#EAF4EE; --warn:#B07A1E; --warn-bg:#FBF3E2; --bad:#C0392B; --bad-bg:#FAECE9;
  --neutral-bg:#F1F0EC;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Archivo',system-ui,sans-serif;background:var(--paper);color:var(--ink);line-height:1.45;font-size:15px}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 18px 60px}}
header{{padding:30px 0 18px;border-bottom:2px solid var(--ink)}}
.eyebrow{{font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);margin-bottom:6px}}
h1{{font-family:'Archivo Expanded',sans-serif;font-weight:800;font-size:clamp(21px,4vw,30px);line-height:1.1}}
.sub{{color:var(--muted);margin-top:6px;font-size:13.5px}}
nav{{display:flex;gap:4px;overflow-x:auto;margin:16px 0 26px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--paper);z-index:10;padding-top:6px}}
nav button{{font-family:'Archivo',sans-serif;font-size:13.5px;font-weight:600;padding:10px 14px;border:none;background:none;color:var(--muted);cursor:pointer;border-bottom:3px solid transparent;white-space:nowrap}}
nav button.active{{color:var(--ink);border-bottom-color:var(--ink)}}
nav button:focus-visible{{outline:2px solid var(--ink);outline-offset:2px}}
section{{display:none}}section.show{{display:block;animation:fade .25s ease}}
@keyframes fade{{from{{opacity:0;transform:translateY(4px)}}to{{opacity:1;transform:none}}}}
@media (prefers-reduced-motion:reduce){{section.show{{animation:none}}}}
h2{{font-family:'Archivo Expanded',sans-serif;font-weight:700;font-size:17px;margin:26px 0 12px}}
h2:first-child{{margin-top:0}}
.note{{font-size:12.5px;color:var(--muted);margin-top:8px}}
.sw{{display:inline-block;width:15px;height:15px;border-radius:4px;vertical-align:-2px;margin-right:7px;border:1px solid rgba(0,0,0,.14);flex:none}}
.grid{{display:grid;gap:14px}}
.g2{{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}}
.g3{{grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px}}
.big{{font-family:'Archivo Expanded',sans-serif;font-weight:800;font-size:30px;line-height:1}}
.big small{{font-size:14px;font-weight:600;color:var(--muted)}}
.kicker{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:8px}}
.pill{{display:inline-flex;align-items:center;font-size:12px;font-weight:600;padding:3px 10px;border-radius:20px;margin:2px 3px 2px 0}}
.p-ok{{background:var(--ok-bg);color:var(--ok)}} .p-warn{{background:var(--warn-bg);color:var(--warn)}}
.p-bad{{background:var(--bad-bg);color:var(--bad)}} .p-n{{background:var(--neutral-bg);color:var(--muted)}}
.tags{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}}
.tag{{background:var(--card);border:1px solid var(--line);border-radius:10px 10px 14px 14px;padding:16px 15px 14px;position:relative;box-shadow:0 1px 3px rgba(20,20,15,.05)}}
.tag::before{{content:'';position:absolute;top:9px;left:50%;transform:translateX(-50%);width:9px;height:9px;border-radius:50%;background:var(--paper);border:1.5px solid var(--line)}}
.tag .rank{{position:absolute;top:8px;right:11px;font-family:'Archivo Expanded';font-weight:800;font-size:13px;color:var(--muted)}}
.tag .chip{{width:100%;height:52px;border-radius:8px;border:1px solid rgba(0,0,0,.12);margin:12px 0 10px}}
.tag h3{{font-family:'Archivo Expanded';font-weight:700;font-size:15px}}
.tag .facts{{font-size:12.5px;color:var(--muted);margin-top:4px}}
.checks{{margin-top:9px;font-size:12.5px}}
.checks div{{display:flex;gap:6px;align-items:baseline;padding:1.5px 0}}
.checks .c{{color:var(--ok);font-weight:700}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:13.5px}}
th{{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);text-align:left;padding:10px 12px;border-bottom:1.5px solid var(--ink);background:#F6F5F1}}
td{{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}}
tr:last-child td{{border-bottom:none}}
td.num{{font-variant-numeric:tabular-nums;font-weight:600;text-align:right;white-space:nowrap}}
.tblwrap{{overflow-x:auto;border-radius:12px}}
.total td{{background:#F6F5F1;font-weight:700}}
.tl{{display:flex;align-items:flex-start;margin:14px 0 4px}}
.tl .step{{flex:1;text-align:center;position:relative;padding-top:16px}}
.tl .step::before{{content:'';position:absolute;top:5px;left:50%;transform:translateX(-50%);width:11px;height:11px;border-radius:50%;background:var(--ink)}}
.tl .step::after{{content:'';position:absolute;top:10px;left:calc(50% + 8px);right:calc(-50% + 8px);height:1.5px;background:var(--line)}}
.tl .step:last-child::after{{display:none}}
.tl b{{display:block;font-size:12.5px}}
.tl span{{font-size:11.5px;color:var(--muted)}}
.tl .hot::before{{background:var(--bad)}}
.bucket{{border-radius:12px;padding:16px 18px;margin-bottom:14px;border:1px solid var(--line)}}
.bucket h3{{font-family:'Archivo Expanded';font-size:14.5px;font-weight:700;margin-bottom:3px}}
.bucket p{{font-size:13px;color:var(--muted);margin-bottom:10px}}
.b-bad{{background:var(--bad-bg);border-color:#EDCFC9}}.b-bad h3{{color:var(--bad)}}
.b-warn{{background:var(--warn-bg);border-color:#EBDCBB}}.b-warn h3{{color:var(--warn)}}
.b-ok{{background:var(--ok-bg);border-color:#CBE2D3}}.b-ok h3{{color:var(--ok)}}
.b-n{{background:var(--neutral-bg)}}.b-n h3{{color:var(--muted)}}
.crow{{display:flex;flex-wrap:wrap;gap:8px}}
.cchip{{display:inline-flex;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 11px;font-size:13px;font-weight:600}}
.cchip small{{font-weight:500;color:var(--muted);margin-left:6px}}
.callout{{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:10px;padding:14px 16px;font-size:13.5px;margin-top:16px}}
.callout b{{display:block;margin-bottom:6px;font-family:'Archivo Expanded'}}
.callout.lila{{border-left-color:#9B59B6;background:#FAF5FF}}
footer{{margin-top:36px;padding-top:14px;border-top:1px solid var(--line);font-size:11.5px;color:var(--muted)}}
@media(max-width:640px){{.g2{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="eyebrow">Somos Cuadro · Logística e Inventarios</div>
  <h1>Tela Jabón Microfibra — Plan de compra y colores</h1>
  <div class="sub">Datos al {_esc(meta['fecha'])} · {meta['meses']} meses de venta (oct-25 a jul-26) · Lead time de la tela: 45 días</div>
</header>

<nav id="tabs" role="tablist">
  <button class="active" data-t="t1">Resumen</button>
  <button data-t="t2">Los 5 colores</button>
  <button data-t="t3">Pedido de tela</button>
  <button data-t="t4">Semáforo por color</button>
</nav>

<section id="t1" class="show">
  <div class="grid g2">
    <div class="card">
      <div class="kicker">Decisión 1 · Colores que nunca pueden faltar</div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 10px">{top5_chips}</div>
      <div class="note">Son los que venden mucho, venden <b>todos los meses</b>, están en todo el catálogo y su inventario no se estanca. Detalle en la pestaña "Los 5 colores".</div>
    </div>
    <div class="card">
      <div class="kicker">Decisión 2 · Pedido de tela a montar</div>
      <div class="big">{total_kg:,.0f} <small>kg · {len(pedidos)} colores</small></div>
      <div style="margin-top:8px">{pedido_pills}</div>
      <div class="note">Montado esta semana, llega a <b>fin de septiembre</b>: justo a tiempo para la temporada Nov–Dic. <b>Lila es la prioridad #1</b> aunque no esté en el top 5 permanente.</div>
    </div>
  </div>

  <h2>Por qué ahora</h2>
  <div class="card">
    <div class="tl">
      <div class="step"><b>Hoy</b><span>Se monta el pedido</span></div>
      <div class="step"><b>Fin de septiembre</b><span>Llega la tela (45 días)</span></div>
      <div class="step"><b>Octubre</b><span>Se corta · abre tienda nueva (+10%)</span></div>
      <div class="step hot"><b>Nov – Dic</b><span>Temporada alta: diciembre vende ~2× un mes normal</span></div>
    </div>
    <div class="note">Rojo y Púrpura hoy tienen <b>cero tela</b>: sin pedido no hay capacidad de reacción ante cualquier faltante.</div>
  </div>

  <div class="callout"><b>Tres pendientes antes de emitir la orden</b>{pend_html}</div>
</section>

<section id="t2">
  <h2>Los 5 colores que no se negocian</h2>
  <p style="font-size:13.5px;color:var(--muted);max-width:760px">Para entrar a esta lista un color tiene que cumplir <b>las 4 pruebas</b>: vender mucho, vender todos los meses (no a golpes), venderse en todo el catálogo (caballero, dama y kids) y que su inventario fluya sin acumularse.</p>
  <div class="tags" style="margin-top:14px">{tags_html}</div>

  <div class="callout lila"><b>¿Y el Lila? Vende muchísimo, pero no entra — y esta es la razón</b>
  El Lila vendió <b>{lila['ventas_total']:,.0f} prendas</b>, que lo pondrían de 4º… pero
  <b>el {lila['pct_mes_pico']:.0f}% de esa venta ocurrió en un solo mes</b>
  (el lanzamiento de MAFE Lila en marzo) y el <b>{lila['pct_dama']:.0f}% es solo dama</b>.
  Es un color de <b>moda</b>: hoy explota, mañana puede girar la tendencia y dejar el inventario varado — exactamente el riesgo que esta lista debe evitar.
  La recomendación es tratarlo como color de temporada con compras puntuales. Eso sí:
  <b>para el pedido de tela de HOY es la prioridad número 1</b>, porque está agotado y la demanda sigue viva.</div>
</section>

<section id="t3">
  <h2>Pedido de tela sugerido — {total_kg:,.0f} kg</h2>
  <p style="font-size:13.5px;color:var(--muted);max-width:780px">Solo se pide lo que la producción va a necesitar de aquí a diciembre y que la tela en almacén no alcanza a cubrir. Negro, Blanco y Azul Marino <b>no aparecen</b> porque sus cortes ya están cubiertos con la tela en almacén.</p>
  <div class="tblwrap" style="margin-top:12px"><table>
    <thead><tr><th>Color</th><th>Código Odoo</th><th style="text-align:right">Kg a pedir</th><th>Por qué</th></tr></thead>
    <tbody>{pedido_rows}</tbody>
  </table></div>

  <h2>Lo que ya está cubierto (y por eso no se pide)</h2>
  <div class="crow">{cubiertos_html}</div>
  <div class="note" style="margin-top:10px">El cálculo considera temporada Nov–Dic, tienda nueva (+10% desde octubre), 5% de merma y stock de seguridad. Detalle técnico en <b>analisis_microfibra_jabon.xlsx</b>.</div>
</section>

<section id="t4">
  <h2>Qué hacer con cada color</h2>
  {sem_html}
</section>

<footer>Fuente: ventas Odoo oct-25 a jul-26 ({meta['ventas_total']:,.0f} u) · inventario PT ({meta['inv_pt']:,.0f} u) · tela MP ({meta['inv_tela']:,.0f} kg). Respaldo técnico: analisis_microfibra_jabon.xlsx.</footer>
</div>
<script>
const tabs=document.querySelectorAll('#tabs button'),secs=document.querySelectorAll('section');
tabs.forEach(b=>b.addEventListener('click',()=>{{
  tabs.forEach(x=>x.classList.remove('active'));secs.forEach(s=>s.classList.remove('show'));
  b.classList.add('active');document.getElementById(b.dataset.t).classList.add('show');
  window.scrollTo({{top:0}});
}}));
</script>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
