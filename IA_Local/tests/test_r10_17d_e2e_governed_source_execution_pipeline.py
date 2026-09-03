from pathlib import Path
import sys

def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)

if len(sys.argv) < 2:
    raise SystemExit("Uso: python test_r10_17d_e2e_governed_source_execution_pipeline.py <dashboard.html>")

p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="replace")
print("\n=== R10.17D E2E GOVERNED SOURCE EXECUTION PIPELINE ===")
print("Archivo:", p)
check("source_execution_present", '"enterprise_source_execution":{' in t)
check("source_execution_schema", '"schema_version":"r10.17d"' in t)
check("source_execution_read_only", '"read_only":true' in t)
check("source_execution_fail_closed", '"fail_closed":true' in t)
check("source_execution_precedence", '"source_data_precedence":true' in t)
check("sql_connector_preserved", '"schema_version":"r10.17c"' in t)
check("file_connector_preserved", '"schema_version":"r10.17b"' in t)
check("source_registry_preserved", '"schema_version":"r10.17a"' in t)
check("memory_closure_preserved", '"schema_version":"r10.16f"' in t)
check("freight_still_blocked", '"id":"kpi:freight"' in t and '"status":"BLOCKED"' in t)
check("coverage_still_93_94", '"percent":93.94' in t or '"coverage_pct":93.94' in t)
print("\nPASS R10.17D E2E GOVERNED SOURCE EXECUTION PIPELINE")
