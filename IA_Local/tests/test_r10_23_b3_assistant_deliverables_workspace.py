"""R10.23-B.3: governed deliverables remain tenant-scoped and downloadable."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"
sys.path.insert(0, str(SCRIPTS))

SOURCE = (SCRIPTS / "enterprise_ai" / "api.py").read_text(encoding="utf-8")
ASSISTANT = SOURCE.split('ASSISTANT_HTML = r"""', 1)[1].split('"""\n\n\nADMIN_HTML', 1)[0]


def check(name: str, condition: bool) -> None:
    assert condition, name
    print("PASS", name)


def governed_manifest() -> dict:
    from enterprise_deliverable_manifest import build_governed_deliverable_manifest

    return build_governed_deliverable_manifest(
        dashboard_plan={"execution_plan": {"dashboard_spec": {"schema_version": "fixture", "components": []}}},
        filename="ventas.csv",
        prompt_sha256="a" * 64,
        output_intent={"schema_version": "fixture", "outputs": {"html": True, "pdf": True, "excel": True}},
    )


check("ASSISTANT_DELIVERABLE_PANEL_VISIBLE", 'id="deliverableList"' in ASSISTANT and "Deliverables / Reportes" in ASSISTANT)
check("DOWNLOAD_USES_AUTH_HEADER", "protectedFetch('/api/deliverables/" in ASSISTANT)
check("DOWNLOAD_TOKEN_IN_URL_ABSENT", "?token=" not in ASSISTANT and "location.hash" not in ASSISTANT and "Bearer" not in ASSISTANT.split("downloadDeliverable", 1)[1].split("async function establishSession", 1)[0])
check("SESSION_STORAGE_ONLY", "sessionStorage" in ASSISTANT and "localStorage" not in ASSISTANT)
check("DOWNLOAD_BLOB_CLEANUP", "URL.createObjectURL(blob)" in ASSISTANT and "URL.revokeObjectURL(url)" in ASSISTANT)
check("NO_INNERHTML_FOR_DELIVERABLE_CONTENT", "function renderDeliverables" in ASSISTANT and "innerHTML" not in ASSISTANT.split("function renderDeliverables", 1)[1].split("async function refreshDeliverables", 1)[0])
check("LIST_401_RETURNS_LOGIN", "if(response.status===401){handleUnauthorized();return null}" in ASSISTANT)
check("DOWNLOAD_403_PRESERVES_SESSION", "Acceso denegado para descargar el reporte." in ASSISTANT and "showLogin" not in ASSISTANT.split("async function downloadDeliverable", 1)[1].split("async function establishSession", 1)[0])

with tempfile.TemporaryDirectory() as tmp:
    product = Path(tmp) / "product"
    runtime = product / "IA_Local"
    runtime.mkdir(parents=True)
    (product / "RELEASE_METADATA.json").write_text(json.dumps({"schema_version": 1, "product": "IA_EMPRESARIAL_LOCAL", "product_version": "8.5.5", "release": "r10.22f", "channel": "stable"}), encoding="utf-8")
    os.environ["IA_LOCAL_ROOT"] = str(runtime)

    import analizador_universal as analyzer
    from enterprise_deliverable_registry import GovernedDeliverableRegistry
    from enterprise_identity import PERMISSIONS
    from fastapi.testclient import TestClient

    tenants = analyzer._tenant_registry()
    tenants.create(tenant_id="tenant-a", name="Tenant A")
    tenants.create(tenant_id="tenant-b", name="Tenant B")
    identities = analyzer._identity_store()
    identities.bootstrap_admin(user_id="writer-a", username="writer-a", display_name="Writer A", password="WriterPassword!1", tenant_id="tenant-a")
    identities.create_user(user_id="reader-a", username="reader-a", display_name="Reader A", password="ReaderPassword!1", tenant_id="tenant-a", roles=["VIEWER"])
    identities.create_user(user_id="writer-b", username="writer-b", display_name="Writer B", password="WriterPassword!1", tenant_id="tenant-b", roles=["TENANT_ADMIN"])

    reports = runtime / "workspace" / "Reportes"
    html = reports / "ventas.html"
    pdf = reports / "ventas.pdf"
    xlsx = reports / "ventas.xlsx"
    html.write_text("<h1>Ventas</h1>", encoding="utf-8")
    pdf.write_bytes(b"%PDF-1.4\nfixture\n")
    pd.DataFrame({"ventas": [10]}).to_excel(xlsx, index=False)

    with TestClient(analyzer.app) as client:
        login_a = client.post("/api/auth/login", json={"username": "writer-a", "password": "WriterPassword!1"})
        check("LOGIN_TENANT_A", login_a.status_code == 200)
        token_a = login_a.json()["token"]
        headers_a = {"Authorization": "Bearer " + token_a}
        actor_a = identities.authenticate(token_a)
        scope_a = identities.scope(actor_a)
        record = GovernedDeliverableRegistry(reports, tenant_registry=tenants).register(
            scope=scope_a,
            run_id="ventas-a",
            manifest=governed_manifest(),
            outputs={"html": html.name, "pdf": pdf.name, "excel": xlsx.name},
            domain="fixture",
        )
        check("DELIVERABLE_FIXTURE_GOVERNED", record["status"] == "READY" and len(record["deliverables"]) == 3)

        empty_scope = identities.scope(identities.authenticate(client.post("/api/auth/login", json={"username": "writer-b", "password": "WriterPassword!1"}).json()["token"]))
        check("DELIVERABLE_EMPTY_STATE", GovernedDeliverableRegistry(reports, tenant_registry=tenants).list(empty_scope) == [])

        listing_a = client.get("/api/deliverables", headers=headers_a)
        check("DELIVERABLE_LIST_AUTHORIZED", listing_a.status_code == 200)
        items_a = listing_a.json()["items"]
        check("CURRENT_TENANT_DELIVERABLE_VISIBLE", [item["run_id"] for item in items_a] == ["ventas-a"])
        check("ONLY_DECLARED_FORMATS_VISIBLE", {item["format"] for item in items_a[0]["deliverables"]} == {"html", "pdf", "excel"})
        check("NO_LOCAL_PATH_DISCLOSURE", str(reports).lower() not in json.dumps(listing_a.json()).lower())

        detail_a = client.get("/api/deliverables/ventas-a", headers=headers_a)
        check("DELIVERABLE_DETAIL_AUTHORIZED", detail_a.status_code == 200 and detail_a.json()["record_fingerprint_sha256"] == record["record_fingerprint_sha256"])
        for kind, expected in (("html", html.read_bytes()), ("pdf", pdf.read_bytes()), ("excel", xlsx.read_bytes())):
            download = client.get(f"/api/deliverables/ventas-a/download/{kind}", headers=headers_a)
            check(f"{kind.upper()}_DOWNLOAD_AUTHORIZED", download.status_code == 200 and download.content == expected)
            check(f"{kind.upper()}_DOWNLOAD_CONTENT_TYPE", bool(download.headers.get("content-type")))
        check("DOWNLOAD_BYTES_NONEMPTY", all(client.get(f"/api/deliverables/ventas-a/download/{kind}", headers=headers_a).content for kind in ("html", "pdf", "excel")))
        missing = client.get("/api/deliverables/ventas-a/download/nope", headers=headers_a)
        check("INVALID_OR_MISSING_ARTIFACT_NOT_DOWNLOADABLE", missing.status_code == 404)

        login_b = client.post("/api/auth/login", json={"username": "writer-b", "password": "WriterPassword!1"})
        headers_b = {"Authorization": "Bearer " + login_b.json()["token"]}
        listing_b = client.get("/api/deliverables", headers=headers_b)
        check("CROSS_TENANT_DELIVERABLE_HIDDEN", listing_b.status_code == 200 and listing_b.json()["items"] == [])
        detail_b = client.get("/api/deliverables/ventas-a", headers=headers_b)
        download_b = client.get("/api/deliverables/ventas-a/download/html", headers=headers_b)
        check("CROSS_TENANT_DETAIL_BLOCKED", detail_b.status_code == 404)
        check("CROSS_TENANT_DOWNLOAD_BLOCKED", download_b.status_code == 404)

        check("LIST_401_REAL", client.get("/api/deliverables").status_code == 401)
        check("DOWNLOAD_401_REAL", client.get("/api/deliverables/ventas-a/download/html").status_code == 401)
        original_viewer_permissions = set(PERMISSIONS["VIEWER"])
        try:
            PERMISSIONS["VIEWER"] = original_viewer_permissions - {"deliverable:read"}
            token_reader = client.post("/api/auth/login", json={"username": "reader-a", "password": "ReaderPassword!1"}).json()["token"]
            headers_reader = {"Authorization": "Bearer " + token_reader}
            check("LIST_403_REAL", client.get("/api/deliverables", headers=headers_reader).status_code == 403)
            check("DOWNLOAD_403_REAL", client.get("/api/deliverables/ventas-a/download/html", headers=headers_reader).status_code == 403)
        finally:
            PERMISSIONS["VIEWER"] = original_viewer_permissions

    analyzer.ENTERPRISE_COMPONENTS.vectors.close()

print("PASS DELIVERABLE_WORKSPACE_WITHOUT_LLM")
print("PASS R10.23-B.3")
