from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

KNOWLEDGE_CONTEXT_INJECTION_VERSION = "r10.16c"

_ALLOWED_TYPES = {
    "fact",
    "definition",
    "decision",
    "policy",
    "document_reference",
}


def _safe_text(value: Any, limit: int = 500) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        text = text[:limit]
    return text


def _fingerprint(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_governed_knowledge_interpretation(
    *,
    intent: Dict[str, Any],
    knowledge_retrieval: Dict[str, Any],
) -> Dict[str, Any]:
    base = {
        "schema_version": KNOWLEDGE_CONTEXT_INJECTION_VERSION,
        "status": "EMPTY",
        "matched_entry_count": 0,
        "definitions": [],
        "facts": [],
        "policies": [],
        "decisions": [],
        "document_references": [],
        "provenance": [],
        "fingerprint_sha256": None,
        "governance": {
            "approved_retrieval_only": True,
            "metadata_enrichment_only": True,
            "does_not_add_requested_metrics": True,
            "does_not_add_requested_dimensions": True,
            "does_not_add_requested_analyses": True,
            "does_not_add_pages": True,
            "does_not_authorize_formulas": True,
            "does_not_override_source_data": True,
            "does_not_override_capability_resolution": True,
            "does_not_override_business_rule_registry": True,
            "fail_closed": True,
        },
    }

    if str(knowledge_retrieval.get("status") or "") == "BLOCKED":
        out = dict(base)
        out["status"] = "BLOCKED"
        out["reason"] = knowledge_retrieval.get("reason") or "knowledge_retrieval_blocked"
        return out

    matches = list(knowledge_retrieval.get("matches") or [])
    if not matches:
        out = dict(base)
        out["fingerprint_sha256"] = _fingerprint([])
        return out

    buckets = {
        "definition": "definitions",
        "fact": "facts",
        "policy": "policies",
        "decision": "decisions",
        "document_reference": "document_references",
    }

    out = dict(base)
    out["status"] = "ENRICHED"
    provenance: List[Dict[str, Any]] = []
    canonical = []

    for match in matches:
        kind = str(match.get("type") or "")
        if kind not in _ALLOWED_TYPES:
            continue

        prov = dict(match.get("provenance") or {})
        item = {
            "entry_id": _safe_text(match.get("entry_id"), 200),
            "type": kind,
            "title": _safe_text(match.get("title"), 300),
            "content": _safe_text(match.get("content"), 1000),
            "scope": dict(match.get("scope") or {}),
            "effective_from": match.get("effective_from"),
            "effective_to": match.get("effective_to"),
            "relevance": dict(match.get("relevance") or {}),
            "provenance": prov,
        }

        out[buckets[kind]].append(item)
        provenance.append({
            "entry_id": item["entry_id"],
            "source": _safe_text(prov.get("source"), 300),
            "document_id": _safe_text(prov.get("document_id"), 300),
        })
        canonical.append(item)

    out["matched_entry_count"] = len(canonical)
    out["provenance"] = provenance
    out["fingerprint_sha256"] = _fingerprint(canonical)

    if not canonical:
        out["status"] = "EMPTY"

    return out


def inject_governed_knowledge_into_intent(
    *,
    intent: Dict[str, Any],
    knowledge_interpretation: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(intent or {})

    protected = {
        "metrics": list(out.get("metrics") or []),
        "dimensions": list(out.get("dimensions") or []),
        "analyses": list(out.get("analyses") or []),
        "pages": list(out.get("pages") or []),
        "requested_items": list(out.get("requested_items") or []),
    }

    out["enterprise_knowledge_interpretation"] = knowledge_interpretation

    out["knowledge_governance"] = {
        "schema_version": KNOWLEDGE_CONTEXT_INJECTION_VERSION,
        "status": knowledge_interpretation.get("status"),
        "matched_entry_count": knowledge_interpretation.get("matched_entry_count", 0),
        "fingerprint_sha256": knowledge_interpretation.get("fingerprint_sha256"),
        "computational_authority": False,
        "formula_authority": False,
        "source_data_precedence": True,
        "capability_resolution_precedence": True,
    }

    # Fail safe: assert that the protected prompt intent was not expanded.
    for key, original in protected.items():
        if list(out.get(key) or []) != original:
            raise RuntimeError(f"knowledge_injection_modified_protected_intent:{key}")

    return out
