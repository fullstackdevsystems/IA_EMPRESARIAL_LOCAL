from __future__ import annotations

import hashlib
import os
import re
from typing import Any, Dict, Optional

import pandas as pd

ENTERPRISE_SQL_CONNECTOR_VERSION = "r10.17c"

_FORBIDDEN_TOKENS = {
    "insert","update","delete","merge","drop","alter","create","truncate",
    "exec","execute","grant","revoke","deny","backup","restore","dbcc",
    "kill","use","openrowset","opendatasource","bulk","into",
}
_ALLOWED_START = {"select","with"}

def _governance() -> Dict[str, Any]:
    return {
        "read_only": True,
        "approved_query_only": True,
        "inline_sql_forbidden": True,
        "credential_value_not_serialized": True,
        "credential_reference_required": True,
        "query_fingerprint_required": True,
        "row_limit_required": True,
        "command_timeout_required": True,
        "dangerous_sql_blocked": True,
        "multiple_statements_blocked": True,
        "source_data_precedence": True,
        "formula_authority": False,
        "computational_authority": False,
        "fail_closed": True,
    }

def build_sql_server_connector_capability_audit() -> Dict[str, Any]:
    try:
        import pyodbc  # noqa: F401
        driver_available = True
    except Exception:
        driver_available = False
    return {
        "schema_version": ENTERPRISE_SQL_CONNECTOR_VERSION,
        "status": "AVAILABLE" if driver_available else "DRIVER_MISSING",
        "driver": "pyodbc",
        "driver_available": driver_available,
        "governance": _governance(),
    }

def _fingerprint_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def _normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", str(sql or "").strip())

def validate_read_only_sql(sql: str) -> Dict[str, Any]:
    normalized = _normalize_sql(sql)
    if not normalized:
        return {"valid": False, "reason": "empty_query", "normalized_sql": normalized}
    trimmed = normalized.rstrip()
    if ";" in trimmed.rstrip(";"):
        return {"valid": False, "reason": "multiple_statements_forbidden", "normalized_sql": normalized}
    without_strings = re.sub(r"'(?:''|[^'])*'", "''", normalized)
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", without_strings.lower())
    if not tokens or tokens[0] not in _ALLOWED_START:
        return {"valid": False, "reason": "select_or_cte_required", "normalized_sql": normalized}
    forbidden = sorted(set(tokens) & _FORBIDDEN_TOKENS)
    if forbidden:
        return {
            "valid": False,
            "reason": "dangerous_sql_forbidden",
            "forbidden_tokens": forbidden,
            "normalized_sql": normalized,
        }
    return {
        "valid": True,
        "reason": None,
        "normalized_sql": normalized.rstrip(";"),
        "query_fingerprint_sha256": _fingerprint_text(normalized.rstrip(";")),
    }

def resolve_approved_query(*, source: Dict[str, Any], query_id: str) -> Dict[str, Any]:
    source_id = str(source.get("source_id") or "").strip()
    if str(source.get("kind") or "") != "sql_server":
        return {"status": "BLOCKED", "reason": "source_kind_mismatch", "query": None}
    if str(source.get("status") or "").upper() != "ENABLED":
        return {"status": "BLOCKED", "reason": "source_not_enabled", "query": None}
    if not str(source.get("credential_ref") or "").strip():
        return {"status": "BLOCKED", "reason": "credential_reference_required", "query": None}

    approved_queries = source.get("approved_queries") or []
    if not isinstance(approved_queries, list):
        return {"status": "BLOCKED", "reason": "approved_queries_must_be_array", "query": None}
    matches = [q for q in approved_queries if isinstance(q, dict) and str(q.get("query_id") or "") == query_id]
    if len(matches) != 1:
        return {"status": "BLOCKED", "reason": "approved_query_not_found_or_ambiguous", "query": None}

    query = dict(matches[0])
    validation = validate_read_only_sql(str(query.get("sql") or ""))
    if not validation.get("valid"):
        return {"status": "BLOCKED", "reason": validation.get("reason"), "query": None}

    row_limit = query.get("row_limit", 10000)
    timeout_seconds = query.get("timeout_seconds", 30)
    if isinstance(row_limit, bool) or not isinstance(row_limit, int) or row_limit < 1 or row_limit > 100000:
        return {"status": "BLOCKED", "reason": "invalid_row_limit", "query": None}
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or timeout_seconds < 1 or timeout_seconds > 300:
        return {"status": "BLOCKED", "reason": "invalid_timeout", "query": None}

    return {
        "status": "APPROVED",
        "reason": None,
        "query": {
            "query_id": query_id,
            "sql": validation["normalized_sql"],
            "query_fingerprint_sha256": validation["query_fingerprint_sha256"],
            "row_limit": row_limit,
            "timeout_seconds": timeout_seconds,
        },
    }

