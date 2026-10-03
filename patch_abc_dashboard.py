#!/usr/bin/env python3
"""Patch abc_dashboard_odoo.html in-place (single file, embedded data preserved)."""
from pathlib import Path
import re

ROOT = Path("/workspace")
HTML_PATH = ROOT / "abc_dashboard_odoo.html"
ENGINE_PATH = ROOT / "_abc_engine.js"

ENHANCEMENTS = r'''
  let stateActiveTab = "acciones";
  let searchDebounce = null;
  let ctxCache = null;
  let ctxCacheKey = "";
  let opCache = { key: "", mc: null, prod: null };

  function applyRuntimeConfig() {
    const cfg = (DATA && DATA.meta && DATA.meta.config) || {};
    if (cfg.abc_thresholds) {
      if (cfg.abc_thresholds.A != null) TH.A = cfg.abc_thresholds.A;
      if (cfg.abc_thresholds.B != null) TH.B = cfg.abc_thresholds.B;
    }
    if (cfg.efficiency_option != null) OPTION = cfg.efficiency_option;
    if (cfg.store_to_location) STORE2LOC = cfg.store_to_location;
    if (cfg.coverage_targets) TARGETS = cfg.coverage_targets;
  }

  function dashboardCacheKey() {
    return [
      state.timePreset,
      [...state.customPeriodKeys].sort().join(","),
      state.modelo,
      state.store,
      state.category,
      state.location,
      state.abcClass,
      state.search,
      state.channel,
      state.activeOnly ? 1 : 0,
      state.migMode,
      state.opCtx,
      state.opWin,
      state.opLevel,
    ].join("|");
  }

  function invalidateDashboardCache() {
    ctxCache = null;
    ctxCacheKey = "";
    opCache = { key: "", mc: null, prod: null };
  }

  function computeDashboardContext() {
    const key = dashboardCacheKey();
    if (ctxCache && ctxCacheKey === key) return ctxCache;
    const keys = activePeriodKeys();
    const scopeMap = aggregateSalesScope(keys);
    const act = computeActive();
    let excl = 0;
    if (state.activeOnly)
      scopeMap.forEach((it, sku) => {
        if (!act.has(sku)) {
          scopeMap.delete(sku);
          excl++;
        }
      });
    const { abc: globalAbc } = computeAbc(scopeMap);
    const summary = summarizePositive(globalAbc, scopeMap);
    const invMap = inventoryBySku(true);
    const allModels = buildModelIndex(scopeMap);
    ctxCache = {
      keys,
      scopeMap,
      act,
      excl,
      globalAbc,
      summary,
      invMap,
      allModels,
      modelTrack: null,
      alerts: null,
    };
    ctxCacheKey = key;
    return ctxCache;
  }

  function getMigrationAndAlerts(ctx) {
    if (!ctx.modelTrack) {
      ctx.modelTrack = modelClassByPeriod();
      ctx.alerts = detectTransitions(skuClassByPeriod());
    }
    return ctx;
  }

  function opCacheKey() {
    return dashboardCacheKey() + "|op";
  }

  function getOpLists(invMap) {
    const k = opCacheKey();
    if (opCache.key === k && opCache.mc) return opCache;
    const mcAll = opCompute("mc", invMap);
    const prod = opCompute("prod", invMap);
    opCache = { key: k, mc: mcAll, prod };
    return opCache;
  }

  function getOperativaList(invMap) {
    const { mc, prod } = getOpLists(invMap);
    let list = state.opLevel === "prod" ? prod : mc;
    if (state.opLevel === "prod") {
      const comp = {};
      mc.forEach((g) => {
        const c = (comp[g.producto] = comp[g.producto] || { A: 0, B: 0, C: 0, n: 0 });
        if (["A", "B", "C"].indexOf(g.cls) >= 0) {
          c[g.cls] += Math.max(0, g.margin);
          c.n++;
        }
      });
      list.forEach((g) => (g.comp = comp[g.key]));
    }
    return { mcAll: mc, list };
  }

  function tableNote(elId, shown, total, exportKind) {
    const el = $(elId);
    if (!el) return;
    const extra =
      total > shown
        ? ' · <button type="button" class="linkbtn" data-export="' +
          exportKind +
          '">Descargar los ' +
          total +
          "</button>"
        : "";
    el.innerHTML =
      "Mostrando <strong>" +
      shown +
      "</strong> de <strong>" +
      total +
      "</strong>" +
      extra;
    el.querySelectorAll("[data-export]").forEach((b) => {
      b.onclick = () => {
        if (b.dataset.export === "operativa") exportOperativaCsv();
        else if (b.dataset.export === "class") exportClassCsv();
        else if (b.dataset.export === "excepciones") exportExcepcionesCsv();
      };
    });
  }

  function renderAbcMapBanner() {
    const el = $("abcMapBanner");
    if (!el) return;
    el.innerHTML =
      '<div class="abc-map">' +
      '<div><strong>ABC Margen (SKU)</strong><span>Resumen, export CSV clásico · Pareto margen del período filtrado</span></div>' +
      '<div><strong>ABC Surtido (modelo)</strong><span>Clasificación, catálogo, migración, matriz margen×rotación</span></div>' +
      '<div><strong>ABC Operativo (modelo-color)</strong><span>Acciones de hoy, operativa, ficha · ventana ' +
      state.opWin +
      " meses + inventario</span></div></div>";
  }

  function goFicha(producto) {
    state.ficha = producto;
    st("ficha");
    if ($("fichaSel")) $("fichaSel").value = producto;
    renderFicha();
  }

  function accionesRow(g) {
    return (
      "<tr><td>" +
      clsBadge(g) +
      "</td><td>" +
      estBadge(g.estado) +
      '</td><td class="rn">' +
      esc(g.key) +
      '</td><td style="font-size:0.65rem;color:var(--mu)">' +
      esc(g.ctx) +
      "</td><td>" +
      fmt(g.stock) +
      "</td><td>" +
      covTxt(g.cov) +
      "</td><td>" +
      fmtMoney(g.margin) +
      "</td><td style=\"font-size:0.72rem\">" +
      esc(g.accion) +
      '</td><td><button type="button" class="linkbtn" data-ficha="' +
      esc(g.producto) +
      '">Ficha</button></td></tr>'
    );
  }

  function renderAccionesHoy(ctx) {
    const invMap = ctx.invMap;
    const { list } = getOperativaList(invMap);
    OP = { invMap, mcAll: getOpLists(invMap).mc };
    const valid = list.filter((g) => g.cls !== "—" && g.cls !== "AG");
    const quiebre = valid
      .filter(
        (g) =>
          (g.estado === "Quiebre" || g.estado === "Agotado") &&
          (g.cls === "A" || g.cls === "B" || g.cls === "N")
      )
      .sort((a, b) => (a.cls === "A" ? 0 : 1) - (b.cls === "A" ? 0 : 1) || b.margin - a.margin);
    const exceso = valid
      .filter((g) => g.estado === "Sobrestock" || g.estado === "Sin venta" || g.exVal > 0)
      .sort((a, b) => (b.exVal || 0) - (a.exVal || 0) || b.value - a.value);
    const agot = list
      .filter((g) => g.cls === "AG" && (g.was === "A" || g.was === "B"))
      .sort((a, b) => b.margin - a.margin);
    const capEx = list.reduce((s, g) => s + (g.exVal || 0), 0);

    const k = (v, l, s, c) =>
      '<div class="kpib"><div class="kv" style="color:' +
      (c || "var(--a)") +
      '">' +
      v +
      '</div><div class="kl">' +
      l +
      '</div><div class="ksub">' +
      (s || "") +
      "</div></div>";
    const kpis = $("accionesKpis");
    if (kpis)
      kpis.innerHTML =
        k(quiebre.length, "Quiebre / agotado A·B·N", "reponer", "#ef4444") +
        k(exceso.length, "Sobrestock / sin venta", "liquidar o pausar", "#f59e0b") +
        k(agot.length, "Agotados era A/B", "decidir reposición", "#a78bfa") +
        k(fmtMoney(capEx), "Exceso valorizado", "capital por encima de meta", "#fbbf24");

    function fill(id, rows, limit, noteId, exportKind) {
      const body = $(id);
      if (!body) return;
      const filtered = rows.filter((g) => matchesSearch(g.key + " " + g.ctx));
      body.innerHTML =
        filtered.slice(0, limit).map(accionesRow).join("") ||
        '<tr><td colspan="9">Sin casos con los filtros actuales</td></tr>';
      body.querySelectorAll("[data-ficha]").forEach((b) => {
        b.onclick = () => goFicha(b.getAttribute("data-ficha"));
      });
      tableNote(noteId, Math.min(limit, filtered.length), filtered.length, exportKind);
    }
    fill("accQuiebreBody", quiebre, 80, "accQuiebreNote", "operativa");
    fill("accExcesoBody", exceso, 80, "accExcesoNote", "operativa");
    fill("accAgotBody", agot, 50, "accAgotNote", "operativa");
  }

  function renderExcepciones(ctx) {
    const { scopeMap, globalAbc, invMap, act, excl } = ctx;
    const neg = [];
    const zero = [];
    const inactive = [];
    scopeMap.forEach((it, sku) => {
      const inv = invMap.get(sku)?.total || 0;
      const a = globalAbc.get(sku);
      if (it.margin < 0) neg.push({ sku, it, inv, a });
      else if (it.margin === 0) zero.push({ sku, it, inv, a });
    });
    if (!state.activeOnly) {
      invMap.forEach((inv, sku) => {
        if (!scopeMap.has(sku) && inv.total > 0) {
          const m = skuMeta(sku);
          inactive.push({ sku, it: { modelo: m.modelo, margin: 0, qty: 0, revenue: 0 }, inv: inv.total, a: null });
        }
      });
    }
    const body = $("excBody");
    if (!body) return;
    const rows = []
      .concat(
        neg.map((r) => ({ ...r, tipo: "Margen negativo" })),
        zero.map((r) => ({ ...r, tipo: "Margen cero" })),
        inactive.map((r) => ({ ...r, tipo: "Sin venta en período (con stock)" }))
      )
      .filter((r) => matchesSearch(r.sku + " " + (r.it.modelo || "")));
    body.innerHTML = rows
      .slice(0, 300)
      .map((r) => {
        const v = variantInfo(r.sku);
        return (
          "<tr><td>" +
          esc(r.tipo) +
          "</td><td class=\"rn\">" +
          esc(v.label) +
          "</td><td>" +
          esc(r.sku) +
          "</td><td>" +
          fmtMoney(r.it.margin) +
          "</td><td>" +
          fmt(r.inv) +
          "</td><td>" +
          (r.a ? badge(r.a.class) : "—") +
          "</td></tr>"
        );
      })
      .join("");
    tableNote("excNote", Math.min(300, rows.length), rows.length, "excepciones");
    const sub = $("excSub");
    if (sub)
      sub.textContent =
        neg.length +
        " con margen negativo · " +
        zero.length +
        " con margen cero · " +
        (state.activeOnly ? excl + " SKUs inactivos excluidos del ranking" : inactive.length + " SKUs con stock fuera del scope de ventas");
  }

  function csvEscape(v) {
    const s = String(v == null ? "" : v);
    return s.indexOf(",") >= 0 || s.indexOf('"') >= 0 ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  function downloadCsv(name, lines) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8" }));
    a.download = name;
    a.click();
  }

  function exportOperativaCsv() {
    if (!ctxCache) computeDashboardContext();
    const { list } = getOperativaList(ctxCache.invMap);
    const header =
      "modelo_color,producto,contexto,clase,estado,accion,margen,unidades,stock,cobertura_meses,capital_costo,exceso_valor,sell_through,banda_eficiencia,xyz";
    const lines = [header];
    list
      .filter((g) => g.cls !== "—")
      .forEach((g) => {
        lines.push(
          [
            g.key,
            g.producto,
            g.ctx,
            g.cls,
            g.estado,
            g.accion,
            g.margin.toFixed(2),
            g.units,
            g.stock,
            g.cov === Infinity ? "sin_venta" : g.cov == null ? "" : g.cov.toFixed(2),
            g.value.toFixed(2),
            (g.exVal || 0).toFixed(2),
            g.st != null ? (g.st * 100).toFixed(1) + "%" : "",
            g.band,
            g.xyz,
          ].map(csvEscape).join(",")
        );
      });
    downloadCsv("abc_operativo.csv", lines);
  }

  function exportClassCsv() {
    const ctx = computeDashboardContext();
    const rows = filterModels(ctx.allModels);
    const header = "rank,modelo,abc_margen,matriz,ingresos_netos,margen,share_margen,unidades,abc_rotacion";
    const lines = [header];
    rows.forEach((m) => {
      lines.push(
        [m.rank, m.modelo, m.abcClass, m.matrix, m.revenue, m.margin, m.marginShare, m.qty, m.rotClass]
          .map(csvEscape)
          .join(",")
      );
    });
    downloadCsv("abc_modelos.csv", lines);
  }

  function exportExcepcionesCsv() {
    const ctx = computeDashboardContext();
    renderExcepciones(ctx);
    const body = $("excBody");
    if (!body) return;
    const header = "tipo,modelo,sku,margen,stock,clase_abc_periodo";
    const lines = [header];
    body.querySelectorAll("tr").forEach((tr) => {
      const cells = [...tr.children].map((td) => td.textContent.trim());
      if (cells.length >= 6) lines.push(cells.map(csvEscape).join(","));
    });
    downloadCsv("abc_excepciones.csv", lines);
  }

  function updateFilterBadge() {
    const el = $("filterBadge");
    if (!el) return;
    let n = 0;
    if (state.modelo) n++;
    if (state.store) n++;
    if (state.category) n++;
    if (state.location) n++;
    if (state.abcClass) n++;
    if (state.search) n++;
    if (state.channel !== "retail") n++;
    if (!state.activeOnly) n++;
    if (state.timePreset !== "all") n++;
    el.textContent = n ? "Filtros activos (" + n + ")" : "";
    el.style.display = n ? "inline-block" : "none";
  }

  function syncUrlFromState() {
    if (typeof history === "undefined" || !history.replaceState) return;
    const p = new URLSearchParams();
    p.set("tab", stateActiveTab);
    if (state.channel !== "retail") p.set("channel", state.channel);
    if (state.opWin !== 6) p.set("win", String(state.opWin));
    if (!state.activeOnly) p.set("active", "0");
    if (state.store) p.set("store", state.store);
    if (state.category) p.set("category", state.category);
    if (state.modelo) p.set("modelo", state.modelo);
    const qs = p.toString();
    history.replaceState(null, "", qs ? "?" + qs : location.pathname);
  }

  function applyStateFromUrl() {
    try {
      const p = new URLSearchParams(location.search);
      if (p.get("tab")) stateActiveTab = p.get("tab");
      if (p.get("channel")) state.channel = p.get("channel");
      if (p.get("win")) state.opWin = +p.get("win") || state.opWin;
      if (p.get("active") === "0") state.activeOnly = false;
      if (p.get("store")) state.store = p.get("store");
      if (p.get("category")) state.category = p.get("category");
      if (p.get("modelo")) state.modelo = p.get("modelo");
    } catch (e) {
      /* ignore */
    }
  }

  function renderActiveTab(ctx) {
    const tab = stateActiveTab;
    if (tab === "acciones") renderAccionesHoy(ctx);
    else if (tab === "excepciones") renderExcepciones(ctx);
    else if (tab === "resumen") {
      if (typeof Chart !== "undefined") renderCharts(ctx.summary);
      else {
        const w = $("chartWarn");
        if (w) w.style.display = "block";
      }
      renderPremisaCard(ctx.summary);
    } else if (tab === "clasificacion") renderClassTable(ctx.allModels);
    else if (tab === "catalogo") renderCatalog(ctx.scopeMap, ctx.globalAbc, ctx.invMap);
    else if (tab === "evolucion") {
      getMigrationAndAlerts(ctx);
      renderMigration(ctx.modelTrack);
    } else if (tab === "capital") renderCapital(ctx.scopeMap, ctx.globalAbc, ctx.invMap, ctx.summary);
    else if (tab === "matriz") renderCrossMatrix(ctx.allModels);
    else if (tab === "alertas") {
      getMigrationAndAlerts(ctx);
      renderAlerts(ctx.alerts, ctx.invMap);
    } else if (tab === "operativa") renderOperativa(ctx.invMap);
    else if (tab === "ficha") renderFicha();
  }

  function scheduleRefresh() {
    invalidateDashboardCache();
    refresh();
  }

  function debouncedSearchRefresh() {
    if (searchDebounce) clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => scheduleRefresh(), 300);
  }
'''

