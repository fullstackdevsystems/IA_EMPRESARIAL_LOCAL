from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

KNOWLEDGE_INGESTION_VERSION = "r10.16d"

_ALLOWED_TYPES = {"fact","definition","decision","policy","document_reference"}
_ALLOWED_SCOPE_KEYS = {"tenant_id","company_id","business_unit_id","branch_id"}
_ALLOWED_SOURCE_KINDS = {"manual_validation","document","system","database","erp","policy_repository","contract_repository"}
_FORBIDDEN_KEYS = {"eval","python","code","expression"}
_DRAFT = "DRAFT"
_APPROVED = "APPROVED"

def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

def _parse_date(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None

def _normalize_scope(scope: Any) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    if scope is None:
        return {}, errors
    if not isinstance(scope, dict):
        return None, ["scope_must_be_object"]
    unknown = sorted(set(scope) - _ALLOWED_SCOPE_KEYS)
    if unknown:
        errors.append("unsupported_scope_keys:" + ",".join(unknown))
    normalized: Dict[str, Any] = {}
    for key, value in scope.items():
        if isinstance(value, bool):
            errors.append(f"invalid_scope_value:{key}:bool")
            continue
        if isinstance(value, (list, dict, set, tuple)):
            errors.append(f"invalid_scope_value:{key}:container")
            continue
        if value is None:
            errors.append(f"invalid_scope_value:{key}:none")
            continue
        text = str(value).strip()
        if not text:
            errors.append(f"invalid_scope_value:{key}:empty")
            continue
        if text == "*":
            errors.append(f"invalid_scope_value:{key}:wildcard")
            continue
        normalized[key] = text
    return normalized, errors

def _normalize_provenance(provenance: Any) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    if not isinstance(provenance, dict):
        return None, ["provenance_must_be_object"]
    source = str(provenance.get("source") or "").strip()
    if not source:
        return None, ["missing_provenance_source"]
    source_kind = str(provenance.get("source_kind") or source).strip()
    if source_kind not in _ALLOWED_SOURCE_KINDS:
        return None, [f"unsupported_source_kind:{source_kind}"]
    out = {"source": source, "source_kind": source_kind}
    for key in ("document_id","source_uri","record_id","approved_by","approved_at"):
        value = provenance.get(key)
        if value not in (None, ""):
            out[key] = str(value).strip()
    return out, []

def normalize_knowledge_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    raw = dict(candidate or {})
    scope, scope_errors = _normalize_scope(raw.get("scope"))
    provenance, provenance_errors = _normalize_provenance(raw.get("provenance"))
    entry_id = str(raw.get("entry_id") or "").strip()
    title = str(raw.get("title") or "").strip()
    kind = str(raw.get("type") or "").strip()
    content = str(raw.get("content") or "").strip()
    requested_status = str(raw.get("status") or _DRAFT).strip().upper()
    normalized = {
        "entry_id": entry_id,
        "type": kind,
        "status": _DRAFT,
        "title": title,
        "content": content,
        "scope": scope if scope is not None else {},
        "effective_from": raw.get("effective_from"),
        "effective_to": raw.get("effective_to"),
        "provenance": provenance or {},
    }
    for key in ("keywords","tags"):
        if key in raw:
            normalized[key] = raw.get(key)
    canonical_payload = {
        "entry_id": normalized["entry_id"],
        "type": normalized["type"],
        "title": normalized["title"],
        "content": normalized["content"],
        "scope": normalized["scope"],
        "effective_from": normalized["effective_from"],
        "effective_to": normalized["effective_to"],
        "provenance": normalized["provenance"],
    }
    normalized["content_fingerprint_sha256"] = _sha256_text(_canonical_json(canonical_payload))
    normalized["_normalization_errors"] = scope_errors + provenance_errors
    normalized["_requested_status"] = requested_status
    return normalized

def validate_knowledge_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_knowledge_candidate(candidate)
    errors = list(normalized.pop("_normalization_errors", []))
    requested_status = normalized.pop("_requested_status", _DRAFT)
    if not normalized["entry_id"]:
        errors.append("missing_entry_id")
    if normalized["type"] not in _ALLOWED_TYPES:
        errors.append(f"unsupported_type:{normalized['type']}")
    if not normalized["title"]:
        errors.append("missing_title")
    if not normalized["content"]:
        errors.append("missing_content")
    bad_keys = sorted(k for k in _FORBIDDEN_KEYS if k in dict(candidate or {}))
    if bad_keys:
        errors.append("forbidden_keys:" + ",".join(bad_keys))
    ef = normalized.get("effective_from")
    et = normalized.get("effective_to")
    pef = _parse_date(ef)
    pet = _parse_date(et)
    if ef not in (None,"") and pef is None:
        errors.append("invalid_effective_from")
    if et not in (None,"") and pet is None:
        errors.append("invalid_effective_to")
    if pef and pet and pef > pet:
        errors.append("invalid_effective_range")
    if requested_status == _APPROVED:
        prov = normalized.get("provenance") or {}
        if not str(prov.get("approved_by") or "").strip():
            errors.append("approval_requires_approved_by")
        if not str(prov.get("approved_at") or "").strip():
            errors.append("approval_requires_approved_at")
    return {
        "schema_version": KNOWLEDGE_INGESTION_VERSION,
        "status": "VALID" if not errors else "INVALID",
        "errors": errors,
        "candidate": normalized,
        "governance": {
            "ingested_entries_default_to_draft": True,
            "auto_approval": False,
            "approval_metadata_required_for_promotion": True,
            "scope_must_be_explicit_or_global_empty_object": True,
            "duplicate_fingerprint_guard": True,
            "duplicate_entry_id_guard": True,
            "forbidden_executable_content_keys": True,
            "knowledge_cannot_authorize_formulas": True,
            "knowledge_cannot_override_source_data": True,
        },
    }

def ingest_knowledge_candidates(*, candidates: List[Dict[str, Any]], existing_entries: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    existing_entries = list(existing_entries or [])
    existing_ids = {str(e.get("entry_id") or "").strip() for e in existing_entries}
    existing_fingerprints = {str(e.get("content_fingerprint_sha256") or "").strip() for e in existing_entries}
    existing_fingerprints.discard("")
    accepted, rejected, seen_ids, seen_fp = [], [], set(), set()
    for index, raw in enumerate(list(candidates or [])):
        result = validate_knowledge_candidate(dict(raw or {}))
        item = dict(result.get("candidate") or {})
        errors = list(result.get("errors") or [])
        eid = str(item.get("entry_id") or "")
        fp = str(item.get("content_fingerprint_sha256") or "")
        if eid in existing_ids or eid in seen_ids:
            errors.append("duplicate_entry_id")
        if fp and (fp in existing_fingerprints or fp in seen_fp):
            errors.append("duplicate_fingerprint")
        record = {"index": index, "entry_id": eid, "content_fingerprint_sha256": fp, "errors": errors}
        if errors:
            record["status"] = "REJECTED"
            rejected.append(record)
            continue
        seen_ids.add(eid)
        seen_fp.add(fp)
        accepted.append(item)
    return {
        "schema_version": KNOWLEDGE_INGESTION_VERSION,
        "status": "ACCEPTED" if accepted and not rejected else ("PARTIAL" if accepted else "REJECTED"),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "accepted_entries": accepted,
        "rejected_entries": rejected,
        "governance": {
            "accepted_entries_are_draft": all(str(e.get("status")) == _DRAFT for e in accepted),
            "auto_approval": False,
            "retrieval_requires_registry_approval": True,
            "duplicate_entry_id_guard": True,
            "duplicate_fingerprint_guard": True,
            "source_provenance_required": True,
            "formula_authority": False,
            "source_data_precedence": True,
        },
    }
