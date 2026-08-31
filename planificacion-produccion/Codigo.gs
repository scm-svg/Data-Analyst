/**
 * =====================================================================
 *  SISTEMA DE PLANIFICACIÓN DE PRODUCCIÓN — VERSIÓN 5.9.6 (COMPLETO)
 * =====================================================================
 *  Pegar este archivo completo en el editor de Apps Script (Codigo.gs).
 *
 *  Cambios de esta versión:
 *   - LÍNEA 1: al cambiar de modelo el sobrante del día se llena
 *     (igual que L2-4). Un nativo de L1 que ya está en otra línea no
 *     bloquea el desborde; el overflow se recálcula al ceder la línea.
 *   - CANTIDAD MÍNIMA programa el cupo pedido (ej. 100 pzas) desde el
 *     faltante. Lo ya producido solo quita la banda si YA se cubrió
 *     el piso completo; no recorta 100 a 67. El modelo no cede la
 *     línea hasta cubrir esas piezas.
 *   - CANTIDAD MÍNIMA vuelve a ser la máxima prioridad después de
 *     Especial (Por Hacer - Especial). Gana incluso a Urgente. Al
 *     cubrir la mínima, el modelo cede el sobrante del día y el resto
 *     de su pedido vuelve a la cola normal.
 *   - CAMBIO DE MODELO SECUENCIAL: L1-4 no corren dos modelos en
 *     paralelo, pero sí pueden cambiar el mismo día. Si el ocupante
 *     termina (o no puede seguir), el sobrante de capacidad pasa al
 *     siguiente modelo de la cola. Ya no se deja el día a medias.
 *   - PRIORIZACION - SKUs: no adelanta el modelo. Cuando el modelo
 *     entra a la línea, esos SKUs salen primero (todo su faltante);
 *     luego sigue la distribución de colores núcleo.
 *   - LÍNEA 5: única que trabaja 2 modelos en paralelo (rueda de 5 pzas
 *     cuando hay dos). Si solo hay un modelo, usa las 40 pzas/día.
 *   - Capacidad real por línea (L5 = 40, resto = 130). El lote de 5 ya
 *     no se aplica como techo diario cuando L5 va sola.
 *   - URGENTE (después de Especial y de la cantidad mínima), luego la
 *     fecha más próxima. Un modelo Urgente con 2+ líneas usa ambas.
 *     Líneas 1-4 = un modelo a la vez (secuencial); L5 hasta 2 en paralelo.
 *   - ESPECIAL: respeta Linea de Produccion; línea 1 es la casa. Si L1
 *     termina y quedan Especiales en otras líneas, desbordan a L1.
 *     Fecha de Salida Estimada en Por Hacer - Especial ordena Especiales.
 *   - Priorización elimina modelos con faltante total 0.
 *   - PROYECCIÓN: tablas desde B2; umbrales primer cruce; links a SKUS.
 *   - CANTIDAD MÍNIMA respeta Día de inicio (Por Hacer col. R).
 *   - COLORES CORE primero en toda la distribución de variantes.
 *   - MO ATÓMICA: cada lote (MO) entra completo en UNA sola línea.
 *   - PROYECCIÓN ACUMULADA en "Proyeccion" y "Proyeccion - SKUS".
 *   - Prioridad "Urgente " (espacio) ya no cae a "Sin Asignar".
 *   - Columna Lineas de Priorizacion se usa como candidatas preferidas.
 *   - "2, 4" ya no se guarda como número 2.4 (separador " / ").
 *   - Sync de tracking por lotes; bug datos[i] vs datosM[i] corregido.
 *   - doGet + Guardar Producción (Corte Diario) restaurados.
 * =====================================================================
 */

var VERSION_SISTEMA = "5.9.6";
var BANDA_ESPECIAL = 0;
var BANDA_MINIMA = 1;
var BANDA_URGENTE = 2;
var BANDA_RESTO = 3;
var DIAS_LABORALES = 5;
var MAX_MODELOS_LINEA5 = 2;
var MAX_MODELOS_PARALELO = MAX_MODELOS_LINEA5;
var MAX_SNAPSHOTS = 8;
var NOMBRES_DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"];
var LOTE_RUEDA_LINEA5 = 5;
var CAP_POR_LINEA = { "1": 130, "2": 130, "3": 130, "4": 130, "5": 40 };
var LOCK_MS = 120000;
var COLOR_HEADER_PROY = "#20124D";
var COLOR_MINIMA_PROY = "#FFE599";
var COLOR_META_PROY = "#D9EAD3";
var COLOR_META_TEXTO_PROY = "#38761D";
var COLOR_BORDE_INTERNO = "#D0D0D0";
var NOMBRES_PRIO_SKU = ["Priorizacion - SKUs", "Priorizacion - SKUS", "Priorización - SKUs", "Priorizacion SKUs"];

// =====================================================================
//  MENÚ Y BOTONES (UNIFICADOS)
// =====================================================================
function onOpen() {
  var ui = SpreadsheetApp.getUi();

  ui.createMenu("⚙️ Producción")
    .addItem("1️⃣ Actualizar MOs", "actualizarMOs")
    .addItem("2️⃣ Actualizar Priorización", "actualizarModelosPriorizacion")
    .addItem("3️⃣ Generar Planificación", "generarPlanificacionSemanal")
    .addSeparator()
    .addItem("🔄 Sincronizar Producción", "sincronizarProduccionExterna")
    .addSeparator()
    .addItem("🔍 Filtrar Tableros por Modelo", "filtrarVistas")
    .addItem("🧹 Mostrar Todos (Quitar Filtro)", "limpiarFiltros")
    .addSeparator()
    .addItem("📸 Guardar Snapshot del Plan", "guardarSnapshotManual")
    .addToUi();

  ui.createMenu("👁️ Ver Pestañas")
    .addItem("📅 Semana 1 (Planificación)", "mostrarSemana1")
    .addItem("📅 Semana 2", "mostrarSemana2")
    .addItem("📅 Semana 3", "mostrarSemana3")
    .addItem("📅 Semana 4", "mostrarSemana4")
    .addItem("📅 Semana 5", "mostrarSemana5")
    .addSeparator()
    .addItem("⏳ Pendiente", "mostrarPendiente")
    .addSeparator()
    .addItem("📦 Almacén Modelo", "mostrarAlmacenModelo")
    .addItem("📦 Almacén SKUs", "mostrarAlmacenSkus")
    .addSeparator()
    .addItem("🙈 Ocultar estas pestañas", "ocultarPestanasSemanales")
    .addToUi();

  ui.createMenu("⚙️ Tracking")
    .addItem("💾 Guardar Producción (Corte Diario)", "guardarHistorialProduccionDiario")
    .addToUi();
}

function doGet() {
  return HtmlService.createHtmlOutputFromFile("Dashboard")
    .setTitle("Dashboard Maestro — Planificación de Producción")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

// =====================================================================
//  MÓDULO DE NAVEGACIÓN DE PESTAÑAS
// =====================================================================
function mostrarSemana1() { mostrarHoja_("Planificacion"); }
function mostrarSemana2() { mostrarHoja_("Semana 2"); }
function mostrarSemana3() { mostrarHoja_("Semana 3"); }
function mostrarSemana4() { mostrarHoja_("Semana 4"); }
function mostrarSemana5() { mostrarHoja_("Semana 5"); }
function mostrarPendiente() { mostrarHoja_("Pendiente"); }
function mostrarAlmacenModelo() { mostrarHoja_("Entrada de Almacen Modelo"); }
function mostrarAlmacenSkus() { mostrarHoja_("Entrada de Almacen - Skus"); }

function mostrarHoja_(nombre) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var hoja = ss.getSheetByName(nombre);
  if (hoja) {
    hoja.showSheet();
    hoja.activate();
  } else {
    SpreadsheetApp.getUi().alert("No se encontró la hoja: " + nombre);
  }
}

function ocultarPestanasSemanales() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var hojas = [
    "Planificacion", "Semana 2", "Semana 3", "Semana 4", "Semana 5",
    "Pendiente", "Entrada de Almacen Modelo", "Entrada de Almacen - Skus"
  ];

  hojas.forEach(function(nom) {
    var h = ss.getSheetByName(nom);
    if (h) {
      try { h.hideSheet(); } catch (e) {}
    }
  });
  ss.toast("Las pestañas han sido ocultadas.", "Navegación", 3);
}

function guardarSnapshotManual() {
  var nombre = guardarSnapshotPlan_();
  if (nombre) {
    SpreadsheetApp.getUi().alert("📸 Snapshot guardado como hoja oculta:\n\n" + nombre);
  } else {
    SpreadsheetApp.getUi().alert("No hay datos en 'Planificacion' para guardar.");
  }
}

function filtrarVistas() {
  var ui = SpreadsheetApp.getUi();
  var respuesta = ui.prompt(
    "🔍 Filtrar Vistas por Modelo",
    "Escribe el nombre del modelo (o SKU) que deseas aislar:\n(Ejemplo: SHOUNKI)",
    ui.ButtonSet.OK_CANCEL
  );

  if (respuesta.getSelectedButton() !== ui.Button.OK) return;
  var textoBuscar = respuesta.getResponseText().trim().toLowerCase();
  if (textoBuscar === "") return;

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var hojasSemanales = ["Planificacion", "Semana 2", "Semana 3", "Semana 4", "Semana 5"];
  var hojasEstaticas = ["Proyeccion", "Proyeccion - SKUS", "Pendiente"];

  hojasSemanales.forEach(function(nom) {
    var hoja = ss.getSheetByName(nom);
    if (!hoja) return;
    var ultFila = hoja.getLastRow();
    if (ultFila < 4) return;

    var datos = hoja.getRange(4, 1, ultFila - 3, hoja.getLastColumn()).getValues();
    hoja.showRows(4, ultFila - 3);

    for (var i = 0; i < datos.length; i++) {
      var filaCompletaStr = datos[i].join("").trim();
      if (filaCompletaStr === "") continue;

      var filaTexto = datos[i].join(" ").toLowerCase();
      var colC = datos[i].length > 2 ? String(datos[i][2]).toLowerCase().trim() : "";
      var esProtegida = (colC.indexOf("total") !== -1 || colC.indexOf("🚨") !== -1 || colC === "modelo" || colC === "detalle del producto");

      if (!esProtegida && filaTexto.indexOf(textoBuscar) === -1) {
        hoja.hideRows(i + 4);
      }
    }
  });

  hojasEstaticas.forEach(function(nom) {
    var hoja = ss.getSheetByName(nom);
    if (!hoja) return;
    var ultFila = hoja.getLastRow();
    if (ultFila < 3) return;

    var datos = hoja.getRange(3, 1, ultFila - 2, hoja.getLastColumn()).getValues();
    hoja.showRows(3, ultFila - 2);

    for (var i = 0; i < datos.length; i++) {
      var filaCompletaStr = datos[i].join("").trim();
      if (filaCompletaStr === "") continue;

      var filaTexto = datos[i].join(" ").toLowerCase();
      var colC = datos[i].length > 2 ? String(datos[i][2]).toLowerCase().trim() : "";
      var esProtegida = (colC.indexOf("total") !== -1 || colC.indexOf("🚨") !== -1 || colC === "modelo" || colC === "detalle del producto");

      if (!esProtegida && filaTexto.indexOf(textoBuscar) === -1) {
        hoja.hideRows(i + 3);
      }
    }
  });

  ui.alert("✅ Tableros filtrados exitosamente.\nSe está mostrando únicamente la información relacionada con: " + textoBuscar.toUpperCase() + "\n\n(Para restaurar la vista, usa 'Mostrar Todos' en el menú).");
}

function limpiarFiltros() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var hojasSemanales = ["Planificacion", "Semana 2", "Semana 3", "Semana 4", "Semana 5"];
  var hojasEstaticas = ["Proyeccion", "Proyeccion - SKUS", "Pendiente"];

  hojasSemanales.forEach(function(nom) {
    var hoja = ss.getSheetByName(nom);
    if (hoja && hoja.getMaxRows() > 3) {
      hoja.showRows(4, hoja.getMaxRows() - 3);
    }
  });

  hojasEstaticas.forEach(function(nom) {
    var hoja = ss.getSheetByName(nom);
    if (hoja && hoja.getMaxRows() > 2) {
      hoja.showRows(3, hoja.getMaxRows() - 2);
    }
  });

  ss.toast("Se han restaurado todas las vistas a su estado original.", "🧹 Filtros Limpiados", 3);
}

// =====================================================================
//  CONFIGURACIÓN
// =====================================================================
function leerConfig_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var cfg = {
    semanas: 5,
    forzarMeta: false,
    lunesBase: proximoLunes_(new Date()),
    tz: ss.getSpreadsheetTimeZone()
  };

  var hojaMenu = ss.getSheetByName("Menu");
  if (!hojaMenu) return cfg;

  var datos = hojaMenu.getDataRange().getValues();
  for (var i = 0; i < datos.length; i++) {
    for (var j = 0; j < datos[i].length - 1; j++) {
      var etiqueta = String(datos[i][j]).toLowerCase();
      var valor = datos[i][j + 1];
      if (etiqueta.indexOf("semanas") !== -1) {
        var n = Math.floor(Number(valor));
        if (n >= 1 && n <= 8) cfg.semanas = n;
      }
      if (etiqueta.indexOf("forzar") !== -1) {
        var v = String(valor).trim().toLowerCase();
        cfg.forzarMeta = (v === "si" || v === "sí" || valor === true);
      }
      if (etiqueta.indexOf("lunes") !== -1 && valor instanceof Date && !isNaN(valor)) {
        cfg.lunesBase = new Date(valor);
        cfg.lunesBase.setHours(0, 0, 0, 0);
      }
    }
  }
  return cfg;
}

function proximoLunes_(hoy) {
  var d = new Date(hoy);
  var dow = d.getDay();
  var diasDesdeLunes = (dow + 6) % 7;
  d.setDate(d.getDate() - diasDesdeLunes);
  d.setHours(0, 0, 0, 0);
  return d;
}

function fechaDeDia_(cfg, indiceDia) {
  var semana = Math.floor(indiceDia / DIAS_LABORALES);
  var dia = indiceDia % DIAS_LABORALES;
  var f = new Date(cfg.lunesBase);
  f.setDate(f.getDate() + semana * 7 + dia);
  return f;
}

// =====================================================================
//  UTILIDADES
// =====================================================================
function norm_(s) { return String(s === null || s === undefined ? "" : s).trim(); }
function normUp_(s) { return norm_(s).toUpperCase(); }
function normLow_(s) { return norm_(s).toLowerCase(); }

function quitarTildes_(s) {
  return String(s).replace(/á/g, "a").replace(/é/g, "e").replace(/í/g, "i")
    .replace(/ó/g, "o").replace(/ú/g, "u").replace(/ñ/g, "n")
    .replace(/Á/g, "a").replace(/É/g, "e").replace(/Í/g, "i")
    .replace(/Ó/g, "o").replace(/Ú/g, "u").replace(/Ñ/g, "n");
}

function idxPorFragmento_(headers, fragmentos) {
  for (var i = 0; i < headers.length; i++) {
    var h = normLow_(headers[i]);
    if (h === "") continue;
    for (var f = 0; f < fragmentos.length; f++) {
      if (h.indexOf(fragmentos[f]) !== -1) return i;
    }
  }
  return -1;
}

function idxExacto_(headers, nombre) {
  for (var i = 0; i < headers.length; i++) {
    if (normUp_(headers[i]) === nombre) return i;
  }
  return -1;
}

function claveSku_(s) { return normUp_(s); }

function hojaPorNombreFlex_(ss, nombres) {
  var i, h;
  for (i = 0; i < nombres.length; i++) {
    h = ss.getSheetByName(nombres[i]);
    if (h) return h;
  }
  var alvos = nombres.map(function (n) { return claveModeloNorm_(n); });
  var sheets = ss.getSheets();
  for (i = 0; i < sheets.length; i++) {
    if (alvos.indexOf(claveModeloNorm_(sheets[i].getName())) !== -1) return sheets[i];
  }
  return null;
}

function claveFecha_(v) {
  if (v instanceof Date && !isNaN(v)) return v.getTime();
  if (typeof v === "number" && isFinite(v) && v > 20000 && v < 80000) {
    return new Date(Math.round((v - 25569) * 86400 * 1000)).getTime();
  }
  var s = norm_(v);
  if (s === "") return Infinity;
  var m = s.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})$/);
  if (m) {
    var anio = Number(m[3]); if (anio < 100) anio += 2000;
    var f = new Date(anio, Number(m[2]) - 1, Number(m[1]));
    if (!isNaN(f)) return f.getTime();
  }
  var n = Number(s);
  if (isFinite(n) && n > 20000 && n < 80000) {
    return new Date(Math.round((n - 25569) * 86400 * 1000)).getTime();
  }
  return Infinity;
}

function formatoFecha_(cfg, ms) {
  if (!isFinite(ms)) return "--";
  return Utilities.formatDate(new Date(ms), cfg.tz, "dd/MM/yyyy");
}

function parsearLineas_(str) {
  return String(str === null || str === undefined ? "" : str)
    .split(/[,;\/|]+/)
    .map(function (l) { return String(l).replace(/linea/ig, "").replace(/línea/ig, "").trim(); })
    .filter(function (l) { return l !== "" && !isNaN(Number(l)); })
    .map(function (l) { return String(parseInt(l, 10)); });
}

function formatearLineas_(arr) {
  return (arr || []).join(" / ");
}

function prioridadNum_(txt) {
  var p = quitarTildes_(normLow_(txt));
  if (p.indexOf("urgente") !== -1) return 1;
  if (p.indexOf("alta") !== -1) return 2;
  if (p.indexOf("media") !== -1) return 3;
  if (p.indexOf("baja") !== -1) return 4;
  return 5;
}

function parseCantidad_(v) {
  if (v === true || v === false || v === null || v === undefined || v === "") return 0;
  if (typeof v === "number") return isFinite(v) ? v : 0;
  var s = String(v).trim().replace(/\s/g, "").replace(",", ".");
  var n = Number(s);
  return isFinite(n) ? n : 0;
}

function idxCantidadMinima_(headers) {
  for (var i = 0; i < headers.length; i++) {
    var h = quitarTildes_(normLow_(headers[i]));
    if (h.indexOf("cantidad") !== -1 && (h.indexOf("minima") !== -1 || h.indexOf("min ") !== -1 || h.indexOf(" minimo") !== -1)) {
      return i;
    }
  }
  return idxPorFragmento_(headers, ["cantidad minima", "cantidad mínima", "cant. minima", "minima", "mínima"]);
}

function claveModeloNorm_(s) {
  return quitarTildes_(normLow_(s)).replace(/\s+/g, " ");
}

function minimaDeModelo_(mapaMinimas, modelo) {
  if (!mapaMinimas) return 0;
  if (mapaMinimas[modelo] > 0) return mapaMinimas[modelo];
  var alvo = claveModeloNorm_(modelo);
  if (mapaMinimas[alvo] > 0) return mapaMinimas[alvo];
  var alvoBase = alvo.replace(/\s*\(especial\)\s*$/, "");
  for (var k in mapaMinimas) {
    var nk = claveModeloNorm_(k);
    if ((nk === alvo || nk === alvoBase || nk.replace(/\s*\(especial\)\s*$/, "") === alvoBase) && mapaMinimas[k] > 0) {
      return mapaMinimas[k];
    }
  }
  return 0;
}

function diaInicioEfectivo_(t) {
  return (t && t.diaIngreso) ? t.diaIngreso : 0;
}

function esUrgente_(t) {
  return !t.esEspecial && Number(t.prioridadNum) === 1;
}

function bandaDe_(t) {
  if (t.esEspecial) return BANDA_ESPECIAL;
  if (t.esMinima) return BANDA_MINIMA;
  if (esUrgente_(t)) return BANDA_URGENTE;
  return BANDA_RESTO;
}

function faltanteDeFila_(fila, iCant, iFalt, iProdQty) {
  var sol = iCant !== -1 ? (Number(fila[iCant]) || 0) : 0;
  var prod = iProdQty !== -1 ? (Number(fila[iProdQty]) || 0) : 0;
  if (iProdQty !== -1) return Math.max(0, sol - prod);
  if (iFalt !== -1 && fila[iFalt] !== "") {
    var f = Number(fila[iFalt]);
    if (!isNaN(f)) return f;
  }
  return Math.max(0, sol);
}

function rangoColor_(color) {
  var c = quitarTildes_(normLow_(color));
  if (c === "") return 50;
  if (c === "negro" || c.indexOf("negro") === 0) return 0;
  if (c === "blanco" || c.indexOf("blanco") === 0 || c === "ivory" || c === "blanco hueso") return 1;
  if (c.indexOf("azul marino") === 0 || c.indexOf("navy") === 0 || c === "marino") return 2;
  if (c.indexOf("negro") !== -1) return 3;
  if (c.indexOf("blanco") !== -1 || c.indexOf("ivory") !== -1) return 4;
  if (c.indexOf("marino") !== -1 || c.indexOf("navy") !== -1) return 5;
  return 50;
}

function claveMO_(t) {
  var mo = normUp_(t.mo);
  var tipo = t.esEspecial ? "E" : "R";
  if (mo !== "") return mo + "||" + tipo;
  return "SKU:" + normUp_(t.sku) + "||" + tipo;
}

function cloneTask(t, newQty, isFase2) {
  return {
    sku: t.sku,
    modelo: t.modelo,
    detalle: t.detalle,
    detalleAlmacen: t.detalleAlmacen,
    lineas: t.lineas.slice(),
    cantidad: newQty,
    cantidadOriginal: t.cantidadOriginal,
    solicitadaOrig: t.solicitadaOrig !== undefined ? t.solicitadaOrig : t.cantidadOriginal,
    cap: t.cap,
    prioridadNum: t.prioridadNum,
    esEspecial: t.esEspecial,
    fechaKey: t.fechaKey,
    diaIngreso: t.diaIngreso,
    diaNoLaborable: t.diaNoLaborable,
    mo: t.mo,
    genero: t.genero,
    color: t.color,
    colorRank: t.colorRank !== undefined ? t.colorRank : rangoColor_(t.color),
    talla: t.talla,
    restante: newQty,
    planificada: 0,
    planificadaSem1: 0,
    ultimoDia: -1,
    plan: {},
    indice: t.indice,
    fase2: isFase2,
    lineaFija: t.lineaFija || null,
    esMinima: isFase2 ? false : !!t.esMinima,
    esSkuPrio: !!t.esSkuPrio,
    skuPrioOrden: t.skuPrioOrden !== undefined ? t.skuPrioOrden : 9999
  };
}