def patch_engine(engine: str) -> str:
    engine = engine.replace("  const TH = { A: 0.8, B: 0.95 };", "  let TH = { A: 0.8, B: 0.95 };")
    engine = engine.replace(
        "  let filtersInitialized = false;",
        "  let filtersInitialized = false;\n" + ENHANCEMENTS,
    )
    engine = engine.replace("  const OPTION = 1;", "  let OPTION = 1;")
    engine = engine.replace(
        "  const STORE2LOC = { GRIETA:",
        "  let STORE2LOC = { GRIETA:",
    )
    engine = engine.replace(
        "  const TARGETS = {",
        "  let TARGETS = {",
    )

    old_refresh = engine[engine.find("  function refresh()") : engine.find("  function st(name)")]
    new_refresh = '''  function refresh() {
    if (!DATA) return;
    try {
      const keys = activePeriodKeys();
      if (!keys.length) {
        $("periodWarn").style.display = "block";
        return;
      }
      $("periodWarn").style.display = "none";
      const ctx = computeDashboardContext();
      const ae = $("activeNote");
      if (ae)
        ae.textContent = state.activeOnly
          ? ctx.excl + " SKUs agotados y sin venta en 3 meses fuera del ranking"
          : "Incluye agotados sin venta reciente";
      renderKpis(ctx.summary, ctx.scopeMap, ctx.invMap, periodLabel());
      renderAbcMapBanner();
      updateFilterBadge();
      renderActiveTab(ctx);
      $("subtitle").textContent = periodLabel() + " · " + ({ retail: "Canal retail", sin_grandes: "Sin pedidos grandes", all: "Todos los canales", corp: "Corporativo" }[state.channel] || state.channel);
      syncUrlFromState();
    } catch (err) {
      console.error(err);
      showLoadError("Error: " + err.message);
    }
  }

'''
    engine = engine.replace(old_refresh, new_refresh)

    old_st = '''  function st(name) {
    document.querySelectorAll(".tab").forEach((t) => {
      t.classList.toggle("active", t.dataset.tab === name);
    });
    document.querySelectorAll(".sec").forEach((s) => {
      s.classList.toggle("active", s.id === "sec-" + name);
    });
  }
'''
    new_st = '''  function st(name) {
    stateActiveTab = name;
    document.querySelectorAll(".tab").forEach((t) => {
      t.classList.toggle("active", t.dataset.tab === name);
    });
    document.querySelectorAll(".sec").forEach((s) => {
      s.classList.toggle("active", s.id === "sec-" + name);
    });
    if (DATA) {
      const ctx = computeDashboardContext();
      renderActiveTab(ctx);
      syncUrlFromState();
    }
  }
'''
    engine = engine.replace(old_st, new_st)

    engine = engine.replace(
        'if (sub) sub.textContent = rows.length + " productos (clase ABC fija al catálogo completo del período)";',
        'if (sub) tableNote("classTableSub", Math.min(250, rows.length), rows.length, "class");',
    )
    engine = engine.replace(
        "    void 0;\n    const agot = list.filter",
        "    const agot = list.filter",
    )

    # renderOperativa: use cache at start
    engine = engine.replace(
        "    const mcAll = opCompute(\"mc\", invMap);\n    let list = mcAll;\n    if (state.opLevel === \"prod\") {\n      list = opCompute(\"prod\", invMap);",
        "    const opData = getOperativaList(invMap);\n    const mcAll = opData.mcAll;\n    let list = opData.list;\n    if (false && state.opLevel === \"prod\") {\n      list = opCompute(\"prod\", invMap);",
    )
    engine = engine.replace(
        '    $("opCount").textContent = f.length + " modelo-color · ventana: "',
        '    tableNote("opCount", Math.min(500, f.length), f.length, "operativa");\n    const _opCountExtra = f.length + " modelo-color · ventana: "',
    )
    # fix opCount - the replacement might break - let me read that section after patch

    engine = engine.replace(
        "    const mc = opCompute(\"mc\", invMap).filter((g) => g.producto === P);",
        "    const mc = getOpLists(invMap).mc.filter((g) => g.producto === P);",
    )
    engine = engine.replace(
        "    const pr = opCompute(\"prod\", invMap).find((g) => g.key === P);",
        "    const pr = getOpLists(invMap).prod.find((g) => g.key === P);",
    )

    old_boot = '''  function boot(payload) {
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
'''
    new_boot = '''  function boot(payload) {
    DATA = payload;
    if (!DATA?.periods?.length) {
      showLoadError("Datos incompletos.");
      return;
    }
    applyRuntimeConfig();
    applyStateFromUrl();
    fillSelects();
    if (state.modelo && $("fModel")) $("fModel").value = state.modelo;
    if (state.store && $("fStore")) $("fStore").value = state.store;
    if (state.category && $("fCat")) $("fCat").value = state.category;
    if (state.channel && $("fChannel")) $("fChannel").value = state.channel;
    if ($("fActive")) $("fActive").checked = state.activeOnly;
    if ($("opWin")) $("opWin").value = String(state.opWin);
    initFilters();
    buildPeriodFilters();
    st(stateActiveTab);
    refresh();
  }
'''
    engine = engine.replace(old_boot, new_boot)

    # initFilters: debounce search, export buttons, toggle advanced
    engine = engine.replace(
        '    $("fSearch").oninput = (e) => {\n      state.search = e.target.value.trim();\n      refresh();\n    };',
        '    $("fSearch").oninput = (e) => {\n      state.search = e.target.value.trim();\n      debouncedSearchRefresh();\n    };',
    )
    engine = engine.replace(
        '      refresh();\n    };\n    $("btnExport").onclick = exportCsv;',
        '      scheduleRefresh();\n    };\n    $("btnExport").onclick = exportCsv;\n    if ($("btnExportOp")) $("btnExportOp").onclick = exportOperativaCsv;\n    if ($("btnToggleFilters")) {\n      $("btnToggleFilters").onclick = () => {\n        const p = $("fbarAdvanced");\n        if (p) p.classList.toggle("open");\n      };\n    }',
    )
    # replace all refresh() in initFilters onchange with scheduleRefresh - selective
    for hook in [
        'state.modelo = e.target.value;\n      refresh();',
        'state.store = e.target.value;\n      refresh();',
        'state.category = e.target.value;\n      refresh();',
        'state.location = e.target.value;\n      refresh();',
        'state.activeOnly = e.target.checked; refresh();',
        'state.migMode = e.target.value; refresh();',
        'state.migAll = e.target.checked; refresh();',
        'state.opCtx = e.target.value; refresh();',
        'state.opWin = +e.target.value; refresh();',
        'state.opLevel = e.target.value; refresh();',
        'state.opCls = e.target.value; refresh();',
        'state.opEst = e.target.value; refresh();',
        'state.channel = e.target.value;\n      refresh();',
        'state.abcClass = e.target.value;\n      refresh();',
        'buildPeriodFilters();\n      refresh();',
    ]:
        engine = engine.replace(hook, hook.replace("refresh();", "scheduleRefresh();").replace(" refresh();", " scheduleRefresh();"))

    engine = engine.replace(
        "  global.AbcDashboard = { loadData, st, refresh, setTimePreset };",
        "  global.AbcDashboard = { loadData, st, refresh, setTimePreset, exportOperativaCsv, exportClassCsv };",
    )

    return engine


