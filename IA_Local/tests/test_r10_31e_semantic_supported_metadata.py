from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(
        0,
        str(SCRIPTS),
    )


from enterprise_ai.governed_sql_assistant import (
    GovernedSqlAssistantBridge,
)


def check(
    name,
    condition,
):
    if not condition:
        raise AssertionError(
            name
        )

    print(
        "PASS",
        name,
    )


base = {
    "domain": "sales",
    "entity": "customer",
    "operation": "ranking",
    "metric": "sales_amount",
    "direction": "desc",
    "limit": 10,
}


plain = (
    GovernedSqlAssistantBridge
    ._validated_external_semantic_plan(
        dict(
            base
        )
    )
)

check(
    "legacy_six_key_plan_preserved",
    plain is not None,
)


supported_true = dict(
    base
)

supported_true[
    "supported"
] = True

plan = (
    GovernedSqlAssistantBridge
    ._validated_external_semantic_plan(
        supported_true
    )
)

check(
    "supported_true_plan_accepted",
    plan is not None,
)

check(
    "supported_true_entity_preserved",
    plan.entity
    == "customer",
)

check(
    "supported_metadata_not_promoted",
    "supported"
    not in plan.as_dict(),
)


check(
    "supported_false_fails_closed",
    GovernedSqlAssistantBridge
    ._validated_external_semantic_plan(
        {
            "supported":
                False,
        }
    )
    is None,
)


bad_type = dict(
    base
)

bad_type[
    "supported"
] = "true"

check(
    "supported_non_boolean_fails_closed",
    GovernedSqlAssistantBridge
    ._validated_external_semantic_plan(
        bad_type
    )
    is None,
)


sql_payload = dict(
    base
)

sql_payload[
    "supported"
] = True

sql_payload[
    "sql"
] = (
    "DROP TABLE dbo.Ventas"
)

check(
    "sql_key_still_fails_closed",
    GovernedSqlAssistantBridge
    ._validated_external_semantic_plan(
        sql_payload
    )
    is None,
)


table_payload = dict(
    base
)

table_payload[
    "supported"
] = True

table_payload[
    "table"
] = "dbo.Ventas"

check(
    "physical_table_key_still_fails_closed",
    GovernedSqlAssistantBridge
    ._validated_external_semantic_plan(
        table_payload
    )
    is None,
)


column_payload = dict(
    base
)

column_payload[
    "supported"
] = True

column_payload[
    "column"
] = "Total"

check(
    "physical_column_key_still_fails_closed",
    GovernedSqlAssistantBridge
    ._validated_external_semantic_plan(
        column_payload
    )
    is None,
)


period_payload = dict(
    base
)

period_payload[
    "supported"
] = True

period_payload[
    "period"
] = {
        "kind": "month",
        "year": 2026,
        "month": 8,
}

period_plan = (
    GovernedSqlAssistantBridge
    ._validated_external_semantic_plan(
        period_payload
    )
)

check(
    "supported_true_period_plan_accepted",
    period_plan is not None,
)

check(
    "supported_true_period_still_validated",
    period_plan.period
    == {
        "kind":
            "month",
        "start":
            "2026-08-01",
        "end_exclusive":
            "2026-09-01",
    },
)


unsafe_period = dict(
    base
)

unsafe_period[
    "supported"
] = True

unsafe_period[
    "period"
] = {
        "kind": "month",
        "year": 2026,
        "month": 8,
        "sql": "SELECT * FROM dbo.Ventas",
}

check(
    "supported_true_cannot_bypass_period_allowlist",
    GovernedSqlAssistantBridge
    ._validated_external_semantic_plan(
        unsafe_period
    )
    is None,
)


print(
    "R10_31_SUPPORTED_METADATA_CONTRACT=PASS"
)


# Exact real-model shape observed during P6C-R2:
# valid semantic ranking plus supported=true, but no limit.
real_model_without_limit = {
    "domain": "sales",
    "entity": "customer",
    "operation": "ranking",
    "metric": "sales_amount",
    "direction": "desc",
    "supported": True,
}

real_model_without_limit_plan = (
    GovernedSqlAssistantBridge
    ._validated_external_semantic_plan(
        real_model_without_limit
    )
)

check(
    "missing_limit_defaults_to_ten",
    real_model_without_limit_plan is not None
    and real_model_without_limit_plan.limit == 10,
)


explicit_bad_limit = {
    "domain": "sales",
    "entity": "customer",
    "operation": "ranking",
    "metric": "sales_amount",
    "direction": "desc",
    "limit": 1000,
    "supported": True,
}

check(
    "explicit_unsafe_limit_still_fails_closed",
    GovernedSqlAssistantBridge
    ._validated_external_semantic_plan(
        explicit_bad_limit
    )
    is None,
)