function clonarConBanda_(t, newQty, isFase2, esMinima) {
  var c = cloneTask(t, newQty, isFase2);
  c.esMinima = !isFase2 && !t.esEspecial && !!esMinima;
  return c;
}

function recSkuPrio_(mapa, sku) {
  if (!mapa) return null;
  var rec = mapa[claveSku_(sku)] || mapa[sku];
  if (rec === undefined || rec === null) return null;
  if (typeof rec === "number") return rec > 0 ? { min: rec, orden: 0 } : null;
  if (rec.min > 0) return rec;
  return null;
}

function marcarSkuPrioEnTarea_(t, mapaMinimasSku) {
  var rec = recSkuPrio_(mapaMinimasSku, t.sku);
  if (rec) {
    t.esSkuPrio = true;
    t.skuPrioOrden = rec.orden !== undefined ? rec.orden : 0;
  } else {
    t.esSkuPrio = false;
    if (t.skuPrioOrden === undefined) t.skuPrioOrden = 9999;
  }
}

function cmpTareasDentroModelo_(a, b) {
  var pa = a.esSkuPrio ? 0 : 1, pb = b.esSkuPrio ? 0 : 1;
  if (pa !== pb) return pa - pb;
  if (a.esSkuPrio && b.esSkuPrio) {
    var oa = a.skuPrioOrden !== undefined ? a.skuPrioOrden : 0;
    var ob = b.skuPrioOrden !== undefined ? b.skuPrioOrden : 0;
    if (oa !== ob) return oa - ob;
  }
  var ma = a.esMinima ? 0 : 1, mb = b.esMinima ? 0 : 1;
  if (ma !== mb) return ma - mb;
  var ra = rangoColor_(a.color), rb = rangoColor_(b.color);
  if (ra !== rb) return ra - rb;
  var ca = a.restante !== undefined ? a.restante : a.cantidad;
  var cb = b.restante !== undefined ? b.restante : b.cantidad;
  if (cb !== ca) return cb - ca;
  return String(a.sku).localeCompare(String(b.sku));
}

function expandirTareasPorMinima_(tareas, mapaMinimas, mapaMinimasSku) {
  mapaMinimas = mapaMinimas || {};
  mapaMinimasSku = mapaMinimasSku || {};

  var porModelo = {};
  var orden = [];
  tareas.forEach(function (t) {
    if (!porModelo[t.modelo]) {
      porModelo[t.modelo] = [];
      orden.push(t.modelo);
    }
    porModelo[t.modelo].push(t);
  });

  var out = [];
  orden.forEach(function (mod) {
    var group = porModelo[mod];
    if (group[0].esEspecial) {
      group.forEach(function (t) { out.push(clonarConBanda_(t, t.cantidad, false, false)); });
      return;
    }

    var minModelo = minimaDeModelo_(mapaMinimas, mod);
    var volFaltante = 0, volOriginal = 0;
    group.forEach(function (t) {
      volFaltante += t.cantidad;
      volOriginal += (t.solicitadaOrig !== undefined ? t.solicitadaOrig : t.cantidadOriginal);
    });
    var producido = Math.max(0, volOriginal - volFaltante);
    if (minModelo > 0 && producido >= minModelo) {
      group.forEach(function (t) { out.push(clonarConBanda_(t, t.cantidad, true, false)); });
      return;
    }
    var minModeloFaltante = Math.min(minModelo, volFaltante);

    if (!(minModeloFaltante > 0)) {
      group.forEach(function (t) { out.push(clonarConBanda_(t, t.cantidad, false, false)); });
      return;
    }
    if (minModeloFaltante >= volFaltante) {
      group.forEach(function (t) { out.push(clonarConBanda_(t, t.cantidad, false, true)); });
      return;
    }

    group.sort(function (a, b) {
      var ra = rangoColor_(a.color), rb = rangoColor_(b.color);
      if (ra !== rb) return ra - rb;
      if (b.cantidad !== a.cantidad) return b.cantidad - a.cantidad;
      return String(a.sku).localeCompare(String(b.sku));
    });
    var restoModelo = minModeloFaltante;
    group.forEach(function (t) {
      var left = t.cantidad;
      if (restoModelo > 0 && left > 0) {
        var takeMod = Math.min(left, restoModelo);
        out.push(clonarConBanda_(t, takeMod, false, true));
        restoModelo -= takeMod;
        left -= takeMod;
      }
      if (left > 0) out.push(clonarConBanda_(t, left, true, false));
    });
  });
  out.forEach(function (t) { marcarSkuPrioEnTarea_(t, mapaMinimasSku); });
  return out;
}

function leerMinimasSku_(ss) {
  var mapa = {};
  var hoja = hojaPorNombreFlex_(ss, NOMBRES_PRIO_SKU);
  if (!hoja || hoja.getLastRow() < 3) return mapa;

  var ancho = Math.max(8, hoja.getLastColumn());
  var headers = hoja.getRange(2, 2, 1, ancho - 1).getValues()[0];
  var iSku = idxExacto_(headers, "SKU");
  if (iSku === -1) iSku = idxPorFragmento_(headers, ["sku"]);
  if (iSku === -1) iSku = 0;
  var iProd = idxPorFragmento_(headers, ["producto", "modelo"]);
  var iGen = idxPorFragmento_(headers, ["genero", "género"]);
  var iMin = idxCantidadMinima_(headers);
  var iFec = idxPorFragmento_(headers, ["fecha"]);
  var iLin = idxPorFragmento_(headers, ["linea", "línea"]);

  var nFilas = hoja.getLastRow() - 2;
  if (nFilas < 1) return mapa;
  var datos = hoja.getRange(3, 2, nFilas, ancho - 1).getValues();
  for (var i = 0; i < datos.length; i++) {
    var sku = iSku !== -1 ? norm_(datos[i][iSku]) : "";
    if (sku === "") continue;
    var minVal = iMin !== -1 ? parseCantidad_(datos[i][iMin]) : 0;
    if (!(minVal > 0)) continue;
    var prod = iProd !== -1 ? norm_(datos[i][iProd]) : "";
    var gen = iGen !== -1 ? norm_(datos[i][iGen]) : "";
    var modelo = prod + (gen !== "" && gen !== "--" ? " " + gen : "");
    mapa[claveSku_(sku)] = {
      sku: sku,
      min: minVal,
      modelo: modelo,
      fechaKey: iFec !== -1 ? claveFecha_(datos[i][iFec]) : Infinity,
      lineas: iLin !== -1 ? parsearLineas_(datos[i][iLin]) : [],
      orden: i
    };
  }
  return mapa;
}

function guardarSnapshotPlan_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var hoja = ss.getSheetByName("Planificacion");
  if (!hoja) return null;

  var rango = hoja.getDataRange();
  if (rango.getNumRows() < 4) return null;

  var nombre = "📸 " + Utilities.formatDate(new Date(), ss.getSpreadsheetTimeZone(), "yyyy-MM-dd HH.mm");
  var previa = ss.getSheetByName(nombre);
  if (previa) ss.deleteSheet(previa);

  var copia = hoja.copyTo(ss).setName(nombre);
  var r = copia.getDataRange();
  r.setValues(r.getValues());
  copia.hideSheet();

  var snaps = ss.getSheets()
    .filter(function (s) { return s.getName().indexOf("📸 ") === 0; })
    .sort(function (a, b) { return a.getName().localeCompare(b.getName()); });
  while (snaps.length > MAX_SNAPSHOTS) {
    ss.deleteSheet(snaps.shift());
  }
  return nombre;
}

function leerEmbudo_(hoja, esEspecial, mapaPrioridades, mapaFechaModelo, tareas, skusSinMO, cfg) {
  if (!hoja) return;
  var filas = hoja.getLastRow();
  var cols = hoja.getLastColumn();
  if (filas < 3 || cols < 2) return;

  var datos = hoja.getRange(1, 1, filas, cols).getValues();
  var headers = datos[1];

  var iSKU  = idxExacto_(headers, "SKU");
  var iProd = idxPorFragmento_(headers, ["producto", "modelo"]);
  var iGen  = idxPorFragmento_(headers, ["genero", "género"]);
  var iTal  = idxPorFragmento_(headers, ["talla"]);
  var iCol  = idxPorFragmento_(headers, ["color"]);
  var iLin  = idxPorFragmento_(headers, ["linea", "línea"]);
  var iCant = idxPorFragmento_(headers, ["cantidad solicitada"]);
  var iFalt = idxPorFragmento_(headers, ["faltante"]);
  var iProdQty = idxPorFragmento_(headers, ["producida"]);
  var iCap  = idxPorFragmento_(headers, ["cap produccion", "cap producción", "promedio"]);
  var iDia  = idxPorFragmento_(headers, ["dia de inicio", "día de inicio", "dia de in", "día de in", "fecha de in"]);
  var iNoLab = idxPorFragmento_(headers, ["dia no lab", "día no lab", "feriado"]);
  var iMO   = idxExacto_(headers, "MO");
  var iFec  = idxPorFragmento_(headers, ["fecha de salida", "fecha salida"]);

  if (iSKU === -1 || iProd === -1 || iCant === -1 || iCap === -1 || (!esEspecial && iLin === -1)) {
    SpreadsheetApp.getUi().alert(
      "Error de encabezados en '" + hoja.getName() + "'.\n" +
      "Verifica que existan: SKU, Producto/Modelo, Linea de Produccion, Cantidad Solicitada y Cap Produccion por Dia (fila 2)."
    );
    throw new Error("Encabezados inválidos en " + hoja.getName());
  }

  var mapaDias = { "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, "jueves": 3, "viernes": 4 };

  for (var i = 2; i < datos.length; i++) {
    var fila = datos[i];
    var sku = norm_(fila[iSKU]);
    var productoBase = norm_(fila[iProd]);

    var cantSolicitada = Number(fila[iCant]) || 0;
    var cantProducida = iProdQty !== -1 ? (Number(fila[iProdQty]) || 0) : 0;

    var cantEfectiva = cantSolicitada;
    if (iProdQty !== -1) {
      cantEfectiva = Math.max(0, cantSolicitada - cantProducida);
    } else if (iFalt !== -1 && fila[iFalt] !== "") {
      var faltanteCelda = Number(fila[iFalt]);
      if (!isNaN(faltanteCelda)) cantEfectiva = faltanteCelda;
    }

    var cap = Number(fila[iCap]);
    var lineasStr = iLin !== -1 ? norm_(fila[iLin]) : "";

    if (sku === "" || productoBase === "" || !(cantEfectiva > 0) || !(cap > 0)) continue;
    if (lineasStr === "") {
      if (esEspecial) lineasStr = "1";
      else continue;
    }

    var genero = iGen !== -1 ? norm_(fila[iGen]) : "";
    var talla  = iTal !== -1 ? norm_(fila[iTal]) : "";
    var color  = iCol !== -1 ? norm_(fila[iCol]) : "";
    var mo     = iMO !== -1 ? norm_(fila[iMO]) : "";

    if (mo === "" && skusSinMO.indexOf(sku) === -1) skusSinMO.push(sku);

    var valDia = iDia !== -1 ? fila[iDia] : "";
    var diaIngreso = 0;
    var strDia = String(valDia).trim().toLowerCase();

    if (mapaDias[strDia] !== undefined) {
      diaIngreso = mapaDias[strDia];
    } else if (valDia !== "") {
      var fIngreso = null;
      if (valDia instanceof Date && !isNaN(valDia.getTime())) {
        fIngreso = new Date(valDia);
      } else {
        var mObj = strDia.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})$/);
        if (mObj) {
          var anio = Number(mObj[3]); if (anio < 100) anio += 2000;
          fIngreso = new Date(anio, Number(mObj[2]) - 1, Number(mObj[1]));
        }
      }

      if (fIngreso && !isNaN(fIngreso.getTime())) {
        fIngreso.setHours(0, 0, 0, 0);
        var maxDias = cfg.semanas * DIAS_LABORALES;
        diaIngreso = maxDias;
        for (var dx = 0; dx < maxDias; dx++) {
          var fechaHorizonte = fechaDeDia_(cfg, dx);
          fechaHorizonte.setHours(0, 0, 0, 0);
          if (fechaHorizonte.getTime() >= fIngreso.getTime()) {
            diaIngreso = dx;
            break;
          }
        }
        if (fIngreso.getTime() < fechaDeDia_(cfg, 0).getTime()) {
          diaIngreso = 0;
        }
      }
    }

    var noLabTexto = iNoLab !== -1 ? normLow_(fila[iNoLab]) : "";
    var diaNoLaborable = mapaDias[noLabTexto] !== undefined ? mapaDias[noLabTexto] : -1;

    var modelo = productoBase + (genero !== "" && genero !== "--" ? " " + genero : "");
    var detalle = productoBase;
    if (genero !== "" && genero !== "--") detalle += " " + genero;
    if (talla !== "" && talla !== "--") detalle += " " + talla;
    if (color !== "" && color !== "--") detalle += " " + color;

    var detalleAlmacen = productoBase;
    if (genero !== "" && genero !== "--") detalleAlmacen += " - " + genero;
    if (color !== "" && color !== "--") detalleAlmacen += " - " + color;
    if (talla !== "" && talla !== "--") detalleAlmacen += " - " + talla;

    if (esEspecial) {
      modelo += " (Especial)";
      detalle += " (Especial)";
      detalleAlmacen += " (Especial)";
    }

    var fechaKey = iFec !== -1 ? claveFecha_(fila[iFec]) : Infinity;
    if (!isFinite(fechaKey) && mapaFechaModelo[modelo] !== undefined) {
      fechaKey = mapaFechaModelo[modelo];
    }

    var lineas = parsearLineas_(lineasStr);
    if (lineas.length === 0) {
      lineas = lineasStr.split(",").map(function (l) { return l.trim(); }).filter(function (l) { return l !== ""; });
    }

    tareas.push({
      sku: sku, modelo: modelo, detalle: detalle, detalleAlmacen: detalleAlmacen, lineas: lineas,
      cantidad: cantEfectiva, cantidadOriginal: cantSolicitada, solicitadaOrig: cantSolicitada, cap: cap,
      prioridadNum: esEspecial ? 0 : (mapaPrioridades[modelo] !== undefined ? mapaPrioridades[modelo] : 5),
      esEspecial: esEspecial, fechaKey: fechaKey, diaIngreso: diaIngreso, diaNoLaborable: diaNoLaborable,
      mo: mo, genero: genero, color: color, colorRank: rangoColor_(color), talla: talla,
      restante: cantEfectiva, planificada: 0, planificadaSem1: 0, ultimoDia: -1, plan: {},
      indice: (esEspecial ? -100000 : 0) + i, fase2: false, lineaFija: null, esMinima: false,
      esSkuPrio: false, skuPrioOrden: 9999
    });
  }
}

function conLock_(fn) {
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(LOCK_MS)) {
    SpreadsheetApp.getUi().alert("Otro proceso está corriendo. Intenta de nuevo en unos segundos.");
    return;
  }
  try {
    fn();
  } finally {
    lock.releaseLock();
  }
}

// =====================================================================
//  MOTOR CENTRAL: generarPlanificacionSemanal()
// =====================================================================
function generarPlanificacionSemanal() {
  conLock_(generarPlanificacionSemanal_);
}

