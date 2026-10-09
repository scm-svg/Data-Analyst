/**
 * =====================================================================
 *  MÓDULO DE TRACKING DE PRODUCCIÓN — VERSIÓN 5.9.7 (CANTIDAD CORREO SIN INFLAR)
 * =====================================================================
 *  Cambios de esta versión:
 *   - La cantidad del detalle ya no se infla ni se lee como fecha/talla:
 *     historial con formato fecha, clave con un día de menos (America/Lima)
 *     o el mismo SKU con otro nombre de producto (p. ej. MAR vs MAR LOTE 1).
 *   - Sigue copiando Total del día y tableros diurno/nocturno (v5.9.6).
 * =====================================================================
 */

function onOpen() {
  var ui = SpreadsheetApp.getUi();

  ui.createMenu("⚙️ Tracking")
    .addItem("1️⃣ Actualizar Tablero (Costura)", "actualizarTrackingProduccion")
    .addItem("2️⃣ Actualizar Tablero (Estampado)", "actualizarTrackingEstampado")
    .addSeparator()
    .addItem("🔐 Autorizar envío de correo (una vez)", "autorizarEnvioCorreo")
    .addItem("📧 Enviar Reporte de Producción (Correo)", "enviarReporteProduccion")
    .addItem("↺ Reiniciar historial de correo diario", "reiniciarHistorialCorreo")
    .addSeparator()
    .addItem("💾 Enviar a Historial (Costura)", "guardarHistorialProduccionDiario")
    .addItem("💾 Enviar a Historial (Estampado)", "guardarHistorialEstampadoDiario")
    .addItem("📦 Enviar a Historial (Almacén)", "guardarHistorialAlmacenDiario")
    .addToUi();
}

// =====================================================================
// Helper robusto de detección de fila de encabezados.
// =====================================================================
function quitarTildes_(s) {
  return String(s).replace(/á/g, 'a').replace(/é/g, 'e').replace(/í/g, 'i')
    .replace(/ó/g, 'o').replace(/ú/g, 'u').replace(/ñ/g, 'n');
}

function encontrarFilaEncabezado_(filasData, palabrasClave, maxFilas) {
  var limite = Math.min(maxFilas || filasData.length, filasData.length);
  var palabrasNorm = palabrasClave.map(function(p){ return quitarTildes_(p); });
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

function vaciosDiasTracking_() {
  return { lunes: 0, martes: 0, miercoles: 0, jueves: 0, viernes: 0 };
}

function clasificarTurno_(val) {
  var t = quitarTildes_(String(val == null ? "" : val).toLowerCase()).replace(/\s+/g, " ").trim();
  if (t.indexOf("nocturn") !== -1) return "nocturno";
  return "diurno";
}

function etiquetaTurno_(clave) {
  return clave === "nocturno" ? "Nocturno" : "Diurno";
}

function tituloTableroTurno_(clave) {
  return clave === "nocturno" ? "Turno Nocturno" : "Turno Diurno";
}

function tituloTableroTotalDia_() {
  return "Total del día";
}

var MAX_COLS_TABLERO_CORREO_ = 26;

function maxColFilaTablero_(fila) {
  return Math.max(2, Math.min(MAX_COLS_TABLERO_CORREO_, (fila || []).length));
}

function turnoDeBloque_(texto) {
  var t = quitarTildes_(String(texto == null ? "" : texto).toLowerCase()).replace(/\s+/g, " ").trim();
  if (t.indexOf("nocturn") !== -1) return "nocturno";
  if (t.indexOf("diurn") !== -1) return "diurno";
  return "";
}

function asegurarTotalesTurno_(totalesPorTurno, turno, linea) {
  if (!totalesPorTurno[turno]) totalesPorTurno[turno] = {};
  if (!totalesPorTurno[turno][linea]) totalesPorTurno[turno][linea] = vaciosDiasTracking_();
  return totalesPorTurno[turno][linea];
}

var HEADERS_DETALLE_TRACKING_ = ["Dia", "Fecha", "Linea", "Turno", "MO", "SKU", "Producto", "Genero", "Color", "Talla", "Cantidad"];

function prepararHojaDetalleTracking_(ss, hojaDetalle) {
  if (!hojaDetalle) {
    hojaDetalle = ss.insertSheet("Detalle Tracking - Produccion");
  }
  var datos = hojaDetalle.getLastRow() > 0 ? hojaDetalle.getDataRange().getValues() : [];
  var headerRow = -1;
  for (var r = 0; r < Math.min(5, datos.length); r++) {
    var celdas = (datos[r] || []).map(function(x) {
      return quitarTildes_(String(x == null ? "" : x).toLowerCase().trim());
    });
    if ((celdas.indexOf("dia") !== -1 || celdas.indexOf("linea") !== -1) &&
        (celdas.indexOf("sku") !== -1 || celdas.indexOf("cantidad") !== -1)) {
      headerRow = r;
      break;
    }
  }
  if (headerRow === -1) headerRow = 0;
  hojaDetalle.getRange(headerRow + 1, 2, 1, HEADERS_DETALLE_TRACKING_.length)
    .setValues([HEADERS_DETALLE_TRACKING_])
    .setBackground("#434343").setFontColor("#FFFFFF").setFontWeight("bold")
    .setHorizontalAlignment("center");
  var ultFila = hojaDetalle.getLastRow();
  var dataStart = headerRow + 2;
  if (ultFila >= dataStart) {
    hojaDetalle.getRange(dataStart, 2, ultFila - dataStart + 1, HEADERS_DETALLE_TRACKING_.length)
      .clearContent().setBorder(false, false, false, false, false, false);
  }
  return { hoja: hojaDetalle, headerRow: headerRow, dataStart: dataStart };
}

// =========================================================================
// 1. ACTUALIZAR TABLERO VISUAL DE COSTURA (+ PEDIDOS + DETALLE CON LINKS)
// =========================================================================
function actualizarTrackingProduccion() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var hojaUnidades = ss.getSheetByName("Unidades Producidas - Costura");
  var hojaPedidos = ss.getSheetByName("Pedidos");
  var hojaTracking = ss.getSheetByName("Tracking - Produccion");

  if (!hojaUnidades || !hojaTracking) {
    SpreadsheetApp.getUi().alert("Faltan las hojas principales ('Unidades Producidas - Costura' o 'Tracking - Produccion').");
    return;
  }

  var prepDetalle = prepararHojaDetalleTracking_(ss, ss.getSheetByName("Detalle Tracking - Produccion"));
  var hojaDetalle = prepDetalle.hoja;
  var sheetIdDetalle = hojaDetalle.getSheetId();

  var totalesPorTurno = {};
  var registrosDetalle = []; // [Dia, Fecha, Linea, Turno, MO, SKU, Producto, Genero, Color, Talla, Cantidad]
  var mapaDiasNom = {1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves", 5: "Viernes"};

  // ==============================================================
  // 1. LEER DATOS DE "UNIDADES PRODUCIDAS - COSTURA"
  // ==============================================================
  var datosUnidades = hojaUnidades.getDataRange().getValues();
  if (datosUnidades.length > 0) {
    var detHeadC = encontrarFilaEncabezado_(datosUnidades, ["linea", "lunes"], 10);
    var filaHeaders = detHeadC.fila;
    var headersUnidades = detHeadC.celdas;

    if (filaHeaders !== -1) {
      var idxLinea = headersUnidades.findIndex(function(h) { return h.includes("linea") || h.includes("línea"); });
      var idxMo = headersUnidades.findIndex(function(h) { return h === "mo" || h === "m.o." || h.includes("mo "); });
      var idxSku = headersUnidades.indexOf("sku");
      var idxProd = headersUnidades.findIndex(function(h) { return h === "producto" || h === "modelo"; });
      var idxGen = headersUnidades.findIndex(function(h) { return h.includes("genero") || h.includes("género"); });
      var idxCol = headersUnidades.indexOf("color");
      var idxTal = headersUnidades.indexOf("talla");
      var idxTurno = headersUnidades.findIndex(function(h) { return h === "turno" || h.indexOf("turno") === 0; });

      var colDiasIdx = [
        {dia: "Lunes", idx: headersUnidades.findIndex(function(h) { return h.includes("lunes"); }), claveObj: "lunes"},
        {dia: "Martes", idx: headersUnidades.findIndex(function(h) { return h.includes("martes"); }), claveObj: "martes"},
        {dia: "Miércoles", idx: headersUnidades.findIndex(function(h) { return h.includes("miercoles") || h.includes("miércoles"); }), claveObj: "miercoles"},
        {dia: "Jueves", idx: headersUnidades.findIndex(function(h) { return h.includes("jueves"); }), claveObj: "jueves"},
        {dia: "Viernes", idx: headersUnidades.findIndex(function(h) { return h.includes("viernes"); }), claveObj: "viernes"}
      ];

      var fechasDiasUnidades = {};
      if (filaHeaders > 0) {
        colDiasIdx.forEach(function(dObj) {
          if (dObj.idx !== -1) {
             var valFecha = datosUnidades[filaHeaders - 1][dObj.idx];
             var f = new Date(valFecha);
             if (isNaN(f.getTime()) && typeof valFecha === "string") {
               var partes = valFecha.trim().split(/[\/\-]/);
               if (partes.length === 3) {
                 var y = parseInt(partes[2], 10);
                 if (y < 100) y += 2000;
                 f = new Date(y, parseInt(partes[1], 10) - 1, parseInt(partes[0], 10));
               }
             }
             fechasDiasUnidades[dObj.claveObj] = isNaN(f.getTime()) ? "" : f;
          }
        });
      }

      for (var i = filaHeaders + 1; i < datosUnidades.length; i++) {
        var fila = datosUnidades[i];
        var filaStr = String(fila[idxLinea]).trim().toLowerCase();
        var match = filaStr.match(/\d+/);
        var numLinea = match ? "linea " + match[0] : filaStr;
        if (!numLinea || numLinea === "") continue;

        var turnoFila = clasificarTurno_(idxTurno !== -1 ? fila[idxTurno] : "");
        var etiquetaFila = etiquetaTurno_(turnoFila);
        var prodLinea = asegurarTotalesTurno_(totalesPorTurno, turnoFila, numLinea);

        var mo = idxMo !== -1 ? String(fila[idxMo]).trim() : "";
        var sku = idxSku !== -1 ? String(fila[idxSku]).trim() : "";
        var prodNom = idxProd !== -1 ? String(fila[idxProd]).trim() : "";
        var gen = idxGen !== -1 ? String(fila[idxGen]).trim() : "";
        var color = idxCol !== -1 ? String(fila[idxCol]).trim() : "";
        var talla = idxTal !== -1 ? String(fila[idxTal]).trim() : "";

        colDiasIdx.forEach(function(dObj) {
          if (dObj.idx !== -1) {
            var cantDia = Number(fila[dObj.idx]) || 0;
            if (cantDia > 0) {
              prodLinea[dObj.claveObj] += cantDia;
              registrosDetalle.push([
                dObj.dia,
                fechasDiasUnidades[dObj.claveObj] || "",
                "Línea " + (match ? match[0] : filaStr),
                etiquetaFila,
                mo, sku, prodNom, gen, color, talla, cantDia
              ]);
            }
          }
        });
      }
    }
  }

  // ==============================================================
  // 2. LEER DATOS DE PESTAÑA "PEDIDOS" Y SUMARLOS A LÍNEA 1
  // ==============================================================
  if (hojaPedidos) {
    var datosPedidos = hojaPedidos.getDataRange().getValues();
    if (datosPedidos.length > 0) {
      var detHeadP = encontrarFilaEncabezado_(datosPedidos, ["cantidad", "fecha"], 10);
      var fHeadP = detHeadP.fila;
      var headP = detHeadP.celdas;

      if (fHeadP !== -1) {
        var idCant = headP.findIndex(function(h) { return h.includes("cantidad") && !h.includes("mo"); });
        var idFecha = headP.findIndex(function(h) { return h.includes("fecha"); });
        var idxMoP = headP.findIndex(function(h) { return h === "mo" || h === "m.o." || h.includes("mo "); });
        var idxSkuP = headP.indexOf("sku");
        var idxProdP = headP.findIndex(function(h) { return h === "producto" || h === "modelo"; });
        var idxGenP = headP.findIndex(function(h) { return h.includes("genero") || h.includes("género"); });
        var idxColP = headP.indexOf("color");
        var idxTalP = headP.indexOf("talla");
        var idxTurnoP = headP.findIndex(function(h) { return h === "turno" || h.indexOf("turno") === 0; });

        if (idCant !== -1 && idFecha !== -1) {
          var numLineaP = "linea 1"; // Estricto para Pedidos

          for (var j = fHeadP + 1; j < datosPedidos.length; j++) {
            var filaP = datosPedidos[j];
            var cantidad = Number(filaP[idCant]) || 0;
            var fechaVal = filaP[idFecha];

            if (cantidad > 0 && fechaVal) {
              var turnoP = clasificarTurno_(idxTurnoP !== -1 ? filaP[idxTurnoP] : "");
              var prodLineaP = asegurarTotalesTurno_(totalesPorTurno, turnoP, numLineaP);

              var f = new Date(fechaVal);
              if (!isNaN(f.getTime())) {
                var diaSemana = f.getDay(); // 1=Lunes, 2=Martes, 3=Miercoles, 4=Jueves, 5=Viernes
                var nombreDiaReal = mapaDiasNom[diaSemana] || "Otro";

                if (diaSemana === 1) prodLineaP.lunes += cantidad;
                else if (diaSemana === 2) prodLineaP.martes += cantidad;
                else if (diaSemana === 3) prodLineaP.miercoles += cantidad;
                else if (diaSemana === 4) prodLineaP.jueves += cantidad;
                else if (diaSemana === 5) prodLineaP.viernes += cantidad;

                if (diaSemana >= 1 && diaSemana <= 5) {
                  registrosDetalle.push([
                    nombreDiaReal,
                    f,
                    "Línea 1",
                    etiquetaTurno_(turnoP),
                    idxMoP !== -1 ? String(filaP[idxMoP]).trim() : "",
                    idxSkuP !== -1 ? String(filaP[idxSkuP]).trim() : "",
                    idxProdP !== -1 ? String(filaP[idxProdP]).trim() : "",
                    idxGenP !== -1 ? String(filaP[idxGenP]).trim() : "",
                    idxColP !== -1 ? String(filaP[idxColP]).trim() : "",
                    idxTalP !== -1 ? String(filaP[idxTalP]).trim() : "",
                    cantidad
                  ]);
                }
              }
            }
          }
        }
      }
    }
  }

  // ==============================================================
  // 3. ACTUALIZAR EL TABLERO "TRACKING - PRODUCCION" CON LINKS
  // ==============================================================
  function aplicarEnlace(rango, valor) {
    if (valor > 0) {
      var rtv = SpreadsheetApp.newRichTextValue()
        .setText(String(valor))
        .setLinkUrl("#gid=" + sheetIdDetalle)
        .build();
      rango.setRichTextValue(rtv);
    } else {
      rango.setValue("");
    }
  }

  var datosTracking = hojaTracking.getDataRange().getValues();
  var turnoBloque = "diurno";
  for (var t = 0; t < datosTracking.length; t++) {
    var filaTracking = datosTracking[t];
    var nombreLineaTracking = String(filaTracking[1] == null ? "" : filaTracking[1]).trim();
    var marcaTurno = turnoDeBloque_(nombreLineaTracking);
    if (marcaTurno) {
      turnoBloque = marcaTurno;
      continue;
    }

    var nombreNorm = nombreLineaTracking.toLowerCase();
    if (nombreNorm === "" || (!nombreNorm.includes("linea") && !nombreNorm.includes("línea"))) {
      continue;
    }

    var matchT = nombreNorm.match(/\d+/);
    var numLineaT = matchT ? "linea " + matchT[0] : nombreNorm;
    var mapaTurno = totalesPorTurno[turnoBloque] || {};
    var prod = mapaTurno[numLineaT] || vaciosDiasTracking_();

    aplicarEnlace(hojaTracking.getRange(t + 1, 4), prod.lunes);
    aplicarEnlace(hojaTracking.getRange(t + 1, 6), prod.martes);
    aplicarEnlace(hojaTracking.getRange(t + 1, 8), prod.miercoles);
    aplicarEnlace(hojaTracking.getRange(t + 1, 10), prod.jueves);
    aplicarEnlace(hojaTracking.getRange(t + 1, 12), prod.viernes);

    var totalSemana = prod.lunes + prod.martes + prod.miercoles + prod.jueves + prod.viernes;
    aplicarEnlace(hojaTracking.getRange(t + 1, 14), totalSemana);
  }

  // ==============================================================
  // 4. GUARDAR LOS DESGLOSES EN "DETALLE TRACKING - PRODUCCION"
  // ==============================================================
  if (registrosDetalle.length > 0) {
    registrosDetalle.sort(function(a, b) {
      var timeA = a[1] instanceof Date ? a[1].getTime() : 0;
      var timeB = b[1] instanceof Date ? b[1].getTime() : 0;
      if (timeA !== timeB) return timeA - timeB;
      var lin = String(a[2]).localeCompare(String(b[2]));
      if (lin !== 0) return lin;
      return String(a[3]).localeCompare(String(b[3]));
    });

    var filaDatos = prepDetalle.dataStart;
    var nColsDet = HEADERS_DETALLE_TRACKING_.length;
    var rangoDest = hojaDetalle.getRange(filaDatos, 2, registrosDetalle.length, nColsDet);
    rangoDest.setValues(registrosDetalle)
      .setHorizontalAlignment("center").setVerticalAlignment("middle")
      .setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.SOLID);
    hojaDetalle.getRange(filaDatos, 3, registrosDetalle.length, 1).setNumberFormat("dd/MM/yyyy");
    hojaDetalle.getRange(filaDatos, 6, registrosDetalle.length, 2).setNumberFormat("@");
    hojaDetalle.getRange(filaDatos, 11, registrosDetalle.length, 1).setNumberFormat("@");
    hojaDetalle.getRange(filaDatos, 12, registrosDetalle.length, 1).setNumberFormat("0");
    hojaDetalle.autoResizeColumns(2, nColsDet);
  }

  SpreadsheetApp.getUi().alert("✅ Tableros Actualizados:\n\n1. El tablero diurno y el tablero nocturno ('Tracking - Produccion') se actualizaron según la columna Turno.\n2. La pestaña de desglose ('Detalle Tracking - Produccion') incluye Turno en cada fila.");
}

