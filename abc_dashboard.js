/* Matriz ABC — dashboard compacto */
(function (global) {
  "use strict";

  const ABC = {
    A: { color: "#22d3ee", label: "Intocable" },
    B: { color: "#fbbf24", label: "Clase media" },
    C: { color: "#f472b6", label: "Lastre" },
  };
  const XYZ = {
    X: { color: "#34d399", label: "Estable", hint: "Demanda predecible — CV ≤ 0.5" },
    Y: { color: "#fbbf24", label: "Variable", hint: "Demanda moderada — CV ≤ 1.0" },
    Z: { color: "#f87171", label: "Impredecible", hint: "Demanda muy irregular — CV > 1.0" },
  };
  const TH = { A: 0.8, B: 0.95 };

  let DATA = null;
  let charts = {};
  let state = {
    timePreset: "all",
    customPeriodKeys: new Set(),
    modelo: "",
    store: "",
    category: "",
    location: "",
    abcClass: "",
    search: "",
    expandedModels: new Set(),
    expandedAlertModels: new Set(),
    expandedSinVentaModels: new Set(),
  };
  let filtersInitialized = false;

  if (typeof Chart !== "undefined" && Chart.register && global.ChartDataLabels) {
    try {
      Chart.register(global.ChartDataLabels);
    } catch (e) {
      /* plugin opcional */
    }
  }

  function $(id) {
    return document.getElementById(id);
  }

  function fmt(n, dec) {
    if (n == null || isNaN(n)) return "—";
    return n.toLocaleString("es-VE", {
      minimumFractionDigits: dec ?? 0,
      maximumFractionDigits: dec ?? 0,
    });
  }

  function fmtMoney(n) {
    if (n == null || isNaN(n)) return "—";
    const abs = Math.abs(n);
    if (abs >= 1e6) return "$" + (n / 1e6).toFixed(2) + "M";
    if (abs >= 1e3) return "$" + (n / 1e3).toFixed(1) + "K";
    return "$" + fmt(n, 0);
  }

  function fmtUsd(n) {
    return fmtMoney(n);
  }

  function pct(n) {
    return (n * 100).toFixed(1) + "%";
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  function destroyChart(key) {
    if (charts[key]) {
      charts[key].destroy();
      charts[key] = null;
    }
  }

  function skuMeta(sku) {
    return DATA.skuMaster[sku] || {};
  }

  function passesSkuFilter(sku) {
    const m = skuMeta(sku);
    if (state.modelo && (m.modelo || m.producto) !== state.modelo) return false;
    return true;
  }

  function allPeriodKeysOrdered() {
    return DATA ? DATA.periods.map((p) => p.key) : [];
  }

  function activePeriodKeys() {
    const ordered = allPeriodKeysOrdered();
    if (!ordered.length) return [];
    if (state.timePreset === "last3") return ordered.slice(-3);
    if (state.timePreset === "last6") return ordered.slice(-6);
    if (state.timePreset === "last12") return ordered.slice(-12);
    if (state.timePreset === "custom") {
      if (!state.customPeriodKeys.size) return [];
      return ordered.filter((k) => state.customPeriodKeys.has(k));
    }
    return ordered;
  }

  function setTimePreset(preset) {
    state.timePreset = preset;
    if (preset !== "custom") state.customPeriodKeys.clear();
    buildPeriodFilters();
    refresh();
  }

  function togglePeriodKey(key) {
    if (state.timePreset !== "custom") {
      state.customPeriodKeys = new Set(activePeriodKeys());
      state.timePreset = "custom";
    }
    if (state.customPeriodKeys.has(key)) state.customPeriodKeys.delete(key);
    else state.customPeriodKeys.add(key);
    if (state.customPeriodKeys.size === 0) state.timePreset = "all";
    else if (state.customPeriodKeys.size === DATA.periods.length) {
      state.timePreset = "all";
      state.customPeriodKeys.clear();
    }
    buildPeriodFilters();
    refresh();
  }

  function variantInfo(sku) {
    const m = skuMeta(sku);
    return {
      modelo: m.modelo || m.producto || sku,
      genero: m.genero || "—",
      color: m.color || "—",
      talla: m.talla || "—",
      label: [m.modelo || m.producto, m.genero, m.color, m.talla]
        .filter(Boolean)
        .join(" · "),
    };
  }

  function skuIsActive(it, stock) {
    return (
      it.qty !== 0 ||
      it.revenue !== 0 ||
      it.margin !== 0 ||
      (stock || 0) > 0
    );
  }

  function aggregateSalesScope(periodKeys) {
    const skuMap = new Map();
    const periodSet = new Set(periodKeys);
    const skus = DATA.skus;
    for (let i = 0; i < DATA.salesRows.length; i++) {
      const r = DATA.salesRows[i];
      if (!periodSet.has(DATA.periods[r[0]].key)) continue;
      if (state.store && DATA.stores[r[2]] !== state.store) continue;
      if (state.category && DATA.categories[r[3]] !== state.category) continue;
      const sku = skus[r[1]];
      if (!skuMap.has(sku)) {
        const m = skuMeta(sku);
        skuMap.set(sku, {
          sku,
          producto: m.producto || sku,
          modelo: m.modelo || m.producto || sku,
          categoria: m.categoria || "",
          genero: m.genero || "",
          color: m.color || "",
          talla: m.talla || "",
          qty: 0,
          revenue: 0,
          cost: 0,
          margin: 0,
        });
      }
      const o = skuMap.get(sku);
      o.qty += r[4];
      o.revenue += r[5];
      o.cost += r[6];
      o.margin += r[7];
    }
    return skuMap;
  }

  function aggregateSales(periodKeys) {
    const map = aggregateSalesScope(periodKeys);
    if (!state.modelo) return map;
    const out = new Map();
    map.forEach((v, sku) => {
      if (passesSkuFilter(sku)) out.set(sku, v);
    });
    return out;
  }

  /** Ventas del período + SKUs con stock (universo activo completo para ABC). */
  function fullActiveScope(periodKeys, invMap) {
    const map = aggregateSalesScope(periodKeys);
    DATA.skus.forEach((sku) => {
      if (map.has(sku)) return;
      const stock = invMap.get(sku)?.total || 0;
      if (stock <= 0) return;
      if (state.store || state.category) return;
      if (!passesSkuFilter(sku)) return;
      const m = skuMeta(sku);
      map.set(sku, {
        sku,
        producto: m.producto || sku,
        modelo: m.modelo || m.producto || sku,
        categoria: m.categoria || "",
        genero: m.genero || "",
        color: m.color || "",
        talla: m.talla || "",
        qty: 0,
        revenue: 0,
        cost: 0,
        margin: 0,
      });
    });
    return map;
  }

  function inventoryBySku(scopeOnly, applyLocationFilter) {
    const useLoc = applyLocationFilter !== false;
    const map = new Map();
    DATA.skus.forEach((sku) => map.set(sku, { total: 0 }));
    for (let i = 0; i < DATA.invRows.length; i++) {
      const r = DATA.invRows[i];
      const sku = DATA.skus[r[0]];
      const loc = DATA.locations[r[1]];
      if (useLoc && state.location && loc !== state.location) continue;
      if (!scopeOnly && state.modelo && !passesSkuFilter(sku)) continue;
      map.get(sku).total += r[2];
    }
    return map;
  }

  function locationsForFilter() {
    const totals = {};
    DATA.invRows.forEach((r) => {
      const loc = DATA.locations[r[1]];
      totals[loc] = (totals[loc] || 0) + r[2];
    });
    return DATA.locations.filter((loc) => {
      if (loc === "Sin inventario" || loc === "Transito") return false;
      return (totals[loc] || 0) > 0;
    });
  }

  /** Excluye ventas con ingresos netos negativos (ej. MAR con margen en rojo). */
  function hasNegativeNetIncome(it) {
    return it.revenue > 0 && it.margin <= 0;
  }

  function assignAbcPareto(items, valueKey, classKey, extra) {
    const pos = items
      .filter((x) => x[valueKey] > 0)
      .sort((a, b) => b[valueKey] - a[valueKey]);
    const total = pos.reduce((s, x) => s + x[valueKey], 0);
    let cum = 0;
    pos.forEach((it, idx) => {
      cum += it[valueKey];
      const cumPct = total > 0 ? cum / total : 1;
      let cls = "C";
      if (cumPct <= TH.A) cls = "A";
      else if (cumPct <= TH.B) cls = "B";
      it[classKey] = cls;
      if (extra) {
        extra.rank && (it[extra.rank] = idx + 1);
        extra.share && (it[extra.share] = total > 0 ? it[valueKey] / total : 0);
        extra.cum && (it[extra.cum] = cumPct);
      }
    });
    items.forEach((it) => {
      if (!it[classKey]) it[classKey] = "C";
    });
  }

  function buildModelIndex(scopeSkuMap, invMap, periodKeys) {
    const keys = periodKeys || activePeriodKeys();
    const models = new Map();
    scopeSkuMap.forEach((it, sku) => {
      const stock = invMap ? invMap.get(sku)?.total || 0 : 0;
      if (hasNegativeNetIncome(it)) return;
      if (it.revenue <= 0 && stock <= 0) return;
      const key = it.modelo || it.producto;
      if (!models.has(key)) {
        models.set(key, {
          modelo: key,
          skus: [],
          qty: 0,
          revenue: 0,
          margin: 0,
          stock: 0,
        });
      }
      const m = models.get(key);
      const meta = skuMeta(sku);
      m.skus.push({ ...it, sku, stock, xyz: meta.xyz || "Z", cv: meta.cv || 0 });
      m.qty += it.qty;
      m.revenue += it.revenue;
      m.margin += it.margin;
      m.stock += stock;
    });
    const all = [...models.values()].filter((m) => !hasNegativeNetIncome(m));
    const ranked = all.filter((m) => m.revenue > 0);
    assignAbcPareto(ranked, "revenue", "abcClass", {
      rank: "rank",
      share: "revenueShare",
      cum: "cumPct",
    });
    all.forEach((m) => {
      const qtys = modelMonthlyQty(m.modelo, keys);
      const { cv, xyz } = cvFromMonthly(qtys);
      m.xyzClass = xyz;
      m.cv = cv;
      m.marginPctProd = m.revenue > 0 ? m.margin / m.revenue : 0;
      if (m.revenue <= 0) {
        m.abcClass = "C";
        m.revenueShare = 0;
        m.rank = null;
      }
      m.matrix = m.abcClass + m.xyzClass;
    });
    ranked.sort((a, b) => (a.rank || 99999) - (b.rank || 99999));
    return all.sort((a, b) => b.revenue - a.revenue || b.stock - a.stock);
  }

  function modelMonthlyQty(modelo, periodKeys) {
    const periodSet = new Set(periodKeys);
    const qtys = DATA.periods.map(() => 0);
    for (let i = 0; i < DATA.salesRows.length; i++) {
      const r = DATA.salesRows[i];
      if (!periodSet.has(DATA.periods[r[0]].key)) continue;
      if (state.store && DATA.stores[r[2]] !== state.store) continue;
      if (state.category && DATA.categories[r[3]] !== state.category) continue;
      const sku = DATA.skus[r[1]];
      const m = skuMeta(sku);
      if ((m.modelo || m.producto) !== modelo) continue;
      qtys[r[0]] += r[4];
    }
    return qtys;
  }

  function cvFromMonthly(qtys) {
    if (!qtys.length) return { cv: 0, xyz: "Z" };
    const mean = qtys.reduce((a, b) => a + b, 0) / qtys.length;
    if (mean <= 0) return { cv: 0, xyz: "Z" };
    const variance = qtys.reduce((s, q) => s + (q - mean) ** 2, 0) / qtys.length;
    const cv = Math.sqrt(variance) / mean;
    const th = DATA.meta?.xyz_thresholds || { X: 0.5, Y: 1.0 };
    let xyz = "Z";
    if (cv <= th.X) xyz = "X";
    else if (cv <= th.Y) xyz = "Y";
    return { cv, xyz };
  }

  function filterModels(models) {
    return models.filter((m) => {
      if (state.modelo && m.modelo !== state.modelo) return false;
      if (state.abcClass && m.abcClass !== state.abcClass) return false;
      if (!matchesSearch(m.modelo)) return false;
      return true;
    });
  }

  function computeAbc(skuMap, invMap) {
    const items = [...skuMap.values()];
    const pos = items
      .filter((x) => x.revenue > 0 && x.margin > 0)
      .sort((a, b) => b.revenue - a.revenue);
    const totalPos = pos.reduce((s, x) => s + x.revenue, 0);
    const out = new Map();
    let cum = 0;
    pos.forEach((it, idx) => {
      cum += it.revenue;
      const cumPct = totalPos > 0 ? cum / totalPos : 1;
      let cls = "C";
      if (cumPct <= TH.A) cls = "A";
      else if (cumPct <= TH.B) cls = "B";
      out.set(it.sku, {
        class: cls,
        rank: idx + 1,
        cumPct,
        revenueShare: totalPos > 0 ? it.revenue / totalPos : 0,
        revenue: it.revenue,
        margin: it.margin,
        segment: "venta",
      });
    });
    skuMap.forEach((it, sku) => {
      if (out.has(sku)) return;
      if (hasNegativeNetIncome(it)) return;
      const stock = invMap ? invMap.get(sku)?.total || 0 : 0;
      if (!skuIsActive(it, stock)) return;
      out.set(sku, {
        class: "C",
        rank: null,
        cumPct: 1,
        revenueShare: 0,
        revenue: it.revenue,
        margin: it.margin,
        segment: "sin_venta",
      });
    });
    return { abc: out, items, totalPosRevenue: totalPos };
  }

  function summarizeAbc(abc, skuMap, invMap) {
    const counts = { A: 0, B: 0, C: 0 };
    const marginBy = { A: 0, B: 0, C: 0 };
    const revenueBy = { A: 0, B: 0, C: 0 };
    let n = 0;
    let sinVenta = 0;
    skuMap.forEach((it, sku) => {
      const stock = invMap.get(sku)?.total || 0;
      if (hasNegativeNetIncome(it)) return;
      if (!skuIsActive(it, stock)) return;
      const a = abc.get(sku);
      if (!a) return;
      n++;
      const c = a.class;
      if (a.segment === "sin_venta") sinVenta++;
      counts[c]++;
      marginBy[c] += it.margin;
      revenueBy[c] += it.revenue;
    });
    const mt = marginBy.A + marginBy.B + marginBy.C || 1;
    const rt = revenueBy.A + revenueBy.B + revenueBy.C || 1;
    return {
      counts,
      n,
      sinVenta,
      skuPct: { A: counts.A / (n || 1), B: counts.B / (n || 1), C: counts.C / (n || 1) },
      marginPct: { A: marginBy.A / mt, B: marginBy.B / mt, C: marginBy.C / mt },
      revenuePct: { A: revenueBy.A / rt, B: revenueBy.B / rt, C: revenueBy.C / rt },
      marginBy,
      revenueBy,
    };
  }

  function aggregateByModel(scopeSkuMap) {
    return buildModelIndex(scopeSkuMap);
  }

  /** Modelos de baja prioridad para alertas (líneas promocionales / accesorios band). */
  function isExcludedAlertModel(modelo) {
    const u = (modelo || "").toUpperCase().trim();
    if (!u) return true;
    if (u.startsWith("REFRESH")) return true;
    if (u.includes("CUADRO BAND")) return true;
    return false;
  }

  function modelRevenueInPeriodKeys(modelo, periodKeys) {
    const periodSet = new Set(periodKeys);
    let revenue = 0;
    let margin = 0;
    for (let i = 0; i < DATA.salesRows.length; i++) {
      const r = DATA.salesRows[i];
      if (!periodSet.has(DATA.periods[r[0]].key)) continue;
      if (state.store && DATA.stores[r[2]] !== state.store) continue;
      if (state.category && DATA.categories[r[3]] !== state.category) continue;
      const sku = DATA.skus[r[1]];
      const m = skuMeta(sku);
      if ((m.modelo || m.producto) !== modelo) continue;
      revenue += r[5];
      margin += r[7];
    }
    return { revenue, margin };
  }

  /** Últimos dos meses consecutivos dentro del período activo (ej. Jun → Jul 2026). */
  function alertComparisonPeriods(periodKeys) {
    const ordered = DATA.periods.map((p) => p.key).filter((k) => periodKeys.includes(k));
    if (ordered.length < 2) return null;
    const lastKey = ordered[ordered.length - 1];
    const prevKey = ordered[ordered.length - 2];
    return {
      lastKey,
      prevKey,
      lastPeriod: DATA.periods.find((p) => p.key === lastKey),
      prevPeriod: DATA.periods.find((p) => p.key === prevKey),
    };
  }

  function transitionHint(from, to) {
    if (from === "A" && (to === "B" || to === "C"))
      return "Perdió peso en venta acumulada — revisar precio, promo y stock.";
    if (from === "B" && to === "C")
      return "Bajó de categoría — conviene liquidar o armar combos.";
    if (to === "A" && from !== "A")
      return "Entró al top de venta — asegurar abastecimiento.";
    if (from === "C" && (to === "B" || to === "A"))
      return "Subió de categoría — monitorear si se sostiene.";
    return "Cambio en participación acumulada — vigilar próximo mes.";
  }

  function alertSeverity(from, to, cumulativeRev, revenueShare, lastMonthRev) {
    let s = 1;
    if (from === "A" && to === "C") s = 5;
    else if (from === "A" && to === "B") s = 4;
    else if (from === "B" && to === "C") s = 3;
    else if (to === "A" && from !== "A") s = 3;
    else if (from === "C" && to === "B") s = 2;
    else if (from === "C" && to === "A") s = 3;
    if (cumulativeRev >= 50000) s += 2;
    else if (cumulativeRev >= 15000) s += 1;
    if (revenueShare >= 0.008) s += 1;
    if (lastMonthRev >= 3000) s += 1;
    return Math.max(1, Math.min(5, s));
  }

  function modelClassByPeriod() {
    const track = {};
    const periods = DATA.periods;
    for (let i = 0; i < periods.length; i++) {
      const keys = periods.slice(0, i + 1).map((p) => p.key);
      const map = aggregateSalesScope(keys);
      buildModelIndex(map, null, keys).forEach((m) => {
        if (!track[m.modelo]) track[m.modelo] = {};
        track[m.modelo][periods[i].key] = m.abcClass;
      });
    }
    return track;
  }

  function detectModelTransitions(modelTrack, scopeSkuMap, invMap, periodKeys) {
    const alerts = [];
    const cmp = alertComparisonPeriods(periodKeys || activePeriodKeys());
    if (!cmp) return alerts;

    const { lastKey, prevKey, lastPeriod, prevPeriod } = cmp;
    let totalPeriodRev = 0;
    scopeSkuMap.forEach((it) => {
      if (it.revenue > 0 && it.margin > 0) totalPeriodRev += it.revenue;
    });
    const minCumulativeRev = 5000;
    const minShare = 0.0015;

    Object.keys(modelTrack).forEach((modelo) => {
      if (isExcludedAlertModel(modelo)) return;
      const tr = modelTrack[modelo];
      const from = tr[prevKey];
      const to = tr[lastKey];
      if (!from || !to || from === to) return;
      if (from === "C" && to === "C") return;

      const cumulative = modelRevenueInPeriodKeys(modelo, periodKeys || activePeriodKeys());
      if (cumulative.revenue <= 0 || cumulative.margin <= 0) return;
      if (cumulative.revenue < minCumulativeRev) return;

      const revenueShare = totalPeriodRev > 0 ? cumulative.revenue / totalPeriodRev : 0;
      if (revenueShare < minShare) return;

      const lastMonth = modelRevenueInPeriodKeys(modelo, [lastKey]);
      const stock = modelStock(modelo, invMap);

      alerts.push({
        modelo,
        from,
        to,
        period: lastPeriod.label,
        prevPeriod: prevPeriod.label,
        revenue: cumulative.revenue,
        revenueShare,
        lastMonthRevenue: lastMonth.revenue,
        stock,
        sev: alertSeverity(from, to, cumulative.revenue, revenueShare, lastMonth.revenue),
        skus: modelSkus(modelo, scopeSkuMap, invMap),
        hint: transitionHint(from, to),
      });
    });
    alerts.sort((a, b) => b.sev - a.sev || b.revenue - a.revenue);
    return alerts;
  }

  function matchesSearch(text) {
    if (!state.search) return true;
    return text.toLowerCase().includes(state.search.toLowerCase());
  }

  function badge(cls) {
    if (cls === "-") return '<span class="abc abc-dash">—</span>';
    return '<span class="abc abc-' + cls + '">' + cls + "</span>";
  }

  function xyzBadge(x, cv) {
    const info = XYZ[x] || XYZ.Z;
    const cvTxt = cv != null && cv > 0 ? "CV " + Number(cv).toFixed(2) : "sin venta mensual";
    return (
      '<span class="xyz xyz-' +
      x +
      '" title="' +
      esc(info.hint + " · " + cvTxt) +
      '"><strong>' +
      x +
      "</strong> " +
      info.label +
      "</span>"
    );
  }

  function modelSkus(modelo, scopeSkuMap, invMap) {
    const items = [];
    scopeSkuMap.forEach((it, sku) => {
      if (it.modelo !== modelo) return;
      const meta = skuMeta(sku);
      items.push({
        sku,
        genero: meta.genero || "—",
        color: meta.color || "—",
        talla: meta.talla || "—",
        revenue: it.revenue,
        margin: it.margin,
        stock: invMap.get(sku)?.total || 0,
      });
    });
    DATA.skus.forEach((sku) => {
      if (skuMeta(sku).modelo !== modelo) return;
      if (items.some((x) => x.sku === sku)) return;
      const stock = invMap.get(sku)?.total || 0;
      if (stock <= 0) return;
      const meta = skuMeta(sku);
      items.push({
        sku,
        genero: meta.genero || "—",
        color: meta.color || "—",
        talla: meta.talla || "—",
        revenue: 0,
        margin: 0,
        stock,
      });
    });
    return items.sort((a, b) => b.revenue - a.revenue || b.stock - a.stock);
  }

  function modelStock(modelo, invMap) {
    let total = 0;
    DATA.skus.forEach((sku) => {
      const m = skuMeta(sku);
      if ((m.modelo || m.producto) !== modelo) return;
      total += invMap.get(sku)?.total || 0;
    });
    return total;
  }

  function donutLabels() {
    if (!global.ChartDataLabels) return {};
    return {
      color: "#eef0f8",
      font: { weight: "bold", size: 11 },
      formatter: (v, ctx) => {
        const arr = ctx.chart.data.datasets[0].data;
        const s = arr.reduce((a, b) => a + b, 0);
        return s ? Math.round((v / s) * 100) + "%" : "";
      },
    };
  }

  function renderSideLegend(elId, summary, type) {
    const el = $(elId);
    if (!el) return;
    const rows =
      type === "sku"
        ? [
            ["A", summary.counts.A, pct(summary.skuPct.A)],
            ["B", summary.counts.B, pct(summary.skuPct.B)],
            ["C", summary.counts.C, pct(summary.skuPct.C)],
          ]
        : [
            ["A", fmtUsd(summary.marginBy.A), pct(summary.marginPct.A)],
            ["B", fmtUsd(summary.marginBy.B), pct(summary.marginPct.B)],
            ["C", fmtUsd(summary.marginBy.C), pct(summary.marginPct.C)],
          ];
    el.innerHTML = rows
      .map(
        ([c, val, p]) =>
          '<div><span style="color:' +
          ABC[c].color +
          '">●</span> <strong>' +
          c +
          "</strong> " +
          ABC[c].label +
          "<br><span style=\"color:var(--mu)\">" +
          val +
          " · " +
          p +
          "</span></div>"
      )
      .join("");
  }

  function renderCharts(summary) {
    destroyChart("donutSku");
    destroyChart("donutMarg");
    destroyChart("marginBar");
    const tex = {
      A: "rgba(34,211,238,.85)",
      B: "rgba(251,191,36,.85)",
      C: "rgba(244,114,182,.85)",
    };
    const dl = global.ChartDataLabels
      ? { datalabels: donutLabels() }
      : {};
    const base = {
      maintainAspectRatio: false,
      cutout: "62%",
      plugins: {
        legend: { display: false },
        ...dl,
      },
    };
    const c1 = $("cDonutSku");
    if (c1) {
      charts.donutSku = new Chart(c1, {
        type: "doughnut",
        data: {
          labels: ["A", "B", "C"],
          datasets: [
            {
              data: [summary.counts.A, summary.counts.B, summary.counts.C],
              backgroundColor: [tex.A, tex.B, tex.C],
              borderWidth: 0,
              hoverOffset: 6,
            },
          ],
        },
        options: base,
      });
    }
    const c2 = $("cDonutMarg");
    if (c2) {
      charts.donutMarg = new Chart(c2, {
        type: "doughnut",
        data: {
          labels: ["A", "B", "C"],
          datasets: [
            {
              data: [
                summary.marginBy.A,
                summary.marginBy.B,
                summary.marginBy.C,
              ],
              backgroundColor: [tex.A, tex.B, tex.C],
              borderWidth: 0,
            },
          ],
        },
        options: base,
      });
    }
    const c3 = $("cMarginBar");
    if (c3) {
      charts.marginBar = new Chart(c3, {
        type: "bar",
        data: {
          labels: ["Clase A (obj. 80%)", "Clase B (obj. 15%)", "Clase C (obj. 5%)"],
          datasets: [
            {
              label: "% venta real",
              data: [
                summary.revenuePct.A * 100,
                summary.revenuePct.B * 100,
                summary.revenuePct.C * 100,
              ],
              backgroundColor: [tex.A, tex.B, tex.C],
              borderRadius: 8,
            },
            {
              label: "Objetivo",
              data: [80, 15, 5],
              backgroundColor: "rgba(255,255,255,.08)",
              borderRadius: 8,
            },
          ],
        },
        options: {
          maintainAspectRatio: false,
          indexAxis: "y",
          scales: {
            x: { max: 100, ticks: { callback: (v) => v + "%" } },
          },
          plugins: {
            legend: { position: "bottom", labels: { boxWidth: 10 } },
            datalabels: { display: false },
          },
        },
      });
    }
    renderSideLegend("legendSku", summary, "sku");
    renderSideLegend("legendMarg", summary, "marg");
  }

  function renderKpis(summary, scopeSkuMap, invMap, plabel) {
    const el = $("kpiBar");
    if (!el) return;
    let netRev = 0;
    scopeSkuMap.forEach((it) => {
      netRev += it.revenue;
    });
    let stock = 0;
    scopeSkuMap.forEach((it, sku) => {
      if (skuIsActive(it, invMap.get(sku)?.total || 0)) {
        stock += invMap.get(sku)?.total || 0;
      }
    });
    el.innerHTML =
      '<div class="kpib"><div class="kv">' +
      summary.counts.A +
      '</div><div class="kl">Modelos A</div></div>' +
      '<div class="kpib"><div class="kv">' +
      pct(summary.revenuePct.A) +
      '</div><div class="kl">Venta clase A</div></div>' +
      '<div class="kpib"><div class="kv">' +
      fmtMoney(netRev) +
      '</div><div class="kl">Ingreso bruto</div><div class="ksub">' +
      esc(plabel) +
      "</div></div>" +
      '<div class="kpib"><div class="kv">' +
      fmt(stock, 0) +
      '</div><div class="kl">Stock und.</div></div>';
  }

  function renderPremisaCard(summary) {
    const el = $("premisaCompare");
    if (!el) return;
    const t = DATA.meta.premisas;
    el.innerHTML =
      '<table class="rt"><thead><tr><th></th><th>SKUs</th><th>Ingresos netos</th></tr></thead><tbody>' +
      ["A", "B", "C"]
        .map(
          (c) =>
            "<tr><td>" +
            badge(c) +
            "</td><td>" +
            pct(summary.skuPct[c]) +
            " / " +
            t[c].sku_pct_objetivo +
            "%</td><td>" +
            pct(summary.marginPct[c]) +
            " / " +
            t[c].margen_pct +
            "%</td></tr>"
        )
        .join("") +
      "</tbody></table>";
  }

  function renderClassTable(allModels, summary) {
    const body = $("classBody");
    const sub = $("classTableSub");
    if (!body) return;
    const rows = filterModels(allModels);
    if (sub) {
      let txt = rows.length + " modelos · ABC venta USD (80/15/5) + solo stock como C";
      if (summary && summary.sinVenta)
        txt += " · " + summary.sinVenta + " SKUs sin venta en C";
      sub.textContent = txt;
    }
    body.innerHTML = rows
      .slice(0, 250)
      .map(
        (m) =>
          "<tr><td>" +
          (m.rank || "—") +
          "</td><td class=\"rn\">" +
          esc(m.modelo) +
          "</td><td>" +
          badge(m.abcClass) +
          '</td><td title="' +
          esc(XYZ[m.xyzClass]?.hint || "") +
          '">' +
          xyzBadge(m.xyzClass, m.cv) +
          "</td><td>" +
          fmtMoney(m.revenue) +
          "</td><td>" +
          fmtMoney(m.margin) +
          "</td><td>" +
          pct(m.revenueShare || 0) +
          "</td><td>" +
          fmt(m.qty, 0) +
          "</td><td>" +
          pct(m.marginPctProd) +
          "</td></tr>"
      )
      .join("");
  }

  function renderCatalog(scopeSkuMap, globalAbc, invMap) {
    const body = $("catalogBody");
    if (!body) return;
    const byModel = new Map();
    scopeSkuMap.forEach((it, sku) => {
      const stock = invMap.get(sku)?.total || 0;
      if (hasNegativeNetIncome(it)) return;
      if (!skuIsActive(it, stock)) return;
      const a = globalAbc.get(sku);
      if (state.abcClass && a && a.class !== state.abcClass) return;
      if (state.abcClass && !a && state.abcClass !== "C") return;
      if (!matchesSearch(it.modelo + " " + sku)) return;
      if (state.modelo && it.modelo !== state.modelo) return;
      const k = it.modelo;
      if (!byModel.has(k)) byModel.set(k, { items: [], revenue: 0, qty: 0, stock: 0 });
      const g = byModel.get(k);
      g.items.push({ ...it, abc: a, stock });
      g.revenue += it.revenue;
      g.qty += it.qty;
      g.stock += stock;
    });
    const models = [...byModel.entries()]
      .map(([modelo, g]) => {
        g.items.sort((a, b) => b.revenue - a.revenue);
        const lead = g.items.find((x) => x.abc) || g.items[0];
        return {
          modelo,
          ...g,
          abcClass: lead.abc?.class || (g.revenue > 0 ? "-" : "C"),
        };
      })
      .sort((a, b) => b.revenue - a.revenue);

    let html = "";
    models.slice(0, 120).forEach((m) => {
      const open = state.expandedModels.has(m.modelo);
      html +=
        '<tr class="row-model"><td><span class="expander" data-toggle="' +
        esc(m.modelo) +
        '">' +
        (open ? "▼" : "▶") +
        '</span></td><td>' +
        badge(m.abcClass) +
        '</td><td class="rn">' +
        esc(m.modelo) +
        "</td><td>" +
        fmtMoney(m.revenue) +
        "</td><td>" +
        fmt(m.qty, 0) +
        "</td><td>" +
        fmt(m.stock, 0) +
        "</td><td>" +
        (() => {
          const lead = m.items.find((x) => x.abc) || m.items[0];
          const meta = lead ? skuMeta(lead.sku) : {};
          return lead && lead.revenue > 0
            ? xyzBadge(meta.xyz || "Z", meta.cv)
            : '<span style="color:var(--mu);font-size:.72rem">—</span>';
        })() +
        "</td></tr>";
      if (open) {
        m.items.forEach((v) => {
          const vi = variantInfo(v.sku);
          const meta = skuMeta(v.sku);
          html +=
            '<tr class="row-variant"><td></td><td>' +
            (v.abc ? badge(v.abc.class) : badge("C")) +
            "</td><td>" +
            esc(vi.label) +
            "</td><td>" +
            fmtMoney(v.revenue) +
            "</td><td>" +
            fmt(v.qty, 0) +
            "</td><td>" +
            fmt(v.stock, 0) +
            "</td><td>" +
            xyzBadge(meta.xyz || "Z", meta.cv) +
            "</td></tr>";
        });
      }
    });
    body.innerHTML = html;
    body.querySelectorAll("[data-toggle]").forEach((el) => {
      el.onclick = () => {
        const mod = el.getAttribute("data-toggle");
        if (state.expandedModels.has(mod)) state.expandedModels.delete(mod);
        else state.expandedModels.add(mod);
        renderCatalog(scopeSkuMap, globalAbc, invMap);
      };
    });
  }

  function migrationTrend(classes, periods) {
    const keys = periods.map((p) => p.key);
    let last = null;
    for (let i = keys.length - 1; i >= 0; i--) {
      if (classes[keys[i]]) {
        last = classes[keys[i]];
        break;
      }
    }
    let prev = null;
    for (let i = keys.length - 2; i >= 0; i--) {
      if (classes[keys[i]]) {
        prev = classes[keys[i]];
        break;
      }
    }
    if (!last || !prev || last === prev) return '<span class="trend-up">—</span>';
    const ord = { A: 3, B: 2, C: 1 };
    if (ord[last] > ord[prev])
      return '<span class="trend-up">↑ ' + last + "</span>";
    return '<span class="trend-dn">↓ ' + last + "</span>";
  }

  function renderMigration(modelTrack) {
    const head = $("migHead");
    const body = $("migBody");
    const sub = $("migSub");
    if (!head || !body) return;
    const periods = DATA.periods;
    let rows = Object.keys(modelTrack).map((modelo) => {
      let changes = 0;
      for (let i = 1; i < periods.length; i++) {
        const a = modelTrack[modelo][periods[i - 1].key];
        const b = modelTrack[modelo][periods[i].key];
        if (a && b && a !== b) changes++;
      }
      return { modelo, classes: modelTrack[modelo], changes };
    });
    rows = rows.filter((r) => r.changes > 0);
    rows.sort((a, b) => b.changes - a.changes);
    const total = Object.keys(modelTrack).length;
    if (sub)
      sub.textContent =
        rows.length +
        " productos con cambios / " +
        total +
        " con venta acumulada · ABC por venta valorizada acumulada (Planity)";
    head.innerHTML =
      "<tr><th>Producto</th>" +
      periods.map((p) => "<th>" + p.short + "</th>").join("") +
      "<th>Tend.</th></tr>";
    body.innerHTML = rows
      .slice(0, 100)
      .filter((r) => matchesSearch(r.modelo))
      .filter((r) => !state.modelo || r.modelo === state.modelo)
      .map((r) => {
        let tr = '<tr><td class="rn">' + esc(r.modelo) + "</td>";
        periods.forEach((p) => {
          const cl = r.classes[p.key] || "-";
          tr +=
            '<td class="mig-cell"><span class="mig-dot ' +
            cl +
            '">' +
            (cl === "-" ? "—" : cl) +
            "</span></td>";
        });
        tr += "<td>" + migrationTrend(r.classes, periods) + "</td></tr>";
        return tr;
      })
      .join("");
  }

  function computeCapital(scopeSkuMap, abc, invMap) {
    const cap = {
      A: { u: 0, v: 0, models: new Set() },
      B: { u: 0, v: 0, models: new Set() },
      C: { u: 0, v: 0, models: new Set() },
      X: { u: 0, v: 0, models: new Set(), skus: 0 },
    };
    DATA.skus.forEach((sku) => {
      const stock = invMap.get(sku)?.total || 0;
      if (stock <= 0) return;
      if (state.modelo && !passesSkuFilter(sku)) return;
      const it = scopeSkuMap.get(sku) || {
        qty: 0,
        cost: 0,
        revenue: 0,
        margin: 0,
        modelo: skuMeta(sku).modelo || sku,
      };
      const unitCost = it.qty > 0 ? it.cost / it.qty : 0;
      const val = stock * unitCost;
      const meta = skuMeta(sku);
      let cl = "X";
      if (it.revenue > 0 && abc.get(sku)) cl = abc.get(sku).class;
      cap[cl].u += stock;
      cap[cl].v += val;
      cap[cl].models.add(it.modelo || meta.modelo);
      if (cl === "X") cap.X.skus++;
    });
    const totalU = cap.A.u + cap.B.u + cap.C.u + cap.X.u || 1;
    const totalV = cap.A.v + cap.B.v + cap.C.v + cap.X.v || 1;
    return { cap, totalU, totalV };
  }

  function renderCrossMatrix(scopeSkuMap, globalAbc, invMap) {
    const gridEl = $("crossMatrix");
    const analEl = $("crossAnalysis");
    const detailEl = $("crossDetail");
    if (!gridEl) return;
    const cells = {};
    ["A", "B", "C"].forEach((a) => {
      ["X", "Y", "Z"].forEach((x) => {
        cells[a + x] = { n: 0, revenue: 0, margin: 0, skus: [], models: new Set() };
      });
    });
    scopeSkuMap.forEach((it, sku) => {
      const stock = invMap.get(sku)?.total || 0;
      const abcEntry = globalAbc.get(sku);
      if (!abcEntry || !skuIsActive(it, stock)) return;
      const xyz = skuMeta(sku).xyz || "Z";
      const k = abcEntry.class + xyz;
      const c = cells[k];
      c.n++;
      c.revenue += it.revenue;
      c.margin += it.margin;
      c.skus.push({
        sku,
        modelo: it.modelo,
        genero: it.genero,
        color: it.color,
        talla: it.talla,
        revenue: it.revenue,
        margin: it.margin,
        stock,
        abc: abcEntry.class,
        xyz,
        segment: abcEntry.segment,
      });
      c.models.add(it.modelo);
    });
    const totalRev = Object.values(cells).reduce((s, c) => s + c.revenue, 0) || 1;
    const xyzLbl = {
      X: "Estable",
      Y: "Variable",
      Z: "Impredecible",
    };
    let html = '<div class="mx-grid mx-xyz"><div></div>';
    ["X", "Y", "Z"].forEach((x) => {
      html +=
        '<div class="mx-h">Demanda ' +
        xyzLbl[x] +
        " (" +
        x +
        ")<br><span style=\"font-weight:400;color:var(--mu)\">" +
        esc(XYZ[x].hint) +
        "</span></div>";
    });
    ["A", "B", "C"].forEach((a) => {
      html += '<div class="mx-h">ABC ' + a + "<br>" + ABC[a].label + "</div>";
      ["X", "Y", "Z"].forEach((x) => {
        const k = a + x;
        const c = cells[k];
        const p = c.revenue / totalRev;
        html +=
          '<div class="mx-cell mx-click mx-' +
          k +
          '" data-cell="' +
          k +
          '" title="Clic para ver detalle"><div class="n">' +
          c.n +
          ' SKUs</div><div class="v">' +
          fmtMoney(c.revenue) +
          "<br>" +
          pct(p) +
          " venta</div></div>";
      });
    });
    html += "</div>";
    gridEl.innerHTML = html;

    const Q = {
      AX: { t: "Core estable", d: "Alto valor + demanda predecible.", a: "Reposición automática; stock de seguridad bajo." },
      AY: { t: "Estrella variable", d: "Alto valor, demanda fluctuante.", a: "Monitoreo mensual; buffer moderado." },
      AZ: { t: "Estrella errática", d: "Alto valor, demanda impredecible.", a: "Evitar sobre-stock; revisar estacionalidad." },
      BX: { t: "Medio estable", d: "Valor medio, demanda constante.", a: "Control intermedio; no sobre-comprar." },
      BY: { t: "Medio variable", d: "Valor medio, picos irregulares.", a: "Compras flexibles; bundles con A." },
      BZ: { t: "Medio inestable", d: "Valor medio, alta incertidumbre.", a: "Reducir exposición; promover en temporadas." },
      CX: { t: "Cola estable", d: "Bajo valor, demanda constante.", a: "Mantener mínimo operativo o descontinuar." },
      CY: { t: "Cola variable", d: "Bajo valor, demanda irregular.", a: "Liquidar excedente; no recomprar agresivo." },
      CZ: { t: "Lastre inestable", d: "Bajo valor + impredecible.", a: "Liquidar; liberar capital congelado." },
    };
    if (analEl) {
      analEl.innerHTML = ["AX", "AY", "BX", "BY", "CZ"]
        .map((k) => {
          const c = cells[k];
          const q = Q[k];
          return (
            '<div class="qcard mx-click" data-cell="' +
            k +
            '"><h4>' +
            k +
            " — " +
            q.t +
            " (" +
            c.n +
            ' SKUs)</h4><p>' +
            q.d +
            "</p><p><em>" +
            q.a +
            '</em></p><div class="ex">' +
            esc([...c.models].slice(0, 5).join(" · ")) +
            (c.models.size > 5 ? " …" : "") +
            "</div></div>"
          );
        })
        .join("");
    }

    function showCellDetail(k) {
      if (!detailEl) return;
      const c = cells[k];
      if (!c || !c.n) {
        detailEl.innerHTML = '<div class="sub">Sin SKUs en ' + k + "</div>";
        return;
      }
      const sorted = c.skus.sort((a, b) => b.revenue - a.revenue);
      detailEl.innerHTML =
        "<h4>Cuadrante " +
        k +
        " — " +
        c.n +
        " SKUs · " +
        c.models.size +
        " modelos</h4>" +
        '<div class="cscroll" style="max-height:280px"><table class="ct"><thead><tr><th>Modelo</th><th>SKU</th><th>Género</th><th>Color</th><th>Talla</th><th>Ingreso bruto</th><th>Ingresos netos</th><th>Stock</th></tr></thead><tbody>' +
        sorted
          .slice(0, 120)
          .map(
            (r) =>
              "<tr><td class=\"rn\">" +
              esc(r.modelo) +
              "</td><td>" +
              esc(r.sku) +
              "</td><td>" +
              esc(r.genero || "—") +
              "</td><td>" +
              esc(r.color || "—") +
              "</td><td>" +
              esc(r.talla || "—") +
              "</td><td>" +
              fmtMoney(r.revenue) +
              "</td><td>" +
              fmtMoney(r.margin) +
              "</td><td>" +
              fmt(r.stock, 0) +
              "</td></tr>"
          )
          .join("") +
        "</tbody></table></div>";
    }

    gridEl.querySelectorAll(".mx-click").forEach((el) => {
      el.onclick = () => showCellDetail(el.getAttribute("data-cell"));
    });
    if (analEl) {
      analEl.querySelectorAll(".mx-click").forEach((el) => {
        el.onclick = () => showCellDetail(el.getAttribute("data-cell"));
      });
    }
    if (detailEl && !detailEl.dataset.init) {
      detailEl.dataset.init = "1";
      showCellDetail("AX");
    }
  }

  function renderCapital(scopeSkuMap, abc, invMap, summary) {
    const { cap, totalU, totalV } = computeCapital(scopeSkuMap, abc, invMap);
    const cards = $("capitalCards");
    if (cards) {
      const defs = [
        ["A", "Intocables", "a"],
        ["B", "Clase media", "b"],
        ["C", "Capital retenido", "c"],
      ];
      cards.innerHTML = defs
        .map(([k, title, css]) => {
          const pU = cap[k].u / totalU;
          return (
            '<div class="cap-card ' +
            css +
            '"><div class="lbl">Clase ' +
            k +
            " — " +
            title +
            '</div><div class="big">' +
            fmt(cap[k].u, 0) +
            '</div><div class="sub" style="margin:4px 0">' +
            cap[k].models.size +
            " modelos · " +
            fmtUsd(cap[k].v) +
            " est.</div><div class='sub'>" +
            pct(pU) +
            " del stock físico</div></div>"
          );
        })
        .join("") +
        '<div class="cap-card mx-click" style="cursor:pointer" onclick="AbcDashboard.st(\'sinventa\')" title="Ver detalle completo"><div class="lbl">Sin venta en período + stock</div><div class="big">' +
        fmt(cap.X.u, 0) +
        '</div><div class="sub">' +
        cap.X.skus +
        " SKUs · " +
        cap.X.models.size +
        " modelos · " +
        fmtUsd(cap.X.v) +
        " est.</div></div>";
    }
    function bar(id, cap, total, val) {
      const el = $(id);
      if (!el) return;
      const segs = [
        ["A", cap.A[val], ABC.A.color],
        ["B", cap.B[val], ABC.B.color],
        ["C", cap.C[val], ABC.C.color],
        ["—", cap.X[val], "#555"],
      ];
      el.innerHTML =
        '<div class="bar-stack">' +
        segs
          .filter((s) => s[1] > 0)
          .map(
            ([k, v, c]) =>
              '<span style="flex:' +
              v +
              ";background:" +
              c +
              '">' +
              k +
              " " +
              pct(v / total) +
              "</span>"
          )
          .join("") +
        "</div>";
    }
    bar("stockBar", cap, totalU, "u");
    bar("valueBar", cap, totalV, "v");
    const diag = $("capitalDiag");
    if (diag) {
      diag.innerHTML =
        '<div class="g2">' +
        '<div class="diag r"><strong>' +
        fmtMoney(cap.C.v) +
        "</strong> en clase C (~" +
        pct(summary.marginPct.C) +
        " de ingresos netos). Revisar promoción o bajar recompra.</div>" +
        '<div class="diag g"><strong>' +
        fmtMoney(cap.A.v) +
        "</strong> en clase A (~" +
        pct(summary.marginPct.A) +
        " de ingresos netos). Proteger abastecimiento.</div></div>" +
        (cap.X.u > 0
          ? '<div class="diag m" style="margin-top:8px">' +
            fmt(cap.X.u, 0) +
            " und. en stock sin venta en el período seleccionado (" +
            cap.X.skus +
            " SKUs). Revisar liquidación o activación comercial.</div>"
          : "");
    }
  }

  function renderSinVentaStock(scopeSkuMap, invMap) {
    const kpiEl = $("sinVentaKpis");
    const subEl = $("sinVentaSub");
    const body = $("sinVentaBody");
    if (!body) return;

    const byModel = new Map();
    let totalU = 0;
    let totalV = 0;
    let skuCount = 0;

    DATA.skus.forEach((sku) => {
      const stock = invMap.get(sku)?.total || 0;
      if (stock <= 0) return;
      if (state.modelo && !passesSkuFilter(sku)) return;
      const it = scopeSkuMap.get(sku) || {
        qty: 0,
        cost: 0,
        revenue: 0,
        margin: 0,
        modelo: skuMeta(sku).modelo || sku,
      };
      if (it.revenue > 0) return;
      const meta = skuMeta(sku);
      const modelo = it.modelo || meta.modelo || meta.producto || sku;
      if (!matchesSearch(modelo + " " + sku)) return;

      const unitCost = it.qty > 0 ? it.cost / it.qty : 0;
      const val = stock * unitCost;
      skuCount++;
      totalU += stock;
      totalV += val;

      if (!byModel.has(modelo)) {
        byModel.set(modelo, { modelo, skus: [], stock: 0, val: 0 });
      }
      const g = byModel.get(modelo);
      g.skus.push({
        sku,
        genero: meta.genero || "—",
        color: meta.color || "—",
        talla: meta.talla || "—",
        stock,
        val,
        xyz: meta.xyz || "Z",
        cv: meta.cv || 0,
      });
      g.stock += stock;
      g.val += val;
    });

    const models = [...byModel.values()].sort((a, b) => b.stock - a.stock || b.val - a.val);

    if (kpiEl) {
      kpiEl.innerHTML =
        '<div class="cap-card"><div class="lbl">Unidades en stock</div><div class="big">' +
        fmt(totalU, 0) +
        '</div><div class="sub">Sin venta en el período seleccionado</div></div>' +
        '<div class="cap-card"><div class="lbl">SKUs</div><div class="big">' +
        skuCount +
        '</div><div class="sub">Con inventario y cero ventas</div></div>' +
        '<div class="cap-card"><div class="lbl">Modelos</div><div class="big">' +
        models.length +
        '</div><div class="sub">Productos distintos afectados</div></div>' +
        '<div class="cap-card"><div class="lbl">Valor estimado</div><div class="big">' +
        fmtUsd(totalV) +
        '</div><div class="sub">Stock × costo unitario</div></div>';
    }

    if (subEl) {
      let txt =
        fmt(totalU, 0) +
        " und. · " +
        skuCount +
        " SKUs · " +
        models.length +
        " modelos · " +
        fmtUsd(totalV) +
        " est.";
      if (state.location) txt += " · stock en «" + state.location + "»";
      subEl.textContent = txt;
    }

    let html = "";
    models.slice(0, 150).forEach((m) => {
      const open = state.expandedSinVentaModels.has(m.modelo);
      html +=
        '<tr class="row-model"><td><span class="expander" data-sv-toggle="' +
        esc(m.modelo) +
        '">' +
        (open ? "▼" : "▶") +
        '</span></td><td class="rn">' +
        esc(m.modelo) +
        "</td><td>" +
        m.skus.length +
        "</td><td>" +
        fmt(m.stock, 0) +
        "</td><td>" +
        fmtUsd(m.val) +
        "</td></tr>";
      if (open) {
        m.skus
          .sort((a, b) => b.stock - a.stock)
          .forEach((v) => {
            html +=
              '<tr class="row-variant"><td></td><td>' +
              esc(v.sku) +
              " · " +
              esc(v.color) +
              " · " +
              esc(v.talla) +
              "</td><td>" +
              xyzBadge(v.xyz, v.cv) +
              "</td><td>" +
              fmt(v.stock, 0) +
              "</td><td>" +
              fmtUsd(v.val) +
              "</td></tr>";
          });
      }
    });
    body.innerHTML = html;
    body.querySelectorAll("[data-sv-toggle]").forEach((el) => {
      el.onclick = () => {
        const mod = el.getAttribute("data-sv-toggle");
        if (state.expandedSinVentaModels.has(mod)) state.expandedSinVentaModels.delete(mod);
        else state.expandedSinVentaModels.add(mod);
        renderSinVentaStock(scopeSkuMap, invMap);
      };
    });
  }

  function renderAlerts(alerts, scopeSkuMap, invMap, globalAbc) {
    const body = $("alertBody");
    const sub = $("alertCount");
    if (!body) return;
    let rows = alerts.filter((r) => matchesSearch(r.modelo));
    if (state.modelo) rows = rows.filter((r) => r.modelo === state.modelo);
    if (sub) {
      const cmp = alertComparisonPeriods(activePeriodKeys());
      let msg = rows.length + " cambios con peso";
      if (cmp && cmp.prevPeriod && cmp.lastPeriod) {
        msg +=
          " · " +
          cmp.prevPeriod.short +
          " → " +
          cmp.lastPeriod.short +
          " (clase actual al " +
          cmp.lastPeriod.label +
          ")";
      }
      msg += " · excl. Refresh / Cuadro Band · expandir fila para SKUs";
      if (state.location) msg += " · stock en «" + state.location + "»";
      sub.textContent = msg;
    }
    let html = "";
    rows.slice(0, 200).forEach((r) => {
      const open = state.expandedAlertModels.has(r.modelo);
      html +=
        '<tr class="row-model"><td>' +
        r.sev +
        '</td><td><span class="expander" data-alert-toggle="' +
        esc(r.modelo) +
        '">' +
        (open ? "▼" : "▶") +
        '</span> <span class="rn">' +
        esc(r.modelo) +
        "</span></td><td>" +
        badge(r.from) +
        "→" +
        badge(r.to) +
        "</td><td>" +
        esc(r.prevPeriod) +
        " → " +
        esc(r.period) +
        "</td><td>" +
        fmtMoney(r.revenue) +
        "<br><span style=\"color:var(--mu);font-size:.65rem\">" +
        pct(r.revenueShare || 0) +
        " del período</span></td><td>" +
        fmtMoney(r.lastMonthRevenue || 0) +
        "</td><td>" +
        fmt(r.stock, 0) +
        "</td><td>" +
        esc(r.hint) +
        "</td></tr>";
      if (open && r.skus && r.skus.length) {
        r.skus.forEach((v) => {
          const cls = globalAbc.get(v.sku);
          html +=
            '<tr class="row-variant"><td></td><td colspan="3">' +
            esc(v.sku) +
            " · " +
            esc(v.color) +
            " · " +
            esc(v.talla) +
            "</td><td>" +
            (cls ? badge(cls.class) : badge("-")) +
            "</td><td>" +
            fmtMoney(v.revenue) +
            '</td><td style="color:var(--mu)">—</td><td>' +
            fmt(v.stock, 0) +
            '</td><td style="font-size:.68rem;color:var(--mu)">variante</td></tr>';
        });
      }
    });
    body.innerHTML = html;
    body.querySelectorAll("[data-alert-toggle]").forEach((el) => {
      el.onclick = () => {
        const mod = el.getAttribute("data-alert-toggle");
        if (state.expandedAlertModels.has(mod)) state.expandedAlertModels.delete(mod);
        else state.expandedAlertModels.add(mod);
        renderAlerts(alerts, scopeSkuMap, invMap, globalAbc);
      };
    });
  }

  function buildPeriodFilters() {
    const presets = $("presetChips");
    if (presets) {
      presets.innerHTML = "";
      [
        ["all", "Todo"],
        ["last3", "Últ. 3 meses"],
        ["last6", "Últ. 6 meses"],
        ["last12", "Últ. 12 meses"],
      ].forEach(([id, label]) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "mbtn" + (state.timePreset === id ? " active" : "");
        b.textContent = label;
        b.onclick = () => setTimePreset(id);
        presets.appendChild(b);
      });
    }
    const mc = $("monthChips");
    if (!mc) return;
    mc.innerHTML = "";
    const active = new Set(activePeriodKeys());
    DATA.periods.forEach((p) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "mbtn" + (active.has(p.key) ? " active" : "");
      b.textContent = p.short;
      b.title = p.label;
      b.onclick = () => togglePeriodKey(p.key);
      mc.appendChild(b);
    });
    const lbl = $("periodSelectionLabel");
    if (lbl) lbl.textContent = periodLabel();
  }

  function fillSelects() {
    const models = new Set();
    Object.values(DATA.skuMaster).forEach((m) => {
      if (m.modelo) models.add(m.modelo);
    });
    const fM = $("fModel");
    fM.innerHTML = '<option value="">Todos los modelos</option>';
    [...models].sort().forEach((s) => {
      fM.innerHTML += '<option value="' + esc(s) + '">' + esc(s) + "</option>";
    });
    $("fStore").innerHTML =
      '<option value="">Todas</option>' +
      DATA.stores.map((s) => '<option value="' + esc(s) + '">' + esc(s) + "</option>").join("");
    $("fCat").innerHTML =
      '<option value="">Todas</option>' +
      DATA.categories.map((s) => '<option value="' + esc(s) + '">' + esc(s) + "</option>").join("");
    $("fLoc").innerHTML =
      '<option value="">Todas las ubicaciones</option>' +
      locationsForFilter()
        .map((s) => '<option value="' + esc(s) + '">' + esc(s) + "</option>")
        .join("");
  }

  function periodLabel() {
    const keys = activePeriodKeys();
    const n = DATA.periods.length;
    if (!keys.length) return "";
    if (keys.length === n) {
      return DATA.periods[0].label + " → " + DATA.periods[n - 1].label;
    }
    if (keys.length === 1) {
      const p = DATA.periods.find((x) => x.key === keys[0]);
      return p ? p.label : keys[0];
    }
    return keys.length + " meses seleccionados";
  }

  function showLoadError(msg) {
    const el = $("loadErr");
    if (el) {
      el.style.display = "block";
      el.textContent = msg;
    }
  }

  function refresh() {
    if (!DATA) return;
    try {
      const keys = activePeriodKeys();
      if (!keys.length) {
        $("periodWarn").style.display = "block";
        return;
      }
      $("periodWarn").style.display = "none";
      const invAll = inventoryBySku(true, false);
      const invLoc = inventoryBySku(true, true);
      const scopeMap = fullActiveScope(keys, invAll);
      const { abc: globalAbc } = computeAbc(scopeMap, invAll);
      const summary = summarizeAbc(globalAbc, scopeMap, invAll);
      const allModels = buildModelIndex(scopeMap, invAll, keys);
      const modelTrack = modelClassByPeriod();
      const alerts = detectModelTransitions(modelTrack, scopeMap, invLoc, keys);
      const plabel = periodLabel();

      renderKpis(summary, scopeMap, invLoc, plabel);
      renderPremisaCard(summary);
      if (typeof Chart !== "undefined") renderCharts(summary);
      renderClassTable(allModels, summary);
      renderCatalog(scopeMap, globalAbc, invLoc);
      renderMigration(modelTrack);
      renderCapital(scopeMap, globalAbc, invLoc, summary);
      renderSinVentaStock(scopeMap, invLoc);
      renderCrossMatrix(scopeMap, globalAbc, invAll);
      renderAlerts(alerts, scopeMap, invLoc, globalAbc);

      let sub = periodLabel();
      if (state.location) sub += " · stock en: " + state.location;
      $("subtitle").textContent = sub;
    } catch (err) {
      console.error(err);
      showLoadError("Error: " + err.message);
    }
  }

  function st(name) {
    document.querySelectorAll(".tab").forEach((t) => {
      t.classList.toggle("active", t.dataset.tab === name);
    });
    document.querySelectorAll(".sec").forEach((s) => {
      s.classList.toggle("active", s.id === "sec-" + name);
    });
  }

  function exportCsv() {
    const invAll = inventoryBySku(true, false);
    const invLoc = inventoryBySku(true, true);
    const scopeMap = fullActiveScope(activePeriodKeys(), invAll);
    const { abc } = computeAbc(scopeMap, invAll);
    const lines = ["modelo,sku,genero,color,talla,clase_abc,demanda_xyz,cv,matriz,venta_usd,margen,qty,stock"];
    scopeMap.forEach((it, sku) => {
      const stock = invLoc.get(sku)?.total || 0;
      const a = abc.get(sku);
      if (!a && !skuIsActive(it, stock)) return;
      if (state.modelo && it.modelo !== state.modelo) return;
      const v = variantInfo(sku);
      const meta = skuMeta(sku);
      lines.push(
        [
          it.modelo,
          sku,
          v.genero,
          v.color,
          v.talla,
          a ? a.class : "C",
          meta.xyz || "Z",
          meta.cv || 0,
          (a ? a.class : "-") + (meta.xyz || "Z"),
          it.revenue.toFixed(2),
          it.margin.toFixed(2),
          it.qty,
          stock,
        ].join(",")
      );
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(
      new Blob([lines.join("\n")], { type: "text/csv" })
    );
    a.download = "abc_export.csv";
    a.click();
  }

  function initFilters() {
    if (filtersInitialized) return;
    filtersInitialized = true;
    $("fModel").onchange = (e) => {
      state.modelo = e.target.value;
      refresh();
    };
    $("fStore").onchange = (e) => {
      state.store = e.target.value;
      refresh();
    };
    $("fCat").onchange = (e) => {
      state.category = e.target.value;
      refresh();
    };
    $("fLoc").onchange = (e) => {
      state.location = e.target.value;
      refresh();
    };
    $("fAbc").onchange = (e) => {
      state.abcClass = e.target.value;
      refresh();
    };
    $("fSearch").oninput = (e) => {
      state.search = e.target.value.trim();
      refresh();
    };
    $("btnReset").onclick = () => {
      state.modelo = state.store = state.category = state.location = "";
      state.abcClass = state.search = "";
      state.timePreset = "all";
      state.customPeriodKeys.clear();
      state.expandedModels.clear();
      state.expandedAlertModels.clear();
      state.expandedSinVentaModels.clear();
      ["fModel", "fStore", "fCat", "fLoc", "fAbc"].forEach((id) => ($(id).value = ""));
      $("fSearch").value = "";
      buildPeriodFilters();
      refresh();
    };
    $("btnExport").onclick = exportCsv;
  }

  function boot(payload) {
    DATA = payload;
    if (!DATA?.periods?.length) {
      showLoadError("Datos incompletos.");
      return;
    }
    fillSelects();
    initFilters();
    buildPeriodFilters();
    refresh();
  }

  function loadData(payload) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", () => boot(payload));
    } else boot(payload);
  }

  global.AbcDashboard = { loadData, st, refresh, setTimePreset };
})(window);
