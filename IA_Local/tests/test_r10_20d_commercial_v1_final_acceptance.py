from pathlib import Path
import json
import hashlib

ROOT = Path(__file__).resolve().parents[2]

required = [
    ROOT / "OperarIA.ps1",
    ROOT / "InstallerR1020C1.ps1",
    ROOT / "InstalarLimpio.ps1",
    ROOT / "INSTALAR_IA_EMPRESARIAL_LOCAL.bat",
    ROOT / "MANIFEST_SHA256.json",
    ROOT / "tools" / "regenerate_manifest.py",
]

for path in required:
    assert path.is_file(), f"missing: {path.name}"

operator = (ROOT / "OperarIA.ps1").read_text(encoding="utf-8-sig")

for action in (
    "start",
    "stop",
    "restart",
    "status",
    "health",
    "validate",
    "diagnostics",
    "diagnostic-bundle",
):
    assert f'"{action}"' in operator, action

assert '[string]$HostAddress = "127.0.0.1"' in operator
assert '[string]$HostAddress = "0.0.0.0"' not in operator

for required_contract in (
    "PORT_IN_USE",
    "ALREADY_RUNNING",
    "START_FAILED",
    "Get-OwnedAnalyzerProcess",
    "Rotate-RuntimeLog",
    "Protect-DiagnosticText",
    "New-DiagnosticBundle",
    "[REDACTED]",
):
    assert required_contract in operator, required_contract

for forbidden in (
    "taskkill /IM python.exe",
    "Stop-Process -Name python",
):
    assert forbidden not in operator, forbidden

manifest_path = ROOT / "MANIFEST_SHA256.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

paths = {item["path"] for item in manifest["files"]}
assert "OperarIA.ps1" in paths

for forbidden in (
    "__pycache__",
    "diagnostics_",
    "analizador.pid",
    "analizador.out.log",
    "analizador.err.log",
):
    assert all(forbidden not in p for p in paths), forbidden

for item in manifest["files"]:
    path = ROOT / item["path"]
    assert path.is_file(), item["path"]
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == item["sha256"], item["path"]
    assert len(raw) == item["size"], item["path"]

print("PASS commercial_files")
print("PASS runtime_contract")
print("PASS secure_defaults")
print("PASS process_safety")
print("PASS diagnostics_safety")
print("PASS manifest_integrity")
print("PASS R10.20D COMMERCIAL V1 FINAL ACCEPTANCE")