// =========================================================================
// 2. ACTUALIZAR TABLERO VISUAL DE ESTAMPADO
// =========================================================================
function actualizarTrackingEstampado() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var hojaUnidades = ss.getSheetByName("Unidades Producidas - Estampado");
  var hojaTracking = ss.getSheetByName("Tracking Produccion - Estampado");

  if (!hojaUnidades || !hojaTracking) {
    SpreadsheetApp.getUi().alert("Faltan las hojas 'Unidades Producidas - Estampado' o 'Tracking Produccion - Estampado'.");
    return;
  }

  var datosUnidades = hojaUnidades.getDataRange().getValues();
  var totalesPorEquipo = {};

  if (datosUnidades.length > 0) {
    var filaHeaders = -1;
    var headersUnidades = [];

    for (var r = 0; r < Math.min(10, datosUnidades.length); r++) {
      var tempHeaders = datosUnidades[r].map(function(h) { return String(h).trim().toLowerCase(); });
      if (tempHeaders.some(function(h) { return h.includes("plancha") || h.includes("equipo"); }) &&
          tempHeaders.some(function(h) { return h.includes("lunes"); })) {
        filaHeaders = r;
        headersUnidades = tempHeaders;
        break;
      }
    }

    if (filaHeaders !== -1) {
      var idxPlancha = headersUnidades.findIndex(function(h) { return h.includes("plancha") || h.includes("equipo"); });
      var idxLunes = headersUnidades.findIndex(function(h) { return h.includes("lunes"); });
      var idxMartes = headersUnidades.findIndex(function(h) { return h.includes("martes"); });
      var idxMiercoles = headersUnidades.findIndex(function(h) { return h.includes("miercoles") || h.includes("miércoles"); });
      var idxJueves = headersUnidades.findIndex(function(h) { return h.includes("jueves"); });
      var idxViernes = headersUnidades.findIndex(function(h) { return h.includes("viernes"); });

      for (var i = filaHeaders + 1; i < datosUnidades.length; i++) {
        var filaStr = String(datosUnidades[i][idxPlancha]).trim().toLowerCase();
        var match = filaStr.match(/\d+/);
        var numEquipo = match ? "equipo " + match[0] : filaStr;

        if (!numEquipo || numEquipo === "") continue;

        if (!totalesPorEquipo[numEquipo]) {
          totalesPorEquipo[numEquipo] = { lunes: 0, martes: 0, miercoles: 0, jueves: 0, viernes: 0 };
        }

        totalesPorEquipo[numEquipo].lunes += Number(datosUnidades[i][idxLunes]) || 0;
        totalesPorEquipo[numEquipo].martes += Number(datosUnidades[i][idxMartes]) || 0;
        totalesPorEquipo[numEquipo].miercoles += Number(datosUnidades[i][idxMiercoles]) || 0;
        totalesPorEquipo[numEquipo].jueves += Number(datosUnidades[i][idxJueves]) || 0;
        totalesPorEquipo[numEquipo].viernes += Number(datosUnidades[i][idxViernes]) || 0;
      }
    }
  }

  var datosTracking = hojaTracking.getDataRange().getValues();

  for (var t = 0; t < datosTracking.length; t++) {
    var filaTracking = datosTracking[t];
    var nombreEquipoTracking = String(filaTracking[1]).trim().toLowerCase();

    if (nombreEquipoTracking === "" || !nombreEquipoTracking.includes("equipo")) continue;

    var matchT = nombreEquipoTracking.match(/\d+/);
    var numEquipoT = matchT ? "equipo " + matchT[0] : nombreEquipoTracking;

    var prod = totalesPorEquipo[numEquipoT] || { lunes: 0, martes: 0, miercoles: 0, jueves: 0, viernes: 0 };

    hojaTracking.getRange(t + 1, 4).setValue(prod.lunes > 0 ? prod.lunes : "");
    hojaTracking.getRange(t + 1, 6).setValue(prod.martes > 0 ? prod.martes : "");
    hojaTracking.getRange(t + 1, 8).setValue(prod.miercoles > 0 ? prod.miercoles : "");
    hojaTracking.getRange(t + 1, 10).setValue(prod.jueves > 0 ? prod.jueves : "");
    hojaTracking.getRange(t + 1, 12).setValue(prod.viernes > 0 ? prod.viernes : "");

    var totalSemana = prod.lunes + prod.martes + prod.miercoles + prod.jueves + prod.viernes;
    hojaTracking.getRange(t + 1, 14).setValue(totalSemana > 0 ? totalSemana : "");
  }

  SpreadsheetApp.getUi().alert("✅ Tablero Actualizado: Se han consolidado las unidades reales de Estampado agrupadas por Equipo.");
}

