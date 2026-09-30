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
    def __init__(
        self,
        header_only=False,
    ):
        self.header_only = (
            header_only
        )

        self.sql = []
        self.parameters = []

    def discover(
        self,
        profile,
    ):
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

        if not self.header_only:
            objects.extend(
                [
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
                ]
            )

        return objects

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

        if "_DetalleVentaID" in sql:
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

        return {
            "columns": [
                "_VentaID",
                "Vendedor",
                "FechaVenta",
                "Folio",
                "Cliente",
                "Sucursal",
                "Estatus",
                "Subtotal",
                "IVA",
                "Total",
            ],
            "rows": [
                (
                    1001,
                    "Andres Legarreta",
                    "2026-09-15",
                    "F-1001",
                    "Cliente Uno",
                    "Matriz",
                    "PAGADA",
                    100.00,
                    16.00,
                    116.00,
                ),
            ],
        }


def run_question(
    question,
    *,
    header_only=False,
):
    provider = FakeProvider(
        header_only=header_only,
    )

    bridge = GovernedSqlAssistantBridge(
        store=FakeStore(),
        provider_factory=
            lambda: provider,
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
    expected_mode,
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

    plan = governance[
        "semantic_analytics_plan"
    ]

    assert (
        plan["detail_level"]
        == expected_mode
    )


def test_q8_simple_sales_list_uses_header_mode():
    result, provider = run_question(
        "lista de ventas",
        header_only=True,
    )

    assert_governed(
        result,
        "sale",
    )

    assert len(
        provider.sql
    ) == 1

    sql = provider.sql[0]

    assert "dbo].[Ventas" in sql
    assert "dbo].[Clientes" in sql
    assert "DetalleVentas" not in sql
    assert "Productos" not in sql
    assert "_DetalleVentaID" not in sql

    assert (
        provider.parameters[0]
        == ["CANCELADA"]
    )

    assert (
        "F-1001"
        in result["answer"]
    )

    assert (
        result["answer"].count(
            "Total 116.0"
        )
        == 1
    )


def test_q6_products_by_seller_uses_line_item_mode():
    result, provider = run_question(
        "que productos vendio "
        "Andres Legarreta"
    )

    assert_governed(
        result,
        "line_item",
    )

    sql = provider.sql[0]

    assert "DetalleVentas" in sql
    assert "Productos" in sql
    assert "_DetalleVentaID" in sql
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

    assert (
        "Producto Uno"
        in result["answer"]
    )

    assert (
        result["answer"].count(
            "Total 116.0"
        )
        == 1
    )


def test_plain_seller_sales_uses_header_mode():
    result, provider = run_question(
        "dame las ventas "
        "de Andres Legarreta"
    )

    assert_governed(
        result,
        "sale",
    )

    assert (
        provider.parameters[0]
        == [
            "CANCELADA",
            "Andres Legarreta",
        ]
    )

    assert (
        "DetalleVentas"
        not in provider.sql[0]
    )


def test_plain_period_sales_uses_header_mode():
    result, provider = run_question(
        "dame las ventas de este mes"
    )

    assert_governed(
        result,
        "sale",
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


def test_plain_explicit_limit_uses_header_mode():
    result, provider = run_question(
        "dame 25 ventas"
    )

    assert_governed(
        result,
        "sale",
    )

    assert (
        "TOP (25)"
        in provider.sql[0]
    )

    assert (
        result["governance"][
            "semantic_analytics_plan"
        ][
            "limit"
        ]
        == 25
    )


def test_plain_seller_month_uses_header_mode():
    result, provider = run_question(
        "dame las ventas de Andres Legarreta "
        "de septiembre de 2026"
    )

    assert_governed(
        result,
        "sale",
    )

    assert (
        provider.parameters[0]
        == [
            "CANCELADA",
            "Andres Legarreta",
            "2026-09-01",
            "2026-10-01",
        ]
    )


def test_detailed_sales_stays_line_item():
    result, provider = run_question(
        "dame las ventas detalladas "
        "de Andres Legarreta"
    )

    assert_governed(
        result,
        "line_item",
    )

    assert (
        "DetalleVentas"
        in provider.sql[0]
    )

    assert (
        "Productos"
        in provider.sql[0]
    )


def test_explicit_line_fields_stays_line_item():
    result, provider = run_question(
        "lista las ventas con cliente "
        "producto cantidad e importe"
    )

    assert_governed(
        result,
        "line_item",
    )


def test_header_invalid_limit_fails_closed():
    result, provider = run_question(
        "dame 501 ventas "
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
