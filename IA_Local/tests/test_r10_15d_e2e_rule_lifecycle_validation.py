from pathlib import Path
import sys


def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_15d_e2e_rule_lifecycle_validation.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print()
print("=== R10.15D E2E RULE LIFECYCLE & VALIDATION ===")
print(f"Archivo: {p}")

check("registry_schema_r10_15d", '"schema_version":"r10.15d"' in t)
check("registry_empty", '"status":"EMPTY"' in t)
check("registry_rule_count_zero", '"rule_count":0' in t)
check("duplicate_guard", '"duplicate_rule_ids_are_rejected":true' in t)
check("effective_range_guard", '"invalid_effective_ranges_are_rejected":true' in t)
check("priority_guard", '"invalid_priorities_are_rejected":true' in t)
check("shape_guard", '"invalid_rule_shapes_are_rejected":true' in t)

check("r10_15a_preserved", '"schema_version":"r10.15a"' in t)
check("r10_15c_context_preserved", '"schema_version":"r10.15c"' in t)
check("no_rules_applied", '"active_rule_count":0' in t and '"applied_rule_count":0' in t)
check("r10_14c_preserved", '"business_insights"' in t and '"schema_version":"r10.14c"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)

print()
print("PASS R10.15D E2E RULE LIFECYCLE & VALIDATION")
