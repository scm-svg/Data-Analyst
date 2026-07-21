#!/usr/bin/env python3
"""Análisis detallado proyección compra bags - versión refinada."""

import pandas as pd
import numpy as np
from pathlib import Path

UPLOADS = Path("/home/ubuntu/.cursor/projects/workspace/uploads")

FACTORES = {
    "stock_seguridad": 0.20,
    "pedidos_corporativos": 0.08,
    "factor_marketing": 0.05,
    "factor_migracion": 0.10,
    "expansion_red": 0.55,
}

MESES_PROYECCION = [
    "noviembre-2025", "diciembre-2025", "enero-2026",
    "febrero-2026", "marzo-2026", "abril-2026"
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
    df["fecha_dt"] = pd.to_datetime(df["fecha de la orden"], dayfirst=True, errors="coerce")
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
    return MESES_ES.get(mes_str.split("-")[0], 0)


def calcular_indices(ventas_por_mes):
    v = ventas_por_mes.copy()
    v["mes_num"] = v["mes"].apply(mes_num)
    por_mes = v.groupby("mes_num")["cantidad"].sum()
    prom = por_mes.mean()
    return (por_mes / prom).to_dict() if prom else {}


def analizar():
    archivos = {
        "TRAVEL BAG 40L": {
            "path": UPLOADS / "TRAVEL_BAG_40L_VENTAS_ACTUALIZADO_9a0f.csv",
            "nuevo": "Travel Bag 40L (new)",
            "colores": {"Azul Petróleo 19": 0.35, "Negro 1": 0.65},
            "listo": True,
        },
        "MINI BAG": {
            "path": UPLOADS / "MINI_BAG_VENTAS_ACTUALIZADO_273c.csv",
            "nuevo": "Moon bag",
            "colores": None,  # por definir
            "listo": False,
        },
        "DRY BAG 30L": {
            "path": UPLOADS / "DRY_BAG_30_L_VENTAS_ACTUALIZADO_97a5.csv",
            "nuevo": "Drybag 30L (new)",
            "colores": None,
            "listo": False,
        },
    }

    inv_all = load_inventario(UPLOADS / "INVENTARIO_DE_MODELOS_BAGS_ACTUALIZADO_HOY_2619.csv")
    multiplicador = (
        (1 + FACTORES["expansion_red"])
        * (1 + FACTORES["factor_migracion"])
        * (1 + FACTORES["factor_marketing"])
        * (1 + FACTORES["pedidos_corporativos"])
    )

    print("=" * 90)
    print("ANÁLISIS DETALLADO — PROYECCIÓN COMPRA 6 MESES (Nov 2025 → Abr 2026)")
    print("=" * 90)

    resumen = []

    for modelo, cfg in archivos.items():
        df = load_ventas(cfg["path"], modelo)
        inv_m = inv_all[inv_all["MODELO"] == modelo]

        mensual = df.groupby("mes")["cantidad"].sum().reset_index()
        mensual = mensual.sort_values("mes", key=lambda s: s.map(lambda x: (mes_num(x), x)))
        indices = calcular_indices(mensual)
        prom_mensual = df["cantidad"].sum() / len(mensual)

        demanda_6m = []
        for mp in MESES_PROYECCION:
            idx = indices.get(mes_num(mp), 1.0)
            demanda_6m.append({"mes": mp, "idx": idx, "u": prom_mensual * idx})
        base_6m = sum(d["u"] for d in demanda_6m)

        ajustada = base_6m * multiplicador
        ss = ajustada * FACTORES["stock_seguridad"]
        bruta = ajustada + ss

        inv_total = inv_m["cantidad"].sum()
        inv_tiendas = inv_m[inv_m["ubicacion"] != "TALLER"]["cantidad"].sum()
        inv_taller = inv_m[inv_m["ubicacion"] == "TALLER"]["cantidad"].sum()

        # CRÍTICO: productos nuevos reemplazan viejos → NO descontar inventario viejo
        compra_bruta = round(bruta)
        compra_transicion = round(max(0, bruta - inv_tiendas * 0.3))  # 30% tienda puede liquidarse en transición

        mix = df.groupby("color")["cantidad"].sum()
        mix_pct = (mix / mix.sum() * 100).round(1)

        # Ventas por tienda
        por_tienda = df.groupby("ubicacion")["cantidad"].sum().sort_values(ascending=False)

        # Últimos 3 meses vs promedio (tendencia)
        ultimos = mensual.tail(3)["cantidad"].mean()
        tendencia = "↑" if ultimos > prom_mensual * 1.1 else ("↓" if ultimos < prom_mensual * 0.9 else "→")

        print(f"\n{'━' * 90}")
        print(f"  {modelo}  →  {cfg['nuevo']}")
        print(f"{'━' * 90}")

        print(f"\n  📊 DATOS HISTÓRICOS")
        print(f"     Período: {df['fecha_dt'].min().strftime('%d/%m/%Y')} — {df['fecha_dt'].max().strftime('%d/%m/%Y')} ({len(mensual)} meses)")
        print(f"     Ventas totales: {df['cantidad'].sum():,.0f} u | Promedio/mes: {prom_mensual:.0f} u | Tendencia reciente: {tendencia}")
        print(f"     Estacionalidad ratio: {max(indices.values())/min(indices.values()):.1f}x (índice {min(indices.values()):.2f} — {max(indices.values()):.2f})")

        print(f"\n  📅 DEMANDA PROYECTADA POR MES (base estacional)")
        for d in demanda_6m:
            bar = "█" * int(d["u"] / max(x["u"] for x in demanda_6m) * 30)
            print(f"     {d['mes']:22s} {d['u']:5.0f} u  {bar}")
        print(f"     {'SUBTOTAL 6M':22s} {base_6m:5.0f} u")

        print(f"\n  ⚙️  FACTORES ESTRATÉGICOS (multiplicador ×{multiplicador:.3f})")
        print(f"     +55% Expansión red (Margarita 1.5× + Nueva tienda 1×)")
        print(f"     +10% Migración modelo nuevo")
        print(f"     +5%  Factor marketing")
        print(f"     +8%  Pedidos corporativos")
        print(f"     → Demanda ajustada: {ajustada:,.0f} u")
        print(f"     +20% Stock seguridad: {ss:,.0f} u")
        print(f"     = NECESIDAD BRUTA: {bruta:,.0f} u")

        print(f"\n  📦 INVENTARIO MODELO ACTUAL (NO aplicable al producto nuevo)")
        print(f"     Total viejo: {inv_total:,.0f} u (Tiendas: {inv_tiendas:,.0f} | Taller/bodega: {inv_taller:,.0f})")
        print(f"     ⚠️  Este inventario es del modelo que se DISCONTINÚA — no se descuenta de la compra nueva")

        print(f"\n  🎯 COMPRA RECOMENDADA PARA PRODUCTO NUEVO")
        print(f"     Compra bruta (recomendada):     {compra_bruta:>6,} u")
        print(f"     Esc. conservador (-10%):         {round(compra_bruta*0.9):>6,} u")
        print(f"     Esc. agresivo (+10%):            {round(compra_bruta*1.1):>6,} u")

        if cfg["colores"]:
            print(f"\n  🎨 DISTRIBUCIÓN POR COLOR (producto nuevo)")
            for color, pct in cfg["colores"].items():
                print(f"     {color}: {round(compra_bruta * pct):,} u ({pct*100:.0f}%)")
        else:
            print(f"\n  🎨 DISTRIBUCIÓN SUGERIDA POR COLOR (proxy mix ventas actual)")
            top = mix_pct.sort_values(ascending=False).head(4)
            for color, pct in top.items():
                print(f"     {color}: {round(compra_bruta * pct/100):,} u ({pct}%)")

        print(f"\n  🏪 TOP TIENDAS POR VENTAS (referencia para distribución)")
        for tienda, u in por_tienda.head(6).items():
            print(f"     {tienda}: {u:,.0f} u")

        resumen.append({
            "Modelo actual": modelo,
            "Producto NUEVO": cfg["nuevo"],
            "Listo compra": "SÍ" if cfg["listo"] else "En desarrollo",
            "Demanda base 6m": round(base_6m),
            "Demanda ajustada": round(ajustada),
            "Stock seguridad": round(ss),
            "COMPRA BRUTA": compra_bruta,
            "Conservador (-10%)": round(compra_bruta * 0.9),
            "Agresivo (+10%)": round(compra_bruta * 1.1),
            "Inv. viejo (info)": round(inv_total),
        })

    print(f"\n{'=' * 90}")
    print("TABLA RESUMEN — CANTIDADES PARA NEGOCIAR CON PROVEEDOR")
    print("=" * 90)
    df_r = pd.DataFrame(resumen)
    print(df_r.to_string(index=False))
    total = df_r["COMPRA BRUTA"].sum()
    print(f"\n  🎯 TOTAL CONSOLIDADO COMPRA: {total:,} unidades")
    print(f"     Rango B-C: {df_r['Conservador (-10%)'].sum():,} — {df_r['Agresivo (+10%)'].sum():,} u")
    print(f"\n  NOTA: Travel Bag 40L (new) está APROBADO y listo para ordenar.")
    print(f"        Moon bag y Drybag 30L (new) aún en desarrollo/muestras — validar antes de confirmar.")

    df_r.to_csv("/workspace/proyeccion_compra_bags_6m.csv", index=False)
    return df_r


if __name__ == "__main__":
    analizar()
