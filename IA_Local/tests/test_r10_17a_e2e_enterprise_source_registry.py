from pathlib import Path
import sys

def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)

if len(sys.argv)<2:
    raise SystemExit("Uso: python test_r10_17a_e2e_enterprise_source_registry.py <dashboard.html>")
p=Path(sys.argv[1]); t=p.read_text(encoding="utf-8",errors="replace")
print("\n=== R10.17A E2E ENTERPRISE SOURCE REGISTRY ===")
print("Archivo:",p)
check("source_registry_present", '"enterprise_source_registry":{' in t)
check("source_registry_schema", '"schema_version":"r10.17a"' in t)
check("source_registry_default_empty", '"registry_id":"enterprise-sources"' in t and '"source_count":0' in t)
check("memory_closure_preserved", '"schema_version":"r10.16f"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)
print("\nPASS R10.17A E2E ENTERPRISE SOURCE REGISTRY")
