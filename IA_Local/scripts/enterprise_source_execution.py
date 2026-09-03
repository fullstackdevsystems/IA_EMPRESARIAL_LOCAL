from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

from enterprise_file_connector import ENTERPRISE_FILE_CONNECTOR_VERSION, open_governed_file_source
from enterprise_source_registry import resolve_governed_enterprise_sources
from enterprise_sql_server_connector import ENTERPRISE_SQL_CONNECTOR_VERSION, execute_governed_sql_query

ENTERPRISE_SOURCE_EXECUTION_VERSION = "r10.17d"
_FILE_KINDS = {"excel", "csv"}
_SUPPORTED_UPLOAD_EXTENSIONS = {
    ".xlsx": "excel", ".xlsm": "excel", ".xls": "excel", ".xlsb": "excel",
    ".csv": "csv", ".txt": "csv",
}

def _governance() -> Dict[str, Any]:
    return {
        "fail_closed": True,
        "read_only": True,
        "registry_scope_guard_for_registered_sources": True,
        "registered_source_must_be_enabled": True,
        "connector_dispatch_is_explicit": True,
        "uploaded_files_use_governed_file_connector": True,
        "credential_values_exposed": False,
        "inline_secrets_exposed": False,
        "source_data_precedence": True,
        "formula_authority": False,
        "computational_authority": False,
    }

def build_source_execution_capability_audit() -> Dict[str, Any]:
    return {
        "schema_version": ENTERPRISE_SOURCE_EXECUTION_VERSION,
        "status": "AVAILABLE",
        "supported_kinds": ["csv", "excel", "sql_server"],
        "connectors": {"file": ENTERPRISE_FILE_CONNECTOR_VERSION, "sql_server": ENTERPRISE_SQL_CONNECTOR_VERSION},
        "governance": _governance(),
    }

def _blocked(reason: str, source_id: Optional[str] = None, kind: Optional[str] = None) -> Dict[str, Any]:
    return {
        "schema_version": ENTERPRISE_SOURCE_EXECUTION_VERSION,
        "status": "BLOCKED",
        "reason": reason,
        "source_id": source_id,
        "kind": kind,
        "dataframe": None,
        "provenance": None,
        "governance": _governance(),
    }

def _public_provenance(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    blocked_keys = {"credential_ref","credential","password","pwd","secret","token","api_key","connection_string","sql","query"}
    return {str(k): v for k, v in value.items() if str(k).strip().lower() not in blocked_keys}

def public_source_execution_metadata(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": result.get("schema_version"),
        "status": result.get("status"),
        "reason": result.get("reason"),
        "source_id": result.get("source_id"),
        "kind": result.get("kind"),
        "source_origin": result.get("source_origin"),
        "connector_schema_version": result.get("connector_schema_version"),
        "provenance": _public_provenance(result.get("provenance")),
        "governance": dict(result.get("governance") or {}),
    }

def execute_uploaded_file_source(*, path: str | Path, workspace_root: str | Path) -> Dict[str, Any]:
    root = Path(workspace_root).resolve()
    candidate = Path(path).resolve()
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return _blocked("uploaded_file_outside_workspace")
    ext = candidate.suffix.lower()
    kind = _SUPPORTED_UPLOAD_EXTENSIONS.get(ext)
    if not kind:
        return _blocked("unsupported_uploaded_file_extension")
    digest = hashlib.sha256(relative.as_posix().encode("utf-8")).hexdigest()[:16]
    source_id = f"request.upload.{digest}"
    locator: Dict[str, Any] = {"relative_path": relative.as_posix()}
    if kind == "excel":
        locator["sheet"] = 0
    transient_source = {
        "source_id": source_id,
        "kind": kind,
        "status": "ENABLED",
        "name": candidate.name,
        "scope": {},
        "locator": locator,
        "access": {"mode": "read_only"},
    }
    opened = open_governed_file_source(source=transient_source, workspace_root=root)
    if opened.get("status") != "OPENED":
        return _blocked(str(opened.get("reason") or "file_connector_blocked"), source_id, kind)
    return {
        "schema_version": ENTERPRISE_SOURCE_EXECUTION_VERSION,
        "status": "OPENED",
        "reason": None,
        "source_id": source_id,
        "kind": kind,
        "source_origin": "request_upload",
        "connector_schema_version": opened.get("schema_version"),
        "dataframe": opened.get("dataframe"),
        "provenance": _public_provenance(opened.get("provenance")),
        "governance": _governance(),
    }

def execute_registered_source(*, registry: Dict[str, Any], source_id: str, context: Optional[Dict[str, Any]] = None, workspace_root: str | Path, query_id: Optional[str] = None) -> Dict[str, Any]:
    sid = str(source_id or "").strip()
    if not sid:
        return _blocked("source_id_required")
    resolved = resolve_governed_enterprise_sources(registry=registry, context=dict(context or {}))
    if resolved.get("status") == "BLOCKED":
        return _blocked("registry_resolution_blocked", sid)
    authorized_ids = {str(item.get("source_id") or "") for item in list(resolved.get("sources") or []) if isinstance(item, dict)}
    if sid not in authorized_ids:
        return _blocked("source_not_resolved_for_context", sid)
    matches = [source for source in list(registry.get("sources") or []) if isinstance(source, dict) and str(source.get("source_id") or "") == sid]
    if len(matches) != 1:
        return _blocked("registered_source_not_unique", sid)
    source = matches[0]
    kind = str(source.get("kind") or "")
    if kind in _FILE_KINDS:
        opened = open_governed_file_source(source=source, workspace_root=workspace_root)
    elif kind == "sql_server":
        if not str(query_id or "").strip():
            return _blocked("query_id_required", sid, kind)
        opened = execute_governed_sql_query(source=source, query_id=str(query_id))
    else:
        return _blocked("unsupported_execution_kind", sid, kind)
    if opened.get("status") != "OPENED":
        return _blocked(str(opened.get("reason") or "connector_blocked"), sid, kind)
    return {
        "schema_version": ENTERPRISE_SOURCE_EXECUTION_VERSION,
        "status": "OPENED",
        "reason": None,
        "source_id": sid,
        "kind": kind,
        "source_origin": "enterprise_registry",
        "connector_schema_version": opened.get("schema_version"),
        "dataframe": opened.get("dataframe"),
        "provenance": _public_provenance(opened.get("provenance")),
        "governance": _governance(),
    }
