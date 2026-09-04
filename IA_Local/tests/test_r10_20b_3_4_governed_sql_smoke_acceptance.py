from pathlib import Path
import sys
import tempfile
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analizador_universal as analyzer
from enterprise_sql_gateway import EnterpriseSecretStore, EnterpriseSqlConnectionStore, EnterpriseSqlError, SqlServerPyodbcProvider


def check(name, value):
    if not value: raise AssertionError(name)
    print("PASS", name)


class SecretProvider:
    def __init__(self): self.values = {}
    def set(self, key, value): self.values[key] = value
    def get(self, key): return self.values.get(key)
    def delete(self, key): self.values.pop(key, None)


class FakeProvider:
    def __init__(self, failure=False): self.failure, self.sql, self.timeout = failure, "", None
    def execute(self, profile, sql, parameters, timeout_seconds):
        self.sql, self.timeout = sql, timeout_seconds
        if self.failure: raise EnterpriseSqlError("SQL_EXECUTION_FAILED", "raw password=never-returned")
        return {"columns":["Id", "Name"], "rows":[[index, "row"] for index in range(5)]}
    def discover(self, profile): return []


def payload(limit=10): return {"schema":"dbo", "object":"Allowed", "columns":["Id", "Name"], "limit":limit}


with tempfile.TemporaryDirectory() as td:
    old_reports = analyzer.base.REPORTES; analyzer.base.REPORTES = Path(td) / "reports"
    events, secrets_provider, provider = [], SecretProvider(), FakeProvider()
    try:
        tenants = analyzer._tenant_registry()
        for tenant_id in ("construction", "services", "logistics"): tenants.create(tenant_id=tenant_id, name=tenant_id)
        identities = analyzer._identity_store()
        identities.bootstrap_admin(user_id="sys", username="sys", display_name="System", password="SystemPassword!1", tenant_id="construction")
        identities.create_user(user_id="tenant", username="tenant", display_name="Tenant", password="TenantPassword!1", tenant_id="construction", roles=["TENANT_ADMIN"])
        identities.create_user(user_id="analyst", username="analyst", display_name="Analyst", password="AnalystPassword!1", tenant_id="construction", roles=["ANALYST"])
        identities.create_user(user_id="viewer", username="viewer", display_name="Viewer", password="ViewerPassword!1", tenant_id="construction", roles=["VIEWER"])
        store = EnterpriseSqlConnectionStore(Path(td) / "sql", tenants)
        analyzer.configure_sql_admin_services(store=store, provider=provider, secret_store=EnterpriseSecretStore(secrets_provider), audit_events=events)
        with TestClient(analyzer.app) as client:
            def login(username, password):
                response = client.post("/api/auth/login", json={"username":username, "password":password}); check("login_" + username, response.status_code == 200)
                return {"Authorization":"Bearer " + response.json()["token"]}
            sys_h, tenant_h, analyst_h, viewer_h = login("sys", "SystemPassword!1"), login("tenant", "TenantPassword!1"), login("analyst", "AnalystPassword!1"), login("viewer", "ViewerPassword!1")
            created = client.post("/api/admin/sql/connections", headers=tenant_h, json={"connection_id":"smoke", "server":"sql", "database":"build", "auth_mode":"WINDOWS_INTEGRATED", "allowed_schemas":["dbo"], "allowed_tables":["dbo.Allowed"], "max_rows":3, "timeout_seconds":11})
            check("create", created.status_code == 200)
            check("auth_required", client.post("/api/admin/sql/connections/smoke/smoke", json=payload()).status_code == 401)
            result = client.post("/api/admin/sql/connections/smoke/smoke", headers=tenant_h, json=payload()).json()
            check("tenant_smoke", result["status"] == "PASS" and result["row_count"] == 3 and result["truncated"] is True)
            check("structured_select_limit_timeout", provider.sql == "SELECT TOP (3) [Id], [Name] FROM [dbo].[Allowed]" and provider.timeout == 11)
            check("system_analyst", client.post("/api/admin/sql/connections/smoke/smoke?tenant_id=construction", headers=sys_h, json=payload(2)).status_code == 200 and client.post("/api/admin/sql/connections/smoke/smoke", headers=analyst_h, json=payload(2)).status_code == 200)
            check("viewer", client.post("/api/admin/sql/connections/smoke/smoke", headers=viewer_h, json=payload()).status_code == 403)
            for invalid in ({"sql":"SELECT * FROM dbo.Allowed"}, {"schema":"dbo","object":"Allowed","columns":["*"],"limit":1}, {"schema":"dbo","object":"Allowed","columns":["Id;DELETE"],"limit":1}, {"schema":"other","object":"Allowed","columns":["Id"],"limit":1}, {"schema":"dbo","object":"Other","columns":["Id"],"limit":1}):
                response = client.post("/api/admin/sql/connections/smoke/smoke", headers=tenant_h, json=invalid)
                check("plan_blocked", response.status_code == 400 and response.json()["detail"]["code"] in {"SQL_QUERY_INVALID", "SQL_ALLOWLIST_DENIED"})
            store.register(scope={"company_id":"services","user_id":"sql-admin","business_unit":None,"branch":None}, connection_id="other", server="sql", database="service", auth_mode="WINDOWS_INTEGRATED", allowed_schemas=["dbo"], allowed_tables=["dbo.Allowed"])
            check("cross_tenant", client.post("/api/admin/sql/connections/other/smoke?tenant_id=services", headers=tenant_h, json=payload()).status_code == 403)
            client.post("/api/admin/sql/connections/smoke/disable", headers=tenant_h)
            disabled = client.post("/api/admin/sql/connections/smoke/smoke", headers=tenant_h, json=payload())
            check("disabled", disabled.status_code == 400 and disabled.json()["detail"]["code"] == "SQL_CONNECTION_DISABLED")
            client.post("/api/admin/sql/connections/smoke/enable", headers=tenant_h)
            auth_profile = store.register(scope={"company_id":"construction","user_id":"sql-admin","business_unit":None,"branch":None}, connection_id="auth", server="sql", database="build", auth_mode="SQL_AUTH", username="reader", secret_reference="missing", allowed_schemas=["dbo"], allowed_tables=["dbo.Allowed"])
            analyzer.configure_sql_admin_services(store=store, provider=SqlServerPyodbcProvider(EnterpriseSecretStore()), secret_store=EnterpriseSecretStore(), audit_events=events)
            missing = client.post("/api/admin/sql/connections/auth/smoke", headers=tenant_h, json=payload())
            check("secret_closed", missing.status_code == 503 and missing.json()["detail"]["code"] == "SQL_SECRET_UNAVAILABLE")
            analyzer.configure_sql_admin_services(store=store, provider=FakeProvider(True), secret_store=EnterpriseSecretStore(secrets_provider), audit_events=events)
            failed = client.post("/api/admin/sql/connections/smoke/smoke", headers=tenant_h, json=payload())
            check("error_sanitized", failed.status_code == 400 and "password" not in failed.text.lower())
            analyzer.configure_sql_admin_services(store=store, provider=provider, secret_store=EnterpriseSecretStore(secrets_provider), audit_events=events)
            final_result = client.post("/api/admin/sql/connections/smoke/smoke", headers=tenant_h, json=payload(2)).json()
            profile_data = store.get({"company_id":"construction","user_id":"sql-admin","business_unit":None,"branch":None}, "smoke")
            check("provenance_metadata", final_result["provenance"]["schema"] == "dbo" and len(final_result["provenance"]["query_fingerprint_sha256"]) == 64 and final_result["query_ms"] >= 0 and profile_data["last_query_status"] == "PASS" and profile_data["last_query_row_count"] == 2)
            smoke_events = [event for event in events if event["event"] == "SQL_SMOKE_RUN"]
            check("audit_safe", smoke_events and "rows" not in smoke_events[-1] and smoke_events[-1]["row_count"] == 2 and "bearer" not in str(smoke_events).lower())
            check("no_secret_leak", "password" not in str(final_result["provenance"]).lower() and "connection string" not in str(final_result).lower())
    finally:
        analyzer.configure_sql_admin_services(); analyzer.base.REPORTES = old_reports

print("PASS R10.20B.3.4")
