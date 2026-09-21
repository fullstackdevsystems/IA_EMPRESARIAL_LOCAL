from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_module(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_c2_planner_declares_cancellation_analysis():
    planner = load_module("analysis_planner")

    spec = planner._ANALYSIS_REQUIREMENTS["cancellations"]

    assert spec["operator"] == "cancellation_analysis"
    assert spec["dimensions"] == []
    assert spec["metrics"] == []
    assert spec["optional_metrics"] == ["revenue", "quantity"]


def test_c2_executor_uses_only_authorized_deterministic_signals():
    executor = load_module("analysis_executor")

    df = pd.DataFrame({
        "Folio": ["100", "C101", "102", "103"],
        "Cantidad": [1, 2, -1, 1],
        "Ventas": [100.0, 200.0, -50.0, 300.0],
    })
    original = df.copy(deep=True)

    result = executor._cancellation_analysis(
        df,
        {},
        {
            "invoice": "Folio",
            "quantity": "Cantidad",
            "revenue": "Ventas",
        },
    )

    assert result["kind"] == "cancellation_analysis"
    assert result["evidence_available"] is True
    assert result["row_count"] == 4
    assert result["cancellation_rows"] == 2
    assert result["cancellation_row_pct"] == 50.0

    assert result["cancellation_revenue_net"] == 150.0
    assert result["cancellation_revenue_impact_abs"] == 250.0
    assert result["positive_revenue"] == 600.0

    assert round(
        result["cancellation_impact_pct_of_positive_revenue"], 8
    ) == round(250.0 / 600.0 * 100.0, 8)

    signals = {
        item["signal"]: item["matched_rows"]
        for item in result["signals"]
    }

    assert signals == {
        "negative_quantity": 1,
        "negative_revenue": 1,
        "reference_prefix_c": 1,
    }

    assert result["governance"]["deterministic"] is True
    assert result["governance"]["llm_numeric_inference"] is False
    assert result["governance"]["llm_cancellation_detection"] is False
    assert result["governance"]["business_thresholds_invented"] is False
    assert result["governance"]["status_values_invented"] is False

    pd.testing.assert_frame_equal(df, original)


def test_c2_executor_fails_closed_without_authorized_evidence():
    executor = load_module("analysis_executor")

    df = pd.DataFrame({
        "Estado": ["CANCELADA", "ACTIVA"],
    })

    result = executor._cancellation_analysis(
        df,
        {},
        {"status": "Estado"},
    )

    assert result["evidence_available"] is False
    assert result["cancellation_rows"] == 0
    assert result["signals"] == []
    assert result["governance"]["status_values_invented"] is False


def test_c2_governed_executor_marks_missing_evidence_not_executed():
    executor = load_module("analysis_executor")

    plan = {
        "tasks": [{
            "id": "analysis_plan:cancellations",
            "analysis": "cancellations",
            "operator": "cancellation_analysis",
            "status": "READY",
            "evidence": [],
            "optional_evidence": [],
        }]
    }

    result = executor.execute_governed_analytical_plan(
        pd.DataFrame({"Estado": ["CANCELADA"]}),
        analytical_plan=plan,
        roles={"status": "Estado"},
    )

    assert result["task_count"] == 1
    assert result["executed_count"] == 0
    assert result["not_executed_count"] == 1
    assert result["results"][0]["execution_status"] == "NOT_EXECUTED"


def test_c2_insight_promotes_executed_facts_without_classification():
    insight = load_module("insight_engine")

    assert insight.R10_25C2_CANCELLATION_VERSION == "r10.25c2"

    item = {
        "task_id": "analysis_plan:cancellations",
        "analysis": "cancellations",
        "execution_status": "EXECUTED",
        "result": {
            "kind": "cancellation_analysis",
            "evidence_available": True,
            "row_count": 10,
            "cancellation_rows": 2,
            "cancellation_row_pct": 20.0,
            "cancellation_revenue_net": -100.0,
            "cancellation_revenue_impact_abs": 100.0,
            "positive_revenue": 1000.0,
            "cancellation_impact_pct_of_positive_revenue": 10.0,
            "signals": [{
                "signal": "negative_revenue",
                "source_column": "Ventas",
                "matched_rows": 2,
            }],
            "governance": {"deterministic": True},
        },
    }

    original = copy.deepcopy(item)

    findings, observations = insight._cancellation_insights(item)

    assert observations == []
    assert len(findings) == 2

    assert findings[0]["insight_type"] == "cancellation_rate"
    assert findings[0]["value"] == 20.0

    assert findings[1]["insight_type"] == "cancellation_revenue_impact"
    assert findings[1]["value"] == 100.0
    assert findings[1]["impact_pct_of_positive_revenue"] == 10.0

    for finding in findings:
        assert finding["provenance"]["confidence"] == 1.0
        assert finding["governance"]["calculated_fact"] is True
        assert finding["governance"]["classification_applied"] is False
        assert finding["governance"]["llm_numeric_inference"] is False
        assert finding["governance"]["uses_executed_results_only"] is True
        assert finding["governance"]["business_thresholds_invented"] is False

    assert item == original


def test_c2_builder_does_not_promote_not_executed_result():
    insight = load_module("insight_engine")

    analytical_results = {
        "results": [{
            "task_id": "analysis_plan:cancellations",
            "analysis": "cancellations",
            "execution_status": "NOT_EXECUTED",
            "reason": "No governed cancellation evidence.",
            "result": {
                "kind": "cancellation_analysis",
                "evidence_available": False,
            },
        }]
    }

    result = insight.build_governed_business_insights(
        analytical_results=analytical_results
    )

    assert result["insight_count"] == 0
    assert result["governance"]["not_executed_results_are_never_promoted"] is True
