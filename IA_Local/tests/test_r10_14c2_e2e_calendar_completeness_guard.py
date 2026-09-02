from pathlib import Path
import sys

def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")

if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_14c2_e2e_calendar_completeness_guard.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print()
print("=== R10.14C.2 E2E CALENDAR COMPLETENESS GUARD ===")
print(f"Archivo: {p}")

check("business_insights_present", '"business_insights"' in t)
check("calendar_guard_flag", '"calendar_period_completeness_guard":true' in t)
check("partial_guard_flag", '"partial_periods_are_not_promoted":true' in t)
check("trend_has_observed_min_date", '"observed_min_date":' in t)
check("trend_has_observed_max_date", '"observed_max_date":' in t)
check("analytical_results_preserved", '"schema_version":"r10.14b"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)
check("profit_rule_present", "universal.profit.revenue_minus_cost.v1" in t)
check("margin_rule_present", "universal.margin_pct.revenue_cost_over_revenue.v1" in t)
check("period_completeness_present", '"period_completeness":{' in t)
check("calendar_status_present", '"calendar_status":"' in t)
check("expected_period_end_present", '"expected_period_end":"' in t)

print()
print("PASS R10.14C.2 E2E CALENDAR COMPLETENESS GUARD")