function generarPlanificacionSemanal_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  limpiarFiltros();
  var cfg = leerConfig_();
  cfg.semanas = Math.max(cfg.semanas, 5);
  var totalDias = DIAS_LABORALES * cfg.semanas;

  var hojaPorHacer = ss.getSheetByName("Por Hacer");
  var hojaEspecial = ss.getSheetByName("Por Hacer - Especial");
  var nombresHojasSemanas = ["Planificacion", "Semana 2", "Semana 3", "Semana 4", "Semana 5"];

  var hojaPriorizacion = ss.getSheetByName("Priorizacion");
  var hojaPendiente = ss.getSheetByName("Pendiente");
  var hojasLineas = {
    "1": ss.getSheetByName("Linea 1"), "2": ss.getSheetByName("Linea 2"),
    "3": ss.getSheetByName("Linea 3"), "4": ss.getSheetByName("Linea 4"),
    "5": ss.getSheetByName("Linea 5")
  };
  if (!hojaPorHacer || !ss.getSheetByName("Planificacion")) {
    SpreadsheetApp.getUi().alert("Faltan las hojas 'Por Hacer' o 'Planificacion'.");
    return;
  }

  ss.toast("Leyendo prioridades y fechas... (v" + VERSION_SISTEMA + ")", "⚙️ Planificando", 5);
  guardarSnapshotPlan_();
  asegurarHojaPriorizacionSkus_(ss);

  var jerarquiaInversa = { 0: "ESPECIAL (Satélite)", 1: "Urgente", 2: "Alta", 3: "Media", 4: "Baja", 5: "Sin Asignar" };
  var mapaPrioridades = {};
  var mapaFechaModelo = {};
  var mapaMinimas = {};
  var mapaLineasModelo = {};
  var mapaMinimasSku = leerMinimasSku_(ss);

  if (hojaPriorizacion && hojaPriorizacion.getLastRow() >= 3) {
    var anchoPrio = Math.max(6, hojaPriorizacion.getLastColumn());
    var headersPrio = hojaPriorizacion.getRange(2, 2, 1, anchoPrio - 1).getValues()[0];
    var idxTipo = idxPorFragmento_(headersPrio, ["tipo"]);
    var idxPrio = idxPorFragmento_(headersPrio, ["prioridad"]);
    var idxFec = idxPorFragmento_(headersPrio, ["fecha"]);
    var idxMin = idxCantidadMinima_(headersPrio);
    var idxLinP = idxPorFragmento_(headersPrio, ["linea", "línea"]);

    var datosPrio = hojaPriorizacion.getRange(3, 2, hojaPriorizacion.getLastRow() - 2, anchoPrio - 1).getValues();
    for (var p = 0; p < datosPrio.length; p++) {
      var modP = norm_(datosPrio[p][0]);
      var tipoP = idxTipo !== -1 ? norm_(datosPrio[p][idxTipo]) : "";
      if (modP === "") continue;

      if (tipoP.toLowerCase() === "especial") {
        modP += " (Especial)";
      }

      mapaPrioridades[modP] = idxPrio !== -1 ? prioridadNum_(datosPrio[p][idxPrio]) : 5;

      var fk = idxFec !== -1 ? claveFecha_(datosPrio[p][idxFec]) : Infinity;
      if (isFinite(fk)) mapaFechaModelo[modP] = fk;

      if (idxMin !== -1) {
        var minVal = parseCantidad_(datosPrio[p][idxMin]);
        if (minVal > 0) mapaMinimas[modP] = minVal;
      }
      if (idxLinP !== -1) {
        var lsPref = parsearLineas_(datosPrio[p][idxLinP]);
        if (lsPref.length > 0) mapaLineasModelo[modP] = lsPref;
      }
    }
  }

  var tareas = [];
  var skusSinMO = [];
  leerEmbudo_(hojaEspecial, true, mapaPrioridades, mapaFechaModelo, tareas, skusSinMO, cfg);
  leerEmbudo_(hojaPorHacer, false, mapaPrioridades, mapaFechaModelo, tareas, skusSinMO, cfg);

  if (skusSinMO.length > 0) {
    var maxMostrar = 15;
    var lista = skusSinMO.slice(0, maxMostrar).join("\n- ");
    if (skusSinMO.length > maxMostrar) lista += "\n... y " + (skusSinMO.length - maxMostrar) + " más.";
    SpreadsheetApp.getUi().alert(
      "🛑 ALERTA DE CONTROL DE PROCESOS 🛑\n\n" +
      "Se ha bloqueado la planificación porque existen productos sin Orden de Producción (MO).\n\n" +
      "SKUs sin MO:\n- " + lista + "\n\n" +
      "➡️ Ejecuta 'Actualizar MOs' antes de planificar."
    );
    return;
  }
  if (tareas.length === 0) {
    SpreadsheetApp.getUi().alert("No hay tareas válidas pendientes de producción.");
    return;
  }

  tareas.forEach(function (t) {
    var pref = mapaLineasModelo[t.modelo];
    if (pref && pref.length) {
      var inter = t.lineas.filter(function (l) { return pref.indexOf(l) !== -1; });
      if (inter.length) t.lineas = inter;
    }
    t.colorRank = rangoColor_(t.color);
    var recSku = mapaMinimasSku[claveSku_(t.sku)];
    if (recSku && !recSku.modelo) recSku.modelo = t.modelo;
  });

  var sumaSkuPorModelo = {};
  Object.keys(mapaMinimasSku).forEach(function (k) {
    var recS = mapaMinimasSku[k];
    if (recS.modelo) sumaSkuPorModelo[recS.modelo] = (sumaSkuPorModelo[recS.modelo] || 0) + recS.min;
  });

  var nModelosConMinima = Object.keys(mapaMinimas).length;
  var detalleMinimas = [];
  for (var mk in mapaMinimas) detalleMinimas.push(mk + ": " + mapaMinimas[mk]);
  var nSkusMin = Object.keys(mapaMinimasSku).length;
  var detalleSkusMin = [];
  Object.keys(mapaMinimasSku).forEach(function (k) {
    var rsk = mapaMinimasSku[k];
    detalleSkusMin.push(rsk.sku + ": " + rsk.min);
  });
  tareas = expandirTareasPorMinima_(tareas, mapaMinimas, mapaMinimasSku);

  tareas.sort(function (a, b) {
    var ba = bandaDe_(a), bb = bandaDe_(b);
    if (ba !== bb) return ba - bb;
    if (a.fechaKey !== b.fechaKey) return a.fechaKey - b.fechaKey;
    if (a.prioridadNum !== b.prioridadNum) return a.prioridadNum - b.prioridadNum;
    var ra = a.colorRank, rb = b.colorRank;
    if (ra !== rb) return ra - rb;
    if (b.cantidad !== a.cantidad) return b.cantidad - a.cantidad;
    if (a.modelo !== b.modelo) return a.modelo.localeCompare(b.modelo);
    return a.indice - b.indice;
  });

  ss.toast("Asignando capacidad (" + cfg.semanas + " semanas, cambio secuencial, L5 hasta 2)...", "⚙️ Planificando", 5);

  var carga = {};
  ["1", "2", "3", "4", "5"].forEach(function (l) {
    carga[l] = [];
    for (var d0 = 0; d0 < totalDias; d0++) carga[l].push(0.0);
  });

  var mapaModelos = {};
  var ordenModelos = [];
  tareas.forEach(function (t) {
    if (!mapaModelos[t.modelo]) {
      mapaModelos[t.modelo] = {
        nombre: t.modelo, tareas: [], volumen: 0,
        prioMin: t.prioridadNum, fechaMin: t.fechaKey,
        esEspecial: !!t.esEspecial, banda: bandaDe_(t)
      };
      ordenModelos.push(t.modelo);
    }
    var mm = mapaModelos[t.modelo];
    mm.tareas.push(t);
    mm.volumen += t.cantidad;
    if (t.prioridadNum < mm.prioMin) mm.prioMin = t.prioridadNum;
    if (t.fechaKey < mm.fechaMin) mm.fechaMin = t.fechaKey;
    var bt = bandaDe_(t);
    if (bt < mm.banda) mm.banda = bt;
  });

  var listaModelos = ordenModelos.map(function (n) { return mapaModelos[n]; });
  listaModelos.sort(cmpModelosCola_);
  listaModelos.forEach(function (m) {
    m.tareas.sort(cmpTareasDentroModelo_);
  });

  function restanteModelo_(m) {
    return m.tareas.reduce(function (s, t) { return s + t.restante; }, 0);
  }

  function restanteMinima_(m) {
    return m.tareas.reduce(function (s, t) { return s + (t.esMinima ? t.restante : 0); }, 0);
  }

  function tuvoMinima_(m) {
    return m.tareas.some(function (t) { return t.esMinima; });
  }

  function bandaViva_(m) {
    var b = 9;
    m.tareas.forEach(function (t) {
      if (t.restante > 0) {
        var bt = bandaDe_(t);
        if (bt < b) b = bt;
      }
    });
    return b;
  }

  function cmpModelosCola_(a, b) {
    if (a.banda !== b.banda) return a.banda - b.banda;
    if (a.fechaMin !== b.fechaMin) return a.fechaMin - b.fechaMin;
    if (a.prioMin !== b.prioMin) return a.prioMin - b.prioMin;
    if (b.volumen !== a.volumen) return b.volumen - a.volumen;
    return a.nombre.localeCompare(b.nombre);
  }

  function refrescarColaModelos_() {
    listaModelos.forEach(function (m) { m.banda = bandaViva_(m); });
    listaModelos.sort(cmpModelosCola_);
  }

  function capLinea_(lin) {
    return CAP_POR_LINEA[String(lin)] || 130;
  }

  function maxOcupantes_(lin) {
    return String(lin) === "5" ? MAX_MODELOS_LINEA5 : 1;
  }

  function asignar_(t, lin, d, maxPiezas) {
    if (maxPiezas <= 0 || t.restante <= 0) return 0;
    var piezas = Math.min(t.restante, maxPiezas);
    if (!t.plan[lin]) {
      t.plan[lin] = [];
      for (var k = 0; k < totalDias; k++) t.plan[lin].push(0);
    }
    t.plan[lin][d] += piezas;
    carga[lin][d] += piezas / capLinea_(lin);
    t.restante -= piezas;
    t.planificada += piezas;
    if (d < DIAS_LABORALES) t.planificadaSem1 += piezas;
    if (d > t.ultimoDia) t.ultimoDia = d;
    t.lineaFija = lin;
    return piezas;
  }

  var lineaPorMO = {};

  function estimarDiaFinLinea_(t, lin, fromDay) {
    var rest = t.restante;
    var capLin = capLinea_(lin);
    for (var d = fromDay; d < totalDias; d++) {
      if (d < diaInicioEfectivo_(t)) continue;
      if (d < DIAS_LABORALES && (d % DIAS_LABORALES) === t.diaNoLaborable) continue;
      var avail = Math.max(0, 1 - carga[lin][d]);
      var piezas = Math.floor(avail * capLin + 0.0001);
      rest -= piezas;
      if (rest <= 0) return d;
    }
    return totalDias + Math.max(0, rest);
  }

  function fijarLineaSiHaceFalta_(t, d) {
    var clave = claveMO_(t);
    if (lineaPorMO[clave]) {
      t.lineaFija = lineaPorMO[clave];
      return t.lineaFija;
    }
    if (t.lineaFija && carga[t.lineaFija] !== undefined) {
      lineaPorMO[clave] = t.lineaFija;
      return t.lineaFija;
    }
    var cands = t.lineas.filter(function (lin) { return carga[lin] !== undefined; });
    if (cands.length === 0) return null;
    if (cands.length === 1) {
      lineaPorMO[clave] = cands[0];
      t.lineaFija = cands[0];
      return cands[0];
    }
    cands.sort(function (a, b) {
      var fa = estimarDiaFinLinea_(t, a, d);
      var fb = estimarDiaFinLinea_(t, b, d);
      if (fa !== fb) return fa - fb;
      if (carga[a][d] !== carga[b][d]) return carga[a][d] - carga[b][d];
      return String(a).localeCompare(String(b));
    });
    lineaPorMO[clave] = cands[0];
    t.lineaFija = cands[0];
    return cands[0];
  }

  function nativosLinea1Pendientes_(d) {
    for (var iN = 0; iN < listaModelos.length; iN++) {
      var mN = listaModelos[iN];
      if (!mN.esEspecial || restanteModelo_(mN) <= 0) continue;
      var ocupandoOtra = ["2", "3", "4", "5"].some(function (l2) {
        return ocupante[l2].indexOf(mN.nombre) !== -1;
      });
      if (ocupandoOtra) continue;
      for (var tN = 0; tN < mN.tareas.length; tN++) {
        var tNat = mN.tareas[tN];
        if (tNat.restante <= 0 || tNat.lineas.indexOf("1") === -1) continue;
        if (d < diaInicioEfectivo_(tNat)) continue;
        if (d < DIAS_LABORALES && (d % DIAS_LABORALES) === tNat.diaNoLaborable) continue;
        var claveNat = claveMO_(tNat);
        if (lineaPorMO[claveNat] && lineaPorMO[claveNat] !== "1") continue;
        if (tNat.lineaFija && tNat.lineaFija !== "1") continue;
        return true;
      }
    }
    return false;
  }

  function elegiblesTarea_(t, overflow) {
    var ls = t.lineas.slice();
    if (t.esEspecial && overflow && ls.indexOf("1") === -1) ls.push("1");
    return ls.filter(function (l) { return carga[l] !== undefined; });
  }

  function capRestanteSemana_(lin, d) {
    var week = Math.floor(d / DIAS_LABORALES);
    var end = Math.min(totalDias, (week + 1) * DIAS_LABORALES);
    var cap = capLinea_(lin);
    var piezas = 0;
    for (var dd = d; dd < end; dd++) piezas += Math.max(0, 1 - carga[lin][dd]) * cap;
    return piezas;
  }

  function producirLote_(mP, lin, d, overflow, maxLote, soloMinima) {
    var capLin = capLinea_(lin);
    for (var ti = 0; ti < mP.tareas.length; ti++) {
      var t = mP.tareas[ti];
      var diaSemanaActual = d % DIAS_LABORALES;
      if (t.restante <= 0 || d < diaInicioEfectivo_(t) || (d < DIAS_LABORALES && diaSemanaActual === t.diaNoLaborable)) continue;
      if (soloMinima && !t.esMinima) continue;
      var clave = claveMO_(t);
      if (lineaPorMO[clave]) t.lineaFija = lineaPorMO[clave];
      if (t.lineaFija && t.lineaFija !== lin) continue;
      if (elegiblesTarea_(t, overflow).indexOf(lin) === -1) continue;
      var avail = 1 - carga[lin][d];
      if (avail <= 0.001) return 0;
      var piezasCaben = Math.floor(avail * capLin + 0.0001);
      if (maxLote > 0) piezasCaben = Math.min(piezasCaben, maxLote);
      if (piezasCaben <= 0) return 0;
      var puestas = asignar_(t, lin, d, piezasCaben);
      if (puestas > 0) {
        lineaPorMO[clave] = lin;
        return puestas;
      }
    }
    return 0;
  }

  function producirModeloDia_(mP, lin, d, overflow) {
    var soloMinima = restanteMinima_(mP) > 0;
    while (carga[lin][d] < 0.999) {
      if (producirLote_(mP, lin, d, overflow, 0, soloMinima) <= 0) break;
    }
  }

  function producirRuedaLinea5_(noms, d, overflow) {
    var lin = "5";
    var iR = 0;
    var estancado = 0;
    while (carga[lin][d] < 0.999 && estancado < noms.length) {
      var nom = noms[iR % noms.length];
      iR++;
      var soloMinima = restanteMinima_(mapaModelos[nom]) > 0;
      var p = producirLote_(mapaModelos[nom], lin, d, overflow, LOTE_RUEDA_LINEA5, soloMinima);
      estancado = p > 0 ? 0 : estancado + 1;
    }
  }

  var ocupante = { "1": [], "2": [], "3": [], "4": [], "5": [] };

  for (var d = 0; d < totalDias; d++) {
    refrescarColaModelos_();
    if (d % DIAS_LABORALES === 0) {
      ["1", "2", "3", "4", "5"].forEach(function (lin) { ocupante[lin] = []; });
    }
    var overflowL1 = !nativosLinea1Pendientes_(d);
    ["1", "2", "3", "4", "5"].forEach(function (lin) {
      ocupante[lin] = ocupante[lin].filter(function (mod) {
        var mO = mapaModelos[mod];
        if (!mO || restanteModelo_(mO) <= 0) return false;
        return mO.tareas.some(function (t) {
          if (t.restante <= 0 || d < diaInicioEfectivo_(t)) return false;
          if (d < DIAS_LABORALES && (d % DIAS_LABORALES) === t.diaNoLaborable) return false;
          if (t.lineaFija && t.lineaFija !== lin) return false;
          return elegiblesTarea_(t, overflowL1).indexOf(lin) !== -1;
        });
      });
    });
    overflowL1 = !nativosLinea1Pendientes_(d);

    function lineasLibresDe_(m) {
      var out = [], seen = {};
      m.tareas.forEach(function (t) {
        if (t.restante <= 0) return;
        elegiblesTarea_(t, overflowL1).forEach(function (lin) {
          if (seen[lin]) return;
          var occ = ocupante[lin] || [];
          if (occ.indexOf(m.nombre) !== -1) return;
          if (occ.length >= maxOcupantes_(lin)) return;
          seen[lin] = true;
          out.push(lin);
        });
      });
      return out;
    }

    var vivos = listaModelos.filter(function (m) { return restanteModelo_(m) > 0; });
    vivos.forEach(function (m) {
      var ya = ["1", "2", "3", "4", "5"].some(function (lin) {
        return ocupante[lin].indexOf(m.nombre) !== -1;
      });
      if (ya) return;
      var libres = lineasLibresDe_(m);
      if (libres.length === 0) return;
      libres.sort(function (a, b) {
        if (carga[a][d] !== carga[b][d]) return carga[a][d] - carga[b][d];
        return String(a).localeCompare(String(b));
      });
      ocupante[libres[0]].push(m.nombre);
    });
    vivos.forEach(function (m) {
      if (m.banda > BANDA_URGENTE) return;
      var owned = ["1", "2", "3", "4", "5"].filter(function (lin) {
        return ocupante[lin].indexOf(m.nombre) !== -1;
      });
      if (owned.length === 0) return;
      var capOwned = owned.reduce(function (s, lin) { return s + capRestanteSemana_(lin, d); }, 0);
      if (restanteModelo_(m) <= capOwned + 0.001) return;
      lineasLibresDe_(m).forEach(function (lin) {
        if (restanteModelo_(m) <= capOwned + 0.001) return;
        ocupante[lin].push(m.nombre);
        capOwned += capRestanteSemana_(lin, d);
      });
    });
    if (overflowL1 && ocupante["1"].length === 0) {
      for (var iE = 0; iE < vivos.length; iE++) {
        var mE = vivos[iE];
        if (!mE.esEspecial) continue;
        var hayPend = mE.tareas.some(function (t) {
          return t.restante > 0 && (!t.lineaFija || t.lineaFija === "1");
        });
        if (!hayPend) continue;
        ocupante["1"].push(mE.nombre);
        break;
      }
    }

    vivos.forEach(function (m) {
      var owned = ["1", "2", "3", "4", "5"].filter(function (lin) {
        return ocupante[lin].indexOf(m.nombre) !== -1;
      });
      if (owned.length < 2) return;
      var unfixed = m.tareas.filter(function (t) {
        return t.restante > 0 && !t.lineaFija && !lineaPorMO[claveMO_(t)] && d >= diaInicioEfectivo_(t);
      });
      unfixed.sort(cmpTareasDentroModelo_);
      var load = {};
      owned.forEach(function (lin) { load[lin] = carga[lin][d]; });
      unfixed.forEach(function (t) {
        var cands = owned.filter(function (lin) { return elegiblesTarea_(t, overflowL1).indexOf(lin) !== -1; });
        if (cands.length === 0) cands = owned;
        cands.sort(function (a, b) {
          if (load[a] !== load[b]) return load[a] - load[b];
          return String(a).localeCompare(String(b));
        });
        t.lineaFija = cands[0];
        lineaPorMO[claveMO_(t)] = cands[0];
        load[cands[0]] += 0.01;
      });
    });

    function modeloPuedeProducirHoy_(nom, lin, d, overflow) {
      var mO = mapaModelos[nom];
      if (!mO || restanteModelo_(mO) <= 0) return false;
      return mO.tareas.some(function (t) {
        if (t.restante <= 0 || d < diaInicioEfectivo_(t)) return false;
        if (d < DIAS_LABORALES && (d % DIAS_LABORALES) === t.diaNoLaborable) return false;
        var clave = claveMO_(t);
        if (lineaPorMO[clave] && lineaPorMO[clave] !== lin) return false;
        if (t.lineaFija && t.lineaFija !== lin) return false;
        return elegiblesTarea_(t, overflow).indexOf(lin) !== -1;
      });
    }

    function siguienteCandidato_(lin, d, overflow, skip) {
      skip = skip || {};
      for (var iC = 0; iC < listaModelos.length; iC++) {
        var mC = listaModelos[iC];
        if (restanteModelo_(mC) <= 0) continue;
        if (skip[mC.nombre]) continue;
        if (ocupante[lin].indexOf(mC.nombre) !== -1) continue;
        var yaOtra = ["1", "2", "3", "4", "5"].some(function (l2) {
          return l2 !== lin && ocupante[l2].indexOf(mC.nombre) !== -1;
        });
        if (yaOtra && !(overflow && lin === "1" && mC.esEspecial)) continue;
        if (!modeloPuedeProducirHoy_(mC.nombre, lin, d, overflow)) continue;
        return mC.nombre;
      }
      return null;
    }

    function producirLineaDia_(lin, d) {
      var skip = {};
      var guard = 0;
      while (carga[lin][d] < 0.999 && guard < 40) {
        guard++;
        var overflow = !nativosLinea1Pendientes_(d);
        ocupante[lin] = ocupante[lin].filter(function (nom) {
          return !skip[nom] && modeloPuedeProducirHoy_(nom, lin, d, overflow);
        });
        var noms = ocupante[lin];
        var before = carga[lin][d];
        if (String(lin) === "5" && noms.length >= 2) {
          producirRuedaLinea5_(noms, d, overflow);
        } else if (noms.length > 0) {
          producirModeloDia_(mapaModelos[noms[0]], lin, d, overflow);
        }
        if (carga[lin][d] >= 0.999) break;

        ocupante[lin] = ocupante[lin].filter(function (nom) {
          if (skip[nom] || !modeloPuedeProducirHoy_(nom, lin, d, overflow)) return false;
          var mOcc = mapaModelos[nom];
          if (tuvoMinima_(mOcc) && restanteMinima_(mOcc) <= 0) return false;
          return true;
        });
        if (carga[lin][d] <= before + 0.0001) {
          ocupante[lin].forEach(function (nom) { skip[nom] = true; });
          ocupante[lin] = ocupante[lin].filter(function (nom) { return !skip[nom]; });
        }
        refrescarColaModelos_();
        overflow = !nativosLinea1Pendientes_(d);
        if (ocupante[lin].length >= maxOcupantes_(lin)) break;
        var next = siguienteCandidato_(lin, d, overflow, skip);
        if (!next) break;
        ocupante[lin].push(next);
      }
    }

    ["1", "2", "3", "4", "5"].forEach(function (lin) {
      producirLineaDia_(lin, d);
    });
  }

  if (cfg.forzarMeta) {
    tareas.forEach(function (t) {
      if (t.restante <= 0) return;
      var lin = t.lineaFija || fijarLineaSiHaceFalta_(t, t.diaIngreso || 0);
      if (!lin || carga[lin] === undefined) return;

      var dias = [];
      for (var dF = t.diaIngreso; dF < DIAS_LABORALES; dF++) {
        if (dF !== t.diaNoLaborable) dias.push(dF);
      }
      if (dias.length === 0) return;
      var base = Math.floor(t.restante / dias.length);
      var resto = t.restante % dias.length;
      dias.forEach(function (dF, idx) {
        asignar_(t, lin, dF, base + (idx < resto ? 1 : 0));
      });
    });
  }

  ss.toast("Dibujando tableros...", "⚙️ Planificando", 5);

  var datosPorLinea = { "1": [], "2": [], "3": [], "4": [], "5": [] };
  var mapaGlobal = {};
  var infoModelo = {};
  var infoSku = {};
  var consolLineaData = { "1": {}, "2": {}, "3": {}, "4": {}, "5": {} };
  var mosMultiLinea = 0;
  var mosAtomicas = 0;
  var piezasFase1 = 0;
  var piezasFase2 = 0;

  tareas.forEach(function (t) {
    if (t.fase2) piezasFase2 += t.planificada;
    else piezasFase1 += t.planificada;

    if (!infoModelo[t.modelo]) {
      infoModelo[t.modelo] = {
        solicitada: 0, sem1: 0, prioMin: t.prioridadNum,
        fechaObj: t.fechaKey, mos: new Set(),
        porSemana: [], restante: 0, ultimoDia: -1,
        diaFinEstimado: -1,
        minima: Math.max(minimaDeModelo_(mapaMinimas, t.modelo), sumaSkuPorModelo[t.modelo] || 0),
        bandaMin: 9
      };
      for (var w = 0; w < cfg.semanas; w++) infoModelo[t.modelo].porSemana.push(0);
    }
    var im = infoModelo[t.modelo];
    im.solicitada += t.cantidad;
    im.sem1 += t.planificadaSem1;
    im.restante += t.restante;
    var bandaT = bandaDe_(t);
    if (bandaT < im.bandaMin) im.bandaMin = bandaT;
    if (t.prioridadNum < im.prioMin) im.prioMin = t.prioridadNum;
    if (t.fechaKey < im.fechaObj) im.fechaObj = t.fechaKey;
    if (t.ultimoDia > im.ultimoDia) im.ultimoDia = t.ultimoDia;
    if (t.mo !== "") {
      t.mo.split(",").map(function (m) { return m.trim(); })
        .filter(function (m) { return m !== ""; })
        .forEach(function (m) { im.mos.add(m); });
    }

    var skuKey = t.sku + "||" + (t.esEspecial ? "ESPECIAL" : "PRODUCCION");
    if (!infoSku[skuKey]) {
      infoSku[skuKey] = {
        sku: t.sku,
        modelo: t.modelo,
        detalle: t.detalle,
        genero: t.genero, color: t.color, talla: t.talla, cap: t.cap,
        lineas: t.lineas, esEspecial: t.esEspecial,
        solicitada: 0, sem1: 0, prioMin: t.prioridadNum,
        fechaObj: t.fechaKey, porSemana: [], restante: 0, ultimoDia: -1,
        diaFinEstimado: -1, lineaAsignada: t.lineaFija || "",
        minima: (mapaMinimasSku[claveSku_(t.sku)] || {}).min || 0,
        esSkuPrio: !!t.esSkuPrio,
        skuPrioOrden: t.skuPrioOrden !== undefined ? t.skuPrioOrden : 9999
      };
      for (var wSku = 0; wSku < cfg.semanas; wSku++) infoSku[skuKey].porSemana.push(0);
    }
    var isku = infoSku[skuKey];
    isku.solicitada += t.cantidad;
    isku.sem1 += t.planificadaSem1;
    isku.restante += t.restante;
    if (t.prioridadNum < isku.prioMin) isku.prioMin = t.prioridadNum;
    if (t.fechaKey < isku.fechaObj) isku.fechaObj = t.fechaKey;
    if (t.ultimoDia > isku.ultimoDia) isku.ultimoDia = t.ultimoDia;
    if (t.lineaFija) isku.lineaAsignada = t.lineaFija;

    var diaFinTarea = t.ultimoDia;
    if (t.restante > 0 && t.cap > 0) {
      var diasExtra = Math.ceil(t.restante / t.cap);
      diaFinTarea = (totalDias - 1) + diasExtra;
    }
    if (diaFinTarea > im.diaFinEstimado) im.diaFinEstimado = diaFinTarea;
    if (diaFinTarea > isku.diaFinEstimado) isku.diaFinEstimado = diaFinTarea;

    var lineasUsadasTarea = [];
    for (var lin in t.plan) {
      var arr = t.plan[lin];
      var totalLinea = 0, sem1Linea = 0;
      for (var d = 0; d < totalDias; d++) {
        totalLinea += arr[d];
        if (d < DIAS_LABORALES) sem1Linea += arr[d];
        var indexSemana = Math.floor(d / DIAS_LABORALES);
        im.porSemana[indexSemana] += arr[d];
        isku.porSemana[indexSemana] += arr[d];
      }
      if (totalLinea <= 0) continue;
      lineasUsadasTarea.push(lin);

      if (sem1Linea > 0 || totalLinea > 0) {
        var kLin = t.sku + "_" + t.mo + "_" + (t.esEspecial ? "E" : "R");
        if (!consolLineaData[lin][kLin]) {
          consolLineaData[lin][kLin] = {
            mo: t.mo, sku: t.sku, detalle: t.detalle, totalLinea: 0,
            dias: [0, 0, 0, 0, 0], sem1Linea: 0
          };
        }
        var cl = consolLineaData[lin][kLin];
        cl.totalLinea += totalLinea;
        cl.sem1Linea += sem1Linea;
        for (var dDia = 0; dDia < 5; dDia++) cl.dias[dDia] += arr[dDia];
      }

      var clave = lin + "_" + t.modelo;
      if (!mapaGlobal[clave]) {
        mapaGlobal[clave] = {
          linea: lin, modelo: t.modelo, solicitada: 0,
          dias: new Array(totalDias).fill(0),
          totalSemana: 0, mos: new Set()
        };
      }
      var mg = mapaGlobal[clave];
      mg.solicitada += totalLinea;
      for (var d5 = 0; d5 < totalDias; d5++) mg.dias[d5] += arr[d5];
      mg.totalSemana += sem1Linea;
      if (t.mo !== "") {
        t.mo.split(",").map(function (mm) { return mm.trim(); })
          .filter(function (mm) { return mm !== ""; })
          .forEach(function (mm) { mg.mos.add(mm); });
      }
    }
    if (lineasUsadasTarea.length > 1) mosMultiLinea++;
    else if (lineasUsadasTarea.length === 1) mosAtomicas++;
  });

  for (var l in consolLineaData) {
    for (var k in consolLineaData[l]) {
      var clD = consolLineaData[l][k];
      datosPorLinea[l].push([
        clD.mo, clD.sku, clD.detalle, clD.totalLinea,
        clD.dias[0] === 0 ? "--" : clD.dias[0],
        clD.dias[1] === 0 ? "--" : clD.dias[1],
        clD.dias[2] === 0 ? "--" : clD.dias[2],
        clD.dias[3] === 0 ? "--" : clD.dias[3],
        clD.dias[4] === 0 ? "--" : clD.dias[4],
        clD.sem1Linea
      ]);
    }
  }

  for (var linW in hojasLineas) {
    var hl = hojasLineas[linW];
    if (!hl) continue;
    var arrData = datosPorLinea[linW];

    var maxFilasL = hl.getMaxRows();
    if (maxFilasL > 2) {
      hl.getRange(3, 2, maxFilasL - 2, 10).clearContent();
      hl.getRange(3, 2, maxFilasL - 2, 10).setBorder(false, false, false, false, false, false);
    }

    if (arrData.length > 0) {
      arrData.sort(function (a, b) {
        var diaA = 9, diaB = 9;
        for (var i = 4; i <= 8; i++) { if (a[i] !== "--" && a[i] > 0) { diaA = i; break; } }
        for (var j = 4; j <= 8; j++) { if (b[j] !== "--" && b[j] > 0) { diaB = j; break; } }
        if (diaA !== diaB) return diaA - diaB;
        if (b[9] !== a[9]) return b[9] - a[9];
        return String(a[1]).localeCompare(String(b[1]));
      });

      var rDest = hl.getRange(3, 2, arrData.length, 10);
      rDest.setValues(arrData)
        .setHorizontalAlignment("center")
        .setVerticalAlignment("middle")
        .setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.SOLID);
      hl.getRange(3, 2, arrData.length, 1).setNumberFormat("@");
    }
  }

  dibujarTablerosSemanales_(ss, cfg, nombresHojasSemanas, mapaGlobal, infoModelo, hojasLineas, hojaPendiente, jerarquiaInversa);
  dibujarPendiente_(hojaPendiente, tareas, cfg);
  dibujarProyecciones_(ss, cfg, infoModelo, infoSku);
  dibujarAlmacen_(ss, cfg, tareas, infoModelo, totalDias);

  var nMinAplicadas = 0;
  var piezasMinima = 0;
  tareas.forEach(function (t) {
    if (t.esMinima) piezasMinima += t.planificada;
  });
  for (var modMin in mapaMinimas) {
    if (infoModelo[modMin]) nMinAplicadas++;
  }
  var txtMin = detalleMinimas.length ? detalleMinimas.join("\n  - ") : "(ningún modelo con cupo > 0 en Priorizacion)";
  var txtSkuMin = detalleSkusMin.length
    ? detalleSkusMin.slice(0, 15).join("\n  - ") + (detalleSkusMin.length > 15 ? "\n  - … +" + (detalleSkusMin.length - 15) + " SKUs" : "")
    : "(ningún SKU con cupo en Priorizacion - SKUs)";

  SpreadsheetApp.getUi().alert(
    "✅ Planificación v" + VERSION_SISTEMA + " generada\n\n" +
    "• Líneas 1-4: un modelo a la vez (no en paralelo). Si termina, el sobrante del día pasa al siguiente.\n" +
    "• Línea 5: hasta 2 modelos en paralelo (40 pzas/día; rueda de 5 si hay dos).\n" +
    "• SKUs de Priorizacion - SKUs salen primero cuando el modelo entra; luego colores núcleo.\n" +
    "• Orden de carga: 1) Especial  →  2) Cantidad mínima  →  3) Urgente / resto.\n" +
    "• Cupo mínimo de modelo (" + nModelosConMinima + "):\n  - " + txtMin + "\n" +
    "• Cupo mínimo de SKU (" + nSkusMin + "):\n  - " + txtSkuMin + "\n" +
    "  Programadas en banda mínima: " + piezasMinima + " pzas.  |  Modelos vivos con cupo: " + nMinAplicadas + "\n" +
    "  Fase 1 (mínima): " + piezasFase1 + " pzas.  |  Fase 2 (resto): " + piezasFase2 + " pzas.\n" +
    "• Tableros semanales ordenados por flujo diario (primer día con producción).\n" +
    "• MOs atómicas (1 línea): " + mosAtomicas + (mosMultiLinea ? "\n⚠️ MOs partidas (no debería ocurrir): " + mosMultiLinea : "") + "\n" +
    "• Proyección: amarillo al llegar a la mínima, verde al llegar a la meta."
  );
}

