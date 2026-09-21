from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from analysis_executor import _anomaly_scan, execute_governed_analytical_plan
from analysis_planner import _ANALYSIS_REQUIREMENTS
from insight_engine import (
    R10_25C3_ANOMALY_VERSION,
    _anomaly_insights,
    build_governed_business_insights,
)


def _task():
    return {
        "id": "analysis_plan:anomalies",
        "analysis": "anomalies",
        "operator": "anomaly_scan",
        "status": "SUPPORTED",
        "required_dimensions": ["date"],
        "required_metrics": [],
        "optional_metrics": ["revenue"],
        "evidence": [
            {
                "kind": "dimension",
                "key": "date",
                "required": True,
                "status": "SUPPORTED",
                "source_columns": ["Fecha"],
                "formula": None,
                "dependencies": [],
                "rule": {},
                "reason": None,
                "provenance": {
                    "source": "semantic_role",
                    "confidence": 1.0,
                },
            }
        ],
        "optional_evidence": [
            {
                "kind": "metric",
                "key": "revenue",
                "required": False,
                "status": "SUPPORTED",
                "source_columns": ["Ventas"],
                "formula": None,
                "dependencies": [],
                "rule": {},
                "reason": None,
                "provenance": {
                    "source": "governed_test_capability",
                    "confidence": 1.0,
                },
            }
        ],
        "blocked_evidence": [],
        "reason": None,
    }


def test_planner_declares_governed_anomaly_scan():
    spec = _ANALYSIS_REQUIREMENTS["anomalies"]
    assert spec["operator"] == "anomaly_scan"
    assert spec["dimensions"] == ["date"]
    assert "revenue" in spec["optional_metrics"]


def test_iqr_detection_is_deterministic_and_source_is_immutable():
    df = pd.DataFrame({
        "Fecha": [
            "2026-01-15",
            "2026-02-15",
            "2026-03-15",
            "2026-04-15",
            "2026-05-15",
        ],
        "Ventas": [100.0, 100.0, 100.0, 100.0, 1000.0],
    })
    before = df.copy(deep=True)

    result = _anomaly_scan(df, _task(), {"date": "Fecha", "revenue": "Ventas"})

    assert result["kind"] == "anomaly_scan"
    assert result["evidence_available"] is True
    assert result["grain"] == "month"
    assert result["period_count"] == 5
    assert result["anomaly_count"] == 1

    anomaly = result["anomalies"][0]
    assert anomaly["metric"] == "revenue"
    assert anomaly["period"] == "2026-05"
    assert anomaly["value"] == 1000.0
    assert anomaly["direction"] == "above_upper_bound"
    assert anomaly["q1"] == 100.0
    assert anomaly["q3"] == 100.0
    assert anomaly["iqr"] == 0.0
    assert anomaly["lower_bound"] == 100.0
    assert anomaly["upper_bound"] == 100.0

    governance = result["governance"]
    assert governance["deterministic"] is True
    assert governance["method"] == "iqr"
    assert governance["statistical_multiplier"] == 1.5
    assert governance["business_thresholds_invented"] is False
    assert governance["business_classification_applied"] is False
    assert governance["llm_numeric_inference"] is False
    assert governance["llm_anomaly_detection_authority"] is False

    pd.testing.assert_frame_equal(df, before)


def test_insufficient_history_fails_closed():
    df = pd.DataFrame({
        "Fecha": ["2026-01-15", "2026-02-15", "2026-03-15"],
        "Ventas": [100.0, 120.0, 130.0],
    })

    result = _anomaly_scan(df, _task(), {"date": "Fecha", "revenue": "Ventas"})

    assert result["evidence_available"] is False
    assert result["anomalies"] == []
    assert "four governed monthly observations" in result["reason"]


def test_executor_marks_insufficient_anomaly_evidence_not_executed():
    df = pd.DataFrame({
        "Fecha": ["2026-01-15", "2026-02-15", "2026-03-15"],
        "Ventas": [100.0, 120.0, 130.0],
    })

    plan = {
        "tasks": [_task()],
    }

    executed = execute_governed_analytical_plan(
        df,
        analytical_plan=plan,
        roles={"date": "Fecha", "revenue": "Ventas"},
    )

    assert executed["executed_count"] == 0
    assert executed["not_executed_count"] == 1
    item = executed["results"][0]
    assert item["execution_status"] == "NOT_EXECUTED"
    assert item["result"]["evidence_available"] is False


def test_anomaly_insight_is_fact_only_and_unclassified():
    item = {
        "task_id": "analysis_plan:anomalies",
        "analysis": "anomalies",
        "execution_status": "EXECUTED",
        "result": {
            "kind": "anomaly_scan",
            "evidence_available": True,
            "anomalies": [{
                "metric": "revenue",
                "period": "2026-05",
                "value": 1000.0,
                "direction": "above_upper_bound",
                "q1": 100.0,
                "q3": 100.0,
                "iqr": 0.0,
                "lower_bound": 100.0,
                "upper_bound": 100.0,
            }],
            "governance": {
                "deterministic": True,
            },
        },
    }

    insights, observations = _anomaly_insights(item)

    assert observations == []
    assert len(insights) == 1

    finding = insights[0]
    assert finding["insight_type"] == "statistical_anomaly"
    assert finding["severity"] is None
    assert finding["classification"] is None
    assert finding["confidence"] == 1.0
    assert finding["governance"]["calculated_fact"] is True
    assert finding["governance"]["classification_applied"] is False
    assert finding["governance"]["llm_numeric_inference"] is False
    assert finding["governance"]["llm_anomaly_detection_authority"] is False
    assert finding["governance"]["business_thresholds_invented"] is False


def test_builder_promotes_only_executed_governed_anomalies():
    executed_item = {
        "task_id": "analysis_plan:anomalies",
        "analysis": "anomalies",
        "operator": "anomaly_scan",
        "execution_status": "EXECUTED",
        "result": {
            "kind": "anomaly_scan",
            "evidence_available": True,
            "anomalies": [{
                "metric": "revenue",
                "period": "2026-05",
                "value": 1000.0,
                "direction": "above_upper_bound",
                "q1": 100.0,
                "q3": 100.0,
                "iqr": 0.0,
                "lower_bound": 100.0,
                "upper_bound": 100.0,
            }],
            "governance": {"deterministic": True},
        },
    }

    blocked_item = deepcopy(executed_item)
    blocked_item["task_id"] = "analysis_plan:blocked_anomalies"
    blocked_item["execution_status"] = "NOT_EXECUTED"

    result = build_governed_business_insights(
        analytical_results={
            "results": [executed_item, blocked_item],
        }
    )

    anomaly_insights = [
        item
        for item in result["insights"]
        if item.get("insight_type") == "statistical_anomaly"
    ]

    assert len(anomaly_insights) == 1
    assert anomaly_insights[0]["evidence_source"] == "analysis_plan:anomalies"


def test_c3_contract_version_and_no_business_policy():
    assert R10_25C3_ANOMALY_VERSION == "r10.25c3"

    source = Path(SCRIPTS / "analysis_executor.py").read_text(encoding="utf-8")
    insight_source = Path(SCRIPTS / "insight_engine.py").read_text(encoding="utf-8")

    assert '"business_thresholds_invented": False' in source
    assert '"llm_anomaly_detection_authority": False' in source
    assert '"classification_applied": False' in insight_source
    assert '"severity": None' in insight_source
