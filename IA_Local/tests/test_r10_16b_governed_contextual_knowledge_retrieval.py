from pathlib import Path
import json, sys, tempfile
ROOT=Path(__file__).resolve().parents[1]; S=ROOT/"scripts"
if str(S) not in sys.path: sys.path.insert(0,str(S))
from enterprise_knowledge_ingestion import ingest_knowledge_candidates
from enterprise_knowledge_approval import promote_draft_knowledge_entry
from enterprise_knowledge_registry import load_governed_enterprise_knowledge_registry
from enterprise_knowledge_retrieval import KNOWLEDGE_RETRIEVAL_VERSION, public_knowledge_context, retrieve_contextual_enterprise_knowledge
def check(n,c):
    if not c: print("FAIL",n); raise AssertionError(n)
    print("PASS",n)
def approved_entry(raw):
    x=dict(raw); x["status"]="DRAFT"
    d=ingest_knowledge_candidates(candidates=[x])["accepted_entries"][0]
    return promote_draft_knowledge_entry(entry=d,approved_by="TEST_ADMIN",approved_at="2026-09-02T14:30:00-07:00",expected_content_fingerprint_sha256=d["content_fingerprint_sha256"])["entry"]
print("\n=== R10.16B GOVERNED CONTEXTUAL KNOWLEDGE RETRIEVAL ===")
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/"knowledge.json"
    freight=approved_entry({"entry_id":"demo.freight.policy.v1","type":"policy","title":"Política de flete","content":"El costo de flete requiere una regla empresarial aprobada.","keywords":["flete","costo","regla"],"scope":{"company_id":"DEMO"},"effective_from":"2026-01-01","provenance":{"source":"manual_validation","source_kind":"manual_validation","document_id":"POL-001"}})
    currency=approved_entry({"entry_id":"demo.currency.v1","type":"definition","title":"Moneda operativa","content":"MXN","scope":{"company_id":"DEMO"},"provenance":{"source":"manual_validation","source_kind":"manual_validation"}})
    draft={"entry_id":"demo.freight.draft.v1","type":"fact","status":"DRAFT","title":"Flete borrador","content":"No debe recuperarse","scope":{"company_id":"DEMO"},"provenance":{"source":"draft"}}
    p.write_text(json.dumps({"schema_version":"r10.16a","registry_id":"demo","knowledge_version":"1","entries":[freight,currency,draft]}),encoding="utf-8")
    reg=load_governed_enterprise_knowledge_registry(str(p)); check("registry_loaded",reg["status"]=="LOADED")
    r=retrieve_contextual_enterprise_knowledge(prompt="Analiza el costo de flete y usa reglas aprobadas.",registry=reg,context={"company_id":"DEMO"},as_of="2026-09-02")
    check("version",KNOWLEDGE_RETRIEVAL_VERSION=="r10.16b"); check("retrieved",r["status"]=="RETRIEVED")
    check("relevant_only",r["matched_entry_count"]==1); check("freight_selected",r["matches"][0]["entry_id"]=="demo.freight.policy.v1")
    check("draft_never_selected",all(x["entry_id"]!="demo.freight.draft.v1" for x in r["matches"]))
    check("provenance_preserved",r["matches"][0]["provenance"]["source"]=="manual_validation")
    check("deterministic_only",r["governance"]["llm_relevance_inference"] is False)
    w=retrieve_contextual_enterprise_knowledge(prompt="costo de flete",registry=reg,context={"company_id":"OTHER"},as_of="2026-09-02"); check("cross_company_empty",w["matched_entry_count"]==0)
    public=public_knowledge_context(r); check("public_context_has_match",public["matched_entry_count"]==1); check("public_context_strips_content","content" not in public["matches"][0])
    wp=Path(td)/"wildcard.json"
    wp.write_text(json.dumps({"schema_version":"r10.16a","registry_id":"bad","knowledge_version":"1","entries":[{"entry_id":"bad.scope.v1","type":"fact","status":"DRAFT","title":"Bad scope","content":"x","scope":{"company_id":"*"},"provenance":{"source":"test"}}]}),encoding="utf-8")
    bad=load_governed_enterprise_knowledge_registry(str(wp)); check("wildcard_scope_rejected",bad["status"]=="INVALID")
default=load_governed_enterprise_knowledge_registry(str(ROOT/"config"/"enterprise_knowledge.json"))
empty=retrieve_contextual_enterprise_knowledge(prompt="ventas clientes rentabilidad",registry=default,context={})
check("default_empty",empty["status"]=="EMPTY"); check("default_zero_matches",empty["matched_entry_count"]==0)
builder=(S/"dashboard_spec_builder.py").read_text(encoding="utf-8",errors="replace")
check("builder_retrieval_import","retrieve_contextual_enterprise_knowledge" in builder)
check("builder_public_context","public_knowledge_context" in builder)
check("builder_context_embedded",'"enterprise_knowledge_context"' in builder)
check("builder_internal_intent_context",'intent["knowledge_context"] = enterprise_knowledge_context' in builder)
print("\nPASS R10.16B GOVERNED CONTEXTUAL KNOWLEDGE RETRIEVAL")
