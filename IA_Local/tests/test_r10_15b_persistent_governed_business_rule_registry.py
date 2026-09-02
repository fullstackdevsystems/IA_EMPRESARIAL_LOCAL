from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from business_rule_registry import (
    REGISTRY_VERSION,
    load_governed_business_rule_registry,
)


def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


print()
print("=== R10.15B PERSISTENT GOVERNED BUSINESS RULE REGISTRY ===")

with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    missing = load_governed_business_rule_registry(str(base / "missing.json"))
    check("version", REGISTRY_VERSION == "r10.15b" and missing["schema_version"] == "r10.15b")
    check("missing_empty", missing["status"] == "EMPTY" and missing["rule_count"] == 0)
    check("missing_no_rules", missing["rules"] == [])
    check("missing_fail_closed", missing["governance"]["fail_closed"] is True)

    malformed_path = base / "malformed.json"
    malformed_path.write_text("{not-json", encoding="utf-8")
    malformed = load_governed_business_rule_registry(str(malformed_path))
    check("malformed_invalid", malformed["status"] == "INVALID")
    check("malformed_no_rules", malformed["rules"] == [] and malformed["rule_count"] == 0)
    check("malformed_fingerprint", bool(malformed["fingerprint_sha256"]))

    wrong_schema_path = base / "wrong_schema.json"
    wrong_schema_path.write_text(
        json.dumps({
            "schema_version": "r9",
            "registry_id": "bad",
            "ruleset_version": "bad",
            "rules": [{"rule_id": "should.not.load"}],
        }),
        encoding="utf-8",
    )
    wrong = load_governed_business_rule_registry(str(wrong_schema_path))
    check("wrong_schema_invalid", wrong["status"] == "INVALID")
    check("wrong_schema_no_rules", wrong["rules"] == [])

    valid_path = base / "valid.json"
    valid_payload = {
        "schema_version": "r10.15b",
        "registry_id": "company-demo-rules",
        "ruleset_version": "2026.09",
        "rules": [
            {
                "rule_id": "company.demo.revenue_decline.v1",
                "enabled": True,
                "scope": {"company_id": "DEMO"},
                "effective_from": "2026-01-01",
                "priority": 100,
                "insight_type": "decline",
                "metric": "revenue",
                "field": "change_pct",
                "operator": "lte",
                "threshold": -10.0,
                "classification": {"severity": "high"},
            }
        ],
    }
    valid_path.write_text(
        json.dumps(valid_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    valid = load_governed_business_rule_registry(str(valid_path))
    check("valid_loaded", valid["status"] == "LOADED")
    check("valid_rule_count", valid["rule_count"] == 1)
    check("valid_registry_id", valid["registry_id"] == "company-demo-rules")
    check("valid_ruleset_version", valid["ruleset_version"] == "2026.09")
    check("valid_rule_preserved", valid["rules"][0]["rule_id"] == "company.demo.revenue_decline.v1")
    check("valid_fingerprint", len(valid["fingerprint_sha256"]) == 64)
    check("no_default_invention", valid["governance"]["default_rules_are_never_invented"] is True)

default_registry = ROOT / "config" / "business_rules.json"
check("default_registry_exists", default_registry.exists())

default = load_governed_business_rule_registry(str(default_registry))
check("default_registry_schema", default["schema_version"] == "r10.15b")
check("default_registry_empty", default["rule_count"] == 0)
check("default_registry_status", default["status"] == "EMPTY")

builder_text = (SCRIPTS / "dashboard_spec_builder.py").read_text(
    encoding="utf-8",
    errors="replace",
)
check("builder_loader_imported", "load_governed_business_rule_registry" in builder_text)
check("builder_registry_loaded", "business_rule_registry = load_governed_business_rule_registry()" in builder_text)
check("builder_rules_passed", 'rule_registry=business_rule_registry.get("rules")' in builder_text)
check("builder_registry_audit_embedded", '"registry"' in builder_text and '"fingerprint_sha256"' in builder_text)

print()
print("PASS R10.15B PERSISTENT GOVERNED BUSINESS RULE REGISTRY")