function numCeldaDia_(row, idx) {
  if (idx < 4 || idx > 8) return 0;
  var v = row[idx];
  if (v === "--" || v === "" || v === null || v === undefined) return 0;
  return Number(v) || 0;
}

function primerDiaFila_(row) {
  for (var i = 4; i <= 8; i++) {
    if (numCeldaDia_(row, i) > 0) return i;
  }
  return 99;
}

function dibujarTablerosSemanales_(ss, cfg, nombresHojasSemanas, mapaGlobal, infoModelo, hojasLineas, hojaPendiente, jerarquiaInversa) {
  for (var ws = 0; ws < 5; ws++) {
    var nombreHojaS = nombresHojasSemanas[ws];
    var hojaS = ss.getSheetByName(nombreHojaS);
    if (!hojaS) continue;

    var fechasS = [];
    for (var ds = 0; ds < 5; ds++) {
      var msS = fechaDeDia_(cfg, ws * 5 + ds).getTime();
      fechasS.push(Utilities.formatDate(new Date(msS), cfg.tz, "dd/MM/yyyy"));
    }
    hojaS.getRange(2, 6, 1, 5).setValues([fechasS])
      .setHorizontalAlignment("center").setVerticalAlignment("middle")
      .setFontWeight("bold").setFontColor("#000000");

    var datosGlobalesS = [];
    var totalesPorLineaS = {};
    var totDiasS = [0, 0, 0, 0, 0];
    var granTotalS = 0;
    var totalMOsGlobalS = new Set();

    for (var clave in mapaGlobal) {
      var regS = mapaGlobal[clave];
      var sumS = 0;
      var valDias = [];
      for (var dx = 0; dx < 5; dx++) {
        var v = regS.dias[ws * 5 + dx] || 0;
        sumS += v;
        valDias.push(v);
      }
      if (sumS <= 0) continue;

      totalesPorLineaS[regS.linea] = (totalesPorLineaS[regS.linea] || 0) + sumS;

      datosGlobalesS.push([
        regS.linea, regS.modelo, regS.mos.size, regS.solicitada,
        valDias[0] === 0 ? "--" : valDias[0],
        valDias[1] === 0 ? "--" : valDias[1],
        valDias[2] === 0 ? "--" : valDias[2],
        valDias[3] === 0 ? "--" : valDias[3],
        valDias[4] === 0 ? "--" : valDias[4],
        sumS, 0
      ]);
      for (var dx2 = 0; dx2 < 5; dx2++) totDiasS[dx2] += valDias[dx2];
      granTotalS += sumS;
      regS.mos.forEach(function (m) { totalMOsGlobalS.add(m); });
    }

    datosGlobalesS.forEach(function (row) { row[10] = totalesPorLineaS[row[0]]; });

    var maxFilasS = hojaS.getMaxRows();
    if (maxFilasS > 3) {
      var limpS = hojaS.getRange(4, 1, maxFilasS - 3, 15);
      try { limpS.breakMergedRanges(); } catch (e) {}
      try { limpS.clear(); } catch (e) {}
    }

    var filaTotalesS = 4;
    if (datosGlobalesS.length > 0) {
      datosGlobalesS.sort(function (a, b) {
        if (String(a[0]) !== String(b[0])) return String(a[0]).localeCompare(String(b[0]));
        var da = primerDiaFila_(a);
        var db = primerDiaFila_(b);
        if (da !== db) return da - db;
        var ia = infoModelo[a[1]] || {};
        var ib = infoModelo[b[1]] || {};
        var ba = (ia.bandaMin !== undefined) ? ia.bandaMin : 9;
        var bb = (ib.bandaMin !== undefined) ? ib.bandaMin : 9;
        if (ba !== bb) return ba - bb;
        var qtyA = numCeldaDia_(a, da);
        var qtyB = numCeldaDia_(b, db);
        if (qtyA !== qtyB) return qtyB - qtyA;
        return String(a[1]).localeCompare(String(b[1]));
      });

      var rangoS = hojaS.getRange(4, 2, datosGlobalesS.length, 11);
      var richTextS = [];
      for (var r = 0; r < datosGlobalesS.length; r++) {
        var filaRT = [];
        var linReg = String(datosGlobalesS[r][0]);
        var targetSheet = hojasLineas[linReg];
        var sheetId = targetSheet ? targetSheet.getSheetId() : null;
        for (var cc = 0; cc < datosGlobalesS[r].length; cc++) {
          var builder = SpreadsheetApp.newRichTextValue().setText(String(datosGlobalesS[r][cc]));
          if ((cc === 0 || cc === 1) && sheetId !== null) builder.setLinkUrl("#gid=" + sheetId);
          filaRT.push(builder.build());
        }
        richTextS.push(filaRT);
      }
      rangoS.setRichTextValues(richTextS).setHorizontalAlignment("center").setVerticalAlignment("middle");

      var filaInicio = 0;
      for (var r3 = 0; r3 < datosGlobalesS.length; r3++) {
        var linAct = datosGlobalesS[r3][0];
        var linSig = (r3 + 1 < datosGlobalesS.length) ? datosGlobalesS[r3 + 1][0] : null;
        if (linAct !== linSig) {
          var nFil = r3 - filaInicio + 1;
          var bloque = hojaS.getRange(4 + filaInicio, 2, nFil, 11);
          try {
            bloque.setBorder(null, null, null, null, true, false, "#cccccc", SpreadsheetApp.BorderStyle.SOLID);
            bloque.setBorder(true, true, true, true, null, null, "black", SpreadsheetApp.BorderStyle.SOLID_MEDIUM);
            var nInt = parseInt(linAct, 10);
            bloque.setBackground(!isNaN(nInt) && nInt % 2 === 0 ? "#E6F2FF" : "#FFFFFF");
          } catch (e) {}
          try {
            var cLin = hojaS.getRange(4 + filaInicio, 2, nFil, 1);
            if (nFil > 1) cLin.mergeVertically();
            cLin.setHorizontalAlignment("center").setVerticalAlignment("middle");
          } catch (e) {}
          try {
            var cTot = hojaS.getRange(4 + filaInicio, 12, nFil, 1);
            if (nFil > 1) cTot.mergeVertically();
            cTot.setHorizontalAlignment("center").setVerticalAlignment("middle")
              .setBackground("#6FA8DC").setFontColor("#000000").setFontWeight("bold");
          } catch (e) {}
          filaInicio = r3 + 1;
        }
      }

      filaTotalesS = 4 + datosGlobalesS.length;
      hojaS.getRange(filaTotalesS, 4).setValue(totalMOsGlobalS.size)
        .setHorizontalAlignment("center").setVerticalAlignment("middle")
        .setFontWeight("bold").setFontColor("#000000");

      var celdasTotS = hojaS.getRange(filaTotalesS, 6, 1, 5);
      celdasTotS.setValues([[totDiasS[0], totDiasS[1], totDiasS[2], totDiasS[3], totDiasS[4]]])
        .setBackground("#6FA8DC").setFontWeight("bold").setFontColor("#000000")
        .setHorizontalAlignment("center").setVerticalAlignment("middle")
        .setBorder(null, null, null, null, true, false, "#cccccc", SpreadsheetApp.BorderStyle.SOLID)
        .setBorder(true, true, true, true, null, null, "black", SpreadsheetApp.BorderStyle.SOLID_MEDIUM);

      hojaS.getRange(filaTotalesS, 11).setValue(granTotalS)
        .setBackground("#00BFFF").setFontWeight("bold").setFontColor("#000000")
        .setHorizontalAlignment("center").setVerticalAlignment("middle")
        .setBorder(true, true, true, true, null, null, "black", SpreadsheetApp.BorderStyle.SOLID_MEDIUM);
    }

    var datosResumenS = [];
    var totalSolS = 0, totalPlanS = 0, totalMOsResS = new Set();

    for (var modS in infoModelo) {
      var imS = infoModelo[modS];
      var acumuladoPrevio = 0;
      for (var prev = 0; prev < ws; prev++) acumuladoPrevio += imS.porSemana[prev];
      var metaSemanaActual = Math.max(0, imS.solicitada - acumuladoPrevio);

      if (metaSemanaActual <= 0 && imS.porSemana[ws] <= 0) continue;

      var planS = imS.porSemana[ws];
      var pendS = Math.max(0, metaSemanaActual - planS);

      datosResumenS.push({
        modelo: modS, mos: imS.mos.size, meta: metaSemanaActual, plan: planS,
        pct: metaSemanaActual > 0 ? planS / metaSemanaActual : (planS > 0 ? 1 : 0),
        pendiente: pendS, prioMin: imS.prioMin, fechaObj: imS.fechaObj,
        bandaMin: (imS.bandaMin !== undefined) ? imS.bandaMin : 9
      });
      totalSolS += metaSemanaActual; totalPlanS += planS;
      imS.mos.forEach(function (m) { totalMOsResS.add(m); });
    }

    datosResumenS.sort(function (a, b) {
      if (a.bandaMin !== b.bandaMin) return a.bandaMin - b.bandaMin;
      var aPlan = a.plan > 0, bPlan = b.plan > 0;
      if (aPlan !== bPlan) return aPlan ? -1 : 1;
      if (a.fechaObj !== b.fechaObj) return a.fechaObj - b.fechaObj;
      if (a.prioMin !== b.prioMin) return a.prioMin - b.prioMin;
      if (b.meta !== a.meta) return b.meta - a.meta;
      if (b.pendiente !== a.pendiente) return b.pendiente - a.pendiente;
      return a.modelo.localeCompare(b.modelo);
    });

    var filaInicioResumenS = filaTotalesS + 3;
    var cabResS = hojaS.getRange(filaInicioResumenS, 3, 1, 5);
    var tituloMeta = ws === 0 ? "Meta Actual (Faltante)" : "Meta Sem " + (ws + 1) + " (Arrastre)";
    cabResS.setValues([["Modelo", "MOs", tituloMeta, "A Fabricar", "% Cobertura"]])
      .setBackground("#434343").setFontColor("#FFFFFF").setFontWeight("bold")
      .setHorizontalAlignment("center").setVerticalAlignment("middle")
      .setBorder(true, true, true, true, null, null, "black", SpreadsheetApp.BorderStyle.SOLID_MEDIUM);

    var filaTotalesResumenS = filaInicioResumenS;
    if (datosResumenS.length > 0) {
      var matResS = datosResumenS.map(function (x) { return [x.modelo, x.mos, x.meta, x.plan, x.pct]; });
      var rResS = hojaS.getRange(filaInicioResumenS + 1, 3, matResS.length, 5);
      rResS.setValues(matResS)
        .setHorizontalAlignment("center").setVerticalAlignment("middle")
        .setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.SOLID);
      hojaS.getRange(filaInicioResumenS + 1, 7, matResS.length, 1).setNumberFormat("0.00%");

      filaTotalesResumenS = filaInicioResumenS + 1 + matResS.length;
      var pctTotS = totalSolS > 0 ? totalPlanS / totalSolS : 0;
      var rTotResS = hojaS.getRange(filaTotalesResumenS, 3, 1, 5);
      rTotResS.setValues([["TOTAL", totalMOsResS.size, totalSolS, totalPlanS, pctTotS]])
        .setBackground("#6FA8DC").setFontWeight("bold").setFontColor("#000000")
        .setHorizontalAlignment("center").setVerticalAlignment("middle")
        .setBorder(true, true, true, true, null, null, "black", SpreadsheetApp.BorderStyle.SOLID_MEDIUM);
      hojaS.getRange(filaTotalesResumenS, 7).setNumberFormat("0.00%");
    }

    var pendientesS = datosResumenS.filter(function (x) { return x.pendiente > 0; });
    if (pendientesS.length > 0) {
      var filaAlertaS = filaTotalesResumenS + 3;

      pendientesS.sort(function (a, b) {
        if (a.bandaMin !== b.bandaMin) return a.bandaMin - b.bandaMin;
        var aPlan = a.plan > 0, bPlan = b.plan > 0;
        if (aPlan !== bPlan) return aPlan ? -1 : 1;
        if (a.fechaObj !== b.fechaObj) return a.fechaObj - b.fechaObj;
        if (a.prioMin !== b.prioMin) return a.prioMin - b.prioMin;
        if (b.pendiente !== a.pendiente) return b.pendiente - a.pendiente;
        if (b.meta !== a.meta) return b.meta - a.meta;
        return a.modelo.localeCompare(b.modelo);
      });

      var cabAS = hojaS.getRange(filaAlertaS, 3, 1, 4);
      cabAS.setValues([["🚨 ALERTA: MODELOS CON PRODUCCIÓN PENDIENTE TRAS SEMANA " + (ws + 1) + " 🚨", "", "", ""]]);
      cabAS.mergeAcross();
      cabAS.setBackground("#cc0000").setFontColor("#FFFFFF").setFontWeight("bold")
        .setHorizontalAlignment("center").setVerticalAlignment("middle")
        .setBorder(true, true, true, true, null, null, "black", SpreadsheetApp.BorderStyle.SOLID_MEDIUM);

      hojaS.getRange(filaAlertaS + 1, 3, 1, 4)
        .setValues([["Modelo", "Prioridad", "Fecha Objetivo", "Cant. Pendiente"]])
        .setBackground("#ea9999").setFontColor("#000000").setFontWeight("bold")
        .setHorizontalAlignment("center").setVerticalAlignment("middle")
        .setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.SOLID);

      var sheetIdPendS = hojaPendiente ? hojaPendiente.getSheetId() : null;
      var richAlertaS = [];
      var totalFaltanteS = 0;
      pendientesS.forEach(function (x) {
        totalFaltanteS += x.pendiente;
        var filaVals = [x.modelo, jerarquiaInversa[x.prioMin] || "Sin Asignar", formatoFecha_(cfg, x.fechaObj), x.pendiente];
        var filaRich = filaVals.map(function (vv, jj) {
          var b = SpreadsheetApp.newRichTextValue().setText(String(vv));
          if (jj === 0 && sheetIdPendS !== null) b.setLinkUrl("#gid=" + sheetIdPendS);
          return b.build();
        });
        richAlertaS.push(filaRich);
      });

      var rAlS = hojaS.getRange(filaAlertaS + 2, 3, richAlertaS.length, 4);
      rAlS.setRichTextValues(richAlertaS)
        .setHorizontalAlignment("center").setVerticalAlignment("middle")
        .setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.SOLID);
      hojaS.getRange(filaAlertaS + 2, 6, richAlertaS.length, 1)
        .setBackground("#fce5cd").setFontColor("#cc0000").setFontWeight("bold");

      var filaTotAlS = filaAlertaS + 2 + richAlertaS.length;
      var rTotAlS = hojaS.getRange(filaTotAlS, 3, 1, 4);
      rTotAlS.setValues([["TOTAL PIEZAS PENDIENTES TRAS SEMANA " + (ws + 1), "", "", totalFaltanteS]]);
      var txtTotS = hojaS.getRange(filaTotAlS, 3, 1, 3);
      txtTotS.mergeAcross();
      txtTotS.setHorizontalAlignment("right").setVerticalAlignment("middle");
      rTotAlS.setBackground("#ea9999").setFontColor("#000000").setFontWeight("bold")
        .setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.SOLID_MEDIUM);
      hojaS.getRange(filaTotAlS, 6).setBackground("#fce5cd").setFontColor("#cc0000")
        .setHorizontalAlignment("center").setFontWeight("bold");
    }
  }
}

function dibujarPendiente_(hojaPendiente, tareas, cfg) {
  if (!hojaPendiente) return;
  var maxFP = hojaPendiente.getMaxRows();
  if (maxFP > 2) {
    var limpP = hojaPendiente.getRange(3, 2, maxFP - 2, 5);
    try { limpP.clearContent(); } catch (e) {}
    try { limpP.setBorder(false, false, false, false, false, false); } catch (e) {}
    try { limpP.setBackground("#FFFFFF"); } catch (e) {}
  }
  hojaPendiente.getRange(2, 2, 1, 5)
    .setValues([["MO", "SKU", "Producto", "Cant. Pendiente Sem 1", "Programado Para"]])
    .setBackground("#434343").setFontColor("#FFFFFF").setFontWeight("bold")
    .setHorizontalAlignment("center").setVerticalAlignment("middle");

  var porSkuPend = {};
  tareas.forEach(function (t) {
    var faltSem1 = t.cantidad - t.planificadaSem1;
    if (faltSem1 <= 0) return;
    var destino;
    if (t.restante <= 0) {
      destino = "Semana " + (Math.floor(t.ultimoDia / DIAS_LABORALES) + 1) + " (" + formatoFecha_(cfg, fechaDeDia_(cfg, t.ultimoDia).getTime()) + ")";
    } else if (t.planificada > 0) {
      destino = "⛔ Fuera de horizonte (quedan " + t.restante + ")";
    } else {
      destino = "⛔ Sin capacidad / sin línea válida";
    }
    var key = t.sku + "||" + (t.esEspecial ? "E" : "R");
    if (!porSkuPend[key]) {
      porSkuPend[key] = {
        mo: t.mo === "" ? "--" : t.mo, sku: t.sku, producto: t.detalle,
        faltante: 0, destino: destino, fechaObj: t.fechaKey, prio: t.prioridadNum
      };
    }
    porSkuPend[key].faltante += faltSem1;
    if (t.fechaKey < porSkuPend[key].fechaObj) porSkuPend[key].fechaObj = t.fechaKey;
    if (t.prioridadNum < porSkuPend[key].prio) porSkuPend[key].prio = t.prioridadNum;
    porSkuPend[key].destino = destino;
  });

  var detPend = Object.keys(porSkuPend).map(function (k) { return porSkuPend[k]; });
  detPend.sort(function (a, b) {
    if (a.fechaObj !== b.fechaObj) return a.fechaObj - b.fechaObj;
    if (a.prio !== b.prio) return a.prio - b.prio;
    if (b.faltante !== a.faltante) return b.faltante - a.faltante;
    return a.sku.localeCompare(b.sku);
  });

  if (detPend.length > 0) {
    var matPend = detPend.map(function (p) {
      return [p.mo, p.sku, p.producto, p.faltante, p.destino];
    });
    var rPend = hojaPendiente.getRange(3, 2, matPend.length, 5);
    rPend.setValues(matPend)
      .setHorizontalAlignment("center").setVerticalAlignment("middle")
      .setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.SOLID);
    hojaPendiente.getRange(3, 2, matPend.length, 1).setNumberFormat("@");
    hojaPendiente.getRange(3, 5, matPend.length, 1).setBackground("#fce5cd").setFontColor("#cc0000").setFontWeight("bold");
  }
}

