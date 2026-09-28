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
        name + "_sql_once",
        len(provider.sql)
        == 1,
    )

    check(
        name + "_governed_route",
        result["retrieval"][
            "fast_path"
        ]
        == "governed_sql",
    )

    return (
        result,
        provider,
    )


#
# MONTH:
# user-facing month is a calendar month.
# Compiler must use an inclusive start and exclusive next-month bound.
#
result, provider = run_plan(
    name="month_period",
    question=(
        "quién vendió más "
        "en agosto de 2026"
    ),
    payload={
        "domain": "sales",
        "entity": "seller",
        "operation": "ranking",
        "metric": "sales_amount",
        "direction": "desc",
        "limit": 10,
        "period": {
            "kind": "month",
            "year": 2026,
            "month": 8,
        },
    },
)

month_sql = provider.sql[-1]
month_params = provider.parameters[-1]

check(
    "month_uses_fecha_venta",
    "[FechaVenta]"
    in month_sql,
)

check(
    "month_uses_parameterized_lower_bound",
    ">= ?"
    in month_sql,
)

check(
    "month_uses_parameterized_upper_bound",
    "< ?"
    in month_sql,
)

check(
    "month_preserves_ventas_validas",
    month_params[0]
    == "CANCELADA",
)

check(
    "month_start_parameter",
    str(month_params[1])
    == "2026-08-01",
)

check(
    "month_end_parameter",
    str(month_params[2])
    == "2026-09-01",
)


#
# YEAR:
#
result, provider = run_plan(
    name="year_period",
    question=(
        "dime el vendedor líder "
        "durante 2025"
    ),
    payload={
        "domain": "sales",
        "entity": "seller",
        "operation": "ranking",
        "metric": "sales_amount",
        "direction": "desc",
        "limit": 10,
        "period": {
            "kind": "year",
            "year": 2025,
        },
    },
)

year_params = provider.parameters[-1]

check(
    "year_start_parameter",
    str(year_params[1])
    == "2025-01-01",
)

check(
    "year_end_parameter",
    str(year_params[2])
    == "2026-01-01",
)


#
# EXPLICIT RANGE:
# start/end are inclusive business dates.
# SQL upper bound must be exclusive end + 1 day.
#
result, provider = run_plan(
    name="range_period",
    question=(
        "qué vendedor encabezó "
        "del 10 al 20 de marzo de 2026"
    ),
    payload={
        "domain": "sales",
        "entity": "seller",
        "operation": "ranking",
        "metric": "sales_amount",
        "direction": "desc",
        "limit": 10,
        "period": {
            "kind": "range",
            "start": "2026-03-10",
            "end": "2026-03-20",
        },
    },
)

range_params = provider.parameters[-1]

check(
    "range_start_parameter",
    str(range_params[1])
    == "2026-03-10",
)

check(
    "range_end_is_exclusive_next_day",
    str(range_params[2])
    == "2026-03-21",
)


#
# PERIOD MUST APPLY TO PRODUCT ANALYTICS THROUGH SALES HEADER v.
#
result, provider = run_plan(
    name="product_month_period",
    question=(
        "qué producto desplazamos más "
        "en agosto de 2026"
    ),
    payload={
        "domain": "sales",
        "entity": "product",
        "operation": "ranking",
        "metric": "quantity",
        "direction": "desc",
        "limit": 10,
        "period": {
            "kind": "month",
            "year": 2026,
            "month": 8,
        },
    },
)

product_sql = provider.sql[-1]

check(
    "product_period_uses_sales_header_date",
    "v.[FechaVenta]"
    in product_sql,
)

check(
    "product_period_preserves_sales_header_join",
    "JOIN"
    in product_sql
    and "Ventas"
    in product_sql,
)


#
# NO PERIOD:
# old six-key semantic payload remains valid and means all available history.
#
result, provider = run_plan(
    name="all_time_backward_compatible",
    question=(
        "dime quién encabeza "
        "la facturación comercial"
    ),
    payload={
        "domain": "sales",
        "entity": "seller",
        "operation": "ranking",
        "metric": "sales_amount",
        "direction": "desc",
        "limit": 10,
    },
)

check(
    "all_time_has_no_date_filter",
    "[FechaVenta]"
    not in provider.sql[-1],
)

check(
    "all_time_keeps_sales_validity_only",
    provider.parameters[-1]
    == ["CANCELADA"],
)


#
# INVALID CALENDAR MONTH MUST FAIL CLOSED.
#
invalid_month_provider = FakeProvider()

invalid_month_bridge = GovernedSqlAssistantBridge(
    store=FakeStore(),
    provider_factory=
        lambda: invalid_month_provider,
    semantic_plan_resolver=
        Resolver(
            {
                "domain": "sales",
                "entity": "seller",
                "operation": "ranking",
                "metric": "sales_amount",
                "direction": "desc",
                "limit": 10,
                "period": {
                    "kind": "month",
                    "year": 2026,
                    "month": 13,
                },
            }
        ),
)

invalid_month_result = (
    invalid_month_bridge.resolve(
        scope=dict(SCOPE),
        analytic_bindings=
            ANALYTIC_BINDINGS,
        question=(
            "ventas del mes trece"
        ),
    )
)

check(
    "invalid_month_rejected",
    invalid_month_result
    is None,
)

check(
    "invalid_month_executes_no_sql",
    invalid_month_provider.sql
    == [],
)


#
# INVALID RANGE ORDER MUST FAIL CLOSED.
#
invalid_range_provider = FakeProvider()

invalid_range_bridge = GovernedSqlAssistantBridge(
    store=FakeStore(),
    provider_factory=
        lambda: invalid_range_provider,
    semantic_plan_resolver=
        Resolver(
            {
                "domain": "sales",
                "entity": "seller",
                "operation": "ranking",
                "metric": "sales_amount",
                "direction": "desc",
                "limit": 10,
                "period": {
                    "kind": "range",
                    "start": "2026-09-20",
                    "end": "2026-09-10",
                },
            }
        ),
)

invalid_range_result = (
    invalid_range_bridge.resolve(
        scope=dict(SCOPE),
        analytic_bindings=
            ANALYTIC_BINDINGS,
        question=(
            "ventas del veinte "
            "al diez"
        ),
    )
)

check(
    "invalid_range_rejected",
    invalid_range_result
    is None,
)

check(
    "invalid_range_executes_no_sql",
    invalid_range_provider.sql
    == [],
)


#
# PERIOD OBJECT MAY NEVER CARRY SQL OR PHYSICAL SOURCE AUTHORITY.
#
unsafe_provider = FakeProvider()

unsafe_bridge = GovernedSqlAssistantBridge(
    store=FakeStore(),
    provider_factory=
        lambda: unsafe_provider,
    semantic_plan_resolver=
        Resolver(
            {
                "domain": "sales",
                "entity": "seller",
                "operation": "ranking",
                "metric": "sales_amount",
                "direction": "desc",
                "limit": 10,
                "period": {
                    "kind": "month",
                    "year": 2026,
                    "month": 8,
                    "sql":
                        "DROP TABLE dbo.Ventas",
                },
            }
        ),
)

unsafe_result = unsafe_bridge.resolve(
    scope=dict(SCOPE),
    analytic_bindings=
        ANALYTIC_BINDINGS,
    question=(
        "consulta agosto"
    ),
)

check(
    "period_sql_payload_rejected",
    unsafe_result is None,
)

check(
    "period_sql_payload_executes_no_sql",
    unsafe_provider.sql
    == [],
)


print(
    "R10_31_TIME_PERIOD_CONTRACT=PASS"
)
