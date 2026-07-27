"""SHORT SPORT R1 — authoritative SKUs from Quants (stock.quant) (6)."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from sku_catalog import norm_sku

R1_QUANTS6_PATH = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/Quants__stock.quant___6__9b8c.xlsx"
)

# Catalog codes that must never be used for R1 (not in Odoo R1 quants).
INVALID_R1_SKU_PREFIXES = ("SHOSPBFCA", "SHOSPBFDA")


def norm_color_r1(text) -> str:
    if pd.isna(text):
        return ""
    c = str(text).strip().upper()
    c = c.replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
    aliases = {
        "G OSCURO": "GRIS OSCURO",
        "GRIS OSCURO": "GRIS OSCURO",
        "GRIS C": "GRIS",
    }
    return aliases.get(c, c)


def norm_talla_r1(text) -> str:
    if pd.isna(text):
        return ""
    t = str(text).strip().upper()
    if t == "XXL":
        return "2XL"
    if t.endswith(".0"):
        t = t[:-2]
    return t


def infer_r1_genero(fallback_name, sku: str) -> str | None:
    fb = str(fallback_name or "").upper()
    if " CAB" in fb or fb.endswith(" CAB"):
        return "CAB"
    if " DAMA" in fb:
        return "DAMA"
    sk = norm_sku(sku)
    if sk.startswith("SHUNTCA") or sk.startswith("SHONTCA"):
        return "CAB"
    if sk.startswith("SHUNTDA") or sk.startswith("SHONTDA"):
        return "DAMA"
    return None


def _parse_r1_attrs(product_id: str) -> tuple[str | None, str | None, str | None]:
    m = re.search(
        r"SHORT SPORT R1 (CAB|DAMA)\s*\(([^,]+),\s*([^)]+)\)",
        product_id,
        re.IGNORECASE,
    )
    if not m:
        return None, None, None
    gen = m.group(1).upper()
    color = m.group(2).strip().upper()
    talla = m.group(3).strip().upper()
    return gen, color, talla


def load_r1_quants6() -> tuple[set[str], dict[tuple[str, str, str], tuple[str, str]], dict[str, str]]:
    """
    Returns:
      - set of valid R1 SKUs
      - index (CAB|DAMA, color, talla) -> (sku, full product_id)
      - sku -> full product_id
    """
    if not R1_QUANTS6_PATH.exists():
        return set(), {}, {}

    df = pd.read_excel(R1_QUANTS6_PATH, sheet_name=0)
    skus: set[str] = set()
    index: dict[tuple[str, str, str], tuple[str, str]] = {}
    pid_map: dict[str, str] = {}

    for val in df["Producto"].dropna():
        s = str(val).strip()
        m = re.match(r"^\[([^\]]+)\]\s*(.*)$", s)
        if not m:
            continue
        sku = norm_sku(m.group(1))
        pid = s
        skus.add(sku)
        pid_map[sku] = pid
        gen, color, talla = _parse_r1_attrs(pid)
        if gen and color and talla:
            index[(gen, color, talla)] = (sku, pid)

    return skus, index, pid_map


def is_invalid_r1_catalog_sku(sku: str) -> bool:
    sk = norm_sku(sku)
    return sk.startswith(INVALID_R1_SKU_PREFIXES)


def resolve_r1_sku(
    sku: str,
    *,
    tipo_producto: str | None = None,
    talla=None,
    color=None,
    fallback_name=None,
    r1_skus: set[str],
    r1_index: dict[tuple[str, str, str], tuple[str, str]],
) -> tuple[str, str | None]:
    """Return (sku, remapped_product_id or None)."""
    sk = norm_sku(sku)
    tipo = str(tipo_producto or "").strip().upper()
    is_r1 = (
        tipo == "R1"
        or is_invalid_r1_catalog_sku(sk)
        or "SHORT SPORT R1" in str(fallback_name or "").upper()
    )
    if not is_r1:
        return sk, None

    if sk in r1_skus and not is_invalid_r1_catalog_sku(sk):
        return sk, None

    gen = infer_r1_genero(fallback_name, sk)
    c = norm_color_r1(color)
    t = norm_talla_r1(talla)
    if not gen or not c or not t:
        return sk, None

    hit = r1_index.get((gen, c, t))
    if not hit:
        return sk, None
    new_sku, pid = hit
    return new_sku, pid
