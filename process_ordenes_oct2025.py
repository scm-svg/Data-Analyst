"""Fill missing parsed columns on Oct 2025+ orders export."""
import sys

import pandas as pd

from process_inventory import build_color_code_map, fix_misplaced_fields, parse_inventory_product
from process_ventas_report import assign_tienda, export_excel, sanitize_dataframe_for_excel


def process_ordenes_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "Vendedor" in out.columns and "vendedor" not in out.columns:
        out["vendedor"] = out["Vendedor"]
    if "Producto" in out.columns and "modelo" not in out.columns:
        out["modelo"] = out["Producto"]

    color_map = build_color_code_map(out["Variante del producto"])
    parsed = out["Variante del producto"].apply(
        lambda v: parse_inventory_product(v, color_map)
    )
    out["SKU"] = parsed.apply(lambda x: x[0])
    out["GENERO"] = parsed.apply(lambda x: x[2])
    out["COLOR"] = parsed.apply(lambda x: x[3])
    out["TALLA"] = parsed.apply(lambda x: x[4])

    fixed = out.apply(lambda r: fix_misplaced_fields(r, color_map), axis=1)
    out["COLOR"] = fixed["COLOR"]
    out["TALLA"] = fixed["TALLA"]

    out["tienda / ubicación"] = out.apply(
        lambda r: assign_tienda(None, r["vendedor"]),
        axis=1,
    )

    fechas = pd.to_datetime(out["Fecha de la orden"], errors="coerce")
    out["fecha (mes año)"] = fechas.dt.strftime("%m/%Y")

    return out


def main() -> None:
    input_path = (
        "/home/ubuntu/.cursor/projects/workspace/uploads/"
        "Ordenes_de_Ventas_Oct2025_en_adelante_3b3f.xlsx"
    )
    output_path = "/workspace/Ordenes_de_Ventas_Oct2025_COMPLETO.xlsx"

    df = pd.read_excel(input_path, sheet_name="VENTAS")
    result = process_ordenes_dataframe(df)

    # Logical column order: keep source columns, insert parsed fields after Variante
    base = [
        "Año",
        "Mes",
        "Fecha de la orden",
        "Categoría del producto",
        "Producto",
        "Variante del producto",
    ]
    parsed_cols = ["SKU", "GENERO", "COLOR", "TALLA", "tienda / ubicación"]
    tail = [
        "Cant. ordenada",
        "Vendedor",
        "Total",
        "TOTAL ($)",
        "COSTO ($) UNITARIO",
        "COSTO ($) TOTAL",
        "%GANANCIA",
        "fecha (mes año)",
    ]
    ordered = base + parsed_cols + tail
    result = result[[c for c in ordered if c in result.columns]]

    sanitized = sanitize_dataframe_for_excel(result)
    with pd.ExcelWriter(
        output_path,
        engine="openpyxl",
        datetime_format="yyyy-mm-dd hh:mm:ss",
        date_format="yyyy-mm-dd",
    ) as writer:
        sanitized.to_excel(writer, sheet_name="VENTAS", index=False)
        ws = writer.sheets["VENTAS"]
        ws.freeze_panes = "A2"

    print("Output:", output_path)
    print("Rows:", len(result))
    print("Nulls parsed:", result[parsed_cols].isnull().sum().to_dict())
    print("Tienda:", result["tienda / ubicación"].value_counts(dropna=False).head(12).to_dict())
    print("COLOR with digits:", result["COLOR"].astype(str).str.contains(r"\\d", na=False).sum())


if __name__ == "__main__":
    main()
