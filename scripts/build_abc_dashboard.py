#!/usr/bin/env python3
"""
Genera UN solo HTML autocontenido (JS + JSON embebido) para Matriz ABC.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_JSON = ROOT / "abc_dashboard_data.json"
TEMPLATE = ROOT / "abc_inventario_dashboard.html"
JS_PATH = ROOT / "abc_dashboard.js"
INJECT_MARKER = "<!--INJECT_APP-->"

# Nombre principal que debe abrir el usuario (un solo archivo)
OUTPUT_NAMES = (
    "Matriz_ABC_Inventario.html",
    "abc_inventario_completo.html",
    "abc_inventario_standalone.html",
)

MES_MAP = {
    "ENERO": 1,
    "FEBRERO": 2,
    "MARZO": 3,
    "ABRIL": 4,
    "MAYO": 5,
    "JUNIO": 6,
    "JULIO": 7,
    "AGOSTO": 8,
    "SEPTIEMBRE": 9,
    "OCTUBRE": 10,
    "NOVIEMBRE": 11,
    "DICIEMBRE": 12,
}

MES_LABEL = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

ABC_THRESHOLDS = {"A": 0.80, "B": 0.95}


def clean_str(val, default: str = "") -> str:
    if val is None:
        return default
    try:
        if pd.isna(val):
            return default
    except (TypeError, ValueError):
        pass
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return default
    s = str(val).strip()
    return s if s and s.lower() != "nan" else default


def sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0.0
        return obj
    try:
        if pd.isna(obj):
            return ""
    except (TypeError, ValueError):
        pass
    return obj


def load_sales() -> pd.DataFrame:
    path = DATA_DIR / "Ordenes_de_Ventas_Oct2025_COMPLETO.xlsx"
    df = pd.read_excel(path, sheet_name="VENTAS")
    df = df[df["SKU"].notna()].copy()
    df["SKU"] = df["SKU"].astype(str).str.strip()
    df["Mes"] = df["Mes"].astype(str).str.strip().str.upper()
    df["mnum"] = df["Mes"].map(MES_MAP)
    df["Año"] = df["Año"].astype(int)
    df["period"] = (
        df["Año"].astype(str)
        + "-"
        + df["mnum"].astype(int).astype(str).str.zfill(2)
    )
    df["tienda"] = df["tienda / ubicación"].fillna("SIN TIENDA").astype(str).str.strip()
    df["categoria"] = df["Categoría del producto"].fillna("Sin categoría").astype(str)
    df["producto"] = df["Producto"].fillna("").astype(str).str.strip()
    df["genero"] = df["GENERO"].fillna("").astype(str)
    df["color"] = df["COLOR"].fillna("").astype(str)
    df["talla"] = df["TALLA"].fillna("").astype(str)
    df["qty"] = pd.to_numeric(df["Cant. ordenada"], errors="coerce").fillna(0)
    df["revenue"] = pd.to_numeric(df["TOTAL ($)"], errors="coerce").fillna(0)
    df["cost"] = pd.to_numeric(df["COSTO ($) TOTAL"], errors="coerce").fillna(0)
    df["margin"] = df["revenue"] - df["cost"]
    return df


def load_inventory() -> pd.DataFrame:
    path = DATA_DIR / "INVENTARIO_TALLER_TIENDAS_COMPLETO.xlsx"
    df = pd.read_excel(path, sheet_name="Inventario")
    df = df[df["SKU"].notna()].copy()
    df["SKU"] = df["SKU"].astype(str).str.strip()
    df["ubicacion"] = df["Ubicación"].fillna("SIN UBICACIÓN").astype(str).str.strip()
    df["modelo"] = df["MODELO"].fillna("").astype(str).str.strip()
    df["qty"] = pd.to_numeric(df["Cantidad en inventario"], errors="coerce").fillna(0)
    return df


def load_p3_supplement() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None:
    """SKUs activos fuera de ABC (P3) — cruce SKU-GLOBAL."""
    path = DATA_DIR / "SKUs_Faltantes_ABC.xlsx"
    if not path.exists():
        return None
    resumen = pd.read_excel(path, sheet_name="Resumen por SKU")
    inv_detail = pd.read_excel(path, sheet_name="Detalle Inventario")
    sales_detail = pd.read_excel(path, sheet_name="Detalle Ventas por Fecha")
    for df in (resumen, inv_detail, sales_detail):
        if "SKU" in df.columns:
            df["SKU"] = df["SKU"].astype(str).str.strip()
    return resumen, inv_detail, sales_detail


def merge_p3_into_inventory(inv: pd.DataFrame, p3: tuple) -> pd.DataFrame:
    """Añade filas de inventario P3 que no están en el archivo principal."""
    resumen, inv_detail, _ = p3
    known = set(inv["SKU"].unique())
    extra_rows = []
    for _, r in inv_detail.iterrows():
        sku = clean_str(r["SKU"])
        if not sku or sku in known:
            continue
        info = resumen[resumen["SKU"] == sku]
        row = info.iloc[0] if len(info) else r
        extra_rows.append(
            {
                "Ubicación": clean_str(r.get("Almacen"), "P3"),
                "Producto": clean_str(row.get("Producto") or r.get("Producto"), sku),
                "SKU": sku,
                "MODELO": clean_str(row.get("Producto") or r.get("Producto"), sku),
                "GENERO": clean_str(row.get("GENERO"), ""),
                "COLOR": clean_str(row.get("COLOR"), ""),
                "TALLA": clean_str(row.get("TALLA"), ""),
                "Cantidad en inventario": float(r.get("Cantidad") or 0),
            }
        )
        known.add(sku)
    if not extra_rows:
        return inv
    extra = pd.DataFrame(extra_rows)
    merged = pd.concat([inv, extra], ignore_index=True)
    merged["ubicacion"] = merged["Ubicación"].fillna("SIN UBICACIÓN").astype(str).str.strip()
    merged["modelo"] = merged["MODELO"].fillna("").astype(str).str.strip()
    merged["qty"] = pd.to_numeric(
        merged["Cantidad en inventario"], errors="coerce"
    ).fillna(0)
    return merged


def build_indexes(
    sales: pd.DataFrame, inv: pd.DataFrame, p3: tuple | None = None
) -> dict:
    periods = sorted(sales["period"].unique())
    period_meta = []
    for p in periods:
        y, m = p.split("-")
        mi = int(m)
        period_meta.append(
            {
                "key": p,
                "year": int(y),
                "month": mi,
                "label": f"{MES_LABEL[mi]} {y}",
                "short": f"{MES_LABEL[mi][:3]} {y[-2:]}",
            }
        )

    stores = sorted(sales["tienda"].unique())
    categories = sorted(sales["categoria"].unique())
    skus = sorted(set(sales["SKU"].unique()) | set(inv["SKU"].unique()))

    sku_master = {}
    sales_info = (
        sales.groupby("SKU")
        .agg(
            producto=("producto", "first"),
            categoria=("categoria", "first"),
            genero=("genero", "first"),
            color=("color", "first"),
            talla=("talla", "first"),
        )
        .to_dict("index")
    )
    inv_model = inv.groupby("SKU")["modelo"].first().to_dict()
    inv_gen = inv.groupby("SKU")["GENERO"].first().to_dict() if "GENERO" in inv.columns else {}
    inv_col = inv.groupby("SKU")["COLOR"].first().to_dict() if "COLOR" in inv.columns else {}
    inv_tal = inv.groupby("SKU")["TALLA"].first().to_dict() if "TALLA" in inv.columns else {}

    p3_skus: set[str] = set()
    p3_meta: dict[str, dict] = {}
    if p3:
        resumen, _, _ = p3
        for _, r in resumen.iterrows():
            sku = clean_str(r["SKU"])
            if not sku:
                continue
            p3_skus.add(sku)
            p3_meta[sku] = {
                "producto": clean_str(r.get("Producto"), sku),
                "genero": clean_str(r.get("GENERO"), ""),
                "color": clean_str(r.get("COLOR"), ""),
                "talla": clean_str(r.get("TALLA"), ""),
                "modelo": clean_str(r.get("Producto"), sku),
                "en_ventas": "SI" in clean_str(r.get("En_Ventas"), "").upper(),
                "en_inventario": "SI" in clean_str(r.get("En_Inventario"), "").upper(),
            }

    for sku in skus:
        info = sales_info.get(sku, {})
        p3 = p3_meta.get(sku, {})
        sku_master[sku] = {
            "producto": clean_str(
                info.get("producto") or p3.get("producto") or inv_model.get(sku, sku),
                sku,
            ),
            "categoria": clean_str(info.get("categoria"), "Sin ventas / solo stock"),
            "genero": clean_str(
                info.get("genero") or p3.get("genero") or inv_gen.get(sku, "")
            ),
            "color": clean_str(
                info.get("color") or p3.get("color") or inv_col.get(sku, "")
            ),
            "talla": clean_str(
                info.get("talla") or p3.get("talla") or inv_tal.get(sku, "")
            ),
            "modelo": clean_str(
                inv_model.get(sku)
                or p3.get("modelo")
                or info.get("producto")
                or sku,
                sku,
            ),
            "p3": sku in p3_skus,
        }

    sku_idx = {s: i for i, s in enumerate(skus)}
    store_idx = {s: i for i, s in enumerate(stores)}
    cat_idx = {c: i for i, c in enumerate(categories)}
    period_idx = {p["key"]: i for i, p in enumerate(period_meta)}

    rows = []
    g = sales.groupby(
        ["period", "SKU", "tienda", "categoria"], as_index=False
    ).agg(qty=("qty", "sum"), revenue=("revenue", "sum"), cost=("cost", "sum"))
    g["margin"] = g["revenue"] - g["cost"]
    for _, r in g.iterrows():
        rows.append(
            [
                period_idx[r["period"]],
                sku_idx[r["SKU"]],
                store_idx[r["tienda"]],
                cat_idx[r["categoria"]],
                round(float(r["qty"]), 4),
                round(float(r["revenue"]), 4),
                round(float(r["cost"]), 4),
                round(float(r["margin"]), 4),
            ]
        )

    locations = sorted(inv["ubicacion"].unique())
    loc_idx = {l: i for i, l in enumerate(locations)}
    inv_rows = []
    inv_g = inv.groupby(["SKU", "ubicacion"], as_index=False)["qty"].sum()
    for _, r in inv_g.iterrows():
        if r["SKU"] not in sku_idx:
            continue
        inv_rows.append(
            [sku_idx[r["SKU"]], loc_idx[r["ubicacion"]], round(float(r["qty"]), 4)]
        )

    stats = {
        "lineas_ventas": int(len(sales)),
        "skus_unicos": len(skus),
        "periodos": len(periods),
        "rango": f"{period_meta[0]['label']} → {period_meta[-1]['label']}",
        "margen_neto_total": round(float(sales["margin"].sum()), 2),
        "p3_skus": len(p3_skus),
        "p3_integrados": len(p3_skus & set(skus)),
    }

    return {
        "meta": {
            "generated": pd.Timestamp.now().isoformat(),
            "metric": "margen_contribucion",
            "abc_thresholds": ABC_THRESHOLDS,
            "premisas": {
                "A": {"margen_pct": 80, "sku_pct_objetivo": 20},
                "B": {"margen_pct": 15, "sku_pct_objetivo": 30},
                "C": {"margen_pct": 5, "sku_pct_objetivo": 50},
            },
            "stats": stats,
        },
        "periods": period_meta,
        "stores": stores,
        "categories": categories,
        "locations": locations,
        "skus": skus,
        "skuMaster": sku_master,
        "salesRows": rows,
        "invRows": inv_rows,
        "p3Skus": sorted(p3_skus),
    }


BOOT_SCRIPT = """
<script>
(function(){
  function boot(){
    var errEl=document.getElementById('loadErr');
    try{
      var raw=document.getElementById('abc-embedded-data');
      if(!raw) throw new Error('Datos no embebidos — regenerá con build_abc_dashboard.py');
      var payload=JSON.parse(raw.textContent);
      if(typeof AbcDashboard==='undefined') throw new Error('Motor del dashboard no cargó (revisá bloqueo de scripts)');
      AbcDashboard.loadData(payload);
      if(errEl) errEl.style.display='none';
    }catch(e){
      console.error(e);
      if(errEl){ errEl.style.display='block'; errEl.textContent='Error al cargar: '+e.message; }
      var sub=document.getElementById('subtitle');
      if(sub) sub.textContent='No se pudo cargar la data.';
    }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
</script>
"""


def build_unified_html(template: str, js: str, data_json: str) -> str:
    if INJECT_MARKER not in template:
        raise RuntimeError(f"Falta marcador {INJECT_MARKER} en plantilla")
    block = (
        f"<script>\n{js}\n</script>\n"
        f'<script type="application/json" id="abc-embedded-data">\n{data_json}\n</script>\n'
        f"{BOOT_SCRIPT.strip()}\n"
    )
    return template.replace(INJECT_MARKER, block)


def main() -> None:
    sales = load_sales()
    inv = load_inventory()
    p3 = load_p3_supplement()
    if p3:
        inv = merge_p3_into_inventory(inv, p3)
    payload = build_indexes(sales, inv, p3)
    payload = sanitize_for_json(payload)
    data_json = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    OUT_JSON.write_text(data_json, encoding="utf-8")

    template = TEMPLATE.read_text(encoding="utf-8")
    js = JS_PATH.read_text(encoding="utf-8")
    unified = build_unified_html(template, js, data_json)

    for name in OUTPUT_NAMES:
        out = ROOT / name
        out.write_text(unified, encoding="utf-8")
        print(f"OK → {out} ({out.stat().st_size / (1024*1024):.2f} MB)")

    print(json.dumps(payload["meta"]["stats"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
