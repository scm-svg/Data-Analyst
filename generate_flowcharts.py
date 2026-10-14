#!/usr/bin/env python3
"""Generate process flowchart PNGs with proper spacing and branch layout."""

import os
import textwrap

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT_DIR = "/workspace/flowcharts"

C_START = "#2E7D32"
C_PROCESS = "#1565C0"
C_DECISION = "#F57C00"
C_END = "#6A1B9A"
C_NOTE = "#546E7A"
C_ARROW = "#37474F"
C_BG = "#FAFAFA"

BOX_W = 6.2
BOX_W_BRANCH = 3.15
BOX_H = 0.82
DIAMOND_R = 0.62
X_CENTER = 5.0
X_LEFT = 2.35
X_RIGHT = 7.65
GAP = 0.58
GAP_DIAMOND = 0.62


def _display(step):
    text = step["text"]
    actor = step.get("actor", "")
    if actor:
        return f"{text}\n({actor})"
    return text


def _draw_box(ax, x, y, step, width=None):
    stype = step.get("type", "process")
    text = _display(step)
    lines = len(text.split("\n"))
    h = BOX_H + max(0, lines - 2) * 0.12
    w = BOX_W if width is None else width

    if stype == "start":
        edge, face = C_START, "#E8F5E9"
    elif stype == "end":
        edge, face = C_END, "#F3E5F5"
    elif stype == "note":
        edge, face = C_NOTE, "#ECEFF1"
    else:
        edge, face = C_PROCESS, "#E3F2FD"

    style = "round,pad=0.06,rounding_size=0.15"
    ls = "dashed" if stype == "note" else "solid"
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle=style, linewidth=1.5, edgecolor=edge, facecolor=face,
        linestyle=ls, zorder=2,
    )
    ax.add_patch(patch)
    ax.text(x, y, text, ha="center", va="center", fontsize=8.2, color="#263238", zorder=3)
    return h


def _draw_diamond(ax, x, y, text):
    diamond = mpatches.RegularPolygon(
        (x, y), 4, radius=DIAMOND_R, orientation=0,
        linewidth=1.5, edgecolor=C_DECISION, facecolor="#FFF3E0", zorder=2,
    )
    ax.add_patch(diamond)
    ax.text(x, y, text, ha="center", va="center", fontsize=8.2, color="#263238", zorder=3)
    return DIAMOND_R * 2


def _arrow(ax, x1, y1, x2, y2, color=C_ARROW, style="-|>"):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle=style, mutation_scale=11,
        linewidth=1.25, color=color, zorder=5,
    ))


def _arrow_path(ax, points, color=C_ARROW):
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        style = "-|>" if i == len(points) - 2 else "-"
        ax.add_patch(FancyArrowPatch(
            (x1, y1), (x2, y2), arrowstyle=style, mutation_scale=11,
            linewidth=1.25, color=color, zorder=5,
        ))


def _is_destino_branch(step):
    b = step.get("branches", {})
    return "Tienda" in b or "Taller" in b


def _is_yes_no_before_end(steps, i):
    if steps[i].get("type") != "decision":
        return False
    if i + 2 >= len(steps):
        return False
    return steps[i + 1].get("type") == "process" and steps[i + 2].get("type") == "end"


def _box_height(step):
    lines = len(_display(step).split("\n"))
    return BOX_H + max(0, lines - 2) * 0.12


def _step_height(step):
    if step.get("type") == "decision":
        return DIAMOND_R * 2
    return _box_height(step)


