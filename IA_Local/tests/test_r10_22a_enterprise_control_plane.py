"""Deterministic, fail-closed R10.22A Enterprise Control Plane checks."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "IA_Local" / "scripts"))

from enterprise_ai.security import Principal, create_token
from enterprise_control_plane import ControlPlaneError, EnterpriseControlPlane
from enterprise_platform_config import PlatformConfigError
from enterprise_sql_gateway import EnterpriseSqlError, validate_query_plan
from enterprise_tenant_registry import EnterpriseTenantRegistry


def expect(name, code, call, error_type=ControlPlaneError):
    try:
        call()
    except error_type as exc:
        assert exc.code == code, (name, exc.code)
        print("PASS", name)
        return
    raise AssertionError(name)


def release(root, payload=None):
    (root / "RELEASE_METADATA.json").write_text(json.dumps(payload or {
        "schema_version": 1, "product": "IA_EMPRESARIAL_LOCAL", "product_version": "8.5.5", "release": "r10.21f", "channel": "stable"}), encoding="utf-8")


with tempfile.TemporaryDirectory() as tmp:
    product = Path(tmp) / "product"; runtime = product / "IA_Local"; runtime.mkdir(parents=True)
    plane = EnterpriseControlPlane(runtime)
    assert plane.tenants.root == runtime / "workspace" / "Reportes" / ".tenants"
    assert not (runtime / "Reportes").exists()
    print("PASS workspace_reportes_authority")
    external_tenants = EnterpriseTenantRegistry(runtime / "workspace" / "Reportes" / ".tenants")
    external_tenants.create(tenant_id="alpha", name="Alpha")
    assert plane.tenants.get("alpha")["name"] == "Alpha"
    print("PASS existing_authority_data_visible")
    plane.tenants.create(tenant_id="bravo", name="Bravo")
    admin = plane.identity.bootstrap_admin(user_id="admin", username="admin", display_name="Admin", password="PasswordSeguro12", tenant_id="alpha")
    tenant_admin = plane.identity.create_user(user_id="tenantadmin", username="tenantadmin", display_name="Tenant Admin", password="PasswordSeguro12", tenant_id="alpha", roles=["TENANT_ADMIN"])
    viewer = plane.identity.create_user(user_id="viewer", username="viewer", display_name="Viewer", password="PasswordSeguro12", tenant_id="alpha", roles=["VIEWER"])
    foreign = plane.identity.create_user(user_id="foreign", username="foreign", display_name="Foreign", password="PasswordSeguro12", tenant_id="bravo", roles=["TENANT_ADMIN"])
    admin_p = Principal(company_id="alpha", user_id=admin["user_id"], role="admin")
    tenant_p = Principal(company_id="alpha", user_id=tenant_admin["user_id"], role="user")
    viewer_p = Principal(company_id="alpha", user_id=viewer["user_id"], role="user")

    expect("release_metadata_missing", "CONTROL_PLANE_RELEASE_METADATA_MISSING", lambda: plane.overview(admin_p))
    release(product, {"schema_version": 1, "product": "bad", "product_version": "8.5.5", "release": "r", "channel": "stable"})
    expect("release_metadata_invalid", "CONTROL_PLANE_RELEASE_METADATA_INVALID", lambda: plane.overview(admin_p))
    release(product); assert plane._release()["release"] == "r10.21f"
    print("PASS release_metadata_valid")

    plane.platform.update_global({"ai_provider": {"provider_type": "OLLAMA", "base_url": "http://localhost:11434", "model": "global-model", "timeout": 30}})
    assert plane.ai_for(tenant_p)["model"] == "global-model"
    print("PASS provider_global_effective")
    plane.platform.update_tenant("alpha", {"ai_provider": {"provider_type": "OPENAI_COMPATIBLE_LOCAL", "base_url": "http://127.0.0.1:1234/v1", "model": "tenant-model", "timeout": 30}})
    assert plane.ai_for(tenant_p)["model"] == "tenant-model"
    print("PASS provider_tenant_effective")
    plane.platform.update_tenant("alpha", {"ai_provider": {"provider_type": "DISABLED"}})
    assert plane.ai_for(tenant_p)["provider_type"] == "DISABLED"
    print("PASS ai_disabled_valid")
    expect("provider_local_invalid_blocked", "AI_PROVIDER_INVALID", lambda: plane.platform.update_tenant("alpha", {"ai_provider": {"provider_type": "OLLAMA", "base_url": "https://remote", "model": "x"}}), PlatformConfigError)

    source_a = plane.sql.register(scope=plane.identity.scope(tenant_admin), connection_id="source_a", server="server-a", database="database-a", auth_mode="WINDOWS_INTEGRATED", allowed_schemas=["dbo"], allowed_tables=["dbo.TableA"])
    plane.sql.register(scope=plane.identity.scope(foreign), connection_id="source_b", server="server-b", database="database-b", auth_mode="WINDOWS_INTEGRATED", allowed_schemas=["dbo"], allowed_tables=["dbo.TableB"])
    assert [x["connection_id"] for x in plane.sql_sources_for(tenant_p)] == ["source_a"]
    print("PASS cross_tenant_sql_store_isolation")
    expect("sql_write_blocked", "SQL_QUERY_NOT_READ_ONLY", lambda: validate_query_plan(source_a, {"operation": "DELETE", "sql": "DELETE FROM dbo.TableA"}), EnterpriseSqlError)
    expect("sql_auth_missing_reference_blocked", "SQL_SECRET_UNAVAILABLE", lambda: plane.sql.register(scope=plane.identity.scope(tenant_admin), connection_id="bad_auth", server="server", database="db", auth_mode="SQL_AUTH", allowed_schemas=["dbo"], allowed_tables=["dbo.TableA"]), EnterpriseSqlError)

    overview = plane.overview(tenant_p, health={"live": True})
    assert overview["active_tenant"]["tenant_id"] == "alpha" and overview["sql"]["sources"][0]["read_only"] is True
    forbidden = {"password", "password_hash", "secret_reference", "credential_ref", "token", "token_fingerprint"}
    assert not any(field in json.dumps(overview).lower() for field in forbidden)
    print("PASS secret_safe_public_serialization")
    expect("viewer_without_permission_blocked", "CONTROL_PLANE_PERMISSION_DENIED", lambda: plane.overview(viewer_p))
    assert [x["tenant_id"] for x in plane.tenants_for(tenant_p)] == ["alpha"]
    assert {x["tenant_id"] for x in plane.users_for(tenant_p)} == {"alpha"}
    print("PASS tenant_admin_isolation")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import enterprise_ai.api as enterprise_api
    class Config:
        root = runtime
        def section(self, name): return {"token_secret_file": str(runtime / "config" / "control.secret")} if name == "security" else {}
    original = enterprise_api.build_components
    enterprise_api.build_components = lambda _root: SimpleNamespace(cfg=Config(), llm=SimpleNamespace(healthy=lambda: False), vectors=object())
    try:
        app = FastAPI(); enterprise_api.install_enterprise_routes(app, runtime); client = TestClient(app)
        secret = (runtime / "config" / "control.secret").read_text(encoding="utf-8").encode()
        admin_token = create_token(secret, admin_p); viewer_token = create_token(secret, viewer_p)
        for endpoint in ("overview", "tenants", "users", "sql-sources", "ai"):
            path = "/api/enterprise/control-plane/" + endpoint
            assert client.get(path).status_code == 401, endpoint
            assert client.get(path, headers={"Authorization": "Bearer " + viewer_token}).status_code == 403, endpoint
            assert client.get(path, headers={"Authorization": "Bearer " + admin_token}).status_code == 200, endpoint
        print("PASS all_control_plane_endpoints_authorized")
    finally:
        enterprise_api.build_components = original

    html = enterprise_api.UNIFIED_ADMIN_HTML.lower()
    assert "control-plane/overview" in html and "secret_reference" not in html and "password_hash" not in html and "credential_ref" not in html
    print("PASS admin_ui_secret_safe")
print("PASS R10.22A")
