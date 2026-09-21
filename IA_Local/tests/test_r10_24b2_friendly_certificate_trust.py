from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "IA_Local" / "scripts" / "enterprise_ai" / "api.py"
UI = ROOT / "IA_Local" / "scripts" / "enterprise_ai" / "product_settings_ui.py"
GATEWAY = ROOT / "IA_Local" / "scripts" / "enterprise_sql_gateway.py"

def check(name, value):
    if not value:
        raise AssertionError(name)
    print("PASS", name)

api = API.read_text(encoding="utf-8")
ui = UI.read_text(encoding="utf-8")
gateway = GATEWAY.read_text(encoding="utf-8")

ast.parse(api)
ast.parse(ui)

check(
    "probe_request_accepts_trust",
    "trust_server_certificate: bool = False" in api,
)

probe = api.split(
    "/api/enterprise/data-connections/probe",
    1,
)[1].split(
    '@router.get("/api/enterprise/data-connections")',
    1,
)[0]

check(
    "probe_passes_trust_to_transient_profile",
    "body.trust_server_certificate" in probe,
)

create = api.split(
    '@router.post("/api/enterprise/data-connections")',
    1,
)[1].split(
    '@router.',
    1,
)[0]

check(
    "create_persists_trust",
    "trust_server_certificate=body.trust_server_certificate" in create,
)

check(
    "gateway_supports_trust",
    "trust_server_certificate:bool=False" in gateway
    and '"trust_server_certificate":bool(trust_server_certificate)' in gateway,
)

check(
    "friendly_checkbox_present",
    'id="connectionTrustCertificate"' in ui,
)

check(
    "friendly_copy_present",
    "Mi servidor usa un certificado interno" in ui,
)

check(
    "probe_sends_trust",
    'trust_server_certificate:q("connectionTrustCertificate").checked' in ui,
)

check(
    "save_sends_trust",
    ui.count(
        'trust_server_certificate:q("connectionTrustCertificate").checked'
    ) >= 2,
)

check(
    "trust_change_invalidates_probe",
    'q("connectionTrustCertificate").onchange=invalidateDataProbe' in ui,
)

check(
    "technical_admin_probe_not_used",
    '"/api/admin/sql/probe"' not in ui,
)

check(
    "tenant_identifier_not_exposed",
    "tenant_id" not in ui,
)

check(
    "password_not_persisted_client_side",
    'sessionStorage.setItem("connectionPassword"' not in ui
    and 'localStorage' not in ui,
)

print("PASS R10.24B2 FRIENDLY CERTIFICATE TRUST")
