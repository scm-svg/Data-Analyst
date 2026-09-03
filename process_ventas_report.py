"""Process sales report: parse variants and assign store locations."""
import re
import pandas as pd

SIZES = {"XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"}

STORE_RULES_ORDEN = [
    ("SAMBIL VALENCIA", "SAMBIL VALENCIA"),
    ("SAMBIL CHACAO", "SAMBIL CHACAO"),
    ("CHACAO", "SAMBIL CHACAO"),
    ("CERRO VERDE", "CERRO VERDE"),
    ("GRAND PLAZ", "GRAND PLAZ"),
    ("GRANDPLAZ", "GRAND PLAZ"),
    ("TOLON", "TOLON"),
    ("LA VELA", "LA VELA"),
    ("GRIETA", "GRIETA"),
    ("SAMBIL", "SAMBIL VALENCIA"),
]

STORE_RULES_VENDEDOR = [
    ("SAMBIL CHACAO", "SAMBIL CHACAO"),
    ("SAMBIL VALENCIA", "SAMBIL VALENCIA"),
    ("SAMBIL", "SAMBIL VALENCIA"),
    ("CERRO VERDE", "CERRO VERDE"),
    ("GRANDPLAZ", "GRAND PLAZ"),
    ("GRAND PLAZ", "GRAND PLAZ"),
    ("TOLON", "TOLON"),
    ("LA VELA", "LA VELA"),
    ("GRIETA", "GRIETA"),
]


def _split_size_color(content: str):
    parts = [p.strip() for p in content.split(", ")]
    if len(parts) == 2:
        if parts[0] in SIZES or parts[0].isdigit():
            return parts[0], parts[1]
        if parts[1] in SIZES or parts[1].isdigit():
            return parts[1], parts[0]
        return None, content
    if len(parts) == 1:
        return None, parts[0]
    return None, content


def _genero_from_modelo(modelo: str):
    m = re.search(r"\b(DAMA|CAB|KIDS)\b", str(modelo))
    return m.group(1) if m else None


def parse_variant(variante: str, modelo: str):
    v = str(variante).strip()
    sku = genero = color = talla = None

    m_sku = re.search(r"\[([^\]]+)\]", v)
    if m_sku:
        sku = m_sku.group(1)

    m_app = re.search(r"\]\s*(.+?)\s+(DAMA|CAB|KIDS)\s+\(([^)]+)\)\s*$", v)
    if m_app:
        genero = m_app.group(2)
        talla, color = _split_size_color(m_app.group(3))
        return sku, genero, color, talla

    m_app2 = re.search(r"^(.+?)\s+(DAMA|CAB|KIDS)\s+\(([^)]+)\)\s*$", v)
    if m_app2:
        genero = m_app2.group(2)
        talla, color = _split_size_color(m_app2.group(3))
        return sku, genero, color, talla

    m_col = re.search(r"\]\s*(.+?)\s+\(([^)]+)\)\s*$", v)
    if m_col:
        talla, color = _split_size_color(m_col.group(2))
        genero = _genero_from_modelo(modelo)
        return sku, genero, color, talla

    m_plain = re.search(r"\[([^\]]+)\]\s*(.+?)\s+(.+)$", v)
    if m_plain and "(" not in v:
        sku = sku or m_plain.group(1)
        color = m_plain.group(3).strip()
        genero = _genero_from_modelo(modelo)
        return sku, genero, color, talla

    genero = _genero_from_modelo(modelo)
    return sku, genero, color, talla


def clean_color(color):
    """Remove numeric color codes; keep names only (e.g. Rosado Pastel - 20663 → Rosado Pastel)."""
    if color is None or (isinstance(color, float) and pd.isna(color)):
        return color
    s = str(color).strip()
    if not s:
        return s

    if " - " in s:
        left, right = s.rsplit(" - ", 1)
        if re.search(r"\d", right.strip()):
            s = left.strip()

    s = re.sub(r"\d+", "", s)
    s = re.sub(r"\s+", " ", s).strip(" -,")
    return s if s else None