// =========================================================================
// 3. ENVIAR HISTORIAL A PLANIFICACIÓN CENTRAL (COSTURA)
// =========================================================================
function guardarHistorialProduccionDiario() {
  var ui = SpreadsheetApp.getUi();
  var respuesta = ui.alert(
    "💾 Enviar a Historial (COSTURA)",
    "¿Deseas enviar la producción registrada de COSTURA al archivo de Planificación?\n\nSe identificará la fecha exacta de cada día y se enviarán solo las cantidades nuevas.",
    ui.ButtonSet.YES_NO
  );

  if (respuesta !== ui.Button.YES) return;

  var ssTracking = SpreadsheetApp.getActiveSpreadsheet();
  var hojaTracking = ssTracking.getSheetByName("Unidades Producidas - Costura");

  if (!hojaTracking) {
    ui.alert("🛑 Error: No se encontró la hoja 'Unidades Producidas - Costura'.");
    return;
  }

  var datosCompletos = hojaTracking.getDataRange().getValues();
  if (datosCompletos.length < 2) {
    ui.alert("No hay datos para guardar.");
    return;
  }

  var filaHeaders = -1;
  var headers = [];

  for (var r = 0; r < Math.min(10, datosCompletos.length); r++) {
    var filaTmp = datosCompletos[r].map(function(h) { return String(h).trim().toLowerCase(); });
    if (filaTmp.indexOf("sku") !== -1 && filaTmp.indexOf("total producido") !== -1) {
      filaHeaders = r;
      headers = filaTmp;
      break;
    }
  }

  if (filaHeaders === -1) {
    ui.alert("🛑 Error de estructura: Faltan columnas clave (SKU o Total Producido).");
    return;
  }

  var idxMo = headers.indexOf("mo");
  var idxSku = headers.indexOf("sku");
  var idxProd = headers.indexOf("producto");
  var idxGen = headers.indexOf("genero");
  var idxCol = headers.indexOf("color");
  var idxTal = headers.indexOf("talla");
  var idxLin = headers.indexOf("linea");
  var idxTotal = headers.indexOf("total producido");
  var idxExportado = headers.indexOf("total exportado");

  var idxLunes = headers.indexOf("lunes");
  var idxMartes = headers.indexOf("martes");
  var idxMiercoles = headers.indexOf("miércoles") !== -1 ? headers.indexOf("miércoles") : headers.indexOf("miercoles");
  var idxJueves = headers.indexOf("jueves");
  var idxViernes = headers.indexOf("viernes");

  var diasSemanaIdx = [idxLunes, idxMartes, idxMiercoles, idxJueves, idxViernes];
  var fechasDias = [];
  var fechaFallback = new Date();

  for (var d = 0; d < diasSemanaIdx.length; d++) {
    var colIdx = diasSemanaIdx[d];
    if (colIdx !== -1 && filaHeaders > 0) {
      var valFecha = datosCompletos[filaHeaders - 1][colIdx];
      var f = new Date(valFecha);

      if (isNaN(f.getTime()) && typeof valFecha === "string") {
         var partes = valFecha.trim().split(/[\/\-]/);
         if (partes.length === 3) {
            var y = parseInt(partes[2], 10);
            if (y < 100) y += 2000;
            f = new Date(y, parseInt(partes[1], 10) - 1, parseInt(partes[0], 10));
         }
      }
      fechasDias.push(isNaN(f.getTime()) ? fechaFallback : f);
    } else {
      fechasDias.push(fechaFallback);
    }
  }

  if (idxExportado === -1) {
    idxExportado = 14;
    hojaTracking.getRange(filaHeaders + 1, idxExportado + 1).setValue("Total Exportado")
      .setBackground("#434343").setFontColor("#FFFFFF").setFontWeight("bold")
      .setHorizontalAlignment("center");
  }

  var datosAGuardar = [];
  var actualizacionExportados = [];

  for (var i = filaHeaders + 1; i < datosCompletos.length; i++) {
    var fila = datosCompletos[i];

    var mo = idxMo !== -1 ? String(fila[idxMo] || "").trim() : "";
    var sku = idxSku !== -1 ? String(fila[idxSku] || "").trim() : "";
    var totalProducido = Number(fila[idxTotal]) || 0;
    var totalExportadoPrevio = idxExportado < fila.length ? (Number(fila[idxExportado]) || 0) : 0;

    if (mo === "" && sku === "" && totalProducido === 0 && totalExportadoPrevio === 0) {
      actualizacionExportados.push([""]);
      continue;
    }

    var cantidadNueva = totalProducido - totalExportadoPrevio;

    if (cantidadNueva > 0) {
      var producto = idxProd !== -1 ? fila[idxProd] : "";
      var genero = idxGen !== -1 ? fila[idxGen] : "";
      var color = idxCol !== -1 ? fila[idxCol] : "";
      var talla = idxTal !== -1 ? fila[idxTal] : "";
      var linea = idxLin !== -1 ? fila[idxLin] : "";

      var exportadoRestante = totalExportadoPrevio;
      var piezasDistribuidas = 0;

      for (var k = 0; k < diasSemanaIdx.length; k++) {
        var cIdx = diasSemanaIdx[k];
        if (cIdx === -1) continue;

        var prodDia = Number(fila[cIdx]) || 0;
        if (prodDia <= 0) continue;

        if (exportadoRestante >= prodDia) {
          exportadoRestante -= prodDia;
        } else {
          var cantAExportar = prodDia - exportadoRestante;
          exportadoRestante = 0;
          datosAGuardar.push([mo, sku, producto, genero, color, talla, linea, cantAExportar, fechasDias[k]]);
          piezasDistribuidas += cantAExportar;
        }
      }

      if (piezasDistribuidas < cantidadNueva) {
        var remanente = cantidadNueva - piezasDistribuidas;
        datosAGuardar.push([mo, sku, producto, genero, color, talla, linea, remanente, fechaFallback]);
      }
      actualizacionExportados.push([totalProducido]);
    } else {
      actualizacionExportados.push([totalExportadoPrevio === 0 ? "" : totalExportadoPrevio]);
    }
  }

  if (datosAGuardar.length === 0) {
    hojaTracking.hideColumns(idxExportado + 1);
    ui.alert("⚠️ Todo está al día. No se detectaron cantidades de producción nuevas desde el último envío.");
    return;
  }

  var idPlanificacion = "1VqJ4GFKXGAflRmeyk_eDF_x9UdVb-i38rGZsxxMNEgI";
  var ssPlanificacion;
  try {
    ssPlanificacion = SpreadsheetApp.openById(idPlanificacion);
  } catch(e) {
    ui.alert("🛑 Error de Conexión: No se pudo acceder al archivo de Planificación. Verifica los permisos.");
    return;
  }

  var hojaDestino = ssPlanificacion.getSheetByName("Produccion - Costura");
  if (!hojaDestino) {
    var sheets = ssPlanificacion.getSheets();
    for (var s = 0; s < sheets.length; s++) {
      var sName = sheets[s].getName().toLowerCase().replace(/á/g, 'a').replace(/é/g, 'e').replace(/í/g, 'i').replace(/ó/g, 'o').replace(/ú/g, 'u').trim();
      if (sName.indexOf("produccion") !== -1 && sName.indexOf("costura") !== -1) {
        hojaDestino = sheets[s];
        break;
      }
    }
  }

  if (!hojaDestino) {
    ui.alert("🛑 Error: No se encontró la pestaña 'Produccion - Costura' en el archivo maestro.");
    return;
  }

  var ultFilaDestino = hojaDestino.getLastRow();
  var filaInicioDestino = ultFilaDestino < 2 ? 3 : ultFilaDestino + 1;

  var rangoDestino = hojaDestino.getRange(filaInicioDestino, 2, datosAGuardar.length, datosAGuardar[0].length);
  rangoDestino.setValues(datosAGuardar);

  hojaDestino.getRange(filaInicioDestino, 10, datosAGuardar.length, 1).setNumberFormat("dd/MM/yyyy");
  rangoDestino.setHorizontalAlignment("center").setVerticalAlignment("middle")
    .setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.SOLID);

  var rangoExportado = hojaTracking.getRange(filaHeaders + 2, idxExportado + 1, actualizacionExportados.length, 1);
  rangoExportado.setValues(actualizacionExportados)
    .setHorizontalAlignment("center").setVerticalAlignment("middle")
    .setBackground("#f3f4f6");

  hojaTracking.hideColumns(idxExportado + 1);

  ui.alert("✅ Sincronización Exitosa", "Se registraron " + datosAGuardar.length + " ingresos de Costura en el historial maestro.", ui.ButtonSet.OK);
}

