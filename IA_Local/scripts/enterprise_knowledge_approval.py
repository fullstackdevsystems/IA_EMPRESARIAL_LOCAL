from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

APPROVAL_WORKFLOW_VERSION = "r10.16e"
_ALLOWED_DECISIONS = {"APPROVE", "REJECT"}
_APPROVED = "APPROVED"
_DRAFT = "DRAFT"

def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()

def _scalar_identity(value: Any, field: str) -> Tuple[Optional[str], List[str]]:
    if isinstance(value, bool) or isinstance(value, (list, dict, set, tuple)) or value is None:
        return None, [f"invalid_{field}"]
    text = str(value).strip()
    if not text or text == "*":
        return None, [f"invalid_{field}"]
    return text, []

def _aware_iso_datetime(value: Any, field: str) -> Tuple[Optional[str], List[str]]:
    text, errors = _scalar_identity(value, field)
    if errors:
        return None, errors
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None, [f"invalid_{field}"]
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None, [f"{field}_timezone_required"]
    return text, []

def knowledge_content_fingerprint(entry: Dict[str, Any]) -> str:
    prov = dict(entry.get("provenance") or {})
    prov.pop("approved_by", None)
    prov.pop("approved_at", None)
    payload = {
        "entry_id": str(entry.get("entry_id") or "").strip(),
        "type": str(entry.get("type") or "").strip(),
        "title": str(entry.get("title") or "").strip(),
        "content": str(entry.get("content") or "").strip(),
        "scope": dict(entry.get("scope") or {}),
        "effective_from": entry.get("effective_from"),
        "effective_to": entry.get("effective_to"),
        "provenance": prov,
    }
    return _sha256(payload)

def _approval_payload(*, entry_id: str, content_fingerprint_sha256: str, approved_by: str, approved_at: str) -> Dict[str, Any]:
    return {
        "schema_version": APPROVAL_WORKFLOW_VERSION,
        "decision": _APPROVED,
        "entry_id": entry_id,
        "content_fingerprint_sha256": content_fingerprint_sha256,
        "approved_by": approved_by,
        "approved_at": approved_at,
    }

def _approval_fingerprint(payload: Dict[str, Any]) -> str:
    return _sha256(payload)

