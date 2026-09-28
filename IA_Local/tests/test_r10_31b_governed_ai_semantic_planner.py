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


SCOPE = {
    "company_id": "company-a",
    "user_id": "sql-admin",
    "business_unit": None,
    "branch": None,
}


ANALYTIC_BINDINGS = [
    {
        "id": "binding-sales-valid",
        "rule_type": "row_filter",
        "target": "sales_valid",
        "priority": 100,
        "active": True,
        "rule": {
            "id": "rule-sales-valid",
            "name": "VENTAS_VALIDAS",
            "expression": 'Estatus != "CANCELADA"',
            "status": "VALIDADO",
            "active": True,
            "version": 2,
            "source_type": "admin_console",
            "source_ref":
                "r10.30-business-semantics",
        },
    },
]


class FakeStore:
    def __init__(self):
        self.profile = {
            "connection_id":
                "connection-a",
            "display_name":
                "Ventas_Pruebas",
            "database":
                "DB_VENTAS",
            "enabled":
                True,
            "read_only":
                True,
            "status":
                "ACTIVE",
            "timeout_seconds":
                30,
            "allowed_tables": [
                "dbo.Clientes",
                "dbo.DetalleVentas",
                "dbo.Productos",
                "dbo.Ventas",
            ],
            "scope":
                dict(SCOPE),
        }

    def list(self, scope):
        return [
            dict(self.profile)
        ]

    def get(
        self,
        scope,
        connection_id,
    ):
        return dict(
            self.profile
        )


class FakeProvider:
    def __init__(self):
        self.sql = []
        self.parameters = []

    def discover(self, profile):
        return [
            {
                "schema": "dbo",
                "name": "Clientes",
                "type": "TABLE",
                "columns": [
                    {"name": "ClienteID"},
                    {"name": "Nombre"},
                ],
            },
            {
                "schema": "dbo",
                "name":
                    "DetalleVentas",
                "type": "TABLE",
                "columns": [
                    {"name": "DetalleVentaID"},
                    {"name": "VentaID"},
                    {"name": "ProductoID"},
                    {"name": "Cantidad"},
                    {"name": "Importe"},
                ],
            },
            {
                "schema": "dbo",
                "name": "Productos",
                "type": "TABLE",
                "columns": [
                    {"name": "ProductoID"},
                    {"name": "Nombre"},
                ],
            },
            {
                "schema": "dbo",
                "name": "Ventas",
                "type": "TABLE",
                "columns": [
                    {"name": "VentaID"},
                    {"name": "ClienteID"},
                    {"name": "FechaVenta"},
                    {"name": "Vendedor"},
                    {"name": "Sucursal"},
                    {"name": "Estatus"},
                    {"name": "Total"},
                ],
            },
        ]

    def execute(
        self,
        profile,
        sql,
        parameters,
        timeout_seconds,
    ):
        self.sql.append(sql)
        self.parameters.append(
            list(parameters or [])
        )

        return {
            "columns": [
                "Vendedor",
                "ImporteVendido",
            ],
            "rows": [
                (
                    "ANA",
                    125000.00,
                ),
                (
                    "LUIS",
                    98000.00,
                ),
            ],
        }


def check(
    name,
    value,
):
    if not value:
        raise AssertionError(name)

    print(
        "PASS",
        name,
    )


class FakeSemanticResolver:
    def __init__(
        self,
        payload=None,
        raises=False,
    ):
        self.payload = payload
        self.raises = raises
        self.calls = []

    def __call__(
        self,
        question,
    ):
        self.calls.append(
            question
        )

        if self.raises:
            raise RuntimeError(
                "simulated semantic model failure"
            )

        return self.payload


#
# 1. Novel wording deliberately not covered by the
# deterministic seller phrases from P2.
#
provider = FakeProvider()

ai_resolver = FakeSemanticResolver(
    {
        "domain": "sales",
        "entity": "seller",
        "operation": "ranking",
        "metric": "sales_amount",
        "direction": "desc",
        "limit": 10,
    }
)

bridge = GovernedSqlAssistantBridge(
    store=FakeStore(),
    provider_factory=lambda: provider,
    semantic_plan_resolver=
        ai_resolver,
)

question = (
    "dime quién encabeza "
    "la facturación del equipo comercial"
)

result = bridge.resolve(
    scope=dict(SCOPE),
    analytic_bindings=
        ANALYTIC_BINDINGS,
    question=question,
)

check(
    "ai_semantic_question_resolved",
    isinstance(
        result,
        dict,
    ),
)

check(
    "ai_semantic_resolver_called",
    ai_resolver.calls
    == [question],
)