function valoresAcumuladosSemanas_(porSemana, nSemanas, meta) {
  var acum = 0;
  var previo = 0;
  var metaNum = Number(meta) || 0;
  var metaAlcanzada = false;
  var out = [];
  for (var w = 0; w < nSemanas; w++) {
    acum += (porSemana[w] || 0);
    if (metaAlcanzada || acum === 0 || acum === previo) {
      out.push("--");
    } else {
      out.push(acum);
      previo = acum;
      if (metaNum > 0 && acum >= metaNum) metaAlcanzada = true;
    }
  }
  return out;
}

function letraColumna_(col) {
  var s = "";
  var n = Number(col) || 0;
  while (n > 0) {
    var m = (n - 1) % 26;
    s = String.fromCharCode(65 + m) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function colorEstadoProy_(txt) {
  var t = String(txt || "");
  if (t.indexOf("RETRASADO") >= 0) {
    return { bg: "#F4CCCC", fg: "#990000", bold: true };
  }
  if (t.indexOf("A TIEMPO") >= 0) {
    return { bg: COLOR_META_PROY, fg: COLOR_META_TEXTO_PROY, bold: true };
  }
  if (t.indexOf("SIN FECHA") >= 0 || t.indexOf("Sin fecha") >= 0) {
    return { bg: "#FFF2CC", fg: "#BF9000", bold: false };
  }
  return { bg: "#FFFFFF", fg: "#000000", bold: false };
}

function umbralesSemana_(acumArr, minima, meta, nCols, idxSem, nSemanas) {
  var fondos = [], fuentes = [], negrita = [];
  var i;
  for (i = 0; i < nCols; i++) {
    fondos.push("#FFFFFF");
    fuentes.push("#000000");
  }
  var minHecho = false, metaHecho = false;
  var celdasAmarillas = [], celdasVerdes = [];
  for (var w = 0; w < nSemanas; w++) {
    var v = acumArr[w];
    if (v === "--" || v === "" || v === null || v === undefined) continue;
    var n = Number(v);
    if (!isFinite(n) || n <= 0) continue;
    var idx = idxSem + w;
    if (!metaHecho && meta > 0 && n >= meta) {
      fondos[idx] = COLOR_META_PROY;
      fuentes[idx] = COLOR_META_TEXTO_PROY;
      celdasVerdes.push(idx);
      negrita.push(idx);
      metaHecho = true;
      minHecho = true;
    } else if (!minHecho && minima > 0 && n >= minima) {
      fondos[idx] = COLOR_MINIMA_PROY;
      fuentes[idx] = "#000000";
      celdasAmarillas.push(idx);
      negrita.push(idx);
      minHecho = true;
    }
  }
  return { fondos: fondos, fuentes: fuentes, amarillas: celdasAmarillas, verdes: celdasVerdes, negrita: negrita };
}

function aplicarColorEstadoFila_(est, idxEstado, estado) {
  var estE = colorEstadoProy_(estado);
  est.fondos[idxEstado] = estE.bg;
  est.fuentes[idxEstado] = estE.fg;
  if (estE.bold) est.negrita.push(idxEstado);
  return est;
}

function aplicarNegritaUmbrales_(hoja, filaIni, colIni, filasEstilos) {
  var refs = [];
  for (var i = 0; i < filasEstilos.length; i++) {
    var lista = (filasEstilos[i] && filasEstilos[i].negrita) || [];
    for (var k = 0; k < lista.length; k++) {
      refs.push(letraColumna_(colIni + lista[k]) + (filaIni + i));
    }
  }
  if (refs.length === 0) return;
  try { hoja.getRangeList(refs).setFontWeight("bold"); } catch (e) {}
}

function aplicarBordesFilasProy_(hoja, filaIni, nFilas, colIni, nCols) {
  if (nFilas <= 0) return;
  for (var i = 0; i < nFilas; i++) {
    var row = hoja.getRange(filaIni + i, colIni, 1, nCols);
    row.setBorder(null, null, null, null, true, false, COLOR_BORDE_INTERNO, SpreadsheetApp.BorderStyle.SOLID);
    row.setBorder(true, true, true, true, null, null, "black", SpreadsheetApp.BorderStyle.SOLID);
  }
}

function estiloEncabezadoProy_(hoja, fila, colIni, nCols) {
  var header = hoja.getRange(fila, colIni, 1, nCols);
  header.setBackground(COLOR_HEADER_PROY)
    .setFontColor("#FFFFFF")
    .setFontWeight("bold")
    .setFontFamily("Arial")
    .setFontSize(10)
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle")
    .setWrap(true)
    .setBorder(null, null, null, null, true, false, COLOR_BORDE_INTERNO, SpreadsheetApp.BorderStyle.SOLID)
    .setBorder(true, true, true, true, null, null, "black", SpreadsheetApp.BorderStyle.SOLID);
  try { hoja.setFrozenRows(fila); } catch (e) {}
  try { hoja.setRowHeight(fila, 32); } catch (e2) {}
}

function limpiarHojaProy_(hoja, nColsMin) {
  var maxF = hoja.getMaxRows();
  var maxC = Math.max(nColsMin || 12, hoja.getMaxColumns());
  if (maxF > 0) {
    try { hoja.getRange(1, 1, maxF, maxC).clear(); } catch (e) {}
  }
}

function estadoProyeccion_(restante, fechaObj, fechaFinMs) {
  if (restante > 0) {
    if (isFinite(fechaObj)) {
      return fechaFinMs <= fechaObj ? "✅ FUERA DE HORIZONTE (PERO A TIEMPO)" : "🚨 FUERA DE HORIZONTE Y RETRASADO";
    }
    return "⚠️ FUERA DE HORIZONTE";
  }
  if (isFinite(fechaObj)) {
    return fechaFinMs <= fechaObj ? "✅ A TIEMPO" : "🚨 RETRASADO";
  }
  return "— Sin fecha objetivo";
}

function escribirTablaProyeccion_(hoja, cab, filas, fondos, fuentes, estilos, colIni, filaEnc) {
  var filaDatos = filaEnc + 1;
  hoja.getRange(filaEnc, colIni, 1, cab.length).setValues([cab]);
  estiloEncabezadoProy_(hoja, filaEnc, colIni, cab.length);
  try { hoja.setColumnWidth(1, 24); } catch (e0) {}
  if (filas.length === 0) return filaDatos;
  var rango = hoja.getRange(filaDatos, colIni, filas.length, cab.length);
  rango.setValues(filas)
    .setBackgrounds(fondos)
    .setFontColors(fuentes)
    .setFontFamily("Arial")
    .setFontSize(10)
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle")
    .setWrap(false);
  aplicarBordesFilasProy_(hoja, filaDatos, filas.length, colIni, cab.length);
  aplicarNegritaUmbrales_(hoja, filaDatos, colIni, estilos);
  try { hoja.setRowHeights(filaDatos, Math.min(filas.length, 400), 24); } catch (e) {}
  try { hoja.autoResizeColumns(colIni, cab.length); } catch (e2) {}
  return filaDatos;
}

function aplicarEnlacesModeloProy_(ss, hoja, filaDatos, filas, primeraFilaSku, gidSku, colIni) {
  var base = ss.getUrl();
  for (var r = 0; r < filas.length; r++) {
    var modelo = String(filas[r][0] || "");
    if (!modelo) continue;
    var destino = primeraFilaSku[modelo] || filaDatos;
    var url = base + "#gid=" + gidSku + "&range=B" + destino;
    try {
      var rich = SpreadsheetApp.newRichTextValue().setText(modelo).setLinkUrl(url).build();
      hoja.getRange(filaDatos + r, colIni).setRichTextValue(rich).setFontWeight("bold");
    } catch (eLink) {}
  }
}

function dibujarProyecciones_(ss, cfg, infoModelo, infoSku) {
  var COL_INI = 2;
  var FILA_ENC = 2;
  var filaDatos = FILA_ENC + 1;

  var hojaProy = ss.getSheetByName("Proyeccion") || ss.insertSheet("Proyeccion");
  var hojaProySkus = ss.getSheetByName("Proyeccion - SKUS") || ss.insertSheet("Proyeccion - SKUS");
  limpiarHojaProy_(hojaProy, 12);
  limpiarHojaProy_(hojaProySkus, 20);

  var cabProy = ["Modelo", "Fecha Objetivo", "Meta (Faltante)"];
  var cabProySku = ["SKU", "Modelo", "Detalle del Producto", "Fecha Objetivo", "Meta (Faltante)"];
  for (var w2 = 0; w2 < cfg.semanas; w2++) {
    var etq = "Acum Sem " + (w2 + 1) + " (" + Utilities.formatDate(fechaDeDia_(cfg, w2 * DIAS_LABORALES), cfg.tz, "dd/MM") + ")";
    cabProy.push(etq);
    cabProySku.push(etq);
  }
  cabProy.push("Sin Programar", "Fecha Estim. Término", "Estado");
  cabProySku.push("Sin Programar", "Fecha Estim. Término", "Estado", "Genero", "Color", "Talla", "Linea", "Cap Produccion por Dia", "Tipo");
  var idxSemProy = 3;
  var idxSemSku = 5;
  var idxEstadoProy = 3 + cfg.semanas + 2;
  var idxEstadoSku = 5 + cfg.semanas + 2;

  var modelosOrdenados = Object.keys(infoModelo).sort(function (a, b) {
    var ia = infoModelo[a], ib = infoModelo[b];
    var ba = (ia.bandaMin !== undefined) ? ia.bandaMin : 9;
    var bb = (ib.bandaMin !== undefined) ? ib.bandaMin : 9;
    if (ba !== bb) return ba - bb;
    var aPlan = (ia.porSemana[0] || 0) > 0, bPlan = (ib.porSemana[0] || 0) > 0;
    if (aPlan !== bPlan) return aPlan ? -1 : 1;
    if (ia.fechaObj !== ib.fechaObj) return ia.fechaObj - ib.fechaObj;
    if (ia.prioMin !== ib.prioMin) return ia.prioMin - ib.prioMin;
    if (ib.solicitada !== ia.solicitada) return ib.solicitada - ia.solicitada;
    if (ib.restante !== ia.restante) return ib.restante - ia.restante;
    return a.localeCompare(b);
  });

  var idxModelo = {};
  for (var imo = 0; imo < modelosOrdenados.length; imo++) idxModelo[modelosOrdenados[imo]] = imo;

  var skusOrdenados = Object.keys(infoSku).sort(function (a, b) {
    var ia = infoSku[a], ib = infoSku[b];
    var ma = idxModelo.hasOwnProperty(ia.modelo) ? idxModelo[ia.modelo] : 9999;
    var mb = idxModelo.hasOwnProperty(ib.modelo) ? idxModelo[ib.modelo] : 9999;
    if (ma !== mb) return ma - mb;
    var pa = ia.esSkuPrio ? 0 : 1, pb = ib.esSkuPrio ? 0 : 1;
    if (pa !== pb) return pa - pb;
    if (ia.esSkuPrio && ib.esSkuPrio) {
      var oa = ia.skuPrioOrden !== undefined ? ia.skuPrioOrden : 0;
      var ob = ib.skuPrioOrden !== undefined ? ib.skuPrioOrden : 0;
      if (oa !== ob) return oa - ob;
    }
    var aPlan = (ia.porSemana[0] || 0) > 0, bPlan = (ib.porSemana[0] || 0) > 0;
    if (aPlan !== bPlan) return aPlan ? -1 : 1;
    if (ia.fechaObj !== ib.fechaObj) return ia.fechaObj - ib.fechaObj;
    if (ia.prioMin !== ib.prioMin) return ia.prioMin - ib.prioMin;
    var ra = rangoColor_(ia.color), rb = rangoColor_(ib.color);
    if (ra !== rb) return ra - rb;
    if (ib.solicitada !== ia.solicitada) return ib.solicitada - ia.solicitada;
    if (ib.restante !== ia.restante) return ib.restante - ia.restante;
    return String(ia.sku).localeCompare(String(ib.sku));
  });

  var filasProySku = [];
  var fondosSku = [];
  var fuentesSku = [];
  var estilosSku = [];
  var primeraFilaSku = {};

  for (var miS = 0; miS < skusOrdenados.length; miS++) {
    var claveSku = skusOrdenados[miS];
    var isku = infoSku[claveSku];
    var fechaFinMsSku = Infinity;
    if (isku.diaFinEstimado >= 0) {
      fechaFinMsSku = fechaDeDia_(cfg, isku.diaFinEstimado).getTime();
    }
    var estadoSku = estadoProyeccion_(isku.restante, isku.fechaObj, fechaFinMsSku);
    var filaS = [isku.sku, isku.modelo, isku.detalle, formatoFecha_(cfg, isku.fechaObj), isku.solicitada];
    var acumSku = valoresAcumuladosSemanas_(isku.porSemana, cfg.semanas, isku.solicitada);
    for (var w3S = 0; w3S < cfg.semanas; w3S++) filaS.push(acumSku[w3S]);
    filaS.push(isku.restante === 0 ? "--" : isku.restante);
    filaS.push(isFinite(fechaFinMsSku) ? formatoFecha_(cfg, fechaFinMsSku) : "--");
    filaS.push(estadoSku);
    filaS.push(isku.genero || "");
    filaS.push(isku.color || "");
    filaS.push(isku.talla || "");
    filaS.push(isku.lineaAsignada ? String(isku.lineaAsignada) : formatearLineas_(isku.lineas || []));
    filaS.push(isku.cap || "");
    filaS.push(isku.esEspecial ? "Especial" : "Producción");
    filasProySku.push(filaS);

    var estSku = umbralesSemana_(acumSku, isku.minima || 0, isku.solicitada, cabProySku.length, idxSemSku, cfg.semanas);
    aplicarColorEstadoFila_(estSku, idxEstadoSku, estadoSku);
    fondosSku.push(estSku.fondos);
    fuentesSku.push(estSku.fuentes);
    estilosSku.push(estSku);

    if (!primeraFilaSku[isku.modelo]) primeraFilaSku[isku.modelo] = filaDatos + miS;
  }

  escribirTablaProyeccion_(hojaProySkus, cabProySku, filasProySku, fondosSku, fuentesSku, estilosSku, COL_INI, FILA_ENC);
  if (filasProySku.length > 0) {
    try { hojaProySkus.getRange(filaDatos, COL_INI, filasProySku.length, 1).setNumberFormat("@"); } catch (eFmt) {}
  }

  var filasProy = [];
  var fondosProy = [];
  var fuentesProy = [];
  var estilosProy = [];

  for (var mi2 = 0; mi2 < modelosOrdenados.length; mi2++) {
    var nomMod = modelosOrdenados[mi2];
    var im3 = infoModelo[nomMod];
    var fechaFinMs = Infinity;
    if (im3.diaFinEstimado >= 0) {
      fechaFinMs = fechaDeDia_(cfg, im3.diaFinEstimado).getTime();
    }
    var estado = estadoProyeccion_(im3.restante, im3.fechaObj, fechaFinMs);
    var fila = [nomMod, formatoFecha_(cfg, im3.fechaObj), im3.solicitada];
    var acumMod = valoresAcumuladosSemanas_(im3.porSemana, cfg.semanas, im3.solicitada);
    for (var w3 = 0; w3 < cfg.semanas; w3++) fila.push(acumMod[w3]);
    fila.push(im3.restante === 0 ? "--" : im3.restante);
    fila.push(isFinite(fechaFinMs) ? formatoFecha_(cfg, fechaFinMs) : "--");
    fila.push(estado);
    filasProy.push(fila);

    var estMod = umbralesSemana_(acumMod, im3.minima || 0, im3.solicitada, cabProy.length, idxSemProy, cfg.semanas);
    aplicarColorEstadoFila_(estMod, idxEstadoProy, estado);
    fondosProy.push(estMod.fondos);
    fuentesProy.push(estMod.fuentes);
    estilosProy.push(estMod);
  }

  escribirTablaProyeccion_(hojaProy, cabProy, filasProy, fondosProy, fuentesProy, estilosProy, COL_INI, FILA_ENC);
  aplicarEnlacesModeloProy_(ss, hojaProy, filaDatos, filasProy, primeraFilaSku, hojaProySkus.getSheetId(), COL_INI);
}


function addBusinessDays_(dateMs, days) {
  if (!isFinite(dateMs)) return Infinity;
  var d = new Date(dateMs);
  var added = 0;
  while (added < days) {
    d.setDate(d.getDate() + 1);
    var dow = d.getDay();
    if (dow !== 0 && dow !== 6) added++;
  }
  return d;
}

function dibujarAlmacen_(ss, cfg, tareas, infoModelo, totalDias) {
  ss.toast("Generando proyecciones de Almacén...", "⚙️ Planificando", 5);

  var hojaAlmacenModelo = ss.getSheetByName("Entrada de Almacen Modelo");
  if (!hojaAlmacenModelo) hojaAlmacenModelo = ss.insertSheet("Entrada de Almacen Modelo");
  var hojaAlmacenSku = ss.getSheetByName("Entrada de Almacen - Skus");
  if (!hojaAlmacenSku) hojaAlmacenSku = ss.insertSheet("Entrada de Almacen - Skus");

  var viejosModelo = {};
  if (hojaAlmacenModelo.getLastRow() >= 3) {
    var maxF_M = hojaAlmacenModelo.getLastRow() - 2;
    var dMod = hojaAlmacenModelo.getRange(3, 2, maxF_M, 7).getValues();
    var fMod = hojaAlmacenModelo.getRange(3, 2, maxF_M, 7).getFormulas();
    dMod.forEach(function (r, i) {
      var k = norm_(r[1]);
      if (k !== "") {
        viejosModelo[k] = {
          rec: fMod[i][5] ? fMod[i][5] : r[5],
          fal: fMod[i][6] ? fMod[i][6] : r[6]
        };
      }
    });
  }

  var viejosSku = {};
  if (hojaAlmacenSku.getLastRow() >= 3) {
    var maxF_S = hojaAlmacenSku.getLastRow() - 2;
    var dSku = hojaAlmacenSku.getRange(3, 2, maxF_S, 8).getValues();
    var fSku = hojaAlmacenSku.getRange(3, 2, maxF_S, 8).getFormulas();
    dSku.forEach(function (r, i) {
      var k = norm_(r[0]) + "_" + norm_(r[1]);
      if (k !== "_") {
        viejosSku[k] = {
          rec: fSku[i][6] ? fSku[i][6] : r[6],
          fal: fSku[i][7] ? fSku[i][7] : r[7]
        };
      }
    });
  }

  var agrupadoSku = {};
  tareas.forEach(function (t) {
    var moClave = t.mo === "" ? "--" : t.mo;
    var key = moClave + "_" + t.sku + "_" + (t.esEspecial ? "E" : "R");
    if (!agrupadoSku[key]) {
      agrupadoSku[key] = {
        mo: moClave, sku: t.sku, producto: t.detalleAlmacen,
        cantidad: t.solicitadaOrig !== undefined ? t.solicitadaOrig : t.cantidadOriginal,
        diaFin: -1, prioMin: t.prioridadNum,
        esSkuPrio: !!t.esSkuPrio, skuPrioOrden: t.skuPrioOrden !== undefined ? t.skuPrioOrden : 9999
      };
    }
    if (t.prioridadNum < agrupadoSku[key].prioMin) agrupadoSku[key].prioMin = t.prioridadNum;
    if (t.esSkuPrio) agrupadoSku[key].esSkuPrio = true;
    var dFin = t.ultimoDia;
    if (t.restante > 0 && t.cap > 0) dFin = (totalDias - 1) + Math.ceil(t.restante / t.cap);
    if (dFin > agrupadoSku[key].diaFin) agrupadoSku[key].diaFin = dFin;
  });

  var listAlmacenModelo = [];
  for (var mod in infoModelo) {
    var im = infoModelo[mod];
    if (im.solicitada <= 0) continue;
    listAlmacenModelo.push({ mod: mod, im: im, diaFin: im.diaFinEstimado, prio: im.prioMin });
  }

  listAlmacenModelo.sort(function (a, b) {
    if (a.diaFin !== b.diaFin) return a.diaFin - b.diaFin;
    if (a.prio !== b.prio) return a.prio - b.prio;
    return a.mod.localeCompare(b.mod);
  });

  var arrModelo = [];
  var richTextModelo = [];
  var sheetIdSkus = hojaAlmacenSku.getSheetId();

  listAlmacenModelo.forEach(function (item) {
    var imA = item.im;
    var msSalida = imA.diaFinEstimado >= 0 ? fechaDeDia_(cfg, imA.diaFinEstimado).getTime() : Infinity;
    var msEntrada = addBusinessDays_(msSalida, 2);
    var v = viejosModelo[norm_(item.mod)] || { rec: "", fal: "" };

    arrModelo.push([
      imA.mos.size, item.mod, imA.solicitada,
      isFinite(msSalida) ? formatoFecha_(cfg, msSalida) : "--",
      (msEntrada !== Infinity && isFinite(msEntrada.getTime())) ? formatoFecha_(cfg, msEntrada.getTime()) : "--",
      v.rec, v.fal
    ]);

    richTextModelo.push([
      SpreadsheetApp.newRichTextValue()
        .setText(String(imA.mos.size))
        .setLinkUrl("#gid=" + sheetIdSkus)
        .build()
    ]);
  });

  var listAlmacenSku = [];
  for (var kA in agrupadoSku) {
    if (agrupadoSku[kA].cantidad > 0) listAlmacenSku.push(agrupadoSku[kA]);
  }

  listAlmacenSku.sort(function (a, b) {
    if (a.diaFin !== b.diaFin) return a.diaFin - b.diaFin;
    var pa = a.esSkuPrio ? 0 : 1, pb = b.esSkuPrio ? 0 : 1;
    if (pa !== pb) return pa - pb;
    if (a.skuPrioOrden !== b.skuPrioOrden) return a.skuPrioOrden - b.skuPrioOrden;
    if (a.prioMin !== b.prioMin) return a.prioMin - b.prioMin;
    return a.sku.localeCompare(b.sku);
  });

  var arrSku = [];
  listAlmacenSku.forEach(function (tG) {
    var msSalida = tG.diaFin >= 0 ? fechaDeDia_(cfg, tG.diaFin).getTime() : Infinity;
    var msEntrada = addBusinessDays_(msSalida, 2);
    var v = viejosSku[norm_(tG.mo) + "_" + norm_(tG.sku)] || { rec: "", fal: "" };

    arrSku.push([
      tG.mo, tG.sku, tG.producto, tG.cantidad,
      isFinite(msSalida) ? formatoFecha_(cfg, msSalida) : "--",
      (msEntrada !== Infinity && isFinite(msEntrada.getTime())) ? formatoFecha_(cfg, msEntrada.getTime()) : "--",
      v.rec, v.fal
    ]);
  });

  var mRows = hojaAlmacenModelo.getMaxRows();
  if (mRows > 2) {
    hojaAlmacenModelo.getRange(3, 2, mRows - 2, 7).clearContent().setBorder(false, false, false, false, false, false);
  }
  if (arrModelo.length > 0) {
    hojaAlmacenModelo.getRange(3, 2, arrModelo.length, 7).setValues(arrModelo)
      .setHorizontalAlignment("center").setVerticalAlignment("middle")
      .setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.SOLID);
    hojaAlmacenModelo.getRange(3, 2, richTextModelo.length, 1).setRichTextValues(richTextModelo);
  }

  var sRows = hojaAlmacenSku.getMaxRows();
  if (sRows > 2) {
    hojaAlmacenSku.getRange(3, 2, sRows - 2, 8).clearContent().setBorder(false, false, false, false, false, false);
  }
  if (arrSku.length > 0) {
    hojaAlmacenSku.getRange(3, 2, arrSku.length, 8).setValues(arrSku)
      .setHorizontalAlignment("center").setVerticalAlignment("middle")
      .setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.SOLID);
    hojaAlmacenSku.getRange(3, 2, arrSku.length, 1).setNumberFormat("@");
    hojaAlmacenSku.getRange(3, 3, arrSku.length, 1).setNumberFormat("@");
  }
}


