"""R10.23-B.6: governed out-of-process backup and recovery workspace."""

from __future__ import annotations

from pathlib import Path
import hashlib
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(
        0,
        str(SCRIPTS),
    )


from fastapi.testclient import TestClient

import analizador_universal as analyzer
import enterprise_maintenance_worker as maintenance

from enterprise_backup_recovery import backup
from enterprise_identity import PERMISSIONS


def check(name, condition):
    if not condition:
        raise AssertionError(name)

    print(
        "PASS",
        name,
    )


admin_source = (
    SCRIPTS
    / "enterprise_ai"
    / "admin_console.py"
).read_text(
    encoding="utf-8",
)

universal_source = (
    SCRIPTS
    / "analizador_universal.py"
).read_text(
    encoding="utf-8",
)


check(
    "ADMIN_RECOVERY_PANEL_VISIBLE",
    'data-p="recuperacion"'
    in admin_source
    and 'id="maintenanceRestoreFile"'
    in admin_source
    and "maintenanceCreateBackup()"
    in admin_source
    and "maintenanceRestore()"
    in admin_source,
)

check(
    "ADMIN_RECOVERY_SYSTEM_ADMIN_ONLY",
    (
        'data-cp-system-admin="true"'
        in admin_source
        and "controlSystemAdmin()"
        in admin_source
    ),
)

check(
    "ADMIN_RECOVERY_EXPLICIT_PERMISSION_GATES",
    (
        'data-cp-permission="backup:create"'
        in admin_source
        and 'data-cp-permission="backup:restore"'
        in admin_source
        and '"backup:create"'
        in universal_source
        and '"backup:restore"'
        in universal_source
    ),
)

check(
    "SYSTEM_ADMIN_PERMISSION_MODEL_DECLARES_MAINTENANCE",
    {
        "backup:create",
        "backup:restore",
    }.issubset(
        PERMISSIONS[
            "SYSTEM_ADMIN"
        ]
    ),
)

check(
    "TENANT_ADMIN_PERMISSION_MODEL_EXCLUDES_MAINTENANCE",
    (
        "backup:create"
        not in PERMISSIONS[
            "TENANT_ADMIN"
        ]
        and
        "backup:restore"
        not in PERMISSIONS[
            "TENANT_ADMIN"
        ]
    ),
)

check(
    "ADMIN_RECOVERY_HAS_NO_FILESYSTEM_PATH_INPUT",
    (
        "BackupPath"
        not in admin_source
        and "RestorePath"
        not in admin_source
        and 'type="text" id="maintenance'
        not in admin_source
    ),
)

check(
    "RECOVERY_API_PRESENT",
    (
        '@app.post(\n    "/api/admin/maintenance/backup"'
        in universal_source
        and '/api/admin/maintenance/restore'
        in universal_source
        and '/api/admin/maintenance/jobs/{job_id}/download'
        in universal_source
    ),
)

restore_function_start = universal_source.index(
    "async def admin_maintenance_restore("
)

restore_function_end = universal_source.index(
    "@app.get(\n    \"/api/admin/maintenance/jobs/{job_id}/download\"",
    restore_function_start,
)

restore_function_source = universal_source[
    restore_function_start:
    restore_function_end
]

check(
    "RESTORE_RESERVES_LOCK_BEFORE_UPLOAD",
    (
        restore_function_source.index(
            "_maintenance_create_job("
        )
        <
        restore_function_source.index(
            "with upload.open("
        )
    ),
)

check(
    "WORKER_IS_OUT_OF_PROCESS",
    (
        "subprocess.Popen("
        in (
            SCRIPTS
            / "enterprise_maintenance_worker.py"
        ).read_text(
            encoding="utf-8",
        )
        and "DETACHED_PROCESS"
        in (
            SCRIPTS
            / "enterprise_maintenance_worker.py"
        ).read_text(
            encoding="utf-8",
        )
    ),
)

check(
    "WORKER_STOPS_BEFORE_BACKUP_OR_RESTORE",
    (
        '"STOPPING"'
        in (
            SCRIPTS
            / "enterprise_maintenance_worker.py"
        ).read_text(
            encoding="utf-8",
        )
        and '_invoke_operar_action(\n            product,\n            "stop"'
        in (
            SCRIPTS
            / "enterprise_maintenance_worker.py"
        ).read_text(
            encoding="utf-8",
        )
    ),
)

