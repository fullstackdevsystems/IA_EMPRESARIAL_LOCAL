from pathlib import Path
import sys


def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_15c_e2e_context_scope_governance.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print()
print("=== R10.15C E2E CONTEXT & SCOPE GOVERNANCE ===")
print(f"Archivo: {p}")

check("r10_15a_interpreter_preserved", '"schema_version":"r10.15a"' in t)
check("r10_15b_registry_preserved", '"schema_version":"r10.15b"' in t)
check("context_governance_present", '"context_governance":{' in t)
check("context_schema", '"schema_version":"r10.15c"' in t)
check("context_unconfigured", '"status":"UNCONFIGURED"' in t)
check("context_empty", '"context":{}' in t)
check("explicit_context_required", '"explicit_context_required_for_scoped_rules":true' in t)
check("unknown_scope_not_inferred", '"unknown_scope_is_never_inferred":true' in t)
check("fail_closed", '"fail_closed":true' in t)
check("no_rules_applied_without_context", '"active_rule_count":0' in t and '"applied_rule_count":0' in t)

check("r10_14c_preserved", '"business_insights"' in t and '"schema_version":"r10.14c"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)
check("profit_rule_present", "universal.profit.revenue_minus_cost.v1" in t)
check("margin_rule_present", "universal.margin_pct.revenue_cost_over_revenue.v1" in t)

print()
print("PASS R10.15C E2E CONTEXT & SCOPE GOVERNANCE")
