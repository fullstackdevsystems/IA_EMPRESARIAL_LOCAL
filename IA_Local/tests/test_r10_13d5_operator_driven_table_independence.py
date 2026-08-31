from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

RENDERER = (
    ROOT
    / "IA_Local"
    / "scripts"
    / "dynamic_renderer.py"
)

BUILDER = (
    ROOT
    / "IA_Local"
    / "scripts"
    / "dashboard_spec_builder.py"
)


renderer = RENDERER.read_text(
    encoding="utf-8"
)

builder = BUILDER.read_text(
    encoding="utf-8"
)


checks = []


def check(name, condition):

    if not condition:
        raise AssertionError(
            f"FAIL {name}"
        )

    print(
        f"PASS {name}"
    )

    checks.append(name)


print()
print(
    "=== R10.13D.5 "
    "OPERATOR-DRIVEN TABLE INDEPENDENCE ==="
)


# =========================================================
# GENERIC OPERATOR AUTHORITY
# =========================================================

check(
    "execution_operator_exists",
    "execution.operator" in renderer,
)

check(
    "grouped_operator_dispatch",
    "if(operator==='grouped_business_table')" in renderer,
)

check(
    "transaction_operator_dispatch",
    "if(operator==='transaction_table')" in renderer,
)

check(
    "raw_operator_dispatch",
    "if(operator==='raw_table')" in renderer,
)


# =========================================================
# GENERIC EXECUTION MUST PRECEDE / REPLACE LEGACY IDS
# =========================================================

grouped_pos = renderer.find(
    "if(operator==='grouped_business_table')"
)

transaction_pos = renderer.find(
    "if(operator==='transaction_table')"
)

raw_pos = renderer.find(
    "if(operator==='raw_table')"
)


customers_pos = renderer.find(
    "if(id==='table:customers')"
)

products_pos = renderer.find(
    "if(id==='table:products')"
)

sellers_pos = renderer.find(
    "if(id==='table:sellers')"
)

operations_pos = renderer.find(
    "if(id==='table:operations')"
)


check(
    "grouped_before_customers_legacy",
    (
        grouped_pos >= 0
        and (
            customers_pos < 0
            or grouped_pos < customers_pos
        )
    ),
)

check(
    "grouped_before_products_legacy",
    (
        grouped_pos >= 0
        and (
            products_pos < 0
            or grouped_pos < products_pos
        )
    ),
)

check(
    "grouped_before_sellers_legacy",
    (
        grouped_pos >= 0
        and (
            sellers_pos < 0
            or grouped_pos < sellers_pos
        )
    ),
)

check(
    "transaction_before_operations_legacy",
    (
        transaction_pos >= 0
        and (
            operations_pos < 0
            or transaction_pos < operations_pos
        )
    ),
)


# =========================================================
# GROUPED EXECUTION MUST BE SPEC DRIVEN
# =========================================================

grouped_block = renderer[
    grouped_pos:
    transaction_pos
]


check(
    "grouped_reads_grain_roles",
    "execution.grain_roles"
    in grouped_block,
)

check(
    "grouped_reads_fallback_grain_roles",
    "execution.fallback_grain_roles"
    in grouped_block,
)

check(
    "grouped_reads_label_roles",
    "execution.label_roles"
    in grouped_block,
)

check(
    "grouped_reads_measure_kpis",
    "execution.measure_kpis"
    in grouped_block,
)

check(
    "grouped_reads_sort_metric",
    "execution.sort_metric"
    in grouped_block,
)

check(
    "grouped_reads_limit",
    "execution.limit"
    in grouped_block,
)


# =========================================================
# DUPLICATE LABEL PROTECTION
# =========================================================

check(
    "active_grain_roles_exists",
    "activeGrainRoles"
    in grouped_block,
)

check(
    "effective_label_roles_exists",
    "effectiveLabelRoles"
    in grouped_block,
)

check(
    "label_excludes_active_grain",
    "!activeGrainRoles.includes(r)"
    in grouped_block,
)


# =========================================================
# TRANSACTION EXECUTION MUST BE SPEC DRIVEN
# =========================================================

transaction_end = (
    raw_pos
    if raw_pos > transaction_pos
    else len(renderer)
)

transaction_block = renderer[
    transaction_pos:
    transaction_end
]


check(
    "transaction_reads_columns",
    "execution.columns"
    in transaction_block,
)

check(
    "transaction_resolves_semantic_roles",
    ".map("
    in transaction_block
    and "role(r)"
    in transaction_block,
)

check(
    "transaction_uses_table_card",
    "tableCard("
    in transaction_block,
)


# =========================================================
# BUILDER DEFINES EXECUTION SEMANTICS
# =========================================================

check(
    "builder_execution_planner_exists",
    "_table_execution_spec"
    in builder,
)

check(
    "builder_grouped_business_table",
    '"grouped_business_table"'
    in builder,
)

check(
    "builder_transaction_table",
    '"transaction_table"'
    in builder,
)

check(
    "builder_raw_table",
    '"raw_table"'
    in builder,
)

check(
    "builder_attaches_execution",
    'c["execution"]'
    in builder,
)

check(
    "builder_execution_provenance",
    "table_execution_planner"
    in builder,
)


# =========================================================
# ARCHITECTURAL CONTRACT
# =========================================================

check(
    "renderer_does_not_require_customer_id_for_dispatch",
    (
        "if(operator==='grouped_business_table')"
        in renderer
    ),
)

check(
    "renderer_does_not_require_product_id_for_dispatch",
    (
        "if(operator==='grouped_business_table')"
        in renderer
    ),
)

check(
    "renderer_does_not_require_seller_id_for_dispatch",
    (
        "if(operator==='grouped_business_table')"
        in renderer
    ),
)

check(
    "renderer_does_not_require_operations_id_for_dispatch",
    (
        "if(operator==='transaction_table')"
        in renderer
    ),
)


# =========================================================
# LEGACY TABLE-ID DISPATCH MUST BE GONE
# =========================================================

check(
    "legacy_customers_dispatch_removed",
    "if(id==='table:customers')"
    not in renderer,
)

check(
    "legacy_products_dispatch_removed",
    "if(id==='table:products')"
    not in renderer,
)

check(
    "legacy_sellers_dispatch_removed",
    "if(id==='table:sellers')"
    not in renderer,
)

check(
    "legacy_operations_dispatch_removed",
    "if(id==='table:operations')"
    not in renderer,
)


# =========================================================
# GENERIC BLOCKS MUST NOT DEPEND ON KNOWN TABLE IDS
# =========================================================

check(
    "grouped_block_has_no_customers_id",
    "table:customers"
    not in grouped_block,
)

check(
    "grouped_block_has_no_products_id",
    "table:products"
    not in grouped_block,
)

check(
    "grouped_block_has_no_sellers_id",
    "table:sellers"
    not in grouped_block,
)

check(
    "transaction_block_has_no_operations_id",
    "table:operations"
    not in transaction_block,
)


print()
print(
    "PASS R10.13D.5 "
    "OPERATOR-DRIVEN TABLE INDEPENDENCE"
)

print(
    f"{len(checks)}/{len(checks)} PASS"
)
