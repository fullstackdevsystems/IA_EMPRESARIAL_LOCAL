"""RC.9C.5 - upgrade VERSION identity transaction regression."""

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


ck(
    "version_is_managed_root_file",
    r"'IA_Local\VERSION.txt'"
    in text,
)

ck(
    "scripts_upgrade_still_present",
    "INSTALL MODE: UPGRADE"
    in text
    and "IA_Local/scripts/*"
    in text,
)

ck(
    "stage_parent_created",
    "$stagedParent = Split-Path"
    in text
    and "New-Item `"
    in text,
)

ck(
    "previous_parent_created",
    "$previousParent = Split-Path"
    in text,
)

ck(
    "live_parent_created",
    "$liveParent = Split-Path"
    in text,
)

ck(
    "root_transaction_staging_preserved",
    "$stagedRoot = Join-Path"
    in text
    and "$previousRoot = Join-Path"
    in text,
)

ck(
    "rollback_preserved",
    "previous managed root files and scripts restored"
    in text,
)

ck(
    "persistent_runtime_not_added_to_root_transaction",
    "'IA_Local\\\\data\\\\enterprise'"
    not in text
    and "'IA_Local\\\\workspace\\\\Conocimiento'"
    not in text
    and "'IA_Local\\\\config'"
    not in text,
)

root_block = re.search(
    r"\$rootFiles\s*=\s*@\((.*?)\)\s*",
    text,
    re.S,
)

ck(
    "root_files_block_found",
    root_block is not None,
)

if root_block is not None:
    block = root_block.group(1)

    ck(
        "version_exactly_once_in_root_files",
        block.count(
            r"IA_Local\VERSION.txt"
        )
        == 1,
    )

if not all(checks):
    raise SystemExit(1)

print(
    "\nPASS RC.9C.5 UPGRADE VERSION IDENTITY REGRESSION"
)
