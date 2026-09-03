from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from enterprise_deliverable_manifest import (
    ENTERPRISE_DELIVERABLE_MANIFEST_VERSION,
    build_governed_deliverable_manifest,
    deliverable_manifest_component_rows,
    deliverable_manifest_summary_rows,
)


def check(name, condition):
    if not condition:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)


plan = {
    "request_prompt_sha256": "a" * 64,
    "prompt_integrity": "verified",
    "execution_plan": {
        "source_of_truth": "dashboard_spec",
        "version": "r10.14b",
        "coverage_pct": 50.0,
        "dashboard_spec": {
            "schema_version": "r10.13a",
            "source": {"fingerprint_sha256": "b" * 64},
            "provenance": {"ruleset_version": "r10.13c"},
            "components": [
                {
                    "id": "kpi:revenue", "type": "kpi", "title": "Revenue",
                    "status": "SUPPORTED", "semantic_role": "revenue",
                    "source_columns": ["Importe"], "dependencies": [],
                    "provenance": {"source": "semantic_contract", "confidence": 1.0},
                },
                {
                    "id": "kpi:freight", "type": "kpi", "title": "Freight",
                    "status": "BLOCKED", "semantic_role": "freight",
                    "source_columns": [], "dependencies": ["approved_freight_rule"],
                    "reason": "approved business rule required",
                    "provenance": {"source": "capability_resolver", "confidence": 1.0},
                },
            ],
            "enterprise_query_registry": {
                "schema_version": "r10.17e", "status": "EMPTY",
                "fingerprint_sha256": "c" * 64,
            },
        },
    },
}

manifest = build_governed_deliverable_manifest(
    dashboard_plan=plan,
    filename="ventas.xlsx",
    sheet="Datos",
    row_count=2,
)
serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
print("\n=== R10.18A GOVERNED DELIVERABLE MANIFEST ===")
check("version", ENTERPRISE_DELIVERABLE_MANIFEST_VERSION == "r10.18a")
check("ready", manifest["status"] == "READY")
check("same_authority", manifest["authority"]["source_of_truth"] == "dashboard_spec")
check("counts", manifest["summary"]["supported_count"] == 1 and manifest["summary"]["blocked_count"] == 1)
check("freight_blocked", any(item["component_id"] == "kpi:freight" and item["status"] == "BLOCKED" for item in manifest["components"]))
check("fingerprint", len(manifest["manifest_fingerprint_sha256"]) == 64)
check("summary_rows", any(row["Campo"] == "Prompt SHA-256" for row in deliverable_manifest_summary_rows(manifest)))
check("component_rows", any(row["Componente"] == "kpi:freight" for row in deliverable_manifest_component_rows(manifest)))
check("no_sql", '"sql"' not in serialized.lower())
check("no_credentials", "credential_ref" not in serialized.lower() and "password" not in serialized.lower() and "connection_string" not in serialized.lower())

blocked = build_governed_deliverable_manifest(dashboard_plan={}, filename="x.csv")
check("missing_spec_blocked", blocked["status"] == "BLOCKED" and blocked["reason"] == "governed_dashboard_spec_required")
print("PASS R10.18A GOVERNED DELIVERABLE MANIFEST")
