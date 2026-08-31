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
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


df = pd.DataFrame(
    {
        "Cod_Cliente": ["C1", "C2", "C1"],
        "Cliente": ["Cliente A", "Cliente B", "Cliente A"],
        "Cod_Articulo": ["P1", "P2", "P1"],
        "Articulo": ["Maíz", "Sorgo", "Maíz"],
        "Cod_Vendedor": ["V1", "V2", "V1"],
        "Vendedor": ["Ana", "Beto", "Ana"],
        "Almacen": ["Norte", "Sur", "Norte"],
        "Fecha": pd.to_datetime(
            ["2026-01-01", "2026-01-02", "2026-02-01"]
        ),
        "Refer": ["R1", "R2", "R3"],
        "Importe_Venta": [1000.0, 2000.0, 1500.0],
        "Costo": [800.0, 1500.0, 1200.0],
        "Toneladas_Vendidas": [10.0, 20.0, 15.0],
    }
)

prompt = """
Analiza ventas y rentabilidad por cliente, producto, vendedor y almacén.
Calcula ventas totales, costo total, utilidad, margen de utilidad,
toneladas vendidas, número de operaciones y ticket promedio.
Genera páginas Clientes, Productos, Vendedores y Resumen Ejecutivo.
"""

roles = {
    "customer": "Cliente",
    "customer_id": "Cod_Cliente",
    "product": "Articulo",
    "product_id": "Cod_Articulo",
    "seller": "Vendedor",
    "seller_id": "Cod_Vendedor",
    "warehouse": "Almacen",
    "date": "Fecha",
    "transaction_id": "Refer",
    "revenue": "Importe_Venta",
    "cost": "Costo",
    "quantity": "Toneladas_Vendidas",
}

spec = build_dashboard_spec(
    df,
    prompt,
    sheet="Datos",
    semantic_roles=roles,
)

components = {
    c.get("id"): c
    for c in spec.get("components") or []
    if isinstance(c, dict)
}

print()
print("=== R10.13D.7.1 GENERIC DIMENSION CHART EXECUTOR ===")

for role_name in (
    "customer",
    "product",
    "seller",
    "warehouse",
):
    c = components.get(
        f"analysis:dimension_{role_name}"
    )

    check(
        f"component_exists:{role_name}",
        c is not None,
    )

    execution = c.get("execution") or {}
    chart = execution.get("chart") or {}

    check(
        f"dimension_operator:{role_name}",
        execution.get("operator")
        == "dimension_profitability",
    )

    check(
        f"chart_operator:{role_name}",
        chart.get("operator")
        == "dimension_bar_chart",
    )

    check(
        f"chart_metric:{role_name}",
        chart.get("metric")
        == "kpi:revenue",
    )

    check(
        f"chart_top_n:{role_name}",
        chart.get("top_n")
        == 15,
    )

rt = runtime_markup()

check(
    "chart_spec_runtime",
    "execution.chart" in rt,
)

check(
    "dimension_bar_chart_dispatch",
    "chartOperator==='dimension_bar_chart'" in rt,
)

check(
    "chart_metric_runtime",
    "chartMetricId" in rt,
)

check(
    "chart_metric_definition_runtime",
    "chartMetricDef" in rt,
)

check(
    "chart_data_runtime",
    "const chartData=" in rt,
)

check(
    "generic_bars_card_reused",
    "barsCard(" in rt,
)

check(
    "chart_and_table_returned",
    "${chartHtml}" in rt,
)

check(
    "chart_uses_dimension_label",
    "item.label" in rt
    and "item.identity" in rt,
)

check(
    "chart_is_operator_driven",
    "dimension_bar_chart" in rt,
)

check(
    "no_dimension_specific_chart_ids",
    "chart:dimension_customer" not in rt
    and "chart:dimension_product" not in rt
    and "chart:dimension_seller" not in rt,
)

print()
print("PASS R10.13D.7.1 GENERIC DIMENSION CHART EXECUTOR")
