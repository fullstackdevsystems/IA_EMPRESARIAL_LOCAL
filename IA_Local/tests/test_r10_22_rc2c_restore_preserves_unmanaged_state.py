from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(
    0,
    str(ROOT / "IA_Local" / "scripts"),
)

from enterprise_backup_recovery import backup, restore


def check(name, value):
    assert value, name
    print("PASS", name)


def put(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    source = base / "source" / "IA_Local"
    target = base / "target" / "IA_Local"

    source.mkdir(parents=True)
    target.mkdir(parents=True)

    # Managed persistent state in backup source.
    put(
        source,
        "workspace/Reportes/.tenants/tenants.json",
        "new-tenants",
    )
    put(
        source,
        "workspace/Conocimiento/doc.txt",
        "new-knowledge",
    )
    put(
        source,
        "data/enterprise/enterprise_ai.sqlite3",
        "new-db",
    )
    put(
        source,
        "config/business_rules.json",
        "new-rules",
    )

    # Existing managed state in restore target.
    put(
        target,
        "workspace/Reportes/.tenants/tenants.json",
        "old-tenants",
    )
    put(
        target,
        "workspace/Conocimiento/old.txt",
        "old-knowledge",
    )
    put(
        target,
        "data/enterprise/enterprise_ai.sqlite3",
        "old-db",
    )
    put(
        target,
        "config/business_rules.json",
        "old-rules",
    )

    # Unmanaged siblings MUST survive restore.
    put(
        target,
        "workspace/Usuario/keep.txt",
        "workspace-must-survive",
    )
    put(
        target,
        "data/custom/keep.txt",
        "data-must-survive",
    )

    # Runtime secrets MUST survive existing installation restore,
    # but must never come from the backup archive.
    put(
        target,
        "config/enterprise.secret",
        "existing-secret-must-survive",
    )
    put(
        target,
        "config/local-user.token",
        "existing-token-must-survive",
    )

    archive = base / "backup.zip"

    backup(source, archive)

    restore(target, archive)

    check(
        "managed_reportes_restored",
        (
            target
            / "workspace/Reportes/.tenants/tenants.json"
        ).read_text(encoding="utf-8")
        == "new-tenants",
    )

    check(
        "managed_knowledge_restored",
        (
            target
            / "workspace/Conocimiento/doc.txt"
        ).read_text(encoding="utf-8")
        == "new-knowledge",
    )

    check(
        "managed_enterprise_data_restored",
        (
            target
            / "data/enterprise/enterprise_ai.sqlite3"
        ).read_text(encoding="utf-8")
        == "new-db",
    )

    check(
        "managed_config_restored",
        (
            target
            / "config/business_rules.json"
        ).read_text(encoding="utf-8")
        == "new-rules",
    )

    check(
        "unmanaged_workspace_preserved",
        (
            target
            / "workspace/Usuario/keep.txt"
        ).read_text(encoding="utf-8")
        == "workspace-must-survive",
    )

    check(
        "unmanaged_data_preserved",
        (
            target
            / "data/custom/keep.txt"
        ).read_text(encoding="utf-8")
        == "data-must-survive",
    )

    check(
        "existing_secret_preserved",
        (
            target
            / "config/enterprise.secret"
        ).read_text(encoding="utf-8")
        == "existing-secret-must-survive",
    )

    check(
        "existing_token_preserved",
        (
            target
            / "config/local-user.token"
        ).read_text(encoding="utf-8")
        == "existing-token-must-survive",
    )

print("PASS R10.22 RC.2C NON-MANAGED STATE PRESERVATION")
