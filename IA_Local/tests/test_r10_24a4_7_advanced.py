"""R10.24A4.7: advanced preferences are commercial, scoped and persistent."""
from __future__ import annotations
import ast
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
from enterprise_platform_config import EnterprisePlatformConfigStore
from enterprise_tenant_registry import EnterpriseTenantRegistry
import enterprise_ai.api as enterprise_api
api = (SCRIPTS / "enterprise_ai" / "api.py").read_text(encoding="utf-8")
ui = (SCRIPTS / "enterprise_ai" / "product_settings_ui.py").read_text(encoding="utf-8")
ast.parse(api); ast.parse(ui)

def check(name, condition):
    assert condition, name
    print("PASS", name)

for text in ["Avanzado", "Preferencias regionales", "Idioma y formato", "Zona horaria", "Guardar preferencias"]:
    check("ui:" + text, text in ui)
for route in ['@router.get("/api/enterprise/advanced-preferences")', '@router.put("/api/enterprise/advanced-preferences")']:
    check("route:" + route, route in api)
for forbidden in ["password", "secret_reference", "credential_ref", "SHA-256"]:
    advanced = ui.split('<section id="advancedPanel"', 1)[1].split('</section>', 1)[0]
    check("advanced_hides:" + forbidden, forbidden not in advanced)
check("permissions_real", 'require_permission("config:read")' in api and 'require_permission("config:write")' in api)

with tempfile.TemporaryDirectory(prefix="r1024_a47_") as td:
    runtime = Path(td) / "IA_Local"; reports = runtime / "workspace" / "Reportes"; runtime.mkdir(parents=True)
    tenants = EnterpriseTenantRegistry(reports / ".tenants")
    tenants.create(tenant_id="alpha", name="Alpha"); tenants.create(tenant_id="bravo", name="Bravo")
    identity = EnterpriseIdentityStore(reports / ".identity", tenants)
    passwords = {key: secrets.token_urlsafe(24) for key in ("system", "admin", "analyst", "bravo")}
    identity.bootstrap_admin(user_id="system", username="system", display_name="System", password=passwords["system"], tenant_id="alpha")
    identity.create_user(user_id="admin", username="admin", display_name="Admin", password=passwords["admin"], tenant_id="alpha", roles=["TENANT_ADMIN"])
    identity.create_user(user_id="analyst", username="analyst", display_name="Analyst", password=passwords["analyst"], tenant_id="alpha", roles=["ANALYST"])
    identity.create_user(user_id="bravo", username="bravo", display_name="Bravo", password=passwords["bravo"], tenant_id="bravo", roles=["TENANT_ADMIN"])
    class Config:
        root = runtime
        def section(self, _name): return {}
    original = enterprise_api.build_components
    enterprise_api.build_components = lambda _root: SimpleNamespace(cfg=Config(), llm=SimpleNamespace(healthy=lambda: False), vectors=SimpleNamespace(close=lambda: None), db=SimpleNamespace(audit=lambda *args, **kwargs: None), service=SimpleNamespace(connected_sql_resolver=None))
    try:
        app = FastAPI(); enterprise_api.install_enterprise_routes(app, runtime)
        def headers(user, password):
            token, _ = identity.login(user, password); return {"Authorization": "Bearer " + token}
        admin, analyst, bravo = headers("admin", passwords["admin"]), headers("analyst", passwords["analyst"]), headers("bravo", passwords["bravo"])
        with TestClient(app) as client:
            check("missing_session_401", client.get("/api/enterprise/advanced-preferences").status_code == 401)
            initial = client.get("/api/enterprise/advanced-preferences", headers=admin)
            check("default_valid", initial.status_code == 200 and initial.json()["preferences"]["locale"] == "es-MX")
            check("read_allowed", client.get("/api/enterprise/advanced-preferences", headers=analyst).status_code == 200)
            check("write_denied", client.put("/api/enterprise/advanced-preferences", headers=analyst, json={"locale":"es-MX","timezone":"America/Mexico_City"}).status_code == 403)
            saved = client.put("/api/enterprise/advanced-preferences", headers=admin, json={"locale":"es-MX","timezone":"America/Mexico_City","tenant_id":"bravo"})
            check("company_hint_ignored", saved.status_code == 200 and saved.json()["preferences"]["timezone"] == "America/Mexico_City")
            check("cross_tenant_isolated", client.get("/api/enterprise/advanced-preferences", headers=bravo).json()["preferences"]["timezone"] == "America/Chihuahua")
            check("invalid_type_rejected", client.put("/api/enterprise/advanced-preferences", headers=admin, json={"locale":"","timezone":""}).status_code == 422)
        reopened = EnterprisePlatformConfigStore(reports / ".platform_config", tenants)
        effective = reopened.resolve_effective_config("alpha")
        check("restart_persistence", effective["timezone"] == "America/Mexico_City" and effective["locale"] == "es-MX")
    finally:
        enterprise_api.build_components = original
print("R10_24A4_7_ADVANCED=PASS")
