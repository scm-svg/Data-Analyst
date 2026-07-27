#!/usr/bin/env python3
"""Match SKUs from Cuadro Global catalog onto LISTA POR AJUSTE rows."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

ADJ_PATH = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/por_ajuste_sku_darle_forma_6918.xlsx"
)
CATALOG_PATH = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/"
    "Coopia_de_Cuadro_-_SKU_Productos__Global__cfa8.xlsx"
)
URBAN_COTTON_PATH = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/urban_cotton_ACTX1_923d.xlsx"
)
OUT_PATH = Path("/workspace/output/por_ajuste_sku_con_sku.xlsx")


def norm(text) -> str:
    if pd.isna(text):
        return ""
    s = str(text).strip().upper()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^A-Z0-9 ,./-]", "", s)
    return s.strip()


def norm_color(text) -> str:
    n = norm(text)
    aliases = {
        "G OSCURO": "GRIS OSCURO",
        "GRIS C": "GRIS CLARO",
        "ROSADO P": "ROSADO PASTEL",
        "LAVANDA": "AZUL LAVANDA",
        "PURPURA": "PURPURA",
        "VINOTINTO": "VINOTINTO",
    }
    return aliases.get(n, n)


def norm_genero(text) -> str:
    g = norm(text)
    if g in ("CABALLERO", "CAB"):
        return "CAB"
    if g == "KIDS":
        return "KIDS"
    return "DAMA"


def norm_talla(text) -> str:
    if pd.isna(text):
        return ""
    t = str(text).strip().upper()
    if t == "XXL":
        return "2XL"
    if t.endswith(".0"):
        t = t[:-2]
    return t


ESTAMPADO_COLORS = {
    "SAL",
    "SOMBRERO",
    "PLAYUELA",
    "TUCUPIDO",
    "ATLANTICO",
    "BOGA",
    "CARITE",
    "CRASQUI",
    "DORADO",
    "FRAILE",
    "FRANCISQUI",
    "HONEY",
    "MADRISQUI",
    "MAKO",
    "MAREA",
    "NAVY",
    "PACIFICO",
    "PAINT",
    "RAYA",
    "ROYAL",
}


def product_candidates(raw_product: str, genero: str, color: str) -> list[str]:
    p = norm(raw_product)
    g = norm_genero(genero)
    c = norm_color(color)

    if p == "SHORT PLAYA" and c in ESTAMPADO_COLORS:
        return ["SHORT PLAYA ESTAMPADO"]

    explicit: dict[str, list[str]] = {
        "BIO MOVE DOMINI": ["DOMINIC BIO MOVE CAB", "DOMINIC"],
        "DOMINIC BIO MOVE": ["DOMINIC BIO MOVE CAB", "DOMINIC"],
        "EXPLOR SHORT": ["EXPLORE SHORT", "EXPLORE SHORT "],
        "MIKA": ["MIKA SPORT LITE"],
        "NOAH": ["NOAH SPORT LITE"],
        "MAYA": ["MAYA SPORT LITE"],
        "GEO MAYA": ["GEO MAYA"],
        "CLASICA": ["CLASICA"],
        "CLASICA SPORT": ["CLASICA SPORT LISO", "CLASICA SPORT MESH"],
        "MOTION LOOP CLASICA": ["MOTION CLASICA"],
        "DAILY 3.0": ["DAILY CLASICA 3.0"],
        "R1": [],  # resolved via r1_quants6 in match_row, not catalog SHOSPBFCA*
        "CROP TEE BASIC LINE": ["BASIC LINE CROP TEE"],
        "BASIC LINE CROP": ["BASIC LINE CROP TEE", "BASIC LINE CROP TEE TEENS"],
        "BASIC LINE OVERSIZED": [
            "BASIC LINE OVERSIZED CAB" if g == "CAB" else "BASIC LINE OVERSIZED",
            "BASIC LINE OVERSIZED",
        ],
        "SHORT SUBLIMADO": ["SHORT PLAYA ESTAMPADO"],
        "MIA": ["MIA"],
        "ADVANCE MAFE": ["ADVANCE MAFE"],
    }

    if p in explicit:
        return explicit[p]

    # Default: use cleaned name; matcher also tries normalized equality on catalog.
    return [p]


def load_catalog() -> pd.DataFrame:
    mfg = pd.read_excel(CATALOG_PATH, sheet_name="MANUFACTURADO")
    colors = pd.read_excel(CATALOG_PATH, sheet_name="COLORES")
    color_map = {norm(c): str(c).strip().upper() for c in colors["COLORES"]}

    mfg = mfg.copy()
    mfg["_prod_norm"] = mfg["PRODUCTO"].map(norm)
    mfg["_gen_norm"] = mfg["GÉNERO"].map(norm_genero)
    mfg["_color_norm"] = mfg["COLORES"].map(lambda x: norm_color(str(x).upper()))
    mfg["_talla_norm"] = mfg["TALLA"].map(norm_talla)
    mfg["_color_canonical"] = mfg["COLORES"].map(
        lambda x: color_map.get(norm(x), norm_color(str(x).upper()))
    )
    return mfg


def load_urban_cotton_lookup() -> pd.DataFrame | None:
    if not URBAN_COTTON_PATH.exists():
        return None
    uc = pd.read_excel(URBAN_COTTON_PATH, sheet_name="BASE DATOS URBAN COTTON")
    uc = uc.dropna(subset=["SKU", "GENERO", "TALLA", "COLOR"])
    uc = uc.copy()
    uc["_gen_norm"] = uc["GENERO"].map(norm_genero)
    uc["_talla_norm"] = uc["TALLA"].map(norm_talla)
    uc["_color_norm"] = uc["COLOR"].map(norm_color)
    grouped = (
        uc.groupby(["_gen_norm", "_talla_norm", "_color_norm", "PRODUCTO", "SKU"], dropna=False)
        .size()
        .reset_index(name="_n")
    )
    idx = grouped.groupby(["_gen_norm", "_talla_norm", "_color_norm"])["_n"].idxmax()
    return grouped.loc[idx].reset_index(drop=True)


def match_urban_cotton(
    row, lookup: pd.DataFrame | None
) -> tuple[str | None, str | None, str]:
    if lookup is None or norm(row["Tipo de Producto"]) != "URBAN COTTON":
        return None, None, "product_not_found"

    genero = norm_genero(row["GENERO"])
    talla = norm_talla(row["Talla"])
    color_w = norm_color(row["color"])

    hits = lookup[
        (lookup["_gen_norm"] == genero)
        & (lookup["_talla_norm"] == talla)
        & (lookup["_color_norm"] == color_w)
    ]
    if hits.empty and len(color_w) >= 4:
        hits = lookup[
            (lookup["_gen_norm"] == genero)
            & (lookup["_talla_norm"] == talla)
            & (lookup["_color_norm"].str.contains(re.escape(color_w[:4]), na=False))
        ]

    if hits.empty:
        return None, None, "urban_cotton_not_found"

    best = hits.iloc[0]
    return str(best["SKU"]).strip(), str(best["PRODUCTO"]).strip(), "ok_urban_cotton"


def resolve_color_wanted(wanted: str, catalog_colors: pd.Series) -> str:
    w = norm_color(wanted)
    uniq = catalog_colors.dropna().unique().tolist()
    norm_to_orig = {norm_color(c): norm(c) for c in uniq}
    if w in norm_to_orig:
        return norm_to_orig[w]
    for c in uniq:
        cn = norm(c)
        if w in cn or cn in w:
            return cn
    return w


def match_row(
    row,
    catalog: pd.DataFrame,
    urban_lookup: pd.DataFrame | None = None,
) -> tuple[str | None, str | None, str]:
    product_raw = row["Tipo de Producto"]
    if pd.isna(product_raw) or norm(product_raw) in ("", "TOTAL GENERAL"):
        return None, None, "empty"

    genero = norm_genero(row["GENERO"])
    talla = norm_talla(row["Talla"])
    color_w = norm_color(row["color"])

    if norm(product_raw) == "URBAN COTTON":
        sku, prod, st = match_urban_cotton(row, urban_lookup)
        if sku:
            return sku, prod, st
        if st == "urban_cotton_not_found":
            return None, None, st

    if norm(product_raw) == "R1":
        from r1_quants6 import infer_r1_genero, load_r1_quants6, norm_color_r1, norm_talla_r1

        r1_skus, r1_index, _r1_pid = load_r1_quants6()
        gen = infer_r1_genero(f"SHORT SPORT R1 {'CAB' if genero == 'CAB' else 'DAMA'}", "")
        if not gen:
            gen = "CAB" if genero == "CAB" else "DAMA"
        key = (gen, norm_color_r1(row["color"]), norm_talla_r1(row["Talla"]))
        hit = r1_index.get(key)
        if hit:
            sku_key, _pid = hit
            return sku_key, "SHORT SPORT R1", "ok_r1_quants6"
        return None, "SHORT SPORT R1", "r1_not_in_quants6"

    candidates = product_candidates(str(product_raw), str(row["GENERO"]), str(row["color"]))
    candidate_norms = [norm(c) for c in candidates]

    last_reason = "product_not_found"
    last_prod = None

    for cand_norm in candidate_norms:
        pool = catalog[catalog["_prod_norm"] == cand_norm]
        if pool.empty:
            continue

        pool = pool[pool["_gen_norm"] == genero]
        if pool.empty:
            last_reason = "genero_not_found"
            last_prod = pool.iloc[0]["PRODUCTO"] if not pool.empty else None
            continue

        pool = pool[pool["_talla_norm"] == talla]
        if pool.empty:
            last_reason = "talla_not_found"
            last_prod = catalog[catalog["_prod_norm"] == cand_norm].iloc[0]["PRODUCTO"]
            continue

        color_resolved = resolve_color_wanted(color_w, pool["COLORES"])
        color_pool = pool[pool["_color_norm"] == norm_color(color_resolved)]
        if color_pool.empty:
            color_pool = pool[pool["_color_norm"] == color_w]
        if color_pool.empty and len(color_w) >= 4:
            color_pool = pool[
                pool["_color_norm"].str.contains(re.escape(color_w[:4]), na=False)
            ]

        if color_pool.empty:
            last_reason = "color_not_found"
            last_prod = pool.iloc[0]["PRODUCTO"]
            continue

        if len(color_pool) > 1:
            color_pool = color_pool.sort_values(by="_prod_norm")

        sku = color_pool.iloc[0]["SKU"]
        prod = color_pool.iloc[0]["PRODUCTO"]
        return str(sku).strip(), str(prod).strip(), "ok"

    pool = catalog[catalog["_prod_norm"] == norm(product_raw)]
    if pool.empty:
        return None, last_prod, last_reason

    return None, last_prod, last_reason


def main() -> None:
    raw = pd.read_excel(ADJ_PATH, sheet_name=0, header=None)
    catalog = load_catalog()
    urban_lookup = load_urban_cotton_lookup()

    header_row = 2
    data = raw.iloc[header_row + 1 :].copy()
    data.columns = raw.iloc[header_row].tolist()

    skus: list[str | None] = []
    prod_cat: list[str | None] = []
    status: list[str] = []

    for _, row in data.iterrows():
        sku, prod, st = match_row(row, catalog, urban_lookup)
        skus.append(sku)
        prod_cat.append(prod)
        status.append(st)

    data["SKU"] = skus
    data["PRODUCTO CATALOGO"] = prod_cat
    data["MATCH_STATUS"] = status

    valid = data[data["Tipo de Producto"].notna() & (data["Tipo de Producto"] != "Total General")]

    export = valid[
        [
            "Tipo de Producto",
            "Talla",
            "GENERO",
            "color",
            "SKU",
            "Cantidad",
            "FECHA",
            "PRODUCTO CATALOGO",
            "MATCH_STATUS",
        ]
    ].copy()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
        export.to_excel(
            writer,
            sheet_name="LISTA POR AJUSTE produccion ",
            index=False,
            startrow=2,
        )
        ws = writer.sheets["LISTA POR AJUSTE produccion "]
        ws["A1"] = "REPORTE DE  PIEZAS SIN ORDEN DE PRODUCCION"

        pendientes = valid[~valid["MATCH_STATUS"].isin(["ok", "ok_urban_cotton"])].copy()
        pendientes.to_excel(writer, sheet_name="PENDIENTES REVISION", index=False)

    ok = valid["MATCH_STATUS"].isin(["ok", "ok_urban_cotton"]).sum()
    print(f"Output: {OUT_PATH}")
    print(f"Rows with data: {len(valid)}")
    print(f"Matched OK: {ok}")
    print(f"Unmatched: {len(valid) - ok}")
    print("\nUnmatched breakdown:")
    pending = valid[~valid["MATCH_STATUS"].isin(["ok", "ok_urban_cotton"])]
    print(pending.groupby("MATCH_STATUS").size().to_string())
    print("\nSample unmatched:")
    bad = pending[["Tipo de Producto", "Talla", "GENERO", "color", "MATCH_STATUS"]]
    print(bad.head(25).to_string())


if __name__ == "__main__":
    main()