// =========================================================================
// 4. ENVIAR HISTORIAL A PLANIFICACIÓN CENTRAL (ESTAMPADO)
// =========================================================================
function guardarHistorialEstampadoDiario() {
  var ui = SpreadsheetApp.getUi();
  var respuesta = ui.alert(
    "💾 Enviar a Historial (ESTAMPADO)",
    "¿Deseas enviar la producción registrada de ESTAMPADO al archivo de Planificación?\n\nSe identificará la fecha exacta de cada día trabajado y se enviarán solo las cantidades nuevas.",
    ui.ButtonSet.YES_NO
  );

  if (respuesta !== ui.Button.YES) return;

  var ssTracking = SpreadsheetApp.getActiveSpreadsheet();
  var hojaTracking = ssTracking.getSheetByName("Unidades Producidas - Estampado");

  if (!hojaTracking) {
    ui.alert("🛑 Error: No se encontró la hoja 'Unidades Producidas - Estampado'.");
    return;
  }

  var datosCompletos = hojaTracking.getDataRange().getValues();
  if (datosCompletos.length < 2) {
    ui.alert("No hay datos para guardar.");
    return;
  }

  var filaHeaders = -1;
  var headers = [];

  for (var r = 0; r < Math.min(10, datosCompletos.length); r++) {
    var filaTmp = datosCompletos[r].map(function(h) { return String(h).trim().toLowerCase(); });
    if (filaTmp.indexOf("sku") !== -1 && filaTmp.indexOf("total producido") !== -1) {
      filaHeaders = r;
      headers = filaTmp;
      break;
    }
  }

  if (filaHeaders === -1) {
    ui.alert("🛑 Error de estructura: Faltan columnas clave (SKU o Total Producido).");
    return;
  }

  var idxMo = headers.indexOf("mo");
  var idxSku = headers.indexOf("sku");
  var idxProd = headers.indexOf("producto");
  var idxGen = headers.indexOf("genero");
  var idxCol = headers.indexOf("color");
  var idxTal = headers.indexOf("talla");
  var idxLin = headers.indexOf("linea");
  var idxPlancha = headers.findIndex(function(h) { return h.includes("plancha") || h.includes("equipo"); });
  var idxTotal = headers.indexOf("total producido");
  var idxExportado = headers.indexOf("total exportado");

  var idxLunes = headers.indexOf("lunes");
  var idxMartes = headers.indexOf("martes");
  var idxMiercoles = headers.indexOf("miércoles") !== -1 ? headers.indexOf("miércoles") : headers.indexOf("miercoles");
  var idxJueves = headers.indexOf("jueves");
  var idxViernes = headers.indexOf("viernes");

  var diasSemanaIdx = [idxLunes, idxMartes, idxMiercoles, idxJueves, idxViernes];
  var fechasDias = [];
  var fechaFallback = new Date();

  for (var d = 0; d < diasSemanaIdx.length; d++) {
    var colIdx = diasSemanaIdx[d];
    if (colIdx !== -1 && filaHeaders > 0) {
      var valFecha = datosCompletos[filaHeaders - 1][colIdx];
      var f = new Date(valFecha);

      if (isNaN(f.getTime()) && typeof valFecha === "string") {
         var partes = valFecha.trim().split(/[\/\-]/);
         if (partes.length === 3) {
            var y = parseInt(partes[2], 10);
            if (y < 100) y += 2000;
            f = new Date(y, parseInt(partes[1], 10) - 1, parseInt(partes[0], 10));
         }
      }
      fechasDias.push(isNaN(f.getTime()) ? fechaFallback : f);
    } else {
      fechasDias.push(fechaFallback);
    }
  }

  if (idxExportado === -1) {
    idxExportado = 15;
    hojaTracking.getRange(filaHeaders + 1, idxExportado + 1).setValue("Total Exportado")
      .setBackground("#434343").setFontColor("#FFFFFF").setFontWeight("bold")
      .setHorizontalAlignment("center");
  }

  var datosAGuardar = [];
  var actualizacionExportados = [];

  for (var i = filaHeaders + 1; i < datosCompletos.length; i++) {
    var fila = datosCompletos[i];

    var mo = idxMo !== -1 ? String(fila[idxMo] || "").trim() : "";
    var sku = idxSku !== -1 ? String(fila[idxSku] || "").trim() : "";
    var totalProducido = Number(fila[idxTotal]) || 0;
    var totalExportadoPrevio = idxExportado < fila.length ? (Number(fila[idxExportado]) || 0) : 0;

    if (mo === "" && sku === "" && totalProducido === 0 && totalExportadoPrevio === 0) {
      actualizacionExportados.push([""]);
      continue;
    }

    var cantidadNueva = totalProducido - totalExportadoPrevio;

    if (cantidadNueva > 0) {
      var producto = idxProd !== -1 ? fila[idxProd] : "";
      var genero = idxGen !== -1 ? fila[idxGen] : "";
      var color = idxCol !== -1 ? fila[idxCol] : "";
      var talla = idxTal !== -1 ? fila[idxTal] : "";
      var linea = idxLin !== -1 ? fila[idxLin] : "";
      var plancha = idxPlancha !== -1 ? fila[idxPlancha] : "";

      var exportadoRestante = totalExportadoPrevio;
      var piezasDistribuidas = 0;

      for (var k = 0; k < diasSemanaIdx.length; k++) {
        var cIdx = diasSemanaIdx[k];
        if (cIdx === -1) continue;

        var prodDia = Number(fila[cIdx]) || 0;
        if (prodDia <= 0) continue;

        if (exportadoRestante >= prodDia) {
          exportadoRestante -= prodDia;
        } else {
          var cantAExportar = prodDia - exportadoRestante;
          exportadoRestante = 0;
          datosAGuardar.push([mo, sku, producto, genero, color, talla, linea, plancha, cantAExportar, fechasDias[k]]);
          piezasDistribuidas += cantAExportar;
        }
      }

      if (piezasDistribuidas < cantidadNueva) {
        var remanente = cantidadNueva - piezasDistribuidas;
        datosAGuardar.push([mo, sku, producto, genero, color, talla, linea, plancha, remanente, fechaFallback]);
      }
      actualizacionExportados.push([totalProducido]);
    } else {
      actualizacionExportados.push([totalExportadoPrevio === 0 ? "" : totalExportadoPrevio]);
    }
  }

  if (datosAGuardar.length === 0) {
    hojaTracking.hideColumns(idxExportado + 1);
    ui.alert("⚠️ Todo está al día. No se detectaron cantidades de producción de Estampado nuevas desde el último envío.");
    return;
  }

  var idPlanificacion = "1VqJ4GFKXGAflRmeyk_eDF_x9UdVb-i38rGZsxxMNEgI";
  var ssPlanificacion;
  try {
    ssPlanificacion = SpreadsheetApp.openById(idPlanificacion);
  } catch(e) {
    ui.alert("🛑 Error de Conexión: No se pudo acceder al archivo de Planificación. Verifica los permisos.");
    return;
  }

  var hojaDestino = ssPlanificacion.getSheetByName("Produccion - Estampado");
  if (!hojaDestino) {
    var sheets = ssPlanificacion.getSheets();
    for (var s = 0; s < sheets.length; s++) {
      var sName = sheets[s].getName().toLowerCase().replace(/á/g, 'a').replace(/é/g, 'e').replace(/í/g, 'i').replace(/ó/g, 'o').replace(/ú/g, 'u').trim();
      if (sName.indexOf("produccion") !== -1 && sName.indexOf("estampado") !== -1) {
        hojaDestino = sheets[s];
        break;
      }
    }
  }

  if (!hojaDestino) {
    ui.alert("🛑 Error: No se encontró la pestaña 'Produccion - Estampado' en el archivo maestro.");
    return;
  }

  var ultFilaDestino = hojaDestino.getLastRow();
  var filaInicioDestino = ultFilaDestino < 2 ? 3 : ultFilaDestino + 1;

  var rangoDestino = hojaDestino.getRange(filaInicioDestino, 2, datosAGuardar.length, datosAGuardar[0].length);
  rangoDestino.setValues(datosAGuardar);

  hojaDestino.getRange(filaInicioDestino, 11, datosAGuardar.length, 1).setNumberFormat("dd/MM/yyyy");
  rangoDestino.setHorizontalAlignment("center").setVerticalAlignment("middle")
    .setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.SOLID);

  var rangoExportado = hojaTracking.getRange(filaHeaders + 2, idxExportado + 1, actualizacionExportados.length, 1);
  rangoExportado.setValues(actualizacionExportados)
    .setHorizontalAlignment("center").setVerticalAlignment("middle")
    .setBackground("#f3f4f6");

  hojaTracking.hideColumns(idxExportado + 1);

  ui.alert("✅ Sincronización Exitosa", "Se registraron " + datosAGuardar.length + " ingresos de Estampado en el historial maestro.", ui.ButtonSet.OK);
}

