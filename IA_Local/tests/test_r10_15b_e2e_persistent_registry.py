from pathlib import Path
import sys


def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_15b_e2e_persistent_registry.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print()
print("=== R10.15B E2E PERSISTENT BUSINESS RULE REGISTRY ===")
print(f"Archivo: {p}")

check("r10_15a_interpreter_preserved", '"schema_version":"r10.15a"' in t)
check("registry_embedded", '"registry":{' in t)
check("registry_schema", '"schema_version":"r10.15b"' in t)
check("registry_id", '"registry_id":"enterprise-business-rules"' in t)
check("registry_ruleset", '"ruleset_version":"unconfigured"' in t)
check("registry_empty", '"rule_count":0' in t)
check("registry_status_empty", '"status":"EMPTY"' in t)
check("fingerprint_present", '"fingerprint_sha256":"' in t)
check("no_rules_applied", '"active_rule_count":0' in t and '"applied_rule_count":0' in t)

check("r10_14c_preserved", '"business_insights"' in t and '"schema_version":"r10.14c"' in t)
check("no_default_thresholds", '"default_enterprise_thresholds":false' in t)
check("no_arbitrary_eval", '"arbitrary_expression_evaluation":false' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)
check("profit_rule_present", "universal.profit.revenue_minus_cost.v1" in t)
check("margin_rule_present", "universal.margin_pct.revenue_cost_over_revenue.v1" in t)

print()
print("PASS R10.15B E2E PERSISTENT BUSINESS RULE REGISTRY")