def draw_flowchart(title, steps, filename):
    """Render flowchart with branch-aware layout."""
    fig_w = 10
    est = 2.5 + len(steps) * (BOX_H + GAP + 0.2)
    fig_h = max(8.0, est)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, fig_h)
    ax.axis("off")
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_BG)

    ax.text(X_CENTER, fig_h - 0.45, title, ha="center", va="center", fontsize=12.5,
            fontweight="bold", color="#263238")

    # Layout pass: assign vertical centers (cy) top-down
    blocks = []  # dicts with draw info
    i = 0
    y_top = fig_h - 1.05

    while i < len(steps):
        step = steps[i]
        stype = step.get("type", "process")

        if stype == "decision" and _is_destino_branch(step) and i + 3 < len(steps):
            dh = DIAMOND_R * 2
            cy_d = y_top - dh / 2
            hl = _box_height(steps[i + 1])
            hr = _box_height(steps[i + 2])
            hm = _box_height(steps[i + 3])
            branch_h = max(hl, hr)
            y_after_d = cy_d - dh / 2 - GAP_DIAMOND
            cy_branch = y_after_d - branch_h / 2
            y_after_branch = cy_branch - branch_h / 2 - GAP
            cy_merge = y_after_branch - hm / 2
            blocks.append({
                "kind": "destino",
                "decision": step,
                "cy_d": cy_d,
                "left": steps[i + 1],
                "right": steps[i + 2],
                "merge": steps[i + 3],
                "cy_branch": cy_branch,
                "cy_merge": cy_merge,
                "hl": hl,
                "hr": hr,
                "hm": hm,
            })
            y_top = cy_merge - hm / 2 - GAP
            i += 4
            continue

        if _is_yes_no_before_end(steps, i):
            dh = DIAMOND_R * 2
            cy_d = y_top - dh / 2
            hy = _box_height(steps[i + 1])
            he = _box_height(steps[i + 2])
            y_after_d = cy_d - dh / 2 - GAP_DIAMOND
            cy_yes = y_after_d - hy / 2
            y_after_yes = cy_yes - hy / 2 - GAP
            cy_end = y_after_yes - he / 2
            blocks.append({
                "kind": "yesno",
                "decision": step,
                "cy_d": cy_d,
                "yes": steps[i + 1],
                "end": steps[i + 2],
                "cy_yes": cy_yes,
                "cy_end": cy_end,
                "hy": hy,
                "he": he,
            })
            y_top = cy_end - he / 2 - GAP
            i += 3
            continue

        h = _step_height(step)
        cy = y_top - h / 2
        blocks.append({"kind": "single", "step": step, "cy": cy, "h": h})
        y_top = cy - h / 2 - GAP
        i += 1

    # Draw pass
    connectors = []  # (x1,y1,x2,y2)

    for bi, block in enumerate(blocks):
        if block["kind"] == "single":
            step = block["step"]
            cy, h = block["cy"], block["h"]
            if step.get("type") == "decision":
                _draw_diamond(ax, X_CENTER, cy, step["text"])
            else:
                _draw_box(ax, X_CENTER, cy, step)
            if bi + 1 < len(blocks) and blocks[bi + 1]["kind"] == "single":
                nb = blocks[bi + 1]
                connectors.append((X_CENTER, cy - h / 2, X_CENTER, nb["cy"] + nb["h"] / 2))
            elif bi + 1 < len(blocks):
                nb = blocks[bi + 1]
                if nb["kind"] == "destino":
                    connectors.append((X_CENTER, cy - h / 2, X_CENTER, nb["cy_d"] + DIAMOND_R))
                elif nb["kind"] == "yesno":
                    connectors.append((X_CENTER, cy - h / 2, X_CENTER, nb["cy_d"] + DIAMOND_R))

        elif block["kind"] == "destino":
            cy_d = block["cy_d"]
            _draw_diamond(ax, X_CENTER, cy_d, block["decision"]["text"])
            cy_b, hl, hr = block["cy_branch"], block["hl"], block["hr"]
            _draw_box(ax, X_LEFT, cy_b, block["left"], width=BOX_W_BRANCH)
            _draw_box(ax, X_RIGHT, cy_b, block["right"], width=BOX_W_BRANCH)
            ax.text(X_LEFT, cy_b + max(hl, hr) / 2 + 0.12, "Tienda", fontsize=7.5,
                    color=C_DECISION, fontweight="bold", ha="center")
            ax.text(X_RIGHT, cy_b + max(hl, hr) / 2 + 0.12, "Taller", fontsize=7.5,
                    color=C_DECISION, fontweight="bold", ha="center")
            cy_m, hm = block["cy_merge"], block["hm"]
            _draw_box(ax, X_CENTER, cy_m, block["merge"])

            _arrow(ax, X_CENTER - 0.2, cy_d - DIAMOND_R, X_LEFT, cy_b + hl / 2)
            _arrow(ax, X_CENTER + 0.2, cy_d - DIAMOND_R, X_RIGHT, cy_b + hr / 2)
            _arrow(ax, X_LEFT, cy_b - hl / 2, X_CENTER - 0.15, cy_m + hm / 2)
            _arrow(ax, X_RIGHT, cy_b - hr / 2, X_CENTER + 0.15, cy_m + hm / 2)

            if bi + 1 < len(blocks) and blocks[bi + 1]["kind"] == "single":
                nb = blocks[bi + 1]
                connectors.append((X_CENTER, cy_m - hm / 2, X_CENTER, nb["cy"] + nb["h"] / 2))

        elif block["kind"] == "yesno":
            cy_d = block["cy_d"]
            _draw_diamond(ax, X_CENTER, cy_d, block["decision"]["text"])
            cy_y, hy = block["cy_yes"], block["hy"]
            cy_e, he = block["cy_end"], block["he"]
            _draw_box(ax, X_LEFT, cy_y, block["yes"], width=BOX_W_BRANCH)
            _draw_box(ax, X_CENTER, cy_e, block["end"])
            ax.text(X_LEFT, cy_d - DIAMOND_R - 0.12, "Sí", fontsize=7.5, color=C_DECISION,
                    fontweight="bold", ha="center")
            ax.text(X_RIGHT, cy_d - DIAMOND_R - 0.12, "No", fontsize=7.5, color=C_DECISION,
                    fontweight="bold", ha="center")

            _arrow(ax, X_CENTER - 0.2, cy_d - DIAMOND_R, X_LEFT, cy_y + hy / 2)
            _arrow(ax, X_CENTER + 0.2, cy_d - DIAMOND_R, X_RIGHT, cy_d - DIAMOND_R - 0.05)
            _arrow(ax, X_LEFT, cy_y - hy / 2, X_CENTER - 0.12, cy_e + he / 2)
            _arrow_path(ax, [
                (X_RIGHT, cy_d - DIAMOND_R - 0.08),
                (X_RIGHT, cy_e + he / 2 + 0.05),
                (X_CENTER + 0.1, cy_e + he / 2 + 0.05),
            ])

    for x1, y1, x2, y2 in connectors:
        _arrow(ax, x1, y1, x2, y2)

    plt.tight_layout()
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, filename)
    plt.savefig(path, dpi=180, bbox_inches="tight", facecolor=C_BG)
    plt.close()
    return path


