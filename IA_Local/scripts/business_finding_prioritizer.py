from copy import deepcopy
from typing import Any, Dict, List, Tuple


BUSINESS_FINDING_PRIORITIZER_VERSION = "r10.25c4"

_FINDING_CLASSES = {
    "risk",
    "opportunity",
    "attention",
    "informational",
}

# This is ordering of an already governed, rule-supplied classification.
# It is not a calculated score, business threshold, or rule precedence.
_SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "informational": 4,
}


def _finding_id(item: Dict[str, Any]) -> str:
    return str(item.get("id") or item.get("insight_id") or "")


def _classification(item: Dict[str, Any]) -> Tuple[str, str]:
    interpretation = dict(item.get("enterprise_interpretation") or {})

    if str(interpretation.get("status") or "").upper() != "APPLIED":
        return "", ""

    classification = dict(interpretation.get("classification") or {})

    finding_class = str(classification.get("finding_class") or "").strip().lower()
    severity = str(classification.get("severity") or "").strip().lower()

    if finding_class not in _FINDING_CLASSES:
        return "", ""

    return finding_class, severity


def _sort_key(item: Dict[str, Any]) -> Tuple[int, str]:
    _, severity = _classification(item)

    severity_rank = _SEVERITY_ORDER.get(severity)

    # Missing/unknown severity is not invented. Such findings remain valid
    # but are placed after explicitly governed severities.
    unresolved_rank = len(_SEVERITY_ORDER) + 1

    return (
        severity_rank if severity_rank is not None else unresolved_rank,
        _finding_id(item),
    )


def build_governed_business_findings(
    *,
    business_rule_interpretation: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build deterministic prioritized business findings from already interpreted
    governed insights.

    This layer does not:
      - calculate risk/opportunity classifications,
      - calculate severity,
      - reuse rule priority as finding priority,
      - invent business thresholds,
      - create numeric scores,
      - invoke or delegate authority to an LLM.
    """

    source_items = list(
        (business_rule_interpretation or {}).get("interpreted_insights") or []
    )

    risks: List[Dict[str, Any]] = []
    opportunities: List[Dict[str, Any]] = []
    attention: List[Dict[str, Any]] = []
    informational: List[Dict[str, Any]] = []
    unclassified: List[Dict[str, Any]] = []

    for source in source_items:
        item = deepcopy(source)
        finding_class, severity = _classification(item)

        interpretation = dict(item.get("enterprise_interpretation") or {})

        if not finding_class:
            item["finding_prioritization"] = {
                "status": "NOT_EVALUATED",
                "reason": "No governed finding classification was applied.",
                "finding_class": None,
                "severity": None,
                "rank": None,
            }
            unclassified.append(item)
            continue

        severity_is_governed = severity in _SEVERITY_ORDER

        item["finding_prioritization"] = {
            "status": (
                "PRIORITIZED"
                if severity_is_governed
                else "NOT_EVALUATED"
            ),
            "reason": (
                None
                if severity_is_governed
                else "No governed severity was supplied."
            ),
            "finding_class": finding_class,
            "severity": severity if severity else None,
            "rank": None,
            "rule_id": interpretation.get("rule_id"),
            "ruleset_version": interpretation.get("ruleset_version"),
        }

        if finding_class == "risk":
            risks.append(item)
        elif finding_class == "opportunity":
            opportunities.append(item)
        elif finding_class == "attention":
            attention.append(item)
        elif finding_class == "informational":
            informational.append(item)

    risks.sort(key=_sort_key)
    opportunities.sort(key=_sort_key)
    attention.sort(key=_sort_key)
    informational.sort(key=_sort_key)

    # Rank is positional only inside the same governed finding class.
    # It is not a score and does not cross-compare risk vs opportunity.
    for collection in (risks, opportunities, attention, informational):
        governed_position = 0

        for item in collection:
            prioritization = item["finding_prioritization"]

            if prioritization["status"] != "PRIORITIZED":
                continue

            governed_position += 1
            prioritization["rank"] = governed_position

    return {
        "schema_version": BUSINESS_FINDING_PRIORITIZER_VERSION,
        "mode": "governed-deterministic-finding-prioritization",
        "risks": risks,
        "opportunities": opportunities,
        "attention": attention,
        "informational": informational,
        "unclassified": unclassified,
        "counts": {
            "risks": len(risks),
            "opportunities": len(opportunities),
            "attention": len(attention),
            "informational": len(informational),
            "unclassified": len(unclassified),
        },
        "governance": {
            "source": "business_rule_interpretation.interpreted_insights",
            "classification_is_rule_supplied_only": True,
            "severity_is_rule_supplied_only": True,
            "severity_used_for_ordering_only": True,
            "rule_priority_used_for_finding_ranking": False,
            "numeric_finding_scores": False,
            "business_thresholds_invented": False,
            "cross_class_ranking": False,
            "unclassified_findings_promoted": False,
            "missing_severity_is_not_invented": True,
            "llm_classification_authority": False,
            "llm_severity_authority": False,
            "llm_ranking_authority": False,
            "source_interpretation_is_not_mutated": True,
        },
    }
