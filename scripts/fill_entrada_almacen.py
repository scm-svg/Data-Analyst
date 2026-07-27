#!/usr/bin/env python3
"""Fill PRODUCTO column for warehouse entrada file from SKU catalog."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sku_catalog import load_sku_index, lookup_product, norm_sku

IN_PATH = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/"
    "SKU_POR_ARREGLAR_ENTRADA_ALMACEN_8db9.xlsx"
)
OUT_PATH = Path("/workspace/output/SKU_ENTRADA_ALMACEN_completado.xlsx")


def main() -> None:
    df = pd.read_excel(IN_PATH, sheet_name=0)
    index = load_sku_index()

    productos: list[str | None] = []
    sku_catalogo: list[str | None] = []
    fuentes: list[str | None] = []
    estados: list[str] = []

    for _, row in df.iterrows():
        raw = row.get("SKU")
        prod, sku_used, reason = lookup_product(str(raw), index)
        productos.append(prod)
        sku_catalogo.append(sku_used)
        if prod and sku_used:
            if reason == "exact" and norm_sku(raw) == sku_used:
                estados.append("ok")
                fuentes.append(index.set_index("SKU").loc[sku_used, "FUENTE"])
            else:
                estados.append("ok_sku_corregido")
                fuentes.append(f"{reason}; {index.set_index('SKU').loc[sku_used, 'FUENTE']}")
        else:
            estados.append("not_found")
            fuentes.append(None)

    out = df.copy()
    out["PRODUCTO"] = productos
    out["SKU_CATALOGO"] = sku_catalogo
    out["FUENTE"] = fuentes
    out["ESTADO"] = estados

    pendientes = out[out["ESTADO"] == "not_found"]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
        out[["SKU", "PRODUCTO", "CANT"]].to_excel(
            writer, sheet_name="ENTRADA LIMPIA", index=False
        )
        out.to_excel(writer, sheet_name="Hoja1", index=False)
        if len(pendientes):
            pendientes.to_excel(writer, sheet_name="PENDIENTES", index=False)

    ok = (out["ESTADO"] != "not_found").sum()
    print(f"Output: {OUT_PATH}")
    print(f"Total filas: {len(out)}")
    print(f"PRODUCTO completado: {ok}")
    print(f"Pendientes: {len(out) - ok}")
    print(out["ESTADO"].value_counts().to_string())


if __name__ == "__main__":
    main()
