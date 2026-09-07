"""R10.22B: Enterprise AI HTTP accepts only EnterpriseIdentityStore sessions."""
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


with tempfile.TemporaryDirectory() as tmp:
    product = Path(tmp) / "product"; runtime = product / "IA_Local"; runtime.mkdir(parents=True)
    (product / "RELEASE_METADATA.json").write_text(json.dumps({"schema_version": 1, "product": "IA_EMPRESARIAL_LOCAL", "product_version": "8.5.5", "release": "r10.21f", "channel": "stable"}), encoding="utf-8")
    os.environ["IA_LOCAL_ROOT"] = str(runtime)
    import analizador_universal as analyzer
    from enterprise_ai.security import Principal, create_token
    from enterprise_sql_gateway import EnterpriseSqlConnectionStore
    from fastapi.testclient import TestClient

    reports = runtime / "workspace" / "Reportes"
    check("canonical_identity_store_root", analyzer._identity_store().root.resolve() == (reports / ".identity").resolve())
    tenants = analyzer._tenant_registry()
    tenants.create(tenant_id="alpha", name="Alpha"); tenants.create(tenant_id="bravo", name="Bravo")
    identities = analyzer._identity_store()
    identities.bootstrap_admin(user_id="sys", username="sys", display_name="System", password="SystemPassword!1", tenant_id="alpha")
    identities.create_user(user_id="tenant", username="tenant", display_name="Tenant", password="TenantPassword!1", tenant_id="alpha", roles=["TENANT_ADMIN"])
    identities.create_user(user_id="analyst", username="analyst", display_name="Analyst", password="AnalystPassword!1", tenant_id="alpha", roles=["ANALYST"])
    identities.create_user(user_id="viewer", username="viewer", display_name="Viewer", password="ViewerPassword!1", tenant_id="alpha", roles=["VIEWER"])
    identities.create_user(user_id="bravo_user", username="bravo", display_name="Bravo", password="BravoPassword!1", tenant_id="bravo", roles=["TENANT_ADMIN"])
    sql = EnterpriseSqlConnectionStore(reports / ".sql_connections", tenants)
    sql.register(scope=identities.scope(identities.get("tenant")), connection_id="alpha_source", server="a", database="a", auth_mode="WINDOWS_INTEGRATED", allowed_schemas=["dbo"], allowed_tables=["dbo.TableA"])
    sql.register(scope=identities.scope(identities.get("bravo_user")), connection_id="bravo_source", server="b", database="b", auth_mode="WINDOWS_INTEGRATED", allowed_schemas=["dbo"], allowed_tables=["dbo.TableB"])

    with TestClient(analyzer.app) as client:
        bad = client.post("/api/auth/login", json={"username": "sys", "password": "wrong"})
        check("invalid_credentials", bad.status_code == 401 and "token" not in bad.text.lower())
        login = client.post("/api/auth/login", json={"username": "sys", "password": "SystemPassword!1"})
        check("enterprise_login", login.status_code == 200 and isinstance(login.json().get("token"), str))
        token = login.json()["token"]; headers = {"Authorization": "Bearer " + token}
        check("opaque_session_token", "." not in token and len(token) >= 32)
        stored = (reports / ".identity" / "identity.json").read_text(encoding="utf-8")
        check("raw_token_not_persisted", token not in stored and "token_fingerprint" in stored)
        me = client.get("/api/auth/me", headers=headers)
        enterprise = client.get("/api/enterprise/health", headers=headers)
        check("me_agrees_with_enterprise_principal", me.status_code == 200 and enterprise.status_code == 200 and me.json()["tenant_id"] == enterprise.json()["company"] and me.json()["user_id"] == enterprise.json()["user"])
        legacy = create_token(b"legacy-secret", Principal("alpha", "sys", "admin"), expires_seconds=300)
        check("legacy_hmac_rejected", client.get("/api/enterprise/health", headers={"Authorization": "Bearer " + legacy}).status_code == 401)

        for endpoint in ("overview", "tenants", "users", "sql-sources", "ai"):
            check("system_endpoint_" + endpoint, client.get("/api/enterprise/control-plane/" + endpoint, headers=headers).status_code == 200)
        tenant_login = client.post("/api/auth/login", json={"username": "tenant", "password": "TenantPassword!1"}).json()["token"]
        tenant_h = {"Authorization": "Bearer " + tenant_login}
        tenant_sources = client.get("/api/enterprise/control-plane/sql-sources?tenant_id=bravo", headers=tenant_h)
        check("cross_tenant_override_blocked", tenant_sources.status_code == 200 and [x["connection_id"] for x in tenant_sources.json()["sources"]] == ["alpha_source"])
        check("tenant_scope", [x["tenant_id"] for x in client.get("/api/enterprise/control-plane/tenants", headers=tenant_h).json()["tenants"]] == ["alpha"])
        analyst_h = {"Authorization": "Bearer " + client.post("/api/auth/login", json={"username": "analyst", "password": "AnalystPassword!1"}).json()["token"]}
        viewer_h = {"Authorization": "Bearer " + client.post("/api/auth/login", json={"username": "viewer", "password": "ViewerPassword!1"}).json()["token"]}
        check("analyst_permissions", client.get("/api/enterprise/control-plane/sql-sources", headers=analyst_h).status_code == 200 and client.get("/api/enterprise/control-plane/users", headers=analyst_h).status_code == 403)
        check("viewer_permissions", client.get("/api/enterprise/control-plane/overview", headers=viewer_h).status_code == 403)
        public = client.get("/api/enterprise/control-plane/overview", headers=headers).text.lower()
        check("public_responses_secret_safe", all(item not in public for item in ("password_hash", "secret_reference", "credential_ref", "token_fingerprint")))

        check("logout_revokes_enterprise", client.post("/api/auth/logout", headers=headers).status_code == 200 and client.get("/api/enterprise/health", headers=headers).status_code == 401)
        disabled_token = client.post("/api/auth/login", json={"username": "viewer", "password": "ViewerPassword!1"}).json()["token"]
        identities.set_status("viewer", "DISABLED")
        check("disabled_user_rejected", client.get("/api/enterprise/health", headers={"Authorization": "Bearer " + disabled_token}).status_code == 401)
        password_token = client.post("/api/auth/login", json={"username": "tenant", "password": "TenantPassword!1"}).json()["token"]
        identities.change_password("tenant", "TenantPassword!2")
        check("password_change_revokes", client.get("/api/enterprise/health", headers={"Authorization": "Bearer " + password_token}).status_code == 401)
        exp_token, _ = identities.login("analyst", "AnalystPassword!1")
        data = identities._load(); data["sessions"][-1]["expires_at"] = "2000-01-01T00:00:00+00:00"; identities._save(data)
        check("expired_session_rejected", client.get("/api/enterprise/health", headers={"Authorization": "Bearer " + exp_token}).status_code == 401)
        bravo_token = client.post("/api/auth/login", json={"username": "bravo", "password": "BravoPassword!1"}).json()["token"]
        tenants.disable("bravo")
        check("disabled_tenant_rejected", client.get("/api/enterprise/health", headers={"Authorization": "Bearer " + bravo_token}).status_code == 401)
        check("auth_failures_not_500", all(client.get("/api/enterprise/health", headers={"Authorization": "Bearer " + value}).status_code == 401 for value in ("random", legacy, disabled_token, password_token, exp_token, bravo_token)))
    analyzer.ENTERPRISE_COMPONENTS.vectors.close()
    logging.shutdown()
print("PASS R10.22B")
