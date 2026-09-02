from pathlib import Path
import sys

def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")

if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_15f_e2e_enterprise_rule_engine_closure.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print()
print("=== R10.15F E2E ENTERPRISE BUSINESS RULE ENGINE CLOSURE ===")
print(f"Archivo: {p}")

check("closure_present", '"enterprise_rule_governance":{' in t)
check("closure_schema", '"schema_version":"r10.15f"' in t)
check("closure_ready", '"status":"READY"' in t)
check("version_contract_ok", '"version_contract_ok":true' in t)
check("safety_contract_ok", '"safety_contract_ok":true' in t)
check("phase_consolidated", '"phase_r10_15_consolidated":true' in t)
check("invalid_context_business_guard", '"invalid_context_blocks_business_rule_execution":true' in t)
check("invalid_context_metric_guard", '"invalid_context_blocks_enterprise_metric_rule_execution":true' in t)
check("invalid_as_of_guard", '"invalid_explicit_as_of_is_fail_closed":true' in t)

check("r10_15a_preserved", '"schema_version":"r10.15a"' in t)
check("r10_15c_preserved", '"schema_version":"r10.15c"' in t)
check("r10_15d_preserved", '"schema_version":"r10.15d"' in t)
check("r10_15e_preserved", '"schema_version":"r10.15e"' in t)
check("r10_14c_preserved", '"business_insights"' in t and '"schema_version":"r10.14c"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("freight_analysis_still_blocked", '"id":"analysis:freight_analysis"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)

print()
print("PASS R10.15F E2E ENTERPRISE BUSINESS RULE ENGINE CLOSURE")