check(
    "WORKER_RESTARTS_RUNTIME",
    '_invoke_operar_action(\n                    product,\n                    "start"'
    in (
        SCRIPTS
        / "enterprise_maintenance_worker.py"
    ).read_text(
        encoding="utf-8",
    ),
)

check(
    "RESTORE_DOUBLE_VALIDATION",
    (
        universal_source.count(
            "_maintenance_validate_archive("
        )
        >= 1
        and (
            SCRIPTS
            / "enterprise_maintenance_worker.py"
        ).read_text(
            encoding="utf-8",
        ).count(
            "strict_validate_archive("
        )
        >= 3
    ),
)


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    product = (
        base
        / "product"
    )

    runtime = (
        product
        / "IA_Local"
    )

    reports = (
        runtime
        / "workspace"
        / "Reportes"
    )

    reports.mkdir(
        parents=True,
        exist_ok=True,
    )

    old_root = analyzer.base.ROOT
    old_reports = analyzer.base.REPORTES
    old_launcher = analyzer._launch_maintenance_worker

    analyzer.base.ROOT = runtime
    analyzer.base.REPORTES = reports

    launched = []

    analyzer._launch_maintenance_worker = (
        lambda product_root, job_id:
            launched.append(
                (
                    Path(product_root),
                    str(job_id),
                )
            )
            or 12345
    )

    try:
        tenants = analyzer._tenant_registry()

        tenants.create(
            tenant_id="alpha",
            name="Alpha",
        )

        identity = analyzer._identity_store()

        identity.bootstrap_admin(
            user_id="sys",
            username="sys",
            display_name="System",
            password="SystemPassword!1",
            tenant_id="alpha",
        )

        identity.create_user(
            user_id="tenant-admin",
            username="tenant-admin",
            display_name="Tenant Admin",
            password="TenantPassword!1",
            tenant_id="alpha",
            roles=[
                "TENANT_ADMIN"
            ],
        )

        with TestClient(
            analyzer.app
        ) as client:

            def login(
                username,
                password,
            ):
                response = client.post(
                    "/api/auth/login",
                    json={
                        "username":
                            username,
                        "password":
                            password,
                    },
                )

                check(
                    "LOGIN_" + username,
                    response.status_code
                    == 200,
                )

                return {
                    "Authorization":
                        "Bearer "
                        + response.json()[
                            "token"
                        ]
                }

            system = login(
                "sys",
                "SystemPassword!1",
            )

            tenant_admin = login(
                "tenant-admin",
                "TenantPassword!1",
            )

            unauth = client.post(
                "/api/admin/maintenance/backup"
            )

            check(
                "BACKUP_REQUIRES_AUTH",
                unauth.status_code
                == 401,
            )

            denied = client.post(
                "/api/admin/maintenance/backup",
                headers=tenant_admin,
            )

            check(
                "TENANT_ADMIN_BACKUP_DENIED",
                denied.status_code
                == 403,
            )

            backup_request = client.post(
                "/api/admin/maintenance/backup",
                headers=system,
            )

            check(
                "SYSTEM_ADMIN_BACKUP_ACCEPTED",
                backup_request.status_code
                == 202,
            )

            backup_job = (
                backup_request.json()
            )

            check(
                "BACKUP_JOB_PUBLIC_SAFE",
                (
                    backup_job[
                        "operation"
                    ]
                    == "backup"
                    and backup_job[
                        "status"
                    ]
                    == "QUEUED"
                    and "path"
                    not in backup_job
                    and "actor_user_id"
                    not in backup_job
                    and "worker_pid"
                    not in backup_job
                ),
            )

            check(
                "BACKUP_WORKER_LAUNCHED",
                len(
                    launched
                )
                == 1,
            )

            job_id = (
                backup_job[
                    "job_id"
                ]
            )

            artifact = (
                maintenance.backup_artifact_path(
                    product,
                    job_id,
                )
            )

            artifact.write_bytes(
                b"ZIP"
            )

            maintenance.update_job(
                product,
                job_id,
                status="COMPLETED",
                size_bytes=3,
                sha256=hashlib.sha256(
                    b"ZIP"
                ).hexdigest(),
                download_ready=True,
            )

            maintenance.release_job_lock(
                product,
                job_id,
            )

            jobs = client.get(
                "/api/admin/maintenance/jobs",
                headers=system,
            )

            check(
                "SYSTEM_ADMIN_CAN_LIST_JOBS",
                jobs.status_code
                == 200
                and len(
                    jobs.json()[
                        "items"
                    ]
                )
                >= 1,
            )

            tenant_jobs = client.get(
                "/api/admin/maintenance/jobs",
                headers=tenant_admin,
            )

            check(
                "TENANT_ADMIN_JOB_LIST_DENIED",
                tenant_jobs.status_code
                == 403,
            )

            download = client.get(
                (
                    "/api/admin/maintenance/jobs/"
                    + job_id
                    + "/download"
                ),
                headers=system,
            )

            check(
                "BACKUP_DOWNLOAD_AUTHORIZED",
                download.status_code
                == 200
                and download.content
                == b"ZIP",
            )

            bad_restore = client.post(
                "/api/admin/maintenance/restore",
                headers=system,
                files={
                    "file": (
                        "bad.zip",
                        b"not-a-zip",
                        "application/zip",
                    )
                },
            )

            check(
                "INVALID_RESTORE_REJECTED_BEFORE_MAINTENANCE",
                bad_restore.status_code
                == 400,
            )

            source_runtime = (
                base
                / "source"
                / "IA_Local"
            )

            (
                source_runtime
                / "config"
            ).mkdir(
                parents=True,
                exist_ok=True,
            )

            (
                source_runtime
                / "config"
                / "business_context.json"
            ).write_text(
                '{"company":"Alpha"}',
                encoding="utf-8",
            )

            valid_zip = (
                base
                / "valid-backup.zip"
            )

            backup(
                source_runtime,
                valid_zip,
            )

            restore_denied = client.post(
                "/api/admin/maintenance/restore",
                headers=tenant_admin,
                files={
                    "file": (
                        "backup.zip",
                        valid_zip.read_bytes(),
                        "application/zip",
                    )
                },
            )

            check(
                "TENANT_ADMIN_RESTORE_DENIED",
                restore_denied.status_code
                == 403,
            )

            restore_request = client.post(
                "/api/admin/maintenance/restore",
                headers=system,
                files={
                    "file": (
                        "backup.zip",
                        valid_zip.read_bytes(),
                        "application/zip",
                    )
                },
            )

            check(
                "SYSTEM_ADMIN_RESTORE_ACCEPTED",
                restore_request.status_code
                == 202,
            )

            restore_job = (
                restore_request.json()
            )

            check(
                "RESTORE_VALIDATED_BEFORE_QUEUE",
                restore_job[
                    "operation"
                ]
                == "restore"
                and restore_job[
                    "status"
                ]
                == "QUEUED"
                and restore_job[
                    "validated_files"
                ]
                >= 1,
            )

            check(
                "RESTORE_API_NO_PATH_DISCLOSURE",
                "path"
                not in restore_job
                and "input_sha256"
                not in restore_job,
            )

            check(
                "RESTORE_WORKER_LAUNCHED",
                len(
                    launched
                )
                == 2,
            )

            maintenance.update_job(
                product,
                restore_job[
                    "job_id"
                ],
                status="FAILED",
                error_code="TEST_COMPLETE",
            )

            maintenance.release_job_lock(
                product,
                restore_job[
                    "job_id"
                ],
            )

    finally:
        analyzer._launch_maintenance_worker = (
            old_launcher
        )

        analyzer.base.ROOT = (
            old_root
        )

        analyzer.base.REPORTES = (
            old_reports
        )


