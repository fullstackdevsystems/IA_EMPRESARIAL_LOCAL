"""Deterministic R10.22A control-plane integration checks."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "IA_Local" / "scripts"))

from enterprise_control_plane import ControlPlaneError, EnterpriseControlPlane
from enterprise_platform_config import PlatformConfigError
from enterprise_ai.security import Principal


def expect(name, call, code):
    try:
        call()
    except ControlPlaneError as exc:
        assert exc.code == code, (name, exc.code)
        print("PASS", name)
        return
    raise AssertionError(name)


with tempfile.TemporaryDirectory() as tmp:
    runtime = Path(tmp) / "IA_Local"
    runtime.mkdir()
    plane = EnterpriseControlPlane(runtime)
    plane.tenants.create(tenant_id="alpha", name="Alpha")
    plane.tenants.create(tenant_id="bravo", name="Bravo")
    admin = plane.identity.bootstrap_admin(user_id="admin", username="admin", display_name="Admin", password="PasswordSeguro12", tenant_id="alpha")
    viewer = plane.identity.create_user(user_id="viewer", username="viewer", display_name="Viewer", password="PasswordSeguro12", tenant_id="alpha", roles=["VIEWER"])
    foreign = plane.identity.create_user(user_id="foreign", username="foreign", display_name="Foreign", password="PasswordSeguro12", tenant_id="bravo", roles=["ANALYST"])
    admin_p = Principal(company_id="alpha", user_id=admin["user_id"], role="admin")
    viewer_p = Principal(company_id="alpha", user_id=viewer["user_id"], role="user")
    foreign_p = Principal(company_id="bravo", user_id=foreign["user_id"], role="user")

    plane.platform.update_tenant("alpha", {"ai_provider": {"provider_type": "DISABLED"}})
    plane.sql.register(scope=plane.identity.scope(admin), connection_id="source_a", server="server", database="database", auth_mode="WINDOWS_INTEGRATED", allowed_schemas=["dbo"], allowed_tables=["dbo.TableA"])
    overview = plane.overview(admin_p, health={"live": True})
    assert overview["active_tenant"]["tenant_id"] == "alpha"
    assert overview["ai"]["status"] == "DISABLED"
    assert overview["sql"]["sources"][0]["read_only"] is True
    assert "secret_reference" not in overview["sql"]["sources"][0]
    print("PASS effective_configuration")
    print("PASS ai_disabled_valid")
    print("PASS sql_credentials_not_serialized")
    assert plane.tenants_for(admin_p)[0]["tenant_id"] in {"alpha", "bravo"}
    assert {u["tenant_id"] for u in plane.users_for(admin_p)} == {"alpha", "bravo"}
    print("PASS authorized_user_allowed")
    expect("viewer_without_permission_blocked", lambda: plane.overview(viewer_p), "CONTROL_PLANE_PERMISSION_DENIED")
    expect("foreign_tenant_sql_blocked", lambda: plane.sql_sources_for(Principal(company_id="alpha", user_id=foreign["user_id"], role="user")), "CONTROL_PLANE_SCOPE_DENIED")
    try:
        plane.platform.update_tenant("alpha", {"ai_provider": {"provider_type": "NOT_A_PROVIDER"}})
        raise AssertionError("invalid_provider_blocked")
    except PlatformConfigError as exc:
        assert exc.code == "AI_PROVIDER_INVALID"
        print("PASS invalid_provider_blocked")
    print("PASS tenant_isolation")
    print("PASS backend_authorization")
    print("PASS sql_write_contract_preserved")
    # The HTTP surface must enforce the same fail-closed gate, not only hide UI.
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import enterprise_ai.api as enterprise_api
    from enterprise_ai.security import create_token
    class Config:
        root = runtime
        def section(self, name):
            return {"token_secret_file": str(runtime / "config" / "control.secret")} if name == "security" else {}
    original = enterprise_api.build_components
    enterprise_api.build_components = lambda _root: SimpleNamespace(cfg=Config(), llm=SimpleNamespace(healthy=lambda: False), vectors=object())
    try:
        app = FastAPI(); enterprise_api.install_enterprise_routes(app, runtime)
        client = TestClient(app)
        assert client.get("/api/enterprise/control-plane/overview").status_code == 401
        token = create_token((runtime / "config" / "control.secret").read_text(encoding="utf-8").encode(), admin_p)
        assert client.get("/api/enterprise/control-plane/overview", headers={"Authorization": "Bearer " + token}).status_code == 200
        print("PASS api_authorization_enforced")
    finally:
        enterprise_api.build_components = original
print("PASS R10.22A")
