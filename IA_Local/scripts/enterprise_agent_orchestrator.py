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
def answer_enterprise_question_orchestrated(*,registry,knowledge_store,scope,question:str,run_id:Optional[str]=None,sql_context:Optional[Dict[str,Any]]=None,sql_executor:Optional[EnterpriseSqlExecutor]=None):
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
        result=sql_executor.execute(scope,str(sql_context["connection_id"]),sql_context["query_plan"])
        return _wrap({"status":result["status"],"question":text,"answer":{"columns":result["columns"],"rows":result["rows"],"row_count":result["row_count"],"truncated":result["truncated"]},"provenance":result["provenance"]},attempted,["governed_sql"],started)
    attempted.append("enterprise_knowledge")
    result=answer_unified_enterprise_question(registry=registry,knowledge_store=knowledge_store,scope=scope,question=text,run_id=None)
    return _wrap(result,attempted,["enterprise_knowledge"] if result.get("status")!="UNRESOLVED" else [],started)