with tempfile.TemporaryDirectory() as td:
    product = (
        Path(td)
        / "worker-product"
    )

    runtime = (
        product
        / "IA_Local"
    )

    (
        runtime
        / "config"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        runtime
        / "config"
        / "business_context.json"
    ).write_text(
        '{"test":true}',
        encoding="utf-8",
    )

    job = maintenance.create_job(
        product,
        "backup",
        "system-test",
        runtime_port=8123,
    )

    actions = []

    old_operar = (
        maintenance._invoke_operar_action
    )

    old_wait = (
        maintenance._wait_runtime_live
    )

    maintenance._invoke_operar_action = (
        lambda product_root, action, port=8090:
            actions.append(
                (
                    action,
                    int(port),
                )
            )
    )

    maintenance._wait_runtime_live = (
        lambda expected, timeout_seconds, port=8090:
            None
    )

    try:
        result = maintenance.run_job(
            product,
            job[
                "job_id"
            ],
            startup_delay=0,
        )

        check(
            "WORKER_BACKUP_COMPLETES",
            result[
                "status"
            ]
            == "COMPLETED",
        )

        check(
            "WORKER_STOP_START_SEQUENCE",
            actions
            == [
                (
                    "stop",
                    8123,
                ),
                (
                    "start",
                    8123,
                ),
            ],
        )

        check(
            "WORKER_CREATES_CURRENT_FORMAT_BACKUP",
            maintenance.strict_validate_archive(
                maintenance.backup_artifact_path(
                    product,
                    job[
                        "job_id"
                    ],
                )
            )[
                "version"
            ]
            == 2,
        )

        check(
            "WORKER_RELEASES_MAINTENANCE_LOCK",
            not maintenance.active_lock_path(
                product
            ).exists(),
        )

    finally:
        maintenance._invoke_operar_action = (
            old_operar
        )

        maintenance._wait_runtime_live = (
            old_wait
        )



