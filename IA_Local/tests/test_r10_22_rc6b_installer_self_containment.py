from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

INSTALLER = ROOT / "InstallerR1020C1.ps1"
BAT = ROOT / "INSTALAR_IA_EMPRESARIAL_LOCAL.bat"

failures = []


def check(name, value):
    ok = bool(value)
    print(("PASS" if ok else "FAIL"), name)

    if not ok:
        failures.append(name)


installer = INSTALLER.read_text(
    encoding="utf-8-sig"
)

bat = BAT.read_text(
    encoding="utf-8-sig"
)


# -------------------------------------------------
# 1. Installed commercial root must be self-contained.
# -------------------------------------------------

root_files_match = re.search(
    r"\$rootFiles\s*=\s*@\((.*?)\)",
    installer,
    re.DOTALL | re.IGNORECASE,
)

root_files_text = (
    root_files_match.group(1)
    if root_files_match
    else ""
)

check(
    "root_files_block_exists",
    root_files_match is not None,
)

check(
    "validator_is_managed_root_file",
    "ValidarInstalador.ps1" in root_files_text,
)

check(
    "bat_is_managed_root_file",
    "INSTALAR_IA_EMPRESARIAL_LOCAL.bat"
    in root_files_text,
)

check(
    "wrapper_is_managed_root_file",
    "InstalarLimpio.ps1"
    in root_files_text,
)

check(
    "installer_is_managed_root_file",
    "InstallerR1020C1.ps1"
    in root_files_text,
)


# -------------------------------------------------
# 2. BAT dependency must be satisfiable after install.
# -------------------------------------------------

check(
    "bat_uses_validator",
    "ValidarInstalador.ps1" in bat,
)

check(
    "bat_validator_dependency_is_deployed",
    (
        "ValidarInstalador.ps1" in bat
        and "ValidarInstalador.ps1"
        in root_files_text
    ),
)


# -------------------------------------------------
# 3. Installer startup identity must be metadata-driven.
# -------------------------------------------------

check(
    "installer_reads_release_metadata",
    "RELEASE_METADATA.json" in installer
    and "$releaseMetadata" in installer,
)

check(
    "installer_uses_dynamic_release",
    "$release" in installer
    and "$channel" in installer
    and "$productVersion" in installer,
)

check(
    "installer_has_no_stale_r10_21f_startup_label",
    "R10.21F installer starting"
    not in installer,
)

check(
    "installer_has_generic_dynamic_startup_label",
    (
        'installer starting - product '
        in installer.lower()
        and "$release" in installer
        and "$channel" in installer
    ),
)


# -------------------------------------------------
# 4. Commercial BAT must not advertise obsolete R7.
# -------------------------------------------------

check(
    "bat_has_no_r7_branding",
    re.search(
        r"\bR7\b",
        bat,
        re.IGNORECASE,
    )
    is None,
)

check(
    "bat_has_no_legacy_fixed_release_branding",
    re.search(
        r"\bR10\.21F\b",
        bat,
        re.IGNORECASE,
    )
    is None,
)

check(
    "bat_keeps_installer_entrypoints",
    (
        "ValidarInstalador.ps1" in bat
        and "InstalarLimpio.ps1" in bat
    ),
)


if failures:
    raise AssertionError(
        "RC.6B expected current commercial "
        "installer contract failures: "
        + ", ".join(failures)
    )

print(
    "PASS R10.22 RC.6B "
    "INSTALLER SELF-CONTAINMENT AND IDENTITY"
)
