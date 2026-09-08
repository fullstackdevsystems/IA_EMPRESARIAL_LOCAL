"""R10.22E: tenant lifecycle, authorization and session security regression."""

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
# UI lifecycle contract
# ----------------------------------------------------------------------

from enterprise_ai.admin_console import UNIFIED_ADMIN_HTML

html = UNIFIED_ADMIN_HTML

ui_checks = {
    "ui_tenant_runtime_store":
        "let CONTROL_TENANTS=[];" in html,

    "ui_tenant_create_form":
        'id="cpTenantCreate"' in html
        and 'id="cpCreateTenantBtn"' in html,

    "ui_create_system_admin_only":
        'data-cp-system-admin="true"' in html,

    "ui_tenant_update_gate":
        'data-cp-permission="tenant:update"' in html
        and "can('tenant:update')" in html,

    "ui_canonical_admin_tenant_api":
        "/api/admin/tenants" in html
        and "/api/enterprise/control-plane/tenants" not in html,

    "ui_tenant_create":
        "async function controlCreateTenant()" in html,

    "ui_tenant_edit":
        "async function controlEditTenant(tenantId)" in html,

    "ui_tenant_enable_disable":
        "async function controlTenantState(tenantId,action)" in html
        and "'enable'" in html
        and "'disable'" in html,

    "ui_system_admin_self_disable_guard":
        "No se permite deshabilitar desde la consola" in html
        and "controlSystemAdmin()" in html
        and "ownTenant" in html,

    "ui_tenant_self_disable_local_session_clear":
        "La empresa fue deshabilitada" in html
        and "showLogin(" in html,

    "ui_settings_preservation":
        "const currentSettings={" in html
        and "...currentSettings" in html,

    "ui_tenant_id_validation":
        "^[a-z0-9][a-z0-9_.-]{0,79}$" in html,

    "ui_session_storage_only":
        "sessionStorage.getItem('iaEnterpriseSession')" in html
        and "localStorage" not in html,

    "ui_no_url_token":
        "location.hash" not in html
        and "URLSearchParams" not in html
        and "#token" not in html,

    "ui_existing_control_plane_flows_preserved":
        "async function controlCreateUser()" in html
        and "async function controlCreateSql()" in html
        and "async function controlSaveAi()" in html,

    "ui_no_secret_reference_rendering":
        "secret_reference" not in html
        and "credential_ref" not in html,
}

for name, value in ui_checks.items():
    check(name, value)


# ----------------------------------------------------------------------
# Backend structural authority contract
# ----------------------------------------------------------------------

analyzer_path = SCRIPTS / "analizador_universal.py"
identity_path = SCRIPTS / "enterprise_identity.py"

analyzer_source = analyzer_path.read_text(encoding="utf-8")
identity_source = identity_path.read_text(encoding="utf-8")

analyzer_tree = ast.parse(analyzer_source)
identity_tree = ast.parse(identity_source)

analyzer_lines = analyzer_source.splitlines()
identity_lines = identity_source.splitlines()


def analyzer_function(name):
    nodes = [
        node
        for node in analyzer_tree.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
        and node.name == name
    ]

    assert len(nodes) == 1, name

    node = nodes[0]

    return "\n".join(
        analyzer_lines[
            node.lineno - 1:
            node.end_lineno
        ]
    )


identity_store = next(
    node
    for node in identity_tree.body
    if isinstance(node, ast.ClassDef)
    and node.name == "EnterpriseIdentityStore"
)

identity_methods = {
    node.name: node
    for node in identity_store.body
    if isinstance(node, ast.FunctionDef)
}

check(
    "backend_revoke_tenant_sessions_exists",
    "revoke_tenant_sessions"
    in identity_methods,
)

revoke_node = identity_methods[
    "revoke_tenant_sessions"
]

revoke_source = "\n".join(
    identity_lines[
        revoke_node.lineno - 1:
        revoke_node.end_lineno
    ]
)

backend_checks = {
    "backend_revoke_uses_canonical_tenant":
        "self.tenants.get(tenant_id)" in revoke_source
        and 'canonical_tenant_id=tenant["tenant_id"]'
        in revoke_source,

    "backend_revoke_selects_all_tenant_users":
        'u["tenant_id"]==canonical_tenant_id'
        in revoke_source,

    "backend_revoke_all_matching_sessions":
        's["user_id"] in user_ids'
        in revoke_source
        and 's["revoked"]=True'
        in revoke_source,

    "backend_revoke_persists":
        "self._save(d)" in revoke_source,

    "backend_revoke_returns_count":
        "return count" in revoke_source,
}

for name, value in backend_checks.items():
    check(name, value)