function asegurarHojaPriorizacionSkus_(ss) {
  var hoja = hojaPorNombreFlex_(ss, NOMBRES_PRIO_SKU);
  if (!hoja) {
    hoja = ss.insertSheet("Priorizacion - SKUs");
  }
  var cab = hoja.getRange("B2:I2").getValues()[0];
  var cabOk = normUp_(cab[0]) === "SKU" && quitarTildes_(normLow_(cab[5] || "")).indexOf("minima") !== -1;
  if (!cabOk) {
    hoja.getRange("B2:I2").setValues([["SKU", "Producto", "Genero", "Color", "Talla", "Cantidad Minima", "Fecha de Salida Estimada", "Lineas"]]);
    hoja.getRange("B2:I2").setBackground("#3d85c6").setFontColor("#FFFFFF")
      .setFontWeight("bold").setHorizontalAlignment("center").setVerticalAlignment("middle");
  }
  var maxPre = 200;
  if (!hoja.getRange(3, 9).getFormula()) {
    var formulas = [];
    for (var r = 3; r <= maxPre; r++) {
      formulas.push(["=IFERROR(VLOOKUP(B" + r + ",'Por Hacer'!$F$2:$S$2000,6,FALSE),\"\")"]);
    }
    hoja.getRange(3, 9, formulas.length, 1).setFormulas(formulas);
  }
  hoja.getRange("B3:B" + maxPre).setNumberFormat("@");
  hoja.getRange("G3:G" + maxPre).setNumberFormat("0");
  hoja.getRange("H3:H" + maxPre).setNumberFormat("dd/mm/yyyy");
  hoja.setFrozenRows(2);
  return hoja;
}

// =====================================================================
//  GESTOR DE PRIORIZACIÓN: actualizarModelosPriorizacion()
// =====================================================================
function actualizarModelosPriorizacion() {
  conLock_(actualizarModelosPriorizacion_);
}

function actualizarModelosPriorizacion_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var hojaPorHacer = ss.getSheetByName("Por Hacer");
  var hojaEspecial = ss.getSheetByName("Por Hacer - Especial");
  var hojaPrio = ss.getSheetByName("Priorizacion");

  if (!hojaPorHacer || !hojaPrio) {
    SpreadsheetApp.getUi().alert("Faltan las hojas 'Por Hacer' o 'Priorizacion'.");
    return;
  }

  var modelosUnicos = new Set();
  var quitadosCero = 0;

  function procesarModelos(datos, tipo) {
    if (!datos || datos.length < 3) return;
    var headers = datos[1];
    var iProd = idxPorFragmento_(headers, ["modelo", "producto"]);
    var iGen = idxPorFragmento_(headers, ["genero", "género"]);
    var iCant = idxPorFragmento_(headers, ["cantidad solicitada"]);
    var iFalt = idxPorFragmento_(headers, ["faltante"]);
    var iProdQty = idxPorFragmento_(headers, ["producida"]);
    if (iProd === -1) return;

    var tot = {};
    for (var i = 2; i < datos.length; i++) {
      var prod = norm_(datos[i][iProd]);
      if (prod === "") continue;
      var gen = iGen !== -1 ? norm_(datos[i][iGen]) : "";
      var nombreCompleto = prod + (gen !== "" && gen !== "--" ? " " + gen : "");
      var falt = faltanteDeFila_(datos[i], iCant, iFalt, iProdQty);
      tot[nombreCompleto] = (tot[nombreCompleto] || 0) + falt;
    }
    Object.keys(tot).forEach(function (nombreCompleto) {
      if (tot[nombreCompleto] > 0) modelosUnicos.add(nombreCompleto + "||" + tipo);
      else quitadosCero++;
    });
  }

  procesarModelos(hojaPorHacer.getDataRange().getValues(), "Producción");
  if (hojaEspecial) procesarModelos(hojaEspecial.getDataRange().getValues(), "Especial");

  var ultPrio = hojaPrio.getLastRow();

  if (ultPrio < 2 || normUp_(hojaPrio.getRange("C2").getValue()) !== "TIPO") {
    hojaPrio.getRange("B2:G2").setValues([["Modelo", "Tipo", "Prioridad", "Fecha de Salida Estimada", "Cantidad Minima", "Lineas"]]);
    hojaPrio.getRange("B2:G2").setBackground("#434343").setFontColor("#FFFFFF")
      .setFontWeight("bold").setHorizontalAlignment("center");
    ultPrio = 2;
  }

  var conservados = [];
  var existentes = new Set();
  var huerfanos = 0;

  if (ultPrio >= 3) {
    var colCount = Math.max(6, hojaPrio.getLastColumn() - 1);
    var datosP = hojaPrio.getRange(3, 2, ultPrio - 2, colCount).getValues();
    for (var j = 0; j < datosP.length; j++) {
      var modP = norm_(datosP[j][0]);
      var tipoP = norm_(datosP[j][1]) || "Producción";
      if (modP === "") continue;

      var clave = modP + "||" + tipoP;
      if (modelosUnicos.has(clave)) {
        conservados.push([
          modP, tipoP,
          datosP[j][2] !== undefined ? datosP[j][2] : "",
          datosP[j][3] !== undefined ? datosP[j][3] : "",
          datosP[j][4] !== undefined ? datosP[j][4] : "",
          datosP[j][5] !== undefined ? datosP[j][5] : ""
        ]);
        existentes.add(clave);
      } else {
        huerfanos++;
      }
    }
  }

  var nuevos = 0;
  modelosUnicos.forEach(function (clave) {
    if (!existentes.has(clave)) {
      var partes = clave.split("||");
      conservados.push([partes[0], partes[1], "", "", "", ""]);
      nuevos++;
    }
  });

  if (ultPrio >= 3) hojaPrio.getRange(3, 2, ultPrio - 2, Math.max(6, hojaPrio.getLastColumn() - 1)).clearContent();
  if (conservados.length > 0) {
    var rDest = hojaPrio.getRange(3, 2, conservados.length, 6);
    rDest.setValues(conservados)
      .setHorizontalAlignment("center").setVerticalAlignment("middle")
      .setBorder(true, true, true, true, false, false, "black", SpreadsheetApp.BorderStyle.SOLID);
    hojaPrio.getRange(3, 5, conservados.length, 1).setNumberFormat("dd/mm/yyyy");
    hojaPrio.getRange(3, 6, conservados.length, 1).setNumberFormat("0");
    hojaPrio.getRange(3, 7, conservados.length, 1).setNumberFormat("@");
  }

  asegurarHojaPriorizacionSkus_(ss);

  var msg = "";
  if (huerfanos > 0) msg += "🗑️ LIMPIEZA:\nSe eliminaron " + huerfanos + " modelos huérfanos.\n\n";
  if (quitadosCero > 0) msg += "📦 FALTANTE 0:\nSe quitaron " + quitadosCero + " modelos ya cubiertos (faltante total 0).\n\n";
  msg += nuevos > 0
    ? "➕ ACTUALIZACIÓN:\nSe agregaron " + nuevos + " modelos nuevos.\nAsigna Prioridad, Fecha, Cantidad Mínima y Líneas."
    : "✅ ACTUALIZACIÓN:\nTu lista de priorización está al día.";
  msg += "\n\nLa hoja 'Priorizacion - SKUs' está lista: ingresa SKU y Cantidad Minima a mano (Líneas se calcula sola).";
  SpreadsheetApp.getUi().alert("RESUMEN DE PRIORIZACIÓN\n\n" + msg);
}

// =====================================================================
//  GESTOR DE ÓRDENES: actualizarMOs()
// =====================================================================
var CAMPOS_HISTORIAL = [
  "SKU", "Tipo", "Producto", "Genero", "Color", "Talla", "Linea de Produccion",
  "Cantidad Solicitada", "Cantida Producida", "Faltante", "Cap Produccion por Dia",
  "Prioridad", "Dia de inicio", "Dia no laborable", "Fecha de Salida Estimada", "MO", "MO STATUS",
  "Fecha de Archivo", "Origen"
];

function campoCanonico_(header) {
  var h = normLow_(header);
  if (h === "") return null;
  if (h === "sku") return "SKU";
  if (h === "tipo") return "Tipo";
  if (h.indexOf("producto") !== -1 || h.indexOf("modelo") !== -1) return "Producto";
  if (h.indexOf("genero") !== -1 || h.indexOf("género") !== -1) return "Genero";
  if (h.indexOf("color") !== -1) return "Color";
  if (h.indexOf("talla") !== -1) return "Talla";
  if (h.indexOf("linea") !== -1 || h.indexOf("línea") !== -1) return "Linea de Produccion";
  if (h.indexOf("cantidad solicitada") !== -1) return "Cantidad Solicitada";
  if (h.indexOf("producida") !== -1) return "Cantida Producida";
  if (h.indexOf("faltante") !== -1) return "Faltante";
  if (h.indexOf("cap produccion") !== -1 || h.indexOf("cap producción") !== -1 || h.indexOf("promedio") !== -1) return "Cap Produccion por Dia";
  if (h.indexOf("prioridad") !== -1) return "Prioridad";
  if (h.indexOf("dia de in") !== -1 || h.indexOf("día de in") !== -1) return "Dia de inicio";
  if (h.indexOf("dia no lab") !== -1 || h.indexOf("día no lab") !== -1 || h.indexOf("feriado") !== -1) return "Dia no laborable";
  if (h.indexOf("fecha de salida") !== -1 || h.indexOf("fecha salida") !== -1) return "Fecha de Salida Estimada";
  if (normUp_(header) === "MO") return "MO";
  if (h.indexOf("mo status") !== -1) return "MO STATUS";
  return null;
}

function actualizarMOs() {
  conLock_(actualizarMOs_);
}

function actualizarMOs_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var hojaPorHacer = ss.getSheetByName("Por Hacer");
  var hojaEspecial = ss.getSheetByName("Por Hacer - Especial");
  var hojaMO = ss.getSheetByName("MO");
  if (!hojaPorHacer || !hojaMO) {
    SpreadsheetApp.getUi().alert("Faltan las hojas principales 'Por Hacer' o 'MO'.");
    return;
  }

  var mensaje = "";
  ss.toast("Fase 1: detectando órdenes terminadas...", "🔄 Actualizando MOs", 5);

  var ultMO = hojaMO.getLastRow();
  var skusTerminados = {};
  var bloqueMO = [];

  if (ultMO >= 3) {
    bloqueMO = hojaMO.getRange(3, 3, ultMO - 2, 5).getValues();
    for (var m = 0; m < bloqueMO.length; m++) {
      var skuAct = norm_(bloqueMO[m][0]);
      var tipoAct = norm_(bloqueMO[m][1]);
      var statusOriginal = norm_(bloqueMO[m][4]);
      var st = statusOriginal.toLowerCase();
      if (skuAct !== "" && (st === "hecho" || st === "cancelada")) {
        skusTerminados[skuAct + "||" + tipoAct] = statusOriginal;
      }
    }
  }
  var cantTerminados = Object.keys(skusTerminados).length;

  function limpiarYRespaldar(hojaTrabajo, tipoAsignado) {
    if (!hojaTrabajo) return 0;
    var fT = hojaTrabajo.getLastRow();
    var cT = hojaTrabajo.getLastColumn();
    if (fT < 3) return 0;

    var datos = hojaTrabajo.getRange(1, 1, fT, cT).getValues();
    var headers = datos[1];
    var iSku = idxExacto_(headers, "SKU");
    if (iSku === -1) return 0;

    var mapaCampos = {};
    for (var h = 0; h < headers.length; h++) {
      var campo = campoCanonico_(headers[h]);
      if (campo !== null && mapaCampos[campo] === undefined) mapaCampos[campo] = h;
    }

    var filasABorrar = [];
    var filasHistorial = [];
    var fecha = new Date();

    for (var p = datos.length - 1; p >= 2; p--) {
      var skuFila = norm_(datos[p][iSku]);
      var clave = skuFila + "||" + tipoAsignado;
      if (!skusTerminados.hasOwnProperty(clave)) continue;
      filasABorrar.push(p + 1);

      var filaH = CAMPOS_HISTORIAL.map(function (campoH) {
        if (campoH === "MO STATUS") return skusTerminados[clave];
        if (campoH === "Fecha de Archivo") return fecha;
        if (campoH === "Origen") return hojaTrabajo.getName();
        if (campoH === "Tipo") return tipoAsignado;
        var idxOrig = mapaCampos[campoH];
        return idxOrig !== undefined ? datos[p][idxOrig] : "";
      });
      filasHistorial.push(filaH);
    }

    if (filasHistorial.length > 0) {
      var hojaHist = ss.getSheetByName("Historial MO");
      if (!hojaHist) {
        hojaHist = ss.insertSheet("Historial MO");
        hojaHist.hideSheet();
      }
      var cab1 = normUp_(hojaHist.getRange(1, 1).getValue());
      if (cab1 !== "SKU") {
        var filaCab = hojaHist.getLastRow() === 0 ? 1 : hojaHist.getLastRow() + 2;
        hojaHist.getRange(filaCab, 1, 1, CAMPOS_HISTORIAL.length).setValues([CAMPOS_HISTORIAL])
          .setBackground("#434343").setFontColor("#FFFFFF").setFontWeight("bold");
      }
      var ultH = hojaHist.getLastRow();
      hojaHist.getRange(ultH + 1, 1, filasHistorial.length, CAMPOS_HISTORIAL.length)
        .setValues(filasHistorial);
    }

    for (var e = 0; e < filasABorrar.length; e++) {
      hojaTrabajo.deleteRow(filasABorrar[e]);
    }
    return filasABorrar.length;
  }

  if (cantTerminados > 0) {
    var elimReg = limpiarYRespaldar(hojaPorHacer, "Producción");
    var elimEsp = limpiarYRespaldar(hojaEspecial, "Especial");
    mensaje += "✅ CULMINADOS/CANCELADOS:\nSe archivaron " + (elimReg + elimEsp) +
      " SKUs en 'Historial MO' (columnas alineadas por nombre).\n\n";
  }

  ss.toast("Fase 2: sincronizando hoja MO...", "🔄 Actualizando MOs", 5);
  var skusActivos = {};

  function extraerActivos(hoja, tipoAsignado) {
    if (!hoja) return;
    var uF = hoja.getLastRow(), uC = hoja.getLastColumn();
    if (uF < 3 || uC < 2) return;
    var d = hoja.getRange(1, 1, uF, uC).getValues();
    var hs = d[1];
    var iS = idxExacto_(hs, "SKU");
    var iC = idxPorFragmento_(hs, ["cantidad solicitada"]);
    if (iS === -1 || iC === -1) return;
    for (var i = 2; i < d.length; i++) {
      var s = norm_(d[i][iS]);
      var c = Number(d[i][iC]);
      if (s !== "" && c > 0) {
        var claveA = s + "||" + tipoAsignado;
        skusActivos[claveA] = (skusActivos[claveA] || 0) + c;
      }
    }
  }

  extraerActivos(hojaPorHacer, "Producción");
  extraerActivos(hojaEspecial, "Especial");

  if (Object.keys(skusActivos).length === 0) {
    if (ultMO >= 3) hojaMO.getRange(3, 3, ultMO - 2, 5).clearContent();
    SpreadsheetApp.getUi().alert((mensaje !== "" ? mensaje : "") + "Ya no hay tareas pendientes en ninguna lista.");
    return;
  }

  var filasMOFinal = [];
  var skusEnMO = new Set();
  var huerfanos = 0;

  for (var b = 0; b < bloqueMO.length; b++) {
    var skuB = norm_(bloqueMO[b][0]);
    var tipoB = norm_(bloqueMO[b][1]) || "Producción";
    if (skuB === "") continue;

    var claveB = skuB + "||" + tipoB;
    if (skusTerminados.hasOwnProperty(claveB)) continue;
    if (!skusActivos.hasOwnProperty(claveB)) { huerfanos++; continue; }

    filasMOFinal.push([skuB, tipoB, bloqueMO[b][2], bloqueMO[b][3], bloqueMO[b][4]]);
    skusEnMO.add(claveB);
  }

  var nuevas = 0;
  for (var claveActiva in skusActivos) {
    if (!skusEnMO.has(claveActiva)) {
      var partes = claveActiva.split("||");
      filasMOFinal.push([partes[0], partes[1], skusActivos[claveActiva], "", ""]);
      nuevas++;
    }
  }

  if (normUp_(hojaMO.getRange("C2").getValue()) !== "SKU" || normUp_(hojaMO.getRange("D2").getValue()) !== "TIPO") {
    hojaMO.getRange("C2:G2").setValues([["SKU", "Tipo", "Cantidad Solicitada", "MO", "MO STATUS"]])
      .setBackground("#434343").setFontColor("#FFFFFF").setFontWeight("bold")
      .setHorizontalAlignment("center");
  }

  if (ultMO >= 3) hojaMO.getRange(3, 3, ultMO - 2, 5).clearContent();
  if (filasMOFinal.length > 0) {
    var rMO = hojaMO.getRange(3, 3, filasMOFinal.length, 5);
    rMO.setValues(filasMOFinal)
      .setHorizontalAlignment("center").setVerticalAlignment("middle")
      .setBorder(true, true, true, true, false, false, "black", SpreadsheetApp.BorderStyle.SOLID);
    hojaMO.getRange(3, 3, filasMOFinal.length, 1).setNumberFormat("@");
    hojaMO.getRange(3, 6, filasMOFinal.length, 1).setNumberFormat("@");
  }

  if (huerfanos > 0) mensaje += "🗑️ SINCRONIZACIÓN:\nSe eliminaron " + huerfanos + " órdenes huérfanas de 'MO'.\n\n";
  if (nuevas > 0) mensaje += "➕ NUEVOS:\nSe agregaron " + nuevas + " SKUs nuevos a la cola de 'MO'.\n\n";
  if (cantTerminados === 0 && huerfanos === 0 && nuevas === 0) {
    mensaje += "✅ AL DÍA:\nTu hoja 'MO' ya está sincronizada con ambas listas.\n\n";
  }

  ss.toast("Fase 3: vinculando MO y estatus...", "🔄 Actualizando MOs", 5);
  var diccMO = {};
  filasMOFinal.forEach(function (f) {
    diccMO[norm_(f[0]) + "||" + norm_(f[1])] = { mo: norm_(f[3]), status: norm_(f[4]) };
  });

  function escribirValores(hoja, tipoAsignado) {
    if (!hoja) return;
    var uF = hoja.getLastRow();
    if (uF < 3) return;
    var hs = hoja.getRange(2, 1, 1, hoja.getLastColumn()).getValues()[0];
    var colSku = -1, colMo = -1, colMoStatus = -1;

    for (var h = 0; h < hs.length; h++) {
      var n = normUp_(hs[h]);
      if (n === "SKU") colSku = h + 1;
      if (n === "MO") colMo = h + 1;
      if (n === "MO STATUS") colMoStatus = h + 1;
    }

    if (colSku === -1 || colMo === -1 || colMoStatus === -1) return;

    var nF = uF - 2;
    var skus = hoja.getRange(3, colSku, nF, 1).getValues();
    var matMo = [];
    var matStatus = [];

    for (var i = 0; i < skus.length; i++) {
      var claveW = norm_(skus[i][0]) + "||" + tipoAsignado;
      if (diccMO[claveW]) {
        matMo.push([diccMO[claveW].mo]);
        matStatus.push([diccMO[claveW].status]);
      } else {
        matMo.push([""]);
        matStatus.push([""]);
      }
    }

    hoja.getRange(3, colMo, nF, 1).setValues(matMo);
    hoja.getRange(3, colMoStatus, nF, 1).setValues(matStatus);
  }

  escribirValores(hojaPorHacer, "Producción");
  escribirValores(hojaEspecial, "Especial");
  mensaje += "🔄 DATOS VINCULADOS:\nLas columnas MO y MO STATUS se actualizaron en todas las listas sin comprometer fórmulas.";

  SpreadsheetApp.getUi().alert("RESUMEN DE ACTUALIZACIÓN\n\n" + mensaje);
}