# -------------------------------------------------
# Unknown/corrupt maintenance lock fails closed.
# -------------------------------------------------

with tempfile.TemporaryDirectory() as td:
    product = (
        Path(td)
        / "lock-product"
    )

    lock = maintenance.active_lock_path(
        product
    )

    lock.write_text(
        "not-a-valid-job-id",
        encoding="ascii",
    )

    busy = False

    try:
        maintenance.create_job(
            product,
            "backup",
            "system-test",
        )
    except maintenance.MaintenanceBusy:
        busy = True

    check(
        "CORRUPT_MAINTENANCE_LOCK_FAILS_CLOSED",
        busy
        and lock.exists(),
    )


# -------------------------------------------------
# Active maintenance blocks a second job.
# -------------------------------------------------

with tempfile.TemporaryDirectory() as td:
    product = (
        Path(td)
        / "busy-product"
    )

    first = maintenance.create_job(
        product,
        "backup",
        "system-test",
    )

    blocked = False

    try:
        maintenance.create_job(
            product,
            "backup",
            "system-test-2",
        )
    except maintenance.MaintenanceBusy:
        blocked = True

    check(
        "ACTIVE_MAINTENANCE_BLOCKS_SECOND_JOB",
        blocked,
    )

    maintenance.fail_job(
        product,
        first[
            "job_id"
        ],
        "TEST_COMPLETE",
    )


# -------------------------------------------------
# Full restore worker execution.
# -------------------------------------------------

with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    source_runtime = (
        base
        / "restore-source"
        / "IA_Local"
    )

    (
        source_runtime
        / "config"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        source_runtime
        / "config"
        / "business_context.json"
    ).write_text(
        '{"value":"RESTORED"}',
        encoding="utf-8",
    )

    source_zip = (
        base
        / "restore-source.zip"
    )

    backup(
        source_runtime,
        source_zip,
    )

    product = (
        base
        / "restore-target"
    )

    runtime = (
        product
        / "IA_Local"
    )

    (
        runtime
        / "config"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        runtime
        / "config"
        / "business_context.json"
    ).write_text(
        '{"value":"OLD"}',
        encoding="utf-8",
    )

    job_id = maintenance.new_job_id()

    upload = (
        maintenance.restore_upload_path(
            product,
            job_id,
        )
    )

    upload.write_bytes(
        source_zip.read_bytes()
    )

    restore_job = maintenance.create_job(
        product,
        "restore",
        "system-test",
        job_id=job_id,
        input_sha256=(
            maintenance.sha256_file(
                upload
            )
        ),
        runtime_port=8124,
    )

    actions = []

    old_operar = maintenance._invoke_operar_action
    old_wait = maintenance._wait_runtime_live

    maintenance._invoke_operar_action = (
        lambda product_root, action, port=8090:
            actions.append(
                (
                    action,
                    int(port),
                )
            )
    )

    maintenance._wait_runtime_live = (
        lambda expected, timeout_seconds, port=8090:
            None
    )

    try:
        result = maintenance.run_job(
            product,
            restore_job[
                "job_id"
            ],
            startup_delay=0,
        )

        check(
            "WORKER_RESTORE_COMPLETES",
            result[
                "status"
            ]
            == "COMPLETED",
        )

        check(
            "WORKER_RESTORE_STOP_START_SEQUENCE",
            actions
            == [
                (
                    "stop",
                    8124,
                ),
                (
                    "start",
                    8124,
                ),
            ],
        )

        check(
            "WORKER_RESTORE_REPLACES_MANAGED_STATE",
            (
                runtime
                / "config"
                / "business_context.json"
            ).read_text(
                encoding="utf-8",
            )
            == '{"value":"RESTORED"}',
        )

        check(
            "WORKER_RESTORE_REMOVES_UPLOAD",
            not upload.exists(),
        )

        check(
            "WORKER_RESTORE_RELEASES_LOCK",
            not maintenance.active_lock_path(
                product
            ).exists(),
        )

    finally:
        maintenance._invoke_operar_action = old_operar
        maintenance._wait_runtime_live = old_wait


