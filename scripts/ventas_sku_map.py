"""SKU → Odoo product_id from sales report (authoritative for live Odoo labels)."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from sku_catalog import norm_sku

VENTAS_PATH = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/"
    "Reporte_ventas_UNIFICADO_COMPLETO_eb79.xlsx"
)

# Wrong legacy / catalog codes → correct Odoo SKU (same variant intent).
SKU_REMAPS: dict[str, str] = {
    "CLASPCA16TS": "CLAMECA16TS",
    "CLMSUCA152TM": "MLCMJCA66TM",
}

TALLA_TOKENS = frozenset({"XS", "S", "M", "L", "XL", "2XL", "XXL", "3XL"})


def apply_sku_remap(raw_sku: str) -> tuple[str, str | None]:
    sk = norm_sku(raw_sku)
    target = SKU_REMAPS.get(sk)
    if target:
        return norm_sku(target), sk
    return sk, None


def _parse_bracket_product_id(text: str) -> tuple[str | None, str | None]:
    if pd.isna(text):
        return None, None
    s = str(text).strip()
    m = re.match(r"^\[([^\]]+)\]\s*(.*)$", s)
    if not m:
        return None, None
    return norm_sku(m.group(1)), s


def load_ventas_product_id_map() -> dict[str, str]:
    """One canonical `[SKU] …` label per SKU from Ventas (last row wins)."""
    if not VENTAS_PATH.exists():
        return {}

    df = pd.read_excel(
        VENTAS_PATH,
        sheet_name="Ventas",
        usecols=["SKU", "Variante del producto"],
    )
    df = df.dropna(subset=["SKU", "Variante del producto"])
    out: dict[str, str] = {}
    for _, row in df.iterrows():
        sku = norm_sku(row["SKU"])
        variant = str(row["Variante del producto"]).strip()
        if not sku or not variant.startswith("["):
            continue
        bracket_sku, _ = _parse_bracket_product_id(variant)
        if bracket_sku and bracket_sku != sku:
            continue
        out[sku] = variant
    return out


def _parse_r1_variant_pair(gen: str, part_a: str, part_b: str) -> tuple[str, str] | None:
    """Return (color_upper, talla_upper) from parentheses content."""
    a = part_a.strip().upper()
    b = part_b.strip().upper()
    a_talla = a in TALLA_TOKENS or a.replace(".", "").isdigit()
    b_talla = b in TALLA_TOKENS or b.replace(".", "").isdigit()
    if a_talla and not b_talla:
        talla, color_raw = a, b
    elif b_talla and not a_talla:
        color_raw, talla = a, b
    else:
        color_raw, talla = a, b
    color = re.sub(r"\s*-\s*\d+\s*$", "", color_raw).strip()
    if talla == "XXL":
        talla = "2XL"
    return color, talla


def augment_r1_from_ventas(
    skus: set[str],
    index: dict[tuple[str, str, str], tuple[str, str]],
    pid_map: dict[str, str],
) -> int:
    """Add SHORT SPORT R1 rows from ventas missing in Quants (6). Returns count added."""
    ventas = load_ventas_product_id_map()
    added = 0
    pattern = re.compile(
        r"SHORT SPORT R1 (CAB|DAMA)\s*\(([^,]+),\s*([^)]+)\)",
        re.IGNORECASE,
    )
    for sku, pid in ventas.items():
        if not sku.startswith(("SHUNTCA", "SHUNTDA", "SHONTCA", "SHONTDA")):
            continue
        if "SHORT SPORT R1" not in pid.upper():
            continue
        m = pattern.search(pid)
        if not m:
            continue
        gen = m.group(1).upper()
        parsed = _parse_r1_variant_pair(gen, m.group(2), m.group(3))
        if not parsed:
            continue
        color, talla = parsed
        key = (gen, color, talla)
        if key in index and index[key][0] == sku:
            continue
        skus.add(sku)
        pid_map[sku] = pid
        if key not in index:
            index[key] = (sku, pid)
            added += 1
    return added


def validate_product_ids(
    df: pd.DataFrame,
    ventas_map: dict[str, str],
) -> pd.DataFrame:
    """Rows where product_id disagrees with ventas or bracket SKU mismatch."""
    rows: list[dict] = []
    for _, r in df.iterrows():
        sku = norm_sku(r.get("SKU"))
        pid = str(r.get("product_id") or "").strip()
        if not sku or not pid:
            continue
        bracket = re.match(r"^\[([^\]]+)\]", pid)
        bracket_sku = norm_sku(bracket.group(1)) if bracket else ""
        issues: list[str] = []
        if bracket_sku and bracket_sku != sku:
            issues.append("bracket_sku_mismatch")
        ventas_pid = ventas_map.get(sku)
        if ventas_pid and ventas_pid != pid:
            issues.append("differs_from_ventas")
        if issues:
            rows.append(
                {
                    "SKU": sku,
                    "product_id_actual": pid,
                    "product_id_ventas": ventas_pid,
                    "issues": ",".join(issues),
                    "inventory_quantity": r.get("inventory_quantity"),
                }
            )
    return pd.DataFrame(rows)


def audit_ventas_coverage(
    enriched: pd.DataFrame,
    ventas_map: dict[str, str],
) -> pd.DataFrame:
    """All SKUs in ventas that appear in the load, with label comparison."""
    tmp = enriched[enriched["product_id"].notna()].copy()
    tmp = tmp.drop_duplicates(subset=["SKU"], keep="first")
    rows: list[dict] = []
    for _, r in tmp.iterrows():
        sku = norm_sku(r["SKU"])
        ventas_pid = ventas_map.get(sku)
        if not ventas_pid:
            continue
        pid = str(r["product_id"]).strip()
        if pid != ventas_pid:
            rows.append(
                {
                    "SKU": sku,
                    "product_id_carga": pid,
                    "product_id_ventas": ventas_pid,
                    "source": r.get("source"),
                    "product_id_method": r.get("product_id_method"),
                }
            )
    return pd.DataFrame(rows)
