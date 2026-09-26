from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

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
    def __init__(
        self,
        allowed_tables=None,
    ):
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
            "allowed_tables":
                list(
                    allowed_tables
                    or [
                        "dbo.Clientes",
                        "dbo.DetalleVentas",
                        "dbo.Productos",
                        "dbo.Ventas",
                    ]
                ),
            "scope":
                dict(SCOPE),
        }

    def list(self, scope):
        assert (
            scope["company_id"]
            == "company-a"
        )

        return [
            dict(self.profile)
        ]

    def get(
        self,
        scope,
        connection_id,
    ):
        assert (
            scope["company_id"]
            == "company-a"
        )

        assert (
            connection_id
            == "connection-a"
        )

        return dict(
            self.profile
        )


class FakeProvider:
    def __init__(self):
        self.sql = []
        self.parameters = []
        self.discovery_calls = 0

    def discover(self, profile):
        self.discovery_calls += 1

        objects = [
            {
                "schema": "dbo",
                "name": "Clientes",
                "type": "TABLE",
                "columns": [
                    {
                        "name":
                            "ClienteID"
                    },
                    {
                        "name":
                            "Nombre"
                    },
                ],
            },
            {
                "schema": "dbo",
                "name":
                    "DetalleVentas",
                "type": "TABLE",
                "columns": [
                    {
                        "name":
                            "DetalleVentaID"
                    },
                    {
                        "name":
                            "VentaID"
                    },
                    {
                        "name":
                            "ProductoID"
                    },
                    {
                        "name":
                            "Cantidad"
                    },
                    {
                        "name":
                            "Importe"
                    },
                ],
            },
            {
                "schema": "dbo",
                "name": "Productos",
                "type": "TABLE",
                "columns": [
                    {
                        "name":
                            "ProductoID"
                    },
                    {
                        "name":
                            "Nombre"
                    },
                    {
                        "name":
                            "Categoria"
                    },
                ],
            },
            {
                "schema": "dbo",
                "name": "Ventas",
                "type": "TABLE",
                "columns": [
                    {
                        "name":
                            "VentaID"
                    },
                    {
                        "name":
                            "FechaVenta"
                    },
                    {
                        "name":
                            "Estatus"
                    },
                ],
            },
        ]

        allowed = {
            str(x).lower()
            for x in (
                profile.get(
                    "allowed_tables"
                )
                or []
            )
        }

        return [
            item
            for item in objects
            if (
                (
                    f"{item['schema']}."
                    f"{item['name']}"
                ).lower()
                in allowed
            )
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
            list(
                parameters
                or []
            )
        )

        if "COUNT_BIG" in sql:
            return {
                "columns": [
                    "TOTAL_REGISTROS"
                ],
                "rows": [
                    (7,)
                ],
            }

        return {
            "columns": [
                "Producto",
                "CantidadVendida",
                "ImporteVendido",
            ],
            "rows": [
                (
                    "Melaza",
                    150,
                    32000,
                ),
                (
                    "Maiz",
                    120,
                    28000,
                ),
                (
                    "Pasta",
                    95,
                    24000,
                ),
            ],
        }


def check(name, value):
    if not value:
        raise AssertionError(name)

    print("PASS", name)


provider = FakeProvider()

bridge = GovernedSqlAssistantBridge(
    store=FakeStore(),
    provider_factory=lambda: provider,
)

question = (
    "que productos se han "
    "vendido mas?"
)

result = bridge.resolve(
    scope=dict(SCOPE),
    analytic_bindings=
        ANALYTIC_BINDINGS,
    question=question,
)

check(
    "top_products_answered",
    isinstance(result, dict),
)

check(
    "top_products_structured",
    result["retrieval"][
        "structured"
    ]
    is True,
)

check(
    "top_products_governed_route",
    result["retrieval"][
        "fast_path"
    ]
    == "governed_sql",
)

check(
    "top_products_answer_contains_result",
    "Melaza" in result["answer"]
    and "150" in result["answer"],
)

check(
    "top_products_explicit_metric",
    "por cantidad"
    in result["answer"],
)

sql = provider.sql[-1]

check(
    "top_products_join",
    "JOIN [dbo].[Productos] AS p"
    in sql,
)

check(
    "top_products_sales_header_join",
    "JOIN [dbo].[Ventas] AS v"
    in sql
    and (
        "v.[VentaID] "
        "= d.[VentaID]"
    )
    in sql,
)

check(
    "top_products_validated_status_filter",
    (
        "WHERE "
        "(v.[Estatus] <> ?)"
    )
    in sql,
)

