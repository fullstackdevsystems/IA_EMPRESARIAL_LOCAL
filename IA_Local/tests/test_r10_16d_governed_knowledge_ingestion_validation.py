from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "scripts"
if str(S) not in sys.path:
    sys.path.insert(0, str(S))
from enterprise_knowledge_ingestion import KNOWLEDGE_INGESTION_VERSION, validate_knowledge_candidate, ingest_knowledge_candidates

def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)

print("\n=== R10.16D GOVERNED KNOWLEDGE INGESTION & VALIDATION ===")
base = {
    "entry_id": "demo.freight.policy.v2",
    "type": "policy",
    "status": "APPROVED",
    "title": "Política de flete",
    "content": "El costo total de flete requiere una regla empresarial validada.",
    "scope": {"company_id": "DEMO"},
    "effective_from": "2026-01-01",
    "provenance": {
        "source": "manual_validation",
        "source_kind": "manual_validation",
        "document_id": "POL-002",
        "approved_by": "ADMIN",
        "approved_at": "2026-09-02T14:00:00-07:00",
    },
}
v = validate_knowledge_candidate(base)
check("version", KNOWLEDGE_INGESTION_VERSION == "r10.16d")
check("valid_candidate", v["status"] == "VALID")
check("forced_draft", v["candidate"]["status"] == "DRAFT")
check("fingerprint_present", len(v["candidate"]["content_fingerprint_sha256"]) == 64)
check("provenance_preserved", v["candidate"]["provenance"]["document_id"] == "POL-002")
check("no_auto_approval", v["governance"]["auto_approval"] is False)

bad_scope = dict(base); bad_scope["entry_id"]="bad.scope"; bad_scope["scope"]={"company_id":"  *  "}
check("whitespace_wildcard_rejected", validate_knowledge_candidate(bad_scope)["status"]=="INVALID")
bad_bool = dict(base); bad_bool["entry_id"]="bad.bool"; bad_bool["scope"]={"company_id":True}
check("bool_scope_rejected", validate_knowledge_candidate(bad_bool)["status"]=="INVALID")
bad_container = dict(base); bad_container["entry_id"]="bad.container"; bad_container["scope"]={"company_id":["DEMO"]}
check("container_scope_rejected", validate_knowledge_candidate(bad_container)["status"]=="INVALID")
global_entry = dict(base); global_entry["entry_id"]="global.def"; global_entry["scope"]={}
check("global_empty_scope_allowed", validate_knowledge_candidate(global_entry)["status"]=="VALID")
missing_approval = dict(base); missing_approval["entry_id"]="missing.approval"; missing_approval["provenance"]={"source":"manual_validation","source_kind":"manual_validation"}
mv=validate_knowledge_candidate(missing_approval)
check("approval_metadata_required", "approval_requires_approved_by" in mv["errors"] and "approval_requires_approved_at" in mv["errors"])
draft_candidate = dict(base); draft_candidate["entry_id"]="demo.draft.v1"; draft_candidate["status"]="DRAFT"; draft_candidate["provenance"]={"source":"document","source_kind":"document","document_id":"DOC-001"}
iv=ingest_knowledge_candidates(candidates=[draft_candidate])
check("ingest_accepted", iv["status"]=="ACCEPTED")
check("accepted_is_draft", iv["accepted_entries"][0]["status"]=="DRAFT")
check("retrieval_requires_approval", iv["governance"]["retrieval_requires_registry_approval"] is True)
dup=ingest_knowledge_candidates(candidates=[draft_candidate,draft_candidate])
check("duplicate_rejected", dup["accepted_count"]==1 and dup["rejected_count"]==1)
code_candidate=dict(draft_candidate); code_candidate["entry_id"]="bad.code"; code_candidate["code"]="print('x')"
check("executable_key_rejected", validate_knowledge_candidate(code_candidate)["status"]=="INVALID")
print("\nPASS R10.16D GOVERNED KNOWLEDGE INGESTION & VALIDATION")
