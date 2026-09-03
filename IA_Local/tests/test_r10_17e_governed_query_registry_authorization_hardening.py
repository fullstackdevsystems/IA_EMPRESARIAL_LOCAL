from pathlib import Path
import json
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "scripts"
if str(S) not in sys.path:
    sys.path.insert(0, str(S))

from enterprise_query_registry import ENTERPRISE_QUERY_REGISTRY_VERSION, load_governed_enterprise_query_registry, resolve_governed_enterprise_query
from enterprise_source_execution import execute_registered_source
from enterprise_source_registry import load_governed_enterprise_source_registry
from enterprise_sql_server_connector import validate_read_only_sql

def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)

print("\n=== R10.17E GOVERNED QUERY REGISTRY & AUTHORIZATION HARDENING ===")
check("version", ENTERPRISE_QUERY_REGISTRY_VERSION == "r10.17e")
check("sql_comments_blocked_line", validate_read_only_sql("SELECT 1 -- comment")["valid"] is False)
check("sql_comments_blocked_block", validate_read_only_sql("SELECT /* comment */ 1")["valid"] is False)

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    good = td / "queries.json"
    good.write_text(json.dumps({
        "schema_version":"r10.17e","registry_id":"queries-demo","queries_version":"1",
        "queries":[{
            "query_id":"ventas_resumen","source_id":"demo.erp.sql","status":"ENABLED",
            "sql":"SELECT TOP 100 Cliente, Venta FROM dbo.Ventas",
            "row_limit":5000,"timeout_seconds":30,
            "approved_by":"admin-demo","approved_at":"2026-09-02T19:30:00-07:00"
        }]
    }), encoding="utf-8")
    registry = load_governed_enterprise_query_registry(str(good))
    check("registry_loaded", registry["status"] == "LOADED")
    check("query_count", registry["query_count"] == 1)
    check("fingerprint", len(registry["queries"][0]["query_fingerprint_sha256"]) == 64)
    resolved = resolve_governed_enterprise_query(registry=registry, source_id="demo.erp.sql", query_id="ventas_resumen")
    check("query_resolved", resolved["status"] == "APPROVED")
    check("approval_metadata", resolved["query"]["approved_by"] == "admin-demo")
    check("wrong_source_blocked", resolve_governed_enterprise_query(registry=registry, source_id="other.sql", query_id="ventas_resumen")["status"] == "BLOCKED")

    forged = dict(registry)
    forged["status"] = "EMPTY"
    check("non_loaded_registry_blocked", resolve_governed_enterprise_query(registry=forged, source_id="demo.erp.sql", query_id="ventas_resumen")["status"] == "BLOCKED")

    tampered = dict(registry)
    tampered["queries"] = [dict(registry["queries"][0], sql="SELECT 2")]
    check("tampered_query_blocked", resolve_governed_enterprise_query(registry=tampered, source_id="demo.erp.sql", query_id="ventas_resumen")["reason"] == "query_fingerprint_mismatch")

    source_path = td / "sources.json"
    source_path.write_text(json.dumps({
        "schema_version":"r10.17a","registry_id":"sources-demo","sources_version":"1",
        "sources":[{
            "source_id":"demo.erp.sql","kind":"sql_server","status":"ENABLED","name":"ERP",
            "scope":{},"locator":{"server":"SQL01","database":"ERP"},
            "credential_ref":"env:IA_SQL_ERP","access":{"mode":"read_only"}
        }]
    }), encoding="utf-8")
    source_registry = load_governed_enterprise_source_registry(str(source_path))
    check("execution_missing_registry_blocked", execute_registered_source(
        registry=source_registry, source_id="demo.erp.sql", workspace_root=td,
        query_id="ventas_resumen",
    )["reason"] == "query_registry_required")
    connector_result = {
        "schema_version":"r10.17c","status":"OPENED","dataframe":"sentinel",
        "provenance":{"query_id":"ventas_resumen"},
    }
    with patch("enterprise_source_execution.execute_governed_sql_query", return_value=connector_result) as execute_sql:
        executed = execute_registered_source(
            registry=source_registry, source_id="demo.erp.sql", workspace_root=td,
            query_id="ventas_resumen", query_registry=registry,
        )
    check("execution_registry_query_opened", executed["status"] == "OPENED")
    dispatched_source = execute_sql.call_args.kwargs["source"]
    check("execution_dispatches_registry_query", dispatched_source["approved_queries"] == [registry["queries"][0]])

    bad = json.loads(good.read_text(encoding="utf-8"))
    bad["queries"][0]["row_limit"] = True
    p = td / "bad_bool.json"; p.write_text(json.dumps(bad), encoding="utf-8")
    check("bool_limit_blocked", load_governed_enterprise_query_registry(str(p))["status"] == "INVALID")

    bad = json.loads(good.read_text(encoding="utf-8"))
    bad["queries"][0].pop("approved_by")
    p = td / "bad_approval.json"; p.write_text(json.dumps(bad), encoding="utf-8")
    check("missing_approval_blocked", load_governed_enterprise_query_registry(str(p))["status"] == "INVALID")

    bad = json.loads(good.read_text(encoding="utf-8"))
    bad["queries"][0]["sql"] = "SELECT 1 -- hidden"
    p = td / "bad_comment.json"; p.write_text(json.dumps(bad), encoding="utf-8")
    check("comment_sql_blocked", load_governed_enterprise_query_registry(str(p))["status"] == "INVALID")

    p = td / "source_missing_scope.json"
    p.write_text(json.dumps({
        "schema_version":"r10.17a","registry_id":"bad","sources_version":"1",
        "sources":[{
            "source_id":"demo.erp.sql","kind":"sql_server","status":"ENABLED","name":"ERP",
            "locator":{"server":"SQL01","database":"ERP"},"credential_ref":"env:IA_SQL_ERP",
            "access":{"mode":"read_only"}
        }]
    }), encoding="utf-8")
    check("missing_scope_blocked", load_governed_enterprise_source_registry(str(p))["status"] == "INVALID")

default = load_governed_enterprise_query_registry(str(ROOT / "config" / "enterprise_queries.json"))
check("default_empty", default["status"] == "EMPTY" and default["query_count"] == 0)
sql_connector = (S / "enterprise_sql_server_connector.py").read_text(encoding="utf-8", errors="replace")
check("read_committed_default", "READ COMMITTED" in sql_connector)
check("read_uncommitted_removed", "READ UNCOMMITTED" not in sql_connector)
source_execution = (S / "enterprise_source_execution.py").read_text(encoding="utf-8", errors="replace")
check("execution_uses_query_registry", "resolve_governed_enterprise_query" in source_execution)
check("execution_requires_query_registry", "query_registry_required" in source_execution)
builder = (S / "dashboard_spec_builder.py").read_text(encoding="utf-8", errors="replace")
check("builder_query_registry_import", "build_query_registry_capability_audit" in builder)
check("builder_query_registry_audit", '"enterprise_query_registry"' in builder)
print("\nPASS R10.17E GOVERNED QUERY REGISTRY & AUTHORIZATION HARDENING")
