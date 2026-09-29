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


def clave_detalle(fila):
    return "|".join(
        [
            dia_clave(fila.get("dia")),
            fecha_clave(fila.get("fecha")),
            linea_clave(fila.get("linea")),
            str(fila.get("mo") or "").strip().lower(),
            str(fila.get("sku") or "").strip().lower(),
            str(fila.get("producto") or "").strip().lower(),
            str(fila.get("genero") or "").strip().lower(),
            str(fila.get("color") or "").strip().lower(),
            str(fila.get("talla") or "").strip().lower(),
        ]
    )


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
        self.assertIn("htmlCeldaTablero_(tag, val, bg, fg, isHeader || esTotal, false)", src)
        self.assertIn("border: none", src)
        self.assertIn('table cellspacing=\'0\'', src)

    def test_resumen_copia_tablero_completo_detalle_solo_nuevo(self):
        with open(GS, encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("function aplicarDeltasEnTablero_(", src)
        self.assertNotIn("function deltasPorLineaDia_(", src)
        self.assertIn(
            "construirHtmlTableroTracking_(datosTracking, fondosTracking, coloresTracking)",
            src,
        )
        self.assertIn("construirHtmlDetalle_(filasNuevas", src)
        self.assertIn("tal cual está en la hoja", src)

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


if __name__ == "__main__":
    unittest.main()
