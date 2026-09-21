from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "IA_Local" / "scripts" / "enterprise_ai" / "api.py"
UI = ROOT / "IA_Local" / "scripts" / "enterprise_ai" / "product_settings_ui.py"

api = API.read_text(encoding="utf-8")
ui = UI.read_text(encoding="utf-8")

def check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name)
    print("PASS", name)

start = api.index(
    '@router.post("/api/enterprise/readiness/validate")'
)
end = api.index(
    '@router.get("/api/enterprise/app-context")',
    start,
)
segment = api[start:end]

check(
    "single_commercial_validate_route",
    api.count(
        '@router.post("/api/enterprise/readiness/validate")'
    ) == 1,
)
check(
    "validate_requires_write_permission",
    'require_permission("config:write")' in segment,
)
check(
    "sql_configure_permission_preserved",
    '"sql:configure"' in segment,
)
check(
    "sql_read_permission_preserved",
    '"sql:read"' in segment,
)
check(
    "existing_sql_test_reused",
    "test_connection(" in segment,
)
check(
    "existing_sql_discovery_reused",
    "discover_schema(" in segment,
)
check(
    "existing_ai_provider_test_reused",
    ".test_provider(" in segment,
)
check(
    "ai_test_evidence_passed_to_readiness",
    "ai_test=ai_test" in segment,
)
check(
    "readiness_not_faked",
    'readiness.get("status")' in segment,
)
check(
    "no_ai_configuration_save_in_validator",
    "update_tenant(" not in segment,
)
check(
    "no_sql_configuration_save_in_validator",
    ".create(" not in segment
    and ".update(" not in segment,
)
check(
    "b4_posts_governed_validator",
    'pf("/api/enterprise/readiness/validate",{method:"POST"})'
    in ui,
)
check(
    "b4_enter_still_requires_ready",
    'overall==="READY"' in ui,
)

print("R10_24B4_COMMERCIAL_READINESS_VALIDATION=PASS")
