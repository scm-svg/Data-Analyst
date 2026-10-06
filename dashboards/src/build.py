#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DATA = ROOT / "data"
OUT = ROOT

css = (SRC / "app.css").read_text(encoding="utf-8")
js = (SRC / "metrics.js").read_text(encoding="utf-8") + "\n" + (SRC / "app.js").read_text(encoding="utf-8")
logo = (SRC / "logo.html").read_text(encoding="utf-8")
shell = (SRC / "shell.html").read_text(encoding="utf-8")
labels = json.loads((DATA / "labels.json").read_text(encoding="utf-8"))
order = ["sambil", "chacao", "cerroverde", "grieta", "vela", "tolon", "grandplaz"]

def page(title, payload):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html = (shell
            .replace("<!--TITLE-->", title)
            .replace("<!--CSS-->", css)
            .replace("<!--LOGO-->", logo)
            .replace("<!--DATA-->", raw)
            .replace("<!--JS-->", js))
    return html

stores = []
for key in order:
    data = json.loads((DATA / f"{key}.json").read_text(encoding="utf-8"))
    payload = {
        "mode": "store",
        "id": key,
        "name": labels[key],
        "corte": "30/09/2026",
        "chain": "cadena.html",
        "file": f"{key}.html",
        "data": data,
    }
    html = page(f"{labels[key]} · Análisis de tienda · CUADRO", payload)
    (OUT / f"{key}.html").write_text(html, encoding="utf-8")
    print(key, len(html))
    stores.append({
        "id": key,
        "name": labels[key],
        "file": f"{key}.html",
        "data": data,
    })

chain = page("Cadena · CUADRO", {"mode": "chain", "corte": "30/09/2026", "stores": stores})
(OUT / "cadena.html").write_text(chain, encoding="utf-8")
print("cadena", len(chain))

index = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tiendas · CUADRO</title>
<style>
body{font-family:Montserrat,system-ui,sans-serif;margin:0;background:#fff;color:#1A1A1A}
header{background:#0B3F6B;color:#fff;padding:28px 32px}
a{display:block;padding:14px 18px;margin:8px 0;background:#F1F1F1;border-radius:12px;color:#0B3F6B;font-weight:700;text-decoration:none}
main{max-width:720px;margin:0 auto;padding:24px}
</style>
</head>
<body>
<header><h1>Tableros de tienda</h1><p>Corte 30/09/2026 · la misma lógica en las siete tiendas y en la cadena.</p></header>
<main>
<a href="cadena.html">Cadena · comparación y traslados</a>
""" + "\n".join(f'<a href="{k}.html">{labels[k]}</a>' for k in order) + """
</main>
</body>
</html>
"""
(OUT / "index.html").write_text(index, encoding="utf-8")
print("index")
