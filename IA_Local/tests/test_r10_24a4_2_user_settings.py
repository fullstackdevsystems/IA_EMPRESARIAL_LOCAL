"""R10.24A4.2: commercial user settings, permissions, isolation and persistence."""
import ast
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from enterprise_identity import EnterpriseIdentityStore, IdentityError
from enterprise_tenant_registry import EnterpriseTenantRegistry
import enterprise_ai.api as enterprise_api


def check(name, condition):
    assert condition, name
    print("PASS", name)


api_path = SCRIPTS / "enterprise_ai" / "api.py"
ui_path = SCRIPTS / "enterprise_ai" / "product_settings_ui.py"
api = api_path.read_text(encoding="utf-8")
ui = ui_path.read_text(encoding="utf-8")
ast.parse(api)
ast.parse(ui)

for marker in [
    "Usuarios",
    "Agregar usuario",
    "Contraseña temporal",
    "Confirmar contraseña",
    "Administrador",
    "Analista",
    "Consulta",
    "Activo",
    "Desactivado",
    "/api/enterprise/users",
    "Crear usuario",
    "Guardar",
    "Desactivar",
    "Activar",
]:
    check("ui:" + marker, marker in ui)

for future_section in [
    "Datos y conexiones",
    "Inteligencia artificial",
    "Apariencia",
    "Seguridad y recuperación",
    "Avanzado",
]:
    check("future_section:" + future_section, future_section in ui)

for forbidden in [
    "tenant_id",
    "company_id",
    "SYSTEM_ADMIN",
    "TENANT_ADMIN",
    "ANALYST",
    "VIEWER",
    "password_hash",
    "UUID",
    "SHA-256",
    "ODBC",
    "localhost",
    "127.0.0.1",
    "renderer",
]:
    check("commercial_copy:" + forbidden, forbidden not in ui)

check("responsive_contract", "@media(max-width:760px)" in ui)
check("touch_targets", "min-height:44px" in ui)
check("settings_tabs", "companyTab" in ui and "usersTab" in ui)
check("create_secret_fields", 'type="password"' in ui and "newPassword" in ui and "confirmPassword" in ui)

for route in [
    '@router.get("/api/enterprise/users")',
    '@router.post("/api/enterprise/users")',
    '@router.patch("/api/enterprise/users/{username}")',
    '@router.put("/api/enterprise/users/{username}/status")',
]:
    check("api_route:" + route, route in api)

check("session_company_scope", "enterprise_identity.list(principal.company_id)" in api)
check("create_permission", 'require_permission("user:create")' in api)
check("update_permission", 'require_permission("user:update")' in api)
check("disable_permission", 'require_permission("user:disable")' in api)
check("role_assign_permission", "user:role_assign" in api)
check("self_role_guard", "No puedes cambiar tu propio rol" in api)
check("self_disable_guard", "No puedes desactivar tu propio acceso" in api)
check("last_admin_guard", "Debe existir al menos otro administrador activo" in api)

