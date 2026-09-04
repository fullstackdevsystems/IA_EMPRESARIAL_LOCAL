from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from enterprise_sql_gateway import (EnterpriseSecretStore, EnterpriseSqlConnectionStore,
    EnterpriseSqlError, SqlServerPyodbcProvider, discover_schema, test_connection)


def check(name, value):
    if not value:
        raise AssertionError(name)
    print("PASS", name)


def blocked(name, code, action):
    try:
        action()
    except EnterpriseSqlError as exc:
        check(name, exc.code == code)
        return
    raise AssertionError(name)


def scope(company):
    return {"company_id": company, "user_id": "admin", "business_unit": None, "branch": None}


class SecretProvider:
    def __init__(self): self.values = {}
    def set(self, key, value): self.values[key] = value
    def get(self, key): return self.values.get(key)
    def delete(self, key): self.values.pop(key, None)


class FakeProvider:
    def __init__(self, failure=None): self.failure, self.closed = failure, False
    def test_connection(self, profile, timeout_seconds):
        try:
            if self.failure: raise EnterpriseSqlError(self.failure, "sensitive password=never-visible")
            return {"database": profile["database"]}
        finally:
            self.closed = True
    def discover(self, profile):
        try:
            if self.failure: raise EnterpriseSqlError(self.failure, "secret=never-visible")
            return [
                {"schema":"dbo", "name":"Allowed", "type":"TABLE", "columns":[{"name":"Id", "type":"int", "nullable":False}]},
                {"schema":"dbo", "name":"AllowedView", "type":"VIEW", "columns":[{"name":"Nombre", "type":"nvarchar", "nullable":True}]},
                {"schema":"private", "name":"Hidden", "type":"TABLE", "columns":[{"name":"Password", "type":"nvarchar", "nullable":False}]},
            ]
        finally:
            self.closed = True


with tempfile.TemporaryDirectory() as temp:
    store = EnterpriseSqlConnectionStore(Path(temp) / "connections")
    construction, services, logistics = scope("construction"), scope("services"), scope("logistics")
    win = store.register(scope=construction, connection_id="win", server="sql-host", database="build", auth_mode="WINDOWS_INTEGRATED", allowed_schemas=["dbo"], allowed_tables=["dbo.Allowed", "dbo.AllowedView"])
    sql = store.register(scope=services, connection_id="sql", server="sql-host", database="service", auth_mode="SQL_AUTH", username="reader", secret_reference="secret:services", allowed_schemas=["dbo"], allowed_tables=["dbo.Allowed"])
    store.register(scope=logistics, connection_id="log", server="sql-host", database="log", auth_mode="WINDOWS_INTEGRATED", allowed_schemas=["dbo"], allowed_tables=["dbo.Allowed"])
    check("windows_profile", win["auth_mode"] == "WINDOWS_INTEGRATED")
    provider = FakeProvider()
    result = test_connection(store, provider, construction, "win")
    check("windows_connection_test", result["status"] == "PASS" and result["authentication_mode"] == "WINDOWS_INTEGRATED")
    check("connection_close_success", provider.closed and result["connection_ms"] >= 0)
    profile = store.get(construction, "win")
    check("last_test_metadata", profile["last_test_status"] == "PASS" and profile["last_latency_ms"] >= 0 and profile["last_test_at"])
    secrets = EnterpriseSecretStore(SecretProvider())
    secrets.set("secret:services", "not-a-public-value")
    check("sql_auth_profile", sql["auth_mode"] == "SQL_AUTH" and secrets.get("secret:services"))
    check("sql_auth_connection_test", test_connection(store, FakeProvider(), services, "sql")["status"] == "PASS")
    blocked("missing_secret", "SQL_SECRET_UNAVAILABLE", lambda: test_connection(store, SqlServerPyodbcProvider(EnterpriseSecretStore()), services, "sql"))
    discovery = discover_schema(store, FakeProvider(), construction, "win")
    check("discovery_metadata", discovery["status"] == "PASS" and len(discovery["objects"]) == 2)
    check("tables_views_columns", {x["type"] for x in discovery["objects"]} == {"TABLE", "VIEW"} and all(x["columns"] for x in discovery["objects"]))
    check("allowlist_respected", all(x["name"] != "Hidden" for x in discovery["objects"]) and store.get(construction, "win")["allowed_tables"] == ["dbo.Allowed", "dbo.AllowedView"])
    check("discovery_metadata_saved", store.get(construction, "win")["discovered_object_count"] == 2 and store.get(construction, "win")["last_discovery_ms"] >= 0)
    blocked("scope_isolation", "SQL_CONNECTION_NOT_FOUND", lambda: test_connection(store, FakeProvider(), services, "win"))
    disabled = store.disable(construction, "win")
    blocked("disabled_test", "SQL_CONNECTION_DISABLED", lambda: test_connection(store, FakeProvider(), construction, disabled["connection_id"]))
    blocked("disabled_discovery", "SQL_CONNECTION_DISABLED", lambda: discover_schema(store, FakeProvider(), construction, disabled["connection_id"]))
    store.enable(construction, "win")
    for code in ("SQL_DRIVER_NOT_AVAILABLE", "SQL_AUTH_FAILED", "SQL_DATABASE_UNAVAILABLE"):
        failing = FakeProvider(code)
        blocked("error_" + code, code, lambda failing=failing: test_connection(store, failing, construction, "win"))
        check("close_" + code, failing.closed)
    discovery_failure = FakeProvider("SQL_SCHEMA_DISCOVERY_FAILED")
    blocked("discovery_failure", "SQL_SCHEMA_DISCOVERY_FAILED", lambda: discover_schema(store, discovery_failure, construction, "win"))
    try:
        test_connection(store, FakeProvider("SQL_AUTH_FAILED"), construction, "win")
    except EnterpriseSqlError as exc:
        check("error_sanitized", "password" not in str(exc).lower() and "secret" not in str(exc).lower())
    safe_payload = json.dumps({"test": result, "discovery": discovery}).lower()
    check("no_secret_or_data", "password" not in safe_payload and "secret" not in safe_payload and "not-a-public-value" not in safe_payload and "hidden" not in safe_payload)
    reloaded = EnterpriseSqlConnectionStore(Path(temp) / "connections").get(construction, "win")
    check("persistence_integrity", reloaded["last_test_at"] and reloaded["fingerprint_sha256"])
    raw = store._path(construction, "win"); tampered = json.loads(raw.read_text(encoding="utf-8")); tampered["database"] = "tampered"; raw.write_text(json.dumps(tampered), encoding="utf-8")
    blocked("tampering_detected", "SQL_CONNECTION_INTEGRITY_MISMATCH", lambda: store.get(construction, "win"))
    check("business_agnostic", bool(store.get(services, "sql")) and bool(store.get(logistics, "log")))

print("PASS R10.20B.3.2")
