from copy import deepcopy
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from business_finding_prioritizer import (
    BUSINESS_FINDING_PRIORITIZER_VERSION,
    build_governed_business_findings,
)


def _item(
    insight_id,
    *,
    finding_class=None,
    severity=None,
    rule_priority=0,
    applied=True,
):
    classification = {}

    if finding_class is not None:
        classification["finding_class"] = finding_class

    if severity is not None:
        classification["severity"] = severity

    return {
        "id": insight_id,
        "insight_type": "synthetic_governed_fact",
        "severity": None,
        "confidence": 1.0,
        "enterprise_interpretation": {
            "status": "APPLIED" if applied else "NOT_APPLIED",
            "rule_id": f"rule.{insight_id}" if applied else None,
            "ruleset_version": "test",
            "classification": classification if applied else None,
            "priority": rule_priority if applied else None,
        },
    }


def test_contract_version_and_governance():
    source = {"interpreted_insights": []}

    out = build_governed_business_findings(
        business_rule_interpretation=source,
    )

    assert BUSINESS_FINDING_PRIORITIZER_VERSION == "r10.25c4"
    assert out["schema_version"] == "r10.25c4"

    governance = out["governance"]

    assert governance["classification_is_rule_supplied_only"] is True
    assert governance["severity_is_rule_supplied_only"] is True
    assert governance["severity_used_for_ordering_only"] is True
    assert governance["rule_priority_used_for_finding_ranking"] is False
    assert governance["numeric_finding_scores"] is False
    assert governance["business_thresholds_invented"] is False
    assert governance["cross_class_ranking"] is False
    assert governance["llm_classification_authority"] is False
    assert governance["llm_severity_authority"] is False
    assert governance["llm_ranking_authority"] is False


def test_risks_are_ordered_only_by_governed_severity():
    source = {
        "interpreted_insights": [
            _item(
                "risk.low.high-rule-priority",
                finding_class="risk",
                severity="low",
                rule_priority=999,
            ),
            _item(
                "risk.critical.low-rule-priority",
                finding_class="risk",
                severity="critical",
                rule_priority=1,
            ),
            _item(
                "risk.high",
                finding_class="risk",
                severity="high",
                rule_priority=50,
            ),
        ]
    }

    out = build_governed_business_findings(
        business_rule_interpretation=source,
    )

    assert [x["id"] for x in out["risks"]] == [
        "risk.critical.low-rule-priority",
        "risk.high",
        "risk.low.high-rule-priority",
    ]

    assert [x["finding_prioritization"]["rank"] for x in out["risks"]] == [
        1,
        2,
        3,
    ]


def test_rule_priority_is_not_finding_ranking():
    source = {
        "interpreted_insights": [
            _item(
                "risk.low",
                finding_class="risk",
                severity="low",
                rule_priority=1000,
            ),
            _item(
                "risk.high",
                finding_class="risk",
                severity="high",
                rule_priority=1,
            ),
        ]
    }

    out = build_governed_business_findings(
        business_rule_interpretation=source,
    )

    assert out["risks"][0]["id"] == "risk.high"
    assert out["risks"][1]["id"] == "risk.low"


def test_risk_and_opportunity_are_never_cross_ranked():
    source = {
        "interpreted_insights": [
            _item(
                "opportunity.critical",
                finding_class="opportunity",
                severity="critical",
            ),
            _item(
                "risk.low",
                finding_class="risk",
                severity="low",
            ),
        ]
    }

    out = build_governed_business_findings(
        business_rule_interpretation=source,
    )

    assert out["risks"][0]["finding_prioritization"]["rank"] == 1
    assert out["opportunities"][0]["finding_prioritization"]["rank"] == 1
    assert out["governance"]["cross_class_ranking"] is False


def test_missing_severity_is_preserved_but_not_prioritized():
    source = {
        "interpreted_insights": [
            _item(
                "risk.no-severity",
                finding_class="risk",
                severity=None,
            ),
            _item(
                "risk.medium",
                finding_class="risk",
                severity="medium",
            ),
        ]
    }

    out = build_governed_business_findings(
        business_rule_interpretation=source,
    )

    assert [x["id"] for x in out["risks"]] == [
        "risk.medium",
        "risk.no-severity",
    ]

    unresolved = out["risks"][1]["finding_prioritization"]

    assert unresolved["status"] == "NOT_EVALUATED"
    assert unresolved["severity"] is None
    assert unresolved["rank"] is None


def test_unclassified_and_not_applied_are_not_promoted():
    source = {
        "interpreted_insights": [
            _item(
                "no.rule",
                applied=False,
            ),
            _item(
                "legacy.severity.only",
                finding_class=None,
                severity="high",
                applied=True,
            ),
        ]
    }

    out = build_governed_business_findings(
        business_rule_interpretation=source,
    )

    assert out["risks"] == []
    assert out["opportunities"] == []
    assert len(out["unclassified"]) == 2

    assert all(
        item["finding_prioritization"]["status"] == "NOT_EVALUATED"
        for item in out["unclassified"]
    )


def test_attention_and_informational_remain_separate():
    source = {
        "interpreted_insights": [
            _item(
                "attention.high",
                finding_class="attention",
                severity="high",
            ),
            _item(
                "info.low",
                finding_class="informational",
                severity="low",
            ),
        ]
    }

    out = build_governed_business_findings(
        business_rule_interpretation=source,
    )

    assert out["risks"] == []
    assert out["opportunities"] == []
    assert out["counts"]["attention"] == 1
    assert out["counts"]["informational"] == 1


def test_ties_are_deterministic_by_finding_id():
    source = {
        "interpreted_insights": [
            _item(
                "risk.z",
                finding_class="risk",
                severity="high",
            ),
            _item(
                "risk.a",
                finding_class="risk",
                severity="high",
            ),
        ]
    }

    out = build_governed_business_findings(
        business_rule_interpretation=source,
    )

    assert [x["id"] for x in out["risks"]] == [
        "risk.a",
        "risk.z",
    ]


def test_source_interpretation_is_immutable():
    source = {
        "interpreted_insights": [
            _item(
                "risk.high",
                finding_class="risk",
                severity="high",
            ),
            _item(
                "opportunity.medium",
                finding_class="opportunity",
                severity="medium",
            ),
        ]
    }

    before = deepcopy(source)

    build_governed_business_findings(
        business_rule_interpretation=source,
    )

    assert source == before
