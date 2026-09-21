from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

API = (
    ROOT
    / "IA_Local"
    / "scripts"
    / "enterprise_ai"
    / "api.py"
)

SETTINGS = (
    ROOT
    / "IA_Local"
    / "scripts"
    / "enterprise_ai"
    / "product_settings_ui.py"
)


def check(name, condition):
    if not condition:
        raise AssertionError(name)

    print(
        "PASS",
        name,
    )


api = API.read_text(
    encoding="utf-8"
)

settings = SETTINGS.read_text(
    encoding="utf-8"
)

ast.parse(api)
ast.parse(settings)


route_marker = (
    '@router.post(\n'
    '        "/api/enterprise/data-connections/probe"'
)

check(
    "commercial_probe_route",
    route_marker
    in api,
)

route = api.split(
    route_marker,
    1,
)[1].split(
    '@router.get("/api/enterprise/data-connections")',
    1,
)[0]


check(
    "commercial_probe_permission",
    'require_permission('
    in route
    and '"sql:configure"'
    in route,
)

check(
    "scope_from_authenticated_principal",
    "data_connection_scope("
    in route
    and "principal"
    in route,
)

check(
    "no_browser_tenant_parameter",
    "tenant_id"
    not in route,
)

check(
    "no_browser_company_parameter",
    "body.company_id"
    not in route,
)

check(
    "safe_transient_profile_reused",
    "build_transient_sql_probe_profile"
    in route,
)

check(
    "safe_metadata_probe_reused",
    "probe_sql_server_metadata"
    in route,
)

check(
    "request_local_secret_provider",
    "class _RequestLocalSecretProvider"
    in route
    and "transient_backend.clear()"
    in route,
)

check(
    "pre_save_probe_does_not_register_profile",
    ".register("
    not in route,
)

check(
    "commercial_auth_values",
    '"windows"'
    in route
    and '"password"'
    in route,
)

check(
    "product_ui_uses_commercial_probe",
    '"/api/enterprise/data-connections/probe"'
    in settings,
)

check(
    "product_ui_does_not_call_admin_probe",
    '"/api/admin/sql/probe"'
    not in settings,
)

check(
    "product_ui_sends_commercial_auth",
    "authentication:access"
    in settings,
)

check(
    "product_ui_has_no_tenant_id",
    "tenant_id"
    not in settings,
)

check(
    "password_not_client_persisted",
    'localStorage'
    not in settings
    and 'sessionStorage.setItem("connectionPassword"'
    not in settings,
)

print(
    "PASS R10.24B2 COMMERCIAL PRE-SAVE SQL PROBE"
)
