"""Recalcula el modelo v4 desde cero en Python y lo compara con el Excel.

Sirve para detectar formulas que apunten a la fila equivocada. Se ejecuta
sobre el archivo recalculado por LibreOffice (recalc/), que ya trae los
valores en cache.
"""

import sys

import openpyxl

RECALC = "recalc/Modelo_Capacidad_CUADRO_v4.xlsx"

DIAS = 20
OPS_PZA = 8.9
SS = 0.10
GAIN = 0.08
CESION_L3 = 0.10
REPROC = {"Actual": 0.0576, "A": 0.048, "B": 0.04, "C": 0.04, "D": 0.035}
OPS_TIPO = {"Overlock": 7, "Cuello": 1, "Ruedo": 1}
DEM_REG, DEM_DIC, SURTIDO = 4145, 9434, 6000
TIENDAS, NUEVAS_26, NUEVAS_27 = 8, 1, 3
NUEVA = "nueva"

# (linea, tipo, nominal, {escenario: ops/dia o NUEVA})
POSICIONES = [
    ("L1", "Overlock", 190, dict(Actual=190, A=190, B=190, C=190, D=190)),
    ("L1", "Cuello", 196, dict(Actual=196, A=196, B=196, C=196, D=196)),
    ("L1", "Overlock", 198, dict(Actual=198, A=198, B=198, C=198, D=198)),
    ("L1", "Ruedo", 101, dict(Actual=101, A=101, B=101, C=101, D=101)),
    ("L2", "Overlock", 190, dict(Actual=150, A=NUEVA, B=NUEVA, C=NUEVA, D=NUEVA)),
    ("L2", "Cuello", 196, dict(Actual=196, A=196, B=196, C=196, D=196)),
    ("L2", "Overlock", 198, dict(Actual=198, A=198, B=198, C=198, D=198)),
    ("L2", "Ruedo", 101, dict(Actual=101, A=101, B=101, C=101, D=101)),
    ("L3", "Overlock", 190, dict(Actual=190, A=190, B=190, C=190, D=190)),
    ("L3", "Cuello", 196, dict(Actual=196, A=196, B=196, C=196, D=196)),
    ("L3", "Overlock", 198, dict(Actual=198, A=198, B=198, C=198, D=198)),
    ("L3", "Ruedo", 101, dict(Actual=50.5, A=NUEVA, B=NUEVA, C=NUEVA, D=NUEVA)),
    ("L3", "Ruedo", 100, dict(Actual=0, A=NUEVA, B=NUEVA, C=NUEVA, D=NUEVA)),
    ("L4", "Overlock", 190, dict(Actual=190, A=190, B=190, C=190, D=190)),
    ("L4", "Cuello", 196, dict(Actual=196, A=196, B=196, C=196, D=196)),
    ("L4", "Overlock", 198, dict(Actual=198, A=198, B=198, C=198, D=198)),
    ("L4", "Ruedo", 101, dict(Actual=101, A=101, B=NUEVA, C=NUEVA, D=NUEVA)),
    ("L4", "Ruedo", 100, dict(Actual=0, A=NUEVA, B=NUEVA, C=NUEVA, D=NUEVA)),
    ("L1", "Ruedo", 100, dict(Actual=0, A=0, B=NUEVA, C=NUEVA, D=NUEVA)),
    ("L2", "Ruedo", 100, dict(Actual=0, A=0, B=NUEVA, C=NUEVA, D=NUEVA)),
    # Overlock de apoyo: el cambio de la v4.
    ("L1", "Overlock", 190, dict(Actual=0, A=0, B=NUEVA, C=NUEVA, D=NUEVA)),
    ("L2", "Overlock", 190, dict(Actual=0, A=0, B=NUEVA, C=NUEVA, D=NUEVA)),
    ("L6", "Overlock", 190, dict(Actual=0, A=0, B=0, C=0, D=NUEVA)),
    ("L6", "Cuello", 196, dict(Actual=0, A=0, B=0, C=0, D=NUEVA)),
    ("L6", "Overlock", 198, dict(Actual=0, A=0, B=0, C=0, D=NUEVA)),
    ("L6", "Ruedo", 101, dict(Actual=0, A=0, B=0, C=0, D=NUEVA)),
    ("L6", "Ruedo", 100, dict(Actual=0, A=0, B=0, C=0, D=NUEVA)),
]
ESCENARIOS = ["Actual", "A", "B", "C", "D"]
# La cesion del 10% de L3 a la Linea 5 se recupera en C y D.
CEDE_L3 = {"Actual": True, "A": True, "B": True, "C": False, "D": False}


def ops(pos, esc):
    valor = pos[3][esc]
    return pos[2] * (1 + GAIN) if valor == NUEVA else valor


def capacidad(esc):
    por_tipo = {t: 0.0 for t in OPS_TIPO}
    por_linea = {}
    for pos in POSICIONES:
        linea, tipo = pos[0], pos[1]
        valor = ops(pos, esc)
        if linea == "L3" and CEDE_L3[esc]:
            valor *= 1 - CESION_L3
        por_tipo[tipo] += valor
        por_linea[linea] = por_linea.get(linea, 0.0) + valor
    return por_tipo, por_linea