def _resolve_credential_reference(ref: str) -> Optional[str]:
    ref = str(ref or "").strip()
    if not ref.startswith("env:"):
        return None
    name = ref[4:].strip()
    if not name:
        return None
    value = os.environ.get(name)
    return value if value else None

def execute_governed_sql_query(*, source: Dict[str, Any], query_id: str) -> Dict[str, Any]:
    resolved = resolve_approved_query(source=source, query_id=query_id)
    source_id = str(source.get("source_id") or "").strip() or None
    if resolved.get("status") != "APPROVED":
        return {
            "schema_version": ENTERPRISE_SQL_CONNECTOR_VERSION,
            "status": "BLOCKED",
            "reason": resolved.get("reason"),
            "source_id": source_id,
            "dataframe": None,
            "provenance": None,
            "governance": _governance(),
        }

    credential_ref = str(source.get("credential_ref") or "")
    connection_string = _resolve_credential_reference(credential_ref)
    if not connection_string:
        return {
            "schema_version": ENTERPRISE_SQL_CONNECTOR_VERSION,
            "status": "BLOCKED",
            "reason": "credential_unavailable",
            "source_id": source_id,
            "dataframe": None,
            "provenance": None,
            "governance": _governance(),
        }

    try:
        import pyodbc
    except Exception:
        return {
            "schema_version": ENTERPRISE_SQL_CONNECTOR_VERSION,
            "status": "BLOCKED",
            "reason": "pyodbc_unavailable",
            "source_id": source_id,
            "dataframe": None,
            "provenance": None,
            "governance": _governance(),
        }

    q = resolved["query"]
    conn = None
    try:
        conn = pyodbc.connect(connection_string, timeout=int(q["timeout_seconds"]), autocommit=False)
        cursor = conn.cursor()
        cursor.timeout = int(q["timeout_seconds"])
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        cursor.execute(q["sql"])
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(int(q["row_limit"]) + 1)
        truncated = len(rows) > int(q["row_limit"])
        if truncated:
            rows = rows[: int(q["row_limit"])]
        df = pd.DataFrame.from_records(rows, columns=columns)
        try:
            conn.rollback()
        except Exception:
            pass
    except Exception as exc:
        return {
            "schema_version": ENTERPRISE_SQL_CONNECTOR_VERSION,
            "status": "BLOCKED",
            "reason": f"query_failed:{type(exc).__name__}",
            "source_id": source_id,
            "dataframe": None,
            "provenance": None,
            "governance": _governance(),
        }
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

    locator = source.get("locator") if isinstance(source.get("locator"), dict) else {}
    provenance = {
        "schema_version": ENTERPRISE_SQL_CONNECTOR_VERSION,
        "source_id": source_id,
        "server": locator.get("server"),
        "database": locator.get("database"),
        "query_id": query_id,
        "query_fingerprint_sha256": q["query_fingerprint_sha256"],
        "row_limit": q["row_limit"],
        "timeout_seconds": q["timeout_seconds"],
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "truncated": truncated,
        "credential_ref_present": True,
        "credential_value_exposed": False,
    }

    return {
        "schema_version": ENTERPRISE_SQL_CONNECTOR_VERSION,
        "status": "OPENED",
        "reason": None,
        "source_id": source_id,
        "dataframe": df,
        "provenance": provenance,
        "governance": _governance(),
    }