check(
    "ai_semantic_governed_route",
    result["retrieval"][
        "fast_path"
    ]
    == "governed_sql",
)

check(
    "ai_semantic_real_data_returned",
    "ANA"
    in result["answer"],
)

check(
    "ai_semantic_sql_executed",
    len(provider.sql)
    == 1,
)

check(
    "ai_semantic_sales_rule_applied",
    provider.parameters[-1]
    == ["CANCELADA"],
)

governance = dict(
    result.get(
        "governance"
    )
    or {}
)

check(
    "ai_semantic_source_declared",
    governance.get(
        "semantic_plan_source"
    )
    == "llm_structured",
)

check(
    "ai_semantic_llm_has_no_sql_generation",
    governance.get(
        "llm_sql_generation"
    )
    is False,
)

check(
    "ai_semantic_llm_has_no_execution_authority",
    governance.get(
        "sql_execution_authority"
    )
    == "governed_executor",
)


#
# 2. Model output containing SQL must be rejected.
#
provider_invalid = FakeProvider()

invalid_resolver = FakeSemanticResolver(
    {
        "domain": "sales",
        "entity": "seller",
        "operation": "ranking",
        "metric": "sales_amount",
        "direction": "desc",
        "limit": 10,
        "sql":
            "SELECT * FROM dbo.Ventas",
    }
)

invalid_bridge = GovernedSqlAssistantBridge(
    store=FakeStore(),
    provider_factory=
        lambda: provider_invalid,
    semantic_plan_resolver=
        invalid_resolver,
)

invalid_result = invalid_bridge.resolve(
    scope=dict(SCOPE),
    analytic_bindings=
        ANALYTIC_BINDINGS,
    question=(
        "dime el líder comercial "
        "de la compañía"
    ),
)

check(
    "ai_sql_injection_payload_rejected",
    invalid_result is None,
)

check(
    "ai_sql_injection_executes_no_sql",
    provider_invalid.sql
    == [],
)


#
# 3. Unsupported semantic vocabulary must fail closed.
#
provider_unknown = FakeProvider()

unknown_resolver = FakeSemanticResolver(
    {
        "domain": "finance",
        "entity": "bank_account",
        "operation": "ranking",
        "metric": "balance",
        "direction": "desc",
        "limit": 10,
    }
)

unknown_bridge = GovernedSqlAssistantBridge(
    store=FakeStore(),
    provider_factory=
        lambda: provider_unknown,
    semantic_plan_resolver=
        unknown_resolver,
)

unknown_result = unknown_bridge.resolve(
    scope=dict(SCOPE),
    analytic_bindings=
        ANALYTIC_BINDINGS,
    question=(
        "quién tiene "
        "el mayor saldo"
    ),
)

check(
    "unsupported_ai_plan_rejected",
    unknown_result is None,
)

check(
    "unsupported_ai_plan_executes_no_sql",
    provider_unknown.sql
    == [],
)


#
# 4. Model outage must not fall through into arbitrary SQL.
#
provider_error = FakeProvider()

error_resolver = FakeSemanticResolver(
    raises=True,
)

error_bridge = GovernedSqlAssistantBridge(
    store=FakeStore(),
    provider_factory=
        lambda: provider_error,
    semantic_plan_resolver=
        error_resolver,
)

error_result = error_bridge.resolve(
    scope=dict(SCOPE),
    analytic_bindings=
        ANALYTIC_BINDINGS,
    question=(
        "muéstrame al líder "
        "de facturación comercial"
    ),
)

check(
    "ai_planner_failure_fails_closed",
    error_result is None,
)

check(
    "ai_planner_failure_executes_no_sql",
    provider_error.sql
    == [],
)


#
# 5. Existing deterministic route must remain usable
# without invoking the model.
#
provider_direct = FakeProvider()

direct_resolver = FakeSemanticResolver(
    {
        "domain": "invalid",
    }
)

direct_bridge = GovernedSqlAssistantBridge(
    store=FakeStore(),
    provider_factory=
        lambda: provider_direct,
    semantic_plan_resolver=
        direct_resolver,
)

direct_result = direct_bridge.resolve(
    scope=dict(SCOPE),
    analytic_bindings=
        ANALYTIC_BINDINGS,
    question=(
        "que persona "
        "ha vendido mas?"
    ),
)

check(
    "deterministic_seller_path_preserved",
    isinstance(
        direct_result,
        dict,
    ),
)

check(
    "deterministic_path_does_not_need_llm",
    direct_resolver.calls
    == [],
)

check(
    "deterministic_path_executes_governed_sql",
    len(provider_direct.sql)
    == 1,
)


print(
    "R10_31_AI_SEMANTIC_PLANNER_CONTRACT=PASS"
)
