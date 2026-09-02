from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "IA_Local" / "scripts"))

from insight_engine import build_governed_business_insights

def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")

print()
print("=== R10.14C.4 POLICY BOUNDARY GUARD ===")

trend_results = {
    "schema_version": "r10.14b",
    "results": [{
        "task_id": "task:trend",
        "analysis": "trend",
        "execution_status": "EXECUTED",
        "result": {
            "kind": "time_trend",
            "rows": [
                {"period": "2026-06", "record_count": 100, "observed_min_date": "2026-06-01", "observed_max_date": "2026-06-30", "revenue": 100.0},
                {"period": "2026-07", "record_count": 100, "observed_min_date": "2026-07-01", "observed_max_date": "2026-07-31", "revenue": 80.0},
            ],
        },
    }],
}

trend_out = build_governed_business_insights(analytical_results=trend_results)
trend = (trend_out.get("insights") or [])[0]
check("trend_change_preserved", trend.get("change_pct") == -20.0)
check("trend_direction", trend.get("direction") == "decrease")
check("trend_severity_not_classified", trend.get("severity") is None)
check("trend_policy_not_applied", (trend.get("provenance") or {}).get("interpretation_policy") == "NOT_APPLIED")
check("trend_guard_source", (trend.get("provenance") or {}).get("source") == "r10.14c4_policy_boundary_guard")

grouped_results = {
    "schema_version": "r10.14b",
    "results": [{
        "task_id": "task:customers",
        "analysis": "customers",
        "execution_status": "EXECUTED",
        "result": {
            "kind": "grouped_analysis",
            "dimensions": ["customer"],
            "row_limit": 500,
            "returned_group_count": 5,
            "total_group_count": 5,
            "is_truncated": False,
            "rows": [
                {"customer": "A", "record_count": 1, "revenue": 24.0},
                {"customer": "B", "record_count": 1, "revenue": 19.0},
                {"customer": "C", "record_count": 1, "revenue": 19.0},
                {"customer": "D", "record_count": 1, "revenue": 19.0},
                {"customer": "E", "record_count": 1, "revenue": 19.0},
            ],
        },
    }],
}

grouped_out = build_governed_business_insights(analytical_results=grouped_results)
grouped = (grouped_out.get("insights") or [])[0]
check("concentration_below_old_25_threshold_is_reported", grouped.get("share_pct") == 24.0)
check("concentration_severity_not_classified", grouped.get("severity") is None)
check("concentration_policy_not_applied", (grouped.get("provenance") or {}).get("interpretation_policy") == "NOT_APPLIED")
check("concentration_population_complete", (grouped.get("provenance") or {}).get("population_complete") is True)

gov = grouped_out.get("governance") or {}
check("governance_no_severity_thresholds", gov.get("business_severity_thresholds_are_not_hardcoded") is True)
check("governance_no_concentration_thresholds", gov.get("concentration_thresholds_are_not_hardcoded") is True)
check("governance_deferred_to_rule_engine", gov.get("enterprise_interpretation_deferred_to_business_rule_engine") is True)

print()
print("PASS R10.14C.4 POLICY BOUNDARY GUARD")
