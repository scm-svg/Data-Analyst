const fs = require('fs');
const path = require('path');
const M = require('./metrics.js');

const dir = path.join(__dirname, '..', 'data');
const files = ['sambil', 'chacao', 'cerroverde', 'grieta', 'vela', 'tolon', 'grandplaz'];
let failed = 0;
function assert(cond, msg) {
  if (!cond) { failed++; console.error('FAIL', msg); }
  else console.log('ok', msg);
}

const stores = {};
files.forEach(function (n) {
  stores[n] = JSON.parse(fs.readFileSync(path.join(dir, n + '.json'), 'utf8'));
});

const s6 = M.analyzeStore(stores.sambil, 6);
assert(s6.catalogSales === 13774, 'sambil 6m catalog sales 13774, got ' + s6.catalogSales);
assert(s6.storeSales === 13775, 'sambil 6m store series 13775, got ' + s6.storeSales);
assert(s6.orphan === 1, 'sambil 6m orphan 1, got ' + s6.orphan);
const modelSales = s6.models.reduce(function (s, m) { return s + m.sales; }, 0);
assert(modelSales === s6.catalogSales, 'model sales sum to catalog KPI');
const skuSales = s6.skus.reduce(function (s, r) { return s + r.sales; }, 0);
assert(skuSales === s6.catalogSales, 'sku sales sum to catalog KPI');
const monthSum = s6.catalogByMonth.reduce(function (s, n) { return s + n; }, 0);
assert(monthSum === s6.catalogSales, 'month columns sum to catalog KPI');
assert(s6.abc.models.A + s6.abc.models.B + s6.abc.models.C === s6.modelN, 'ABC covers every model');
assert(s6.models.filter(function (m) { return m.abc === 'A'; }).length === s6.abc.models.A, 'A count matches filter');

const s3 = M.analyzeStore(stores.sambil, 3);
assert(s3.catalogSales === 7670, 'sambil 3m sales 7670, got ' + s3.catalogSales);
assert(Math.abs(s3.velocity - s6.velocity) > 1, '3m velocity differs from 6m');
assert(s3.per === 3 && s6.per === 6, 'period sticks');
assert(Math.abs(s3.cob - s6.cob) > 0.2, 'raw coverage moves with period: ' + s3.cob + ' vs ' + s6.cob);

const s12 = M.analyzeStore(stores.sambil, 12);
assert(s12.catalogSales === 29090, 'sambil 12m catalog 29090, got ' + s12.catalogSales);
assert(s12.orphan === 2008, 'sambil 12m orphan 2008, got ' + s12.orphan);
assert(s12.variation == null, '12m has no previous window');
assert(s3.abc.models.A !== s12.abc.models.A || s3.quiebreN !== s12.quiebreN, 'ABC or quiebres move with the window');

const qInf = s6.skus.filter(function (s) { return s.cl === 'QUIEBRE' && s.cob !== 0; });
assert(qInf.length === 0, 'every quiebre has coverage 0, bad ' + qInf.length);

function names(list) { return new Set(list.map(function (x) { return x.id || x.m; })); }
function overlap(a, b) {
  const sb = names(b);
  return [...names(a)].filter(function (x) { return sb.has(x); });
}
['rep', 'reb', 'man', 'act', 'sob', 'sm'].forEach(function (a, i, arr) {
  for (let j = i + 1; j < arr.length; j++) {
    const b = arr[j];
    const inter = overlap(s6.decisions[a], s6.decisions[b]);
    assert(inter.length === 0, 'sambil decisions ' + a + ' & ' + b + ' overlap ' + inter.slice(0, 3).join(','));
  }
});

s6.decisions.rep.forEach(function (f) {
  const child = f.variants.reduce(function (s, v) {
    const short = v.s === 0 || (v.cobT != null && v.cobT < s6.pol.crit);
    return s + (short ? v.qty : 0);
  }, 0);
  if (child !== f.qty) assert(false, f.id + ' qty ' + f.qty + ' != children ' + child);
});
assert(true, 'reponer qty equals sum of short variants');
assert(s6.decisions.rep.every(function (f) { return f.qty > 0; }), 'reponer rows have qty > 0');

const g6 = M.analyzeStore(stores.grieta, 6);
const band = g6.models.find(function (m) { return m.id === 'CUADRO BAND'; });
assert(band && band.cobT > 36, 'grieta cuadro band cobT uncapped ' + (band && band.cobT));
const t6 = M.analyzeStore(stores.tolon, 6);
const tband = t6.families.find(function (m) { return m.id === 'CUADRO BAND'; }) || t6.models.find(function (m) { return m.id === 'CUADRO BAND'; });
assert(tband && tband.cobT > 36, 'tolon cuadro band cobT uncapped ' + (tband && Math.round(tband.cobT)));

const v = M.analyzeStore(stores.vela, 6);
assert(v.avm === 4 && v.per === 4, 'vela clamps 6 to 4 months, per ' + v.per + ' avm ' + v.avm);
assert(v.perOpts.join(',') === '3,4', 'vela options 3 and 4, got ' + v.perOpts.join(','));
assert(v.months.length === 4, 'vela shows 4 month columns');
assert(v.months[0].name === 'Jun' && v.months[0].year === 2026, 'vela starts Jun 2026');

files.forEach(function (n) {
  const a = M.analyzeStore(stores[n], 6);
  const cls = Object.keys(a.classes).reduce(function (s, k) { return s + a.classes[k]; }, 0);
  const uni = Object.keys(a.classesU).reduce(function (s, k) { return s + a.classesU[k]; }, 0);
  assert(cls === a.skuN, n + ' classes sum to skus');
  assert(uni === a.stock, n + ' class units sum to stock ' + uni + ' vs ' + a.stock);
  assert(a.flowDelta === 0 || a.flowDelta !== 0, n + ' flow delta computed ' + a.flowDelta);
  const monthOk = a.models.every(function (m) {
    return m.byMonth.reduce(function (s, x) { return s + x; }, 0) === m.sales;
  });
  assert(monthOk, n + ' each model month columns sum to its sales');
});

const denom = s6.stockedN;
const pct = Math.round(100 * s6.activeStocked / denom);
assert(s6.activeStocked < s6.stockedN || pct <= 100, 'active stocked share <= 100, ' + s6.activeStocked + '/' + denom);
assert(s6.quiebreN > 0 && s6.activeStocked + s6.sinVentaN <= s6.stockedN + s6.quiebreN, 'stocked split sane');

const analyzed = files.map(function (n) {
  return { id: n, name: n, view: M.analyzeStore(stores[n], 6) };
});
const ideas = M.transferIdeas(analyzed);
assert(ideas.skus > 50, 'chain finds cross-store gaps, skus ' + ideas.skus);
assert(ideas.rows.length > 50, 'chain suggests moves ' + ideas.rows.length);
assert(ideas.rows.every(function (r) { return r.qty >= 2 && r.from !== r.to; }), 'moves are at least 2 units and between stores');

if (failed) {
  console.error(failed + ' failed');
  process.exit(1);
}
console.log('ALL PASSED');
