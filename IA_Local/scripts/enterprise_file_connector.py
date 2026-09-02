from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

ENTERPRISE_FILE_CONNECTOR_VERSION = "r10.17b"
_FILE_KINDS = {"excel", "csv"}
_EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".xlsb"}
_CSV_EXTENSIONS = {".csv", ".txt"}

def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()

def _governance() -> Dict[str, Any]:
    return {
        "read_only": True,
        "workspace_boundary_enforced": True,
        "path_traversal_blocked": True,
        "symlink_escape_blocked": True,
        "extension_kind_match_required": True,
        "file_fingerprint_required": True,
        "toctou_fingerprint_check": True,
        "no_query_execution": True,
        "no_code_execution": True,
        "no_formula_authority": True,
        "source_data_precedence": True,
        "fail_closed": True,
    }

def _blocked(reason: str, source_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "schema_version": ENTERPRISE_FILE_CONNECTOR_VERSION,
        "status": "BLOCKED",
        "reason": reason,
        "source_id": source_id,
        "dataframe": None,
        "provenance": None,
        "governance": _governance(),
    }

def build_file_connector_capability_audit() -> Dict[str, Any]:
    return {
        "schema_version": ENTERPRISE_FILE_CONNECTOR_VERSION,
        "status": "AVAILABLE",
        "supported_kinds": sorted(_FILE_KINDS),
        "governance": _governance(),
    }

def _read_csv_robust(path: Path) -> pd.DataFrame:
    last_error: Optional[Exception] = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            return pd.read_csv(path, encoding=encoding, sep=None, engine="python")
        except Exception as exc:
            last_error = exc
    raise ValueError(f"csv_read_failed:{type(last_error).__name__ if last_error else 'unknown'}")

def _excel_engine(path: Path) -> Optional[str]:
    ext = path.suffix.lower()
    try:
        import python_calamine  # noqa: F401
        return "calamine"
    except Exception:
        if ext in {".xlsx", ".xlsm"}:
            return "openpyxl"
        if ext == ".xls":
            return "xlrd"
        if ext == ".xlsb":
            return "pyxlsb"
    return None

def _read_excel(path: Path, sheet_name: Any = 0) -> Tuple[pd.DataFrame, str]:
    engine = _excel_engine(path)
    if not engine:
        raise ValueError("excel_engine_unavailable")
    try:
        return pd.read_excel(path, sheet_name=sheet_name, engine=engine), engine
    except Exception:
        fallback = "openpyxl" if path.suffix.lower() in {".xlsx", ".xlsm"} else ("xlrd" if path.suffix.lower() == ".xls" else "pyxlsb")
        if fallback == engine:
            raise
        return pd.read_excel(path, sheet_name=sheet_name, engine=fallback), fallback

def open_governed_file_source(*, source: Dict[str, Any], workspace_root: str | Path) -> Dict[str, Any]:
    if not isinstance(source, dict):
        return _blocked("source_must_be_object")

    source_id = str(source.get("source_id") or "").strip() or None
    kind = str(source.get("kind") or "").strip()
    status = str(source.get("status") or "").strip().upper()
    access = source.get("access") or {}
    locator = source.get("locator") or {}

    if kind not in _FILE_KINDS:
        return _blocked("unsupported_file_source_kind", source_id)
    if status != "ENABLED":
        return _blocked("source_not_enabled", source_id)
    if not isinstance(access, dict) or str(access.get("mode") or "read_only") != "read_only":
        return _blocked("source_not_read_only", source_id)
    if not isinstance(locator, dict):
        return _blocked("locator_must_be_object", source_id)

    relative_path = str(locator.get("relative_path") or "").strip()
    if not relative_path:
        return _blocked("missing_relative_path", source_id)

    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        return _blocked("unsafe_relative_path", source_id)

    root = Path(workspace_root).resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return _blocked("workspace_escape_blocked", source_id)

    if not candidate.exists():
        return _blocked("source_file_not_found", source_id)
    if not candidate.is_file():
        return _blocked("source_path_not_file", source_id)

    ext = candidate.suffix.lower()
    if kind == "csv" and ext not in _CSV_EXTENSIONS:
        return _blocked("kind_extension_mismatch", source_id)
    if kind == "excel" and ext not in _EXCEL_EXTENSIONS:
        return _blocked("kind_extension_mismatch", source_id)

    try:
        fingerprint_before = _sha256_file(candidate)
        stat_before = candidate.stat()

        if kind == "csv":
            df = _read_csv_robust(candidate)
            engine = "pandas_csv_python"
            sheet = None
        else:
            sheet = locator.get("sheet", 0)
            df, engine = _read_excel(candidate, sheet_name=sheet)

        fingerprint_after = _sha256_file(candidate)
        stat_after = candidate.stat()
    except Exception as exc:
        return _blocked(f"read_failed:{type(exc).__name__}", source_id)

    if fingerprint_before != fingerprint_after:
        return _blocked("source_changed_during_read", source_id)
    if stat_before.st_size != stat_after.st_size:
        return _blocked("source_size_changed_during_read", source_id)

    provenance = {
        "schema_version": ENTERPRISE_FILE_CONNECTOR_VERSION,
        "source_id": source_id,
        "kind": kind,
        "relative_path": relative.as_posix(),
        "file_name": candidate.name,
        "extension": ext,
        "size_bytes": int(stat_after.st_size),
        "fingerprint_sha256": fingerprint_after,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "reader_engine": engine,
        "sheet": sheet,
    }

    return {
        "schema_version": ENTERPRISE_FILE_CONNECTOR_VERSION,
        "status": "OPENED",
        "reason": None,
        "source_id": source_id,
        "dataframe": df,
        "provenance": provenance,
        "governance": _governance(),
    }
