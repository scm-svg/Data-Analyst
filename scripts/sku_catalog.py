"""Build SKU → product lookups from workspace data sources."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

CATALOG_PATH = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/"
    "Coopia_de_Cuadro_-_SKU_Productos__Global__cfa8.xlsx"
)
URBAN_COTTON_PATH = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/urban_cotton_ACTX1_923d.xlsx"
)
QUANTS_PATHS = (
    Path(
        "/home/ubuntu/.cursor/projects/workspace/uploads/"
        "Quants__stock.quant___1__5059.xlsx"
    ),
    Path(
        "/home/ubuntu/.cursor/projects/workspace/uploads/"
        "Quants__stock.quant___2__3ab0.xlsx"
    ),
    Path(
        "/home/ubuntu/.cursor/projects/workspace/uploads/"
        "Quants__stock.quant___3__7680.xlsx"
    ),
)

# Odoo labels confirmed outside quant exports (or not yet in a file).
ODOO_KNOWN_LABELS: dict[str, str] = {
    "MLMMJDA66TS": "MOTION LOOP MAFE DAMA (Verde Militar, S)",
}

CATALOG_SKU_SHEETS = (
    "MANUFACTURADO",
    "CLASFSKUSYSGRIETA",
    "EQUIPAMIENTO",
    "EQUIPAMIENTO - ROPA",
    "SUMINISTROS",
    "MATERIA PRIMA",
)

R2_COLOR_CODES = {
    "43": "Negro",
    "66": "Verde Militar",
    "70": "Vinotinto",
    "12": "Azul Marino",
    "13": "Azul Rey",
    "123": "Verde Manzana",
}


def norm_sku(text) -> str:
    if pd.isna(text):
        return ""
    return str(text).strip().upper().replace(" ", "")


def parse_odoo_product_label(text: str) -> tuple[str | None, str | None]:
    """Parse `[SKU] Product description` from Odoo quant export."""
    if pd.isna(text):
        return None, None
    s = str(text).strip()
    m = re.match(r"^\[([^\]]+)\]\s*(.*)$", s)
    if not m:
        return None, s
    return norm_sku(m.group(1)), m.group(2).strip()


def odoo_label_to_producto(display: str) -> str:
    """Catalog-style name: line without color/size variant."""
    base = display.split("(", 1)[0].strip()
    return re.sub(r"\s+", " ", base)


def decode_r2_from_sku(raw_sku: str) -> tuple[str | None, str | None]:
    """Infer R2 product from SSR2VIU / SRR2VIU SKU when absent from quants."""
    s = norm_sku(raw_sku)
    m = re.match(r"^(SSR2VIU|SRR2VIU)(\d+)(T(.+))$", s)
    if not m:
        return None, None
    prefix, color_code, _, size = m.group(1), m.group(2), m.group(3), m.group(4)
    color = R2_COLOR_CODES.get(color_code)
    if not color:
        return None, None
    if prefix.startswith("SSR"):
        display = f'R2 SPORT  5" ({color}, {size})'
    else:
        display = f'R2 RUNNING 3,5" ({color}, {size})'
    return odoo_label_to_producto(display), display


def normalize_sku_for_catalog(raw_sku: str) -> list[tuple[str, str]]:
    """Catalog-only fallbacks (not R2 / Odoo)."""
    s = norm_sku(raw_sku)
    if not s:
        return []

    candidates: list[tuple[str, str]] = [(s, "exact")]

    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for c, reason in candidates:
        if c and c not in seen:
            seen.add(c)
            out.append((c, reason))
    return out


def load_quants_index() -> pd.DataFrame:
    rows: list[dict] = []
    for path in QUANTS_PATHS:
        if not path.exists():
            continue
        df = pd.read_excel(path, sheet_name=0)
        col = "Producto" if "Producto" in df.columns else None
        if not col:
            continue
        for _, r in df.iterrows():
            sku, display = parse_odoo_product_label(r.get(col))
            if not sku or not display:
                continue
            rows.append(
                {
                    "SKU": sku,
                    "PRODUCTO": odoo_label_to_producto(display),
                    "PRODUCTO_ODOO": display,
                    "FUENTE": f"quants:{path.name}",
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=["SKU", "PRODUCTO", "PRODUCTO_ODOO", "FUENTE"]
        )

    idx = pd.DataFrame(rows)
    # Later quant files win on duplicate SKU (more recent export).
    return idx.drop_duplicates(subset=["SKU"], keep="last").reset_index(drop=True)


def load_sku_index() -> pd.DataFrame:
    rows: list[dict] = []

    if CATALOG_PATH.exists():
        for sheet in CATALOG_SKU_SHEETS:
            df = pd.read_excel(CATALOG_PATH, sheet_name=sheet)
            if "SKU" not in df.columns:
                continue
            for _, r in df.iterrows():
                sku = norm_sku(r.get("SKU"))
                if not sku:
                    continue
                producto = r.get("PRODUCTO")
                if pd.isna(producto) and "DESCRIPCIÓN" in df.columns:
                    producto = r.get("DESCRIPCIÓN")
                if pd.isna(producto):
                    continue
                rows.append(
                    {
                        "SKU": sku,
                        "PRODUCTO": str(producto).strip(),
                        "FUENTE": f"global:{sheet}",
                    }
                )

    if URBAN_COTTON_PATH.exists():
        uc = pd.read_excel(URBAN_COTTON_PATH, sheet_name="BASE DATOS URBAN COTTON")
        for _, r in uc.iterrows():
            sku = norm_sku(r.get("SKU"))
            prod = r.get("PRODUCTO")
            if sku and pd.notna(prod):
                rows.append(
                    {
                        "SKU": sku,
                        "PRODUCTO": str(prod).strip(),
                        "FUENTE": "urban_cotton:ACTX1",
                    }
                )

    if not rows:
        return pd.DataFrame(columns=["SKU", "PRODUCTO", "FUENTE"])

    idx = pd.DataFrame(rows)
    priority = {
        "global:MANUFACTURADO": 0,
        "global:CLASFSKUSYSGRIETA": 1,
        "urban_cotton:ACTX1": 2,
    }

    def pri(src: str) -> int:
        for key, val in priority.items():
            if src.startswith(key):
                return val
        return 5

    idx["_pri"] = idx["FUENTE"].map(pri)
    idx = idx.sort_values(["SKU", "_pri"]).drop_duplicates(subset=["SKU"], keep="first")
    return idx.drop(columns=["_pri"]).reset_index(drop=True)


def lookup_product(
    raw_sku: str,
    catalog_index: pd.DataFrame,
    quants_index: pd.DataFrame | None = None,
) -> tuple[str | None, str | None, str | None, str | None]:
    """
    Returns: producto, sku_used, reason, producto_odoo (full Odoo label if known)
    """
    sku = norm_sku(raw_sku)
    if not sku:
        return None, None, "not_found", None

    if quants_index is not None and not quants_index.empty:
        hit = quants_index[quants_index["SKU"] == sku]
        if not hit.empty:
            row = hit.iloc[0]
            return (
                row["PRODUCTO"],
                sku,
                "ok_quants_odoo",
                row.get("PRODUCTO_ODOO"),
            )

    if sku in ODOO_KNOWN_LABELS:
        display = ODOO_KNOWN_LABELS[sku]
        return odoo_label_to_producto(display), sku, "ok_odoo_known", display

    if sku.startswith("SSR2VIU") or sku.startswith("SRR2VIU"):
        prod, display = decode_r2_from_sku(sku)
        if prod:
            return prod, sku, "ok_r2_inferred", display

    sku_map = dict(zip(catalog_index["SKU"], catalog_index["PRODUCTO"]))
    fuente_map = dict(zip(catalog_index["SKU"], catalog_index["FUENTE"]))

    for candidate, reason in normalize_sku_for_catalog(raw_sku):
        prod = sku_map.get(candidate)
        if prod:
            fuente = fuente_map.get(candidate, "catalog")
            tag = "ok" if reason == "exact" and candidate == sku else f"ok_catalog:{reason}"
            return prod, candidate, tag, None

    return None, None, "not_found", None
