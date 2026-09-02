from pathlib import Path
import sys
def check(n,c):
    if not c: print("FAIL",n); raise AssertionError(n)
    print("PASS",n)
if len(sys.argv)<2: raise SystemExit("Uso: python test_r10_16a_e2e_governed_enterprise_knowledge_registry.py <dashboard.html>")
p=Path(sys.argv[1]); t=p.read_text(encoding="utf-8",errors="replace")
print("\n=== R10.16A E2E GOVERNED ENTERPRISE KNOWLEDGE REGISTRY ==="); print("Archivo:",p)
check("knowledge_registry_present",'"enterprise_knowledge_registry":{' in t)
check("knowledge_registry_schema",'"schema_version":"r10.16a"' in t)
check("knowledge_registry_empty",'"registry_id":"enterprise-knowledge"' in t and '"entry_count":0' in t)
check("source_precedence",'"knowledge_does_not_override_source_data":true' in t)
check("no_metric_authority",'"knowledge_does_not_create_metrics_by_itself":true' in t)
check("r10_15f_preserved",'"schema_version":"r10.15f"' in t)
check("freight_still_blocked",'"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94",'"percent":93.94' in t or '"coverage_pct":93.94' in t)
print("\nPASS R10.16A E2E GOVERNED ENTERPRISE KNOWLEDGE REGISTRY")
