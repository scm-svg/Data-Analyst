#!/usr/bin/env python3
"""Extract design preview images from COMPRAS JULIO ECOBAG xlsx."""
import base64
import json
import re
from pathlib import Path
from zipfile import ZipFile

XLSX = '/home/ubuntu/.cursor/projects/workspace/uploads/Copia_de_COMPRAS_JULIO_-_ECOBAG_fc0a.xlsx'
OUT_JSON = Path(__file__).parent / 'ecobags_design_images.json'
OUT_DIR = Path(__file__).parent / 'ecobags_images'

# Excel row (0-based from drawing anchor) -> dashboard color key
ROW_TO_COLOR = {
    8: 'Made in Venezuela/Verde',
    9: 'Palmeras/Azul',
    10: 'Ovalo/Azul',
    11: 'Daily/Negro',
    12: 'Ondas/Verde',
}


def main():
    OUT_DIR.mkdir(exist_ok=True)
    with ZipFile(XLSX) as z:
        xml = z.read('xl/drawings/drawing1.xml').decode()
        rels = z.read('xl/drawings/_rels/drawing1.xml.rels').decode()
        rid_map = {
            m.group(1): m.group(2)
            for m in re.finditer(r'Id="(rId\d+)"[^>]*Target="\.\./media/([^"]+)"', rels)
        }
        color_images = {}
        anchor_re = re.compile(
            r'<xdr:(?:oneCellAnchor|twoCellAnchor)[^>]*>.*?</xdr:(?:oneCellAnchor|twoCellAnchor)>',
            re.DOTALL,
        )
        for block in anchor_re.findall(xml):
            row_m = re.search(r'<xdr:from>.*?<xdr:row>(\d+)</xdr:row>', block, re.DOTALL)
            if not row_m:
                row_m = re.search(r'<xdr:row>(\d+)</xdr:row>', block)
            col_m = re.search(r'<xdr:from>.*?<xdr:col>(\d+)</xdr:col>', block, re.DOTALL)
            if not col_m:
                col_m = re.search(r'<xdr:col>(\d+)</xdr:col>', block)
            rid_m = re.search(r'r:embed="(rId\d+)"', block)
            if not (row_m and col_m and rid_m):
                continue
            row, col = int(row_m.group(1)), int(col_m.group(1))
            fname = rid_map.get(rid_m.group(1))
            if col != 3 or row not in ROW_TO_COLOR or not fname:
                continue
            data = z.read(f'xl/media/{fname}')
            ext = fname.rsplit('.', 1)[-1].lower()
            mime = 'image/jpeg' if ext in ('jpg', 'jpeg') else 'image/png'
            (OUT_DIR / fname).write_bytes(data)
            color_images[ROW_TO_COLOR[row]] = f'data:{mime};base64,{base64.b64encode(data).decode()}'

    OUT_JSON.write_text(json.dumps(color_images, ensure_ascii=False), encoding='utf-8')
    print(f'Mapped {len(color_images)} designs -> {OUT_JSON}')
    for k in color_images:
        print(f'  {k}')


if __name__ == '__main__':
    main()
