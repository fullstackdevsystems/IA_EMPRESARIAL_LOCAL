"""R10.22F.5C guided enterprise readiness UI contract."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

ADMIN = (
    ROOT
    / "IA_Local"
    / "scripts"
    / "enterprise_ai"
    / "admin_console.py"
)

text = ADMIN.read_text(
    encoding="utf-8"
)


def check(name, value):
    assert value, name
    print("PASS", name)


def function_source(name):
    match = re.search(
        rf"\b(?:async\s+)?function\s+"
        rf"{re.escape(name)}\s*\([^)]*\)\s*\{{",
        text,
    )

    assert match, (
        "missing_function:"
        + name
    )

    brace = text.find(
        "{",
        match.start(),
        match.end(),
    )

    depth = 0
    quote = None
    escape = False
    index = brace

    while index < len(text):
        char = text[index]

        if quote is not None:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
        else:
            if char in ("'", '"', "`"):
                quote = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1

                if depth == 0:
                    return text[
                        match.start():
                        index + 1
                    ]

        index += 1

    raise AssertionError(
        "unterminated_function:"
        + name
    )


check(
    "readiness_card_present",
    'id="cpReadinessCard"'
    in text
    and 'id="controlReadiness"'
    in text,
)

check(
    "guided_readiness_labels",
    all(
        status in text
        for status in (
            "CONFIGURED",
            "TESTED",
            "READY",
            "DEGRADED",
            "BLOCKED",
        )
    ),
)

check(
    "status_visual_contract",
    all(
        ".pill." + status
        in text
        for status in (
            "CONFIGURED",
            "TESTED",
            "READY",
            "DEGRADED",
            "BLOCKED",
        )
    ),
)

load = function_source(
    "controlLoadReadiness"
)

check(
    "readiness_get_uses_canonical_endpoint",
    "'/api/admin/tenants/'"
    in load
    and "'/readiness'"
    in load
    and "'GET'"
    in load,
)

check(
    "readiness_validation_uses_server_endpoint",
    "'/validate'"
    in load
    and "'POST'"
    in load,
)

check(
    "validation_sends_no_client_ai_evidence",
    "ai_test"
    not in load
    and "provider"
    not in load
    and "body:"
    not in load,
)

validate = function_source(
    "controlValidateReadiness"
)

check(
    "validate_delegates_server_side",
    "controlLoadReadiness"
    in validate
    and "true"
    in validate,
)

test_ai = function_source(
    "controlTestAi"
)

check(
    "unsaved_ai_test_is_tenant_contextual",
    "controlTenantId()"
    in test_ai
    and "tenant_id:tenant"
    in test_ai
    and "provider"
    in test_ai,
)

check(
    "unsaved_ai_test_not_readiness_certification",
    "/readiness"
    not in test_ai
    and "/validate"
    not in test_ai,
)

tenant_changed = function_source(
    "controlTenantChanged"
)

check(
    "tenant_change_refreshes_readiness",
    "controlLoadReadiness(false)"
    in tenant_changed,
)

save_ai = function_source(
    "controlSaveAi"
)

check(
    "ai_save_refreshes_readiness",
    "controlLoadReadiness(false)"
    in save_ai,
)

sql_run = function_source(
    "controlSqlRun"
)

check(
    "sql_operations_refresh_readiness",
    "controlLoadReadiness(false)"
    in sql_run,
)

load_cp = function_source(
    "loadControlPlane"
)

check(
    "control_plane_loads_readiness",
    "controlLoadReadiness(false)"
    in load_cp,
)

check(
    "readiness_permission_gate",
    text.count(
        'data-cp-permission="config:read"'
    ) >= 2
    and "if(!can('config:read'))"
    in load,
)

check(
    "session_storage_only",
    "sessionStorage"
    in text
    and "localStorage"
    not in text,
)

check(
    "no_token_in_url",
    "?token="
    not in text
    and "#token="
    not in text
    and "access_token="
    not in text,
)

render = function_source(
    "controlRenderReadiness"
)

check(
    "no_readiness_secret_rendering",
    all(
        secret
        not in render
        for secret in (
            "password",
            "secret_reference",
            "credential_ref",
            "token",
        )
    ),
)

check(
    "existing_control_plane_preserved",
    all(
        name in text
        for name in (
            "controlLoadTenants",
            "controlLoadUsers",
            "controlLoadSql",
            "controlLoadAi",
            "controlSaveAi",
            "controlTestAi",
        )
    ),
)

print(
    "PASS R10.22F.5C GUIDED READINESS UI"
)
