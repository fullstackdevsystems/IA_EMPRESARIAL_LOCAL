from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

checks: list[tuple[str, bool]] = []


def ck(name: str, condition: bool) -> None:
    checks.append((name, bool(condition)))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


root_meta = json.loads(read(ROOT / "RELEASE_METADATA.json"))
rc_meta = json.loads(
    read(
        ROOT
        / "release_candidates"
        / "r10.22-rc1"
        / "RELEASE_METADATA.json"
    )
)

ck(
    "frozen_root_authority",
    root_meta.get("product") == "IA_EMPRESARIAL_LOCAL"
    and root_meta.get("product_version") == "8.5.5"
    and root_meta.get("release") == "r10.21f"
    and root_meta.get("channel") == "stable",
)

ck(
    "rc_authority",
    rc_meta.get("product") == "IA_EMPRESARIAL_LOCAL"
    and rc_meta.get("product_version") == "8.5.5"
    and rc_meta.get("release") == "r10.22-rc1"
    and rc_meta.get("channel") == "rc",
)

version_text = read(ROOT / "IA_Local" / "VERSION.txt").strip()

ck(
    "version_visible_identity",
    version_text == "8.5.5-r10.22-rc1",
)

wrapper_text = read(ROOT / "InstalarLimpio.ps1")
wrapper_lines = wrapper_text.splitlines()
wrapper_nonblank = [
    line.strip()
    for line in wrapper_lines
    if line.strip()
]

ck(
    "wrapper_delegates_installer",
    "InstallerR1020C1.ps1" in wrapper_text
    and "@PSBoundParameters" in wrapper_text,
)

ck(
    "wrapper_minimal",
    len(wrapper_nonblank) == 4
    and "InstallerR1020C1.ps1" in wrapper_nonblank[2]
    and wrapper_nonblank[3].lower().startswith("exit ")
    and "R7" not in wrapper_text
    and "$PackageRoot" not in wrapper_text,
)

validator_text = read(ROOT / "ValidarInstalador.ps1")

ck(
    "validator_installer",
    "InstallerR1020C1.ps1" in validator_text
    and "ParseFile" in validator_text,
)

ck(
    "validator_metadata",
    "RELEASE_METADATA.json" in validator_text,
)

ck(
    "validator_manifest",
    "MANIFEST_SHA256.json" in validator_text,
)

ck(
    "validator_hashes",
    "Get-FileHash" in validator_text,
)

installer_text = read(ROOT / "InstallerR1020C1.ps1")

ck(
    "fresh_cleanup_function",
    re.search(
        r"function\s+Cleanup-FreshInstallArtifacts\b",
        installer_text,
        re.IGNORECASE,
    )
    is not None,
)

ck(
    "fresh_runtime_conflict_guard",
    "$runtimeRootPreExisted" in installer_text
    and "RUNTIME_ROOT_CONFLICT" in installer_text,
)

ck(
    "fresh_cleanup_failure_paths",
    installer_text.count("Cleanup-FreshInstallArtifacts") >= 5,
)

requirements = [
    line.strip()
    for line in read(
        ROOT / "IA_Local" / "requirements-local.txt"
    ).splitlines()
    if line.strip()
    and not line.strip().startswith("#")
]

expected_requirements = [
    "open-webui==0.11.3",
    "open-terminal==0.12.4",
    "pandas==3.0.3",
    "python-calamine==0.8.2",
    "openpyxl==3.1.5",
    "xlrd==2.0.2",
    "pyxlsb==1.0.10",
    "xlsxwriter==3.2.9",
    "matplotlib==3.11.1",
    "reportlab==5.0.1",
    "pypdf==6.7.5",
    "pymupdf==1.28.2",
    "python-docx==1.2.0",
    "tabulate==0.10.0",
    "fastapi==0.136.3",
    "uvicorn==0.51.0",
    "python-multipart==0.0.32",
    "pyodbc==5.3.0",
    "requests==2.34.2",
]

ck(
    "requirements_count_19",
    len(requirements) == 19,
)

ck(
    "requirements_exact_proven_pins",
    requirements == expected_requirements,
)

builder_text = read(ROOT / "BuildReleaseR1021A.ps1")

ck(
    "builder_outputdir_contract",
    "$OutputDir" in builder_text
    and "$OutputRoot" not in builder_text,
)

failed = [
    name
    for name, ok in checks
    if not ok
]

for name, ok in checks:
    print(
        ("PASS " if ok else "FAIL ")
        + name
    )

print(
    f"{len(checks) - len(failed)}/{len(checks)} PASS"
)

if failed:
    print(
        "FAILED_CONTROLS="
        + ",".join(failed)
    )
    sys.exit(1)

print(
    "RC.7D COMMERCIAL HYGIENE CONTRACT: PASS"
)