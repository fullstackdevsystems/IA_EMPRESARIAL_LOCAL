"""R10.24A4.1: commercial company settings are session-scoped and persistent."""
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
from enterprise_identity import EnterpriseIdentityStore
from enterprise_platform_config import EnterprisePlatformConfigStore
from enterprise_tenant_registry import EnterpriseTenantRegistry
import enterprise_ai.api as enterprise_api


def check(name, condition):
    assert condition, name
    print("PASS", name)


api_path = SCRIPTS / "enterprise_ai" / "api.py"
ui_path = SCRIPTS / "enterprise_ai" / "product_settings_ui.py"
config_path = SCRIPTS / "enterprise_platform_config.py"
api = api_path.read_text(encoding="utf-8")
ui = ui_path.read_text(encoding="utf-8")
config = config_path.read_text(encoding="utf-8")
ast.parse(api)
ast.parse(ui)
ast.parse(config)

for marker in ["Mi empresa", "Nombre de la empresa", "Tipo de empresa", "Color principal", "Tema visual", "Logotipo", "/api/enterprise/company-profile"]:
    check("ui:" + marker, marker in ui)
commercial_surface = ""
tree = ast.parse(ui)
for node in tree.body:
    if isinstance(node, ast.Assign):
        names = [
            target.id
            for target in node.targets
            if isinstance(target, ast.Name)
        ]
        if "SETTINGS_BODY" in names:
            if (
                isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                commercial_surface = node.value.value
                break

check("commercial_surface_found", bool(commercial_surface))

for forbidden in ["tenant_id", "company_id", "UUID", "SHA-256", "provider", "schema", "renderer", "localhost", "127.0.0.1"]:
    check(
        "commercial_copy:" + forbidden,
        forbidden not in commercial_surface,
    )
check("settings_route", '@router.get("/settings"' in api and "PRODUCT_SETTINGS_HTML" in api)
check("enterprise_facade", '"/api/enterprise/company-profile"' in api and 'require_permission("config:read")' in api and 'require_permission("config:write")' in api)
check("business_type_governed", '"business_type"' in config and "_BUSINESS_TYPES" in config)
shell = (SCRIPTS / "enterprise_ai" / "product_workspaces_ui.py").read_text(encoding="utf-8")
check("same_shell", "from .product_workspaces_ui import page" in ui and "sessionStorage" in shell)
check("branding_applied_to_shell", "document.documentElement.dataset.theme" in shell and "style.setProperty('--b',accent)" in shell)
check("touch_targets", "min-height:44px" in shell)

with tempfile.TemporaryDirectory() as tmp:
    runtime = Path(tmp) / "IA_Local"
    reports = runtime / "workspace" / "Reportes"
    runtime.mkdir(parents=True)
    tenants = EnterpriseTenantRegistry(reports / ".tenants")
    tenants.create(tenant_id="alpha", name="Alpha")
    tenants.create(tenant_id="bravo", name="Bravo")
    identity = EnterpriseIdentityStore(reports / ".identity", tenants)
    identity.bootstrap_admin(user_id="alpha-admin", username="alpha", display_name="Alpha Admin", password="AlphaPassword!1", tenant_id="alpha")
    identity.create_user(user_id="alpha-viewer", username="viewer", display_name="Alpha Viewer", password="ViewerPassword!1", tenant_id="alpha", roles=["VIEWER"])
    identity.create_user(user_id="bravo-admin", username="bravo", display_name="Bravo Admin", password="BravoPassword!1", tenant_id="bravo", roles=["TENANT_ADMIN"])
    platform = EnterprisePlatformConfigStore(reports / ".platform_config", tenants)
    platform.update_tenant("bravo", {"display_name": "Bravo Original", "business_type": "Servicios", "branding": {"display_name": "Bravo Original", "accent_color": "#2354A6", "theme": "professional-light"}})

    class Config:
        root = runtime
        def section(self, _name):
            return {}

    components = SimpleNamespace(
        cfg=Config(), llm=SimpleNamespace(healthy=lambda: False), vectors=SimpleNamespace(close=lambda: None),
        db=SimpleNamespace(audit=lambda *args, **kwargs: None),
        service=SimpleNamespace(connected_sql_resolver=None),
    )
    original = enterprise_api.build_components
    enterprise_api.build_components = lambda _root: components
    try:
        app = FastAPI()
        enterprise_api.install_enterprise_routes(app, runtime)
        alpha_token, _ = identity.login("alpha", "AlphaPassword!1")
        viewer_token, _ = identity.login("viewer", "ViewerPassword!1")
        bravo_token, _ = identity.login("bravo", "BravoPassword!1")
        alpha = {"Authorization": "Bearer " + alpha_token}
        viewer = {"Authorization": "Bearer " + viewer_token}
        bravo = {"Authorization": "Bearer " + bravo_token}
        with TestClient(app) as client:
            settings = client.get("/settings")
            check("settings_page_exists", settings.status_code == 200 and "Mi empresa" in settings.text and "location.hash" not in settings.text)
            check("missing_session_blocked", client.get("/api/enterprise/company-profile").status_code == 401)
            check("viewer_read_blocked", client.get("/api/enterprise/company-profile", headers=viewer).status_code == 403)
            profile = client.get("/api/enterprise/company-profile", headers=alpha)
            check("authorized_read", profile.status_code == 200 and profile.json()["company"]["business_type"] == "Otro")
            public = json.dumps(profile.json()).lower()
            check("profile_hides_internal_and_secrets", not any(value in public for value in ["tenant_id", "company_id", "secret_reference", "credential_ref", "password", "token"]))
            payload = {"display_name": "Empresa Alfa", "business_type": "Distribución", "accent_color": "#1D67D2", "theme": "professional-dark"}
            saved = client.put("/api/enterprise/company-profile", headers=alpha, json=payload)
            check("authorized_save", saved.status_code == 200 and saved.json()["company"]["display_name"] == "Empresa Alfa")
            reloaded = client.get("/api/enterprise/company-profile", headers=alpha)
            check("persistence", reloaded.status_code == 200 and reloaded.json()["company"] == saved.json()["company"])
            check("store_persistence", platform.tenant_config("alpha")["business_type"] == "Distribución")
            denied = client.put("/api/enterprise/company-profile", headers=viewer, json=payload)
            check("write_without_permission_blocked", denied.status_code == 403)
            bravo_profile = client.get("/api/enterprise/company-profile", headers=bravo)
            check("tenant_isolation", bravo_profile.status_code == 200 and bravo_profile.json()["company"]["display_name"] == "Bravo Original")
            invalid = client.put("/api/enterprise/company-profile", headers=alpha, json={**payload, "business_type": "No permitido"})
            check("invalid_business_type_blocked", invalid.status_code == 400)
            check("valid_state_preserved", platform.tenant_config("alpha")["business_type"] == "Distribución")
    finally:
        enterprise_api.build_components = original

print("R10_24A4_1_COMPANY_SETTINGS=PASS")
