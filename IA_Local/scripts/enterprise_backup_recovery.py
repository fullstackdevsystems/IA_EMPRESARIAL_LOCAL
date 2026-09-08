"""Governed backup/restore of commercial persistent runtime state."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BACKUP_FORMAT = "IA_EMPRESARIAL_LOCAL_BACKUP"
BACKUP_VERSION = 2

RUNTIME_TREES = (
    "workspace/Reportes",
    "workspace/Conocimiento",
    "data/enterprise",
)

CONFIG_JSON_DIR = "config"

SECRET_RELATIVE_PATHS = {
    "config/enterprise.secret",
    "config/local-user.token",
}

VOLATILE_SUFFIXES = {
    ".lock",
    ".tmp",
    ".temp",
    ".pyc",
}

LEGACY_REPORTES_STORES = (
    ".tenants",
    ".identity",
    ".platform_config",
    ".sql_connections",
    ".registry",
)


class BackupError(ValueError):
    pass


def _safe(rel: str) -> str:
    value = str(rel or "").replace("\\", "/").strip()
    p = Path(value)

    if (
        not value
        or value.startswith(("/", "\\"))
        or p.is_absolute()
        or ".." in p.parts
        or ":" in value
        or "\\" in value
    ):
        raise BackupError("unsafe backup path")

    return value


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)

    return h.hexdigest()


def _is_volatile(path: Path) -> bool:
    name = path.name.lower()

    if name in {".ds_store", "thumbs.db"}:
        return True

    if path.suffix.lower() in VOLATILE_SUFFIXES:
        return True

    return False


def _is_secret_runtime_relative(relative: str) -> bool:
    return relative.replace("\\", "/").strip().lower() in SECRET_RELATIVE_PATHS


def _is_legacy_reportes_root(root: Path) -> bool:
    root = Path(root).resolve()

    if root.name.lower() == "reportes":
        return True

    return any(
        (root / name).exists()
        for name in LEGACY_REPORTES_STORES
    )


def _resolve_root_contract(root: Path):
    root = Path(root).resolve()

    # Modern contract:
    # --runtime-root points directly to IA_Local.
    if (
        (root / "workspace" / "Reportes").exists()
        or (root / "workspace" / "Conocimiento").exists()
        or (root / "data" / "enterprise").exists()
        or (root / "config").exists()
    ):
        return "runtime", root

    # Compatibility with R10.21 commercial CLI:
    # --runtime-root may point to ProductRoot and legacy state
    # may exist below ProductRoot/IA_Local/Reportes.
    legacy_from_product = (
        root
        / "IA_Local"
        / "Reportes"
    )

    if legacy_from_product.exists():
        return "legacy", legacy_from_product.resolve()

    # Compatibility with direct legacy API callers that pass
    # the Reportes directory itself.
    if _is_legacy_reportes_root(root):
        return "legacy", root

    # Empty/new roots are interpreted as modern RuntimeRoot.
    # backup() will fail closed if no persistent state exists.
    return "runtime", root


def _iter_files(root: Path):
    for file in sorted(root.rglob("*")):
        if file.is_file() and not _is_volatile(file):
            yield file


def _collect_runtime_files(runtime_root: Path):
    runtime_root = Path(runtime_root).resolve()
    items = []
    seen = set()

    for tree in RUNTIME_TREES:
        tree_root = runtime_root / tree

        if not tree_root.exists():
            continue

        for file in _iter_files(tree_root):
            relative = file.relative_to(runtime_root).as_posix()

            if _is_secret_runtime_relative(relative):
                continue

            archive_path = _safe("persistent/" + relative)
            key = archive_path.lower()

            if key in seen:
                raise BackupError("duplicate backup path")

            seen.add(key)
            items.append((file, archive_path))

    config_root = runtime_root / CONFIG_JSON_DIR

    if config_root.exists():
        for file in sorted(config_root.glob("*.json")):
            if not file.is_file() or _is_volatile(file):
                continue

            relative = file.relative_to(runtime_root).as_posix()

            if _is_secret_runtime_relative(relative):
                continue

            archive_path = _safe("persistent/" + relative)
            key = archive_path.lower()

            if key in seen:
                raise BackupError("duplicate backup path")

            seen.add(key)
            items.append((file, archive_path))

    return items


def _collect_legacy_reportes_files(reports_root: Path):
    reports_root = Path(reports_root).resolve()
    items = []
    seen = set()

    if not reports_root.exists():
        return items

    for file in _iter_files(reports_root):
        relative = file.relative_to(reports_root).as_posix()
        archive_path = _safe("persistent/workspace/Reportes/" + relative)
        key = archive_path.lower()

        if key in seen:
            raise BackupError("duplicate backup path")

        seen.add(key)
        items.append((file, archive_path))

    return items


def backup(runtime_root, output):
    requested_root = Path(runtime_root).resolve()
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    mode, root = _resolve_root_contract(
        requested_root
    )

    if mode == "legacy":
        files = _collect_legacy_reportes_files(root)
        root_contract = "legacy_reportes_root"
    else:
        files = _collect_runtime_files(root)
        root_contract = "runtime_root_is_IA_Local"

    if not files:
        raise BackupError("empty backup rejected")

    manifest_files = []

    with tempfile.TemporaryDirectory() as td:
        temp_zip = Path(td) / "backup.zip"

        with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as z:
            for source, archive_path in files:
                raw = source.read_bytes()

                manifest_files.append(
                    {
                        "path": archive_path,
                        "size": len(raw),
                        "sha256": _sha256_bytes(raw),
                    }
                )

                z.writestr(archive_path, raw)

            manifest = {
                "format": BACKUP_FORMAT,
                "version": BACKUP_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "root_contract": root_contract,
                "secret_policy": "runtime_secrets_excluded",
                "files": manifest_files,
                "total_files": len(manifest_files),
            }

            z.writestr(
                "backup_manifest.json",
                json.dumps(manifest, ensure_ascii=False, sort_keys=True),
            )

        shutil.copy2(temp_zip, output)

    return output


def _normalize_archive_payload_path(path: str) -> str:
    rel = _safe(path)

    if rel.startswith("persistent/"):
        rel = rel[len("persistent/") :]
    else:
        raise BackupError("backup path outside persistent namespace")

    # Legacy R10.21 backups used persistent/Reportes/*
    if rel.startswith("Reportes/"):
        rel = "workspace/" + rel

    allowed = (
        "workspace/Reportes/",
        "workspace/Conocimiento/",
        "data/enterprise/",
        "config/",
    )

    if not rel.startswith(allowed):
        raise BackupError("unsupported backup path")

    if _is_secret_runtime_relative(rel):
        raise BackupError("secret path rejected")

    return _safe(rel)


def _validate_archive(source: Path):
    with zipfile.ZipFile(source) as z:
        try:
            manifest = json.loads(z.read("backup_manifest.json"))
        except Exception as exc:
            raise BackupError("missing manifest") from exc

        names = set(z.namelist())
        seen = set()
        entries = []

        files = manifest.get("files", [])

        if not isinstance(files, list) or not files:
            raise BackupError("backup manifest empty")

        for entry in files:
            if not isinstance(entry, dict):
                raise BackupError("backup manifest invalid")

            archive_path = _safe(entry.get("path"))
            runtime_relative = _normalize_archive_payload_path(archive_path)
            key = archive_path.lower()

            if key in seen:
                raise BackupError("backup integrity mismatch")

            if archive_path not in names:
                raise BackupError("backup integrity mismatch")

            raw = z.read(archive_path)
            expected = str(entry.get("sha256") or "").lower()

            if _sha256_bytes(raw) != expected:
                raise BackupError("backup integrity mismatch")

            seen.add(key)
            entries.append((archive_path, runtime_relative, raw))

        if int(manifest.get("total_files", -1)) != len(entries):
            raise BackupError("backup manifest count mismatch")

        return manifest, entries


def _remove_path(path: Path):
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _copy_tree_contents(source: Path, destination: Path):
    for item in sorted(source.rglob("*")):
        if not item.is_file():
            continue

        relative = item.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)


def restore(runtime_root, source, *, _fail_after_stage=False):
    requested_root = Path(runtime_root).resolve()
    source = Path(source).resolve()

    mode, root = _resolve_root_contract(
        requested_root
    )

    legacy_reportes_root = (
        mode == "legacy"
    )

    manifest, entries = _validate_archive(source)

    with tempfile.TemporaryDirectory() as td:
        temp = Path(td)
        stage = temp / "stage"
        old = temp / "old"

        for _, runtime_relative, raw in entries:
            if legacy_reportes_root:
                if runtime_relative.startswith("workspace/Reportes/"):
                    target_relative = runtime_relative[len("workspace/Reportes/") :]
                else:
                    continue
            else:
                target_relative = runtime_relative

            target = stage / target_relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)

        if _fail_after_stage:
            raise BackupError("injected restore failure")

        if legacy_reportes_root:
            restore_roots = [
                item
                for item in stage.iterdir()
                if item.exists()
            ]

            moved = []

            try:
                old.mkdir(parents=True, exist_ok=True)

                for item in restore_roots:
                    live = root / item.name
                    previous = old / item.name

                    if live.exists():
                        shutil.move(str(live), str(previous))

                    shutil.move(str(item), str(live))
                    moved.append((live, previous))

            except Exception:
                for live, previous in reversed(moved):
                    _remove_path(live)

                    if previous.exists():
                        shutil.move(str(previous), str(live))

                raise

            return None

        root.mkdir(parents=True, exist_ok=True)
        old.mkdir(parents=True, exist_ok=True)

        managed_roots = (
            Path("workspace/Reportes"),
            Path("workspace/Conocimiento"),
            Path("data/enterprise"),
        )

        moved_roots = []
        config_old = old / "config"

        try:
            for relative in managed_roots:
                staged = stage / relative

                if not staged.exists():
                    continue

                live = root / relative
                previous = old / relative

                previous.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                live.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                if live.exists():
                    shutil.move(
                        str(live),
                        str(previous),
                    )

                shutil.move(
                    str(staged),
                    str(live),
                )

                moved_roots.append(
                    (live, previous)
                )

            staged_config = stage / "config"

            if staged_config.exists():
                live_config = root / "config"

                if live_config.exists():
                    shutil.copytree(
                        live_config,
                        config_old,
                    )

                live_config.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                _copy_tree_contents(
                    staged_config,
                    live_config,
                )

        except Exception:
            for live, previous in reversed(
                moved_roots
            ):
                _remove_path(live)

                if previous.exists():
                    live.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    shutil.move(
                        str(previous),
                        str(live),
                    )

            live_config = root / "config"

            if config_old.exists():
                _remove_path(live_config)

                shutil.move(
                    str(config_old),
                    str(live_config),
                )

            raise

    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("backup", "restore"))
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--backup-path")
    parser.add_argument("--restore-path")

    args = parser.parse_args()

    try:
        if args.action == "backup" and args.backup_path:
            backup(args.runtime_root, args.backup_path)
        elif args.action == "restore" and args.restore_path:
            restore(args.runtime_root, args.restore_path)
        else:
            raise BackupError("required path missing")

        print(json.dumps({"status": "PASS"}))
        return 0

    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "code": type(exc).__name__,
                    "message": str(exc),
                },
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())