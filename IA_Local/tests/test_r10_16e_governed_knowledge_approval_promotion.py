from pathlib import Path
import json, sys, tempfile
ROOT=Path(__file__).resolve().parents[1]; S=ROOT/"scripts"
if str(S) not in sys.path: sys.path.insert(0,str(S))
from enterprise_knowledge_ingestion import ingest_knowledge_candidates
from enterprise_knowledge_approval import APPROVAL_WORKFLOW_VERSION, promote_draft_knowledge_entry, reject_draft_knowledge_entry, validate_approved_knowledge_entry
from enterprise_knowledge_registry import load_governed_enterprise_knowledge_registry, retrieve_governed_enterprise_knowledge

def check(name,cond):
    if not cond: print("FAIL",name); raise AssertionError(name)
    print("PASS",name)

print("\n=== R10.16E GOVERNED KNOWLEDGE APPROVAL & PROMOTION ===")
raw={"entry_id":"demo.freight.policy.v3","type":"policy","status":"DRAFT","title":"Política de flete","content":"El costo de flete requiere una regla empresarial validada.","scope":{"company_id":"DEMO"},"effective_from":"2026-01-01","provenance":{"source":"document","source_kind":"document","document_id":"POL-003"}}
ing=ingest_knowledge_candidates(candidates=[raw]); draft=ing["accepted_entries"][0]; fp=draft["content_fingerprint_sha256"]
check("version",APPROVAL_WORKFLOW_VERSION=="r10.16e")
check("draft_from_ingestion",draft["status"]=="DRAFT")
approved=promote_draft_knowledge_entry(entry=draft,approved_by="ADMIN",approved_at="2026-09-02T14:30:00-07:00",expected_content_fingerprint_sha256=fp)
check("promotion_approved",approved["status"]=="APPROVED")
check("entry_promoted",approved["entry"]["status"]=="APPROVED")
check("approval_record_present",approved["entry"]["approval"]["schema_version"]=="r10.16e")
check("approval_fingerprint_present",len(approved["entry"]["approval"]["approval_fingerprint_sha256"])==64)
check("approval_metadata_in_provenance",approved["entry"]["provenance"]["approved_by"]=="ADMIN")
check("approval_validation",validate_approved_knowledge_entry(approved["entry"])==[])
check("formula_authority_false",approved["governance"]["formula_authority"] is False)
check("computational_authority_false",approved["governance"]["computational_authority"] is False)
stale=promote_draft_knowledge_entry(entry=draft,approved_by="ADMIN",approved_at="2026-09-02T14:30:00-07:00",expected_content_fingerprint_sha256="0"*64)
check("stale_fingerprint_blocked",stale["status"]=="BLOCKED" and "stale_content_fingerprint" in stale["errors"])
tampered=dict(draft); tampered["content"]=draft["content"]+" ALTERADO"
tamper=promote_draft_knowledge_entry(entry=tampered,approved_by="ADMIN",approved_at="2026-09-02T14:30:00-07:00",expected_content_fingerprint_sha256=fp)
check("tamper_blocked",tamper["status"]=="BLOCKED" and "content_tampering_detected" in tamper["errors"])
naive=promote_draft_knowledge_entry(entry=draft,approved_by="ADMIN",approved_at="2026-09-02T14:30:00",expected_content_fingerprint_sha256=fp)
check("timezone_required",naive["status"]=="BLOCKED")
bad_actor=promote_draft_knowledge_entry(entry=draft,approved_by=" * ",approved_at="2026-09-02T14:30:00-07:00",expected_content_fingerprint_sha256=fp)
check("wildcard_actor_blocked",bad_actor["status"]=="BLOCKED")
rejected=reject_draft_knowledge_entry(entry=draft,rejected_by="REVIEWER",rejected_at="2026-09-02T14:31:00-07:00",expected_content_fingerprint_sha256=fp,reason="Documento pendiente de validación legal")
check("rejection_recorded",rejected["status"]=="REJECTED")
check("rejection_does_not_promote",rejected["entry"]["status"]=="DRAFT")
check("rejection_audit_fingerprint",len(rejected["audit_event"]["event_fingerprint_sha256"])==64)
second=promote_draft_knowledge_entry(entry=approved["entry"],approved_by="ADMIN2",approved_at="2026-09-02T14:32:00-07:00",expected_content_fingerprint_sha256=fp)
check("approved_cannot_be_reapproved",second["status"]=="BLOCKED")
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/"knowledge.json"
    p.write_text(json.dumps({"schema_version":"r10.16a","registry_id":"demo","knowledge_version":"1","entries":[approved["entry"]]}),encoding="utf-8")
    registry=load_governed_enterprise_knowledge_registry(str(p))
    check("promoted_registry_loaded",registry["status"]=="LOADED")
    retrieved=retrieve_governed_enterprise_knowledge(registry=registry,context={"company_id":"DEMO"},as_of="2026-09-02")
    check("approved_retrievable",retrieved["status"]=="RETRIEVED" and retrieved["entry_count"]==1)
    forged=dict(approved["entry"]); forged.pop("approval",None)
    q=Path(td)/"forged.json"
    q.write_text(json.dumps({"schema_version":"r10.16a","registry_id":"bad","knowledge_version":"1","entries":[forged]}),encoding="utf-8")
    bad_reg=load_governed_enterprise_knowledge_registry(str(q))
    check("forged_approved_rejected",bad_reg["status"]=="INVALID")
print("\nPASS R10.16E GOVERNED KNOWLEDGE APPROVAL & PROMOTION")
