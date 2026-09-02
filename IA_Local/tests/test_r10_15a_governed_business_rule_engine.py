from pathlib import Path
import copy
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from business_rule_engine import (
    BUSINESS_RULE_ENGINE_VERSION,
    apply_governed_business_rules,
)
from dashboard_spec_builder import build_dashboard_spec


def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


print()
print("=== R10.15A GOVERNED BUSINESS RULE REGISTRY & INTERPRETER ===")

source = {
    "schema_version": "r10.14c",
    "insights": [
        {
            "id": "insight:trend:revenue:decline",
            "insight_type": "decline",
            "metric": "revenue",
            "change_pct": -12.5,
            "severity": None,
            "provenance": {"interpretation_policy": "NOT_APPLIED"},
        },
        {
            "id": "insight:customers:revenue:concentration",
            "insight_type": "concentration",
            "metric": "revenue",
            "share_pct": 31.0,
            "severity": None,
            "provenance": {"interpretation_policy": "NOT_APPLIED"},
        },
    ],
    "observations": [
        {
            "id": "observation:freight_analysis:blocked",
            "observation_type": "blocked_analysis",
            "analysis": "freight_analysis",
        }
    ],
}
original = copy.deepcopy(source)

rules = [
    {
        "rule_id": "company.demo.revenue_decline.critical.v1",
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
        "classification": {
            "severity": "high",
            "business_status": "REVIEW_REQUIRED",
        },
    },
    {
        "rule_id": "company.demo.revenue_concentration.review.v1",
        "ruleset_version": "demo-1",
        "enabled": True,
        "scope": {"company_id": "DEMO"},
        "effective_from": "2026-01-01",
        "effective_to": "2026-12-31",
        "priority": 50,
        "insight_type": "concentration",
        "metric": "revenue",
        "field": "share_pct",
        "operator": "gte",
        "threshold": 30.0,
        "classification": {
            "severity": "medium",
            "business_status": "MONITOR",
        },
    },
    {
        "rule_id": "company.other.should_not_apply.v1",
        "enabled": True,
        "scope": {"company_id": "OTHER"},
        "priority": 999,
        "insight_type": "decline",
        "metric": "revenue",
        "field": "change_pct",
        "operator": "lte",
        "threshold": -1.0,
        "classification": {"severity": "critical"},
    },
    {
        "rule_id": "company.demo.expired.v1",
        "enabled": True,
        "scope": {"company_id": "DEMO"},
        "effective_to": "2025-12-31",
        "priority": 999,
        "insight_type": "decline",
        "metric": "revenue",
        "field": "change_pct",
        "operator": "lte",
        "threshold": -1.0,
        "classification": {"severity": "critical"},
    },
    {
        "rule_id": "unsafe.eval.rule",
        "enabled": True,
        "expression": "__import__('os').system('echo unsafe')",
        "field": "change_pct",
        "operator": "lte",
        "threshold": -1.0,
        "classification": {"severity": "critical"},
    },
]

out = apply_governed_business_rules(
    business_insights=source,
    rule_registry=rules,
    context={"company_id": "DEMO"},
    as_of="2026-09-02",
)

check("version", BUSINESS_RULE_ENGINE_VERSION == "r10.15a" and out["schema_version"] == "r10.15a")
check("mode", out["mode"] == "governed-whitelist-business-rules")
check("two_active_rules", out["active_rule_count"] == 2)
check("two_rules_applied", out["applied_rule_count"] == 2)
check("unsafe_rule_rejected", any(x.get("rule_id") == "unsafe.eval.rule" for x in out["rejected_rules"]))

decline = next(x for x in out["interpreted_insights"] if x["insight_type"] == "decline")
check("decline_interpreted", decline["enterprise_interpretation"]["status"] == "APPLIED")
check("decline_rule", decline["enterprise_interpretation"]["rule_id"] == "company.demo.revenue_decline.critical.v1")
check("decline_severity", decline["enterprise_interpretation"]["classification"]["severity"] == "high")

concentration = next(x for x in out["interpreted_insights"] if x["insight_type"] == "concentration")
check("concentration_interpreted", concentration["enterprise_interpretation"]["status"] == "APPLIED")
check("concentration_rule", concentration["enterprise_interpretation"]["rule_id"] == "company.demo.revenue_concentration.review.v1")

check("source_not_mutated", source == original)
check("freight_observation_preserved", out["observations"][0]["analysis"] == "freight_analysis")
check("no_default_thresholds", out["governance"]["default_enterprise_thresholds"] is False)
check("no_arbitrary_eval", out["governance"]["arbitrary_expression_evaluation"] is False)
check("whitelist_only", out["governance"]["whitelist_operators_only"] is True)
check("scope_guard", out["governance"]["scope_guard"] is True)
check("effective_date_guard", out["governance"]["effective_date_guard"] is True)
check("builder_integrated", callable(build_dashboard_spec))

empty = apply_governed_business_rules(
    business_insights=source,
    rule_registry=None,
    context={"company_id": "DEMO"},
    as_of="2026-09-02",
)
check("empty_registry_no_rules", empty["active_rule_count"] == 0 and empty["applied_rule_count"] == 0)
check("empty_registry_not_applied", all(
    x["enterprise_interpretation"]["status"] == "NOT_APPLIED"
    for x in empty["interpreted_insights"]
))

print()
print("PASS R10.15A GOVERNED BUSINESS RULE REGISTRY & INTERPRETER")
