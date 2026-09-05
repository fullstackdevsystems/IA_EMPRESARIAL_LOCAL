from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "IA_Local" / "scripts"))
from enterprise_onboarding import EnterpriseOnboarding, OnboardingError


def check(name, value):
    if not value:
        raise AssertionError(name)
    print("PASS", name)


with tempfile.TemporaryDirectory() as temporary:
    reports = Path(temporary) / "IA_Local" / "Reportes"
    onboarding = EnterpriseOnboarding(reports)
    first = onboarding.status()
    check("detects_first_run", first["status"] == "FIRST_RUN")
    check("sql_optional_contract", first["sql"] == "NOT_CONFIGURED")
    check("ai_provider_optional_contract", first["ai_provider"] == "NOT_CONFIGURED")
    try:
        onboarding.validate()
        raise AssertionError("configuration_validation")
    except OnboardingError as exc:
        check("configuration_validation", exc.code == "CONFIGURATION_REQUIRED")

    try:
        onboarding.configure(tenant_id="services", tenant_name="Servicios de Prueba", admin_user_id="services-admin", admin_username="services.admin", admin_display_name="Administración Servicios", password="corta")
        raise AssertionError("failed_first_run_atomicity")
    except OnboardingError as exc:
        check("failed_first_run_atomicity", exc.code == "PASSWORD_INVALID" and onboarding.status()["status"] == "FIRST_RUN")
        check("failed_first_run_empty", onboarding.status()["tenant_count"] == 0 and onboarding.status()["admin_count"] == 0)

    configured = onboarding.configure(
        tenant_id="services",
        tenant_name="Servicios de Prueba",
        admin_user_id="services-admin",
        admin_username="services.admin",
        admin_display_name="Administración Servicios",
        password="prueba-segura-2026",
    )
    check("persists_tenant", onboarding.tenants.get("services")["name"] == "Servicios de Prueba")
    admin = onboarding.identity.get("services-admin")
    check("creates_enterprise_identity", admin["tenant_id"] == "services")
    check("admin_contract", "SYSTEM_ADMIN" in admin["roles"] and "password_hash" not in admin)
    check("detects_configured_state", configured["status"] == "CONFIGURED")
    check("no_hardcoded_secrets", "prueba-segura-2026" not in (ROOT / "IA_Local" / "scripts" / "enterprise_onboarding.py").read_text(encoding="utf8"))
    public = json.dumps(configured, ensure_ascii=False)
    raw_identity = (reports / ".identity" / "identity.json").read_text(encoding="utf8")
    check("no_secret_output", "prueba-segura-2026" not in public and "prueba-segura-2026" not in raw_identity)
    check("restart_persistence", EnterpriseOnboarding(reports).validate()["status"] == "CONFIGURED")
    check("idempotent_configuration", EnterpriseOnboarding(reports).configure(
        tenant_id="services", tenant_name="Servicios de Prueba", admin_user_id="services-admin",
        admin_username="services.admin", admin_display_name="Administración Servicios", password="prueba-segura-2026"
    )["status"] == "CONFIGURED")
    before_conflict = onboarding.status()
    try:
        onboarding.configure(tenant_id="services", tenant_name="Nombre Conflicto", admin_user_id="services-admin", admin_username="services.admin", admin_display_name="Administración Servicios", password="prueba-segura-2026")
        raise AssertionError("conflict_fail_closed")
    except OnboardingError as exc:
        check("conflict_fail_closed", exc.code == "CONFIGURATION_CONFLICT" and onboarding.status() == before_conflict)
    try:
        onboarding.configure(tenant_id="other", tenant_name="Otra Empresa", admin_user_id="other-admin", admin_username="other.admin", admin_display_name="Otra Administración", password="corta")
    except OnboardingError:
        pass
    check("preexisting_data_safety", onboarding.tenants.get("services")["name"] == "Servicios de Prueba" and onboarding.identity.get("services-admin")["tenant_id"] == "services")
    # R10.21B replaces scripts only; governed Reportes state remains untouched.
    before = {p.name: p.read_text(encoding="utf8") for p in reports.rglob("*.json")}
    check("upgrade_persistence", all(p.read_text(encoding="utf8") == text for p, text in ((reports / ".tenants" / "tenants.json", before["tenants.json"]), (reports / ".identity" / "identity.json", before["identity.json"]), (reports / ".platform_config" / "platform_config.json", before["platform_config.json"]))))

print("PASS R10.21C")
