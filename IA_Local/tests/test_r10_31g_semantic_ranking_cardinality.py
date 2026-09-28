from __future__ import annotations

from scripts.enterprise_ai.governed_sql_assistant import (
    GovernedSqlAssistantBridge,
    SemanticAnalyticsPlanner,
    _ranking_cardinality_hint,
)


def _payload(**overrides):
    value = {
        "domain": "sales",
        "entity": "seller",
        "operation": "ranking",
        "metric": "sales_amount",
        "direction": "desc",
    }
    value.update(overrides)
    return value


def test_real_singular_temporal_is_one():
    question = (
        "que vendedor genero el mayor importe monetario "
        "en ventas durante agosto de 2026"
    )
    assert _ranking_cardinality_hint(question) == 1
    plan = GovernedSqlAssistantBridge._validated_external_semantic_plan(
        _payload(),
        question,
    )
    assert plan is not None
    assert plan.limit == 1


def test_year_is_not_explicit_cardinality():
    assert _ranking_cardinality_hint(
        "que vendedores vendieron mas durante agosto de 2026"
    ) is None


def test_plural_que_is_not_singular():
    question = (
        "que vendedores vendieron mas durante agosto de 2026"
    )
    plan = GovernedSqlAssistantBridge._validated_external_semantic_plan(
        _payload(),
        question,
    )
    assert plan is not None
    assert plan.limit == 10


def test_explicit_top_five():
    question = (
        "top 5 vendedores con mayor importe durante 2026"
    )
    assert _ranking_cardinality_hint(question) == 5
    plan = GovernedSqlAssistantBridge._validated_external_semantic_plan(
        _payload(),
        question,
    )
    assert plan is not None
    assert plan.limit == 5


def test_explicit_los_five():
    question = (
        "los 5 vendedores con mayor importe durante 2026"
    )
    assert _ranking_cardinality_hint(question) == 5


def test_singular_overrides_model_ten():
    question = (
        "que vendedor genero el mayor importe monetario "
        "en ventas durante agosto de 2026"
    )
    plan = GovernedSqlAssistantBridge._validated_external_semantic_plan(
        _payload(limit=10),
        question,
    )
    assert plan is not None
    assert plan.limit == 1


def test_invalid_model_limit_still_fails_closed():
    plan = GovernedSqlAssistantBridge._validated_external_semantic_plan(
        _payload(limit=0),
        "que vendedor genero el mayor importe en ventas",
    )
    assert plan is None


def test_explicit_over_max_fails_closed():
    plan = GovernedSqlAssistantBridge._validated_external_semantic_plan(
        _payload(),
        "top 51 vendedores con mayor importe en ventas",
    )
    assert plan is None


def test_all_time_person_singular_is_one():
    assert _ranking_cardinality_hint(
        "que persona ha vendido mas?"
    ) == 1
    plan = SemanticAnalyticsPlanner.plan(
        "que persona ha vendido mas?"
    )
    assert plan is not None
    assert plan.limit == 1


def test_cual_es_el_vendedor_is_one():
    assert _ranking_cardinality_hint(
        "cual es el vendedor que vendio mas?"
    ) == 1
