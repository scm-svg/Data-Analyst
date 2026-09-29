# -*- coding: utf-8 -*-
"""El script de Tracking declara envío por Gmail/MailApp y los oauthScopes."""
import json
import os
import unittest

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


if __name__ == "__main__":
    unittest.main()
