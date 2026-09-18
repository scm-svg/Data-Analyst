"""Genera el dashboard HTML de decisión del pedido especial 10K.

Lee metricas.json (lo produce compute.py) y escribe un HTML autocontenido: los datos
van embebidos en el propio archivo, sin dependencias externas ni conexión a internet.

Uso:
    python3 build_dashboard.py [salida.html]
"""
import json
import datetime
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(os.path.join(AQUI, "metricas.json")))
SALIDA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    AQUI, "Dashboard_Pedido_Especial_Escenarios.html")

VEREDICTO = {
    "A": {
        "titulo": "No llega a la fecha",
        "nivel": "malo",
        "resumen": "El pedido completo sale de costura el 15/10 y se entrega el 20/10: 7 días hábiles después del límite. "
                   "Más de la mitad del pedido (520 pzas) queda fuera de fecha.",
        "pros": [
            "Solo se toca la Línea 4: el resto del taller sigue su plan sin cambios.",
            "Es el escenario con menos modelos aplazados (5) y menos piezas afectadas (3.906).",
            "No hay que coordinar cortes ni sublimado por tandas: todo entra de una vez.",
        ],
        "contras": [
            "Entrega el 20/10, 7 días hábiles tarde. Es el único escenario que no llega ni acercándose.",
            "520 de las 1.000 pzas se cosen después del 06/10, la última fecha útil para cumplir.",
            "El pedido ocupa la Línea 4 durante 13 días seguidos: si hay un paro, no hay dónde recuperarlo.",
            "El plan carga 250 pzas de RIO en la Línea 1 la semana del 28/09, pero esa línea ya está comprometida con otro pedido: ese arrastre no es realizable y RIO se atrasaría todavía más.",
            "RIO NS DAMA se va 15 días hábiles (entra a almacén el 16/11 en vez del 26/10).",
        ],
    },
    "B": {
        "titulo": "Se queda corto por 3 días",
        "nivel": "malo",
        "resumen": "Adelantar Running Tank funciona (sale el 23/09), pero el resto se acumula en la Línea 4. "
                   "Mafe DAMA cierra el 09/10 y se entrega el 14/10: 3 días hábiles tarde.",
        "pros": [
            "Running Tank, el modelo más difícil, queda resuelto el 23/09 con 9 días hábiles de margen.",
            "Clásica Cab y Clásica DAMA sí llegan a tiempo (07/10 y 09/10).",
            "Solo 785 de 1.000 pzas quedan dentro de fecha, pero el faltante es un único modelo.",
            "La Línea 1 queda libre la semana del 28/09 para el otro pedido.",
        ],
        "contras": [
            "Entrega el 14/10: 3 días hábiles tarde. 215 pzas de Mafe DAMA no llegan.",
            "La Línea 4 queda tomada 10 días seguidos por el pedido; es el cuello de botella.",
            "RIO CAB se va 8 días hábiles (almacén del 16/10 al 28/10).",
            "Sin margen: cualquier retraso en corte o sublimado empuja más piezas fuera de fecha.",
        ],
    },
    "C": {
        "titulo": "Llega con 2 días de margen",
        "nivel": "bueno",
        "resumen": "Running Tank sale el 23/09 y el resto se reparte entre Líneas 3 y 4 en una sola semana. "
                   "Todo el pedido cierra costura el 02/10 y se entrega el 07/10, dentro del límite.",
        "pros": [
            "Las 1.000 pzas llegan a tiempo, con 2 días hábiles de colchón.",
            "El pedido solo ocupa 7 días de costura repartidos: la carga se absorbe en una semana.",
            "El atraso al resto del taller es el más parejo de todos: ningún modelo se pasa de 5 días hábiles.",
            "La Línea 1 queda libre la semana del 28/09 para el otro pedido.",
            "Si algo se retrasa, quedan Líneas 3 y 4 para recuperar el mismo día.",
        ],
        "contras": [
            "Toca 8 modelos del plan regular (6.831 pzas), el máximo de los cuatro escenarios.",
            "MAR KIDS, RIO CAB y RIO NS se corren 5 días hábiles cada uno.",
            "Exige tener cortadas y sublimadas Clásica y Mafe para el 28/09: dos líneas paradas si el material no llega.",
            "El margen es de solo 2 días hábiles: no cubre un paro largo.",
        ],
    },
    "D": {
        "titulo": "Llega con 3 días de margen",
        "nivel": "bueno",
        "resumen": "Igual que C pero Mafe DAMA se va a la Línea 2. El pedido cierra costura el 01/10 "
                   "y se entrega el 06/10: es la opción más rápida, con 3 días hábiles de colchón.",
        "pros": [
            "La entrega más temprana: 06/10, con 3 días hábiles de margen.",
            "Solo 6 días de costura: es el escenario que menos tiempo mantiene el pedido en planta.",
            "Las 1.000 pzas llegan a tiempo y el pedido queda cerrado antes de octubre.",
            "La Línea 1 queda libre la semana del 28/09 para el otro pedido.",
        ],
        "contras": [
            "Usa 4 líneas a la vez: es el que más desordena el plan regular.",
            "Concentra el golpe en RIO NS DAMA (+12 días hábiles) y RIO NS CAB (+8): entran a almacén en noviembre.",
            "Toca 8 modelos (6.831 pzas), igual que C, pero con atrasos más desiguales.",
            "Ocupar la Línea 2 obliga a mover RIO KIDS y RIO DAMA en plena semana del 28/09.",
        ],
    },
}

