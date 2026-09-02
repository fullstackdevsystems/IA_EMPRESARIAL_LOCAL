from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

ENTERPRISE_MEMORY_CLOSURE_VERSION = "r10.16f"

def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def _contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        if key in value:
            return True
        return any(_contains_key(v, key) for v in value.values())
    if isinstance(value, list):
        return any(_contains_key(v, key) for v in value)
    return False

def build_enterprise_memory_closure(*, registry: Dict[str, Any], retrieval: Dict[str, Any], interpretation: Dict[str, Any]) -> Dict[str, Any]:
    registry_status = str(registry.get("status") or "")
    retrieval_status = str(retrieval.get("status") or "")
    interpretation_status = str(interpretation.get("status") or "")
    blocked = registry_status in {"INVALID", "ERROR"} or retrieval_status == "BLOCKED" or interpretation_status == "BLOCKED"
    raw_content_detected = _contains_key(interpretation, "content")
    base = {
        "schema_version": ENTERPRISE_MEMORY_CLOSURE_VERSION,
        "status": "BLOCKED" if blocked else "CONSOLIDATED",
        "lifecycle": {
            "ingest_to_draft": "r10.16d",
            "approval_promotion": "r10.16e",
            "registry": str(registry.get("schema_version") or "r10.16a"),
            "retrieval": str(retrieval.get("schema_version") or "r10.16b"),
            "context_injection": str(interpretation.get("schema_version") or "r10.16c"),
            "closure": ENTERPRISE_MEMORY_CLOSURE_VERSION,
            "consolidated": not blocked,
        },
        "runtime": {
            "registry_status": registry_status,
            "retrieval_status": retrieval_status,
            "interpretation_status": interpretation_status,
            "matched_entry_count": int(interpretation.get("matched_entry_count") or 0),
        },
        "security": {
            "raw_knowledge_content_serialized": raw_content_detected,
            "approved_only_retrieval": True,
            "draft_not_retrievable": True,
            "approval_evidence_required": True,
            "fingerprint_integrity_required": True,
            "tamper_detection_required": True,
            "scope_guard_required": True,
            "effective_date_guard_required": True,
            "prompt_instructions_inside_knowledge_are_non_executable": True,
            "knowledge_cannot_create_metrics": True,
            "knowledge_cannot_authorize_formulas": True,
            "knowledge_cannot_override_source_data": True,
            "knowledge_cannot_override_capability_resolution": True,
            "computational_authority": False,
            "formula_authority": False,
            "fail_closed": True,
        },
        "fingerprint_sha256": None,
    }
    canonical = {
        "status": base["status"],
        "lifecycle": base["lifecycle"],
        "runtime": base["runtime"],
        "security": base["security"],
        "registry_fingerprint_sha256": registry.get("fingerprint_sha256"),
        "retrieval_query_fingerprint_sha256": retrieval.get("query_fingerprint_sha256"),
        "interpretation_fingerprint_sha256": interpretation.get("fingerprint_sha256"),
    }
    base["fingerprint_sha256"] = _fingerprint(canonical)
    return base
