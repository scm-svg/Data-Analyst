/**
 * Tracking de Producción — Google Apps Script
 *
 * Estima la fecha de salida de cada SKU según:
 *  - capacidad diaria por línea (o por SKU si está en la hoja)
 *  - líneas habilitadas para ese SKU (ej. "1, 2")
 *  - cola de faltantes
 *  - etapa: "En Confeccion" ocupa la línea primero;
 *           "A espera de Confeccion" entra después, ya lista para producir
 *
 * Menú: Tracking Producción → Recalcular fechas / Abrir dashboard / Crear hoja Config
 * Web App: Implementar > Implementar como aplicación web (doGet)
 */

var CONFIG_SHEET_NAME = 'Config Tracking';

var DEFAULT_CONFIG = {
  HOJA_DATOS: '',
  FILA_ENCABEZADOS: '2',
  DIAS_LABORABLES: '1,2,3,4,5',
  FECHA_INICIO: '',
  ETAPAS_EN_LINEA: 'En Confeccion',
  ETAPAS_LISTAS: 'A espera de Confeccion',
  ETAPAS_TERMINADO: 'Terminado,Completado,Entregado',
  CAPACIDAD_DEFAULT: '130'
};

var HEADER_ALIASES = {
  mo: ['mo', 'numero de orden', 'nro mo', 'orden'],
  tipo: ['tipo'],
  sku: ['sku'],
  producto: ['producto'],
  genero: ['genero', 'género'],
  color: ['color'],
  talla: ['talla'],
  lineas: ['linea de produccion', 'línea de produccion', 'linea de producción', 'línea de producción'],
  solicitada: ['cantidad solicitada'],
  producida: ['cantida producida', 'cantidad producida'],
  faltante: ['faltante'],
  cap: ['cap produccion por dia', 'cap producción por dia', 'capacidad produccion por dia'],
  fecha: ['dia estimado de salida', 'día estimado de salida'],
  etapa: ['etapa'],
  status: ['mo status', 'status', 'estatus'],
  cliente: ['clientes', 'cliente'],
  concatenado: ['concanetado', 'concatenado']
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Tracking Producción')
    .addItem('Recalcular fechas estimadas', 'recalcularFechas')
    .addItem('Abrir dashboard', 'abrirDashboard')
    .addSeparator()
    .addItem('Crear / actualizar hoja Config', 'ensureConfigSheet')
    .addToUi();
}

function doGet() {
  return HtmlService.createTemplateFromFile('Dashboard')
    .evaluate()
    .setTitle('Tracking Producción')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function abrirDashboard() {
  var html = HtmlService.createHtmlOutputFromFile('Dashboard')
    .setTitle('Tracking Producción')
    .setWidth(1200)
    .setHeight(800);
  SpreadsheetApp.getUi().showModalDialog(html, 'Tracking Producción');
}

function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}

function recalcularFechas() {
  var result = getDashboardData(true);
  var n = result.meta.fechasEscritas;
  SpreadsheetApp.getUi().alert(
    'Fechas actualizadas',
    'Se estimaron ' + n + ' fechas de salida y se escribieron en la columna "Dia Estimado de Salida".\n\n' +
    'Inicio de simulación: ' + result.startDate + '\n' +
    'Última salida: ' + (result.meta.ultimaSalida || '—'),
    SpreadsheetApp.getUi().ButtonSet.OK
  );
  return result;
}

function getDashboardData(writeDates) {
  var cfg = readConfig();
  var parsed = readProductionRows(cfg);
  var scheduled = estimateExitDates(parsed.rows, cfg);

  var written = 0;
  if (writeDates) {
    written = writeEstimatedDates_(parsed.sheet, parsed.headers, parsed.colMap, scheduled.rows, cfg);
  }

  var lineLoad = {};
  Object.keys(scheduled.lineLoad).forEach(function (k) {
    lineLoad[k] = scheduled.lineLoad[k];
  });

  return {
    generatedAt: Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd'T'HH:mm:ss"),
    startDate: scheduled.startDate,
    workdays: scheduled.workdays,
    lineCaps: scheduled.lineCaps,
    lineLoad: lineLoad,
    sheetName: parsed.sheet.getName(),
    rows: scheduled.rows,
    meta: {
      totalFilas: scheduled.rows.length,
      fechasEscritas: written,
      ultimaSalida: scheduled.ultimaSalida || '',
      wroteDates: !!writeDates
    }
  };
}

