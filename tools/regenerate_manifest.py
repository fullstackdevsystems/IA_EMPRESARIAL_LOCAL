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

# The customer manifest is an allowlist.  Never inherit paths from a prior
# manifest: that would make historical tests, prompts, or support utilities
# silently distributable forever.
paths = {
    "RELEASE_METADATA.json",
    "InstalarLimpio.ps1",
    "INSTALAR_IA_EMPRESARIAL_LOCAL.bat",
    "InstallerR1020C1.ps1",
    "OperarIA.ps1",
    "ValidarInstalador.ps1",
    "LEEME_INSTALACION_LIMPIA.txt",
    "IA_Local/VERSION.txt",
    "IA_Local/requirements-local.txt",
    "IA_Local/requirements-optional.txt",
    "IA_Local/config/.keep",
    "IA_Local/data/enterprise/.keep",
    "IA_Local/data/open-webui/.keep",
    "IA_Local/logs/.keep",
    "IA_Local/workspace/Conocimiento/.keep",
    "IA_Local/workspace/Entrada/.keep",
    "IA_Local/workspace/Historico/.keep",
    "IA_Local/workspace/Reportes/.keep",
}

# All canonical Python runtime modules under IA_Local/scripts.
scripts_dir = ROOT / "IA_Local" / "scripts"

excluded_runtime_scripts = {
    "run_enterprise_tests.py",
    "prueba_regresion_v7.py",
}

for file in scripts_dir.rglob("*.py"):
    if file.is_file():
        if file.name not in excluded_runtime_scripts:
            paths.add(file.relative_to(ROOT).as_posix())

# Runtime templates are part of the product surface, unlike tests and sample
# prompts.  Keep the extension list deliberately narrow and deterministic.
templates_dir = scripts_dir / "templates"
for file in templates_dir.rglob("*.html"):
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
