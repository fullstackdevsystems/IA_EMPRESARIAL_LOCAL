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


def pos(fragment):
    return text.find(fragment)


# -------------------------------------------------
# Baseline contracts.
# -------------------------------------------------

check(
    "fresh_mode_exists",
    "INSTALL MODE: FRESH" in text,
)

check(
    "release_metadata_is_managed_root_file",
    "'RELEASE_METADATA.json'" in text
    and "$rootFiles" in text,
)

check(
    "health_imports_analyzer",
    "import analizador_universal" in text,
)

check(
    "root_transaction_exists",
    "$rootUpdateBackup =" in text,
)


# -------------------------------------------------
# Fresh install must bootstrap canonical metadata
# before analyzer health import.
# -------------------------------------------------

fresh_start = pos("INSTALL MODE: FRESH")
health_start = pos("$HealthScript =")
root_txn = pos("$rootUpdateBackup =")


bootstrap_markers = (
    "FRESH_METADATA_BOOTSTRAP",
    "Bootstrap-FreshReleaseMetadata",
)

bootstrap_positions = [
    pos(marker)
    for marker in bootstrap_markers
    if pos(marker) >= 0
]

bootstrap_before_health = any(
    p > fresh_start and p < health_start
    for p in bootstrap_positions
)

check(
    "fresh_metadata_bootstrap_exists_before_health",
    bootstrap_before_health,
)


# -------------------------------------------------
# Bootstrap must source metadata from verified
# package authority and write to ProductRoot.
# -------------------------------------------------

bootstrap_contract = bool(
    re.search(
        r"RELEASE_METADATA\.json",
        text,
        re.IGNORECASE,
    )
    and re.search(
        r"\$ProductRoot",
        text,
        re.IGNORECASE,
    )
)

check(
    "metadata_bootstrap_uses_product_root",
    bootstrap_contract,
)


# -------------------------------------------------
# Health must still occur before the full managed
# root transaction. We are NOT moving the complete
# root deployment earlier.
# -------------------------------------------------

check(
    "full_root_transaction_remains_after_health",
    (
        health_start >= 0
        and root_txn > health_start
    ),
)


# -------------------------------------------------
# Upgrade behavior must remain transactional and
# must not depend on the fresh-only bootstrap.
# -------------------------------------------------

check(
    "upgrade_script_backup_contract_preserved",
    "$previousScripts" in text
    and "Restore-PreviousManagedScripts" in text,
)

check(
    "root_rollback_contract_preserved",
    "$previousRoot" in text
    and "previous managed root files and scripts restored"
    in text,
)


# -------------------------------------------------
# Bootstrap must be explicitly fresh-scoped.
# -------------------------------------------------

fresh_branch_start = text.find(
    "if (-not $existingInstall)"
)

upgrade_branch_start = text.find(
    "else {",
    fresh_branch_start,
)

fresh_branch = (
    text[fresh_branch_start:upgrade_branch_start]
    if fresh_branch_start >= 0
    and upgrade_branch_start > fresh_branch_start
    else ""
)

check(
    "fresh_bootstrap_is_scoped_to_fresh_branch",
    (
        "FRESH_METADATA_BOOTSTRAP" in fresh_branch
        or "Bootstrap-FreshReleaseMetadata"
        in fresh_branch
    ),
)


# -------------------------------------------------
# The bootstrap is temporary. It must be removed
# after successful health and before the full root
# transaction, and failure paths must also clean it.
# -------------------------------------------------

cleanup_helper = "function Cleanup-FreshMetadataBootstrap"

check(
    "fresh_metadata_cleanup_helper_exists",
    cleanup_helper in text,
)

health_fail = text.find(
    "Stop-Install 'health imports failed'"
)

cleanup_after_health = text.find(
    "Cleanup-FreshMetadataBootstrap",
    health_fail + 1,
)

check(
    "fresh_metadata_removed_before_root_transaction",
    (
        health_fail >= 0
        and cleanup_after_health > health_fail
        and root_txn > cleanup_after_health
    ),
)

full_cleanup_helper = (
    "function Cleanup-FreshInstallArtifacts"
)

full_cleanup_start = text.find(
    full_cleanup_helper
)

restore_helper_start = text.find(
    "function Restore-PreviousManagedScripts",
    full_cleanup_start + 1,
)

full_cleanup_block = (
    text[
        full_cleanup_start:restore_helper_start
    ]
    if (
        full_cleanup_start >= 0
        and restore_helper_start
        > full_cleanup_start
    )
    else ""
)

check(
    "fresh_metadata_cleanup_covers_failure_paths",
    (
        cleanup_helper in text
        and full_cleanup_start >= 0
        and "Cleanup-FreshMetadataBootstrap"
        in full_cleanup_block
        and text.count(
            "Cleanup-FreshInstallArtifacts"
        ) >= 5
        and "venv creation failed" in text
        and "dependency install failed" in text
        and "health imports failed" in text
        and "fresh payload deployment failed"
        in text
    ),
)


if failures:
    raise AssertionError(
        "RC.6K.2 fresh metadata bootstrap failures: "
        + ", ".join(failures)
    )

print(
    "PASS R10.22 RC.6K.2 "
    "FRESH METADATA BOOTSTRAP CONTRACT"
)