// =====================================================================
//  BLOQUEO DE SKUs DUPLICADOS
// =====================================================================
function onEdit(e) {
  if (!e || !e.range) return;
  var sheet = e.range.getSheet();
  var nombre = sheet.getName();
  if (nombre !== "Por Hacer" && nombre !== "Por Hacer - Especial") return;

  var rangoEditado = e.range;
  var filaEditada = rangoEditado.getRow();
  if (filaEditada <= 2) return;

  var headers = sheet.getRange(2, 1, 1, sheet.getLastColumn()).getValues()[0];
  var colSKU = -1;
  for (var h = 0; h < headers.length; h++) {
    if (normUp_(headers[h]) === "SKU") { colSKU = h + 1; break; }
  }
  if (colSKU === -1) return;

  var colEditada = rangoEditado.getColumn();
  var esCampoSku = (colEditada === colSKU);
  if (!esCampoSku) {
    var hEdit = normLow_(headers[colEditada - 1] || "");
    esCampoSku = (hEdit.indexOf("producto") !== -1 || hEdit.indexOf("modelo") !== -1 ||
      hEdit.indexOf("genero") !== -1 || hEdit.indexOf("género") !== -1 ||
      hEdit.indexOf("color") !== -1 || hEdit.indexOf("talla") !== -1);
  }
  if (!esCampoSku) return;

  SpreadsheetApp.flush();

  var skuGenerado = normUp_(sheet.getRange(filaEditada, colSKU).getValue());
  if (skuGenerado === "" || skuGenerado.indexOf("#") === 0) return;

  var ultimaFila = sheet.getLastRow();
  if (ultimaFila < 3) return;
  var valores = sheet.getRange(3, colSKU, ultimaFila - 2, 1).getValues();
  var contador = 0;
  for (var i = 0; i < valores.length; i++) {
    if (normUp_(valores[i][0]) === skuGenerado) contador++;
  }

  if (contador > 1) {
    if (e.oldValue !== undefined) rangoEditado.setValue(e.oldValue);
    else rangoEditado.clearContent();
    SpreadsheetApp.getUi().alert(
      "🚨 BLOQUEO DE SISTEMA: El producto ingresado genera el SKU '" + skuGenerado +
      "', el cual YA EXISTE en esta misma pestaña.\n\nSe ha revertido la celda para evitar duplicados."
    );
  }
}

// =====================================================================
//  SINCRONIZACIÓN DE TRACKING DE PRODUCCIÓN EXTERNO
// =====================================================================
function sincronizarProduccionExterna() {
  var ssMain = SpreadsheetApp.getActiveSpreadsheet();
  var idExterno = "17jm_xU7YhcJT4MlO7ARZTQOZ1bfjepsSNHANggGlgV4";
  var ssExt;

  try {
    ssExt = SpreadsheetApp.openById(idExterno);
  } catch (err) {
    SpreadsheetApp.getUi().alert("🚨 Error de Conexión: No se pudo acceder al archivo de Tracking externo. Verifica los permisos.");
    return;
  }

  var hojaUnidades = ssExt.getSheetByName("Unidades Producidas - Costura");
  var hojaTrackingMain = ssMain.getSheetByName("Tracking - Produccion");
  var hojaPorHacer = ssMain.getSheetByName("Por Hacer");
  var hojaEspecial = ssMain.getSheetByName("Por Hacer - Especial");

  if (!hojaUnidades || !hojaTrackingMain || !hojaPorHacer) {
    SpreadsheetApp.getUi().alert("Faltan hojas clave en los archivos. Verifica que existan 'Unidades Producidas - Costura' (externo), 'Tracking - Produccion' y 'Por Hacer' (principal).");
    return;
  }

  var datosUnidades = hojaUnidades.getDataRange().getValues();
  var totalesPorLineaExterno = {};

  if (datosUnidades.length > 0) {
    var detHeadC = encontrarFilaEncabezado_(datosUnidades, ["linea", "lunes"], 10);
    var filaHeaders = detHeadC.fila;
    var headersUnidades = detHeadC.celdas;

    if (filaHeaders !== -1) {
      var idxLinea = headersUnidades.findIndex(function (h) { return h.indexOf("linea") !== -1 || h.indexOf("línea") !== -1; });
      var idxLunes = headersUnidades.findIndex(function (h) { return h.indexOf("lunes") !== -1; });
      var idxMartes = headersUnidades.findIndex(function (h) { return h.indexOf("martes") !== -1; });
      var idxMiercoles = headersUnidades.findIndex(function (h) { return h.indexOf("miercoles") !== -1 || h.indexOf("miércoles") !== -1; });
      var idxJueves = headersUnidades.findIndex(function (h) { return h.indexOf("jueves") !== -1; });
      var idxViernes = headersUnidades.findIndex(function (h) { return h.indexOf("viernes") !== -1; });

      for (var i = filaHeaders + 1; i < datosUnidades.length; i++) {
        var filaStr = String(datosUnidades[i][idxLinea]).trim().toLowerCase();
        var match = filaStr.match(/\d+/);
        var numLinea = match ? "linea " + match[0] : filaStr;
        if (!numLinea) continue;
        if (!totalesPorLineaExterno[numLinea]) totalesPorLineaExterno[numLinea] = { lunes: 0, martes: 0, miercoles: 0, jueves: 0, viernes: 0 };
        totalesPorLineaExterno[numLinea].lunes += Number(datosUnidades[i][idxLunes]) || 0;
        totalesPorLineaExterno[numLinea].martes += Number(datosUnidades[i][idxMartes]) || 0;
        totalesPorLineaExterno[numLinea].miercoles += Number(datosUnidades[i][idxMiercoles]) || 0;
        totalesPorLineaExterno[numLinea].jueves += Number(datosUnidades[i][idxJueves]) || 0;
        totalesPorLineaExterno[numLinea].viernes += Number(datosUnidades[i][idxViernes]) || 0;
      }
    }
  }

  var datosTracking = hojaTrackingMain.getDataRange().getValues();
  var nTrack = datosTracking.length;
  var colD = [], colF = [], colH = [], colJ = [], colL = [], colN = [];
  for (var t = 0; t < nTrack; t++) {
    var filaTracking = datosTracking[t];
    var nombreLineaTracking = String(filaTracking[1]).trim().toLowerCase();
    if (nombreLineaTracking === "" || (nombreLineaTracking.indexOf("linea") === -1 && nombreLineaTracking.indexOf("línea") === -1)) {
      colD.push([filaTracking[3] || ""]); colF.push([filaTracking[5] || ""]);
      colH.push([filaTracking[7] || ""]); colJ.push([filaTracking[9] || ""]);
      colL.push([filaTracking[11] || ""]); colN.push([filaTracking[13] || ""]);
      continue;
    }
    var matchT = nombreLineaTracking.match(/\d+/);
    var numLineaT = matchT ? "linea " + matchT[0] : nombreLineaTracking;
    var prod = totalesPorLineaExterno[numLineaT] || { lunes: 0, martes: 0, miercoles: 0, jueves: 0, viernes: 0 };
    colD.push([prod.lunes > 0 ? prod.lunes : ""]);
    colF.push([prod.martes > 0 ? prod.martes : ""]);
    colH.push([prod.miercoles > 0 ? prod.miercoles : ""]);
    colJ.push([prod.jueves > 0 ? prod.jueves : ""]);
    colL.push([prod.viernes > 0 ? prod.viernes : ""]);
    var totalSemana = prod.lunes + prod.martes + prod.miercoles + prod.jueves + prod.viernes;
    colN.push([totalSemana > 0 ? totalSemana : ""]);
  }
  if (nTrack > 0) {
    hojaTrackingMain.getRange(1, 4, nTrack, 1).setValues(colD);
    hojaTrackingMain.getRange(1, 6, nTrack, 1).setValues(colF);
    hojaTrackingMain.getRange(1, 8, nTrack, 1).setValues(colH);
    hojaTrackingMain.getRange(1, 10, nTrack, 1).setValues(colJ);
    hojaTrackingMain.getRange(1, 12, nTrack, 1).setValues(colL);
    hojaTrackingMain.getRange(1, 14, nTrack, 1).setValues(colN);
  }

  var hojaProdCostura = ssMain.getSheetByName("Produccion - Costura");
  var totalesPorMo = {};
  var totalesPorLineaYMo = {};

  if (hojaProdCostura && hojaProdCostura.getLastRow() >= 3) {
    var ultFilaPC = hojaProdCostura.getLastRow();
    var datosPC = hojaProdCostura.getRange(3, 2, ultFilaPC - 2, 9).getValues();

    datosPC.forEach(function (fila) {
      var mo = String(fila[0] || "").trim().toUpperCase();
      var lineaTxt = String(fila[6] || "").trim().toLowerCase();
      var cantidad = Number(fila[7]) || 0;
      if (mo === "" || cantidad === 0) return;

      totalesPorMo[mo] = (totalesPorMo[mo] || 0) + cantidad;
      var matchL = lineaTxt.match(/\d+/);
      var numLineaPC = matchL ? "linea " + matchL[0] : lineaTxt;
      if (numLineaPC) {
        var keyLS = numLineaPC + "_" + mo;
        totalesPorLineaYMo[keyLS] = (totalesPorLineaYMo[keyLS] || 0) + cantidad;
      }
    });
  } else {
    SpreadsheetApp.getUi().alert("⚠️ Aviso: la pestaña 'Produccion - Costura' no existe o está vacía.\n'Cantidad Producida' no pudo recalcularse.\nUsa '💾 Guardar Producción (Corte Diario)' primero.");
  }

  function inyectarCantidades(hojaDestino, nombreHoja) {
    if (!hojaDestino) return;
    var ultFila = hojaDestino.getLastRow();
    var ultCol = hojaDestino.getLastColumn();
    if (ultFila < 3) return;

    var datosVal = hojaDestino.getDataRange().getValues();
    var detHeadPH = encontrarFilaEncabezado_(datosVal, ["mo", "cantidad solicitada"], 6);
    if (detHeadPH.fila === -1) return;

    var headers = detHeadPH.celdas;
    var idxMoH = headers.findIndex(function (h) { return h === "mo" || h === "m.o." || h.indexOf("mo ") === 0; });
    var idxSkuH = headers.indexOf("sku");
    var idxSolH = headers.findIndex(function (h) { return h.indexOf("cantidad solicitada") !== -1; });
    var idxProdH = headers.findIndex(function (h) { return h.indexOf("cantida producida") !== -1 || h.indexOf("cantidad producida") !== -1; });
    var idxFaltH = headers.findIndex(function (h) { return h === "faltante"; });

    if (idxMoH === -1 || idxSolH === -1 || idxProdH === -1 || idxFaltH === -1) {
      SpreadsheetApp.getUi().alert("⚠️ Aviso: No se pudieron actualizar las cantidades en '" + nombreHoja + "' por falta de encabezados exactos.");
      return;
    }

    var datosH = hojaDestino.getRange(detHeadPH.fila + 2, 1, ultFila - (detHeadPH.fila + 1), ultCol).getValues();
    var colProduccion = [];
    var colFaltante = [];

    for (var r = 0; r < datosH.length; r++) {
      var rowMoStr = String(datosH[r][idxMoH]).trim().toUpperCase();
      var valSol = String(datosH[r][idxSolH]).trim();
      var cantSol = Number(valSol) || 0;
      var rowSkuStr = idxSkuH !== -1 ? String(datosH[r][idxSkuH]).trim() : "";

      if (rowMoStr === "" && rowSkuStr === "" && valSol === "") {
        colProduccion.push([""]);
        colFaltante.push([""]);
        continue;
      }

      var prodHoy = 0;
      if (rowMoStr !== "") {
        rowMoStr.split(",").forEach(function (mm) {
          prodHoy += (totalesPorMo[mm.trim()] || 0);
        });
      }

      var faltante = cantSol - prodHoy;
      if (faltante < 0) faltante = 0;

      colProduccion.push([prodHoy > 0 ? prodHoy : ""]);
      colFaltante.push([prodHoy > 0 ? faltante : (valSol !== "" ? cantSol : "")]);
    }
    hojaDestino.getRange(detHeadPH.fila + 2, idxProdH + 1, colProduccion.length, 1).setValues(colProduccion);
    hojaDestino.getRange(detHeadPH.fila + 2, idxFaltH + 1, colFaltante.length, 1).setValues(colFaltante);
  }

  inyectarCantidades(hojaPorHacer, "Por Hacer");
  if (hojaEspecial) inyectarCantidades(hojaEspecial, "Por Hacer - Especial");

  ["Linea 1", "Linea 2", "Linea 3", "Linea 4", "Linea 5"].forEach(function (nombreHoja) {
    var hojaLinea = ssMain.getSheetByName(nombreHoja);
    if (!hojaLinea) return;
    var ultFila = hojaLinea.getLastRow();
    if (ultFila < 3) return;
    var datosLinea = hojaLinea.getRange(3, 1, ultFila - 2, 11).getValues();
    var colProduccionL = [];
    var colFaltanteL = [];
    var prefijoLinea = nombreHoja.toLowerCase();

    for (var r = 0; r < datosLinea.length; r++) {
      var rowMoStrL = String(datosLinea[r][1]).trim().toUpperCase();
      var rowSkuL = String(datosLinea[r][2]).trim().toUpperCase();
      var valAsignada = String(datosLinea[r][4]).trim();
      var cantAsignada = Number(valAsignada) || 0;

      if (rowMoStrL === "" && rowSkuL === "" && valAsignada === "") {
        colProduccionL.push([""]);
        colFaltanteL.push([""]);
        continue;
      }

      var produccionEnEstaLinea = 0;
      if (rowMoStrL !== "") {
        rowMoStrL.split(",").forEach(function (mm) {
          produccionEnEstaLinea += (totalesPorLineaYMo[prefijoLinea + "_" + mm.trim()] || 0);
        });
      }

      var faltanteEnLinea = cantAsignada - produccionEnEstaLinea;
      if (faltanteEnLinea < 0) faltanteEnLinea = 0;

      colProduccionL.push([produccionEnEstaLinea > 0 ? produccionEnEstaLinea : ""]);
      colFaltanteL.push([produccionEnEstaLinea > 0 ? faltanteEnLinea : valAsignada]);
    }

    hojaLinea.getRange(3, 12, colProduccionL.length, 1).setValues(colProduccionL);
    hojaLinea.getRange(3, 13, colFaltanteL.length, 1).setValues(colFaltanteL);
    hojaLinea.getRange(3, 12, colProduccionL.length, 2)
      .setHorizontalAlignment("center")
      .setVerticalAlignment("middle")
      .setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.SOLID);
  });

  var mapaMoAModelo = {};

  function mapearModelosPorMo(hoja, esEspecial) {
    if (!hoja) return;
    var datosM = hoja.getDataRange().getValues();
    var detHeadM = encontrarFilaEncabezado_(datosM, ["mo", "producto"], 6);
    if (detHeadM.fila === -1) return;
    var headersM = detHeadM.celdas;
    var idMo = headersM.findIndex(function (h) { return h === "mo" || h === "m.o." || h.indexOf("mo ") === 0; });
    var idProd = headersM.findIndex(function (h) { return h === "producto" || h === "modelo"; });
    var idGen = headersM.findIndex(function (h) { return h.indexOf("genero") !== -1 || h.indexOf("género") !== -1; });
    if (idMo === -1 || idProd === -1) return;

    for (var i = detHeadM.fila + 1; i < datosM.length; i++) {
      var moStr = String(datosM[i][idMo]).trim().toUpperCase();
      if (moStr === "") continue;
      var prod = String(datosM[i][idProd]).trim();
      var gen = idGen !== -1 ? String(datosM[i][idGen]).trim() : "";
      var mod = prod + (gen !== "" && gen !== "--" ? " " + gen : "");
      if (esEspecial) mod += " (Especial)";
      moStr.split(",").forEach(function (mm) { mapaMoAModelo[mm.trim()] = mod; });
    }
  }

  mapearModelosPorMo(hojaPorHacer, false);
  mapearModelosPorMo(hojaEspecial, true);

  var hojaValidacion = ssMain.getSheetByName("Entrada a almacen - Validación");
  if (!hojaValidacion) {
    var sheets = ssMain.getSheets();
    for (var s = 0; s < sheets.length; s++) {
      var sName = quitarTildes_(sheets[s].getName().toLowerCase()).trim();
      if (sName.indexOf("entrada") !== -1 && sName.indexOf("almacen") !== -1 && sName.indexOf("valida") !== -1) {
        hojaValidacion = sheets[s];
        break;
      }
    }
  }

  var totalesAlmacenMo = {};
  var totalesAlmacenModelo = {};

  if (hojaValidacion) {
    var datosV = hojaValidacion.getDataRange().getValues();
    var detHeadV = encontrarFilaEncabezado_(datosV, ["mo", "cantidad"], 6);
    if (detHeadV.fila !== -1) {
      var headersV = detHeadV.celdas;
      var idMoV = headersV.indexOf("mo");
      var idCantV = headersV.indexOf("cantidad");
      if (idMoV !== -1 && idCantV !== -1) {
        for (var iv = detHeadV.fila + 1; iv < datosV.length; iv++) {
          var moV = String(datosV[iv][idMoV]).trim().toUpperCase();
          var cantV = Number(datosV[iv][idCantV]) || 0;
          if (cantV > 0 && moV !== "") {
            totalesAlmacenMo[moV] = (totalesAlmacenMo[moV] || 0) + cantV;
            var modMapping = mapaMoAModelo[moV];
            if (modMapping) totalesAlmacenModelo[modMapping] = (totalesAlmacenModelo[modMapping] || 0) + cantV;
          }
        }
      }
    }
  }

  var hojaAlmacenSku = ssMain.getSheetByName("Entrada de Almacen - Skus");
  if (hojaAlmacenSku && hojaAlmacenSku.getLastRow() >= 3) {
    var ultFilaS = hojaAlmacenSku.getLastRow();
    var datosS = hojaAlmacenSku.getRange(3, 2, ultFilaS - 2, 8).getValues();
    var colRecepcionado = [];
    var colFaltanteS = [];
    for (var rS = 0; rS < datosS.length; rS++) {
      var rowMoStr = String(datosS[rS][0]).trim().toUpperCase();
      var rowSku = String(datosS[rS][1]).trim().toUpperCase();
      var valSolS = String(datosS[rS][3]).trim();
      var cantSolS = Number(valSolS) || 0;
      if (rowMoStr === "" && rowSku === "" && valSolS === "") {
        colRecepcionado.push([""]); colFaltanteS.push([""]); continue;
      }
      var recHoy = 0;
      if (rowMoStr !== "") {
        rowMoStr.split(",").forEach(function (mm) { recHoy += (totalesAlmacenMo[mm.trim()] || 0); });
      }
      var faltS = cantSolS - recHoy; if (faltS < 0) faltS = 0;
      colRecepcionado.push([recHoy > 0 ? recHoy : ""]);
      colFaltanteS.push([recHoy > 0 ? faltS : (valSolS !== "" ? cantSolS : "")]);
    }
    hojaAlmacenSku.getRange(3, 8, colRecepcionado.length, 1).setValues(colRecepcionado);
    hojaAlmacenSku.getRange(3, 9, colFaltanteS.length, 1).setValues(colFaltanteS);
  }

  var hojaAlmacenMod = ssMain.getSheetByName("Entrada de Almacen Modelo");
  if (hojaAlmacenMod && hojaAlmacenMod.getLastRow() >= 3) {
    var ultFilaM = hojaAlmacenMod.getLastRow();
    var datosMm = hojaAlmacenMod.getRange(3, 2, ultFilaM - 2, 7).getValues();
    var colRecepcionadoM = [];
    var colFaltanteM = [];
    for (var rM = 0; rM < datosMm.length; rM++) {
      var rowModelo = String(datosMm[rM][1]).trim();
      var valSolM = String(datosMm[rM][2]).trim();
      var cantSolM = Number(valSolM) || 0;
      if (rowModelo === "" && valSolM === "") {
        colRecepcionadoM.push([""]); colFaltanteM.push([""]); continue;
      }
      var recHoyM = totalesAlmacenModelo[rowModelo] || 0;
      var faltM = cantSolM - recHoyM; if (faltM < 0) faltM = 0;
      colRecepcionadoM.push([recHoyM > 0 ? recHoyM : ""]);
      colFaltanteM.push([recHoyM > 0 ? faltM : (valSolM !== "" ? cantSolM : "")]);
    }
    hojaAlmacenMod.getRange(3, 7, colRecepcionadoM.length, 1).setValues(colRecepcionadoM);
    hojaAlmacenMod.getRange(3, 8, colFaltanteM.length, 1).setValues(colFaltanteM);
  }

  SpreadsheetApp.getUi().alert(
    "✅ SINCRONIZACIÓN MAESTRA EXITOSA\n\n" +
    "• Tablero visual 'Tracking - Produccion' actualizado con el archivo externo.\n" +
    "• 'Cantidad Producida' / 'Faltante' recalculados en todas las listas locales.\n" +
    "• Pestañas de Línea 1-5 actualizadas.\n" +
    "• 📦 Pestañas de Almacén (Modelo y SKUs) sincronizadas con los ingresos basados SOLO en MO."
  );
}

function encontrarFilaEncabezado_(filasData, palabrasClave, maxFilas) {
  var limite = Math.min(maxFilas || filasData.length, filasData.length);
  var palabrasNorm = palabrasClave.map(function (p) { return quitarTildes_(p); });
  for (var r = 0; r < limite; r++) {
    var fila = filasData[r];
    if (!fila) continue;
    var celdas = fila.map(function (x) { return quitarTildes_(String(x).toLowerCase().trim()); });
    var coincideTodas = palabrasNorm.every(function (p) {
      return celdas.some(function (c) { return c === p || (c.indexOf(p) === 0 && c.length <= p.length + 3); });
    });
    if (coincideTodas) return { fila: r, celdas: celdas };
  }
  return { fila: -1, celdas: [] };
}

function guardarHistorialProduccionDiario() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var hoja = ss.getSheetByName("Produccion - Costura");
  if (!hoja || hoja.getLastRow() < 3) {
    SpreadsheetApp.getUi().alert("No hay datos en 'Produccion - Costura' para guardar el corte diario.");
    return;
  }

  var stamp = Utilities.formatDate(new Date(), ss.getSpreadsheetTimeZone(), "yyyy-MM-dd HH.mm");
  var nombre = "🗓 Costura " + stamp;
  var previa = ss.getSheetByName(nombre);
  if (previa) ss.deleteSheet(previa);

  var copia = hoja.copyTo(ss).setName(nombre);
  var r = copia.getDataRange();
  r.setValues(r.getValues());
  copia.hideSheet();

  var snaps = ss.getSheets()
    .filter(function (s) { return s.getName().indexOf("🗓 Costura ") === 0; })
    .sort(function (a, b) { return a.getName().localeCompare(b.getName()); });
  while (snaps.length > 14) ss.deleteSheet(snaps.shift());

  SpreadsheetApp.getUi().alert("💾 Corte diario guardado como hoja oculta:\n\n" + nombre +
    "\n\nSe conservan los últimos 14 cortes.");
}

