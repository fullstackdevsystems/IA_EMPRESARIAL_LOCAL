from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"

universal = (
    SCRIPTS / "analizador_universal.py"
).read_text(encoding="utf-8")

settings = (
    SCRIPTS
    / "enterprise_ai"
    / "product_settings_ui.py"
).read_text(encoding="utf-8")


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print("PASS", name)


check(
    "b1_continues_to_data_step",
    universal.count("/settings?setup=data") >= 2,
)

check(
    "step_2_progress_present",
    "Primera configuración · Paso 2 de 4" in settings
    and "<span>Empresa</span>" in settings
    and "<span>Datos</span>" in settings
    and "<span>IA</span>" in settings
    and "<span>Listo</span>" in settings,
)

check(
    "data_step_is_active",
    'class="first-run-step active" aria-current="step"'
    in settings
    and "<strong>2</strong><span>Datos</span>" in settings,
)

check(
    "guided_connection_fields",
    'id="connectionName"' in settings
    and 'id="connectionServer"' in settings
    and 'id="connectionDatabase"' in settings
    and 'id="connectionAccess"' in settings
    and 'id="connectionUsername"' in settings
    and 'id="connectionPassword"' in settings,
)

check(
    "friendly_auth_choices",
    "Usar acceso de Windows" in settings
    and "Usar usuario y contraseña" in settings,
)

check(
    "commercial_probe_auth_contract",
    "authentication:access" in settings,
)

check(
    "safe_probe_required",
    'id="probeConnection"' in settings
    and "Probar conexión y buscar tablas" in settings
    and '"/api/enterprise/data-connections/probe"' in settings
    and "DATA_PROBE_VALID" in settings,
)

check(
    "visual_source_selection",
    'id="connectionSourcePicker"' in settings
    and 'makeElement("label","source-option")' in settings
    and 'id="selectAllSources"' in settings
    and "selectedProbeSources()" in settings,
)

check(
    "allowlist_is_derived_not_typed",
    'id="connectionSources" type="hidden"' in settings
    and "allowed_sources:sources" in settings,
)

check(
    "probe_invalidated_on_connection_change",
    '"connectionServer"' in settings
    and '"connectionDatabase"' in settings
    and '"connectionUsername"' in settings
    and '"connectionPassword"' in settings
    and 'addEventListener("input",invalidateDataProbe)' in settings,
)

check(
    "commercial_create_api_reused",
    '"/api/enterprise/data-connections"' in settings,
)

check(
    "persisted_connection_is_verified",
    '"/test"' in settings
    and "tested.verified!==true" in settings,
)

check(
    "continues_to_ai_step",
    settings.count("/settings?setup=ai") >= 2,
)

check(
    "setup_can_be_deferred",
    'id="skipDataSetup"' in settings
    and "Configurar después" in settings,
)

guided_start = settings.index(
    '<div id="firstRunDataGuide"'
)
guided_end = settings.index(
    '<div id="connectionsList"',
    guided_start,
)
guided_html = settings[
    guided_start:guided_end
].lower()

for forbidden in (
    "allowlist",
    "secret_reference",
    "credential_ref",
    "odbc",
    "timeout_seconds",
    "context_window",
    "sha-256",
):
    check(
        "guided_html_hides_" + forbidden.replace("-", "_"),
        forbidden not in guided_html,
    )

check(
    "password_not_client_persisted",
    "localStorage" not in guided_html
    and "sessionStorage.setItem("
       '"connectionPassword"' not in settings
    and "sessionStorage.setItem("
       "'connectionPassword'" not in settings,
)

check(
    "existing_settings_data_api_preserved",
    'async function loadConnections()' in settings
    and 'async function toggleConnection' in settings
    and 'async function testConnection' in settings,
)

check(
    "responsive_guided_data_contract",
    "@media(max-width:760px)" in settings
    and ".first-run-progress" in settings
    and ".source-toolbar" in settings,
)

print(
    "PASS R10.24B2 GUIDED DATA CONNECTION WIZARD"
)

check(
    "first_run_setup_hides_settings_menu",
    'html.first-run-setup .company-menu{display:none!important}'
    in settings,
)

check(
    "first_run_setup_expands_active_panel",
    'html.first-run-setup #dataPanel,html.first-run-setup #aiPanel'
    in settings
    and 'grid-column:1/-1!important'
    in settings,
)

check(
    "first_run_setup_class_applied",
    settings.count(
        'document.documentElement.classList.add("first-run-setup")'
    ) >= 2,
)

check(
    "dark_first_run_contrast_contract",
    'html[data-theme="professional-dark"] .first-run-data-guide'
    in settings
    and 'color:#f8fafc'
    in settings
    and 'color:#cbd5e1'
    in settings,
)

print(
    "PASS R10.24B2 FIRST-RUN VISUAL CORRECTION"
)