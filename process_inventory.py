"""Parse inventory/stock product rows into SKU, model, gender, color, size."""
import re
from collections import Counter

import pandas as pd

SIZES = {"XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL", "P"}
SIZE_LABELS = {"PEQUEÑO", "MEDIANO", "GRANDE", "PEQUENO"}
KIDS_SIZES = {str(n) for n in range(1, 20)}
ALL_SIZES = SIZES | KIDS_SIZES | SIZE_LABELS

COLOR_ALIASES = {
    "Black": "Negro",
    "WHITE": "Blanco",
    "NEGRO": "Negro",
    "BLANCO": "Blanco",
    "VERDE MILITAR": "Verde Militar",
    "AGUAMARINA": "Aguamarina",
}


def _is_size(token: str) -> bool:
    token = str(token).strip()
    if token.upper() in {s.upper() for s in SIZE_LABELS}:
        return True
    return token in ALL_SIZES


def build_color_code_map(productos: pd.Series) -> dict[str, str]:
    """Infer 2-digit SKU color codes from rows that include a color name."""
    code_colors: dict[str, Counter] = {}
    for producto in productos.dropna().astype(str):
        m = re.search(r"\[([A-Z0-9]+)\].*\(([^)]+)\)", producto)
        if not m:
            continue
        sku, inner = m.group(1), m.group(2)
        parts = [p.strip() for p in inner.split(", ")]
        if len(parts) != 2:
            continue
        if _is_size(parts[0]):
            color = parts[1]
        elif _is_size(parts[1]):
            color = parts[0]
        else:
            color = parts[0]
        color = normalize_color_name(color, final_pass=False)
        if not color:
            continue
        for code in re.findall(r"\d{2}", sku):
            code_colors.setdefault(code, Counter())[color] += 1
    return {code: counts.most_common(1)[0][0] for code, counts in code_colors.items()}


def color_from_sku(sku: str, color_map: dict[str, str]) -> str | None:
    if not sku:
        return None
    m = re.search(r"(\d{2})T", sku)
    if m and m.group(1) in color_map:
        return color_map[m.group(1)]
    for code in re.findall(r"\d{2}", sku):
        if code in color_map:
            return color_map[code]
    return None


def normalize_color_name(color, final_pass: bool = True) -> str | None:
    if color is None or (isinstance(color, float) and pd.isna(color)):
        return None
    s = str(color).strip()
    if not s:
        return None

    if "," in s:
        parts = [p.strip() for p in s.split(",")]
        if len(parts) == 2 and _is_size(parts[1]):
            s = parts[0]

    if "/" in s:
        s = s.split("/")[0].strip()

    if " - " in s:
        left, right = s.rsplit(" - ", 1)
        if re.search(r"\d", right.strip()):
            s = left.strip()

    s = re.sub(r"\d+", "", s)
    s = re.sub(r"\s+", " ", s).strip(" -,")
    if not s:
        return None

    if s in COLOR_ALIASES:
        s = COLOR_ALIASES[s]

    if final_pass and s.isupper() and len(s) > 2:
        s = s.title()

    return s


def extract_modelo(producto: str) -> str:
    v = str(producto).strip()
    m = re.search(r"\]\s*(.+?)\s+\(", v)
    if m:
        name = re.sub(r"\s+(DAMA|CAB|KIDS)$", "", m.group(1).strip())
        return name
    m2 = re.search(r"\]\s*(.+)$", v)
    if m2:
        return re.sub(r"\s+(DAMA|CAB|KIDS)$", "", m2.group(1).strip())
    return v


def _genero_from_text(text: str) -> str | None:
    m = re.search(r"\b(DAMA|CAB|KIDS)\b", str(text))
    return m.group(1) if m else None


def parse_inventory_product(producto: str, color_map: dict[str, str]):
    v = str(producto).strip()
    sku = genero = color = talla = None
    modelo = None

    m_sku = re.search(r"\[([^\]]+)\]", v)
    if m_sku:
        sku = m_sku.group(1)

    genero = _genero_from_text(v)

    m_app = re.search(r"\]\s*(.+?)\s+(DAMA|CAB|KIDS)\s+\(([^)]+)\)\s*$", v)
    if m_app:
        genero = m_app.group(2)
        content = m_app.group(3).strip()
    else:
        m_paren = re.search(r"\(([^)]+)\)\s*$", v)
        content = m_paren.group(1).strip() if m_paren else None

    if content:
        parts = [p.strip() for p in content.split(", ")]
        if len(parts) == 2:
            if _is_size(parts[0]):
                talla, color = parts[0], parts[1]
            elif _is_size(parts[1]):
                color, talla = parts[0], parts[1]
            else:
                color, talla = parts[0], None
        elif len(parts) == 1:
            if _is_size(parts[0]):
                talla = parts[0]
            else:
                color = parts[0]
    elif m_sku and "(" not in v:
        trailing = re.search(r"\]\s*(.+)$", v)
        if trailing:
            tokens = trailing.group(1).strip().split()
            if len(tokens) >= 2:
                modelo = " ".join(tokens[:-1])
                color = tokens[-1]
            elif len(tokens) == 1:
                modelo = tokens[0]
    elif re.fullmatch(r"([A-Z]+)(\d{2})T(\d{1,2})", v):
        sku = v
        m_bare = re.fullmatch(r"([A-Z]+)(\d{2})T(\d{1,2})", v)
        modelo = m_bare.group(1)
        color = color_map.get(m_bare.group(2))
        talla = m_bare.group(3)
        if "KI" in m_bare.group(1):
            genero = "KIDS"
    elif not m_sku and re.fullmatch(r"[A-Z0-9]+", v):
        sku = v

    if not color and talla and sku:
        color = color_from_sku(sku, color_map)

    if not sku and re.fullmatch(r"[A-Z0-9]+", v):
        sku = v

    color = normalize_color_name(color)
    if modelo is None:
        modelo = extract_modelo(v)

    if color and _is_size(color) and not talla:
        talla, color = color, None
        if not color and sku:
            color = color_from_sku(sku, color_map)

    if color and _is_size(color):
        if not talla:
            talla = color
        color = color_from_sku(sku, color_map) if sku else None

    color = normalize_color_name(color)
    return sku, modelo, genero, color, talla


def fix_misplaced_fields(row: pd.Series, color_map: dict[str, str]) -> pd.Series:
    color = row["COLOR"]
    talla = row["TALLA"]
    sku = row["SKU"]

    if pd.notna(color) and _is_size(str(color)):
        if pd.isna(talla):
            talla = color
        color = color_from_sku(str(sku) if pd.notna(sku) else "", color_map)

    color = normalize_color_name(color)
    return pd.Series({"COLOR": color, "TALLA": talla})


def process_inventory_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    color_map = build_color_code_map(out["Producto"])

    parsed = out["Producto"].apply(lambda p: parse_inventory_product(p, color_map))
    out["SKU"] = parsed.apply(lambda x: x[0])
    out["MODELO"] = parsed.apply(lambda x: x[1])
    out["GENERO"] = parsed.apply(lambda x: x[2])
    out["COLOR"] = parsed.apply(lambda x: x[3])
    out["TALLA"] = parsed.apply(lambda x: x[4])

    fixed = out.apply(lambda r: fix_misplaced_fields(r, color_map), axis=1)
    out["COLOR"] = fixed["COLOR"]
    out["TALLA"] = fixed["TALLA"]

    return out
