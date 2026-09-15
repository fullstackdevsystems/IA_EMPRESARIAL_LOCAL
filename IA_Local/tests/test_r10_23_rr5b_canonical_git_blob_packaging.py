from __future__ import annotations

from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile


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

RC1_METADATA = (
    ROOT
    / "release_candidates"
    / "r10.23-rc1"
    / "RELEASE_METADATA.json"
)

RC1_MANIFEST = (
    ROOT
    / "release_candidates"
    / "r10.23-rc1"
    / "MANIFEST_SHA256.json"
)

RC1_HASHES = {
    RC1_METADATA:
        "c4d17a37b575f4bbf52435f4cb95ad24d95b6849fb90f18d9b954104b8c27fa3",

    RC1_MANIFEST:
        "9a82735c2ab4f5952d4269c82f5656e28beaa711320494d59075f86a08fd64eb",
}


def check(
    name: str,
    condition: bool,
) -> None:
    assert condition, name
    print(
        "PASS",
        name,
    )


def sha256_bytes(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def sha256_file(
    path: Path,
) -> str:
    return sha256_bytes(
        path.read_bytes()
    )


def head_blob(
    relative: str,
) -> bytes:
    result = subprocess.run(
        [
            "git",
            "cat-file",
            "blob",
            "HEAD:" + relative,
        ],
        cwd=ROOT,
        capture_output=True,
    )

    if result.returncode != 0:
        raise AssertionError(
            "HEAD blob missing: "
            + relative
        )

    return result.stdout


for path, expected in RC1_HASHES.items():
    check(
        "RC1_EXISTS_" + path.name,
        path.is_file(),
    )

    check(
        "RC1_UNCHANGED_" + path.name,
        sha256_file(path) == expected,
    )


generator_source = GENERATOR.read_text(
    encoding="utf-8-sig"
)

builder_source = BUILDER.read_text(
    encoding="utf-8-sig"
)

with tempfile.TemporaryDirectory(
    prefix="r10_23_rr5b_parser_"
) as parser_td:
    parser_script = (
        Path(parser_td)
        / "parse_builder.ps1"
    )

    parser_script.write_text(
        "param(\n"
        "    [Parameter(Mandatory = $true)]\n"
        "    [string]$Path\n"
        ")\n"
        "$tokens = $null\n"
        "$errors = $null\n"
        "[System.Management.Automation.Language.Parser]::ParseFile(\n"
        "    $Path,\n"
        "    [ref]$tokens,\n"
        "    [ref]$errors\n"
        ") | Out-Null\n"
        "if ($errors.Count -ne 0) {\n"
        "    foreach ($errorItem in $errors) {\n"
        "        [Console]::Error.WriteLine($errorItem.Message)\n"
        "    }\n"
        "    exit 7\n"
        "}\n"
        "exit 0\n",
        encoding="utf-8",
    )

    parser_result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(parser_script),
            "-Path",
            str(BUILDER),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    if parser_result.stdout:
        print(
            parser_result.stdout
        )

    if parser_result.stderr:
        print(
            parser_result.stderr
        )

    check(
        "BUILDER_REAL_POWERSHELL_PARSE",
        parser_result.returncode == 0,
    )

check(
    "GENERATOR_IMPORTS_SUBPROCESS",
    "import subprocess"
    in generator_source,
)

check(
    "GENERATOR_USES_GIT_HEAD_BLOB",
    (
        '"cat-file"'
        in generator_source
        and '"blob"'
        in generator_source
        and '"HEAD:" + normalized'
        in generator_source
    ),
)

check(
    "GENERATOR_HASHES_BYTES",
    (
        "sha256_bytes("
        in generator_source
        and "len("
        in generator_source
    ),
)

check(
    "BUILDER_HAS_BINARY_SAFE_BLOB_WRITER",
    (
        "function Write-GitHeadBlob"
        in builder_source
        and "StandardOutput.BaseStream.CopyTo"
        in builder_source
        and "System.IO.FileMode]::Create"
        in builder_source
    ),
)

check(
    "BUILDER_VERIFIES_MATERIALIZED_HASH",
    "PACKAGE_MATERIALIZED_HASH_MISMATCH"
    in builder_source,
)

check(
    "BUILDER_VERIFIES_MATERIALIZED_SIZE",
    "PACKAGE_MATERIALIZED_SIZE_MISMATCH"
    in builder_source,
)

check(
    "BUILDER_REQUIRED_ROOTS_ARE_VERIFIED_NOT_OVERWRITTEN",
    (
        "REQUIRED_RELEASE_FILE_NOT_MANIFESTED"
        in builder_source
        and "REQUIRED_RELEASE_FILE_NOT_MATERIALIZED"
        in builder_source
    ),
)

with tempfile.TemporaryDirectory(
    prefix="r10_23_rr5b_"
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

    metadata_payload = {
        "schema_version": 1,
        "product": "IA_EMPRESARIAL_LOCAL",
        "product_version": "8.5.5",
        "release": "r10.23-rc2",
        "channel": "rc",
    }

    metadata.write_text(
        json.dumps(
            metadata_payload,
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
        "RC2_TEMP_MANIFEST_GENERATION",
        result.returncode == 0,
    )

    check(
        "RC2_TEMP_MANIFEST_EXISTS",
        manifest.is_file(),
    )

    generated = json.loads(
        manifest.read_text(
            encoding="utf-8"
        )
    )

    check(
        "RC2_TEMP_IDENTITY",
        generated.get("version")
        == "r10.23-rc2",
    )

    items = {
        str(item["path"]).replace(
            "\\",
            "/",
        ): item
        for item in generated.get(
            "files",
            []
        )
    }

    check(
        "RC2_TEMP_MANIFEST_NONEMPTY",
        bool(items),
    )

    metadata_bytes = metadata.read_bytes()
    metadata_item = items.get(
        "RELEASE_METADATA.json"
    )

    check(
        "ISOLATED_METADATA_PRESENT",
        metadata_item is not None,
    )

    check(
        "ISOLATED_METADATA_HASHES_ITS_OWN_BYTES",
        (
            metadata_item["sha256"]
            == sha256_bytes(
                metadata_bytes
            )
            and int(
                metadata_item["size"]
            )
            == len(
                metadata_bytes
            )
        ),
    )

    mismatches = []

    for relative, item in sorted(
        items.items()
    ):
        if relative == "RELEASE_METADATA.json":
            continue

        blob = head_blob(
            relative
        )

        actual_hash = sha256_bytes(
            blob
        )

        actual_size = len(
            blob
        )

        if (
            item.get("sha256")
            != actual_hash
            or int(
                item.get("size")
            )
            != actual_size
        ):
            mismatches.append(
                (
                    relative,
                    item.get("sha256"),
                    actual_hash,
                    item.get("size"),
                    actual_size,
                )
            )

    if mismatches:
        print(
            "HEAD_BLOB_MANIFEST_MISMATCHES="
            + repr(
                mismatches[:20]
            )
        )

    check(
        "ALL_NON_METADATA_ENTRIES_MATCH_HEAD_BLOBS",
        not mismatches,
    )

    known_paths = {
        "IA_Local/scripts/analizador_universal.py",
        "IA_Local/scripts/enterprise_ai/admin_console.py",
        "IA_Local/scripts/enterprise_ai/api.py",
        "IA_Local/scripts/enterprise_identity.py",
        "IA_Local/scripts/enterprise_maintenance_worker.py",
        "IA_Local/scripts/templates/dashboard_bi.html",
        "IA_Local/scripts/templates/dashboard_clientes.html",
        "IA_Local/scripts/templates/dashboard_generico.html",
        "INSTALAR_IA_EMPRESARIAL_LOCAL.bat",
    }

    missing_known = sorted(
        known_paths
        - set(items)
    )

    if missing_known:
        print(
            "KNOWN_CANONICAL_PATHS_MISSING="
            + repr(missing_known)
        )

    check(
        "KNOWN_RR5A_PATHS_MANIFESTED",
        not missing_known,
    )

    divergent_worktree = []

    for relative in sorted(
        known_paths
    ):
        worktree_path = (
            ROOT
            / relative
        )

        blob = head_blob(
            relative
        )

        if (
            worktree_path.is_file()
            and worktree_path.read_bytes()
            != blob
        ):
            divergent_worktree.append(
                relative
            )

    print(
        "WORKTREE_HEAD_BYTE_DIVERGENCE_COUNT="
        + str(
            len(divergent_worktree)
        )
    )

    for relative in divergent_worktree:
        print(
            "WORKTREE_HEAD_BYTE_DIVERGENCE="
            + relative
        )

    check(
        "WORKTREE_DIVERGENCE_DOES_NOT_AFFECT_MANIFEST",
        all(
            items[relative]["sha256"]
            == sha256_bytes(
                head_blob(
                    relative
                )
            )
            for relative
            in known_paths
        ),
    )


check(
    "REAL_RC2_AUTHORITY_NOT_CREATED",
    not (
        ROOT
        / "release_candidates"
        / "r10.23-rc2"
    ).exists(),
)

for path, expected in RC1_HASHES.items():
    check(
        "RC1_STILL_UNCHANGED_" + path.name,
        sha256_file(path) == expected,
    )

print(
    "PASS R10.23-RR.5B CANONICAL GIT BLOB PACKAGING"
)
