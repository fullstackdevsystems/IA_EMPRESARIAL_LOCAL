from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load_general_classifier():
    service_path = SCRIPTS / "enterprise_ai" / "service.py"

    source = service_path.read_text(
        encoding="utf-8-sig",
    )

    tree = ast.parse(
        source,
        filename=str(service_path),
    )

    constants = {}

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue

        if len(node.targets) != 1:
            continue

        target = node.targets[0]

        if not isinstance(target, ast.Name):
            continue

        try:
            constants[target.id] = ast.literal_eval(node.value)
        except Exception:
            continue

    method = None

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "_looks_general_knowledge"
        ):
            method = node
            break

    assert method is not None

    method.decorator_list = []

    module = ast.Module(
        body=[method],
        type_ignores=[],
    )

    ast.fix_missing_locations(module)

    namespace = dict(constants)

    exec(
        compile(
            module,
            filename=str(service_path),
            mode="exec",
        ),
        namespace,
        namespace,
    )

    return namespace["_looks_general_knowledge"]


def _sales_valid_binding():
    return {
        "id": "binding-sales-valid",
        "rule_id": "rule-sales-valid",
        "rule_type": "row_filter",
        "target": "sales_valid",
        "rule": {
            "id": "rule-sales-valid",
            "name": "VENTAS_VALIDAS",
            "expression": 'Estatus != "CANCELADA"',
            "status": "VALIDADO",
            "version": 2,
        },
    }


def _freight_binding():
    return {
        "id": "binding-freight",
        "rule_id": "rule-freight",
        "rule_type": "metric",
        "target": "freight",
        "rule": {
            "id": "rule-freight",
            "name": "Costo total de flete",
            "expression": (
                "Costo_Flete_Corto + "
                "Costo_Flete_Largo + "
                "Costo_Flete_Traspaso"
            ),
            "status": "VALIDADO",
            "version": 2,
        },
    }


def test_enterprise_analysis_prompts_do_not_use_general_fast_path():
    classify = _load_general_classifier()

    prompts = [
        "Dame un resumen ejecutivo de la información disponible.",
        "¿Qué información importante debería revisar hoy?",
        "Identifica tendencias, cambios o anomalías relevantes.",
        "Explícame qué información tienes disponible sobre mi empresa.",
    ]

    for prompt in prompts:
        assert classify(prompt) is False, prompt


def test_genuine_general_question_preserves_fast_path():
    classify = _load_general_classifier()

    assert classify("¿Qué es SQL Server?") is True
    assert classify("Explícame cómo funciona una API REST.") is True


def test_sales_valid_filter_is_not_applicable_without_estatus():
    from enterprise_ai.analytic_rules import (
        _row_filter_binding_applicability,
    )

    applicable, missing = _row_filter_binding_applicability(
        _sales_valid_binding(),
        {
            "date": "Fecha",
            "customer": "Cliente",
            "product": "Articulo",
            "sales": "Importe_Venta",
        },
        [
            "Fecha",
            "Cliente",
            "Articulo",
            "Importe_Venta",
        ],
    )

    assert applicable is False
    assert [value.lower() for value in missing] == ["estatus"]


def test_sales_valid_filter_is_applicable_when_estatus_exists():
    from enterprise_ai.analytic_rules import (
        _row_filter_binding_applicability,
    )

    applicable, missing = _row_filter_binding_applicability(
        _sales_valid_binding(),
        {
            "date": "Fecha",
            "sales": "Importe",
        },
        [
            "Fecha",
            "Importe",
            "Estatus",
        ],
    )

    assert applicable is True
    assert missing == []


def test_invalid_validated_expression_remains_fail_closed():
    from enterprise_ai.analytic_rules import (
        _row_filter_binding_applicability,
    )

    binding = _sales_valid_binding()
    binding["rule"]["expression"] = "Estatus !="

    applicable, missing = _row_filter_binding_applicability(
        binding,
        {},
        ["Fecha", "Importe"],
    )

    assert applicable is True
    assert missing == []


def test_build_context_filters_only_source_incompatible_row_filter():
    from enterprise_ai.analytic_rules import AnalyticRuleEngine

    sales = _sales_valid_binding()
    freight = _freight_binding()

    fake_engine = SimpleNamespace(
        applicable_bindings=lambda principal, on_date=None: [
            sales,
            freight,
        ]
    )

    principal = SimpleNamespace(
        company_id="prueba",
        user_id="admin",
    )

    context = AnalyticRuleEngine.build_context(
        fake_engine,
        principal,
        {
            "date": "Fecha",
            "sales": "Importe_Venta",
        },
        columns=[
            "Fecha",
            "Importe_Venta",
            "Costo_Flete_Corto",
            "Costo_Flete_Largo",
            "Costo_Flete_Traspaso",
        ],
    )

    targets = {
        item.get("target")
        for item in context["bindings"]
    }

    assert "sales_valid" not in targets
    assert "freight" in targets

    assert len(context["skipped_bindings"]) == 1

    skipped = context["skipped_bindings"][0]

    assert skipped["target"] == "sales_valid"
    assert skipped["reason"] == "SOURCE_INCOMPATIBLE_MISSING_FIELDS"
    assert [x.lower() for x in skipped["missing_fields"]] == ["estatus"]


def test_build_context_keeps_sales_valid_for_compatible_source():
    from enterprise_ai.analytic_rules import AnalyticRuleEngine

    sales = _sales_valid_binding()

    fake_engine = SimpleNamespace(
        applicable_bindings=lambda principal, on_date=None: [sales]
    )

    principal = SimpleNamespace(
        company_id="prueba",
        user_id="admin",
    )

    context = AnalyticRuleEngine.build_context(
        fake_engine,
        principal,
        {
            "date": "Fecha",
            "sales": "Importe",
        },
        columns=[
            "Fecha",
            "Importe",
            "Estatus",
        ],
    )

    assert [
        item.get("target")
        for item in context["bindings"]
    ] == ["sales_valid"]

    assert context["skipped_bindings"] == []


def test_governed_sql_sales_valid_authority_remains_present():
    path = SCRIPTS / "enterprise_ai" / "governed_sql_assistant.py"

    source = path.read_text(
        encoding="utf-8-sig",
    )

    assert "def _sales_validity_bindings(" in source
    assert 'if target != "sales_valid":' in source
    assert "NO_VALIDATED_SALES_VALID_ROW_FILTER" in source


TESTS = [
    test_enterprise_analysis_prompts_do_not_use_general_fast_path,
    test_genuine_general_question_preserves_fast_path,
    test_sales_valid_filter_is_not_applicable_without_estatus,
    test_sales_valid_filter_is_applicable_when_estatus_exists,
    test_invalid_validated_expression_remains_fail_closed,
    test_build_context_filters_only_source_incompatible_row_filter,
    test_build_context_keeps_sales_valid_for_compatible_source,
    test_governed_sql_sales_valid_authority_remains_present,
]


if __name__ == "__main__":
    failures = []

    for test in TESTS:
        try:
            test()
            print("PASS=" + test.__name__)
        except Exception as exc:
            failures.append((test.__name__, exc))
            print(
                "FAIL="
                + test.__name__
                + "|"
                + type(exc).__name__
                + "|"
                + str(exc)
            )

    print("TEST_COUNT=" + str(len(TESTS)))
    print("PASS_COUNT=" + str(len(TESTS) - len(failures)))
    print("FAIL_COUNT=" + str(len(failures)))

    if failures:
        raise SystemExit(1)

    print("R10_34_FOCUSED_REGRESSION=PASS")
