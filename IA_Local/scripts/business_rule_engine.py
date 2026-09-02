from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Tuple

BUSINESS_RULE_ENGINE_VERSION = "r10.15a"

_ALLOWED_OPERATORS = {"gte", "lte"}
_ALLOWED_FIELDS = {"change_pct", "share_pct"}
_FORBIDDEN_RULE_KEYS = {"expression", "formula", "python", "code", "eval"}


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _parse_date(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def _rule_scope_matches(rule: Dict[str, Any], context: Dict[str, Any]) -> bool:
    scope = dict(rule.get("scope") or {})
    for key, expected in scope.items():
        if expected in (None, "", "*"):
            continue
        if str(context.get(str(key)) or "") != str(expected):
            return False
    return True


def _rule_effective(rule: Dict[str, Any], as_of: date) -> bool:
    start = _parse_date(rule.get("effective_from"))
    end = _parse_date(rule.get("effective_to"))
    if rule.get("effective_from") not in (None, "") and start is None:
        return False
    if rule.get("effective_to") not in (None, "") and end is None:
        return False
    if start and as_of < start:
        return False
    if end and as_of > end:
        return False
    return True


def _validate_rule(rule: Dict[str, Any]) -> Tuple[bool, str]:
    if not str(rule.get("rule_id") or "").strip():
        return False, "missing_rule_id"
    if any(key in rule for key in _FORBIDDEN_RULE_KEYS):
        return False, "arbitrary_expression_not_allowed"
    if str(rule.get("operator") or "") not in _ALLOWED_OPERATORS:
        return False, "unsupported_operator"
    if str(rule.get("field") or "") not in _ALLOWED_FIELDS:
        return False, "unsupported_field"
    if _to_float(rule.get("threshold")) is None:
        return False, "invalid_threshold"
    classification = dict(rule.get("classification") or {})
    if not classification:
        return False, "missing_classification"
    return True, ""


def _rule_matches_insight(rule: Dict[str, Any], insight: Dict[str, Any]) -> bool:
    expected_type = str(rule.get("insight_type") or "")
    expected_metric = str(rule.get("metric") or "")
    if expected_type and expected_type != str(insight.get("insight_type") or ""):
        return False
    if expected_metric and expected_metric != str(insight.get("metric") or ""):
        return False

    field = str(rule.get("field") or "")
    actual = _to_float(insight.get(field))
    threshold = _to_float(rule.get("threshold"))
    if actual is None or threshold is None:
        return False

    op = str(rule.get("operator") or "")
    if op == "gte":
        return actual >= threshold
    if op == "lte":
        return actual <= threshold
    return False


def apply_governed_business_rules(
    *,
    business_insights: Dict[str, Any],
    rule_registry: Optional[Iterable[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
    as_of: Optional[str] = None,
) -> Dict[str, Any]:
    # Interpret deterministic insights using only explicit governed whitelist rules.
    # R10.15A intentionally ships with no company thresholds. Rules must be supplied
    # explicitly by a governed registry. Arbitrary expressions are never evaluated.
    ctx = dict(context or {})
    resolved_as_of = _parse_date(as_of) if as_of else date.today()
    if resolved_as_of is None:
        resolved_as_of = date.today()

    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for raw in list(rule_registry or []):
        rule = dict(raw or {})
        ok, reason = _validate_rule(rule)
        if not ok:
            rejected.append({
                "rule_id": rule.get("rule_id"),
                "reason": reason,
            })
            continue
        if rule.get("enabled") is False:
            continue
        if not _rule_scope_matches(rule, ctx):
            continue
        if not _rule_effective(rule, resolved_as_of):
            continue
        accepted.append(rule)

    accepted.sort(
        key=lambda r: (
            -int(r.get("priority") or 0),
            str(r.get("rule_id") or ""),
        )
    )

    interpreted: List[Dict[str, Any]] = []
    applications: List[Dict[str, Any]] = []

    for source in list((business_insights or {}).get("insights") or []):
        item = deepcopy(source)
        item["enterprise_interpretation"] = {
            "status": "NOT_APPLIED",
            "rule_id": None,
            "classification": None,
        }

        for rule in accepted:
            if not _rule_matches_insight(rule, item):
                continue

            classification = deepcopy(dict(rule.get("classification") or {}))
            item["enterprise_interpretation"] = {
                "status": "APPLIED",
                "rule_id": rule.get("rule_id"),
                "ruleset_version": rule.get("ruleset_version"),
                "classification": classification,
                "priority": int(rule.get("priority") or 0),
                "effective_from": rule.get("effective_from"),
                "effective_to": rule.get("effective_to"),
                "scope": deepcopy(dict(rule.get("scope") or {})),
            }

            applications.append({
                "insight_id": item.get("id"),
                "rule_id": rule.get("rule_id"),
                "field": rule.get("field"),
                "operator": rule.get("operator"),
                "threshold": rule.get("threshold"),
                "observed_value": item.get(str(rule.get("field") or "")),
                "classification": classification,
            })
            break

        interpreted.append(item)

    return {
        "schema_version": BUSINESS_RULE_ENGINE_VERSION,
        "mode": "governed-whitelist-business-rules",
        "as_of": resolved_as_of.isoformat(),
        "context": ctx,
        "active_rule_count": len(accepted),
        "rejected_rule_count": len(rejected),
        "applied_rule_count": len(applications),
        "interpreted_insights": interpreted,
        "rule_applications": applications,
        "rejected_rules": rejected,
        "observations": deepcopy(list((business_insights or {}).get("observations") or [])),
        "governance": {
            "default_enterprise_thresholds": False,
            "arbitrary_expression_evaluation": False,
            "whitelist_operators_only": True,
            "explicit_registry_required": True,
            "effective_date_guard": True,
            "scope_guard": True,
            "priority_resolution": "highest_priority_first_match",
            "source_business_insights_are_not_mutated": True,
        },
    }