/* ───────── Config ───────── */

function ensureConfigSheet() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(CONFIG_SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(CONFIG_SHEET_NAME);
  }
  var existing = {};
  var last = sh.getLastRow();
  if (last >= 2) {
    var vals = sh.getRange(2, 1, last - 1, 2).getValues();
    vals.forEach(function (r) {
      if (r[0]) existing[String(r[0]).trim()] = r[1];
    });
  }
  sh.getRange(1, 1, 1, 3).setValues([['Parametro', 'Valor', 'Descripcion']]);
  sh.getRange(1, 1, 1, 3).setFontWeight('bold');

  var rows = [
    ['HOJA_DATOS', existing.HOJA_DATOS || DEFAULT_CONFIG.HOJA_DATOS, 'Nombre de la hoja de pedidos. Vacío = detectar automáticamente.'],
    ['FILA_ENCABEZADOS', existing.FILA_ENCABEZADOS || DEFAULT_CONFIG.FILA_ENCABEZADOS, 'Fila donde están MO, SKU, Producto, etc.'],
    ['DIAS_LABORABLES', existing.DIAS_LABORABLES || DEFAULT_CONFIG.DIAS_LABORABLES, 'ISO: 1=Lunes … 7=Domingo. Default lun-vie.'],
    ['FECHA_INICIO', existing.FECHA_INICIO || DEFAULT_CONFIG.FECHA_INICIO, 'Fecha de arranque de la simulación. Vacío = hoy.'],
    ['ETAPAS_EN_LINEA', existing.ETAPAS_EN_LINEA || DEFAULT_CONFIG.ETAPAS_EN_LINEA, 'Ya están en las líneas (ocupan capacidad primero).'],
    ['ETAPAS_LISTAS', existing.ETAPAS_LISTAS || DEFAULT_CONFIG.ETAPAS_LISTAS, 'Preparadas para entrar a línea. Van después de las que ya están en confección.'],
    ['ETAPAS_TERMINADO', existing.ETAPAS_TERMINADO || DEFAULT_CONFIG.ETAPAS_TERMINADO, 'Etapas consideradas terminadas. Si aún hay faltante, se programan al final.'],
    ['CAPACIDAD_DEFAULT', existing.CAPACIDAD_DEFAULT || DEFAULT_CONFIG.CAPACIDAD_DEFAULT, 'Piezas/día si el SKU no trae Cap Produccion por Dia.']
  ];
  sh.getRange(2, 1, rows.length, 3).setValues(rows);
  sh.setColumnWidth(1, 200);
  sh.setColumnWidth(2, 220);
  sh.setColumnWidth(3, 520);
  sh.getRange('A1:C1').setBackground('#1e1f2b').setFontColor('#ffffff');
  return sh;
}

function readConfig() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(CONFIG_SHEET_NAME);
  var cfg = {};
  Object.keys(DEFAULT_CONFIG).forEach(function (k) { cfg[k] = DEFAULT_CONFIG[k]; });
  if (!sh) return cfg;
  var last = sh.getLastRow();
  if (last < 2) return cfg;
  var vals = sh.getRange(2, 1, last - 1, 2).getValues();
  vals.forEach(function (r) {
    var key = String(r[0] || '').trim();
    if (!key) return;
    var val = r[1];
    if (val instanceof Date) {
      cfg[key] = Utilities.formatDate(val, Session.getScriptTimeZone(), 'yyyy-MM-dd');
    } else if (val !== '' && val !== null) {
      cfg[key] = String(val).trim();
    }
  });
  return cfg;
}

/* ───────── Lectura de la hoja ───────── */

