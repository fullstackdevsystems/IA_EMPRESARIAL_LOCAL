from pathlib import Path
import sys

def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")

if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_14c3_e2e_safe_concentration_guard.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print()
print("=== R10.14C.3 E2E SAFE CONCENTRATION GUARD ===")
print(f"Archivo: {p}")

check("business_insights_present", '"business_insights"' in t)
check("truncation_guard_flag", '"truncated_grouped_results_are_not_used_for_concentration":true' in t)
check("calendar_guard_preserved", '"calendar_period_completeness_guard":true' in t)
check("partial_guard_preserved", '"partial_periods_are_not_promoted":true' in t)
check("analytical_results_preserved", '"schema_version":"r10.14b"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)
check("profit_rule_present", "universal.profit.revenue_minus_cost.v1" in t)
check("margin_rule_present", "universal.margin_pct.revenue_cost_over_revenue.v1" in t)

has_grouped = '"kind":"grouped_analysis"' in t

if has_grouped:
    check("grouped_total_count_present", '"total_group_count":' in t)
    check("grouped_returned_count_present", '"returned_group_count":' in t)
    check("grouped_truncation_marker_present", '"is_truncated":' in t)

    if '"is_truncated":true' in t:
        check("truncated_not_promoted", '"observation_type":"concentration_not_assessed"' in t)
        print("INFO grouped_analysis=APPLICABLE truncated=true")
    else:
        print("INFO grouped_analysis=APPLICABLE truncated=false")
else:
    print("PASS grouped_analysis_not_applicable")
    print("INFO No grouped_analysis was executed by this analytical plan.")
    print("INFO Truncation behavior remains covered by the deterministic static test.")

print()
print("PASS R10.14C.3 E2E SAFE CONCENTRATION GUARD")
