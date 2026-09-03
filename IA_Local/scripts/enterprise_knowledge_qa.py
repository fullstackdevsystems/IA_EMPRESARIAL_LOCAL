from __future__ import annotations

from typing import Any, Dict, Optional

from enterprise_deliverable_registry import DeliverableRegistryError, GovernedDeliverableRegistry
from enterprise_knowledge_store import EnterpriseKnowledgeStore
from enterprise_question_answering import answer_enterprise_question


ENTERPRISE_KNOWLEDGE_QA_VERSION = "r10.19b"


def _governance() -> Dict[str, bool]:
    return {"fail_closed": True, "llm_computational_authority": False, "llm_formula_authority": False, "source_data_precedence": True}


def _knowledge_answer(question: str, matches: list[Dict[str, Any]]) -> Dict[str, Any]:
    if not matches:
        return {"schema_version": ENTERPRISE_KNOWLEDGE_QA_VERSION, "status": "UNRESOLVED", "question": question, "answer": None, "reason": "knowledge_not_found", "evidence_source": "enterprise_knowledge_store", "knowledge_ids": [], "governance": _governance()}
    top_score = matches[0]["relevance"]["score"]
    top = [item for item in matches if item["relevance"]["score"] == top_score]
    contents = {str(item.get("content") or "") for item in top}
    if len(contents) > 1:
        return {"schema_version": ENTERPRISE_KNOWLEDGE_QA_VERSION, "status": "CONFLICT", "question": question, "answer": None, "reason": "conflicting_active_knowledge", "evidence_source": "enterprise_knowledge_store", "knowledge_ids": [item["knowledge_id"] for item in top], "provenance": [item["provenance"] for item in top], "governance": _governance()}
    item = top[0]
    return {"schema_version": ENTERPRISE_KNOWLEDGE_QA_VERSION, "status": "ANSWERED", "question": question, "answer": item["content"], "reason": None, "evidence_source": "enterprise_knowledge_store", "answer_source_type": item["knowledge_type"], "knowledge_ids": [item["knowledge_id"]], "provenance": item["provenance"], "governance": _governance()}


def answer_unified_enterprise_question(*, registry: GovernedDeliverableRegistry, knowledge_store: EnterpriseKnowledgeStore, scope: Dict[str, Any], question: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    """Prioriza evidencia actual; sólo recurre a conocimiento gobernado si falta."""
    text = str(question or "").strip()
    if not text:
        raise ValueError("QUESTION_REQUIRED")
    if run_id:
        try:
            current = answer_enterprise_question(registry=registry, scope=scope, run_id=run_id, question=text)
            if current.get("status") != "UNRESOLVED":
                current["evidence_source"] = "current_governed_run"
                current["knowledge_ids"] = []
                return current
        except DeliverableRegistryError:
            raise
    return _knowledge_answer(text, knowledge_store.search(scope, text))
