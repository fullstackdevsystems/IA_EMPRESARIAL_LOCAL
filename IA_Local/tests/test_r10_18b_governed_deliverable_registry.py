from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from enterprise_deliverable_manifest import build_governed_deliverable_manifest
from enterprise_deliverable_registry import (
    ENTERPRISE_DELIVERABLE_REGISTRY_VERSION,
    DeliverableRegistryError,
    GovernedDeliverableRegistry,
    deliverable_registry_public_audit,
)


def check(name, condition):
    if not condition:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)


def blocked(name, code, action):
    try:
        action()
    except DeliverableRegistryError as exc:
        check(name, exc.code == code)
        return
    raise AssertionError(name)


plan = {
    "request_prompt_sha256": "a" * 64,
    "prompt_integrity": "r10.18a-cross-format-authority",
    "execution_plan": {
        "source_of_truth": "Datos",
        "version": "r10.11.3",
        "coverage_pct": 50.0,
        "dashboard_spec": {
            "schema_version": "r10.13a",
            "source": {"fingerprint_sha256": "b" * 64},
            "provenance": {"ruleset_version": "r10.13c"},
            "components": [{
                "id": "kpi:freight", "type": "kpi", "title": "Freight",
                "status": "BLOCKED", "semantic_role": "freight",
                "reason": "approved business rule required",
                "provenance": {"source": "capability_resolver", "confidence": 1.0},
            }],
        },
    },
}
manifest = build_governed_deliverable_manifest(dashboard_plan=plan, filename="ventas.xlsx", sheet="Datos", row_count=2)
scope_a = {"company_id": "empresa-a", "user_id": "ana", "business_unit": None, "branch": None}
scope_b = {"company_id": "empresa-b", "user_id": "ana", "business_unit": None, "branch": None}

print("\n=== R10.18B GOVERNED DELIVERABLE REGISTRY ===")
with tempfile.TemporaryDirectory() as td:
    reports = Path(td) / "Reportes"
    reports.mkdir()
    (reports / "dashboard.html").write_text("<html>ok</html>", encoding="utf-8")
    (reports / "report.xlsx").write_bytes(b"xlsx-test")
    (reports / "report.pdf").write_bytes(b"pdf-test")
    registry = GovernedDeliverableRegistry(reports)
    record = registry.register(
        scope=scope_a,
        run_id="run-001",
        manifest=manifest,
        outputs={"html": "dashboard.html", "excel": "report.xlsx", "pdf": "report.pdf"},
        domain="comercial",
    )
    check("version", ENTERPRISE_DELIVERABLE_REGISTRY_VERSION == "r10.18b")
    check("registered", record["status"] == "READY" and len(record["deliverables"]) == 3)
    check("hashes", all(len(item["sha256"]) == 64 for item in record["deliverables"]))
    check("explicit_scope", record["scope"] == scope_a)
    serialized = json.dumps(record, ensure_ascii=False).lower()
    check("no_paths", str(reports).lower() not in serialized and '"path"' not in serialized)
    check("no_credentials", "password" not in serialized and "credential_ref" not in serialized)
    restarted = GovernedDeliverableRegistry(reports)
    loaded = restarted.get(scope_a, "run-001")
    check("restart_recovery", loaded["record_fingerprint_sha256"] == record["record_fingerprint_sha256"])
    check("list_scoped", [item["run_id"] for item in restarted.list(scope_a)] == ["run-001"])
    check("cross_company_empty", restarted.list(scope_b) == [])
    blocked("cross_company_get_blocked", "RUN_NOT_FOUND", lambda: restarted.get(scope_b, "run-001"))
    blocked("missing_scope_blocked", "SCOPE_REQUIRED", lambda: restarted.list(None))
    blocked("bool_limit_blocked", "INVALID_LIMIT", lambda: restarted.list(scope_a, True))
    blocked("traversal_blocked", "INVALID_IDENTIFIER", lambda: restarted.get(scope_a, "../run-001"))
    blocked("duplicate_run_blocked", "RUN_ALREADY_EXISTS", lambda: restarted.register(scope=scope_a, run_id="run-001", manifest=manifest, outputs={"html":"dashboard.html"}))
    tampered_manifest = dict(manifest)
    tampered_manifest["status"] = "BLOCKED"
    blocked("manifest_tamper_blocked", "MANIFEST_INTEGRITY_MISMATCH", lambda: restarted.register(scope=scope_a, run_id="run-002", manifest=tampered_manifest, outputs={"html":"dashboard.html"}))
    audit = deliverable_registry_public_audit([loaded])
    check("public_audit", audit["schema_version"] == "r10.18b" and audit["paths_serialized"] is False)
    (reports / "dashboard.html").write_text("<html>tampered</html>", encoding="utf-8")
    blocked("artifact_tamper_blocked", "ARTIFACT_INTEGRITY_MISMATCH", lambda: restarted.get(scope_a, "run-001"))

print("PASS R10.18B GOVERNED DELIVERABLE REGISTRY")
