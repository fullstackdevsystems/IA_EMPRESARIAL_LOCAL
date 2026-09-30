from __future__ import annotations

import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )

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
            "expression":
                'Estatus != "CANCELADA"',
            "status": "VALIDADO",
            "active": True,
            "version": 2,
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

    def list(
        self,
        scope,
    ):
        assert (
            scope["company_id"]
            == "company-a"
        )

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

    def discover(
        self,
        profile,
    ):
        self.discovery_calls += 1

        objects = [
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
                "name": "DetalleVentas",
                "type": "TABLE",
                "columns": [
                    {"name": "DetalleVentaID"},
                    {"name": "VentaID"},
                    {"name": "ProductoID"},
                    {"name": "Cantidad"},
                    {"name": "PrecioUnitario"},
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
                    {"name": "Folio"},
                    {"name": "ClienteID"},
                    {"name": "FechaVenta"},
                    {"name": "Vendedor"},
                    {"name": "Sucursal"},
                    {"name": "Estatus"},
                    {"name": "Subtotal"},
                    {"name": "IVA"},
                    {"name": "Total"},
                ],
            },
        ]

        allowed = {
            str(value).lower()
            for value in (
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
        self.sql.append(
            sql
        )

        self.parameters.append(
            list(
                parameters
                or []
            )
        )

        return {
            "columns": [
                "_VentaID",
                "_DetalleVentaID",
                "Vendedor",
                "FechaVenta",
                "Folio",
                "Cliente",
                "Sucursal",
                "Estatus",
                "Subtotal",
                "IVA",
                "Total",
                "Producto",
                "Cantidad",
                "PrecioUnitario",
                "Importe",
            ],
            "rows": [
                (
                    1001,
                    5001,
                    "Andres Legarreta",
                    "2026-09-15",
                    "F-1001",
                    "Cliente Uno",
                    "Matriz",
                    "PAGADA",
                    100.00,
                    16.00,
                    116.00,
                    "Producto Uno",
                    2.00,
                    50.00,
                    100.00,
                ),
            ],
        }


def make_bridge():
    provider = FakeProvider()

    bridge = GovernedSqlAssistantBridge(
        store=FakeStore(),
        provider_factory=
            lambda: provider,
    )

    return (
        bridge,
        provider,
    )


def run_question(
    question: str,
):
    bridge, provider = (
        make_bridge()
    )

    result = bridge.resolve(
        scope=dict(SCOPE),
        analytic_bindings=
            ANALYTIC_BINDINGS,
        question=question,
    )

    return (
        result,
        provider,
    )


def assert_governed(
    result,
):
    assert isinstance(
        result,
        dict,
    )

    assert (
        result["retrieval"][
            "fast_path"
        ]
        == "governed_sql"
    )

    assert (
        result["retrieval"][
            "structured"
        ]
        is True
    )

    governance = (
        result.get(
            "governance",
            {},
        )
    )

    assert (
        governance.get(
            "read_only"
        )
        is True
    )

    assert (
        governance.get(
            "allowlist_enforced"
        )
        is True
    )

    assert (
        governance.get(
            "fail_closed"
        )
        is True
    )

    assert (
        governance.get(
            "business_row_filter_applied"
        )
        is True
    )

    assert (
        governance.get(
            "llm_sql_generation"
        )
        is False
    )


def test_seller_detail_is_parameterized():
    result, provider = run_question(
        "dame las ventas detalladas "
        "de Andres Legarreta"
    )

    assert_governed(
        result
    )

    assert len(
        provider.sql
    ) == 1

    sql = provider.sql[0]

    assert "[Vendedor]" in sql
    assert "= ?" in sql

    assert (
        "Andres Legarreta"
        not in sql
    )

    assert (
        provider.parameters[0]
        == [
            "CANCELADA",
            "Andres Legarreta",
        ]
    )

    plan = result[
        "governance"
    ][
        "semantic_analytics_plan"
    ]

    assert (
        plan["seller"]
        == "Andres Legarreta"
    )

    assert (
        plan["limit"]
        == 100
    )


def test_seller_month_is_start_inclusive_end_exclusive():
    result, provider = run_question(
        "dame las ventas de Andres Legarreta "
        "de septiembre de 2026"
    )

    assert_governed(
        result
    )

    sql = provider.sql[0]

    assert "[FechaVenta]" in sql
    assert ">= ?" in sql
    assert "< ?" in sql

    assert (
        provider.parameters[0]
        == [
            "CANCELADA",
            "Andres Legarreta",
            "2026-09-01",
            "2026-10-01",
        ]
    )

    plan = result[
        "governance"
    ][
        "semantic_analytics_plan"
    ]

    assert (
        plan["period"]["start"]
        == "2026-09-01"
    )

    assert (
        plan["period"][
            "end_exclusive"
        ]
        == "2026-10-01"
    )


def test_current_month_detail_is_parameterized():
    result, provider = run_question(
        "muestrame las ventas "
        "detalladas de este mes"
    )

    assert_governed(
        result
    )

    today = date.today()

    start = date(
        today.year,
        today.month,
        1,
    )

    if today.month == 12:
        end = date(
            today.year + 1,
            1,
            1,
        )
    else:
        end = date(
            today.year,
            today.month + 1,
            1,
        )

    assert (
        provider.parameters[0]
        == [
            "CANCELADA",
            start.isoformat(),
            end.isoformat(),
        ]
    )


def test_explicit_limit_controls_sql_and_presentation():
    result, provider = run_question(
        "dame 25 ventas detalladas "
        "de Andres Legarreta"
    )

    assert_governed(
        result
    )

    sql = provider.sql[0]

    assert (
        "TOP (25)"
        in sql
    )

    assert (
        "hasta 25 renglones"
        in result["answer"]
    )

    plan = result[
        "governance"
    ][
        "semantic_analytics_plan"
    ]

    assert (
        plan["limit"]
        == 25
    )


def test_invalid_limit_fails_closed_without_sql():
    result, provider = run_question(
        "dame 501 ventas detalladas "
        "de Andres Legarreta"
    )

    assert isinstance(
        result,
        dict,
    )

    assert (
        result["retrieval"][
            "fast_path"
        ]
        == "governed_sql_blocked"
    )

    assert (
        result["governance"][
            "reason"
        ]
        == "SALES_DETAIL_LIMIT_INVALID"
    )

    assert (
        provider.sql
        == []
    )


def test_seller_injection_fails_closed_without_sql():
    result, provider = run_question(
        "dame las ventas detalladas "
        "de Andres' OR 1=1--"
    )

    assert isinstance(
        result,
        dict,
    )

    assert (
        result["retrieval"][
            "fast_path"
        ]
        == "governed_sql_blocked"
    )

    assert (
        result["governance"][
            "reason"
        ]
        == "SALES_DETAIL_SELLER_INVALID"
    )

    assert (
        provider.sql
        == []
    )


def test_simple_sales_list_uses_header_mode():
    result, provider = run_question(
        "lista de ventas"
    )

    assert isinstance(
        result,
        dict,
    )

    assert (
        result["retrieval"][
            "fast_path"
        ]
        == "governed_sql"
    )

    assert (
        result["retrieval"][
            "structured"
        ]
        is True
    )

    assert len(
        provider.sql
    ) == 1

    sql = provider.sql[0]

    assert (
        "DetalleVentas"
        not in sql
    )

    assert (
        "Productos"
        not in sql
    )

    assert (
        provider.parameters[0]
        == ["CANCELADA"]
    )

    plan = result[
        "governance"
    ][
        "semantic_analytics_plan"
    ]

    assert (
        plan["detail_level"]
        == "sale"
    )


def test_products_by_seller_uses_line_item_mode():
    result, provider = run_question(
        "que productos vendio "
        "Andres Legarreta"
    )

    assert isinstance(
        result,
        dict,
    )

    assert (
        result["retrieval"][
            "fast_path"
        ]
        == "governed_sql"
    )

    assert (
        result["retrieval"][
            "structured"
        ]
        is True
    )

    assert len(
        provider.sql
    ) == 1

    sql = provider.sql[0]

    assert (
        "DetalleVentas"
        in sql
    )

    assert (
        "Productos"
        in sql
    )

    assert (
        "Andres Legarreta"
        not in sql
    )

    assert (
        provider.parameters[0]
        == [
            "CANCELADA",
            "Andres Legarreta",
        ]
    )

    plan = result[
        "governance"
    ][
        "semantic_analytics_plan"
    ]

    assert (
        plan["detail_level"]
        == "line_item"
    )

    assert (
        plan["seller"]
        == "Andres Legarreta"
    )
