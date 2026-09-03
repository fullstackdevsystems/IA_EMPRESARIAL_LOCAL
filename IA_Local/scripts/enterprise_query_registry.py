from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from enterprise_sql_server_connector import validate_read_only_sql

ENTERPRISE_QUERY_REGISTRY_VERSION = "r10.17e"
_ALLOWED_STATUSES = {"ENABLED", "DISABLED"}


def _default_registry_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "enterprise_queries.json"


def _fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _base(path: Path) -> Dict[str, Any]:
    return {
        "schema_version": ENTERPRISE_QUERY_REGISTRY_VERSION,
        "status": "EMPTY",
        "path": str(path),
        "registry_id": None,
        "queries_version": None,
        "query_count": 0,
        "enabled_query_count": 0,
        "queries": [],
        "fingerprint_sha256": None,
        "errors": [],
        "governance": {
            "fail_closed": True,
            "approved_query_only": True,
            "source_binding_required": True,
            "approval_metadata_required": True,
            "query_fingerprint_required": True,
            "strict_integer_limits": True,
            "sql_comments_forbidden": True,
            "read_only_sql_required": True,
            "inline_credentials_forbidden": True,
            "query_registry_does_not_execute_queries": True,
            "formula_authority": False,
            "computational_authority": False,
        },
    }


def _validate_query(query: Dict[str, Any], index: int) -> List[str]:
    errors: List[str] = []
    query_id = str(query.get("query_id") or "").strip()
    source_id = str(query.get("source_id") or "").strip()
    status = str(query.get("status") or "").strip().upper()

    if not query_id:
        return [f"query_{index}:missing_query_id"]
    if not source_id:
        errors.append(f"query_{index}:missing_source_id:{query_id}")
    if status not in _ALLOWED_STATUSES:
        errors.append(f"query_{index}:unsupported_status:{query_id}:{status}")

    approved_by = str(query.get("approved_by") or "").strip()
    approved_at = str(query.get("approved_at") or "").strip()
    if not approved_by:
        errors.append(f"query_{index}:missing_approved_by:{query_id}")
    if not approved_at:
        errors.append(f"query_{index}:missing_approved_at:{query_id}")

    validation = validate_read_only_sql(str(query.get("sql") or ""))
    if not validation.get("valid"):
        errors.append(f"query_{index}:invalid_sql:{query_id}:{validation.get('reason')}")

    row_limit = query.get("row_limit")
    timeout_seconds = query.get("timeout_seconds")
    if isinstance(row_limit, bool) or not isinstance(row_limit, int) or not (1 <= row_limit <= 100000):
        errors.append(f"query_{index}:invalid_row_limit:{query_id}")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not (1 <= timeout_seconds <= 300):
        errors.append(f"query_{index}:invalid_timeout:{query_id}")

    forbidden_keys = {
        "credential_ref", "credential", "password", "pwd", "secret", "token",
        "api_key", "connection_string",
    }
    present = sorted(k for k in query if str(k).strip().lower() in forbidden_keys)
    if present:
        errors.append(f"query_{index}:inline_credentials_forbidden:{query_id}:{','.join(present)}")

    return errors


