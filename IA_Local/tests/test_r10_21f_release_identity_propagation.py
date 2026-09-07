import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

METADATA_PATH = ROOT / "RELEASE_METADATA.json"
BUILD_PATH = ROOT / "BuildReleaseR1021A.ps1"
INSTALLER_PATH = ROOT / "InstallerR1020C1.ps1"
ANALYZER_PATH = ROOT / "IA_Local" / "scripts" / "analizador_universal.py"
STARTER_PATH = ROOT / "IA_Local" / "scripts" / "Iniciar.ps1"


def load(path):
    return path.read_text(encoding="utf8")


def ck(name, condition):
    if not condition:
        raise AssertionError(name)
    print("PASS", name)


metadata = json.loads(load(METADATA_PATH))

product = metadata["product"]
product_version = metadata["product_version"]
release = metadata["release"]
channel = metadata["channel"]

build = load(BUILD_PATH)
installer = load(INSTALLER_PATH)
analyzer = load(ANALYZER_PATH)
starter = load(STARTER_PATH)


ck(
    "canonical_metadata_contract",
    product == "IA_EMPRESARIAL_LOCAL"
    and product_version == "8.5.5"
    and release == "r10.21f"
    and channel == "stable",
)


ck(
    "build_reads_release_metadata",
    "RELEASE_METADATA.json" in build
    and "product_version" in build
    and "release" in build
    and "channel" in build,
)


ck(
    "build_does_not_use_manifest_as_version_authority",
    '$version = [string]$manifest.version' not in build,
)


ck(
    "analyzer_no_legacy_composite_product_version",
    '8.5.5-r10.2' not in analyzer,
)


ck(
    "analyzer_runtime_uses_canonical_product_version",
    "base.app.version = PRODUCT_VERSION" in analyzer
    and '"version": PRODUCT_VERSION' in analyzer,
)


ck(
    "analyzer_runtime_uses_canonical_release_identity",
    '"release": RELEASE_ID' in analyzer
    and '"channel": RELEASE_CHANNEL' in analyzer
    and '_RELEASE_METADATA_PATH' in analyzer,
)

ck(
    "analyzer_current_release_not_hardcoded_in_runtime_surface",
    '"release": "r10.21f"' not in analyzer
    and '"channel": "stable"' not in analyzer
    and 'V8.5.5 R10.2' not in analyzer,
)

ck(
    "analyzer_visible_identity_is_dynamic",
    'V{PRODUCT_VERSION} {RELEASE_ID.upper()}' in analyzer,
)


ck(
    "starter_expected_product_version_matches_metadata",
    '$AnalyzerExpectedVersion = "8.5.5"' in starter,
)


ck(
    "installer_no_legacy_release_identity",
    "r10.20c.1" not in installer,
)


ck(
    "installer_reads_canonical_release_metadata",
    "RELEASE_METADATA.json" in installer,
)


root_files_matches = re.findall(
    r"(?ms)^\s*\$rootFiles\s*=\s*@\(\s*(.*?)^\s*\)\s*$",
    installer,
)

root_files_body = (
    root_files_matches[0]
    if len(root_files_matches) == 1
    else ""
)

metadata_in_root_files = len(
    re.findall(
        r"(?m)^\s*'RELEASE_METADATA\.json'\s*,?\s*$",
        root_files_body,
    )
)

root_files_copy_loop_count = installer.count(
    "foreach ($rootFile in $rootFiles) {"
)

root_files_product_copy_count = installer.count(
    "Copy-Item $sourceFile (Join-Path $ProductRoot $rootFile) -Force"
)

ck(
    "installer_copies_canonical_release_metadata_to_product_root",
    len(root_files_matches) == 1
    and metadata_in_root_files == 1
    and root_files_copy_loop_count == 1
    and root_files_product_copy_count == 1,
)


ck(
    "installer_log_uses_canonical_release_identity",
    'logs\\installer-{0}.log' in installer
    and '-f $release' in installer
    and 'installer-r10.21f.log' not in installer,
)


print("PASS R10.21F RELEASE IDENTITY PROPAGATION")