// =========================================================================
// 5. ENVIAR HISTORIAL A PLANIFICACIÓN CENTRAL (ALMACÉN)
// =========================================================================
function guardarHistorialAlmacenDiario() {
  var ui = SpreadsheetApp.getUi();
  var respuesta = ui.alert(
    "💾 Enviar a Historial (ALMACÉN)",
    "¿Deseas enviar la recepción registrada de ALMACÉN al archivo maestro de Planificación?\n\nSe enviarán solo las cantidades nuevas (Ingresada) identificadas.",
    ui.ButtonSet.YES_NO
  );

  if (respuesta !== ui.Button.YES) return;

  var ssTracking = SpreadsheetApp.getActiveSpreadsheet();
  var hojaTracking = ssTracking.getSheetByName("Entrada a Almacen");

  if (!hojaTracking) {
    ui.alert("🛑 Error: No se encontró la hoja 'Entrada a Almacen'.");
    return;
  }

  var datosCompletos = hojaTracking.getDataRange().getValues();
  if (datosCompletos.length < 2) {
    ui.alert("No hay datos para guardar.");
    return;
  }

  var filaHeaders = -1;
  var headers = [];

  for (var r = 0; r < Math.min(10, datosCompletos.length); r++) {
    var filaTmp = datosCompletos[r].map(function(h) { return String(h).trim().toLowerCase(); });
    if (filaTmp.indexOf("sku") !== -1 && filaTmp.findIndex(function(h) { return h.includes("ingresada"); }) !== -1) {
      filaHeaders = r;
      headers = filaTmp;
      break;
    }
  }

  if (filaHeaders === -1) {
    ui.alert("🛑 Error de estructura: Faltan columnas clave (SKU o Ingresada).");
    return;
  }

  var idxMo = headers.indexOf("mo");
  var idxSku = headers.indexOf("sku");
  var idxProd = headers.indexOf("producto");
  var idxGen = headers.indexOf("genero");
  if (idxGen === -1) idxGen = headers.indexOf("género");
  var idxCol = headers.indexOf("color");
  var idxTal = headers.indexOf("talla");
  var idxIngresada = headers.findIndex(function(h) { return h.includes("ingresada"); });
  var idxFecha = headers.findIndex(function(h) { return h.includes("fecha"); });
  var idxExportado = headers.indexOf("total exportado");

  if (idxExportado === -1) {
    idxExportado = headers.length;
    hojaTracking.getRange(filaHeaders + 1, idxExportado + 1).setValue("Total Exportado")
      .setBackground("#434343").setFontColor("#FFFFFF").setFontWeight("bold")
      .setHorizontalAlignment("center");
  }

  var datosAGuardar = [];
  var actualizacionExportados = [];
  var fechaFallback = new Date();

  for (var i = filaHeaders + 1; i < datosCompletos.length; i++) {
    var fila = datosCompletos[i];

    var mo = idxMo !== -1 ? String(fila[idxMo] || "").trim() : "";
    var sku = idxSku !== -1 ? String(fila[idxSku] || "").trim() : "";
    var totalIngresado = Number(fila[idxIngresada]) || 0;
    var totalExportadoPrevio = idxExportado < fila.length ? (Number(fila[idxExportado]) || 0) : 0;

    if (mo === "" && sku === "" && totalIngresado === 0 && totalExportadoPrevio === 0) {
      actualizacionExportados.push([""]);
      continue;
    }

    var cantidadNueva = totalIngresado - totalExportadoPrevio;

    if (cantidadNueva > 0) {
      var producto = idxProd !== -1 ? fila[idxProd] : "";
      var genero = idxGen !== -1 ? fila[idxGen] : "";
      var color = idxCol !== -1 ? fila[idxCol] : "";
      var talla = idxTal !== -1 ? fila[idxTal] : "";

      var fechaFila = idxFecha !== -1 ? fila[idxFecha] : "";
      var fechaEntrada = fechaFallback;
      if (fechaFila instanceof Date && !isNaN(fechaFila.getTime())) {
        fechaEntrada = fechaFila;
      } else if (typeof fechaFila === "string" && fechaFila.trim() !== "") {
         var partes = fechaFila.trim().split(/[\/\-]/);
         if (partes.length === 3) {
            var y = parseInt(partes[2], 10);
            if (y < 100) y += 2000;
            fechaEntrada = new Date(y, parseInt(partes[1], 10) - 1, parseInt(partes[0], 10));
         }
      }

      datosAGuardar.push([mo, sku, producto, genero, color, talla, cantidadNueva, fechaEntrada]);
      actualizacionExportados.push([totalIngresado]);

    } else {
      actualizacionExportados.push([totalExportadoPrevio === 0 ? "" : totalExportadoPrevio]);
    }
  }

  if (datosAGuardar.length === 0) {
    hojaTracking.hideColumns(idxExportado + 1);
    ui.alert("⚠️ Todo está al día. No se detectaron cantidades nuevas en Almacén desde el último envío.");
    return;
  }

  var idPlanificacion = "1VqJ4GFKXGAflRmeyk_eDF_x9UdVb-i38rGZsxxMNEgI";
  var ssPlanificacion;
  try {
    ssPlanificacion = SpreadsheetApp.openById(idPlanificacion);
  } catch(e) {
    ui.alert("🛑 Error de Conexión: No se pudo acceder al archivo maestro de Planificación. Verifica los permisos.");
    return;
  }

  var hojaDestino = ssPlanificacion.getSheetByName("Entrada a almacen - Validación");

  if (!hojaDestino) {
    var sheets = ssPlanificacion.getSheets();
    for (var s = 0; s < sheets.length; s++) {
      var sName = sheets[s].getName().toLowerCase()
                    .replace(/á/g, 'a')
                    .replace(/é/g, 'e')
                    .replace(/í/g, 'i')
                    .replace(/ó/g, 'o')
                    .replace(/ú/g, 'u').trim();
      if (sName.indexOf("entrada") !== -1 && sName.indexOf("almacen") !== -1 && sName.indexOf("valida") !== -1) {
        hojaDestino = sheets[s];
        break;
      }
    }
  }

  if (!hojaDestino) {
    ui.alert("🛑 Error: No se encontró la pestaña 'Entrada a almacen - Validación' en el archivo maestro. Verifica que la pestaña realmente exista.");
    return;
  }

  var ultFilaDestino = hojaDestino.getLastRow();
  var filaInicioDestino = ultFilaDestino < 2 ? 3 : ultFilaDestino + 1;

  var rangoDestino = hojaDestino.getRange(filaInicioDestino, 2, datosAGuardar.length, 8);
  rangoDestino.setValues(datosAGuardar);
  hojaDestino.getRange(filaInicioDestino, 9, datosAGuardar.length, 1).setNumberFormat("dd/MM/yyyy");
  rangoDestino.setHorizontalAlignment("center").setVerticalAlignment("middle")
    .setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.SOLID);

  var rangoExportado = hojaTracking.getRange(filaHeaders + 2, idxExportado + 1, actualizacionExportados.length, 1);
  rangoExportado.setValues(actualizacionExportados)
    .setHorizontalAlignment("center").setVerticalAlignment("middle")
    .setBackground("#f3f4f6");

  hojaTracking.hideColumns(idxExportado + 1);

  ui.alert("✅ Sincronización Exitosa", "Se registraron " + datosAGuardar.length + " nuevos ingresos de Almacén en el historial de validación.", ui.ButtonSet.OK);
}


// =========================================================================
// 5b. PERMISOS DE CORREO (OAuth: script.send_mail + gmail.send)
// =========================================================================
var NOMBRE_HISTORIAL_CORREO_ = "_Correo Enviado";
var ASUNTO_REPORTE_CORREO_ = "Reporte de Producción Diaria y Proyección a Almacén";

function textoPlanoDeHtml_(html) {
  return String(html)
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/p>/gi, "\n")
    .replace(/<\/h[1-6]>/gi, "\n")
    .replace(/<\/tr>/gi, "\n")
    .replace(/<\/(td|th)>/gi, " | ")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function escapeHtml_(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function pad2_(n) {
  return (n < 10 ? "0" : "") + n;
}

function esFechaObjeto_(val) {
  return Object.prototype.toString.call(val) === "[object Date]" && !isNaN(val.getTime());
}

function normalizarFechaClave_(val) {
  // Date-only cells from Sheets are UTC midnight of the calendar day.
  // getDate() in America/Lima turns 2026-10-05 into 2026-10-04 and breaks the historial.
  if (esFechaObjeto_(val)) {
    return val.getUTCFullYear() + "-" + pad2_(val.getUTCMonth() + 1) + "-" + pad2_(val.getUTCDate());
  }
  var s = String(val == null ? "" : val).trim();
  var m = s.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})$/);
  if (m) {
    var y = parseInt(m[3], 10);
    if (y < 100) y += 2000;
    return y + "-" + pad2_(parseInt(m[2], 10)) + "-" + pad2_(parseInt(m[1], 10));
  }
  return s.toLowerCase();
}

var MAX_CANTIDAD_CORREO_ = 100000;

function numeroCantidadOk_(n) {
  return typeof n === "number" && isFinite(n) && n >= 0 && n < MAX_CANTIDAD_CORREO_;
}

function numeroCantidad_(val, display) {
  if (typeof val === "number" && isFinite(val)) {
    return numeroCantidadOk_(val) ? val : 0;
  }
  if (display != null) {
    var ds = String(display).trim().replace(/\s/g, "").replace(",", ".");
    if (/^[0-9]+(\.[0-9]+)?$/.test(ds)) {
      var dn = Number(ds);
      if (numeroCantidadOk_(dn)) return dn;
    }
  }
  if (esFechaObjeto_(val)) {
    // Cell was stored as a number (p. ej. 5) then formatted as date → getValues() returns Date.
    // Never use Number(date) (milliseconds). Recover the Sheets serial, with the 1900 leap bug.
    var utcMidnight = Date.UTC(val.getUTCFullYear(), val.getUTCMonth(), val.getUTCDate());
    var epoch = Date.UTC(1899, 11, 30);
    var serial = Math.round((utcMidnight - epoch) / 86400000);
    if (serial > 0 && serial < 61) serial -= 1;
    return numeroCantidadOk_(serial) ? serial : 0;
  }
  var s = String(val == null ? "" : val).trim().replace(",", ".");
  var n = Number(s);
  return numeroCantidadOk_(n) ? n : 0;
}

function normalizarMoClave_(val) {
  var s = String(val == null ? "" : val).trim().toLowerCase();
  if (/^\d+$/.test(s)) return String(parseInt(s, 10));
  return s;
}

function normalizarTallaClave_(val) {
  if (typeof val === "number" && isFinite(val)) {
    return String(val === Math.floor(val) ? Math.floor(val) : val);
  }
  if (esFechaObjeto_(val)) {
    var n = numeroCantidad_(val);
    return n ? String(n) : "";
  }
  return String(val == null ? "" : val).trim().toLowerCase();
}

function fechasVecinasClave_(yyyyMmDd) {
  var s = String(yyyyMmDd || "");
  var m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return [s];
  var t = Date.UTC(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10));
  function fmt(ms) {
    var d = new Date(ms);
    return d.getUTCFullYear() + "-" + pad2_(d.getUTCMonth() + 1) + "-" + pad2_(d.getUTCDate());
  }
  return [fmt(t), fmt(t - 86400000), fmt(t + 86400000)];
}

function lineaClaveCorreo_(s) {
  var t = quitarTildes_(String(s || "").toLowerCase());
  var m = t.match(/(\d+)/);
  if ((t.indexOf("linea") !== -1 || t.indexOf("línea") !== -1) && m) return "linea " + m[1];
  return t.replace(/\s+/g, " ").trim();
}

function diaClaveCorreo_(s) {
  return quitarTildes_(String(s || "").toLowerCase()).replace(/\s+/g, " ").trim();
}

function turnoClaveCorreo_(s) {
  return clasificarTurno_(s);
}

function migrarClaveHistorialCorreo_(clave) {
  var parts = String(clave || "").split("|");
  if (parts.length === 9) {
    parts.splice(3, 0, "diurno");
    return parts.join("|");
  }
  return clave;
}

function claveDetalleCorreo_(fila) {
  return [
    diaClaveCorreo_(fila.dia),
    normalizarFechaClave_(fila.fecha),
    lineaClaveCorreo_(fila.linea),
    turnoClaveCorreo_(fila.turno),
    normalizarMoClave_(fila.mo),
    String(fila.sku == null ? "" : fila.sku).trim().toLowerCase(),
    String(fila.producto == null ? "" : fila.producto).trim().toLowerCase(),
    String(fila.genero == null ? "" : fila.genero).trim().toLowerCase(),
    String(fila.color == null ? "" : fila.color).trim().toLowerCase(),
    normalizarTallaClave_(fila.talla)
  ].join("|");
}

function claveEstableCorreo_(fila) {
  var fecha = normalizarFechaClave_(fila.fecha);
  var linea = lineaClaveCorreo_(fila.linea);
  var turno = turnoClaveCorreo_(fila.turno);
  var mo = normalizarMoClave_(fila.mo);
  var sku = String(fila.sku == null ? "" : fila.sku).trim().toLowerCase();
  var talla = normalizarTallaClave_(fila.talla);
  if (sku) return ["sku", fecha, linea, turno, mo, sku, talla].join("|");
  return [
    "nosku", fecha, linea, turno, mo,
    String(fila.producto == null ? "" : fila.producto).trim().toLowerCase(),
    String(fila.genero == null ? "" : fila.genero).trim().toLowerCase(),
    String(fila.color == null ? "" : fila.color).trim().toLowerCase(),
    talla
  ].join("|");
}