check(
    "top_products_filter_parameterized",
    provider.parameters[-1]
    == ["CANCELADA"],
)

check(
    "top_products_detail_source",
    "FROM [dbo].[DetalleVentas] AS d"
    in sql,
)

check(
    "top_products_sum_quantity",
    "SUM(d.[Cantidad])"
    in sql,
)

check(
    "top_products_sum_amount",
    "SUM(d.[Importe])"
    in sql,
)

check(
    "top_products_group_by",
    "GROUP BY"
    in sql,
)

check(
    "top_products_order_by_quantity",
    (
        "ORDER BY "
        "SUM(d.[Cantidad]) "
        "DESC"
    )
    in sql,
)

check(
    "top_products_only_allowed_objects",
    "[dbo].[DetalleVentas]"
    in sql
    and "[dbo].[Productos]"
    in sql
    and "[dbo].[Ventas]"
    in sql
    and "[dbo].[Clientes]"
    not in sql,
)

check(
    "top_products_governance",
    result["governance"][
        "allowlist_enforced"
    ]
    is True
    and result["governance"][
        "read_only"
    ]
    is True
    and result["governance"][
        "llm_sql_generation"
    ]
    is False
    and result["governance"][
        "business_row_filter_applied"
    ]
    is True
    and result["governance"][
        "business_semantics_authority"
    ]
    == "validated_analytic_row_filter",
)

ungoverned_provider = (
    FakeProvider()
)

ungoverned_bridge = (
    GovernedSqlAssistantBridge(
        store=FakeStore(),
        provider_factory=(
            lambda:
                ungoverned_provider
        ),
    )
)

ungoverned = (
    ungoverned_bridge.resolve(
        scope=dict(SCOPE),
        analytic_bindings=[],
        question=question,
    )
)

check(
    "top_products_without_validated_sales_rule_fails_closed",
    isinstance(
        ungoverned,
        dict,
    )
    and ungoverned[
        "retrieval"
    ][
        "structured"
    ]
    is False
    and ungoverned[
        "retrieval"
    ][
        "fast_path"
    ]
    == "governed_sql_blocked",
)

check(
    "top_products_without_validated_sales_rule_executes_no_sql",
    len(
        ungoverned_provider.sql
    )
    == 0,
)


explicit = bridge.resolve(
    scope=dict(SCOPE),
    analytic_bindings=
        ANALYTIC_BINDINGS,
    question=(
        "revisa la base de datos "
        "y dime que productos "
        "se han vendido mas?"
    ),
)

check(
    "explicit_database_wording_answered",
    isinstance(explicit, dict)
    and "Melaza"
    in explicit["answer"],
)

revenue = bridge.resolve(
    scope=dict(SCOPE),
    analytic_bindings=
        ANALYTIC_BINDINGS,
    question=(
        "que productos tienen "
        "mayor importe vendido?"
    ),
)

check(
    "revenue_intent_answered",
    isinstance(revenue, dict),
)

check(
    "revenue_orders_by_amount",
    (
        "ORDER BY "
        "SUM(d.[Importe]) "
        "DESC"
    )
    in provider.sql[-1],
)

count_result = bridge.resolve(
    scope=dict(SCOPE),
    analytic_bindings=
        ANALYTIC_BINDINGS,
    question=(
        "cuantos registros hay "
        "en dbo.Productos?"
    ),
)

check(
    "legacy_count_preserved",
    count_result["answer"]
    == "Total de registros: 7",
)

execution_count = len(
    provider.sql
)

unrelated = bridge.resolve(
    scope=dict(SCOPE),
    analytic_bindings=
        ANALYTIC_BINDINGS,
    question=(
        "como calculamos "
        "la utilidad?"
    ),
)

check(
    "unrelated_question_not_claimed",
    unrelated is None,
)

check(
    "unrelated_question_no_sql",
    len(provider.sql)
    == execution_count,
)

missing_provider = (
    FakeProvider()
)

missing_bridge = (
    GovernedSqlAssistantBridge(
        store=FakeStore(
            allowed_tables=[
                "dbo.Productos",
            ]
        ),
        provider_factory=(
            lambda:
                missing_provider
        ),
    )
)

missing = missing_bridge.resolve(
    scope=dict(SCOPE),
    analytic_bindings=
        ANALYTIC_BINDINGS,
    question=question,
)

check(
    "missing_relational_authority_fails_closed",
    missing is None,
)

check(
    "missing_relational_authority_no_query",
    len(missing_provider.sql)
    == 0,
)

print(
    "R10_30A_GOVERNED_SQL_TOP_PRODUCTS=PASS"
)
