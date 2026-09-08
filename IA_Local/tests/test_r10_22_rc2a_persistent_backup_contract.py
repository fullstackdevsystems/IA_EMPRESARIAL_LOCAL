from pathlib import Path
import json
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BACKUP_ENGINE = ROOT / "IA_Local" / "scripts" / "enterprise_backup_recovery.py"
OPERAR = ROOT / "OperarIA.ps1"

failures = []


def check(name, value):
    ok = bool(value)
    print(("PASS" if ok else "FAIL"), name)
    if not ok:
        failures.append(name)


def put(root: Path, relative: str, content: str):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


with tempfile.TemporaryDirectory() as td:
    temp = Path(td)

    # RuntimeRoot contract = .../IA_Local
    runtime = temp / "product" / "IA_Local"
    runtime.mkdir(parents=True)

    # -----------------------------
    # Persistent Reportes plane
    # -----------------------------
    put(
        runtime,
        "workspace/Reportes/.tenants/tenants.json",
        '{"tenant_id":"demo"}',
    )
    put(
        runtime,
        "workspace/Reportes/.identity/identity.json",
        '{"users":[]}',
    )
    put(
        runtime,
        "workspace/Reportes/.platform_config/platform_config.json",
        '{"global":{}}',
    )
    put(
        runtime,
        "workspace/Reportes/.sql_connections/demo/admin/_/_/sql.json",
        '{"read_only":true}',
    )
    put(
        runtime,
        "workspace/Reportes/.registry/demo/admin/_/_/run-demo.json",
        '{"run_id":"run-demo"}',
    )
    put(
        runtime,
        "workspace/Reportes/dashboard-demo.html",
        "<html>demo</html>",
    )

    # -----------------------------
    # Knowledge/documents plane
    # -----------------------------
    put(
        runtime,
        "workspace/Conocimiento/demo/documento.txt",
        "conocimiento persistente",
    )

    # -----------------------------
    # Enterprise DB/vector plane
    # -----------------------------
    put(
        runtime,
        "data/enterprise/enterprise_ai.sqlite3",
        "sqlite-demo",
    )
    put(
        runtime,
        "data/enterprise/vectors.sqlite3",
        "vectors-demo",
    )
    put(
        runtime,
        "data/enterprise/qdrant/meta.json",
        '{"qdrant":"demo"}',
    )

    # -----------------------------
    # Governed config plane
    # -----------------------------
    config_files = {
        "business_context.json": '{"company":"demo"}',
        "business_rules.json": '{"rules":[]}',
        "enterprise_knowledge.json": '{"entries":[]}',
        "enterprise_metric_rules.json": '{"rules":[]}',
        "enterprise_queries.json": '{"queries":[]}',
        "enterprise_sources.json": '{"sources":[]}',
        "enterprise_ai.json": '{"version":"demo"}',
    }

    for name, content in config_files.items():
        put(runtime, f"config/{name}", content)

    # Explicit secrets: must NOT be serialized in ordinary backup.
    put(runtime, "config/enterprise.secret", "DO_NOT_BACKUP_SECRET")
    put(runtime, "config/local-user.token", "DO_NOT_BACKUP_TOKEN")

    # -----------------------------
    # OperarIA RuntimeRoot contract
    # -----------------------------
    operar_text = OPERAR.read_text(encoding="utf-8-sig")

    bad_runtime_lines = [
        line
        for line in operar_text.splitlines()
        if "--runtime-root" in line
        and "$ProductRoot" in line
        and (
            "$Onboarding" in line
            or "$BackupEngine" in line
        )
    ]

    check(
        "operaria_uses_runtime_root_for_internal_cli",
        len(bad_runtime_lines) == 0,
    )

    # -----------------------------
    # Backup CLI
    # -----------------------------
    backup_zip = temp / "backup.zip"

    run = subprocess.run(
        [
            sys.executable,
            str(BACKUP_ENGINE),
            "backup",
            "--runtime-root",
            str(runtime),
            "--backup-path",
            str(backup_zip),
        ],
        capture_output=True,
        text=True,
    )

    check(
        "backup_cli_success",
        run.returncode == 0 and backup_zip.is_file(),
    )

    names = set()
    manifest = {}

    if backup_zip.is_file():
        with zipfile.ZipFile(backup_zip) as z:
            names = set(z.namelist())

            if "backup_manifest.json" in names:
                manifest = json.loads(
                    z.read("backup_manifest.json")
                )

    required = {
        "persistent/workspace/Reportes/.tenants/tenants.json",
        "persistent/workspace/Reportes/.identity/identity.json",
        "persistent/workspace/Reportes/.platform_config/platform_config.json",
        "persistent/workspace/Reportes/.sql_connections/demo/admin/_/_/sql.json",
        "persistent/workspace/Reportes/.registry/demo/admin/_/_/run-demo.json",
        "persistent/workspace/Reportes/dashboard-demo.html",
        "persistent/workspace/Conocimiento/demo/documento.txt",
        "persistent/data/enterprise/enterprise_ai.sqlite3",
        "persistent/data/enterprise/vectors.sqlite3",
        "persistent/data/enterprise/qdrant/meta.json",
        "persistent/config/business_context.json",
        "persistent/config/business_rules.json",
        "persistent/config/enterprise_knowledge.json",
        "persistent/config/enterprise_metric_rules.json",
        "persistent/config/enterprise_queries.json",
        "persistent/config/enterprise_sources.json",
        "persistent/config/enterprise_ai.json",
    }

    missing = sorted(required - names)

    check(
        "backup_contains_all_required_persistent_state",
        not missing,
    )

    if missing:
        print("MISSING:")
        for item in missing:
            print(" ", item)

    secret_paths = {
        "persistent/config/enterprise.secret",
        "persistent/config/local-user.token",
    }

    check(
        "backup_excludes_runtime_secrets",
        not bool(names & secret_paths),
    )

    persistent_entries = [
        name
        for name in names
        if name.startswith("persistent/")
        and not name.endswith("/")
    ]

    check(
        "backup_manifest_nonempty",
        int(manifest.get("total_files", 0)) > 0,
    )

    check(
        "backup_manifest_matches_archive",
        int(manifest.get("total_files", -1))
        == len(persistent_entries),
    )

    # -----------------------------
    # Restore into clean runtime
    # -----------------------------
    restored = temp / "restored" / "IA_Local"
    restored.mkdir(parents=True)

    restore_run = subprocess.run(
        [
            sys.executable,
            str(BACKUP_ENGINE),
            "restore",
            "--runtime-root",
            str(restored),
            "--restore-path",
            str(backup_zip),
        ],
        capture_output=True,
        text=True,
    )

    check(
        "restore_cli_success",
        restore_run.returncode == 0,
    )

    restore_required = {
        "workspace/Reportes/.tenants/tenants.json":
            '{"tenant_id":"demo"}',

        "workspace/Reportes/.registry/demo/admin/_/_/run-demo.json":
            '{"run_id":"run-demo"}',

        "workspace/Reportes/dashboard-demo.html":
            "<html>demo</html>",

        "workspace/Conocimiento/demo/documento.txt":
            "conocimiento persistente",

        "data/enterprise/enterprise_ai.sqlite3":
            "sqlite-demo",

        "config/business_rules.json":
            '{"rules":[]}',
    }

    restored_ok = True

    for relative, expected in restore_required.items():
        path = restored / relative

        if (
            not path.is_file()
            or path.read_text(encoding="utf-8") != expected
        ):
            restored_ok = False
            print("RESTORE_MISSING_OR_INVALID:", relative)

    check(
        "restore_preserves_complete_persistent_state",
        restored_ok,
    )

    check(
        "restore_does_not_create_secret",
        not (restored / "config/enterprise.secret").exists()
        and not (restored / "config/local-user.token").exists(),
    )

    # -----------------------------
    # Empty backup must fail closed
    # -----------------------------
    empty_runtime = temp / "empty" / "IA_Local"
    empty_runtime.mkdir(parents=True)

    empty_zip = temp / "empty.zip"

    empty_run = subprocess.run(
        [
            sys.executable,
            str(BACKUP_ENGINE),
            "backup",
            "--runtime-root",
            str(empty_runtime),
            "--backup-path",
            str(empty_zip),
        ],
        capture_output=True,
        text=True,
    )

    check(
        "empty_backup_rejected",
        empty_run.returncode != 0,
    )

if failures:
    raise AssertionError(
        "RC.2A expected contract failures: "
        + ", ".join(failures)
    )

print("PASS R10.22 RC.2A PERSISTENT BACKUP CONTRACT")
