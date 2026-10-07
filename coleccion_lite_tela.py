"""Tela disponible compartida Chaqueta Lite + Lite Pant (Negro + Verde Militar)."""

# Metros comprados (pool global para ambos modelos)
TELA_POOL_NEGRO_MTS = 2500
TELA_POOL_VERDE_MTS = 950

# Negro: escenario conservador = reserva / margen +30% sobre consumo de corte
NEGRO_FACTOR_RESERVA = 1.30

# Reparto de tela entre modelos (mismo peso que rango acordado 1.280 / 1.350)
PANT_FABRIC_SHARE = 1280 / (1280 + 1350)
CHAQUETA_FABRIC_SHARE = 1 - PANT_FABRIC_SHARE

COLORES_TELA_REAL = ["Negro", "Verde Militar"]


def avg_consumo_mts(consumo_mts: dict, talla_pct: dict, tallas: list) -> float:
    return sum(consumo_mts[t] * talla_pct[t] for t in tallas)


def calc_fabric_production(
    fabric_share: float,
    consumo_mts: dict,
    talla_pct: dict,
    tallas: list,
) -> dict:
    """Verde al máximo de la tela asignada; negro mín/máx con factor +30%."""
    avg_m = avg_consumo_mts(consumo_mts, talla_pct, tallas)
    if avg_m <= 0:
        raise ValueError("Consumo promedio por pieza debe ser > 0")

    verde_m = TELA_POOL_VERDE_MTS * fabric_share
    negro_m_full = TELA_POOL_NEGRO_MTS * fabric_share
    negro_m_reserva = negro_m_full / NEGRO_FACTOR_RESERVA

    verde_und = int(verde_m / avg_m)
    negro_und_min = int(negro_m_reserva / avg_m)
    negro_und_max = int(negro_m_full / avg_m)

    color_min = {"Verde Militar": verde_und, "Negro": negro_und_min}
    color_max = {"Verde Militar": verde_und, "Negro": negro_und_max}

    return {
        "avg_m": round(avg_m, 4),
        "verde_m_asignado": round(verde_m, 2),
        "negro_m_asignado": round(negro_m_full, 2),
        "negro_m_con_reserva_30": round(negro_m_reserva, 2),
        "verde_und": verde_und,
        "negro_und_min": negro_und_min,
        "negro_und_max": negro_und_max,
        "prod_min": verde_und + negro_und_min,
        "prod_max": verde_und + negro_und_max,
        "color_totals_min": color_min,
        "color_totals_max": color_max,
    }


def distribute_by_color_talla_fixed(
    color_totals: dict,
    talla_pct: dict,
    tallas: list,
    distribute_by_talla,
) -> tuple[dict, dict]:
    matrix = {c: distribute_by_talla(color_totals[c], talla_pct) for c in color_totals}
    return matrix, dict(color_totals)
