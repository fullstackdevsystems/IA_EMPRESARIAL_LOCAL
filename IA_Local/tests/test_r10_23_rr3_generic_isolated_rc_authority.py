from __future__ import annotations

from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]

TOOL = (
    ROOT
    / "tools"
    / "regenerate_release_candidate_manifest.py"
)

ROOT_METADATA = (
    ROOT
    / "RELEASE_METADATA.json"
)

ROOT_MANIFEST = (
    ROOT
    / "MANIFEST_SHA256.json"
)

R1022F = (
    ROOT
    / "release_candidates"
    / "r10.22f"
)

R1022F_METADATA = (
    R1022F
    / "RELEASE_METADATA.json"
)

R1022F_MANIFEST = (
    R1022F
    / "MANIFEST_SHA256.json"
)

R1023_RC1 = (
    ROOT
    / "release_candidates"
    / "r10.23-rc1"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def check(
    name: str,
    condition: bool,
) -> None:
    assert condition, name
    print(
        "PASS",
        name,
    )


def authority_state(
    root: Path,
):
    if not root.exists():
        return None

    if not root.is_dir():
        return {
            "__INVALID_TYPE__": True,
        }

    return {
        path.relative_to(root).as_posix():
            sha256(path)
        for path in sorted(
            root.rglob("*")
        )
        if path.is_file()
    }


def run_tool(
    metadata: Path,
    manifest: Path,
):
    return subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--metadata",
            str(metadata),
            "--manifest",
            str(manifest),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


source = TOOL.read_text(
    encoding="utf-8-sig",
)

check(
    "NO_R10_22_RC1_RELEASE_COUPLING",
    (
        'metadata["release"] != "r10.22-rc1"'
        not in source
    ),
)

check(
    "GENERIC_RC_RELEASE_PATTERN_PRESENT",
    (
        "re.fullmatch("
        in source
        and "unexpected RC release"
        in source
        and "re.IGNORECASE"
        in source
    ),
)

check(
    "CURRENT_PRODUCT_VERSION_CONTRACT_PRESERVED",
    (
        'metadata["product_version"] != "8.5.5"'
        in source
    ),
)

check(
    "RC_CHANNEL_CONTRACT_PRESERVED",
    (
        'metadata["channel"] != "rc"'
        in source
    ),
)

before = {
    "ROOT_METADATA":
        sha256(ROOT_METADATA),

    "ROOT_MANIFEST":
        sha256(ROOT_MANIFEST),

    "R1022F_METADATA":
        sha256(R1022F_METADATA),

    "R1022F_MANIFEST":
        sha256(R1022F_MANIFEST),
}

r1023_authority_before = authority_state(
    R1023_RC1
)

with tempfile.TemporaryDirectory(
    prefix="r10_23_rr3_"
) as td:
    temp = Path(td)

    metadata = (
        temp
        / "RELEASE_METADATA.json"
    )

    manifest = (
        temp
        / "MANIFEST_SHA256.json"
    )

    metadata.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product": "IA_EMPRESARIAL_LOCAL",
                "product_version": "8.5.5",
                "release": "r10.23-rc1",
                "channel": "rc",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_tool(
        metadata,
        manifest,
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)

    check(
        "R10_23_RC1_GENERATION_SUCCEEDS",
        result.returncode == 0,
    )

    check(
        "R10_23_RC1_MANIFEST_CREATED",
        manifest.is_file(),
    )

    generated = json.loads(
        manifest.read_text(
            encoding="utf-8"
        )
    )

    check(
        "R10_23_RC1_MANIFEST_IDENTITY",
        (
            generated.get("version")
            == "r10.23-rc1"
        ),
    )

    paths = {
        str(
            item.get("path")
            or ""
        ).replace(
            "\\",
            "/",
        )
        for item
        in generated.get(
            "files",
            [],
        )
    }

    required_package_surface = {
        "RELEASE_METADATA.json",
        "InstalarLimpio.ps1",
        "INSTALAR_IA_EMPRESARIAL_LOCAL.bat",
        "InstallerR1020C1.ps1",
        "OperarIA.ps1",
        "BuildReleaseR1021A.ps1",
        "LEEME_INSTALACION_LIMPIA.txt",
        "ValidarInstalador.ps1",
        "IA_Local/scripts/enterprise_maintenance_worker.py",
        "IA_Local/scripts/enterprise_ai/api.py",
        "IA_Local/scripts/enterprise_ai/admin_console.py",
    }

    missing = sorted(
        required_package_surface
        - paths
    )

    if missing:
        print(
            "MISSING_PACKAGE_SURFACE="
            + repr(missing)
        )

    check(
        "R10_23_CURRENT_PACKAGE_SURFACE_COVERED",
        not missing,
    )

    current_runtime_scripts = {
        path.relative_to(ROOT).as_posix()
        for path in (
            ROOT
            / "IA_Local"
            / "scripts"
        ).rglob("*.py")
        if path.is_file()
    }

    missing_runtime_scripts = sorted(
        current_runtime_scripts
        - paths
    )

    if missing_runtime_scripts:
        print(
            "MISSING_CURRENT_RUNTIME_SCRIPTS="
            + repr(missing_runtime_scripts)
        )

    check(
        "R10_23_MANIFEST_COVERS_ALL_CURRENT_RUNTIME_SCRIPTS",
        not missing_runtime_scripts,
    )

    worktree_only_launchers = {
        "IA_Local/ABRIR_ADMIN_MEMORIA_RAG.bat",
        "IA_Local/ABRIR_ASISTENTE.bat",
        "IA_Local/scripts/Iniciar.ps1",
    }

    distributed_launchers = sorted(
        worktree_only_launchers
        & paths
    )

    if distributed_launchers:
        print(
            "UNEXPECTED_DISTRIBUTED_LAUNCHERS="
            + repr(distributed_launchers)
        )

    check(
        "WORKTREE_LAUNCHERS_NOT_REINTRODUCED_TO_COMMERCIAL_PACKAGE",
        not distributed_launchers,
    )

    forbidden = sorted(
        path
        for path in paths
        if (
            path.startswith(
                "IA_Local/tests/"
            )
            or path
            == "IA_Local/MOSTRAR_TOKEN_LOCAL.bat"
        )
    )

    if forbidden:
        print(
            "FORBIDDEN_MANIFEST_PATHS="
            + repr(forbidden)
        )

    check(
        "COMMERCIAL_HYGIENE_PRESERVED",
        not forbidden,
    )

    invalid_metadata = (
        temp
        / "INVALID_RELEASE_METADATA.json"
    )

    invalid_manifest = (
        temp
        / "INVALID_MANIFEST.json"
    )

    invalid_metadata.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product": "IA_EMPRESARIAL_LOCAL",
                "product_version": "8.5.5",
                "release": "r10.23-ga1",
                "channel": "rc",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    invalid = run_tool(
        invalid_metadata,
        invalid_manifest,
    )

    check(
        "NON_RC_RELEASE_ID_REJECTED",
        invalid.returncode != 0,
    )

    check(
        "INVALID_MANIFEST_NOT_CREATED",
        not invalid_manifest.exists(),
    )


after = {
    "ROOT_METADATA":
        sha256(ROOT_METADATA),

    "ROOT_MANIFEST":
        sha256(ROOT_MANIFEST),

    "R1022F_METADATA":
        sha256(R1022F_METADATA),

    "R1022F_MANIFEST":
        sha256(R1022F_MANIFEST),
}

check(
    "FROZEN_AUTHORITIES_UNCHANGED",
    before == after,
)

r1023_authority_after = authority_state(
    R1023_RC1
)

check(
    "R10_23_AUTHORITY_STATE_UNCHANGED",
    (
        r1023_authority_after
        == r1023_authority_before
    ),
)

if r1023_authority_before is None:
    check(
        "R10_23_AUTHORITY_NOT_CREATED",
        r1023_authority_after is None,
    )
else:
    check(
        "PREEXISTING_R10_23_AUTHORITY_PRESERVED",
        (
            r1023_authority_after
            == r1023_authority_before
        ),
    )

print(
    "PASS R10.23-RR.3 GENERIC ISOLATED RC AUTHORITY"
)
