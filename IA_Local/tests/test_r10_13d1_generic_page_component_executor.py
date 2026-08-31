from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from dynamic_renderer import runtime_markup


def check(name, cond):
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name}")
        raise AssertionError(name)


rt = runtime_markup()


checks = [

    # ---------------------------------------------------------
    # R10.13D.1 canonical dispatcher
    # ---------------------------------------------------------

    (
        "component_executor_exists",
        "function componentCard(c,rr)" in rt
    ),

    (
        "page_uses_component_executor",
        "componentCard(" in rt
        and "function pageHtml(page,rr)" in rt
    ),


    # ---------------------------------------------------------
    # Generic table executor
    # ---------------------------------------------------------

    (
        "generic_table_executor_exists",
        "function genericTableCard(c,rr)" in rt
    ),

    (
        "table_dispatch",
        "c.type==='table'" in rt
        and "genericTableCard(" in rt
    ),

    (
        "customers_table_executor",
        "table:customers" in rt
        and "role('customer')" in rt
    ),

    (
        "products_table_executor",
        "table:products" in rt
        and "role('product')" in rt
    ),

    (
        "sellers_table_executor",
        "table:sellers" in rt
        and "role('seller')" in rt
    ),

    (
        "operations_table_executor",
        "table:operations" in rt
        and "'Refer'" in rt
    ),


    # ---------------------------------------------------------
    # Generic filter executor
    # ---------------------------------------------------------

    (
        "generic_filter_executor_exists",
        "function genericFilterCard(c)" in rt
    ),

    (
        "filter_dispatch",
        "c.type==='filter'" in rt
        and "genericFilterCard(" in rt
    ),

    (
        "filter_global_authority",
        "Filtro global activo para esta página." in rt
    ),


    # ---------------------------------------------------------
    # Deliverable executor
    # ---------------------------------------------------------

    (
        "deliverable_executor_exists",
        "function deliverableCard(c)" in rt
    ),

    (
        "deliverable_dispatch",
        "c.type==='deliverable'" in rt
        and "deliverableCard(" in rt
    ),

    (
        "deliverable_not_fake_chart",
        "Entregable solicitado por el prompt" in rt
    ),


    # ---------------------------------------------------------
    # Commercial profitability executor
    # ---------------------------------------------------------

    (
        "profitability_executor_exists",
        "analysis:profitability" in rt
    ),

    (
        "profitability_uses_revenue",
        "role('revenue')" in rt
    ),

    (
        "profitability_uses_cost",
        "role('cost')" in rt
    ),

    (
        "profitability_uses_customer",
        "role('customer')" in rt
    ),

    (
        "profitability_chart",
        "Rentabilidad por cliente" in rt
    ),


    # ---------------------------------------------------------
    # Detail executor
    # ---------------------------------------------------------

    (
        "detail_analysis_executor",
        "analysis:detail" in rt
        and "Detalle Logístico" in rt
    ),

    (
        "detail_table_executor",
        "tableCard(" in rt
    ),


    # ---------------------------------------------------------
    # Freight safety
    # ---------------------------------------------------------

    (
        "freight_analysis_blocked_executor",
        "analysis:freight_analysis" in rt
        and "Análisis de Flete" in rt
    ),

    (
        "blocked_precedence",
        "if(c.status==='BLOCKED')" in rt
    ),

    (
        "blocked_nd",
        "· N/D" in rt
    ),


    # ---------------------------------------------------------
    # Derived rules compatibility
    # ---------------------------------------------------------

    (
        "difference_of_sums_preserved",
        "op==='difference_of_sums'" in rt
    ),

    (
        "ratio_of_sums_preserved",
        "op==='ratio_of_sums'" in rt
    ),

    (
        "sum_over_nunique_preserved",
        "op==='sum_over_nunique'" in rt
    ),

    (
        "zero_division_nd_preserved",
        "división por cero: N/D" in rt
    ),


    # ---------------------------------------------------------
    # Filter reactivity
    # ---------------------------------------------------------

    (
        "filter_change_reactivity",
        "ia-dashboard-filter-change" in rt
    ),


    # ---------------------------------------------------------
    # Version marker
    # ---------------------------------------------------------

    (
        "d1_runtime_marker",
        "R10.13D.1 · Generic Component Executor" in rt
    ),


    # ---------------------------------------------------------
    # Legacy compatibility
    # ---------------------------------------------------------

    (
        "legacy_sales_mode_preserved",
        "legacyMode=model.domain==='sales'" in rt
    ),

    (
        "legacy_derived_metrics_preserved",
        "Métricas derivadas gobernadas" in rt
    ),
]


for name, cond in checks:
    check(name, cond)


print()
print("PASS R10.13D.1 GENERIC PAGE COMPONENT EXECUTOR")
print(f"{len(checks)}/{len(checks)} PASS")