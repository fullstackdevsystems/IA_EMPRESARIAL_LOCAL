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
print("=== R10.14C.3 SAFE CONCENTRATION TRUNCATION GUARD ===")

truncated = {
    "results": [{
        "task_id": "analysis_plan:customers",
        "analysis": "customer_profile",
        "execution_status": "EXECUTED",
        "result": {
            "kind": "grouped_analysis",
            "dimensions": ["customer"],
            "row_limit": 500,
            "returned_group_count": 500,
            "total_group_count": 620,
            "is_truncated": True,
            "rows": [
                {"customer": "A", "record_count": 10, "revenue": 900.0},
                {"customer": "B", "record_count": 5, "revenue": 100.0},
            ],
        },
    }]
}

out = build_governed_business_insights(analytical_results=truncated)
check("truncated_no_concentration", not any(x.get("insight_type") == "concentration" for x in out["insights"]))
obs = next(x for x in out["observations"] if x.get("observation_type") == "concentration_not_assessed")
check("truncated_observation", obs["total_group_count"] == 620)
check("truncated_returned_count", obs["returned_group_count"] == 500)
check("truncated_guard_source", obs["provenance"]["source"] == "r10.14c3_safe_concentration_guard")
check("truncated_governance", out["governance"]["truncated_grouped_results_are_not_used_for_concentration"] is True)

complete = {
    "results": [{
        "task_id": "analysis_plan:customers",
        "analysis": "customer_profile",
        "execution_status": "EXECUTED",
        "result": {
            "kind": "grouped_analysis",
            "dimensions": ["customer"],
            "row_limit": 500,
            "returned_group_count": 3,
            "total_group_count": 3,
            "is_truncated": False,
            "rows": [
                {"customer": "A", "record_count": 10, "revenue": 600.0},
                {"customer": "B", "record_count": 5, "revenue": 250.0},
                {"customer": "C", "record_count": 2, "revenue": 150.0},
            ],
        },
    }]
}

out2 = build_governed_business_insights(analytical_results=complete)
ins = next(x for x in out2["insights"] if x.get("insight_type") == "concentration")
check("complete_concentration_allowed", ins["share_pct"] == 60.0)
check("complete_entity", ins["entity"]["customer"] == "A")
check("complete_total", ins["total_value"] == 1000.0)
check("complete_population_provenance", ins["provenance"]["population_complete"] is True)

print()
print("PASS R10.14C.3 SAFE CONCENTRATION TRUNCATION GUARD")
