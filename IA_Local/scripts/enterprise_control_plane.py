"""Read-only, fail-closed control-plane view over governed enterprise stores."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from enterprise_identity import EnterpriseIdentityStore, IdentityError
from enterprise_platform_config import EnterprisePlatformConfigStore, PlatformConfigError
from enterprise_sql_gateway import EnterpriseSqlConnectionStore, EnterpriseSqlError, public_sql_profile
from enterprise_tenant_registry import EnterpriseTenantRegistry, TenantRegistryError


class ControlPlaneError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class EnterpriseControlPlane:
    """Composes existing authorities; it never owns identity, SQL, or config data."""

    def __init__(self, runtime_root: str | Path):
        root = Path(runtime_root)
        reports = root / "workspace" / "Reportes"
        self.runtime_root = root
        self.tenants = EnterpriseTenantRegistry(reports / ".tenants")
        self.identity = EnterpriseIdentityStore(reports / ".identity", self.tenants)
        self.platform = EnterprisePlatformConfigStore(reports / ".platform_config", self.tenants)
        self.sql = EnterpriseSqlConnectionStore(reports / ".sql_connections", self.tenants)

    def _actor(self, principal: Any) -> Dict[str, Any]:
        try:
            actor = self.identity.get(principal.user_id)
            if actor["status"] != "ACTIVE" or actor["tenant_id"] != principal.company_id:
                raise ControlPlaneError("CONTROL_PLANE_SCOPE_DENIED", "Identidad no autorizada")
            self.tenants.assert_active(actor["tenant_id"])
            return actor
        except ControlPlaneError:
            raise
        except (IdentityError, TenantRegistryError) as exc:
            raise ControlPlaneError("CONTROL_PLANE_AUTH_REQUIRED", "Identidad empresarial requerida") from exc

    def _permit(self, principal: Any, permission: str) -> Dict[str, Any]:
        actor = self._actor(principal)
        if not self.identity.has_permission(actor, permission):
            raise ControlPlaneError("CONTROL_PLANE_PERMISSION_DENIED", "Permiso administrativo requerido")
        return actor

    @staticmethod
    def _public_tenant(record: Dict[str, Any], effective: Dict[str, Any]) -> Dict[str, Any]:
        return {"tenant_id": record["tenant_id"], "name": record["name"], "status": record["status"],
                "branding": effective.get("branding", {}), "enabled_features": effective.get("enabled_features", {})}

    def _release(self) -> Dict[str, Any]:
        path = self.runtime_root.parent / "RELEASE_METADATA.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ControlPlaneError("CONTROL_PLANE_RELEASE_METADATA_MISSING", "Metadata de release no disponible") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ControlPlaneError("CONTROL_PLANE_RELEASE_METADATA_INVALID", "Metadata de release inválida") from exc
        required = ("product_version", "release", "channel")
        if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("product") != "IA_EMPRESARIAL_LOCAL" or any(not isinstance(data.get(key), str) or not data[key].strip() for key in required):
            raise ControlPlaneError("CONTROL_PLANE_RELEASE_METADATA_INVALID", "Metadata de release inválida")
        return {key: data[key] for key in required}

    def overview(self, principal: Any, *, health: Dict[str, Any] | None = None) -> Dict[str, Any]:
        actor = self._permit(principal, "config:read")
        tenant = self.tenants.get(actor["tenant_id"])
        effective = self.platform.public_effective_config(actor["tenant_id"])
        profiles = [public_sql_profile(item) for item in self.sql.list(self.identity.scope(actor))]
        provider = effective.get("ai_provider")
        return {"release": self._release(), "active_tenant": self._public_tenant(tenant, effective),
                "active_user": {key: actor.get(key) for key in ("user_id", "username", "display_name", "roles", "business_units", "branches", "status")},
                "effective_config": effective, "sql": {"status": "CONFIGURED" if profiles else "NOT_CONFIGURED", "sources": profiles},
                "ai": {"status": "DISABLED" if provider and provider.get("provider_type") == "DISABLED" else ("CONFIGURED" if provider else "NOT_CONFIGURED"),
                       "provider": self._public_provider(provider)}, "health": dict(health or {})}

    def tenants_for(self, principal: Any) -> List[Dict[str, Any]]:
        actor = self._permit(principal, "tenant:list")
        records = self.tenants.list() if self.identity.has_permission(actor, "*") else [self.tenants.get(actor["tenant_id"])]
        return [self._public_tenant(item, self.platform.public_effective_config(item["tenant_id"])) for item in records]

    def users_for(self, principal: Any) -> List[Dict[str, Any]]:
        actor = self._permit(principal, "user:list")
        users = self.identity.list() if self.identity.has_permission(actor, "*") else self.identity.list(actor["tenant_id"])
        return [{key: item.get(key) for key in ("user_id", "username", "display_name", "tenant_id", "status", "roles", "business_units", "branches", "created_at", "updated_at")} for item in users]

    def sql_sources_for(self, principal: Any) -> List[Dict[str, Any]]:
        actor = self._permit(principal, "sql:read")
        return [public_sql_profile(item) for item in self.sql.list(self.identity.scope(actor))]

    def ai_for(self, principal: Any) -> Dict[str, Any]:
        actor = self._permit(principal, "config:read")
        return self._public_provider(self.platform.resolve_effective_config(actor["tenant_id"]).get("ai_provider"))

    @staticmethod
    def _public_provider(provider: Any) -> Dict[str, Any] | None:
        if not isinstance(provider, dict):
            return None
        return {key: provider.get(key) for key in ("provider_id", "provider_type", "base_url", "model", "enabled", "timeout", "context_window")}