def demanda():
    return {
        1: DEM_REG * (1 + SS),
        2: DEM_DIC * (1 + SS),
        3: (DEM_REG * 2 + DEM_DIC) * (1 + SS) / 3,
        4: ((DEM_REG * 2 + DEM_DIC) * (1 + NUEVAS_26 / TIENDAS)
            + SURTIDO * NUEVAS_26) * (1 + SS) / 3,
        5: DEM_REG * ((TIENDAS + NUEVAS_26 + NUEVAS_27) / TIENDAS) * (1 + SS),
        6: ((DEM_REG * 2 + DEM_DIC) * ((TIENDAS + NUEVAS_26 + NUEVAS_27) / TIENDAS)
            + SURTIDO * NUEVAS_27) * (1 + SS) / 3,
    }


def main():
    wb = openpyxl.load_workbook(RECALC, data_only=True)
    cap_ws, dem_ws, lin_ws = wb["Capacidad"], wb["Demanda y Deficit"], wb["Lineas por Escenario"]
    cols = dict(zip(ESCENARIOS, "BCDEF"))
    dem_cols = dict(zip(ESCENARIOS, "CDEFG"))
    fila_tipo = {"Overlock": 5, "Cuello": 6, "Ruedo": 7}
    fila_linea = {"L1": 35, "L2": 36, "L3": 37, "L4": 38, "L6": 39}
    col_linea = dict(zip(ESCENARIOS, ["F", "H", "J", "L", "N"]))

    fallos = []

    def check(etiqueta, esperado, obtenido, tol=1e-6):
        ok = obtenido is not None and abs(esperado - obtenido) < tol
        print(f"{'OK ' if ok else 'MAL'} {etiqueta:52s} py={esperado:12.4f} xl="
              f"{'None' if obtenido is None else format(obtenido, '12.4f')}")
        if not ok:
            fallos.append(etiqueta)

    for esc in ESCENARIOS:
        por_tipo, por_linea = capacidad(esc)
        col = cols[esc]
        for tipo, fila in fila_tipo.items():
            check(f"[{esc}] ops/día {tipo}", por_tipo[tipo],
                  cap_ws[f"{col}{fila}"].value)
        for linea, fila in fila_linea.items():
            check(f"[{esc}] ops/día {linea}", por_linea.get(linea, 0.0),
                  lin_ws[f"{col_linea[esc]}{fila}"].value)
        total = sum(por_tipo.values())
        check(f"[{esc}] TOTAL ops/día", total, cap_ws[f"{col}8"].value)

        # Modelo 1
        check(f"[{esc}] M1 pzas/mes netas",
              total * DIAS * (1 - REPROC[esc]) / OPS_PZA, cap_ws[f"{col}15"].value)
        # Modelo 2
        pzas_dia = min(por_tipo[t] / OPS_TIPO[t] for t in OPS_TIPO)
        check(f"[{esc}] M2 pzas/día (restricción)", pzas_dia,
              cap_ws[f"{col}23"].value)
        pzas_mes = pzas_dia * DIAS * (1 - REPROC[esc])
        check(f"[{esc}] M2 pzas/mes netas", pzas_mes, cap_ws[f"{col}26"].value)
        restriccion = min(OPS_TIPO, key=lambda t: por_tipo[t] / OPS_TIPO[t])
        xl_restriccion = cap_ws[f"{col}24"].value
        esperado_txt = {"Overlock": "Overlock", "Cuello": "Collaret Cuello",
                        "Ruedo": "Collaret Ruedo"}[restriccion]
        ok = xl_restriccion == esperado_txt
        print(f"{'OK ' if ok else 'MAL'} [{esc}] restricción activa"
              f"{'':29s} py={esperado_txt} xl={xl_restriccion}")
        if not ok:
            fallos.append(f"[{esc}] restricción")

        for n, dem in demanda().items():
            check(f"[{esc}] déficit demanda {n}", pzas_mes - dem,
                  dem_ws[f"{dem_cols[esc]}{n + 4}"].value, tol=1e-4)

    inv_ws = wb["Inversion"]
    precios = dict(ruedo=3000, cuello=1900, over=1400)
    compras = {"A": (3, 0, 1), "B": (6, 0, 3), "C": (7, 0, 3), "D": (9, 1, 5)}
    for i, (esc, (r, c, o)) in enumerate(compras.items()):
        total = r * precios["ruedo"] + c * precios["cuello"] + o * precios["over"]
        check(f"[{esc}] inversión US$", total, inv_ws[f"H{5 + i}"].value)
        check(f"[{esc}] nº máquinas", r + c + o, wb["Escenarios"][f"D{5 + i}"].value)

    print()
    if fallos:
        print(f"FALLARON {len(fallos)} comprobaciones: {fallos}")
        sys.exit(1)
    print("Todas las comprobaciones coinciden con el recálculo independiente.")


if __name__ == "__main__":
    main()
