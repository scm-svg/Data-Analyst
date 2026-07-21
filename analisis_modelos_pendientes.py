#!/usr/bin/env python3
"""Proyección compra 6 meses — modelos pendientes (versión refinada)."""

import pandas as pd
from pathlib import Path

UPLOADS = Path("/home/ubuntu/.cursor/projects/workspace/uploads")
VENTAS_FILE = UPLOADS / "VENTAS_completo_MODELOS_POR_ANALIZAR_daac.csv"
INV_FILE = UPLOADS / "INVENTARIOS_completo_DE_LOS_SIGUIENTS_MODELOS_A_EVALUAR_db41.csv"

FACTORES = {
    "stock_seguridad": 0.20,
    "pedidos_corporativos": 0.08,
    "factor_marketing": 0.05,
    "factor_migracion": 0.10,
    "expansion_red": 0.55,
}

MESES_PROYECCION = [
    "noviembre-2025", "diciembre-2025", "enero-2026",
    "febrero-2026", "marzo-2026", "abril-2026",
]

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

MULTIPLICADOR = (
    (1 + FACTORES["expansion_red"])
    * (1 + FACTORES["factor_migracion"])
    * (1 + FACTORES["factor_marketing"])
    * (1 + FACTORES["pedidos_corporativos"])
)


