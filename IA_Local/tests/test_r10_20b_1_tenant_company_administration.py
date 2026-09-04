from pathlib import Path
import json
import sys
import tempfile

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import analizador_universal as analyzer
from enterprise_deliverable_registry import normalize_deliverable_scope
from enterprise_knowledge_store import EnterpriseKnowledgeStore, EnterpriseKnowledgeError
from enterprise_sql_gateway import EnterpriseSqlConnectionStore, EnterpriseSqlError
from enterprise_tenant_registry import EnterpriseTenantRegistry, TenantRegistryError, assert_tenant_active


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print("PASS", name)


def expect(code, fn):
    try:
        fn()
    except TenantRegistryError as exc:
        check(code, exc.code == code)
        return
    raise AssertionError(code)


def scope(company):
    return {"company_id": company, "user_id": "admin-local", "business_unit": "unidad-a", "branch": "norte"}


print("=== R10.20B.1 TENANT COMPANY ADMINISTRATION ===")
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    registry = EnterpriseTenantRegistry(root / "tenants")
    construction = registry.create(tenant_id="constructora-norte", name="Constructora Norte", settings={"locale": "es-MX", "default_theme": "professional-light"}, default_business_unit="obra", default_branch="norte")
    services = registry.create(tenant_id="servicios-centro", name="Servicios Centro", settings={"enabled_features": ["knowledge"]})
    logistics = registry.create(tenant_id="logistica-sur", name="Logística Sur", settings={"timezone": "America/Chihuahua"})
    check("create", construction["status"] == "ACTIVE" and construction["tenant_id"] == "constructora-norte")
    expect("TENANT_ALREADY_EXISTS", lambda: registry.create(tenant_id="constructora-norte", name="Duplicado"))
    check("get_list", registry.get("constructora-norte")["name"] == "Constructora Norte" and len(registry.list()) == 3)
    updated = registry.update("servicios-centro", name="Servicios Centro UTF-8 ñ", settings={"locale": "es-MX", "enabled_features": ["deliverables"]}, default_business_unit="operacion", default_branch="centro")
    check("update", updated["name"].endswith("ñ") and updated["settings"]["enabled_features"] == ["deliverables"] and updated["default_branch"] == "centro")
    disabled = registry.disable("logistica-sur")
    check("disable", disabled["status"] == "DISABLED")
    expect("TENANT_DISABLED", lambda: registry.assert_active("logistica-sur"))
    check("enable", registry.enable("logistica-sur")["status"] == "ACTIVE" and registry.assert_active("logistica-sur")["tenant_id"] == "logistica-sur")
    check("scope_active", assert_tenant_active(scope("constructora-norte"), registry)["company_id"] == "constructora-norte")
    check("legacy_scope", assert_tenant_active(scope("legacy-company"))["company_id"] == "legacy-company")
    check("persistence", EnterpriseTenantRegistry(root / "tenants").get("servicios-centro")["name"].endswith("ñ"))
    raw_path = root / "tenants" / "tenants.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8")); raw["records"][0]["name"] = "Manipulado"; raw_path.write_text(json.dumps(raw), encoding="utf-8")
    expect("TENANT_INTEGRITY_MISMATCH", lambda: EnterpriseTenantRegistry(root / "tenants").list())

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    strict_registry = EnterpriseTenantRegistry(root / "tenants")
    strict_registry.create(tenant_id="constructora-norte", name="Constructora")
    strict_registry.create(tenant_id="servicios-centro", name="Servicios")
    strict_registry.disable("servicios-centro")
    knowledge = EnterpriseKnowledgeStore(root / "knowledge", tenant_registry=strict_registry)
    tenant_a, tenant_b = scope("constructora-norte"), scope("servicios-centro")
    knowledge.register_knowledge(scope=tenant_a, knowledge_id="definition-a", knowledge_type="definition", title="Progreso", content="Contenido A", source={"source": "fixture"}, provenance={"origin": "test"})
    check("knowledge_isolation", len(knowledge.list(tenant_a)) == 1)
    try:
        knowledge.get(tenant_b, "definition-a")
    except TenantRegistryError as exc:
        check("knowledge_b_blocked", exc.code == "TENANT_DISABLED")
    sql = EnterpriseSqlConnectionStore(root / "sql", tenant_registry=strict_registry)
    sql.register(scope=tenant_a, connection_id="profile-a", server="server", database="db", auth_mode="integrated", credential_ref="env:TEST", allowed_schemas=["dbo"], allowed_tables=["dbo.Table"])
    check("sql_isolation", len(sql.list(tenant_a)) == 1)
    try:
        sql.get(tenant_b, "profile-a")
    except TenantRegistryError as exc:
        check("sql_b_blocked", exc.code == "TENANT_DISABLED")
    check("scope_preserved", normalize_deliverable_scope(tenant_a)["business_unit"] == "unidad-a" and normalize_deliverable_scope(tenant_a)["branch"] == "norte")

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    old_reports = analyzer.base.REPORTES
    analyzer.base.REPORTES = root / "reports"
    analyzer.configure_tenant_admin_guard(lambda: False)
    try:
        with TestClient(analyzer.app) as client:
            check("admin_guard", client.get("/api/admin/tenants").status_code == 403)
            analyzer.configure_tenant_admin_guard(lambda: True)
            created = client.post("/api/admin/tenants", json={"tenant_id": "servicios-api", "name": "Servicios API", "settings": {"locale": "es-MX"}})
            check("api_create", created.status_code == 200 and created.json()["tenant_id"] == "servicios-api")
            check("api_list", len(client.get("/api/admin/tenants").json()["tenants"]) == 1)
            check("api_get", client.get("/api/admin/tenants/servicios-api").status_code == 200)
            changed = client.patch("/api/admin/tenants/servicios-api", json={"name": "Servicios API ñ"})
            check("api_update", changed.status_code == 200 and changed.json()["name"].endswith("ñ"))
            check("api_disable", client.post("/api/admin/tenants/servicios-api/disable").json()["status"] == "DISABLED")
            check("api_enable", client.post("/api/admin/tenants/servicios-api/enable").json()["status"] == "ACTIVE")
            duplicate = client.post("/api/admin/tenants", json={"tenant_id": "servicios-api", "name": "x"})
            check("api_error_contract", duplicate.status_code == 409 and duplicate.json()["detail"]["code"] == "TENANT_ALREADY_EXISTS")
    finally:
        analyzer.configure_tenant_admin_guard(lambda: False)
        analyzer.base.REPORTES = old_reports

print("PASS R10.20B.1 TENANT COMPANY ADMINISTRATION")
