#!/usr/bin/env python3
"""Fill PRODUCTO column for warehouse entrada file from SKU catalog."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sku_catalog import load_quants_index, load_sku_index, lookup_product, norm_sku

IN_PATH = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/"
    "SKU_POR_ARREGLAR_ENTRADA_ALMACEN_8db9.xlsx"
)
OUT_PATH = Path("/workspace/output/SKU_ENTRADA_ALMACEN_completado.xlsx")


def main() -> None:
    df = pd.read_excel(IN_PATH, sheet_name=0)
    catalog = load_sku_index()
    quants = load_quants_index()

    productos: list[str | None] = []
    productos_odoo: list[str | None] = []
    sku_catalogo: list[str | None] = []
    fuentes: list[str | None] = []
    estados: list[str] = []

    for _, row in df.iterrows():
        raw = row.get("SKU")
        prod, sku_used, reason, prod_odoo = lookup_product(str(raw), catalog, quants)
        productos.append(prod)
        productos_odoo.append(prod_odoo)
        sku_catalogo.append(sku_used)
        estados.append(reason if prod else "not_found")

        if prod and sku_used:
            if reason == "ok_quants_odoo":
                qrow = quants[quants["SKU"] == sku_used].iloc[0]
                fuentes.append(qrow["FUENTE"])
            elif reason.startswith("ok_catalog"):
                fuente = catalog.set_index("SKU").loc[sku_used, "FUENTE"]
                fuentes.append(f"{reason}; {fuente}")
            elif reason == "ok":
                fuentes.append(catalog.set_index("SKU").loc[sku_used, "FUENTE"])
            else:
                fuentes.append(reason)
        else:
            fuentes.append(None)

    out = df.copy()
    out["PRODUCTO"] = productos
    out["PRODUCTO_ODOO"] = productos_odoo
    out["SKU_CATALOGO"] = sku_catalogo
    out["FUENTE"] = fuentes
    out["ESTADO"] = estados

    pendientes = out[out["ESTADO"] == "not_found"]

    r2_mask = out["SKU"].astype(str).str.upper().str.match(r"^(SSR2VIU|SRR2VIU)")
    revision_r2 = out[r2_mask].copy()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
        out[["SKU", "PRODUCTO", "CANT"]].to_excel(
            writer, sheet_name="ENTRADA LIMPIA", index=False
        )
        out.to_excel(writer, sheet_name="Hoja1", index=False)
        if len(revision_r2):
            revision_r2.to_excel(writer, sheet_name="R2 VALIDADO QUANTS", index=False)
        if len(pendientes):
            pendientes.to_excel(writer, sheet_name="PENDIENTES", index=False)

    ok = (out["ESTADO"] != "not_found").sum()
    print(f"Output: {OUT_PATH}")
    print(f"Total filas: {len(out)}")
    print(f"PRODUCTO completado: {ok}")
    print(f"Pendientes: {len(out) - ok}")
    print(out["ESTADO"].value_counts().to_string())
    if len(revision_r2):
        print("\nR2 sample:")
        print(
            revision_r2[["SKU", "PRODUCTO", "PRODUCTO_ODOO", "ESTADO"]]
            .head(10)
            .to_string()
        )


if __name__ == "__main__":
    main()
