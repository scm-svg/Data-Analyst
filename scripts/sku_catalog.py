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

# Sheets with product/SKU rows in the global workbook.
CATALOG_SKU_SHEETS = (
    "MANUFACTURADO",
    "CLASFSKUSYSGRIETA",
    "EQUIPAMIENTO",
    "EQUIPAMIENTO - ROPA",
    "SUMINISTROS",
    "MATERIA PRIMA",
)


def norm_sku(text) -> str:
    if pd.isna(text):
        return ""
    return str(text).strip().upper().replace(" ", "")


def normalize_sku_for_lookup(raw_sku: str) -> list[tuple[str, str]]:
    """Return candidate catalog SKUs to try, with reason tags."""
    s = norm_sku(raw_sku)
    if not s:
        return []

    candidates: list[tuple[str, str]] = [(s, "exact")]

    fixed = s
    if "SSR2VIU" in fixed or "SRR2VIU" in fixed:
        fixed = fixed.replace("SSR2VIU", "SERVIDA").replace("SRR2VIU", "SERVIDA")
        candidates.append((fixed, "alias_servida"))

    if fixed.startswith("MLMMJDA"):
        fixed2 = fixed.replace("MLMMJDA", "MILMIDA", 1)
        candidates.append((fixed2, "alias_mila"))

    if "123T" in fixed:
        candidates.append((fixed.replace("123T", "12T", 1), "color_123_to_12"))

    # Entrada almacén truncó "123" como "13" en Serenity (p. ej. SRR2VIU13TS).
    m = re.match(r"^(SERVIDA)13(T.+)$", fixed)
    if m:
        candidates.append((f"{m.group(1)}12{m.group(2)}", "color_13_to_12"))

    m2 = re.match(r"^(SRR2VIU|SSR2VIU)13(T.+)$", s)
    if m2:
        expanded = s.replace("13T", "123T", 1)
        for c, reason in normalize_sku_for_lookup(expanded):
            if c not in {x[0] for x in candidates}:
                candidates.append((c, f"expand_13_to_123:{reason}"))

    # De-dupe preserving order
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for c, reason in candidates:
        if c and c not in seen:
            seen.add(c)
            out.append((c, reason))
    return out


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
    # Prefer MANUFACTURADO / CLASFSKUSYSGRIETA over duplicates in other sheets.
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


def lookup_product(raw_sku: str, index: pd.DataFrame) -> tuple[str | None, str | None, str | None]:
    sku_map = dict(zip(index["SKU"], index["PRODUCTO"]))
    fuente_map = dict(zip(index["SKU"], index["FUENTE"]))

    for candidate, reason in normalize_sku_for_lookup(raw_sku):
        prod = sku_map.get(candidate)
        if prod:
            return prod, candidate, reason
    return None, None, "not_found"
