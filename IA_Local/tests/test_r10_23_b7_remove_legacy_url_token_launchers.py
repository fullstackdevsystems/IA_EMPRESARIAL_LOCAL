from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]

LOCAL = ROOT / "IA_Local"

ADMIN_BAT = (
    LOCAL
    / "ABRIR_ADMIN_MEMORIA_RAG.bat"
)

ASSISTANT_BAT = (
    LOCAL
    / "ABRIR_ASISTENTE.bat"
)

STARTER = (
    LOCAL
    / "scripts"
    / "Iniciar.ps1"
)

API = (
    LOCAL
    / "scripts"
    / "enterprise_ai"
    / "api.py"
)

GUIDE = (
    LOCAL
    / "GUIA_PRUEBAS_MEMORIA_RAG_V8.md"
)

STRUCTURE = (
    LOCAL
    / "ESTRUCTURA.txt"
)


def text(path: Path) -> str:
    return path.read_text(
        encoding="utf-8-sig"
    )


def check(
    name: str,
    condition: bool,
) -> None:
    assert condition, name
    print(
        "PASS",
        name,
    )


admin = text(
    ADMIN_BAT
)

assistant = text(
    ASSISTANT_BAT
)

starter = text(
    STARTER
)

api = text(
    API
)

guide = text(
    GUIDE
)

structure = text(
    STRUCTURE
)


check(
    "ADMIN_LAUNCHER_NO_LOCAL_TOKEN",
    (
        "local-user.token"
        not in admin
        and "#token="
        not in admin
        and "?token="
        not in admin
    ),
)

check(
    "ADMIN_LAUNCHER_OPENS_UNIFIED_ROUTE",
    (
        "http://127.0.0.1:8090/admin"
        in admin
    ),
)

check(
    "ASSISTANT_LAUNCHER_NO_LOCAL_TOKEN",
    (
        "local-user.token"
        not in assistant
        and "#token="
        not in assistant
        and "?token="
        not in assistant
    ),
)

check(
    "ASSISTANT_LAUNCHER_OPENS_LOGIN_ROUTE",
    (
        "http://127.0.0.1:8090/assistant"
        in assistant
    ),
)

check(
    "STARTER_NO_URL_TOKEN",
    (
        "#token="
        not in starter
        and "?token="
        not in starter
        and (
            "Get-Content $EnterpriseToken"
            not in starter
        )
    ),
)

check(
    "STARTER_OPENS_ASSISTANT_LOGIN",
    (
        'Start-Process "http://127.0.0.1:8090/assistant"'
        in starter
    ),
)

route = re.search(
    (
        r'@router\.get\("/admin",'
        r'[\s\S]{0,300}?'
        r'def\s+admin_page\(\):'
        r'[\s\S]{0,120}?'
        r'return\s+([A-Z_]+)'
    ),
    api,
)

check(
    "ACTIVE_ADMIN_REMAINS_UNIFIED",
    (
        route is not None
        and route.group(1)
        == "UNIFIED_ADMIN_HTML"
    ),
)

legacy_admin_definitions = re.findall(
    r"(?m)^\s*ADMIN_HTML\s*=",
    api,
)

check(
    "LEGACY_ADMIN_HTML_NOT_REACTIVATED",
    (
        len(
            legacy_admin_definitions
        )
        == 1
    ),
)

check(
    "GUIDE_USES_ENTERPRISE_LOGIN",
    (
        "http://127.0.0.1:8090/assistant"
        in guide
        and "http://127.0.0.1:8090/admin"
        in guide
        and "login empresarial"
        in guide
        and "#token="
        not in guide
    ),
)

check(
    "STRUCTURE_DESCRIBES_ENTERPRISE_LOGIN",
    (
        structure.count(
            "login empresarial"
        )
        >= 2
    ),
)

runtime_exposure = (
    "#token="
    in admin
    or "#token="
    in assistant
    or "#token="
    in starter
)

check(
    "LEGACY_URL_TOKEN_RUNTIME_EXPOSURE_REMOVED",
    not runtime_exposure,
)

print(
    "PASS R10.23-B.7"
)
