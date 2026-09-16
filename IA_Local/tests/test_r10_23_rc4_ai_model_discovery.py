from pathlib import Path
import sys
import tempfile

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analizador_universal as analyzer


def check(name, condition):
    assert condition, name
    print("PASS", name)


class DiscoveryAdapter:
    mode = "models"

    def discover_models(self, config):
        if self.mode == "timeout":
            raise TimeoutError()
        if self.mode == "unavailable":
            raise OSError("never expose endpoint details")
        if self.mode == "empty":
            return []
        return [
            {"name": "qwen3:4b-instruct"},
            {"name": "llama3:latest"},
            {"name": "qwen3:4b-instruct"},
        ]


def provider(model=None):
    return {
        "provider_id": "ollama",
        "provider_type": "OLLAMA",
        "base_url": "http://127.0.0.1:11434",
        "model": model,
        "enabled": True,
        "timeout": 5,
    }


with tempfile.TemporaryDirectory() as temporary:
    old_reports = analyzer.base.REPORTES
    old_adapter = analyzer._EnterpriseAiHealthAdapter
    analyzer.base.REPORTES = Path(temporary) / "Reportes"
    analyzer._EnterpriseAiHealthAdapter = DiscoveryAdapter
    try:
        tenants = analyzer._tenant_registry()
        tenants.create(tenant_id="alpha", name="Alpha")
        identity = analyzer._identity_store()
        identity.bootstrap_admin(
            user_id="admin",
            username="admin",
            display_name="Admin",
            password="SafePassword!1",
            tenant_id="alpha",
        )
        with TestClient(analyzer.app) as client:
            endpoint = "/api/admin/ai/provider/models"
            check("unauthenticated_blocked", client.post(endpoint, json={"provider": provider()}).status_code == 401)
            login = client.post("/api/auth/login", json={"username": "admin", "password": "SafePassword!1"})
            check("admin_login", login.status_code == 200)
            headers = {"Authorization": "Bearer " + login.json()["token"]}
            response = client.post(endpoint, headers=headers, json={"tenant_id": "alpha", "provider": provider("missing:model")})
            body = response.json()
            check("models_normalized", response.status_code == 200 and body["status"] == "PASS" and body["reachable"] and body["models"] == [{"id": "qwen3:4b-instruct", "name": "qwen3:4b-instruct"}, {"id": "llama3:latest", "name": "llama3:latest"}])
            check("discovery_secret_safe", "127.0.0.1:11434" not in response.text and "password" not in response.text.lower() and "token" not in response.text.lower())
            DiscoveryAdapter.mode = "empty"
            empty = client.post(endpoint, headers=headers, json={"tenant_id": "alpha", "provider": provider()}).json()
            check("empty_models_governed", empty["status"] == "EMPTY" and empty["reachable"] and empty["models"] == [])
            DiscoveryAdapter.mode = "timeout"
            timeout = client.post(endpoint, headers=headers, json={"tenant_id": "alpha", "provider": provider()}).json()
            check("timeout_governed", timeout["status"] == "TIMEOUT" and timeout["models"] == [])
            DiscoveryAdapter.mode = "unavailable"
            unavailable = client.post(endpoint, headers=headers, json={"tenant_id": "alpha", "provider": provider()}).json()
            check("unavailable_governed", unavailable["status"] == "UNAVAILABLE" and "endpoint" not in str(unavailable).lower())
            disabled = client.post(endpoint, headers=headers, json={"tenant_id": "alpha", "provider": {"provider_type": "DISABLED"}}).json()
            check("disabled_governed", disabled["status"] == "DISABLED" and disabled["models"] == [])
    finally:
        analyzer.base.REPORTES = old_reports
        analyzer._EnterpriseAiHealthAdapter = old_adapter


console = (ROOT / "scripts" / "enterprise_ai" / "admin_console.py").read_text(encoding="utf-8")
check("control_plane_model_is_select", '<select id="cpAiModel"' in console and '<input id="cpAiModel"' not in console)
check("guided_model_is_select", '<select id="gsAiModel"' in console and '<input id="gsAiModel"' not in console)
check("frontend_discovery_and_unavailable_state", "/api/admin/ai/provider/models" in console and "No fue posible conectar con el proveedor" in console)
check("configured_unavailable_preserved", "configurado, no disponible actualmente" in console)

print("PASS R10.23-RC4 AI model discovery")
