from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "scripts"
if str(S) not in sys.path:
    sys.path.insert(0, str(S))

from enterprise_sql_server_connector import (
    ENTERPRISE_SQL_CONNECTOR_VERSION,
    build_sql_server_connector_capability_audit,
    execute_governed_sql_query,
    resolve_approved_query,
    validate_read_only_sql,
)

def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)

print("\n=== R10.17C GOVERNED SQL SERVER CONNECTOR ===")
check("version", ENTERPRISE_SQL_CONNECTOR_VERSION == "r10.17c")
check("select_allowed", validate_read_only_sql("SELECT TOP 10 * FROM Ventas")["valid"] is True)
check("cte_allowed", validate_read_only_sql("WITH x AS (SELECT 1 AS a) SELECT * FROM x")["valid"] is True)
check("insert_blocked", validate_read_only_sql("INSERT INTO X VALUES (1)")["valid"] is False)
check("update_blocked", validate_read_only_sql("UPDATE X SET A=1")["valid"] is False)
check("delete_blocked", validate_read_only_sql("DELETE FROM X")["valid"] is False)
check("exec_blocked", validate_read_only_sql("EXEC sp_help")["valid"] is False)
check("select_into_blocked", validate_read_only_sql("SELECT * INTO X FROM Y")["valid"] is False)
check("multi_statement_blocked", validate_read_only_sql("SELECT 1; SELECT 2")["valid"] is False)

source = {
    "source_id": "demo.erp.sql",
    "kind": "sql_server",
    "status": "ENABLED",
    "name": "ERP SQL",
    "scope": {"company_id": "DEMO"},
    "locator": {"server": "SQL01", "database": "ERP"},
    "credential_ref": "env:IA_SQL_ERP",
    "access": {"mode": "read_only"},
    "approved_queries": [{
        "query_id": "ventas_resumen",
        "sql": "SELECT TOP 100 Cliente, Venta FROM dbo.Ventas",
        "row_limit": 5000,
        "timeout_seconds": 30
    }]
}
approved = resolve_approved_query(source=source, query_id="ventas_resumen")
check("approved_query_resolved", approved["status"] == "APPROVED")
check("query_fingerprint", len(approved["query"]["query_fingerprint_sha256"]) == 64)
check("row_limit", approved["query"]["row_limit"] == 5000)
check("timeout", approved["query"]["timeout_seconds"] == 30)
check("unapproved_query_blocked", resolve_approved_query(source=source, query_id="no_existe")["status"] == "BLOCKED")

no_credential = dict(source)
no_credential.pop("credential_ref")
check("credential_ref_required", resolve_approved_query(source=no_credential, query_id="ventas_resumen")["status"] == "BLOCKED")

bad_source = dict(source)
bad_source["approved_queries"] = [{
    "query_id": "evil",
    "sql": "DELETE FROM dbo.Ventas",
    "row_limit": 10,
    "timeout_seconds": 5
}]
check("dangerous_approved_query_still_blocked", resolve_approved_query(source=bad_source, query_id="evil")["status"] == "BLOCKED")

execution = execute_governed_sql_query(source=source, query_id="ventas_resumen")
check("missing_env_fails_closed", execution["status"] == "BLOCKED" and execution["reason"] in {"credential_unavailable", "pyodbc_unavailable"})

audit = build_sql_server_connector_capability_audit()
check("audit_schema", audit["schema_version"] == "r10.17c")
check("audit_read_only", audit["governance"]["read_only"] is True)
check("audit_approved_only", audit["governance"]["approved_query_only"] is True)
check("audit_no_formula_authority", audit["governance"]["formula_authority"] is False)

builder = (S / "dashboard_spec_builder.py").read_text(encoding="utf-8", errors="replace")
check("builder_import", "build_sql_server_connector_capability_audit" in builder)
check("builder_audit", '\"enterprise_sql_server_connector\"' in builder)
print("\nPASS R10.17C GOVERNED SQL SERVER CONNECTOR")
