from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "scripts"
if str(S) not in sys.path:
    sys.path.insert(0, str(S))

from enterprise_source_registry import load_governed_enterprise_source_registry, resolve_governed_enterprise_sources
from enterprise_file_connector import ENTERPRISE_FILE_CONNECTOR_VERSION, build_file_connector_capability_audit, open_governed_file_source

def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)

print("\n=== R10.17B GOVERNED SOURCE RESOLUTION & FILE CONNECTOR ===")

with tempfile.TemporaryDirectory() as td:
    workspace = Path(td).resolve()
    entrada = workspace / "Entrada"
    entrada.mkdir(parents=True)
    csv_path = entrada / "ventas.csv"
    csv_path.write_text("cliente,venta\nA,100\nB,200\n", encoding="utf-8")

    registry_path = workspace / "sources.json"
    registry_path.write_text(json.dumps({
        "schema_version": "r10.17a",
        "registry_id": "demo",
        "sources_version": "1",
        "sources": [{
            "source_id": "demo.sales.csv",
            "kind": "csv",
            "status": "ENABLED",
            "name": "Ventas CSV",
            "scope": {"company_id": "DEMO"},
            "locator": {"relative_path": "Entrada/ventas.csv"},
            "access": {"mode": "read_only"}
        }]
    }), encoding="utf-8")

    registry = load_governed_enterprise_source_registry(str(registry_path))
    check("version", ENTERPRISE_FILE_CONNECTOR_VERSION == "r10.17b")
    check("registry_loaded", registry["status"] == "LOADED")

    resolved = resolve_governed_enterprise_sources(registry=registry, context={"company_id": "DEMO"}, kinds=["csv", "excel"])
    check("source_resolved", resolved["status"] == "RESOLVED" and resolved["source_count"] == 1)

    opened = open_governed_file_source(source=resolved["sources"][0], workspace_root=workspace)
    check("opened", opened["status"] == "OPENED")
    check("rows", len(opened["dataframe"]) == 2)
    check("columns", list(opened["dataframe"].columns) == ["cliente", "venta"])
    check("fingerprint", len(opened["provenance"]["fingerprint_sha256"]) == 64)
    check("relative_provenance", opened["provenance"]["relative_path"] == "Entrada/ventas.csv")
    check("read_only", opened["governance"]["read_only"] is True)
    check("source_precedence", opened["governance"]["source_data_precedence"] is True)

    wrong_ext = dict(resolved["sources"][0])
    wrong_ext["kind"] = "excel"
    mismatch = open_governed_file_source(source=wrong_ext, workspace_root=workspace)
    check("extension_mismatch_blocked", mismatch["status"] == "BLOCKED" and mismatch["reason"] == "kind_extension_mismatch")

    traversal = dict(resolved["sources"][0])
    traversal["locator"] = {"relative_path": "../outside.csv"}
    check("path_traversal_blocked", open_governed_file_source(source=traversal, workspace_root=workspace)["status"] == "BLOCKED")

    disabled = dict(resolved["sources"][0])
    disabled["status"] = "DISABLED"
    check("disabled_blocked", open_governed_file_source(source=disabled, workspace_root=workspace)["status"] == "BLOCKED")

    sql_source = {"source_id": "demo.sql", "kind": "sql_server", "status": "ENABLED", "locator": {"server": "SQL01", "database": "ERP"}, "access": {"mode": "read_only"}}
    check("sql_not_opened_by_file_connector", open_governed_file_source(source=sql_source, workspace_root=workspace)["status"] == "BLOCKED")

audit = build_file_connector_capability_audit()
check("audit_available", audit["status"] == "AVAILABLE")
check("audit_no_query", audit["governance"]["no_query_execution"] is True)
check("audit_no_code", audit["governance"]["no_code_execution"] is True)

builder = (S / "dashboard_spec_builder.py").read_text(encoding="utf-8", errors="replace")
check("builder_import", "build_file_connector_capability_audit" in builder)
check("builder_audit", '\"enterprise_file_connector\"' in builder)

print("\nPASS R10.17B GOVERNED SOURCE RESOLUTION & FILE CONNECTOR")
