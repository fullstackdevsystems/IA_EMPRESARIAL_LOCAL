"""Commercial first-run configuration using the existing governed stores."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from enterprise_identity import EnterpriseIdentityStore, IdentityError, validate_password
from enterprise_platform_config import EnterprisePlatformConfigStore, PlatformConfigError
from enterprise_tenant_registry import EnterpriseTenantRegistry, TenantRegistryError
from enterprise_sql_gateway import EnterpriseSqlConnectionStore, EnterpriseSqlError, public_sql_profile


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
        self.sql = EnterpriseSqlConnectionStore(self.reports_root / ".sql_connections", self.tenants)

    def _admins(self):
        return [u for u in self.identity.list() if u["status"] == "ACTIVE" and "SYSTEM_ADMIN" in u["roles"]]

    def _scope(self, tenant_id):
        admin = next((u for u in self._admins() if u["tenant_id"] == self.tenants.get(tenant_id)["tenant_id"]), None)
        if not admin: raise OnboardingError("CONFIGURATION_REQUIRED", "Administrador requerido")
        return {"company_id": admin["tenant_id"], "user_id": admin["user_id"], "business_unit": None, "branch": None}

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
            sql_state = "NOT_CONFIGURED"
            if len(tenants) == 1 and admins:
                try: sql_state = "CONFIGURED" if self.sql.list(self._scope(tenants[0]["tenant_id"])) else "NOT_CONFIGURED"
                except EnterpriseSqlError: sql_state = "INVALID_CONFIGURATION"
            ai = self.platform.tenant_config(tenants[0]["tenant_id"]).get("ai_provider") if tenants else None
            return {
                "status": state,
                "tenant_count": len(tenants),
                "admin_count": len(admins),
                "sql": sql_state,
                "ai_provider": "DISABLED" if ai and ai.get("provider_type") == "DISABLED" else ("CONFIGURED" if ai else "NOT_CONFIGURED"),
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
            # Password policy remains centralized in enterprise_identity and is
            # validated before this façade creates any persistent resource.
            validate_password(password)
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

    def configure_sql(self, *, tenant_id, connection_id, server, database, auth_mode, allowed_schemas, allowed_tables, secret_reference="", username=""):
        try:
            profile = self.sql.register(scope=self._scope(tenant_id), connection_id=connection_id, server=server, database=database, auth_mode=auth_mode, allowed_schemas=allowed_schemas, allowed_tables=allowed_tables, secret_reference=secret_reference, username=username)
            return public_sql_profile(profile)
        except (EnterpriseSqlError, TenantRegistryError) as exc: raise OnboardingError(exc.code, "Configuración SQL inválida") from exc

    def configure_ai(self, *, tenant_id, provider):
        try: return self.platform.update_tenant(tenant_id, {"ai_provider": provider})
        except PlatformConfigError as exc: raise OnboardingError(exc.code, "Configuración IA inválida") from exc


def _reports_from_runtime(runtime_root: str) -> Path:
    return Path(runtime_root).resolve() / "IA_Local" / "Reportes"


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Configuración inicial IA Empresarial Local")
    parser.add_argument("action", choices=("status", "validate", "configure", "configure-sql", "configure-ai"))
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--tenant-id")
    parser.add_argument("--tenant-name")
    parser.add_argument("--admin-user-id")
    parser.add_argument("--admin-username")
    parser.add_argument("--admin-display-name")
    parser.add_argument("--connection-id"); parser.add_argument("--server"); parser.add_argument("--database"); parser.add_argument("--auth-mode"); parser.add_argument("--allowed-schemas"); parser.add_argument("--allowed-tables"); parser.add_argument("--secret-reference", default=""); parser.add_argument("--username", default="")
    parser.add_argument("--provider"); parser.add_argument("--base-url"); parser.add_argument("--model"); parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args(argv)
    onboarding = EnterpriseOnboarding(_reports_from_runtime(args.runtime_root))
    try:
        if args.action == "status":
            result = onboarding.status()
        elif args.action == "validate":
            result = onboarding.validate()
        elif args.action == "configure":
            password = os.environ.get("IA_ONBOARDING_ADMIN_PASSWORD")
            if not password:
                raise OnboardingError("PASSWORD_REQUIRED", "Password administrativo requerido")
            required = (args.tenant_id, args.tenant_name, args.admin_user_id, args.admin_username, args.admin_display_name)
            if not all(required):
                raise OnboardingError("CONFIGURATION_REQUIRED", "Campos de configuración requeridos")
            result = onboarding.configure(tenant_id=args.tenant_id, tenant_name=args.tenant_name, admin_user_id=args.admin_user_id, admin_username=args.admin_username, admin_display_name=args.admin_display_name, password=password)
        elif args.action == "configure-sql":
            result = onboarding.configure_sql(tenant_id=args.tenant_id, connection_id=args.connection_id, server=args.server, database=args.database, auth_mode=args.auth_mode, allowed_schemas=(args.allowed_schemas or "").split(","), allowed_tables=(args.allowed_tables or "").split(","), secret_reference=args.secret_reference, username=args.username)
        else:
            result = onboarding.configure_ai(tenant_id=args.tenant_id, provider={"provider_type": args.provider, "base_url": args.base_url or None, "model": args.model or None, "timeout": args.timeout})
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except OnboardingError as exc:
        print(json.dumps({"status": "INVALID_CONFIGURATION", "code": exc.code}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
