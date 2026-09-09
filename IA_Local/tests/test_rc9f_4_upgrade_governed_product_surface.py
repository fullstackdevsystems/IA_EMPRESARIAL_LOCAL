"""RC.9F.4 governed product upgrade surface regression."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

INSTALLER = (
    ROOT
    / "InstallerR1020C1.ps1"
)

text = INSTALLER.read_text(
    encoding="utf-8",
)

checks = []


def ck(name, condition):
    condition = bool(condition)

    print(
        "PASS" if condition else "FAIL",
        name,
    )

    checks.append(condition)


root_block = re.search(
    r"\$rootFiles\s*=\s*@\((.*?)\)\s*",
    text,
    re.S,
)

ck(
    "managed_block_found",
    root_block is not None,
)

block = (
    root_block.group(1)
    if root_block is not None
    else ""
)

required = [
    "BuildReleaseR1021A.ps1",
    r"IA_Local\VERSION.txt",
    r"IA_Local\requirements-local.txt",
]

for item in required:
    ck(
        "managed_" + item.replace(
            "\\",
            "_",
        ).replace(
            ".",
            "_",
        ),
        block.count(item) == 1,
    )

ck(
    "scripts_transaction_preserved",
    "IA_Local/scripts/*" in text,
)

ck(
    "nested_stage_parent_preserved",
    "$stagedParent = Split-Path"
    in text,
)

ck(
    "nested_previous_parent_preserved",
    "$previousParent = Split-Path"
    in text,
)

ck(
    "nested_live_parent_preserved",
    "$liveParent = Split-Path"
    in text,
)

ck(
    "rollback_preserved",
    "previous managed root files and scripts restored"
    in text,
)

for forbidden in [
    r"IA_Local\data\enterprise",
    r"IA_Local\workspace\Conocimiento",
    r"IA_Local\workspace\Reportes\.tenants",
    r"IA_Local\workspace\Reportes\.identity",
    r"IA_Local\workspace\Reportes\.platform_config",
    r"IA_Local\workspace\Reportes\.sql_connections",
    r"IA_Local\workspace\Reportes\.registry",
    r"IA_Local\config\enterprise.secret",
    r"IA_Local\config\local-user.token",
]:
    ck(
        "persistent_not_managed_"
        + forbidden.replace(
            "\\",
            "_",
        ).replace(
            ".",
            "_",
        ),
        forbidden not in block,
    )

ck(
    "pip_uses_verified_package_requirements",
    "-r (Join-Path $source 'requirements-local.txt')"
    in text,
)

ck(
    "pip_does_not_use_live_runtime_requirements",
    "-r (Join-Path $RuntimeRoot 'requirements-local.txt')"
    not in text,
)

if not all(checks):
    raise SystemExit(1)

print(
    "\nPASS RC.9F.4 GOVERNED PRODUCT UPGRADE SURFACE"
)
