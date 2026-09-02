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

print()
print("=== R10.14C.2 CALENDAR COMPLETENESS GUARD ===")

partial = {
    "results": [{
        "task_id": "analysis_plan:trend",
        "analysis": "trend",
        "execution_status": "EXECUTED",
        "result": {
            "kind": "time_trend",
            "rows": [
                {"period":"2026-01","record_count":100,"observed_min_date":"2026-01-01","observed_max_date":"2026-01-31","revenue":1000},
                {"period":"2026-02","record_count":110,"observed_min_date":"2026-02-01","observed_max_date":"2026-02-28","revenue":1200},
                {"period":"2026-03","record_count":105,"observed_min_date":"2026-03-01","observed_max_date":"2026-03-31","revenue":1250},
                {"period":"2026-04","record_count":108,"observed_min_date":"2026-04-01","observed_max_date":"2026-04-30","revenue":1300},
                {"period":"2026-05","record_count":112,"observed_min_date":"2026-05-01","observed_max_date":"2026-05-31","revenue":1400},
                {"period":"2026-06","record_count":115,"observed_min_date":"2026-06-01","observed_max_date":"2026-06-30","revenue":1500},
                {"period":"2026-07","record_count":109,"observed_min_date":"2026-07-01","observed_max_date":"2026-07-20","revenue":1200},
            ],
        },
    }]
}

out = build_governed_business_insights(analytical_results=partial)
check("calendar_partial_no_decline", not any(x.get("insight_type") == "decline" for x in out["insights"]))
obs = next(x for x in out["observations"] if x.get("observation_type") == "partial_period_comparison")
pc = obs["period_completeness"]
check("calendar_partial_status", pc["status"] == "PARTIAL")
check("calendar_status_partial", pc["calendar_status"] == "PARTIAL")
check("calendar_expected_end", pc["expected_period_end"] == "2026-07-31")
check("calendar_observed_max", pc["observed_max_date"] == "2026-07-20")
check("calendar_guard_governance", out["governance"]["calendar_period_completeness_guard"] is True)

complete = {
    "results": [{
        "task_id": "analysis_plan:trend",
        "analysis": "trend",
        "execution_status": "EXECUTED",
        "result": {
            "kind": "time_trend",
            "rows": [
                {"period":"2026-01","record_count":100,"observed_min_date":"2026-01-01","observed_max_date":"2026-01-31","revenue":1000},
                {"period":"2026-02","record_count":110,"observed_min_date":"2026-02-01","observed_max_date":"2026-02-28","revenue":1200},
                {"period":"2026-03","record_count":105,"observed_min_date":"2026-03-01","observed_max_date":"2026-03-31","revenue":1250},
                {"period":"2026-04","record_count":108,"observed_min_date":"2026-04-01","observed_max_date":"2026-04-30","revenue":1300},
                {"period":"2026-05","record_count":112,"observed_min_date":"2026-05-01","observed_max_date":"2026-05-31","revenue":1400},
                {"period":"2026-06","record_count":115,"observed_min_date":"2026-06-01","observed_max_date":"2026-06-30","revenue":1500},
                {"period":"2026-07","record_count":109,"observed_min_date":"2026-07-01","observed_max_date":"2026-07-31","revenue":1200},
            ],
        },
    }]
}

out2 = build_governed_business_insights(analytical_results=complete)
decline = next(x for x in out2["insights"] if x.get("insight_type") == "decline")
pc2 = decline["period_completeness"]
check("calendar_complete_decline_allowed", decline["change_pct"] == -20.0)
check("calendar_complete_status", pc2["status"] == "COMPARABLE")
check("calendar_complete_marker", pc2["calendar_status"] == "COMPLETE")
check("volume_comparable_marker", pc2["volume_status"] == "COMPARABLE")

print()
print("PASS R10.14C.2 CALENDAR COMPLETENESS GUARD")
