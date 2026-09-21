"""R10.24A4.3.1: company-owned governed SQL connection scope."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from enterprise_control_plane import EnterpriseControlPlane
from enterprise_identity import EnterpriseIdentityStore
from enterprise_sql_gateway import EnterpriseSqlConnectionStore, EnterpriseSqlError, _fingerprint
from enterprise_tenant_registry import EnterpriseTenantRegistry


def check(name, condition):
    assert condition, name
    print("PASS", name)


def expect(code, operation):
    try:
        operation()
    except EnterpriseSqlError as exc:
        assert exc.code == code, exc.code
        return
    raise AssertionError(code)


def legacy_record(store, scope, connection_id, *, server="legacy-server", secret_reference="legacy-secret"):
    record = {
        "schema_version": "r10.19c", "connection_id": connection_id,
        "scope": scope, "provider": "sqlserver", "server": server,
        "database": "legacy-db", "auth_mode": "SQL_AUTH",
        "credential_ref": secret_reference, "secret_reference": secret_reference,
        "username": "legacy-reader", "allowed_schemas": ["dbo"],
        "allowed_tables": ["dbo.Orders"], "read_only": True, "enabled": True,
        "status": "ACTIVE", "display_name": "Legacy source",
        "driver": "ODBC Driver 18 for SQL Server", "timeout_seconds": 30,
        "max_rows": 500, "trust_server_certificate": False,
        "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00",
    }
    record["fingerprint_sha256"] = _fingerprint(record)
    directory = store._legacy_dir(scope)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{connection_id}.json").write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    return record


with tempfile.TemporaryDirectory(prefix="r1024_a43_") as temporary:
    runtime = Path(temporary) / "IA_Local"
    reports = runtime / "workspace" / "Reportes"
    reports.mkdir(parents=True)
    (runtime.parent / "RELEASE_METADATA.json").write_text(
        json.dumps({"schema_version": 1, "product": "IA_EMPRESARIAL_LOCAL", "product_version": "8.5.5", "release": "development", "channel": "development"}), encoding="utf-8"
    )
    tenants = EnterpriseTenantRegistry(reports / ".tenants")
    tenants.create(tenant_id="alpha", name="Alpha")
    tenants.create(tenant_id="bravo", name="Bravo")
    identity = EnterpriseIdentityStore(reports / ".identity", tenants)
    admin = identity.bootstrap_admin(user_id="alpha-admin", username="alpha-admin", display_name="Alpha admin", password="AlphaAdminPassword!1", tenant_id="alpha")
    analyst = identity.create_user(user_id="alpha-analyst", username="alpha-analyst", display_name="Alpha analyst", password="AlphaAnalystPassword!1", tenant_id="alpha", roles=["ANALYST"])
    viewer = identity.create_user(user_id="alpha-viewer", username="alpha-viewer", display_name="Alpha viewer", password="AlphaViewerPassword!1", tenant_id="alpha", roles=["VIEWER"])
    bravo = identity.create_user(user_id="bravo-admin", username="bravo-admin", display_name="Bravo admin", password="BravoAdminPassword!1", tenant_id="bravo", roles=["TENANT_ADMIN"])
    store = EnterpriseSqlConnectionStore(reports / ".sql_connections", tenants)

    created = store.register(scope=store.company_scope(identity.scope(admin)), connection_id="sales", server="alpha-server", database="Sales", auth_mode="WINDOWS_INTEGRATED", allowed_schemas=["dbo"], allowed_tables=["dbo.Orders"])
    canonical = {"company_id": "alpha", "user_id": "sql-admin", "business_unit": None, "branch": None}
    check("admin_write_is_company_scope", created["scope"] == canonical)
    check("analyst_same_company_can_list", [item["connection_id"] for item in store.list(store.company_scope(identity.scope(analyst)))] == ["sales"])
    check("viewer_has_no_sql_read", not identity.has_permission(viewer, "sql:read"))
    check("analyst_has_no_sql_configure", not identity.has_permission(analyst, "sql:configure"))
    check("other_company_cannot_list", store.list(store.company_scope(identity.scope(bravo))) == [])
    check("canonical_persists_after_restart", EnterpriseSqlConnectionStore(reports / ".sql_connections", tenants).get(canonical, "sales")["scope"] == canonical)

    legacy_scope = {"company_id": "alpha", "user_id": "former-admin", "business_unit": None, "branch": None}
    legacy_record(store, legacy_scope, "legacy-auth")
    migrated = store.migrate_legacy_scope(legacy_scope)
    check("legacy_migration_preserves_source", migrated["source_preserved"] and store._legacy_dir(legacy_scope).joinpath("legacy-auth.json").is_file())
    migrated_profile = store.get(canonical, "legacy-auth")
    check("legacy_migration_recomputes_scope_and_preserves_secret_reference", migrated_profile["scope"] == canonical and migrated_profile["secret_reference"] == "legacy-secret")
    again = store.migrate_legacy_scope(legacy_scope)
    check("legacy_migration_idempotent", again["migrated"] == [] and again["skipped"] == ["legacy-auth"])

    conflict_scope = {"company_id": "alpha", "user_id": "other-former-admin", "business_unit": None, "branch": None}
    legacy_record(store, conflict_scope, "sales", server="different-server")
    expect("MIGRATION_TARGET_CONFLICT", lambda: store.migrate_legacy_scope(conflict_scope))
    check("conflict_preserves_legacy_source", store._legacy_dir(conflict_scope).joinpath("sales.json").is_file())
    check("conflict_preserves_canonical_target", store.get(canonical, "sales")["server"] == "alpha-server")

    plane = EnterpriseControlPlane(runtime)
    alpha_principal = SimpleNamespace(user_id="alpha-analyst", company_id="alpha")
    bravo_principal = SimpleNamespace(user_id="bravo-admin", company_id="bravo")
    check("control_plane_uses_company_scope", {item["connection_id"] for item in plane.sql_sources_for(alpha_principal)} == {"sales", "legacy-auth"})
    check("control_plane_tenant_isolation", plane.sql_sources_for(bravo_principal) == [])

print("PASS R10.24A4.3 COMPANY SQL SCOPE")