def parse_cantidad(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    return float(str(val).replace(",", "."))


def mes_num(mes_str):
    return MESES_ES.get(str(mes_str).split("-")[0].strip().lower(), 0)


def load_ventas(path):
    df = pd.read_csv(path, sep=";", encoding="latin-1", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    qty_col = [c for c in df.columns if "Cant" in c or "cant" in c][0]
    df["cantidad"] = df[qty_col].apply(parse_cantidad)
    df["mes"] = df["FECHA"].str.strip().str.lower()
    df["modelo"] = df["Modelo"].str.strip()
    df["fecha_dt"] = pd.to_datetime(df["Fecha de la orden"], dayfirst=True, errors="coerce")
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
        elif "color" in cl:
            col_map[c] = "color"
        else:
            col_map[c] = c.strip()
    df = df.rename(columns=col_map)
    df["cantidad"] = df["cantidad_inv"].apply(parse_cantidad)
    df["modelo"] = df["MODELO"].str.strip()
    df["color"] = df["color"].str.strip()
    return df


def calcular_demanda_6m(mensual, prom_mensual, usar_estacional=True):
    if not usar_estacional or len(mensual) < 6:
        base = prom_mensual * 6
        detalle = [{"mes": m, "idx": 1.0, "u": prom_mensual} for m in MESES_PROYECCION]
        return base, detalle, "promedio simple (historial < 6 meses)"

    v = mensual.copy()
    v["mes_num"] = v["mes"].apply(mes_num)
    por_mes = v.groupby("mes_num")["cantidad"].sum()
    prom = por_mes.mean()
    indices = (por_mes / prom).to_dict() if prom else {}

    detalle = []
    for mp in MESES_PROYECCION:
        idx = indices.get(mes_num(mp), 1.0)
        detalle.append({"mes": mp, "idx": round(idx, 3), "u": prom_mensual * idx})
    base = sum(d["u"] for d in detalle)
    ratio = round(max(indices.values()) / min(indices.values()), 2) if indices and min(indices.values()) > 0 else None
    return base, detalle, f"estacional (ratio {ratio}x)" if ratio else "estacional"


def proyectar_modelo(df_v, inv_m, modelo):
    mensual = df_v.groupby("mes")["cantidad"].sum().reset_index()
    mensual = mensual.sort_values("mes", key=lambda s: s.map(lambda x: (mes_num(x), x)))
    n_meses = len(mensual)
    total = df_v["cantidad"].sum()
    prom_mensual = total / n_meses if n_meses else 0

    usar_estacional = n_meses >= 6
    base_6m, demanda_6m, metodo = calcular_demanda_6m(mensual, prom_mensual, usar_estacional)

    ajustada = base_6m * MULTIPLICADOR
    ss = ajustada * FACTORES["stock_seguridad"]
    bruta = ajustada + ss

    inv_total = inv_m["cantidad"].sum()
    inv_tiendas = inv_m[inv_m["ubicacion"].str.upper() != "TALLER"]["cantidad"].sum()
    inv_taller = inv_m[inv_m["ubicacion"].str.upper() == "TALLER"]["cantidad"].sum()

    compra_neta = max(0, round(bruta - inv_total))
    compra_bruta = round(bruta)
    meses_cobertura = inv_total / (ajustada / 6) if ajustada > 0 else 99

    mix = df_v.groupby("Color")["cantidad"].sum().sort_values(ascending=False)
    mix_pct = (mix / mix.sum() * 100).round(1) if mix.sum() else mix * 0
    inv_color = inv_m.groupby("color")["cantidad"].sum()

    ultimos = mensual.tail(3)["cantidad"].mean() if len(mensual) >= 3 else prom_mensual
    tendencia = "↑" if ultimos > prom_mensual * 1.1 else ("↓" if ultimos < prom_mensual * 0.9 else "→")

    alerta = []
    if n_meses < 6:
        alerta.append(f"⚠️ Solo {n_meses} meses de ventas — proyección con promedio simple")
    if meses_cobertura > 6:
        alerta.append(f"⚠️ Inventario cubre {meses_cobertura:.1f} meses de demanda ajustada — sin compra urgente")
    if inv_taller > inv_tiendas * 2 and inv_taller > 500:
        alerta.append(f"⚠️ Alto stock en Taller ({inv_taller:.0f} u) — revisar redistribución antes de comprar")

    return {
        "modelo": modelo,
        "n_meses": n_meses,
        "metodo": metodo,
        "historico": {"total": round(total), "prom_mensual": round(prom_mensual, 1), "tendencia": tendencia},
        "demanda_6m": demanda_6m,
        "base_6m": round(base_6m),
        "ajustada": round(ajustada),
        "stock_seg": round(ss),
        "bruta": round(bruta),
        "inventario": {"total": round(inv_total), "tiendas": round(inv_tiendas), "taller": round(inv_taller)},
        "meses_cobertura": round(meses_cobertura, 1),
        "compra_neta": compra_neta,
        "compra_bruta": compra_bruta,
        "conservador": round(max(0, compra_bruta * 0.9 - inv_total)),
        "agresivo": round(max(0, compra_bruta * 1.1 - inv_total)),
        "mix_color": mix_pct.to_dict(),
        "inv_color": inv_color.round(0).astype(int).to_dict(),
        "alertas": alerta,
    }


def distribuir_color(compra, mix_pct, inv_color, top_n=6):
    if compra <= 0 or not mix_pct:
        return []
    top = sorted(mix_pct.items(), key=lambda x: -x[1])[:top_n]
    dist = []
    remaining = compra
    for i, (color, pct) in enumerate(top):
        qty = round(compra * pct / 100) if i < len(top) - 1 else remaining
        remaining -= qty
        inv = inv_color.get(color, 0)
        dist.append({"color": color, "compra": qty, "inv": inv, "pct": pct})
    return dist


def main():
    ventas = load_ventas(VENTAS_FILE)
    inventario = load_inventario(INV_FILE)
    modelos = sorted(ventas["modelo"].unique())

    print("=" * 92)
    print("PROYECCIÓN COMPRA 6 MESES — MODELOS PENDIENTES (Nov 2025 → Abr 2026)")
    print(f"Factores: +55% red | +10% migración | +5% mkt | +8% corp | +20% SS | ×{MULTIPLICADOR:.3f}")
    print("Productos en catálogo continuo → se descuenta inventario actual del mismo SKU")
    print("=" * 92)

    resumen = []
    for modelo in modelos:
        r = proyectar_modelo(
            ventas[ventas["modelo"] == modelo],
            inventario[inventario["modelo"] == modelo],
            modelo,
        )

        print(f"\n{'━' * 92}")
        print(f"  {r['modelo']}")
        print(f"{'━' * 92}")
        h = r["historico"]
        print(f"  Ventas: {h['total']:,} u | {r['n_meses']} meses histórico | Prom: {h['prom_mensual']} u/mes | Tendencia: {h['tendencia']}")
        print(f"  Método proyección: {r['metodo']}")
        for a in r["alertas"]:
            print(f"  {a}")

        print(f"\n  Cálculo: base {r['base_6m']:,} → ajustada {r['ajustada']:,} → +SS {r['stock_seg']:,} → bruta {r['bruta']:,} u")
        print(f"  Inventario: {r['inventario']['total']:,} u (tiendas {r['inventario']['tiendas']:,} | taller {r['inventario']['taller']:,})")
        print(f"  Cobertura actual: {r['meses_cobertura']} meses de demanda ajustada")
        print(f"  ✅ COMPRA NETA: {r['compra_neta']:,} u  |  Conservador: {r['conservador']:,}  |  Agresivo: {r['agresivo']:,}")

        factor_mes = r["bruta"] / r["base_6m"] if r["base_6m"] else 1
        print(f"\n  Demanda mensual (bruta con factores):")
        for d in r["demanda_6m"]:
            print(f"    {d['mes']:22s} {d['u'] * factor_mes:6.0f} u")

        dist = distribuir_color(r["compra_neta"], r["mix_color"], r["inv_color"])
        if dist:
            print(f"\n  Distribución por color:")
            for row in dist:
                print(f"    {row['color']}: {row['compra']:,} u ({row['pct']}%) | inv: {row['inv']}")

        resumen.append({
            "Modelo": modelo,
            "Meses histórico": r["n_meses"],
            "Prom mensual": h["prom_mensual"],
            "Demanda base 6m": r["base_6m"],
            "Demanda ajustada": r["ajustada"],
            "Necesidad bruta": r["bruta"],
            "Inventario": r["inventario"]["total"],
            "Meses cobertura": r["meses_cobertura"],
            "COMPRA NETA": r["compra_neta"],
            "Conservador": r["conservador"],
            "Agresivo": r["agresivo"],
        })

    print(f"\n{'=' * 92}")
    print("RESUMEN EJECUTIVO — CANTIDADES PARA NEGOCIAR")
    print("=" * 92)
    df = pd.DataFrame(resumen)
    print(df.to_string(index=False))
    print(f"\n  🎯 TOTAL COMPRA NETA: {df['COMPRA NETA'].sum():,} u")
    print(f"     Rango B-C: {df['Conservador'].sum():,} — {df['Agresivo'].sum():,} u")

    # Modelos sin compra pero con necesidad
    sin_compra = df[df["COMPRA NETA"] == 0]
    if len(sin_compra):
        print(f"\n  📋 Modelos SIN compra (inventario suficiente):")
        for _, row in sin_compra.iterrows():
            print(f"     {row['Modelo']}: inv {row['Inventario']:,} u cubre {row['Meses cobertura']} meses (necesidad bruta {row['Necesidad bruta']:,} u)")

    out = Path("/workspace/proyeccion_compra_modelos_pendientes_6m.csv")
    df.to_csv(out, index=False)
    print(f"\n  Archivo: {out}")
    return df


if __name__ == "__main__":
    main()
