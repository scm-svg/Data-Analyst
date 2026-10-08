"""Tela disponible compartida Chaqueta Lite + Lite Pant (Negro + Verde Militar)."""

# Metros comprados (pool global para ambos modelos)
TELA_POOL_NEGRO_MTS = 2500
TELA_POOL_VERDE_MTS = 950

# Escenario MÍN: metros utilizables = asignados ÷ factor (margen sobre consumo de corte)
# Escenario MÁX: 100% de los metros asignados al color
VERDE_TELA_MIN_FACTOR = 1.30
NEGRO_TELA_MIN_FACTOR = 1.15  # mín negro más alto que con ÷1,30 (menos margen en mín)

# Reparto de tela entre modelos (mismo peso que rango acordado 1.280 / 1.350)
PANT_FABRIC_SHARE = 1280 / (1280 + 1350)
CHAQUETA_FABRIC_SHARE = 1 - PANT_FABRIC_SHARE

COLORES_TELA_REAL = ["Negro", "Verde Militar"]

# Compatibilidad con textos existentes
NEGRO_FACTOR_RESERVA = NEGRO_TELA_MIN_FACTOR

# Objetivo XS (I+D): lo restado de XS se reparte 50/50 entre S y M; L y XL sin cambio
CHAQUETA_XS_TARGET = 0.205
PANT_XS_TARGET = 0.18


def apply_xs_shift_to_sm(talla_pct: dict, xs_target: float) -> dict:
    """Fija XS al objetivo; transfiere el exceso por igual a S y M."""
    out = dict(talla_pct)
    xs = out.get("XS", 0)
    if xs <= xs_target:
        return out
    delta = xs - xs_target
    out["XS"] = xs_target
    out["S"] = out.get("S", 0) + delta / 2
    out["M"] = out.get("M", 0) + delta / 2
    return out


def avg_consumo_mts(consumo_mts: dict, talla_pct: dict, tallas: list) -> float:
    return sum(consumo_mts[t] * talla_pct[t] for t in tallas)


def _und_from_meters(meters: float, avg_m: float, min_factor: float = 1.0) -> int:
    return int(meters / min_factor / avg_m)


def calc_fabric_production(
    fabric_share: float,
    consumo_mts: dict,
    talla_pct: dict,
    tallas: list,
) -> dict:
    """Mín y máx por color según tela asignada; verde y negro con rangos distintos."""
    avg_m = avg_consumo_mts(consumo_mts, talla_pct, tallas)
    if avg_m <= 0:
        raise ValueError("Consumo promedio por pieza debe ser > 0")

    verde_m = TELA_POOL_VERDE_MTS * fabric_share
    negro_m = TELA_POOL_NEGRO_MTS * fabric_share

    verde_und_max = _und_from_meters(verde_m, avg_m, 1.0)
    verde_und_min = _und_from_meters(verde_m, avg_m, VERDE_TELA_MIN_FACTOR)
    negro_und_max = _und_from_meters(negro_m, avg_m, 1.0)
    negro_und_min = _und_from_meters(negro_m, avg_m, NEGRO_TELA_MIN_FACTOR)

    color_min = {"Verde Militar": verde_und_min, "Negro": negro_und_min}
    color_max = {"Verde Militar": verde_und_max, "Negro": negro_und_max}

    return {
        "avg_m": round(avg_m, 4),
        "verde_m_asignado": round(verde_m, 2),
        "negro_m_asignado": round(negro_m, 2),
        "verde_m_min_uso": round(verde_m / VERDE_TELA_MIN_FACTOR, 2),
        "negro_m_min_uso": round(negro_m / NEGRO_TELA_MIN_FACTOR, 2),
        "verde_und_min": verde_und_min,
        "verde_und_max": verde_und_max,
        "negro_und_min": negro_und_min,
        "negro_und_max": negro_und_max,
        "verde_und": verde_und_max,
        "prod_min": verde_und_min + negro_und_min,
        "prod_max": verde_und_max + negro_und_max,
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
