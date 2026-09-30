from __future__ import annotations

import copy
import runpy
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
P4_TEST = (
    ROOT
    / "tests"
    / "test_r10_32c_governed_sales_detail_modes.py"
)

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


P4 = runpy.run_path(
    str(P4_TEST),
    run_name="__r10_32_p4_fixture__",
)


FakeStore = P4[
    "FakeStore"
]

FakeProvider = P4[
    "FakeProvider"
]

GovernedSqlAssistantBridge = P4[
    "GovernedSqlAssistantBridge"
]

SCOPE = P4[
    "SCOPE"
]

ANALYTIC_BINDINGS = P4[
    "ANALYTIC_BINDINGS"
]


def run_with_provider(
    question,
    provider,
    *,
    bindings=None,
):
    if bindings is None:
        bindings = ANALYTIC_BINDINGS

    bridge = GovernedSqlAssistantBridge(
        store=FakeStore(),
        provider_factory=
            lambda: provider,
    )

    result = bridge.resolve(
        scope=dict(SCOPE),
        analytic_bindings=
            bindings,
        question=question,
    )

    return (
        result,
        provider,
    )


def run_question(
    question,
):
    return run_with_provider(
        question,
        FakeProvider(),
    )


def assert_governed_acceptance(
    result,
    *,
    mode,
):
    assert isinstance(
        result,
        dict,
    )

    retrieval = result[
        "retrieval"
    ]

    governance = result[
        "governance"
    ]

    assert (
        retrieval[
            "fast_path"
        ]
        == "governed_sql"
    )

    assert (
        retrieval[
            "structured"
        ]
        is True
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
            "business_semantics_authority"
        )
        == "validated_analytic_row_filter"
    )

    assert (
        governance.get(
            "sql_rule_compiler"
        )
        == "r10.30-row-filter-v1"
    )

    assert (
        governance.get(
            "llm_sql_generation"
        )
        is False
    )

    assert (
        governance.get(
            "llm_computational_authority"
        )
        is False
    )

    assert (
        governance.get(
            "semantic_plan_source"
        )
        == "deterministic"
    )

    assert (
        governance.get(
            "semantic_planner"
        )
        == "r10.32-sales-detail-v1"
    )

    plan = governance[
        "semantic_analytics_plan"
    ]

    assert (
        plan["version"]
        == "r10.32-sales-detail-v1"
    )

    assert (
        plan["domain"]
        == "sales"
    )

    assert (
        plan["entity"]
        == "sale"
    )

    assert (
        plan["operation"]
        == "detail"
    )

    assert (
        plan["detail_level"]
        == mode
    )

    sources = list(
        result.get(
            "sources"
        )
        or []
    )

    assert any(
        source.get(
            "type"
        )
        == "connected_data"
        for source in sources
        if isinstance(
            source,
            dict,
        )
    )


def assert_blocked_without_sql(
    result,
    provider,
):
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
            "fail_closed"
        ]
        is True
    )

    assert (
        provider.sql
        == []
    )


def test_acceptance_01_exact_defect():
    result, provider = run_question(
        "pasame la lista de ventas "
        "detalladas por vendedor"
    )

    assert_governed_acceptance(
        result,
        mode="line_item",
    )

    assert (
        provider.parameters[0]
        == ["CANCELADA"]
    )

    sql = provider.sql[0]

    assert "DetalleVentas" in sql
    assert "Productos" in sql
    assert "ORDER BY" in sql
    assert "[Vendedor]" in sql

    assert (
        "internal_context"
        not in str(result)
    )


def test_acceptance_02_detailed_seller():
    result, provider = run_question(
        "dame las ventas detalladas "
        "de Andres Legarreta"
    )

    assert_governed_acceptance(
        result,
        mode="line_item",
    )

    assert (
        provider.parameters[0]
        == [
            "CANCELADA",
            "Andres Legarreta",
        ]
    )

    assert (
        "Andres Legarreta"
        not in provider.sql[0]
    )

    assert "= ?" in provider.sql[0]


