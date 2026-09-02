from pathlib import Path
import sys


def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)


if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_16c_e2e_governed_knowledge_context_injection.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print()
print("=== R10.16C E2E GOVERNED KNOWLEDGE CONTEXT INJECTION ===")
print("Archivo:", p)

check("knowledge_interpretation_present", '"enterprise_knowledge_interpretation":{' in t)
check("knowledge_injection_schema", '"schema_version":"r10.16c"' in t)
check("computational_authority_false", '"computational_authority":false' in t)
check("formula_authority_false", '"formula_authority":false' in t)
check("source_data_precedence", '"source_data_precedence":true' in t)
check("capability_precedence", '"capability_resolution_precedence":true' in t)
check("r10_16b_preserved", '"schema_version":"r10.16b"' in t)
check("r10_16a_preserved", '"schema_version":"r10.16a"' in t)
check("r10_15f_preserved", '"schema_version":"r10.15f"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)

print()
print("PASS R10.16C E2E GOVERNED KNOWLEDGE CONTEXT INJECTION")