def load_governed_enterprise_query_registry(path: Optional[str] = None) -> Dict[str, Any]:
    p = Path(path) if path else _default_registry_path()
    base = _base(p)
    if not p.exists():
        return base
    try:
        raw = p.read_bytes()
    except Exception as exc:
        out = dict(base)
        out["status"] = "ERROR"
        out["errors"] = [f"read_error:{type(exc).__name__}"]
        return out

    digest = _fingerprint(raw)
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        out = dict(base)
        out["status"] = "INVALID"
        out["fingerprint_sha256"] = digest
        out["errors"] = [f"json_error:{type(exc).__name__}"]
        return out

    if not isinstance(data, dict):
        out = dict(base)
        out["status"] = "INVALID"
        out["fingerprint_sha256"] = digest
        out["errors"] = ["registry_root_must_be_object"]
        return out
    if str(data.get("schema_version") or "") != ENTERPRISE_QUERY_REGISTRY_VERSION:
        out = dict(base)
        out["status"] = "INVALID"
        out["fingerprint_sha256"] = digest
        out["errors"] = ["unsupported_registry_schema"]
        return out

    queries = data.get("queries")
    if not isinstance(queries, list):
        out = dict(base)
        out["status"] = "INVALID"
        out["fingerprint_sha256"] = digest
        out["errors"] = ["queries_must_be_array"]
        return out

    seen = set()
    clean = []
    errors: List[str] = []
    for index, raw_query in enumerate(queries):
        if not isinstance(raw_query, dict):
            errors.append(f"query_{index}:query_must_be_object")
            continue
        query = dict(raw_query)
        query_id = str(query.get("query_id") or "").strip()
        if query_id and query_id in seen:
            errors.append(f"query_{index}:duplicate_query_id:{query_id}")
            continue
        if query_id:
            seen.add(query_id)

        item_errors = _validate_query(query, index)
        if item_errors:
            errors.extend(item_errors)
            continue

        validation = validate_read_only_sql(str(query.get("sql") or ""))
        clean.append({
            "query_id": query_id,
            "source_id": str(query.get("source_id") or "").strip(),
            "status": str(query.get("status") or "").strip().upper(),
            "sql": validation["normalized_sql"],
            "query_fingerprint_sha256": validation["query_fingerprint_sha256"],
            "row_limit": query["row_limit"],
            "timeout_seconds": query["timeout_seconds"],
            "approved_by": str(query.get("approved_by") or "").strip(),
            "approved_at": str(query.get("approved_at") or "").strip(),
        })

    if errors:
        out = dict(base)
        out.update({
            "status": "INVALID",
            "registry_id": data.get("registry_id"),
            "queries_version": data.get("queries_version"),
            "fingerprint_sha256": digest,
            "errors": errors,
        })
        return out

    enabled = sum(1 for q in clean if q["status"] == "ENABLED")
    out = dict(base)
    out.update({
        "status": "LOADED" if clean else "EMPTY",
        "registry_id": data.get("registry_id"),
        "queries_version": data.get("queries_version"),
        "query_count": len(clean),
        "enabled_query_count": enabled,
        "queries": clean,
        "fingerprint_sha256": digest,
    })
    return out


def resolve_governed_enterprise_query(*, registry: Dict[str, Any], source_id: str, query_id: str) -> Dict[str, Any]:
    if str(registry.get("status") or "") != "LOADED":
        return {
            "schema_version": ENTERPRISE_QUERY_REGISTRY_VERSION,
            "status": "BLOCKED",
            "reason": "invalid_query_registry",
            "query": None,
        }

    sid = str(source_id or "").strip()
    qid = str(query_id or "").strip()
    matches = [
        q for q in list(registry.get("queries") or [])
        if isinstance(q, dict)
        and str(q.get("source_id") or "") == sid
        and str(q.get("query_id") or "") == qid
        and str(q.get("status") or "").upper() == "ENABLED"
    ]
    if len(matches) != 1:
        return {
            "schema_version": ENTERPRISE_QUERY_REGISTRY_VERSION,
            "status": "BLOCKED",
            "reason": "approved_query_not_found_or_ambiguous",
            "query": None,
        }

    q = dict(matches[0])
    if _validate_query(q, 0):
        return {
            "schema_version": ENTERPRISE_QUERY_REGISTRY_VERSION,
            "status": "BLOCKED",
            "reason": "invalid_approved_query",
            "query": None,
        }
    validation = validate_read_only_sql(str(q.get("sql") or ""))
    if q.get("query_fingerprint_sha256") != validation.get("query_fingerprint_sha256"):
        return {
            "schema_version": ENTERPRISE_QUERY_REGISTRY_VERSION,
            "status": "BLOCKED",
            "reason": "query_fingerprint_mismatch",
            "query": None,
        }
    q["sql"] = validation["normalized_sql"]
    return {
        "schema_version": ENTERPRISE_QUERY_REGISTRY_VERSION,
        "status": "APPROVED",
        "reason": None,
        "query": q,
        "provenance": {
            "query_id": q["query_id"],
            "source_id": q["source_id"],
            "query_fingerprint_sha256": q["query_fingerprint_sha256"],
            "approved_by": q["approved_by"],
            "approved_at": q["approved_at"],
        },
        "governance": dict(registry.get("governance") or {}),
    }


def build_query_registry_capability_audit() -> Dict[str, Any]:
    registry = load_governed_enterprise_query_registry()
    return {
        "schema_version": ENTERPRISE_QUERY_REGISTRY_VERSION,
        "status": registry.get("status"),
        "registry_id": registry.get("registry_id"),
        "queries_version": registry.get("queries_version"),
        "query_count": registry.get("query_count"),
        "enabled_query_count": registry.get("enabled_query_count"),
        "fingerprint_sha256": registry.get("fingerprint_sha256"),
        "errors": list(registry.get("errors") or []),
        "governance": dict(registry.get("governance") or {}),
    }
