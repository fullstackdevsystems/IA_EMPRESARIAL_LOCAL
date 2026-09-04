from pathlib import Path
import sys
import tempfile
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analizador_universal as analyzer
from enterprise_sql_gateway import EnterpriseSecretStore, EnterpriseSqlConnectionStore, EnterpriseSqlError


def check(name, value):
    if not value: raise AssertionError(name)
    print("PASS", name)


class SecretProvider:
    def __init__(self): self.values = {}
    def set(self, key, value): self.values[key] = value
    def get(self, key): return self.values.get(key)
    def delete(self, key): self.values.pop(key, None)


class FakeProvider:
    def __init__(self): self.closed = False
    def test_connection(self, profile, timeout): self.closed = True; return {"database": profile["database"]}
    def discover(self, profile):
        self.closed = True
        return [{"schema":"dbo", "name":"Allowed", "type":"TABLE", "columns":[{"name":"id", "type":"int", "nullable":False}]}, {"schema":"private", "name":"Hidden", "type":"TABLE", "columns":[{"name":"secret", "type":"nvarchar", "nullable":False}]}]


class FailingProvider(FakeProvider):
    def test_connection(self, profile, timeout):
        raise EnterpriseSqlError("SQL_AUTH_FAILED", "raw password=never-returned")


def profile(connection_id, mode="WINDOWS_INTEGRATED"):
    data = {"connection_id":connection_id, "server":"sql-host", "database":"enterprise", "auth_mode":mode, "allowed_schemas":["dbo"], "allowed_tables":["dbo.Allowed"]}
    if mode == "SQL_AUTH": data.update({"username":"reader", "password":"PasswordNeverReturned!"})
    return data


