/**
 * Dashboard de Capacidades - Taller
 * Pegar este archivo en el editor de Apps Script (Código.gs).
 * El HTML debe llamarse Index (createHtmlOutputFromFile('Index')).
 */

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
      .setTitle('Dashboard - Operaciones Taller')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function getSheetByTrimmedName_(ss, wanted) {
  var target = String(wanted || '').trim().toLowerCase();
  var sheets = ss.getSheets();
  for (var i = 0; i < sheets.length; i++) {
    if (String(sheets[i].getName()).trim().toLowerCase() === target) {
      return sheets[i];
    }
  }
  return ss.getSheetByName(wanted) || null;
}

function getSheetData() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = getSheetByTrimmedName_(ss, 'Operaciones - Taller');

  if (!sheet) {
    return [];
  }

  var lastRow = sheet.getLastRow();
  if (lastRow < 3) {
    return [];
  }

  var data = sheet.getRange(3, 2, lastRow - 2, 6).getValues();

  var formattedData = data.map(function(row) {
    var estatus = row[4];
    if (estatus === null || estatus === undefined || estatus === '') {
      estatus = '';
    } else {
      estatus = estatus.toString().trim();
    }
    return {
      Linea: row[0] ? row[0].toString().trim() : '',
      Maquina: row[1] ? row[1].toString().trim() : '',
      Operacion: row[2] ? row[2].toString().trim() : '',
      Capacidad_Teorica: Number(row[3]) || 0,
      Estatus: estatus,
      Capacidad_Real: Number(row[5]) || 0
    };
  });

  return formattedData.filter(function(item) {
    return item.Linea !== '' || item.Maquina !== '';
  });
}

function getAdicionalesData() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = getSheetByTrimmedName_(ss, 'Adicionales');

  if (!sheet) {
    return [];
  }

  var lastRow = sheet.getLastRow();
  if (lastRow < 5) {
    return [];
  }

  var data = sheet.getRange(5, 2, lastRow - 4, 5).getValues();

  var formattedData = data.map(function(row) {
    var estatus = row[3];
    if (estatus === null || estatus === undefined || estatus === '') {
      estatus = '';
    } else {
      estatus = estatus.toString().trim();
    }
    return {
      Linea: 'Adicionales',
      Maquina: row[0] ? row[0].toString().trim() : '',
      Operacion: row[1] ? row[1].toString().trim() : '',
      Capacidad_Teorica: Number(row[2]) || 0,
      Estatus: estatus,
      Capacidad_Real: Number(row[4]) || 0
    };
  });

  return formattedData.filter(function(item) {
    return item.Maquina !== '';
  });
}
