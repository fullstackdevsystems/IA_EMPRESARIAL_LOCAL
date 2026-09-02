from __future__ import annotations
import hashlib, json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

KNOWLEDGE_REGISTRY_VERSION = "r10.16a"
_ALLOWED_TYPES = {"fact","definition","decision","policy","document_reference"}
_ALLOWED_SCOPE_KEYS = {"tenant_id","company_id","business_unit_id","branch_id"}
_ALLOWED_STATUSES = {"APPROVED","DRAFT","REVOKED"}
_FORBIDDEN_KEYS = {"eval","python","code","expression"}

def _default_registry_path():
    return Path(__file__).resolve().parents[1] / "config" / "enterprise_knowledge.json"

def _fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def _parse_date(v):
    if v in (None,""): return None
    try: return date.fromisoformat(str(v))
    except Exception: return None

def _base(p):
    return {
        "schema_version": KNOWLEDGE_REGISTRY_VERSION,
        "status": "EMPTY",
        "path": str(p),
        "registry_id": None,
        "knowledge_version": None,
        "entry_count": 0,
        "approved_entry_count": 0,
        "entries": [],
        "fingerprint_sha256": None,
        "errors": [],
        "governance": {
            "fail_closed": True,
            "approved_entries_only_are_retrievable": True,
            "unknown_knowledge_is_never_inferred": True,
            "source_provenance_required": True,
            "scope_is_explicit": True,
            "effective_date_guard": True,
            "revoked_entries_are_not_retrievable": True,
            "knowledge_does_not_override_source_data": True,
            "knowledge_does_not_create_metrics_by_itself": True
        }
    }

def _validate_entry(entry, index):
    errors=[]; eid=str(entry.get("entry_id") or "").strip()
    if not eid: return [f"entry_{index}:missing_entry_id"]
    bad=sorted(k for k in _FORBIDDEN_KEYS if k in entry)
    if bad: errors.append(f"entry_{index}:forbidden_keys:{eid}:{','.join(bad)}")
    kind=str(entry.get("type") or "")
    if kind not in _ALLOWED_TYPES: errors.append(f"entry_{index}:unsupported_type:{eid}:{kind}")
    status=str(entry.get("status") or "")
    if status not in _ALLOWED_STATUSES: errors.append(f"entry_{index}:unsupported_status:{eid}:{status}")
    if not str(entry.get("title") or "").strip(): errors.append(f"entry_{index}:missing_title:{eid}")
    content=entry.get("content")
    if content in (None,""): errors.append(f"entry_{index}:missing_content:{eid}")
    prov=entry.get("provenance")
    if not isinstance(prov,dict) or not str(prov.get("source") or "").strip():
        errors.append(f"entry_{index}:missing_provenance_source:{eid}")
    scope=entry.get("scope") or {}
    if not isinstance(scope,dict):
        errors.append(f"entry_{index}:scope_must_be_object:{eid}")
    else:
        unknown=sorted(set(scope)-_ALLOWED_SCOPE_KEYS)
        if unknown: errors.append(f"entry_{index}:unsupported_scope_keys:{eid}:{','.join(unknown)}")
        wildcard_keys=sorted(k for k,v in scope.items() if v in (None,"","*"))
        if wildcard_keys:
            errors.append(f"entry_{index}:wildcard_scope_values_forbidden:{eid}:{','.join(wildcard_keys)}")
    ef,et=entry.get("effective_from"),entry.get("effective_to")
    pef,pet=_parse_date(ef),_parse_date(et)
    if ef not in (None,"") and pef is None: errors.append(f"entry_{index}:invalid_effective_from:{eid}")
    if et not in (None,"") and pet is None: errors.append(f"entry_{index}:invalid_effective_to:{eid}")
    if pef and pet and pef>pet: errors.append(f"entry_{index}:invalid_effective_range:{eid}")
    return errors

