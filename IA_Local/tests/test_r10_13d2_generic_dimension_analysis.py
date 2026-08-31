from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


from dashboard_spec_builder import build_dashboard_spec
from dynamic_renderer import runtime_markup


def check(name, cond):
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name}")
        raise AssertionError(name)


df = pd.DataFrame(
    {
        "Fecha": [
            "2026-01-01",
            "2026-01-02",
            "2026-01-03",
        ],
        "Cliente": [
            "Cliente A",
            "Cliente B",
            "Cliente A",
        ],
        "Cod_Cliente": [
            "A",
            "B",
            "A",
        ],
        "Articulo": [
            "Producto 1",
            "Producto 2",
            "Producto 1",
        ],
        "Vendedor": [
            "Vendedor 1",
            "Vendedor 2",
            "Vendedor 1",
        ],
        "Almacen": [
            "Almacén 1",
            "Almacén 2",
            "Almacén 1",
        ],
        "Refer": [
            "R1",
            "R2",
            "R3",
        ],
        "Toneladas_Vendidas": [
            10.0,
            20.0,
            30.0,
        ],
        "Importe_Venta": [
            1000.0,
            2000.0,
            3000.0,
        ],
        "Costo": [
            800.0,
            1600.0,
            2500.0,
        ],
    }
)


prompt = """
Analiza el archivo desde una perspectiva comercial.

Genera análisis por:
- cliente
- producto
- vendedor
- almacén

Quiero calcular:
- ventas totales
- toneladas vendidas
- costo total

Quiero las siguientes páginas:
- Resumen Ejecutivo
- Clientes
- Productos
- Vendedores
- Detalle

No inventes métricas.
"""


roles = {
    "date": "Fecha",
    "customer": "Cliente",
    "customer_id": "Cod_Cliente",
    "product": "Articulo",
    "seller": "Vendedor",
    "warehouse": "Almacen",
    "transaction_id": "Refer",
    "quantity": "Toneladas_Vendidas",
    "revenue": "Importe_Venta",
    "cost": "Costo",
}


spec = build_dashboard_spec(
    df,
    prompt,
    sheet="Datos",
    semantic_roles=roles,
)


components = {
    c["id"]: c
    for c in spec.get("components") or []
}


pages = {
    p["id"]: p
    for p in spec.get("pages") or []
}


expected = {
    "analysis:dimension_customer",
    "analysis:dimension_product",
    "analysis:dimension_seller",
    "analysis:dimension_warehouse",
}


print()
print("=== COMPONENTES R10.13D.2 ===")

for cid in sorted(expected):
    c = components.get(cid)

    print(
        cid,
        "->",
        (c or {})
        .get("page_routing", {})
        .get("assigned_page"),
    )


print()
print("=== VALIDACIÓN DE COMPONENTES ===")


for cid in sorted(expected):

    check(
        f"exists:{cid}",
        cid in components,
    )

    c = components[cid]

    check(
        f"type:{cid}",
        c.get("type") == "analysis",
    )

    check(
        f"status:{cid}",
        c.get("status") == "SUPPORTED",
    )

    check(
        f"internal:{cid}",
        c.get("requested_by_prompt") is False,
    )

    check(
        f"provenance:{cid}",
        c.get("provenance", {}).get("source")
        == "dimension_analysis_planner",
    )

    check(
        f"operator:{cid}",
        c.get("execution", {}).get("operator")
        == "group_by_dimension",
    )

    check(
        f"measure:{cid}",
        c.get("execution", {}).get("measure_role")
        == "quantity",
    )

    check(
        f"routing_trace:{cid}",
        c.get("page_routing", {}).get("planner_version")
        == "r10.13d",
    )


print()
print("=== VALIDACIÓN DE ROUTING ===")


check(
    "customer_on_customers_page",
    "analysis:dimension_customer"
    in pages.get("customers", {}).get(
        "components",
        [],
    ),
)


check(
    "product_on_products_page",
    "analysis:dimension_product"
    in pages.get("productos", {}).get(
        "components",
        [],
    ),
)


check(
    "seller_on_sellers_page",
    "analysis:dimension_seller"
    in pages.get("vendedores", {}).get(
        "components",
        [],
    ),
)


check(
    "warehouse_on_summary_page",
    "analysis:dimension_warehouse"
    in pages.get("summary", {}).get(
        "components",
        [],
    ),
)


print()
print("=== VALIDACIÓN DE COVERAGE ===")


coverage = spec.get("coverage") or {}


check(
    "internal_components_not_counted",
    coverage.get("requested") < len(
        spec.get("components") or []
    ),
)


check(
    "coverage_consistency",
    coverage.get("fulfilled")
    == (
        coverage.get("supported", 0)
        + coverage.get("derivable", 0)
    ),
)


check(
    "coverage_percent_consistency",
    (
        coverage.get("percent") == 100.0
        if not coverage.get("requested")
        else round(
            coverage.get("fulfilled", 0)
            / coverage.get("requested", 1)
            * 100,
            2,
        )
        == coverage.get("percent")
    ),
)


print()
print("=== VALIDACIÓN DEL RUNTIME ===")


rt = runtime_markup()


check(
    "generic_dimension_executor",
    "analysis:dimension_" in rt,
)


check(
    "dimension_role_runtime",
    "dimension_role" in rt,
)


check(
    "measure_role_runtime",
    "measure_role" in rt,
)


check(
    "dimension_column_runtime",
    "dimensionCol" in rt,
)


check(
    "measure_column_runtime",
    "measureCol" in rt,
)


check(
    "group_runtime",
    "group(" in rt,
)


check(
    "dimension_missing_block",
    "No existe una columna semántica válida" in rt,
)


check(
    "measure_missing_block",
    "No existe una medida soportada" in rt,
)


check(
    "bars_executor",
    "barsCard(" in rt,
)


print()
print(
    "PASS R10.13D.2 "
    "GENERIC DIMENSION ANALYSIS EXECUTOR"
)