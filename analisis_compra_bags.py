#!/usr/bin/env python3
"""Proyección de compra 6 meses - Travel Bag 40L, Mini Bag, Dry Bag 30L."""

import pandas as pd
import numpy as np
from pathlib import Path

UPLOADS = Path("/home/ubuntu/.cursor/projects/workspace/uploads")

# Factores estratégicos (imágenes del usuario)
FACTORES = {
    "stock_seguridad": 0.20,
    "pedidos_corporativos": 0.08,
    "factor_marketing": 0.05,
    "factor_migracion": 0.10,  # productos nuevos que reemplazan modelo existente
    "expansion_red": 0.55,     # Margarita 33% + Nueva tienda 22%
}

# Mapeo modelo actual -> producto nuevo
MODELOS = {
    "TRAVEL BAG 40L": {
        "nuevo": "Travel Bag 40L (new)",
        "colores_nuevos": ["Azul Petróleo 19", "Negro 1"],
        "estado": "Aprobado - listo para compra",
        "aplica_migracion": True,
    },
    "MINI BAG": {
        "nuevo": "Moon bag",
        "colores_nuevos": ["Por definir (tonos tierra/oliva/beige)"],
        "estado": "En desarrollo - posible sustituto Minibag",
        "aplica_migracion": True,
    },
    "DRY BAG 30L": {
        "nuevo": "Drybag 30L (new)",
        "colores_nuevos": ["Por definir"],
        "estado": "Muestra en desarrollo",
        "aplica_migracion": True,
    },
}

