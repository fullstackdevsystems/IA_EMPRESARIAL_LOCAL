from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

ENTERPRISE_SOURCE_REGISTRY_VERSION = "r10.17a"
_ALLOWED_KINDS = {"excel", "csv", "sql_server", "erp", "api"}
_ALLOWED_SCOPE_KEYS = {"tenant_id", "company_id", "business_unit_id", "branch_id"}
_ALLOWED_STATUSES = {"ENABLED", "DISABLED"}
_FORBIDDEN_INLINE_SECRET_KEYS = {
    "password","pwd","secret","token","api_key","apikey",
    "access_token","refresh_token","connection_string","connectionstring",
}
_FILE_KINDS = {"excel", "csv"}

def _default_registry_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "enterprise_sources.json"

def _fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def _normalized_scalar(value: Any) -> Optional[str]:
    if value is None or isinstance(value, bool) or isinstance(value, (list, dict, set, tuple)):
        return None
    text = str(value).strip()
    if not text or text == "*":
        return None
    return text

def _base(path: Path) -> Dict[str, Any]:
    return {
        "schema_version": ENTERPRISE_SOURCE_REGISTRY_VERSION,
        "status": "EMPTY",
        "path": str(path),
        "registry_id": None,
        "sources_version": None,
        "source_count": 0,
        "enabled_source_count": 0,
        "sources": [],
        "fingerprint_sha256": None,
        "errors": [],
        "governance": {
            "fail_closed": True,
            "inline_secrets_forbidden": True,
            "credentials_must_use_external_reference": True,
            "source_scope_is_explicit": True,
            "disabled_sources_are_not_resolvable": True,
            "source_kind_is_explicit": True,
            "file_sources_are_read_only": True,
            "sql_sources_are_read_only": True,
            "registry_does_not_open_connections": True,
            "registry_does_not_execute_queries": True,
            "source_data_precedence": True,
        },
    }

def _validate_scope(scope: Any, source_id: str, index: int) -> List[str]:
    errors: List[str] = []
    if scope is None:
        return [f"source_{index}:scope_required_explicit_object:{source_id}"]
    if not isinstance(scope, dict):
        return [f"source_{index}:scope_must_be_object:{source_id}"]
    unknown = sorted(set(scope) - _ALLOWED_SCOPE_KEYS)
    if unknown:
        errors.append(f"source_{index}:unsupported_scope_keys:{source_id}:{','.join(unknown)}")
    invalid = [k for k, v in scope.items() if _normalized_scalar(v) is None]
    if invalid:
        errors.append(f"source_{index}:invalid_scope_values:{source_id}:{','.join(sorted(invalid))}")
    return errors

def _validate_no_inline_secrets(value: Any, path: str = "") -> List[str]:
    errors: List[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).strip().lower()
            current = f"{path}.{key}" if path else str(key)
            if normalized_key in _FORBIDDEN_INLINE_SECRET_KEYS:
                errors.append(f"inline_secret_forbidden:{current}")
            errors.extend(_validate_no_inline_secrets(child, current))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            errors.extend(_validate_no_inline_secrets(child, f"{path}[{i}]"))
    return errors

def _validate_locator(source: Dict[str, Any], source_id: str, kind: str, index: int) -> List[str]:
    locator = source.get("locator")
    if not isinstance(locator, dict):
        return [f"source_{index}:locator_must_be_object:{source_id}"]
    errors: List[str] = []
    if kind in _FILE_KINDS:
        relative_path = _normalized_scalar(locator.get("relative_path"))
        if not relative_path:
            errors.append(f"source_{index}:missing_relative_path:{source_id}")
        else:
            p = Path(relative_path)
            if p.is_absolute() or ".." in p.parts:
                errors.append(f"source_{index}:unsafe_relative_path:{source_id}")
        if any(k in locator for k in ("server", "database", "query", "sql")):
            errors.append(f"source_{index}:invalid_file_locator_fields:{source_id}")
    elif kind == "sql_server":
        if not _normalized_scalar(locator.get("server")):
            errors.append(f"source_{index}:missing_sql_server:{source_id}")
        if not _normalized_scalar(locator.get("database")):
            errors.append(f"source_{index}:missing_sql_database:{source_id}")
        if "query" in locator or "sql" in locator:
            errors.append(f"source_{index}:inline_sql_forbidden:{source_id}")
    elif kind == "erp":
        if not _normalized_scalar(locator.get("system")):
            errors.append(f"source_{index}:missing_erp_system:{source_id}")
    elif kind == "api":
        base_url = _normalized_scalar(locator.get("base_url"))
        if not base_url:
            errors.append(f"source_{index}:missing_api_base_url:{source_id}")
        elif not (
            base_url.startswith("https://")
            or base_url.startswith("http://127.0.0.1")
            or base_url.startswith("http://localhost")
        ):
            errors.append(f"source_{index}:insecure_api_base_url:{source_id}")
    return errors

