from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from semantic_layer import resolve_semantic_map
from dashboard_spec_builder import build_dashboard_spec


def check(name: str, condition: bool) -> None:
    if not condition:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


def main() -> None:
    df = pd.DataFrame(
        {
            "Cod_Cliente": ["C001", "C002", "C001"],
            "Cliente": ["Cliente Uno", "Cliente Dos", "Cliente Uno"],
            "Cod_Articulo": ["P001", "P002", "P001"],
            "Articulo": ["MAIZ", "SORGO", "MAIZ"],
            "Cod_Vendedor": ["V01", "V02", "V01"],
            "Vendedor": ["VENDEDOR A", "VENDEDOR B", "VENDEDOR A"],
            "Refer": ["A1", "A2", "A3"],
            "Fecha": pd.to_datetime(
                ["2026-01-01", "2026-01-02", "2026-01-03"]
            ),
            "Importe_Venta": [1000.0, 2000.0, 1500.0],
            "Costo": [800.0, 1500.0, 1100.0],
            "Toneladas_Vendidas": [10.0, 20.0, 15.0],
            "Almacen": ["ALM 1", "ALM 1", "ALM 2"],
        }
    )

    sm = resolve_semantic_map(df)

    usable = dict(sm.get("usable") or {})
    concepts = dict(sm.get("concepts") or {})

    check(
        "product_label_stays_articulo",
        usable.get("product") == "Articulo",
    )

    check(
        "product_id_resolves_cod_articulo",
        usable.get("product_id") == "Cod_Articulo",
    )

    check(
        "seller_label_stays_vendedor",
        usable.get("seller") == "Vendedor",
    )

    check(
        "seller_id_resolves_cod_vendedor",
        usable.get("seller_id") == "Cod_Vendedor",
    )

    check(
        "product_id_exact_or_strong",
        (concepts.get("product_id") or {}).get("confidence")
        in {"EXACT", "STRONG"},
    )

    check(
        "seller_id_exact_or_strong",
        (concepts.get("seller_id") or {}).get("confidence")
        in {"EXACT", "STRONG"},
    )

    prompt = """
    Genera un dashboard comercial.
    Quiero páginas: Productos, Vendedores y Detalle.
    Analiza ventas, costo, utilidad y toneladas.
    Genera tablas por producto y vendedor.
    """

    spec = build_dashboard_spec(
        df,
        prompt,
        sheet="Datos",
    )

    provenance_roles = dict(
        (spec.get("provenance") or {}).get("semantic_roles") or {}
    )

    check(
        "builder_receives_product_id",
        provenance_roles.get("product_id") == "Cod_Articulo",
    )

    check(
        "builder_receives_seller_id",
        provenance_roles.get("seller_id") == "Cod_Vendedor",
    )

    tables = {
        x.get("id"): x
        for x in (spec.get("tables") or [])
        if isinstance(x, dict)
    }

    product_exec = dict(
        (tables.get("table:products") or {}).get("execution") or {}
    )

    seller_exec = dict(
        (tables.get("table:sellers") or {}).get("execution") or {}
    )

    check(
        "products_grain_prefers_product_id",
        product_exec.get("grain_roles") == ["product_id"],
    )

    check(
        "products_fallback_product",
        product_exec.get("fallback_grain_roles") == ["product"],
    )

    check(
        "products_label_product",
        product_exec.get("label_roles") == ["product"],
    )

    check(
        "sellers_grain_prefers_seller_id",
        seller_exec.get("grain_roles") == ["seller_id"],
    )

    check(
        "sellers_fallback_seller",
        seller_exec.get("fallback_grain_roles") == ["seller"],
    )

    check(
        "sellers_label_seller",
        seller_exec.get("label_roles") == ["seller"],
    )

    print()
    print("PASS R10.13D.6 SEMANTIC ENTITY IDS")


if __name__ == "__main__":
    main()
