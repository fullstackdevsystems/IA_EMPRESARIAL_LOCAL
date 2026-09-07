"""Development-only deterministic manifest regeneration; never run by installer."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST_SHA256.json"
RELEASE_METADATA = ROOT / "RELEASE_METADATA.json"

if not MANIFEST.is_file():
    raise SystemExit("manifest not found")

if not RELEASE_METADATA.is_file():
    raise SystemExit("release metadata not found")

old = json.loads(MANIFEST.read_text(encoding="utf8"))
metadata = json.loads(RELEASE_METADATA.read_text(encoding="utf8"))

required_metadata = {
    "schema_version",
    "product",
    "product_version",
    "release",
    "channel",
}

missing_metadata = sorted(required_metadata - set(metadata))

if missing_metadata:
    raise SystemExit(
        "release metadata missing fields: " + ", ".join(missing_metadata)
    )

if metadata["schema_version"] != 1:
    raise SystemExit("unsupported release metadata schema")

for field in ("product", "product_version", "release", "channel"):
    value = metadata[field]
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"invalid release metadata field: {field}")

if metadata["product"] != "IA_EMPRESARIAL_LOCAL":
    raise SystemExit("unexpected release metadata product")

release = metadata["release"].strip()

paths = {item["path"] for item in old["files"]}

# Root commercial/runtime files.
paths |= {
    "RELEASE_METADATA.json",
    "InstalarLimpio.ps1",
    "INSTALAR_IA_EMPRESARIAL_LOCAL.bat",
    "InstallerR1020C1.ps1",
    "OperarIA.ps1",
    "BuildReleaseR1021A.ps1",
    "LEEME_INSTALACION_LIMPIA.txt",
}

# All canonical Python runtime modules under IA_Local/scripts.
scripts_dir = ROOT / "IA_Local" / "scripts"

for file in scripts_dir.rglob("*.py"):
    if file.is_file():
        paths.add(file.relative_to(ROOT).as_posix())

files = []

for rel in sorted(paths):
    path = ROOT / rel

    if not path.is_file():
        raise SystemExit(f"missing manifest file: {rel}")

    raw = path.read_bytes()

    files.append(
        {
            "path": rel.replace("\\", "/"),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
        }
    )

payload = (
    json.dumps(
        {
            # Compatibility field. Its value is derived exclusively from
            # RELEASE_METADATA.json and is not an independent authority.
            "version": release,
            "files": files,
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n"
)

fd, temp_name = tempfile.mkstemp(
    prefix=".manifest_",
    suffix=".tmp",
    dir=str(MANIFEST.parent),
)

try:
    with os.fdopen(
        fd,
        "w",
        encoding="utf-8",
        newline="\n",
    ) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(
        temp_name,
        MANIFEST,
    )

except Exception:
    try:
        os.unlink(temp_name)
    except FileNotFoundError:
        pass
    raise