with tempfile.TemporaryDirectory() as tmp:
    runtime = Path(tmp) / "IA_Local"
    reports = runtime / "workspace" / "Reportes"
    runtime.mkdir(parents=True)

    tenants = EnterpriseTenantRegistry(reports / ".tenants")
    tenants.create(tenant_id="alpha", name="Alpha")
    tenants.create(tenant_id="bravo", name="Bravo")

    identity = EnterpriseIdentityStore(reports / ".identity", tenants)
    identity.bootstrap_admin(
        user_id="alpha-system",
        username="alpha-system",
        display_name="Alpha System",
        password="SystemPassword!1",
        tenant_id="alpha",
    )
    identity.create_user(
        user_id="alpha-admin",
        username="alpha-admin",
        display_name="Alpha Admin",
        password="AdminPassword!1",
        tenant_id="alpha",
        roles=["TENANT_ADMIN"],
    )
    identity.create_user(
        user_id="alpha-viewer",
        username="alpha-viewer",
        display_name="Alpha Viewer",
        password="ViewerPassword!1",
        tenant_id="alpha",
        roles=["VIEWER"],
    )
    identity.create_user(
        user_id="bravo-admin",
        username="bravo-admin",
        display_name="Bravo Admin",
        password="BravoPassword!1",
        tenant_id="bravo",
        roles=["TENANT_ADMIN"],
    )

    class Config:
        root = runtime
        def section(self, _name):
            return {}

    components = SimpleNamespace(
        cfg=Config(),
        llm=SimpleNamespace(healthy=lambda: False),
        vectors=SimpleNamespace(close=lambda: None),
        db=SimpleNamespace(audit=lambda *args, **kwargs: None),
        service=SimpleNamespace(connected_sql_resolver=None),
    )

    original = enterprise_api.build_components
    enterprise_api.build_components = lambda _root: components

    try:
        app = FastAPI()
        enterprise_api.install_enterprise_routes(app, runtime)

        system_token, _ = identity.login("alpha-system", "SystemPassword!1")
        admin_token, _ = identity.login("alpha-admin", "AdminPassword!1")
        viewer_token, _ = identity.login("alpha-viewer", "ViewerPassword!1")
        bravo_token, _ = identity.login("bravo-admin", "BravoPassword!1")

        system = {"Authorization": "Bearer " + system_token}
        admin = {"Authorization": "Bearer " + admin_token}
        viewer = {"Authorization": "Bearer " + viewer_token}
        bravo = {"Authorization": "Bearer " + bravo_token}

        with TestClient(app) as client:
            settings = client.get("/settings")
            check("settings_page", settings.status_code == 200 and "Usuarios" in settings.text)

            check("missing_session_401", client.get("/api/enterprise/users").status_code == 401)
            check("viewer_denied_403", client.get("/api/enterprise/users", headers=viewer).status_code == 403)

            listed = client.get("/api/enterprise/users", headers=admin)
            check("admin_list_200", listed.status_code == 200)
            listed_json = listed.json()
            check("list_scoped_alpha", all(item["username"] != "bravo-admin" for item in listed_json["users"]))

            public_text = json.dumps(listed_json, ensure_ascii=False)
            for hidden in ["tenant_id", "company_id", "user_id", "password_hash", "SYSTEM_ADMIN", "TENANT_ADMIN", "ANALYST", "VIEWER"]:
                check("public_hides:" + hidden, hidden not in public_text)

            check(
                "friendly_roles",
                {item["label"] for item in listed_json["roles"]} == {"Administrador", "Analista", "Consulta"},
            )

            created = client.post(
                "/api/enterprise/users",
                headers=admin,
                json={
                    "username": "new-user",
                    "display_name": "Nuevo Usuario",
                    "password": "TemporaryPass!1",
                    "role": "analyst",
                },
            )
            check("create_user_200", created.status_code == 200)
            check("create_public_role", created.json()["user"]["role_label"] == "Analista")

            internal = identity.get("new-user")
            check("create_internal_role", internal["roles"] == ["ANALYST"])
            check("create_internal_tenant", internal["tenant_id"] == "alpha")

            duplicate = client.post(
                "/api/enterprise/users",
                headers=admin,
                json={
                    "username": "new-user",
                    "display_name": "Duplicado",
                    "password": "TemporaryPass!1",
                    "role": "viewer",
                },
            )
            check("duplicate_409", duplicate.status_code == 409)

            raw_role = client.post(
                "/api/enterprise/users",
                headers=admin,
                json={
                    "username": "bad-role",
                    "display_name": "Bad Role",
                    "password": "TemporaryPass!1",
                    "role": "SYSTEM_ADMIN",
                },
            )
            check("raw_role_blocked_400", raw_role.status_code == 400)

            new_admin = client.post(
                "/api/enterprise/users",
                headers=admin,
                json={
                    "username": "second-admin",
                    "display_name": "Segundo Admin",
                    "password": "TemporaryPass!2",
                    "role": "administrator",
                },
            )
            check("commercial_admin_200", new_admin.status_code == 200)
            check("commercial_admin_internal_role", identity.get("second-admin")["roles"] == ["TENANT_ADMIN"])

            updated = client.patch(
                "/api/enterprise/users/new-user",
                headers=admin,
                json={"display_name": "Usuario Editado", "role": "viewer"},
            )
            check("update_user_200", updated.status_code == 200)
            check("update_persisted", identity.get("new-user")["display_name"] == "Usuario Editado" and identity.get("new-user")["roles"] == ["VIEWER"])

            self_role = client.patch(
                "/api/enterprise/users/alpha-admin",
                headers=admin,
                json={"role": "viewer"},
            )
            check("self_role_change_403", self_role.status_code == 403)

            self_disable = client.put(
                "/api/enterprise/users/alpha-admin/status",
                headers=admin,
                json={"enabled": False},
            )
            check("self_disable_403", self_disable.status_code == 403)

            cross = client.patch(
                "/api/enterprise/users/bravo-admin",
                headers=admin,
                json={"display_name": "Intrusión"},
            )
            check("cross_tenant_404", cross.status_code == 404)

            disabled = client.put(
                "/api/enterprise/users/new-user/status",
                headers=admin,
                json={"enabled": False},
            )
            check("disable_200", disabled.status_code == 200 and disabled.json()["user"]["status_label"] == "Desactivado")
            check("disable_persisted", identity.get("new-user")["status"] == "DISABLED")

            try:
                identity.login("new-user", "TemporaryPass!1")
            except IdentityError as exc:
                check("disabled_login_blocked", exc.code == "AUTH_INVALID_CREDENTIALS")
            else:
                raise AssertionError("disabled_login_blocked")

            enabled = client.put(
                "/api/enterprise/users/new-user/status",
                headers=admin,
                json={"enabled": True},
            )
            check("enable_200", enabled.status_code == 200 and enabled.json()["user"]["status_label"] == "Activo")
            check("enable_persisted", identity.get("new-user")["status"] == "ACTIVE")

            restored_token, restored_user = identity.login("new-user", "TemporaryPass!1")
            check("reenabled_login_works", bool(restored_token) and restored_user["username"] == "new-user")

            bravo_list = client.get("/api/enterprise/users", headers=bravo)
            check("bravo_list_200", bravo_list.status_code == 200)
            check(
                "bravo_isolation",
                {item["username"] for item in bravo_list.json()["users"]} == {"bravo-admin"},
            )

            system_list = client.get("/api/enterprise/users", headers=system)
            check("system_list_200", system_list.status_code == 200)
            check(
                "system_commercial_scope_alpha",
                all(item["username"] != "bravo-admin" for item in system_list.json()["users"]),
            )

        reopened_tenants = EnterpriseTenantRegistry(reports / ".tenants")
        reopened_identity = EnterpriseIdentityStore(reports / ".identity", reopened_tenants)
        reopened = reopened_identity.get("new-user")
        check("restart_persistence_name", reopened["display_name"] == "Usuario Editado")
        check("restart_persistence_role", reopened["roles"] == ["VIEWER"])
        check("restart_persistence_status", reopened["status"] == "ACTIVE")
        check("restart_persistence_tenant", reopened["tenant_id"] == "alpha")

    finally:
        enterprise_api.build_components = original

print("R10_24A4_2_USER_SETTINGS=PASS")
