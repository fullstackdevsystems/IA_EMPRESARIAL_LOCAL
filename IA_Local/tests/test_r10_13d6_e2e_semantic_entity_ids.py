from __future__ import annotations

import sys
from pathlib import Path


def check(name: str, condition: bool) -> None:
    if not condition:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Uso:\n"
            "  python test_r10_13d6_e2e_semantic_entity_ids.py "
            "<Dashboard_generado.html>"
        )
        return 2

    path = Path(sys.argv[1]).resolve()
    if not path.exists():
        raise FileNotFoundError(path)

    text = path.read_text(encoding="utf-8", errors="replace")

    print()
    print("=== R10.13D.6 E2E SEMANTIC ENTITY IDS ===")
    print(f"Archivo: {path}")

    check(
        "product_id_role_resolved",
        '"product_id":"Cod_Articulo"' in text
        or '"product_id": "Cod_Articulo"' in text,
    )

    check(
        "seller_id_role_resolved",
        '"seller_id":"Cod_Vendedor"' in text
        or '"seller_id": "Cod_Vendedor"' in text,
    )

    check(
        "product_label_preserved",
        '"product":"Articulo"' in text
        or '"product": "Articulo"' in text,
    )

    check(
        "seller_label_preserved",
        '"seller":"Vendedor"' in text
        or '"seller": "Vendedor"' in text,
    )

    check(
        "products_table_uses_product_id_grain",
        '"semantic_role":"products"' in text
        and '"grain_roles":["product_id"]' in text,
    )

    check(
        "products_table_keeps_product_label",
        '"semantic_role":"products"' in text
        and '"label_roles":["product"]' in text,
    )

    check(
        "sellers_table_uses_seller_id_grain",
        '"semantic_role":"sellers"' in text
        and '"grain_roles":["seller_id"]' in text,
    )

    check(
        "sellers_table_keeps_seller_label",
        '"semantic_role":"sellers"' in text
        and '"label_roles":["seller"]' in text,
    )

    check(
        "d5_operator_runtime_preserved",
        "R10.13D.5 · Operator-Driven Table Executor" in text,
    )

    check(
        "freight_still_blocked",
        '"id":"kpi:freight"' in text
        and '"status":"BLOCKED"' in text,
    )

    check(
        "coverage_still_93_94",
        '"percent":93.94' in text,
    )

    print()
    print("PASS R10.13D.6 E2E SEMANTIC ENTITY IDS")
    print()
    print(
        "Revisión visual adicional: Productos debe usar Código Producto + Producto "
        "sin fusionar códigos distintos; Vendedores debe usar Código Vendedor + Vendedor."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
