/* Matriz ABC — dashboard compacto */
(function (global) {
  "use strict";

  const ABC = {
    A: { color: "#22d3ee", label: "Intocable" },
    B: { color: "#fbbf24", label: "Clase media" },
    C: { color: "#f472b6", label: "Lastre" },
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
  };
  let filtersInitialized = false;

  if (typeof Chart !== "undefined" && Chart.register && global.ChartDataLabels) {
    Chart.register(global.ChartDataLabels);
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

  function fmtUsd(n) {
    if (n == null || isNaN(n)) return "—";
    if (Math.abs(n) >= 1000) return "$" + (n / 1000).toFixed(1) + "K";
    return "$" + fmt(n, 2);
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

  function aggregateSales(periodKeys) {
    const skuMap = new Map();
    const periodSet = new Set(periodKeys);
    const skus = DATA.skus;
    for (let i = 0; i < DATA.salesRows.length; i++) {
      const r = DATA.salesRows[i];
      if (!periodSet.has(DATA.periods[r[0]].key)) continue;
      if (state.store && DATA.stores[r[2]] !== state.store) continue;
      if (state.category && DATA.categories[r[3]] !== state.category) continue;
      const sku = skus[r[1]];
      if (!passesSkuFilter(sku)) continue;
      if (!skuMap.has(sku)) {
        const m = skuMeta(sku);
        skuMap.set(sku, {
          sku,
          producto: m.producto || sku,
          modelo: m.modelo || m.producto || sku,
          categoria: m.categoria || "",
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

  function inventoryBySku() {
    const map = new Map();
    DATA.skus.forEach((sku) => map.set(sku, { total: 0 }));
    for (let i = 0; i < DATA.invRows.length; i++) {
      const r = DATA.invRows[i];
      const sku = DATA.skus[r[0]];
      if (!passesSkuFilter(sku)) continue;
      if (state.location && DATA.locations[r[1]] !== state.location) continue;
      map.get(sku).total += r[2];
    }
    return map;
  }

  function computeAbc(skuMap) {
    const items = [...skuMap.values()];
    const pos = items
      .filter((x) => x.margin > 0)
      .sort((a, b) => b.margin - a.margin);
    const totalPos = pos.reduce((s, x) => s + x.margin, 0);
    const out = new Map();
    let cum = 0;
    pos.forEach((it, idx) => {
      cum += it.margin;
      const cumPct = totalPos > 0 ? cum / totalPos : 1;
      let cls = "C";
      if (cumPct <= TH.A) cls = "A";
      else if (cumPct <= TH.B) cls = "B";
      out.set(it.sku, {
        class: cls,
        rank: idx + 1,
        cumPct,
        marginShare: totalPos > 0 ? it.margin / totalPos : 0,
        margin: it.margin,
      });
    });
    return { abc: out, items, totalPosMargin: totalPos };
  }

  function summarizePositive(abc, skuMap) {
    const counts = { A: 0, B: 0, C: 0 };
    const marginBy = { A: 0, B: 0, C: 0 };
    let n = 0;
    skuMap.forEach((it, sku) => {
      if (it.margin <= 0) return;
      n++;
      const c = abc.get(sku)?.class || "C";
      counts[c]++;
      marginBy[c] += it.margin;
    });
    const mt = marginBy.A + marginBy.B + marginBy.C || 1;
    return {
      counts,
      n,
      skuPct: { A: counts.A / (n || 1), B: counts.B / (n || 1), C: counts.C / (n || 1) },
      marginPct: { A: marginBy.A / mt, B: marginBy.B / mt, C: marginBy.C / mt },
      marginBy,
    };
  }

  function aggregateByModel(skuMap, abc) {
    const models = new Map();
    skuMap.forEach((it, sku) => {
      if (it.margin <= 0) return;
      const key = it.modelo || it.producto;
      if (!models.has(key)) {
        models.set(key, {
          modelo: key,
          skus: [],
          qty: 0,
          revenue: 0,
          margin: 0,
        });
      }
      const m = models.get(key);
      m.skus.push({ ...it, abc: abc.get(sku) });
      m.qty += it.qty;
      m.revenue += it.revenue;
      m.margin += it.margin;
    });
    const list = [...models.values()].sort((a, b) => b.margin - a.margin);
    const totalPos = list.reduce((s, x) => s + x.margin, 0);
    let cum = 0;
    list.forEach((m, idx) => {
      cum += m.margin;
      m.cumPct = totalPos > 0 ? cum / totalPos : 1;
      m.rank = idx + 1;
      m.marginShare = totalPos > 0 ? m.margin / totalPos : 0;
      m.marginPctProd = m.revenue > 0 ? m.margin / m.revenue : 0;
      if (m.cumPct <= TH.A) m.abcClass = "A";
      else if (m.cumPct <= TH.B) m.abcClass = "B";
      else m.abcClass = "C";
      m.rotClass =
        m.qty >= 500 ? "A" : m.qty >= 100 ? "B" : "C";
    });
    return list;
  }

  function modelClassByPeriod() {
    const track = {};
    DATA.periods.forEach((p) => {
      const map = aggregateSales([p.key]);
      const { abc } = computeAbc(map);
      aggregateByModel(map, abc).forEach((m) => {
        if (!track[m.modelo]) track[m.modelo] = {};
        track[m.modelo][p.key] = m.abcClass;
      });
    });
    return track;
  }

  function skuClassByPeriod() {
    const result = {};
    DATA.periods.forEach((p) => {
      const map = aggregateSales([p.key]);
      const { abc } = computeAbc(map);
      map.forEach((it, sku) => {
        if (it.margin <= 0) return;
        if (!result[sku]) result[sku] = {};
        result[sku][p.key] = abc.get(sku).class;
      });
    });
    return result;
  }

  function detectTransitions(classByPeriod) {
    const alerts = [];
    const periods = DATA.periods.map((p) => p.key);
    const sev = (f, t) => {
      if (f === "A" && t === "C") return 5;
      if (f === "A" && t === "B") return 4;
      if (f === "B" && t === "C") return 3;
      if (t === "A" && f !== "A") return 2;
      return 1;
    };
    Object.keys(classByPeriod).forEach((sku) => {
      const tr = classByPeriod[sku];
      for (let i = 1; i < periods.length; i++) {
        const from = tr[periods[i - 1]];
        const to = tr[periods[i]];
        if (!from || !to || from === to) continue;
        const m = skuMeta(sku);
        alerts.push({
          sku,
          modelo: m.modelo || sku,
          from,
          to,
          period: DATA.periods[i].label,
          sev: sev(from, to),
          hint:
            from === "A" && (to === "B" || to === "C")
              ? "Promo, marketing, reubicación en tienda, revisar stock."
              : from === "B" && to === "C"
                ? "Riesgo inventario lento — bundle o liquidación."
                : to === "A"
                  ? "Escalar abastecimiento."
                  : "Monitorear.",
        });
      }
    });
    alerts.sort((a, b) => b.sev - a.sev);
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

  function donutLabels() {
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
    const dl = global.ChartDataLabels ? { datalabels: donutLabels() } : {};
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
              label: "% margen real",
              data: [
                summary.marginPct.A * 100,
                summary.marginPct.B * 100,
                summary.marginPct.C * 100,
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

  function renderKpis(summary, skuMap, invMap, plabel) {
    const el = $("kpiBar");
    if (!el) return;
    let posMargin = 0;
    skuMap.forEach((it) => {
      if (it.margin > 0) posMargin += it.margin;
    });
    let stock = 0;
    skuMap.forEach((it, sku) => {
      if (it.margin > 0) stock += invMap.get(sku)?.total || 0;
    });
    el.innerHTML =
      '<div class="kpib"><div class="kv">' +
      summary.counts.A +
      '</div><div class="kl">SKU A+</div></div>' +
      '<div class="kpib"><div class="kv">' +
      pct(summary.marginPct.A) +
      '</div><div class="kl">Margen A</div></div>' +
      '<div class="kpib"><div class="kv">' +
      fmtUsd(posMargin) +
      '</div><div class="kl">Margen +</div><div class="ksub">' +
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
      '<table class="rt"><thead><tr><th></th><th>SKUs</th><th>Margen</th></tr></thead><tbody>' +
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

  function renderClassTable(models) {
    const body = $("classBody");
    const sub = $("classTableSub");
    if (!body) return;
    let rows = models.filter((m) => m.margin > 0);
    if (state.abcClass)
      rows = rows.filter((m) => m.abcClass === state.abcClass);
    rows = rows.filter((m) => matchesSearch(m.modelo));
    if (sub) sub.textContent = rows.length + " productos con margen positivo";
    body.innerHTML = rows
      .slice(0, 250)
      .map(
        (m) =>
          "<tr><td>" +
          m.rank +
          "</td><td class=\"rn\">" +
          esc(m.modelo) +
          "</td><td>" +
          badge(m.abcClass) +
          "</td><td>" +
          fmtUsd(m.revenue) +
          "</td><td>" +
          fmtUsd(m.margin) +
          "</td><td>" +
          pct(m.marginShare) +
          "</td><td>" +
          pct(m.cumPct) +
          "</td><td>" +
          fmt(m.qty, 0) +
          "</td><td>" +
          pct(m.marginPctProd) +
          "</td><td>" +
          badge(m.rotClass) +
          "</td></tr>"
      )
      .join("");
  }

  function renderCatalog(skuMap, abc, invMap) {
    const body = $("catalogBody");
    if (!body) return;
    const byModel = new Map();
    skuMap.forEach((it, sku) => {
      if (it.margin <= 0) return;
      const a = abc.get(sku);
      if (state.abcClass && a.class !== state.abcClass) return;
      if (!matchesSearch(it.modelo + " " + sku)) return;
      const k = it.modelo;
      if (!byModel.has(k)) byModel.set(k, { items: [], margin: 0, qty: 0, stock: 0 });
      const g = byModel.get(k);
      g.items.push({ ...it, abc: a, stock: invMap.get(sku)?.total || 0 });
      g.margin += it.margin;
      g.qty += it.qty;
      g.stock += g.items[g.items.length - 1].stock;
    });
    const models = [...byModel.entries()]
      .map(([modelo, g]) => {
        g.items.sort((a, b) => b.margin - a.margin);
        const totalM = g.margin;
        let cum = 0;
        g.items.forEach((it) => {
          cum += it.margin;
          it.share = totalM > 0 ? it.margin / totalM : 0;
        });
        const rep = g.items[0].abc;
        return { modelo, ...g, abcClass: rep.class };
      })
      .sort((a, b) => b.margin - a.margin);

    let html = "";
    models.slice(0, 120).forEach((m) => {
      const open = state.expandedModels.has(m.modelo);
      html +=
        '<tr class="row-model" data-model="' +
        esc(m.modelo) +
        '"><td><span class="expander" data-toggle="' +
        esc(m.modelo) +
        '">' +
        (open ? "▼" : "▶") +
        '</span></td><td>' +
        badge(m.abcClass) +
        '</td><td class="rn">' +
        esc(m.modelo) +
        "</td><td>" +
        fmtUsd(m.margin) +
        "</td><td>100%</td><td>" +
        fmt(m.qty, 0) +
        "</td><td>" +
        fmt(m.stock, 0) +
        "</td></tr>";
      if (open) {
        m.items.forEach((v) => {
          html +=
            '<tr class="row-variant"><td></td><td>' +
            badge(v.abc.class) +
            "</td><td>" +
            esc(v.sku) +
            "</td><td>" +
            fmtUsd(v.margin) +
            "</td><td>" +
            pct(v.share) +
            "</td><td>" +
            fmt(v.qty, 0) +
            "</td><td>" +
            fmt(v.stock, 0) +
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
        renderCatalog(skuMap, abc, invMap);
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
        rows.length + " productos con cambios / " + total + " con venta en algún mes";
    head.innerHTML =
      "<tr><th>Producto</th>" +
      periods.map((p) => "<th>" + p.short + "</th>").join("") +
      "<th>Tend.</th></tr>";
    body.innerHTML = rows
      .slice(0, 100)
      .filter((r) => matchesSearch(r.modelo))
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

  function computeCapital(skuMap, abc, invMap) {
    const cap = {
      A: { u: 0, v: 0, models: new Set() },
      B: { u: 0, v: 0, models: new Set() },
      C: { u: 0, v: 0, models: new Set() },
      X: { u: 0, v: 0, models: new Set() },
    };
    skuMap.forEach((it, sku) => {
      const stock = invMap.get(sku)?.total || 0;
      if (stock <= 0) return;
      const unitCost = it.qty > 0 ? it.cost / it.qty : 0;
      const val = stock * unitCost;
      let cl = "X";
      if (it.margin > 0) cl = abc.get(sku)?.class || "C";
      cap[cl].u += stock;
      cap[cl].v += val;
      cap[cl].models.add(it.modelo);
    });
    const totalU = cap.A.u + cap.B.u + cap.C.u + cap.X.u || 1;
    const totalV = cap.A.v + cap.B.v + cap.C.v + cap.X.v || 1;
    return { cap, totalU, totalV };
  }

  function renderCapital(skuMap, abc, invMap, summary) {
    const { cap, totalU, totalV } = computeCapital(skuMap, abc, invMap);
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
        '<div class="cap-card"><div class="lbl">Sin venta + en stock</div><div class="big">' +
        fmt(cap.X.u, 0) +
        '</div><div class="sub">' +
        cap.X.models.size +
        " modelos</div></div>";
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
        '<div class="diag r"><strong>$' +
        fmt(cap.C.v, 0) +
        '</strong> en clase C (~' +
        pct(summary.marginPct.C) +
        " del margen). Revisar promoción o bajar recompra.</div>" +
        '<div class="diag g"><strong>$' +
        fmt(cap.A.v, 0) +
        '</strong> en clase A (~' +
        pct(summary.marginPct.A) +
        " del margen). Proteger abastecimiento.</div>" +
        (cap.X.u > 0
          ? '<div class="diag m">' +
            fmt(cap.X.u, 0) +
            " und. con stock sin venta positiva en el período.</div>"
          : "");
    }
  }

  function renderAlerts(alerts, invMap) {
    const body = $("alertBody");
    if (!body) return;
    let rows = alerts.filter((r) => matchesSearch(r.modelo + r.sku));
    if (state.modelo) rows = rows.filter((r) => r.modelo === state.modelo);
    body.innerHTML = rows
      .slice(0, 200)
      .map(
        (r) =>
          "<tr><td>" +
          r.sev +
          '</td><td class="rn">' +
          esc(r.modelo) +
          "</td><td>" +
          esc(r.sku) +
          "</td><td>" +
          badge(r.from) +
          "→" +
          badge(r.to) +
          "</td><td>" +
          esc(r.period) +
          "</td><td>" +
          fmt((invMap.get(r.sku) || {}).total || 0, 0) +
          "</td><td>" +
          esc(r.hint) +
          "</td></tr>"
      )
      .join("");
    $("alertCount").textContent = rows.length + " movimientos";
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
      '<option value="">Todas</option>' +
      DATA.locations.map((s) => '<option value="' + esc(s) + '">' + esc(s) + "</option>").join("");
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
      const skuMap = aggregateSales(keys);
      const { abc } = computeAbc(skuMap);
      const summary = summarizePositive(abc, skuMap);
      const invMap = inventoryBySku();
      const models = aggregateByModel(skuMap, abc);
      const modelTrack = modelClassByPeriod();
      const alerts = detectTransitions(skuClassByPeriod());

      renderKpis(summary, skuMap, invMap, periodLabel());
      renderPremisaCard(summary);
      if (typeof Chart !== "undefined") renderCharts(summary);
      renderClassTable(models);
      renderCatalog(skuMap, abc, invMap);
      renderMigration(modelTrack);
      renderCapital(skuMap, abc, invMap, summary);
      renderAlerts(alerts, invMap);

      $("subtitle").textContent = periodLabel();
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
    const skuMap = aggregateSales(activePeriodKeys());
    const { abc } = computeAbc(skuMap);
    const invMap = inventoryBySku();
    const lines = ["modelo,sku,clase,margen,qty,stock"];
    skuMap.forEach((it, sku) => {
      if (it.margin <= 0) return;
      const a = abc.get(sku);
      lines.push(
        [
          it.modelo,
          sku,
          a.class,
          a.margin.toFixed(2),
          it.qty,
          invMap.get(sku)?.total || 0,
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
