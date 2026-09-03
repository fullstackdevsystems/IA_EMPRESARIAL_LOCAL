from pathlib import Path
import sys

def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)

if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_17e_e2e_query_registry_authorization_hardening.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")
print("\n=== R10.17E E2E QUERY REGISTRY & AUTHORIZATION HARDENING ===")
print("Archivo:", p)
check("query_registry_present", '"enterprise_query_registry":{' in t)
check("query_registry_schema", '"schema_version":"r10.17e"' in t)
check("approval_required", '"approval_metadata_required":true' in t)
check("sql_comments_forbidden", '"sql_comments_forbidden":true' in t)
check("strict_integer_limits", '"strict_integer_limits":true' in t)
check("source_execution_preserved", '"schema_version":"r10.17d"' in t)
check("sql_connector_preserved", '"schema_version":"r10.17c"' in t)
check("file_connector_preserved", '"schema_version":"r10.17b"' in t)
check("source_registry_preserved", '"schema_version":"r10.17a"' in t)
check("memory_closure_preserved", '"schema_version":"r10.16f"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_canonical", any(value in t for value in ('"percent":94.29', '"coverage_pct":94.29', '"percent":93.94', '"coverage_pct":93.94')))
print("\nPASS R10.17E E2E QUERY REGISTRY & AUTHORIZATION HARDENING")
