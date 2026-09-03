from pathlib import Path
import sys

def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)

if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_17c_e2e_sql_server_connector.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")
print("\n=== R10.17C E2E GOVERNED SQL SERVER CONNECTOR ===")
print("Archivo:", p)
check("sql_connector_present", '\"enterprise_sql_server_connector\":{' in t)
check("sql_connector_schema", '\"schema_version\":\"r10.17c\"' in t)
check("read_only", '\"read_only\":true' in t)
check("approved_query_only", '\"approved_query_only\":true' in t)
check("credentials_not_serialized", '\"credential_value_not_serialized\":true' in t)
check("file_connector_preserved", '\"schema_version\":\"r10.17b\"' in t)
check("source_registry_preserved", '\"schema_version\":\"r10.17a\"' in t)
check("memory_closure_preserved", '\"schema_version\":\"r10.16f\"' in t)
check("freight_still_blocked", '\"id\":\"kpi:freight\"' in t and '\"status\":\"BLOCKED\"' in t)
check("coverage_canonical", any(value in t for value in ('"percent":94.29', '"coverage_pct":94.29', '"percent":93.94', '"coverage_pct":93.94')))
print("\nPASS R10.17C E2E GOVERNED SQL SERVER CONNECTOR")
