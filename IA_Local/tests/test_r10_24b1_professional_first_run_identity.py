"""R10.24B1 professional first-run identity and branding regression."""

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from enterprise_onboarding import EnterpriseOnboarding, OnboardingError


def check(name, value):
    if not value:
        raise AssertionError(name)
    print("PASS", name)


source = (SCRIPTS / "analizador_universal.py").read_text(encoding="utf-8")

check(
    "professional_first_run_fields",
    all(
        marker in source
        for marker in (
            'id="ia-first-run-panel"',
            'id="ia-setup-business-type"',
            'id="ia-setup-accent"',
            'id="ia-setup-theme"',
            "Paso 1 de 4",
            "Tipo de empresa",
            "Color principal",
            "Tema visual",
        )
    ),
)

check(
    "professional_progress_contract",
    all(
        label in source
        for label in (
            "<span>Empresa</span>",
            "<span>Datos</span>",
            "<span>IA</span>",
            "<span>Listo</span>",
            'aria-current="step"',
        )
    ),
)

check(
    "bootstrap_profile_payload_contract",
    all(
        token in source
        for token in (
            "business_type:",
            "accent_color:",
            "theme:",
            'data.next || ' + "'/settings?setup=data'",
            '"/settings?setup=data"',
        )
    ),
)

first_run_html = source.split(
    '_ANALYZE_LOGIN_GATE = r"""',
    1,
)[1].split(
    '_ANALYZE_LOGIN_SCRIPT = r"""',
    1,
)[0].lower()

check(
    "first_run_has_no_technical_jargon",
    all(
        forbidden not in first_run_html
        for forbidden in (
            "tenant",
            "rag",
            "renderer",
            "sha-256",
            "odbc",
            "system_admin",
        )
    ),
)

with tempfile.TemporaryDirectory() as temporary:
    reports = Path(temporary) / "IA_Local" / "Reportes"
    onboarding = EnterpriseOnboarding(reports)

    try:
        onboarding.configure(
            tenant_id="empresa-demo",
            tenant_name="Empresa Demo",
            admin_user_id="admin",
            admin_username="admin",
            admin_display_name="Administrador",
            password="prueba-segura-b1-2026",
            business_type="NoPermitido",
            accent_color="#123456",
            theme="professional-light",
        )
        raise AssertionError("invalid_profile_not_blocked")
    except OnboardingError as exc:
        check(
            "invalid_profile_is_atomic",
            exc.code == "CONFIG_INVALID"
            and onboarding.status()["status"] == "FIRST_RUN"
            and onboarding.status()["tenant_count"] == 0
            and onboarding.status()["admin_count"] == 0,
        )

    configured = onboarding.configure(
        tenant_id="empresa-demo",
        tenant_name="Empresa Demo",
        admin_user_id="admin",
        admin_username="admin",
        admin_display_name="Administrador",
        password="prueba-segura-b1-2026",
        business_type="Servicios",
        accent_color="#123456",
        theme="professional-dark",
    )

    public = onboarding.platform.public_effective_config(
        "empresa-demo"
    )

    check(
        "company_admin_configured",
        configured["status"] == "CONFIGURED"
        and onboarding.status()["tenant_count"] == 1
        and onboarding.status()["admin_count"] == 1,
    )

    check(
        "business_type_persisted",
        public["business_type"] == "Servicios",
    )

    check(
        "theme_persisted",
        public["theme"] == "professional-dark",
    )

    check(
        "accent_persisted",
        public["accent_color"] == "#123456",
    )

    check(
        "company_name_persisted",
        public["display_name"] == "Empresa Demo",
    )

    restarted = EnterpriseOnboarding(reports)
    restarted_public = restarted.platform.public_effective_config(
        "empresa-demo"
    )

    check(
        "profile_survives_restart",
        restarted.validate()["status"] == "CONFIGURED"
        and restarted_public["business_type"] == "Servicios"
        and restarted_public["theme"] == "professional-dark"
        and restarted_public["accent_color"] == "#123456",
    )

print("PASS R10.24B1 PROFESSIONAL FIRST-RUN IDENTITY")
