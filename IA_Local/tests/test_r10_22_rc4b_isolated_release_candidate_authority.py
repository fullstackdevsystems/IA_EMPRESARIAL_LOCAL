import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ROOT_METADATA = ROOT / "RELEASE_METADATA.json"
ROOT_MANIFEST = ROOT / "MANIFEST_SHA256.json"

RC_ROOT = (
    ROOT
    / "release_candidates"
    / "r10.22-rc1"
)

RC_METADATA = RC_ROOT / "RELEASE_METADATA.json"
RC_MANIFEST = RC_ROOT / "MANIFEST_SHA256.json"

BUILDER = ROOT / "BuildReleaseR1021A.ps1"

failures = []


def check(name, value):
    ok = bool(value)
    print(("PASS" if ok else "FAIL"), name)

    if not ok:
        failures.append(name)


def load_json(path):
    if not path.is_file():
        return None

    return json.loads(
        path.read_text(encoding="utf-8")
    )


# -------------------------------------------------
# 1. Frozen R10.21F authorities MUST remain intact.
# -------------------------------------------------

root_metadata = load_json(ROOT_METADATA)
root_manifest = load_json(ROOT_MANIFEST)

check(
    "frozen_root_metadata_exists",
    root_metadata is not None,
)

check(
    "frozen_root_metadata_remains_r10_21f",
    (
        root_metadata is not None
        and root_metadata.get("schema_version") == 1
        and root_metadata.get("product")
        == "IA_EMPRESARIAL_LOCAL"
        and root_metadata.get("product_version")
        == "8.5.5"
        and root_metadata.get("release")
        == "r10.21f"
        and root_metadata.get("channel")
        == "stable"
    ),
)

check(
    "frozen_root_manifest_remains_r10_21f",
    (
        root_manifest is not None
        and root_manifest.get("version")
        == "r10.21f"
    ),
)


# -------------------------------------------------
# 2. RC authority MUST be isolated.
# -------------------------------------------------

rc_metadata = load_json(RC_METADATA)
rc_manifest = load_json(RC_MANIFEST)

check(
    "rc_metadata_exists",
    rc_metadata is not None,
)

check(
    "rc_metadata_contract",
    (
        rc_metadata is not None
        and rc_metadata.get("schema_version") == 1
        and rc_metadata.get("product")
        == "IA_EMPRESARIAL_LOCAL"
        and rc_metadata.get("product_version")
        == "8.5.5"
        and rc_metadata.get("release")
        == "r10.22-rc1"
        and rc_metadata.get("channel")
        == "rc"
    ),
)

check(
    "rc_manifest_exists",
    rc_manifest is not None,
)

check(
    "rc_manifest_identity_matches_metadata",
    (
        rc_metadata is not None
        and rc_manifest is not None
        and rc_manifest.get("version")
        == rc_metadata.get("release")
    ),
)


# -------------------------------------------------
# 3. RC manifest MUST cover all runtime scripts.
# -------------------------------------------------

manifest_paths = set()

if rc_manifest is not None:
    manifest_paths = {
        str(item.get("path", "")).replace("\\", "/")
        for item in rc_manifest.get("files", [])
    }

runtime_scripts = {
    path.relative_to(ROOT).as_posix()
    for path in (
        ROOT
        / "IA_Local"
        / "scripts"
    ).rglob("*.py")
    if path.is_file()
}

missing_scripts = sorted(
    runtime_scripts - manifest_paths
)

check(
    "rc_manifest_covers_all_runtime_scripts",
    not missing_scripts,
)

if missing_scripts:
    print("RC MANIFEST MISSING SCRIPTS:")

    for path in missing_scripts:
        print(" ", path)


check(
    "enterprise_control_plane_is_governed",
    (
        "IA_Local/scripts/"
        "enterprise_control_plane.py"
    )
    in manifest_paths,
)

check(
    "prompt_polarity_is_governed",
    (
        "IA_Local/scripts/"
        "prompt_polarity.py"
    )
    in manifest_paths,
)


# -------------------------------------------------
# 4. Critical commercial root files MUST be governed.
# -------------------------------------------------

required_root_files = {
    "RELEASE_METADATA.json",
    "InstalarLimpio.ps1",
    "INSTALAR_IA_EMPRESARIAL_LOCAL.bat",
    "InstallerR1020C1.ps1",
    "OperarIA.ps1",
    "BuildReleaseR1021A.ps1",
    "LEEME_INSTALACION_LIMPIA.txt",
    "ValidarInstalador.ps1",
}

missing_root = sorted(
    required_root_files - manifest_paths
)

check(
    "rc_manifest_covers_required_root_files",
    not missing_root,
)

if missing_root:
    print("RC MANIFEST MISSING ROOT FILES:")

    for path in missing_root:
        print(" ", path)


# -------------------------------------------------
# 5. Builder MUST support isolated authorities.
# -------------------------------------------------

builder = BUILDER.read_text(
    encoding="utf-8-sig"
)

check(
    "builder_has_manifest_path_parameter",
    bool(
        re.search(
            r"\[\s*string\s*\]\s*\$ManifestPath",
            builder,
            re.IGNORECASE,
        )
    ),
)

check(
    "builder_has_release_metadata_path_parameter",
    bool(
        re.search(
            r"\[\s*string\s*\]\s*\$ReleaseMetadataPath",
            builder,
            re.IGNORECASE,
        )
    ),
)

check(
    "builder_does_not_force_root_manifest",
    '$ManifestPath = Join-Path $Root "MANIFEST_SHA256.json"'
    not in builder,
)

check(
    "builder_does_not_force_root_release_metadata",
    '$ReleaseMetadataPath = Join-Path $Root "RELEASE_METADATA.json"'
    not in builder,
)


# -------------------------------------------------
# 6. RC package identity MUST remain metadata-driven.
# -------------------------------------------------

check(
    "builder_uses_release_as_package_version",
    '$version = $release' in builder,
)

check(
    "builder_requires_manifest_metadata_match",
    (
        "MANIFEST_RELEASE_METADATA_MISMATCH"
        in builder
    ),
)


if failures:
    raise AssertionError(
        "RC.4B expected isolated RC authority "
        "contract failures: "
        + ", ".join(failures)
    )

print(
    "PASS R10.22 RC.4B "
    "ISOLATED RELEASE CANDIDATE AUTHORITY"
)
