from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "OperarIA.ps1"

assert SCRIPT.exists(), "OperarIA.ps1 missing"

text = SCRIPT.read_text(encoding="utf-8-sig")

# Actions
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
    assert f'"{action}"' in text, f"missing action: {action}"

# Canonical runtime
assert "analizador_universal.py" in text
assert "127.0.0.1" in text

# Process ownership / PID
for item in (
    "Get-PortListenerPid",
    "Get-RegisteredPid",
    "Get-OwnedAnalyzerProcess",
    "Repair-StalePid",
):
    assert item in text, item

# Safety
for item in (
    "PORT_IN_USE",
    "ALREADY_RUNNING",
    "START_FAILED",
):
    assert item in text, item

# Diagnostics / logging
for item in (
    "Rotate-RuntimeLog",
    "Protect-DiagnosticText",
    "New-DiagnosticBundle",
):
    assert item in text, item

assert "5MB" in text
assert "Keep = 3" in text

# Never kill arbitrary Python processes.
for forbidden in (
    "taskkill /IM python.exe",
    "Stop-Process -Name python",
    "taskkill /F /IM python.exe",
):
    assert forbidden not in text, forbidden

# No public binding by default.
assert '[string]$HostAddress = "127.0.0.1"' in text
assert '[string]$HostAddress = "0.0.0.0"' not in text

# Secret sanitization contract.
assert re.search(r"authorization.*bearer", text, re.I | re.S)
assert re.search(r"password", text, re.I)
assert "[REDACTED]" in text

# Diagnostic bundle should only include sanitized runtime diagnostics/logs.
assert "Compress-Archive" in text
assert "knowledge" not in text.lower() or "knowledge" not in re.findall(
    r'New-DiagnosticBundle.*?switch \(\$Action\)',
    text,
    re.S
)[0].lower()

print("R10.20C.2 FORMAL CONTRACT: PASS")