def all_charts():
    return [
        {
            "filename": "00_overview_logistica.png",
            "title": "Vista General — Procesos de Logística e Inventarios",
            "steps": [
                {"type": "start", "text": "Inicio — Área de Logística e Inventarios"},
                {"type": "process", "text": "Proceso 1: Despacho MP e insumos"},
                {"type": "process", "text": "Proceso 2: Recepción tela e insumos"},
                {"type": "process", "text": "Proceso 3: Despacho y recepción consumibles"},
                {"type": "end", "text": "Movimiento registrado con trazabilidad"},
            ],
        },
        {
            "filename": "01_despacho_tela.png",
            "title": "Proceso 1.1 — Despacho de Tela a Áreas Solicitantes",
            "steps": [
                {"type": "start", "text": "Solicitud de tela asociada a OT en Odoo", "actor": "Área solicitante"},
                {"type": "process", "text": "Entrega trazos impresos (Audaces)", "actor": "Producción / Diseño / Pedidos / Calidad"},
                {"type": "process", "text": "Calcula cantidad de tela según trazos", "actor": "Supervisor"},
                {"type": "process", "text": "Envía información del cálculo al equipo", "actor": "Supervisor"},
                {"type": "process", "text": "Prepara picking según indicación", "actor": "Operadores MP"},
                {"type": "process", "text": "Entrega físicamente la tela al solicitante", "actor": "Operadores MP"},
                {"type": "process", "text": "Registra entrega en Sheets de control\n(SKU, cantidad, área)", "actor": "Operadores MP"},
                {"type": "process", "text": "Registra en Odoo OT + PC\nTH/Existencia MP → Preproducción", "actor": "Supervisor"},
                {"type": "end", "text": "Despacho completado — trazabilidad física y Odoo"},
            ],
        },
        {
            "filename": "02_despacho_insumos_etiquetado.png",
            "title": "Proceso 1.2 — Despacho de Insumos (Etiquetado)",
            "steps": [
                {"type": "start", "text": "Solicitud de insumos de Etiquetado", "actor": "Etiquetado"},
                {"type": "note", "text": "Hang tag, cinta TPU, tinta Zencamer, cordones, etc."},
                {"type": "process", "text": "Prepara picking de insumos", "actor": "Operadores MP"},
                {"type": "process", "text": "Entrega física al área de Etiquetado", "actor": "Operadores MP"},
                {"type": "process", "text": "Registra en Sheets de control interno", "actor": "Operadores MP"},
                {"type": "process", "text": "Registra movimiento en Odoo", "actor": "Supervisor"},
                {"type": "end", "text": "Insumos despachados y registrados"},
            ],
        },
        {
            "filename": "03_devolucion_tela.png",
            "title": "Proceso 1.3 — Devolución de Tela por Producción",
            "steps": [
                {"type": "start", "text": "Producción informa rollos no utilizados", "actor": "Producción"},
                {"type": "process", "text": "Retira y pesa rollos devueltos", "actor": "Operadores MP"},
                {"type": "process", "text": "Modifica hablador con nuevo peso", "actor": "Operadores MP"},
                {"type": "process", "text": "Ubica rollo en sección correspondiente", "actor": "Operadores MP"},
                {"type": "process", "text": "Registra devolución en Sheets", "actor": "Operadores MP"},
                {"type": "process", "text": "Registra movimiento en Odoo", "actor": "Supervisor"},
                {"type": "end", "text": "Devolución registrada — inventario actualizado"},
            ],
        },
        {
            "filename": "04_recepcion_tela.png",
            "title": "Proceso 2.1 — Recepción de Tela (Rollo Aprobado)",
            "steps": [
                {"type": "start", "text": "Compras informa llegada de tela", "actor": "Compras"},
                {"type": "process", "text": "Tiende rollo en plegadora", "actor": "Operadores MP"},
                {"type": "process", "text": "QA acompaña revisión y anota variables", "actor": "Operadores + QA"},
                {"type": "note", "text": "Si QA rechaza el rollo → ver flujograma\n«Rollo rechazado en recepción»"},
                {"type": "process", "text": "Pesa, identifica con hablador y ubica", "actor": "Operadores MP"},
                {"type": "process", "text": "Registra en hoja de soporte de recepción", "actor": "Operadores MP"},
                {"type": "process", "text": "Traslada en Odoo a Materia Prima", "actor": "Supervisor"},
                {"type": "process", "text": "Si hay diferencias, notifica a Compras", "actor": "Supervisor"},
                {"type": "end", "text": "Recepción completada — física y Odoo"},
            ],
        },
        {
            "filename": "04b_recepcion_tela_rechazo.png",
            "title": "Proceso 2.1 (Rama) — Rollo Rechazado en Recepción",
            "steps": [
                {"type": "start", "text": "Rollo rechazado por Calidad", "actor": "QA"},
                {"type": "process", "text": "Pesa e identifica con hablador", "actor": "Operadores MP"},
                {"type": "process", "text": "Ubica en área de rechazo", "actor": "Operadores MP"},
                {"type": "process", "text": "Registra en hoja de soporte", "actor": "Operadores MP"},
                {"type": "note", "text": "No se realiza transferencia en Odoo"},
                {"type": "process", "text": "Notifica rechazo a Compras", "actor": "Supervisor"},
                {"type": "end", "text": "Rollo en área de rechazo"},
            ],
        },
        {
            "filename": "05_rechazados_devolucion.png",
            "title": "Proceso 2.2 — Rechazados y Devolución al Proveedor",
            "steps": [
                {"type": "start", "text": "Rollos en área de rechazo", "actor": "Operadores MP"},
                {"type": "process", "text": "Compras gestiona reclamo al proveedor", "actor": "Compras"},
                {"type": "process", "text": "Informa rollos aptos para devolución", "actor": "Compras"},
                {"type": "process", "text": "Embobina y protege rollos", "actor": "Operadores MP"},
                {"type": "process", "text": "Informa a Compras: listos para retiro", "actor": "Supervisor / Operadores"},
                {"type": "end", "text": "Rollos listos para devolver al proveedor"},
            ],
        },
        {
            "filename": "06_recepcion_insumos.png",
            "title": "Proceso 2.3 — Recepción de Insumos (No Tela)",
            "steps": [
                {"type": "start", "text": "Compras entrega detalle recibido", "actor": "Compras"},
                {"type": "process", "text": "Contabiliza insumos recibidos", "actor": "Operadores MP"},
                {"type": "process", "text": "Pasa detalle al Supervisor", "actor": "Operadores MP"},
                {"type": "process", "text": "Traslado en Odoo — stock disponible", "actor": "Supervisor"},
                {"type": "end", "text": "Insumos recibidos en Odoo"},
            ],
        },
        {
            "filename": "07_despacho_consumibles.png",
            "title": "Proceso 3.1 — Despacho de Consumibles (Tiendas / Taller)",
            "steps": [
                {"type": "start", "text": "Registra requerimiento en Sheets", "actor": "Tienda / Taller"},
                {"type": "process", "text": "Revisa Sheets de solicitudes", "actor": "Operador Consumibles"},
                {"type": "process", "text": "Imprime información de la solicitud", "actor": "Operador Consumibles"},
                {"type": "process", "text": "Realiza picking de lo solicitado", "actor": "Operador Consumibles"},
                {"type": "decision", "text": "¿Destino?", "branches": {"Tienda": 1, "Taller": 2}},
                {"type": "process", "text": "Prepara cajas para envío\na Tienda", "actor": "Operador Consumibles"},
                {"type": "process", "text": "Entrega directa interna\na Taller", "actor": "Operador Consumibles"},
                {"type": "process", "text": "Registra descuento en Sheets\nde control de inventario", "actor": "Operador Consumibles"},
                {"type": "end", "text": "Consumibles despachados — registro en Sheets"},
            ],
        },
        {
            "filename": "08_recepcion_consumibles.png",
            "title": "Proceso 3.2 — Recepción de Consumibles Comprados",
            "steps": [
                {"type": "start", "text": "Compras informa llegada y detalle", "actor": "Compras"},
                {"type": "process", "text": "Recibe, contabiliza y chequea", "actor": "Operador Consumibles"},
                {"type": "process", "text": "Ubica en zona de almacén", "actor": "Operador Consumibles"},
                {"type": "process", "text": "Informa al Supervisor", "actor": "Operador Consumibles"},
                {"type": "process", "text": "Registra recepción en Sheets", "actor": "Operador Consumibles"},
                {"type": "decision", "text": "¿Existen\ndiferencias?", "branches": {"Sí": 1, "No": 2}},
                {"type": "process", "text": "Informa diferencias a Compras", "actor": "Supervisor"},
                {"type": "end", "text": "Recepción de consumibles completada"},
            ],
        },
        {
            "filename": "req_01_requisicion_compra.png",
            "title": "Proceso — Solicitud de Requisición de Compra",
            "steps": [
                {"type": "start", "text": "Identifica necesidad de tela o consumibles", "actor": "Supervisor"},
                {"type": "process", "text": "Ingresa a Odoo — Aprobaciones", "actor": "Supervisor"},
                {"type": "process", "text": "Ingresa SKU, cantidad y justificación", "actor": "Supervisor"},
                {"type": "process", "text": "Envía la orden generada", "actor": "Supervisor"},
                {"type": "process", "text": "Compras revisa la solicitud", "actor": "Compras"},
                {"type": "note", "text": "Si requiere más info → ver flujograma\n«Información adicional»"},
                {"type": "process", "text": "Aprueba y gestiona compra\n(lead time del insumo)", "actor": "Compras"},
                {"type": "process", "text": "Supervisor da seguimiento al lead time", "actor": "Supervisor"},
                {"type": "end", "text": "Requisición aprobada — seguimiento activo"},
            ],
        },
        {
            "filename": "req_02_requisicion_info_adicional.png",
            "title": "Rama — Compras Solicita Información Adicional",
            "steps": [
                {"type": "start", "text": "Compras solicita información adicional", "actor": "Compras"},
                {"type": "process", "text": "Supervisor completa y reenvía", "actor": "Supervisor"},
                {"type": "process", "text": "Compras revisa solicitud actualizada", "actor": "Compras"},
                {"type": "decision", "text": "¿Información\nsuficiente?", "branches": {"Sí": 1, "No": 2}},
                {"type": "process", "text": "Aprueba solicitud", "actor": "Compras"},
                {"type": "end", "text": "Retorna al flujo principal"},
            ],
        },
    ]


def main():
    for chart in all_charts():
        path = draw_flowchart(chart["title"], chart["steps"], chart["filename"])
        print("OK", path)


if __name__ == "__main__":
    main()
