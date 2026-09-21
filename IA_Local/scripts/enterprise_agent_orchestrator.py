from __future__ import annotations
import time
from typing import Any, Dict, Optional
from enterprise_question_answering import answer_enterprise_question
from enterprise_knowledge_qa import answer_unified_enterprise_question
from enterprise_sql_gateway import EnterpriseSqlExecutor

ENTERPRISE_AGENT_ORCHESTRATOR_VERSION="r10.19d"
def _wrap(result, attempted, selected, started):
    result=dict(result); result["schema_version"]=ENTERPRISE_AGENT_ORCHESTRATOR_VERSION
    result["sources_used"]=selected; result["routing"]={"attempted_sources":attempted,"selected_sources":selected,"orchestrator_ms":round((time.time()-started)*1000,2)}
    result.setdefault("governance",{}).update({"fail_closed":True,"llm_computational_authority":False,"llm_formula_authority":False,"llm_sql_execution_authority":False})
    return result
def answer_enterprise_question_orchestrated(*,registry,knowledge_store,scope,question:str,run_id:Optional[str]=None,sql_context:Optional[Dict[str,Any]]=None,sql_executor:Optional[EnterpriseSqlExecutor]=None,sql_scope:Optional[Dict[str,Any]]=None):
    text=str(question or "").strip()
    if not text: raise ValueError("QUESTION_REQUIRED")
    started=time.time(); attempted=[]
    if run_id:
        attempted.append("current_governed_run")
        current=answer_enterprise_question(registry=registry,scope=scope,run_id=run_id,question=text)
        if current.get("status")!="UNRESOLVED": return _wrap(current,attempted,["current_governed_run"],started)
    if sql_context is not None:
        attempted.append("governed_sql")
        if not sql_executor or not sql_context.get("connection_id") or not isinstance(sql_context.get("query_plan"),dict):
            return _wrap({"status":"UNRESOLVED","question":text,"answer":None,"reason":"AGENT_SQL_PLAN_REQUIRED"},attempted,[],started)
        effective_sql_scope=sql_scope if sql_scope is not None else scope
        result=sql_executor.execute(effective_sql_scope,str(sql_context["connection_id"]),sql_context["query_plan"])
        return _wrap({"status":result["status"],"question":text,"answer":{"columns":result["columns"],"rows":result["rows"],"row_count":result["row_count"],"truncated":result["truncated"]},"provenance":result["provenance"]},attempted,["governed_sql"],started)
    attempted.append("enterprise_knowledge")
    result=answer_unified_enterprise_question(registry=registry,knowledge_store=knowledge_store,scope=scope,question=text,run_id=None)
    return _wrap(result,attempted,["enterprise_knowledge"] if result.get("status")!="UNRESOLVED" else [],started)
# R10.25B1: pure enterprise routing contract.
#
# This layer decides routing precedence and governance only. It deliberately
# does not execute SQL, retrieve memories/documents, build RAG context, call an
# LLM, or compose the final answer. Execution remains the responsibility of
# EnterpriseAIService and the existing governed authorities.
R10_25B1_ROUTING_CONTRACT_VERSION = "r10.25b1"

ENTERPRISE_ROUTE_GOVERNANCE = {
    "fail_closed": True,
    "llm_computational_authority": False,
    "llm_formula_authority": False,
    "llm_sql_execution_authority": False,
}


class EnterpriseRouteDecision:
    """Immutable-by-convention routing decision for enterprise chat."""

    __slots__ = ("route", "reason", "governance")

    def __init__(self, route: str, reason: str):
        route_value = str(route or "").strip()
        reason_value = str(reason or "").strip()

        allowed = {
            "governed_sql",
            "memory_lexical",
            "system_capabilities",
            "general_llm",
            "internal_context",
        }

        if route_value not in allowed:
            raise ValueError("ENTERPRISE_ROUTE_NOT_ALLOWED")

        if not reason_value:
            raise ValueError("ENTERPRISE_ROUTE_REASON_REQUIRED")

        self.route = route_value
        self.reason = reason_value
        self.governance = dict(ENTERPRISE_ROUTE_GOVERNANCE)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": R10_25B1_ROUTING_CONTRACT_VERSION,
            "route": self.route,
            "reason": self.reason,
            "governance": dict(self.governance),
        }


def route_enterprise_question(
    *,
    question: str,
    governed_sql_available: bool = False,
    direct_memory_question: bool = False,
    system_capabilities_question: bool = False,
    general_knowledge_question: bool = False,
) -> EnterpriseRouteDecision:
    """Return the governed execution route without executing the route.

    Precedence intentionally mirrors the current EnterpriseAIService.chat()
    behavior:

      governed_sql
      -> memory_lexical
      -> system_capabilities
      -> general_llm
      -> internal_context

    The classifier booleans are supplied by the existing service classifiers.
    R10.25B1 therefore centralizes precedence without duplicating classifier
    logic.
    """

    text = str(question or "").strip()

    if not text:
        raise ValueError("QUESTION_REQUIRED")

    if governed_sql_available:
        return EnterpriseRouteDecision(
            "governed_sql",
            "GOVERNED_SQL_AVAILABLE",
        )

    if direct_memory_question:
        return EnterpriseRouteDecision(
            "memory_lexical",
            "DIRECT_MEMORY_QUESTION",
        )

    if system_capabilities_question:
        return EnterpriseRouteDecision(
            "system_capabilities",
            "SYSTEM_CAPABILITIES_QUESTION",
        )

    if general_knowledge_question:
        return EnterpriseRouteDecision(
            "general_llm",
            "GENERAL_KNOWLEDGE_QUESTION",
        )

    return EnterpriseRouteDecision(
        "internal_context",
        "ENTERPRISE_CONTEXT_REQUIRED",
    )
