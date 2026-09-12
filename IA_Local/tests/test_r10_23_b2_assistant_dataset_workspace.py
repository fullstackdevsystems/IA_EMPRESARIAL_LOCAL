"""R10.23-B.2: assistant workspace reuses governed documents and datasets."""
import io
import json
import logging
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


def check(name, condition):
    assert condition, name
    print("PASS", name)


check("assistant_source_picker_visible", 'id="workspace"' in ASSISTANT and 'id="sourceFile"' in ASSISTANT)
check("assistant_upload_excel_csv", "accept=\".csv,.xlsx,.xls,.xlsm,.xlsb" in ASSISTANT and "FormData" in ASSISTANT)
check("source_type_and_status_visible", "DOCUMENT · " in ASSISTANT and "DATASET · " in ASSISTANT and "sourceStatus" in ASSISTANT)
check("protected_source_requests", "protectedFetch('/api/enterprise/documents'" in ASSISTANT and "protectedFetch('/api/enterprise/datasets')" in ASSISTANT)
check("upload_401_uses_global_handler", "if(!response)return" in ASSISTANT and "protectedFetch" in ASSISTANT)
check("no_local_storage_auth", "localStorage" not in ASSISTANT)
check("no_token_in_url", "?token=" not in ASSISTANT and "location.hash" not in ASSISTANT)

with tempfile.TemporaryDirectory() as tmp:
    product = Path(tmp) / "product"; runtime = product / "IA_Local"; runtime.mkdir(parents=True)
    (product / "RELEASE_METADATA.json").write_text(json.dumps({"schema_version": 1, "product": "IA_EMPRESARIAL_LOCAL", "product_version": "8.5.5", "release": "r10.22f", "channel": "stable"}), encoding="utf-8")
    os.environ["IA_LOCAL_ROOT"] = str(runtime)
    import analizador_universal as analyzer
    from enterprise_ai.security import Principal
    from fastapi.testclient import TestClient

    tenants = analyzer._tenant_registry(); tenants.create(tenant_id="tenant-a", name="Tenant A"); tenants.create(tenant_id="tenant-b", name="Tenant B")
    identities = analyzer._identity_store()
    identities.bootstrap_admin(user_id="writer-a", username="writer-a", display_name="Writer A", password="WriterPassword!1", tenant_id="tenant-a")
    identities.create_user(user_id="reader-a", username="reader-a", display_name="Reader A", password="ReaderPassword!1", tenant_id="tenant-a", roles=["VIEWER"])
    identities.create_user(user_id="writer-b", username="writer-b", display_name="Writer B", password="WriterPassword!1", tenant_id="tenant-b", roles=["TENANT_ADMIN"])

    csv = b"producto,ventas\nA,10\nB,20\n"
    workbook = io.BytesIO()
    pd.DataFrame({"producto": ["A"], "ventas": [10]}).to_excel(workbook, index=False)
    with TestClient(analyzer.app) as client:
        login_a = client.post("/api/auth/login", json={"username": "writer-a", "password": "WriterPassword!1"}).json()["token"]
        headers_a = {"Authorization": "Bearer " + login_a}
        check("auth_me_real", client.get("/api/auth/me", headers=headers_a).json()["tenant_id"] == "tenant-a")
        csv_upload = client.post("/api/enterprise/documents", headers=headers_a, files={"file": ("ventas.csv", csv, "text/csv")}, data={"scope": "company"})
        check("csv_upload", csv_upload.status_code == 200 and csv_upload.json()["ok"])
        check("semantic_degraded_state_honest", csv_upload.json()["metadata"].get("semantic_index_available") is False and csv_upload.json()["metadata"].get("semantic_index_degraded") == "provider_unavailable")
        xlsx_upload = client.post("/api/enterprise/documents", headers=headers_a, files={"file": ("ventas.xlsx", workbook.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, data={"scope": "company"})
        check("xlsx_upload", xlsx_upload.status_code == 200 and xlsx_upload.json()["ok"])
        documents = client.get("/api/enterprise/documents", headers=headers_a).json()["documents"]
        datasets = client.get("/api/enterprise/datasets", headers=headers_a).json()["datasets"]
        check("document_created_current_tenant", {item["name"] for item in documents} >= {"ventas.csv", "ventas.xlsx"})
        check("dataset_registered_current_tenant", {item["name"] for item in datasets} >= {"ventas.csv", "ventas.xlsx"})
        check("dataset_list_authorized", all(item["company_id"] == "tenant-a" for item in datasets))
        structured = analyzer.ENTERPRISE_COMPONENTS.datasets.query(Principal("tenant-a", "writer-a", "admin"), "ventas.csv ventas por producto")
        check("structured_query_without_llm", isinstance(structured, dict) and bool(structured))
        reader_token = client.post("/api/auth/login", json={"username": "reader-a", "password": "ReaderPassword!1"}).json()["token"]
        reader_upload = client.post("/api/enterprise/documents", headers={"Authorization": "Bearer " + reader_token}, files={"file": ("denied.csv", csv, "text/csv")}, data={"scope": "company"})
        check("upload_permission_denied_403", reader_upload.status_code == 403)
        login_b = client.post("/api/auth/login", json={"username": "writer-b", "password": "WriterPassword!1"}).json()["token"]
        headers_b = {"Authorization": "Bearer " + login_b}
        documents_b = client.get("/api/enterprise/documents", headers=headers_b).json()["documents"]
        datasets_b = client.get("/api/enterprise/datasets", headers=headers_b).json()["datasets"]
        check("cross_tenant_document_access_blocked", not documents_b)
        check("cross_tenant_dataset_access_blocked", not datasets_b)
        check("protected_assistant_query", client.post("/api/enterprise/chat/stream", headers=headers_a, json={"message": "ventas por producto", "history": []}).status_code == 200)
    analyzer.ENTERPRISE_COMPONENTS.vectors.close(); logging.shutdown()

print("PASS R10.23-B.2")
