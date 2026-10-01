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
    run_name="__r10_33_fixture__",
)


FakeStore = P4["FakeStore"]
FakeProvider = P4["FakeProvider"]
GovernedSqlAssistantBridge = P4["GovernedSqlAssistantBridge"]
SCOPE = P4["SCOPE"]
ANALYTIC_BINDINGS = P4["ANALYTIC_BINDINGS"]


def run_question(
    question,
    *,
    provider=None,
    bindings=None,
):
    if provider is None:
        provider = FakeProvider()

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

    return result, provider


def assert_paged(
    result,
    *,
    mode,
    page,
    page_size,
    offset,
    has_more=False,
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

    governance = result[
        "governance"
    ]

    assert (
        governance["read_only"]
        is True
    )

    assert (
        governance[
            "allowlist_enforced"
        ]
        is True
    )

    assert (
        governance[
            "fail_closed"
        ]
        is True
    )

    assert (
        governance[
            "llm_sql_generation"
        ]
        is False
    )

    assert (
        governance[
            "business_row_filter_applied"
        ]
        is True
    )

    assert (
        governance[
            "business_semantics_authority"
        ]
        == "validated_analytic_row_filter"
    )

    assert (
        governance[
            "semantic_planner"
        ]
        == "r10.33-sales-detail-pagination-v1"
    )

    plan = governance[
        "semantic_analytics_plan"
    ]

    assert (
        plan["version"]
        == "r10.33-sales-detail-pagination-v1"
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

    assert (
        plan["limit"]
        == page_size
    )

    assert (
        plan["page"]
        == page
    )

    assert (
        plan["page_size"]
        == page_size
    )

    assert (
        plan["offset"]
        == offset
    )

    assert (
        plan["explicit"]
        is True
    )

    assert (
        plan["has_more"]
        is has_more
    )


def assert_blocked_no_sql(
    result,
    provider,
    *,
    reason=None,
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
        result["retrieval"][
            "structured"
        ]
        is False
    )

    assert (
        result["governance"][
            "fail_closed"
        ]
        is True
    )

    if reason is not None:
        assert (
            result["governance"][
                "reason"
            ]
            == reason
        )

    assert (
        provider.sql
        == []
    )


def assert_offset_fetch(
    sql,
):
    assert (
        "OFFSET ? ROWS "
        "FETCH NEXT ? ROWS ONLY"
        in sql
    )

    assert (
        "SELECT TOP"
        not in sql
    )


def test_a01_line_item_page_2_size_25():
    result, provider = run_question(
        "dame 25 ventas detalladas "
        "de Andres Legarreta pagina 2"
    )

    assert_paged(
        result,
        mode="line_item",
        page=2,
        page_size=25,
        offset=25,
    )

    sql = provider.sql[0]

    assert_offset_fetch(
        sql
    )

    assert (
        provider.parameters[0]
        == [
            "CANCELADA",
            "Andres Legarreta",
            25,
            26,
        ]
    )

    assert (
        "Andres Legarreta"
        not in sql
    )

    assert (
        "v.[VentaID] DESC"
        in sql
    )

    assert (
        sql.index(
            "v.[VentaID] DESC"
        )
        <
        sql.index(
            "d.[DetalleVentaID] ASC"
        )
    )


def test_a02_line_item_page_2_default_size():
    result, provider = run_question(
        "dame las ventas detalladas "
        "de Andres Legarreta pagina 2"
    )

    assert_paged(
        result,
        mode="line_item",
        page=2,
        page_size=100,
        offset=100,
    )

    assert_offset_fetch(
        provider.sql[0]
    )

    assert (
        provider.parameters[0]
        == [
            "CANCELADA",
            "Andres Legarreta",
            100,
            101,
        ]
    )


def test_a03_header_page_3_size_25():
    result, provider = run_question(
        "dame 25 ventas de "
        "Andres Legarreta pagina 3"
    )

    assert_paged(
        result,
        mode="sale",
        page=3,
        page_size=25,
        offset=50,
    )

    sql = provider.sql[0]

    assert_offset_fetch(
        sql
    )

    assert (
        "DetalleVentas"
        not in sql
    )

    assert (
        "Productos"
        not in sql
    )

    assert (
        "v.[VentaID] DESC"
        in sql
    )

    assert (
        provider.parameters[0]
        == [
            "CANCELADA",
            "Andres Legarreta",
            50,
            26,
        ]
    )


def test_a04_header_seller_period_page_2():
    result, provider = run_question(
        "dame las ventas de Andres Legarreta "
        "de septiembre de 2026 pagina 2"
    )

    assert_paged(
        result,
        mode="sale",
        page=2,
        page_size=100,
        offset=100,
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
        plan["period"]
        == {
            "kind": "month",
            "start": "2026-09-01",
            "end_exclusive": "2026-10-01",
        }
    )

    assert (
        provider.parameters[0]
        == [
            "CANCELADA",
            "Andres Legarreta",
            "2026-09-01",
            "2026-10-01",
            100,
            101,
        ]
    )


def test_a05_current_month_page_2():
    result, provider = run_question(
        "muestrame las ventas "
        "detalladas de este mes pagina 2"
    )

    assert_paged(
        result,
        mode="line_item",
        page=2,
        page_size=100,
        offset=100,
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
            100,
            101,
        ]
    )


def test_a06_max_page_and_page_size():
    result, provider = run_question(
        "dame 500 ventas detalladas "
        "de Andres Legarreta pagina 1000"
    )

    assert_paged(
        result,
        mode="line_item",
        page=1000,
        page_size=500,
        offset=499500,
    )

    assert (
        provider.parameters[0][-2:]
        == [
            499500,
            501,
        ]
    )


def test_a07_non_paged_r10_32_path_is_preserved():
    result, provider = run_question(
        "dame 25 ventas detalladas "
        "de Andres Legarreta"
    )

    sql = provider.sql[0]

    assert (
        "TOP (25)"
        in sql
    )

    assert (
        "OFFSET ? ROWS"
        not in sql
    )

    governance = result[
        "governance"
    ]

    assert (
        governance[
            "semantic_planner"
        ]
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
        "page"
        not in plan
    )

    assert (
        "page_size"
        not in plan
    )

    assert (
        provider.parameters[0]
        == [
            "CANCELADA",
            "Andres Legarreta",
        ]
    )


def test_a08_page_suffix_is_not_part_of_seller():
    result, provider = run_question(
        "dame las ventas de "
        "Andres Legarreta pagina 2"
    )

    assert_paged(
        result,
        mode="sale",
        page=2,
        page_size=100,
        offset=100,
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
        provider.parameters[0][1]
        == "Andres Legarreta"
    )


def test_n01_page_zero_fails_closed():
    result, provider = run_question(
        "dame 25 ventas detalladas "
        "de Andres Legarreta pagina 0"
    )

    assert_blocked_no_sql(
        result,
        provider,
        reason=
            "SALES_DETAIL_PAGE_INVALID",
    )


def test_n02_page_1001_fails_closed():
    result, provider = run_question(
        "dame 25 ventas detalladas "
        "de Andres Legarreta pagina 1001"
    )

    assert_blocked_no_sql(
        result,
        provider,
        reason=
            "SALES_DETAIL_PAGE_INVALID",
    )


def test_n03_page_injection_fails_closed():
    result, provider = run_question(
        "dame 25 ventas detalladas "
        "de Andres Legarreta "
        "pagina 2 OR 1=1"
    )

    assert_blocked_no_sql(
        result,
        provider,
        reason=
            "SALES_DETAIL_PAGE_INVALID",
    )


def test_n04_page_without_number_fails_closed():
    result, provider = run_question(
        "dame 25 ventas detalladas "
        "de Andres Legarreta pagina"
    )

    assert_blocked_no_sql(
        result,
        provider,
        reason=
            "SALES_DETAIL_PAGE_INVALID",
    )


def test_n05_missing_ventas_validas_fails_closed():
    result, provider = run_question(
        "dame 25 ventas detalladas "
        "de Andres Legarreta pagina 2",
        bindings=[],
    )

    assert_blocked_no_sql(
        result,
        provider,
    )


def test_n06_invalid_ventas_validas_status_fails_closed():
    bindings = copy.deepcopy(
        ANALYTIC_BINDINGS
    )

    bindings[0][
        "rule"
    ][
        "status"
    ] = "PROPUESTO"

    result, provider = run_question(
        "dame 25 ventas detalladas "
        "de Andres Legarreta pagina 2",
        bindings=bindings,
    )

    assert_blocked_no_sql(
        result,
        provider,
    )


class EmptyPageProvider(
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

        result["rows"] = []

        return result


def test_n07_empty_page_is_governed_empty():
    provider = EmptyPageProvider()

    result, provider = run_question(
        "dame 25 ventas detalladas "
        "de Andres Legarreta pagina 2",
        provider=provider,
    )

    assert_paged(
        result,
        mode="line_item",
        page=2,
        page_size=25,
        offset=25,
    )

    assert (
        "No se encontraron ventas"
        in result["answer"]
    )

    assert (
        "internal_context"
        not in str(result)
    )


class HasMoreProvider(
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

        row = result["rows"][0]

        result["rows"] = [
            row
            for _ in range(26)
        ]

        return result


def test_has_more_comes_from_executor_truncation():
    provider = HasMoreProvider()

    result, provider = run_question(
        "dame 25 ventas detalladas "
        "de Andres Legarreta pagina 2",
        provider=provider,
    )

    assert_paged(
        result,
        mode="line_item",
        page=2,
        page_size=25,
        offset=25,
        has_more=True,
    )

    assert (
        provider.parameters[0][-1]
        == 26
    )
