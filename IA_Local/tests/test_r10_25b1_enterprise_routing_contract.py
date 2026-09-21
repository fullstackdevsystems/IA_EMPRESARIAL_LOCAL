from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from enterprise_agent_orchestrator import (
    ENTERPRISE_ROUTE_GOVERNANCE,
    R10_25B1_ROUTING_CONTRACT_VERSION,
    EnterpriseRouteDecision,
    route_enterprise_question,
)


def check(name, condition):
    if not condition:
        raise AssertionError(name)


def decision(**kwargs):
    return route_enterprise_question(
        question="consulta empresarial",
        **kwargs,
    )


def main():
    check(
        "version",
        R10_25B1_ROUTING_CONTRACT_VERSION == "r10.25b1",
    )

    expected_governance = {
        "fail_closed": True,
        "llm_computational_authority": False,
        "llm_formula_authority": False,
        "llm_sql_execution_authority": False,
    }

    check(
        "governance_contract",
        ENTERPRISE_ROUTE_GOVERNANCE == expected_governance,
    )

    sql = decision(
        governed_sql_available=True,
        direct_memory_question=True,
        system_capabilities_question=True,
        general_knowledge_question=True,
    )
    check("sql_precedence", sql.route == "governed_sql")
    check("sql_reason", sql.reason == "GOVERNED_SQL_AVAILABLE")

    memory = decision(
        direct_memory_question=True,
        system_capabilities_question=True,
        general_knowledge_question=True,
    )
    check("memory_precedence", memory.route == "memory_lexical")

    capabilities = decision(
        system_capabilities_question=True,
        general_knowledge_question=True,
    )
    check(
        "system_capabilities_precedence",
        capabilities.route == "system_capabilities",
    )

    general = decision(
        general_knowledge_question=True,
    )
    check("general_route", general.route == "general_llm")

    internal = decision()
    check("internal_route", internal.route == "internal_context")
    check(
        "internal_reason",
        internal.reason == "ENTERPRISE_CONTEXT_REQUIRED",
    )

    payload = internal.as_dict()
    check(
        "payload_version",
        payload["schema_version"] == "r10.25b1",
    )
    check(
        "payload_governance",
        payload["governance"] == expected_governance,
    )

    # Defensive copy: a caller must not be able to mutate global governance.
    payload["governance"]["fail_closed"] = False
    check(
        "governance_copy",
        ENTERPRISE_ROUTE_GOVERNANCE["fail_closed"] is True,
    )

    try:
        route_enterprise_question(question="")
    except ValueError as exc:
        check("question_required", str(exc) == "QUESTION_REQUIRED")
    else:
        raise AssertionError("question_required")

    try:
        EnterpriseRouteDecision("unknown", "x")
    except ValueError as exc:
        check(
            "route_allowlist",
            str(exc) == "ENTERPRISE_ROUTE_NOT_ALLOWED",
        )
    else:
        raise AssertionError("route_allowlist")

    try:
        EnterpriseRouteDecision("internal_context", "")
    except ValueError as exc:
        check(
            "reason_required",
            str(exc) == "ENTERPRISE_ROUTE_REASON_REQUIRED",
        )
    else:
        raise AssertionError("reason_required")

    print("R10_25B1_ENTERPRISE_ROUTING_CONTRACT=PASS")


if __name__ == "__main__":
    main()