"""Commercial first-run configuration using the existing governed stores."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from enterprise_identity import EnterpriseIdentityStore, IdentityError
from enterprise_platform_config import EnterprisePlatformConfigStore, PlatformConfigError
from enterprise_tenant_registry import EnterpriseTenantRegistry, TenantRegistryError


class OnboardingError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class EnterpriseOnboarding:
    """Small façade; tenant, identity and platform stores remain authoritative."""

    def __init__(self, reports_root: Path):
        self.reports_root = Path(reports_root)
        self.tenants = EnterpriseTenantRegistry(self.reports_root / ".tenants")
        self.identity = EnterpriseIdentityStore(self.reports_root / ".identity", self.tenants)
        self.platform = EnterprisePlatformConfigStore(self.reports_root / ".platform_config", self.tenants)

    def _admins(self):
        return [u for u in self.identity.list() if u["status"] == "ACTIVE" and "SYSTEM_ADMIN" in u["roles"]]

    def status(self) -> Dict[str, Any]:
        try:
            tenants = self.tenants.list()
            admins = self._admins()
            if not tenants and not admins:
                state = "FIRST_RUN"
            elif tenants and admins and all(any(t["tenant_id"] == a["tenant_id"] for t in tenants) for a in admins):
                state = "CONFIGURED"
            else:
                state = "INVALID_CONFIGURATION"
            return {
                "status": state,
                "tenant_count": len(tenants),
                "admin_count": len(admins),
                "sql": "NOT_CONFIGURED",
                "ai_provider": "NOT_CONFIGURED" if self.platform.global_config()["default_ai_provider"] == "DISABLED" else "CONFIGURED",
            }
        except (TenantRegistryError, IdentityError, PlatformConfigError) as exc:
            return {"status": "INVALID_CONFIGURATION", "code": exc.code, "sql": "NOT_CONFIGURED", "ai_provider": "NOT_CONFIGURED"}

    def validate(self) -> Dict[str, Any]:
        result = self.status()
        if result["status"] != "CONFIGURED":
            raise OnboardingError("CONFIGURATION_REQUIRED", "CONFIGURATION: REQUIRED")
        return result

    def configure(self, *, tenant_id: str, tenant_name: str, admin_user_id: str, admin_username: str, admin_display_name: str, password: str) -> Dict[str, Any]:
        try:
            try:
                tenant = self.tenants.get(tenant_id)
                if tenant["name"] != str(tenant_name).strip():
                    raise OnboardingError("CONFIGURATION_CONFLICT", "Tenant existente incompatible")
            except TenantRegistryError as exc:
                if exc.code != "TENANT_NOT_FOUND":
                    raise
                self.tenants.create(tenant_id=tenant_id, name=tenant_name)
            admins = self._admins()
            existing = next((u for u in admins if u["user_id"] == str(admin_user_id).strip().lower() and u["tenant_id"] == str(tenant_id).strip().lower()), None)
            if not existing:
                if admins:
                    raise OnboardingError("CONFIGURATION_CONFLICT", "Ya existe un administrador empresarial")
                self.identity.bootstrap_admin(user_id=admin_user_id, username=admin_username, display_name=admin_display_name, password=password, tenant_id=tenant_id)
            self.platform.update_tenant(tenant_id, {"display_name": str(tenant_name).strip()})
            return self.validate()
        except OnboardingError:
            raise
        except (TenantRegistryError, IdentityError, PlatformConfigError) as exc:
            raise OnboardingError(exc.code, "Configuración empresarial inválida") from exc


def _reports_from_runtime(runtime_root: str) -> Path:
    return Path(runtime_root).resolve() / "IA_Local" / "Reportes"


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Configuración inicial IA Empresarial Local")
    parser.add_argument("action", choices=("status", "validate", "configure"))
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--tenant-id")
    parser.add_argument("--tenant-name")
    parser.add_argument("--admin-user-id")
    parser.add_argument("--admin-username")
    parser.add_argument("--admin-display-name")
    args = parser.parse_args(argv)
    onboarding = EnterpriseOnboarding(_reports_from_runtime(args.runtime_root))
    try:
        if args.action == "status":
            result = onboarding.status()
        elif args.action == "validate":
            result = onboarding.validate()
        else:
            password = os.environ.get("IA_ONBOARDING_ADMIN_PASSWORD")
            if not password:
                raise OnboardingError("PASSWORD_REQUIRED", "Password administrativo requerido")
            required = (args.tenant_id, args.tenant_name, args.admin_user_id, args.admin_username, args.admin_display_name)
            if not all(required):
                raise OnboardingError("CONFIGURATION_REQUIRED", "Campos de configuración requeridos")
            result = onboarding.configure(tenant_id=args.tenant_id, tenant_name=args.tenant_name, admin_user_id=args.admin_user_id, admin_username=args.admin_username, admin_display_name=args.admin_display_name, password=password)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except OnboardingError as exc:
        print(json.dumps({"status": "INVALID_CONFIGURATION", "code": exc.code}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