function readProductionRows(cfg) {
  var ss = SpreadsheetApp.getActive();
  var sheet = resolveDataSheet_(ss, cfg);
  var headerRow = parseInt(cfg.FILA_ENCABEZADOS, 10) || 2;
  var lastCol = Math.max(sheet.getLastColumn(), 20);
  var lastRow = sheet.getLastRow();
  if (lastRow <= headerRow) {
    throw new Error('La hoja "' + sheet.getName() + '" no tiene filas de datos.');
  }

  var headerVals = sheet.getRange(headerRow, 1, 1, lastCol).getValues()[0];
  var headers = headerVals.map(function (h) { return normalizeHeader_(h); });
  var colMap = mapColumns_(headers);

  var nRows = lastRow - headerRow;
  var values = sheet.getRange(headerRow + 1, 1, nRows, lastCol).getValues();
  var rows = [];

  for (var i = 0; i < values.length; i++) {
    var r = values[i];
    var producto = cellStr_(r[colMap.producto]);
    var sku = cellStr_(r[colMap.sku]);
    var mo = cellStr_(r[colMap.mo]);
    if (!producto && !sku && !mo) continue;

    var solicitada = cellNum_(r[colMap.solicitada]);
    var producida = cellNum_(r[colMap.producida]);
    var faltanteRaw = r[colMap.faltante];
    var faltante = (faltanteRaw === '' || faltanteRaw === null)
      ? Math.max(0, solicitada - producida)
      : Math.max(0, cellNum_(faltanteRaw));
    var cap = cellNum_(r[colMap.cap]);
    var lineasRaw = cellStr_(r[colMap.lineas]);

    rows.push({
      row: headerRow + 1 + i,
      mo: mo,
      tipo: cellStr_(r[colMap.tipo]),
      sku: sku,
      producto: producto,
      genero: normalizeGenero_(cellStr_(r[colMap.genero])),
      color: cellStr_(r[colMap.color]),
      talla: cellStr_(r[colMap.talla]),
      lineasRaw: lineasRaw,
      lineas: parseLines_(lineasRaw),
      solicitada: solicitada,
      producida: producida,
      faltante: faltante,
      cap: cap,
      etapa: cellStr_(r[colMap.etapa]) || '--',
      status: cellStr_(r[colMap.status]) || '--',
      cliente: cellStr_(r[colMap.cliente]),
      concatenado: colMap.concatenado >= 0 ? cellStr_(r[colMap.concatenado]) : ''
    });
  }

  return { sheet: sheet, headers: headers, colMap: colMap, headerRow: headerRow, rows: rows };
}

function resolveDataSheet_(ss, cfg) {
  if (cfg.HOJA_DATOS) {
    var named = ss.getSheetByName(cfg.HOJA_DATOS);
    if (!named) throw new Error('No existe la hoja "' + cfg.HOJA_DATOS + '".');
    return named;
  }
  var sheets = ss.getSheets();
  var headerRow = parseInt(cfg.FILA_ENCABEZADOS, 10) || 2;
  for (var i = 0; i < sheets.length; i++) {
    var sh = sheets[i];
    if (sh.getName() === CONFIG_SHEET_NAME) continue;
    var lastCol = sh.getLastColumn();
    if (lastCol < 5) continue;
    var headers = sh.getRange(headerRow, 1, 1, lastCol).getValues()[0].map(normalizeHeader_);
    if (headers.indexOf('mo') >= 0 && headers.indexOf('sku') >= 0) return sh;
  }
  return ss.getActiveSheet();
}

function mapColumns_(headers) {
  var map = {};
  Object.keys(HEADER_ALIASES).forEach(function (key) {
    map[key] = -1;
    var aliases = HEADER_ALIASES[key];
    for (var i = 0; i < headers.length; i++) {
      if (aliases.indexOf(headers[i]) >= 0) {
        map[key] = i;
        break;
      }
    }
  });
  var required = ['mo', 'sku', 'producto', 'solicitada'];
  var missing = required.filter(function (k) { return map[k] < 0; });
  if (missing.length) {
    throw new Error('Faltan columnas en el encabezado: ' + missing.join(', ') +
      '. Revisa FILA_ENCABEZADOS en la hoja Config Tracking.');
  }
  return map;
}

/* ───────── Estimación de fechas ───────── */

