(function () {
  const RAW = JSON.parse(document.getElementById('DATA').textContent);
  const $ = function (id) { return document.getElementById(id); };
  const CL_ORDER = ['CRITICO', 'SALUDABLE', 'LENTO', 'EXCESO', 'SIN VENTA'];
  const CL_COL = {
    QUIEBRE: '#C70705', CRITICO: '#C70705', SALUDABLE: '#1E7B34',
    LENTO: '#C9A000', EXCESO: '#9A6B00', 'SIN VENTA': '#B3B3B3'
  };
  const PILL = { QUIEBRE: 'p-qb', CRITICO: 'p-cr', SALUDABLE: 'p-ok', LENTO: 'p-le', EXCESO: 'p-ex', 'SIN VENTA': 'p-sv' };

  function fm(n) { return Math.round(Number(n) || 0).toLocaleString('es-VE'); }
  function n1(v) {
    if (v == null || !isFinite(v)) return '—';
    return Number(v).toFixed(1).replace('.', ',');
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function cobCol(c, pol) {
    if (c == null || !isFinite(c)) return '#8a8a8a';
    if (c < pol.crit) return '#C70705';
    if (c <= pol.sano) return '#1E7B34';
    if (c <= pol.lento) return '#C9A000';
    return '#9A6B00';
  }
  function cobText(c, cl, pol) {
    if (cl === 'QUIEBRE' || c === 0) return '<span class="mono" style="color:#C70705;font-weight:700">0,0 m</span>';
    if (c == null) return '<span class="dim">sin venta</span>';
    return '<span class="mono" style="color:' + cobCol(c, pol) + ';font-weight:700">' + n1(c) + ' m</span>';
  }
  function classLabel(pol) {
    return {
      CRITICO: 'Crítico <' + n1(pol.crit) + ' m',
      SALUDABLE: 'Saludable ' + n1(pol.crit) + '–' + n1(pol.sano) + ' m',
      LENTO: 'Lento más de ' + n1(pol.sano) + ' hasta ' + n1(pol.lento) + ' m',
      EXCESO: 'Exceso >' + n1(pol.lento) + ' m',
      'SIN VENTA': 'Sin venta en el período',
      QUIEBRE: 'Quiebre · vendió y está en 0'
    };
  }
  function trendOf(byMonth) {
    if (!byMonth || byMonth.length < 2) return '<span class="eq">—</span>';
    const last = byMonth[byMonth.length - 1];
    const prev = byMonth[byMonth.length - 2];
    const d = last - prev;
    const base = Math.max(prev, 1);
    if (d >= 2 && d / base >= 0.15) return '<span class="up">▲ +' + fm(d) + '</span>';
    if (d <= -2 && -d / base >= 0.15) return '<span class="dn">▼ ' + fm(d) + '</span>';
    return '<span class="eq">≈</span>';
  }
  function csvDownload(filename, rows) {
    const escCell = function (v) {
      const s = v == null ? '' : String(v);
      return /[;"\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    const body = rows.map(function (r) { return r.map(escCell).join(';'); }).join('\n');
    const blob = new Blob(['\ufeff' + body], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }
  function sortRows(rows, key, dir) {
    return rows.slice().sort(function (a, b) {
      let x = a[key];
      let y = b[key];
      const cov = key === 'cob' || key === 'cobT';
      if (x == null) x = cov ? Infinity : (typeof y === 'string' ? '' : -Infinity);
      if (y == null) y = cov ? Infinity : (typeof x === 'string' ? '' : -Infinity);
      if (typeof x === 'string' || typeof y === 'string') return String(x).localeCompare(String(y)) * dir;
      return (x - y) * dir;
    });
  }

  if (RAW.mode === 'chain') bootChain();
  else bootStore();

  function bootStore() {
    const D = RAW.data;
    const name = RAW.name;
    let per = Math.min(6, Math.max(1, 12 - ((D.kpi && D.kpi.first) || 0)));
    let sCl = '';
    let mAbc = '';
    let sSort = { k: 'sales', d: -1 };
    let mSort = { k: 'sales', d: -1 };
    const openModels = new Set();
    const openDec = { rep: new Set(), reb: new Set(), man: new Set(), act: new Set(), sob: new Set(), sm: new Set() };
    let view = null;
    let chMes = null;
    let chEst = null;
    let skuRows = [];
    let modelRows = [];

    $('badge').textContent = name;
    document.title = name + ' · Análisis de tienda · CUADRO';

    document.addEventListener('click', function (e) {
      const tab = e.target.closest('#storeApp [data-tab]');
      if (tab) {
        document.querySelectorAll('#storeApp .tab').forEach(function (t) { t.classList.toggle('on', t === tab); });
        document.querySelectorAll('#storeApp .sec').forEach(function (s) { s.classList.remove('on'); });
        $('sec-' + tab.dataset.tab).classList.add('on');
        return;
      }
      const chip = e.target.closest('#perChips [data-per]');
      if (chip) { per = +chip.dataset.per; draw(); return; }
      const cl = e.target.closest('#sec-salud [data-cl]');
      if (cl) {
        sCl = cl.dataset.cl;
        document.querySelectorAll('#sec-salud [data-cl]').forEach(function (c) { c.classList.toggle('on', c === cl); });
        renderSalud();
        return;
      }
      const abc = e.target.closest('#sec-modelos [data-abc]');
      if (abc) {
        mAbc = abc.dataset.abc;
        document.querySelectorAll('#sec-modelos [data-abc]').forEach(function (c) { c.classList.toggle('on', c === abc); });
        renderModelos();
        return;
      }
      const th = e.target.closest('th[data-k]');
      if (th && th.closest('#sHead')) {
        const k = th.dataset.k;
        sSort = sSort.k === k ? { k: k, d: -sSort.d } : { k: k, d: -1 };
        renderSalud();
        return;
      }
      if (th && th.closest('#mHead')) {
        const k = th.dataset.k;
        mSort = mSort.k === k ? { k: k, d: -mSort.d } : { k: k, d: -1 };
        renderModelos();
        return;
      }
      const model = e.target.closest('#mBody tr[data-model]');
      if (model) {
        const id = model.dataset.model;
        if (openModels.has(id)) openModels.delete(id); else openModels.add(id);
        renderModelos();
        return;
      }
      const drow = e.target.closest('#sec-dec [data-panel]');
      if (drow) {
        const panel = drow.dataset.panel;
        const id = drow.dataset.id;
        if (openDec[panel].has(id)) openDec[panel].delete(id); else openDec[panel].add(id);
        renderDec();
        return;
      }
      const csv = e.target.closest('[data-csv]');
      if (csv) { exportCsv(csv.dataset.csv); }
    });
    $('sMod').addEventListener('change', renderSalud);
    $('sSrch').addEventListener('input', renderSalud);
    $('mSrch').addEventListener('input', renderModelos);

    function rangeLabel() {
      const a = view.months[0];
      const b = view.months[view.months.length - 1];
      return a.long + ' – ' + b.long;
    }

    function draw() {
      view = Metrics.analyzeStore(D, per);
      per = view.per;
      const a = view.months[0];
      const b = view.months[view.months.length - 1];
      const open = view.first > 0 ? Metrics.monthMeta(view.first, view.meses12) : null;
      $('hdrSub').textContent = 'SOMOS CUADRO · ' + (open ? open.long.toUpperCase() : a.long.toUpperCase()) + ' – ' + b.long.toUpperCase() + ' · CORTE ' + RAW.corte + ' · PERÍODO EN PANTALLA ' + view.per + ' MESES';
      $('hdrR').textContent = fm(view.stockedN) + ' SKUs con stock · ' + fm(view.modelN) + ' modelos';
      $('perNote').textContent = open ? 'La tienda vende desde ' + open.long + '.' : '';
      $('perChips').innerHTML = view.perOpts.map(function (n) {
        return '<span class="chip' + (n === view.per ? ' on' : '') + '" data-per="' + n + '">' + n + ' meses</span>';
      }).join('');
      renderKpis();
      renderFlow();
      renderMini();
      renderAbc();
      renderCharts();
      renderSalud();
      renderModelos();
      renderDec();
    }

    function renderKpis() {
      const orphan = view.orphan
        ? ' Serie de tienda: ' + fm(view.storeSales) + '. Hay ' + fm(view.orphan) + ' und de SKUs que ya no están en la tabla.'
        : ' Coincide con la serie de la tienda.';
      const bulk = view.bigExcl
        ? ' La extracción dejó fuera ' + fm(view.bigExcl) + ' und de pedidos de 100 o más. Ese dato no está partido por mes y no se resta de esta cifra.'
        : '';
      const pct = view.stockedN ? Math.round(100 * view.activeStocked / view.stockedN) : 0;
      $('krow').innerHTML = [
        kpi('c-em', fm(view.stock), 'Stock actual', fm(view.stockedN) + ' SKUs con unidades · ' + fm(view.quiebreN) + ' variantes agotadas no están en piso'),
        kpi('c-wh', fm(view.catalogSales), 'Unidades vendidas · ' + view.per + ' meses', view.months[0].name.toLowerCase() + '–' + view.months[view.months.length - 1].name.toLowerCase() + ' · SKUs del listado.' + orphan + bulk),
        kpi('c-em', fm(Math.round(view.velocity)) + '<small>/mes</small>', 'Ritmo del período', 'Promedio de estos ' + view.per + ' meses. Cambia con el período de arriba.'),
        kpi('c-wh', (view.cob == null ? '—' : n1(view.cob)) + '<small> meses</small>', 'Cobertura al ritmo del período', 'Con temporada: ' + (view.cobT == null ? '—' : n1(view.cobT)) + ' meses · índice ' + (view.season.src === 'red' ? 'de red' : 'propio de la tienda') + '.'),
        kpi('c-wh', fm(view.activeStocked), 'SKUs con venta y con stock', pct + '% de los ' + fm(view.stockedN) + ' SKUs que tienen unidades'),
        kpi('c-re', fm(view.quiebreN), 'Variantes agotadas', fm(view.quiebreSales) + ' und vendidas en estos ' + view.per + ' meses y hoy en 0')
      ].join('');
    }

    function kpi(cls, val, label, sub) {
      return '<div class="kpi ' + cls + '"><div class="kv">' + val + '</div><div class="kl">' + label + '</div><div class="ks">' + sub + '</div></div>';
    }

    function renderFlow() {
      const f = view.flow;
      if (!f) { $('flowWrap').innerHTML = ''; return; }
      const delta = view.flowDelta || 0;
      const boxes = [
        ['Inicial', f.inicial, 'desde ' + (f.desde || '')],
        ['Recibido', f.recibido, ''],
        ['Vendido puente', f.vendido, 'no es la venta del período'],
        ['Trasladado', f.trasladado, ''],
        ['Ajustes', f.ajustes, ''],
        ['Stock puente', f.actual, 'cierra la suma del puente'],
        ['Stock del listado', view.stock, delta === 0 ? 'cuadra con el puente' : 'diferencia ' + (delta > 0 ? '+' : '') + fm(delta) + ' und']
      ];
      $('flowWrap').innerHTML = '<div class="flow">' + boxes.map(function (b, i) {
        const bad = i === 6 && delta !== 0;
        return '<div class="fbox"><div class="fv' + (bad ? ' delta-bad' : '') + '">' + fm(b[1]) + '</div><div class="fl">' + esc(b[0]) + '</div><div class="fs">' + esc(b[2]) + '</div></div>';
      }).join('') + '</div>';
    }

    function renderMini() {
      const pol = view.pol;
      const labels = classLabel(pol);
      $('defn').textContent = 'Crítico: menos de ' + n1(pol.crit) + ' meses. Saludable: de ' + n1(pol.crit) + ' a ' + n1(pol.sano) + '. Lento: más de ' + n1(pol.sano) + ' y hasta ' + n1(pol.lento) + '. Exceso: más de ' + n1(pol.lento) + '. Reposición: ' + n1(pol.repq) + ' meses' + (pol.ciclo ? ' (' + pol.ciclo + ')' : '') + '. El sell-through usa solo el período elegido: una ventana más corta baja el porcentaje aunque el negocio no cambie. Para comparar, mira la cobertura.';
      const stColor = view.sellThrough >= 50 ? '#0B3F6B' : '#9A6B00';
      const varColor = view.variation == null ? '#5c5c5c' : (view.variation < 0 ? '#C70705' : '#0B3F6B');
      const varTxt = view.variation == null ? '—' : ((view.variation > 0 ? '+' : '') + n1(view.variation) + '%');
      $('miniK').innerHTML = [
        card('Sell-through del período', '<span style="color:' + stColor + '">' + n1(view.sellThrough) + '%</span>', 'Ventas de estos ' + view.per + ' meses ÷ (esas ventas + stock actual), SKUs del listado.'),
        card('Stock sin venta en el período', '<span style="color:#C70705">' + fm(view.sinVentaU) + ' und</span>', fm(view.sinVentaN) + ' variantes · ' + fm(view.sinMovFamilies) + ' familias completas en 0 ventas.'),
        card('Cobertura con temporada', '<span style="color:' + cobCol(view.cobT, pol) + '">' + (view.cobT == null ? '—' : n1(view.cobT)) + ' meses</span>', 'Ritmo desestacionalizado de estos ' + view.per + ' meses, proyectado con el índice ' + (view.season.src === 'red' ? 'de red' : 'propio') + '. Al ritmo crudo: ' + (view.cob == null ? '—' : n1(view.cob)) + ' meses.'),
        card('Variación del período', '<span style="color:' + varColor + '">' + varTxt + '</span>', view.variationLabel + '.')
      ].join('');
    }
    function card(t, n, d) {
      return '<div class="card"><div class="ct">' + t + '</div><div class="bigN">' + n + '</div><div class="cdesc">' + d + '</div></div>';
    }

    function renderAbc() {
      const abc = view.abc;
      const pol = view.pol;
      $('abcEm').textContent = 'el número es de modelos y coincide con el filtro de la pestaña Modelos';
      function block(cls, n, fam, text, chips) {
        return '<div class="abcCard ' + cls + '"><div class="abcT">Clase ' + cls.toUpperCase() + ' · ' + fm(n) + ' modelos</div>'
          + '<div class="abcS">' + text + ' · ' + fm(fam) + ' familias con la misma regla.</div>'
          + (chips ? '<div class="chips">' + chips.map(function (c) { return '<span class="mchip">' + esc(c) + '</span>'; }).join('') + '</div>' : '')
          + '</div>';
      }
      $('abcRow').innerHTML = [
        block('a', abc.models.A, abc.families.A, 'Entran en el 80% de las unidades y su cobertura con temporada no pasa de ' + n1(pol.lento) + ' meses. Si están cortos, aparecen en Reponer: alta rotación no significa stock sano.', abc.chips),
        block('b', abc.models.B, abc.families.B, 'Cola media, o alta rotación con exceso (más de ' + n1(pol.lento) + ' meses).'),
        block('c', abc.models.C, abc.families.C, 'El resto. Incluye ' + fm(abc.models.sv) + ' modelos sin venta en el período.')
      ].join('');
    }

    function renderCharts() {
      const labels = [];
      const data = [];
      const colors = [];
      const hi = {};
      view.months.forEach(function (m) { hi[m.i] = 1; });
      for (let i = view.first; i < 12; i++) {
        const meta = Metrics.monthMeta(i, view.meses12);
        labels.push(meta.short);
        data.push(view.catalogAll[i]);
        colors.push(hi[i] ? '#0B3F6B' : '#B9C9DC');
      }
      $('ctMes').innerHTML = 'Ventas de los SKUs del listado <em>· en oscuro, los ' + view.per + ' meses del período</em>';
      if (chMes) chMes.destroy();
      chMes = new Chart($('cMes'), {
        type: 'bar',
        data: { labels: labels, datasets: [{ data: data, backgroundColor: colors, borderRadius: 6, maxBarThickness: 48 }] },
        options: {
          animation: false, maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { callbacks: { label: function (c) { return ' ' + fm(c.parsed.y) + ' unidades'; } } } },
          scales: { x: { grid: { display: false } }, y: { beginAtZero: true, grid: { color: '#e2e2e2' } } }
        }
      });
      const labelsCl = classLabel(view.pol);
      $('ctEstado').innerHTML = 'Unidades en stock <em>· ' + fm(view.quiebreN) + ' variantes agotadas no entran: tienen 0 unidades</em>';
      if (chEst) chEst.destroy();
      chEst = new Chart($('cEstado'), {
        type: 'doughnut',
        data: {
          labels: CL_ORDER.map(function (c) { return labelsCl[c] + ' · ' + fm(view.classesU[c]) + ' und · ' + fm(view.classes[c]) + ' SKUs'; }),
          datasets: [{ data: CL_ORDER.map(function (c) { return view.classesU[c]; }), backgroundColor: CL_ORDER.map(function (c) { return CL_COL[c]; }), borderColor: '#fff', borderWidth: 2 }]
        },
        options: { animation: false, maintainAspectRatio: false, cutout: '58%', plugins: { legend: { position: 'right', labels: { boxWidth: 10, font: { size: 10 } } } } }
      });
    }

    function monthHeads(sortAttr) {
      return view.months.map(function (m) {
        return '<th class="num">' + esc(m.name) + '</th>';
      }).join('');
    }

    function renderSalud() {
      const labels = classLabel(view.pol);
      const order = ['QUIEBRE', 'CRITICO', 'SALUDABLE', 'LENTO', 'EXCESO', 'SIN VENTA'];
      $('sKpis').innerHTML = order.map(function (k) {
        return '<div class="skpi"><div class="kv" style="color:' + CL_COL[k] + '">' + fm(view.classes[k]) + '</div><div class="kl">' + k + ' <span style="color:var(--lm2)">SKUs</span></div><div class="ks">' + labels[k] + '</div></div>';
      }).join('');
      const prev = $('sMod').value;
      const mods = Array.from(new Set(view.skus.map(function (s) { return s.m; }))).sort();
      $('sMod').innerHTML = '<option value="">Todos los modelos</option>' + mods.map(function (m) { return '<option>' + esc(m) + '</option>'; }).join('');
      if (prev) $('sMod').value = prev;
      $('sHead').innerHTML = '<tr>'
        + th('k', 'SKU') + th('m', 'Modelo') + th('col', 'Color') + th('t', 'Talla') + th('s', 'Stock', 1)
        + monthHeads()
        + th('sales', 'Vta ' + view.per + ' meses', 1) + th('sales12', 'Histórico', 1)
        + th('cob', 'Cobertura', 1) + th('cobT', 'Con temporada', 1) + th('cl', 'Estado')
        + '</tr>';
      const q = $('sSrch').value.trim().toLowerCase();
      const mod = $('sMod').value;
      let rows = view.skus.filter(function (r) {
        if (sCl && r.cl !== sCl) return false;
        if (mod && r.m !== mod) return false;
        if (q && (r.k + ' ' + r.m + ' ' + r.col + ' ' + r.t).toLowerCase().indexOf(q) === -1) return false;
        return true;
      });
      rows = sortRows(rows, sSort.k, sSort.d);
      skuRows = rows;
      const units = rows.reduce(function (s, r) { return s + r.s; }, 0);
      $('sCount').textContent = fm(rows.length) + ' SKUs · ' + fm(units) + ' und';
      const shown = rows.slice(0, 600);
      $('sBody').innerHTML = shown.map(function (r) {
        return '<tr><td class="mono dim">' + esc(r.k) + '</td><td style="font-weight:600">' + esc(r.m) + '</td>'
          + '<td class="dim">' + esc(r.col || '—') + '</td><td class="mono dim">' + esc(r.t || '—') + '</td>'
          + '<td class="num">' + fm(r.s) + '</td>'
          + r.byMonth.map(function (x) { return '<td class="num dim">' + (x || '') + '</td>'; }).join('')
          + '<td class="num" style="font-weight:700;color:' + (r.sales > 0 ? '#0B3F6B' : '#B3B3B3') + '">' + (r.sales || '—') + '</td>'
          + '<td class="num dim">' + (r.sales12 || '—') + '</td>'
          + '<td class="num">' + cobText(r.cob, r.cl, view.pol) + '</td>'
          + '<td class="num">' + cobText(r.cobT, r.cl, view.pol) + '</td>'
          + '<td><span class="pill ' + PILL[r.cl] + '">' + esc(r.cl) + '</span></td></tr>';
      }).join('') + (rows.length > 600 ? '<tr><td colspan="20" class="dim" style="text-align:center;padding:10px">Hay ' + fm(rows.length - 600) + ' filas más. El CSV las incluye todas.</td></tr>' : '');
    }

    function th(k, label, num) {
      return '<th ' + (num ? 'class="num" ' : '') + 'data-k="' + k + '">' + label + '</th>';
    }

    function renderModelos() {
      $('mHead').innerHTML = '<tr>'
        + th('m', 'Modelo') + th('abc', 'ABC') + th('k', 'Variantes', 1) + th('s', 'Stock', 1)
        + monthHeads()
        + '<th>Tend.</th>'
        + th('sales', 'Vta ' + view.per + ' meses', 1) + th('sales12', 'Histórico', 1)
        + th('cob', 'Cobertura', 1) + th('cobT', 'Con temporada', 1) + th('q', 'Agotadas', 1)
        + '<th>Venta vs stock</th></tr>';
      const q = $('mSrch').value.trim().toLowerCase();
      let rows = view.models.filter(function (r) {
        if (mAbc === 'SV') return r.sv;
        if (mAbc && r.abc !== mAbc) return false;
        if (q && r.m.toLowerCase().indexOf(q) === -1) return false;
        return true;
      });
      rows = sortRows(rows, mSort.k, mSort.d);
      modelRows = rows;
      const sold = rows.reduce(function (s, r) { return s + r.sales; }, 0);
      $('mCount').textContent = fm(rows.length) + ' modelos · ' + fm(sold) + ' und en el período';
      const maxT = Math.max.apply(null, view.models.map(function (r) { return r.sales + r.s; }).concat([1]));
      $('mBody').innerHTML = rows.map(function (r) {
        const open = openModels.has(r.m);
        const wv = 140 * r.sales / maxT;
        const ws = 140 * r.s / maxT;
        let html = '<tr class="exp' + (open ? ' open' : '') + '" data-model="' + esc(r.m) + '">'
          + '<td style="font-weight:700"><span class="caret">▶</span>' + esc(r.m) + '</td>'
          + '<td><span class="pill p-' + r.abc.toLowerCase() + '">' + r.abc + '</span></td>'
          + '<td class="num dim">' + fm(r.k) + '</td><td class="num">' + fm(r.s) + '</td>'
          + r.byMonth.map(function (x) { return '<td class="num dim">' + (x || '') + '</td>'; }).join('')
          + '<td class="trend">' + trendOf(r.byMonth) + '</td>'
          + '<td class="num" style="font-weight:700;color:' + (r.sales ? '#0B3F6B' : '#B3B3B3') + '">' + (r.sales || '—') + '</td>'
          + '<td class="num dim">' + (r.sales12 || '—') + '</td>'
          + '<td class="num">' + cobText(r.cob, r.cl, view.pol) + '</td>'
          + '<td class="num">' + cobText(r.cobT, r.cl, view.pol) + '</td>'
          + '<td class="num" style="color:' + (r.q ? '#C70705' : '#B3B3B3') + '">' + (r.q || '—') + '</td>'
          + '<td><span class="barCell"><i style="width:' + wv + 'px;background:#355E91"></i><i style="width:' + ws + 'px;background:#DDDDDD"></i></span></td></tr>';
        if (open) {
          html += r.variants.slice().sort(function (a, b) { return b.sales - a.sales || b.s - a.s; }).map(function (s) {
            return '<tr class="vrow"><td style="padding-left:26px"><span class="mono dim">' + esc(s.k) + '</span><div style="font-size:.64rem;font-weight:600">' + esc(s.col || '—') + (s.t ? ' · ' + esc(s.t) : '') + '</div></td>'
              + '<td><span class="pill ' + PILL[s.cl] + '">' + esc(s.cl) + '</span></td><td></td>'
              + '<td class="num">' + fm(s.s) + '</td>'
              + s.byMonth.map(function (x) { return '<td class="num dim">' + (x || '') + '</td>'; }).join('')
              + '<td></td><td class="num">' + (s.sales || '—') + '</td><td class="num dim">' + (s.sales12 || '—') + '</td>'
              + '<td class="num">' + cobText(s.cob, s.cl, view.pol) + '</td>'
              + '<td class="num">' + cobText(s.cobT, s.cl, view.pol) + '</td><td></td><td></td></tr>';
          }).join('');
        }
        return html;
      }).join('');
    }

    function planLine(v) {
      return 'ritmo ' + n1(v.ritmo) + '/mes × factor ' + n1(v.r3) + ' × ' + n1(view.pol.repq) + ' meses = objetivo ' + fm(Math.ceil(v.target)) + ' · stock ' + fm(v.s) + (v.qty ? ' · +' + fm(v.qty) : '');
    }

    function drow(panel, f, stat) {
      const open = openDec[panel] && openDec[panel].has(f.id);
      let extra = '';
      if (open) {
        const list = panel === 'rep'
          ? f.variants.filter(function (v) { return v.s === 0 || (v.cobT != null && v.cobT < view.pol.crit); })
          : panel === 'reb'
            ? f.holes.concat(f.donors.filter(function (d) { return f.holes.indexOf(d) === -1; })).slice(0, 24)
            : f.variants.slice().sort(function (a, b) { return b.s - a.s; }).slice(0, 20);
        extra = '<div class="dsub">' + (list.length ? list.map(function (v) {
          const role = v.s === 0 ? 'agotada' : (v.cobT != null && v.cobT > view.pol.lento ? 'sobra' : '');
          return '<div class="dvar"><span class="sku">' + esc(v.k) + '</span><span>' + esc(v.col || '—') + (v.t ? ' · ' + esc(v.t) : '') + (role ? ' · ' + role : '') + '</span><span class="vt">' + planLine(v) + '</span></div>';
        }).join('') : '<div class="dvar dim">Sin variantes en este corte</div>') + '</div>';
      }
      return '<div class="drow clk' + (open ? ' open' : '') + '" data-panel="' + panel + '" data-id="' + esc(f.id) + '"><span class="dcaret">▶</span><span class="nm">' + esc(f.id) + '</span><span class="stat">' + stat + '</span></div>' + extra;
    }

    function renderDec() {
      const pol = view.pol;
      $('decNote').textContent = 'Familias = modelo sin separar CAB, DAMA y KIDS. La cantidad a reponer es la suma de las variantes cortas. Ritmo = venta del período ÷ ' + view.per + ' meses. Factor = el r3 que ya venía en cada variante.';
      $('txtRep').innerHTML = 'Ritmo de la familia de ' + n1(2) + ' und/mes o más, y cobertura bajo ' + n1(pol.crit) + ' meses, o variantes agotadas. <b class="t-gr">+n</b> sale de ritmo × factor × ' + n1(pol.repq) + ' meses − stock. No se fuerza una unidad de más.';
      $('txtMan').textContent = 'Cobertura con temporada entre ' + n1(pol.crit) + ' y ' + n1(pol.sano) + ' meses. Solo seguimiento.';
      $('txtAct').textContent = 'Venden, superan ' + n1(pol.exceso) + ' meses y tienen 100 unidades o más. No se repiten en Sobre-stock. Si además tienen una variante agotada, están en Rebalancear.';
      $('txtReb').textContent = 'La familia no está crítica, pero hay variantes en 0 con 3 o más vendidas y otras por encima de ' + n1(pol.lento) + ' meses. Mover talla o color antes de comprar el modelo.';
      $('txtSm').textContent = '0 ventas en estos ' + view.per + ' meses y stock en piso. Evaluar traslado o liquidación.';
      $('txtSob').textContent = 'Venden y superan ' + n1(pol.lento) + ' meses, con menos de 100 unidades. El exceso grande está en Activar o en Rebalancear.';
      const empty = '<div class="empty">Ninguna familia en este estado con el período de ' + view.per + ' meses.</div>';
      $('dRep').innerHTML = view.decisions.rep.length ? view.decisions.rep.map(function (f) {
        return drow('rep', f, '<b>' + fm(f.sales) + 'v</b> / <b>' + fm(f.s) + 's</b> · ritmo ' + n1(f.ritmo) + ' · <b class="t-gr">+' + fm(f.qty) + '</b><span class="formula">suma de variantes con cobertura bajo ' + n1(pol.crit) + ' m o en 0</span>');
      }).join('') : empty;
      $('dMan').innerHTML = view.decisions.man.length ? view.decisions.man.map(function (f) {
        return drow('man', f, fm(f.sales) + 'v / ' + fm(f.s) + 's · ' + n1(f.cobT) + ' m');
      }).join('') : empty;
      $('dAct').innerHTML = view.decisions.act.length ? view.decisions.act.map(function (f) {
        return drow('act', f, '<b>' + fm(f.s) + 's</b> · ' + fm(f.sales) + 'v · ' + n1(f.cobT) + ' m');
      }).join('') : '<div class="empty">Ninguna. Si un modelo grande tiene exceso y también una variante en cero, está en Rebalancear.</div>';
      $('dReb').innerHTML = view.decisions.reb.length ? view.decisions.reb.map(function (f) {
        return drow('reb', f, '<b>' + fm(f.s) + 's</b> · ' + n1(f.cobT) + ' m · ' + fm(f.holes.length) + ' agotadas' + (f.qty ? ' · compra neta +' + fm(f.qty) : ''));
      }).join('') : empty;
      $('dSm').innerHTML = view.decisions.sm.length ? view.decisions.sm.map(function (f) {
        return drow('sm', f, '<b>' + fm(f.s) + ' und</b>');
      }).join('') : empty;
      $('dSob').innerHTML = view.decisions.sob.length ? view.decisions.sob.map(function (f) {
        return drow('sob', f, '<b>' + fm(f.s) + 's</b> · ' + n1(f.cobT) + ' m · ' + fm(f.sales) + 'v');
      }).join('') : empty;
      $('dQb').innerHTML = view.decisions.quiebres.length ? view.decisions.quiebres.map(function (r) {
        return '<div class="drow"><span class="nm">' + esc(r.m) + ' <span class="dim" style="font-weight:500">· ' + esc(r.col || '—') + (r.t ? ' · ' + esc(r.t) : '') + '</span></span><span class="stat"><span class="mono dim">' + esc(r.k) + '</span> · <b class="t-re">' + fm(r.sales) + 'v · 0s · +' + fm(r.qty) + '</b></span></div>';
      }).join('') : '<div class="empty">Las agotadas de familias con sobrante interno están en Rebalancear.</div>';
      $('dMarg').innerHTML = view.decisions.marg.length ? view.decisions.marg.map(function (r) {
        const who = r.whole ? esc(r.m) + ' <span class="dim">· modelo completo</span>' : esc(r.m) + ' <span class="dim">· ' + esc(r.col || '—') + (r.t ? ' · ' + esc(r.t) : '') + '</span>';
        return '<div class="drow"><span class="nm">' + who + '</span><span class="stat"><b>' + fm(r.sales) + 'v · 0s</b></span></div>';
      }).join('') : '<div class="empty">Ninguno.</div>';
    }

    function exportCsv(kind) {
      if (kind === 'sku') {
        const head = ['SKU', 'Modelo', 'Color', 'Talla', 'Stock'].concat(view.months.map(function (m) { return m.short; }), ['Venta período', 'Histórico', 'Cobertura', 'Con temporada', 'Estado', 'Reponer']);
        const body = skuRows.map(function (r) {
          return [r.k, r.m, r.col, r.t, r.s].concat(r.byMonth, [r.sales, r.sales12, r.cob == null ? '' : n1(r.cob), r.cobT == null ? '' : n1(r.cobT), r.cl, r.qty || 0]);
        });
        csvDownload(RAW.id + '-skus-' + view.per + 'm.csv', [head].concat(body));
      } else {
        const head = ['Modelo', 'ABC', 'Variantes', 'Stock'].concat(view.months.map(function (m) { return m.short; }), ['Venta período', 'Histórico', 'Cobertura', 'Con temporada', 'Agotadas']);
        const body = modelRows.map(function (r) {
          return [r.m, r.abc, r.k, r.s].concat(r.byMonth, [r.sales, r.sales12, r.cob == null ? '' : n1(r.cob), r.cobT == null ? '' : n1(r.cobT), r.q]);
        });
        csvDownload(RAW.id + '-modelos-' + view.per + 'm.csv', [head].concat(body));
      }
    }

    if (window.Chart) {
      Chart.defaults.font.family = "'Montserrat',sans-serif";
      Chart.defaults.font.size = 11;
      Chart.defaults.color = '#5c5c5c';
    }
    draw();
  }

  function bootChain() {
    $('storeApp').style.display = 'none';
    $('chainApp').style.display = 'block';
    document.title = 'Cadena · CUADRO';
    let per = 6;
    let chA = null;
    let chB = null;
    const stores = RAW.stores;

    function draw() {
      const views = stores.map(function (st) {
        const view = Metrics.analyzeStore(st.data, per);
        return { id: st.id, name: st.name, file: st.file, view: view };
      });
      const ideas = Metrics.transferIdeas(views);
      $('cSub').textContent = 'CORTE ' + RAW.corte + ' · PERÍODO PEDIDO ' + per + ' MESES · CADA TIENDA USA LOS MESES QUE TIENE';
      $('cNote').textContent = views.map(function (st) { return st.name + ' ' + st.view.per + 'm'; }).join(' · ');
      $('cChips').innerHTML = [3, 6, 12].map(function (n) {
        return '<span class="chip' + (n === per ? ' on' : '') + '" data-cper="' + n + '">' + n + ' meses</span>';
      }).join('');
      const head = '<thead><tr><th>Tienda</th><th class="num">Meses</th><th class="num">Stock</th><th class="num">Venta</th><th class="num">Ritmo</th><th class="num">Cobertura</th><th class="num">Con temporada</th><th class="num">Sell-through</th><th class="num">Exceso</th><th class="num">Sin venta</th><th class="num">Agotadas</th><th></th></tr></thead>';
      $('cCmp').innerHTML = head + '<tbody>' + views.map(function (st) {
        const v = st.view;
        const exc = v.stock ? 100 * v.classesU.EXCESO / v.stock : 0;
        const dead = v.stock ? 100 * v.classesU['SIN VENTA'] / v.stock : 0;
        return '<tr><td style="font-weight:700">' + esc(st.name) + '</td><td class="num">' + v.per + '</td><td class="num">' + fm(v.stock) + '</td><td class="num">' + fm(v.catalogSales) + '</td><td class="num">' + fm(Math.round(v.velocity)) + '</td><td class="num">' + n1(v.cob) + '</td><td class="num">' + n1(v.cobT) + '</td><td class="num">' + n1(v.sellThrough) + '%</td><td class="num">' + n1(exc) + '%</td><td class="num">' + n1(dead) + '%</td><td class="num">' + fm(v.quiebreN) + '</td><td><a href="' + esc(st.file) + '">Abrir</a></td></tr>';
      }).join('') + '</tbody>';
      $('cFlow').innerHTML = '<thead><tr><th>Tienda</th><th class="num">Inicial</th><th class="num">Recibido</th><th class="num">Vendido</th><th class="num">Trasladado</th><th class="num">Ajustes</th><th class="num">Puente</th><th class="num">Listado</th><th class="num">Diferencia</th><th>Desde</th></tr></thead><tbody>'
        + views.map(function (st) {
          const f = st.view.flow || {};
          const d = st.view.flowDelta || 0;
          return '<tr><td>' + esc(st.name) + '</td><td class="num">' + fm(f.inicial) + '</td><td class="num">' + fm(f.recibido) + '</td><td class="num">' + fm(f.vendido) + '</td><td class="num">' + fm(f.trasladado) + '</td><td class="num">' + fm(f.ajustes) + '</td><td class="num">' + fm(f.actual) + '</td><td class="num">' + fm(st.view.stock) + '</td><td class="num ' + (d ? 'delta-bad' : 'delta-ok') + '">' + (d > 0 ? '+' : '') + fm(d) + '</td><td>' + esc(f.desde || '') + '</td></tr>';
        }).join('') + '</tbody>';
      const top = ideas.rows.slice(0, 250);
      $('cTrTitle').textContent = 'Traslados · ' + fm(ideas.skus) + ' SKUs con quiebre en una tienda y exceso en otra · ' + fm(ideas.rows.length) + ' movimientos';
      $('cTr').innerHTML = '<thead><tr><th>SKU</th><th>Modelo</th><th>Color</th><th>Talla</th><th>Desde</th><th>Hacia</th><th class="num">Mover</th><th class="num">Stock origen</th><th class="num">Venta destino</th><th class="num">Cobertura origen</th></tr></thead><tbody>'
        + top.map(function (r) {
          return '<tr><td class="mono">' + esc(r.k) + '</td><td>' + esc(r.m) + '</td><td>' + esc(r.col || '—') + '</td><td>' + esc(r.t || '—') + '</td><td>' + esc(r.from) + '</td><td>' + esc(r.to) + '</td><td class="num" style="font-weight:800">' + fm(r.qty) + '</td><td class="num">' + fm(r.fromStock) + '</td><td class="num">' + fm(r.toSales) + '</td><td class="num">' + n1(r.fromCob) + ' m</td></tr>';
        }).join('') + '</tbody>';
      if (chA) chA.destroy();
      if (chB) chB.destroy();
      const labels = views.map(function (s) {
        return s.name.replace(' · MARGARITA', '').replace('SAMBIL ', 'Sambil ');
      });
      const axis = {
        indexAxis: 'y',
        animation: false,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } },
        scales: {
          x: { stacked: true, beginAtZero: true, grid: { color: '#e2e2e2' } },
          y: { stacked: true, grid: { display: false }, ticks: { font: { size: 10 } } }
        }
      };
      chA = new Chart($('cStock'), {
        type: 'bar',
        data: { labels: labels, datasets: [
          { label: 'Exceso', data: views.map(function (s) { return s.view.classesU.EXCESO; }), backgroundColor: '#9A6B00' },
          { label: 'Sin venta', data: views.map(function (s) { return s.view.classesU['SIN VENTA']; }), backgroundColor: '#B3B3B3' },
          { label: 'Resto con stock', data: views.map(function (s) { return s.view.stock - s.view.classesU.EXCESO - s.view.classesU['SIN VENTA']; }), backgroundColor: '#0B3F6B' }
        ] },
        options: axis
      });
      chB = new Chart($('cCob'), {
        type: 'bar',
        data: { labels: labels, datasets: [
          { label: 'Al ritmo del período', data: views.map(function (s) { return Math.round((s.view.cob || 0) * 10) / 10; }), backgroundColor: '#355E91' },
          { label: 'Con temporada', data: views.map(function (s) { return Math.round((s.view.cobT || 0) * 10) / 10; }), backgroundColor: '#0B3F6B' }
        ] },
        options: Object.assign({}, axis, { scales: { x: { beginAtZero: true, grid: { color: '#e2e2e2' } }, y: { grid: { display: false }, ticks: { font: { size: 10 } } } } })
      });
    }

    document.addEventListener('click', function (e) {
      const chip = e.target.closest('#cChips [data-cper]');
      if (!chip) return;
      per = +chip.dataset.cper;
      draw();
    });
    if (window.Chart) {
      Chart.defaults.font.family = "'Montserrat',sans-serif";
      Chart.defaults.font.size = 11;
      Chart.defaults.color = '#5c5c5c';
    }
    draw();
  }
})();
