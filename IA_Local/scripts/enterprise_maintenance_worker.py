"""Out-of-process governed maintenance worker for backup/recovery."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
import zipfile

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from enterprise_backup_recovery import (
    BACKUP_FORMAT,
    BACKUP_VERSION,
    BackupError,
    _validate_archive,
    backup,
    restore,
)


TERMINAL_STATES = {
    "COMPLETED",
    "FAILED",
}

ACTIVE_STATES = {
    "QUEUED",
    "UPLOADING",
    "STOPPING",
    "VALIDATING",
    "BACKING_UP",
    "RESTORING",
    "STARTING",
    "VERIFYING",
}


class MaintenanceError(ValueError):
    def __init__(
        self,
        code: str,
        message: str = "",
    ):
        self.code = str(code)
        super().__init__(
            message or self.code
        )


class MaintenanceBusy(MaintenanceError):
    pass


def utcnow() -> str:
    return (
        datetime.now(
            timezone.utc
        )
        .isoformat()
    )


def _normalize_job_id(
    job_id: str,
) -> str:
    try:
        return str(
            uuid.UUID(
                str(job_id)
            )
        )
    except Exception as exc:
        raise MaintenanceError(
            "MAINTENANCE_JOB_INVALID"
        ) from exc


def new_job_id() -> str:
    return str(
        uuid.uuid4()
    )


def runtime_root(
    product_root: str | Path,
) -> Path:
    return (
        Path(product_root)
        .resolve()
        / "IA_Local"
    )


def maintenance_root(
    product_root: str | Path,
) -> Path:
    root = (
        runtime_root(
            product_root
        )
        / "logs"
        / "maintenance"
    )

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    for name in (
        "jobs",
        "uploads",
        "artifacts",
        "worker-logs",
    ):
        (
            root
            / name
        ).mkdir(
            parents=True,
            exist_ok=True,
        )

    return root


def job_path(
    product_root: str | Path,
    job_id: str,
) -> Path:
    normalized = (
        _normalize_job_id(
            job_id
        )
    )

    return (
        maintenance_root(
            product_root
        )
        / "jobs"
        / f"{normalized}.json"
    )


def restore_upload_path(
    product_root: str | Path,
    job_id: str,
) -> Path:
    normalized = (
        _normalize_job_id(
            job_id
        )
    )

    return (
        maintenance_root(
            product_root
        )
        / "uploads"
        / f"{normalized}.zip"
    )


def backup_artifact_path(
    product_root: str | Path,
    job_id: str,
) -> Path:
    normalized = (
        _normalize_job_id(
            job_id
        )
    )

    return (
        maintenance_root(
            product_root
        )
        / "artifacts"
        / f"{normalized}.zip"
    )


def active_lock_path(
    product_root: str | Path,
) -> Path:
    return (
        maintenance_root(
            product_root
        )
        / "active.lock"
    )


def sha256_file(
    path: str | Path,
) -> str:
    digest = hashlib.sha256()

    with Path(path).open(
        "rb"
    ) as stream:
        for chunk in iter(
            lambda:
                stream.read(
                    1024 * 1024
                ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


def max_upload_bytes() -> int:
    raw = os.environ.get(
        "IA_MAINTENANCE_MAX_UPLOAD_MB",
        "8192",
    )

    try:
        value = int(raw)
    except Exception:
        value = 8192

    value = max(
        1,
        min(
            value,
            65536,
        ),
    )

    return (
        value
        * 1024
        * 1024
    )


def max_expanded_bytes() -> int:
    raw = os.environ.get(
        "IA_MAINTENANCE_MAX_EXPANDED_MB",
        "32768",
    )

    try:
        value = int(raw)
    except Exception:
        value = 32768

    value = max(
        1,
        min(
            value,
            131072,
        ),
    )

    return (
        value
        * 1024
        * 1024
    )


def strict_validate_archive(
    source: str | Path,
) -> Dict[str, Any]:
    path = Path(
        source
    ).resolve()

    if not path.is_file():
        raise MaintenanceError(
            "BACKUP_NOT_FOUND"
        )

    try:
        with zipfile.ZipFile(
            path
        ) as archive:
            infos = [
                item
                for item
                in archive.infolist()
                if not item.is_dir()
            ]

            if len(infos) > 250000:
                raise MaintenanceError(
                    "BACKUP_TOO_MANY_FILES"
                )

            expanded = sum(
                int(item.file_size)
                for item in infos
            )

            if (
                expanded
                > max_expanded_bytes()
            ):
                raise MaintenanceError(
                    "BACKUP_EXPANDED_TOO_LARGE"
                )

            try:
                manifest = json.loads(
                    archive.read(
                        "backup_manifest.json"
                    )
                )
            except Exception as exc:
                raise MaintenanceError(
                    "BACKUP_MANIFEST_INVALID"
                ) from exc

    except MaintenanceError:
        raise

    except zipfile.BadZipFile as exc:
        raise MaintenanceError(
            "BACKUP_ZIP_INVALID"
        ) from exc

    except Exception as exc:
        raise MaintenanceError(
            "BACKUP_VALIDATION_FAILED"
        ) from exc

    if not isinstance(
        manifest,
        dict,
    ):
        raise MaintenanceError(
            "BACKUP_MANIFEST_INVALID"
        )

    if (
        manifest.get(
            "format"
        )
        != BACKUP_FORMAT
    ):
        raise MaintenanceError(
            "BACKUP_FORMAT_INVALID"
        )

    try:
        version = int(
            manifest.get(
                "version"
            )
        )
    except Exception as exc:
        raise MaintenanceError(
            "BACKUP_VERSION_INVALID"
        ) from exc

    if version != BACKUP_VERSION:
        raise MaintenanceError(
            "BACKUP_VERSION_UNSUPPORTED"
        )

    if (
        manifest.get(
            "secret_policy"
        )
        != "runtime_secrets_excluded"
    ):
        raise MaintenanceError(
            "BACKUP_SECRET_POLICY_INVALID"
        )

    try:
        validated_manifest, entries = (
            _validate_archive(
                path
            )
        )
    except BackupError as exc:
        raise MaintenanceError(
            "BACKUP_INTEGRITY_INVALID"
        ) from exc

    return {
        "format":
            validated_manifest.get(
                "format"
            ),
        "version":
            int(
                validated_manifest.get(
                    "version"
                )
            ),
        "total_files":
            len(entries),
        "expanded_bytes":
            expanded,
    }


def _read_job_internal(
    product_root: str | Path,
    job_id: str,
) -> Dict[str, Any]:
    path = job_path(
        product_root,
        job_id,
    )

    if not path.is_file():
        raise MaintenanceError(
            "MAINTENANCE_JOB_NOT_FOUND"
        )

    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        raise MaintenanceError(
            "MAINTENANCE_JOB_INVALID"
        ) from exc

    if not isinstance(
        data,
        dict,
    ):
        raise MaintenanceError(
            "MAINTENANCE_JOB_INVALID"
        )

    return data



def _write_job(
    product_root: str | Path,
    data: Dict[str, Any],
    *,
    touch_updated_at: bool = True,
) -> Dict[str, Any]:
    job_id = _normalize_job_id(
        data.get(
            "job_id"
        )
    )

    path = job_path(
        product_root,
        job_id,
    )

    payload = dict(
        data
    )

    payload[
        "job_id"
    ] = job_id

    if touch_updated_at:
        payload[
            "updated_at"
        ] = utcnow()

    elif not payload.get(
        "updated_at"
    ):
        payload[
            "updated_at"
        ] = utcnow()

    temp = path.with_suffix(
        ".json.tmp"
    )

    temp.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    temp.replace(
        path
    )

    return payload


def public_job(
    data: Dict[str, Any],
) -> Dict[str, Any]:
    allowed = (
        "job_id",
        "operation",
        "status",
        "created_at",
        "updated_at",
        "error_code",
        "total_files",
        "size_bytes",
        "sha256",
        "download_ready",
    )

    return {
        key:
            data.get(key)
        for key in allowed
        if key in data
    }


def get_public_job(
    product_root: str | Path,
    job_id: str,
) -> Dict[str, Any]:
    return public_job(
        _read_job_internal(
            product_root,
            job_id,
        )
    )


def list_public_jobs(
    product_root: str | Path,
    limit: int = 20,
):
    jobs_dir = (
        maintenance_root(
            product_root
        )
        / "jobs"
    )

    rows = []

    for path in jobs_dir.glob(
        "*.json"
    ):
        try:
            data = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

            if isinstance(
                data,
                dict,
            ):
                rows.append(
                    public_job(
                        data
                    )
                )

        except Exception:
            continue

    rows.sort(
        key=lambda item:
            str(
                item.get(
                    "updated_at"
                )
                or ""
            ),
        reverse=True,
    )

    return rows[
        : max(
            1,
            min(
                int(limit),
                100,
            ),
        )
    ]


def update_job(
    product_root: str | Path,
    job_id: str,
    **changes,
) -> Dict[str, Any]:
    data = _read_job_internal(
        product_root,
        job_id,
    )

    data.update(
        changes
    )

    return _write_job(
        product_root,
        data,
    )




def stale_job_seconds() -> int:
    raw = os.environ.get(
        "IA_MAINTENANCE_STALE_SECONDS",
        "1800",
    )

    try:
        value = int(
            raw
        )
    except Exception:
        value = 1800

    return max(
        300,
        min(
            value,
            86400,
        ),
    )


def backup_retention_count() -> int:
    raw = os.environ.get(
        "IA_MAINTENANCE_BACKUP_RETENTION_COUNT",
        "10",
    )

    try:
        value = int(
            raw
        )
    except Exception:
        value = 10

    return max(
        1,
        min(
            value,
            1000,
        ),
    )


def _job_is_stale(
    data: Dict[str, Any],
) -> bool:
    raw = str(
        data.get(
            "updated_at"
        )
        or ""
    ).strip()

    if not raw:
        return False

    try:
        stamp = datetime.fromisoformat(
            raw.replace(
                "Z",
                "+00:00",
            )
        )

        if stamp.tzinfo is None:
            stamp = stamp.replace(
                tzinfo=timezone.utc
            )

        age = (
            datetime.now(
                timezone.utc
            )
            - stamp.astimezone(
                timezone.utc
            )
        ).total_seconds()

    except Exception:
        return False

    return (
        age
        >= stale_job_seconds()
    )


def _worker_process_matches(
    job_id: str,
    worker_pid: Any,
) -> Optional[bool]:
    normalized = _normalize_job_id(
        job_id
    )

    try:
        pid = int(
            worker_pid
        )
    except Exception:
        return False

    if pid <= 0:
        return False

    if os.name != "nt":
        try:
            os.kill(
                pid,
                0,
            )

            return True

        except ProcessLookupError:
            return False

        except PermissionError:
            return None

        except Exception:
            return None

    command = (
        "$ErrorActionPreference='Stop';"
        "$p=Get-CimInstance Win32_Process "
        f'-Filter "ProcessId = {pid}";'
        "if($null -eq $p){exit 3};"
        "$c=[string]$p.CommandLine;"
        "if([string]::IsNullOrWhiteSpace($c)){exit 5};"
        "if("
        "$c.Contains('enterprise_maintenance_worker.py') "
        "-and $c.Contains('--job-id') "
        f"-and $c.Contains('{normalized}')"
        "){exit 0};"
        "exit 4"
    )

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                command,
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=8,
        )
    except Exception:
        return None

    if result.returncode == 0:
        return True

    if result.returncode in {
        3,
        4,
    }:
        return False

    return None


def _mark_interrupted_job(
    product_root: str | Path,
    job_id: str,
    data: Dict[str, Any],
) -> None:
    if (
        data.get(
            "operation"
        )
        == "restore"
    ):
        restore_upload_path(
            product_root,
            job_id,
        ).unlink(
            missing_ok=True
        )

    fail_job(
        product_root,
        job_id,
        "MAINTENANCE_INTERRUPTED",
    )


def prune_backup_artifacts(
    product_root: str | Path,
    *,
    keep: Optional[int] = None,
):
    product = Path(
        product_root
    ).resolve()

    if keep is None:
        keep = backup_retention_count()

    try:
        keep = int(
            keep
        )
    except Exception as exc:
        raise MaintenanceError(
            "BACKUP_RETENTION_INVALID"
        ) from exc

    if keep < 1:
        raise MaintenanceError(
            "BACKUP_RETENTION_INVALID"
        )

    jobs_dir = (
        maintenance_root(
            product
        )
        / "jobs"
    )

    candidates = []

    for path in jobs_dir.glob(
        "*.json"
    ):
        try:
            data = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            continue

        if not isinstance(
            data,
            dict,
        ):
            continue

        if (
            data.get(
                "operation"
            )
            != "backup"
            or data.get(
                "status"
            )
            != "COMPLETED"
            or not data.get(
                "download_ready"
            )
        ):
            continue

        try:
            job_id = _normalize_job_id(
                data.get(
                    "job_id"
                )
            )
        except Exception:
            continue

        artifact = backup_artifact_path(
            product,
            job_id,
        )

        if not artifact.is_file():
            data[
                "download_ready"
            ] = False

            _write_job(
                product,
                data,
                touch_updated_at=False,
            )

            continue

        candidates.append(
            (
                str(
                    data.get(
                        "updated_at"
                    )
                    or ""
                ),
                job_id,
                artifact,
                data,
            )
        )

    candidates.sort(
        key=lambda row:
            row[0],
        reverse=True,
    )

    removed = []

    for (
        _updated,
        job_id,
        artifact,
        data,
    ) in candidates[
        keep:
    ]:
        artifact.unlink(
            missing_ok=True
        )

        data[
            "download_ready"
        ] = False

        data[
            "artifact_expired_at"
        ] = utcnow()

        _write_job(
            product,
            data,
            touch_updated_at=False,
        )

        removed.append(
            job_id
        )

    return removed



def _acquire_lock(
    product_root: str | Path,
    job_id: str,
) -> None:
    lock = active_lock_path(
        product_root
    )

    for _ in range(3):
        try:
            descriptor = os.open(
                str(lock),
                os.O_CREAT
                | os.O_EXCL
                | os.O_WRONLY,
            )

            try:
                os.write(
                    descriptor,
                    _normalize_job_id(
                        job_id
                    ).encode(
                        "ascii"
                    ),
                )

            finally:
                os.close(
                    descriptor
                )

            return

        except FileExistsError:
            try:
                existing_id = (
                    _normalize_job_id(
                        lock.read_text(
                            encoding="ascii"
                        ).strip()
                    )
                )

                existing = (
                    _read_job_internal(
                        product_root,
                        existing_id,
                    )
                )

            except Exception as exc:
                # Unknown lock ownership always fails closed.
                raise MaintenanceBusy(
                    "MAINTENANCE_BUSY"
                ) from exc

            if (
                existing.get(
                    "status"
                )
                in TERMINAL_STATES
            ):
                try:
                    lock.unlink(
                        missing_ok=True
                    )
                except Exception as exc:
                    raise MaintenanceBusy(
                        "MAINTENANCE_BUSY"
                    ) from exc

                continue

            worker_pid = existing.get(
                "worker_pid"
            )

            if worker_pid is not None:
                process_state = (
                    _worker_process_matches(
                        existing_id,
                        worker_pid,
                    )
                )

                if process_state is True:
                    raise MaintenanceBusy(
                        "MAINTENANCE_BUSY"
                    )

                if process_state is None:
                    # If process identity cannot be checked,
                    # never guess that maintenance is abandoned.
                    raise MaintenanceBusy(
                        "MAINTENANCE_BUSY"
                    )

                try:
                    _mark_interrupted_job(
                        product_root,
                        existing_id,
                        existing,
                    )
                except Exception as exc:
                    raise MaintenanceBusy(
                        "MAINTENANCE_BUSY"
                    ) from exc

                continue

            # QUEUED / UPLOADING jobs briefly have no worker PID.
            # Only reconcile them after a conservative stale lease.
            if not _job_is_stale(
                existing
            ):
                raise MaintenanceBusy(
                    "MAINTENANCE_BUSY"
                )

            try:
                _mark_interrupted_job(
                    product_root,
                    existing_id,
                    existing,
                )
            except Exception as exc:
                raise MaintenanceBusy(
                    "MAINTENANCE_BUSY"
                ) from exc

            continue

    raise MaintenanceBusy(
        "MAINTENANCE_BUSY"
    )


def release_job_lock(
    product_root: str | Path,
    job_id: str,
) -> None:
    lock = active_lock_path(
        product_root
    )

    if not lock.exists():
        return

    try:
        current = (
            lock.read_text(
                encoding="ascii"
            )
            .strip()
        )
    except Exception:
        return

    if current == _normalize_job_id(
        job_id
    ):
        lock.unlink(
            missing_ok=True
        )



def create_job(
    product_root: str | Path,
    operation: str,
    actor_user_id: str,
    *,
    job_id: Optional[str] = None,
    input_sha256: Optional[str] = None,
    runtime_port: int = 8090,
    restart_after: bool = True,
) -> Dict[str, Any]:
    operation = str(
        operation
    ).strip().lower()

    if operation not in {
        "backup",
        "restore",
    }:
        raise MaintenanceError(
            "MAINTENANCE_OPERATION_INVALID"
        )

    job_id = (
        _normalize_job_id(
            job_id
        )
        if job_id
        else new_job_id()
    )

    try:
        runtime_port = int(
            runtime_port
        )
    except Exception as exc:
        raise MaintenanceError(
            "RUNTIME_PORT_INVALID"
        ) from exc

    if not (
        1
        <= runtime_port
        <= 65535
    ):
        raise MaintenanceError(
            "RUNTIME_PORT_INVALID"
        )

    _acquire_lock(
        product_root,
        job_id,
    )

    now = utcnow()

    data = {
        "job_id":
            job_id,
        "operation":
            operation,
        "status":
            "QUEUED",
        "created_at":
            now,
        "updated_at":
            now,
        "actor_user_id":
            str(
                actor_user_id
                or ""
            ),
        "runtime_port":
            runtime_port,
        "restart_after":
            bool(
                restart_after
            ),
        "download_ready":
            False,
    }

    if input_sha256:
        data[
            "input_sha256"
        ] = str(
            input_sha256
        ).lower()

    try:
        return _write_job(
            product_root,
            data,
        )

    except Exception:
        release_job_lock(
            product_root,
            job_id,
        )

        raise


def fail_job(
    product_root: str | Path,
    job_id: str,
    error_code: str,
) -> None:
    try:
        update_job(
            product_root,
            job_id,
            status="FAILED",
            error_code=str(
                error_code
            ),
            download_ready=False,
        )
    finally:
        release_job_lock(
            product_root,
            job_id,
        )


def launch_worker(
    product_root: str | Path,
    job_id: str,
) -> int:
    product = Path(
        product_root
    ).resolve()

    script = (
        product
        / "IA_Local"
        / "scripts"
        / "enterprise_maintenance_worker.py"
    )

    if not script.is_file():
        raise MaintenanceError(
            "MAINTENANCE_WORKER_NOT_FOUND"
        )

    normalized = _normalize_job_id(
        job_id
    )

    log = (
        maintenance_root(
            product
        )
        / "worker-logs"
        / f"{normalized}.log"
    )

    flags = 0

    if os.name == "nt":
        flags |= getattr(
            subprocess,
            "DETACHED_PROCESS",
            0,
        )

        flags |= getattr(
            subprocess,
            "CREATE_NEW_PROCESS_GROUP",
            0,
        )

        flags |= getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )

    stream = log.open(
        "ab"
    )

    try:
        process = subprocess.Popen(
            [
                sys.executable,
                str(script),
                "--product-root",
                str(product),
                "--job-id",
                normalized,
            ],
            cwd=str(product),
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=stream,
            close_fds=True,
            creationflags=flags,
        )
    finally:
        stream.close()

    update_job(
        product,
        normalized,
        worker_pid=int(
            process.pid
        ),
    )

    return int(
        process.pid
    )



def _invoke_operar_action(
    product_root: Path,
    action: str,
    port: int = 8090,
) -> None:
    script = (
        product_root
        / "OperarIA.ps1"
    )

    if not script.is_file():
        raise MaintenanceError(
            "OPERARIA_NOT_FOUND"
        )

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-Action",
            str(action),
            "-RuntimeRoot",
            str(product_root),
            "-HostAddress",
            "127.0.0.1",
            "-Port",
            str(
                int(
                    port
                )
            ),
        ],
        cwd=product_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    if result.stdout:
        print(
            result.stdout,
            flush=True,
        )

    if result.stderr:
        print(
            result.stderr,
            file=sys.stderr,
            flush=True,
        )

    if result.returncode != 0:
        raise MaintenanceError(
            (
                "RUNTIME_STOP_FAILED"
                if action == "stop"
                else
                "RUNTIME_START_FAILED"
            )
        )



def _runtime_live(
    port: int = 8090,
    timeout: float = 1.5,
) -> bool:
    request = urllib.request.Request(
        (
            "http://127.0.0.1:"
            + str(
                int(
                    port
                )
            )
            + "/api/enterprise/health/live"
        ),
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            return (
                int(
                    response.status
                )
                == 200
            )
    except Exception:
        return False



def _wait_runtime_live(
    expected: bool,
    timeout_seconds: float,
    port: int = 8090,
) -> None:
    deadline = (
        time.monotonic()
        + float(
            timeout_seconds
        )
    )

    while (
        time.monotonic()
        < deadline
    ):
        if (
            _runtime_live(
                port=port
            )
            is expected
        ):
            return

        time.sleep(
            0.4
        )

    raise MaintenanceError(
        (
            "RUNTIME_STILL_RUNNING"
            if not expected
            else
            "RUNTIME_NOT_LIVE"
        )
    )



def run_job(
    product_root: str | Path,
    job_id: str,
    *,
    startup_delay: float = 2.0,
) -> Dict[str, Any]:
    product = Path(
        product_root
    ).resolve()

    normalized = _normalize_job_id(
        job_id
    )

    job = _read_job_internal(
        product,
        normalized,
    )

    operation = str(
        job.get(
            "operation"
        )
        or ""
    )

    if operation not in {
        "backup",
        "restore",
    }:
        fail_job(
            product,
            normalized,
            "MAINTENANCE_OPERATION_INVALID",
        )

        return get_public_job(
            product,
            normalized,
        )

    try:
        runtime_port = int(
            job.get(
                "runtime_port"
            )
            or 8090
        )
    except Exception:
        fail_job(
            product,
            normalized,
            "RUNTIME_PORT_INVALID",
        )

        return get_public_job(
            product,
            normalized,
        )

    if not (
        1
        <= runtime_port
        <= 65535
    ):
        fail_job(
            product,
            normalized,
            "RUNTIME_PORT_INVALID",
        )

        return get_public_job(
            product,
            normalized,
        )

    restart_after = bool(
        job.get(
            "restart_after",
            True,
        )
    )

    if startup_delay > 0:
        time.sleep(
            float(
                startup_delay
            )
        )

    stop_attempted = False
    operation_error = None
    start_error = None

    try:
        update_job(
            product,
            normalized,
            status="STOPPING",
            error_code=None,
        )

        # Once stop is attempted, recovery/start is attempted
        # even if the stop command itself later reports failure.
        stop_attempted = True

        _invoke_operar_action(
            product,
            "stop",
            runtime_port,
        )

        _wait_runtime_live(
            False,
            20,
            runtime_port,
        )

        if operation == "backup":
            update_job(
                product,
                normalized,
                status="BACKING_UP",
            )

            artifact = (
                backup_artifact_path(
                    product,
                    normalized,
                )
            )

            result = backup(
                runtime_root(
                    product
                ),
                artifact,
            )

            strict = (
                strict_validate_archive(
                    result
                )
            )

            update_job(
                product,
                normalized,
                total_files=int(
                    strict[
                        "total_files"
                    ]
                ),
                size_bytes=int(
                    artifact.stat().st_size
                ),
                sha256=sha256_file(
                    artifact
                ),
            )

        else:
            upload = (
                restore_upload_path(
                    product,
                    normalized,
                )
            )

            update_job(
                product,
                normalized,
                status="VALIDATING",
            )

            expected_hash = str(
                job.get(
                    "input_sha256"
                )
                or ""
            ).lower()

            actual_hash = (
                sha256_file(
                    upload
                )
            )

            if (
                not expected_hash
                or actual_hash
                != expected_hash
            ):
                raise MaintenanceError(
                    "BACKUP_UPLOAD_CHANGED"
                )

            strict_validate_archive(
                upload
            )

            update_job(
                product,
                normalized,
                status="RESTORING",
            )

            restore(
                runtime_root(
                    product
                ),
                upload,
            )

    except Exception as exc:
        if isinstance(
            exc,
            MaintenanceError,
        ):
            operation_error = (
                exc.code
            )

        elif isinstance(
            exc,
            BackupError,
        ):
            operation_error = (
                "BACKUP_ENGINE_FAILED"
            )

        else:
            operation_error = (
                "MAINTENANCE_OPERATION_FAILED"
            )

        print(
            (
                "OPERATION_ERROR="
                + operation_error
            ),
            file=sys.stderr,
            flush=True,
        )

    finally:
        if (
            restart_after
            and stop_attempted
        ):
            try:
                update_job(
                    product,
                    normalized,
                    status="STARTING",
                )

                _invoke_operar_action(
                    product,
                    "start",
                    runtime_port,
                )

                update_job(
                    product,
                    normalized,
                    status="VERIFYING",
                )

                _wait_runtime_live(
                    True,
                    15,
                    runtime_port,
                )

            except Exception as exc:
                if isinstance(
                    exc,
                    MaintenanceError,
                ):
                    start_error = (
                        exc.code
                    )
                else:
                    start_error = (
                        "RUNTIME_START_FAILED"
                    )

    try:
        if start_error:
            update_job(
                product,
                normalized,
                status="FAILED",
                error_code=start_error,
                download_ready=False,
            )

        elif operation_error:
            update_job(
                product,
                normalized,
                status="FAILED",
                error_code=operation_error,
                download_ready=False,
            )

        else:
            update_job(
                product,
                normalized,
                status="COMPLETED",
                error_code=None,
                download_ready=(
                    operation
                    == "backup"
                ),
            )

            if operation == "backup":
                try:
                    removed = (
                        prune_backup_artifacts(
                            product
                        )
                    )

                    if removed:
                        print(
                            "RETENTION_REMOVED="
                            + str(
                                len(
                                    removed
                                )
                            ),
                            flush=True,
                        )

                except Exception as exc:
                    # The new backup remains valid even if an older
                    # artifact could not be purged. A future backup
                    # retries retention automatically.
                    print(
                        (
                            "RETENTION_ERROR="
                            + type(
                                exc
                            ).__name__
                        ),
                        file=sys.stderr,
                        flush=True,
                    )

    finally:
        if operation == "restore":
            restore_upload_path(
                product,
                normalized,
            ).unlink(
                missing_ok=True
            )

        release_job_lock(
            product,
            normalized,
        )

    return get_public_job(
        product,
        normalized,
    )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--product-root",
        required=True,
    )

    parser.add_argument(
        "--job-id",
        required=True,
    )

    args = parser.parse_args()

    result = run_job(
        args.product_root,
        args.job_id,
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    return (
        0
        if result.get(
            "status"
        )
        == "COMPLETED"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
