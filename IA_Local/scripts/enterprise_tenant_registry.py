from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


TENANT_REGISTRY_VERSION = "r10.20b.1"
_TENANT_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")
_STATUSES = {"ACTIVE", "DISABLED"}
_SETTING_KEYS = {"display_name", "locale", "timezone", "default_theme", "enabled_features", "logo_reference", "accent_color"}
_SECRET_KEY = re.compile(r"password|secret|credential|connection|token", re.IGNORECASE)


class TenantRegistryError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_tenant_id(value: Any) -> str:
    tenant_id = str(value or "").strip().lower()
    if not _TENANT_ID.fullmatch(tenant_id) or tenant_id in {".", ".."}:
        raise TenantRegistryError("TENANT_INVALID_ID", "tenant_id no es seguro o válido")
    return tenant_id


def _name(value: Any) -> str:
    name = str(value or "").strip()
    if not name or len(name) > 160:
        raise TenantRegistryError("TENANT_INVALID_NAME", "name es obligatorio y debe tener hasta 160 caracteres")
    return name


def _settings(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict) or set(value) - _SETTING_KEYS:
        raise TenantRegistryError("TENANT_INVALID_SETTINGS", "settings contiene campos no permitidos")
    for key, item in value.items():
        if _SECRET_KEY.search(key) or (isinstance(item, str) and ("password=" in item.lower() or "connection string" in item.lower())):
            raise TenantRegistryError("TENANT_INVALID_SETTINGS", "settings no puede contener secretos")
    enabled = value.get("enabled_features")
    if enabled is not None and (not isinstance(enabled, list) or not all(isinstance(item, str) and item.strip() for item in enabled)):
        raise TenantRegistryError("TENANT_INVALID_SETTINGS", "enabled_features debe ser una lista de textos")
    return dict(value)


def _record(tenant_id: str, name: str, settings: Dict[str, Any], now: str) -> Dict[str, Any]:
    record = {"tenant_id": tenant_id, "name": name, "status": "ACTIVE", "created_at": now, "updated_at": now, "default_business_unit": None, "default_branch": None, "settings": settings}
    record["integrity"] = {"fingerprint_sha256": _fingerprint(record)}
    return record


def _verify_record(record: Any) -> Dict[str, Any]:
    if not isinstance(record, dict):
        raise TenantRegistryError("TENANT_INTEGRITY_MISMATCH", "Registro tenant inválido")
    integrity = record.get("integrity") if isinstance(record.get("integrity"), dict) else {}
    expected = str(integrity.get("fingerprint_sha256") or "")
    unsigned = dict(record)
    unsigned.pop("integrity", None)
    if not re.fullmatch(r"[a-f0-9]{64}", expected) or expected != _fingerprint(unsigned):
        raise TenantRegistryError("TENANT_INTEGRITY_MISMATCH", "Registro tenant alterado")
    normalize_tenant_id(record.get("tenant_id")); _name(record.get("name")); _settings(record.get("settings"))
    if record.get("status") not in _STATUSES:
        raise TenantRegistryError("TENANT_INTEGRITY_MISMATCH", "Estado tenant inválido")
    return dict(record)


