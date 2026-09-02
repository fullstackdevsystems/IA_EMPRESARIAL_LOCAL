from pathlib import Path
import sys

def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")

if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_14c4_e2e_policy_boundary_guard.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print()
print("=== R10.14C.4 E2E POLICY BOUNDARY GUARD ===")
print(f"Archivo: {p}")

check("business_insights_present", '"business_insights"' in t)
check("no_hardcoded_severity_policy", '"business_severity_thresholds_are_not_hardcoded":true' in t)
check("no_hardcoded_concentration_policy", '"concentration_thresholds_are_not_hardcoded":true' in t)
check("interpretation_deferred", '"enterprise_interpretation_deferred_to_business_rule_engine":true' in t)
check("interpretation_policy_not_applied", '"interpretation_policy":"NOT_APPLIED"' in t)
check("trend_direction_present", '"direction":"increase"' in t or '"direction":"decrease"' in t)
check("calendar_guard_preserved", '"calendar_period_completeness_guard":true' in t)
check("truncation_guard_preserved", '"truncated_grouped_results_are_not_used_for_concentration":true' in t)
check("analytical_results_preserved", '"schema_version":"r10.14b"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)
check("profit_rule_present", "universal.profit.revenue_minus_cost.v1" in t)
check("margin_rule_present", "universal.margin_pct.revenue_cost_over_revenue.v1" in t)

print()
print("PASS R10.14C.4 E2E POLICY BOUNDARY GUARD")
