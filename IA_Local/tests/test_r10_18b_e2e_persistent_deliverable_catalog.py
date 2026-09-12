from pathlib import Path
import os
import sys
import tempfile

import pandas as pd
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import analizador_universal as analyzer
from enterprise_deliverable_registry import GovernedDeliverableRegistry


# GA.5 authenticated migration fixture.
#
# These historical tests intentionally keep their original local scope
# semantics while exercising the now-authenticated HTTP/API contract.
_GA5_HISTORICAL_TOKEN = "ga5-historical-analyst"


class _Ga5HistoricalIdentity:
    def __init__(self):
        self.actor = {
            "user_id": "admin-local",
            "username": "admin-local",
            "tenant_id": "empresa-local",
            "roles": ["ANALYST"],
            "business_units": [],
            "branches": [],
        }

        self.permissions = {
            "analysis:run",
            "deliverable:read",
            "knowledge:read",
            "knowledge:write",
            "sql:read",
            "config:read",
        }

    def authenticate(self, token):
        if str(token or "") != _GA5_HISTORICAL_TOKEN:
            raise RuntimeError(
                "INVALID_GA5_HISTORICAL_TOKEN"
            )

        return dict(
            self.actor
        )

    def has_permission(
        self,
        actor,
        permission,
    ):
        return (
            str(permission)
            in self.permissions
        )

    def scope(self, actor):
        return {
            "company_id":
                str(
                    actor["tenant_id"]
                ),
            "user_id":
                str(
                    actor["user_id"]
                ),
            "business_unit":
                None,
            "branch":
                None,
        }


_GA5_IDENTITY = _Ga5HistoricalIdentity()

HISTORICAL_AUTHORIZATION = (
    "Bearer "
    + _GA5_HISTORICAL_TOKEN
)

HISTORICAL_HEADERS = {
    "Authorization":
        HISTORICAL_AUTHORIZATION
}

analyzer._identity_store = (
    lambda:
        _GA5_IDENTITY
)


def check(name, condition):
    if not condition:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)


prompt = """Genera dashboard HTML, reporte PDF y archivo Excel analítico.
Incluye ventas, costo, utilidad y flete.
No calcules flete sin una regla aprobada. Incluye trazabilidad y capacidades bloqueadas."""

print("\n=== R10.18B E2E PERSISTENT DELIVERABLE CATALOG ===")
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    source = root / "ventas.csv"
    pd.DataFrame([
        {"Fecha":"2026-01-10", "Cliente":"A", "Articulo":"P1", "Importe_Venta":1000, "Costo":800, "Toneladas_Vendidas":10, "Costo_Flete_Corto":10, "Costo_Flete_Largo":20, "Costo_Flete_Traspaso":5},
        {"Fecha":"2026-02-10", "Cliente":"B", "Articulo":"P2", "Importe_Venta":2400, "Costo":1800, "Toneladas_Vendidas":20, "Costo_Flete_Corto":20, "Costo_Flete_Largo":30, "Costo_Flete_Traspaso":10},
    ]).to_csv(source, index=False)
    reports = root / "Reportes"
    reports.mkdir()
    old_reports = analyzer.base.REPORTES
    old_workspace = analyzer.base.WORKSPACE
    old_llm = os.environ.get("IA_DYNAMIC_DASHBOARD_LLM")
    analyzer.base.REPORTES = reports
    analyzer.base.WORKSPACE = root
    os.environ["IA_DYNAMIC_DASHBOARD_LLM"] = "0"
    try:
        result = analyzer.analyze_file(source, prompt)
        run = result["deliverable_run"]
        check("analysis_ok", result["ok"] is True)
        check("run_registered", run["schema_version"] == "r10.18b" and run["status"] == "READY")
        check("three_formats", {item["format"] for item in run["deliverables"]} == {"html", "excel", "pdf"})
        check("manifest_chain", len(run["manifest_fingerprint_sha256"]) == 64)
        restarted = GovernedDeliverableRegistry(reports)
        loaded = restarted.get(analyzer._local_deliverable_scope(), run["run_id"])
        check("restart_recovery", loaded["record_fingerprint_sha256"] == run["record_fingerprint_sha256"])
        check("artifacts_verified", all(restarted.artifact_path(analyzer._local_deliverable_scope(), run["run_id"], item["format"]).is_file() for item in run["deliverables"]))
        catalog = analyzer.list_governed_deliverables(authorization=HISTORICAL_AUTHORIZATION)
        check("catalog_api", catalog["registry"]["run_count"] == 1 and catalog["items"][0]["run_id"] == run["run_id"])
        detail = analyzer.get_governed_deliverable(run["run_id"], authorization=HISTORICAL_AUTHORIZATION)
        check("detail_api", detail["run_id"] == run["run_id"])
        with TestClient(analyzer.app) as client:
            http_catalog = client.get("/api/deliverables", headers=HISTORICAL_HEADERS)
            check("http_catalog", http_catalog.status_code == 200 and http_catalog.json()["items"][0]["run_id"] == run["run_id"])
            http_detail = client.get(f"/api/deliverables/{run['run_id']}", headers=HISTORICAL_HEADERS)
            check("http_detail", http_detail.status_code == 200 and http_detail.json()["record_fingerprint_sha256"] == run["record_fingerprint_sha256"])
            http_download = client.get(f"/api/deliverables/{run['run_id']}/download/html", headers=HISTORICAL_HEADERS)
            check("http_download", http_download.status_code == 200 and b"const DATA=" in http_download.content)
        other_scope = {"company_id":"otra-empresa", "user_id":"admin-local", "business_unit":None, "branch":None}
        check("cross_company_empty", restarted.list(other_scope) == [])
        html = (reports / result["html"]).read_text(encoding="utf-8", errors="replace")
        check("freight_still_blocked", '"id":"kpi:freight"' in html and '"status":"BLOCKED"' in html)
    finally:
        analyzer.base.REPORTES = old_reports
        analyzer.base.WORKSPACE = old_workspace
        if old_llm is None:
            os.environ.pop("IA_DYNAMIC_DASHBOARD_LLM", None)
        else:
            os.environ["IA_DYNAMIC_DASHBOARD_LLM"] = old_llm

print("PASS R10.18B E2E PERSISTENT DELIVERABLE CATALOG")
