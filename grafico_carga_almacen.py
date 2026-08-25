"""Genera el grafico del perfil de carga por dia derivado de la tabla de
asignaciones del documento, mas la comparacion de escenarios de dotacion."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

JORNADA = 8.25
SEMANA_FTE = JORNADA * 5
dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
carga = np.array([80.50, 80.50, 75.25, 25.75, 25.75])
cap_nominal = np.array([82.50] * 5)
omitidas = 105.0
no_asignadas = cap_nominal - carga

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(17, 7))

x = np.arange(len(dias))
ancho = 0.38
ax1.bar(x - ancho / 2, cap_nominal, ancho, label="Capacidad nominal (10 pers. × 8.25 h)",
        color="#c7d2e0", edgecolor="#4a6079")
ax1.bar(x + ancho / 2, carga, ancho, label="Carga asignada (tabla del documento)",
        color="#2f6f9f", edgecolor="#1c4460")

for i, (c, a) in enumerate(zip(cap_nominal, carga)):
    ax1.text(i + ancho / 2, a + 1.5, f"{a:.2f} HH\n({100*a/c:.0f}%)", ha="center",
             fontsize=9, fontweight="bold", color="#1c4460")
    if c - a > 20:
        ax1.annotate("", xy=(i - ancho / 2, c - 0.5), xytext=(i - ancho / 2, a + 0.5),
                     arrowprops=dict(arrowstyle="<->", color="#c0392b", lw=1.6))
        ax1.text(i - ancho / 2, (c + a) / 2, f"+{c-a:.2f} HH\nlibres",
                 ha="center", va="center", fontsize=8.5, color="#c0392b", fontweight="bold",
                 bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                           edgecolor="#c0392b", alpha=0.95))

ax1.set_xticks(x)
ax1.set_xticklabels(dias, fontsize=11)
ax1.set_ylabel("Horas-Hombre por día", fontsize=11)
ax1.set_title("HALLAZGO CENTRAL: el promedio semanal esconde el perfil real\n"
              "Lun-Mié al 91-98% de uso; Jue-Vie al 31%",
              fontsize=12, fontweight="bold")
ax1.legend(loc="upper left", fontsize=9, framealpha=0.95)
ax1.grid(axis="y", alpha=0.3, linestyle=":")
ax1.set_ylim(0, 112)
ax1.text(0.5, -0.13,
         f"Horas nominales NO asignadas hoy: {no_asignadas.sum():.2f} HH/semana  vs.  "
         f"tareas 'omitidas' reclamadas: {omitidas:.1f} HH/semana",
         transform=ax1.transAxes, ha="center", fontsize=10.5, fontweight="bold",
         bbox=dict(boxstyle="round,pad=0.5", facecolor="#fdf3d0", edgecolor="#b8860b"))

escenarios = [
    ("Documento\n(9 pers., pérdidas\npermanentes)", 2.52, "#c0392b"),
    ("Corrigiendo\nplantilla a\n10 personas", 1.52, "#e67e22"),
    ("Si las pérdidas son\ntransitorias\n(9 pers. al 100%)", 0.52, "#f1c40f"),
    ("Documento + su propia\nexpansión (4 tiendas)\naplicando el 12.5%", 4.32, "#8e44ad"),
    ("Modelo recomendado:\ndemanda recurrente\n/ disponibilidad 85%", 10.06, "#7f8c8d"),
    ("Modelo recomendado\na 12 meses\n(+4 tiendas)", 12.18, "#1e8449"),
]
etiquetas = [e[0] for e in escenarios]
valores = [e[1] for e in escenarios]
colores = [e[2] for e in escenarios]

barras = ax2.barh(range(len(escenarios)), valores, color=colores, edgecolor="black", alpha=0.88)
for i, (b, v) in enumerate(zip(barras, valores)):
    sufijo = " FTE totales" if i >= 4 else " FTE adicionales"
    ax2.text(v + 0.15, i, f"{v:.2f}{sufijo}", va="center", fontsize=10, fontweight="bold")

ax2.axvline(3, color="#c0392b", linestyle="--", lw=2)
ax2.annotate("Petición del documento:\n3 personas", xy=(3.0, 1.75), xytext=(6.6, 1.75),
             color="#c0392b", fontsize=9.5, fontweight="bold", va="center", ha="left",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#c0392b"),
             arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.5))
ax2.set_yticks(range(len(escenarios)))
ax2.set_yticklabels(etiquetas, fontsize=9)
ax2.invert_yaxis()
ax2.set_ylim(len(escenarios) + 0.4, -0.6)
ax2.set_xlabel("FTE (equivalentes a tiempo completo)", fontsize=11, labelpad=8)
ax2.set_title("La misma data soporta respuestas entre 0.5 y 12 FTE\n"
              "según el supuesto que se elija: el modelo no es robusto",
              fontsize=12, fontweight="bold")
ax2.grid(axis="x", alpha=0.3, linestyle=":")
ax2.set_xlim(0, 16)
ax2.text(0.5, -0.175,
         "Las 4 primeras barras son incrementos sobre la plantilla actual; las 2 últimas son "
         "dotación total requerida\n(la plantilla actual de 9-10 personas ya está incluida en esa cifra)",
         transform=ax2.transAxes, ha="center", fontsize=9, style="italic")

fig.suptitle("Auditoría de la Propuesta de Aumento de Plantilla — Almacén Fábrica",
             fontsize=15, fontweight="bold", y=0.99)
plt.tight_layout(rect=[0, 0.04, 1, 0.96])
plt.savefig("/opt/cursor/artifacts/auditoria_carga_almacen_v4.png", dpi=140,
            bbox_inches="tight", facecolor="white")
print("Grafico generado: /opt/cursor/artifacts/auditoria_carga_almacen_v4.png")
print(f"Suma de control carga semanal = {carga.sum():.2f} HH (documento: 287.75 HH)")
print(f"Suma de control horas libres  = {no_asignadas.sum():.2f} HH")
