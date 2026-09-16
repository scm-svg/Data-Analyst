#!/usr/bin/env python3
"""Embed flowchart PNGs as base64 so HTML works standalone."""
import base64
import glob
import os
import re

HTML_PATH = "/workspace/Manual_Procesos_Logistica.html"
FLOW_DIR = "/workspace/flowcharts"

with open(HTML_PATH, "r", encoding="utf-8") as f:
    html = f.read()

for png in glob.glob(os.path.join(FLOW_DIR, "*.png")):
    name = os.path.basename(png)
    with open(png, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    data_uri = f"data:image/png;base64,{b64}"
    html = html.replace(f'src="flowcharts/{name}"', f'src="{data_uri}"')

with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(html)

count = len(re.findall(r'data:image/png;base64,', html))
print(f"Embedded {count} images")
