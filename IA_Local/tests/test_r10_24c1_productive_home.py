from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME_UI = ROOT / "IA_Local" / "scripts" / "enterprise_ai" / "product_ui.py"

text = HOME_UI.read_text(encoding="utf-8")

def check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name)
    print("PASS", name)

check("home_route_contract", 'href="/app"' in text)
check("assistant_action", 'href="/assistant"' in text)
check("analyze_action", 'href="/analyze"' in text)
check("data_action", 'href="/data"' in text)
check("reports_action", 'href="/reports"' in text)

check("connect_data_action", 'id="connect-data-action"' in text and 'href="/settings?section=data"' in text)
check("connect_data_capability_gate", "capabilities.configure_data" in text)

check("company_logo_in_header", 'id="company-logo"' in text and "logo_reference" in text and "renderCompanyLogo(company,companyName)" in text)

check("profile_access", 'id="profile-button"' in text and 'id="profile-panel"' in text and 'id="profile-name"' in text and 'id="profile-role"' in text)

check("settings_visibility_deterministic", "const canOpenSettings = Boolean(capabilities.settings);" in text)

check("friendly_ready_mapping", "if(status === 'READY') return ['Listo','ok'];" in text)
check("friendly_tested_mapping", "if(status === 'TESTED') return ['Verificado','ok'];" in text)
check("friendly_configured_mapping", "if(status === 'CONFIGURED') return ['Configurado','ok'];" in text)

check("app_context_reused", "/api/enterprise/app-context" in text)
check("session_storage_only", "sessionStorage" in text and "localStorage" not in text)
check("responsive_home", "@media(max-width:820px)" in text and "@media(max-width:620px)" in text)
check("touch_targets_preserved", "min-height:44px" in text)

check("no_internal_version_in_home", "V8.5.5" not in text)
check("no_localhost_port_in_home", "localhost:" not in text)

check(
    "mobile_user_meta_hook",
    '<div class="user-meta">' in text
    and ".user-meta{display:none}" in text,
)
check(
    "mobile_profile_button_no_wrap",
    "white-space:nowrap" in text,
)
check(
    "mobile_topbar_compact",
    ".topbar{padding:10px 14px;gap:10px}" in text,
)
check(
    "mobile_company_safe_shrink",
    ".companybox{min-width:0;flex:1}" in text
    and "text-overflow:ellipsis" in text,
)
check(
    "mobile_userbox_compact",
    ".userbox{gap:7px;flex:0 0 auto}" in text,
)
check(
    "mobile_profile_panel_width",
    "width:min(280px,calc(100vw - 28px))" in text,
)

check(
    "profile_css_declaration_integrity",
    "font-weight:700;" in text
    and "white-space:nowrap;" in text,
)
print("R10_24C1_PRODUCTIVE_HOME=PASS")