function ponerCantidadMapa_(map, clave, cant) {
  if (!clave) return;
  map[clave] = Math.max(numeroCantidad_(map[clave]), numeroCantidad_(cant));
}

function estableDesdePartesClave_(parts) {
  if (!parts || parts.length !== 10) return "";
  if (parts[5]) return ["sku", parts[1], parts[2], parts[3], parts[4], parts[5], parts[9]].join("|");
  return ["nosku", parts[1], parts[2], parts[3], parts[4], parts[6], parts[7], parts[8], parts[9]].join("|");
}

function registrarCantidadMapa_(map, clave, fila, cant) {
  ponerCantidadMapa_(map, clave, cant);
  var migrada = migrarClaveHistorialCorreo_(clave);
  ponerCantidadMapa_(map, migrada, cant);
  var parts = String(migrada).split("|");
  ponerCantidadMapa_(map, estableDesdePartesClave_(parts), cant);
  if (parts.length === 10) {
    var sinProd = parts.slice();
    sinProd[6] = "";
    ponerCantidadMapa_(map, sinProd.join("|"), cant);
  }
  if (!fila) return;
  ponerCantidadMapa_(map, claveDetalleCorreo_(fila), cant);
  ponerCantidadMapa_(map, claveEstableCorreo_(fila), cant);
  var reb = claveDetalleCorreo_(fila).split("|");
  if (reb.length === 10) {
    var sinReb = reb.slice();
    sinReb[6] = "";
    ponerCantidadMapa_(map, sinReb.join("|"), cant);
  }
}

function clavesBusquedaCorreo_(fila) {
  var base = fila.clave || claveDetalleCorreo_(fila);
  var out = [];
  function add(k) {
    if (k && out.indexOf(k) === -1) out.push(k);
  }
  add(base);
  add(migrarClaveHistorialCorreo_(base));
  add(claveDetalleCorreo_(fila));
  add(claveEstableCorreo_(fila));
  var parts = String(base).split("|");
  if (parts.length === 10) {
    var fechas = fechasVecinasClave_(parts[1]);
    for (var i = 0; i < fechas.length; i++) {
      var p = parts.slice();
      p[1] = fechas[i];
      add(p.join("|"));
      var sinProd = p.slice();
      sinProd[6] = "";
      add(sinProd.join("|"));
    }
  }
  return out;
}

function cantidadEnviadaDeMapa_(map, fila) {
  var keys = clavesBusquedaCorreo_(fila);
  var best = 0;
  for (var i = 0; i < keys.length; i++) {
    if (!Object.prototype.hasOwnProperty.call(map, keys[i])) continue;
    var n = numeroCantidad_(map[keys[i]]);
    if (n > best) best = n;
  }
  return best;
}

function agregarCantidadMapa_(mapa, clave, cant) {
  mapa[clave] = (mapa[clave] || 0) + (numeroCantidad_(cant) || 0);
}

function deltaCantidadCorreo_(actual, enviado) {
  var d = numeroCantidad_(actual) - numeroCantidad_(enviado);
  return d > 0 ? d : 0;
}

function mensajePermisoCorreo_(errGmail, errMail) {
  return (
    "Google bloqueó el envío por falta de autorización (OAuth).\n\n" +
    "Haz esto UNA vez, desde el EDITOR (un botón de la hoja no abre el diálogo):\n" +
    "1. Extensiones → Apps Script\n" +
    "2. Arriba elige la función autorizarEnvioCorreo\n" +
    "3. Pulsa Ejecutar y acepta todos los permisos\n" +
    "   Si dice 'Aplicación no verificada': Avanzado → Ir a proyecto → Permitir\n" +
    "4. Recarga la hoja y usa Tracking → Enviar Reporte\n\n" +
    "También pega appsscript.json con el scope https://www.googleapis.com/auth/script.send_mail\n\n" +
    "GmailApp: " + errGmail + "\n" +
    "MailApp: " + errMail
  );
}

function asegurarPermisoCorreo_() {
  try {
    var info = ScriptApp.getAuthorizationInfo(ScriptApp.AuthMode.FULL);
    if (info.getAuthorizationStatus() === ScriptApp.AuthorizationStatus.REQUIRED) {
      var url = "";
      try { url = info.getAuthorizationUrl() || ""; } catch (eUrl) { url = ""; }
      SpreadsheetApp.getUi().alert(
        "Falta autorizar el envío de correo",
        "Este script aún no tiene permiso para Gmail / MailApp (script.send_mail).\n\n" +
        "Abre Extensiones → Apps Script, selecciona autorizarEnvioCorreo y pulsa Ejecutar." +
        (url ? ("\n\nEnlace de autorización:\n" + url) : ""),
        SpreadsheetApp.getUi().ButtonSet.OK
      );
      return false;
    }
  } catch (e) {
    // Si no se puede consultar el estado, se intenta el envío igual.
  }
  return true;
}

function autorizarEnvioCorreo() {
  var ui = SpreadsheetApp.getUi();
  var cuenta = "";
  var cuotaGmail = -1;
  var cuotaMail = -1;

  try {
    cuenta = Session.getActiveUser().getEmail() || Session.getEffectiveUser().getEmail() || "";
  } catch (eCuenta) {
    cuenta = "";
  }

  try {
    cuotaGmail = GmailApp.getRemainingDailyQuota();
  } catch (eGmail) {
    ui.alert(
      "Falta autorizar Gmail",
      "Google no concedió (o se rechazó) el permiso de envío.\n\n" +
      "En el editor: función autorizarEnvioCorreo → Ejecutar.\n" +
      "Si sale 'Aplicación no verificada': Avanzado → Ir a [proyecto] → Permitir.\n" +
      "Hay que aceptar 'Enviar correo electrónico en tu nombre'.\n\n" +
      "Detalle: " + eGmail.toString(),
      ui.ButtonSet.OK
    );
    return;
  }

  try {
    cuotaMail = MailApp.getRemainingDailyQuota();
  } catch (eMail) {
    cuotaMail = -1;
  }

  ui.alert(
    "Permisos de correo listos",
    "Cuenta: " + (cuenta || "(no leída)") + "\n" +
    "Cuota GmailApp restante: " + cuotaGmail + "\n" +
    "Cuota MailApp restante: " + (cuotaMail < 0 ? "no disponible (se usará GmailApp)" : cuotaMail) + "\n\n" +
    "Ya puedes usar Tracking → Enviar Reporte de Producción (Correo).",
    ui.ButtonSet.OK
  );
}

function enviarCorreoHtml_(to, subject, htmlBody) {
  var texto = textoPlanoDeHtml_(htmlBody);
  var opciones = { htmlBody: htmlBody, name: "Tracking de Producción" };
  var errGmail = "";

  try {
    GmailApp.sendEmail(to, subject, texto, opciones);
    return "GmailApp";
  } catch (e1) {
    errGmail = e1.toString();
  }

  try {
    MailApp.sendEmail({
      to: to,
      subject: subject,
      htmlBody: htmlBody,
      name: "Tracking de Producción"
    });
    return "MailApp";
  } catch (e2) {
    throw new Error(mensajePermisoCorreo_(errGmail, e2.toString()));
  }
}

var HEADERS_HISTORIAL_CORREO_ = [
  "Clave", "Dia", "Fecha", "Linea", "Turno", "MO", "SKU", "Producto", "Genero", "Color", "Talla", "Cantidad Enviada", "Ultimo Envio"
];

function obtenerHojaHistorialCorreo_(ss) {
  var hoja = ss.getSheetByName(NOMBRE_HISTORIAL_CORREO_);
  if (!hoja) {
    hoja = ss.insertSheet(NOMBRE_HISTORIAL_CORREO_);
    hoja.getRange(1, 1).setValue("Historial de cantidades ya enviadas por correo. No borrar. Se oculta sola.");
    hoja.getRange(2, 1, 1, HEADERS_HISTORIAL_CORREO_.length)
      .setValues([HEADERS_HISTORIAL_CORREO_])
      .setFontWeight("bold");
    hoja.hideSheet();
  }
  return hoja;
}

function cargarEnviadoPorClave_(hoja) {
  var map = {};
  var last = hoja.getLastRow();
  if (last < 3) return map;
  var lastCol = Math.max(hoja.getLastColumn(), HEADERS_HISTORIAL_CORREO_.length);
  var headers = hoja.getRange(2, 1, 1, lastCol).getValues()[0];
  var idx = {
    clave: 0, dia: 1, fecha: 2, linea: 3, turno: 4, mo: 5, sku: 6,
    producto: 7, genero: 8, color: 9, talla: 10, cant: 11
  };
  for (var h = 0; h < headers.length; h++) {
    var n = quitarTildes_(String(headers[h] || "").toLowerCase().trim());
    if (n === "clave") idx.clave = h;
    else if (n === "dia") idx.dia = h;
    else if (n === "fecha") idx.fecha = h;
    else if (n === "linea") idx.linea = h;
    else if (n === "turno") idx.turno = h;
    else if (n === "mo" || n === "m.o.") idx.mo = h;
    else if (n === "sku") idx.sku = h;
    else if (n === "producto" || n === "modelo") idx.producto = h;
    else if (n.indexOf("genero") === 0) idx.genero = h;
    else if (n === "color") idx.color = h;
    else if (n === "talla") idx.talla = h;
    else if (n.indexOf("cantidad") !== -1) idx.cant = h;
  }
  var nCols = Math.max(idx.cant + 1, idx.clave + 1, lastCol);
  var vals = hoja.getRange(3, 1, last - 2, nCols).getValues();
  var disps = hoja.getRange(3, 1, last - 2, nCols).getDisplayValues();
  for (var i = 0; i < vals.length; i++) {
    var clave = migrarClaveHistorialCorreo_(String(vals[i][idx.clave] || "").trim());
    var cant = numeroCantidad_(vals[i][idx.cant], disps[i][idx.cant]);
    var fila = {
      dia: vals[i][idx.dia],
      fecha: vals[i][idx.fecha],
      linea: vals[i][idx.linea],
      turno: vals[i][idx.turno],
      mo: vals[i][idx.mo],
      sku: vals[i][idx.sku],
      producto: vals[i][idx.producto],
      genero: vals[i][idx.genero],
      color: vals[i][idx.color],
      talla: vals[i][idx.talla]
    };
    if (!clave && !String(fila.sku || "").trim() && !String(fila.producto || "").trim()) continue;
    registrarCantidadMapa_(map, clave || claveDetalleCorreo_(fila), fila, cant);
  }
  return map;
}

