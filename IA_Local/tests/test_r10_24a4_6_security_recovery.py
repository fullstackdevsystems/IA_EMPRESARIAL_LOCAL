"""R10.24A4.6: commercial backup/recovery facade uses governed engine safely."""
from __future__ import annotations

import ast
import secrets
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from enterprise_identity import EnterpriseIdentityStore
from enterprise_tenant_registry import EnterpriseTenantRegistry
import enterprise_ai.api as enterprise_api


def check(name, value):
    assert value, name
    print("PASS", name)


api = (SCRIPTS / "enterprise_ai" / "api.py").read_text(encoding="utf-8")
ui = (SCRIPTS / "enterprise_ai" / "product_settings_ui.py").read_text(encoding="utf-8")
ast.parse(api); ast.parse(ui)
for text in ["Seguridad y recuperación", "Crear respaldo", "Recuperar respaldo", "Confirmo que deseo recuperar este respaldo"]:
    check("ui:" + text, text in ui)
for route in ["/api/enterprise/security-recovery", "/api/enterprise/security-recovery/backup", "/api/enterprise/security-recovery/restore"]:
    check("route:" + route, route in api)
recovery_markup = ui.split('<section id="recoveryPanel"', 1)[1].split('</section>', 1)[0]
for forbidden in ["secret_reference", "credential_ref", "password", "SHA-256"]:
    check("ui_hides:" + forbidden, forbidden not in recovery_markup)

with tempfile.TemporaryDirectory(prefix="r1024_a46_") as temporary:
    runtime = Path(temporary) / "IA_Local"; reports = runtime / "workspace" / "Reportes"; runtime.mkdir(parents=True)
    tenants = EnterpriseTenantRegistry(reports / ".tenants")
    tenants.create(tenant_id="alpha", name="Alpha")
    identity = EnterpriseIdentityStore(reports / ".identity", tenants)
    password = secrets.token_urlsafe(24)
    identity.bootstrap_admin(user_id="system", username="system", display_name="System", password=password, tenant_id="alpha")
    marker = reports / "recovery-marker.txt"; marker.write_text("original", encoding="utf-8")
    class Config:
        root = runtime
        def section(self, _name): return {}
    components = SimpleNamespace(cfg=Config(), llm=SimpleNamespace(healthy=lambda: False), vectors=SimpleNamespace(close=lambda: None), db=SimpleNamespace(audit=lambda *args, **kwargs: None), service=SimpleNamespace(connected_sql_resolver=None))
    original = enterprise_api.build_components; enterprise_api.build_components = lambda _root: components
    try:
        app = FastAPI(); enterprise_api.install_enterprise_routes(app, runtime)
        token, _ = identity.login("system", password); headers = {"Authorization": "Bearer " + token}
        with TestClient(app) as client:
            check("missing_session_401", client.get("/api/enterprise/security-recovery").status_code == 401)
            state = client.get("/api/enterprise/security-recovery", headers=headers)
            check("system_admin_capabilities", state.status_code == 200 and state.json()["backup_available"] and state.json()["recovery_available"])
            downloaded = client.post("/api/enterprise/security-recovery/backup", headers=headers)
            check("governed_backup_download", downloaded.status_code == 200 and downloaded.content.startswith(b"PK"))
            archive = downloaded.content
            marker.write_text("changed", encoding="utf-8")
            rejected = client.post("/api/enterprise/security-recovery/restore", headers=headers, files={"archive": ("backup.zip", archive, "application/zip")})
            check("restore_requires_confirmation", rejected.status_code == 400 and marker.read_text(encoding="utf-8") == "changed")
            restored = client.post("/api/enterprise/security-recovery/restore?confirmed=true", headers=headers, files={"archive": ("backup.zip", archive, "application/zip")})
            check("confirmed_restore", restored.status_code == 200 and restored.json()["ok"])
        check("restore_persists_original_state", marker.read_text(encoding="utf-8") == "original")
    finally:
        enterprise_api.build_components = original

print("R10_24A4_6_SECURITY_RECOVERY=PASS")

# A4.6 regression: extensionless runtime lock files must never enter backups.
from pathlib import Path as _A46Path
from enterprise_backup_recovery import _is_volatile as _a46_is_volatile
assert _a46_is_volatile(_A46Path(".lock")) is True
print("PASS qdrant_dot_lock_excluded")
