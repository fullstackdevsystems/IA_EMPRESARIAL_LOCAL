from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

CONTEXT_VERSION = "r10.15c"
_ALLOWED_SCOPE_KEYS = ("tenant_id", "company_id", "business_unit_id", "branch_id")


def _default_context_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "business_context.json"


def load_governed_business_context(path: Optional[str] = None) -> Dict[str, Any]:
    p = Path(path) if path else _default_context_path()

    base = {
        "schema_version": CONTEXT_VERSION,
        "status": "UNCONFIGURED",
        "path": str(p),
        "context": {},
        "errors": [],
        "governance": {
            "explicit_context_required_for_scoped_rules": True,
            "unknown_scope_is_never_inferred": True,
            "wildcard_context_is_not_assumed": True,
            "fail_closed": True,
        },
    }

    if not p.exists():
        return base

    try:
        raw = p.read_text(encoding="utf-8-sig")
        data = json.loads(raw)
    except Exception as exc:
        out = deepcopy(base)
        out["status"] = "INVALID"
        out["errors"] = [f"context_read_error:{type(exc).__name__}"]
        return out

    if not isinstance(data, dict):
        out = deepcopy(base)
        out["status"] = "INVALID"
        out["errors"] = ["context_root_must_be_object"]
        return out

    if str(data.get("schema_version") or "") != CONTEXT_VERSION:
        out = deepcopy(base)
        out["status"] = "INVALID"
        out["errors"] = ["unsupported_context_schema"]
        return out

    raw_context = data.get("context")
    if not isinstance(raw_context, dict):
        out = deepcopy(base)
        out["status"] = "INVALID"
        out["errors"] = ["context_must_be_object"]
        return out

    clean = {}
    for key in _ALLOWED_SCOPE_KEYS:
        value = raw_context.get(key)
        if value not in (None, ""):
            clean[key] = str(value)

    as_of = raw_context.get("as_of")
    if as_of not in (None, ""):
        clean["as_of"] = str(as_of)

    return {
        "schema_version": CONTEXT_VERSION,
        "status": "LOADED" if clean else "UNCONFIGURED",
        "path": str(p),
        "context": clean,
        "errors": [],
        "governance": deepcopy(base["governance"]),
    }
