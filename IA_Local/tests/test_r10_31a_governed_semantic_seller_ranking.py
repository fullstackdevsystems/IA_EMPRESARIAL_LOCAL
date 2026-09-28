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
            "source_ref": "r10.30-business-semantics",
        },
    },
]


class FakeStore:
    def __init__(self):
        self.profile = {
            "connection_id": "connection-a",
            "display_name": "Ventas_Pruebas",
            "database": "DB_VENTAS",
            "enabled": True,
            "read_only": True,
            "status": "ACTIVE",
            "timeout_seconds": 30,
            "allowed_tables": [
                "dbo.Clientes",
                "dbo.DetalleVentas",
                "dbo.Productos",
                "dbo.Ventas",
            ],
            "scope": dict(SCOPE),
        }

    def list(self, scope):
        assert scope["company_id"] == "company-a"
        return [dict(self.profile)]

    def get(self, scope, connection_id):
        assert scope["company_id"] == "company-a"
        assert connection_id == "connection-a"
        return dict(self.profile)


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
                    {"name": "Categoria"},
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
                ("ANA", 125000.00),
                ("LUIS", 98000.00),
                ("PEDRO", 76500.00),
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


question = "que persona ha vendido mas?"


result = bridge.resolve(
    scope=dict(SCOPE),
    analytic_bindings=ANALYTIC_BINDINGS,
    question=question,
)


check(
    "seller_question_is_resolved",
    isinstance(result, dict),
)

check(
    "seller_question_uses_governed_sql",
    result["retrieval"]["fast_path"]
    == "governed_sql",
)

check(
    "seller_result_is_structured",
    result["retrieval"]["structured"]
    is True,
)

check(
    "seller_answer_contains_real_result",
    "ANA" in result["answer"]
    and "125000" in result["answer"],
)

check(
    "seller_sql_executed",
    len(provider.sql) == 1,
)

sql = provider.sql[-1]

check(
    "seller_sql_groups_by_vendedor",
    "[Vendedor]" in sql
    and "GROUP BY" in sql,
)

check(
    "seller_sql_uses_total",
    "SUM" in sql
    and "[Total]" in sql,
)

check(
    "seller_sql_orders_descending",
    "ORDER BY" in sql
    and "DESC" in sql,
)

check(
    "seller_sql_applies_validated_sales_filter",
    "[Estatus]" in sql
    and "<> ?" in sql,
)

check(
    "seller_sql_uses_cancelled_parameter",
    provider.parameters[-1]
    == ["CANCELADA"],
)

governance = result.get(
    "governance",
    {},
)

check(
    "seller_governance_read_only",
    governance.get("read_only")
    is True,
)

check(
    "seller_governance_allowlist",
    governance.get("allowlist_enforced")
    is True,
)

check(
    "seller_business_rule_applied",
    governance.get(
        "business_row_filter_applied"
    )
    is True,
)

check(
    "seller_fail_closed",
    governance.get("fail_closed")
    is True,
)

check(
    "seller_llm_has_no_sql_generation_authority",
    governance.get(
        "llm_sql_generation"
    )
    is False,
)

print(
    "R10_31_SELLER_RANKING_CONTRACT=PASS"
)
