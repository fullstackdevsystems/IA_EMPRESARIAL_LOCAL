"""R10.24A4.3: tenant-safe commercial data connection facade."""
from __future__ import annotations

import ast
import json
import secrets
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from enterprise_identity import EnterpriseIdentityStore
from enterprise_sql_gateway import EnterpriseSqlConnectionStore
from enterprise_tenant_registry import EnterpriseTenantRegistry
import enterprise_ai.api as enterprise_api


def check(name, condition):
    assert condition, name
    print("PASS", name)


api_path = SCRIPTS / "enterprise_ai" / "api.py"
ui_path = SCRIPTS / "enterprise_ai" / "product_settings_ui.py"
api, ui = api_path.read_text(encoding="utf-8"), ui_path.read_text(encoding="utf-8")
ast.parse(api); ast.parse(ui)
for marker in ["Datos y conexiones", "Agregar conexión", "Probar conexión", "Usar acceso de Windows", "Fuentes autorizadas", "/api/enterprise/data-connections"]:
    check("ui:" + marker, marker in ui)
for forbidden in ["tenant_id", "company_id", "secret_reference", "credential_ref", "ODBC", "connection string", "SHA-256"]:
    check("ui_hides:" + forbidden, forbidden not in ui)
for route in [
    '@router.get("/api/enterprise/data-connections")',
    '@router.post("/api/enterprise/data-connections")',
    '@router.patch("/api/enterprise/data-connections/{handle}")',
    '@router.put("/api/enterprise/data-connections/{handle}/status")',
    '@router.post("/api/enterprise/data-connections/{handle}/test")',
    '@router.post("/api/enterprise/data-connections/{handle}/discover")',
]:
    check("route:" + route, route in api)
check("read_permission", 'require_permission("sql:read")' in api)
check("configure_permission", 'require_permission("sql:configure")' in api)
check("company_scope_authority", "enterprise_onboarding.sql.company_scope(enterprise_identity.scope(actor))" in api)

with tempfile.TemporaryDirectory(prefix="r1024_a43_api_") as temporary:
    runtime = Path(temporary) / "IA_Local"; reports = runtime / "workspace" / "Reportes"; runtime.mkdir(parents=True)
    tenants = EnterpriseTenantRegistry(reports / ".tenants")
    tenants.create(tenant_id="alpha", name="Alpha"); tenants.create(tenant_id="bravo", name="Bravo")
    identity = EnterpriseIdentityStore(reports / ".identity", tenants)
    passwords = {name: secrets.token_urlsafe(24) for name in ("system", "admin", "analyst", "viewer", "bravo")}
    identity.bootstrap_admin(user_id="alpha-system", username="alpha-system", display_name="Alpha system", password=passwords["system"], tenant_id="alpha")
    identity.create_user(user_id="alpha-admin", username="alpha-admin", display_name="Alpha admin", password=passwords["admin"], tenant_id="alpha", roles=["TENANT_ADMIN"])
    identity.create_user(user_id="alpha-analyst", username="alpha-analyst", display_name="Alpha analyst", password=passwords["analyst"], tenant_id="alpha", roles=["ANALYST"])
    identity.create_user(user_id="alpha-viewer", username="alpha-viewer", display_name="Alpha viewer", password=passwords["viewer"], tenant_id="alpha", roles=["VIEWER"])
    identity.create_user(user_id="bravo-admin", username="bravo-admin", display_name="Bravo admin", password=passwords["bravo"], tenant_id="bravo", roles=["TENANT_ADMIN"])

    class Config:
        root = runtime
        def section(self, _name): return {}
    components = SimpleNamespace(cfg=Config(), llm=SimpleNamespace(healthy=lambda: False), vectors=SimpleNamespace(close=lambda: None), db=SimpleNamespace(audit=lambda *args, **kwargs: None), service=SimpleNamespace(connected_sql_resolver=None))
    original = enterprise_api.build_components; enterprise_api.build_components = lambda _root: components
    try:
        app = FastAPI(); enterprise_api.install_enterprise_routes(app, runtime)
        def headers(username, password):
            token, _ = identity.login(username, password)
            return {"Authorization": "Bearer " + token}
        admin = headers("alpha-admin", passwords["admin"])
        analyst = headers("alpha-analyst", passwords["analyst"])
        viewer = headers("alpha-viewer", passwords["viewer"])
        bravo = headers("bravo-admin", passwords["bravo"])
        with TestClient(app) as client:
            check("missing_session_401", client.get("/api/enterprise/data-connections").status_code == 401)
            check("viewer_read_denied", client.get("/api/enterprise/data-connections", headers=viewer).status_code == 403)
            created = client.post("/api/enterprise/data-connections", headers=admin, json={"display_name": "Ventas", "server": "alpha-host", "database": "Ventas", "authentication": "windows", "allowed_sources": ["ventas.Pedidos"], "tenant_id": "bravo"})
            check("admin_configures_200", created.status_code == 200)
            created_json = created.json()["connection"]
            check("public_profile_safe", not any(item in json.dumps(created_json) for item in ["secret_reference", "credential_ref", "password", "ODBC", "fingerprint", "scope", "user_id", "tenant_id"]))
            handle = created_json["handle"]
            stored = enterprise_api.EnterpriseOnboarding(reports).sql.get({"company_id": "alpha", "user_id": "sql-admin", "business_unit": None, "branch": None}, handle)
            check("browser_tenant_hint_ignored", stored["scope"]["company_id"] == "alpha")
            analyst_list = client.get("/api/enterprise/data-connections", headers=analyst)
            check("analyst_same_company_reads", analyst_list.status_code == 200 and [item["name"] for item in analyst_list.json()["connections"]] == ["Ventas"])
            check("analyst_cannot_configure", client.post("/api/enterprise/data-connections", headers=analyst, json={"display_name": "Blocked", "server": "x", "database": "x", "authentication": "windows", "allowed_sources": ["dbo.Table"]}).status_code == 403)
            check("cross_tenant_list_isolated", client.get("/api/enterprise/data-connections", headers=bravo).json()["connections"] == [])
            check("cross_tenant_handle_hidden", client.patch("/api/enterprise/data-connections/" + handle, headers=bravo, json={"display_name": "Intrusion"}).status_code == 404)
            disabled = client.put("/api/enterprise/data-connections/" + handle + "/status", headers=admin, json={"enabled": False})
            check("status_update_persists", disabled.status_code == 200 and disabled.json()["connection"]["status_label"] == "Desactivada")
            enabled = client.put("/api/enterprise/data-connections/" + handle + "/status", headers=admin, json={"enabled": True})
            check("status_reenabled", enabled.status_code == 200 and enabled.json()["connection"]["enabled"] is True)
            updated = client.patch("/api/enterprise/data-connections/" + handle, headers=admin, json={"display_name": "Ventas centrales", "allowed_sources": ["ventas.Pedidos", "ventas.Clientes"]})
            check("update_persists", updated.status_code == 200 and updated.json()["connection"]["name"] == "Ventas centrales" and updated.json()["connection"]["tables_count"] == 2)
            check("test_requires_configure", client.post("/api/enterprise/data-connections/" + handle + "/test", headers=analyst).status_code == 403)
        reopened = EnterpriseSqlConnectionStore(reports / ".sql_connections", tenants)
        check("restart_persistence", reopened.get({"company_id": "alpha", "user_id": "sql-admin", "business_unit": None, "branch": None}, handle)["display_name"] == "Ventas centrales")
    finally:
        enterprise_api.build_components = original

print("R10_24A4_3_DATA_CONNECTIONS=PASS")