function estimateExitDates(rows, cfg) {
  var tz = Session.getScriptTimeZone();
  var start = parseStartDate_(cfg.FECHA_INICIO, tz);
  var workdays = parseWorkdays_(cfg.DIAS_LABORABLES);
  var defaultCap = parseFloat(cfg.CAPACIDAD_DEFAULT) || 130;

  var lineCaps = {};
  rows.forEach(function (j) {
    var lines = j.lineas.length ? j.lineas : [];
    lines.forEach(function (ln) {
      var cap = j.cap > 0 ? j.cap : defaultCap;
      if (!lineCaps[ln] || cap > lineCaps[ln]) lineCaps[ln] = cap;
    });
  });
  Object.keys(lineCaps).forEach(function (ln) {
    var override = cfg['CAPACIDAD_LINEA_' + ln];
    if (override !== undefined && override !== '') {
      var n = parseFloat(override);
      if (!isNaN(n) && n > 0) lineCaps[ln] = n;
    }
  });

  var lineLoad = {};
  var queued = [];
  rows.forEach(function (j, idx) {
    j._idx = idx;
    if (j.faltante > 0) queued.push(j);
  });

  queued.sort(function (a, b) {
    var ra = stageRank_(a.etapa, cfg);
    var rb = stageRank_(b.etapa, cfg);
    if (ra !== rb) return ra - rb;
    var ma = a.mo || 'zzz';
    var mb = b.mo || 'zzz';
    if (ma < mb) return -1;
    if (ma > mb) return 1;
    return a.row - b.row;
  });

  queued.forEach(function (j) {
    var cands = j.lineas.length ? j.lineas : ['SIN LINEA'];
    var best = cands[0];
    var bestAvail = Infinity;
    for (var i = 0; i < cands.length; i++) {
      var ln = cands[i];
      if (!lineCaps[ln]) lineCaps[ln] = j.cap > 0 ? j.cap : defaultCap;
      var cap = lineCaps[ln] || defaultCap;
      var avail = (lineLoad[ln] || 0) / cap;
      if (avail < bestAvail) {
        bestAvail = avail;
        best = ln;
      }
    }
    var capL = lineCaps[best] || defaultCap;
    var startLoad = lineLoad[best] || 0;
    var endLoad = startLoad + j.faltante;
    var endDay = Math.max(0, Math.ceil(endLoad / capL) - 1);
    var startDay = Math.floor(startLoad / capL);
    lineLoad[best] = endLoad;
    j.lineaAsignada = best;
    j.diaInicioCola = startDay;
    j.diaFinCola = endDay;
    j.diasHabiles = endDay + 1;
    j.fechaEstimada = formatDateIso_(addWorkingDays_(start, endDay, workdays));
    j.avance = j.solicitada > 0 ? Math.round(1000 * j.producida / j.solicitada) / 10 : 0;
  });

  var ultima = '';
  rows.forEach(function (j) {
    if (j.faltante <= 0) {
      j.lineaAsignada = j.lineas.length ? j.lineas[0] : '';
      j.diaInicioCola = null;
      j.diaFinCola = null;
      j.diasHabiles = 0;
      j.fechaEstimada = null;
      j.avance = j.solicitada > 0 ? 100 : 0;
    }
    if (j.fechaEstimada && j.fechaEstimada > ultima) ultima = j.fechaEstimada;
    delete j._idx;
  });

  return {
    rows: rows,
    lineCaps: lineCaps,
    lineLoad: lineLoad,
    startDate: formatDateIso_(start),
    workdays: workdays,
    ultimaSalida: ultima
  };
}

function stageRank_(etapa, cfg) {
  var e = fold_(etapa);
  var enLinea = splitList_(cfg.ETAPAS_EN_LINEA);
  var listas = splitList_(cfg.ETAPAS_LISTAS);
  var terminado = splitList_(cfg.ETAPAS_TERMINADO);
  if (matchesAny_(e, enLinea) || (e.indexOf('confeccion') >= 0 && e.indexOf('espera') < 0)) return 0;
  if (matchesAny_(e, listas) || e.indexOf('espera de confeccion') >= 0) return 1;
  if (matchesAny_(e, terminado)) return 3;
  return 2;
}

function writeEstimatedDates_(sheet, headers, colMap, rows, cfg) {
  var lastCol = sheet.getLastColumn();
  var fechaCol = colMap.fecha;
  if (fechaCol < 0) {
    lastCol += 1;
    sheet.getRange(parseInt(cfg.FILA_ENCABEZADOS, 10) || 2, lastCol).setValue('Dia Estimado de Salida');
    fechaCol = lastCol - 1;
  }

  var lineaCol = findOrCreateCol_(sheet, cfg, 'Linea Asignada');
  var diasCol = findOrCreateCol_(sheet, cfg, 'Dias Habiles');
  var n = 0;
  rows.forEach(function (j) {
    if (j.fechaEstimada) {
      var parts = j.fechaEstimada.split('-');
      var dt = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
      sheet.getRange(j.row, fechaCol + 1).setValue(dt).setNumberFormat('yyyy-mm-dd');
      n++;
    } else {
      sheet.getRange(j.row, fechaCol + 1).setValue('');
    }
    if (lineaCol >= 0) sheet.getRange(j.row, lineaCol + 1).setValue(j.lineaAsignada || '');
    if (diasCol >= 0) sheet.getRange(j.row, diasCol + 1).setValue(j.diasHabiles || '');
  });
  return n;
}

