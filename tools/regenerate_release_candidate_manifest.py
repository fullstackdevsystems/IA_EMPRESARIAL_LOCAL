"""Generate an isolated release-candidate manifest.

This tool never modifies the frozen root RELEASE_METADATA.json or
MANIFEST_SHA256.json authorities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROOT_MANIFEST = ROOT / "MANIFEST_SHA256.json"

REQUIRED_ROOT_FILES = {
    "RELEASE_METADATA.json",
    "InstalarLimpio.ps1",
    "INSTALAR_IA_EMPRESARIAL_LOCAL.bat",
    "InstallerR1020C1.ps1",
    "OperarIA.ps1",
    "BuildReleaseR1021A.ps1",
    "LEEME_INSTALACION_LIMPIA.txt",
    "ValidarInstalador.ps1",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git_head_blob(relative: str) -> bytes:
    normalized = relative.replace("\\", "/")

    result = subprocess.run(
        [
            "git",
            "cat-file",
            "blob",
            "HEAD:" + normalized,
        ],
        cwd=ROOT,
        capture_output=True,
    )

    if result.returncode != 0:
        raise SystemExit(
            "missing canonical HEAD blob: "
            + normalized
        )

    return result.stdout


def load_json(path: Path) -> dict:
    return json.loads(
        path.read_text(encoding="utf-8-sig")
    )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--metadata",
        required=True,
    )

    parser.add_argument(
        "--manifest",
        required=True,
    )

    args = parser.parse_args()

    metadata_path = Path(args.metadata).resolve()
    manifest_path = Path(args.manifest).resolve()

    if not metadata_path.is_file():
        raise SystemExit(
            "RC metadata not found"
        )

    if not ROOT_MANIFEST.is_file():
        raise SystemExit(
            "frozen root manifest not found"
        )

    metadata = load_json(metadata_path)

    required_metadata = {
        "schema_version",
        "product",
        "product_version",
        "release",
        "channel",
    }

    missing = sorted(
        required_metadata - set(metadata)
    )

    if missing:
        raise SystemExit(
            "RC metadata missing fields: "
            + ", ".join(missing)
        )

    if metadata["schema_version"] != 1:
        raise SystemExit(
            "unsupported RC metadata schema"
        )

    if metadata["product"] != "IA_EMPRESARIAL_LOCAL":
        raise SystemExit(
            "unexpected RC product"
        )

    if metadata["product_version"] != "8.5.5":
        raise SystemExit(
            "unexpected RC product version"
        )

    release = str(metadata["release"]).strip()

    if re.fullmatch(
        r"r[0-9]+[.][0-9]+-rc[1-9][0-9]*",
        release,
        re.IGNORECASE,
    ) is None:
        raise SystemExit(
            "unexpected RC release"
        )

    if metadata["channel"] != "rc":
        raise SystemExit(
            "unexpected RC channel"
        )

    frozen = load_json(ROOT_MANIFEST)

    paths = {
        str(item["path"]).replace("\\", "/")
        for item in frozen["files"]
    }

    paths |= REQUIRED_ROOT_FILES

    scripts_dir = ROOT / "IA_Local" / "scripts"

    for path in scripts_dir.rglob("*.py"):
        if path.is_file():
            paths.add(
                path.relative_to(ROOT).as_posix()
            )

    files = []

    for relative in sorted(paths):
        if relative == "RELEASE_METADATA.json":
            if not metadata_path.is_file():
                raise SystemExit(
                    "missing RC manifest source: "
                    + relative
                )

            payload_bytes = metadata_path.read_bytes()
        else:
            payload_bytes = git_head_blob(
                relative
            )

        files.append(
            {
                "path": relative,
                "sha256": sha256_bytes(
                    payload_bytes
                ),
                "size": len(
                    payload_bytes
                ),
            }
        )

    payload = {
        "version": metadata["release"],
        "files": files,
    }

    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fd, temp_name = tempfile.mkstemp(
        prefix=".rc_manifest_",
        suffix=".tmp",
        dir=str(manifest_path.parent),
    )

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                indent=2,
            )

            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(
            temp_name,
            manifest_path,
        )

    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass

        raise

    print(
        json.dumps(
            {
                "status": "PASS",
                "release": metadata["release"],
                "channel": metadata["channel"],
                "files": len(files),
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())