# Meses de la 1ra compra: Noviembre - Abril (6 meses)
MESES_PROYECCION = [
  "noviembre-2025", "diciembre-2025", "enero-2026", "febrero-2026", "marzo-2026", "abril-2026"
]

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def parse_cantidad(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    return float(str(val).replace(",", "."))


def load_ventas(path, modelo):
    df = pd.read_csv(path, sep=";", encoding="latin-1", dtype=str)
    col_map = {c: c.strip().lower() for c in df.columns}
    df = df.rename(columns=col_map)
    qty_col = [c for c in df.columns if "cant" in c][0]
    loc_col = [c for c in df.columns if "ubicaci" in c][0]
    df["cantidad"] = df[qty_col].apply(parse_cantidad)
    df["modelo"] = modelo
    df["mes"] = df["fecha"].str.strip().str.lower()
    df["ubicacion"] = df[loc_col].str.strip()
    return df


def load_inventario(path):
    df = pd.read_csv(path, sep=";", encoding="latin-1", dtype=str)
    col_map = {}
    for c in df.columns:
        cl = c.strip().lower()
        if "ubicaci" in cl:
            col_map[c] = "ubicacion"
        elif "cantidad" in cl:
            col_map[c] = "cantidad_inv"
        else:
            col_map[c] = c.strip()
    df = df.rename(columns=col_map)
    df["cantidad"] = df["cantidad_inv"].apply(parse_cantidad)
    return df


def mes_num(mes_str):
    mes = mes_str.split("-")[0]
    return MESES_ES.get(mes, 0)


def calcular_indices_estacionales(ventas_por_mes):
    """Índice estacional por mes del año (promedio mensual / promedio anual)."""
    ventas_por_mes = ventas_por_mes.copy()
    ventas_por_mes["mes_num"] = ventas_por_mes["mes"].apply(mes_num)
    por_mes_anio = ventas_por_mes.groupby("mes_num")["cantidad"].sum()
    promedio = por_mes_anio.mean()
    if promedio == 0:
        return por_mes_anio * 0 + 1
    return (por_mes_anio / promedio).to_dict()


def proyectar_modelo(df_ventas, inv_modelo, nombre_modelo):
    info = MODELOS[nombre_modelo]

    # Ventas totales por mes
    mensual = df_ventas.groupby("mes")["cantidad"].sum().reset_index()
    mensual = mensual.sort_values("mes", key=lambda s: s.map(lambda x: (mes_num(x), x)))

    total_historico = df_ventas["cantidad"].sum()
    meses_historico = len(mensual)
    promedio_mensual = total_historico / meses_historico if meses_historico else 0

    # Índices estacionales
    indices = calcular_indices_estacionales(mensual)

    # Demanda base 6 meses con estacionalidad
    demanda_mensual = []
    for mes_proj in MESES_PROYECCION:
        m = mes_num(mes_proj)
        idx = indices.get(m, 1.0)
        demanda = promedio_mensual * idx
        demanda_mensual.append({"mes": mes_proj, "indice": round(idx, 3), "demanda": round(demanda, 1)})

    demanda_base_6m = sum(d["demanda"] for d in demanda_mensual)

    # Ventas por ubicación (excluir devoluciones netas)
    por_ubicacion = df_ventas.groupby("ubicacion")["cantidad"].sum().sort_values(ascending=False)

    # Ventas por color
    por_color = df_ventas.groupby("color")["cantidad"].sum().sort_values(ascending=False)
    total_color = por_color.sum()
    mix_color = (por_color / total_color * 100).round(1) if total_color else por_color * 0

    # Inventario
    inv_tiendas = inv_modelo[inv_modelo["ubicacion"] != "TALLER"].groupby("ubicacion")["cantidad"].sum()
    inv_taller = inv_modelo[inv_modelo["ubicacion"] == "TALLER"].groupby("COLOR")["cantidad"].sum()
    inv_total = inv_modelo["cantidad"].sum()
    inv_tiendas_total = inv_modelo[inv_modelo["ubicacion"] != "TALLER"]["cantidad"].sum()
    inv_taller_total = inv_modelo[inv_modelo["ubicacion"] == "TALLER"]["cantidad"].sum()
    inv_por_color = inv_modelo.groupby("COLOR")["cantidad"].sum()

    # Aplicar factores
    f = FACTORES
    migracion = f["factor_migracion"] if info["aplica_migracion"] else 0

    # Fórmula compuesta: demanda ajustada = base × (1+expansión) × (1+migración) × (1+marketing) × (1+corporativo)
    # Stock seguridad se suma al final sobre el total
    multiplicador = (1 + f["expansion_red"]) * (1 + migracion) * (1 + f["factor_marketing"]) * (1 + f["pedidos_corporativos"])
    demanda_ajustada = demanda_base_6m * multiplicador
    stock_seg = demanda_ajustada * f["stock_seguridad"]
    necesidad_bruta = demanda_ajustada + stock_seg
    compra_neta = max(0, necesidad_bruta - inv_total)

  # Escenarios
    escenarios = {}
    for letra, mult in [("A - Base", 1.0), ("B - Conservador (-10%)", 0.90), ("C - Agresivo (+10%)", 1.10)]:
        d = demanda_base_6m * mult
        da = d * multiplicador
        ss = da * f["stock_seguridad"]
        compra = max(0, da + ss - inv_total)
        escenarios[letra] = round(compra)

    return {
        "modelo_actual": nombre_modelo,
        "producto_nuevo": info["nuevo"],
        "estado": info["estado"],
        "colores_nuevos": info["colores_nuevos"],
        "historico": {
            "total_unidades": round(total_historico),
            "meses_datos": meses_historico,
            "promedio_mensual": round(promedio_mensual, 1),
            "rango_mensual": f"{mensual['cantidad'].min():.0f} - {mensual['cantidad'].max():.0f}",
        },
        "estacionalidad": {
            "indices": {k: round(v, 3) for k, v in sorted(indices.items())},
            "min_idx": round(min(indices.values()), 3),
            "max_idx": round(max(indices.values()), 3),
            "ratio": round(max(indices.values()) / min(indices.values()), 2) if min(indices.values()) > 0 else None,
        },
        "demanda_6m": demanda_mensual,
        "demanda_base_6m": round(demanda_base_6m),
        "factores_aplicados": {
            "expansion_red_55pct": f["expansion_red"],
            "migracion_10pct": migracion,
            "marketing_5pct": f["factor_marketing"],
            "corporativos_8pct": f["pedidos_corporativos"],
            "multiplicador_total": round(multiplicador, 4),
            "stock_seguridad_20pct": f["stock_seguridad"],
        },
        "inventario": {
            "total": round(inv_total),
            "tiendas": round(inv_tiendas_total),
            "taller_bodega": round(inv_taller_total),
            "por_color": inv_por_color.round(0).astype(int).to_dict(),
        },
        "proyeccion": {
            "demanda_ajustada_6m": round(demanda_ajustada),
            "stock_seguridad": round(stock_seg),
            "necesidad_bruta": round(necesidad_bruta),
            "inventario_actual": round(inv_total),
            "COMPRA_RECOMENDADA": round(compra_neta),
        },
        "escenarios": escenarios,
        "mix_color_ventas_pct": mix_color.to_dict(),
        "top_ubicaciones_ventas": por_ubicacion.head(8).round(0).astype(int).to_dict(),
    }


def distribuir_por_color(compra_total, mix_color_pct, colores_nuevos_count=2):
    """Distribuye compra según mix histórico de colores."""
    if not mix_color_pct or compra_total <= 0:
        return {}
    # Top colores que representan ~90% ventas
    sorted_colors = sorted(mix_color_pct.items(), key=lambda x: -x[1])
    distrib = {}
    remaining = compra_total
    for color, pct in sorted_colors[:colores_nuevos_count]:
        qty = round(compra_total * pct / 100)
        distrib[color] = qty
        remaining -= qty
    # Ajuste redondeo
    if sorted_colors:
        distrib[sorted_colors[0][0]] += remaining - sum(distrib.values()) + (compra_total - sum(distrib.values()))
    return {k: int(v) for k, v in distrib.items()}


def main():
    archivos = {
        "TRAVEL BAG 40L": UPLOADS / "TRAVEL_BAG_40L_VENTAS_ACTUALIZADO_9a0f.csv",
        "MINI BAG": UPLOADS / "MINI_BAG_VENTAS_ACTUALIZADO_273c.csv",
        "DRY BAG 30L": UPLOADS / "DRY_BAG_30_L_VENTAS_ACTUALIZADO_97a5.csv",
    }

    inv = load_inventario(UPLOADS / "INVENTARIO_DE_MODELOS_BAGS_ACTUALIZADO_HOY_2619.csv")

    resultados = []
    resumen_compras = []

    print("=" * 80)
    print("PROYECCIÓN DE COMPRA — 6 MESES (Nov 2025 - Abr 2026)")
    print("1ra compra anual | Factores: +55% red, +10% migración, +5% mkt, +8% corp, +20% SS")
    print("=" * 80)

    for modelo, path in archivos.items():
        df = load_ventas(path, modelo)
        inv_m = inv[inv["MODELO"] == modelo]
        r = proyectar_modelo(df, inv_m, modelo)
        resultados.append(r)

        print(f"\n{'─' * 80}")
        print(f"📦 {r['modelo_actual']}  →  {r['producto_nuevo']}")
        print(f"   Estado: {r['estado']}")
        print(f"   Colores nuevos: {', '.join(r['colores_nuevos'])}")
        print(f"\n   HISTÓRICO VENTAS ({r['historico']['meses_datos']} meses):")
        print(f"   Total: {r['historico']['total_unidades']:,} u | Prom/mes: {r['historico']['promedio_mensual']} u")
        print(f"   Rango mensual: {r['historico']['rango_mensual']} u")
        ratio = r['estacionalidad']['ratio']
        print(f"   Estacionalidad: índice {r['estacionalidad']['min_idx']} - {r['estacionalidad']['max_idx']} (ratio {ratio}x)")

        print(f"\n   DEMANDA 6 MESES (con estacionalidad):")
        for d in r["demanda_6m"]:
            print(f"     {d['mes']:20s} idx={d['indice']:.2f}  →  {d['demanda']:.0f} u")
        print(f"   Subtotal base: {r['demanda_base_6m']:,} u")

        m = r["factores_aplicados"]["multiplicador_total"]
        print(f"\n   AJUSTES ESTRATÉGICOS (×{m:.3f}):")
        print(f"     +55% expansión red (Margarita + Nueva tienda)")
        print(f"     +10% factor migración (modelo nuevo)")
        print(f"     +5% marketing | +8% pedidos corporativos")
        print(f"   Demanda ajustada: {r['proyeccion']['demanda_ajustada_6m']:,} u")
        print(f"   + Stock seguridad 20%: {r['proyeccion']['stock_seguridad']:,} u")
        print(f"   = Necesidad bruta: {r['proyeccion']['necesidad_bruta']:,} u")

        print(f"\n   INVENTARIO ACTUAL:")
        print(f"     Total: {r['inventario']['total']:,} (Tiendas: {r['inventario']['tiendas']:,} | Taller: {r['inventario']['taller_bodega']:,})")
        print(f"     Por color: {r['inventario']['por_color']}")

        compra = r["proyeccion"]["COMPRA_RECOMENDADA"]
        print(f"\n   ✅ COMPRA NETA RECOMENDADA: {compra:,} unidades")
        print(f"   Escenarios: A={r['escenarios']['A - Base']:,} | B={r['escenarios']['B - Conservador (-10%)']:,} | C={r['escenarios']['C - Agresivo (+10%)']:,}")

        # Distribución por color histórico
        if modelo == "TRAVEL BAG 40L":
            dist = {"Azul Petróleo 19": round(compra * 0.35), "Negro 1": round(compra * 0.65)}
        elif modelo == "MINI BAG":
            # Moon bag - usar mix mini bag como proxy
            mix = r["mix_color_ventas_pct"]
            top = sorted(mix.items(), key=lambda x: -x[1])[:3]
            dist = {f"Color {i+1} (ref {c})": round(compra * p/100) for i, (c, p) in enumerate(top)}
        else:
            mix = r["mix_color_ventas_pct"]
            top = sorted(mix.items(), key=lambda x: -x[1])[:4]
            dist = {c: round(compra * p/100) for c, p in top}

        print(f"   Distribución sugerida por color (proxy histórico):")
        for c, q in dist.items():
            print(f"     {c}: {q:,} u")

        resumen_compras.append({
            "Modelo actual": modelo,
            "Producto nuevo": r["producto_nuevo"],
            "Demanda base 6m": r["demanda_base_6m"],
            "Demanda ajustada": r["proyeccion"]["demanda_ajustada_6m"],
            "Inventario": r["inventario"]["total"],
            "COMPRA": compra,
            "Esc. Conservador": r["escenarios"]["B - Conservador (-10%)"],
            "Esc. Agresivo": r["escenarios"]["C - Agresivo (+10%)"],
        })

    print(f"\n{'=' * 80}")
    print("RESUMEN EJECUTIVO — CANTIDADES PARA NEGOCIAR")
    print("=" * 80)
    df_res = pd.DataFrame(resumen_compras)
    print(df_res.to_string(index=False))
    total = df_res["COMPRA"].sum()
    print(f"\n🎯 TOTAL COMPRA CONSOLIDADA (Escenario A): {total:,} unidades")
    print(f"   Rango escenarios B-C: {df_res['Esc. Conservador'].sum():,} — {df_res['Esc. Agresivo'].sum():,} u")

    # Guardar CSV
    out = Path("/workspace/proyeccion_compra_bags_6m.csv")
    df_res.to_csv(out, index=False)
    print(f"\nArchivo guardado: {out}")

    return resultados, df_res


if __name__ == "__main__":
    main()
