from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "scripts"
if str(S) not in sys.path:
    sys.path.insert(0, str(S))

from enterprise_source_execution import (
    ENTERPRISE_SOURCE_EXECUTION_VERSION,
    build_source_execution_capability_audit,
    execute_registered_source,
    execute_uploaded_file_source,
    public_source_execution_metadata,
)
from enterprise_source_registry import load_governed_enterprise_source_registry

def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)

print("\n=== R10.17D GOVERNED SOURCE EXECUTION PIPELINE ===")
check("version", ENTERPRISE_SOURCE_EXECUTION_VERSION == "r10.17d")

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    entrada = root / "Entrada"
    entrada.mkdir(parents=True)
    csv_path = entrada / "ventas.csv"
    csv_path.write_text("Cliente,Venta\nA,100\nB,200\n", encoding="utf-8")

    opened = execute_uploaded_file_source(path=csv_path, workspace_root=root)
    check("upload_opened", opened["status"] == "OPENED")
    check("upload_file_connector", opened["connector_schema_version"] == "r10.17b")
    check("upload_rows", len(opened["dataframe"]) == 2)
    check("upload_origin", opened["source_origin"] == "request_upload")
    check("upload_read_only", opened["governance"]["read_only"] is True)
    check("upload_no_formula_authority", opened["governance"]["formula_authority"] is False)
    check("upload_provenance_fingerprint", len(opened["provenance"]["fingerprint_sha256"]) == 64)

    outside = root.parent / "outside-r10-17d.csv"
    outside.write_text("x\n1\n", encoding="utf-8")
    try:
        blocked = execute_uploaded_file_source(path=outside, workspace_root=root)
        check("upload_workspace_escape_blocked", blocked["status"] == "BLOCKED")
    finally:
        outside.unlink(missing_ok=True)

    registry_path = root / "enterprise_sources.json"
    registry_path.write_text(json.dumps({
        "schema_version": "r10.17a",
        "registry_id": "r10.17d-test",
        "sources_version": "1",
        "sources": [{
            "source_id": "demo.sales.csv",
            "kind": "csv",
            "status": "ENABLED",
            "name": "Ventas",
            "scope": {"company_id": "DEMO"},
            "locator": {"relative_path": "Entrada/ventas.csv"},
            "access": {"mode": "read_only"}
        }]
    }), encoding="utf-8")
    registry = load_governed_enterprise_source_registry(str(registry_path))
    registered = execute_registered_source(
        registry=registry,
        source_id="demo.sales.csv",
        context={"company_id": "DEMO"},
        workspace_root=root,
    )
    check("registered_opened", registered["status"] == "OPENED")
    check("registered_origin", registered["source_origin"] == "enterprise_registry")
    wrong_scope = execute_registered_source(
        registry=registry,
        source_id="demo.sales.csv",
        context={"company_id": "OTHER"},
        workspace_root=root,
    )
    check("registered_scope_blocked", wrong_scope["status"] == "BLOCKED")

    public = public_source_execution_metadata(registered)
    check("public_no_dataframe", "dataframe" not in public)
    check("public_no_secret", "credential_ref" not in json.dumps(public).lower())

audit = build_source_execution_capability_audit()
check("audit_schema", audit["schema_version"] == "r10.17d")
check("audit_available", audit["status"] == "AVAILABLE")
check("audit_file_connector", audit["connectors"]["file"] == "r10.17b")
check("audit_sql_connector", audit["connectors"]["sql_server"] == "r10.17c")
check("audit_source_precedence", audit["governance"]["source_data_precedence"] is True)

analyzer = (S / "analizador_app.py").read_text(encoding="utf-8", errors="replace")
check("analyzer_uses_execution_pipeline", "execute_uploaded_file_source" in analyzer)
check("analyzer_no_direct_load_in_analyze_file", "original, meta = load_tabular(path)" not in analyzer)

builder = (S / "dashboard_spec_builder.py").read_text(encoding="utf-8", errors="replace")
check("builder_execution_import", "build_source_execution_capability_audit" in builder)
check("builder_execution_audit", '"enterprise_source_execution"' in builder)

print("\nPASS R10.17D GOVERNED SOURCE EXECUTION PIPELINE")
