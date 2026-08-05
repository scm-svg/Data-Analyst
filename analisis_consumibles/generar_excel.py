# -*- coding: utf-8 -*-
"""
Genera el Excel final: Analisis_Consumibles_Taller_Tiendas_2meses.xlsx
Hojas: RESUMEN EJECUTIVO, METODOLOGIA, PARAMETROS, KPI ATENCION, TALLER, TIENDAS,
UNIFICADO, DISTRIBUCION TIENDAS, DISTRIBUCION TALLER, TENDENCIA SEMANAL, GRAFICOS,
DATA TALLER, DATA TIENDAS, DATA CONSOLIDADA, CALIDAD DE DATOS.
"""
import datetime as dt

import pandas as pd
import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell

from analisis_core import (limpiar, tabla_productos, modelo, kpis_alcance,
                           tabla_semanal, matriz, top_no_disponible,
                           Z_SERVICIO, Z_X, Z_Y, Z_Z, LT_DEFAULT,
                           P_SEMANAL, P_QUINCENAL, P_MENSUAL)

OUT = "/workspace/analisis_consumibles/Analisis_Consumibles_Taller_Tiendas_2meses.xlsx"

# Referencias a PARAMETROS usadas por las fórmulas vivas
PR_LT = "PARAMETROS!$B$7"
PR_P = {"SEM": "PARAMETROS!$B$8", "QUINC": "PARAMETROS!$B$9", "MENS": "PARAMETROS!$B$10"}
PR_ZX, PR_ZY, PR_ZZ = "PARAMETROS!$B$11", "PARAMETROS!$B$12", "PARAMETROS!$B$13"

MESES_ES = {1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL", 5: "MAYO", 6: "JUNIO",
            7: "JULIO", 8: "AGOSTO", 9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"}


def make_formats(wb):
    F = {}
    F["titulo"] = wb.add_format({"bold": True, "font_size": 16, "font_color": "#FFFFFF",
                                 "bg_color": "#1F4E78", "align": "left", "valign": "vcenter"})
    F["subtitulo"] = wb.add_format({"italic": True, "font_size": 10, "font_color": "#404040",
                                    "text_wrap": True, "valign": "top"})
    F["seccion"] = wb.add_format({"bold": True, "font_size": 12, "font_color": "#1F4E78",
                                  "bottom": 2, "border_color": "#1F4E78"})
    F["hdr"] = wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#2E75B6",
                              "border": 1, "align": "center", "valign": "vcenter", "text_wrap": True})
    F["txt"] = wb.add_format({"border": 1, "valign": "vcenter"})
    F["txt_wrap"] = wb.add_format({"border": 1, "valign": "top", "text_wrap": True})
    F["txt_b"] = wb.add_format({"border": 1, "valign": "vcenter", "bg_color": "#F2F7FB"})
    F["int"] = wb.add_format({"border": 1, "num_format": "#,##0", "align": "center", "valign": "vcenter"})
    F["int_b"] = wb.add_format({"border": 1, "num_format": "#,##0", "align": "center", "bg_color": "#F2F7FB"})
    F["num2"] = wb.add_format({"border": 1, "num_format": "0.00", "align": "center", "valign": "vcenter"})
    F["num2_b"] = wb.add_format({"border": 1, "num_format": "0.00", "align": "center", "bg_color": "#F2F7FB"})
    F["pct"] = wb.add_format({"border": 1, "num_format": "0.0%", "align": "center", "valign": "vcenter"})
    F["pct_b"] = wb.add_format({"border": 1, "num_format": "0.0%", "align": "center", "bg_color": "#F2F7FB"})
    F["edit"] = wb.add_format({"border": 1, "num_format": "0", "align": "center",
                               "bg_color": "#FFF2CC", "valign": "vcenter"})
    F["edit2"] = wb.add_format({"border": 1, "num_format": "0.00", "align": "center",
                                "bg_color": "#FFF2CC", "valign": "vcenter"})
    F["fecha"] = wb.add_format({"border": 1, "num_format": "dd/mm/yyyy", "align": "center"})
    F["total_lbl"] = wb.add_format({"bold": True, "border": 1, "bg_color": "#D9E2F3"})
    F["total_int"] = wb.add_format({"bold": True, "border": 1, "bg_color": "#D9E2F3",
                                    "num_format": "#,##0", "align": "center"})
    F["total_num"] = wb.add_format({"bold": True, "border": 1, "bg_color": "#D9E2F3",
                                    "num_format": "0.00", "align": "center"})
    F["total_pct"] = wb.add_format({"bold": True, "border": 1, "bg_color": "#D9E2F3",
                                    "num_format": "0.0%", "align": "center"})
    F["kpi_big"] = wb.add_format({"bold": True, "font_size": 14, "font_color": "#1F4E78",
                                  "align": "center", "border": 1, "bg_color": "#EAF1F8",
                                  "num_format": "0.0%"})
    F["nota"] = wb.add_format({"font_size": 9, "font_color": "#595959", "italic": True,
                               "text_wrap": True, "valign": "top"})
    F["ok"] = wb.add_format({"border": 1, "align": "center", "bg_color": "#E2EFDA",
                             "font_color": "#375623", "bold": True})
    F["bad"] = wb.add_format({"border": 1, "align": "center", "bg_color": "#FCE4E4",
                              "font_color": "#9C0006", "bold": True})
    return F


def escribir_titulo(ws, F, titulo, explicacion, ncols):
    ws.merge_range(0, 0, 0, ncols - 1, titulo, F["titulo"])
    ws.set_row(0, 26)
    ws.merge_range(1, 0, 1, ncols - 1, explicacion, F["subtitulo"])
    ws.set_row(1, 42)