# -------------------------------------------------
# Backup engine failure still restarts runtime.
# -------------------------------------------------

with tempfile.TemporaryDirectory() as td:
    product = (
        Path(td)
        / "operation-failure"
    )

    runtime = (
        product
        / "IA_Local"
    )

    (
        runtime
        / "config"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        runtime
        / "config"
        / "business_context.json"
    ).write_text(
        '{"value":"X"}',
        encoding="utf-8",
    )

    job = maintenance.create_job(
        product,
        "backup",
        "system-test",
        runtime_port=8125,
    )

    actions = []

    old_operar = maintenance._invoke_operar_action
    old_wait = maintenance._wait_runtime_live
    old_backup = maintenance.backup

    maintenance._invoke_operar_action = (
        lambda product_root, action, port=8090:
            actions.append(
                (
                    action,
                    int(port),
                )
            )
    )

    maintenance._wait_runtime_live = (
        lambda expected, timeout_seconds, port=8090:
            None
    )

    def fail_backup(
        *args,
        **kwargs,
    ):
        raise maintenance.BackupError(
            "forced test failure"
        )

    maintenance.backup = fail_backup

    try:
        result = maintenance.run_job(
            product,
            job[
                "job_id"
            ],
            startup_delay=0,
        )

        check(
            "OPERATION_FAILURE_MARKED_FAILED",
            result[
                "status"
            ]
            == "FAILED"
            and
            result[
                "error_code"
            ]
            == "BACKUP_ENGINE_FAILED",
        )

        check(
            "OPERATION_FAILURE_RESTARTS_RUNTIME",
            actions
            == [
                (
                    "stop",
                    8125,
                ),
                (
                    "start",
                    8125,
                ),
            ],
        )

    finally:
        maintenance._invoke_operar_action = old_operar
        maintenance._wait_runtime_live = old_wait
        maintenance.backup = old_backup


# -------------------------------------------------
# Stop command failure still attempts runtime recovery.
# -------------------------------------------------

with tempfile.TemporaryDirectory() as td:
    product = (
        Path(td)
        / "stop-failure"
    )

    runtime = (
        product
        / "IA_Local"
    )

    (
        runtime
        / "config"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        runtime
        / "config"
        / "business_context.json"
    ).write_text(
        '{"value":"X"}',
        encoding="utf-8",
    )

    job = maintenance.create_job(
        product,
        "backup",
        "system-test",
        runtime_port=8126,
    )

    actions = []

    old_operar = maintenance._invoke_operar_action
    old_wait = maintenance._wait_runtime_live

    def stop_fails(
        product_root,
        action,
        port=8090,
    ):
        actions.append(
            (
                action,
                int(port),
            )
        )

        if action == "stop":
            raise maintenance.MaintenanceError(
                "RUNTIME_STOP_FAILED"
            )

    maintenance._invoke_operar_action = stop_fails

    maintenance._wait_runtime_live = (
        lambda expected, timeout_seconds, port=8090:
            None
    )

    try:
        result = maintenance.run_job(
            product,
            job[
                "job_id"
            ],
            startup_delay=0,
        )

        check(
            "STOP_FAILURE_MARKED_FAILED",
            result[
                "status"
            ]
            == "FAILED"
            and
            result[
                "error_code"
            ]
            == "RUNTIME_STOP_FAILED",
        )

        check(
            "STOP_FAILURE_ATTEMPTS_RUNTIME_RECOVERY",
            actions
            == [
                (
                    "stop",
                    8126,
                ),
                (
                    "start",
                    8126,
                ),
            ],
        )

    finally:
        maintenance._invoke_operar_action = old_operar
        maintenance._wait_runtime_live = old_wait


