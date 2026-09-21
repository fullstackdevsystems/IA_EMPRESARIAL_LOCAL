"""R10.24A4.5: commercial appearance settings remain tenant-safe."""
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


def check(name, condition):
    assert condition, name
    print("PASS", name)


api = (SCRIPTS / "enterprise_ai" / "api.py").read_text(encoding="utf-8")
ui = (SCRIPTS / "enterprise_ai" / "product_settings_ui.py").read_text(encoding="utf-8")
ast.parse(api); ast.parse(ui)
for text in ["Apariencia", "Tema", "Color principal", "Guardar apariencia", "/api/enterprise/appearance"]:
    check("ui:" + text, text in ui)
for route in ['@router.get("/api/enterprise/appearance")', '@router.put("/api/enterprise/appearance")']:
    check("route:" + route, route in api)

with tempfile.TemporaryDirectory(prefix="r1024_a45_") as temporary:
    runtime = Path(temporary) / "IA_Local"; reports = runtime / "workspace" / "Reportes"; runtime.mkdir(parents=True)
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
    components = SimpleNamespace(cfg=Config(), llm=SimpleNamespace(healthy=lambda: False), vectors=SimpleNamespace(close=lambda: None), db=SimpleNamespace(audit=lambda *args, **kwargs: None), service=SimpleNamespace(connected_sql_resolver=None))
    original = enterprise_api.build_components; enterprise_api.build_components = lambda _root: components
    try:
        app = FastAPI(); enterprise_api.install_enterprise_routes(app, runtime)
        def headers(username, password):
            token, _ = identity.login(username, password); return {"Authorization": "Bearer " + token}
        admin, analyst, bravo = headers("admin", passwords["admin"]), headers("analyst", passwords["analyst"]), headers("bravo", passwords["bravo"])
        with TestClient(app) as client:
            check("missing_session_401", client.get("/api/enterprise/appearance").status_code == 401)
            check("analyst_read_allowed", client.get("/api/enterprise/appearance", headers=analyst).status_code == 200)
            check("analyst_write_denied", client.put("/api/enterprise/appearance", headers=analyst, json={"theme": "professional-dark", "accent_color": "#204080"}).status_code == 403)
            saved = client.put("/api/enterprise/appearance", headers=admin, json={"theme": "professional-dark", "accent_color": "#204080", "tenant_id": "bravo"})
            check("admin_save_allowed", saved.status_code == 200 and saved.json()["appearance"]["theme"] == "professional-dark")
            check("cross_tenant_isolated", client.get("/api/enterprise/appearance", headers=bravo).json()["appearance"]["theme"] == "professional-light")
        reopened = EnterprisePlatformConfigStore(reports / ".platform_config", tenants)
        effective = reopened.public_effective_config("alpha")
        check("restart_persistence", effective["theme"] == "professional-dark" and effective["accent_color"] == "#204080")
    finally:
        enterprise_api.build_components = original

print("R10_24A4_5_APPEARANCE=PASS")