guard = analyzer_function(
    "_require_tenant_admin"
)

create_tenant = analyzer_function(
    "create_admin_tenant"
)

update_tenant = analyzer_function(
    "update_admin_tenant"
)

disable_tenant = analyzer_function(
    "disable_admin_tenant"
)

enable_tenant = analyzer_function(
    "enable_admin_tenant"
)

auth_login = analyzer_function(
    "auth_login"
)

bearer = analyzer_function(
    "_bearer"
)

route_checks = {
    "backend_tenant_read_default":
        'permission: str = "tenant:list"'
        in guard,

    "backend_dynamic_tenant_permission":
        "store.has_permission(user, permission)"
        in guard,

    "backend_create_requires_tenant_update":
        'permission="tenant:update"'
        in create_tenant,

    "backend_create_system_admin_only":
        '"SYSTEM_ADMIN" not in user["roles"]'
        in create_tenant,

    "backend_update_requires_tenant_update":
        'permission="tenant:update"'
        in update_tenant,

    "backend_disable_requires_tenant_update":
        'permission="tenant:update"'
        in disable_tenant,

    "backend_enable_requires_tenant_update":
        'permission="tenant:update"'
        in enable_tenant,

    "backend_system_admin_self_disable_denied":
        '"SYSTEM_ADMIN" in user["roles"]'
        in disable_tenant
        and '"TENANT_SELF_DISABLE_DENIED"'
        in disable_tenant
        and "status_code=403"
        in disable_tenant,

    "backend_self_disable_comparison_normalized":
        ".strip().lower()"
        in disable_tenant,

    "backend_revocation_before_disable":
        disable_tenant.find(
            "revoke_tenant_sessions"
        )
        <
        disable_tenant.find(
            "_tenant_registry().disable"
        ),

    "backend_disabled_login_normalized":
        "except TenantRegistryError"
        in auth_login
        and '"AUTH_INVALID_CREDENTIALS"'
        in auth_login,

    "backend_disabled_session_normalized":
        "except TenantRegistryError"
        in bearer
        and '"AUTH_SESSION_INVALID"'
        in bearer,
}

for name, value in route_checks.items():
    check(name, value)


# ----------------------------------------------------------------------
# Productive API behavior in isolated runtime
# ----------------------------------------------------------------------

from enterprise_identity import PERMISSIONS

old_root = os.environ.get(
    "IA_LOCAL_ROOT"
)