def hoja_modelo(wb, F, nombre, tab, titulo, expl, color_tab):
    """Hojas TALLER / TIENDAS / UNIFICADO con fórmulas vivas MIN/MAX/PEDIDO."""
    ws = wb.add_worksheet(nombre)
    ws.set_tab_color(color_tab)
    hdrs = ["PRODUCTO", "CATEGORÍA", "Nº SOLICITUDES", "UNDS SOLICITADAS (2m)",
            "UNDS ATENDIDAS", "UNDS NO DISPONIBLES", "% ATENCIÓN (UNDS)",
            "DEMANDA DIARIA (D)", "σ SEMANAL", "CLASE DEMANDA", "z NIVEL SERVICIO ✎",
            "LEAD TIME (DÍAS) ✎", "STOCK SEGURIDAD (SS)", "MIN = PUNTO REORDEN",
            "STOCK ACTUAL ✎", "MAX SEMANAL", "PEDIDO SEMANAL",
            "MAX QUINCENAL", "PEDIDO QUINCENAL", "MAX MENSUAL", "PEDIDO MENSUAL"]
    escribir_titulo(ws, F, titulo, expl, len(hdrs))
    hrow = 3
    for c, h in enumerate(hdrs):
        ws.write(hrow, c, h, F["hdr"])
    ws.set_row(hrow, 44)

    n = len(tab)
    first, last = hrow + 1, hrow + n          # filas 0-based de datos
    for i, r in tab.iterrows():
        row = hrow + 1 + i
        band = i % 2 == 1
        fT = F["txt_b"] if band else F["txt"]
        fI = F["int_b"] if band else F["int"]
        fN = F["num2_b"] if band else F["num2"]
        fP = F["pct_b"] if band else F["pct"]
        ws.write(row, 0, r["ARTICULO"], fT)
        ws.write(row, 1, r["CATEGORIA"], fT)
        ws.write_number(row, 2, r["SOLICITUDES"], fI)
        ws.write_number(row, 3, r["UNDS"], fI)
        ws.write_number(row, 4, r["UNDS_ATEND"], fI)
        ws.write_number(row, 5, r["UNDS_NODISP"], fI)
        ws.write_number(row, 6, r["PCT_ATENCION"], fP)
        ws.write_number(row, 7, round(r["D_DIARIA"], 4), fN)
        ws.write_number(row, 8, round(r["SIGMA_SEM"], 4), fN)
        ws.write(row, 9, r["CLASE"], fT)
        cH = xl_rowcol_to_cell(row, 7)    # D diaria
        cI = xl_rowcol_to_cell(row, 8)    # sigma semanal
        cJ = xl_rowcol_to_cell(row, 9)    # clase
        cK = xl_rowcol_to_cell(row, 10)   # z
        cL = xl_rowcol_to_cell(row, 11)   # LT
        cM = xl_rowcol_to_cell(row, 12)   # SS
        cO = xl_rowcol_to_cell(row, 14)   # stock actual
        # z editable: por defecto toma el de su clase XYZ en PARAMETROS
        ws.write_formula(row, 10,
                         f'=IF(LEFT({cJ},1)="X",{PR_ZX},IF(LEFT({cJ},1)="Y",{PR_ZY},{PR_ZZ}))',
                         F["edit2"], float(r["Z_VAL"]))
        # LT editable (por defecto = PARAMETROS!$B$7)
        ws.write_formula(row, 11, f"={PR_LT}", F["edit"], LT_DEFAULT)
        ws.write_formula(row, 12, f"=ROUND({cK}*{cI}*SQRT({cL}/7),2)", fN, r["SS"])
        ws.write_formula(row, 13, f"=ROUNDUP({cH}*{cL}+{cM},0)", fI, r["MIN"])
        ws.write_number(row, 14, 0, F["edit"])          # stock actual editable
        for tag, colmax in [("SEM", 15), ("QUINC", 17), ("MENS", 19)]:
            ws.write_formula(row, colmax,
                             f"=ROUNDUP({cH}*({cL}+{PR_P[tag]})+{cM},0)",
                             fI, int(r[f"MAX_{tag}"]))
            ws.write_formula(row, colmax + 1,
                             f"=MAX(0,{xl_rowcol_to_cell(row, colmax)}-{cO})",
                             fI, int(r[f"PEDIDO_{tag}"]))
    # fila TOTAL
    def _letra(c):
        return "".join(ch for ch in xl_rowcol_to_cell(0, c) if ch.isalpha())

    tr = last + 1
    ws.write(tr, 0, "TOTAL", F["total_lbl"]); ws.write(tr, 1, "", F["total_lbl"])
    for c, key in [(2, "SOLICITUDES"), (3, "UNDS"), (4, "UNDS_ATEND"), (5, "UNDS_NODISP")]:
        ws.write_formula(tr, c, f"=SUM({_letra(c)}{first+1}:{_letra(c)}{last+1})",
                         F["total_int"], int(tab[key].sum()))
    tot_u, tot_a = tab["UNDS"].sum(), tab["UNDS_ATEND"].sum()
    ws.write_formula(tr, 6, f"=E{tr+1}/D{tr+1}", F["total_pct"], tot_a / tot_u)
    ws.write_formula(tr, 7, f"=SUM(H{first+1}:H{last+1})", F["total_num"], round(tab["D_DIARIA"].sum(), 4))
    for c in (8, 9, 10, 11, 12, 14):
        ws.write(tr, c, "", F["total_lbl"])
    ws.write_formula(tr, 13, f"=SUM(N{first+1}:N{last+1})", F["total_int"], int(tab["MIN"].sum()))
    for tag, cmax, cped in [("SEM", 15, 16), ("QUINC", 17, 18), ("MENS", 19, 20)]:
        ws.write_formula(tr, cmax, f"=SUM({_letra(cmax)}{first+1}:{_letra(cmax)}{last+1})",
                         F["total_int"], int(tab[f"MAX_{tag}"].sum()))
        ws.write_formula(tr, cped, f"=SUM({_letra(cped)}{first+1}:{_letra(cped)}{last+1})",
                         F["total_int"], int(tab[f"PEDIDO_{tag}"].sum()))

    ws.conditional_format(first, 6, last, 6,
                          {"type": "3_color_scale", "min_color": "#F8696B",
                           "mid_color": "#FFEB84", "max_color": "#63BE7B"})
    for col in (16, 18, 20):
        ws.conditional_format(first, col, last, col, {"type": "data_bar", "bar_color": "#2E75B6"})
    ws.freeze_panes(first, 2)
    ws.autofilter(hrow, 0, last, len(hdrs) - 1)
    anchos = [34, 23, 10, 12, 11, 12, 10, 10, 9, 15, 10, 10, 10, 11, 10, 10, 11, 11, 12, 10, 11]
    for c, a in enumerate(anchos):
        ws.set_column(c, c, a)
    ws.merge_range(last + 3, 0, last + 3, 20,
                   "✎ Celdas amarillas editables: LEAD TIME por producto, z de NIVEL DE SERVICIO y STOCK ACTUAL; "
                   "SS, MIN, MAX y PEDIDO se recalculan solos. PEDIDO = MAX − STOCK ACTUAL "
                   "(si el stock es 0, el pedido parte de cero). "
                   "MIN = D×LT + SS · MAX = D×(LT+P) + SS (P = 7/14/30 días) · SS = z×σ semanal×√(LT/7). "
                   "CLASE DEMANDA: X regular / Y variable / Z intermitente — define el z inicial "
                   "(95%/90%/80%, configurable en PARAMETROS). Ítems Z: evaluar compra bajo pedido.",
                   F["nota"])
    ws.set_row(last + 3, 44)
    return ws, tr


