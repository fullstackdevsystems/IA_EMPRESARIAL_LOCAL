from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "InstallerR1020C1.ps1"

text = INSTALLER.read_text(
    encoding="utf-8-sig",
)

failures = []


def check(name, value):
    ok = bool(value)
    print(("PASS" if ok else "FAIL"), name)

    if not ok:
        failures.append(name)


# -------------------------------------------------
# Existing commercial root deployment contract
# -------------------------------------------------

required_root_files = (
    "OperarIA.ps1",
    "LEEME_INSTALACION_LIMPIA.txt",
    "MANIFEST_SHA256.json",
    "RELEASE_METADATA.json",
    "InstallerR1020C1.ps1",
    "InstalarLimpio.ps1",
    "INSTALAR_IA_EMPRESARIAL_LOCAL.bat",
    "ValidarInstalador.ps1",
)

for name in required_root_files:
    check(
        f"root_file_declared_{name}",
        name in text,
    )


# -------------------------------------------------
# Scripts upgrade is already transactional
# -------------------------------------------------

check(
    "scripts_have_previous_backup",
    "previous_scripts" in text,
)

check(
    "scripts_have_rollback",
    (
        "previousScripts" in text
        and "catch" in text
        and (
            "Move-Item $previousScripts" in text
            or (
                "function Restore-PreviousManagedScripts" in text
                and text.count(
                    "Restore-PreviousManagedScripts"
                ) >= 2
            )
        )
    ),
)


# -------------------------------------------------
# Root update must ALSO be transactional
# -------------------------------------------------

check(
    "root_upgrade_has_staging",
    bool(
        re.search(
            r"stagedRoot|staged_root|new_root",
            text,
            re.IGNORECASE,
        )
    ),
)

check(
    "root_upgrade_has_previous_backup",
    bool(
        re.search(
            r"previousRoot|previous_root|previous_root_files",
            text,
            re.IGNORECASE,
        )
    ),
)

check(
    "root_upgrade_has_rollback",
    bool(
        re.search(
            r"previousRoot|previous_root|previous_root_files",
            text,
            re.IGNORECASE,
        )
        and re.search(
            r"catch",
            text,
            re.IGNORECASE,
        )
    ),
)


# -------------------------------------------------
# Critical wrapper must participate in root rollback
# -------------------------------------------------

check(
    "operaria_is_managed_root_file",
    "OperarIA.ps1" in text,
)

check(
    "operaria_not_scripts_only",
    (
        "'OperarIA.ps1'" in text
        and "rootFiles" in text
    ),
)


# -------------------------------------------------
# Persistent state must never be root replacement
# -------------------------------------------------

for forbidden in (
    "workspace",
    "data",
    "config",
):
    pattern = (
        r"\$rootFiles\s*=\s*@\("
        r"[\s\S]*?"
        + re.escape(f"'{forbidden}'")
        + r"[\s\S]*?\)"
    )

    check(
        f"persistent_{forbidden}_not_root_replaced",
        not bool(
            re.search(
                pattern,
                text,
                re.IGNORECASE,
            )
        ),
    )


# -------------------------------------------------
# Upgrade failure message should promise full
# managed-runtime rollback, not scripts only.
# -------------------------------------------------

check(
    "failure_contract_not_scripts_only",
    "previous scripts restored" not in text,
)


if failures:
    raise AssertionError(
        "RC.3C expected transactional root upgrade "
        "contract failures: "
        + ", ".join(failures)
    )

print(
    "PASS R10.22 RC.3C "
    "TRANSACTIONAL ROOT UPGRADE CONTRACT"
)
