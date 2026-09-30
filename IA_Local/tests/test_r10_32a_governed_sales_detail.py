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
    _sales_detail_intent,
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
            "max_rows":
                500,
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

    def discover(
        self,
        profile,
    ):
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
                    10,
                    1001,
                    "ANA",
                    "2026-09-28",
                    "F-100",
                    "CLIENTE A",
                    "CULIACAN",
                    "ACTIVA",
                    1000,
                    160,
                    1160,
                    "PRODUCTO A",
                    2,
                    250,
                    500,
                ),
                (
                    10,
                    1002,
                    "ANA",
                    "2026-09-28",
                    "F-100",
                    "CLIENTE A",
                    "CULIACAN",
                    "ACTIVA",
                    1000,
                    160,
                    1160,
                    "PRODUCTO B",
                    1,
                    500,
                    500,
                ),
                (
                    11,
                    1003,
                    "LUIS",
                    "2026-09-27",
                    "F-099",
                    "CLIENTE B",
                    "GUASAVE",
                    "ACTIVA",
                    200,
                    32,
                    232,
                    "PRODUCTO C",
                    1,
                    200,
                    200,
                ),
            ],
        }


def make_bridge(
    provider,
):
    return GovernedSqlAssistantBridge(
        store=FakeStore(),
        provider_factory=
            lambda: provider,
    )


def test_exact_defect_question_routes_to_governed_sql():
    question = (
        "pasame la lista de ventas "
        "detalladas por vendedor"
    )

    assert (
        _sales_detail_intent(
            question
        )
        is True
    )

    provider = FakeProvider()

    result = make_bridge(
        provider
    ).resolve(
        scope=dict(SCOPE),
        analytic_bindings=
            ANALYTIC_BINDINGS,
        question=question,
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
        "SELECT TOP (100)"
        in sql
    )

    assert (
        sql.count(
            "LEFT JOIN"
        )
        == 3
    )

    assert (
        "[Clientes]"
        in sql
        and "[DetalleVentas]"
        in sql
        and "[Productos]"
        in sql
        and "[Ventas]"
        in sql
    )

    assert (
        "v.[Estatus] <> ?"
        in sql
    )

    assert (
        provider.parameters[0]
        == ["CANCELADA"]
    )

    assert (
        "ORDER BY"
        in sql
        and "v.[Vendedor] ASC"
        in sql
        and "v.[FechaVenta] DESC"
        in sql
        and "v.[Folio] DESC"
        in sql
    )

    answer = result[
        "answer"
    ]

    assert (
        "Vendedor: ANA"
        in answer
    )

    assert (
        "Vendedor: LUIS"
        in answer
    )

    assert (
        "Folio F-100"
        in answer
    )

    assert (
        "PRODUCTO A"
        in answer
        and "PRODUCTO B"
        in answer
        and "PRODUCTO C"
        in answer
    )

    assert (
        answer.count(
            "Subtotal 1000"
        )
        == 1
    )

    assert (
        answer.count(
            "Total 1160"
        )
        == 1
    )

    governance = result[
        "governance"
    ]

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
            "analytic_kind"
        )
        == "sales_line_item"
    )

    plan = governance.get(
        "semantic_analytics_plan"
    )

    assert isinstance(
        plan,
        dict,
    )

    assert (
        plan.get(
            "version"
        )
        == "r10.32-sales-detail-v1"
    )

    assert (
        plan.get(
            "domain"
        )
        == "sales"
    )

    assert (
        plan.get(
            "entity"
        )
        == "sale"
    )

    assert (
        plan.get(
            "operation"
        )
        == "detail"
    )

    assert (
        plan.get(
            "detail_level"
        )
        == "line_item"
    )

    assert (
        plan.get(
            "grouping"
        )
        == "seller"
    )

    assert (
        governance.get(
            "llm_sql_generation"
        )
        is False
    )

    assert (
        governance.get(
            "llm_semantic_proposal"
        )
        is False
    )

    assert (
        result["timings_ms"][
            "llm_ms"
        ]
        == 0.0
    )


def test_detail_requires_validated_sales_rule():
    provider = FakeProvider()

    result = make_bridge(
        provider
    ).resolve(
        scope=dict(SCOPE),
        analytic_bindings=None,
        question=(
            "pasame la lista de ventas "
            "detalladas por vendedor"
        ),
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

    assert provider.sql == []

    assert (
        result["governance"][
            "fail_closed"
        ]
        is True
    )

    assert (
        result["governance"][
            "reason"
        ]
        == "NO_VALIDATED_SALES_VALID_ROW_FILTER"
    )


def test_unrelated_question_still_falls_through():
    provider = FakeProvider()

    result = make_bridge(
        provider
    ).resolve(
        scope=dict(SCOPE),
        analytic_bindings=
            ANALYTIC_BINDINGS,
        question=(
            "explicame que es "
            "inteligencia artificial"
        ),
    )

    assert result is None
    assert provider.sql == []