def load_governed_enterprise_knowledge_registry(path: Optional[str]=None)->Dict[str,Any]:
    p=Path(path) if path else _default_registry_path(); base=_base(p)
    if not p.exists(): return base
    try: raw=p.read_bytes()
    except Exception as exc:
        o=dict(base); o["status"]="ERROR"; o["errors"]=[f"read_error:{type(exc).__name__}"]; return o
    digest=_fingerprint(raw)
    try: data=json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        o=dict(base); o["status"]="INVALID"; o["fingerprint_sha256"]=digest; o["errors"]=[f"json_error:{type(exc).__name__}"]; return o
    if not isinstance(data,dict):
        o=dict(base); o["status"]="INVALID"; o["fingerprint_sha256"]=digest; o["errors"]=["registry_root_must_be_object"]; return o
    if str(data.get("schema_version") or "")!=KNOWLEDGE_REGISTRY_VERSION:
        o=dict(base); o["status"]="INVALID"; o["fingerprint_sha256"]=digest; o["errors"]=["unsupported_registry_schema"]; return o
    entries=data.get("entries")
    if not isinstance(entries,list):
        o=dict(base); o["status"]="INVALID"; o["fingerprint_sha256"]=digest; o["errors"]=["entries_must_be_array"]; return o
    seen=set(); clean=[]; errors=[]
    for i,raw_entry in enumerate(entries):
        if not isinstance(raw_entry,dict): errors.append(f"entry_{i}:entry_must_be_object"); continue
        e=dict(raw_entry); eid=str(e.get("entry_id") or "").strip()
        if eid and eid in seen: errors.append(f"entry_{i}:duplicate_entry_id:{eid}"); continue
        if eid: seen.add(eid)
        ee=_validate_entry(e,i)
        if ee: errors.extend(ee); continue
        clean.append(e)
    if errors:
        o=dict(base); o.update({"status":"INVALID","registry_id":data.get("registry_id"),"knowledge_version":data.get("knowledge_version"),"fingerprint_sha256":digest,"errors":errors}); return o
    approved=sum(1 for e in clean if str(e.get("status") or "")=="APPROVED")
    o=dict(base); o.update({"status":"LOADED" if clean else "EMPTY","registry_id":data.get("registry_id"),"knowledge_version":data.get("knowledge_version"),"entry_count":len(clean),"approved_entry_count":approved,"entries":clean,"fingerprint_sha256":digest}); return o

def retrieve_governed_enterprise_knowledge(*,registry,context=None,as_of=None,knowledge_types=None):
    if str(registry.get("status") or "") in {"INVALID","ERROR"}:
        return {"schema_version":KNOWLEDGE_REGISTRY_VERSION,"status":"BLOCKED","entries":[],"reason":"invalid_registry"}
    ctx=dict(context or {}); resolved=_parse_date(as_of) if as_of else date.today()
    if as_of and resolved is None:
        return {"schema_version":KNOWLEDGE_REGISTRY_VERSION,"status":"BLOCKED","entries":[],"reason":"invalid_as_of"}
    allowed=set(knowledge_types or _ALLOWED_TYPES); selected=[]
    for e in list(registry.get("entries") or []):
        if str(e.get("status") or "")!="APPROVED": continue
        if str(e.get("type") or "") not in allowed: continue
        ok=True
        for k,v in dict(e.get("scope") or {}).items():
            if v in (None,"","*"):
                ok=False
                break
            if str(ctx.get(k) or "")!=str(v): ok=False; break
        if not ok: continue
        ef,et=_parse_date(e.get("effective_from")),_parse_date(e.get("effective_to"))
        if ef and resolved<ef: continue
        if et and resolved>et: continue
        selected.append(dict(e))
    return {"schema_version":KNOWLEDGE_REGISTRY_VERSION,"status":"RETRIEVED" if selected else "EMPTY","entry_count":len(selected),"entries":selected,"reason":None,"governance":{"approved_only":True,"scope_guard":True,"effective_date_guard":True,"source_data_precedence":True}}
