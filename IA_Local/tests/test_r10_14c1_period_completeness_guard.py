from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from insight_engine import build_governed_business_insights

def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")

print("\n=== R10.14C.1 PERIOD COMPLETENESS GUARD ===")

partial = {"results":[{"task_id":"analysis_plan:trend","analysis":"trend","execution_status":"EXECUTED","result":{"kind":"time_trend","rows":[
{"period":"2026-01","record_count":100,"revenue":1000},{"period":"2026-02","record_count":110,"revenue":1200},{"period":"2026-03","record_count":105,"revenue":1250},{"period":"2026-04","record_count":108,"revenue":1300},{"period":"2026-05","record_count":112,"revenue":1400},{"period":"2026-06","record_count":115,"revenue":1500},{"period":"2026-07","record_count":50,"revenue":700}]}}]}
out = build_governed_business_insights(analytical_results=partial)
check("partial_no_growth_decline", not any(x.get("insight_type") in {"growth","decline"} for x in out["insights"]))
obs = next(x for x in out["observations"] if x.get("observation_type") == "partial_period_comparison")
check("partial_observation", obs["comparison_status"] == "NOT_COMPARABLE")
check("partial_period", obs["current_period"] == "2026-07")
check("partial_ratio", obs["period_completeness"]["ratio"] < 0.8)
check("partial_governance", out["governance"]["partial_periods_are_not_promoted"] is True)

comparable = {"results":[{"task_id":"analysis_plan:trend","analysis":"trend","execution_status":"EXECUTED","result":{"kind":"time_trend","rows":[
{"period":"2026-01","record_count":100,"revenue":1000},{"period":"2026-02","record_count":110,"revenue":1200},{"period":"2026-03","record_count":105,"revenue":1250},{"period":"2026-04","record_count":108,"revenue":1300},{"period":"2026-05","record_count":112,"revenue":1400},{"period":"2026-06","record_count":115,"revenue":1500},{"period":"2026-07","record_count":109,"revenue":1200}]}}]}
out2 = build_governed_business_insights(analytical_results=comparable)
decline = next(x for x in out2["insights"] if x.get("insight_type") == "decline")
check("comparable_decline_allowed", decline["change_pct"] == -20.0)
check("volume_comparable_status", decline["period_completeness"]["volume_status"] == "COMPARABLE")
check("calendar_unknown_without_dates", decline["period_completeness"]["calendar_status"] == "UNKNOWN")
check("overall_unknown_without_calendar_evidence", decline["period_completeness"]["status"] == "UNKNOWN")
print("\nPASS R10.14C.1 PERIOD COMPLETENESS GUARD")

