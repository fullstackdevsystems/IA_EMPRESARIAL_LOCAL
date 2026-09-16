from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

GENERATOR = (
    ROOT
    / "tools"
    / "regenerate_release_candidate_manifest.py"
)

BUILDER = (
    ROOT
    / "BuildReleaseR1021A.ps1"
)

RC1 = (
    ROOT
    / "release_candidates"
    / "r10.23-rc1"
)

RC2 = (
    ROOT
    / "release_candidates"
    / "r10.23-rc2"
)

RC3 = (
    ROOT
    / "release_candidates"
    / "r10.23-rc3"
)

FORBIDDEN_COMMERCIAL_PATTERNS = (
    re.compile(r"^IA_Local/tests/"),
    re.compile(
        r"^IA_Local/scripts/"
        r"(run_.*tests.*|prueba_regresion.*)\.py$"
    ),
    re.compile(r"^IA_Local/MOSTRAR_TOKEN_LOCAL\.bat$"),
    re.compile(
        r"^IA_Local/"
        r"(LEEME_PRIMERO|README_INSTALACION|"
        r"GUIA_PRUEBAS_MEMORIA_RAG_V8|"
        r"ARQUITECTURA_MEMORIA_RAG_V8|PROMPT_).*"
    ),
)

KNOWN_NONCOMMERCIAL_SCRIPTS = {
    "IA_Local/scripts/prueba_regresion_v7.py",
    "IA_Local/scripts/run_enterprise_tests.py",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def authority_state(root: Path):
    if not root.exists():
        return None

    return {
        path.relative_to(root).as_posix():
            sha256(path)
        for path in sorted(
            root.rglob("*")
        )
        if path.is_file()
    }


def check(
    name: str,
    condition: bool,
) -> None:
    assert condition, name
    print("PASS", name)


def forbidden(
    relative: str,
) -> bool:
    normalized = relative.replace("\\", "/")

    return any(
        pattern.search(normalized)
        for pattern in FORBIDDEN_COMMERCIAL_PATTERNS
    )


before = {
    "RC1": authority_state(RC1),
    "RC2": authority_state(RC2),
}

check(
    "RC3_AUTHORITY_NOT_PREEXISTING",
    not RC3.exists(),
)

builder_source = BUILDER.read_text(
    encoding="utf-8-sig",
)

check(
    "BUILDER_FORBIDS_TEST_TREE",
    "'^IA_Local/tests/'"
    in builder_source,
)

check(
    "BUILDER_FORBIDS_REGRESSION_SCRIPT_PATTERN",
    "prueba_regresion"
    in builder_source,
)

check(
    "BUILDER_FORBIDS_RUN_TEST_SCRIPT_PATTERN",
    "run_.*tests"
    in builder_source,
)

with tempfile.TemporaryDirectory(
    prefix="r10_23_rr6_"
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
                "release": "r10.23-rc3",
                "channel": "rc",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
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

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)

    check(
        "RC3_TEMP_MANIFEST_GENERATION",
        result.returncode == 0,
    )

    check(
        "RC3_TEMP_MANIFEST_EXISTS",
        manifest.is_file(),
    )

    generated = json.loads(
        manifest.read_text(
            encoding="utf-8",
        )
    )

    check(
        "RC3_TEMP_IDENTITY",
        generated.get("version")
        == "r10.23-rc3",
    )

    paths = {
        str(item["path"]).replace(
            "\\",
            "/",
        )
        for item in generated.get(
            "files",
            []
        )
    }

    forbidden_paths = sorted(
        path
        for path in paths
        if forbidden(path)
    )

    if forbidden_paths:
        print(
            "FORBIDDEN_GENERATED_PATHS="
            + repr(forbidden_paths)
        )

    check(
        "GENERATED_MANIFEST_SATISFIES_BUILDER_COMMERCIAL_FILTER",
        not forbidden_paths,
    )

    distributed_harnesses = sorted(
        KNOWN_NONCOMMERCIAL_SCRIPTS
        & paths
    )

    if distributed_harnesses:
        print(
            "DISTRIBUTED_NONCOMMERCIAL_HARNESSES="
            + repr(distributed_harnesses)
        )

    check(
        "NONCOMMERCIAL_SCRIPT_HARNESSES_EXCLUDED",
        not distributed_harnesses,
    )

    commercial_scripts = {
        relative
        for path in (
            ROOT
            / "IA_Local"
            / "scripts"
        ).rglob("*.py")
        if path.is_file()
        for relative in [
            path.relative_to(ROOT).as_posix()
        ]
        if not forbidden(relative)
    }

    missing_commercial_scripts = sorted(
        commercial_scripts
        - paths
    )

    if missing_commercial_scripts:
        print(
            "MISSING_COMMERCIAL_RUNTIME_SCRIPTS="
            + repr(missing_commercial_scripts)
        )

    check(
        "ALL_CURRENT_COMMERCIAL_RUNTIME_SCRIPTS_MANIFESTED",
        not missing_commercial_scripts,
    )


after = {
    "RC1": authority_state(RC1),
    "RC2": authority_state(RC2),
}

check(
    "RC1_RC2_AUTHORITIES_UNCHANGED",
    before == after,
)

check(
    "REAL_RC3_AUTHORITY_NOT_CREATED",
    not RC3.exists(),
)

print(
    "PASS R10.23-RR.6 GENERATOR BUILDER COMMERCIAL MANIFEST CONTRACT"
)