# -------------------------------------------------
# Start failure is surfaced as the critical result.
# -------------------------------------------------

with tempfile.TemporaryDirectory() as td:
    product = (
        Path(td)
        / "start-failure"
    )

    runtime = (
        product
        / "IA_Local"
    )

    (
        runtime
        / "config"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        runtime
        / "config"
        / "business_context.json"
    ).write_text(
        '{"value":"X"}',
        encoding="utf-8",
    )

    job = maintenance.create_job(
        product,
        "backup",
        "system-test",
        runtime_port=8127,
    )

    actions = []

    old_operar = maintenance._invoke_operar_action
    old_wait = maintenance._wait_runtime_live

    def start_fails(
        product_root,
        action,
        port=8090,
    ):
        actions.append(
            (
                action,
                int(port),
            )
        )

        if action == "start":
            raise maintenance.MaintenanceError(
                "RUNTIME_START_FAILED"
            )

    maintenance._invoke_operar_action = start_fails

    maintenance._wait_runtime_live = (
        lambda expected, timeout_seconds, port=8090:
            None
    )

    try:
        result = maintenance.run_job(
            product,
            job[
                "job_id"
            ],
            startup_delay=0,
        )

        check(
            "START_FAILURE_MARKED_CRITICAL",
            result[
                "status"
            ]
            == "FAILED"
            and
            result[
                "error_code"
            ]
            == "RUNTIME_START_FAILED",
        )

        check(
            "START_FAILURE_PORT_PROPAGATED",
            actions
            == [
                (
                    "stop",
                    8127,
                ),
                (
                    "start",
                    8127,
                ),
            ],
        )

    finally:
        maintenance._invoke_operar_action = old_operar
        maintenance._wait_runtime_live = old_wait



# -------------------------------------------------
# Dead worker PID is reconciled automatically.
# -------------------------------------------------

with tempfile.TemporaryDirectory() as td:
    product = (
        Path(td)
        / "orphan-worker"
    )

    first = maintenance.create_job(
        product,
        "backup",
        "system-test",
    )

    maintenance.update_job(
        product,
        first[
            "job_id"
        ],
        status="STOPPING",
        worker_pid=424242,
    )

    old_process_match = (
        maintenance._worker_process_matches
    )

    maintenance._worker_process_matches = (
        lambda job_id, worker_pid:
            False
    )

    try:
        second = maintenance.create_job(
            product,
            "backup",
            "system-test-2",
        )

        first_public = (
            maintenance.get_public_job(
                product,
                first[
                    "job_id"
                ],
            )
        )

        check(
            "DEAD_WORKER_LOCK_RECONCILED",
            (
                first_public[
                    "status"
                ]
                == "FAILED"
                and first_public[
                    "error_code"
                ]
                == "MAINTENANCE_INTERRUPTED"
            ),
        )

        check(
            "NEW_JOB_ACQUIRES_RECONCILED_LOCK",
            second[
                "status"
            ]
            == "QUEUED",
        )

        maintenance.fail_job(
            product,
            second[
                "job_id"
            ],
            "TEST_COMPLETE",
        )

    finally:
        maintenance._worker_process_matches = (
            old_process_match
        )


# -------------------------------------------------
# Unknown process inspection remains fail-closed.
# -------------------------------------------------

with tempfile.TemporaryDirectory() as td:
    product = (
        Path(td)
        / "unknown-worker"
    )

    first = maintenance.create_job(
        product,
        "backup",
        "system-test",
    )

    maintenance.update_job(
        product,
        first[
            "job_id"
        ],
        status="STOPPING",
        worker_pid=424243,
    )

    old_process_match = (
        maintenance._worker_process_matches
    )

    maintenance._worker_process_matches = (
        lambda job_id, worker_pid:
            None
    )

    blocked = False

    try:
        try:
            maintenance.create_job(
                product,
                "backup",
                "system-test-2",
            )
        except maintenance.MaintenanceBusy:
            blocked = True

        check(
            "UNKNOWN_WORKER_STATE_FAILS_CLOSED",
            blocked
            and maintenance.active_lock_path(
                product
            ).exists(),
        )

    finally:
        maintenance._worker_process_matches = (
            old_process_match
        )

        maintenance.fail_job(
            product,
            first[
                "job_id"
            ],
            "TEST_COMPLETE",
        )


