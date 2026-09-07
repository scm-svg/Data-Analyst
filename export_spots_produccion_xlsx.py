#!/usr/bin/env python3
"""Exporta SPOTS_PRODUCCION_EXPANSION.xlsx — matriz color/diseño × talla por zona (estilo Short Playa)."""

from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from build_spots_dashboard import (
    DEFAULT_PROD_MONTHS,
    EXPANSION_CAPS,
    FABRIC_KG_PER_UNIT,
    FABRIC_SAFETY_PCT,
    ZONE_ADICIONAL_COLOR,
    rebuild_data,
)

OUT_PATH = Path(__file__).resolve().parent / "SPOTS_PRODUCCION_EXPANSION.xlsx"
TALLA_ORDER = ["XS", "S", "M", "L", "XL", "2XL"]
THIN = Side(style="thin", color="CCCCCC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HDR_FILL = PatternFill("solid", fgColor="1F2937")
HDR_FONT = Font(bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(bold=True, size=12)
TOTAL_FILL = PatternFill("solid", fgColor="E5E7EB")
TOTAL_FONT = Font(bold=True)
SECTION_FILL = PatternFill("solid", fgColor="F3F4F6")


def _style_range(ws, row, col_start, col_end, fill=None, font=None, border=True):
    for c in range(col_start, col_end + 1):
        cell = ws.cell(row=row, column=c)
        if fill:
            cell.fill = fill
        if font:
            cell.font = font
        if border:
            cell.border = BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center")


def _write_matrix(ws, start_row, title, tallas, rows_data):
    """rows_data: list of (label, {talla: qty})"""
    ws.cell(row=start_row, column=1, value="CANTIDADES POR DISEÑO / COLOR").font = TITLE_FONT
    hdr_row = start_row + 1
    ws.cell(row=hdr_row, column=1, value=title).font = Font(bold=True)
    for i, t in enumerate(tallas, start=2):
        ws.cell(row=hdr_row, column=i, value=t)
    ws.cell(row=hdr_row, column=len(tallas) + 2, value="Tot")
    _style_range(ws, hdr_row, 1, len(tallas) + 2, fill=HDR_FILL, font=HDR_FONT)

    r = hdr_row + 1
    col_totals = defaultdict(int)
    grand = 0
    for label, by_talla in rows_data:
        ws.cell(row=r, column=1, value=label)
        row_sum = 0
        for i, t in enumerate(tallas, start=2):
            qty = int(by_talla.get(t, 0) or 0)
            if qty:
                ws.cell(row=r, column=i, value=qty)
            col_totals[t] += qty
            row_sum += qty
        ws.cell(row=r, column=len(tallas) + 2, value=row_sum)
        grand += row_sum
        _style_range(ws, r, 1, len(tallas) + 2)
        r += 1

    ws.cell(row=r, column=1, value="TOTAL").font = TOTAL_FONT
    for i, t in enumerate(tallas, start=2):
        if col_totals[t]:
            ws.cell(row=r, column=i, value=col_totals[t])
    ws.cell(row=r, column=len(tallas) + 2, value=grand)
    _style_range(ws, r, 1, len(tallas) + 2, fill=TOTAL_FILL, font=TOTAL_FONT)
    return r + 2, grand


def _zone_genero_rows(store, genero, months):
    """Agrupa SKUs por diseño+color para un género."""
    key = f"need_{months}m"
    grouped = defaultdict(lambda: defaultdict(int))
    for sku in store.get("skus", []):
        if sku["genero"] != genero:
            continue
        label = f"{sku['diseno']} ({sku['color']})"
        grouped[label][sku["talla"]] += sku.get(key, sku.get("need_3m", 0))
    tallas = [t for t in TALLA_ORDER if any(grouped[l].get(t) for l in grouped)]
    rows = [(label, dict(tallas)) for label, tallas in sorted(grouped.items())]
    return tallas, rows


def _all_skus_by_genero(data, genero, months):
    """Agrega SKUs de todas las zonas para un género."""
    key = f"need_{months}m"
    by_label = defaultdict(lambda: defaultdict(int))
    meta = {}
    for store in data["expansion"]["by_store"]:
        zone = store["store"]
        for sku in store.get("skus", []):
            if sku["genero"] != genero:
                continue
            if sku["color"] == "Blanco":
                label = f"{sku['diseno']} · Blanco ({zone.title()})"
            else:
                label = f"{sku['color']} · {zone.title()}"
            by_label[label][sku["talla"]] += sku.get(key, sku.get("need_3m", 0))
            meta[label] = {"color": sku["color"], "zona": zone, "diseno": sku["diseno"]}
    return by_label, meta


def _consolidated_rows(by_label, meta):
    """Blanco primero, luego colores — orden Short Playa."""
    blanco = []
    colores = []
    for label, tallas in by_label.items():
        m = meta[label]
        row = (label, dict(tallas), m)
        if m["color"] == "Blanco":
            blanco.append(row)
        else:
            colores.append(row)
    blanco.sort(key=lambda x: (x[2]["zona"], x[2]["diseno"]))
    color_order = {c: i for i, c in enumerate(ZONE_ADICIONAL_COLOR.values())}
    colores.sort(key=lambda x: (color_order.get(x[2]["color"], 99), x[2]["zona"]))
    return blanco, colores


def _write_colores_sheet(wb, data, genero, months):
    """Pestaña estilo Short Playa: blanco arriba, colores abajo, tallas en columnas."""
    ws = wb.create_sheet(genero)
    ws.column_dimensions["A"].width = 36
    for i in range(2, 12):
        ws.column_dimensions[get_column_letter(i)].width = 8

    by_label, meta = _all_skus_by_genero(data, genero, months)
    blanco_rows, color_rows = _consolidated_rows(by_label, meta)
    all_tallas = [t for t in TALLA_ORDER if any(by_label[l].get(t) for l in by_label)]

    row = 1
    ws.cell(row=row, column=1, value="CANTIDADES POR COLORES").font = Font(bold=True, size=13)
    row += 1
    hdr = row
    ws.cell(row=hdr, column=1, value=f"SPOTS MANGA CORTA {genero}")
    for i, t in enumerate(all_tallas, start=2):
        ws.cell(row=hdr, column=i, value=t)
    ws.cell(row=hdr, column=len(all_tallas) + 2, value="Tot")
    _style_range(ws, hdr, 1, len(all_tallas) + 2, fill=HDR_FILL, font=HDR_FONT)
    row = hdr + 1

    def write_rows(rows_data, section_total_label=None):
        nonlocal row
        col_totals = defaultdict(int)
        section_total = 0
        for label, tallas, _m in rows_data:
            ws.cell(row=row, column=1, value=label)
            row_sum = 0
            for i, t in enumerate(all_tallas, start=2):
                qty = int(tallas.get(t, 0) or 0)
                if qty:
                    ws.cell(row=row, column=i, value=qty)
                col_totals[t] += qty
                row_sum += qty
            ws.cell(row=row, column=len(all_tallas) + 2, value=row_sum)
            section_total += row_sum
            _style_range(ws, row, 1, len(all_tallas) + 2)
            row += 1
        if section_total_label and rows_data:
            ws.cell(row=row, column=1, value=section_total_label).font = TOTAL_FONT
            for i, t in enumerate(all_tallas, start=2):
                if col_totals[t]:
                    ws.cell(row=row, column=i, value=col_totals[t])
            ws.cell(row=row, column=len(all_tallas) + 2, value=section_total)
            _style_range(ws, row, 1, len(all_tallas) + 2, fill=TOTAL_FILL, font=TOTAL_FONT)
            row += 1
        return section_total, col_totals

    grand_cols = defaultdict(int)
    grand = 0

    b_tot, b_cols = write_rows(blanco_rows, "TOTAL BLANCO")
    grand += b_tot
    for t, v in b_cols.items():
        grand_cols[t] += v
    row += 1

    c_tot, c_cols = write_rows(color_rows, "TOTAL COLORES")
    grand += c_tot
    for t, v in c_cols.items():
        grand_cols[t] += v

    ws.cell(row=row, column=1, value="TOTAL GENERAL").font = Font(bold=True, size=11)
    for i, t in enumerate(all_tallas, start=2):
        if grand_cols[t]:
            ws.cell(row=row, column=i, value=grand_cols[t])
    ws.cell(row=row, column=len(all_tallas) + 2, value=grand)
    _style_range(ws, row, 1, len(all_tallas) + 2, fill=PatternFill("solid", fgColor="D1FAE5"), font=TOTAL_FONT)


def _write_zone_sheet(wb, store, months):
    zone = store["store"]
    ws = wb.create_sheet(zone.title())
    ws.column_dimensions["A"].width = 34
    for i in range(2, 10):
        ws.column_dimensions[get_column_letter(i)].width = 8

    row = 1
    ws.cell(row=row, column=1, value=f"SPOTS MANGA CORTA — {zone} · Proyección {months} meses")
    ws.cell(row=row, column=1).font = Font(bold=True, size=13)
    row += 2
    ws.cell(row=row, column=1, value=store.get("label", ""))
    row += 2

    zone_total = 0
    for genero in ("CAB", "DAMA"):
        tallas, rows = _zone_genero_rows(store, genero, months)
        if not rows:
            continue
        ws.cell(row=row, column=1, value=genero).font = Font(bold=True, size=11)
        ws.cell(row=row, column=1).fill = SECTION_FILL
        row += 1
        row, sub = _write_matrix(
            ws, row, f"SPOTS MANGA CORTA {genero} — {zone}", tallas, rows,
        )
        zone_total += sub

    ws.cell(row=row, column=1, value=f"TOTAL ZONA {zone}").font = Font(bold=True, size=11)
    ws.cell(row=row, column=2, value=zone_total).font = Font(bold=True, size=11)


def _write_resumen(wb, data, months):
    ws = wb.create_sheet("RESUMEN", 0)
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 40

    exp = data["expansion"]
    fab = data.get("fabric", exp.get("fabric", {}))
    row = 1
    ws.cell(row=row, column=1, value="SPOTS — Resumen producción expansión").font = Font(bold=True, size=14)
    row += 2
    meta = [
        ("Horizonte", f"{months} meses"),
        ("Base rotación", data.get("velocity_months_label", "")),
        ("Temporada alta", f"×{data.get('high_season_factor', 1.2)}"),
        ("Virgen BQT (dic)", f"×{data.get('december_hs_factor', 1.4)}"),
        ("Colores zona", "Caracas Azul Marino · Valencia Vinotinto · Barquisimeto Verde"),
        ("Factor color", f"{int((data.get('additional_color_factor') or 0.7) * 100)}% del blanco principal"),
    ]
    for label, val in meta:
        ws.cell(row=row, column=1, value=label).font = Font(bold=True)
        ws.cell(row=row, column=2, value=val)
        row += 1
    row += 1

    headers = ["Zona", "Blanco", "Color zona", "Total"]
    for i, h in enumerate(headers, start=1):
        ws.cell(row=row, column=i, value=h)
    _style_range(ws, row, 1, 4, fill=HDR_FILL, font=HDR_FONT)
    row += 1
    for store in exp.get("by_store", []):
        ws.cell(row=row, column=1, value=store["store"])
        ws.cell(row=row, column=2, value=store["blanco"])
        ws.cell(row=row, column=3, value=f"{store.get('adicional_color', '')} ({store['adicional']})")
        ws.cell(row=row, column=4, value=store["total"])
        _style_range(ws, row, 1, 4)
        row += 1
    ws.cell(row=row, column=1, value="TOTAL EXPANSIÓN").font = TOTAL_FONT
    ws.cell(row=row, column=2, value=exp.get("total_blanco", 0))
    ws.cell(row=row, column=3, value=exp.get("total_adicional", 0))
    ws.cell(row=row, column=4, value=exp.get("total_expansion", 0))
    _style_range(ws, row, 1, 4, fill=TOTAL_FILL, font=TOTAL_FONT)
    row += 2

    ws.cell(row=row, column=1, value="Nota metodológica").font = Font(bold=True)
    row += 1
    ws.cell(row=row, column=1, value=exp.get("nota", ""))
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
    ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True)
    row += 2

    ws.cell(row=row, column=1, value="Compra de tela (referencia)").font = Font(bold=True, size=12)
    row += 1
    ws.cell(row=row, column=1, value=f"Consumo {FABRIC_KG_PER_UNIT} kg/und · stock seguridad +{int(FABRIC_SAFETY_PCT * 100)}%")
    row += 1
    ws.cell(row=row, column=1, value="Material")
    ws.cell(row=row, column=2, value="Unidades")
    ws.cell(row=row, column=3, value="Tela (kg)")
    _style_range(ws, row, 1, 3, fill=HDR_FILL, font=HDR_FONT)
    row += 1
    blanco = fab.get("blanco", {})
    ws.cell(row=row, column=1, value="Blanco (total)")
    ws.cell(row=row, column=2, value=blanco.get("units", 0))
    ws.cell(row=row, column=3, value=blanco.get("kg", 0))
    _style_range(ws, row, 1, 3)
    row += 1
    for r in fab.get("adicional_by_zone", []):
        ws.cell(row=row, column=1, value=r.get("color", r.get("tipo", "Color")))
        ws.cell(row=row, column=2, value=r.get("units", 0))
        ws.cell(row=row, column=3, value=r.get("kg", 0))
        _style_range(ws, row, 1, 3)
        row += 1
    total = fab.get("total", {})
    ws.cell(row=row, column=1, value="TOTAL TELA").font = TOTAL_FONT
    ws.cell(row=row, column=2, value=total.get("units", 0))
    ws.cell(row=row, column=3, value=total.get("kg", 0))
    _style_range(ws, row, 1, 3, fill=TOTAL_FILL, font=TOTAL_FONT)


def _write_tela(wb, data):
    fab = data.get("fabric", data["expansion"].get("fabric", {}))
    ws = wb.create_sheet("TELA")
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 14
    ws.column_dimensions["E"].width = 14
    ws.column_dimensions["F"].width = 12

    row = 1
    ws.cell(row=row, column=1, value="Pedido de tela — Expansión SPOTS").font = Font(bold=True, size=13)
    row += 2
    headers = ["Material", "Zona / diseño", "Unidades", "Consumo", "Stock seg.", "Tela (kg)"]
    for i, h in enumerate(headers,  start=1):
        ws.cell(row=row, column=i, value=h)
    _style_range(ws, row, 1, 6, fill=HDR_FILL, font=HDR_FONT)
    row += 1

    blanco = fab.get("blanco", {})
    ws.cell(row=row, column=1, value="Blanco")
    ws.cell(row=row, column=2, value="Total expansión")
    ws.cell(row=row, column=3, value=blanco.get("units", 0))
    ws.cell(row=row, column=4, value=f"{FABRIC_KG_PER_UNIT} kg/und")
    ws.cell(row=row, column=5, value=f"+{int(FABRIC_SAFETY_PCT * 100)}%")
    ws.cell(row=row, column=6, value=blanco.get("kg", 0))
    _style_range(ws, row, 1, 6)
    row += 1

    for d in fab.get("blanco_detail", []):
        ws.cell(row=row, column=1, value="↳ Blanco")
        ws.cell(row=row, column=2, value=f"Barquisimeto · {d['detalle']}")
        ws.cell(row=row, column=3, value=d.get("units", 0))
        ws.cell(row=row, column=4, value=f"{FABRIC_KG_PER_UNIT} kg/und")
        ws.cell(row=row, column=5, value=f"+{int(FABRIC_SAFETY_PCT * 100)}%")
        ws.cell(row=row, column=6, value=d.get("kg", 0))
        _style_range(ws, row, 1, 6)
        row += 1

    for r in fab.get("adicional_by_zone", []):
        color = r.get("color", r.get("tipo", "Color"))
        ws.cell(row=row, column=1, value=color)
        ws.cell(row=row, column=2, value=f"{r['zona']} · {r.get('detalle', '')}")
        ws.cell(row=row, column=3, value=r.get("units", 0))
        ws.cell(row=row, column=4, value=f"{FABRIC_KG_PER_UNIT} kg/und")
        ws.cell(row=row, column=5, value=f"+{int(FABRIC_SAFETY_PCT * 100)}%")
        ws.cell(row=row, column=6, value=r.get("kg", 0))
        _style_range(ws, row, 1, 6)
        row += 1

    total = fab.get("total", {})
    ws.cell(row=row, column=1, value="TOTAL").font = TOTAL_FONT
    ws.cell(row=row, column=2, value="Caracas + Valencia + Barquisimeto")
    ws.cell(row=row, column=3, value=total.get("units", 0))
    ws.cell(row=row, column=4, value=f"{FABRIC_KG_PER_UNIT} kg/und")
    ws.cell(row=row, column=5, value=f"+{int(FABRIC_SAFETY_PCT * 100)}%")
    ws.cell(row=row, column=6, value=total.get("kg", 0))
    _style_range(ws, row, 1, 6, fill=TOTAL_FILL, font=TOTAL_FONT)


def _fabric_kg(units: int) -> int:
    return round(units * FABRIC_KG_PER_UNIT * (1 + FABRIC_SAFETY_PCT))


def _parse_label(label: str):
    if " · Blanco (" in label:
        diseno, rest = label.split(" · Blanco (")
        return rest.rstrip(")").upper(), diseno, "Blanco"
    if " · " in label:
        color, zona = label.rsplit(" · ", 1)
        cap = EXPANSION_CAPS.get(zona.upper(), {})
        diseno = cap.get("blanco_diseno") or cap.get("adicional_diseno") or color
        if color != "Blanco" and zona.upper() == "BARQUISIMETO":
            diseno = "Ciudad"
        return zona.upper(), diseno, color
    return None, None, None


def parse_consolidated_sheet(ws, genero: str):
    """Lee filas de detalle desde pestaña CAB o DAMA."""
    tallas = []
    rows = []
    for row in ws.iter_rows(values_only=True):
        vals = list(row)
        if not any(v is not None for v in vals):
            continue
        if vals[0] in (f"SPOTS MANGA CORTA {genero}",):
            tallas = [v for v in vals[1:-1] if v]
            continue
        if vals[0] in (
            "CANTIDADES POR COLORES",
            "TOTAL BLANCO",
            "TOTAL COLORES",
            "TOTAL GENERAL",
        ):
            continue
        if not tallas or not vals[0]:
            continue
        zona, diseno, color = _parse_label(str(vals[0]))
        if not zona:
            continue
        qtys = {str(t): int(vals[i + 1] or 0) for i, t in enumerate(tallas)}
        total = int(vals[len(tallas) + 1] or sum(qtys.values()))
        rows.append({
            "label": vals[0],
            "zona": zona,
            "diseno": diseno,
            "color": color,
            "genero": genero,
            "tallas": qtys,
            "total": total,
        })
    return tallas, rows


def build_manual_bundle(cab_rows, dama_rows, months=DEFAULT_PROD_MONTHS):
    """Construye estructura coherente desde CAB+DAMA editados manualmente."""
    all_rows = cab_rows + dama_rows
    stores = {}
    for r in all_rows:
        z = r["zona"]
        stores.setdefault(z, {
            "store": z,
            "label": EXPANSION_CAPS.get(z, {}).get("label", z.title()),
            "adicional_color": ZONE_ADICIONAL_COLOR.get(z, ""),
            "designs": defaultdict(lambda: defaultdict(lambda: defaultdict(dict))),
        })
        stores[z]["designs"][r["diseno"]][r["color"]][r["genero"]] = dict(r["tallas"])

    by_store = []
    total_blanco = total_color = 0
    blanco_detail = []
    adicional_by_zone = []

    for z in ("CARACAS", "VALENCIA", "BARQUISIMETO"):
        if z not in stores:
            continue
        s = stores[z]
        zb = zc = 0
        designs_meta = []
        for diseno, by_color in sorted(s["designs"].items()):
            for color, by_gen in sorted(by_color.items()):
                t_total = sum(sum(by_gen[g].values()) for g in by_gen)
                designs_meta.append({"diseno": diseno, "color": color, "target_3m": t_total})
                if color == "Blanco":
                    zb += t_total
                    if z == "BARQUISIMETO":
                        blanco_detail.append({
                            "detalle": diseno,
                            "units": t_total,
                            "kg": _fabric_kg(t_total),
                        })
                else:
                    zc += t_total
                    adicional_by_zone.append({
                        "color": color,
                        "zona": z.title(),
                        "detalle": diseno,
                        "units": t_total,
                        "kg": _fabric_kg(t_total),
                    })
        total_z = zb + zc
        if z == "BARQUISIMETO":
            def _design_total(dname, color):
                by_color = s["designs"].get(dname, {})
                by_gen = by_color.get(color, {})
                return sum(sum(t.values()) for t in by_gen.values())

            ciudad_b = _design_total("Ciudad", "Blanco")
            virgen_b = _design_total("Virgen", "Blanco")
            verde = zc
            s["label"] = (
                f"Barquisimeto · 1 tienda · MC · Ciudad {ciudad_b} + Virgen {virgen_b} + "
                f"Verde {verde} · total {total_z}"
            )
        elif z == "CARACAS":
            s["label"] = (
                f"Caracas · 4 tiendas CCS · MC · Blanco {zb} + Azul Marino {zc} · total {total_z}"
            )
        elif z == "VALENCIA":
            s["label"] = (
                f"Valencia · 2 tiendas · MC · Blanco {zb} + Vinotinto {zc} · total {total_z}"
            )
        total_blanco += zb
        total_color += zc
        by_store.append({
            **s,
            "blanco": zb,
            "adicional": zc,
            "total": zb + zc,
            "designs": designs_meta,
            "rows": all_rows,
        })

    total_exp = total_blanco + total_color
    fabric = {
        "kg_per_unit": FABRIC_KG_PER_UNIT,
        "safety_pct": FABRIC_SAFETY_PCT,
        "blanco": {"units": total_blanco, "kg": _fabric_kg(total_blanco)},
        "blanco_detail": blanco_detail,
        "adicional_by_zone": adicional_by_zone,
        "total": {"units": total_exp, "kg": _fabric_kg(total_exp)},
    }
    expansion = {
        "by_store": by_store,
        "total_blanco": total_blanco,
        "total_adicional": total_color,
        "total_expansion": total_exp,
        "nota": (
            f"Cantidades ajustadas manualmente · horizonte {months} meses · "
            "colores: Caracas Azul Marino · Valencia Vinotinto · Barquisimeto Verde."
        ),
    }
    return {
        "months": months,
        "cab_rows": cab_rows,
        "dama_rows": dama_rows,
        "expansion": expansion,
        "fabric": fabric,
        "velocity_months_label": "",
        "high_season_factor": 1.2,
        "december_hs_factor": 1.4,
        "additional_color_factor": 0.7,
    }


def _zone_rows_from_manual(store, genero):
    grouped = defaultdict(lambda: defaultdict(int))
    z = store["store"]
    for r in store.get("rows", []):
        if r["genero"] != genero or r["zona"] != z:
            continue
        label = f"{r['diseno']} ({r['color']})"
        for t, q in r["tallas"].items():
            grouped[label][t] += q
    tallas = [t for t in TALLA_ORDER if any(grouped[l].get(t) for l in grouped)]
    rows = [(label, dict(grouped[label])) for label in sorted(grouped)]
    return tallas, rows


def _write_zone_sheet_manual(wb, store, months):
    zone = store["store"]
    ws = wb.create_sheet(zone.title())
    ws.column_dimensions["A"].width = 34
    for i in range(2, 10):
        ws.column_dimensions[get_column_letter(i)].width = 8

    row = 1
    ws.cell(row=row, column=1, value=f"SPOTS MANGA CORTA — {zone} · Proyección {months} meses")
    ws.cell(row=row, column=1).font = Font(bold=True, size=13)
    row += 2
    ws.cell(row=row, column=1, value=store.get("label", ""))
    row += 2

    zone_total = 0
    for genero in ("CAB", "DAMA"):
        tallas, rows = _zone_rows_from_manual(store, genero)
        if not rows:
            continue
        ws.cell(row=row, column=1, value=genero).font = Font(bold=True, size=11)
        ws.cell(row=row, column=1).fill = SECTION_FILL
        row += 1
        row, sub = _write_matrix(ws, row, f"SPOTS MANGA CORTA {genero} — {zone}", tallas, rows)
        zone_total += sub

    ws.cell(row=row, column=1, value=f"TOTAL ZONA {zone}").font = Font(bold=True, size=11)
    ws.cell(row=row, column=2, value=zone_total).font = Font(bold=True, size=11)


def _write_colores_sheet_manual(wb, bundle, genero):
    ws = wb.create_sheet(genero)
    ws.column_dimensions["A"].width = 36
    for i in range(2, 12):
        ws.column_dimensions[get_column_letter(i)].width = 8

    rows_in = bundle["cab_rows"] if genero == "CAB" else bundle["dama_rows"]
    blanco_rows = [r for r in rows_in if r["color"] == "Blanco"]
    color_rows = [r for r in rows_in if r["color"] != "Blanco"]
    all_tallas = [t for t in TALLA_ORDER if any(r["tallas"].get(t) for r in rows_in)]

    row = 1
    ws.cell(row=row, column=1, value="CANTIDADES POR COLORES").font = Font(bold=True, size=13)
    row += 1
    hdr = row
    ws.cell(row=hdr, column=1, value=f"SPOTS MANGA CORTA {genero}")
    for i, t in enumerate(all_tallas, start=2):
        ws.cell(row=hdr, column=i, value=t)
    ws.cell(row=hdr, column=len(all_tallas) + 2, value="Tot")
    _style_range(ws, hdr, 1, len(all_tallas) + 2, fill=HDR_FILL, font=HDR_FONT)
    row = hdr + 1

    def write_block(items, total_label=None):
        nonlocal row
        col_totals = defaultdict(int)
        section_total = 0
        for r in items:
            ws.cell(row=row, column=1, value=r["label"])
            row_sum = 0
            for i, t in enumerate(all_tallas, start=2):
                qty = int(r["tallas"].get(t, 0) or 0)
                if qty:
                    ws.cell(row=row, column=i, value=qty)
                col_totals[t] += qty
                row_sum += qty
            ws.cell(row=row, column=len(all_tallas) + 2, value=row_sum)
            section_total += row_sum
            _style_range(ws, row, 1, len(all_tallas) + 2)
            row += 1
        if total_label:
            ws.cell(row=row, column=1, value=total_label).font = TOTAL_FONT
            for i, t in enumerate(all_tallas, start=2):
                if col_totals[t]:
                    ws.cell(row=row, column=i, value=col_totals[t])
            ws.cell(row=row, column=len(all_tallas) + 2, value=section_total)
            _style_range(ws, row, 1, len(all_tallas) + 2, fill=TOTAL_FILL, font=TOTAL_FONT)
            row += 1
        return section_total, col_totals

    grand_cols = defaultdict(int)
    b_tot, b_cols = write_block(blanco_rows, "TOTAL BLANCO")
    row += 1
    c_tot, c_cols = write_block(color_rows, "TOTAL COLORES")
    for t, v in b_cols.items():
        grand_cols[t] += v
    for t, v in c_cols.items():
        grand_cols[t] += v
    grand = b_tot + c_tot
    ws.cell(row=row, column=1, value="TOTAL GENERAL").font = Font(bold=True, size=11)
    for i, t in enumerate(all_tallas, start=2):
        if grand_cols[t]:
            ws.cell(row=row, column=i, value=grand_cols[t])
    ws.cell(row=row, column=len(all_tallas) + 2, value=grand)
    _style_range(ws, row, 1, len(all_tallas) + 2, fill=PatternFill("solid", fgColor="D1FAE5"), font=TOTAL_FONT)


def export_from_bundle(bundle, out_path: Path):
    months = bundle["months"]
    data = {**bundle, **bundle["fabric"]}
    wb = Workbook()
    wb.remove(wb.active)
    _write_resumen(wb, bundle, months)
    _write_colores_sheet_manual(wb, bundle, "CAB")
    _write_colores_sheet_manual(wb, bundle, "DAMA")
    for store in bundle["expansion"]["by_store"]:
        _write_zone_sheet_manual(wb, store, months)
    _write_tela(wb, bundle)
    wb.save(out_path)
    return out_path


def sync_produccion_xlsx(source_path: Path, out_path: Path = OUT_PATH, months=DEFAULT_PROD_MONTHS):
    """Toma CAB/DAMA editados manualmente y regenera todas las pestañas."""
    from openpyxl import load_workbook

    wb = load_workbook(source_path, data_only=True)
    _, cab_rows = parse_consolidated_sheet(wb["CAB"], "CAB")
    _, dama_rows = parse_consolidated_sheet(wb["DAMA"], "DAMA")
    bundle = build_manual_bundle(cab_rows, dama_rows, months)
    export_from_bundle(bundle, out_path)
    return bundle, out_path


def export_produccion_xlsx(months: int = DEFAULT_PROD_MONTHS, out_path: Path = OUT_PATH) -> Path:
    data = rebuild_data()
    wb = Workbook()
    wb.remove(wb.active)

    _write_resumen(wb, data, months)
    _write_colores_sheet(wb, data, "CAB", months)
    _write_colores_sheet(wb, data, "DAMA", months)
    for store in data["expansion"]["by_store"]:
        _write_zone_sheet(wb, store, months)
    _write_tela(wb, data)

    wb.save(out_path)
    return out_path


def main():
    import sys

    src = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if src and src.exists():
        bundle, path = sync_produccion_xlsx(src)
        exp = bundle["expansion"]
        print(f"Synced {src.name} → {path}")
        print(f"Expansión {exp['total_expansion']} und · Tela {bundle['fabric']['total']['kg']} kg")
        for s in exp["by_store"]:
            print(f"  {s['store']}: {s['total']} (B{s['blanco']} + {s['adicional_color']} {s['adicional']})")
        return

    path = export_produccion_xlsx()
    data = rebuild_data()
    exp = data["expansion"]
    print(f"Wrote {path}")
    print(f"Expansión {exp['total_expansion']} und · Tela {data['fabric']['total']['kg']} kg")


if __name__ == "__main__":
    main()
