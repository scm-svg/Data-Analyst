#!/usr/bin/env python3
"""Embed flowchart PNGs as base64 in Manual HTML (supports existing data URIs)."""
import base64
import glob
import os
import re

HTML_PATH = "/workspace/Manual_Procesos_Logistica.html"
FLOW_DIR = "/workspace/flowcharts"

ALT_TO_FILE = {
    "Flujograma despacho de tela": "01_despacho_tela.png",
    "Flujograma despacho insumos": "02_despacho_insumos_etiquetado.png",
    "Flujograma devolución tela": "03_devolucion_tela.png",
    "Flujograma recepción tela": "04_recepcion_tela.png",
    "Flujograma rollo rechazado": "04b_recepcion_tela_rechazo.png",
    "Flujograma rechazados": "05_rechazados_devolucion.png",
    "Flujograma recepción insumos": "06_recepcion_insumos.png",
    "Flujograma despacho consumibles": "07_despacho_consumibles.png",
    "Flujograma recepción consumibles": "08_recepcion_consumibles.png",
    "Flujograma requisición compra": "req_01_requisicion_compra.png",
    "Flujograma info adicional": "req_02_requisicion_info_adicional.png",
    "Vista general procesos logística": "00_overview_logistica.png",
}

with open(HTML_PATH, "r", encoding="utf-8") as f:
    html = f.read()

for alt, filename in ALT_TO_FILE.items():
    path = os.path.join(FLOW_DIR, filename)
    if not os.path.isfile(path):
        print("MISSING", path)
        continue
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    uri = f"data:image/png;base64,{b64}"
    pattern = (
        rf'(<img\s+src=")(?:data:image/png;base64,[^"]+|flowcharts/{re.escape(filename)})("'
        rf'[^>]*alt="{re.escape(alt)}"[^>]*>)'
    )
    html, n = re.subn(pattern, rf"\1{uri}\2", html, count=1)
    if n == 0:
        # alt before src
        pattern2 = (
            rf'(<img\s+[^>]*alt="{re.escape(alt)}"[^>]*src=")'
            rf'(?:data:image/png;base64,[^"]+|flowcharts/{re.escape(filename)})(")'
        )
        html, n = re.subn(pattern2, rf"\1{uri}\2", html, count=1)
    print(f"{'OK' if n else 'SKIP'} {filename} ({alt})")

with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print("Done.")
