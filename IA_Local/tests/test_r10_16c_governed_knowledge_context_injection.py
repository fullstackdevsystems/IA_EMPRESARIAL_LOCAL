from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "scripts"
if str(S) not in sys.path:
    sys.path.insert(0, str(S))

from enterprise_knowledge_registry import load_governed_enterprise_knowledge_registry
from enterprise_knowledge_retrieval import retrieve_contextual_enterprise_knowledge
from enterprise_knowledge_context_injection import (
    KNOWLEDGE_CONTEXT_INJECTION_VERSION,
    build_governed_knowledge_interpretation,
    inject_governed_knowledge_into_intent,
)


def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)


print()
print("=== R10.16C GOVERNED KNOWLEDGE CONTEXT INJECTION ===")

intent = {
    "domain": "sales",
    "metrics": ["revenue", "freight"],
    "dimensions": ["customer"],
    "analyses": ["profitability", "freight_analysis"],
    "pages": ["summary"],
    "requested_items": [
        {"kind": "metric", "key": "revenue"},
        {"kind": "metric", "key": "freight"},
    ],
}

with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "knowledge.json"
    p.write_text(json.dumps({
        "schema_version": "r10.16a",
        "registry_id": "demo",
        "knowledge_version": "1",
        "entries": [
            {
                "entry_id": "demo.freight.policy.v1",
                "type": "policy",
                "status": "APPROVED",
                "title": "Política de flete",
                "content": "El flete requiere una regla empresarial validada.",
                "scope": {"company_id": "DEMO"},
                "provenance": {
                    "source": "manual_validation",
                    "document_id": "POL-001"
                }
            },
            {
                "entry_id": "demo.currency.v1",
                "type": "definition",
                "status": "APPROVED",
                "title": "Moneda",
                "content": "MXN",
                "scope": {"company_id": "DEMO"},
                "provenance": {"source": "manual_validation"}
            }
        ]
    }), encoding="utf-8")

    registry = load_governed_enterprise_knowledge_registry(str(p))
    retrieval = retrieve_contextual_enterprise_knowledge(
        prompt="Analiza flete y política de flete",
        registry=registry,
        context={"company_id": "DEMO"},
        as_of="2026-09-02",
    )

    interpretation = build_governed_knowledge_interpretation(
        intent=intent,
        knowledge_retrieval=retrieval,
    )

    check("version", KNOWLEDGE_CONTEXT_INJECTION_VERSION == "r10.16c")
    check("status_enriched", interpretation["status"] == "ENRICHED")
    check("policy_present", len(interpretation["policies"]) == 1)
    check("provenance_present", interpretation["policies"][0]["provenance"]["source"] == "manual_validation")
    check("formula_authority_false", interpretation["governance"]["does_not_authorize_formulas"] is True)

    enriched = inject_governed_knowledge_into_intent(
        intent=intent,
        knowledge_interpretation=interpretation,
    )

    check("metrics_unchanged", enriched["metrics"] == intent["metrics"])
    check("dimensions_unchanged", enriched["dimensions"] == intent["dimensions"])
    check("analyses_unchanged", enriched["analyses"] == intent["analyses"])
    check("pages_unchanged", enriched["pages"] == intent["pages"])
    check("requested_items_unchanged", enriched["requested_items"] == intent["requested_items"])
    check("knowledge_attached", enriched["enterprise_knowledge_interpretation"]["status"] == "ENRICHED")
    check("no_computational_authority", enriched["knowledge_governance"]["computational_authority"] is False)

empty = build_governed_knowledge_interpretation(
    intent=intent,
    knowledge_retrieval={"status": "EMPTY", "matches": []},
)
check("empty_safe", empty["status"] == "EMPTY")

blocked = build_governed_knowledge_interpretation(
    intent=intent,
    knowledge_retrieval={"status": "BLOCKED", "matches": [], "reason": "invalid_registry"},
)
check("blocked_fail_closed", blocked["status"] == "BLOCKED")

builder = (S / "dashboard_spec_builder.py").read_text(encoding="utf-8", errors="replace")
check("builder_import", "enterprise_knowledge_context_injection" in builder)
check("builder_interpretation", "enterprise_knowledge_interpretation" in builder)
check("builder_injection", "inject_governed_knowledge_into_intent" in builder)

print()
print("PASS R10.16C GOVERNED KNOWLEDGE CONTEXT INJECTION")