# -------------------------------------------------
# Stale pre-worker job can recover after lease expiry.
# -------------------------------------------------

with tempfile.TemporaryDirectory() as td:
    product = (
        Path(td)
        / "stale-queue"
    )

    first = maintenance.create_job(
        product,
        "backup",
        "system-test",
    )

    old_stale = (
        maintenance._job_is_stale
    )

    maintenance._job_is_stale = (
        lambda data:
            True
    )

    try:
        second = maintenance.create_job(
            product,
            "backup",
            "system-test-2",
        )

        first_public = (
            maintenance.get_public_job(
                product,
                first[
                    "job_id"
                ],
            )
        )

        check(
            "STALE_PREWORKER_JOB_RECONCILED",
            (
                first_public[
                    "status"
                ]
                == "FAILED"
                and first_public[
                    "error_code"
                ]
                == "MAINTENANCE_INTERRUPTED"
            ),
        )

        maintenance.fail_job(
            product,
            second[
                "job_id"
            ],
            "TEST_COMPLETE",
        )

    finally:
        maintenance._job_is_stale = (
            old_stale
        )


# -------------------------------------------------
# Backup artifacts have bounded retention.
# -------------------------------------------------

with tempfile.TemporaryDirectory() as td:
    product = (
        Path(td)
        / "retention-product"
    )

    jobs = []

    for index in range(
        3
    ):
        job = maintenance.create_job(
            product,
            "backup",
            "system-test",
        )

        artifact = (
            maintenance.backup_artifact_path(
                product,
                job[
                    "job_id"
                ],
            )
        )

        artifact.write_bytes(
            (
                "backup-"
                + str(
                    index
                )
            ).encode(
                "ascii"
            )
        )

        maintenance.update_job(
            product,
            job[
                "job_id"
            ],
            status="COMPLETED",
            download_ready=True,
            size_bytes=int(
                artifact.stat().st_size
            ),
        )

        maintenance.release_job_lock(
            product,
            job[
                "job_id"
            ],
        )

        jobs.append(
            job[
                "job_id"
            ]
        )

    removed = (
        maintenance.prune_backup_artifacts(
            product,
            keep=2,
        )
    )

    artifacts = list(
        (
            maintenance.maintenance_root(
                product
            )
            / "artifacts"
        ).glob(
            "*.zip"
        )
    )

    check(
        "BACKUP_RETENTION_REMOVES_OLD_ARTIFACT",
        len(
            removed
        )
        == 1,
    )

    check(
        "BACKUP_RETENTION_BOUNDS_ARTIFACT_COUNT",
        len(
            artifacts
        )
        == 2,
    )

    expired = (
        maintenance.get_public_job(
            product,
            removed[
                0
            ],
        )
    )

    check(
        "EXPIRED_BACKUP_NOT_DOWNLOAD_READY",
        expired.get(
            "download_ready"
        )
        is False,
    )


# -------------------------------------------------
# Restore upload has a persistent heartbeat marker.
# -------------------------------------------------

check(
    "RESTORE_UPLOAD_HEARTBEAT_PRESENT",
    (
        "async def _maintenance_upload_heartbeat("
        in universal_source
        and "_maintenance_asyncio.create_task("
        in universal_source
        and "heartbeat_task.cancel()"
        in universal_source
        and "_maintenance_asyncio.sleep("
        in universal_source
        and 'status="UPLOADING"'
        in universal_source
        and "last_heartbeat_bytes"
        not in universal_source
    ),
)

check(
    "RESTORE_UPLOAD_HEARTBEAT_IS_TIME_BASED",
    (
        "interval_seconds: float = 30.0"
        in universal_source
        and "min("
        in universal_source
        and "60.0"
        in universal_source
    ),
)


print(
    "PASS R10.23-B.6"
)
