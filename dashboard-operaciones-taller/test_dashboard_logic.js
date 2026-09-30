/**
 * Tests de lógica del dashboard de operaciones del taller.
 * Ejecutar: node dashboard-operaciones-taller/test_dashboard_logic.js
 */
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'dashboard_operaciones_taller.html'), 'utf8');

function extractConstArray(name) {
  const re = new RegExp('const ' + name + ' = (\\[[\\s\\S]*?\\]);');
  const m = html.match(re);
  if (!m) throw new Error('No se encontró ' + name);
  return Function('"use strict"; return (' + m[1] + ')')();
}

function categorizeStatus(item) {
  const est = (item.Estatus === null || item.Estatus === undefined) ? '' : String(item.Estatus).trim();
  const teorica = Number(item.Capacidad_Teorica) || 0;
  const real = Number(item.Capacidad_Real) || 0;
  const lower = est.toLowerCase();

  if (lower === 'inactiva') return 'Inactiva';
  if (lower === 'disponible' || lower === 'activa') {
    if (teorica > 0 && real === 0) return 'Inactiva';
    if (teorica > 0 && real > 0 && real < teorica * 0.99) return 'Parcial';
    return 'Activa';
  }

  const numEst = Number(String(est).replace(',', '.'));
  if (est !== '' && !isNaN(numEst)) {
    if (numEst <= 0) return 'Inactiva';
    if (numEst < 1) return 'Parcial';
    return 'Activa';
  }

  if (teorica > 0 && real === 0) return 'Inactiva';
  if (teorica > 0 && real > 0 && real < teorica * 0.99) return 'Parcial';
  if (real > 0) return 'Activa';
  return 'Inactiva';
}

const data = extractConstArray('EMBEDDED_DATA');
const adic = extractConstArray('EMBEDDED_ADICIONALES');
let failed = 0;

function assert(cond, msg) {
  if (!cond) {
    failed += 1;
    console.error('FAIL:', msg);
  } else {
    console.log('OK  :', msg);
  }
}

assert(data.length === 18, '18 operaciones en pestaña principal (got ' + data.length + ')');
assert(adic.length === 4, '4 máquinas adicionales');

const teo = data.reduce((s, i) => s + i.Capacidad_Teorica, 0);
const real = data.reduce((s, i) => s + i.Capacidad_Real, 0);
assert(teo === 4272, 'Teórica total 4272 (got ' + teo + ')');
assert(real === 3744, 'Real total 3744 (got ' + real + ')');
assert(teo - real === 528, 'Diferencia 528');

const cats = { Activa: 0, Parcial: 0, Inactiva: 0 };
data.forEach(i => { cats[categorizeStatus(i)] += 1; });
assert(cats.Activa === 14, '14 activas en líneas (got ' + cats.Activa + ')');
assert(cats.Parcial === 2, '2 parciales (0.8 y 0.5) (got ' + cats.Parcial + ')');
assert(cats.Inactiva === 2, '2 inactivas en líneas (got ' + cats.Inactiva + ')');

const all = data.concat(adic);
const allCats = { Activa: 0, Parcial: 0, Inactiva: 0 };
all.forEach(i => { allCats[categorizeStatus(i)] += 1; });
assert(allCats.Activa === 16, '16 activas incluyendo 2 Rectas (got ' + allCats.Activa + ')');
assert(allCats.Inactiva === 4, '4 inactivas incluyendo 2 Overlock Cuellos (got ' + allCats.Inactiva + ')');
assert(allCats.Parcial === 2, '2 parciales en totalidad');

assert(categorizeStatus({ Estatus: '0.8', Capacidad_Teorica: 188, Capacidad_Real: 150 }) === 'Parcial', '0.8 es Parcial');
assert(categorizeStatus({ Estatus: '0.5', Capacidad_Teorica: 196, Capacidad_Real: 98 }) === 'Parcial', '0.5 es Parcial');
assert(categorizeStatus({ Estatus: 'Disponible', Capacidad_Teorica: 188, Capacidad_Real: 188 }) === 'Activa', 'Disponible es Activa');
assert(categorizeStatus({ Estatus: 'Activa', Capacidad_Teorica: 0, Capacidad_Real: 0 }) === 'Activa', 'Recta Activa sin capacidad sigue Activa');
assert(categorizeStatus({ Estatus: 'Inactiva', Capacidad_Teorica: 196, Capacidad_Real: 0 }) === 'Inactiva', 'Inactiva');

const lineas = new Set(data.map(i => i.Linea));
assert(lineas.size === 4, '4 líneas operativas');
assert([...lineas].every(l => /^Linea [1-4]$/.test(l)), 'nombres Linea 1-4');

const rectas = adic.filter(i => i.Maquina === 'Recta');
const overlocks = adic.filter(i => i.Maquina === 'Overlock Cuellos');
assert(rectas.length === 2 && rectas.every(i => categorizeStatus(i) === 'Activa'), '2 Rectas activas');
assert(overlocks.length === 2 && overlocks.every(i => categorizeStatus(i) === 'Inactiva'), '2 Overlock Cuellos inactivas');

const htmlHas = [
  'capacidadPie',
  'estatusPie',
  'dd-linea',
  'Observaciones',
  '2 Rectas operativas para 4 líneas',
  'no entrarían dentro de la operación diaria',
  'display: false'
];
htmlHas.forEach(s => assert(html.includes(s), 'HTML contiene: ' + s));

assert(/scales:\s*\{[\s\S]*y:\s*cleanScale\(\)/.test(html) || html.includes('y: cleanScale()'), 'eje Y oculto en barras');

if (failed) {
  console.error('\n' + failed + ' fallos');
  process.exit(1);
}
console.log('\nTodos los tests OK');
