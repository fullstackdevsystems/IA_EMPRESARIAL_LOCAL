from pathlib import Path
import sys

def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)

if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_17b_e2e_file_connector.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")

print("\n=== R10.17B E2E GOVERNED FILE CONNECTOR ===")
print("Archivo:", p)

check("file_connector_present", '\"enterprise_file_connector\":{' in t)
check("file_connector_schema", '\"schema_version\":\"r10.17b\"' in t)
check("file_connector_available", '\"status\":\"AVAILABLE\"' in t)
check("read_only", '\"read_only\":true' in t)
check("workspace_boundary", '\"workspace_boundary_enforced\":true' in t)
check("source_registry_preserved", '\"schema_version\":\"r10.17a\"' in t)
check("memory_closure_preserved", '\"schema_version\":\"r10.16f\"' in t)
check("freight_still_blocked", '\"id\":\"kpi:freight\"' in t and '\"status\":\"BLOCKED\"' in t)
check("coverage_still_93_94", '\"percent\":93.94' in t or '\"coverage_pct\":93.94' in t)

print("\nPASS R10.17B E2E GOVERNED FILE CONNECTOR")
