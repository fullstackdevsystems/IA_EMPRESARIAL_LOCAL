import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNINSTALL = ROOT / "DesinstalarIA.ps1"
BACKUP_MODULE = ROOT / "IA_Local" / "scripts" / "enterprise_backup_recovery.py"

failures = []

def check(name, ok):
    print(("PASS" if ok else "FAIL"), name)
    if not ok:
        failures.append(name)

def run_ps(args):
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(UNINSTALL),
            *args,
        ],
        capture_output=True,
        text=True,
    )

check("uninstall_script_exists", UNINSTALL.is_file())
check("uninstall_batch_exists", (ROOT / "DESINSTALAR_IA_EMPRESARIAL_LOCAL.bat").is_file())
check("uninstall_guide_exists", (ROOT / "LEEME_DESINSTALACION_Y_RECUPERACION.txt").is_file())
source = UNINSTALL.read_text(encoding="utf-8")
check("default_preserves_business_data", "PRESERVE_BUSINESS_DATA" in source and "BUSINESS_DATA: RETAINED" in source)
check("full_removal_requires_explicit_confirmation", "ConfirmRemoveBusinessData" in source and "CONFIRMATION_REQUIRED" in source)
check("full_removal_requires_backup", "BACKUP_REQUIRED" in source and "Validate-GovernedBackup" in source)
check("rollback_guidance_present", "REINSTALL_RECOVERY" in source and "RECOVERY_BACKUP" in source)

with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    preserve = base / "preserve-install"
    runtime = preserve / "IA_Local"
    (runtime / "scripts").mkdir(parents=True)
    (runtime / "workspace" / "Conocimiento").mkdir(parents=True)
    (runtime / "data" / "enterprise").mkdir(parents=True)
    (runtime / "config").mkdir(parents=True)
    (preserve / ".venv").mkdir()
    (preserve / "OperarIA.ps1").write_text(
        "param([string]$Action,[string]$RuntimeRoot); if($Action -eq 'stop'){Write-Host 'STOP: PASS'; exit 0}; exit 1",
        encoding="utf-8",
    )
    (preserve / "InstalarLimpio.ps1").write_text("managed", encoding="utf-8")
    (runtime / "scripts" / "managed.py").write_text("managed", encoding="utf-8")
    state = runtime / "data" / "enterprise" / "state.json"
    knowledge = runtime / "workspace" / "Conocimiento" / "knowledge.txt"
    config = runtime / "config" / "company.json"
    state.write_text('{"value":"keep"}', encoding="utf-8")
    knowledge.write_text("keep knowledge", encoding="utf-8")
    config.write_text('{"company":"keep"}', encoding="utf-8")

    result = run_ps(["-InstallPath", str(preserve)])
    check("preserve_uninstall_exit_zero", result.returncode == 0)
    check("preserve_uninstall_reports_retained", "BUSINESS_DATA: RETAINED" in result.stdout)
    check("managed_runtime_removed", not (runtime / "scripts").exists())
    check("venv_removed", not (preserve / ".venv").exists())
    check("business_state_preserved", state.read_text(encoding="utf-8") == '{"value":"keep"}')
    check("knowledge_preserved", knowledge.read_text(encoding="utf-8") == "keep knowledge")
    check("config_preserved", config.read_text(encoding="utf-8") == '{"company":"keep"}')
    check("retained_notice_created", (preserve / "UNINSTALL_RETAINED_DATA.txt").is_file())

    refusal = base / "refusal-install"
    (refusal / "IA_Local" / "data" / "enterprise").mkdir(parents=True)
    marker = refusal / "IA_Local" / "data" / "enterprise" / "marker.json"
    marker.write_text('{"keep":true}', encoding="utf-8")
    denied = run_ps(["-InstallPath", str(refusal), "-RemoveBusinessData"])
    check("full_remove_without_confirmation_fails", denied.returncode != 0)
    check("failed_full_remove_preserves_state", marker.is_file())

    full = base / "full-remove-install"
    full_runtime = full / "IA_Local"
    (full_runtime / "workspace" / "Reportes").mkdir(parents=True)
    (full_runtime / "data" / "enterprise").mkdir(parents=True)
    (full_runtime / "workspace" / "Reportes" / "report.txt").write_text("report", encoding="utf-8")
    (full_runtime / "data" / "enterprise" / "state.json").write_text('{"full":"remove"}', encoding="utf-8")
    (full / "OperarIA.ps1").write_text(
        "param([string]$Action,[string]$RuntimeRoot); if($Action -eq 'stop'){Write-Host 'STOP: PASS'; exit 0}; exit 1",
        encoding="utf-8",
    )

    backup_zip = base / "governed-backup.zip"
    backup_run = subprocess.run(
        [
            sys.executable,
            str(BACKUP_MODULE),
            "backup",
            "--runtime-root",
            str(full_runtime),
            "--backup-path",
            str(backup_zip),
        ],
        capture_output=True,
        text=True,
    )
    check("governed_backup_created_for_full_remove", backup_run.returncode == 0 and backup_zip.is_file())

    removed = run_ps([
        "-InstallPath",
        str(full),
        "-RemoveBusinessData",
        "-ConfirmRemoveBusinessData",
        "-BackupPath",
        str(backup_zip),
    ])
    check("full_remove_exit_zero", removed.returncode == 0)
    check("full_remove_reports_removed", "BUSINESS_DATA: REMOVED" in removed.stdout)
    check("full_remove_deletes_install_root", not full.exists())
    check("full_remove_keeps_external_backup", backup_zip.is_file())

if failures:
    raise AssertionError("R10.24D6 uninstall failures: " + ", ".join(failures))

print("R10_24D6_UNINSTALL_CONTRACT=PASS")
