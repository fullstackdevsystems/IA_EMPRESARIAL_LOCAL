import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
METADATA_PATH = ROOT / "RELEASE_METADATA.json"
MANIFEST_PATH = ROOT / "MANIFEST_SHA256.json"
REGENERATOR_PATH = ROOT / "tools" / "regenerate_manifest.py"


def load_json(path):
    return json.loads(path.read_text(encoding="utf8"))


def ck(name, condition):
    if not condition:
        raise AssertionError(name)
    print("PASS", name)


metadata = load_json(METADATA_PATH)
manifest = load_json(MANIFEST_PATH)
regenerator = REGENERATOR_PATH.read_text(encoding="utf8")

ck(
    "release_metadata_contract",
    METADATA_PATH.is_file()
    and metadata["schema_version"] == 1
    and metadata["product"] == "IA_EMPRESARIAL_LOCAL"
    and metadata["product_version"] == "8.5.5"
    and metadata["release"] == "r10.25"
    and metadata["channel"] == "development",
)

ck(
    "release_metadata_nonempty",
    all(
        isinstance(metadata[field], str)
        and bool(metadata[field].strip())
        for field in ("product", "product_version", "release", "channel")
    ),
)

ck(
    "release_metadata_release_shape",
    metadata["release"].startswith("r10.")
    and metadata["channel"] in {"development", "rc", "stable"},
)

ck(
    "regenerator_uses_canonical_metadata",
    'RELEASE_METADATA = ROOT / "RELEASE_METADATA.json"' in regenerator
    and 'release = metadata["release"].strip()' in regenerator
    and '"version": release' in regenerator
    and 'old.get("version", "r10.20c.1")' not in regenerator,
)

if metadata["channel"] in {"rc", "stable"}:
    ck(
        "manifest_release_matches_canonical_metadata",
        manifest["version"] == metadata["release"],
    )
else:
    ck(
        "development_manifest_is_not_release_authority",
        metadata["channel"] == "development",
    )

manifest_paths = {
    str(item["path"]).replace("\\", "/")
    for item in manifest["files"]
}

ck(
    "release_metadata_governed_by_manifest",
    "RELEASE_METADATA.json" in manifest_paths,
)

print("PASS CANONICAL RELEASE METADATA")