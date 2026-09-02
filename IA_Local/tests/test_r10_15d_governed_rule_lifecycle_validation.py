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
print("=== R10.15D GOVERNED RULE LIFECYCLE & VALIDATION ===")

with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    valid_path = base / "valid.json"
    valid_path.write_text(json.dumps({
        "schema_version": "r10.15d",
        "registry_id": "demo",
        "ruleset_version": "2026.09",
        "rules": [{
            "rule_id": "demo.rule.v1",
            "enabled": True,
            "scope": {"company_id": "DEMO"},
            "effective_from": "2026-01-01",
            "effective_to": "2026-12-31",
            "priority": 100,
            "insight_type": "decline",
            "metric": "revenue",
            "field": "change_pct",
            "operator": "lte",
            "threshold": -10,
            "classification": {"severity": "high"},
        }],
    }), encoding="utf-8")

    valid = load_governed_business_rule_registry(str(valid_path))
    check("version", REGISTRY_VERSION == "r10.15d")
    check("valid_loaded", valid["status"] == "LOADED")
    check("valid_rule_count", valid["rule_count"] == 1)

    duplicate_path = base / "duplicate.json"
    duplicate_path.write_text(json.dumps({
        "schema_version": "r10.15d",
        "registry_id": "demo",
        "ruleset_version": "2026.09",
        "rules": [
            {"rule_id": "same.rule", "priority": 1},
            {"rule_id": "same.rule", "priority": 2},
        ],
    }), encoding="utf-8")
    duplicate = load_governed_business_rule_registry(str(duplicate_path))
    check("duplicate_invalid", duplicate["status"] == "INVALID")
    check("duplicate_fail_closed", duplicate["rules"] == [] and duplicate["rule_count"] == 0)
    check("duplicate_error", any("duplicate_rule_id" in e for e in duplicate["errors"]))

    bad_range_path = base / "bad_range.json"
    bad_range_path.write_text(json.dumps({
        "schema_version": "r10.15d",
        "registry_id": "demo",
        "ruleset_version": "2026.09",
        "rules": [{
            "rule_id": "bad.range",
            "effective_from": "2026-12-31",
            "effective_to": "2026-01-01",
            "priority": 1,
        }],
    }), encoding="utf-8")
    bad_range = load_governed_business_rule_registry(str(bad_range_path))
    check("bad_range_invalid", bad_range["status"] == "INVALID")
    check("bad_range_error", any("invalid_effective_range" in e for e in bad_range["errors"]))

    bad_date_path = base / "bad_date.json"
    bad_date_path.write_text(json.dumps({
        "schema_version": "r10.15d",
        "registry_id": "demo",
        "ruleset_version": "2026.09",
        "rules": [{
            "rule_id": "bad.date",
            "effective_from": "not-a-date",
            "priority": 1,
        }],
    }), encoding="utf-8")
    bad_date = load_governed_business_rule_registry(str(bad_date_path))
    check("bad_date_invalid", bad_date["status"] == "INVALID")
    check("bad_date_error", any("invalid_effective_from" in e for e in bad_date["errors"]))

    bad_priority_path = base / "bad_priority.json"
    bad_priority_path.write_text(json.dumps({
        "schema_version": "r10.15d",
        "registry_id": "demo",
        "ruleset_version": "2026.09",
        "rules": [{
            "rule_id": "bad.priority",
            "priority": "high",
        }],
    }), encoding="utf-8")
    bad_priority = load_governed_business_rule_registry(str(bad_priority_path))
    check("bad_priority_invalid", bad_priority["status"] == "INVALID")
    check("bad_priority_error", any("invalid_priority" in e for e in bad_priority["errors"]))

    negative_priority_path = base / "negative_priority.json"
    negative_priority_path.write_text(json.dumps({
        "schema_version": "r10.15d",
        "registry_id": "demo",
        "ruleset_version": "2026.09",
        "rules": [{
            "rule_id": "negative.priority",
            "priority": -1,
        }],
    }), encoding="utf-8")
    negative_priority = load_governed_business_rule_registry(str(negative_priority_path))
    check("negative_priority_invalid", negative_priority["status"] == "INVALID")

    bad_scope_path = base / "bad_scope.json"
    bad_scope_path.write_text(json.dumps({
        "schema_version": "r10.15d",
        "registry_id": "demo",
        "ruleset_version": "2026.09",
        "rules": [{
            "rule_id": "bad.scope",
            "scope": "DEMO",
            "priority": 1,
        }],
    }), encoding="utf-8")
    bad_scope = load_governed_business_rule_registry(str(bad_scope_path))
    check("bad_scope_invalid", bad_scope["status"] == "INVALID")

    legacy_path = base / "legacy.json"
    legacy_path.write_text(json.dumps({
        "schema_version": "r10.15b",
        "registry_id": "legacy",
        "ruleset_version": "legacy",
        "rules": [],
    }), encoding="utf-8")
    legacy = load_governed_business_rule_registry(str(legacy_path))
    check("legacy_schema_accepted", legacy["status"] == "EMPTY")
    check("legacy_source_schema_audited", legacy["source_schema_version"] == "r10.15b")

default = load_governed_business_rule_registry(
    str(ROOT / "config" / "business_rules.json")
)
check("default_registry_compatible", default["status"] == "EMPTY")
check("default_registry_no_rules", default["rule_count"] == 0)
check("duplicate_guard", default["governance"]["duplicate_rule_ids_are_rejected"] is True)
check("effective_range_guard", default["governance"]["invalid_effective_ranges_are_rejected"] is True)
check("priority_guard", default["governance"]["invalid_priorities_are_rejected"] is True)
check("shape_guard", default["governance"]["invalid_rule_shapes_are_rejected"] is True)

print()
print("PASS R10.15D GOVERNED RULE LIFECYCLE & VALIDATION")