with tempfile.TemporaryDirectory() as td:
    old_reports = analyzer.base.REPORTES
    analyzer.base.REPORTES = Path(td) / "reports"
    events = []; provider = FakeProvider(); secret_provider = SecretProvider()
    try:
        tenants = analyzer._tenant_registry()
        for tenant_id in ("construction", "services", "logistics"): tenants.create(tenant_id=tenant_id, name=tenant_id)
        identities = analyzer._identity_store()
        identities.bootstrap_admin(user_id="sys", username="sys", display_name="System", password="SystemPassword!1", tenant_id="construction")
        identities.create_user(user_id="tenant", username="tenant", display_name="Tenant", password="TenantPassword!1", tenant_id="construction", roles=["TENANT_ADMIN"])
        identities.create_user(user_id="analyst", username="analyst", display_name="Analyst", password="AnalystPassword!1", tenant_id="construction", roles=["ANALYST"])
        identities.create_user(user_id="viewer", username="viewer", display_name="Viewer", password="ViewerPassword!1", tenant_id="construction", roles=["VIEWER"])
        store = EnterpriseSqlConnectionStore(Path(td) / "sql", tenants)
        analyzer.configure_sql_admin_services(store=store, provider=provider, secret_store=EnterpriseSecretStore(secret_provider), audit_events=events)
        with TestClient(analyzer.app) as client:
            check("unauthenticated", client.get("/api/admin/sql/connections").status_code == 401)
            check("invalid_token", client.get("/api/admin/sql/connections", headers={"Authorization":"Bearer invalid"}).status_code == 401)
            def login(username, password):
                response = client.post("/api/auth/login", json={"username":username, "password":password})
                check("login_" + username, response.status_code == 200)
                return {"Authorization":"Bearer " + response.json()["token"]}
            sys_h = login("sys", "SystemPassword!1"); tenant_h = login("tenant", "TenantPassword!1"); analyst_h = login("analyst", "AnalystPassword!1"); viewer_h = login("viewer", "ViewerPassword!1")
            check("system_explicit_required", client.get("/api/admin/sql/connections", headers=sys_h).status_code == 400)
            check("system_explicit_tenant", client.get("/api/admin/sql/connections?tenant_id=construction", headers=sys_h).status_code == 200)
            created = client.post("/api/admin/sql/connections", headers=tenant_h, json=profile("win"))
            check("tenant_create_windows", created.status_code == 200 and created.json()["profile"]["auth_mode"] == "WINDOWS_INTEGRATED")
            sql_created = client.post("/api/admin/sql/connections", headers=tenant_h, json=profile("sql", "SQL_AUTH"))
            check("create_sql_auth_secret_safe", sql_created.status_code == 200 and "password" not in sql_created.text.lower() and "secret_reference" not in sql_created.text.lower() and secret_provider.values)
            check("list_get", client.get("/api/admin/sql/connections", headers=tenant_h).status_code == 200 and client.get("/api/admin/sql/connections/win", headers=tenant_h).status_code == 200)
            update = client.patch("/api/admin/sql/connections/win", headers=tenant_h, json={"display_name":"Construcción Ñ", "timeout_seconds":12})
            check("update_immutable", update.status_code == 200 and client.patch("/api/admin/sql/connections/win", headers=tenant_h, json={"connection_id":"other"}).status_code == 400)
            allow = client.patch("/api/admin/sql/connections/win/allowlist", headers=tenant_h, json={"schemas":["dbo"], "objects":["dbo.Allowed"]})
            check("allowlist", allow.status_code == 200 and client.patch("/api/admin/sql/connections/win/allowlist", headers=tenant_h, json={"schemas":["dbo"], "objects":["invalid"]}).status_code == 400)
            test = client.post("/api/admin/sql/connections/win/test", headers=tenant_h); discover = client.post("/api/admin/sql/connections/win/discover", headers=tenant_h)
            check("test_discover", test.status_code == 200 and discover.status_code == 200 and "rows" not in discover.text and "Hidden" not in discover.text)
            check("analyst_policy", client.post("/api/admin/sql/connections/win/test", headers=analyst_h).status_code == 200 and client.post("/api/admin/sql/connections/win/discover", headers=analyst_h).status_code == 200 and client.post("/api/admin/sql/connections", headers=analyst_h, json=profile("denied")).status_code == 403)
            check("viewer_policy", client.get("/api/admin/sql/connections", headers=viewer_h).status_code == 403)
            disabled = client.post("/api/admin/sql/connections/win/disable", headers=tenant_h)
            check("disable_closed", disabled.status_code == 200 and client.post("/api/admin/sql/connections/win/test", headers=tenant_h).json()["detail"]["code"] == "SQL_CONNECTION_DISABLED" and client.post("/api/admin/sql/connections/win/discover", headers=tenant_h).json()["detail"]["code"] == "SQL_CONNECTION_DISABLED")
            check("enable", client.post("/api/admin/sql/connections/win/enable", headers=tenant_h).status_code == 200)
            rotated = client.post("/api/admin/sql/connections/sql/secret", headers=tenant_h, json={"secret":"RotatedNeverReturned!"})
            check("secret_rotation", rotated.status_code == 200 and "RotatedNeverReturned" not in rotated.text and "RotatedNeverReturned!" in secret_provider.values.values())
            service = client.post("/api/admin/sql/connections?tenant_id=services", headers=sys_h, json=profile("service"))
            check("system_create_other_tenant", service.status_code == 200)
            cross = client.get("/api/admin/sql/connections/service?tenant_id=services", headers=tenant_h)
            check("tenant_cross_hidden", cross.status_code == 403 and client.post("/api/admin/sql/connections/service/test?tenant_id=services", headers=tenant_h).status_code == 403)
            check("tenant_own_list", len(client.get("/api/admin/sql/connections", headers=tenant_h).json()["items"]) == 2)
            analyzer.configure_sql_admin_services(store=store, provider=provider, secret_store=EnterpriseSecretStore(), audit_events=events)
            check("secret_provider_fail_closed", client.post("/api/admin/sql/connections?tenant_id=logistics", headers=sys_h, json=profile("other", "SQL_AUTH")).status_code == 503)
            analyzer.configure_sql_admin_services(store=store, provider=FailingProvider(), secret_store=EnterpriseSecretStore(secret_provider), audit_events=events)
            sanitized = client.post("/api/admin/sql/connections/win/test", headers=tenant_h)
            check("sanitized_error", sanitized.status_code == 400 and "password" not in sanitized.text.lower() and sanitized.json()["detail"]["code"] == "SQL_AUTH_FAILED")
            analyzer.configure_sql_admin_services(store=store, provider=provider, secret_store=EnterpriseSecretStore(secret_provider), audit_events=events)
            public = client.get("/api/admin/sql/connections/sql", headers=tenant_h).text.lower()
            check("public_safe", "secret_reference" not in public and "credential_ref" not in public and "passwordneverreturned" not in public and "bearer " not in public)
            required_events = {"SQL_CONNECTION_CREATED", "SQL_CONNECTION_UPDATED", "SQL_ALLOWLIST_CHANGED", "SQL_CONNECTION_TESTED", "SQL_DISCOVERY_RUN", "SQL_CONNECTION_DISABLED", "SQL_CONNECTION_ENABLED", "SQL_SECRET_ROTATED"}
            check("audit_events", required_events <= {item["event"] for item in events} and "password" not in str(events).lower())
    finally:
        analyzer.configure_sql_admin_services()
        analyzer.base.REPORTES = old_reports

print("PASS R10.20B.3.3")