function guardarHistorialCorreo_(hoja, filasPersistir, ahora) {
  var last = hoja.getLastRow();
  var nCols = HEADERS_HISTORIAL_CORREO_.length;
  hoja.getRange(2, 1, 1, nCols).setValues([HEADERS_HISTORIAL_CORREO_]).setFontWeight("bold");
  if (last > 2) hoja.getRange(3, 1, last - 2, nCols).clearContent();
  if (!filasPersistir.length) return;
  var out = [];
  for (var i = 0; i < filasPersistir.length; i++) {
    var f = filasPersistir[i];
    out.push([
      f.clave, f.dia, f.fecha, f.linea, etiquetaTurno_(clasificarTurno_(f.turno)),
      f.mo, f.sku, f.producto, f.genero, f.color, f.talla,
      f.enviado, ahora
    ]);
  }
  hoja.getRange(3, 1, out.length, nCols).setValues(out);
  hoja.getRange(3, 3, out.length, 1).setNumberFormat("dd/MM/yyyy");
  hoja.getRange(3, 6, out.length, 2).setNumberFormat("@");
  hoja.getRange(3, 11, out.length, 1).setNumberFormat("@");
  hoja.getRange(3, 12, out.length, 1).setNumberFormat("0");
  hoja.getRange(3, nCols, out.length, 1).setNumberFormat("dd/MM/yyyy HH:mm");
}

function reiniciarHistorialCorreo() {
  var ui = SpreadsheetApp.getUi();
  var r = ui.alert(
    "Reiniciar historial de correo diario",
    "Esto borra el registro de lo ya enviado. El próximo correo volverá a incluir toda la producción del tablero.\n\n¿Continuar?",
    ui.ButtonSet.YES_NO
  );
  if (r !== ui.Button.YES) return;
  var hoja = obtenerHojaHistorialCorreo_(SpreadsheetApp.getActiveSpreadsheet());
  var last = hoja.getLastRow();
  if (last > 2) hoja.getRange(3, 1, last - 2, HEADERS_HISTORIAL_CORREO_.length).clearContent();
  ui.alert("Listo. El siguiente reporte enviará todo el detalle actual.");
}

function extraerFilasDetalleCorreo_(valores, displays) {
  var head = -1;
  var celdasHead = [];
  for (var r = 0; r < Math.min(10, valores.length); r++) {
    var celdas = (valores[r] || []).map(function(x) {
      return quitarTildes_(String(x == null ? "" : x).toLowerCase().trim());
    });
    if (celdas.indexOf("sku") !== -1 && celdas.indexOf("cantidad") !== -1 &&
        (celdas.indexOf("dia") !== -1 || celdas.indexOf("linea") !== -1)) {
      head = r;
      celdasHead = celdas;
      break;
    }
  }
  if (head === -1) return [];

  function idxDe(nombres) {
    for (var n = 0; n < nombres.length; n++) {
      var i = celdasHead.indexOf(nombres[n]);
      if (i !== -1) return i;
    }
    return -1;
  }

  var idxDia = idxDe(["dia"]);
  var idxFecha = idxDe(["fecha"]);
  var idxLinea = idxDe(["linea"]);
  var idxTurno = idxDe(["turno"]);
  var idxMo = idxDe(["mo", "m.o."]);
  var idxSku = idxDe(["sku"]);
  var idxProd = idxDe(["producto", "modelo"]);
  var idxGen = idxDe(["genero"]);
  var idxCol = idxDe(["color"]);
  var idxTal = idxDe(["talla"]);
  var idxCant = idxDe(["cantidad"]);

  var filas = [];
  for (var i = head + 1; i < valores.length; i++) {
    var fila = valores[i] || [];
    var disp = (displays && displays[i]) ? displays[i] : fila;
    var cant = idxCant !== -1 ? numeroCantidad_(fila[idxCant], disp[idxCant]) : 0;
    if (cant <= 0) continue;
    var turnoVal = idxTurno !== -1 ? fila[idxTurno] : "";
    var turnoDisp = idxTurno !== -1 ? disp[idxTurno] : "";
    var obj = {
      dia: idxDia !== -1 ? fila[idxDia] : "",
      fecha: idxFecha !== -1 ? fila[idxFecha] : "",
      linea: idxLinea !== -1 ? fila[idxLinea] : "",
      turno: turnoVal,
      mo: idxMo !== -1 ? fila[idxMo] : "",
      sku: idxSku !== -1 ? fila[idxSku] : "",
      producto: idxProd !== -1 ? fila[idxProd] : "",
      genero: idxGen !== -1 ? fila[idxGen] : "",
      color: idxCol !== -1 ? fila[idxCol] : "",
      talla: idxTal !== -1 ? fila[idxTal] : "",
      cantidad: cant,
      display: {
        dia: idxDia !== -1 ? disp[idxDia] : "",
        fecha: idxFecha !== -1 ? disp[idxFecha] : "",
        linea: idxLinea !== -1 ? disp[idxLinea] : "",
        turno: turnoDisp || etiquetaTurno_(clasificarTurno_(turnoVal)),
        mo: idxMo !== -1 ? disp[idxMo] : "",
        sku: idxSku !== -1 ? disp[idxSku] : "",
        producto: idxProd !== -1 ? disp[idxProd] : "",
        genero: idxGen !== -1 ? disp[idxGen] : "",
        color: idxCol !== -1 ? disp[idxCol] : "",
        talla: idxTal !== -1 ? disp[idxTal] : "",
        cantidad: cant
      }
    };
    obj.clave = claveDetalleCorreo_(obj);
    filas.push(obj);
  }
  return filas;
}

function consolidarDetallePorClave_(filas) {
  var porClave = {};
  var orden = [];
  for (var i = 0; i < filas.length; i++) {
    var f = filas[i];
    var clave = f.clave || claveDetalleCorreo_(f);
    if (!porClave[clave]) {
      porClave[clave] = {
        clave: clave,
        dia: f.dia,
        fecha: f.fecha,
        linea: f.linea,
        turno: f.turno,
        mo: f.mo,
        sku: f.sku,
        producto: f.producto,
        genero: f.genero,
        color: f.color,
        talla: f.talla,
        cantidad: 0,
        display: f.display
      };
      orden.push(clave);
    }
    porClave[clave].cantidad += numeroCantidad_(f.cantidad);
  }
  var out = [];
  for (var k = 0; k < orden.length; k++) out.push(porClave[orden[k]]);
  return out;
}

function partirDetalleNuevo_(consolidados, enviadoMap) {
  var nuevos = [];
  var persistir = [];
  var clavesVistas = {};

  for (var i = 0; i < consolidados.length; i++) {
    var f = consolidados[i];
    var ya = cantidadEnviadaDeMapa_(enviadoMap, f);
    var delta = deltaCantidadCorreo_(f.cantidad, ya);
    clavesVistas[f.clave] = true;
    persistir.push({
      clave: f.clave,
      dia: f.dia,
      fecha: f.fecha,
      linea: f.linea,
      turno: f.turno,
      mo: f.mo,
      sku: f.sku,
      producto: f.producto,
      genero: f.genero,
      color: f.color,
      talla: f.talla,
      enviado: Math.max(ya, numeroCantidad_(f.cantidad))
    });
    if (delta > 0) {
      var copia = {};
      for (var p in f) {
        if (Object.prototype.hasOwnProperty.call(f, p)) copia[p] = f[p];
      }
      copia.cantidad = delta;
      copia.display = copia.display || {};
      copia.display.cantidad = String(delta);
      nuevos.push(copia);
    }
  }

  for (var clave in enviadoMap) {
    if (!Object.prototype.hasOwnProperty.call(enviadoMap, clave)) continue;
    if (clavesVistas[clave]) continue;
    persistir.push({
      clave: clave,
      dia: "",
      fecha: "",
      linea: "",
      turno: "",
      mo: "",
      sku: "",
      producto: "",
      genero: "",
      color: "",
      talla: "",
      enviado: numeroCantidad_(enviadoMap[clave])
    });
  }
  return { nuevos: nuevos, persistir: persistir };
}

function esFilaLineaTablero_(fila) {
  var nom = String(fila && fila[1] != null ? fila[1] : "").trim().toLowerCase();
  return nom.indexOf("linea") !== -1 || nom.indexOf("línea") !== -1;
}

function esFilaTotalTablero_(fila) {
  var nom = quitarTildes_(String(fila && fila[1] != null ? fila[1] : "").trim().toLowerCase());
  return nom.indexOf("total") === 0;
}

function esFilaMarcadorTurno_(fila) {
  return turnoDeBloque_(fila && fila[1] != null ? fila[1] : "") !== "";
}

function filaTableroTieneValor_(fila) {
  var n = maxColFilaTablero_(fila);
  for (var j = 1; j < n; j++) {
    if (String(fila[j] == null ? "" : fila[j]).trim() !== "") return true;
  }
  return false;
}

function limitesTableroCorreo_(datos) {
  var bloques = dividirTablerosTracking_(datos);
  if (!bloques.length) return { first: 0, last: -1, lastCol: 1 };
  return { first: bloques[0].first, last: bloques[0].last, lastCol: bloques[0].lastCol };
}

function dividirTablerosTracking_(datos) {
  var bloques = [];
  var first = -1;
  var last = -1;
  var lastCol = 1;
  var hayLinea = false;
  var hayTotal = false;
  var titulo = tituloTableroTurno_("diurno");
  var pendingTitulo = tituloTableroTurno_("diurno");
  var tope = Math.min(80, datos.length);

  function cerrarBloque() {
    if (first !== -1 && last >= first && (hayLinea || hayTotal)) {
      bloques.push({
        titulo: hayLinea ? titulo : tituloTableroTotalDia_(),
        first: first,
        last: last,
        lastCol: lastCol
      });
    }
    first = -1;
    last = -1;
    lastCol = 1;
    hayLinea = false;
    hayTotal = false;
  }

  for (var i = 0; i < tope; i++) {
    var fila = datos[i] || [];
    if (!filaTableroTieneValor_(fila)) continue;
    var nCols = maxColFilaTablero_(fila);

    if (esFilaMarcadorTurno_(fila)) {
      if (first !== -1 && (hayLinea || hayTotal)) cerrarBloque();
      pendingTitulo = tituloTableroTurno_(turnoDeBloque_(fila[1]));
      titulo = pendingTitulo;
      first = i;
      last = i;
      lastCol = 1;
      hayLinea = false;
      hayTotal = false;
      for (var jm = 1; jm < nCols; jm++) {
        if (String(fila[jm] == null ? "" : fila[jm]).trim() !== "") lastCol = Math.max(lastCol, jm);
      }
      continue;
    }

    for (var j = 1; j < nCols; j++) {
      if (String(fila[j] == null ? "" : fila[j]).trim() !== "") lastCol = Math.max(lastCol, j);
    }
    if (first === -1) {
      first = i;
      titulo = pendingTitulo;
    }
    last = i;
    if (esFilaLineaTablero_(fila)) hayLinea = true;
    if (esFilaTotalTablero_(fila)) {
      hayTotal = true;
      cerrarBloque();
    }
  }
  cerrarBloque();
  return bloques;
}

