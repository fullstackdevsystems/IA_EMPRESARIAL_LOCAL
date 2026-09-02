from pathlib import Path
import sys


def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_15a_e2e_business_rule_engine.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print()
print("=== R10.15A E2E BUSINESS RULE ENGINE ===")
print(f"Archivo: {p}")

check("business_insights_preserved", '"business_insights"' in t and '"schema_version":"r10.14c"' in t)
check("rule_interpretation_present", '"business_rule_interpretation"' in t)
check("r10_15a_schema", '"schema_version":"r10.15a"' in t)
check("governed_rule_mode", '"mode":"governed-whitelist-business-rules"' in t)
check("no_default_thresholds", '"default_enterprise_thresholds":false' in t)
check("no_arbitrary_eval", '"arbitrary_expression_evaluation":false' in t)
check("whitelist_only", '"whitelist_operators_only":true' in t)
check("explicit_registry_required", '"explicit_registry_required":true' in t)
check("scope_guard", '"scope_guard":true' in t)
check("effective_date_guard", '"effective_date_guard":true' in t)
check("empty_default_registry", '"active_rule_count":0' in t and '"applied_rule_count":0' in t)

check("c4_policy_preserved", '"enterprise_interpretation_deferred_to_business_rule_engine":true' in t)
check("c3_guard_preserved", '"truncated_grouped_results_are_not_used_for_concentration":true' in t)
check("c2_guard_preserved", '"calendar_period_completeness_guard":true' in t)
check("analytical_results_preserved", '"schema_version":"r10.14b"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)
check("profit_rule_present", "universal.profit.revenue_minus_cost.v1" in t)
check("margin_rule_present", "universal.margin_pct.revenue_cost_over_revenue.v1" in t)

print()
print("PASS R10.15A E2E BUSINESS RULE ENGINE")
