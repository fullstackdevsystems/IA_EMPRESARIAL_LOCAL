from pathlib import Path
import json, sys, tempfile
ROOT=Path(__file__).resolve().parents[1]; S=ROOT/"scripts"
if str(S) not in sys.path: sys.path.insert(0,str(S))
from enterprise_knowledge_ingestion import ingest_knowledge_candidates
from enterprise_knowledge_approval import promote_draft_knowledge_entry
from enterprise_knowledge_registry import KNOWLEDGE_REGISTRY_VERSION, load_governed_enterprise_knowledge_registry, retrieve_governed_enterprise_knowledge
def check(n,c):
    if not c: print("FAIL",n); raise AssertionError(n)
    print("PASS",n)
def approved_entry(raw):
    x=dict(raw); x["status"]="DRAFT"
    ing=ingest_knowledge_candidates(candidates=[x]); d=ing["accepted_entries"][0]
    r=promote_draft_knowledge_entry(entry=d,approved_by="TEST_ADMIN",approved_at="2026-09-02T14:30:00-07:00",expected_content_fingerprint_sha256=d["content_fingerprint_sha256"])
    return r["entry"]
print("\n=== R10.16A GOVERNED ENTERPRISE KNOWLEDGE REGISTRY ===")
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/"k.json"
    approved=approved_entry({"entry_id":"company.demo.currency.v1","type":"definition","title":"Moneda operativa","content":"MXN","scope":{"company_id":"DEMO"},"effective_from":"2026-01-01","provenance":{"source":"manual_validation","source_kind":"manual_validation"}})
    draft={"entry_id":"company.demo.draft.v1","type":"fact","status":"DRAFT","title":"Dato borrador","content":"NO","scope":{"company_id":"DEMO"},"provenance":{"source":"manual_validation"}}
    p.write_text(json.dumps({"schema_version":"r10.16a","registry_id":"demo","knowledge_version":"1","entries":[approved,draft]}),encoding="utf-8")
    reg=load_governed_enterprise_knowledge_registry(str(p))
    check("version",KNOWLEDGE_REGISTRY_VERSION=="r10.16a"); check("loaded",reg["status"]=="LOADED"); check("approved_count",reg["approved_entry_count"]==1)
    r=retrieve_governed_enterprise_knowledge(registry=reg,context={"company_id":"DEMO"},as_of="2026-09-02")
    check("approved_retrieved",r["status"]=="RETRIEVED" and r["entry_count"]==1)
    check("draft_not_retrieved",r["entries"][0]["entry_id"]=="company.demo.currency.v1")
    w=retrieve_governed_enterprise_knowledge(registry=reg,context={"company_id":"OTHER"},as_of="2026-09-02"); check("scope_guard",w["entry_count"]==0)
    b=retrieve_governed_enterprise_knowledge(registry=reg,context={"company_id":"DEMO"},as_of="bad"); check("invalid_as_of_fail_closed",b["status"]=="BLOCKED")
default=load_governed_enterprise_knowledge_registry(str(ROOT/"config"/"enterprise_knowledge.json"))
check("default_empty",default["status"]=="EMPTY" and default["entry_count"]==0)
check("source_precedence",default["governance"]["knowledge_does_not_override_source_data"] is True)
check("knowledge_not_metric_authority",default["governance"]["knowledge_does_not_create_metrics_by_itself"] is True)
builder=(S/"dashboard_spec_builder.py").read_text(encoding="utf-8",errors="replace")
check("builder_import","load_governed_enterprise_knowledge_registry" in builder)
check("builder_audit",'"enterprise_knowledge_registry"' in builder)
print("\nPASS R10.16A GOVERNED ENTERPRISE KNOWLEDGE REGISTRY")