function columnasUsadasTablero_(datos, first, last, lastCol, ocultar) {
  var minJ = -1;
  var maxJ = -1;
  for (var j = 1; j <= lastCol; j++) {
    var hay = false;
    for (var i = first; i <= last; i++) {
      if (ocultar && ocultar[i]) continue;
      if (String((datos[i] || [])[j] == null ? "" : datos[i][j]).trim() !== "") {
        hay = true;
        break;
      }
    }
    if (hay) {
      if (minJ === -1) minJ = j;
      maxJ = j;
    }
  }
  var usadas = [];
  if (minJ === -1) return usadas;
  for (var k = minJ; k <= maxJ; k++) usadas.push(k);
  return usadas;
}

function htmlCeldaTablero_(tag, val, bg, fg, bold, conBorde) {
  var borde = conBorde ? "border: 1px solid #ccc;" : "border: none;";
  var fondo = bg ? "background-color: " + bg + ";" : "";
  var color = fg ? "color: " + fg + ";" : "";
  var peso = bold ? "font-weight: bold;" : "";
  return "<" + tag + " style='padding: 6px 8px; " + borde + " text-align: center; " + fondo + " " + color + " " + peso + "'>" +
    escapeHtml_(val == null ? "" : val) + "</" + tag + ">";
}

function construirHtmlTableroEnRango_(datos, fondos, colores, first, last, lastCol) {
  if (last < first) return "";
  var cols = columnasUsadasTablero_(datos, first, last, lastCol, {});
  if (!cols.length) return "";

  var html = "<table cellspacing='0' cellpadding='0' style='border-collapse: collapse; border: none; width: 100%; font-size: 13px; margin-bottom: 20px;'>";
  for (var i = first; i <= last; i++) {
    if (String((datos[i] || []).join("")).trim() === "") continue;
    var esLinea = esFilaLineaTablero_(datos[i]);
    var esTotal = esFilaTotalTablero_(datos[i]);
    var esMarcador = esFilaMarcadorTurno_(datos[i]);
    var isHeader = !esLinea && !esTotal;
    var tag = isHeader ? "th" : "td";
    html += "<tr>";
    for (var c = 0; c < cols.length; c++) {
      var j = cols[c];
      var val = datos[i][j];
      var bg = (fondos[i] && fondos[i][j]) ? fondos[i][j] : "";
      var fg = (colores[i] && colores[i][j]) ? colores[i][j] : "";
      html += htmlCeldaTablero_(tag, val, bg, fg, isHeader || esTotal || esMarcador, false);
    }
    html += "</tr>";
  }
  html += "</table>";
  return html;
}

function construirHtmlTableroTracking_(datos, fondos, colores) {
  var lim = limitesTableroCorreo_(datos);
  return construirHtmlTableroEnRango_(datos, fondos, colores, lim.first, lim.last, lim.lastCol);
}

function construirHtmlTablerosTracking_(datos, fondos, colores) {
  var bloques = dividirTablerosTracking_(datos);
  if (!bloques.length) return construirHtmlTableroTracking_(datos, fondos, colores);
  var html = "";
  for (var b = 0; b < bloques.length; b++) {
    var bl = bloques[b];
    html += "<h4 style='color: #2b5797; margin: 16px 0 8px 0;'>" + escapeHtml_(bl.titulo) + "</h4>";
    html += construirHtmlTableroEnRango_(datos, fondos, colores, bl.first, bl.last, bl.lastCol);
  }
  return html;
}

function construirHtmlDetalle_(filasNuevas, fondosHeader, colorHeader) {
  var html = "<table cellspacing='0' cellpadding='0' style='border-collapse: collapse; width: 100%; font-size: 13px;'>";
  var headers = ["Dia", "Fecha", "Linea", "Turno", "MO", "SKU", "Producto", "Genero", "Color", "Talla", "Cantidad"];
  var keys = ["dia", "fecha", "linea", "turno", "mo", "sku", "producto", "genero", "color", "talla", "cantidad"];
  html += "<tr>";
  for (var h = 0; h < headers.length; h++) {
    html += htmlCeldaTablero_("th", headers[h], fondosHeader || "#434343", colorHeader || "#FFFFFF", true, true);
  }
  html += "</tr>";
  for (var i = 0; i < filasNuevas.length; i++) {
    var f = filasNuevas[i];
    var d = f.display || {};
    html += "<tr>";
    for (var k = 0; k < keys.length; k++) {
      var val = d[keys[k]] != null && String(d[keys[k]]).trim() !== "" ? d[keys[k]] : f[keys[k]];
      if (keys[k] === "cantidad") val = f.cantidad;
      if (keys[k] === "fecha") val = d.fecha || (typeof f.fecha === "object" ? "" : f.fecha);
      html += htmlCeldaTablero_("td", val, "#ffffff", "#333333", false, true);
    }
    html += "</tr>";
  }
  html += "</table>";
  return html;
}

// =========================================================================
// 6. ENVIAR REPORTE POR CORREO ELECTRÓNICO (TABLA INLINE, SOLO LO NUEVO)
// =========================================================================
function enviarReporteProduccion() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ui = SpreadsheetApp.getUi();

  var confirm = ui.alert(
    "Enviar Reporte de Producción",
    "El resumen copiará los tableros diurno, nocturno y el total del día de 'Tracking - Produccion' tal cual están en la hoja. El detalle solo incluirá modelos y cantidades nuevas (las que no hayan salido ya en un correo anterior).\n\n¿Continuar?",
    ui.ButtonSet.YES_NO
  );
  if (confirm !== ui.Button.YES) return;

  if (!asegurarPermisoCorreo_()) return;

  var hojaCorreo = ss.getSheetByName("Correo");
  if (!hojaCorreo) {
    ui.alert("Error: No se encontró la pestaña 'Correo'.");
    return;
  }

  var datosCorreo = hojaCorreo.getDataRange().getValues();
  var destinatarios = [];
  for (var i = 0; i < datosCorreo.length; i++) {
    var mail = String(datosCorreo[i][0]).trim();
    if (mail !== "" && mail.indexOf("@") !== -1 && mail.indexOf(".") !== -1) {
      destinatarios.push(mail);
    }
  }

  if (destinatarios.length === 0) {
    ui.alert("Error: No hay direcciones de correo válidas en la pestaña 'Correo'.");
    return;
  }
  var correosUnidos = destinatarios.join(",");

  var hojaTracking = ss.getSheetByName("Tracking - Produccion");
  var hojaDetalle = ss.getSheetByName("Detalle Tracking - Produccion");

  if (!hojaTracking || !hojaDetalle) {
    ui.alert("Error: Faltan las pestañas 'Tracking - Produccion' o 'Detalle Tracking - Produccion'.");
    return;
  }

  var nFilasTrack = Math.min(80, Math.max(hojaTracking.getLastRow(), 1));
  var nColsTrack = Math.min(MAX_COLS_TABLERO_CORREO_, Math.max(hojaTracking.getLastColumn(), 1));
  var rangoTrack = hojaTracking.getRange(1, 1, nFilasTrack, nColsTrack);
  var datosTracking = rangoTrack.getDisplayValues();
  var fondosTracking = rangoTrack.getBackgrounds();
  var coloresTracking = rangoTrack.getFontColors();

  var valoresDetalle = hojaDetalle.getDataRange().getValues();
  var displaysDetalle = hojaDetalle.getDataRange().getDisplayValues();
  var filasDetalle = extraerFilasDetalleCorreo_(valoresDetalle, displaysDetalle);
  if (filasDetalle.length === 0) {
    ui.alert("Error: La pestaña 'Detalle Tracking - Produccion' está vacía. No hay datos que reportar.");
    return;
  }

  var hojaHist = obtenerHojaHistorialCorreo_(ss);
  var enviadoMap = cargarEnviadoPorClave_(hojaHist);
  var consolidados = consolidarDetallePorClave_(filasDetalle);
  var partido = partirDetalleNuevo_(consolidados, enviadoMap);
  var filasNuevas = partido.nuevos;

  if (filasNuevas.length === 0) {
    ui.alert("Todo está al día. No hay modelos ni cantidades nuevas desde el último correo.");
    return;
  }

  ss.toast("Generando tablas HTML...", "Enviando Reporte", 10);

  var htmlTableros = construirHtmlTablerosTracking_(datosTracking, fondosTracking, coloresTracking);
  var htmlDetalle = construirHtmlDetalle_(filasNuevas, "#434343", "#FFFFFF");

  var htmlBody = "<div style='font-family: Arial, sans-serif; color: #333;'>";
  htmlBody += "<h2 style='color: #2b5797;'>Reporte de Producción Diaria</h2>";
  htmlBody += "<p>Estimado equipo,</p>";
  htmlBody += "<p>El resumen copia los tableros diurno, nocturno y el total del día de Tracking. El detalle incluye solo la producción nueva desde el último correo:</p>";

  htmlBody += "<h3 style='color: #444; border-bottom: 2px solid #ddd; padding-bottom: 5px;'>1. Resumen General (Tracking)</h3>";
  htmlBody += "<div style='overflow-x: auto;'>" + htmlTableros + "</div>";

  htmlBody += "<h3 style='color: #444; border-bottom: 2px solid #ddd; padding-bottom: 5px;'>2. Detalle de Producción</h3>";
  htmlBody += "<div style='overflow-x: auto;'>" + htmlDetalle + "</div>";

  htmlBody += "<br><br><div style='background-color: #fff3cd; color: #856404; padding: 15px; border-left: 5px solid #ffeeba;'>";
  htmlBody += "<strong>NOTA PARA ALMACÉN:</strong> Se estima que estos productos llegarán al almacén de producto terminado en aproximadamente <strong>3 días hábiles</strong>.";
  htmlBody += "</div>";

  htmlBody += "<p><br>Saludos cordiales,<br><em>Sistema Automático de Planificación</em></p>";
  htmlBody += "</div>";

  try {
    var via = enviarCorreoHtml_(correosUnidos, ASUNTO_REPORTE_CORREO_, htmlBody);
    guardarHistorialCorreo_(hojaHist, partido.persistir, new Date());
    ui.alert(
      "Éxito",
      "Se envió el reporte diario (" + via + ") con " + filasNuevas.length + " ítems nuevos a:\n\n" + correosUnidos,
      ui.ButtonSet.OK
    );
  } catch (error) {
    ui.alert("Error al enviar el correo:\n\n" + error.toString());
  }
}
