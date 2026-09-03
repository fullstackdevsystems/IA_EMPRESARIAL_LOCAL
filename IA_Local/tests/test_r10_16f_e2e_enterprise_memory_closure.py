from pathlib import Path
import sys

def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)

if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_16f_e2e_enterprise_memory_closure.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print()
print("=== R10.16F E2E ENTERPRISE MEMORY CLOSURE ===")
print("Archivo:", p)

check("memory_closure_present", '"enterprise_memory_closure":{' in t)
check("memory_closure_schema", '"schema_version":"r10.16f"' in t)
check("lifecycle_consolidated", '"consolidated":true' in t)
check("raw_content_not_serialized", '"raw_knowledge_content_serialized":false' in t)
check("knowledge_non_executable", '"prompt_instructions_inside_knowledge_are_non_executable":true' in t)
check("no_computational_authority", '"computational_authority":false' in t)
check("no_formula_authority", '"formula_authority":false' in t)
check("source_data_precedence", '"knowledge_cannot_override_source_data":true' in t)
check("r10_16c_preserved", '"schema_version":"r10.16c"' in t)
check("r10_16b_preserved", '"schema_version":"r10.16b"' in t)
check("r10_16a_preserved", '"schema_version":"r10.16a"' in t)
check("r10_15f_preserved", '"schema_version":"r10.15f"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_canonical", any(value in t for value in ('"percent":94.29', '"coverage_pct":94.29', '"percent":93.94', '"coverage_pct":93.94')))

print()
print("PASS R10.16F E2E ENTERPRISE MEMORY CLOSURE")
