from pathlib import Path
import sys

def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")

if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_14c1_e2e_period_completeness_guard.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")
print("\n=== R10.14C.1 E2E PERIOD COMPLETENESS GUARD ===")
print(f"Archivo: {p}")
check("business_insights_present", '"business_insights"' in t)
check("partial_guard_flag", '"partial_periods_are_not_promoted":true' in t)
check("analytical_results_preserved", '"schema_version":"r10.14b"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)
check("profit_rule_present", "universal.profit.revenue_minus_cost.v1" in t)
check("margin_rule_present", "universal.margin_pct.revenue_cost_over_revenue.v1" in t)
print("\nPASS R10.14C.1 E2E PERIOD COMPLETENESS GUARD")
