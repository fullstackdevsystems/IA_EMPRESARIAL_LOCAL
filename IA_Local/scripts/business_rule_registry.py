from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

REGISTRY_VERSION = "r10.15b"


def _default_registry_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "business_rules.json"


def _fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_governed_business_rule_registry(
    path: Optional[str] = None,
) -> Dict[str, Any]:
    # Load a persistent business-rule registry fail-closed.
    # Missing/malformed/unsupported registries never invent fallback rules.
    p = Path(path) if path else _default_registry_path()

    governance = {
        "fail_closed": True,
        "missing_registry_means_no_rules": True,
        "malformed_registry_means_no_rules": True,
        "default_rules_are_never_invented": True,
    }

    if not p.exists():
        return {
            "schema_version": REGISTRY_VERSION,
            "status": "EMPTY",
            "path": str(p),
            "registry_id": None,
            "ruleset_version": None,
            "rule_count": 0,
            "rules": [],
            "fingerprint_sha256": None,
            "errors": [],
            "governance": governance,
        }

    try:
        raw = p.read_bytes()
    except Exception as exc:
        return {
            "schema_version": REGISTRY_VERSION,
            "status": "ERROR",
            "path": str(p),
            "registry_id": None,
            "ruleset_version": None,
            "rule_count": 0,
            "rules": [],
            "fingerprint_sha256": None,
            "errors": [f"read_error:{type(exc).__name__}"],
            "governance": governance,
        }

    digest = _fingerprint(raw)

    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        return {
            "schema_version": REGISTRY_VERSION,
            "status": "INVALID",
            "path": str(p),
            "registry_id": None,
            "ruleset_version": None,
            "rule_count": 0,
            "rules": [],
            "fingerprint_sha256": digest,
            "errors": [f"json_error:{type(exc).__name__}"],
            "governance": governance,
        }

    if not isinstance(data, dict):
        return {
            "schema_version": REGISTRY_VERSION,
            "status": "INVALID",
            "path": str(p),
            "registry_id": None,
            "ruleset_version": None,
            "rule_count": 0,
            "rules": [],
            "fingerprint_sha256": digest,
            "errors": ["registry_root_must_be_object"],
            "governance": governance,
        }

    source_schema = str(data.get("schema_version") or "")
    rules = data.get("rules")
    errors: List[str] = []

    if source_schema != REGISTRY_VERSION:
        errors.append("unsupported_registry_schema")
    if not isinstance(rules, list):
        errors.append("rules_must_be_array")

    if errors:
        return {
            "schema_version": REGISTRY_VERSION,
            "status": "INVALID",
            "path": str(p),
            "registry_id": data.get("registry_id"),
            "ruleset_version": data.get("ruleset_version"),
            "rule_count": 0,
            "rules": [],
            "fingerprint_sha256": digest,
            "errors": errors,
            "governance": governance,
        }

    clean_rules = [dict(x) for x in rules if isinstance(x, dict)]

    return {
        "schema_version": REGISTRY_VERSION,
        "status": "LOADED" if clean_rules else "EMPTY",
        "path": str(p),
        "registry_id": data.get("registry_id"),
        "ruleset_version": data.get("ruleset_version"),
        "rule_count": len(clean_rules),
        "rules": clean_rules,
        "fingerprint_sha256": digest,
        "errors": [],
        "governance": governance,
    }
