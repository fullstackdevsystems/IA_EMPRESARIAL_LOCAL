from pathlib import Path
import json, sys, tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from business_rule_context import load_governed_business_context
from business_rule_engine import apply_governed_business_rules
from business_rule_registry import load_governed_business_rule_registry
from enterprise_metric_rules import load_governed_enterprise_metric_rule_registry
from enterprise_rule_governance import ENTERPRISE_RULE_GOVERNANCE_VERSION, build_enterprise_rule_governance_audit

def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")

print()
print("=== R10.15F ENTERPRISE BUSINESS RULE ENGINE CLOSURE ===")

with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "bad_context.json"
    p.write_text(json.dumps({
        "schema_version": "r10.15c",
        "context": {"company_id": "DEMO", "as_of": "not-a-date"},
    }), encoding="utf-8")
    bad = load_governed_business_context(str(p))
    check("invalid_as_of_context_invalid", bad["status"] == "INVALID")
    check("invalid_as_of_context_empty", bad["context"] == {})

insights = {
    "insights": [{"id":"insight:test","insight_type":"decline","metric":"revenue","change_pct":-20.0}],
    "observations": [],
}
rules = [{
    "rule_id":"global.test.v1","enabled":True,"field":"change_pct","operator":"lte",
    "threshold":-10,"classification":{"severity":"high"}
}]
invalid_as_of = apply_governed_business_rules(
    business_insights=insights, rule_registry=rules, context={}, as_of="not-a-date"
)
check("invalid_explicit_as_of_blocks_rules", invalid_as_of["active_rule_count"] == 0)
check("invalid_explicit_as_of_not_applied", invalid_as_of["applied_rule_count"] == 0)
check("invalid_explicit_as_of_observed", any(
    x.get("code") == "INVALID_AS_OF_FAIL_CLOSED"
    for x in invalid_as_of.get("governance_observations", [])
))

business_registry = load_governed_business_rule_registry()
business_context = load_governed_business_context()
metric_registry = load_governed_enterprise_metric_rule_registry()
normal = apply_governed_business_rules(
    business_insights={"insights": [], "observations": []},
    rule_registry=business_registry.get("rules"),
    context={},
)
audit = build_enterprise_rule_governance_audit(
    business_rule_interpretation=normal,
    business_rule_registry=business_registry,
    business_rule_context=business_context,
    enterprise_metric_rule_registry=metric_registry,
)
check("version", ENTERPRISE_RULE_GOVERNANCE_VERSION == "r10.15f")
check("closure_ready_default", audit["status"] == "READY")
check("version_contract", audit["version_contract_ok"] is True)
check("safety_contract", audit["safety_contract_ok"] is True)
check("phase_consolidated", audit["governance"]["phase_r10_15_consolidated"] is True)

builder = (SCRIPTS / "dashboard_spec_builder.py").read_text(encoding="utf-8", errors="replace")
check("builder_closure_import", "build_enterprise_rule_governance_audit" in builder)
check("builder_invalid_context_business_fail_closed", "resolved_business_rule_registry = (" in builder)
check("builder_invalid_context_metric_fail_closed", 'context_doc.get("status") == "INVALID"' in builder)
check("builder_closure_embedded", '"enterprise_rule_governance"' in builder)

print()
print("PASS R10.15F ENTERPRISE BUSINESS RULE ENGINE CLOSURE")
