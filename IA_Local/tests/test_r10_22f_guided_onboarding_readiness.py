"""R10.22F guided onboarding readiness regression."""

from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(
    0,
    str(ROOT / "IA_Local" / "scripts"),
)

from enterprise_onboarding import (
    EnterpriseOnboarding,
    _reports_from_runtime,
)

from enterprise_sql_gateway import (
    EnterpriseSqlError,
    discover_schema,
    test_connection,
)


def check(name, value):
    assert value, name
    print("PASS", name)


class FakeProvider:
    def __init__(
        self,
        failure=None,
    ):
        self.failure = failure

    def test_connection(
        self,
        profile,
        timeout_seconds,
    ):
        if self.failure:
            raise EnterpriseSqlError(
                self.failure,
                "password=never-visible",
            )

        return {
            "database":
                profile["database"],
        }

    def discover(
        self,
        profile,
    ):
        if self.failure:
            raise EnterpriseSqlError(
                self.failure,
                "secret=never-visible",
            )

        return [
            {
                "schema": "dbo",
                "name": "Allowed",
                "type": "TABLE",
                "columns": [
                    {
                        "name": "Id",
                        "type": "int",
                        "nullable": False,
                    }
                ],
            },
            {
                "schema": "private",
                "name": "Hidden",
                "type": "TABLE",
                "columns": [
                    {
                        "name": "Secret",
                        "type": "nvarchar",
                        "nullable": False,
                    }
                ],
            },
        ]