with tempfile.TemporaryDirectory() as tmp:

    product = Path(tmp) / "product"
    runtime = product / "IA_Local"

    runtime.mkdir(
        parents=True,
        exist_ok=True,
    )

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

    os.environ[
        "IA_LOCAL_ROOT"
    ] = str(runtime)

    import analizador_universal as analyzer
    from fastapi.testclient import TestClient

    analyzer.configure_tenant_admin_guard(
        lambda: False
    )

    original_system_permissions = set(
        PERMISSIONS["SYSTEM_ADMIN"]
    )

    original_tenant_permissions = set(
        PERMISSIONS["TENANT_ADMIN"]
    )

    try:
        tenants = analyzer._tenant_registry()

        tenants.create(
            tenant_id="platform",
            name="Platform",
            settings={
                "locale": "es-MX",
            },
        )

        tenants.create(
            tenant_id="alpha",
            name="Alpha",
            settings={
                "locale": "es-MX",
                "timezone": "America/Mazatlan",
            },
            default_business_unit="general",
            default_branch="matriz",
        )

        identities = analyzer._identity_store()

        identities.bootstrap_admin(
            user_id="sys",
            username="sys",
            display_name="System",
            password="SystemPassword!1",
            tenant_id="platform",
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
                    "login_" + username,
                    response.status_code == 200
                    and bool(
                        response.json().get(
                            "token"
                        )
                    ),
                )

                return {
                    "Authorization":
                        "Bearer "
                        + response.json()["token"]
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

            # ----------------------------------------------------------
            # tenant:list != tenant:update
            # ----------------------------------------------------------

            try:
                PERMISSIONS[
                    "TENANT_ADMIN"
                ] = {
                    "tenant:list"
                }

                check(
                    "tenant_list_allows_list",
                    client.get(
                        "/api/admin/tenants",
                        headers=tenant,
                    ).status_code == 200,
                )

                check(
                    "tenant_list_does_not_allow_update",
                    client.patch(
                        "/api/admin/tenants/alpha",
                        headers=tenant,
                        json={
                            "name":
                                "Must Not Change"
                        },
                    ).status_code == 403,
                )

                check(
                    "tenant_list_does_not_allow_disable",
                    client.post(
                        "/api/admin/tenants/alpha/disable",
                        headers=tenant,
                    ).status_code == 403,
                )

                PERMISSIONS[
                    "TENANT_ADMIN"
                ] = {
                    "tenant:update"
                }

                check(
                    "tenant_update_without_list_cannot_list",
                    client.get(
                        "/api/admin/tenants",
                        headers=tenant,
                    ).status_code == 403,
                )

                own_update = client.patch(
                    "/api/admin/tenants/alpha",
                    headers=tenant,
                    json={
                        "name":
                            "Alpha Updated"
                    },
                )

                check(
                    "tenant_update_allows_own_update",
                    own_update.status_code == 200
                    and own_update.json()["name"]
                    == "Alpha Updated",
                )

                check(
                    "tenant_update_preserves_existing_settings",
                    own_update.json()["settings"][
                        "locale"
                    ] == "es-MX"
                    and own_update.json()["settings"][
                        "timezone"
                    ] == "America/Mazatlan",
                )

            finally:
                PERMISSIONS[
                    "TENANT_ADMIN"
                ] = (
                    original_tenant_permissions
                )

            # ----------------------------------------------------------
            # Creation authority: SYSTEM_ADMIN only.
            # ----------------------------------------------------------

            denied_create = client.post(
                "/api/admin/tenants",
                headers=tenant,
                json={
                    "tenant_id": "bravo",
                    "name": "Bravo",
                },
            )

            check(
                "tenant_admin_cannot_create_company",
                denied_create.status_code == 403,
            )

            created = client.post(
                "/api/admin/tenants",
                headers=system,
                json={
                    "tenant_id":
                        "bravo",
                    "name":
                        "Bravo",
                    "settings": {
                        "locale":
                            "es-MX",
                        "timezone":
                            "America/Mazatlan",
                    },
                    "default_business_unit":
                        "operacion",
                    "default_branch":
                        "principal",
                },
            )

            check(
                "system_admin_can_create_company",
                created.status_code == 200
                and created.json()["tenant_id"]
                == "bravo",
            )

            check(
                "company_create_settings_persist",
                created.json()["settings"][
                    "locale"
                ] == "es-MX"
                and created.json()["settings"][
                    "timezone"
                ] == "America/Mazatlan"
                and created.json()[
                    "default_business_unit"
                ] == "operacion"
                and created.json()[
                    "default_branch"
                ] == "principal",
            )

            # Tenant isolation.
            check(
                "tenant_admin_cross_company_update_blocked",
                client.patch(
                    "/api/admin/tenants/bravo",
                    headers=tenant,
                    json={
                        "name":
                            "Forbidden"
                    },
                ).status_code == 403,
            )

            # ----------------------------------------------------------
            # SYSTEM_ADMIN own-company protection.
            # ----------------------------------------------------------

            self_disable = client.post(
                "/api/admin/tenants/platform/disable",
                headers=system,
            )

            check(
                "system_admin_self_disable_403",
                self_disable.status_code == 403,
            )

            check(
                "system_admin_self_disable_code",
                self_disable.json()
                .get("detail", {})
                .get("code")
                == "TENANT_SELF_DISABLE_DENIED",
            )

            check(
                "system_admin_self_company_stays_active",
                tenants.get(
                    "platform"
                )["status"] == "ACTIVE",
            )

            check(
                "case_variant_self_disable_blocked",
                client.post(
                    "/api/admin/tenants/PLATFORM/disable",
                    headers=system,
                ).status_code == 403,
            )

            check(
                "system_session_stays_valid",
                client.get(
                    "/api/auth/me",
                    headers=system,
                ).status_code == 200,
            )

            # ----------------------------------------------------------
            # Tenant disable revokes every tenant session persistently.
            # ----------------------------------------------------------

            tenant_disabled = client.post(
                "/api/admin/tenants/alpha/disable",
                headers=tenant,
            )

            check(
                "tenant_admin_can_disable_own_company",
                tenant_disabled.status_code == 200
                and tenant_disabled.json()["status"]
                == "DISABLED",
            )

            state = (
                analyzer
                ._identity_store()
                ._load()
            )

            user_tenants = {
                user["user_id"]:
                    user["tenant_id"]
                for user in state["users"]
            }

            alpha_sessions = [
                session
                for session
                in state["sessions"]
                if user_tenants.get(
                    session["user_id"]
                ) == "alpha"
            ]

            platform_sessions = [
                session
                for session
                in state["sessions"]
                if user_tenants.get(
                    session["user_id"]
                ) == "platform"
            ]

            check(
                "all_company_sessions_persistently_revoked",
                len(alpha_sessions) >= 2
                and all(
                    session["revoked"]
                    for session
                    in alpha_sessions
                ),
            )

            check(
                "other_company_sessions_not_revoked",
                platform_sessions
                and all(
                    not session["revoked"]
                    for session
                    in platform_sessions
                ),
            )

            old_tenant_while_disabled = client.get(
                "/api/auth/me",
                headers=tenant,
            )

            old_analyst_while_disabled = client.get(
                "/api/auth/me",
                headers=analyst,
            )

            check(
                "tenant_old_session_401_while_disabled",
                old_tenant_while_disabled.status_code == 401,
            )

            check(
                "analyst_old_session_401_while_disabled",
                old_analyst_while_disabled.status_code == 401,
            )

            disabled_login = client.post(
                "/api/auth/login",
                json={
                    "username":
                        "tenant",
                    "password":
                        "TenantPassword!1",
                },
            )

            check(
                "disabled_company_login_is_401",
                disabled_login.status_code == 401,
            )

            check(
                "disabled_company_login_is_normalized",
                disabled_login.json()
                .get("detail", {})
                .get("code")
                == "AUTH_INVALID_CREDENTIALS",
            )

            # ----------------------------------------------------------
            # Re-enable does not resurrect old sessions.
            # ----------------------------------------------------------

            enabled = client.post(
                "/api/admin/tenants/alpha/enable",
                headers=system,
            )

            check(
                "system_admin_can_reenable_company",
                enabled.status_code == 200
                and enabled.json()["status"]
                == "ACTIVE",
            )

            check(
                "tenant_old_session_stays_401_after_reenable",
                client.get(
                    "/api/auth/me",
                    headers=tenant,
                ).status_code == 401,
            )

            check(
                "analyst_old_session_stays_401_after_reenable",
                client.get(
                    "/api/auth/me",
                    headers=analyst,
                ).status_code == 401,
            )

            fresh_tenant = login(
                "tenant",
                "TenantPassword!1",
            )

            fresh_analyst = login(
                "analyst",
                "AnalystPassword!1",
            )

            check(
                "fresh_tenant_session_valid_after_reenable",
                client.get(
                    "/api/auth/me",
                    headers=fresh_tenant,
                ).status_code == 200,
            )

            check(
                "fresh_analyst_session_valid_after_reenable",
                client.get(
                    "/api/auth/me",
                    headers=fresh_analyst,
                ).status_code == 200,
            )

            # ----------------------------------------------------------
            # SYSTEM_ADMIN may disable another company; fresh sessions
            # are revoked while its own platform session survives.
            # ----------------------------------------------------------

            system_cross_disable = client.post(
                "/api/admin/tenants/alpha/disable",
                headers=system,
            )

            check(
                "system_admin_can_disable_other_company",
                system_cross_disable.status_code == 200
                and system_cross_disable.json()["status"]
                == "DISABLED",
            )

            check(
                "cross_disable_revokes_fresh_tenant_session",
                client.get(
                    "/api/auth/me",
                    headers=fresh_tenant,
                ).status_code == 401,
            )

            check(
                "cross_disable_revokes_fresh_analyst_session",
                client.get(
                    "/api/auth/me",
                    headers=fresh_analyst,
                ).status_code == 401,
            )

            check(
                "system_session_unaffected_by_cross_disable",
                client.get(
                    "/api/auth/me",
                    headers=system,
                ).status_code == 200,
            )

            # Representative responses remain secret-safe.
            representative = json.dumps(
                {
                    "tenant":
                        created.json(),
                    "self_disable":
                        self_disable.json(),
                },
                ensure_ascii=False,
            ).lower()

            check(
                "tenant_lifecycle_output_secret_safe",
                all(
                    token not in representative
                    for token in (
                        "password_hash",
                        "token_fingerprint",
                        "secret_reference",
                        "credential_ref",
                    )
                ),
            )

    finally:
        PERMISSIONS[
            "SYSTEM_ADMIN"
        ] = original_system_permissions

        PERMISSIONS[
            "TENANT_ADMIN"
        ] = original_tenant_permissions

        analyzer.configure_tenant_admin_guard(
            lambda: False
        )

        components = getattr(
            analyzer,
            "ENTERPRISE_COMPONENTS",
            None,
        )

        vectors = getattr(
            components,
            "vectors",
            None,
        )

        if vectors is not None:
            try:
                vectors.close()
            except Exception:
                pass

        logging.shutdown()

if old_root is None:
    os.environ.pop(
        "IA_LOCAL_ROOT",
        None,
    )
else:
    os.environ[
        "IA_LOCAL_ROOT"
    ] = old_root

print(
    "PASS R10.22E TENANT LIFECYCLE CONTROL PLANE"
)