def validate_approved_knowledge_entry(entry: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if str(entry.get("status") or "") != _APPROVED:
        return ["status_not_approved"]
    entry_id, eid_errors = _scalar_identity(entry.get("entry_id"), "entry_id")
    errors.extend(eid_errors)
    content_fp = str(entry.get("content_fingerprint_sha256") or "").strip().lower()
    if len(content_fp) != 64 or any(c not in "0123456789abcdef" for c in content_fp):
        errors.append("invalid_content_fingerprint")
    elif content_fp != knowledge_content_fingerprint(entry):
        errors.append("content_fingerprint_mismatch")
    approval = entry.get("approval")
    if not isinstance(approval, dict):
        errors.append("missing_approval_record")
        return errors
    if str(approval.get("schema_version") or "") != APPROVAL_WORKFLOW_VERSION:
        errors.append("invalid_approval_schema")
    if str(approval.get("decision") or "") != _APPROVED:
        errors.append("invalid_approval_decision")
    approved_by, approver_errors = _scalar_identity(approval.get("approved_by"), "approved_by")
    errors.extend(approver_errors)
    approved_at, time_errors = _aware_iso_datetime(approval.get("approved_at"), "approved_at")
    errors.extend(time_errors)
    if str(approval.get("entry_id") or "") != str(entry_id or ""):
        errors.append("approval_entry_id_mismatch")
    if str(approval.get("content_fingerprint_sha256") or "").lower() != content_fp:
        errors.append("approval_content_fingerprint_mismatch")
    approval_fp = str(approval.get("approval_fingerprint_sha256") or "").strip().lower()
    if len(approval_fp) != 64 or any(c not in "0123456789abcdef" for c in approval_fp):
        errors.append("invalid_approval_fingerprint")
    elif approved_by and approved_at and entry_id and len(content_fp) == 64:
        expected = _approval_fingerprint(_approval_payload(
            entry_id=entry_id,
            content_fingerprint_sha256=content_fp,
            approved_by=approved_by,
            approved_at=approved_at,
        ))
        if approval_fp != expected:
            errors.append("approval_fingerprint_mismatch")
    prov = entry.get("provenance")
    if not isinstance(prov, dict):
        errors.append("invalid_provenance")
    else:
        if str(prov.get("approved_by") or "") != str(approved_by or ""):
            errors.append("provenance_approved_by_mismatch")
        if str(prov.get("approved_at") or "") != str(approved_at or ""):
            errors.append("provenance_approved_at_mismatch")
    return errors

def _governance() -> Dict[str, Any]:
    return {
        "explicit_human_decision_required": True,
        "auto_approval": False,
        "draft_only_promotion": True,
        "optimistic_fingerprint_lock": True,
        "tamper_detection": True,
        "timezone_aware_approval_time_required": True,
        "rejection_does_not_promote_entry": True,
        "retrieval_requires_approved_registry_entry": True,
        "formula_authority": False,
        "computational_authority": False,
        "source_data_precedence": True,
    }

def decide_draft_knowledge_entry(*, entry: Dict[str, Any], decision: str, actor: Any, decided_at: Any, expected_content_fingerprint_sha256: Any, reason: Optional[str] = None) -> Dict[str, Any]:
    original = deepcopy(dict(entry or {}))
    errors: List[str] = []
    resolved_decision = str(decision or "").strip().upper()
    if resolved_decision not in _ALLOWED_DECISIONS:
        errors.append("unsupported_decision")
    if str(original.get("status") or "") != _DRAFT:
        errors.append("only_draft_entries_can_be_decided")
    actor_text, actor_errors = _scalar_identity(actor, "actor")
    errors.extend(actor_errors)
    decided_at_text, time_errors = _aware_iso_datetime(decided_at, "decided_at")
    errors.extend(time_errors)
    expected_fp = str(expected_content_fingerprint_sha256 or "").strip().lower()
    actual_stored_fp = str(original.get("content_fingerprint_sha256") or "").strip().lower()
    if not expected_fp:
        errors.append("expected_content_fingerprint_required")
    elif expected_fp != actual_stored_fp:
        errors.append("stale_content_fingerprint")
    recomputed_fp = knowledge_content_fingerprint(original)
    if not actual_stored_fp:
        errors.append("missing_content_fingerprint")
    elif actual_stored_fp != recomputed_fp:
        errors.append("content_tampering_detected")
    if resolved_decision == "REJECT" and not str(reason or "").strip():
        errors.append("rejection_reason_required")
    if errors:
        return {
            "schema_version": APPROVAL_WORKFLOW_VERSION,
            "status": "BLOCKED",
            "decision": resolved_decision or None,
            "errors": errors,
            "entry": original,
            "audit_event": None,
            "governance": _governance(),
        }
    if resolved_decision == "REJECT":
        event_payload = {
            "schema_version": APPROVAL_WORKFLOW_VERSION,
            "decision": "REJECTED",
            "entry_id": str(original.get("entry_id") or ""),
            "content_fingerprint_sha256": actual_stored_fp,
            "decided_by": actor_text,
            "decided_at": decided_at_text,
            "reason": str(reason or "").strip(),
        }
        event_payload["event_fingerprint_sha256"] = _sha256(event_payload)
        return {
            "schema_version": APPROVAL_WORKFLOW_VERSION,
            "status": "REJECTED",
            "decision": "REJECT",
            "errors": [],
            "entry": original,
            "audit_event": event_payload,
            "governance": _governance(),
        }
    promoted = deepcopy(original)
    promoted["status"] = _APPROVED
    prov = dict(promoted.get("provenance") or {})
    prov["approved_by"] = actor_text
    prov["approved_at"] = decided_at_text
    promoted["provenance"] = prov
    payload = _approval_payload(
        entry_id=str(promoted.get("entry_id") or ""),
        content_fingerprint_sha256=actual_stored_fp,
        approved_by=actor_text,
        approved_at=decided_at_text,
    )
    approval_fp = _approval_fingerprint(payload)
    promoted["approval"] = {**payload, "approval_fingerprint_sha256": approval_fp}
    validation_errors = validate_approved_knowledge_entry(promoted)
    if validation_errors:
        return {
            "schema_version": APPROVAL_WORKFLOW_VERSION,
            "status": "BLOCKED",
            "decision": "APPROVE",
            "errors": validation_errors,
            "entry": original,
            "audit_event": None,
            "governance": _governance(),
        }
    audit_event = {
        "schema_version": APPROVAL_WORKFLOW_VERSION,
        "decision": "APPROVED",
        "entry_id": str(promoted.get("entry_id") or ""),
        "content_fingerprint_sha256": actual_stored_fp,
        "approved_by": actor_text,
        "approved_at": decided_at_text,
        "approval_fingerprint_sha256": approval_fp,
    }
    audit_event["event_fingerprint_sha256"] = _sha256(audit_event)
    return {
        "schema_version": APPROVAL_WORKFLOW_VERSION,
        "status": "APPROVED",
        "decision": "APPROVE",
        "errors": [],
        "entry": promoted,
        "audit_event": audit_event,
        "governance": _governance(),
    }

def promote_draft_knowledge_entry(*, entry: Dict[str, Any], approved_by: Any, approved_at: Any, expected_content_fingerprint_sha256: Any) -> Dict[str, Any]:
    return decide_draft_knowledge_entry(
        entry=entry,
        decision="APPROVE",
        actor=approved_by,
        decided_at=approved_at,
        expected_content_fingerprint_sha256=expected_content_fingerprint_sha256,
    )

def reject_draft_knowledge_entry(*, entry: Dict[str, Any], rejected_by: Any, rejected_at: Any, expected_content_fingerprint_sha256: Any, reason: str) -> Dict[str, Any]:
    return decide_draft_knowledge_entry(
        entry=entry,
        decision="REJECT",
        actor=rejected_by,
        decided_at=rejected_at,
        expected_content_fingerprint_sha256=expected_content_fingerprint_sha256,
        reason=reason,
    )