def _validate_source(source: Dict[str, Any], index: int) -> List[str]:
    errors: List[str] = []
    source_id = str(source.get("source_id") or "").strip()
    if not source_id:
        return [f"source_{index}:missing_source_id"]
    kind = str(source.get("kind") or "").strip()
    if kind not in _ALLOWED_KINDS:
        errors.append(f"source_{index}:unsupported_kind:{source_id}:{kind}")
    status = str(source.get("status") or "").strip().upper()
    if status not in _ALLOWED_STATUSES:
        errors.append(f"source_{index}:unsupported_status:{source_id}:{status}")
    if not str(source.get("name") or "").strip():
        errors.append(f"source_{index}:missing_name:{source_id}")
    credential_ref = source.get("credential_ref")
    if credential_ref is not None and _normalized_scalar(credential_ref) is None:
        errors.append(f"source_{index}:invalid_credential_ref:{source_id}")
    for error in _validate_no_inline_secrets(source):
        errors.append(f"source_{index}:{source_id}:{error}")
    errors.extend(_validate_scope(source.get("scope"), source_id, index))
    if kind in _ALLOWED_KINDS:
        errors.extend(_validate_locator(source, source_id, kind, index))
    access = source.get("access") or {}
    if not isinstance(access, dict):
        errors.append(f"source_{index}:access_must_be_object:{source_id}")
    elif str(access.get("mode") or "read_only").strip() != "read_only":
        errors.append(f"source_{index}:write_access_forbidden:{source_id}")
    return errors

def load_governed_enterprise_source_registry(path: Optional[str] = None) -> Dict[str, Any]:
    p = Path(path) if path else _default_registry_path()
    base = _base(p)
    if not p.exists():
        return base
    try:
        raw = p.read_bytes()
    except Exception as exc:
        out = dict(base); out["status"] = "ERROR"; out["errors"] = [f"read_error:{type(exc).__name__}"]; return out
    digest = _fingerprint(raw)
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        out = dict(base); out["status"] = "INVALID"; out["fingerprint_sha256"] = digest; out["errors"] = [f"json_error:{type(exc).__name__}"]; return out
    if not isinstance(data, dict):
        out = dict(base); out["status"] = "INVALID"; out["fingerprint_sha256"] = digest; out["errors"] = ["registry_root_must_be_object"]; return out
    if str(data.get("schema_version") or "") != ENTERPRISE_SOURCE_REGISTRY_VERSION:
        out = dict(base); out["status"] = "INVALID"; out["fingerprint_sha256"] = digest; out["errors"] = ["unsupported_registry_schema"]; return out
    sources = data.get("sources")
    if not isinstance(sources, list):
        out = dict(base); out["status"] = "INVALID"; out["fingerprint_sha256"] = digest; out["errors"] = ["sources_must_be_array"]; return out
    seen, clean, errors = set(), [], []
    for index, raw_source in enumerate(sources):
        if not isinstance(raw_source, dict):
            errors.append(f"source_{index}:source_must_be_object"); continue
        source = dict(raw_source)
        source_id = str(source.get("source_id") or "").strip()
        if source_id and source_id in seen:
            errors.append(f"source_{index}:duplicate_source_id:{source_id}"); continue
        if source_id:
            seen.add(source_id)
        source_errors = _validate_source(source, index)
        if source_errors:
            errors.extend(source_errors); continue
        clean.append(source)
    if errors:
        out = dict(base)
        out.update({
            "status": "INVALID",
            "registry_id": data.get("registry_id"),
            "sources_version": data.get("sources_version"),
            "fingerprint_sha256": digest,
            "errors": errors,
        })
        return out
    enabled = sum(1 for s in clean if str(s.get("status") or "").upper() == "ENABLED")
    out = dict(base)
    out.update({
        "status": "LOADED" if clean else "EMPTY",
        "registry_id": data.get("registry_id"),
        "sources_version": data.get("sources_version"),
        "source_count": len(clean),
        "enabled_source_count": enabled,
        "sources": clean,
        "fingerprint_sha256": digest,
    })
    return out

def resolve_governed_enterprise_sources(*, registry: Dict[str, Any], context: Optional[Dict[str, Any]] = None, kinds: Optional[List[str]] = None) -> Dict[str, Any]:
    if str(registry.get("status") or "") in {"INVALID", "ERROR"}:
        return {
            "schema_version": ENTERPRISE_SOURCE_REGISTRY_VERSION,
            "status": "BLOCKED",
            "sources": [],
            "source_count": 0,
            "reason": "invalid_registry",
        }
    ctx = dict(context or {})
    allowed_kinds = set(kinds or _ALLOWED_KINDS)
    selected = []
    for source in list(registry.get("sources") or []):
        if str(source.get("status") or "").upper() != "ENABLED":
            continue
        if str(source.get("kind") or "") not in allowed_kinds:
            continue
        match = True
        for key, value in dict(source.get("scope") or {}).items():
            expected = _normalized_scalar(value)
            actual = _normalized_scalar(ctx.get(key))
            if expected is None or actual is None or expected != actual:
                match = False
                break
        if not match:
            continue
        selected.append({
            "source_id": source.get("source_id"),
            "kind": source.get("kind"),
            "status": source.get("status"),
            "name": source.get("name"),
            "scope": dict(source.get("scope") or {}),
            "locator": dict(source.get("locator") or {}),
            "credential_ref_present": bool(source.get("credential_ref")),
            "access": dict(source.get("access") or {"mode": "read_only"}),
        })
    return {
        "schema_version": ENTERPRISE_SOURCE_REGISTRY_VERSION,
        "status": "RESOLVED" if selected else "EMPTY",
        "source_count": len(selected),
        "sources": selected,
        "reason": None,
        "governance": {
            "enabled_only": True,
            "scope_guard": True,
            "inline_secrets_exposed": False,
            "credential_values_exposed": False,
            "read_only": True,
            "no_connection_opened": True,
            "no_query_executed": True,
        },
    }