RECOMENDACION = """<strong>C y D son los únicos que cumplen el 09/10.</strong> Entre los dos, la diferencia de
entrega es de un solo día (07/10 contra 06/10), pero el reparto del costo es muy distinto: C mueve a ocho modelos
un máximo de 5 días hábiles cada uno, mientras que D gana ese día empujando RIO NS DAMA 12 días hábiles y RIO NS CAB 8,
hasta noviembre. <strong>C es la opción recomendada</strong>: cumple la fecha, deja 2 días de colchón y reparte el
atraso de forma pareja. D solo conviene si se necesita cerrar el pedido antes de octubre y RIO NS puede esperar a
noviembre. A y B quedan descartados: entregan 7 y 3 días hábiles tarde."""

NOMBRES_DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
SEMANAS_VISTA = ["S1", "S2", "S3", "S4", "S5"]


def fecha_corta(iso):
    if not iso or iso == "--":
        return "--"
    y, m, d = iso.split("-")
    return "%s/%s" % (d, m)


def fecha_larga(iso):
    if not iso or iso == "--":
        return "--"
    y, m, d = iso.split("-")
    return "%s/%s/%s" % (d, m, y)


def dia_semana(iso):
    y, m, d = [int(x) for x in iso.split("-")]
    return ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"][datetime.date(y, m, d).weekday()]


payload = {
    "meta": M,
    "veredicto": VEREDICTO,
    "recomendacion": RECOMENDACION,
    "dias": NOMBRES_DIAS,
    "semanas": SEMANAS_VISTA,
}

HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Decisión pedido especial 10K — Planificación de producción</title>
<style>
  :root {
    --azul: #1a56db; --azul-claro: #e8f0fe; --azul-borde: #a8c7fa;
    --verde: #137333; --verde-bg: #e6f4ea; --verde-borde: #a8dab5;
    --rojo: #c5221f; --rojo-bg: #fce8e6; --rojo-borde: #f5b5b3;
    --ambar: #b06000; --ambar-bg: #fef7e0;
    --gris: #5f6368; --gris-bg: #f1f3f4; --borde: #dadce0; --texto: #202124;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: #f6f7f9; color: var(--texto);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    font-size: 15px; line-height: 1.5;
  }
  .wrap { max-width: 1280px; margin: 0 auto; padding: 0 20px 60px; }
  header.top { background: #12203c; color: #fff; padding: 22px 0 0; }
  header.top .wrap { padding-bottom: 0; }
  header.top h1 { margin: 0 0 4px; font-size: 24px; font-weight: 700; }
  header.top .sub { color: #b9c4d8; font-size: 14px; margin-bottom: 16px; }
  .chips { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; }
  .chip {
    background: rgba(255,255,255,.1); border: 1px solid rgba(255,255,255,.2);
    border-radius: 999px; padding: 5px 14px; font-size: 13px; color: #e8eaed;
  }
  .chip b { color: #fff; }
  nav.tabs { display: flex; gap: 2px; flex-wrap: wrap; }
  nav.tabs button {
    background: rgba(255,255,255,.08); color: #cdd6e6; border: 0; cursor: pointer;
    padding: 11px 22px; font-size: 14px; font-weight: 600; font-family: inherit;
    border-radius: 8px 8px 0 0;
  }
  nav.tabs button:hover { background: rgba(255,255,255,.16); color: #fff; }
  nav.tabs button.on { background: #f6f7f9; color: #12203c; }
  section.tab { display: none; padding-top: 24px; }
  section.tab.on { display: block; }
  h2 { font-size: 19px; margin: 30px 0 12px; }
  h2:first-child { margin-top: 6px; }
  h3 { font-size: 15px; margin: 0 0 10px; color: var(--gris); text-transform: uppercase; letter-spacing: .4px; }
  .card { background: #fff; border: 1px solid var(--borde); border-radius: 12px; padding: 18px 20px; }
  .nota { color: var(--gris); font-size: 13.5px; margin: 8px 0 0; }
  .grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  @media (max-width: 900px) { .grid4, .grid2 { grid-template-columns: 1fr; } }

  .vcard { background: #fff; border: 1px solid var(--borde); border-radius: 12px; overflow: hidden; cursor: pointer; }
  .vcard:hover { box-shadow: 0 2px 10px rgba(0,0,0,.09); }
  .vcard .head { padding: 12px 16px; display: flex; align-items: center; gap: 10px; }
  .vcard .letra { font-size: 22px; font-weight: 800; }
  .vcard .estado { font-size: 13px; font-weight: 700; }
  .vcard .body { padding: 14px 16px 16px; }
  .vcard .fecha { font-size: 26px; font-weight: 800; line-height: 1.1; }
  .vcard .fecha small { display: block; font-size: 12px; font-weight: 600; color: var(--gris);
    text-transform: uppercase; letter-spacing: .4px; margin-bottom: 3px; }
  .vcard .txt { font-size: 13.5px; color: var(--gris); margin-top: 10px; }
  .bueno .head { background: var(--verde-bg); color: var(--verde); border-bottom: 1px solid var(--verde-borde); }
  .malo  .head { background: var(--rojo-bg);  color: var(--rojo);  border-bottom: 1px solid var(--rojo-borde); }
  .bueno .fecha { color: var(--verde); }
  .malo  .fecha { color: var(--rojo); }

  table { width: 100%; border-collapse: collapse; background: #fff; font-size: 14px; }
  thead th {
    background: #12203c; color: #fff; text-align: left; padding: 10px 12px;
    font-size: 12.5px; font-weight: 600; text-transform: uppercase; letter-spacing: .3px;
  }
  tbody td { padding: 9px 12px; border-bottom: 1px solid var(--borde); }
  tbody tr:last-child td { border-bottom: 0; }
  tbody tr.destaca td { background: var(--azul-claro); font-weight: 600; }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
  .tablebox { border: 1px solid var(--borde); border-radius: 12px; overflow: hidden; }
  .ok { color: var(--verde); font-weight: 700; }
  .ko { color: var(--rojo); font-weight: 700; }
  .tag { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 12px; font-weight: 700; }
  .tag.ok { background: var(--verde-bg); color: var(--verde); }
  .tag.ko { background: var(--rojo-bg); color: var(--rojo); }
  .tag.mid { background: var(--ambar-bg); color: var(--ambar); }

  .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
  @media (max-width: 900px) { .kpis { grid-template-columns: 1fr 1fr; } }
  .kpi { background: #fff; border: 1px solid var(--borde); border-radius: 12px; padding: 14px 16px; }
  .kpi .lbl { font-size: 12px; color: var(--gris); text-transform: uppercase; letter-spacing: .4px; font-weight: 600; }
  .kpi .val { font-size: 25px; font-weight: 800; margin-top: 4px; line-height: 1.1; }
  .kpi .sub { font-size: 12.5px; color: var(--gris); margin-top: 3px; }

  .timeline { position: relative; }
  .tl-row { display: grid; grid-template-columns: 130px 1fr; align-items: center; gap: 12px; margin-bottom: 10px; }
  .tl-label { font-weight: 700; font-size: 14px; }
  .tl-label small { display: block; font-weight: 500; color: var(--gris); font-size: 12px; }
  .tl-track { position: relative; height: 30px; background: var(--gris-bg); border-radius: 6px; }
  .tl-bar { position: absolute; top: 5px; height: 20px; border-radius: 4px;
    font-size: 11.5px; color: #fff; font-weight: 700; display: flex; align-items: center;
    justify-content: center; white-space: nowrap; }
  .tl-costura { background: var(--azul); }
  .tl-post { background: #9aa7bd; }
  .tl-limite { position: absolute; top: -6px; bottom: -6px; width: 2px; background: var(--rojo); }
  .tl-axis { display: grid; grid-template-columns: 130px 1fr; gap: 12px; margin-top: 4px; }
  .tl-axis-in { position: relative; height: 22px; }
  .tl-tick { position: absolute; font-size: 11px; color: var(--gris); transform: translateX(-50%); white-space: nowrap; }

  .cal { border: 1px solid var(--borde); border-radius: 12px; overflow: hidden; background: #fff; }
  .cal-week { border-bottom: 1px solid var(--borde); }
  .cal-week:last-child { border-bottom: 0; }
  .cal-title { background: #eef1f6; padding: 8px 14px; font-weight: 700; font-size: 13.5px; }
  .cal-title span { color: var(--gris); font-weight: 500; }
  .cal-grid { display: grid; grid-template-columns: 78px repeat(5, 1fr); }
  .cal-grid > div { border-right: 1px solid #eceff3; border-top: 1px solid #eceff3; padding: 6px 8px; min-height: 42px; }
  .cal-grid > div:nth-child(6n) { border-right: 0; }
  .cal-head { background: #fafbfc; font-size: 11.5px; font-weight: 700; color: var(--gris);
    text-transform: uppercase; letter-spacing: .3px; }
  .cal-line { background: #fafbfc; font-weight: 700; font-size: 13px; display: flex; align-items: center; }
  .cal-cell { font-size: 12px; }
  .cal-cell .it { display: block; padding: 2px 6px; border-radius: 4px; margin-bottom: 2px;
    background: var(--gris-bg); color: #3c4043; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .cal-cell .it.esp { background: var(--azul); color: #fff; font-weight: 700; }
  .cal-cell .it b { font-variant-numeric: tabular-nums; }
  .cal-legend { display: flex; gap: 16px; font-size: 12.5px; color: var(--gris); margin-top: 8px; align-items: center; }
  .cal-legend i { display: inline-block; width: 14px; height: 14px; border-radius: 3px; vertical-align: -2px; margin-right: 5px; }

  ul.lista { margin: 0; padding-left: 20px; }
  ul.lista li { margin-bottom: 7px; }
  .pros { border-left: 4px solid var(--verde); }
  .contras { border-left: 4px solid var(--rojo); }
  .pros h3 { color: var(--verde); }
  .contras h3 { color: var(--rojo); }

  .banner { border-radius: 12px; padding: 16px 20px; margin-bottom: 18px; font-size: 14.5px; }
  .banner.bueno { background: var(--verde-bg); border: 1px solid var(--verde-borde); }
  .banner.malo { background: var(--rojo-bg); border: 1px solid var(--rojo-borde); }
  .banner.info { background: var(--azul-claro); border: 1px solid var(--azul-borde); }
  .banner b { font-size: 16px; }

  .barra { height: 9px; background: var(--gris-bg); border-radius: 5px; overflow: hidden; min-width: 70px; }
  .barra i { display: block; height: 100%; background: var(--azul); }
  .barra i.alto { background: var(--rojo); }
</style>
</head>
<body>
<header class="top">
  <div class="wrap">
    <h1>Pedido especial 10K — cuatro formas de meterlo en planta</h1>
    <div class="sub">Comparación contra la planificación actual sin el pedido · Generado el __HOY__</div>
    <div class="chips" id="chips"></div>
    <nav class="tabs" id="tabs"></nav>
  </div>
</header>
<div class="wrap" id="contenido"></div>

<script>
const D = __DATOS__;
const M = D.meta, V = D.veredicto;
const ESC = ["A","B","C","D"];

const fc = iso => (!iso || iso === "--") ? "--" : iso.slice(8,10) + "/" + iso.slice(5,7);
const fl = iso => (!iso || iso === "--") ? "--" : iso.slice(8,10) + "/" + iso.slice(5,7) + "/" + iso.slice(0,4);
const dsem = iso => ["lun","mar","mié","jue","vie","sáb","dom"][new Date(iso + "T00:00:00").getDay() === 0 ? 6 : new Date(iso + "T00:00:00").getDay() - 1];
const n = x => String(Math.round(x || 0)).replace(/\\B(?=(\\d{3})+(?!\\d))/g, ".");
const dias = x => x === 1 ? "1 día hábil" : x + " días hábiles";

function holguraTag(h) {
  if (h > 0) return `<span class="tag ok">${dias(h)} de margen</span>`;
  if (h === 0) return `<span class="tag mid">justo en la fecha</span>`;
  return `<span class="tag ko">${dias(-h)} tarde</span>`;
}

/* ---------- Cabecera ---------- */
document.getElementById("chips").innerHTML = [
  `Pedido: <b>${n(M.pedido_total)} pzas</b> en 4 modelos`,
  `Fecha límite de entrega: <b>${fl(M.limite)}</b>`,
  `Última costura útil: <b>${fl(M.corte_costura)}</b>`,
  `Tras costura: <b>+${M.dias_post_costura} días hábiles</b> hasta estar listo`
].map(t => `<span class="chip">${t}</span>`).join("");

/* ---------- Pestañas ---------- */
const PEST = [["gen","Resumen general"]].concat(ESC.map(k => [k, "Escenario " + k])).concat([["sup","Supuestos"]]);
document.getElementById("tabs").innerHTML = PEST.map(([id,t],i) =>
  `<button data-t="${id}" class="${i===0?"on":""}">${t}</button>`).join("");
document.getElementById("contenido").innerHTML = PEST.map(([id],i) =>
  `<section class="tab ${i===0?"on":""}" id="tab-${id}"></section>`).join("");
document.getElementById("tabs").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return; abrir(b.dataset.t);
});
function abrir(id) {
  document.querySelectorAll("nav.tabs button").forEach(b => b.classList.toggle("on", b.dataset.t === id));
  document.querySelectorAll("section.tab").forEach(s => s.classList.toggle("on", s.id === "tab-" + id));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ---------- Línea de tiempo ---------- */
function timeline() {
  const ini = new Date("2026-09-21T00:00:00");
  const fin = new Date("2026-10-23T00:00:00");
  const span = (fin - ini) / 86400000;
  const pos = iso => ((new Date(iso + "T00:00:00") - ini) / 86400000) / span * 100;
  const lim = pos(M.limite);
  let filas = ESC.map(k => {
    const e = M.escenarios[k], p = e.pedido;
    const a = pos(p.inicio), b = pos(p.fin), c = pos(p.entrega);
    const cls = V[k].nivel;
    return `<div class="tl-row">
      <div class="tl-label">Escenario ${k}<small>${p.a_tiempo ? "entrega " + fc(p.entrega) : "tarde · " + fc(p.entrega)}</small></div>
      <div class="tl-track">
        <div class="tl-bar tl-costura" style="left:${a}%;width:${Math.max(b-a,1.5)}%">costura</div>
        <div class="tl-bar tl-post" style="left:${b}%;width:${Math.max(c-b,1.5)}%">+3 d</div>
        <div class="tl-limite" style="left:${lim}%"></div>
      </div></div>`;
  }).join("");
  const ticks = ["2026-09-21","2026-09-28","2026-10-05","2026-10-09","2026-10-12","2026-10-19"].map(t =>
    `<span class="tl-tick" style="left:${pos(t)}%">${fc(t)}</span>`).join("");
  return `<div class="card"><div class="timeline">${filas}
    <div class="tl-axis"><div></div><div class="tl-axis-in">${ticks}</div></div></div>
    <p class="nota">Azul: días de costura del pedido. Gris: los 3 días hábiles de acabado posteriores.
    La línea roja es el límite del ${fl(M.limite)}.</p></div>`;
}

/* ---------- Calendario por línea y día ---------- */
function calendario(datosSemanas, soloConPedido) {
  const semanas = D.semanas.filter(s => {
    const w = datosSemanas[s]; if (!w) return false;
    return soloConPedido ? w.filas.some(f => f.especial) : true;
  });
  const html = semanas.map(s => {
    const w = datosSemanas[s];
    const cab = D.dias.map((dn,i) => `<div class="cal-grid-head cal-head">${dn} ${fc(w.fechas[i])}</div>`).join("");
    const lineas = ["1","2","3","4","5"].map(L => {
      const celdas = [0,1,2,3,4].map(i => {
        const its = w.filas.filter(f => f.linea === L && f.dias[i] > 0)
          .map(f => `<span class="it ${f.especial?"esp":""}" title="${f.modelo}: ${f.dias[i]} pzas">${f.modelo.replace(" (Especial)","")} <b>${f.dias[i]}</b></span>`).join("");
        return `<div class="cal-cell">${its}</div>`;
      }).join("");
      return `<div class="cal-line">Línea ${L}</div>${celdas}`;
    }).join("");
    const semNum = s.replace("S","");
    const tienePedido = w.filas.some(f => f.especial);
    return `<div class="cal-week">
      <div class="cal-title">Semana ${semNum} <span>· ${fl(w.fechas[0])} al ${fl(w.fechas[4])}${tienePedido?" · con el pedido especial":""}</span></div>
      <div class="cal-grid"><div class="cal-head"></div>${cab}${lineas}</div></div>`;
  }).join("");
  return `<div class="cal">${html}</div>
    <div class="cal-legend"><span><i style="background:#1a56db"></i>Pedido especial 10K</span>
    <span><i style="background:#f1f3f4"></i>Producción regular</span>
    <span>Celda vacía = línea libre ese día</span></div>`;
}

/* ---------- Resumen general ---------- */
function vistaGeneral() {
  const cards = ESC.map(k => {
    const e = M.escenarios[k], p = e.pedido, v = V[k];
    return `<div class="vcard ${v.nivel}" onclick="abrir('${k}')">
      <div class="head"><span class="letra">${k}</span><span class="estado">${v.titulo}</span></div>
      <div class="body">
        <div class="fecha"><small>Pedido listo el</small>${fl(p.entrega)}</div>
        <div style="margin-top:8px">${holguraTag(p.holgura)}</div>
        <div class="txt">Líneas ${e.lineas.join(", ")} · ${n(p.pzas_a_tiempo)} de ${n(p.piezas)} pzas dentro de fecha</div>
      </div></div>`;
  }).join("");

  const maxAplaz = Math.max(...ESC.map(k => M.escenarios[k].impacto.piezas_aplazadas));
  const filas = ESC.map(k => {
    const e = M.escenarios[k], p = e.pedido, im = e.impacto;
    const pct = Math.round(100 * im.piezas_aplazadas / maxAplaz);
    return `<tr class="${p.a_tiempo ? "" : ""}">
      <td><b>${k}</b></td>
      <td>${e.lineas.join(", ")}</td>
      <td>${fl(p.inicio)}</td>
      <td>${fl(p.fin)}</td>
      <td><b class="${p.a_tiempo?"ok":"ko"}">${fl(p.entrega)}</b></td>
      <td>${holguraTag(p.holgura)}</td>
      <td class="num">${p.pct_a_tiempo}%</td>
      <td class="num">${im.n_aplazados}</td>
      <td class="num">${n(im.piezas_aplazadas)}<div class="barra"><i class="${pct>90?"alto":""}" style="width:${pct}%"></i></div></td>
      <td class="num">${im.max_dias}</td></tr>`;
  }).join("");

  const tabla = `<div class="tablebox"><table>
    <thead><tr><th>Esc.</th><th>Líneas</th><th>1ª costura</th><th>Fin costura</th><th>Pedido listo</th>
    <th>Contra el límite</th><th class="num">% a tiempo</th><th class="num">Modelos aplazados</th>
    <th class="num">Pzas aplazadas</th><th class="num">Atraso máx. (d. háb.)</th></tr></thead>
    <tbody>${filas}</tbody></table></div>`;

  const comp = `<div class="tablebox"><table>
    <thead><tr><th>Modelo del pedido</th><th class="num">Piezas</th><th class="num">SKUs</th>
    <th class="num">Capacidad por día</th><th class="num">Días de línea que necesita</th></tr></thead>
    <tbody>${M.pedido.map(p => `<tr><td>${p.modelo}</td><td class="num">${n(p.piezas)}</td>
      <td class="num">${p.skus}</td><td class="num">${p.cap}</td>
      <td class="num">${Math.ceil(p.piezas / p.cap)}</td></tr>`).join("")}
    <tr class="destaca"><td>Total del pedido</td><td class="num">${n(M.pedido_total)}</td>
      <td class="num">${M.pedido.reduce((s,p)=>s+p.skus,0)}</td><td class="num">—</td>
      <td class="num">${M.pedido.reduce((s,p)=>s+Math.ceil(p.piezas/p.cap),0)}</td></tr>
    </tbody></table></div>`;

  return `
  <div class="banner info"><b>La decisión en una línea.</b> Solo los escenarios C y D entregan dentro del
  ${fl(M.limite)}. A llega 7 días hábiles tarde y B, 3. La diferencia entre C y D es un día de entrega,
  pero D carga el atraso sobre RIO NS (hasta 12 días hábiles) y C lo reparte parejo (máximo 5).</div>

  <h2>Qué pasa con el pedido en cada escenario</h2>
  <div class="grid4">${cards}</div>
  <p class="nota">Toca una tarjeta para ver el detalle del escenario.</p>

  <h2>Cuándo estaría listo el pedido</h2>
  ${timeline()}

  <h2>Comparación completa</h2>
  ${tabla}
  <p class="nota">«% a tiempo» son las piezas cosidas hasta el ${fl(M.corte_costura)}, la última fecha que
  permite cumplir el ${fl(M.limite)} sumando los ${M.dias_post_costura} días hábiles de acabado.
  «Modelos aplazados» y «pzas aplazadas» comparan cada escenario contra la planificación sin el pedido.</p>

  <h2>Qué es el pedido</h2>
  ${comp}

  <h2>Recomendación</h2>
  <div class="banner bueno">${D.recomendacion}</div>

  <h2>El plan actual, sin el pedido</h2>
  ${calendario(M.base.semanas, false)}
  <p class="nota">Este es el punto de partida contra el que se comparan los cuatro escenarios.</p>`;
}

/* ---------- Vista de escenario ---------- */
function vistaEscenario(k) {
  const e = M.escenarios[k], p = e.pedido, im = e.impacto, v = V[k];

  const kpis = `<div class="kpis">
    <div class="kpi"><div class="lbl">Pedido listo el</div>
      <div class="val ${p.a_tiempo?"ok":"ko"}">${fl(p.entrega)}</div>
      <div class="sub">costura hasta ${fl(p.fin)} + ${M.dias_post_costura} días hábiles</div></div>
    <div class="kpi"><div class="lbl">Contra el límite ${fc(M.limite)}</div>
      <div class="val ${p.holgura>=0?"ok":"ko"}">${p.holgura>=0?"+":""}${p.holgura} d</div>
      <div class="sub">${p.holgura>=0?"de margen":"de retraso"} (días hábiles)</div></div>
    <div class="kpi"><div class="lbl">Piezas dentro de fecha</div>
      <div class="val">${p.pct_a_tiempo}%</div>
      <div class="sub">${n(p.pzas_a_tiempo)} a tiempo · ${n(p.pzas_tarde)} tarde</div></div>
    <div class="kpi"><div class="lbl">Impacto en el resto</div>
      <div class="val">${im.n_aplazados}</div>
      <div class="sub">modelos aplazados · ${n(im.piezas_aplazadas)} pzas</div></div>
  </div>`;

  const detalle = `<div class="tablebox"><table>
    <thead><tr><th>Modelo del pedido</th><th class="num">Piezas</th><th>Líneas</th>
    <th>Empieza costura</th><th>Termina costura</th><th>Listo</th><th>Contra el límite</th></tr></thead>
    <tbody>${p.modelos.map(m => `<tr>
      <td>${m.modelo}</td><td class="num">${n(m.piezas)}</td><td>${m.lineas.join(" y ")}</td>
      <td>${dsem(m.inicio)} ${fl(m.inicio)}</td><td>${dsem(m.fin)} ${fl(m.fin)}</td>
      <td><b class="${m.holgura>=0?"ok":"ko"}">${fl(m.entrega)}</b></td>
      <td>${holguraTag(m.holgura)}</td></tr>`).join("")}
    <tr class="destaca"><td>Pedido completo</td><td class="num">${n(p.piezas)}</td>
      <td>${e.lineas.join(", ")}</td><td>${fl(p.inicio)}</td><td>${fl(p.fin)}</td>
      <td><b class="${p.a_tiempo?"ok":"ko"}">${fl(p.entrega)}</b></td>
      <td>${holguraTag(p.holgura)}</td></tr></tbody></table></div>`;

  const reparto = `<div class="tablebox"><table>
    <thead><tr><th>Línea</th><th class="num">Piezas del pedido</th>
    <th class="num">Días que la ocupa</th><th class="num">Carga total de la línea (sem. 2 a 4)</th></tr></thead>
    <tbody>${["1","2","3","4","5"].map(L => {
      const pz = p.por_linea[L] || 0;
      if (!pz && !e.ocupacion_pedido[L]) return "";
      return `<tr><td>Línea ${L}</td><td class="num">${n(pz)}</td>
        <td class="num">${e.ocupacion_pedido[L]}</td>
        <td class="num">${n(e.uso.piezas[L])} pzas <span style="color:#5f6368">(sin pedido: ${n(M.base.uso.piezas[L])})</span></td></tr>`;
    }).join("")}</tbody></table></div>`;

  const aplaz = im.aplazados.length ? `<div class="tablebox"><table>
    <thead><tr><th>Modelo aplazado</th><th class="num">Piezas</th><th>Termina sin el pedido</th>
    <th>Termina en este escenario</th><th class="num">Atraso</th><th>Entra a almacén</th></tr></thead>
    <tbody>${im.aplazados.map(f => `<tr>
      <td>${f.modelo}</td><td class="num">${n(f.piezas)}</td>
      <td>${fl(f.fin_base)}</td><td>${fl(f.fin_esc)}</td>
      <td class="num"><span class="tag ${f.dias>=8?"ko":"mid"}">+${f.dias} d</span></td>
      <td>${fl(f.almacen_base)} → <b>${fl(f.almacen_esc)}</b></td></tr>`).join("")}
    </tbody></table></div>` : `<div class="card">Ningún modelo se atrasa.</div>`;

  const adel = im.adelantados.length ? `<p class="nota">Se adelantan: ${im.adelantados.map(f =>
    `${f.modelo} (${-f.dias} d)`).join(", ")}.</p>` : "";

  const l1 = e.linea1_s3.piezas > 0
    ? `<div class="banner malo"><b>Conflicto con la Línea 1.</b> Este plan carga
       ${n(e.linea1_s3.piezas)} pzas de ${e.linea1_s3.modelos.join(" y ")} en la Línea 1 durante la semana
       del 28/09, pero esa línea ya está comprometida con otro pedido. Esa producción no se podrá hacer
       y el atraso del plan regular sería mayor que el mostrado aquí.</div>`
    : `<div class="banner bueno"><b>Línea 1 libre la semana del 28/09.</b> El pedido no la necesita en esa
       semana, así que queda disponible para el otro pedido ya comprometido.</div>`;

  return `
  <div class="banner ${v.nivel}"><b>Escenario ${k} — ${v.titulo}.</b> ${v.resumen}</div>
  <p class="nota" style="margin-top:-8px;margin-bottom:18px">${e.descripcion}</p>
  ${kpis}
  <h2>El pedido, modelo por modelo</h2>
  ${detalle}
  <h2>Cómo se reparte entre las líneas</h2>
  ${reparto}
  ${l1}
  <h2>Calendario de las semanas con el pedido</h2>
  ${calendario(e.semanas, true)}
  <h2>Qué se aplaza frente al plan sin el pedido</h2>
  ${aplaz}
  ${adel}
  <h2>Pros y contras</h2>
  <div class="grid2">
    <div class="card pros"><h3>A favor</h3><ul class="lista">${v.pros.map(x=>`<li>${x}</li>`).join("")}</ul></div>
    <div class="card contras"><h3>En contra</h3><ul class="lista">${v.contras.map(x=>`<li>${x}</li>`).join("")}</ul></div>
  </div>`;
}

/* ---------- Supuestos ---------- */
function vistaSupuestos() {
  return `
  <h2>Cómo leer este informe</h2>
  <div class="card"><ul class="lista">
    <li><b>Fecha límite:</b> ${fl(M.limite)}. Es la fecha en la que el pedido debe estar entregado.</li>
    <li><b>Acabado:</b> después de costura, las piezas de <i>Por Hacer - Especial</i> tardan
      ${M.dias_post_costura} días hábiles en pasar el resto de etapas. Por eso la última costura útil
      es el ${fl(M.corte_costura)}.</li>
    <li><b>Capacidad:</b> la capacidad diaria de cada modelo es la de las máquinas nuevas
      (Clásica 80/día, Mafe 90/día, Running Tank 70/día).</li>
    <li><b>Línea 1:</b> está comprometida con otro pedido la semana del 28/09. Los escenarios B, C y D la
      dejan libre esa semana; el escenario A no.</li>
    <li><b>Atrasos:</b> se miden en días hábiles comparando la fecha estimada de término de cada modelo
      contra la planificación sin el pedido.</li>
    <li><b>Pedido especial:</b> ${n(M.pedido_total)} pzas, 18 SKUs, 4 modelos, cliente 10K.</li>
  </ul></div>

  <h2>Origen de los datos</h2>
  <div class="card"><ul class="lista">
    <li><code>Planificacion sin pedido.xlsx</code> — plan de referencia sin el pedido.</li>
    <li><code>Escenario A/B/C/D.xlsx</code> — un plan generado por cada forma de meter el pedido.</li>
    <li>De cada archivo se leen los tableros semanales (Planificación y Semana 2 a 12), la hoja
      <i>Proyeccion</i> (fecha estimada de término por modelo) y <i>Entrada de Almacen Modelo</i>.</li>
  </ul></div>

  <h2>Diferencia de partida entre escenarios</h2>
  <div class="banner info">El escenario A se generó con el apoyo del 50% de la Línea 1 activo desde la semana 2,
  y los escenarios B, C y D sin él. Por eso en A aparecen RIO DAMA y RIO KIDS produciendo en la Línea 1 durante
  las semanas 2 y 3. Ese apoyo choca con el otro pedido que ya tiene tomada la Línea 1 la semana del 28/09.</div>

  <h2>Configuración cargada en cada escenario</h2>
  ${ESC.map(k => {
    const e = M.escenarios[k];
    const porModelo = {};
    e.config.forEach(c => { porModelo[c.modelo.trim()] = c; });
    return `<h3 style="margin-top:18px">Escenario ${k}</h3>
      <div class="tablebox"><table><thead><tr><th>Modelo</th><th>Líneas asignadas</th>
      <th>Día de inicio</th></tr></thead><tbody>${Object.values(porModelo).map(c =>
      `<tr><td>${c.modelo}</td><td>${c.lineas}</td><td>${fl(c.inicio)}</td></tr>`).join("")}
      </tbody></table></div>`;
  }).join("")}`;
}

document.getElementById("tab-gen").innerHTML = vistaGeneral();
ESC.forEach(k => { document.getElementById("tab-" + k).innerHTML = vistaEscenario(k); });
document.getElementById("tab-sup").innerHTML = vistaSupuestos();
</script>
</body>
</html>
"""

html = HTML.replace("__DATOS__", json.dumps(payload, ensure_ascii=False))
html = html.replace("__HOY__", datetime.date.today().strftime("%d/%m/%Y"))
open(SALIDA, "w", encoding="utf-8").write(html)
print("escrito:", SALIDA, len(html), "bytes")
