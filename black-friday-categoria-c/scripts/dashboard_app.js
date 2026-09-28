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

  function fmtNum(n, d) {
    d = d === undefined ? 0 : d;
    if (n == null || n === "" || Number.isNaN(Number(n))) return "—";
    return Number(n).toLocaleString("en-US", {
      minimumFractionDigits: d,
      maximumFractionDigits: d,
    });
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
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

  function loadPayload() {
    var embedded = document.getElementById("bf-embedded-data");
    if (embedded && embedded.textContent) {
      try {
        return JSON.parse(embedded.textContent);
      } catch (e) {
        showError("Error al leer datos embebidos: " + e.message);
        return null;
      }
    }
    if (window.BF_PROPOSAL_DATA) return window.BF_PROPOSAL_DATA;
    showError("Sin datos embebidos. Regenerá el HTML con build_black_friday_proposal.py.");
    return null;
  }

  function boot() {
    var DATA = loadPayload();
    if (!DATA || !DATA.skus) return;

    var state = { seg: "", search: "" };
    var expanded = Object.create(null);
    var view = DATA.inventario_view || DATA.option_b || {
      name: "Inventario baja rotación",
      description: "",
      sort: "stock_desc",
    };

    function catalogFiltered() {
      var list = (DATA.catalog || []).slice();
      if (state.seg) list = list.filter(function (m) { return m.segmento === state.seg; });
      if (state.search) {
        var q = state.search.toLowerCase();
        list = list.filter(function (m) {
          if (m.modelo.toLowerCase().indexOf(q) >= 0) return true;
          return (m.variants || []).some(function (v) {
            return (
              (v.sku + " " + v.color + " " + v.talla + " " + v.genero)
                .toLowerCase()
                .indexOf(q) >= 0
            );
          });
        });
      }
      return list;
    }

    function sortCatalog(list) {
      list = list.slice();
      list.sort(function (a, b) {
        var sa = a.stock_tiendas + a.stock_taller;
        var sb = b.stock_tiendas + b.stock_taller;
        return sb - sa || b.stock_total - a.stock_total;
      });
      return list;
    }

    function variantLabel(v) {
      return [v.genero, v.color, v.talla].filter(Boolean).join(" · ") || "—";
    }

    function renderCatalogTable() {
      var tbody = $("bodyInv");
      if (!tbody) return;
      var rows = sortCatalog(catalogFiltered());
      var html = "";
      rows.forEach(function (m) {
        var open = !!expanded[m.modelo];
        html +=
          '<tr class="row-model" data-model="' +
          esc(m.modelo) +
          '"><td><span class="expander" data-model="' +
          esc(m.modelo) +
          '">' +
          (open ? "▼" : "▶") +
          '</span></td><td>' +
          esc(m.modelo) +
          '</td><td class="mat">' +
          esc(m.matriz) +
          '</td><td class="num">' +
          fmtNum(m.skus_count) +
          '</td><td class="num">' +
          fmtNum(m.rotacion_mes, 1) +
          '</td><td class="num"><strong>' +
          fmtNum(m.stock_total) +
          '</strong></td><td class="num">' +
          fmtNum(m.stock_tiendas) +
          '</td><td class="num">' +
          fmtNum(m.stock_taller) +
          '</td><td class="num">' +
          (m.meses_cobertura != null ? fmtNum(m.meses_cobertura, 1) : "—") +
          "</td></tr>";
        if (open) {
          (m.variants || []).forEach(function (v) {
            html +=
              '<tr class="row-variant"><td></td><td><div class="sku">' +
              esc(v.sku) +
              '</div><div class="var-meta">' +
              esc(variantLabel(v)) +
              '</div></td><td class="mat">' +
              esc(v.matriz || "—") +
              '</td><td class="num">—</td><td class="num">' +
              fmtNum(v.rotacion_mes, 1) +
              '</td><td class="num">' +
              fmtNum(v.stock_total) +
              '</td><td class="num">' +
              fmtNum(v.stock_tiendas) +
              '</td><td class="num">' +
              fmtNum(v.stock_taller) +
              '</td><td class="num">' +
              (v.meses_cobertura != null ? fmtNum(v.meses_cobertura, 1) : "—") +
              "</td></tr>";
          });
        }
      });
      tbody.innerHTML = html;
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

    var bodyInv = $("bodyInv");
    if (bodyInv) {
      bodyInv.addEventListener("click", function (e) {
        var t = e.target;
        if (!t || !t.getAttribute) return;
        var mod = t.getAttribute("data-model");
        if (!mod) return;
        expanded[mod] = !expanded[mod];
        renderCatalogTable();
      });
    }

    function renderKpis() {
      var s = DATA.summary;
      $("subtitle").textContent = DATA.meta.subtitle;
      $("kpis").innerHTML = [
        ["SKUs", s.skus_c_total],
        ["Und. stock", s.unidades_stock],
        ["En tiendas", s.unidades_tiendas],
        ["En taller", s.unidades_taller],
        ["Modelos", (DATA.catalog || []).length],
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

      if ($("titleInv")) $("titleInv").textContent = view.name;
      if ($("subInv")) $("subInv").textContent = view.description;
      var sug = DATA.meta.sugeridos_revision || [];
      var card = $("sugeridosCard");
      var statsEl = $("resumenStats");
      if (statsEl) {
        var total = s.unidades_stock || 1;
        var pctT = Math.round((100 * s.unidades_tiendas) / total);
        var pctW = 100 - pctT;
        statsEl.innerHTML = [
          ["En tiendas", pctT + "%", fmt(s.unidades_tiendas) + " und."],
          ["En taller", pctW + "%", fmt(s.unidades_taller) + " und."],
          ["Matriz CC", fmt(s.matriz_cc || 0), "SKUs margen C · rot. C"],
        ]
          .map(function (row) {
            return (
              '<div class="stat"><div class="v">' +
              row[1] +
              '</div><div class="l">' +
              row[0] +
              (row[2] ? ' · <span style="text-transform:none;font-weight:400">' + row[2] + "</span>" : "") +
              "</div></div>"
            );
          })
          .join("");
      }

      var topBody = $("bodyTopModelos");
      if (topBody) {
        var top = (DATA.catalog || []).slice(0, 12);
        topBody.innerHTML = top
          .map(function (m) {
            return (
              "<tr><td>" +
              esc(m.modelo) +
              '</td><td class="mat">' +
              esc(m.matriz) +
              '</td><td class="num">' +
              fmtNum(m.skus_count) +
              '</td><td class="num">' +
              fmtNum(m.stock_tiendas) +
              '</td><td class="num">' +
              fmtNum(m.stock_taller) +
              '</td><td class="num">' +
              (m.meses_cobertura != null ? fmtNum(m.meses_cobertura, 1) : "—") +
              "</td></tr>"
            );
          })
          .join("");
      }

      if (card && sug.length) {
        card.style.display = "block";
        $("bodySugeridos").innerHTML = sug
          .map(function (s) {
            return (
              "<tr><td>" +
              esc(s.modelo) +
              "</td><td>" +
              esc(s.sku) +
              '</td><td class="num">' +
              fmtNum(s.stock) +
              '</td><td class="num">' +
              fmtNum(s.rotacion_mes, 1) +
              "</td></tr>"
            );
          })
          .join("");
      }
    }

    function renderFlatSkus() {
      var rows = DATA.skus.filter(function (r) {
        if (state.seg && r.segmento !== state.seg) return false;
        if (state.search) {
          var q = state.search.toLowerCase();
          var blob = (r.sku + " " + r.modelo + " " + (r.producto || "")).toLowerCase();
          if (blob.indexOf(q) < 0) return false;
        }
        return true;
      });
      $("bodyAll").innerHTML = rows
        .map(function (r) {
          return (
            "<tr><td>" +
            esc(r.sku) +
            "</td><td>" +
            esc(r.modelo) +
            "</td><td>" +
            esc([r.genero, r.color, r.talla].filter(Boolean).join(" · ")) +
            "</td><td>" +
            fmtNum(r.rotacion_mes, 1) +
            '</td><td class="num">' +
            fmtNum(r.stock_total) +
            '</td><td class="num">' +
            fmtNum(r.stock_tiendas) +
            '</td><td class="num">' +
            fmtNum(r.stock_taller) +
            "</td></tr>"
          );
        })
        .join("");
    }

    function destroyChart(key) {
      if (window[key]) {
        try {
          window[key].destroy();
        } catch (e) {}
        window[key] = null;
      }
    }

    function renderCharts() {
      if (typeof Chart === "undefined") return;
      var seg = { Manufactura: 0, Equipamiento: 0 };
      DATA.skus.forEach(function (r) {
        seg[r.segmento] = (seg[r.segmento] || 0) + 1;
      });
      var canvas = $("cSeg");
      if (canvas) {
        destroyChart("_bfChartSeg");
        window._bfChartSeg = new Chart(canvas, {
          type: "doughnut",
          data: {
            labels: Object.keys(seg),
            datasets: [
              {
                data: Object.values(seg),
                backgroundColor: ["rgba(37,99,235,.85)", "rgba(100,116,139,.75)"],
                borderColor: "#fff",
                borderWidth: 2,
              },
            ],
          },
          options: {
            plugins: { legend: { position: "bottom", labels: { color: "#64748b" } } },
            maintainAspectRatio: false,
          },
        });
      }

      var cLoc = $("cStockLoc");
      var s = DATA.summary;
      if (cLoc && s) {
        destroyChart("_bfChartLoc");
        window._bfChartLoc = new Chart(cLoc, {
          type: "doughnut",
          data: {
            labels: ["Tiendas", "Taller"],
            datasets: [
              {
                data: [s.unidades_tiendas, s.unidades_taller],
                backgroundColor: ["rgba(43,108,176,.9)", "rgba(148,163,184,.85)"],
                borderColor: "#fff",
                borderWidth: 2,
              },
            ],
          },
          options: {
            plugins: { legend: { position: "bottom", labels: { color: "#64748b" } } },
            maintainAspectRatio: false,
          },
        });
      }
    }

    $("fSeg").onchange = function (e) {
      state.seg = e.target.value;
      renderCatalogTable();
      renderFlatSkus();
    };
    $("fSearch").oninput = function (e) {
      state.search = e.target.value;
      renderCatalogTable();
      renderFlatSkus();
    };

    try {
      renderKpis();
      renderCatalogTable();
      renderFlatSkus();
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
