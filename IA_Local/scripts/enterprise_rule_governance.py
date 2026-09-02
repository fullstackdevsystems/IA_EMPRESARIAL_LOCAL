from __future__ import annotations
from typing import Any, Dict

ENTERPRISE_RULE_GOVERNANCE_VERSION = "r10.15f"

_EXPECTED = {
    "business_rule_engine": "r10.15a",
    "business_rule_registry": "r10.15d",
    "business_rule_context": "r10.15c",
    "enterprise_metric_rule_registry": "r10.15e",
}


def build_enterprise_rule_governance_audit(
    *,
    business_rule_interpretation: Dict[str, Any],
    business_rule_registry: Dict[str, Any],
    business_rule_context: Dict[str, Any],
    enterprise_metric_rule_registry: Dict[str, Any],
) -> Dict[str, Any]:
    versions = {
        "business_rule_engine": business_rule_interpretation.get("schema_version"),
        "business_rule_registry": business_rule_registry.get("schema_version"),
        "business_rule_context": business_rule_context.get("schema_version"),
        "enterprise_metric_rule_registry": enterprise_metric_rule_registry.get("schema_version"),
    }

    version_match = all(versions.get(k) == v for k, v in _EXPECTED.items())
    business_registry_status = str(business_rule_registry.get("status") or "")
    metric_registry_status = str(enterprise_metric_rule_registry.get("status") or "")
    context_status = str(business_rule_context.get("status") or "")

    interpretation_governance = dict(business_rule_interpretation.get("governance") or {})
    business_registry_governance = dict(business_rule_registry.get("governance") or {})
    context_governance = dict(business_rule_context.get("governance") or {})
    metric_governance = dict(enterprise_metric_rule_registry.get("governance") or {})

    safety = {
        "no_default_enterprise_thresholds": interpretation_governance.get("default_enterprise_thresholds") is False,
        "no_arbitrary_business_expression_eval": interpretation_governance.get("arbitrary_expression_evaluation") is False,
        "business_registry_fail_closed": business_registry_governance.get("fail_closed") is True,
        "context_fail_closed": context_governance.get("fail_closed") is True,
        "enterprise_metric_registry_fail_closed": metric_governance.get("fail_closed") is True,
        "enterprise_metric_no_arbitrary_formula_eval": metric_governance.get("arbitrary_formula_evaluation") is False,
        "enterprise_metric_whitelist_only": metric_governance.get("whitelist_operators_only") is True,
        "scoped_context_must_be_explicit": context_governance.get("explicit_context_required_for_scoped_rules") is True,
    }

    registries_valid = business_registry_status not in {"INVALID", "ERROR"} and metric_registry_status not in {"INVALID", "ERROR"}
    context_valid = context_status != "INVALID"
    safety_pass = all(bool(v) for v in safety.values())
    ready = version_match and registries_valid and context_valid and safety_pass

    return {
        "schema_version": ENTERPRISE_RULE_GOVERNANCE_VERSION,
        "status": "READY" if ready else "BLOCKED",
        "versions": versions,
        "expected_versions": dict(_EXPECTED),
        "version_contract_ok": version_match,
        "business_rule_registry_status": business_registry_status,
        "business_rule_context_status": context_status,
        "enterprise_metric_rule_registry_status": metric_registry_status,
        "safety_contract": safety,
        "safety_contract_ok": safety_pass,
        "governance": {
            "invalid_context_blocks_business_rule_execution": True,
            "invalid_context_blocks_enterprise_metric_rule_execution": True,
            "invalid_explicit_as_of_is_fail_closed": True,
            "arbitrary_eval_is_never_required": True,
            "phase_r10_15_consolidated": True,
        },
    }
