/* Cálculo único de los tableros de tienda.
   Los KPI, las tablas y las decisiones salen de aquí, con la misma ventana. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Metrics = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  const START_YEAR = 2025;
  const START_MONTH_INDEX = 9; // octubre = 9

  function yearOf(i) {
    return START_YEAR + Math.floor((START_MONTH_INDEX + i) / 12);
  }

  function monthMeta(i, meses12) {
    const name = (meses12 && meses12[i]) || '';
    const year = yearOf(i);
    return {
      i: i,
      name: name,
      year: year,
      short: name + ' ' + String(year).slice(2),
      long: name + ' ' + year
    };
  }

  function sum(arr) {
    let s = 0;
    for (let i = 0; i < arr.length; i++) s += arr[i] || 0;
    return s;
  }

  function sumIdx(h, idxs) {
    let s = 0;
    for (let i = 0; i < idxs.length; i++) s += (h && h[idxs[i]]) || 0;
    return s;
  }

  function windowIndices(n) {
    const start = 12 - n;
    const idxs = [];
    for (let i = start; i < 12; i++) idxs.push(i);
    return idxs;
  }

  function avgRel(rel, idxs) {
    let s = 0;
    for (let i = 0; i < idxs.length; i++) s += (rel && rel[idxs[i]] != null) ? rel[idxs[i]] : 1;
    return idxs.length ? s / idxs.length : 1;
  }

  function forwardCoverage(stock, base, rel) {
    if (!(base > 0)) return null;
    let left = stock;
    let months = 0;
    for (let k = 0; k < 600; k++) {
      const rate = base * ((rel && rel[k % 12] != null) ? rel[k % 12] : 1);
      if (!(rate > 0)) return null;
      if (left <= rate) return months + left / rate;
      left -= rate;
      months += 1;
    }
    const rate = base * ((rel && rel[0] != null) ? rel[0] : 1);
    return months + (rate > 0 ? left / rate : 0);
  }

  function baseOf(m) {
    const name = String(m || '');
    const suf = [' CAB', ' DAMA', ' KIDS'];
    for (let i = 0; i < suf.length; i++) {
      if (name.endsWith(suf[i])) return name.slice(0, -suf[i].length);
    }
    return name;
  }

  function classify(stock, sales, cobT, pol) {
    if (stock === 0 && sales > 0) return 'QUIEBRE';
    if (!(sales > 0)) return 'SIN VENTA';
    if (cobT == null) return 'SIN VENTA';
    if (cobT < pol.crit) return 'CRITICO';
    if (cobT <= pol.sano) return 'SALUDABLE';
    if (cobT <= pol.lento) return 'LENTO';
    return 'EXCESO';
  }

  function abcOf(rows, pol) {
    const selling = rows.filter(function (r) { return r.sales > 0; })
      .sort(function (a, b) { return b.sales - a.sales; });
    const tot = selling.reduce(function (s, r) { return s + r.sales; }, 0) || 1;
    const map = {};
    rows.forEach(function (r) { if (!(r.sales > 0)) map[r.id] = 'C'; });
    let acc = 0;
    selling.forEach(function (r) {
      const startShare = acc / tot;
      acc += r.sales;
      const excess = r.cobT != null && r.cobT > pol.lento;
      if (startShare < 0.80 && !excess) map[r.id] = 'A';
      else if (startShare < 0.80 || startShare < 0.95) map[r.id] = 'B';
      else map[r.id] = 'C';
    });
    return map;
  }

  function variantPlan(h, stock, r3, n, pol) {
    const sales = sumIdx(h, windowIndices(n));
    const ritmo = n > 0 ? sales / n : 0;
    const factor = (r3 != null && isFinite(r3) && r3 > 0) ? r3 : 1;
    const target = ritmo * factor * pol.repq;
    const raw = target - stock;
    const qty = raw > 1e-6 ? Math.ceil(raw - 1e-9) : 0;
    return { sales: sales, ritmo: ritmo, factor: factor, target: target, qty: qty };
  }

  function round1(v) {
    if (v == null || !isFinite(v)) return null;
    return Math.round(v * 10) / 10;
  }

  function analyzeStore(D, perRequested) {
    const kpi = D.kpi || {};
    const pol = Object.assign({ crit: 1, sano: 2, lento: 4, exceso: 4, repq: 1.5, ciclo: '' }, kpi.pol || {});
    const rel = kpi.rel && kpi.rel.length === 12 ? kpi.rel : [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1];
    const meses12 = kpi.meses12 || [];
    const first = kpi.first || 0;
    const avm = Math.max(1, 12 - first);
    const per = Math.min(Math.max(1, perRequested || Math.min(6, avm)), avm);
    const idxs = windowIndices(per);
    const relAvg = avgRel(rel, idxs);
    const months = idxs.map(function (i) { return monthMeta(i, meses12); });

    const skus = (D.skus || []).map(function (s) {
      const h = s.h && s.h.length === 12 ? s.h : new Array(12).fill(0);
      const sales = sumIdx(h, idxs);
      const sales12 = sum(h);
      const ritmo = sales / per;
      const base = relAvg > 0 ? ritmo / relAvg : ritmo;
      const stock = s.s || 0;
      let cob = null;
      let cobT = null;
      if (stock === 0 && sales > 0) {
        cob = 0;
        cobT = 0;
      } else if (ritmo > 0) {
        cob = stock / ritmo;
        cobT = forwardCoverage(stock, base, rel);
      }
      const cl = classify(stock, sales, cobT, pol);
      const plan = variantPlan(h, stock, s.r3, per, pol);
      const byMonth = idxs.map(function (i) { return h[i] || 0; });
      return {
        k: s.k, m: s.m, col: s.col || '', t: s.t || '', cat: s.cat || '',
        s: stock, h: h, byMonth: byMonth,
        sales: sales, sales12: sales12,
        ritmo: ritmo, cob: cob, cobT: cobT, cl: cl,
        r3: plan.factor, target: plan.target, qty: plan.qty,
        base: baseOf(s.m)
      };
    });

    const storeSeries = (kpi.vta_m12 && kpi.vta_m12.length === 12) ? kpi.vta_m12 : skus.reduce(function (acc, s) {
      s.h.forEach(function (v, i) { acc[i] += v; });
      return acc;
    }, new Array(12).fill(0));
    const catalogAll = new Array(12).fill(0);
    skus.forEach(function (s) {
      for (let i = 0; i < 12; i++) catalogAll[i] += s.h[i] || 0;
    });
    const catalogByMonth = idxs.map(function (i) {
      let s = 0;
      for (let k = 0; k < skus.length; k++) s += skus[k].h[i] || 0;
      return s;
    });
    const storeByMonth = idxs.map(function (i) { return storeSeries[i] || 0; });
    const catalogSales = sum(catalogByMonth);
    const storeSales = sum(storeByMonth);
    const orphan = storeSales - catalogSales;
    const stock = skus.reduce(function (s, r) { return s + r.s; }, 0);
    const stocked = skus.filter(function (r) { return r.s > 0; });
    const activeStocked = stocked.filter(function (r) { return r.sales > 0; });
    const quiebres = skus.filter(function (r) { return r.cl === 'QUIEBRE'; });
    const velocity = per > 0 ? catalogSales / per : 0;
    const baseStore = relAvg > 0 ? velocity / relAvg : velocity;
    const cob = velocity > 0 ? stock / velocity : null;
    const cobT = velocity > 0 ? forwardCoverage(stock, baseStore, rel) : null;
    const sellThrough = (catalogSales + stock) > 0 ? 100 * catalogSales / (catalogSales + stock) : 0;

    const prevStart = 12 - per - per;
    let variation = null;
    let variationLabel = '';
    if (prevStart >= first) {
      const prevIdx = [];
      for (let i = prevStart; i < prevStart + per; i++) prevIdx.push(i);
      const prevSales = skus.reduce(function (s, r) { return s + sumIdx(r.h, prevIdx); }, 0);
      const curName = monthMeta(idxs[0], meses12).name + '–' + monthMeta(idxs[idxs.length - 1], meses12).name;
      const prevName = monthMeta(prevIdx[0], meses12).name + '–' + monthMeta(prevIdx[prevIdx.length - 1], meses12).name;
      variationLabel = curName + ' vs ' + prevName;
      variation = prevSales > 0 ? 100 * (catalogSales - prevSales) / prevSales : null;
    } else {
      variationLabel = 'sin un período anterior del mismo largo';
    }

    function group(keyFn) {
      const map = {};
      skus.forEach(function (s) {
        const id = keyFn(s);
        if (!map[id]) {
          map[id] = {
            id: id, sales: 0, sales12: 0, s: 0, variants: [],
            byMonth: idxs.map(function () { return 0; }),
            h: new Array(12).fill(0)
          };
        }
        const g = map[id];
        g.sales += s.sales;
        g.sales12 += s.sales12;
        g.s += s.s;
        g.variants.push(s);
        for (let i = 0; i < idxs.length; i++) g.byMonth[i] += s.byMonth[i];
        for (let i = 0; i < 12; i++) g.h[i] += s.h[i] || 0;
      });
      return Object.keys(map).map(function (id) {
        const g = map[id];
        const ritmo = g.sales / per;
        const base = relAvg > 0 ? ritmo / relAvg : ritmo;
        let cobG = null;
        let cobTG = null;
        if (g.s === 0 && g.sales > 0) { cobG = 0; cobTG = 0; }
        else if (ritmo > 0) {
          cobG = g.s / ritmo;
          cobTG = forwardCoverage(g.s, base, rel);
        }
        const cl = classify(g.s, g.sales, cobTG, pol);
        const q = g.variants.filter(function (v) { return v.cl === 'QUIEBRE'; }).length;
        const qty = g.variants.reduce(function (s, v) {
          const short = v.s === 0 || (v.cobT != null && v.cobT < pol.crit);
          return s + (short ? v.qty : 0);
        }, 0);
        const holes = g.variants.filter(function (v) { return v.s === 0 && v.sales >= 3; })
          .sort(function (a, b) { return b.sales - a.sales; });
        const donors = g.variants.filter(function (v) {
          return v.s > 0 && v.cobT != null && v.cobT > pol.lento;
        }).sort(function (a, b) { return b.s - a.s; });
        return {
          id: id, m: id, sales: g.sales, sales12: g.sales12, s: g.s,
          byMonth: g.byMonth, h: g.h, variants: g.variants,
          k: g.variants.length, ritmo: ritmo, cob: cobG, cobT: cobTG, cl: cl,
          q: q, qty: qty, holes: holes, donors: donors,
          sv: g.sales === 0
        };
      });
    }

    const models = group(function (s) { return s.m; });
    const families = group(function (s) { return s.base; });
    const abcModel = abcOf(models.map(function (m) { return { id: m.id, sales: m.sales, cobT: m.cobT }; }), pol);
    const abcFamily = abcOf(families.map(function (m) { return { id: m.id, sales: m.sales, cobT: m.cobT }; }), pol);
    models.forEach(function (m) { m.abc = abcModel[m.id] || 'C'; m.sv = m.sales === 0; });
    families.forEach(function (m) { m.abc = abcFamily[m.id] || 'C'; });
    const abcCount = { A: 0, B: 0, C: 0, sv: 0 };
    models.forEach(function (m) {
      abcCount[m.abc] += 1;
      if (m.sv) abcCount.sv += 1;
    });
    const famCount = { A: 0, B: 0, C: 0 };
    families.forEach(function (m) { famCount[m.abc] += 1; });
    const chips = models.filter(function (m) { return m.abc === 'A'; })
      .sort(function (a, b) { return b.sales - a.sales; })
      .slice(0, 12)
      .map(function (m) { return m.id; });

    const classes = { QUIEBRE: 0, CRITICO: 0, SALUDABLE: 0, LENTO: 0, EXCESO: 0, 'SIN VENTA': 0 };
    const classesU = { QUIEBRE: 0, CRITICO: 0, SALUDABLE: 0, LENTO: 0, EXCESO: 0, 'SIN VENTA': 0 };
    skus.forEach(function (s) {
      classes[s.cl] += 1;
      classesU[s.cl] += s.s;
    });

    const decisions = { rep: [], reb: [], man: [], act: [], sob: [], sm: [], quiebres: [], marg: [] };
    families.forEach(function (f) {
      const excessFamily = f.cobT != null && f.cobT > pol.lento;
      const hasHole = f.holes.length > 0;
      const hasDonor = f.donors.length > 0;
      if (hasHole && hasDonor && f.cobT != null && f.cobT > pol.sano) {
        decisions.reb.push(f);
        return;
      }
      if (f.qty > 0 && f.ritmo >= 2 && (f.cobT == null || f.cobT < pol.crit || f.holes.length > 0)) {
        decisions.rep.push(f);
        return;
      }
      if (f.sales > 0 && f.cobT != null && f.cobT >= pol.crit && f.cobT <= pol.sano) {
        decisions.man.push(f);
        return;
      }
      if (f.sales > 0 && excessFamily && f.s >= 100) {
        decisions.act.push(f);
        return;
      }
      if (f.sales > 0 && excessFamily) {
        decisions.sob.push(f);
        return;
      }
      if (f.sales === 0 && f.s > 0) decisions.sm.push(f);
    });
    const bySales = function (a, b) { return b.sales - a.sales; };
    const byStock = function (a, b) { return b.s - a.s; };
    const byQty = function (a, b) { return b.qty - a.qty || b.sales - a.sales; };
    decisions.rep.sort(byQty);
    decisions.reb.sort(byStock);
    decisions.man.sort(bySales);
    decisions.act.sort(byStock);
    decisions.sob.sort(byStock);
    decisions.sm.sort(byStock);

    const modelAbc = {};
    models.forEach(function (m) { modelAbc[m.id] = m.abc; });
    skus.forEach(function (s) {
      if (s.cl === 'QUIEBRE' && s.sales >= 3 && (modelAbc[s.m] === 'A' || modelAbc[s.m] === 'B')) {
        s.abc = modelAbc[s.m];
        decisions.quiebres.push(s);
      } else if (s.cl === 'QUIEBRE' && s.sales > 0 && s.sales < 3) {
        decisions.marg.push(s);
      }
    });
    models.forEach(function (m) {
      if (m.s === 0 && m.sales > 0 && m.sales < 3) {
        decisions.marg.push({ k: '', m: m.id, col: '', t: '', sales: m.sales, s: 0, whole: true });
      }
    });
    const rebBases = {};
    decisions.reb.forEach(function (f) { rebBases[f.id] = 1; });
    decisions.quiebres = decisions.quiebres.filter(function (s) { return !rebBases[s.base]; });
    decisions.quiebres.sort(bySales);
    decisions.marg.sort(bySales);

    const flow = kpi.flow || null;
    const flowActual = flow && flow.actual != null ? flow.actual : null;
    const flowDelta = flowActual == null ? null : stock - flowActual;

    const perOpts = [];
    [3, 6, 12].forEach(function (n) {
      const v = Math.min(n, avm);
      if (perOpts.indexOf(v) === -1) perOpts.push(v);
    });

    return {
      per: per, avm: avm, perOpts: perOpts, pol: pol, relAvg: relAvg,
      first: first, meses12: meses12, season: kpi.season || {},
      months: months, catalogAll: catalogAll, catalogByMonth: catalogByMonth, storeByMonth: storeByMonth,
      catalogSales: catalogSales, storeSales: storeSales, orphan: orphan,
      stock: stock, skuN: skus.length, modelN: models.length, familyN: families.length,
      stockedN: stocked.length, activeStocked: activeStocked.length,
      quiebreN: quiebres.length,
      quiebreSales: quiebres.reduce(function (s, r) { return s + r.sales; }, 0),
      sinVentaU: classesU['SIN VENTA'], sinVentaN: classes['SIN VENTA'],
      sinMovFamilies: decisions.sm.length,
      velocity: velocity, cob: cob, cobT: cobT, sellThrough: sellThrough,
      variation: variation, variationLabel: variationLabel,
      bigExcl: kpi.big_excl || 0,
      classes: classes, classesU: classesU,
      skus: skus, models: models, families: families,
      abc: { models: abcCount, families: famCount, chips: chips },
      decisions: decisions,
      flow: flow, flowDelta: flowDelta,
      storeMonths: idxs.map(function (i) { return monthMeta(i, meses12); })
    };
  }

  function periodChoices(avm) {
    const out = [];
    [3, 6, 12].forEach(function (n) {
      const v = Math.min(n, avm);
      if (out.indexOf(v) === -1) out.push(v);
    });
    return out;
  }

  function transferIdeas(stores) {
    const by = new Map();
    stores.forEach(function (st) {
      st.view.skus.forEach(function (s) {
        if (!by.has(s.k)) by.set(s.k, []);
        by.get(s.k).push({ st: st, sku: s });
      });
    });
    const skuKeys = new Set();
    const rows = [];
    by.forEach(function (list, key) {
      const holes = [];
      const donors = [];
      list.forEach(function (row) {
        const sku = row.sku;
        const st = row.st;
        if (sku.cl === 'QUIEBRE' && sku.sales >= 3) holes.push(row);
        if (sku.s >= 3 && sku.cobT != null && sku.cobT > st.view.pol.lento) donors.push(row);
      });
      if (!holes.length || !donors.length) return;
      skuKeys.add(key);
      holes.forEach(function (h) {
        donors.forEach(function (d) {
          const give = Math.floor(Math.max(0, d.sku.s - d.sku.target));
          const take = Math.max(h.sku.qty, 1);
          const qty = Math.min(give, take);
          if (qty < 2) return;
          rows.push({
            k: key, m: h.sku.m, col: h.sku.col, t: h.sku.t,
            from: d.st.name, to: h.st.name, fromId: d.st.id, toId: h.st.id,
            qty: qty, fromStock: d.sku.s, toSales: h.sku.sales,
            fromCob: d.sku.cobT
          });
        });
      });
    });
    rows.sort(function (a, b) { return b.qty - a.qty || b.toSales - a.toSales; });
    return { skus: skuKeys.size, rows: rows };
  }

  return {
    yearOf: yearOf,
    monthMeta: monthMeta,
    baseOf: baseOf,
    classify: classify,
    forwardCoverage: forwardCoverage,
    analyzeStore: analyzeStore,
    transferIdeas: transferIdeas,
    periodChoices: periodChoices,
    round1: round1,
    windowIndices: windowIndices
  };
});
