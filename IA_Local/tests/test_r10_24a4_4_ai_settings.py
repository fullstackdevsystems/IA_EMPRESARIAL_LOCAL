"""R10.24A4.4: commercial local-AI settings are tenant-safe and fail closed."""
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
from enterprise_onboarding import EnterpriseOnboarding
from enterprise_platform_config import EnterprisePlatformConfigStore
from enterprise_tenant_registry import EnterpriseTenantRegistry
import enterprise_ai.api as enterprise_api


def check(name, condition):
    assert condition, name
    print("PASS", name)


api_path = SCRIPTS / "enterprise_ai" / "api.py"
ui_path = SCRIPTS / "enterprise_ai" / "product_settings_ui.py"
api, ui = api_path.read_text(encoding="utf-8"), ui_path.read_text(encoding="utf-8")
ast.parse(api)
ast.parse(ui)
for text in ["Inteligencia artificial", "Motor local", "Detectar modelos", "Probar configuración", "Guardar cambios"]:
    check("ui:" + text, text in ui)
for forbidden in ["location.hash", "localStorage", "base_url", "context window", "endpoint", "localhost", "secret_reference"]:
    check("ui_hides:" + forbidden, forbidden not in ui)
for route in [
    '@router.get("/api/enterprise/ai-configuration")',
    '@router.put("/api/enterprise/ai-configuration")',
    '@router.post("/api/enterprise/ai-configuration/detect")',
    '@router.post("/api/enterprise/ai-configuration/test")',
]:
    check("route:" + route, route in api)


with tempfile.TemporaryDirectory(prefix="r1024_a44_") as temporary:
    runtime = Path(temporary) / "IA_Local"
    reports = runtime / "workspace" / "Reportes"
    runtime.mkdir(parents=True)
    tenants = EnterpriseTenantRegistry(reports / ".tenants")
    tenants.create(tenant_id="alpha", name="Alpha")
    tenants.create(tenant_id="bravo", name="Bravo")
    identity = EnterpriseIdentityStore(reports / ".identity", tenants)
    passwords = {key: secrets.token_urlsafe(24) for key in ("system", "admin", "analyst", "bravo")}
    identity.bootstrap_admin(user_id="alpha-system", username="alpha-system", display_name="Alpha system", password=passwords["system"], tenant_id="alpha")
    identity.create_user(user_id="alpha-admin", username="alpha-admin", display_name="Alpha admin", password=passwords["admin"], tenant_id="alpha", roles=["TENANT_ADMIN"])
    identity.create_user(user_id="alpha-analyst", username="alpha-analyst", display_name="Alpha analyst", password=passwords["analyst"], tenant_id="alpha", roles=["ANALYST"])
    identity.create_user(user_id="bravo-admin", username="bravo-admin", display_name="Bravo admin", password=passwords["bravo"], tenant_id="bravo", roles=["TENANT_ADMIN"])

    class Config:
        root = runtime
        def section(self, _name): return {}

    components = SimpleNamespace(cfg=Config(), llm=SimpleNamespace(healthy=lambda: False), vectors=SimpleNamespace(close=lambda: None), db=SimpleNamespace(audit=lambda *args, **kwargs: None), service=SimpleNamespace(connected_sql_resolver=None))
    original_components, original_adapter = enterprise_api.build_components, enterprise_api._CommercialAiAdapter

    class DeterministicAdapter:
        def health(self, _config): return True
        def discover_models(self, _config): return [{"id": "nomic-embed-text", "name": "nomic-embed-text"}, {"id": "nomic-embed-text:latest", "name": "nomic-embed-text:latest"}, {"id": "qwen-local", "name": "qwen-local"}]

    enterprise_api.build_components = lambda _root: components
    enterprise_api._CommercialAiAdapter = DeterministicAdapter
    try:
        app = FastAPI()
        enterprise_api.install_enterprise_routes(app, runtime)

        def headers(username, password):
            token, _ = identity.login(username, password)
            return {"Authorization": "Bearer " + token}

        admin = headers("alpha-admin", passwords["admin"])
        analyst = headers("alpha-analyst", passwords["analyst"])
        bravo = headers("bravo-admin", passwords["bravo"])
        with TestClient(app) as client:
            check("missing_session_401", client.get("/api/enterprise/ai-configuration").status_code == 401)
            initial = client.get("/api/enterprise/ai-configuration", headers=admin)
            check("disabled_is_valid", initial.status_code == 200 and initial.json()["configuration"]["engine"] == "disabled")
            check("analyst_read_allowed", client.get("/api/enterprise/ai-configuration", headers=analyst).status_code == 200)
            check("analyst_write_denied", client.put("/api/enterprise/ai-configuration", headers=analyst, json={"engine": "ollama", "model": "qwen-local"}).status_code == 403)
            check("missing_model_fail_closed", client.put("/api/enterprise/ai-configuration", headers=admin, json={"engine": "ollama", "model": None}).status_code == 400)
            saved = client.put("/api/enterprise/ai-configuration", headers=admin, json={"engine": "ollama", "model": "qwen-local", "tenant_id": "bravo"})
            check("admin_save_allowed", saved.status_code == 200 and saved.json()["configuration"]["model"] == "qwen-local")
            check("public_payload_safe", not any(value in json.dumps(saved.json()) for value in ["base_url", "provider_type", "timeout", "context_window", "tenant_id", "secret_reference"]))
            detected = client.post("/api/enterprise/ai-configuration/detect", headers=admin)
            models = [item["id"] for item in detected.json()["models"]]
            check("detected_models", detected.status_code == 200 and "qwen-local" in models)
            check("local_model_alias_normalized", models.count("nomic-embed-text") == 1 and "nomic-embed-text:latest" not in models)
            verified = client.post("/api/enterprise/ai-configuration/test", headers=admin)
            check("verification_state", verified.status_code == 200 and verified.json()["configuration"]["state"] == "TESTED")
            check("cross_company_read_isolated", client.get("/api/enterprise/ai-configuration", headers=bravo).json()["configuration"]["engine"] == "disabled")
        reopened = EnterprisePlatformConfigStore(reports / ".platform_config", tenants)
        check("restart_persistence", reopened.resolve_effective_config("alpha")["ai_provider"]["model"] == "qwen-local")
        incomplete = {"provider_id": "ollama", "provider_type": "OLLAMA", "base_url": "http://127.0.0.1:11434", "model": None, "enabled": True, "timeout": 30, "context_window": None}
        reopened.update_tenant("bravo", {"ai_provider": incomplete, "enabled_features": {"sql_enabled": True, "knowledge_enabled": True, "pdf_enabled": True, "excel_enabled": True, "dashboard_enabled": True, "ai_enabled": True}})
        readiness = EnterpriseOnboarding(reports).readiness("bravo")
        check("missing_required_model_not_configured", readiness["steps"]["ai"]["status"] == "BLOCKED" and readiness["steps"]["ai"]["code"] == "AI_MODEL_INVALID")
    finally:
        enterprise_api.build_components = original_components
        enterprise_api._CommercialAiAdapter = original_adapter

print("R10_24A4_4_AI_SETTINGS=PASS")
