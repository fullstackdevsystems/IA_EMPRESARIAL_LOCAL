from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "InstallerR1020C1.ps1"

text = INSTALLER.read_text(
    encoding="utf-8-sig"
)

failures = []


def check(name, value):
    ok = bool(value)
    print(("PASS" if ok else "FAIL"), name)

    if not ok:
        failures.append(name)


def extract_between(start, end):
    a = text.find(start)
    b = text.find(end, a + len(start))

    if a < 0 or b < 0:
        return ""

    return text[a:b]


check(
    "has_full_span_script_restore_helper",
    bool(
        re.search(
            r"function\s+Restore-PreviousManagedScripts\b",
            text,
            re.IGNORECASE,
        )
    ),
)

check(
    "has_script_backup_cleanup_helper",
    bool(
        re.search(
            r"function\s+Cleanup-ManagedScriptBackup\b",
            text,
            re.IGNORECASE,
        )
    ),
)

upgrade_block = extract_between(
    "else {",
    "foreach ($d in 'config'",
)

check(
    "upgrade_has_script_backup",
    "$backupRoot =" in upgrade_block
    and "$previousScripts =" in upgrade_block,
)

check(
    "upgrade_has_no_premature_backup_finally",
    not bool(
        re.search(
            r"finally\s*\{\s*"
            r"Remove-Item\s+\$backupRoot",
            upgrade_block,
            re.IGNORECASE | re.DOTALL,
        )
    ),
)

check(
    "initial_script_failure_restores_scripts",
    "Restore-PreviousManagedScripts"
    in upgrade_block
    and "Cleanup-ManagedScriptBackup"
    in upgrade_block,
)


venv_block = extract_between(
    "if(-not(Test-Path $vp)){",
    "& $vp -m pip install",
)

check(
    "venv_failure_restores_scripts",
    "Restore-PreviousManagedScripts"
    in venv_block
    and "Cleanup-ManagedScriptBackup"
    in venv_block,
)


pip_start = text.find("& $vp -m pip install")
health_start = text.find("$RuntimeScripts =")

pip_block = (
    text[pip_start:health_start]
    if pip_start >= 0 and health_start > pip_start
    else ""
)

check(
    "dependency_failure_restores_scripts",
    "dependency install failed" in pip_block
    and "Restore-PreviousManagedScripts"
    in pip_block
    and "Cleanup-ManagedScriptBackup"
    in pip_block,
)


health_start = text.find("if($healthExit){")
root_start = text.find(
    "# Managed root files are deployed"
)

health_block = (
    text[health_start:root_start]
    if health_start >= 0 and root_start > health_start
    else ""
)

check(
    "health_failure_restores_scripts",
    "health imports failed" in health_block
    and "Restore-PreviousManagedScripts"
    in health_block
    and "Cleanup-ManagedScriptBackup"
    in health_block,
)


root_catch_start = text.find(
    "catch {",
    text.find("$rootUpdateBackup ="),
)

root_finally = text.find(
    "finally {",
    root_catch_start,
)

root_catch = (
    text[root_catch_start:root_finally]
    if root_catch_start >= 0
    and root_finally > root_catch_start
    else ""
)

check(
    "root_failure_restores_root_files",
    "previous managed root files"
    in root_catch,
)

check(
    "root_failure_also_restores_scripts",
    "Restore-PreviousManagedScripts"
    in root_catch
    and "Cleanup-ManagedScriptBackup"
    in root_catch,
)


root_transaction_position = text.find(
    "$rootUpdateBackup ="
)

success_cleanup_position = text.find(
    "Cleanup-ManagedScriptBackup",
    root_finally,
)

check(
    "successful_cleanup_occurs_after_root_transaction",
    root_transaction_position >= 0
    and root_finally >= 0
    and success_cleanup_position > root_finally,
)


restore_move = bool(
    re.search(
        r"Move-Item\s+`\s*"
        r"\$previousScripts\s+`\s*"
        r"\(Join-Path\s+\$RuntimeRoot\s+'scripts'\)",
        text,
        re.IGNORECASE,
    )
)

check(
    "restore_helper_moves_previous_scripts_back",
    restore_move,
)


check(
    "full_span_failure_phases_governed",
    all(
        marker in text
        for marker in (
            "venv creation failed",
            "dependency install failed",
            "health imports failed",
            "root deployment failed",
        )
    ),
)


if failures:
    raise AssertionError(
        "RC.6F managed upgrade transaction failures: "
        + ", ".join(failures)
    )

print(
    "PASS R10.22 RC.6F "
    "FULL MANAGED UPGRADE TRANSACTION SPAN"
)