function obtenerDatosDashboardCompleto() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var resp = {
    backlog: [], semanas: {}, proyModelo: [], proySku: [], fechasSemanas: {}, skuDiarioS1: {},
    opcionesFiltro: { modelos: [], skus: [], generos: [], colores: [], tallas: [], prioridades: [], lineas: [] }
  };

  function normalizarPrioridad(p) {
    var pLow = String(p).toLowerCase().trim();
    if (pLow.indexOf("urgente") !== -1) return "Urgente";
    if (pLow.indexOf("alta") !== -1) return "Alta";
    if (pLow.indexOf("media") !== -1) return "Media";
    if (pLow.indexOf("baja") !== -1) return "Baja";
    return "Sin Asignar";
  }

  var hpM = null, hpS = null, hojaPrio = null;
  ss.getSheets().forEach(function (s) {
    var nm = s.getName().toLowerCase().replace(/[^a-z0-9]/g, "");
    if (nm.indexOf("proyeccionsku") !== -1) hpS = s;
    else if (nm.indexOf("proyeccion") !== -1) hpM = s;
    if (nm.indexOf("prioriza") !== -1) hojaPrio = s;
  });

  if (hpM) {
    var dpm0 = hpM.getDataRange().getValues();
    var detHead0 = encontrarFilaEncabezado_(dpm0, ["modelo"], 6);
    var headerProy = detHead0.fila !== -1 ? detHead0.celdas : (dpm0[1] ? dpm0[1].map(function (x) { return String(x).toLowerCase().trim(); }) : []);
    for (var k = 0; k < headerProy.length; k++) {
      var hstr = headerProy[k];
      if (hstr.indexOf("sem ") !== -1 || hstr.indexOf("acum sem") !== -1) {
        var semNum = hstr.match(/sem\s*(\d+)/i);
        var dateMatch = hstr.match(/\(([^)]+)\)/);
        if (semNum && dateMatch) resp.fechasSemanas["Semana " + semNum[1]] = dateMatch[1];
      }
    }
  }

  var prioMap = {};
  if (hojaPrio) {
    var dp = hojaPrio.getDataRange().getValues();
    var detHeadPrio = encontrarFilaEncabezado_(dp, ["modelo", "prioridad"], 6);
    var rPrio = detHeadPrio.fila;
    var hPrio = detHeadPrio.celdas;
    if (rPrio !== -1) {
      var pMod = hPrio.indexOf("modelo"), pPri = hPrio.indexOf("prioridad");
      var pTip = hPrio.indexOf("tipo");
      var pFec = hPrio.indexOf("fecha de salida estimada");
      if (pFec === -1) pFec = hPrio.findIndex(function (x) { return x.indexOf("fecha") !== -1; });
      var pMin = hPrio.findIndex(function (x) { return x.indexOf("minima") !== -1 || x.indexOf("mínima") !== -1; });

      for (var i = rPrio + 1; i < dp.length; i++) {
        var mod = pMod !== -1 ? String(dp[i][pMod]).trim() : "";
        var tipoP = pTip !== -1 ? String(dp[i][pTip]).trim().toLowerCase() : "";
        if (mod) {
          if (tipoP === "especial") mod += " (Especial)";
          prioMap[mod] = {
            prioridad: pPri !== -1 ? normalizarPrioridad(dp[i][pPri]) : "Sin Asignar",
            fecha: pFec !== -1 ? (dp[i][pFec] instanceof Date ? dp[i][pFec].getTime() : dp[i][pFec]) : "",
            minima: pMin !== -1 ? Number(dp[i][pMin]) || 0 : 0
          };
        }
      }
    }
  }

  var skuToModelo = {};
  var setModelos = {}, setSkus = {}, setGeneros = {}, setColores = {}, setTallas = {}, setPrioridades = {}, setLineas = {};

  function procesarHojaBacklog(hojaAct, esEspecial) {
    if (!hojaAct) return;
    var dph = hojaAct.getDataRange().getValues();
    var detHeadPH = encontrarFilaEncabezado_(dph, ["sku"], 6);
    var rowPH = detHeadPH.fila;
    var hph = detHeadPH.celdas;
    if (rowPH === -1) return;

    var iSku = hph.indexOf("sku"), iMod = hph.indexOf("producto") !== -1 ? hph.indexOf("producto") : hph.indexOf("modelo");
    var iGen = hph.indexOf("genero") !== -1 ? hph.indexOf("genero") : hph.indexOf("género");
    var iCol = hph.indexOf("color"), iTal = hph.indexOf("talla"), iCant = hph.indexOf("cantidad solicitada");
    var iProdQty = hph.findIndex(function (x) { return x.indexOf("producida") !== -1; });
    var iFalt = hph.indexOf("faltante"), iMo = hph.indexOf("mo"), iPri = hph.indexOf("prioridad");
    var iFecPH = hph.indexOf("fecha de salida estimada");
    var iLinPH = hph.findIndex(function (x) { return x.indexOf("linea") !== -1 || x.indexOf("línea") !== -1; });
    var iCapPH = hph.findIndex(function (x) { return x.indexOf("cap produccion") !== -1 || x.indexOf("cap producción") !== -1 || x.indexOf("promedio") !== -1; });

    for (var i = rowPH + 1; i < dph.length; i++) {
      var s = String(dph[i][iSku]).trim();
      if (!s) continue;

      var mBase = iMod !== -1 ? String(dph[i][iMod]).trim() : "", mGen = iGen !== -1 ? String(dph[i][iGen]).trim() : "";
      var color = iCol !== -1 ? String(dph[i][iCol]).trim() : "", talla = iTal !== -1 ? String(dph[i][iTal]).trim() : "";
      var linea = iLinPH !== -1 ? String(dph[i][iLinPH]).trim() : "";
      var cap = iCapPH !== -1 ? (Number(dph[i][iCapPH]) || 0) : 0;
      var m = mBase + (mGen !== "" && mGen !== "--" ? " " + mGen : "");
      var arrDetalle = [mBase];
      if (mGen && mGen !== "--") arrDetalle.push(mGen);
      if (color && color !== "--") arrDetalle.push(color);
      if (talla && talla !== "--") arrDetalle.push(talla);

      if (esEspecial) {
        m += " (Especial)";
        arrDetalle.push("(Especial)");
      }

      skuToModelo[s] = m;

      var pInfo = prioMap[m] || { prioridad: "Sin Asignar", fecha: "", minima: 0 };
      var prioFila = iPri !== -1 ? String(dph[i][iPri]).trim() : "";
      if (!prioFila) prioFila = pInfo.prioridad;
      var prioridadNormalizada = normalizarPrioridad(prioFila);

      var fechaFila = iFecPH !== -1 ? dph[i][iFecPH] : "";
      if (!fechaFila) fechaFila = pInfo.fecha;

      var cantSol = iCant !== -1 ? (Number(dph[i][iCant]) || 0) : 0;
      var prodQty = iProdQty !== -1 ? (Number(dph[i][iProdQty]) || 0) : 0;
      var faltanteFinal = 0;

      if (iProdQty !== -1) faltanteFinal = Math.max(0, cantSol - prodQty);
      else if (iFalt !== -1 && dph[i][iFalt] !== "") faltanteFinal = Number(dph[i][iFalt]) || 0;
      else faltanteFinal = cantSol;

      resp.backlog.push({
        sku: s, modelo: m, detalle: arrDetalle.join("-"), mo: iMo !== -1 ? String(dph[i][iMo]) : "",
        genero: mGen, color: color, talla: talla, linea: linea, cap: cap,
        tipo: esEspecial ? "Especial" : "Producción",
        solicitada: cantSol, producida: prodQty, faltante: faltanteFinal,
        prioridad: prioridadNormalizada, fechaSalida: fechaFila instanceof Date ? fechaFila.getTime() : fechaFila,
        minima: pInfo.minima
      });

      if (m) setModelos[m] = true;
      if (s) setSkus[s] = true;
      if (mGen && mGen !== "--") setGeneros[mGen] = true;
      if (color && color !== "--") setColores[color] = true;
      if (talla && talla !== "--") setTallas[talla] = true;
      if (prioridadNormalizada) setPrioridades[prioridadNormalizada] = true;
      if (linea) {
        parsearLineas_(linea).forEach(function (l) { setLineas[l] = true; });
      }
    }
  }

  procesarHojaBacklog(ss.getSheetByName("Por Hacer"), false);
  procesarHojaBacklog(ss.getSheetByName("Por Hacer - Especial"), true);

  resp.opcionesFiltro.modelos = Object.keys(setModelos).sort();
  resp.opcionesFiltro.skus = Object.keys(setSkus).sort();
  resp.opcionesFiltro.generos = Object.keys(setGeneros).sort();
  resp.opcionesFiltro.colores = Object.keys(setColores).sort();
  resp.opcionesFiltro.tallas = Object.keys(setTallas).sort();
  resp.opcionesFiltro.prioridades = ["Urgente", "Alta", "Media", "Baja", "Sin Asignar"].filter(function (p) { return setPrioridades[p]; });
  resp.opcionesFiltro.lineas = Object.keys(setLineas).sort();

  ss.getSheets().forEach(function (s) {
    var sName = s.getName().toLowerCase();
    if (sName.indexOf("linea") === -1 && sName.indexOf("línea") === -1) return;
    var data = s.getDataRange().getValues();
    var detHeadL = encontrarFilaEncabezado_(data, ["sku", "lunes"], 16);
    var rHead = detHeadL.fila, cols = {};
    if (rHead === -1) return;
    var rStr = detHeadL.celdas;
    cols.sku = rStr.indexOf("sku");
    cols.lu = rStr.findIndex(function (x) { return x.indexOf("lunes") !== -1; });
    cols.ma = rStr.findIndex(function (x) { return x.indexOf("martes") !== -1; });
    cols.mi = rStr.findIndex(function (x) { return x.indexOf("miercoles") !== -1 || x.indexOf("miércoles") !== -1; });
    cols.ju = rStr.findIndex(function (x) { return x.indexOf("jueves") !== -1; });
    cols.vi = rStr.findIndex(function (x) { return x.indexOf("viernes") !== -1; });
    for (var i = rHead + 1; i < data.length; i++) {
      var sku = String(data[i][cols.sku]).trim();
      if (!sku) continue;
      var lu = cols.lu !== -1 ? (Number(data[i][cols.lu]) || 0) : 0;
      var ma = cols.ma !== -1 ? (Number(data[i][cols.ma]) || 0) : 0;
      var mi = cols.mi !== -1 ? (Number(data[i][cols.mi]) || 0) : 0;
      var ju = cols.ju !== -1 ? (Number(data[i][cols.ju]) || 0) : 0;
      var vi = cols.vi !== -1 ? (Number(data[i][cols.vi]) || 0) : 0;
      if (lu > 0 || ma > 0 || mi > 0 || ju > 0 || vi > 0) {
        if (!resp.skuDiarioS1[sku]) resp.skuDiarioS1[sku] = { lunes: 0, martes: 0, miercoles: 0, jueves: 0, viernes: 0, total: 0 };
        resp.skuDiarioS1[sku].lunes += lu; resp.skuDiarioS1[sku].martes += ma; resp.skuDiarioS1[sku].miercoles += mi;
        resp.skuDiarioS1[sku].jueves += ju; resp.skuDiarioS1[sku].viernes += vi; resp.skuDiarioS1[sku].total += (lu + ma + mi + ju + vi);
      }
    }
  });

  var nombresSemanas = ["Planificacion", "Semana 2", "Semana 3", "Semana 4", "Semana 5"];
  nombresSemanas.forEach(function (nom, idx) {
    var sh = ss.getSheetByName(nom);
    var semanaKey = "Semana " + (idx + 1);
    resp.semanas[semanaKey] = { carga: [], resumen: [] };
    if (!sh) return;
    var data = sh.getDataRange().getValues();
    var detHeadCarga = encontrarFilaEncabezado_(data, ["linea", "modelo"], 50);
    var rCarga = detHeadCarga.fila, colLin = -1, colModCarga = -1, colTotSku = -1;
    var colsDias = { lunes: -1, martes: -1, miercoles: -1, jueves: -1, viernes: -1 };

    if (rCarga !== -1) {
      var rowStr = detHeadCarga.celdas;
      colLin = rowStr.indexOf("linea"); colModCarga = rowStr.indexOf("modelo");
      colTotSku = rowStr.findIndex(function (x) { return (x.indexOf("total semana (sku)") !== -1) || (x.indexOf("total semana") !== -1 && x.indexOf("linea") === -1); });
      if (colTotSku === -1) colTotSku = colModCarga + 8;
      colsDias.lunes = rowStr.findIndex(function (x) { return x.indexOf("lunes") !== -1; });
      colsDias.martes = rowStr.findIndex(function (x) { return x.indexOf("martes") !== -1; });
      colsDias.miercoles = rowStr.findIndex(function (x) { return x.indexOf("miercoles") !== -1 || x.indexOf("miércoles") !== -1; });
      colsDias.jueves = rowStr.findIndex(function (x) { return x.indexOf("jueves") !== -1; });
      colsDias.viernes = rowStr.findIndex(function (x) { return x.indexOf("viernes") !== -1; });
    }

    if (rCarga !== -1) {
      var currLin = "";
      for (var i = rCarga + 1; i < data.length; i++) {
        var valLin = String(data[i][colLin]).trim();
        if (valLin.toUpperCase().indexOf("TOTAL") !== -1) break;
        if (valLin !== "") currLin = valLin;
        var modCarga = String(data[i][colModCarga]).trim(), totSku = Number(data[i][colTotSku]) || 0;
        if (currLin !== "" && modCarga !== "" && totSku > 0) {
          resp.semanas[semanaKey].carga.push({
            linea: "Línea " + currLin, modelo: modCarga, total: totSku,
            dias: {
              lunes: colsDias.lunes !== -1 ? (Number(data[i][colsDias.lunes]) || 0) : 0,
              martes: colsDias.martes !== -1 ? (Number(data[i][colsDias.martes]) || 0) : 0,
              miercoles: colsDias.miercoles !== -1 ? (Number(data[i][colsDias.miercoles]) || 0) : 0,
              jueves: colsDias.jueves !== -1 ? (Number(data[i][colsDias.jueves]) || 0) : 0,
              viernes: colsDias.viernes !== -1 ? (Number(data[i][colsDias.viernes]) || 0) : 0
            }
          });
        }
      }
    }

    var rRes = -1, colMod = -1, colMeta = -1, colPlan = -1, colPct = -1;
    for (var ir = 0; ir < Math.min(120, data.length); ir++) {
      var rowStr2 = data[ir].map(function (x) { return String(x).toLowerCase().trim(); });
      if (rowStr2.indexOf("modelo") !== -1 && rowStr2.findIndex(function (x) { return x.indexOf("% cobertura") !== -1 || x.indexOf("cobertura") !== -1; }) !== -1) {
        rRes = ir; colMod = rowStr2.indexOf("modelo");
        colPct = rowStr2.findIndex(function (x) { return x.indexOf("cobertura") !== -1; });
        colPlan = rowStr2.findIndex(function (x) { return x.indexOf("a fabricar") !== -1 || x.indexOf("planificado") !== -1; });
        colMeta = rowStr2.findIndex(function (x) { return x.indexOf("meta") !== -1 || x.indexOf("faltante") !== -1; });
        break;
      }
    }

    if (rRes !== -1) {
      for (var i2 = rRes + 1; i2 < data.length; i2++) {
        var modR = String(data[i2][colMod]).trim();
        if (modR === "" && String(data[i2].join("")).trim() === "") continue;
        if (modR.toUpperCase().indexOf("TOTAL") !== -1 || modR.indexOf("---") !== -1) break;
        if (modR !== "") {
          var valPct = data[i2][colPct];
          valPct = (typeof valPct === "string" && valPct.indexOf("%") !== -1) ? Number(valPct.replace("%", "").replace(",", ".")) / 100 : Number(valPct) || 0;
          var valMeta = data[i2][colMeta];
          if (valMeta instanceof Date) valMeta = Math.round((valMeta.getTime() - new Date(1899, 11, 30).getTime()) / (1000 * 60 * 60 * 24));
          else valMeta = Number(valMeta) || 0;
          var plan = colPlan !== -1 ? (Number(data[i2][colPlan]) || 0) : 0;
          resp.semanas[semanaKey].resumen.push({ modelo: modR, meta: valMeta, plan: plan, pct: valPct, pendiente: valMeta - plan });
        }
      }
    }
  });

  if (hpM) {
    var dpm = hpM.getDataRange().getValues();
    var detHeadM2 = encontrarFilaEncabezado_(dpm, ["modelo"], 6);
    var rHeadM = detHeadM2.fila;
    if (rHeadM !== -1) {
      var hArrM = detHeadM2.celdas;
      var iModM = hArrM.indexOf("modelo");
      var iFecM = hArrM.indexOf("fecha objetivo") !== -1 ? hArrM.indexOf("fecha objetivo") : hArrM.findIndex(function (x) { return x.indexOf("fecha") !== -1; });
      var iMetaM = hArrM.findIndex(function (x) { return x.indexOf("meta") !== -1 || x.indexOf("faltante") !== -1; });
      var iS1M = hArrM.findIndex(function (x) { return x.indexOf("sem 1") !== -1; });
      var iS2M = hArrM.findIndex(function (x) { return x.indexOf("sem 2") !== -1; });
      var iS3M = hArrM.findIndex(function (x) { return x.indexOf("sem 3") !== -1; });
      var iS4M = hArrM.findIndex(function (x) { return x.indexOf("sem 4") !== -1; });
      var iS5M = hArrM.findIndex(function (x) { return x.indexOf("sem 5") !== -1; });
      var iEstM = hArrM.findIndex(function (x) { return x.indexOf("estado") !== -1; });

      for (var im = rHeadM + 1; im < dpm.length; im++) {
        var mVal = iModM !== -1 ? String(dpm[im][iModM]).trim() : "";
        if (!mVal || mVal.toUpperCase().indexOf("TOTAL") !== -1) continue;
        resp.proyModelo.push({
          modelo: mVal, fecha: iFecM !== -1 ? (dpm[im][iFecM] instanceof Date ? dpm[im][iFecM].getTime() : dpm[im][iFecM]) : "",
          meta: iMetaM !== -1 ? (Number(dpm[im][iMetaM]) || 0) : 0,
          s1: iS1M !== -1 ? dpm[im][iS1M] : 0, s2: iS2M !== -1 ? dpm[im][iS2M] : 0,
          s3: iS3M !== -1 ? dpm[im][iS3M] : 0, s4: iS4M !== -1 ? dpm[im][iS4M] : 0, s5: iS5M !== -1 ? dpm[im][iS5M] : 0,
          estado: iEstM !== -1 ? String(dpm[im][iEstM]) : "",
          acumulado: true
        });
      }
    }
  }

  if (hpS) {
    var dps = hpS.getDataRange().getValues();
    var detHeadS2 = encontrarFilaEncabezado_(dps, ["sku"], 6);
    var rHeadS = detHeadS2.fila;
    if (rHeadS !== -1) {
      var hArrS = detHeadS2.celdas;
      var iSkuS = hArrS.indexOf("sku");
      var iModS = hArrS.indexOf("modelo");
      var iDetS = hArrS.indexOf("detalle del producto") !== -1 ? hArrS.indexOf("detalle del producto") : hArrS.findIndex(function (x) { return x.indexOf("detalle") !== -1; });
      var iMetaS = hArrS.findIndex(function (x) { return x.indexOf("meta") !== -1 || x.indexOf("faltante") !== -1; });
      var iS1S = hArrS.findIndex(function (x) { return x.indexOf("sem 1") !== -1; });
      var iS2S = hArrS.findIndex(function (x) { return x.indexOf("sem 2") !== -1; });
      var iS3S = hArrS.findIndex(function (x) { return x.indexOf("sem 3") !== -1; });
      var iS4S = hArrS.findIndex(function (x) { return x.indexOf("sem 4") !== -1; });
      var iS5S = hArrS.findIndex(function (x) { return x.indexOf("sem 5") !== -1; });
      var iEstS = hArrS.findIndex(function (x) { return x.indexOf("estado") !== -1; });
      var iGenS = hArrS.indexOf("genero"), iColS = hArrS.indexOf("color"), iTalS = hArrS.indexOf("talla");
      var iLinS = hArrS.indexOf("linea"), iCapS = hArrS.findIndex(function (x) { return x.indexOf("cap produccion") !== -1; });
      var iTipoS = hArrS.indexOf("tipo");

      for (var is = rHeadS + 1; is < dps.length; is++) {
        var skuVal = iSkuS !== -1 ? String(dps[is][iSkuS]).trim() : "";
        if (!skuVal) continue;
        var detVal = iDetS !== -1 ? String(dps[is][iDetS]).trim() : "";
        var modVal = (iModS !== -1 && String(dps[is][iModS]).trim() !== "")
          ? String(dps[is][iModS]).trim()
          : (skuToModelo[skuVal] || detVal.split(" ")[0]);

        resp.proySku.push({
          sku: skuVal, detalle: detVal, modelo: modVal,
          meta: iMetaS !== -1 ? (Number(dps[is][iMetaS]) || 0) : 0,
          s1: iS1S !== -1 ? dps[is][iS1S] : 0, s2: iS2S !== -1 ? dps[is][iS2S] : 0,
          s3: iS3S !== -1 ? dps[is][iS3S] : 0, s4: iS4S !== -1 ? dps[is][iS4S] : 0, s5: iS5S !== -1 ? dps[is][iS5S] : 0,
          estado: iEstS !== -1 ? String(dps[is][iEstS]) : "",
          genero: iGenS !== -1 ? String(dps[is][iGenS]) : "",
          color: iColS !== -1 ? String(dps[is][iColS]) : "",
          talla: iTalS !== -1 ? String(dps[is][iTalS]) : "",
          linea: iLinS !== -1 ? String(dps[is][iLinS]) : "",
          cap: iCapS !== -1 ? (Number(dps[is][iCapS]) || 0) : 0,
          tipo: iTipoS !== -1 ? String(dps[is][iTipoS]) : "",
          acumulado: true
        });
      }
    }
  }

  return JSON.stringify({ success: true, data: resp, version: VERSION_SISTEMA });
}
