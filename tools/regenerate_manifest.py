"""Development-only deterministic manifest regeneration; never run by installer."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST_SHA256.json"

old = json.loads(MANIFEST.read_text(encoding="utf8"))

paths = {item["path"] for item in old["files"]}

# Root commercial/runtime files.
paths |= {
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

MANIFEST.write_text(
    json.dumps(
        {
            "version": old.get("version", "r10.20c.1"),
            "files": files,
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf8",
)
