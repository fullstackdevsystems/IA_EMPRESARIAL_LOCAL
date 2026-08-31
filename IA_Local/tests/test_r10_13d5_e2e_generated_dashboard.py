from __future__ import annotations

import sys
from pathlib import Path


EXPECTED_PAGES = [
    ("summary", "Resumen Ejecutivo"),
    ("rentabilidad", "Rentabilidad"),
    ("customers", "Clientes"),
    ("productos", "Productos"),
    ("vendedores", "Vendedores"),
    ("evolution", "Evolución"),
    ("detalle", "Detalle"),
]


def check(name: str, condition: bool) -> None:
    if not condition:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Uso:\n"
            "  python test_r10_13d5_e2e_generated_dashboard.py "
            "<Dashboard_generado.html>"
        )
        return 2

    path = Path(sys.argv[1]).resolve()

    if not path.exists():
        raise FileNotFoundError(path)

    text = path.read_text(encoding="utf-8", errors="replace")

    print()
    print("=== R10.13D.5 GENERATED DASHBOARD E2E CONTRACT ===")
    print(f"Archivo: {path}")

    # ---------------------------------------------------------
    # DATA / PROMPT CONTRACT
    # ---------------------------------------------------------
    check(
        "rows_22512_present",
        '"rows":22512' in text or '"rows": 22512' in text,
    )

    check(
        "commercial_prompt_present",
        "Analiza el archivo desde una perspectiva comercial y de rentabilidad."
        in text,
    )

    check(
        "prompt_length_1222",
        '"prompt_length":1222' in text
        or '"prompt_length": 1222' in text,
    )

    # ---------------------------------------------------------
    # EXACT DYNAMIC PAGES
    # ---------------------------------------------------------
    for page_id, title in EXPECTED_PAGES:
        check(
            f"page_{page_id}_{title}",
            f'"id":"{page_id}","title":"{title}"' in text
            or f'"id": "{page_id}", "title": "{title}"' in text,
        )

    # ---------------------------------------------------------
    # D5 RUNTIME
    # ---------------------------------------------------------
    check(
        "d5_operator_driven_marker",
        "R10.13D.5 · Operator-Driven Table Executor" in text,
    )

    check(
        "grouped_operator_present",
        "grouped_business_table" in text,
    )

    check(
        "transaction_operator_present",
        "transaction_table" in text,
    )

    check(
        "raw_operator_present",
        "raw_table" in text,
    )

    check(
        "execution_operator_dispatch_present",
        "execution.operator" in text,
    )

    # ---------------------------------------------------------
    # LEGACY DISPATCH REMOVAL
    # ---------------------------------------------------------
    check(
        "legacy_customers_dispatch_removed",
        "if(id==='table:customers')" not in text,
    )

    check(
        "legacy_products_dispatch_removed",
        "if(id==='table:products')" not in text,
    )

    check(
        "legacy_sellers_dispatch_removed",
        "if(id==='table:sellers')" not in text,
    )

    check(
        "legacy_operations_dispatch_removed",
        "if(id==='table:operations')" not in text,
    )

    # ---------------------------------------------------------
    # GROUPED TABLE DEDUP CONTRACT
    # ---------------------------------------------------------
    check(
        "active_grain_roles_runtime",
        "activeGrainRoles" in text,
    )

    check(
        "effective_label_roles_runtime",
        "effectiveLabelRoles" in text,
    )

    check(
        "label_excludes_active_grain",
        "!activeGrainRoles.includes(r)" in text,
    )

    # ---------------------------------------------------------
    # TABLE EXECUTION SPECS
    # ---------------------------------------------------------
    check(
        "customers_grouped_spec",
        '"semantic_role":"customers"' in text
        and '"operator":"grouped_business_table"' in text,
    )

    check(
        "products_grouped_spec",
        '"semantic_role":"products"' in text
        and (
            '"grain_roles":["product_id"]' in text
            or '"grain_roles":["product"]' in text
        )
        and '"label_roles":["product"]' in text,
    )

    check(
        "sellers_grouped_spec",
        '"semantic_role":"sellers"' in text
        and (
            '"grain_roles":["seller_id"]' in text
            or '"grain_roles":["seller"]' in text
        )
        and '"label_roles":["seller"]' in text,
    )

    check(
        "detail_transaction_spec",
        '"semantic_role":"operations"' in text
        and '"operator":"transaction_table"' in text
        and '"grain_roles":["transaction_id"]' in text,
    )

    # ---------------------------------------------------------
    # FREIGHT SAFETY
    # ---------------------------------------------------------
    check(
        "freight_semantic_ambiguous",
        '"freight":{"label":"Flete","column":null,"confidence":"AMBIGUOUS"'
        in text,
    )

    check(
        "freight_kpi_blocked",
        '"id":"kpi:freight"' in text
        and '"status":"BLOCKED"' in text,
    )

    check(
        "freight_analysis_blocked",
        '"id":"analysis:freight_analysis"' in text
        and '"status":"BLOCKED"' in text,
    )

    check(
        "coverage_93_94",
        '"percent":93.94' in text,
    )

    # ---------------------------------------------------------
    # RESULT
    # ---------------------------------------------------------
    print()
    print("PASS R10.13D.5 GENERATED DASHBOARD E2E CONTRACT")
    print()
    print(
        "NOTA: esta prueba valida contrato, spec y runtime embebido. "
        "La ejecución visual del JavaScript en navegador se confirma "
        "revisando Productos, Vendedores y Detalle."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
