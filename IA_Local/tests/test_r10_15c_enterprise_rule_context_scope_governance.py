from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from business_rule_context import (
    CONTEXT_VERSION,
    load_governed_business_context,
)
from business_rule_engine import apply_governed_business_rules


def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


print()
print("=== R10.15C ENTERPRISE RULE CONTEXT & SCOPE GOVERNANCE ===")

with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    missing = load_governed_business_context(str(base / "missing.json"))
    check("version", CONTEXT_VERSION == "r10.15c")
    check("missing_unconfigured", missing["status"] == "UNCONFIGURED")
    check("missing_context_empty", missing["context"] == {})
    check("unknown_not_inferred", missing["governance"]["unknown_scope_is_never_inferred"] is True)

    invalid_path = base / "invalid.json"
    invalid_path.write_text("{bad-json", encoding="utf-8")
    invalid = load_governed_business_context(str(invalid_path))
    check("invalid_fail_closed", invalid["status"] == "INVALID" and invalid["context"] == {})

    valid_path = base / "valid.json"
    valid_path.write_text(
        json.dumps({
            "schema_version": "r10.15c",
            "context": {
                "company_id": "DEMO",
                "tenant_id": "TENANT-1",
                "branch_id": "CUL",
                "as_of": "2026-09-02",
                "unexpected": "DROP-ME",
            },
        }),
        encoding="utf-8",
    )
    valid = load_governed_business_context(str(valid_path))
    check("valid_loaded", valid["status"] == "LOADED")
    check("allowed_scope_preserved", valid["context"]["company_id"] == "DEMO")
    check("tenant_preserved", valid["context"]["tenant_id"] == "TENANT-1")
    check("branch_preserved", valid["context"]["branch_id"] == "CUL")
    check("as_of_preserved", valid["context"]["as_of"] == "2026-09-02")
    check("unknown_scope_dropped", "unexpected" not in valid["context"])

insights = {
    "insights": [
        {
            "id": "insight:trend:revenue:decline",
            "insight_type": "decline",
            "metric": "revenue",
            "change_pct": -12.5,
        }
    ],
    "observations": [],
}

rules = [
    {
        "rule_id": "company.demo.revenue_decline.v1",
        "ruleset_version": "demo-1",
        "enabled": True,
        "scope": {"company_id": "DEMO"},
        "effective_from": "2026-01-01",
        "effective_to": "2026-12-31",
        "priority": 100,
        "insight_type": "decline",
        "metric": "revenue",
        "field": "change_pct",
        "operator": "lte",
        "threshold": -10.0,
        "classification": {"severity": "high"},
    }
]

no_context = apply_governed_business_rules(
    business_insights=insights,
    rule_registry=rules,
    context={},
    as_of="2026-09-02",
)
check("scoped_rule_blocked_without_context", no_context["active_rule_count"] == 0)
check("no_context_not_applied", no_context["applied_rule_count"] == 0)

wrong_context = apply_governed_business_rules(
    business_insights=insights,
    rule_registry=rules,
    context={"company_id": "OTHER"},
    as_of="2026-09-02",
)
check("cross_company_rule_blocked", wrong_context["active_rule_count"] == 0)

correct_context = apply_governed_business_rules(
    business_insights=insights,
    rule_registry=rules,
    context={"company_id": "DEMO"},
    as_of="2026-09-02",
)
check("correct_company_rule_active", correct_context["active_rule_count"] == 1)
check("correct_company_rule_applied", correct_context["applied_rule_count"] == 1)

expired_context = apply_governed_business_rules(
    business_insights=insights,
    rule_registry=rules,
    context={"company_id": "DEMO"},
    as_of="2027-01-01",
)
check("effective_date_blocks_expired_rule", expired_context["active_rule_count"] == 0)

default_context = ROOT / "config" / "business_context.json"
check("default_context_exists", default_context.exists())
default_loaded = load_governed_business_context(str(default_context))
check("default_context_unconfigured", default_loaded["status"] == "UNCONFIGURED")
check("default_context_empty", default_loaded["context"] == {})

builder_text = (SCRIPTS / "dashboard_spec_builder.py").read_text(
    encoding="utf-8",
    errors="replace",
)
check("builder_context_loader", "load_governed_business_context" in builder_text)
check("builder_context_loaded", "business_rule_context = load_governed_business_context()" in builder_text)
check("builder_context_passed", "context=resolved_rule_context" in builder_text)
check("builder_as_of_passed", "as_of=resolved_rule_as_of" in builder_text)
check("builder_context_governance_embedded", '"context_governance"' in builder_text)

print()
print("PASS R10.15C ENTERPRISE RULE CONTEXT & SCOPE GOVERNANCE")
