(function () {
  "use strict";

  function $(id) {
    return document.getElementById(id);
  }

  function fmt(n, d) {
    d = d === undefined ? 0 : d;
    if (n == null || n === "" || Number.isNaN(Number(n))) return "—";
    return Number(n).toLocaleString("es-VE", {
      minimumFractionDigits: d,
      maximumFractionDigits: d,
    });
  }

  function showError(msg) {
    var el = $("loadErr");
    if (el) {
      el.style.display = "block";
      el.textContent = msg;
    }
    var sub = $("subtitle");
    if (sub) sub.textContent = "No se pudieron cargar los datos.";
  }

  function boot() {
    var DATA = window.BF_PROPOSAL_DATA;
    if (!DATA || !DATA.skus) {
      showError(
        "No se encontró bf_proposal_data.js. Abrí el HTML desde la carpeta black-friday-categoria-c (junto al .js) o usá: python3 -m http.server"
      );
      return;
    }

    var state = { seg: "", search: "" };

    function filtered() {
      return DATA.skus.filter(function (r) {
        if (state.seg && r.segmento !== state.seg) return false;
        if (state.search) {
          var q = state.search.toLowerCase();
          var blob = (r.sku + " " + r.modelo + " " + (r.producto || "")).toLowerCase();
          if (blob.indexOf(q) < 0) return false;
        }
        return true;
      });
    }

    function tab(name) {
      document.querySelectorAll(".tab").forEach(function (t) {
        t.classList.toggle("active", t.dataset.tab === name);
      });
      document.querySelectorAll(".sec").forEach(function (s) {
        s.classList.toggle("active", s.id === "sec-" + name);
      });
    }

    document.querySelectorAll(".tab").forEach(function (t) {
      t.onclick = function () {
        tab(t.dataset.tab);
      };
    });

    function renderKpis() {
      var s = DATA.summary;
      $("subtitle").textContent = DATA.meta.subtitle + " · " + s.periodo_ventas;
      $("periodLabel").textContent = s.periodo_ventas;
      var meses = (DATA.meta.meses_incluidos || []).join(", ");
      if ($("monthsList")) $("monthsList").textContent = meses || "—";
      $("kpis").innerHTML = [
        ["SKUs ofertables", s.skus_c_total],
        ["Und. stock", s.unidades_stock],
        ["En tiendas", s.unidades_tiendas],
        ["Manufactura", s.manufactura_skus],
        ["Brecha BF", s.brecha_total_unidades],
      ]
        .map(function (pair) {
          return (
            '<div class="kpi"><div class="v">' +
            fmt(pair[1]) +
            '</div><div class="l">' +
            pair[0] +
            "</div></div>"
          );
        })
        .join("");
      $("cardA").innerHTML =
        "<h4>" +
        DATA.option_a.name +
        '</h4><div class="big">' +
        DATA.option_a.avg_discount +
        '%</div><p>' +
        DATA.option_a.description +
        "</p>";
      $("cardB").innerHTML =
        "<h4>" +
        DATA.option_b.name +
        '</h4><div class="big">' +
        DATA.option_b.avg_discount +
        '%</div><p>' +
        DATA.option_b.description +
        "</p>";
      var as = DATA.meta.assumptions || {};
      $("assumptions").innerHTML =
        "Uplift BF ×" +
        (as.bf_uplift_vs_mes || 4) +
        " vs venta mensual (Excel). Reserva " +
        Math.round((as.reserve_pct || 0.15) * 100) +
        "%.";
    }

    function renderTables() {
      var rows = filtered();
      $("bodyA").innerHTML = rows
        .map(function (r) {
          return (
            "<tr><td>" +
            r.sku +
            "</td><td>" +
            r.modelo +
            "</td><td><strong>" +
            fmt(r.stock_total) +
            "</strong></td><td>" +
            fmt(r.venta_mensual_prom, 1) +
            "</td><td>" +
            (r.meses_cobertura != null ? r.meses_cobertura : "—") +
            "</td><td><strong>" +
            r.descuento_opcion_a +
            "%</strong></td></tr>"
          );
        })
        .join("");
      $("bodyB").innerHTML = rows
        .map(function (r) {
          return (
            "<tr><td>" +
            r.sku +
            "</td><td>" +
            r.modelo +
            "</td><td><strong>" +
            fmt(r.stock_total) +
            "</strong></td><td>" +
            (r.meses_cobertura != null ? r.meses_cobertura : "—") +
            "</td><td><strong>" +
            r.descuento_opcion_b +
            "%</strong></td><td>" +
            fmt(r.brecha_abastecimiento) +
            "</td></tr>"
          );
        })
        .join("");
      $("bodyAll").innerHTML = rows
        .map(function (r) {
          return (
            "<tr><td>" +
            r.prioridad +
            "</td><td>" +
            r.sku +
            "</td><td>" +
            r.modelo +
            "</td><td><strong>" +
            fmt(r.stock_total) +
            "</strong></td><td>" +
            fmt(r.qty) +
            "</td><td>" +
            r.descuento_opcion_a +
            "%</td><td>" +
            r.descuento_opcion_b +
            "%</td></tr>"
          );
        })
        .join("");
      $("bodySupply").innerHTML = (DATA.supply || [])
        .filter(function (r) {
          if (!state.search) return true;
          var q = state.search.toLowerCase();
          return (r.sku + " " + r.modelo + " " + r.tienda).toLowerCase().indexOf(q) >= 0;
        })
        .slice(0, 800)
        .map(function (r) {
          return (
            "<tr><td>" +
            r.tienda +
            "</td><td>" +
            r.sku +
            "</td><td>" +
            r.modelo +
            "</td><td>" +
            fmt(r.stock_actual) +
            "</td><td>" +
            fmt(r.objetivo_bf) +
            "</td><td>" +
            fmt(r.brecha) +
            "</td></tr>"
          );
        })
        .join("");
      $("topModels").innerHTML = (DATA.models || [])
        .slice(0, 15)
        .map(function (m) {
          return (
            "<tr><td>" +
            m.modelo +
            "</td><td>" +
            m.segmento +
            "</td><td>" +
            m.skus_c +
            "</td><td>" +
            fmt(m.stock_total) +
            "</td><td>" +
            fmt(m.unidades_vendidas_periodo) +
            "</td><td>" +
            fmt(m.margen_10m, 0) +
            "</td></tr>"
          );
        })
        .join("");
    }

    function renderCharts() {
      if (typeof Chart === "undefined") return;
      var seg = { Manufactura: 0, Equipamiento: 0 };
      DATA.skus.forEach(function (r) {
        seg[r.segmento] = (seg[r.segmento] || 0) + 1;
      });
      var canvas = $("cSeg");
      if (!canvas) return;
      if (window._bfChart) {
        try {
          window._bfChart.destroy();
        } catch (e) {}
      }
      window._bfChart = new Chart(canvas, {
        type: "doughnut",
        data: {
          labels: Object.keys(seg),
          datasets: [
            {
              data: Object.values(seg),
              backgroundColor: ["rgba(34,211,238,.8)", "rgba(251,191,36,.8)"],
            },
          ],
        },
        options: {
          plugins: { legend: { position: "bottom" } },
          maintainAspectRatio: false,
        },
      });
    }

    $("fSeg").onchange = function (e) {
      state.seg = e.target.value;
      renderTables();
    };
    $("fSearch").oninput = function (e) {
      state.search = e.target.value;
      renderTables();
    };

    try {
      renderKpis();
      renderTables();
      renderCharts();
    } catch (err) {
      console.error(err);
      showError("Error al renderizar: " + err.message);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
