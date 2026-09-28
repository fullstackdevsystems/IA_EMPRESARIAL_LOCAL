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
        "id":
            "binding-sales-valid",
        "rule_type":
            "row_filter",
        "target":
            "sales_valid",
        "priority":
            100,
        "active":
            True,
        "rule": {
            "id":
                "rule-sales-valid",
            "name":
                "VENTAS_VALIDAS",
            "expression":
                'Estatus != "CANCELADA"',
            "status":
                "VALIDADO",
            "active":
                True,
            "version":
                2,
            "source_type":
                "admin_console",
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
            dict(
                self.profile
            )
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

    def discover(
        self,
        profile,
    ):
        return [
            {
                "schema":
                    "dbo",
                "name":
                    "Clientes",
                "type":
                    "TABLE",
                "columns": [
                    {"name": "ClienteID"},
                    {"name": "Nombre"},
                ],
            },
            {
                "schema":
                    "dbo",
                "name":
                    "DetalleVentas",
                "type":
                    "TABLE",
                "columns": [
                    {"name": "DetalleVentaID"},
                    {"name": "VentaID"},
                    {"name": "ProductoID"},
                    {"name": "Cantidad"},
                    {"name": "Importe"},
                ],
            },
            {
                "schema":
                    "dbo",
                "name":
                    "Productos",
                "type":
                    "TABLE",
                "columns": [
                    {"name": "ProductoID"},
                    {"name": "Nombre"},
                ],
            },
            {
                "schema":
                    "dbo",
                "name":
                    "Ventas",
                "type":
                    "TABLE",
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
        self.sql.append(
            sql
        )

        self.parameters.append(
            list(
                parameters
                or []
            )
        )

        if "AS [Cliente]" in sql:
            rows = [
                (
                    "CLIENTE UNO",
                    850000.00,
                ),
                (
                    "CLIENTE DOS",
                    640000.00,
                ),
            ]

        elif "AS [Sucursal]" in sql:
            rows = [
                (
                    "MATRIZ",
                    930000.00,
                ),
                (
                    "NORTE",
                    720000.00,
                ),
            ]

        elif "AS [Producto]" in sql:
            rows = [
                (
                    "PASTA DE SOYA",
                    1077,
                    857204.15,
                ),
                (
                    "MAIZ",
                    979,
                    1544017.53,
                ),
            ]

        elif "AS [Operaciones]" in sql:
            rows = [
                (
                    "ANA",
                    45,
                ),
                (
                    "LUIS",
                    39,
                ),
            ]

        else:
            rows = [
                (
                    "ANA",
                    125000.00,
                ),
                (
                    "LUIS",
                    98000.00,
                ),
            ]

        return {
            "columns": [],
            "rows":
                rows,
        }


class Resolver:
    def __init__(
        self,
        payload,
    ):
        self.payload = payload
        self.calls = []

    def __call__(
        self,
        question,
    ):
        self.calls.append(
            question
        )

        return dict(
            self.payload
        )


def check(
    name,
    value,
):
    if not value:
        raise AssertionError(
            name
        )

    print(
        "PASS",
        name,
    )


def run_plan(
    *,
    name,
    question,
    payload,
):
    provider = FakeProvider()
    resolver = Resolver(
        payload
    )

    bridge = GovernedSqlAssistantBridge(
        store=FakeStore(),
        provider_factory=
            lambda: provider,
        semantic_plan_resolver=
            resolver,
    )

    result = bridge.resolve(
        scope=dict(SCOPE),
        analytic_bindings=
            ANALYTIC_BINDINGS,
        question=question,
    )

    check(
        name + "_resolved",
        isinstance(
            result,
            dict,
        ),
    )

    check(
        name + "_resolver_called",
        resolver.calls
        == [question],
    )

    check(
        name + "_governed_route",
        result["retrieval"][
            "fast_path"
        ]
        == "governed_sql",
    )

    check(
        name + "_sql_executed_once",
        len(
            provider.sql
        )
        == 1,
    )

    check(
        name + "_ventas_validas",
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
        name + "_llm_no_sql_authority",
        governance.get(
            "llm_sql_generation"
        )
        is False,
    )

    check(
        name + "_governed_executor",
        governance.get(
            "sql_execution_authority"
        )
        == "governed_executor",
    )

    check(
        name + "_semantic_source",
        governance.get(
            "semantic_plan_source"
        )
        == "llm_structured",
    )

    return (
        result,
        provider,
    )


#
# CUSTOMER BY SALES AMOUNT
#
result, provider = run_plan(
    name="customer_sales_amount",
    question=(
        "muéstrame quiénes son "
        "nuestros compradores más fuertes"
    ),
    payload={
        "domain": "sales",
        "entity": "customer",
        "operation": "ranking",
        "metric": "sales_amount",
        "direction": "desc",
        "limit": 10,
    },
)

check(
    "customer_sql_joins_clientes",
    "Clientes" in provider.sql[-1]
    and "ClienteID" in provider.sql[-1],
)

check(
    "customer_sql_aggregates_total",
    "SUM" in provider.sql[-1]
    and "[Total]" in provider.sql[-1],
)

check(
    "customer_answer_contains_result",
    "CLIENTE UNO"
    in result["answer"],
)


#
# BRANCH BY SALES AMOUNT
#
result, provider = run_plan(
    name="branch_sales_amount",
    question=(
        "qué punto de operación "
        "genera más facturación"
    ),
    payload={
        "domain": "sales",
        "entity": "branch",
        "operation": "ranking",
        "metric": "sales_amount",
        "direction": "desc",
        "limit": 10,
    },
)

check(
    "branch_sql_groups_sucursal",
    "[Sucursal]"
    in provider.sql[-1],
)

check(
    "branch_answer_contains_result",
    "MATRIZ"
    in result["answer"],
)


#
# PRODUCT BY QUANTITY
#
result, provider = run_plan(
    name="product_quantity",
    question=(
        "ordena los artículos "
        "por volumen desplazado"
    ),
    payload={
        "domain": "sales",
        "entity": "product",
        "operation": "ranking",
        "metric": "quantity",
        "direction": "desc",
        "limit": 10,
    },
)

check(
    "product_quantity_joins_detail",
    "DetalleVentas"
    in provider.sql[-1],
)

check(
    "product_quantity_joins_products",
    "Productos"
    in provider.sql[-1],
)

check(
    "product_quantity_uses_sum_quantity",
    "SUM" in provider.sql[-1]
    and "[Cantidad]" in provider.sql[-1],
)

check(
    "product_quantity_answer",
    "PASTA DE SOYA"
    in result["answer"],
)


#
# PRODUCT BY SALES AMOUNT
#
result, provider = run_plan(
    name="product_sales_amount",
    question=(
        "qué artículos aportan "
        "más valor vendido"
    ),
    payload={
        "domain": "sales",
        "entity": "product",
        "operation": "ranking",
        "metric": "sales_amount",
        "direction": "desc",
        "limit": 10,
    },
)

check(
    "product_amount_uses_importe",
    "[Importe]"
    in provider.sql[-1],
)


#
# SELLER BY NUMBER OF TRANSACTIONS
#
result, provider = run_plan(
    name="seller_transaction_count",
    question=(
        "quién cerró más "
        "operaciones comerciales"
    ),
    payload={
        "domain": "sales",
        "entity": "seller",
        "operation": "ranking",
        "metric": "transaction_count",
        "direction": "desc",
        "limit": 10,
    },
)

check(
    "seller_count_uses_count",
    "COUNT" in provider.sql[-1],
)

check(
    "seller_count_alias",
    "AS [Operaciones]"
    in provider.sql[-1],
)


#
# CUSTOMER BY NUMBER OF TRANSACTIONS
#
result, provider = run_plan(
    name="customer_transaction_count",
    question=(
        "qué clientes hacen "
        "más compras"
    ),
    payload={
        "domain": "sales",
        "entity": "customer",
        "operation": "ranking",
        "metric": "transaction_count",
        "direction": "desc",
        "limit": 10,
    },
)

check(
    "customer_count_uses_count",
    "COUNT" in provider.sql[-1],
)


#
# ASCENDING DIRECTION MUST BE GOVERNED TOO.
#
result, provider = run_plan(
    name="branch_bottom_sales",
    question=(
        "qué sucursal vende menos"
    ),
    payload={
        "domain": "sales",
        "entity": "branch",
        "operation": "ranking",
        "metric": "sales_amount",
        "direction": "asc",
        "limit": 10,
    },
)

check(
    "ascending_direction_compiled",
    " ASC"
    in provider.sql[-1],
)


#
# LIMIT MUST COME FROM THE VALIDATED PLAN,
# NEVER DIRECTLY FROM FREEFORM SQL.
#
result, provider = run_plan(
    name="seller_top_five",
    question=(
        "dame los cinco líderes "
        "de venta"
    ),
    payload={
        "domain": "sales",
        "entity": "seller",
        "operation": "ranking",
        "metric": "sales_amount",
        "direction": "desc",
        "limit": 5,
    },
)

check(
    "validated_limit_compiled",
    "TOP (5)"
    in provider.sql[-1],
)


#
# UNSUPPORTED METRICS MUST REMAIN FAIL-CLOSED.
#
provider_bad = FakeProvider()

bad_bridge = GovernedSqlAssistantBridge(
    store=FakeStore(),
    provider_factory=
        lambda: provider_bad,
    semantic_plan_resolver=
        Resolver(
            {
                "domain": "sales",
                "entity": "seller",
                "operation": "ranking",
                "metric": "profit",
                "direction": "desc",
                "limit": 10,
            }
        ),
)

bad_result = bad_bridge.resolve(
    scope=dict(SCOPE),
    analytic_bindings=
        ANALYTIC_BINDINGS,
    question=(
        "quién deja más utilidad"
    ),
)

check(
    "unsupported_metric_rejected",
    bad_result is None,
)

check(
    "unsupported_metric_executes_no_sql",
    provider_bad.sql
    == [],
)


#
# OUT-OF-RANGE LIMIT MUST REMAIN FAIL-CLOSED.
#
provider_limit = FakeProvider()

limit_bridge = GovernedSqlAssistantBridge(
    store=FakeStore(),
    provider_factory=
        lambda: provider_limit,
    semantic_plan_resolver=
        Resolver(
            {
                "domain": "sales",
                "entity": "seller",
                "operation": "ranking",
                "metric": "sales_amount",
                "direction": "desc",
                "limit": 5000,
            }
        ),
)

limit_result = limit_bridge.resolve(
    scope=dict(SCOPE),
    analytic_bindings=
        ANALYTIC_BINDINGS,
    question=(
        "dame miles de vendedores"
    ),
)

check(
    "unsafe_limit_rejected",
    limit_result is None,
)

check(
    "unsafe_limit_executes_no_sql",
    provider_limit.sql
    == [],
)


print(
    "R10_31_SEMANTIC_ANALYTICS_MATRIX=PASS"
)
