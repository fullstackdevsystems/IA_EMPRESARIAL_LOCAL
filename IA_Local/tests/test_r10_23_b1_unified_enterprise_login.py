"""R10.23-B.1: assistant login UX uses enterprise sessions and fails closed."""

import json
import logging
import os
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"
sys.path.insert(0, str(SCRIPTS))
SOURCE = (SCRIPTS / "enterprise_ai" / "api.py").read_text(encoding="utf-8")
ASSISTANT = SOURCE.split('ASSISTANT_HTML = r"""', 1)[1].split('"""\n\n\nADMIN_HTML', 1)[0]


def check(name, condition):
    assert condition, name
    print("PASS", name)


check("assistant_login_form", 'id="authUser"' in ASSISTANT and 'type="password"' in ASSISTANT)
check("enterprise_login_endpoint", "'/api/auth/login'" in ASSISTANT)
check("auth_me_uses_protected_request", "protectedFetch('/api/auth/me')" in ASSISTANT)
check("session_storage_only", "sessionStorage" in ASSISTANT and "localStorage" not in ASSISTANT)
check("no_url_token", "?token=" not in ASSISTANT and "location.hash" not in ASSISTANT)
check("logout_contract", "'/api/auth/logout'" in ASSISTANT and "enterpriseLogout" in ASSISTANT)
check("global_401_handler", "function handleUnauthorized()" in ASSISTANT and "response.status===401" in ASSISTANT)
check("401_clears_session", "function clearEnterpriseSession()" in ASSISTANT and "sessionStorage.removeItem('iaEnterpriseSession')" in ASSISTANT)
check("stream_stops_before_reader", "if(!r)return;if(r.status===403)" in ASSISTANT and "const reader=r.body.getReader()" in ASSISTANT)
check("stream_403_preserves_session", "bubble.textContent='Acceso denegado.';return" in ASSISTANT)
check("feedback_uses_global_protected_request", ASSISTANT.count("protectedFetch('/api/enterprise/feedback") >= 2)
check("memory_confirmation_uses_global_protected_request", "protectedFetch('/api/enterprise/memories/'+id+'/confirm'" in ASSISTANT)
check("legacy_manual_login_removed", "ABRIR_ASISTENTE.bat" not in ASSISTANT and "PowerShell" not in ASSISTANT)
check("no_legacy_identity_fallback", "empresa-local" not in ASSISTANT and "admin-local" not in ASSISTANT)


with tempfile.TemporaryDirectory() as tmp:
    product = Path(tmp) / "product"
    runtime = product / "IA_Local"
    runtime.mkdir(parents=True)
    (product / "RELEASE_METADATA.json").write_text(
        json.dumps({"schema_version": 1, "product": "IA_EMPRESARIAL_LOCAL", "product_version": "8.5.5", "release": "r10.22f", "channel": "stable"}),
        encoding="utf-8",
    )
    os.environ["IA_LOCAL_ROOT"] = str(runtime)
    import analizador_universal as analyzer
    from fastapi.testclient import TestClient

    tenants = analyzer._tenant_registry()
    tenants.create(tenant_id="alpha", name="Alpha")
    tenants.create(tenant_id="bravo", name="Bravo")
    identities = analyzer._identity_store()
    identities.bootstrap_admin(user_id="alpha-admin", username="alpha", display_name="Alpha", password="AlphaPassword!1", tenant_id="alpha")
    identities.create_user(user_id="bravo-admin", username="bravo", display_name="Bravo", password="BravoPassword!1", tenant_id="bravo", roles=["TENANT_ADMIN"])
    identities.create_user(user_id="viewer", username="viewer", display_name="Viewer", password="ViewerPassword!1", tenant_id="alpha", roles=["VIEWER"])

    with TestClient(analyzer.app) as client:
        invalid = client.post("/api/auth/login", json={"username": "alpha", "password": "wrong"})
        check("real_login_invalid_credentials", invalid.status_code == 401 and "token" not in invalid.text.lower())
        login = client.post("/api/auth/login", json={"username": "alpha", "password": "AlphaPassword!1"})
        check("real_login_flow", login.status_code == 200 and isinstance(login.json().get("token"), str))
        alpha_token = login.json()["token"]
        alpha_headers = {"Authorization": "Bearer " + alpha_token}
        alpha_me = client.get("/api/auth/me", headers=alpha_headers)
        check("auth_me_validation", alpha_me.status_code == 200 and alpha_me.json()["tenant_id"] == "alpha")
        stream_ok = client.post("/api/enterprise/chat/stream", headers=alpha_headers, json={"message": "estado", "history": []})
        check("assistant_protected_operation", stream_ok.status_code == 200)
        stream_401 = client.post("/api/enterprise/chat/stream", json={"message": "estado", "history": []})
        check("chat_stream_401_real", stream_401.status_code == 401)
        viewer_token = client.post("/api/auth/login", json={"username": "viewer", "password": "ViewerPassword!1"}).json()["token"]
        viewer_headers = {"Authorization": "Bearer " + viewer_token}
        stream_403 = client.post("/api/enterprise/chat/stream", headers=viewer_headers, json={"message": "estado", "history": []})
        viewer_me = client.get("/api/auth/me", headers=viewer_headers)
        check("chat_stream_403_session_preserved", stream_403.status_code == 403 and viewer_me.status_code == 200)
        bravo_token = client.post("/api/auth/login", json={"username": "bravo", "password": "BravoPassword!1"}).json()["token"]
        bravo_headers = {"Authorization": "Bearer " + bravo_token}
        bravo_me = client.get("/api/auth/me", headers=bravo_headers)
        bravo_tenants = client.get("/api/enterprise/control-plane/tenants?tenant_id=alpha", headers=bravo_headers)
        check("tenant_isolation_real_sessions", bravo_me.status_code == 200 and bravo_me.json()["tenant_id"] == "bravo" and bravo_tenants.status_code == 200 and [item["tenant_id"] for item in bravo_tenants.json()["tenants"]] == ["bravo"])
        logged_out = client.post("/api/auth/logout", headers=alpha_headers)
        revoked_stream = client.post("/api/enterprise/chat/stream", headers=alpha_headers, json={"message": "estado", "history": []})
        check("logout_ui_backend_contract", logged_out.status_code == 200 and revoked_stream.status_code == 401)
    analyzer.ENTERPRISE_COMPONENTS.vectors.close()
    logging.shutdown()

print("PASS R10.23-B.1")