class EnterpriseTenantRegistry:
    """Small local registry that establishes company identity before scope use."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.path = self.root / "tenants.json"

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": TENANT_REGISTRY_VERSION, "records": [], "registry_fingerprint_sha256": _fingerprint({"schema_version": TENANT_REGISTRY_VERSION, "records": []})}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TenantRegistryError("TENANT_INTEGRITY_MISMATCH", "Registry tenant ilegible") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != TENANT_REGISTRY_VERSION or not isinstance(payload.get("records"), list):
            raise TenantRegistryError("TENANT_INTEGRITY_MISMATCH", "Registry tenant inválido")
        unsigned = {"schema_version": payload["schema_version"], "records": payload["records"]}
        if payload.get("registry_fingerprint_sha256") != _fingerprint(unsigned):
            raise TenantRegistryError("TENANT_INTEGRITY_MISMATCH", "Registry tenant alterado")
        records = [_verify_record(record) for record in payload["records"]]
        if len({record["tenant_id"] for record in records}) != len(records):
            raise TenantRegistryError("TENANT_INTEGRITY_MISMATCH", "Registry tenant duplicado")
        return {**payload, "records": records}

    def _save(self, records: List[Dict[str, Any]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": TENANT_REGISTRY_VERSION, "records": records}
        payload["registry_fingerprint_sha256"] = _fingerprint(payload)
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.root, prefix=".tenants-", suffix=".tmp", delete=False)
        try:
            with handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            os.replace(handle.name, self.path)
        finally:
            if os.path.exists(handle.name):
                os.unlink(handle.name)

    def create(self, *, tenant_id: Any, name: Any, settings: Any = None, default_business_unit: Any = None, default_branch: Any = None) -> Dict[str, Any]:
        safe_id = normalize_tenant_id(tenant_id); records = self._load()["records"]
        if any(item["tenant_id"] == safe_id for item in records):
            raise TenantRegistryError("TENANT_ALREADY_EXISTS", "El tenant ya existe")
        record = _record(safe_id, _name(name), _settings(settings), _now())
        record["default_business_unit"] = str(default_business_unit).strip() if default_business_unit not in (None, "") else None
        record["default_branch"] = str(default_branch).strip() if default_branch not in (None, "") else None
        record["integrity"] = {"fingerprint_sha256": _fingerprint({key: value for key, value in record.items() if key != "integrity"})}
        records.append(record); self._save(records)
        return dict(record)

    def get(self, tenant_id: Any) -> Dict[str, Any]:
        safe_id = normalize_tenant_id(tenant_id)
        for record in self._load()["records"]:
            if record["tenant_id"] == safe_id:
                return dict(record)
        raise TenantRegistryError("TENANT_NOT_FOUND", "Tenant no encontrado")

    def list(self) -> List[Dict[str, Any]]:
        return [dict(item) for item in sorted(self._load()["records"], key=lambda item: item["tenant_id"])]

    def update(self, tenant_id: Any, *, name: Any = None, settings: Any = None, default_business_unit: Any = None, default_branch: Any = None) -> Dict[str, Any]:
        safe_id = normalize_tenant_id(tenant_id); payload = self._load(); found = None
        for record in payload["records"]:
            if record["tenant_id"] == safe_id:
                found = record; break
        if found is None:
            raise TenantRegistryError("TENANT_NOT_FOUND", "Tenant no encontrado")
        if name is not None: found["name"] = _name(name)
        if settings is not None: found["settings"] = _settings(settings)
        if default_business_unit is not None: found["default_business_unit"] = str(default_business_unit).strip() or None
        if default_branch is not None: found["default_branch"] = str(default_branch).strip() or None
        found["updated_at"] = _now(); found["integrity"] = {"fingerprint_sha256": _fingerprint({key: value for key, value in found.items() if key != "integrity"})}
        self._save(payload["records"]); return dict(found)

    def set_status(self, tenant_id: Any, status: str) -> Dict[str, Any]:
        if status not in _STATUSES:
            raise TenantRegistryError("TENANT_INVALID_STATUS", "Estado tenant inválido")
        record = self.update(tenant_id)
        payload = self._load()
        for item in payload["records"]:
            if item["tenant_id"] == record["tenant_id"]:
                item["status"] = status; item["updated_at"] = _now(); item["integrity"] = {"fingerprint_sha256": _fingerprint({key: value for key, value in item.items() if key != "integrity"})}; self._save(payload["records"]); return dict(item)
        raise TenantRegistryError("TENANT_NOT_FOUND", "Tenant no encontrado")

    def disable(self, tenant_id: Any) -> Dict[str, Any]:
        return self.set_status(tenant_id, "DISABLED")

    def enable(self, tenant_id: Any) -> Dict[str, Any]:
        return self.set_status(tenant_id, "ACTIVE")

    def assert_active(self, tenant_id: Any) -> Dict[str, Any]:
        record = self.get(tenant_id)
        if record["status"] != "ACTIVE":
            raise TenantRegistryError("TENANT_DISABLED", "Tenant deshabilitado")
        return record


def assert_tenant_active(scope: Dict[str, Any], registry: Optional[EnterpriseTenantRegistry] = None) -> Dict[str, Any]:
    if registry is None:
        return dict(scope)
    if not isinstance(scope, dict) or not scope.get("company_id"):
        raise TenantRegistryError("TENANT_REQUIRED", "company_id es obligatorio")
    registry.assert_active(scope["company_id"])
    return dict(scope)
