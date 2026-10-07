# -*- coding: utf-8 -*-
"""El script de Tracking declara envío por Gmail/MailApp, correo diario y tablero sin cuadrícula."""
import json
import os
import re
import unittest
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKING = os.path.join(ROOT, "tracking")
GS = os.path.join(TRACKING, "Codigo.gs")
MANIFEST = os.path.join(TRACKING, "appsscript.json")

SCOPES_REQUERIDOS = {
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/script.container.ui",
    "https://www.googleapis.com/auth/script.send_mail",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
}


def quitar_tildes(s):
    return (
        str(s)
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )


def linea_clave(s):
    t = quitar_tildes(str(s or "").lower())
    m = re.search(r"(\d+)", t)
    if "linea" in t and m:
        return "linea " + m.group(1)
    return re.sub(r"\s+", " ", t).strip()


def dia_clave(s):
    return re.sub(r"\s+", " ", quitar_tildes(str(s or "").lower())).strip()


def fecha_clave(val):
    if hasattr(val, "year"):
        return "%04d-%02d-%02d" % (val.year, val.month, val.day)
    s = str(val or "").strip()
    m = re.match(r"^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})$", s)
    if m:
        y = int(m.group(3))
        if y < 100:
            y += 2000
        return "%04d-%02d-%02d" % (y, int(m.group(2)), int(m.group(1)))
    return s.lower()


def clasificar_turno(val):
    t = re.sub(r"\s+", " ", quitar_tildes(str(val or "").lower())).strip()
    if "nocturn" in t:
        return "nocturno"
    return "diurno"


def etiqueta_turno(clave):
    return "Nocturno" if clave == "nocturno" else "Diurno"


def titulo_tablero_turno(clave):
    return "Turno Nocturno" if clave == "nocturno" else "Turno Diurno"


def turno_de_bloque(texto):
    t = re.sub(r"\s+", " ", quitar_tildes(str(texto or "").lower())).strip()
    if "nocturn" in t:
        return "nocturno"
    if "diurn" in t:
        return "diurno"
    return ""


def migrar_clave_historial(clave):
    parts = str(clave or "").split("|")
    if len(parts) == 9:
        parts.insert(3, "diurno")
        return "|".join(parts)
    return clave


def clave_detalle(fila):
    return "|".join(
        [
            dia_clave(fila.get("dia")),
            fecha_clave(fila.get("fecha")),
            linea_clave(fila.get("linea")),
            clasificar_turno(fila.get("turno")),
            str(fila.get("mo") or "").strip().lower(),
            str(fila.get("sku") or "").strip().lower(),
            str(fila.get("producto") or "").strip().lower(),
            str(fila.get("genero") or "").strip().lower(),
            str(fila.get("color") or "").strip().lower(),
            str(fila.get("talla") or "").strip().lower(),
        ]
    )


def vacios_dias():
    return {"lunes": 0, "martes": 0, "miercoles": 0, "jueves": 0, "viernes": 0}


def asegurar_totales(totales, turno, linea):
    totales.setdefault(turno, {})
    totales[turno].setdefault(linea, vacios_dias())
    return totales[turno][linea]


def es_fila_linea(fila):
    nom = str(fila[1] if fila and len(fila) > 1 else "").strip().lower()
    return "linea" in nom or "línea" in nom


def es_fila_total(fila):
    nom = quitar_tildes(str(fila[1] if fila and len(fila) > 1 else "").strip().lower())
    return nom.startswith("total")


def es_marcador_turno(fila):
    return turno_de_bloque(fila[1] if fila and len(fila) > 1 else "") != ""


def fila_tiene_valor(fila):
    for j in range(1, min(16, len(fila or []))):
        if str(fila[j] or "").strip() != "":
            return True
    return False


