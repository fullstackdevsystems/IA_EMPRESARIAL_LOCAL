from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from insight_engine import build_governed_business_insights, INSIGHT_VERSION
from dashboard_spec_builder import build_dashboard_spec


def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


print("\n=== R10.14C GOVERNED BUSINESS INSIGHTS ===")

analytical_results = {
    "results": [
        {
            "task_id": "analysis_plan:trend",
            "analysis": "trend",
            "execution_status": "EXECUTED",
            "result": {
                "kind": "time_trend",
                "rows": [
                    {"period": "2026-01", "revenue": 1000.0, "profit": 100.0},
                    {"period": "2026-02", "revenue": 800.0, "profit": 120.0},
                ],
            },
        },
        {
            "task_id": "analysis_plan:customer_profile",
            "analysis": "customer_profile",
            "execution_status": "EXECUTED",
            "result": {
                "kind": "grouped_analysis",
                "dimensions": ["customer"],
                "rows": [
                    {"customer": "A", "revenue": 700.0},
                    {"customer": "B", "revenue": 200.0},
                    {"customer": "C", "revenue": 100.0},
                ],
            },
        },
        {
            "task_id": "analysis_plan:freight_analysis",
            "analysis": "freight_analysis",
            "execution_status": "NOT_EXECUTED",
            "reason": "Blocked freight evidence.",
            "result": None,
        },
    ]
}

out = build_governed_business_insights(analytical_results=analytical_results)

check("version", INSIGHT_VERSION == "r10.14c" and out["schema_version"] == "r10.14c")
check("mode", out["mode"] == "deterministic-evidence-only")
decline = next(x for x in out["insights"] if x["insight_type"] == "decline" and x["metric"] == "revenue")
check("decline_detected", decline["change_pct"] == -20.0)
check("decline_evidence", decline["previous_value"] == 1000.0 and decline["current_value"] == 800.0)
check("decline_confidence", decline["confidence"] == 1.0)
growth = next(x for x in out["insights"] if x["insight_type"] == "growth" and x["metric"] == "profit")
check("growth_detected", growth["change_pct"] == 20.0)
concentration = next(x for x in out["insights"] if x["insight_type"] == "concentration")
check("concentration_detected", concentration["share_pct"] == 70.0)
check("concentration_entity", concentration["entity"]["customer"] == "A")
check("blocked_not_promoted", not any(x.get("evidence_source") == "analysis_plan:freight_analysis" for x in out["insights"]))
check("blocked_observation_kept", any(x.get("analysis") == "freight_analysis" for x in out["observations"]))
check("no_llm_numeric_inference", out["governance"]["llm_numeric_inference"] is False)
check("executed_only", out["governance"]["uses_executed_results_only"] is True)
check("builder_integrated", callable(build_dashboard_spec))

print("\nPASS R10.14C GOVERNED BUSINESS INSIGHTS")
