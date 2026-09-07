"""R10.22D: editable Enterprise Control Plane regression coverage."""

from pathlib import Path
import ast
import json
import logging
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def check(name, condition):
    assert condition, name
    print("PASS", name)


# ----------------------------------------------------------------------
# UI contract
# ----------------------------------------------------------------------

from enterprise_ai.admin_console import UNIFIED_ADMIN_HTML

html = UNIFIED_ADMIN_HTML

check(
    "ui_session_storage_only",
    "sessionStorage.getItem('iaEnterpriseSession')" in html
    and "localStorage" not in html,
)

check(
    "ui_no_url_token",
    "location.hash" not in html
    and "URLSearchParams" not in html
    and "#token" not in html,
)

check(
    "ui_partial_permission_loading",
    "Promise.allSettled(" in html
    and "const [o,t,u,s,a]=await Promise.all([" not in html,
)

check(
    "ui_control_plane_capability_gates",
    "data-cp-permission" in html
    and "can('user:create')" in html
    and "can('user:update')" in html
    and "can('user:disable')" in html
    and "can('user:role_assign')" in html
    and "can('sql:read')" in html
    and "can('sql:configure')" in html
    and "can('config:read')" in html
    and "can('config:write')" in html,
)

check(
    "ui_user_id_required",
    "user_id:controlElement('cpUserId').value.trim()," in html
    and (
        "if(!body.user_id||!body.username||"
        "!body.password||!body.roles.length){"
    ) in html
    and (
        "user_id:controlElement('cpUserId').value.trim()||null,"
        not in html
    ),
)

check(
    "ui_password_secret_inputs_protected",
    'id="cpUserPassword" type="password"' in html
    and 'id="cpSqlSecret" type="password"' in html,
)

check(
    "ui_transient_secret_cleanup",
    "password.value=''" in html
    and "password=''" in html
    and "secret.value=''" in html
    and "secret=''" in html,
)

check(
    "ui_no_sql_secret_reference_rendering",
    "secret_reference" not in html
    and "credential_ref" not in html,
)

check(
    "ui_existing_admin_apis_reused",
    "/api/admin/users" in html
    and "/api/admin/sql/connections" in html
    and "/api/admin/ai/provider/test" in html
    and "/api/admin/tenants/" in html,
)

check(
    "ui_401_403_semantics_preserved",
    "if(r.status===401){showLogin" in html
    and "if(!r.ok)throw" in html,
)


# ----------------------------------------------------------------------
# Exact backend permission contract
# ----------------------------------------------------------------------

analyzer_path = SCRIPTS / "analizador_universal.py"
analyzer_source = analyzer_path.read_text(encoding="utf-8")
analyzer_tree = ast.parse(analyzer_source)
analyzer_lines = analyzer_source.splitlines()


def function_source(name):
    matches = [
        node
        for node in analyzer_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]

    assert len(matches) == 1, name

    node = matches[0]

    return "\n".join(
        analyzer_lines[
            node.lineno - 1 :
            getattr(node, "end_lineno", node.lineno)
        ]
    )


global_config_patch = function_source("update_platform_config")
user_action = function_source("user_action")

check(
    "backend_global_config_requires_write",
    '_config_actor(authorization,"config:write")'
    in global_config_patch
    and '_config_actor(authorization,"config:read")'
    not in global_config_patch,
)

check(
    "backend_reset_password_requires_update",
    (
        'permission="user:update" '
        'if action=="reset-password" '
        'else "user:disable"'
    )
    in user_action,
)


# ----------------------------------------------------------------------
# Behavioral API contract in isolated runtime
# ----------------------------------------------------------------------

from enterprise_identity import PERMISSIONS
from enterprise_sql_gateway import (
    EnterpriseSecretStore,
    EnterpriseSqlConnectionStore,
)


class SecretProvider:
    def __init__(self):
        self.values = {}

    def set(self, key, value):
        self.values[key] = value

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        self.values.pop(key, None)


class FakeSqlProvider:
    def test_connection(self, profile, timeout):
        return {
            "database": profile["database"],
        }

    def discover(self, profile):
        return [
            {
                "schema": "dbo",
                "name": "Allowed",
                "type": "TABLE",
                "columns": [
                    {
                        "name": "id",
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
                        "name": "secret",
                        "type": "nvarchar",
                        "nullable": False,
                    }
                ],
            },
        ]


