from __future__ import annotations

import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from business_rule_engine import (
    BUSINESS_RULE_ENGINE_VERSION,
    R10_25C1_FINDING_CLASSIFICATION_VERSION,
    apply_governed_business_rules,
)


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


def _source():
    return {
        "schema_version": "r10.14c",
        "insights": [
            {
                "id": "insight:trend:revenue:decline",
                "insight_type": "decline",
                "metric": "revenue",
                "change_pct": -18.0,
                "severity": None,
                "provenance": {
                    "interpretation_policy": "NOT_APPLIED",
                },
            },
            {
                "id": "insight:customers:revenue:concentration",
                "insight_type": "concentration",
                "metric": "revenue",
                "share_pct": 44.0,
                "severity": None,
                "provenance": {
                    "interpretation_policy": "NOT_APPLIED",
                },
            },
        ],
        "observations": [],
    }


def main():
    print("=== R10.25C1 GOVERNED BUSINESS FINDING CLASSIFICATION ===")

    source = _source()
    original = copy.deepcopy(source)

    rules = [
        {
            "rule_id": "company.demo.revenue_decline.risk.v1",
            "ruleset_version": "r10.25-demo",
            "enabled": True,
            "scope": {"company_id": "DEMO"},
            "priority": 100,
            "insight_type": "decline",
            "metric": "revenue",
            "field": "change_pct",
            "operator": "lte",
            "threshold": -10.0,
            "classification": {
                "finding_class": "risk",
                "severity": "high",
                "label": "Revenue decline requires review",
            },
        },
        {
            "rule_id": "company.demo.revenue_concentration.attention.v1",
            "ruleset_version": "r10.25-demo",
            "enabled": True,
            "scope": {"company_id": "DEMO"},
            "priority": 50,
            "insight_type": "concentration",
            "metric": "revenue",
            "field": "share_pct",
            "operator": "gte",
            "threshold": 40.0,
            "classification": {
                "finding_class": "attention",
                "severity": "medium",
            },
        },
    ]

    out = apply_governed_business_rules(
        business_insights=source,
        rule_registry=rules,
        context={"company_id": "DEMO"},
        as_of="2026-09-21",
    )

    check(
        "legacy_schema_preserved",
        BUSINESS_RULE_ENGINE_VERSION == "r10.15a"
        and out["schema_version"] == "r10.15a",
    )

    check(
        "c1_contract_version",
        R10_25C1_FINDING_CLASSIFICATION_VERSION == "r10.25c1"
        and out["governance"]["finding_classification_contract"] == "r10.25c1",
    )

    decline = next(
        item
        for item in out["interpreted_insights"]
        if item["insight_type"] == "decline"
    )

    concentration = next(
        item
        for item in out["interpreted_insights"]
        if item["insight_type"] == "concentration"
    )

    check(
        "risk_classification_rule_supplied",
        decline["enterprise_interpretation"]["classification"]["finding_class"]
        == "risk",
    )

    check(
        "risk_severity_rule_supplied",
        decline["enterprise_interpretation"]["classification"]["severity"]
        == "high",
    )

    check(
        "attention_classification_rule_supplied",
        concentration["enterprise_interpretation"]["classification"][
            "finding_class"
        ]
        == "attention",
    )

    check(
        "source_not_mutated",
        source == original,
    )

    check(
        "source_severity_not_overwritten",
        all(item["severity"] is None for item in source["insights"]),
    )

    check(
        "rule_priority_remains_rule_precedence",
        decline["enterprise_interpretation"]["priority"] == 100
        and out["governance"]["priority_resolution"]
        == "highest_priority_first_match"
        and out["governance"]["finding_ranking_is_not_rule_priority"] is True,
    )

    check(
        "no_default_classification",
        out["governance"]["finding_classification_defaults_are_not_invented"]
        is True,
    )

    check(
        "no_llm_classification_authority",
        out["governance"]["llm_finding_classification_authority"] is False,
    )

    no_rules = apply_governed_business_rules(
        business_insights=source,
        rule_registry=None,
        context={"company_id": "DEMO"},
        as_of="2026-09-21",
    )

    check(
        "empty_registry_does_not_invent_findings",
        no_rules["active_rule_count"] == 0
        and no_rules["applied_rule_count"] == 0
        and all(
            item["enterprise_interpretation"]["classification"] is None
            for item in no_rules["interpreted_insights"]
        ),
    )

    invalid_class = apply_governed_business_rules(
        business_insights=source,
        rule_registry=[
            {
                "rule_id": "invalid.finding.class",
                "enabled": True,
                "priority": 1,
                "insight_type": "decline",
                "metric": "revenue",
                "field": "change_pct",
                "operator": "lte",
                "threshold": -1.0,
                "classification": {
                    "finding_class": "magic_prediction",
                    "severity": "high",
                },
            }
        ],
        context={},
        as_of="2026-09-21",
    )

    check(
        "unsupported_finding_class_rejected",
        invalid_class["active_rule_count"] == 0
        and any(
            item.get("reason") == "unsupported_finding_class"
            for item in invalid_class["rejected_rules"]
        ),
    )

    invalid_severity = apply_governed_business_rules(
        business_insights=source,
        rule_registry=[
            {
                "rule_id": "invalid.finding.severity",
                "enabled": True,
                "priority": 1,
                "insight_type": "decline",
                "metric": "revenue",
                "field": "change_pct",
                "operator": "lte",
                "threshold": -1.0,
                "classification": {
                    "finding_class": "risk",
                    "severity": "extreme",
                },
            }
        ],
        context={},
        as_of="2026-09-21",
    )

    check(
        "unsupported_finding_severity_rejected",
        invalid_severity["active_rule_count"] == 0
        and any(
            item.get("reason") == "unsupported_finding_severity"
            for item in invalid_severity["rejected_rules"]
        ),
    )

    legacy_rule = apply_governed_business_rules(
        business_insights=source,
        rule_registry=[
            {
                "rule_id": "legacy.r10.15.rule",
                "enabled": True,
                "priority": 1,
                "insight_type": "decline",
                "metric": "revenue",
                "field": "change_pct",
                "operator": "lte",
                "threshold": -10.0,
                "classification": {
                    "severity": "high",
                },
            }
        ],
        context={},
        as_of="2026-09-21",
    )

    check(
        "legacy_r10_15_classification_remains_valid",
        legacy_rule["active_rule_count"] == 1
        and legacy_rule["applied_rule_count"] == 1
        and legacy_rule["interpreted_insights"][0][
            "enterprise_interpretation"
        ]["classification"]["severity"]
        == "high",
    )

    print("PASS R10.25C1 GOVERNED BUSINESS FINDING CLASSIFICATION")


if __name__ == "__main__":
    main()