def main():
    df, excluidas, observaciones = limpiar()
    df_t = df[df["ORIGEN"] == "TALLER"]
    df_i = df[df["ORIGEN"] == "TIENDAS"]

    tab_t, dias_t = tabla_productos(df_t)
    tab_i, dias_i = tabla_productos(df_i)
    tab_u, dias_u = tabla_productos(df)
    mod_t, mod_i, mod_u = modelo(tab_t), modelo(tab_i), modelo(tab_u)
    kpis = kpis_alcance(df)
    semanal = tabla_semanal(df)
    mat_tiendas = matriz(df_i, "SUCURSAL")
    mat_taller = matriz(df_t, "SUCURSAL")
    top_nd = top_no_disponible(df)

    f_min, f_max = df["FECHA"].min(), df["FECHA"].max()
    periodo = f"{f_min:%d/%m/%Y} al {f_max:%d/%m/%Y}"
    semanas = dias_u / 7

    wb = xlsxwriter.Workbook(OUT, {"nan_inf_to_errors": True})
    F = make_formats(wb)

    # =================================================================
    # 1. RESUMEN EJECUTIVO
    # =================================================================
    ws = wb.add_worksheet("RESUMEN EJECUTIVO")
    ws.set_tab_color("#1F4E78")
    ws.set_column("A:A", 30); ws.set_column("B:J", 15)
    ws.merge_range("A1:J1", "ANÁLISIS DE CONSUMIBLES — TALLER Y TIENDAS · HISTORIAL 2 MESES", F["titulo"])
    ws.set_row(0, 30)
    ws.merge_range("A2:J2",
                   f"Período analizado: {periodo} ({dias_u} días ≈ {semanas:.1f} semanas). "
                   "Objetivo: dimensionar el pedido periódico de consumibles con datos reales de consumo, "
                   "establecer stock MÍNIMO y MÁXIMO por producto y comparar 3 frecuencias de compra "
                   "(semanal, quincenal y mensual). Todo el análisis usa EXCLUSIVAMENTE los dos archivos "
                   "de solicitudes suministrados.", F["subtitulo"])
    ws.set_row(1, 44)

    r = 3
    ws.write(r, 0, "1 · FUENTES DE DATOS", F["seccion"]); r += 1
    fuentes = [
        ("TALLER", "solicitudes_taller_2_meses.xlsx — hoja 'CRECO SOLICITUDES'",
         f"{len(df_t)} solicitudes válidas (09-jun al 05-ago)"),
        ("TIENDAS", "_Solicitudes (TIENDAS) consumibles 2meses.xlsx — 7 tiendas "
                    "(GRIETA, SAMBIL VALENCIA, GRAND PLAZ, CERRO VERDE, SAMBIL CHACAO, TOLON, MARGARITA)",
         f"{len(df_i)} solicitudes válidas (08-jun al 04-ago)"),
        ("CATÁLOGO", "Hoja 'INVENTARIO DE CONSUMIBLES' del archivo de tiendas",
         "173 productos con categoría (usada para clasificar)"),
    ]
    for a, b, c in fuentes:
        ws.write(r, 0, a, F["total_lbl"]); ws.merge_range(r, 1, r, 7, b, F["txt"])
        ws.merge_range(r, 8, r, 9, c, F["txt"]); r += 1

    r += 1
    ws.write(r, 0, "2 · INDICADORES CLAVE DE ATENCIÓN", F["seccion"]); r += 1
    hdr = ["ALCANCE", "SOLICITUDES", "ATENDIDAS", "NO DISPONIBLES", "% ATENDIDAS",
           "% NO DISPONIBLES", "UNDS SOLICITADAS", "UNDS ATENDIDAS", "UNDS NO CUBIERTAS", "% UNDS ATENDIDAS"]
    for c, h in enumerate(hdr):
        ws.write(r, c, h, F["hdr"])
    ws.set_row(r, 30); r += 1
    for nombre in ["TALLER", "TIENDAS", "UNIFICADO"]:
        k = kpis[nombre]
        ws.write(r, 0, nombre, F["total_lbl"])
        ws.write_number(r, 1, k["solicitudes"], F["int"])
        ws.write_number(r, 2, k["atendidas"], F["int"])
        ws.write_number(r, 3, k["no_disponible"], F["int"])
        ws.write_number(r, 4, k["pct_atendidas"], F["kpi_big"])
        ws.write_number(r, 5, k["pct_no_disponible"], F["kpi_big"])
        ws.write_number(r, 6, k["unds"], F["int"])
        ws.write_number(r, 7, k["unds_atend"], F["int"])
        ws.write_number(r, 8, k["unds_nodisp"], F["int"])
        ws.write_number(r, 9, k["pct_unds_atend"], F["pct"])
        r += 1
    ws.merge_range(r, 0, r, 9,
                   "ATENDIDA = solicitudes en estado RECIBIDO / ENTREGADO / ENVIADO + SOLICITADO "
                   "(criterio indicado: 'recibido e incluye solicitado'). NO ATENDIDA = NO DISPONIBLE. "
                   "Las 12 filas sin estado (SAMBIL VALENCIA 04-ago) se tratan como SOLICITADO. "
                   "Detalle en la hoja KPI ATENCION.", F["nota"])
    r += 2

    ws.write(r, 0, "3 · COMPRA SUGERIDA SEGÚN FRECUENCIA (UNIFICADO, stock inicial = 0)", F["seccion"]); r += 1
    for c, h in enumerate(["OPCIÓN", "CICLO (DÍAS)", "UNDS A PEDIR (PRIMER PEDIDO)",
                           "STOCK MÁXIMO TOTAL", "STOCK MÍNIMO TOTAL (PUNTO REORDEN)", "LECTURA"]):
        ws.write(r, c, h, F["hdr"])
    r += 1
    tr_uni = None  # se completa tras crear la hoja UNIFICADO
    filas_opciones = r
    r += 3

    r += 1
    ws.write(r, 0, "4 · TOP 10 PRODUCTOS POR UNIDADES (UNIFICADO, 2 MESES)", F["seccion"]); r += 1
    for c, h in enumerate(["#", "PRODUCTO", "CATEGORÍA", "UNDS 2 MESES", "UNDS/SEMANA", "% ATENCIÓN"]):
        ws.write(r, c, h, F["hdr"])
    r += 1
    for i, row in mod_u.head(10).iterrows():
        ws.write_number(r, 0, i + 1, F["int"])
        ws.write(r, 1, row["ARTICULO"], F["txt"])
        ws.write(r, 2, row["CATEGORIA"], F["txt"])
        ws.write_number(r, 3, int(row["UNDS"]), F["int"])
        ws.write_number(r, 4, round(row["D_DIARIA"] * 7, 1), F["num2"])
        ws.write_number(r, 5, row["PCT_ATENCION"], F["pct"])
        r += 1

    r += 1
    ws.write(r, 0, "5 · CONCLUSIONES Y RECOMENDACIONES", F["seccion"]); r += 1
    k = kpis["UNIFICADO"]
    intermitentes = mod_u[(mod_u["SOLICITUDES"] <= 2) & (mod_u["UNDS"] <= 4)]
    top_nd_txt = ", ".join(f"{x.ARTICULO} ({x.VECES} veces)" for x in top_nd.head(5).itertuples())
    concl = [
        f"1. En 2 meses se registraron {k['solicitudes']} solicitudes por {k['unds']:,} unidades: "
        f"{kpis['TALLER']['solicitudes']} del taller ({kpis['TALLER']['unds']:,} unds) y "
        f"{kpis['TIENDAS']['solicitudes']} de tiendas ({kpis['TIENDAS']['unds']:,} unds). "
        "Las tiendas concentran el grueso del consumo (bolsas, stickers, limpieza).",
        f"2. Atención global: {k['pct_atendidas']:.1%} de las solicitudes fueron atendidas y "
        f"{k['pct_no_disponible']:.1%} quedaron NO DISPONIBLES ({k['no_disponible']} solicitudes, "
        f"{k['unds_nodisp']:,} unds no cubiertas). El taller tuvo {kpis['TALLER']['pct_atendidas']:.1%} "
        f"de atención y las tiendas {kpis['TIENDAS']['pct_atendidas']:.1%}.",
        f"3. Productos que más veces quedaron NO DISPONIBLES: {top_nd_txt}. "
        "Conviene asegurar proveedor/stock de estos ítems primero: son demanda real que hoy se pierde.",
        f"4. La demanda NO cubierta ({k['unds_nodisp']:,} unds) NO está en las cifras de consumo atendido: "
        "los MIN/MAX de este archivo se calcularon sobre la demanda SOLICITADA (real), "
        "precisamente para corregir ese desabastecimiento.",
        f"5. {len(intermitentes)} de {len(mod_u)} productos son de demanda intermitente "
        "(≤2 solicitudes y ≤4 unds en 2 meses). Para ellos el MÁXIMO calculado es bajo: "
        "evalúe comprarlos solo bajo pedido para no inmovilizar capital.",
        "6. Frecuencia recomendada: la opción QUINCENAL equilibra capital de trabajo y riesgo de quiebre "
        "de stock con proveedores de ~1 semana de lead time. Si el proveedor exige pedido mensual, "
        "use la columna PEDIDO MENSUAL; si puede reaccionar semanal, la SEMANAL minimiza inventario. "
        "Compare los totales en la sección 3.",
        "7. Ajuste el LEAD TIME y el z de NIVEL DE SERVICIO por producto (columnas amarillas en "
        "TALLER/TIENDAS/UNIFICADO) cuando tenga el dato real del proveedor: MIN/MAX/PEDIDO se recalculan "
        "automáticamente. Los productos clase Z (intermitentes) son candidatos a compra bajo pedido.",
        "8. Mejora de registro: corregir el estado 'ENTRGADO' (typo), registrar el estado en TODAS las "
        "solicitudes (12 quedaron vacías el 04-ago) y agregar 'REGLETA' al catálogo de consumibles.",
    ]
    for t in concl:
        ws.merge_range(r, 0, r, 9, t, F["txt_wrap"])
        ws.set_row(r, 42)
        r += 1

    r += 1
    ws.write(r, 0, "6 · GUÍA DEL ARCHIVO", F["seccion"]); r += 1
    guia = [
        ("METODOLOGIA", "Cómo se limpió la data, definiciones y fórmulas del modelo MIN/MAX."),
        ("PARAMETROS", "Nivel de servicio (z), lead time por defecto y días de ciclo. Editables."),
        ("KPI ATENCION", "% de solicitudes atendidas vs no disponibles por alcance, sucursal, mes y producto."),
        ("TALLER / TIENDAS / UNIFICADO", "Tablas por producto con demanda, MIN/MAX y PEDIDO para las 3 frecuencias."),
        ("DISTRIBUCION TIENDAS / TALLER", "En qué sucursal se consume cada producto (para repartir el pedido)."),
        ("TENDENCIA SEMANAL", "Evolución del consumo semana a semana."),
        ("GRAFICOS", "Visualización de atención, top productos, tendencia y faltantes."),
        ("DATA TALLER / TIENDAS / CONSOLIDADA", "Data limpia y clasificada usada en todos los cálculos."),
        ("CALIDAD DE DATOS", "Filas excluidas y observaciones de limpieza."),
    ]
    for a, b in guia:
        ws.write(r, 0, a, F["total_lbl"]); ws.merge_range(r, 1, r, 9, b, F["txt"]); r += 1

    # =================================================================
    # 2. METODOLOGIA
    # =================================================================
    ws = wb.add_worksheet("METODOLOGIA")
    ws.set_tab_color("#7F7F7F")
    ws.set_column("A:A", 4); ws.set_column("B:B", 130)
    ws.merge_range("A1:B1", "METODOLOGÍA, DEFINICIONES Y SUPUESTOS", F["titulo"])
    ws.set_row(0, 26)
    met = [
        ("1 · ALCANCE Y FUENTES", [
            f"Se usaron EXCLUSIVAMENTE los 2 archivos suministrados. Historial completo desde cero: "
            f"{periodo} ({dias_u} días). Taller: {dias_t} días de registro (09-jun al 05-ago); "
            f"tiendas: {dias_i} días (08-jun al 04-ago).",
            "Cada fila = 1 solicitud de un artículo con su cantidad (unidades según lo registrado: "
            "und, paquete, galón, caja…). El análisis se concentra en UNIDADES, tal como se pidió.",
        ]),
        ("2 · LIMPIEZA DE DATOS", [
            "• Se eliminaron 4 filas basura (3 vacías con '.' en TOLON y 1 sin datos en TALLER). Detalle en CALIDAD DE DATOS.",
            "• 'ENTRGADO' (error de tipeo) se normalizó a 'ENTREGADO' (136 filas del taller).",
            "• 12 solicitudes sin estado (SAMBIL VALENCIA, 04-ago, último día del registro) se tratan como SOLICITADO.",
            "• 1 solicitud del taller sin artículo (Kiria Pinto, 30-jun, 3 unds ENTREGADO) cuenta para los KPIs "
            "generales pero no puede asignarse a ningún producto.",
            "• Cuando ARTICULO estaba vacío se usó CARACTER ADICIONAL (caso 'REGLETA').",
            "• No hubo cantidades negativas ni cero; todas son enteros positivos. No hubo duplicados reales.",
        ]),
        ("3 · CLASIFICACIÓN DE ATENCIÓN (KPI PEDIDO)", [
            "ATENDIDA = RECIBIDO + ENTREGADO + ENVIADO + SOLICITADO (criterio: 'recibido e incluye solicitado').",
            "NO ATENDIDA = NO DISPONIBLE.",
            "% ATENDIDA = solicitudes atendidas / total de solicitudes. Se reporta también en base a unidades.",
        ]),
        ("4 · MODELO DE INVENTARIO (POR PRODUCTO)", [
            "Demanda diaria D = unidades solicitadas en los 2 meses / días del período.",
            "Se usa la demanda SOLICITADA (no solo la atendida) porque lo NO DISPONIBLE es demanda real insatisfecha.",
            "Variabilidad σ SEMANAL = desviación estándar del consumo por semanas COMPLETAS del período. "
            "Se trabaja en semanas (no en días) porque las tiendas retiran en lotes; así el stock de seguridad "
            "no se infla artificialmente.",
            "Clase de demanda (XYZ): X = regular (CV semanal ≤ 0.5) → z = 1.65 (95% de servicio); "
            "Y = variable (CV 0.5–1) → z = 1.28 (90%); Z = intermitente (CV > 1 o ≤2 solicitudes pequeñas) "
            "→ z = 0.84 (80%). Así los productos parejos se protegen más y los erráticos no inflan el inventario.",
            "Stock de seguridad SS = z × σ semanal × √(LT/7)  →  cubre la variabilidad mientras llega el pedido.",
            "MÍNIMO (punto de reorden) = D × LT + SS  →  cuando el stock baje de este valor, hay que pedir.",
            "MÁXIMO (nivel objetivo) = D × (LT + P) + SS, donde P = días del ciclo de compra "
            "(7 semanal, 14 quincenal, 30 mensual).",
            "PEDIDO SUGERIDO = MÁXIMO − stock actual. Como el historial arranca desde cero, el stock actual "
            "por defecto es 0 y el primer pedido = MÁXIMO.",
            "Todas estas celdas son FÓRMULAS VIVAS: cambie LT y z por producto (columnas amarillas), "
            "los z por clase o los P (en PARAMETROS) y todo se recalcula.",
        ]),
        ("5 · TRES OPCIONES DE FRECUENCIA", [
            f"SEMANAL (P={P_SEMANAL}d): pedidos pequeños y frecuentes → menor inventario promedio inmovilizado, "
            "más trabajo administrativo y dependencia de que el proveedor cumpla cada semana.",
            f"QUINCENAL (P={P_QUINCENAL}d): equilibrio entre capital de trabajo y riesgo de quiebre de stock. "
            "Opción recomendada como punto de partida.",
            f"MENSUAL (P={P_MENSUAL}d): un solo pedido grande al mes → menor costo administrativo, "
            "pero mayor inventario promedio y mayor riesgo si un proveedor falla (cubrir con el SS).",
        ]),
        ("6 · SUPUESTOS Y LIMITACIONES", [
            "• Lead time (LT): los archivos no traen tiempos de entrega. Se parte de LT = 7 días para todos "
            "los productos y se deja EDITABLE por producto (columna amarilla) porque puede variar por ítem/proveedor.",
            "• 2 meses es una ventana corta: productos intermitentes (1-2 solicitudes) tienen estadística débil; "
            "sus MIN/MAX deben tomarse como referencia inicial y refinarse con más historia.",
            "• No hay precios ni unidades de empaque: las cantidades son unidades tal como se registraron.",
            "• Agosto solo tiene 4-5 días registrados (mes parcial).",
            "• Productos estacionales (p. ej. 'NAVIDAD 2024') pueden no repetir su demanda fuera de temporada.",
        ]),
    ]
    r = 2
    for sec, parrafos in met:
        ws.write(r, 1, sec, F["seccion"]); r += 1
        for p in parrafos:
            ws.write(r, 1, p, F["txt_wrap"])
            ws.set_row(r, max(15, 14 * (len(p) // 118 + 1)))
            r += 1
        r += 1

    # =================================================================
    # 3. PARAMETROS  (¡posiciones fijas: B7=z, B8=LT, B9..B11=P!)
    # =================================================================
    ws = wb.add_worksheet("PARAMETROS")
    ws.set_tab_color("#FFC000")
    ws.set_column("A:A", 38); ws.set_column("B:B", 14); ws.set_column("C:C", 95)
    ws.merge_range("A1:C1", "PARÁMETROS DEL MODELO (celdas amarillas editables)", F["titulo"])
    ws.set_row(0, 26)
    ws.write("A3", "PARÁMETRO", F["hdr"]); ws.write("B3", "VALOR", F["hdr"]); ws.write("C3", "DESCRIPCIÓN", F["hdr"])
    filas_param = [
        ("Días del período — TALLER", dias_t, "Del 09-jun-2026 al 05-ago-2026 (informativo).", F["int"], False),
        ("Días del período — TIENDAS", dias_i, "Del 08-jun-2026 al 04-ago-2026 (informativo).", F["int"], False),
        ("Días del período — UNIFICADO", dias_u, "Ventana completa del análisis (informativo).", F["int"], False),
        ("Lead time por defecto (días)", LT_DEFAULT, "Tiempo entre pedir y recibir. Es el valor inicial de la "
         "columna LEAD TIME de cada producto (editable allí producto por producto, porque varía por ítem/proveedor).", F["int"], True),
        ("P — Ciclo SEMANAL (días)", P_SEMANAL, "Días entre pedidos en la opción semanal.", F["int"], True),
        ("P — Ciclo QUINCENAL (días)", P_QUINCENAL, "Días entre pedidos en la opción quincenal.", F["int"], True),
        ("P — Ciclo MENSUAL (días)", P_MENSUAL, "Días entre pedidos en la opción mensual.", F["int"], True),
        ("z — Clase X (demanda regular)", Z_X, "1.65 → 95% de no quedarse sin stock durante el lead time. "
         "Se aplica a productos de consumo parejo (CV semanal ≤ 0.5).", F["edit2"], True),
        ("z — Clase Y (demanda variable)", Z_Y, "1.28 → 90%. Productos con consumo irregular "
         "(CV semanal entre 0.5 y 1).", F["edit2"], True),
        ("z — Clase Z (demanda intermitente)", Z_Z, "0.84 → 80%. Productos esporádicos "
         "(CV semanal > 1 o ≤2 solicitudes pequeñas). Para ellos considere compra bajo pedido.", F["edit2"], True),
    ]
    for i, (a, b, c, fmt, edit) in enumerate(filas_param):
        row = 3 + i                                     # filas 4..13 → B7..B13 coinciden con PR_*
        ws.write(row, 0, a, F["txt"])
        ws.write_number(row, 1, b, F["edit2"] if edit and fmt is F["edit2"] else (F["edit"] if edit else fmt))
        ws.write(row, 2, c, F["txt_wrap"])
        ws.set_row(row, 30)
    ws.merge_range("A15:C15",
                   "Estos valores alimentan las fórmulas de las hojas TALLER, TIENDAS y UNIFICADO: "
                   "al modificarlos, SS / MIN / MAX / PEDIDO se recalculan automáticamente en todo el libro. "
                   "El z de cada producto puede sobreescribirse individualmente en su columna amarilla.",
                   F["nota"])

    # =================================================================
    # 4. KPI ATENCION
    # =================================================================
    ws = wb.add_worksheet("KPI ATENCION")
    ws.set_tab_color("#70AD47")
    escribir_titulo(ws, F, "% DE SOLICITUDES ATENDIDAS vs NO DISPONIBLES",
                    "ATENDIDA = RECIBIDO/ENTREGADO/ENVIADO + SOLICITADO (criterio indicado). "
                    "NO ATENDIDA = NO DISPONIBLE. Se muestra por alcance, estado, sucursal, mes y producto, "
                    "en base a número de solicitudes y a unidades.", 10)
    ws.set_column("A:A", 26); ws.set_column("B:J", 14)
    r = 3
    ws.write(r, 0, "POR ALCANCE", F["seccion"]); r += 1
    hdr = ["ALCANCE", "SOLICITUDES", "ATENDIDAS", "NO DISPONIBLES", "% ATENDIDAS",
           "% NO DISPONIBLES", "UNDS", "UNDS ATENDIDAS", "UNDS NO CUBIERTAS", "% UNDS ATENDIDAS"]
    for c, h in enumerate(hdr):
        ws.write(r, c, h, F["hdr"])
    ws.set_row(r, 30); r += 1
    fila_kpi_alcance = r
    for nombre in ["TALLER", "TIENDAS", "UNIFICADO"]:
        k = kpis[nombre]
        for c, v in enumerate([nombre, k["solicitudes"], k["atendidas"], k["no_disponible"],
                               k["pct_atendidas"], k["pct_no_disponible"], k["unds"],
                               k["unds_atend"], k["unds_nodisp"], k["pct_unds_atend"]]):
            fmt = F["total_lbl"] if c == 0 else (F["pct"] if c in (4, 5, 9) else F["int"])
            (ws.write if c == 0 else ws.write_number)(r, c, v, fmt)
        r += 1
    r += 1

    ws.write(r, 0, "POR ESTADO (DETALLE)", F["seccion"]); r += 1
    for c, h in enumerate(["ESTADO", "TALLER", "TIENDAS", "TOTAL", "CLASIFICACIÓN"]):
        ws.write(r, c, h, F["hdr"])
    r += 1
    estados = df.groupby(["ESTADO", "ORIGEN"]).size().unstack(fill_value=0)
    for est in ["RECIBIDO", "ENTREGADO", "ENVIADO", "SOLICITADO", "SIN ESTADO", "NO DISPONIBLE"]:
        t_ = int(estados.get("TALLER", pd.Series(dtype=int)).get(est, 0))
        i_ = int(estados.get("TIENDAS", pd.Series(dtype=int)).get(est, 0))
        ws.write(r, 0, est, F["txt"])
        ws.write_number(r, 1, t_, F["int"]); ws.write_number(r, 2, i_, F["int"])
        ws.write_number(r, 3, t_ + i_, F["int"])
        ws.write(r, 4, "NO ATENDIDA" if est == "NO DISPONIBLE" else "ATENDIDA",
                 F["bad"] if est == "NO DISPONIBLE" else F["ok"])
        r += 1
    r += 1

    ws.write(r, 0, "POR SUCURSAL / SUB-ÁREA", F["seccion"]); r += 1
    for c, h in enumerate(["ORIGEN", "SUCURSAL", "SOLICITUDES", "ATENDIDAS", "NO DISPONIBLES",
                           "% ATENDIDAS", "UNDS", "UNDS NO CUBIERTAS"]):
        ws.write(r, c, h, F["hdr"])
    r += 1
    for (org, suc), g in df.groupby(["ORIGEN", "SUCURSAL"]):
        at = int(g["ATENDIDA"].sum()); unds = int(g["CANTIDAD"].sum())
        unds_nd = int(g.loc[~g["ATENDIDA"], "CANTIDAD"].sum())
        ws.write(r, 0, org, F["txt"]); ws.write(r, 1, suc, F["txt"])
        ws.write_number(r, 2, len(g), F["int"]); ws.write_number(r, 3, at, F["int"])
        ws.write_number(r, 4, len(g) - at, F["int"])
        ws.write_number(r, 5, at / len(g), F["pct"])
        ws.write_number(r, 6, unds, F["int"]); ws.write_number(r, 7, unds_nd, F["int"])
        r += 1
    r += 1

    ws.write(r, 0, "POR MES", F["seccion"]); r += 1
    for c, h in enumerate(["MES", "SOL. TALLER", "% AT. TALLER", "SOL. TIENDAS", "% AT. TIENDAS",
                           "SOL. TOTAL", "% AT. TOTAL", "UNDS TOTAL"]):
        ws.write(r, c, h, F["hdr"])
    r += 1
    for mes, g in df.groupby("MES"):
        gt, gi = g[g["ORIGEN"] == "TALLER"], g[g["ORIGEN"] == "TIENDAS"]
        label = MESES_ES[mes.month] + (" (PARCIAL)" if mes == df["MES"].max() else "")
        ws.write(r, 0, label, F["txt"])
        for c, sub in [(1, gt), (3, gi), (5, g)]:
            at = int(sub["ATENDIDA"].sum())
            ws.write_number(r, c, len(sub), F["int"])
            ws.write_number(r, c + 1, at / len(sub) if len(sub) else 0, F["pct"])
        ws.write_number(r, 7, int(g["CANTIDAD"].sum()), F["int"])
        r += 1
    r += 1

    ws.write(r, 0, "TOP 10 PRODUCTOS CON MÁS 'NO DISPONIBLE' (demanda perdida)", F["seccion"]); r += 1
    for c, h in enumerate(["PRODUCTO", "VECES NO DISPONIBLE", "UNDS NO CUBIERTAS",
                           "UNDS SOLICITADAS", "% NO CUBIERTO"]):
        ws.write(r, c, h, F["hdr"])
    r += 1
    fila_top_nd = r
    for x in top_nd.itertuples():
        ws.write(r, 0, x.ARTICULO, F["txt"])
        ws.write_number(r, 1, int(x.VECES), F["int"])
        ws.write_number(r, 2, int(x.UNDS_NODISP), F["int"])
        ws.write_number(r, 3, int(x.UNDS_TOTAL), F["int"])
        ws.write_number(r, 4, x.PCT_NO_CUBIERTO, F["pct"])
        r += 1

    # =================================================================
    # 5-7. TALLER / TIENDAS / UNIFICADO
    # =================================================================
    expl_modelo = ("Una fila por producto. MIN = punto de reorden = D×LT + SS · MAX = stock objetivo = "
                   "D×(LT+P) + SS (P = 7/14/30 días) · PEDIDO = MAX − stock actual. "
                   "Celdas amarillas editables (z de servicio, lead time y stock actual): todo se recalcula. "
                   "CLASE DEMANDA: X regular / Y variable / Z intermitente. "
                   "La demanda usada es la SOLICITADA (incluye lo que quedó NO DISPONIBLE).")
    ws_t, _ = hoja_modelo(wb, F, "TALLER", mod_t,
                          "TALLER — ANÁLISIS POR PRODUCTO Y PEDIDO (3 OPCIONES)",
                          expl_modelo + " Ámbito: solo solicitudes del TALLER (todas sus sub-áreas).", "#2E75B6")
    ws_i, _ = hoja_modelo(wb, F, "TIENDAS", mod_i,
                          "TIENDAS — ANÁLISIS POR PRODUCTO Y PEDIDO (3 OPCIONES)",
                          expl_modelo + " Ámbito: consolidado de las 7 tiendas.", "#2E75B6")
    ws_u, tr_uni = hoja_modelo(wb, F, "UNIFICADO", mod_u,
                               "UNIFICADO (TALLER + TIENDAS) — PEDIDO CONSOLIDADO POR PRODUCTO",
                               expl_modelo + " Esta es la hoja principal para armar el pedido único de consumibles; "
                               "luego repártalo con las hojas de DISTRIBUCIÓN.", "#548235")

    # completar sección 3 del RESUMEN con referencias al total UNIFICADO
    wsR = wb.get_worksheet_by_name("RESUMEN EJECUTIVO")
    lect = {"SEMANAL": "Menor inventario inmovilizado; requiere proveedor ágil cada semana.",
            "QUINCENAL": "Equilibrio recomendado entre capital y riesgo de quiebre.",
            "MENSUAL": "Un solo pedido grande; más stock promedio, menor carga administrativa."}
    for j, (tag, ctag, ciclo, cped, cmax) in enumerate(
            [("SEMANAL", "SEM", P_SEMANAL, 16, 15),
             ("QUINCENAL", "QUINC", P_QUINCENAL, 18, 17),
             ("MENSUAL", "MENS", P_MENSUAL, 20, 19)]):
        rr = filas_opciones + j
        cell_ped = xl_rowcol_to_cell(tr_uni, cped)
        cell_max = xl_rowcol_to_cell(tr_uni, cmax)
        cell_min = xl_rowcol_to_cell(tr_uni, 13)
        wsR.write(rr, 0, f"OPCIÓN {tag}", F["total_lbl"])
        wsR.write_number(rr, 1, ciclo, F["int"])
        wsR.write_formula(rr, 2, f"=UNIFICADO!{cell_ped}", F["total_int"], int(mod_u[f"PEDIDO_{ctag}"].sum()))
        wsR.write_formula(rr, 3, f"=UNIFICADO!{cell_max}", F["total_int"], int(mod_u[f"MAX_{ctag}"].sum()))
        wsR.write_formula(rr, 4, f"=UNIFICADO!{cell_min}", F["total_int"], int(mod_u["MIN"].sum()))
        wsR.write(rr, 5, lect[tag], F["txt_wrap"])
        wsR.set_row(rr, 30)

    # =================================================================
    # 8-9. DISTRIBUCIONES
    # =================================================================
    def hoja_matriz(nombre, m, titulo, expl):
        ws = wb.add_worksheet(nombre)
        ws.set_tab_color("#9DC3E6")
        cols = list(m.columns)
        escribir_titulo(ws, F, titulo, expl, len(cols) + 1)
        ws.write(3, 0, "PRODUCTO", F["hdr"])
        for c, h in enumerate(cols):
            ws.write(3, c + 1, h, F["hdr"])
        for i, (art, row) in enumerate(m.iterrows()):
            rr = 4 + i
            ws.write(rr, 0, art, F["txt_b"] if i % 2 else F["txt"])
            for c, val in enumerate(row):
                ws.write_number(rr, c + 1, int(val), F["int_b"] if i % 2 else F["int"])
        tr = 4 + len(m)
        ws.write(tr, 0, "TOTAL", F["total_lbl"])
        for c in range(len(cols)):
            letra = xl_rowcol_to_cell(0, c + 1)
            letra = "".join(ch for ch in letra if ch.isalpha())
            ws.write_formula(tr, c + 1, f"=SUM({letra}5:{letra}{tr})", F["total_int"],
                             int(m.iloc[:, c].sum()))
        ws.set_column(0, 0, 36)
        ws.set_column(1, len(cols), 13)
        ws.freeze_panes(4, 1)
        ws.autofilter(3, 0, tr - 1, len(cols))
        ws.conditional_format(4, 1, tr - 1, len(cols), {"type": "data_bar", "bar_color": "#9DC3E6"})

    hoja_matriz("DISTRIBUCION TIENDAS", mat_tiendas,
                "DISTRIBUCIÓN DEL CONSUMO POR TIENDA (UNDS SOLICITADAS, 2 MESES)",
                "Cuántas unidades pidió cada tienda de cada producto. Úsela para repartir el pedido "
                "unificado entre las tiendas según su consumo real. La última columna es el total por producto.")
    hoja_matriz("DISTRIBUCION TALLER", mat_taller,
                "DISTRIBUCIÓN DEL CONSUMO POR SUB-ÁREA DEL TALLER (UNDS, 2 MESES)",
                "Cuántas unidades pidió cada sub-área (TALLER, I+D, ALMACEN, MANTENIMIENTO, RRHH, OFICINAS) "
                "de cada producto, para repartir el pedido del taller.")

    # =================================================================
    # 10. TENDENCIA SEMANAL
    # =================================================================
    ws = wb.add_worksheet("TENDENCIA SEMANAL")
    ws.set_tab_color("#7030A0")
    hdrs = ["SEMANA (LUNES)", "SOL. TALLER", "UNDS TALLER", "SOL. TIENDAS",
            "UNDS TIENDAS", "SOL. TOTAL", "UNDS TOTAL"]
    escribir_titulo(ws, F, "TENDENCIA SEMANAL DE SOLICITUDES Y UNIDADES",
                    "Consumo semana a semana (semanas inician en lunes). Sirve para verificar que la demanda "
                    "es estable y que los promedios usados en el modelo son representativos.", len(hdrs))
    for c, h in enumerate(hdrs):
        ws.write(3, c, h, F["hdr"])
    ws.set_row(3, 28)
    for i, x in semanal.iterrows():
        rr = 4 + i
        ws.write(rr, 0, f"Sem. {x.SEMANA:%d/%m}", F["txt"])
        for c, k in enumerate(["SOL_TALLER", "UNDS_TALLER", "SOL_TIENDAS",
                               "UNDS_TIENDAS", "SOL_TOTAL", "UNDS_TOTAL"]):
            ws.write_number(rr, c + 1, int(x[k]), F["int"])
    tr = 4 + len(semanal)
    ws.write(tr, 0, "TOTAL", F["total_lbl"])
    for c in range(1, 7):
        letra = "".join(ch for ch in xl_rowcol_to_cell(0, c) if ch.isalpha())
        ws.write_formula(tr, c, f"=SUM({letra}5:{letra}{tr})", F["total_int"],
                         int(semanal.iloc[:, c].sum()))
    ws.set_column(0, 0, 16); ws.set_column(1, 6, 13)

    # =================================================================
    # 11. GRAFICOS
    # =================================================================
    ws = wb.add_worksheet("GRAFICOS")
    ws.set_tab_color("#ED7D31")
    ws.merge_range("A1:N1", "GRÁFICOS DEL ANÁLISIS", F["titulo"])
    ws.set_row(0, 26)

    # --- datos locales para gráficos ---
    base = 40
    ws.write(base, 0, "Datos gráfico 1: % atención por alcance", F["seccion"])
    ws.write_row(base + 1, 0, ["ALCANCE", "% ATENDIDAS", "% NO DISPONIBLES"], F["hdr"])
    for j, nombre in enumerate(["TALLER", "TIENDAS", "UNIFICADO"]):
        ws.write(base + 2 + j, 0, nombre, F["txt"])
        ws.write_number(base + 2 + j, 1, kpis[nombre]["pct_atendidas"], F["pct"])
        ws.write_number(base + 2 + j, 2, kpis[nombre]["pct_no_disponible"], F["pct"])

    ws.write(base, 4, "Datos gráfico 2: top 10 unds (unificado)", F["seccion"])
    ws.write_row(base + 1, 4, ["PRODUCTO", "UNDS"], F["hdr"])
    for j, x in enumerate(mod_u.head(10).itertuples()):
        ws.write(base + 2 + j, 4, x.ARTICULO, F["txt"])
        ws.write_number(base + 2 + j, 5, int(x.UNDS), F["int"])

    ws.write(base, 7, "Datos gráfico 4: top 10 NO DISPONIBLE (unds perdidas)", F["seccion"])
    ws.write_row(base + 1, 7, ["PRODUCTO", "UNDS NO CUBIERTAS"], F["hdr"])
    for j, x in enumerate(top_nd.itertuples()):
        ws.write(base + 2 + j, 7, x.ARTICULO, F["txt"])
        ws.write_number(base + 2 + j, 8, int(x.UNDS_NODISP), F["int"])

    g1 = wb.add_chart({"type": "column"})
    g1.add_series({"name": "% ATENDIDAS",
                   "categories": ["GRAFICOS", base + 2, 0, base + 4, 0],
                   "values": ["GRAFICOS", base + 2, 1, base + 4, 1],
                   "fill": {"color": "#70AD47"}, "gap": 60})
    g1.add_series({"name": "% NO DISPONIBLES",
                   "categories": ["GRAFICOS", base + 2, 0, base + 4, 0],
                   "values": ["GRAFICOS", base + 2, 2, base + 4, 2],
                   "fill": {"color": "#C00000"}, "gap": 60})
    g1.set_title({"name": "% solicitudes atendidas vs no disponibles"})
    g1.set_y_axis({"num_format": "0%", "max": 1})
    g1.set_size({"width": 560, "height": 320})
    g1.set_legend({"position": "bottom"})
    ws.insert_chart("A3", g1)

    g2 = wb.add_chart({"type": "bar"})
    g2.add_series({"name": "UNDS (2 meses)",
                   "categories": ["GRAFICOS", base + 2, 4, base + 11, 4],
                   "values": ["GRAFICOS", base + 2, 5, base + 11, 5],
                   "fill": {"color": "#2E75B6"}})
    g2.set_title({"name": "Top 10 productos por unidades (unificado)"})
    g2.set_size({"width": 560, "height": 380})
    g2.set_legend({"none": True})
    ws.insert_chart("A20", g2)

    g3 = wb.add_chart({"type": "line"})
    nsem = len(semanal)
    for nombre, col, color in [("UNDS TALLER", 2, "#2E75B6"), ("UNDS TIENDAS", 4, "#ED7D31"),
                               ("UNDS TOTAL", 6, "#70AD47")]:
        g3.add_series({"name": nombre,
                       "categories": ["TENDENCIA SEMANAL", 4, 0, 3 + nsem, 0],
                       "values": ["TENDENCIA SEMANAL", 4, col, 3 + nsem, col],
                       "line": {"color": color, "width": 2.25},
                       "marker": {"type": "circle", "size": 5, "fill": {"color": color}}})
    g3.set_title({"name": "Tendencia semanal de unidades solicitadas"})
    g3.set_size({"width": 560, "height": 320})
    g3.set_legend({"position": "bottom"})
    ws.insert_chart("H3", g3)

    g4 = wb.add_chart({"type": "bar"})
    g4.add_series({"name": "UNDS NO CUBIERTAS",
                   "categories": ["GRAFICOS", base + 2, 7, base + 11, 7],
                   "values": ["GRAFICOS", base + 2, 8, base + 11, 8],
                   "fill": {"color": "#C00000"}})
    g4.set_title({"name": "Top 10 demanda perdida (NO DISPONIBLE, unds)"})
    g4.set_size({"width": 560, "height": 380})
    g4.set_legend({"none": True})
    ws.insert_chart("H20", g4)
    ws.set_column(0, 12, 14)

    # =================================================================
    # 12-14. DATA LIMPIA
    # =================================================================
    def hoja_data(nombre, d, color):
        ws = wb.add_worksheet(nombre)
        ws.set_tab_color(color)
        cols = ["FECHA", "SEMANA", "MES", "ORIGEN", "SUCURSAL", "NOMBRE", "ARTICULO",
                "CARACTER ADICIONAL", "CATEGORIA", "CANTIDAD", "ESTADO ORIGINAL",
                "ESTADO", "ATENCIÓN", "NOTA LIMPIEZA"]
        escribir_titulo(ws, F, nombre,
                        "Data limpia y clasificada usada en todos los cálculos. ATENCIÓN = ATENDIDA "
                        "(recibido/entregado/enviado/solicitado) o NO DISPONIBLE.", len(cols))
        for c, h in enumerate(cols):
            ws.write(3, c, h, F["hdr"])
        d = d.sort_values(["FECHA", "ORIGEN", "SUCURSAL"])
        fmt_fecha = wb.add_format({"border": 1, "num_format": "dd/mm/yyyy", "align": "center"})
        fmt_fecha_b = wb.add_format({"border": 1, "num_format": "dd/mm/yyyy", "align": "center",
                                     "bg_color": "#F2F7FB"})

        def _s(v):
            return v if isinstance(v, str) else ("" if v is None or pd.isna(v) else str(v))

        for i, (_, x) in enumerate(d.iterrows()):
            rr = 4 + i
            f = F["txt_b"] if i % 2 else F["txt"]
            ws.write_datetime(rr, 0, dt.datetime.combine(x["FECHA"], dt.time()),
                              fmt_fecha_b if i % 2 else fmt_fecha)
            ws.write(rr, 1, f"Sem. {x['SEMANA']:%d/%m}", f)
            ws.write(rr, 2, MESES_ES[x["MES"].month], f)
            ws.write(rr, 3, _s(x["ORIGEN"]), f)
            ws.write(rr, 4, _s(x["SUCURSAL"]), f)
            ws.write(rr, 5, _s(x["NOMBRE"]), f)
            ws.write(rr, 6, _s(x["ARTICULO"]), f)
            ws.write(rr, 7, _s(x["CARACTER ADICIONAL"]), f)
            ws.write(rr, 8, _s(x["CATEGORIA"]), f)
            ws.write_number(rr, 9, int(x["CANTIDAD"]), F["int_b"] if i % 2 else F["int"])
            ws.write(rr, 10, _s(x["ESTADO ORIGINAL"]), f)
            ws.write(rr, 11, _s(x["ESTADO"]), f)
            ws.write(rr, 12, "ATENDIDA" if x["ATENDIDA"] else "NO DISPONIBLE",
                     F["ok"] if x["ATENDIDA"] else F["bad"])
            ws.write(rr, 13, _s(x["NOTA LIMPIEZA"]), f)
        ws.freeze_panes(4, 0)
        ws.autofilter(3, 0, 3 + len(d), len(cols) - 1)
        anchos = [11, 11, 10, 9, 17, 22, 36, 22, 24, 10, 14, 13, 13, 28]
        for c, a in enumerate(anchos):
            ws.set_column(c, c, a)

    hoja_data("DATA TALLER", df_t, "#404040")
    hoja_data("DATA TIENDAS", df_i, "#404040")
    hoja_data("DATA CONSOLIDADA", df, "#404040")

    # =================================================================
    # 15. CALIDAD DE DATOS
    # =================================================================
    ws = wb.add_worksheet("CALIDAD DE DATOS")
    ws.set_tab_color("#C00000")
    escribir_titulo(ws, F, "CALIDAD DE DATOS — FILAS EXCLUIDAS Y OBSERVACIONES",
                    "Transparencia total sobre la limpieza: qué filas se excluyeron del análisis y por qué, "
                    "y qué correcciones/normalizaciones se aplicaron.", 10)
    ws.set_column("A:A", 34); ws.set_column("B:I", 15); ws.set_column("J:J", 60)
    r = 3
    ws.write(r, 0, f"FILAS EXCLUIDAS DEL ANÁLISIS ({len(excluidas)})", F["seccion"]); r += 1
    for c, h in enumerate(["REFERENCIA", "ORIGEN", "HOJA", "FECHA", "NOMBRE", "ARTICULO",
                           "CAR. ADICIONAL", "CANTIDAD", "ESTADO", "MOTIVO DE EXCLUSIÓN"]):
        ws.write(r, c, h, F["hdr"])
    r += 1
    for fila in excluidas:
        for c, v in enumerate(fila):
            ws.write(r, c, "" if v == "None" else v, F["txt_wrap"] if c == 9 else F["txt"])
        r += 1
    r += 1
    ws.write(r, 0, "OBSERVACIONES DE LIMPIEZA Y NORMALIZACIÓN", F["seccion"]); r += 1
    for o in observaciones:
        ws.merge_range(r, 0, r, 9, "• " + o, F["txt_wrap"]); ws.set_row(r, 30); r += 1
    r += 1
    ws.write(r, 0, "FILAS VÁLIDAS USADAS EN EL ANÁLISIS", F["seccion"]); r += 1
    for c, h in enumerate(["ORIGEN", "SOLICITUDES VÁLIDAS", "UNIDADES"]):
        ws.write(r, c, h, F["hdr"])
    r += 1
    for org, sub in [("TALLER", df_t), ("TIENDAS", df_i), ("TOTAL", df)]:
        ws.write(r, 0, org, F["total_lbl"])
        ws.write_number(r, 1, len(sub), F["int"])
        ws.write_number(r, 2, int(sub["CANTIDAD"].sum()), F["int"])
        r += 1

    wb.close()
    print("OK ->", OUT)
    print(f"filas: taller={len(df_t)}, tiendas={len(df_i)}, total={len(df)}; excluidas={len(excluidas)}")
    print(f"dias: taller={dias_t}, tiendas={dias_i}, unificado={dias_u}")
    for n in ["TALLER", "TIENDAS", "UNIFICADO"]:
        k = kpis[n]
        print(f"{n}: sol={k['solicitudes']} atend={k['atendidas']} ({k['pct_atendidas']:.1%}) "
              f"unds={k['unds']} unds_atend={k['unds_atend']} ({k['pct_unds_atend']:.1%})")
    print("Totales pedido unificado:",
          {t: int(mod_u[f"PEDIDO_{t}"].sum()) for t in ["SEM", "QUINC", "MENS"]})


if __name__ == "__main__":
    main()
