/* Matriz ABC — lógica de negocio y render */
(function (global) {
  "use strict";

  const ABC_COLORS = { A: "#4caf76", B: "#ffc107", C: "#ef4444" };
  const TH = { A: 0.8, B: 0.95 };

  let DATA = null;
  let charts = {};
  let state = {
    years: new Set(),
    months: new Set(),
    store: "",
    category: "",
    location: "",
    abcClass: "",
    search: "",
    tab: "resumen",
  };

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
    return "$" + fmt(n, 2);
  }

  function pct(n) {
    return (n * 100).toFixed(1) + "%";
  }

  function destroyChart(key) {
    if (charts[key]) {
      charts[key].destroy();
      charts[key] = null;
    }
  }

  function activePeriodKeys() {
    if (!DATA) return [];
    return DATA.periods
      .filter((p) => {
        if (state.years.size && !state.years.has(p.year)) return false;
        if (state.months.size && !state.months.has(p.month)) return false;
        return true;
      })
      .map((p) => p.key);
  }

  function presetSemester(which) {
    state.months.clear();
    if (which === "h1") [1, 2, 3, 4, 5, 6].forEach((m) => state.months.add(m));
    if (which === "h2") [7, 8, 9, 10, 11, 12].forEach((m) => state.months.add(m));
    buildPeriodFilters();
    refresh();
  }

  function aggregateSales(periodKeys) {
    const skuMap = new Map();
    const periodSet = new Set(periodKeys);
    const skus = DATA.skus;
    const rows = DATA.salesRows;
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i];
      const pi = r[0];
      const pkey = DATA.periods[pi].key;
      if (!periodSet.has(pkey)) continue;
      if (state.store && DATA.stores[r[2]] !== state.store) continue;
      if (state.category && DATA.categories[r[3]] !== state.category) continue;
      const si = r[1];
      const sku = skus[si];
      if (!skuMap.has(sku)) {
        const m = DATA.skuMaster[sku] || {};
        skuMap.set(sku, {
          sku,
          producto: m.producto || sku,
          modelo: m.modelo || m.producto || sku,
          categoria: m.categoria || "",
          genero: m.genero || "",
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
    const skus = DATA.skus;
    const locs = DATA.locations;
    for (const sku of skus) {
      map.set(sku, { total: 0, byLoc: {} });
    }
    for (let i = 0; i < DATA.invRows.length; i++) {
      const r = DATA.invRows[i];
      const sku = skus[r[0]];
      const loc = locs[r[1]];
      if (state.location && loc !== state.location) continue;
      const ent = map.get(sku);
      if (!ent) continue;
      ent.total += r[2];
      ent.byLoc[loc] = (ent.byLoc[loc] || 0) + r[2];
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
    items.forEach((it) => {
      if (!out.has(it.sku)) {
        out.set(it.sku, {
          class: "C",
          rank: 99999,
          cumPct: 1,
          marginShare: 0,
          margin: it.margin,
        });
      } else {
        const e = out.get(it.sku);
        e.margin = it.margin;
      }
    });
    return { abc: out, items, totalPosMargin: totalPos };
  }

  function summarizeAbc(abc, items) {
    const counts = { A: 0, B: 0, C: 0 };
    const marginBy = { A: 0, B: 0, C: 0 };
    items.forEach((it) => {
      const c = abc.get(it.sku).class;
      counts[c]++;
      if (it.margin > 0) marginBy[c] += it.margin;
    });
    const n = items.length || 1;
    const mt = marginBy.A + marginBy.B + marginBy.C || 1;
    return {
      counts,
      skuPct: {
        A: counts.A / n,
        B: counts.B / n,
        C: counts.C / n,
      },
      marginPct: {
        A: marginBy.A / mt,
        B: marginBy.B / mt,
        C: marginBy.C / mt,
      },
      marginBy,
    };
  }

  function abcForSinglePeriod(periodKey) {
    return aggregateSales([periodKey]);
  }

  function monthlyAbcTimeline() {
    const timeline = [];
    DATA.periods.forEach((p) => {
      const map = aggregateSales([p.key]);
      const { abc, items } = computeAbc(map);
      const sum = summarizeAbc(abc, items);
      timeline.push({
        key: p.key,
        label: p.short,
        full: p.label,
        summary: sum,
      });
    });
    return timeline;
  }

  function skuClassByPeriod() {
    const result = {};
    DATA.periods.forEach((p) => {
      const map = abcForSinglePeriod(p.key);
      const { abc } = computeAbc(map);
      abc.forEach((v, sku) => {
        if (!result[sku]) result[sku] = {};
        result[sku][p.key] = v.class;
      });
    });
    return result;
  }

  function detectTransitions(classByPeriod) {
    const alerts = [];
    const periods = DATA.periods.map((p) => p.key);
    const severity = (from, to) => {
      if (from === "A" && to === "C") return 5;
      if (from === "A" && to === "B") return 4;
      if (from === "B" && to === "C") return 3;
      if (from === "C" && to === "A") return 2;
      if (from === "B" && to === "A") return 1;
      if (from === "C" && to === "B") return 1;
      return 0;
    };
    const actionHint = (from, to) => {
      if (from === "A" && (to === "B" || to === "C"))
        return "Intervención urgente: revisar stock, precio, visibilidad en tienda, marketing/promo.";
      if (from === "B" && to === "C")
        return "Riesgo de inventario lento: promoción, reubicación o bundle.";
      if (from === "C" && to === "A")
        return "Oportunidad: asegurar abastecimiento y escalar lo que está despegando.";
      if (to === "C")
        return "Capital retenido: evaluar liquidación o bajar compra.";
      return "Monitorear tendencia.";
    };
    Object.keys(classByPeriod).forEach((sku) => {
      const track = classByPeriod[sku];
      for (let i = 1; i < periods.length; i++) {
        const prev = periods[i - 1];
        const cur = periods[i];
        const from = track[prev];
        const to = track[cur];
        if (!from || !to || from === to) continue;
        const m = DATA.skuMaster[sku] || {};
        alerts.push({
          sku,
          modelo: m.modelo || m.producto || sku,
          producto: m.producto || sku,
          from,
          to,
          period: DATA.periods[i].label,
          periodKey: cur,
          sev: severity(from, to),
          hint: actionHint(from, to),
        });
      }
    });
    alerts.sort((a, b) => b.sev - a.sev || a.modelo.localeCompare(b.modelo));
    return alerts;
  }

  function aggregateByModel(skuMap, abc) {
    const models = new Map();
    skuMap.forEach((it, sku) => {
      const key = it.modelo || it.producto;
      if (!models.has(key)) {
        models.set(key, {
          modelo: key,
          skus: 0,
          qty: 0,
          revenue: 0,
          margin: 0,
          a: 0,
          b: 0,
          c: 0,
        });
      }
      const m = models.get(key);
      m.skus++;
      m.qty += it.qty;
      m.revenue += it.revenue;
      m.margin += it.margin;
      const cl = abc.get(sku).class;
      m[cl.toLowerCase()]++;
    });
    const list = [...models.values()].sort((a, b) => b.margin - a.margin);
    const totalPos = list.reduce((s, x) => s + Math.max(0, x.margin), 0);
    let cum = 0;
    list.forEach((m) => {
      if (m.margin <= 0) {
        m.abcClass = "C";
        m.cumPct = 1;
        return;
      }
      cum += m.margin;
      const cp = totalPos > 0 ? cum / totalPos : 1;
      m.cumPct = cp;
      if (cp <= TH.A) m.abcClass = "A";
      else if (cp <= TH.B) m.abcClass = "B";
      else m.abcClass = "C";
    });
    return list;
  }

  function paretoSeries(skuMap, abc) {
    const sorted = [...skuMap.values()]
      .filter((x) => x.margin > 0)
      .sort((a, b) => b.margin - a.margin);
    const total = sorted.reduce((s, x) => s + x.margin, 0) || 1;
    let cum = 0;
    return sorted.map((it, i) => {
      cum += it.margin;
      return {
        i: i + 1,
        sku: it.sku,
        modelo: it.modelo,
        margin: it.margin,
        cumPct: cum / total,
        cls: abc.get(it.sku).class,
      };
    });
  }

  function matchesSearch(row, q) {
    if (!q) return true;
    q = q.toLowerCase();
    return (
      row.sku.toLowerCase().includes(q) ||
      (row.producto && row.producto.toLowerCase().includes(q)) ||
      (row.modelo && row.modelo.toLowerCase().includes(q))
    );
  }

  function renderKpis(summary, skuMap, invMap, periodLabel) {
    const el = $("kpiBar");
    if (!el) return;
    const stockVal = [...skuMap.values()].reduce((s, it) => {
      const inv = invMap.get(it.sku);
      return s + (inv ? inv.total : 0);
    }, 0);
    el.innerHTML =
      '<div class="kpib"><div class="kv">' +
      summary.counts.A +
      '</div><div class="kl">SKUs A</div><div class="ksub">' +
      pct(summary.skuPct.A) +
      " catálogo</div></div>" +
      '<div class="kpib"><div class="kv">' +
      summary.counts.B +
      '</div><div class="kl">SKUs B</div><div class="ksub">' +
      pct(summary.skuPct.B) +
      "</div></div>" +
      '<div class="kpib"><div class="kv">' +
      summary.counts.C +
      '</div><div class="kl">SKUs C</div><div class="ksub">' +
      pct(summary.skuPct.C) +
      "</div></div>" +
      '<div class="kpib"><div class="kv">' +
      pct(summary.marginPct.A) +
      '</div><div class="kl">Margen en A</div><div class="ksub">obj. ~80%</div></div>' +
      '<div class="kpib"><div class="kv">' +
      fmtUsd(
        [...skuMap.values()].reduce((s, x) => s + x.margin, 0)
      ) +
      '</div><div class="kl">Margen neto</div><div class="ksub">' +
      periodLabel +
      '</div></div>' +
      '<div class="kpib"><div class="kv">' +
      fmt(stockVal, 0) +
      '</div><div class="kl">Und. inventario</div><div class="ksub">filtro ubicación</div></div>';
  }

  function renderPremisaCard(summary) {
    const el = $("premisaCompare");
    if (!el) return;
    const targets = DATA.meta.premisas;
    const rows = ["A", "B", "C"]
      .map((c) => {
        return (
          "<tr><td><span class=\"chip\" style=\"background:" +
          ABC_COLORS[c] +
          '"></span> ' +
          c +
          "</td><td>" +
          pct(summary.skuPct[c]) +
          " / " +
          targets[c].sku_pct_objetivo +
          "% SKUs</td><td>" +
          pct(summary.marginPct[c]) +
          " / " +
          targets[c].margen_pct +
          "% margen</td></tr>"
        );
      })
      .join("");
    el.innerHTML =
      '<table class="rt"><thead><tr><th>Clase</th><th>SKUs (real / objetivo)</th><th>Margen (real / objetivo)</th></tr></thead><tbody>' +
      rows +
      "</tbody></table>";
  }

  function renderCharts(summary, pareto, timeline) {
    destroyChart("donutSku");
    destroyChart("donutMarg");
    destroyChart("pareto");
    destroyChart("monthly");

    const ctx1 = $("cDonutSku");
    if (ctx1) {
      charts.donutSku = new Chart(ctx1, {
        type: "doughnut",
        data: {
          labels: ["A", "B", "C"],
          datasets: [
            {
              data: [
                summary.counts.A,
                summary.counts.B,
                summary.counts.C,
              ],
              backgroundColor: [ABC_COLORS.A, ABC_COLORS.B, ABC_COLORS.C],
            },
          ],
        },
        options: {
          plugins: { legend: { position: "bottom" } },
          maintainAspectRatio: false,
        },
      });
    }
    const ctx2 = $("cDonutMarg");
    if (ctx2) {
      charts.donutMarg = new Chart(ctx2, {
        type: "doughnut",
        data: {
          labels: ["A", "B", "C"],
          datasets: [
            {
              data: [
                summary.marginPct.A,
                summary.marginPct.B,
                summary.marginPct.C,
              ],
              backgroundColor: [ABC_COLORS.A, ABC_COLORS.B, ABC_COLORS.C],
            },
          ],
        },
        options: {
          plugins: {
            legend: { position: "bottom" },
            tooltip: {
              callbacks: {
                label: (c) => c.label + ": " + pct(c.raw),
              },
            },
          },
          maintainAspectRatio: false,
        },
      });
    }
    const ctx3 = $("cPareto");
    if (ctx3 && pareto.length) {
      const step = Math.max(1, Math.floor(pareto.length / 120));
      const sample = pareto.filter((_, i) => i % step === 0 || i < 30);
      charts.pareto = new Chart(ctx3, {
        type: "line",
        data: {
          labels: sample.map((p) => p.i),
          datasets: [
            {
              label: "% margen acumulado",
              data: sample.map((p) => p.cumPct * 100),
              borderColor: "#5b6af7",
              backgroundColor: "rgba(91,106,247,.15)",
              fill: true,
              tension: 0.2,
              yAxisID: "y",
            },
          ],
        },
        options: {
          maintainAspectRatio: false,
          scales: {
            y: {
              min: 0,
              max: 100,
              title: { display: true, text: "% acumulado" },
            },
            x: { title: { display: true, text: "Ranking SKU" } },
          },
          plugins: {
            annotation: {},
          },
        },
      });
    }
    const ctx4 = $("cMonthly");
    if (ctx4) {
      charts.monthly = new Chart(ctx4, {
        type: "bar",
        data: {
          labels: timeline.map((t) => t.label),
          datasets: [
            {
              label: "A",
              data: timeline.map((t) => t.summary.counts.A),
              backgroundColor: ABC_COLORS.A,
            },
            {
              label: "B",
              data: timeline.map((t) => t.summary.counts.B),
              backgroundColor: ABC_COLORS.B,
            },
            {
              label: "C",
              data: timeline.map((t) => t.summary.counts.C),
              backgroundColor: ABC_COLORS.C,
            },
          ],
        },
        options: {
          maintainAspectRatio: false,
          scales: { x: { stacked: true }, y: { stacked: true } },
          plugins: { legend: { position: "bottom" } },
        },
      });
    }
  }

  function badge(cls) {
    return (
      '<span class="abc abc-' +
      cls +
      '">' +
      cls +
      "</span>"
    );
  }

  function renderSkuTable(skuMap, abc, invMap) {
    const body = $("skuBody");
    if (!body) return;
    let rows = [...skuMap.values()].map((it) => {
      const a = abc.get(it.sku);
      const inv = invMap.get(it.sku) || { total: 0 };
      return { ...it, abc: a, stock: inv.total };
    });
    if (state.abcClass)
      rows = rows.filter((r) => r.abc.class === state.abcClass);
    rows = rows.filter((r) => matchesSearch(r, state.search));
    rows.sort((a, b) => a.abc.rank - b.abc.rank);
    const maxShow = 500;
    body.innerHTML = rows
      .slice(0, maxShow)
      .map((r, i) => {
        return (
          "<tr><td>" +
          (i + 1) +
          "</td><td>" +
          badge(r.abc.class) +
          "</td><td class=\"rn\">" +
          r.modelo +
          "</td><td>" +
          r.sku +
          "</td><td>" +
          fmtUsd(r.margin) +
          "</td><td>" +
          pct(r.abc.marginShare) +
          "</td><td>" +
          fmt(r.qty, 0) +
          "</td><td>" +
          fmt(r.stock, 0) +
          "</td><td>" +
          (r.abc.class === "A" && r.stock <= 0
            ? '<span class="flag">⚠ Sin stock</span>'
            : r.abc.class === "C" && r.stock > 10
              ? '<span class="flag warn">Capital retenido</span>'
              : "") +
          "</td></tr>"
        );
      })
      .join("");
    $("skuFootnote").textContent =
      rows.length > maxShow
        ? "Mostrando " + maxShow + " de " + rows.length + " SKUs."
        : rows.length + " SKUs en el período filtrado.";
  }

  function renderModelTable(models) {
    const body = $("modelBody");
    if (!body) return;
    let rows = models.filter((r) => matchesSearch(r, state.search));
    if (state.abcClass)
      rows = rows.filter((r) => r.abcClass === state.abcClass);
    body.innerHTML = rows
      .slice(0, 300)
      .map((r, i) => {
        return (
          "<tr><td>" +
          (i + 1) +
          "</td><td>" +
          badge(r.abcClass) +
          "</td><td class=\"rn\">" +
          r.modelo +
          "</td><td>" +
          r.skus +
          "</td><td>" +
          fmtUsd(r.margin) +
          "</td><td>" +
          fmt(r.qty, 0) +
          "</td><td>A:" +
          r.a +
          " B:" +
          r.b +
          " C:" +
          r.c +
          "</td></tr>"
        );
      })
      .join("");
  }

  function renderHeatmap(classByPeriod) {
    const wrap = $("abcHeatmap");
    if (!wrap) return;
    const periods = DATA.periods;
    const skuScores = Object.keys(classByPeriod).map((sku) => {
      const m = DATA.skuMaster[sku] || {};
      let changes = 0;
      for (let i = 1; i < periods.length; i++) {
        const a = classByPeriod[sku][periods[i - 1].key];
        const c = classByPeriod[sku][periods[i].key];
        if (a && c && a !== c) changes++;
      }
      return { sku, modelo: m.modelo || sku, changes };
    });
    skuScores.sort((a, b) => b.changes - a.changes);
    const top = skuScores.filter((x) => x.changes > 0).slice(0, 40);
    if (!top.length) {
      wrap.innerHTML = '<p class="nodata">Sin cambios de clase entre meses consecutivos.</p>';
      return;
    }
    let html =
      '<table class="hmt"><thead><tr><th>Modelo / SKU</th>';
    periods.forEach((p) => {
      html += "<th>" + p.short + "</th>";
    });
    html += "</tr></thead><tbody>";
    top.forEach((row) => {
      html += '<tr><td class="rl">' + row.modelo + "<br><small>" + row.sku + "</small></td>";
      periods.forEach((p) => {
        const cl = classByPeriod[row.sku][p.key] || "—";
        const bg =
          cl === "A"
            ? "rgba(76,175,118,.35)"
            : cl === "B"
              ? "rgba(255,193,7,.35)"
              : cl === "C"
                ? "rgba(239,68,68,.25)"
                : "transparent";
        html +=
          '<td style="background:' +
          bg +
          '">' +
          (cl === "—" ? "·" : cl) +
          "</td>";
      });
      html += "</tr>";
    });
    html += "</tbody></table>";
    wrap.innerHTML = html;
  }

  function renderAlerts(alerts, invMap) {
    const body = $("alertBody");
    if (!body) return;
    let rows = alerts;
    if (state.search)
      rows = rows.filter((r) => matchesSearch(r, state.search));
    body.innerHTML = rows
      .slice(0, 400)
      .map((r) => {
        const stock = (invMap.get(r.sku) || {}).total || 0;
        return (
          "<tr><td>" +
          r.sev +
          "</td><td class=\"rn\">" +
          r.modelo +
          "</td><td>" +
          r.sku +
          "</td><td>" +
          badge(r.from) +
          " → " +
          badge(r.to) +
          "</td><td>" +
          r.period +
          "</td><td>" +
          fmt(stock, 0) +
          "</td><td>" +
          r.hint +
          "</td></tr>"
        );
      })
      .join("");
    $("alertCount").textContent = rows.length + " movimientos detectados";
  }

  function renderMetaNotes() {
    const el = $("metaNotes");
    if (!el || !DATA.meta) return;
    const s = DATA.meta.stats;
    el.innerHTML =
      "<ul>" +
      DATA.meta.notas.map((n) => "<li>" + n + "</li>").join("") +
      "<li>Rango de ventas: <strong>" +
      s.rango +
      "</strong> · " +
      s.lineas_ventas.toLocaleString() +
      " líneas · Devoluciones (qty negativa): " +
      s.lineas_neg_qty.toLocaleString() +
      ".</li></ul>";
  }

  function buildPeriodFilters() {
    const years = [...new Set(DATA.periods.map((p) => p.year))].sort();
    const yc = $("yearChips");
    yc.innerHTML = "";
    years.forEach((y) => {
      const b = document.createElement("button");
      const on =
        !state.years.size || state.years.has(y);
      b.className = "mbtn" + (on ? " active" : "");
      b.textContent = String(y);
      b.onclick = () => {
        if (!state.years.size) {
          years.forEach((yy) => {
            if (yy !== y) state.years.add(yy);
          });
        } else if (state.years.has(y)) {
          state.years.delete(y);
          if (!state.years.size) state.years.clear();
        } else {
          state.years.add(y);
          if (state.years.size === years.length) state.years.clear();
        }
        buildPeriodFilters();
        refresh();
      };
      yc.appendChild(b);
    });

    const mc = $("monthChips");
    mc.innerHTML = "";
    const monthNames = [
      "Ene",
      "Feb",
      "Mar",
      "Abr",
      "May",
      "Jun",
      "Jul",
      "Ago",
      "Sep",
      "Oct",
      "Nov",
      "Dic",
    ];
    for (let m = 1; m <= 12; m++) {
      const b = document.createElement("button");
      const on = !state.months.size || state.months.has(m);
      b.className = "mbtn" + (on ? " active" : "");
      b.textContent = monthNames[m - 1];
      b.onclick = () => {
        if (!state.months.size) {
          for (let mm = 1; mm <= 12; mm++) {
            if (mm !== m) state.months.add(mm);
          }
        } else if (state.months.has(m)) {
          state.months.delete(m);
          if (!state.months.size) state.months.clear();
        } else {
          state.months.add(m);
          if (state.months.size === 12) state.months.clear();
        }
        buildPeriodFilters();
        refresh();
      };
      mc.appendChild(b);
    }
  }

  function fillSelects() {
    const fT = $("fStore");
    fT.innerHTML = '<option value="">Todas las tiendas</option>';
    DATA.stores.forEach((s) => {
      fT.innerHTML += '<option value="' + s + '">' + s + "</option>";
    });
    const fC = $("fCat");
    fC.innerHTML = '<option value="">Todas las categorías</option>';
    DATA.categories.forEach((s) => {
      fC.innerHTML += '<option value="' + s + '">' + s + "</option>";
    });
    const fL = $("fLoc");
    fL.innerHTML = '<option value="">Todas las ubicaciones</option>';
    DATA.locations.forEach((s) => {
      fL.innerHTML += '<option value="' + s + '">' + s + "</option>";
    });
  }

  function periodLabel() {
    const keys = activePeriodKeys();
    if (keys.length === DATA.periods.length) return "Todos los meses";
    if (keys.length === 1) {
      const p = DATA.periods.find((x) => x.key === keys[0]);
      return p ? p.label : keys.join(", ");
    }
    return keys.length + " meses seleccionados";
  }

  function refresh() {
    if (!DATA) return;
    const keys = activePeriodKeys();
    if (!keys.length) {
      $("periodWarn").style.display = "block";
      return;
    }
    $("periodWarn").style.display = "none";
    const skuMap = aggregateSales(keys);
    const { abc, items } = computeAbc(skuMap);
    const summary = summarizeAbc(abc, items);
    const invMap = inventoryBySku();
    const pareto = paretoSeries(skuMap, abc);
    const timeline = monthlyAbcTimeline();
    const classByPeriod = skuClassByPeriod();
    const alerts = detectTransitions(classByPeriod);
    const models = aggregateByModel(skuMap, abc);

    renderKpis(summary, skuMap, invMap, periodLabel());
    renderPremisaCard(summary);
    renderCharts(summary, pareto, timeline);
    renderSkuTable(skuMap, abc, invMap);
    renderModelTable(models);
    renderHeatmap(classByPeriod);
    renderAlerts(alerts, invMap);

    $("subtitle").textContent =
      periodLabel() +
      (state.store ? " · " + state.store : "") +
      (state.category ? " · " + state.category : "");
  }

  function st(name) {
    state.tab = name;
    document.querySelectorAll(".tab").forEach((t) => {
      t.classList.toggle("active", t.dataset.tab === name);
    });
    document.querySelectorAll(".sec").forEach((s) => {
      s.classList.toggle("active", s.id === "sec-" + name);
    });
  }

  function exportCsv() {
    const keys = activePeriodKeys();
    const skuMap = aggregateSales(keys);
    const { abc } = computeAbc(skuMap);
    const invMap = inventoryBySku();
    const lines = [
      "sku,modelo,producto,categoria,clase_abc,rank,margen,margen_pct,qty,stock",
    ];
    skuMap.forEach((it, sku) => {
      const a = abc.get(sku);
      const inv = invMap.get(sku) || { total: 0 };
      lines.push(
        [
          sku,
          it.modelo,
          it.producto,
          it.categoria,
          a.class,
          a.rank,
          a.margin.toFixed(2),
          (a.marginShare * 100).toFixed(2),
          it.qty,
          inv.total,
        ].join(",")
      );
    });
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "abc_inventario_export.csv";
    a.click();
  }

  function initFilters() {
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
      state.store = "";
      state.category = "";
      state.location = "";
      state.abcClass = "";
      state.search = "";
      state.months.clear();
      state.years.clear();
      $("fStore").value = "";
      $("fCat").value = "";
      $("fLoc").value = "";
      $("fAbc").value = "";
      $("fSearch").value = "";
      buildPeriodFilters();
      refresh();
    };
    $("btnExport").onclick = exportCsv;
  }

  function loadData(payload) {
    DATA = payload;
    renderMetaNotes();
    fillSelects();
    buildPeriodFilters();
    initFilters();
    refresh();
  }

  global.AbcDashboard = {
    loadData,
    st,
    refresh,
    presetSemester,
  };
})(window);