with tempfile.TemporaryDirectory() as td:

    product = Path(td)

    runtime_root = (
        product
        / "IA_Local"
    )

    reports = (
        runtime_root
        / "workspace"
        / "Reportes"
    )

    check(
        "canonical_runtime_reports_path",
        _reports_from_runtime(
            str(runtime_root)
        ).resolve()
        == reports.resolve(),
    )

    onboarding = (
        EnterpriseOnboarding(
            reports
        )
    )

    check(
        "legacy_first_run_preserved",
        onboarding.status()[
            "status"
        ] == "FIRST_RUN",
    )

    configured = (
        onboarding.configure(
            tenant_id="services",
            tenant_name="Services",
            admin_user_id="admin",
            admin_username="admin",
            admin_display_name="Admin",
            password=
                "safe-password-2026",
        )
    )

    check(
        "legacy_configured_preserved",
        configured["status"]
        == "CONFIGURED",
    )

    initial = onboarding.readiness(
        "services"
    )

    check(
        "system_admin_counts_as_admin",
        initial["steps"]["admin"][
            "status"
        ] == "CONFIGURED"
        and initial["steps"]["admin"][
            "active_admin_count"
        ] == 1,
    )

    check(
        "required_sql_missing_blocks",
        initial["steps"]["sql"][
            "status"
        ] == "BLOCKED"
        and initial["status"]
        == "BLOCKED",
    )

    check(
        "disabled_ai_not_required",
        initial["steps"]["ai"][
            "required"
        ] is False,
    )

    onboarding.configure_sql(
        tenant_id="services",
        connection_id="primary",
        server="sql-host",
        database="enterprise",
        auth_mode=
            "WINDOWS_INTEGRATED",
        allowed_schemas=["dbo"],
        allowed_tables=[
            "dbo.Allowed"
        ],
    )

    sql_saved = (
        onboarding.readiness(
            "services"
        )
    )

    check(
        "sql_configured_not_tested",
        sql_saved["steps"]["sql"][
            "status"
        ] == "CONFIGURED"
        and sql_saved["status"]
        == "CONFIGURED",
    )

    scope = (
        onboarding.sql_readiness_scope(
            "services"
        )
    )

    test_connection(
        onboarding.sql,
        FakeProvider(),
        scope,
        "primary",
    )

    discover_schema(
        onboarding.sql,
        FakeProvider(),
        scope,
        "primary",
    )

    ready = onboarding.readiness(
        "services"
    )

    check(
        "sql_persisted_evidence_tested",
        ready["steps"]["sql"][
            "status"
        ] == "TESTED"
        and ready["steps"]["sql"][
            "tested_count"
        ] == 1,
    )

    check(
        "ready_after_required_sql_test",
        ready["status"]
        == "READY"
        and ready[
            "verification_status"
        ] == "TESTED",
    )

    restarted = (
        EnterpriseOnboarding(
            reports
        ).readiness(
            "services"
        )
    )

    check(
        "sql_test_evidence_persists",
        restarted["steps"]["sql"][
            "status"
        ] == "TESTED",
    )

    try:
        test_connection(
            onboarding.sql,
            FakeProvider(
                "SQL_AUTH_FAILED"
            ),
            scope,
            "primary",
        )
    except EnterpriseSqlError:
        pass

    degraded_sql = (
        onboarding.readiness(
            "services"
        )
    )

    check(
        "failed_sql_degrades",
        degraded_sql["steps"][
            "sql"
        ]["status"] == "DEGRADED"
        and degraded_sql["status"]
        == "DEGRADED"
        and degraded_sql[
            "verification_status"
        ] == "DEGRADED",
    )

    # Recover SQL.
    test_connection(
        onboarding.sql,
        FakeProvider(),
        scope,
        "primary",
    )

    discover_schema(
        onboarding.sql,
        FakeProvider(),
        scope,
        "primary",
    )

    # Enable AI as a required feature.
    onboarding.platform.update_tenant(
        "services",
        {
            "enabled_features": {
                "ai_enabled": True,
            },
            "ai_provider": {
                "provider_type":
                    "OLLAMA",
                "base_url":
                    "http://127.0.0.1:11434",
                "model":
                    "qwen3",
                "timeout":
                    10,
            },
        },
    )

    ai_pending = (
        onboarding.readiness(
            "services"
        )
    )

    check(
        "configured_ai_not_fake_tested",
        ai_pending["steps"]["ai"][
            "status"
        ] == "CONFIGURED"
        and ai_pending["status"]
        == "CONFIGURED"
        and ai_pending[
            "verification_status"
        ] == "CONFIGURED",
    )

    ai_pass = (
        onboarding.readiness(
            "services",
            ai_test={
                "status": "PASS",
                "latency_ms": 1.0,
            },
        )
    )

    check(
        "explicit_ai_pass_tested",
        ai_pass["steps"]["ai"][
            "status"
        ] == "TESTED"
        and ai_pass["status"]
        == "READY"
        and ai_pass[
            "verification_status"
        ] == "TESTED",
    )

    check(
        "ai_evidence_not_fake_persisted",
        EnterpriseOnboarding(
            reports
        ).readiness(
            "services"
        )["steps"]["ai"][
            "status"
        ] == "CONFIGURED",
    )

    ai_fail = (
        onboarding.readiness(
            "services",
            ai_test={
                "status": "FAIL",
            },
        )
    )

    check(
        "explicit_ai_failure_degrades",
        ai_fail["steps"]["ai"][
            "status"
        ] == "DEGRADED"
        and ai_fail["status"]
        == "DEGRADED"
        and ai_fail[
            "verification_status"
        ] == "DEGRADED",
    )

    # Second tenant proves readiness
    # is tenant-scoped rather than based
    # on the one global SYSTEM_ADMIN.
    onboarding.tenants.create(
        tenant_id="bravo",
        name="Bravo",
    )

    bravo_admin = (
        onboarding.identity.create_user(
            user_id="bravo-admin",
            username="bravo.admin",
            display_name="Bravo Admin",
            password=
                "bravo-password-2026",
            tenant_id="bravo",
            roles=["TENANT_ADMIN"],
        )
    )

    onboarding.platform.update_tenant(
        "bravo",
        {
            "enabled_features": {
                "sql_enabled": False,
                "ai_enabled": False,
            }
        },
    )

    bravo = onboarding.readiness(
        "bravo"
    )

    check(
        "tenant_admin_counts_for_tenant",
        bravo_admin["tenant_id"]
        == "bravo"
        and bravo["steps"]["admin"][
            "status"
        ] == "CONFIGURED",
    )

    check(
        "per_tenant_no_external_ready",
        bravo["status"]
        == "READY"
        and bravo[
            "verification_status"
        ] == "NOT_REQUIRED",
    )

    onboarding.tenants.disable(
        "bravo"
    )

    disabled = (
        onboarding.readiness(
            "bravo"
        )
    )

    check(
        "disabled_tenant_blocked",
        disabled["status"]
        == "BLOCKED"
        and disabled[
            "verification_status"
        ] == "BLOCKED",
    )

    safe = json.dumps(
        {
            "services": ai_pass,
            "bravo": bravo,
        },
        ensure_ascii=False,
    ).lower()

    check(
        "readiness_secret_safe",
        all(
            item not in safe
            for item in (
                "password_hash",
                "secret_reference",
                "credential_ref",
                "token_fingerprint",
                "safe-password-2026",
                "bravo-password-2026",
            )
        ),
    )

print(
    "PASS R10.22F GUIDED ONBOARDING READINESS"
)