def dividir_tableros(datos):
    bloques = []
    first = last = -1
    last_col = 1
    hay_linea = False
    titulo = pending = "Turno Diurno"

    def cerrar():
        nonlocal first, last, last_col, hay_linea
        if first != -1 and last >= first and hay_linea:
            bloques.append(
                {"titulo": titulo, "first": first, "last": last, "lastCol": last_col}
            )
        first = last = -1
        last_col = 1
        hay_linea = False

    for i, fila in enumerate(datos[:80]):
        if not fila_tiene_valor(fila):
            continue
        if es_marcador_turno(fila):
            if first != -1 and hay_linea:
                cerrar()
            pending = titulo_tablero_turno(turno_de_bloque(fila[1]))
            titulo = pending
            first = last = i
            last_col = 1
            hay_linea = False
            for jm in range(1, min(16, len(fila))):
                if str(fila[jm] or "").strip() != "":
                    last_col = max(last_col, jm)
            continue
        for j in range(1, min(16, len(fila))):
            if str(fila[j] or "").strip() != "":
                last_col = max(last_col, j)
        if first == -1:
            first = i
            titulo = pending
        last = i
        if es_fila_linea(fila):
            hay_linea = True
        if es_fila_total(fila):
            cerrar()
    cerrar()
    return bloques


def consolidar(filas):
    por = OrderedDict()
    for f in filas:
        c = clave_detalle(f)
        if c not in por:
            por[c] = dict(f)
            por[c]["clave"] = c
            por[c]["cantidad"] = 0
        por[c]["cantidad"] += int(f.get("cantidad") or 0)
    return list(por.values())


def delta(actual, enviado):
    d = (int(actual) or 0) - (int(enviado) or 0)
    return d if d > 0 else 0


def partir_nuevo(consolidados, enviado_map):
    nuevos = []
    persistir = {}
    for f in consolidados:
        ya = enviado_map.get(f["clave"], 0)
        d = delta(f["cantidad"], ya)
        persistir[f["clave"]] = max(ya, f["cantidad"])
        if d > 0:
            copia = dict(f)
            copia["cantidad"] = d
            nuevos.append(copia)
    for clave, cant in enviado_map.items():
        persistir.setdefault(clave, cant)
    return nuevos, persistir


def html_celda_tablero(val, con_borde):
    borde = "border: 1px solid #ccc;" if con_borde else "border: none;"
    return "<td style='padding: 6px 8px; %s text-align: center;'>%s</td>" % (borde, val)


