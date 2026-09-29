/**
 * =====================================================================
 *  MÓDULO DE TRACKING DE PRODUCCIÓN — VERSIÓN 5.9.3 (CORREO DIARIO)
 * =====================================================================
 *  Cambios de esta versión:
 *   - Asunto y nota de almacén sin emojis (Gmail los mostraba como �).
 *   - Resumen General (Tracking) sin líneas de cuadrícula.
 *   - Correo diario: solo modelos/cantidades nuevas. Lo ya enviado
 *     queda en la hoja oculta "_Correo Enviado" y no se reenvía.
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

  // Preparar u obtener la hoja de Detalles desde el principio para tener su ID
  var hojaDetalle = ss.getSheetByName("Detalle Tracking - Produccion");
  if (!hojaDetalle) {
    hojaDetalle = ss.insertSheet("Detalle Tracking - Produccion");
    var headersDetalle = ["Dia", "Fecha", "Linea", "MO", "SKU", "Producto", "Genero", "Color", "Talla", "Cantidad"];
    hojaDetalle.getRange(2, 2, 1, 10).setValues([headersDetalle])
      .setBackground("#434343").setFontColor("#FFFFFF").setFontWeight("bold")
      .setHorizontalAlignment("center");
  } else {
    var ultFilaDet = hojaDetalle.getLastRow();
    if (ultFilaDet > 2) {
      hojaDetalle.getRange(3, 2, ultFilaDet - 2, 10).clearContent().setBorder(false, false, false, false, false, false);
    }
  }
  var sheetIdDetalle = hojaDetalle.getSheetId();

  var totalesPorLinea = {};
  var registrosDetalle = []; // [Dia, Fecha, Linea, MO, SKU, Producto, Genero, Color, Talla, Cantidad]
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

        if (!totalesPorLinea[numLinea]) {
          totalesPorLinea[numLinea] = { lunes: 0, martes: 0, miercoles: 0, jueves: 0, viernes: 0 };
        }

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
              totalesPorLinea[numLinea][dObj.claveObj] += cantDia;
              registrosDetalle.push([
                dObj.dia,
                fechasDiasUnidades[dObj.claveObj] || "",
                "Línea " + (match ? match[0] : filaStr),
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

        if (idCant !== -1 && idFecha !== -1) {
          var numLineaP = "linea 1"; // Estricto para Pedidos

          for (var j = fHeadP + 1; j < datosPedidos.length; j++) {
            var filaP = datosPedidos[j];
            var cantidad = Number(filaP[idCant]) || 0;
            var fechaVal = filaP[idFecha];

            if (cantidad > 0 && fechaVal) {
              if (!totalesPorLinea[numLineaP]) {
                 totalesPorLinea[numLineaP] = { lunes: 0, martes: 0, miercoles: 0, jueves: 0, viernes: 0 };
              }

              var f = new Date(fechaVal);
              if (!isNaN(f.getTime())) {
                var diaSemana = f.getDay(); // 1=Lunes, 2=Martes, 3=Miercoles, 4=Jueves, 5=Viernes
                var nombreDiaReal = mapaDiasNom[diaSemana] || "Otro";

                if (diaSemana === 1) totalesPorLinea[numLineaP].lunes += cantidad;
                else if (diaSemana === 2) totalesPorLinea[numLineaP].martes += cantidad;
                else if (diaSemana === 3) totalesPorLinea[numLineaP].miercoles += cantidad;
                else if (diaSemana === 4) totalesPorLinea[numLineaP].jueves += cantidad;
                else if (diaSemana === 5) totalesPorLinea[numLineaP].viernes += cantidad;

                if (diaSemana >= 1 && diaSemana <= 5) {
                  registrosDetalle.push([
                    nombreDiaReal,
                    f,
                    "Línea 1",
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
  for (var t = 0; t < datosTracking.length; t++) {
    var filaTracking = datosTracking[t];
    var nombreLineaTracking = String(filaTracking[1]).trim().toLowerCase();

    if (nombreLineaTracking === "" || (!nombreLineaTracking.includes("linea") && !nombreLineaTracking.includes("línea"))) {
      continue;
    }

    var matchT = nombreLineaTracking.match(/\d+/);
    var numLineaT = matchT ? "linea " + matchT[0] : nombreLineaTracking;
    var prod = totalesPorLinea[numLineaT] || { lunes: 0, martes: 0, miercoles: 0, jueves: 0, viernes: 0 };

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
      return a[2].localeCompare(b[2]);
    });

    var rangoDest = hojaDetalle.getRange(3, 2, registrosDetalle.length, 10);
    rangoDest.setValues(registrosDetalle)
      .setHorizontalAlignment("center").setVerticalAlignment("middle")
      .setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.SOLID);
    hojaDetalle.getRange(3, 3, registrosDetalle.length, 1).setNumberFormat("dd/MM/yyyy");
    hojaDetalle.autoResizeColumns(2, 10);
  }

  SpreadsheetApp.getUi().alert("✅ Tableros Actualizados:\n\n1. El tablero numérico ('Tracking - Produccion') fue actualizado con links dinámicos.\n2. La pestaña de desglose ('Detalle Tracking - Produccion') fue regenerada con el registro individual de piezas.");
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

function normalizarFechaClave_(val) {
  if (Object.prototype.toString.call(val) === "[object Date]" && !isNaN(val.getTime())) {
    return val.getFullYear() + "-" + pad2_(val.getMonth() + 1) + "-" + pad2_(val.getDate());
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

function lineaClaveCorreo_(s) {
  var t = quitarTildes_(String(s || "").toLowerCase());
  var m = t.match(/(\d+)/);
  if ((t.indexOf("linea") !== -1 || t.indexOf("línea") !== -1) && m) return "linea " + m[1];
  return t.replace(/\s+/g, " ").trim();
}

function diaClaveCorreo_(s) {
  return quitarTildes_(String(s || "").toLowerCase()).replace(/\s+/g, " ").trim();
}

function claveDetalleCorreo_(fila) {
  return [
    diaClaveCorreo_(fila.dia),
    normalizarFechaClave_(fila.fecha),
    lineaClaveCorreo_(fila.linea),
    String(fila.mo == null ? "" : fila.mo).trim().toLowerCase(),
    String(fila.sku == null ? "" : fila.sku).trim().toLowerCase(),
    String(fila.producto == null ? "" : fila.producto).trim().toLowerCase(),
    String(fila.genero == null ? "" : fila.genero).trim().toLowerCase(),
    String(fila.color == null ? "" : fila.color).trim().toLowerCase(),
    String(fila.talla == null ? "" : fila.talla).trim().toLowerCase()
  ].join("|");
}

function agregarCantidadMapa_(mapa, clave, cant) {
  mapa[clave] = (mapa[clave] || 0) + (Number(cant) || 0);
}

function deltaCantidadCorreo_(actual, enviado) {
  var d = (Number(actual) || 0) - (Number(enviado) || 0);
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

function obtenerHojaHistorialCorreo_(ss) {
  var hoja = ss.getSheetByName(NOMBRE_HISTORIAL_CORREO_);
  if (!hoja) {
    hoja = ss.insertSheet(NOMBRE_HISTORIAL_CORREO_);
    hoja.getRange(1, 1).setValue("Historial de cantidades ya enviadas por correo. No borrar. Se oculta sola.");
    hoja.getRange(2, 1, 1, 12).setValues([[
      "Clave", "Dia", "Fecha", "Linea", "MO", "SKU", "Producto", "Genero", "Color", "Talla", "Cantidad Enviada", "Ultimo Envio"
    ]]).setFontWeight("bold");
    hoja.hideSheet();
  }
  return hoja;
}

function cargarEnviadoPorClave_(hoja) {
  var map = {};
  var last = hoja.getLastRow();
  if (last < 3) return map;
  var vals = hoja.getRange(3, 1, last - 2, 11).getValues();
  for (var i = 0; i < vals.length; i++) {
    var clave = String(vals[i][0] || "").trim();
    if (!clave) continue;
    map[clave] = Number(vals[i][10]) || 0;
  }
  return map;
}

function guardarHistorialCorreo_(hoja, filasPersistir, ahora) {
  var last = hoja.getLastRow();
  if (last > 2) hoja.getRange(3, 1, last - 2, 12).clearContent();
  if (!filasPersistir.length) return;
  var out = [];
  for (var i = 0; i < filasPersistir.length; i++) {
    var f = filasPersistir[i];
    out.push([
      f.clave, f.dia, f.fecha, f.linea, f.mo, f.sku, f.producto, f.genero, f.color, f.talla,
      f.enviado, ahora
    ]);
  }
  hoja.getRange(3, 1, out.length, 12).setValues(out);
  hoja.getRange(3, 3, out.length, 1).setNumberFormat("dd/MM/yyyy");
  hoja.getRange(3, 12, out.length, 1).setNumberFormat("dd/MM/yyyy HH:mm");
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
  if (last > 2) hoja.getRange(3, 1, last - 2, 12).clearContent();
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
    var cant = idxCant !== -1 ? Number(fila[idxCant]) || 0 : 0;
    if (cant <= 0) continue;
    var obj = {
      dia: idxDia !== -1 ? fila[idxDia] : "",
      fecha: idxFecha !== -1 ? fila[idxFecha] : "",
      linea: idxLinea !== -1 ? fila[idxLinea] : "",
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
        mo: idxMo !== -1 ? disp[idxMo] : "",
        sku: idxSku !== -1 ? disp[idxSku] : "",
        producto: idxProd !== -1 ? disp[idxProd] : "",
        genero: idxGen !== -1 ? disp[idxGen] : "",
        color: idxCol !== -1 ? disp[idxCol] : "",
        talla: idxTal !== -1 ? disp[idxTal] : "",
        cantidad: idxCant !== -1 ? disp[idxCant] : cant
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
    porClave[clave].cantidad += Number(f.cantidad) || 0;
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
    var ya = enviadoMap[f.clave] || 0;
    var delta = deltaCantidadCorreo_(f.cantidad, ya);
    clavesVistas[f.clave] = true;
    persistir.push({
      clave: f.clave,
      dia: f.dia,
      fecha: f.fecha,
      linea: f.linea,
      mo: f.mo,
      sku: f.sku,
      producto: f.producto,
      genero: f.genero,
      color: f.color,
      talla: f.talla,
      enviado: Math.max(ya, Number(f.cantidad) || 0)
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
      mo: "",
      sku: "",
      producto: "",
      genero: "",
      color: "",
      talla: "",
      enviado: enviadoMap[clave]
    });
  }
  return { nuevos: nuevos, persistir: persistir };
}

function deltasPorLineaDia_(filasNuevas) {
  var out = {};
  for (var i = 0; i < filasNuevas.length; i++) {
    var f = filasNuevas[i];
    var lin = lineaClaveCorreo_(f.linea);
    var dia = diaClaveCorreo_(f.dia);
    if (!out[lin]) out[lin] = {};
    out[lin][dia] = (out[lin][dia] || 0) + (Number(f.cantidad) || 0);
  }
  return out;
}

function detectarMapaRealesTablero_(datos) {
  var mapa = {};
  var filaDias = -1;
  var tope = Math.min(25, datos.length);
  for (var i = 0; i < tope; i++) {
    var celdas = (datos[i] || []).map(function(x) {
      return quitarTildes_(String(x == null ? "" : x).toLowerCase().trim());
    });
    if (celdas.indexOf("lunes") !== -1 && celdas.indexOf("martes") !== -1) {
      filaDias = i;
      break;
    }
  }
  if (filaDias === -1) return { mapa: mapa, filaDias: -1, filaPlanReal: -1, colTotalReal: -1 };

  var filaPR = filaDias + 1;
  var celdasDias = (datos[filaDias] || []).map(function(x) {
    return quitarTildes_(String(x == null ? "" : x).toLowerCase().trim());
  });
  var celdasPR = filaPR < datos.length ? (datos[filaPR] || []).map(function(x) {
    return quitarTildes_(String(x == null ? "" : x).toLowerCase().trim());
  }) : [];

  var dias = ["lunes", "martes", "miercoles", "jueves", "viernes"];
  for (var d = 0; d < dias.length; d++) {
    var nombre = dias[d];
    var idxDia = -1;
    for (var j = 0; j < celdasDias.length; j++) {
      if (celdasDias[j].indexOf(nombre) === 0) { idxDia = j; break; }
    }
    if (idxDia === -1) continue;
    if (celdasPR[idxDia] && celdasPR[idxDia].indexOf("real") !== -1) mapa[nombre] = idxDia;
    else if (celdasPR[idxDia + 1] && celdasPR[idxDia + 1].indexOf("real") !== -1) mapa[nombre] = idxDia + 1;
    else mapa[nombre] = idxDia;
  }

  var colTotalReal = -1;
  for (var t = celdasPR.length - 1; t >= 0; t--) {
    if (celdasPR[t].indexOf("real") !== -1) { colTotalReal = t; break; }
  }
  if (colTotalReal === -1) {
    for (var u = celdasDias.length - 1; u >= 0; u--) {
      if (celdasDias[u].indexOf("total") !== -1) { colTotalReal = u; break; }
    }
  }
  return { mapa: mapa, filaDias: filaDias, filaPlanReal: filaPR, colTotalReal: colTotalReal };
}

function esFilaLineaTablero_(fila) {
  var nom = String(fila && fila[1] != null ? fila[1] : "").trim().toLowerCase();
  return nom.indexOf("linea") !== -1 || nom.indexOf("línea") !== -1;
}

function esFilaTotalTablero_(fila) {
  var nom = quitarTildes_(String(fila && fila[1] != null ? fila[1] : "").trim().toLowerCase());
  return nom.indexOf("total") === 0;
}

function limitesTableroCorreo_(datos) {
  var first = -1;
  var last = -1;
  var lastCol = 1;
  var tope = Math.min(40, datos.length);
  for (var i = 0; i < tope; i++) {
    var fila = datos[i] || [];
    var hay = false;
    for (var j = 1; j < Math.min(16, fila.length); j++) {
      if (String(fila[j] == null ? "" : fila[j]).trim() !== "") {
        hay = true;
        lastCol = Math.max(lastCol, j);
      }
    }
    if (!hay) continue;
    if (first === -1) first = i;
    last = i;
    if (esFilaTotalTablero_(fila)) break;
  }
  if (first === -1) return { first: 0, last: -1, lastCol: 1 };
  return { first: first, last: last, lastCol: lastCol };
}

function aplicarDeltasEnTablero_(datos, detReales) {
  var copia = [];
  for (var i = 0; i < datos.length; i++) copia.push((datos[i] || []).slice());
  var mapaInfo = detectarMapaRealesTablero_(copia);
  var mapa = mapaInfo.mapa;
  var colTotal = mapaInfo.colTotalReal;
  var filasOcultar = {};

  for (var r = 0; r < copia.length && r < 40; r++) {
    if (!esFilaLineaTablero_(copia[r])) continue;
    var lin = lineaClaveCorreo_(copia[r][1]);
    var deltas = detReales[lin] || {};
    var suma = 0;
    for (var dia in mapa) {
      if (!Object.prototype.hasOwnProperty.call(mapa, dia)) continue;
      var col = mapa[dia];
      var val = Number(deltas[dia]) || 0;
      suma += val;
      copia[r][col] = val > 0 ? String(val) : "";
    }
    if (colTotal !== -1) copia[r][colTotal] = suma > 0 ? String(suma) : "";
    if (suma <= 0) filasOcultar[r] = true;
  }

  for (var t = 0; t < copia.length && t < 40; t++) {
    if (!esFilaTotalTablero_(copia[t])) continue;
    var tot = 0;
    for (var diaT in mapa) {
      if (!Object.prototype.hasOwnProperty.call(mapa, diaT)) continue;
      var colT = mapa[diaT];
      var acc = 0;
      for (var rr = 0; rr < copia.length && rr < 40; rr++) {
        if (filasOcultar[rr]) continue;
        if (!esFilaLineaTablero_(copia[rr])) continue;
        acc += Number(copia[rr][colT]) || 0;
      }
      copia[t][colT] = acc > 0 ? String(acc) : "";
      tot += acc;
    }
    if (colTotal !== -1) copia[t][colTotal] = tot > 0 ? String(tot) : "";
  }
  return { datos: copia, ocultar: filasOcultar };
}

function columnasUsadasTablero_(datos, first, last, lastCol, ocultar) {
  var usadas = [];
  for (var j = 1; j <= lastCol; j++) {
    var hay = false;
    for (var i = first; i <= last; i++) {
      if (ocultar && ocultar[i]) continue;
      if (String((datos[i] || [])[j] == null ? "" : datos[i][j]).trim() !== "") {
        hay = true;
        break;
      }
    }
    if (hay) usadas.push(j);
  }
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

function construirHtmlTableroTracking_(datos, fondos, colores, detReales) {
  var aplicado = aplicarDeltasEnTablero_(datos, detReales);
  var tab = aplicado.datos;
  var ocultar = aplicado.ocultar;
  var lim = limitesTableroCorreo_(tab);
  if (lim.last < lim.first) return "";
  var cols = columnasUsadasTablero_(tab, lim.first, lim.last, lim.lastCol, ocultar);
  if (!cols.length) return "";

  var html = "<table cellspacing='0' cellpadding='0' style='border-collapse: collapse; border: none; width: 100%; font-size: 13px; margin-bottom: 20px;'>";
  for (var i = lim.first; i <= lim.last; i++) {
    if (String((datos[i] || []).join("")).trim() === "") continue;
    if (ocultar[i]) continue;
    var esLinea = esFilaLineaTablero_(tab[i]);
    var esTotal = esFilaTotalTablero_(tab[i]);
    var isHeader = !esLinea && !esTotal;
    var tag = isHeader ? "th" : "td";
    html += "<tr>";
    for (var c = 0; c < cols.length; c++) {
      var j = cols[c];
      var val = tab[i][j];
      var bg = (fondos[i] && fondos[i][j]) ? fondos[i][j] : "";
      var fg = (colores[i] && colores[i][j]) ? colores[i][j] : "";
      html += htmlCeldaTablero_(tag, val, bg, fg, isHeader || esTotal, false);
    }
    html += "</tr>";
  }
  html += "</table>";
  return html;
}

function construirHtmlDetalle_(filasNuevas, fondosHeader, colorHeader) {
  var html = "<table cellspacing='0' cellpadding='0' style='border-collapse: collapse; width: 100%; font-size: 13px;'>";
  var headers = ["Dia", "Fecha", "Linea", "MO", "SKU", "Producto", "Genero", "Color", "Talla", "Cantidad"];
  var keys = ["dia", "fecha", "linea", "mo", "sku", "producto", "genero", "color", "talla", "cantidad"];
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
    "Se enviará solo la producción nueva (la que no haya salido ya en un correo anterior). El tablero de Tracking irá sin cuadrícula.\n\n¿Continuar?",
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

  var rangoTrack = hojaTracking.getRange(1, 1, Math.min(40, Math.max(hojaTracking.getLastRow(), 1)), Math.min(16, Math.max(hojaTracking.getLastColumn(), 1)));
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

  var detReales = deltasPorLineaDia_(filasNuevas);
  var htmlTablero = construirHtmlTableroTracking_(datosTracking, fondosTracking, coloresTracking, detReales);
  var htmlDetalle = construirHtmlDetalle_(filasNuevas, "#434343", "#FFFFFF");

  var htmlBody = "<div style='font-family: Arial, sans-serif; color: #333;'>";
  htmlBody += "<h2 style='color: #2b5797;'>Reporte de Producción Diaria</h2>";
  htmlBody += "<p>Estimado equipo,</p>";
  htmlBody += "<p>A continuación se presenta solo la producción nueva desde el último correo:</p>";

  htmlBody += "<h3 style='color: #444; border-bottom: 2px solid #ddd; padding-bottom: 5px;'>1. Resumen General (Tracking)</h3>";
  htmlBody += "<div style='overflow-x: auto;'>" + htmlTablero + "</div>";

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
