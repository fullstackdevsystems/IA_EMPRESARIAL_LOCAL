"""R10.22H.1 SQL failure, recovery and safe readiness contract."""

from pathlib import Path
import json
import os
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def check(name, value):
    assert value, name
    print("PASS", name)


class FakeSqlProvider:
    def __init__(self):
        self.failure = None

    def _fail(self):
        if self.failure:
            raise EnterpriseSqlError(
                self.failure,
                "PWD=never-visible;SERVER=never-visible;traceback=never-visible",
            )

    def test_connection(self, profile, timeout_seconds):
        self._fail()
        return {"database": profile["database"]}

    def discover(self, profile):
        self._fail()
        return [{
            "schema": "core",
            "name": "Metrics",
            "type": "TABLE",
            "columns": [{"name": "Id", "type": "int", "nullable": False}],
        }]

    def execute(self, profile, sql, parameters, timeout_seconds):
        self._fail()
        return {"columns": [], "rows": []}


old_root = os.environ.get("IA_LOCAL_ROOT")

with tempfile.TemporaryDirectory() as td:
    product = Path(td) / "product"
    runtime = product / "IA_Local"
    runtime.mkdir(parents=True)
    (product / "RELEASE_METADATA.json").write_text(
        json.dumps({
            "schema_version": 1,
            "product": "IA_EMPRESARIAL_LOCAL",
            "product_version": "8.5.5",
            "release": "r10.21f",
            "channel": "stable",
        }),
        encoding="utf-8",
    )
    os.environ["IA_LOCAL_ROOT"] = str(runtime)

    import analizador_universal as analyzer
    from enterprise_onboarding import EnterpriseOnboarding
    from enterprise_sql_gateway import EnterpriseSqlError, EnterpriseSqlExecutor
    from fastapi.testclient import TestClient

    provider = FakeSqlProvider()
    try:
        onboarding = EnterpriseOnboarding(runtime / "workspace" / "Reportes")
        onboarding.configure(
            tenant_id="alpha",
            tenant_name="Alpha",
            admin_user_id="sys",
            admin_username="sys",
            admin_display_name="System",
            password="SystemPassword!1",
        )
        onboarding.tenants.create(tenant_id="bravo", name="Bravo")
        onboarding.identity.create_user(
            user_id="tenant",
            username="tenant",
            display_name="Tenant",
            password="TenantPassword!1",
            tenant_id="alpha",
            roles=["TENANT_ADMIN"],
        )
        onboarding.platform.update_tenant(
            "alpha",
            {"enabled_features": {"sql_enabled": True, "ai_enabled": False}},
        )

        scope = onboarding.sql_readiness_scope("alpha")
        initial = onboarding.readiness("alpha")
        check(
            "missing_required_sql_configuration_blocks",
            initial["steps"]["sql"]["status"] == "BLOCKED"
            and initial["status"] == "BLOCKED",
        )

        profile = onboarding.sql.register(
            scope=scope,
            connection_id="primary",
            server="safe-server",
            database="safe-database",
            auth_mode="WINDOWS_INTEGRATED",
            allowed_schemas=["core"],
            allowed_tables=["core.Metrics"],
        )
        analyzer.configure_sql_admin_services(provider=provider)

        with TestClient(analyzer.app) as client:
            login = client.post(
                "/api/auth/login",
                json={"username": "tenant", "password": "TenantPassword!1"},
            )
            check("tenant_login", login.status_code == 200 and bool(login.json().get("token")))
            headers = {"Authorization": "Bearer " + login.json()["token"]}

            provider.failure = "SQL_CONNECTION_TEST_FAILED"
            unavailable = client.post("/api/admin/tenants/alpha/readiness/validate", headers=headers)
            unavailable_body = unavailable.json()
            check(
                "sql_unavailable_degrades",
                unavailable.status_code == 200
                and unavailable_body["sql_test"]["code"] == "SQL_CONNECTION_TEST_FAILED"
                and unavailable_body["readiness"]["steps"]["sql"]["status"] == "DEGRADED"
                and unavailable_body["readiness"]["status"] == "DEGRADED",
            )
            sql_observability = unavailable_body["readiness"]["steps"]["sql"]
            check(
                "readiness_api_exposes_safe_component_status",
                sql_observability["component"] == "sql"
                and sql_observability["code"] == "SQL_CONNECTION_TEST_FAILED"
                and sql_observability["recoverable"] is True
                and bool(sql_observability["safe_message"]),
            )
            check(
                "readiness_api_exposes_safe_recovery_action",
                bool(sql_observability.get("suggested_action"))
                and "safe-server" not in sql_observability["suggested_action"],
            )
            live = client.get("/api/enterprise/health/live")
            check(
                "liveness_independent_from_tenant_readiness",
                live.status_code == 200
                and live.json()["status"] == "live"
                and unavailable_body["readiness"]["status"] == "DEGRADED",
            )

            provider.failure = "SQL_TIMEOUT"
            timeout = client.post("/api/admin/tenants/alpha/readiness/validate", headers=headers)
            check(
                "sql_timeout_degrades",
                timeout.status_code == 200
                and timeout.json()["sql_test"]["code"] == "SQL_TIMEOUT"
                and timeout.json()["readiness"]["status"] == "DEGRADED",
            )

            provider.failure = "SQL_AUTH_FAILED"
            auth = client.post("/api/admin/tenants/alpha/readiness/validate", headers=headers)
            check(
                "sql_auth_failure_degrades",
                auth.status_code == 200
                and auth.json()["sql_test"]["code"] == "SQL_AUTH_FAILED"
                and auth.json()["readiness"]["status"] == "DEGRADED",
            )

            onboarding.sql.disable(scope, "primary")
            disabled = client.post("/api/admin/tenants/alpha/readiness/validate", headers=headers)
            check(
                "disabled_sql_connection_blocks",
                disabled.status_code == 200
                and disabled.json()["sql_test"]["code"] == "SQL_CONNECTION_DISABLED"
                and disabled.json()["readiness"]["status"] == "BLOCKED",
            )

            onboarding.sql.enable(scope, "primary")
            provider.failure = None
            recovered = client.post("/api/admin/tenants/alpha/readiness/validate", headers=headers)
            recovered_body = recovered.json()
            saved = onboarding.sql.get(scope, "primary")
            check(
                "sql_recovery_clears_degraded_state",
                recovered.status_code == 200
                and recovered_body["sql_test"]["status"] == "PASS"
                and recovered_body["readiness"]["steps"]["sql"]["status"] == "TESTED"
                and recovered_body["readiness"]["status"] == "READY",
            )
            check(
                "sql_recovery_preserves_profile",
                saved["connection_id"] == profile["connection_id"]
                and saved["allowed_schemas"] == ["core"]
                and saved["allowed_tables"] == ["core.Metrics"]
                and saved["read_only"] is True
                and saved["enabled"] is True,
            )
            check(
                "sql_readiness_evidence_is_persisted",
                saved["last_test_status"] == "PASS"
                and saved["last_discovery_status"] == "PASS"
                and saved["last_error_code"] is None,
            )
            check(
                "readiness_exposes_existing_sql_evidence_timestamp",
                bool(recovered_body["readiness"]["steps"]["sql"].get("last_checked_at")),
            )

            executor = EnterpriseSqlExecutor(onboarding.sql, provider)
            try:
                executor.execute(scope, "primary", {
                    "sql": "DELETE FROM core.Metrics",
                    "objects": ["core.Metrics"],
                    "limit": 1,
                    "timeout_seconds": 5,
                })
                non_select_blocked = False
            except EnterpriseSqlError as exc:
                non_select_blocked = exc.code == "SQL_QUERY_NOT_READ_ONLY"
            check(
                "sql_policy_non_select_blocked_without_degrading",
                non_select_blocked
                and onboarding.readiness("alpha")["steps"]["sql"]["status"] == "TESTED",
            )

            try:
                executor.execute(scope, "primary", {
                    "sql": "SELECT * FROM core.Other",
                    "objects": ["core.Other"],
                    "limit": 1,
                    "timeout_seconds": 5,
                })
                allowlist_blocked = False
            except EnterpriseSqlError as exc:
                allowlist_blocked = exc.code == "SQL_OBJECT_NOT_ALLOWED"
            check(
                "sql_policy_allowlist_blocked_without_degrading",
                allowlist_blocked
                and onboarding.readiness("alpha")["steps"]["sql"]["status"] == "TESTED",
            )

            cross_tenant = client.post("/api/admin/tenants/bravo/readiness/validate", headers=headers)
            check("readiness_remains_tenant_scoped", cross_tenant.status_code == 403)
            check(
                "readiness_validate_composes_sql_and_existing_ai",
                "sql_test" in recovered_body
                and recovered_body["sql_test"]["status"] == "PASS"
                and recovered_body["ai_test"]["status"] == "NOT_REQUIRED",
            )

            safe = json.dumps({"unavailable": unavailable_body, "timeout": timeout.json(), "auth": auth.json()}).lower()
            check(
                "sql_safe_error_payload",
                all(value not in safe for value in (
                    "pwd=", "password", "secret=", "bearer", "authorization:",
                    "trusted_connection", "driver=", "server=", "database=", "uid=",
                    "connection string", "traceback", "pyodbc", "localhost\\",
                )),
            )
            check("no_raw_driver_exception_exposed", "never-visible" not in safe)
            check("no_secret_or_connection_string_exposed", "safe-server" not in safe and "safe-database" not in safe)

            platform = onboarding.platform
            platform.update_tenant(
                "alpha",
                {
                    "enabled_features": {"sql_enabled": True, "ai_enabled": False},
                    "ai_provider": {"provider_type": "DISABLED"},
                },
            )
            optional_disabled = onboarding.readiness("alpha")
            check(
                "ai_disabled_valid_when_not_required",
                optional_disabled["steps"]["ai"]["status"] == "CONFIGURED"
                and optional_disabled["status"] == "READY",
            )

            platform.update_tenant(
                "alpha",
                {"enabled_features": {"sql_enabled": True, "ai_enabled": True}},
            )
            disabled_ai = client.post("/api/admin/tenants/alpha/readiness/validate", headers=headers)
            check(
                "ai_disabled_blocks_when_required",
                disabled_ai.status_code == 200
                and disabled_ai.json()["ai_test"]["status"] == "DISABLED"
                and disabled_ai.json()["readiness"]["status"] == "BLOCKED",
            )

            platform.update_tenant(
                "alpha",
                {"ai_provider": {
                    "provider_type": "OLLAMA",
                    "base_url": "http://localhost:19090",
                    "model": None,
                    "timeout": 10,
                    "enabled": True,
                }},
            )
            incomplete = client.post("/api/admin/tenants/alpha/readiness/validate", headers=headers)
            check(
                "incomplete_ai_configuration_blocks",
                incomplete.status_code == 200
                and incomplete.json()["ai_test"]["code"] == "AI_MODEL_INVALID"
                and incomplete.json()["readiness"]["steps"]["ai"]["status"] == "BLOCKED"
                and incomplete.json()["readiness"]["status"] == "BLOCKED",
            )
            check(
                "missing_model_does_not_report_ready",
                incomplete.json()["readiness"]["status"] != "READY",
            )

            provider_config = {
                "provider_type": "OLLAMA",
                "base_url": "http://localhost:19090",
                "model": "local-model",
                "timeout": 10,
                "enabled": True,
            }
            platform.update_tenant("alpha", {"ai_provider": provider_config})
            original_health = analyzer.OllamaProvider.healthy
            try:
                analyzer.OllamaProvider.healthy = lambda self: False
                ai_unavailable = client.post("/api/admin/tenants/alpha/readiness/validate", headers=headers)
                check(
                    "ollama_unavailable_degrades",
                    ai_unavailable.status_code == 200
                    and ai_unavailable.json()["ai_test"]["code"] == "AI_PROVIDER_UNAVAILABLE"
                    and ai_unavailable.json()["readiness"]["status"] == "DEGRADED",
                )

                analyzer.OllamaProvider.healthy = lambda self: (_ for _ in ()).throw(TimeoutError())
                ai_timeout = client.post("/api/admin/tenants/alpha/readiness/validate", headers=headers)
                check(
                    "ollama_timeout_degrades",
                    ai_timeout.status_code == 200
                    and ai_timeout.json()["ai_test"]["code"] == "AI_PROVIDER_TIMEOUT"
                    and ai_timeout.json()["readiness"]["status"] == "DEGRADED",
                )
                ai_observability = ai_timeout.json()["readiness"]["steps"]["ai"]
                check(
                    "ai_failure_visible_in_admin_ui_contract",
                    ai_observability["component"] == "ai"
                    and ai_observability["code"] == "AI_PROVIDER_TIMEOUT"
                    and bool(ai_observability.get("suggested_action")),
                )

                analyzer.OllamaProvider.healthy = lambda self: True
                ai_recovered = client.post("/api/admin/tenants/alpha/readiness/validate", headers=headers)
                saved_provider = platform.resolve_effective_config("alpha")["ai_provider"]
                check(
                    "ai_recovery_clears_degraded_state",
                    ai_recovered.status_code == 200
                    and ai_recovered.json()["ai_test"]["status"] == "PASS"
                    and ai_recovered.json()["readiness"]["status"] == "READY",
                )
                check(
                    "ai_recovery_preserves_provider_config",
                    saved_provider["provider_type"] == "OLLAMA"
                    and saved_provider["model"] == "local-model"
                    and saved_provider["base_url"] == "http://localhost:19090",
                )

                provider.failure = "SQL_CONNECTION_TEST_FAILED"
                sql_and_ai_degraded = client.post("/api/admin/tenants/alpha/readiness/validate", headers=headers)
                provider.failure = None
                analyzer.OllamaProvider.healthy = lambda self: False
                sql_recovered_ai_degraded = client.post("/api/admin/tenants/alpha/readiness/validate", headers=headers)
                check(
                    "component_recovery_does_not_hide_remaining_failure",
                    sql_and_ai_degraded.json()["readiness"]["status"] == "DEGRADED"
                    and sql_recovered_ai_degraded.json()["sql_test"]["status"] == "PASS"
                    and sql_recovered_ai_degraded.json()["readiness"]["status"] == "DEGRADED",
                )
                analyzer.OllamaProvider.healthy = lambda self: True
                client.post("/api/admin/tenants/alpha/readiness/validate", headers=headers)
            finally:
                analyzer.OllamaProvider.healthy = original_health

            platform.update_tenant(
                "alpha",
                {
                    "enabled_features": {"sql_enabled": True, "ai_enabled": False},
                    "ai_provider": {"provider_type": "DISABLED"},
                },
            )
            onboarding.tenants.disable("alpha")
            disabled_tenant = onboarding.readiness("alpha")
            disabled_tenant_http = client.get("/api/admin/tenants/alpha/readiness", headers=headers)
            check(
                "disabled_tenant_never_ready",
                disabled_tenant["status"] == "BLOCKED"
                and disabled_tenant["verification_status"] == "BLOCKED",
            )
            check("disabled_tenant_cannot_run_readiness_validation", disabled_tenant_http.status_code == 401)
            onboarding.tenants.enable("alpha")
            check(
                "nonexistent_tenant_not_ready",
                onboarding.readiness("missing")["status"] == "BLOCKED",
            )

            def integrity_roundtrip(name, path, expected_code):
                valid = path.read_bytes()
                path.write_bytes(b'{"corrupt":"password=never-visible"}')
                blocked = onboarding.readiness("alpha")
                unchanged = path.read_bytes()
                check(
                    name + "_integrity_mismatch_blocks",
                    blocked["status"] == "BLOCKED" and blocked.get("code") == expected_code,
                )
                check(name + "_does_not_get_silently_recreated", unchanged != valid)
                path.write_bytes(valid)
                recovered_state = onboarding.readiness("alpha")
                check(
                    name + "_recovery_clears_blocked_state",
                    recovered_state["status"] == "READY",
                )
                return blocked

            tenant_blocked = integrity_roundtrip(
                "tenant_store",
                onboarding.tenants.path,
                "TENANT_INTEGRITY_MISMATCH",
            )
            identity_blocked = integrity_roundtrip(
                "identity_store",
                onboarding.identity.path,
                "IDENTITY_INTEGRITY_MISMATCH",
            )
            platform_blocked = integrity_roundtrip(
                "platform_store",
                onboarding.platform.path,
                "CONFIG_INTEGRITY_MISMATCH",
            )
            sql_blocked = integrity_roundtrip(
                "sql_store",
                onboarding.sql._path(scope, "primary"),
                "SQL_CONNECTION_INTEGRITY_MISMATCH",
            )
            check(
                "store_recovery_clears_blocked_state",
                all(state["status"] == "BLOCKED" for state in (
                    tenant_blocked, identity_blocked, platform_blocked, sql_blocked,
                )),
            )

            platform_bytes = onboarding.platform.path.read_bytes()
            onboarding.platform.path.write_bytes(b'{"raw":"password=never-visible"}')
            integrity_http = client.get("/api/admin/tenants/alpha/readiness", headers=headers)
            integrity_safe = json.dumps(integrity_http.json()).lower()
            onboarding.platform.path.write_bytes(platform_bytes)
            check(
                "safe_integrity_error_payload",
                integrity_http.status_code == 200
                and integrity_http.json()["status"] == "BLOCKED"
                and "password" not in integrity_safe
                and "never-visible" not in integrity_safe,
            )
            integrity_step = integrity_http.json()["steps"]["configuration"]
            check(
                "blocked_integrity_visible_in_admin_ui_contract",
                integrity_step["component"] == "configuration"
                and integrity_step["code"] == "CONFIG_INTEGRITY_MISMATCH"
                and bool(integrity_step.get("suggested_action")),
            )
            ai_safe = json.dumps({"unavailable": ai_unavailable.json(), "timeout": ai_timeout.json()}).lower()
            check(
                "safe_ai_error_payload",
                all(value not in ai_safe for value in (
                    "password", "secret", "bearer", "authorization", "traceback",
                    "localhost", "never-visible",
                )),
            )
            check("no_raw_provider_exception_exposed", "timeouterror" not in ai_safe)
            check("no_sensitive_store_content_exposed", "corrupt" not in integrity_safe)

            console = (SCRIPTS / "enterprise_ai" / "admin_console.py").read_text(encoding="utf-8")
            renderer = console[
                console.index("function controlReadinessStep"):
                console.index("function controlRenderReadiness")
            ]
            check(
                "sql_failure_visible_in_admin_ui_contract",
                "item.code" in renderer
                and "item.safe_message" in renderer
                and "item.suggested_action" in renderer,
            )
            check(
                "ui_escapes_safe_message",
                "esc(safeMessage)" in renderer
                and "esc(action)" in renderer
                and "esc(code)" in renderer,
            )
            check(
                "ui_does_not_render_raw_exception",
                "innerHTML=item" not in renderer
                and "raw_exception" not in renderer
                and "traceback" not in renderer.lower(),
            )
            check(
                "revalidation_updates_component_state",
                recovered_body["readiness"]["steps"]["sql"]["status"] == "TESTED"
                and ai_recovered.json()["readiness"]["steps"]["ai"]["status"] == "TESTED",
            )
            check(
                "ready_after_full_recovery",
                ai_recovered.json()["readiness"]["status"] == "READY"
                and recovered_body["readiness"]["status"] == "READY",
            )
    finally:
        analyzer.configure_sql_admin_services()
        if old_root is None:
            os.environ.pop("IA_LOCAL_ROOT", None)
        else:
            os.environ["IA_LOCAL_ROOT"] = old_root

print("PASS R10.22H.1 + H.2 + H.3")