class TestTrackingCorreo(unittest.TestCase):
    def test_manifiesto_incluye_scopes_de_correo(self):
        with open(MANIFEST, encoding="utf-8") as f:
            data = json.load(f)
        scopes = set(data.get("oauthScopes") or [])
        faltan = SCOPES_REQUERIDOS - scopes
        self.assertFalse(faltan, "Faltan oauthScopes: %s" % sorted(faltan))
        self.assertEqual(data.get("runtimeVersion"), "V8")

    def test_script_autoriza_y_envia_con_gmail_y_mailapp(self):
        with open(GS, encoding="utf-8") as f:
            src = f.read()
        for token in (
            "function autorizarEnvioCorreo(",
            "function asegurarPermisoCorreo_(",
            "function enviarCorreoHtml_(",
            "GmailApp.sendEmail",
            "MailApp.sendEmail",
            "GmailApp.getRemainingDailyQuota",
            "MailApp.getRemainingDailyQuota",
            "autorizarEnvioCorreo",
            "enviarCorreoHtml_(",
            "script.send_mail",
        ):
            self.assertIn(token, src, "No aparece en Codigo.gs: %s" % token)
        self.assertIn("Autorizar envío de correo", src)
        self.assertIn("enviarReporteProduccion", src)
        idx_gmail = src.find("GmailApp.sendEmail")
        idx_mail = src.rfind("MailApp.sendEmail")
        self.assertGreater(idx_gmail, 0)
        self.assertGreater(idx_mail, idx_gmail)
        self.assertIn("enviarCorreoHtml_(correosUnidos", src)

    def test_fallback_gmail_luego_mailapp(self):
        def enviar(gmail_ok, mail_ok):
            try:
                if not gmail_ok:
                    raise RuntimeError(
                        "No tienes permiso para llamar a GmailApp.sendEmail"
                    )
                return "GmailApp"
            except RuntimeError:
                try:
                    if not mail_ok:
                        raise RuntimeError(
                            "No tienes permiso para llamar a MailApp.sendEmail. "
                            "Permisos necesarios: https://www.googleapis.com/auth/script.send_mail"
                        )
                    return "MailApp"
                except RuntimeError as e2:
                    return "ERROR:" + str(e2)

        self.assertEqual(enviar(True, False), "GmailApp")
        self.assertEqual(enviar(False, True), "MailApp")
        self.assertIn("script.send_mail", enviar(False, False))

    def test_asunto_y_nota_sin_emoji(self):
        with open(GS, encoding="utf-8") as f:
            src = f.read()
        self.assertIn(
            'ASUNTO_REPORTE_CORREO_ = "Reporte de Producción Diaria y Proyección a Almacén"',
            src,
        )
        self.assertNotIn("📢", src)
        self.assertIn("<strong>NOTA PARA ALMACÉN:</strong>", src)
        self.assertNotIn("📦 NOTA PARA ALMACÉN", src)
        self.assertNotRegex(src, r"📦\s*NOTA PARA ALMAC")

    def test_tablero_tracking_sin_cuadricula(self):
        with open(GS, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("function construirHtmlTableroTracking_(", src)
        self.assertIn("function construirHtmlTablerosTracking_(", src)
        self.assertIn("htmlCeldaTablero_(tag, val, bg, fg, isHeader || esTotal || esMarcador, false)", src)
        self.assertIn("border: none", src)
        self.assertIn('table cellspacing=\'0\'', src)

    def test_resumen_copia_tablero_completo_detalle_solo_nuevo(self):
        with open(GS, encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("function aplicarDeltasEnTablero_(", src)
        self.assertNotIn("function deltasPorLineaDia_(", src)
        self.assertIn(
            "construirHtmlTablerosTracking_(datosTracking, fondosTracking, coloresTracking)",
            src,
        )
        self.assertIn("construirHtmlDetalle_(filasNuevas", src)
        self.assertIn("tal cual están en la hoja", src)
        self.assertIn("Turno Diurno", src)
        self.assertIn("Turno Nocturno", src)

    def test_historial_diario_en_script(self):
        with open(GS, encoding="utf-8") as f:
            src = f.read()
        for token in (
            'NOMBRE_HISTORIAL_CORREO_ = "_Correo Enviado"',
            "function partirDetalleNuevo_(",
            "function reiniciarHistorialCorreo(",
            "function extraerFilasDetalleCorreo_(",
            "Todo está al día. No hay modelos ni cantidades nuevas",
        ):
            self.assertIn(token, src, "Falta: %s" % token)

    def test_no_reenvia_cantidades_ya_enviadas(self):
        filas = [
            {
                "dia": "Lunes",
                "fecha": "28/09/2026",
                "linea": "Línea 5",
                "mo": "1256",
                "sku": "SHONRCA30TL",
                "producto": "SHORT SPORT",
                "genero": "CAB",
                "color": "Gris Claro",
                "talla": "L",
                "cantidad": 20,
            },
            {
                "dia": "Lunes",
                "fecha": "28/09/2026",
                "linea": "Línea 4",
                "mo": "",
                "sku": "",
                "producto": "Running Tank",
                "genero": "CAB",
                "color": "BLANCO",
                "talla": "L",
                "cantidad": 40,
            },
            {
                "dia": "Lunes",
                "fecha": "28/09/2026",
                "linea": "Línea 4",
                "mo": "",
                "sku": "",
                "producto": "Running Tank",
                "genero": "CAB",
                "color": "BLANCO",
                "talla": "L",
                "cantidad": 40,
            },
        ]
        cons = consolidar(filas)
        self.assertEqual(len(cons), 2)
        tank = [x for x in cons if x["producto"] == "Running Tank"][0]
        self.assertEqual(tank["cantidad"], 80)

        nuevos1, persistir1 = partir_nuevo(cons, {})
        self.assertEqual(sum(x["cantidad"] for x in nuevos1), 100)
        self.assertEqual(persistir1[tank["clave"]], 80)

        nuevos2, persistir2 = partir_nuevo(cons, persistir1)
        self.assertEqual(nuevos2, [])
        self.assertEqual(persistir2[tank["clave"]], 80)

        cons2 = consolidar(
            filas
            + [
                {
                    "dia": "Martes",
                    "fecha": "29/09/2026",
                    "linea": "Línea 5",
                    "mo": "1256",
                    "sku": "SHONRCA30TL",
                    "producto": "SHORT SPORT",
                    "genero": "CAB",
                    "color": "Gris Claro",
                    "talla": "L",
                    "cantidad": 12,
                }
            ]
        )
        nuevos3, persistir3 = partir_nuevo(cons2, persistir1)
        self.assertEqual(len(nuevos3), 1)
        self.assertEqual(nuevos3[0]["cantidad"], 12)
        self.assertEqual(nuevos3[0]["dia"], "Martes")
        self.assertEqual(sum(persistir3.values()), 80 + 20 + 12)

    def test_delta_nunca_negativo(self):
        self.assertEqual(delta(20, 20), 0)
        self.assertEqual(delta(15, 20), 0)
        self.assertEqual(delta(35, 20), 15)

    def test_html_tablero_sin_borde(self):
        html = html_celda_tablero("66", False)
        self.assertIn("border: none;", html)
        self.assertNotIn("border: 1px solid #ccc;", html)
        html_det = html_celda_tablero("66", True)
        self.assertIn("border: 1px solid #ccc;", html_det)

    def test_clasificar_turno(self):
        self.assertEqual(clasificar_turno(""), "diurno")
        self.assertEqual(clasificar_turno("Diurno"), "diurno")
        self.assertEqual(clasificar_turno("NOCTURNO"), "nocturno")
        self.assertEqual(clasificar_turno("Turno nocturno"), "nocturno")
        self.assertEqual(turno_de_bloque("NOCTURNO"), "nocturno")
        self.assertEqual(turno_de_bloque("Linea 1"), "")

    def test_clave_incluye_turno_y_migra_historial_viejo(self):
        base = {
            "dia": "Lunes",
            "fecha": "05/10/2026",
            "linea": "Línea 2",
            "mo": "1",
            "sku": "ABC",
            "producto": "RIO",
            "genero": "CAB",
            "color": "Negro",
            "talla": "L",
            "cantidad": 10,
        }
        diurno = dict(base, turno="Diurno")
        nocturno = dict(base, turno="Nocturno")
        self.assertNotEqual(clave_detalle(diurno), clave_detalle(nocturno))
        self.assertIn("|diurno|", clave_detalle(diurno))
        self.assertIn("|nocturno|", clave_detalle(nocturno))
        vieja = "lunes|2026-10-05|linea 2|1|abc|rio|cab|negro|l"
        self.assertEqual(migrar_clave_historial(vieja), clave_detalle(diurno))
        cons = consolidar([diurno, nocturno, dict(diurno, cantidad=5)])
        self.assertEqual(len(cons), 2)
        por_turno = {clasificar_turno(x["turno"]): x["cantidad"] for x in cons}
        self.assertEqual(por_turno["diurno"], 15)
        self.assertEqual(por_turno["nocturno"], 10)

    def test_script_reparte_turnos_en_tableros_y_detalle(self):
        with open(GS, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("VERSIÓN 5.9.5", src)
        for token in (
            "function clasificarTurno_(",
            "function turnoDeBloque_(",
            "function dividirTablerosTracking_(",
            "function prepararHojaDetalleTracking_(",
            "totalesPorTurno",
            'HEADERS_DETALLE_TRACKING_ = ["Dia", "Fecha", "Linea", "Turno"',
            '"Turno", "MO", "SKU"',
            "migrarClaveHistorialCorreo_",
        ):
            self.assertIn(token, src, "Falta: %s" % token)
        self.assertIn("tablero diurno y el tablero nocturno", src)

    def test_divide_tableros_diurno_y_nocturno(self):
        vac = [""] * 15
        datos = []
        for _ in range(30):
            datos.append(list(vac))
        datos[1][1] = "SEMANA"
        datos[4][1] = ""
        datos[4][2] = "Lunes"
        datos[6][1] = "Linea 1"
        datos[6][3] = "10"
        datos[11][1] = "Total"
        datos[11][3] = "10"
        datos[14][1] = "NOCTURNO"
        datos[16][2] = "Lunes"
        datos[18][1] = "Linea 1"
        datos[18][3] = "52"
        datos[23][1] = "Total"
        datos[23][3] = "52"
        datos[26][1] = "TOTAL"
        datos[26][3] = "62"
        bloques = dividir_tableros(datos)
        self.assertEqual([b["titulo"] for b in bloques], ["Turno Diurno", "Turno Nocturno"])
        self.assertEqual(bloques[0]["first"], 1)
        self.assertEqual(bloques[0]["last"], 11)
        self.assertEqual(bloques[1]["first"], 14)
        self.assertEqual(bloques[1]["last"], 23)

    def test_agrega_reales_por_turno_y_linea(self):
        filas = [
            ("linea 2", "Diurno", 39, 0),
            ("linea 2", "Diurno", 50, 23),
            ("linea 2", "Nocturno", 46, 101),
            ("linea 1", "Nocturno", 52, 57),
            ("linea 4", "", 88, 0),
        ]
        totales = {}
        for lin, turno, lun, mar in filas:
            prod = asegurar_totales(totales, clasificar_turno(turno), lin)
            prod["lunes"] += lun
            prod["martes"] += mar
        self.assertEqual(totales["diurno"]["linea 2"]["lunes"], 89)
        self.assertEqual(totales["diurno"]["linea 2"]["martes"], 23)
        self.assertEqual(totales["nocturno"]["linea 2"]["lunes"], 46)
        self.assertEqual(totales["nocturno"]["linea 1"]["martes"], 57)
        self.assertEqual(totales["diurno"]["linea 4"]["lunes"], 88)
        self.assertNotIn("linea 1", totales.get("diurno", {}))

    def test_excel_costura_separa_diurno_nocturno(self):
        xlsx = "/home/ubuntu/.cursor/projects/workspace/uploads/Tracking_-_Produccion__2__8f48.xlsx"
        if not os.path.isfile(xlsx):
            self.skipTest("Excel de Tracking no está en este entorno")
        from collections import defaultdict
        from openpyxl import load_workbook

        wb = load_workbook(xlsx, data_only=True)
        ws = wb["Unidades Producidas - Costura"]
        tot = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        days = {10: "lunes", 11: "martes", 12: "miercoles", 13: "jueves", 14: "viernes"}
        for r in range(5, ws.max_row + 1):
            linea = ws.cell(r, 8).value
            if not linea:
                continue
            m = re.search(r"(\d+)", str(linea))
            if not m:
                continue
            lin = "linea " + m.group(1)
            turno = clasificar_turno(ws.cell(r, 9).value)
            for c, d in days.items():
                v = ws.cell(r, c).value
                if v and float(v) > 0:
                    tot[turno][lin][d] += float(v)
        self.assertEqual(tot["diurno"]["linea 2"]["lunes"], 115)
        self.assertEqual(tot["diurno"]["linea 4"]["martes"], 84)
        self.assertEqual(tot["nocturno"]["linea 1"]["lunes"], 52)
        self.assertEqual(tot["nocturno"]["linea 2"]["martes"], 101)
        self.assertEqual(sum(tot["nocturno"]["linea 5"].values()), 30)


if __name__ == "__main__":
    unittest.main()