def test_acceptance_03_seller_month():
    result, provider = run_question(
        "dame las ventas de Andres Legarreta "
        "de septiembre de 2026"
    )

    assert_governed_acceptance(
        result,
        mode="sale",
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

    sql = provider.sql[0]

    assert ">= ?" in sql
    assert "< ?" in sql
    assert "DetalleVentas" not in sql
    assert "Productos" not in sql


def test_acceptance_04_current_month_detail():
    result, provider = run_question(
        "muestrame las ventas "
        "detalladas de este mes"
    )

    assert_governed_acceptance(
        result,
        mode="line_item",
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


def test_acceptance_05_explicit_limit():
    result, provider = run_question(
        "dame 25 ventas detalladas "
        "de Andres Legarreta"
    )

    assert_governed_acceptance(
        result,
        mode="line_item",
    )

    assert (
        "TOP (25)"
        in provider.sql[0]
    )

    assert (
        result[
            "governance"
        ][
            "semantic_analytics_plan"
        ][
            "limit"
        ]
        == 25
    )

    assert (
        "hasta 25 renglones"
        in result["answer"]
    )


def test_acceptance_06_products_by_seller():
    result, provider = run_question(
        "que productos vendio "
        "Andres Legarreta"
    )

    assert_governed_acceptance(
        result,
        mode="line_item",
    )

    sql = provider.sql[0]

    assert "DetalleVentas" in sql
    assert "Productos" in sql

    assert (
        provider.parameters[0]
        == [
            "CANCELADA",
            "Andres Legarreta",
        ]
    )


def test_acceptance_07_explicit_line_fields():
    result, provider = run_question(
        "lista las ventas con cliente "
        "producto cantidad e importe"
    )

    assert_governed_acceptance(
        result,
        mode="line_item",
    )

    sql = provider.sql[0]

    assert "AS [Cliente]" in sql
    assert "AS [Producto]" in sql
    assert "AS [Cantidad]" in sql
    assert "AS [Importe]" in sql


def test_simple_sales_list_is_header_mode():
    result, provider = run_question(
        "lista de ventas"
    )

    assert_governed_acceptance(
        result,
        mode="sale",
    )

    sql = provider.sql[0]

    assert "DetalleVentas" not in sql
    assert "Productos" not in sql
    assert "_DetalleVentaID" not in sql


def test_negative_sql_injection_fails_closed():
    result, provider = run_question(
        "dame las ventas detalladas "
        "de Andres' OR 1=1--"
    )

    assert_blocked_without_sql(
        result,
        provider,
    )

    assert (
        result["governance"][
            "reason"
        ]
        == "SALES_DETAIL_SELLER_INVALID"
    )


def test_negative_invalid_limit_fails_closed():
    result, provider = run_question(
        "dame 501 ventas detalladas "
        "de Andres Legarreta"
    )

    assert_blocked_without_sql(
        result,
        provider,
    )

    assert (
        result["governance"][
            "reason"
        ]
        == "SALES_DETAIL_LIMIT_INVALID"
    )


def test_limit_500_is_allowed():
    result, provider = run_question(
        "dame 500 ventas detalladas "
        "de Andres Legarreta"
    )

    assert_governed_acceptance(
        result,
        mode="line_item",
    )

    assert (
        "TOP (500)"
        in provider.sql[0]
    )


def test_missing_ventas_validas_fails_closed():
    provider = FakeProvider()

    result, provider = run_with_provider(
        "pasame la lista de ventas "
        "detalladas por vendedor",
        provider,
        bindings=[],
    )

    assert_blocked_without_sql(
        result,
        provider,
    )


def test_invalid_ventas_validas_status_fails_closed():
    bindings = copy.deepcopy(
        ANALYTIC_BINDINGS
    )

    bindings[0][
        "rule"
    ][
        "status"
    ] = "PROPUESTO"

    provider = FakeProvider()

    result, provider = run_with_provider(
        "pasame la lista de ventas "
        "detalladas por vendedor",
        provider,
        bindings=bindings,
    )

    assert_blocked_without_sql(
        result,
        provider,
    )


class MissingProductTableProvider(
    FakeProvider
):
    def discover(
        self,
        profile,
    ):
        return [
            item
            for item in super().discover(
                profile
            )
            if item.get(
                "name"
            )
            != "Productos"
        ]


def test_unknown_or_missing_required_table_fails_closed():
    provider = (
        MissingProductTableProvider()
    )

    result, provider = run_with_provider(
        "lista las ventas con cliente "
        "producto cantidad e importe",
        provider,
    )

    assert_blocked_without_sql(
        result,
        provider,
    )


class MissingRequiredColumnProvider(
    FakeProvider
):
    def discover(
        self,
        profile,
    ):
        objects = super().discover(
            profile
        )

        for item in objects:
            if (
                item.get(
                    "name"
                )
                == "DetalleVentas"
            ):
                item[
                    "columns"
                ] = [
                    column
                    for column
                    in item.get(
                        "columns",
                        []
                    )
                    if column.get(
                        "name"
                    )
                    != "Importe"
                ]

        return objects


def test_unknown_or_missing_required_column_fails_closed():
    provider = (
        MissingRequiredColumnProvider()
    )

    result, provider = run_with_provider(
        "lista las ventas con cliente "
        "producto cantidad e importe",
        provider,
    )

    assert_blocked_without_sql(
        result,
        provider,
    )


class EmptyResultProvider(
    FakeProvider
):
    def execute(
        self,
        profile,
        sql,
        parameters,
        timeout_seconds,
    ):
        result = super().execute(
            profile,
            sql,
            parameters,
            timeout_seconds,
        )

        result[
            "rows"
        ] = []

        return result


def test_empty_result_is_governed_and_never_documentary_fallback():
    provider = EmptyResultProvider()

    result, provider = run_with_provider(
        "pasame la lista de ventas "
        "detalladas por vendedor",
        provider,
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

    assert (
        "No se encontraron ventas"
        in result["answer"]
    )

    assert (
        "internal_context"
        not in str(result)
    )


def test_exact_defect_never_returns_documentary_fallback():
    result, provider = run_question(
        "pasame la lista de ventas "
        "detalladas por vendedor"
    )

    assert result is not None

    assert (
        result["retrieval"][
            "fast_path"
        ]
        == "governed_sql"
    )

    assert (
        result["retrieval"][
            "fast_path"
        ]
        != "internal_context"
    )

    assert len(
        provider.sql
    ) == 1


def test_sale_totals_are_not_repeated_per_product():
    result, provider = run_question(
        "dame las ventas detalladas "
        "de Andres Legarreta"
    )

    assert_governed_acceptance(
        result,
        mode="line_item",
    )

    assert (
        result["answer"].count(
            "Total 116.0"
        )
        == 1
    )


def test_header_mode_has_no_detail_multiplication():
    result, provider = run_question(
        "lista de ventas"
    )

    assert_governed_acceptance(
        result,
        mode="sale",
    )

    sql = provider.sql[0]

    assert "DetalleVentas" not in sql
    assert "Productos" not in sql
    assert "_DetalleVentaID" not in sql
