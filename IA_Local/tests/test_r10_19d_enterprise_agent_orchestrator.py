from pathlib import Path
import json, sys, tempfile
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]; S=ROOT/"scripts"
if str(S) not in sys.path: sys.path.insert(0,str(S))
from enterprise_agent_orchestrator import answer_enterprise_question_orchestrated
from enterprise_knowledge_store import EnterpriseKnowledgeStore
from enterprise_deliverable_registry import GovernedDeliverableRegistry
from enterprise_deliverable_manifest import build_governed_deliverable_manifest
from enterprise_sql_gateway import EnterpriseSqlError
import analizador_universal as analyzer
SCOPE={"company_id":"obra","user_id":"ana","business_unit":None,"branch":None}; OTHER={"company_id":"otra","user_id":"ana","business_unit":None,"branch":None}
def ck(n,x):
 if not x: raise AssertionError(n)
 print("PASS",n)
class FakeSql:
 def execute(self,scope,cid,plan):
  if "UPDATE" in plan.get("sql","").upper(): raise EnterpriseSqlError("SQL_QUERY_NOT_READ_ONLY","no")
  return {"status":"ANSWERED","columns":["avance"],"rows":[[2]],"row_count":1,"truncated":False,"provenance":{"connection_id":cid,"provider":"sqlserver"}}
def run(reports,blocked=False,run_id="r",scope=SCOPE):
 comp={"id":"kpi:freight","status":"BLOCKED","reason":"rule"} if blocked else {"id":"kpi:revenue","status":"SUPPORTED","value":7}
 spec={"schema_version":"x","source":{"fingerprint_sha256":"b"*64},"components":[comp]}; plan={"execution_plan":{"dashboard_spec":spec}}
 man=build_governed_deliverable_manifest(dashboard_plan=plan,filename="x")
 (reports/"d.html").write_text("<script>const DATA="+json.dumps({"plan":{"execution_plan":{"dashboard_spec":spec}}})+";</script>",encoding="utf8")
 return GovernedDeliverableRegistry(reports).register(scope=scope,run_id=run_id,manifest=man,outputs={"html":"d.html"})
print("=== R10.19D ===")
with tempfile.TemporaryDirectory() as td:
 r=Path(td); reports=r/"R"; reports.mkdir(); ks=EnterpriseKnowledgeStore(r/"K"); reg=GovernedDeliverableRegistry(reports)
 ks.register_knowledge(scope=SCOPE,knowledge_id="abc",knowledge_type="definition",title="avance físico",content="Avance físico validado.",source={"source":"doc"},provenance={"origin":"human"})
 try: answer_enterprise_question_orchestrated(registry=reg,knowledge_store=ks,scope=SCOPE,question="")
 except ValueError as e: ck("question_required",str(e)=="QUESTION_REQUIRED")
 q=answer_enterprise_question_orchestrated(registry=reg,knowledge_store=ks,scope=SCOPE,question="avance físico"); ck("knowledge_business_agnostic",q["status"]=="ANSWERED" and q["sources_used"]==["enterprise_knowledge"])
 ck("scope_knowledge",answer_enterprise_question_orchestrated(registry=reg,knowledge_store=ks,scope=OTHER,question="avance físico")["status"]=="UNRESOLVED")
 run(reports); cur=answer_enterprise_question_orchestrated(registry=reg,knowledge_store=ks,scope=SCOPE,run_id="r",question="ventas"); ck("current_precedence",cur["status"]=="ANSWERED" and cur["sources_used"]==["current_governed_run"])
 run(reports,blocked=True,run_id="blocked"); block=answer_enterprise_question_orchestrated(registry=reg,knowledge_store=ks,scope=SCOPE,run_id="blocked",question="flete"); ck("blocked_precedence",block["status"]=="BLOCKED" and block["sources_used"]==["current_governed_run"])
 sql=answer_enterprise_question_orchestrated(registry=reg,knowledge_store=ks,scope=SCOPE,question="avance actual",sql_context={"connection_id":"c","query_plan":{"sql":"SELECT"}},sql_executor=FakeSql()); ck("sql_route",sql["status"]=="ANSWERED" and sql["sources_used"]==["governed_sql"] and sql["provenance"]["provider"]=="sqlserver")
 missing=answer_enterprise_question_orchestrated(registry=reg,knowledge_store=ks,scope=SCOPE,question="x",sql_context={},sql_executor=FakeSql()); ck("sql_plan_required",missing["status"]=="UNRESOLVED")
 ks.register_knowledge(scope=SCOPE,knowledge_id="c1",knowledge_type="definition",title="nivel servicio",content="Nivel A.",source={"source":"d"},provenance={"origin":"human"})
 ks.register_knowledge(scope=SCOPE,knowledge_id="c2",knowledge_type="definition",title="nivel servicio",content="Nivel B.",source={"source":"d"},provenance={"origin":"human"})
 conflict=answer_enterprise_question_orchestrated(registry=reg,knowledge_store=ks,scope=SCOPE,question="nivel servicio"); ck("knowledge_conflict",conflict["status"]=="CONFLICT" and len(conflict["knowledge_ids"])==2 and conflict["routing"]["selected_sources"]==["enterprise_knowledge"])
 active=ks.register_knowledge(scope=SCOPE,knowledge_id="old",knowledge_type="definition",title="vigencia",content="Activo.",source={"source":"d"},provenance={"origin":"human"}); ck("active_answer",answer_enterprise_question_orchestrated(registry=reg,knowledge_store=ks,scope=SCOPE,question="vigencia")["status"]=="ANSWERED"); ks.invalidate(SCOPE,"old",reason="retired",actor="ana"); ck("invalidation",answer_enterprise_question_orchestrated(registry=reg,knowledge_store=ks,scope=SCOPE,question="vigencia")["status"]=="UNRESOLVED")
 old_reports,old_executor=analyzer.base.REPORTES,analyzer._sql_executor; analyzer.base.REPORTES=reports; run(reports,run_id="api-r",scope=analyzer._local_deliverable_scope()); analyzer._sql_executor=lambda:FakeSql()
 try:
  with TestClient(analyzer.app) as client:
   plain=client.post("/api/ask",json={"question":"ventas","run_id":"api-r"}); ck("api_without_sql",plain.status_code==200 and plain.json()["result"]["status"]=="ANSWERED")
   via=client.post("/api/ask",json={"question":"avance","sql":{"connection_id":"c","query_plan":{"sql":"SELECT"}}}); ck("api_with_sql",via.status_code==200 and via.json()["result"]["routing"]["selected_sources"]==["governed_sql"])
   danger=client.post("/api/ask",json={"question":"x","sql":{"connection_id":"c","query_plan":{"sql":"UPDATE x"}}}); ck("api_sql_policy",danger.status_code==400)
 finally: analyzer.base.REPORTES,analyzer._sql_executor=old_reports,old_executor
print("PASS R10.19D")