def sql_profile(connection_id, auth_mode="WINDOWS_INTEGRATED"):
    profile = {
        "connection_id": connection_id,
        "display_name": connection_id,
        "server": "sql-host",
        "database": "enterprise",
        "auth_mode": auth_mode,
        "allowed_schemas": ["dbo"],
        "allowed_tables": ["dbo.Allowed"],
        "max_rows": 100,
    }

    if auth_mode == "SQL_AUTH":
        profile.update(
            {
                "username": "reader",
                "password": "SqlPasswordNeverReturned!1",
            }
        )

    return profile


old_root = os.environ.get("IA_LOCAL_ROOT")

with tempfile.TemporaryDirectory() as tmp:
    product = Path(tmp) / "product"
    runtime = product / "IA_Local"
    runtime.mkdir(parents=True)

    (product / "RELEASE_METADATA.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product": "IA_EMPRESARIAL_LOCAL",
                "product_version": "8.5.5",
                "release": "r10.21f",
                "channel": "stable",
            }
        ),
        encoding="utf-8",
    )

    os.environ["IA_LOCAL_ROOT"] = str(runtime)

    import analizador_universal as analyzer
    from fastapi.testclient import TestClient

    events = []
    secret_provider = SecretProvider()
    sql_provider = FakeSqlProvider()

    try:
        tenants = analyzer._tenant_registry()

        tenants.create(
            tenant_id="alpha",
            name="Alpha",
        )

        tenants.create(
            tenant_id="bravo",
            name="Bravo",
        )

        identities = analyzer._identity_store()

        identities.bootstrap_admin(
            user_id="sys",
            username="sys",
            display_name="System",
            password="SystemPassword!1",
            tenant_id="alpha",
        )

        identities.create_user(
            user_id="tenant",
            username="tenant",
            display_name="Tenant",
            password="TenantPassword!1",
            tenant_id="alpha",
            roles=["TENANT_ADMIN"],
        )

        identities.create_user(
            user_id="analyst",
            username="analyst",
            display_name="Analyst",
            password="AnalystPassword!1",
            tenant_id="alpha",
            roles=["ANALYST"],
        )

        identities.create_user(
            user_id="viewer",
            username="viewer",
            display_name="Viewer",
            password="ViewerPassword!1",
            tenant_id="alpha",
            roles=["VIEWER"],
        )

        sql_store = EnterpriseSqlConnectionStore(
            Path(tmp) / "sql",
            tenants,
        )

        analyzer.configure_sql_admin_services(
            store=sql_store,
            provider=sql_provider,
            secret_store=EnterpriseSecretStore(secret_provider),
            audit_events=events,
        )

        with TestClient(analyzer.app) as client:

            def login(username, password):
                response = client.post(
                    "/api/auth/login",
                    json={
                        "username": username,
                        "password": password,
                    },
                )

                check(
                    "login_" + username,
                    response.status_code == 200
                    and response.json().get("token"),
                )

                return {
                    "Authorization":
                        "Bearer " + response.json()["token"]
                }

            system = login(
                "sys",
                "SystemPassword!1",
            )

            tenant = login(
                "tenant",
                "TenantPassword!1",
            )

            analyst = login(
                "analyst",
                "AnalystPassword!1",
            )

            viewer = login(
                "viewer",
                "ViewerPassword!1",
            )

            # ----------------------------------------------------------
            # Canonical auth/session
            # ----------------------------------------------------------

            check(
                "canonical_auth_me",
                client.get(
                    "/api/auth/me",
                    headers=analyst,
                ).status_code == 200,
            )

            check(
                "unauthenticated_admin_is_401",
                client.get(
                    "/api/admin/sql/connections"
                ).status_code == 401,
            )

            # ----------------------------------------------------------
            # Global config read vs write authority
            #
            # Temporarily narrow SYSTEM_ADMIN capabilities so the
            # response proves that PATCH actually checks config:write.
            # ----------------------------------------------------------

            original_system_permissions = set(
                PERMISSIONS["SYSTEM_ADMIN"]
            )

            try:
                PERMISSIONS["SYSTEM_ADMIN"] = {
                    "config:read"
                }

                check(
                    "global_config_read_does_not_grant_write",
                    client.patch(
                        "/api/admin/config",
                        headers=system,
                        json={
                            "product_name":
                                "Should Not Change"
                        },
                    ).status_code == 403,
                )

                PERMISSIONS["SYSTEM_ADMIN"] = {
                    "config:read",
                    "config:write",
                }

                check(
                    "global_config_write_permission_works",
                    client.patch(
                        "/api/admin/config",
                        headers=system,
                        json={
                            "product_name":
                                "R10.22D Test"
                        },
                    ).status_code == 200,
                )
            finally:
                PERMISSIONS["SYSTEM_ADMIN"] = (
                    original_system_permissions
                )

            # ----------------------------------------------------------
            # User CRUD + tenant isolation
            # ----------------------------------------------------------

            created = client.post(
                "/api/admin/users",
                headers=tenant,
                json={
                    "user_id": "worker",
                    "username": "worker",
                    "display_name": "Worker",
                    "password": "WorkerPassword!1",
                    "tenant_id": "alpha",
                    "roles": ["VIEWER"],
                },
            )

            check(
                "user_create_existing_api",
                created.status_code == 200
                and created.json()["user_id"] == "worker"
                and "password_hash" not in created.text.lower(),
            )

            check(
                "user_create_cross_tenant_blocked",
                client.post(
                    "/api/admin/users",
                    headers=tenant,
                    json={
                        "user_id": "cross",
                        "username": "cross",
                        "display_name": "Cross",
                        "password": "CrossPassword!1",
                        "tenant_id": "bravo",
                        "roles": ["VIEWER"],
                    },
                ).status_code == 403,
            )

            worker_session = login(
                "worker",
                "WorkerPassword!1",
            )

            # ----------------------------------------------------------
            # Reset-password authority is user:update, not user:disable.
            # ----------------------------------------------------------

            original_tenant_permissions = set(
                PERMISSIONS["TENANT_ADMIN"]
            )

            try:
                PERMISSIONS["TENANT_ADMIN"] = (
                    original_tenant_permissions
                    - {"user:disable"}
                )

                reset = client.post(
                    "/api/admin/users/worker/reset-password",
                    headers=tenant,
                    json={
                        "password":
                            "WorkerPassword!2"
                    },
                )

                check(
                    "reset_password_works_with_user_update_only",
                    reset.status_code == 200,
                )

                check(
                    "disable_still_requires_user_disable",
                    client.post(
                        "/api/admin/users/worker/disable",
                        headers=tenant,
                    ).status_code == 403,
                )
            finally:
                PERMISSIONS["TENANT_ADMIN"] = (
                    original_tenant_permissions
                )

            check(
                "password_reset_revokes_old_session",
                client.get(
                    "/api/auth/me",
                    headers=worker_session,
                ).status_code == 401,
            )

            worker_session = login(
                "worker",
                "WorkerPassword!2",
            )

            disabled = client.post(
                "/api/admin/users/worker/disable",
                headers=tenant,
            )

            check(
                "user_disable_with_user_disable_permission",
                disabled.status_code == 200,
            )

            check(
                "disable_revokes_active_session",
                client.get(
                    "/api/auth/me",
                    headers=worker_session,
                ).status_code == 401,
            )

            check(
                "user_enable_with_user_disable_permission",
                client.post(
                    "/api/admin/users/worker/enable",
                    headers=tenant,
                ).status_code == 200,
            )

            # ----------------------------------------------------------
            # Tenant AI configuration + provider test
            # ----------------------------------------------------------

            check(
                "analyst_can_read_ai_provider",
                client.get(
                    "/api/admin/ai/providers",
                    headers=analyst,
                ).status_code == 200,
            )

            check(
                "analyst_can_test_ai_provider",
                client.post(
                    "/api/admin/ai/provider/test",
                    headers=analyst,
                    json={
                        "provider": {
                            "provider_type": "DISABLED"
                        }
                    },
                ).status_code == 200,
            )

            check(
                "analyst_cannot_write_ai_config",
                client.patch(
                    "/api/admin/tenants/alpha/config",
                    headers=analyst,
                    json={
                        "ai_provider": {
                            "provider_type":
                                "DISABLED"
                        }
                    },
                ).status_code == 403,
            )

            check(
                "tenant_admin_can_write_ai_config",
                client.patch(
                    "/api/admin/tenants/alpha/config",
                    headers=tenant,
                    json={
                        "ai_provider": {
                            "provider_id":
                                "disabled",
                            "provider_type":
                                "DISABLED",
                        }
                    },
                ).status_code == 200,
            )

            check(
                "tenant_ai_cross_scope_blocked",
                client.patch(
                    "/api/admin/tenants/bravo/config",
                    headers=tenant,
                    json={
                        "ai_provider": {
                            "provider_type":
                                "DISABLED"
                        }
                    },
                ).status_code == 403,
            )

            # ----------------------------------------------------------
            # SQL read/configure split + secret safety
            # ----------------------------------------------------------

            win = client.post(
                "/api/admin/sql/connections",
                headers=tenant,
                json=sql_profile("win"),
            )

            check(
                "sql_create_with_configure",
                win.status_code == 200,
            )

            sql_auth = client.post(
                "/api/admin/sql/connections",
                headers=tenant,
                json=sql_profile(
                    "sql-auth",
                    "SQL_AUTH",
                ),
            )

            check(
                "sql_auth_secret_not_returned",
                sql_auth.status_code == 200
                and "sqlpasswordneverreturned"
                not in sql_auth.text.lower()
                and "secret_reference"
                not in sql_auth.text.lower()
                and "credential_ref"
                not in sql_auth.text.lower()
                and bool(secret_provider.values),
            )

            check(
                "analyst_sql_read",
                client.get(
                    "/api/admin/sql/connections",
                    headers=analyst,
                ).status_code == 200,
            )

            check(
                "analyst_sql_test",
                client.post(
                    "/api/admin/sql/connections/win/test",
                    headers=analyst,
                ).status_code == 200,
            )

            discover = client.post(
                "/api/admin/sql/connections/win/discover",
                headers=analyst,
            )

            check(
                "analyst_sql_discovery_read_only",
                discover.status_code == 200
                and "Hidden" not in discover.text,
            )

            check(
                "analyst_sql_create_denied",
                client.post(
                    "/api/admin/sql/connections",
                    headers=analyst,
                    json=sql_profile("denied"),
                ).status_code == 403,
            )

            check(
                "analyst_sql_state_change_denied",
                client.post(
                    "/api/admin/sql/connections/win/disable",
                    headers=analyst,
                ).status_code == 403,
            )

            check(
                "tenant_sql_disable",
                client.post(
                    "/api/admin/sql/connections/win/disable",
                    headers=tenant,
                ).status_code == 200,
            )

            check(
                "tenant_sql_enable",
                client.post(
                    "/api/admin/sql/connections/win/enable",
                    headers=tenant,
                ).status_code == 200,
            )

            check(
                "system_sql_requires_explicit_tenant",
                client.get(
                    "/api/admin/sql/connections",
                    headers=system,
                ).status_code == 400,
            )

            check(
                "system_sql_other_tenant",
                client.post(
                    (
                        "/api/admin/sql/connections"
                        "?tenant_id=bravo"
                    ),
                    headers=system,
                    json=sql_profile("bravo"),
                ).status_code == 200,
            )

            check(
                "tenant_sql_cross_scope_blocked",
                client.get(
                    (
                        "/api/admin/sql/connections/bravo"
                        "?tenant_id=bravo"
                    ),
                    headers=tenant,
                ).status_code == 403,
            )

            public_sql = client.get(
                "/api/admin/sql/connections/sql-auth",
                headers=tenant,
            )

            check(
                "sql_public_profile_secret_safe",
                public_sql.status_code == 200
                and "secret_reference"
                not in public_sql.text.lower()
                and "credential_ref"
                not in public_sql.text.lower()
                and "sqlpasswordneverreturned"
                not in public_sql.text.lower(),
            )

            # ----------------------------------------------------------
            # Existing Control Plane partial permissions
            # ----------------------------------------------------------

            check(
                "analyst_control_sql_but_not_users",
                client.get(
                    "/api/enterprise/control-plane/sql-sources",
                    headers=analyst,
                ).status_code == 200
                and client.get(
                    "/api/enterprise/control-plane/users",
                    headers=analyst,
                ).status_code == 403,
            )

            check(
                "viewer_control_plane_denied",
                client.get(
                    "/api/enterprise/control-plane/overview",
                    headers=viewer,
                ).status_code == 403,
            )

            # ----------------------------------------------------------
            # No backend secret material in representative output
            # ----------------------------------------------------------

            combined = (
                client.get(
                    "/api/enterprise/control-plane/overview",
                    headers=system,
                ).text
                + client.get(
                    "/api/admin/sql/connections/sql-auth",
                    headers=tenant,
                ).text
            ).lower()

            check(
                "representative_output_secret_safe",
                all(
                    key not in combined
                    for key in (
                        "password_hash",
                        "token_fingerprint",
                        "secret_reference",
                        "credential_ref",
                        "sqlpasswordneverreturned",
                    )
                ),
            )

    finally:
        analyzer.configure_sql_admin_services()

        try:
            analyzer.ENTERPRISE_COMPONENTS.vectors.close()
        except Exception:
            pass

        logging.shutdown()

if old_root is None:
    os.environ.pop("IA_LOCAL_ROOT", None)
else:
    os.environ["IA_LOCAL_ROOT"] = old_root

print("PASS R10.22D")