def assign_tienda(orden_relacionada: str, vendedor: str) -> str | None:
    orden = str(orden_relacionada).strip()
    vend_upper = str(vendedor).upper()
    if orden.upper().startswith("S0"):
        if "WEB" in vend_upper:
            return "WEB"
        return "PEDIDOS"

    orden_upper = orden.upper()
    for keyword, store in STORE_RULES_ORDEN:
        if keyword in orden_upper:
            return store

    for keyword, store in STORE_RULES_VENDEDOR:
        if keyword in str(vendedor).upper():
            return store

    if "EVENTOS" in orden_upper:
        return "EVENTOS"

    return None


_ILLEGAL_XML_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def sanitize_excel_value(value):
    """Remove characters that break Excel / Office Open XML."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().replace(tzinfo=None)
    s = _ILLEGAL_XML_RE.sub("", str(value))
    if len(s) > 32767:
        s = s[:32767]
    return s


def sanitize_dataframe_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "Fecha de la orden" in out.columns:
        out["Fecha de la orden"] = pd.to_datetime(
            out["Fecha de la orden"], errors="coerce"
        ).dt.tz_localize(None)
    for col in out.columns:
        if out[col].dtype == object or pd.api.types.is_string_dtype(out[col]):
            out[col] = out[col].map(sanitize_excel_value)
    return out


def add_fecha_mes_anio(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    fechas = pd.to_datetime(out["Fecha de la orden"], errors="coerce")
    out["fecha (mes año)"] = fechas.dt.strftime("%m/%Y")
    return out


def export_excel(df: pd.DataFrame, output_path: str) -> None:
    df = sanitize_dataframe_for_excel(df)
    with pd.ExcelWriter(
        output_path,
        engine="openpyxl",
        datetime_format="yyyy-mm-dd hh:mm:ss",
        date_format="yyyy-mm-dd",
    ) as writer:
        df.to_excel(writer, sheet_name="Ventas", index=False)
        ws = writer.sheets["Ventas"]
        ws.freeze_panes = "A2"
        for idx, col in enumerate(df.columns, start=1):
            width = min(max(len(str(col)), 12), 40)
            if col in ("Variante del producto", "Orden relacionada"):
                width = 42
            ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = width


def main():
    input_path = (
        "/home/ubuntu/.cursor/projects/workspace/uploads/"
        "Reporte_del_an_lisis_de_ventas_ARREGLAR_INSTANCIA_VIEJA_65d2.xlsx"
    )
    output_path = "/workspace/Reporte_ventas_COMPLETO.xlsx"

    df = pd.read_excel(input_path)

    for col in ["SKU", "GENERO", "COLOR", "TALLA", "tienda / ubicación"]:
        df[col] = df[col].astype(object)

    parsed = df.apply(
        lambda r: parse_variant(r["Variante del producto"], r["modelo"]),
        axis=1,
        result_type="expand",
    )
    parsed.columns = ["SKU_p", "GENERO_p", "COLOR_p", "TALLA_p"]
    df["SKU"] = parsed["SKU_p"]
    df["GENERO"] = parsed["GENERO_p"]
    df["COLOR"] = parsed["COLOR_p"].apply(clean_color)
    df["TALLA"] = parsed["TALLA_p"]

    df["tienda / ubicación"] = df.apply(
        lambda r: assign_tienda(r["Orden relacionada"], r["vendedor"]),
        axis=1,
    )

    df.drop(columns=["SKU_p", "GENERO_p", "COLOR_p", "TALLA_p"], errors="ignore", inplace=True)

    df = add_fecha_mes_anio(df)
    export_excel(df, output_path)

    print("Output:", output_path)
    print("Columns:", list(df.columns))
    print("Rows:", len(df))
    print("\nNull counts after processing:")
    print(df[["SKU", "GENERO", "COLOR", "TALLA", "tienda / ubicación"]].isnull().sum())
    print("\nTienda distribution:")
    print(df["tienda / ubicación"].value_counts(dropna=False).head(15))
    print("\nGENERO filled:", df["GENERO"].notna().sum())
    print("TALLA filled:", df["TALLA"].notna().sum())
    print("COLOR filled:", df["COLOR"].notna().sum())
    print("fecha (mes año) nulls:", df["fecha (mes año)"].isna().sum())
    print("fecha (mes año) sample:", df["fecha (mes año)"].dropna().head(3).tolist())


if __name__ == "__main__":
    main()
