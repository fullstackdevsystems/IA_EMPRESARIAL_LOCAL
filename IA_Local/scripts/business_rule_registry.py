from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REGISTRY_VERSION = "r10.15d"


def _default_registry_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "business_rules.json"


def _fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _parse_date(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def _rule_identity(rule: Dict[str, Any]) -> str:
    return str(rule.get("rule_id") or "").strip()


def _validate_registry_rules(rules: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    validated: List[Dict[str, Any]] = []
    seen_ids = set()

    for index, raw in enumerate(rules):
        if not isinstance(raw, dict):
            errors.append(f"rule_{index}:rule_must_be_object")
            continue

        rule = dict(raw)
        rule_id = _rule_identity(rule)

        if not rule_id:
            errors.append(f"rule_{index}:missing_rule_id")
            continue

        if rule_id in seen_ids:
            errors.append(f"rule_{index}:duplicate_rule_id:{rule_id}")
            continue
        seen_ids.add(rule_id)

        effective_from_raw = rule.get("effective_from")
        effective_to_raw = rule.get("effective_to")
        effective_from = _parse_date(effective_from_raw)
        effective_to = _parse_date(effective_to_raw)

        if effective_from_raw not in (None, "") and effective_from is None:
            errors.append(f"rule_{index}:invalid_effective_from:{rule_id}")
            continue

        if effective_to_raw not in (None, "") and effective_to is None:
            errors.append(f"rule_{index}:invalid_effective_to:{rule_id}")
            continue

        if effective_from and effective_to and effective_from > effective_to:
            errors.append(f"rule_{index}:invalid_effective_range:{rule_id}")
            continue

        try:
            priority = int(rule.get("priority") or 0)
        except Exception:
            errors.append(f"rule_{index}:invalid_priority:{rule_id}")
            continue

        if priority < 0:
            errors.append(f"rule_{index}:negative_priority:{rule_id}")
            continue

        scope = rule.get("scope")
        if scope is not None and not isinstance(scope, dict):
            errors.append(f"rule_{index}:scope_must_be_object:{rule_id}")
            continue

        classification = rule.get("classification")
        if classification is not None and not isinstance(classification, dict):
            errors.append(f"rule_{index}:classification_must_be_object:{rule_id}")
            continue

        validated.append(rule)

    return validated, errors


def load_governed_business_rule_registry(
    path: Optional[str] = None,
) -> Dict[str, Any]:
    p = Path(path) if path else _default_registry_path()

    governance = {
        "fail_closed": True,
        "missing_registry_means_no_rules": True,
        "malformed_registry_means_no_rules": True,
        "default_rules_are_never_invented": True,
        "duplicate_rule_ids_are_rejected": True,
        "invalid_effective_ranges_are_rejected": True,
        "invalid_priorities_are_rejected": True,
        "invalid_rule_shapes_are_rejected": True,
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

    if source_schema not in {"r10.15b", REGISTRY_VERSION}:
        errors.append("unsupported_registry_schema")
    if not isinstance(rules, list):
        errors.append("rules_must_be_array")

    if errors:
        return {
            "schema_version": REGISTRY_VERSION,
            "source_schema_version": source_schema or None,
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

    validated_rules, rule_errors = _validate_registry_rules(rules)
    if rule_errors:
        return {
            "schema_version": REGISTRY_VERSION,
            "source_schema_version": source_schema,
            "status": "INVALID",
            "path": str(p),
            "registry_id": data.get("registry_id"),
            "ruleset_version": data.get("ruleset_version"),
            "rule_count": 0,
            "rules": [],
            "fingerprint_sha256": digest,
            "errors": rule_errors,
            "governance": governance,
        }

    return {
        "schema_version": REGISTRY_VERSION,
        "source_schema_version": source_schema,
        "status": "LOADED" if validated_rules else "EMPTY",
        "path": str(p),
        "registry_id": data.get("registry_id"),
        "ruleset_version": data.get("ruleset_version"),
        "rule_count": len(validated_rules),
        "rules": validated_rules,
        "fingerprint_sha256": digest,
        "errors": [],
        "governance": governance,
    }