def patch_html(html: str) -> str:
    if "BUILD: Odoo" not in html:
        html = html.replace(
            "<!DOCTYPE html>",
            "<!DOCTYPE html>\n<!-- BUILD: Odoo → build_abc_dashboard.py → HTML único con JSON embebido (#abc-embedded-data). Regenerar tras cambios en ventas/costo/inventario. -->",
        )

    css_extra = """
.abc-map{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:0 32px 10px;padding:10px 12px;background:var(--surf);border:1px solid var(--brd);border-radius:var(--r);font-size:0.68rem;line-height:1.45}
.abc-map strong{display:block;font-family:var(--fh);font-size:0.72rem;color:var(--a);margin-bottom:2px}
.abc-map span{color:var(--mu)}
.fbar-compact{display:flex;gap:8px;align-items:center;flex-wrap:wrap;width:100%}
.fbar-adv{display:none;width:100%;gap:8px;align-items:center;flex-wrap:wrap;padding-top:6px;border-top:1px dashed var(--brd);margin-top:6px}
.fbar-adv.open{display:flex}
.linkbtn{background:transparent;border:none;color:var(--a);cursor:pointer;font-size:0.72rem;text-decoration:underline;padding:0}
#filterBadge{font-size:0.62rem;color:var(--b);margin-left:6px}
#chartWarn{display:none;margin:0 32px 8px;padding:8px;border-radius:8px;background:rgba(251,191,36,.12);border:1px solid var(--b);color:var(--b);font-size:0.74rem}
details.glossary{margin-top:10px;font-size:0.72rem;color:var(--mu);line-height:1.55}
details.glossary summary{cursor:pointer;color:var(--a);font-weight:600}
@media(max-width:960px){.abc-map{grid-template-columns:1fr;margin:0 16px 10px}}
"""
    html = html.replace("@media(max-width:960px){.g2,.g3,.chart-row{grid-template-columns:1fr}}", css_extra + "\n@media(max-width:960px){.g2,.g3,.chart-row{grid-template-columns:1fr}}")

    html = html.replace(
        '<div id="periodWarn">',
        '<div id="chartWarn">No se cargó Chart.js (CDN bloqueado). Los números y tablas funcionan; los gráficos del resumen no.</div>\n<div id="abcMapBanner"></div>\n<div id="periodWarn">',
    )

    old_fbar = '''<div class="fbar">
  <label>Modelo</label><select id="fModel"></select>
  <label>Tienda</label><select id="fStore"></select>
  <label title="Excluye del ranking los SKUs sin stock y sin venta en los últimos 3 meses"><input type="checkbox" id="fActive" checked> Solo surtido activo</label><span id="activeNote" style="font-size:0.6rem;color:var(--mu)"></span>
  <label>Canal</label><select id="fChannel"><option value="retail" selected>Retail (sin corporativo ni pedidos)</option><option value="sin_grandes">Todos sin pedidos grandes (≥100 und)</option><option value="all">Todos los canales</option><option value="corp">Solo corporativo</option></select>
  <label>Categoría</label><select id="fCat"></select>
  <label>Stock en</label><select id="fLoc"></select>
  <label>Clase</label><select id="fAbc"><option value="">Todas</option><option value="A">A</option><option value="B">B</option><option value="C">C</option></select>
  <label>Buscar</label><input id="fSearch" placeholder="SKU, modelo…" size="16">
  <button class="fbtn" type="button" id="btnExport">CSV</button>
  <button class="fbtn" type="button" id="btnReset" style="background:var(--s3);color:var(--tx);border:1px solid var(--brd)">Limpiar</button>
</div>'''

    new_fbar = '''<div class="fbar">
  <div class="fbar-compact">
    <label>Canal</label><select id="fChannel"><option value="retail" selected>Retail (sin corporativo ni pedidos)</option><option value="sin_grandes">Todos sin pedidos grandes (≥100 und)</option><option value="all">Todos los canales</option><option value="corp">Solo corporativo</option></select>
    <label title="Excluye del ranking los SKUs sin stock y sin venta en los últimos 3 meses"><input type="checkbox" id="fActive" checked> Solo surtido activo</label><span id="activeNote" style="font-size:0.6rem;color:var(--mu)"></span>
    <label>Buscar</label><input id="fSearch" placeholder="SKU, modelo…" size="16">
    <button class="fbtn" type="button" id="btnToggleFilters" style="background:var(--s3);color:var(--tx);border:1px solid var(--brd)">Más filtros</button>
    <span id="filterBadge"></span>
    <button class="fbtn" type="button" id="btnExport" title="ABC margen SKU">CSV ABC</button>
    <button class="fbtn" type="button" id="btnExportOp" title="Clasificación operativa completa">CSV operativo</button>
    <button class="fbtn" type="button" id="btnReset" style="background:var(--s3);color:var(--tx);border:1px solid var(--brd)">Limpiar</button>
  </div>
  <div class="fbar-adv" id="fbarAdvanced">
    <label>Modelo</label><select id="fModel"></select>
    <label>Tienda</label><select id="fStore"></select>
    <label>Categoría</label><select id="fCat"></select>
    <label>Stock en</label><select id="fLoc"></select>
    <label>Clase ABC margen</label><select id="fAbc"><option value="">Todas</option><option value="A">A</option><option value="B">B</option><option value="C">C</option></select>
  </div>
</div>'''
    html = html.replace(old_fbar, new_fbar)

    old_tabs = '''<div class="tabs">
  <button class="tab active" data-tab="resumen" onclick="AbcDashboard.st('resumen')">Resumen</button>
  <button class="tab" data-tab="clasificacion" onclick="AbcDashboard.st('clasificacion')">Clasificación ABC</button>
  <button class="tab" data-tab="catalogo" onclick="AbcDashboard.st('catalogo')">Catálogo</button>
  <button class="tab" data-tab="evolucion" onclick="AbcDashboard.st('evolucion')">Migración mensual</button>
  <button class="tab" data-tab="capital" onclick="AbcDashboard.st('capital')">Capital e inventario</button>
  <button class="tab" data-tab="matriz" onclick="AbcDashboard.st('matriz')">Matriz cruzada</button>
  <button class="tab" data-tab="alertas" onclick="AbcDashboard.st('alertas')">Alertas</button>
  <button class="tab" data-tab="operativa" onclick="AbcDashboard.st('operativa')">⭐ Clasificación operativa</button>
  <button class="tab" data-tab="ficha" onclick="AbcDashboard.st('ficha')">🔎 Ficha de modelo</button>
</div>
<div class="content">
  <section class="sec active" id="sec-resumen">'''

    new_tabs = '''<div class="tabs">
  <button class="tab active" data-tab="acciones" onclick="AbcDashboard.st('acciones')">Acciones de hoy</button>
  <button class="tab" data-tab="excepciones" onclick="AbcDashboard.st('excepciones')">Excepciones</button>
  <button class="tab" data-tab="resumen" onclick="AbcDashboard.st('resumen')">Resumen ABC margen</button>
  <button class="tab" data-tab="clasificacion" onclick="AbcDashboard.st('clasificacion')">ABC surtido (modelo)</button>
  <button class="tab" data-tab="catalogo" onclick="AbcDashboard.st('catalogo')">Catálogo</button>
  <button class="tab" data-tab="evolucion" onclick="AbcDashboard.st('evolucion')">Migración</button>
  <button class="tab" data-tab="capital" onclick="AbcDashboard.st('capital')">Capital</button>
  <button class="tab" data-tab="matriz" onclick="AbcDashboard.st('matriz')">Matriz margen×rot.</button>
  <button class="tab" data-tab="alertas" onclick="AbcDashboard.st('alertas')">Alertas SKU</button>
  <button class="tab" data-tab="operativa" onclick="AbcDashboard.st('operativa')">ABC operativo</button>
  <button class="tab" data-tab="ficha" onclick="AbcDashboard.st('ficha')">Ficha modelo</button>
</div>
<div class="content">
  <section class="sec active" id="sec-acciones">
    <div class="card">
      <h3>Acciones de hoy</h3>
      <div class="sub">Colas accionables desde la clasificación operativa (misma ventana y filtros de canal/tienda/categoría)</div>
      <div class="kpi-bar" id="accionesKpis" style="margin-bottom:12px"></div>
    </div>
    <div class="g2">
      <div class="card">
        <h3>Quiebre o agotado (A · B · Nuevo)</h3>
        <div class="sub" id="accQuiebreNote"></div>
        <div class="cscroll"><table class="ct"><thead><tr><th>Clase</th><th>Estado</th><th>Modelo · color</th><th>Contexto</th><th>Stock</th><th>Cob.</th><th>Margen</th><th>Acción</th><th></th></tr></thead><tbody id="accQuiebreBody"></tbody></table></div>
      </div>
      <div class="card">
        <h3>Sobrestock, sin venta y exceso</h3>
        <div class="sub" id="accExcesoNote"></div>
        <div class="cscroll"><table class="ct"><thead><tr><th>Clase</th><th>Estado</th><th>Modelo · color</th><th>Contexto</th><th>Stock</th><th>Cob.</th><th>Margen</th><th>Acción</th><th></th></tr></thead><tbody id="accExcesoBody"></tbody></table></div>
      </div>
    </div>
    <div class="card">
      <h3>Agotados que eran A o B</h3>
      <div class="sub" id="accAgotNote"></div>
      <div class="cscroll"><table class="ct"><thead><tr><th>Clase</th><th>Estado</th><th>Modelo · color</th><th>Contexto</th><th>Stock</th><th>Cob.</th><th>Margen</th><th>Acción</th><th></th></tr></thead><tbody id="accAgotBody"></tbody></table></div>
    </div>
  </section>
  <section class="sec" id="sec-excepciones">
    <div class="card">
      <h3>Excepciones</h3>
      <div class="sub" id="excSub">Margen ≤ 0, sin venta en el período y otros casos fuera del ranking positivo</div>
      <div class="sub" id="excNote"></div>
      <div class="cscroll"><table class="ct"><thead><tr><th>Tipo</th><th>Variante</th><th>SKU</th><th>Margen período</th><th>Stock</th><th>ABC margen SKU</th></tr></thead><tbody id="excBody"></tbody></table></div>
    </div>
  </section>
  <section class="sec" id="sec-resumen">'''

    html = html.replace(old_tabs, new_tabs)

    # glossary accordion in operativa
    long_glossary = html[html.find("<strong>Cómo se asigna la clase"): html.find("</div>\n    </div>\n    <div class=\"card\">\n      <h3>🟣 Agotados")]
    if long_glossary:
        replacement = '''<details class="glossary"><summary>Cómo se calcula la clase operativa (glosario)</summary>
        <p><strong>En orden:</strong> ① surtido activo · ② Pareto margen + unidades por contexto (80/95) → letra conjunta · ③ continuidad en la ventana (A ≥ 2/3 meses, B ≥ 1/3) · ④ eficiencia sell-through vs mediana del contexto (informativa; opción 2 puede bajar letra).</p>
        <p><strong>Estados:</strong> cobertura vs meta por línea (Manufactura / Equipamiento) → quiebre, sano, sobrestock · SV sin venta con stock · AG agotado sin rotación · N nuevo (&lt;3 meses vendiendo).</p>
        <p><strong>Exceso:</strong> stock sobre venta prom. 6m × cobertura máxima; 6+ meses sin venta = todo exceso.</p>
      </details>'''
        html = html.replace(
            '<div class="sub" style="margin-top:10px;line-height:1.6">\n        <strong>Cómo se asigna la clase (en orden):</strong>' + long_glossary.split("<strong>Cómo se asigna la clase (en orden):</strong>", 1)[1],
            replacement,
        )

    html = html.replace("<h3>🟣 Agotados que eran A o B", "<h3>Agotados que eran A o B")
    html = html.replace(
        '<h3>Clasificación operativa</h3>',
        '<h3>ABC operativo (modelo-color)</h3>',
    )
    html = html.replace(
        '<h3>Clasificación ABC — productos</h3>',
        '<h3>ABC surtido por modelo</h3>',
    )
    html = html.replace(
        '<div class="sub" id="classTableSub"></div>',
        '<div class="sub" id="classTableSub"></div>',
    )

    html = html.replace(
        '<div class="footer">ABC · margen',
        '<div class="footer"><strong>Uso confidencial</strong> — no reenviar fuera de la empresa · ABC · margen',
    )

    html = html.replace(
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>',
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js" crossorigin="anonymous" onerror="window.__chartJsMissing=true"></script>',
    )

    return html


def reassemble(html: str, engine: str) -> str:
    parts = re.split(r"(<script[^>]*>)([\s\S]*?)(</script>)", html)
    script_idx = 0
    out = []
    for i in range(0, len(parts), 4):
        if i >= len(parts):
            break
        out.append(parts[i])
        if i + 3 >= len(parts):
            continue
        open_tag, body, close_tag = parts[i + 1], parts[i + 2], parts[i + 3]
        if open_tag.startswith("<script"):
            if script_idx == 1:
                out.append(open_tag + engine + close_tag)
            else:
                out.append(open_tag + body + close_tag)
            script_idx += 1
        else:
            out.append(open_tag + body + close_tag)
    return "".join(out)


def main():
    html = HTML_PATH.read_text("utf-8")
    engine = ENGINE_PATH.read_text("utf-8")
    engine = patch_engine(engine)
    ENGINE_PATH.write_text(engine, encoding="utf-8")
    html = patch_html(html)
    html = reassemble(html, engine)
    HTML_PATH.write_text(html, encoding="utf-8")
    print("Patched", HTML_PATH, "bytes", HTML_PATH.stat().st_size)


if __name__ == "__main__":
    main()
