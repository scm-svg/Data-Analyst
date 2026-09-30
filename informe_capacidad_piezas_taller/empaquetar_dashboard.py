"""
Empaqueta el dashboard en un único HTML autocontenido.

El dashboard original cargaba Chart.js, el plugin de datalabels y los datos
desde archivos externos. Al abrir el HTML desde GitHub, htmlpreview o como
archivo suelto esos scripts no llegan: DATA y Chart quedan indefinidos, el
JS se detiene y no se ve ningún dato ni responde ningún botón.

Este script incrusta las tres dependencias y endurece el arranque.
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE / "dashboard_capacidad_piezas.src.html"
HTML = BASE / "dashboard_capacidad_piezas.html"

html = SRC.read_text(encoding="utf-8")

chart = (BASE / "vendor" / "chart.umd.min.js").read_text(encoding="utf-8")
plugin = (BASE / "vendor" / "chartjs-plugin-datalabels.min.js").read_text(encoding="utf-8")
datos = (BASE / "datos_modelo.js").read_text(encoding="utf-8")

OLD_SCRIPTS = """<script src="vendor/chart.umd.min.js"></script>
<script src="vendor/chartjs-plugin-datalabels.min.js"></script>
<script src="datos_modelo.js"></script>"""

NEW_SCRIPTS = f"""<!-- Autocontenido: Chart.js + plugin + datos incrustados.
     No depende de vendor/ ni de datos_modelo.js para funcionar. -->
<script>{chart}
</script>
<script>{plugin}
</script>
<script>
{datos}
</script>"""

if OLD_SCRIPTS not in html:
    raise SystemExit("No se encontraron las etiquetas de script externas a reemplazar.")

html = html.replace(OLD_SCRIPTS, NEW_SCRIPTS)

# Arranque defensivo: si Chart o DATA fallan, los botones siguen vivos.
OLD_BOOT = """Chart.register(ChartDataLabels);
Chart.defaults.set('plugins.datalabels', {display:false});"""

NEW_BOOT = """(function bootCharts(){
  if (typeof Chart === 'undefined') {
    console.error('Chart.js no cargó. Los gráficos no se pintarán.');
    return;
  }
  if (typeof ChartDataLabels !== 'undefined') {
    try { Chart.register(ChartDataLabels); } catch (e) { console.warn(e); }
  }
  try {
    if (Chart.defaults && typeof Chart.defaults.set === 'function') {
      Chart.defaults.set('plugins.datalabels', {display:false});
    } else if (Chart.defaults && Chart.defaults.plugins) {
      Chart.defaults.plugins.datalabels = {display:false};
    }
  } catch (e) { console.warn(e); }
})();"""

if OLD_BOOT not in html:
    raise SystemExit("No se encontró el arranque de Chart.js a reemplazar.")
html = html.replace(OLD_BOOT, NEW_BOOT)

# Mover los handlers de pestañas/tema ANTES de pintar, y envolver el pintado.
OLD_TAIL = """document.querySelectorAll('.tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('on'));
  document.querySelectorAll('.page').forEach(x => x.classList.remove('on'));
  t.classList.add('on');
  document.getElementById(t.dataset.p).classList.add('on');
  Object.values(charts).forEach(c => c.resize());
});

document.getElementById('theme').onclick = () => {
  document.body.classList.toggle('light');
  document.getElementById('theme').textContent =
    document.body.classList.contains('light') ? 'Modo oscuro' : 'Modo claro';
  pintaTodo();
};

pintaTodo();
</script>"""

NEW_TAIL = """function wireUi(){
  document.querySelectorAll('.tab').forEach(t => t.onclick = () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('on'));
    document.querySelectorAll('.page').forEach(x => x.classList.remove('on'));
    t.classList.add('on');
    const page = document.getElementById(t.dataset.p);
    if (page) page.classList.add('on');
    Object.values(charts).forEach(c => { try { c.resize(); } catch (e) {} });
  });
  const themeBtn = document.getElementById('theme');
  if (themeBtn) themeBtn.onclick = () => {
    document.body.classList.toggle('light');
    themeBtn.textContent =
      document.body.classList.contains('light') ? 'Modo oscuro' : 'Modo claro';
    try { pintaTodo(); } catch (e) { console.error(e); }
  };
}

wireUi();
if (typeof DATA === 'undefined') {
  console.error('DATA no está definido. El modelo no se cargó.');
  document.getElementById('kpis').innerHTML =
    '<div class="kpi b"><div class="n">Sin datos</div><div class="l">El modelo no se cargó en este archivo.</div></div>';
} else if (typeof Chart === 'undefined') {
  console.error('Chart.js no está definido.');
} else {
  try { pintaTodo(); }
  catch (e) { console.error('Error al pintar el dashboard:', e); }
}
</script>"""

if OLD_TAIL not in html:
    raise SystemExit("No se encontró el bloque final de handlers a reemplazar.")
html = html.replace(OLD_TAIL, NEW_TAIL)

HTML.write_text(html, encoding="utf-8")
print(f"Escrito {HTML} ({HTML.stat().st_size // 1024} KB)")