function findOrCreateCol_(sheet, cfg, name) {
  var needle = normalizeHeader_(name);
  var headerRow = parseInt(cfg.FILA_ENCABEZADOS, 10) || 2;
  var last = Math.max(sheet.getLastColumn(), 1);
  var current = sheet.getRange(headerRow, 1, 1, last).getValues()[0];
  for (var i = 0; i < current.length; i++) {
    if (normalizeHeader_(current[i]) === needle) return i;
  }
  var col = last + 1;
  sheet.getRange(headerRow, col).setValue(name).setFontWeight('bold');
  return col - 1;
}

/* ───────── Helpers ───────── */

function normalizeHeader_(h) {
  return fold_(h).replace(/\s+/g, ' ').trim();
}

function fold_(s) {
  return String(s || '')
    .toLowerCase()
    .replace(/[áàä]/g, 'a')
    .replace(/[éèë]/g, 'e')
    .replace(/[íìï]/g, 'i')
    .replace(/[óòö]/g, 'o')
    .replace(/[úùü]/g, 'u')
    .trim();
}

function cellStr_(v) {
  if (v === null || v === undefined || v === '') return '';
  if (v instanceof Date) return Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  var t = String(v).trim();
  if (t === '--' || t === 'None' || t === 'nan') return '';
  return t;
}

function cellNum_(v) {
  if (v === null || v === undefined || v === '') return 0;
  if (typeof v === 'number') return isNaN(v) ? 0 : v;
  var t = String(v).replace(',', '.').replace(/[^\d.\-]/g, '');
  var n = parseFloat(t);
  return isNaN(n) ? 0 : n;
}

function parseLines_(raw) {
  return String(raw || '')
    .split(/[;,]/)
    .map(function (p) { return p.trim(); })
    .filter(function (p) { return p && p !== '--'; });
}

function normalizeGenero_(g) {
  var t = String(g || '').trim();
  if (!t || t === '-') return '-';
  var u = t.toUpperCase();
  if (u === 'CAB' || u === 'DAMA') return u;
  if (u.indexOf('CAB') === 0) return 'CAB';
  if (u.indexOf('DAM') === 0) return 'DAMA';
  return u;
}

function splitList_(s) {
  return String(s || '').split(',').map(function (x) { return fold_(x); }).filter(Boolean);
}

function matchesAny_(folded, list) {
  for (var i = 0; i < list.length; i++) {
    if (!list[i]) continue;
    if (folded === list[i] || folded.indexOf(list[i]) >= 0) return true;
  }
  return false;
}

function parseWorkdays_(s) {
  var parts = String(s || '1,2,3,4,5').split(',');
  var out = [];
  parts.forEach(function (p) {
    var n = parseInt(p.trim(), 10);
    if (n >= 1 && n <= 7) out.push(n);
  });
  return out.length ? out : [1, 2, 3, 4, 5];
}

function parseStartDate_(value, tz) {
  if (value) {
    var m = String(value).match(/(\d{4})-(\d{2})-(\d{2})/);
    if (m) return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    var d = new Date(value);
    if (!isNaN(d.getTime())) return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }
  var now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function addWorkingDays_(start, offset, workdays) {
  var d = new Date(start.getFullYear(), start.getMonth(), start.getDate());
  var guard = 0;
  while (workdays.indexOf(isoDow_(d)) < 0 && guard < 14) {
    d.setDate(d.getDate() + 1);
    guard++;
  }
  var remaining = offset;
  while (remaining > 0) {
    d.setDate(d.getDate() + 1);
    if (workdays.indexOf(isoDow_(d)) >= 0) remaining--;
  }
  return d;
}

function isoDow_(d) {
  var n = d.getDay();
  return n === 0 ? 7 : n;
}

function formatDateIso_(d) {
  var y = d.getFullYear();
  var m = ('0' + (d.getMonth() + 1)).slice(-2);
  var day = ('0' + d.getDate()).slice(-2);
  return y + '-' + m + '-' + day;
}
