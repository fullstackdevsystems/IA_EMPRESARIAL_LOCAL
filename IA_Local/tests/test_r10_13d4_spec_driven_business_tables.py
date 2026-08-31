from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

BUILDER = (
    ROOT
    / "scripts"
    / "dashboard_spec_builder.py"
)

RENDERER = (
    ROOT
    / "scripts"
    / "dynamic_renderer.py"
)


builder_text = BUILDER.read_text(
    encoding="utf-8"
)

renderer_text = RENDERER.read_text(
    encoding="utf-8"
)


checks = []


def check(
    name: str,
    condition: bool,
) -> None:

    checks.append(
        (
            name,
            bool(condition),
        )
    )

    print(
        (
            "PASS "
            if condition
            else "FAIL "
        )
        + name
    )


print(
    "\n=== R10.13D.4 "
    "SPEC-DRIVEN BUSINESS TABLE EXECUTOR ==="
)


# ============================================================
# BUILDER / EXECUTION PLAN
# ============================================================

check(
    "table_execution_spec_exists",
    "def _table_execution_spec(" in builder_text,
)

check(
    "builder_grouped_operator",
    '"operator": "grouped_business_table"'
    in builder_text,
)

check(
    "builder_transaction_operator",
    '"operator": "transaction_table"'
    in builder_text,
)

check(
    "builder_raw_operator",
    '"operator": "raw_table"'
    in builder_text,
)

check(
    "builder_grain_roles",
    '"grain_roles"' in builder_text,
)

check(
    "builder_fallback_grain_roles",
    '"fallback_grain_roles"' in builder_text,
)

check(
    "builder_label_roles",
    '"label_roles"' in builder_text,
)

check(
    "builder_measure_kpis",
    '"measure_kpis"' in builder_text,
)

check(
    "builder_sort_metric",
    '"sort_metric"' in builder_text,
)

check(
    "builder_limit",
    '"limit"' in builder_text,
)

check(
    "builder_attaches_execution",
    'c["execution"] ='
    in builder_text,
)

check(
    "builder_table_execution_planner_provenance",
    '"table_execution_planner"'
    in builder_text,
)


# ============================================================
# ENTITY GRAIN SAFETY
# ============================================================

check(
    "customer_id_supported_as_grain",
    '"customer_id"'
    in builder_text,
)

check(
    "product_id_supported_as_grain",
    '"product_id"'
    in builder_text,
)

check(
    "seller_id_supported_as_grain",
    '"seller_id"'
    in builder_text,
)

check(
    "transaction_id_reserved_for_operations",
    '"transaction_id"'
    in builder_text,
)


# ============================================================
# RENDERER
# ============================================================

check(
    "renderer_reads_execution_operator",
    "execution.operator"
    in renderer_text,
)

check(
    "renderer_grouped_dispatch",
    "if(operator==='grouped_business_table')"
    in renderer_text,
)

check(
    "renderer_transaction_dispatch",
    "if(operator==='transaction_table')"
    in renderer_text,
)

check(
    "renderer_raw_dispatch",
    "if(operator==='raw_table')"
    in renderer_text,
)

check(
    "renderer_grouped_uses_grain_roles",
    "execution.grain_roles"
    in renderer_text,
)

check(
    "renderer_grouped_uses_fallback_grain",
    "execution.fallback_grain_roles"
    in renderer_text,
)

check(
    "renderer_grouped_uses_label_roles",
    "execution.label_roles"
    in renderer_text,
)

check(
    "renderer_grouped_uses_measure_kpis",
    "execution.measure_kpis"
    in renderer_text,
)

check(
    "renderer_grouped_uses_sort_metric",
    "execution.sort_metric"
    in renderer_text,
)

check(
    "renderer_grouped_uses_limit",
    "execution.limit"
    in renderer_text,
)


# ============================================================
# CANONICAL KPI REUSE
# ============================================================

check(
    "renderer_reuses_business_metric_definitions",
    "businessMetricDefinitions()"
    in renderer_text,
)

check(
    "renderer_reuses_aggregate_metric",
    "aggregateMetric("
    in renderer_text,
)

check(
    "renderer_reuses_kpi_value",
    "return kpiValue("
    in renderer_text,
)


# ============================================================
# TRANSACTION TABLE SAFETY
# ============================================================

check(
    "transaction_table_resolves_roles",
    ".map("
    in renderer_text
    and "role(r)"
    in renderer_text,
)

check(
    "transaction_table_uses_table_card",
    "return tableCard("
    in renderer_text,
)

transaction_pos = renderer_text.find(
    "if(operator==='transaction_table')"
)
raw_pos = renderer_text.find(
    "if(operator==='raw_table')"
)

transaction_block = renderer_text[
    transaction_pos:
    raw_pos if raw_pos > transaction_pos else len(renderer_text)
]

check(
    "transaction_table_not_grouped",
    (
        transaction_pos >= 0
        and "aggregateGroups("
        not in transaction_block
    ),
)


# ============================================================
# D.5 ARCHITECTURE: LEGACY TABLE IDS REMOVED
# ============================================================

check(
    "legacy_customers_removed",
    "if(id==='table:customers')"
    not in renderer_text,
)

check(
    "legacy_products_removed",
    "if(id==='table:products')"
    not in renderer_text,
)

check(
    "legacy_sellers_removed",
    "if(id==='table:sellers')"
    not in renderer_text,
)

check(
    "legacy_operations_removed",
    "if(id==='table:operations')"
    not in renderer_text,
)

check(
    "renderer_version_preserved",
    'VERSION = "r10.13c"'
    in renderer_text,
)

check(
    "d5_runtime_marker",
    "R10.13D.5 · Operator-Driven Table Executor"
    in renderer_text,
)


# ============================================================
# RESULT
# ============================================================

failed = [
    name
    for name, ok in checks
    if not ok
]

if failed:

    print(
        "\n=== FAILURES ==="
    )

    for name in failed:
        print(
            "FAIL",
            name,
        )

    raise SystemExit(
        1
    )


print(
    "\nPASS R10.13D.4 "
    "SPEC-DRIVEN BUSINESS TABLE EXECUTOR"
)

print(
    f"{len(checks)}/{len(checks)} PASS"
)
