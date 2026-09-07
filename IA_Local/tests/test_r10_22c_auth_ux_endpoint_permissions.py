"""R10.22C: local enterprise login UX and endpoint-specific permissions."""
import json
import logging
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "IA_Local" / "scripts"))


def check(name, condition):
    assert condition, name
    print("PASS", name)


from enterprise_ai.admin_console import UNIFIED_ADMIN_HTML
from enterprise_ai.security import Principal, create_token

check("admin_without_url_token", "location.hash" not in UNIFIED_ADMIN_HTML and "URLSearchParams" not in UNIFIED_ADMIN_HTML and "#token" not in UNIFIED_ADMIN_HTML)
check("session_storage_only", "sessionStorage.getItem('iaEnterpriseSession')" in UNIFIED_ADMIN_HTML and "localStorage" not in UNIFIED_ADMIN_HTML)
check("login_ux", "/api/auth/login" in UNIFIED_ADMIN_HTML and 'type=\"password\"' in UNIFIED_ADMIN_HTML and "p.value=''" in UNIFIED_ADMIN_HTML)
check("logout_ux", "/api/auth/logout" in UNIFIED_ADMIN_HTML and "sessionStorage.removeItem('iaEnterpriseSession')" in UNIFIED_ADMIN_HTML)
check("auth_me_context", "/api/auth/me" in UNIFIED_ADMIN_HTML)
check("401_and_403_distinct", "if(r.status===401){showLogin" in UNIFIED_ADMIN_HTML and "if(!r.ok)throw" in UNIFIED_ADMIN_HTML)

with tempfile.TemporaryDirectory() as tmp:
    product = Path(tmp) / "product"; runtime = product / "IA_Local"; runtime.mkdir(parents=True)
    (product / "RELEASE_METADATA.json").write_text(json.dumps({"schema_version": 1, "product": "IA_EMPRESARIAL_LOCAL", "product_version": "8.5.5", "release": "r10.21f", "channel": "stable"}), encoding="utf-8")
    os.environ["IA_LOCAL_ROOT"] = str(runtime)
    import analizador_universal as analyzer
    from fastapi.testclient import TestClient

    reports = runtime / "workspace" / "Reportes"
    tenants = analyzer._tenant_registry(); tenants.create(tenant_id="alpha", name="Alpha"); tenants.create(tenant_id="bravo", name="Bravo")
    identities = analyzer._identity_store()
    identities.bootstrap_admin(user_id="sys", username="sys", display_name="System", password="SystemPassword!1", tenant_id="alpha")
    identities.create_user(user_id="tenant", username="tenant", display_name="Tenant", password="TenantPassword!1", tenant_id="alpha", roles=["TENANT_ADMIN"])
    identities.create_user(user_id="analyst", username="analyst", display_name="Analyst", password="AnalystPassword!1", tenant_id="alpha", roles=["ANALYST"])
    identities.create_user(user_id="viewer", username="viewer", display_name="Viewer", password="ViewerPassword!1", tenant_id="alpha", roles=["VIEWER"])

    def login(client, username, password):
        response = client.post("/api/auth/login", json={"username": username, "password": password})
        check("login_" + username, response.status_code == 200 and response.json().get("token"))
        return {"Authorization": "Bearer " + response.json()["token"]}

    with TestClient(analyzer.app) as client:
        system = login(client, "sys", "SystemPassword!1")
        tenant = login(client, "tenant", "TenantPassword!1")
        analyst = login(client, "analyst", "AnalystPassword!1")
        viewer = login(client, "viewer", "ViewerPassword!1")
        me = client.get("/api/auth/me", headers=analyst)
        check("effective_permissions_from_identity", me.status_code == 200 and "analysis:run" in me.json()["effective_permissions"] and "admin:audit" not in me.json()["effective_permissions"])

        protected = ("/api/enterprise/control-plane/overview", "/api/enterprise/control-plane/tenants", "/api/enterprise/control-plane/users", "/api/enterprise/control-plane/sql-sources", "/api/enterprise/control-plane/ai")
        check("all_control_endpoints_require_session", all(client.get(path).status_code == 401 for path in protected))
        check("system_admin_global", all(client.get(path, headers=system).status_code == 200 for path in protected))
        check("tenant_admin_isolated", client.get("/api/enterprise/control-plane/tenants", headers=tenant).json()["tenants"][0]["tenant_id"] == "alpha")
        check("analyst_sql_read_not_user_list", client.get("/api/enterprise/control-plane/sql-sources", headers=analyst).status_code == 200 and client.get("/api/enterprise/control-plane/users", headers=analyst).status_code == 403)
        check("viewer_real_permissions", client.get("/api/enterprise/control-plane/overview", headers=viewer).status_code == 403)
        check("config_read_permission", client.get("/api/enterprise/settings", headers=analyst).status_code == 200 and client.get("/api/enterprise/settings", headers=viewer).status_code == 403)
        check("config_write_permission", client.put("/api/enterprise/settings", headers=analyst, json={}).status_code == 403 and client.put("/api/enterprise/settings", headers=tenant, json={}).status_code == 200)
        check("knowledge_read_write_permissions", client.get("/api/enterprise/memories", headers=viewer).status_code == 200 and client.post("/api/enterprise/memories", headers=viewer, json={"content": "x", "category": "conocimiento_empresa"}).status_code == 403)
        check("audit_permission", client.get("/api/enterprise/audit", headers=analyst).status_code == 403 and client.get("/api/enterprise/audit", headers=tenant).status_code == 200)
        legacy = create_token(b"legacy", Principal("alpha", "sys", "admin"), expires_seconds=60)
        check("legacy_hmac_rejected", client.get("/api/enterprise/health", headers={"Authorization": "Bearer " + legacy}).status_code == 401)
        check("invalid_session_401", client.get("/api/enterprise/settings", headers={"Authorization": "Bearer random"}).status_code == 401)
        public = client.get("/api/enterprise/control-plane/overview", headers=system).text.lower()
        check("no_secret_leakage", all(key not in public for key in ("password_hash", "token_fingerprint", "secret_reference", "credential_ref")))
    analyzer.ENTERPRISE_COMPONENTS.vectors.close()
    logging.shutdown()
print("PASS R10.22C")
