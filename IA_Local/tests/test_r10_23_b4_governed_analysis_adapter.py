"""R10.23-B.4: governed analysis adapter for existing datasets."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"
sys.path.insert(0, str(SCRIPTS))

SOURCE = (SCRIPTS / "enterprise_ai" / "api.py").read_text(
    encoding="utf-8"
)
ASSISTANT = SOURCE.split(
    'ASSISTANT_HTML = r"""',
    1,
)[1].split(
    '"""\n\n\nADMIN_HTML',
    1,
)[0]


def check(name: str, condition: bool) -> None:
    assert condition, name
    print("PASS", name)


check(
    "ASSISTANT_GENERATION_ACTION_VISIBLE",
    "Generar reporte" in ASSISTANT
    and 'id="analysisPrompt"' in ASSISTANT,
)
check(
    "ASSISTANT_GENERATION_USES_DATASET_ID",
    "/api/enterprise/datasets/" in ASSISTANT
    and "/analyze" in ASSISTANT
    and "encodeURIComponent(datasetId)" in ASSISTANT,
)
check(
    "ASSISTANT_GENERATION_PROTECTED_FETCH",
    "protectedFetch('/api/enterprise/datasets/" in ASSISTANT,
)
check(
    "NO_CLIENT_FILESYSTEM_PATH",
    "source_path" not in ASSISTANT
    and "stored_path" not in ASSISTANT
    and "C:\\" not in ASSISTANT,
)
check(
    "GENERATION_401_USES_GLOBAL_HANDLER",
    "if(response.status===401){handleUnauthorized();return null}"
    in ASSISTANT,
)

generation_block = ASSISTANT.split(
    "async function generateDatasetReport",
    1,
)[1].split(
    "async function uploadSource",
    1,
)[0]

check(
    "GENERATION_403_PRESERVES_SESSION",
    "Acceso denegado para ejecutar análisis." in generation_block
    and "showLogin" not in generation_block,
)

with tempfile.TemporaryDirectory() as tmp:
    product = Path(tmp) / "product"
    runtime = product / "IA_Local"
    runtime.mkdir(parents=True)

    (product / "RELEASE_METADATA.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product": "IA_EMPRESARIAL_LOCAL",
                "product_version": "8.5.5",
                "release": "r10.22f",
                "channel": "stable",
            }
        ),
        encoding="utf-8",
    )

    os.environ["IA_LOCAL_ROOT"] = str(runtime)

    import analizador_universal as analyzer
    from enterprise_identity import PERMISSIONS
    from fastapi.testclient import TestClient

    tenants = analyzer._tenant_registry()
    tenants.create(
        tenant_id="tenant-a",
        name="Tenant A",
    )
    tenants.create(
        tenant_id="tenant-b",
        name="Tenant B",
    )

    identities = analyzer._identity_store()

    identities.bootstrap_admin(
        user_id="writer-a",
        username="writer-a",
        display_name="Writer A",
        password="WriterPassword!1",
        tenant_id="tenant-a",
    )

    identities.create_user(
        user_id="reader-a",
        username="reader-a",
        display_name="Reader A",
        password="ReaderPassword!1",
        tenant_id="tenant-a",
        roles=["VIEWER"],
    )

    identities.create_user(
        user_id="analyst-a",
        username="analyst-a",
        display_name="Analyst A",
        password="AnalystPassword!1",
        tenant_id="tenant-a",
        roles=["ANALYST"],
    )

    identities.create_user(
        user_id="writer-b",
        username="writer-b",
        display_name="Writer B",
        password="WriterPassword!1",
        tenant_id="tenant-b",
        roles=["TENANT_ADMIN"],
    )

    csv = (
        b"Fecha,Cliente,Producto,Ventas\n"
        b"2026-01-01,Cliente A,Producto A,100\n"
        b"2026-01-02,Cliente B,Producto B,200\n"
        b"2026-02-01,Cliente A,Producto B,150\n"
    )

    with TestClient(analyzer.app) as client:
        token_a = client.post(
            "/api/auth/login",
            json={
                "username": "writer-a",
                "password": "WriterPassword!1",
            },
        ).json()["token"]

        headers_a = {
            "Authorization": "Bearer " + token_a,
        }

        upload = client.post(
            "/api/enterprise/documents",
            headers=headers_a,
            files={
                "file": (
                    "ventas.csv",
                    csv,
                    "text/csv",
                )
            },
            data={"scope": "company"},
        )

        check(
            "SOURCE_UPLOAD",
            upload.status_code == 200
            and upload.json()["ok"],
        )

        documents_response = client.get(
            "/api/enterprise/documents",
            headers=headers_a,
        )

        check(
            "DOCUMENT_LIST_AUTHORIZED",
            documents_response.status_code == 200,
        )

        documents = documents_response.json()["documents"]

        check(
            "DOCUMENT_LOCAL_PATH_NOT_DISCLOSED",
            all(
                "stored_path" not in item
                for item in documents
            ),
        )

        datasets_response = client.get(
            "/api/enterprise/datasets",
            headers=headers_a,
        )

        check(
            "DATASET_LIST_AUTHORIZED",
            datasets_response.status_code == 200,
        )

        datasets_before = datasets_response.json()["datasets"]

        check(
            "DATASET_AVAILABLE",
            len(datasets_before) == 1,
        )

        check(
            "DATASET_LOCAL_PATH_NOT_DISCLOSED",
            all(
                "path" not in item
                for item in datasets_before
            ),
        )

        dataset_id = datasets_before[0]["id"]

        original_ollama_available = analyzer.base.ollama_available
        original_ollama_chat = analyzer.base.ollama_chat

        def forbidden_ollama_chat(*args, **kwargs):
            raise AssertionError(
                "OLLAMA_MUST_NOT_BE_CALLED"
            )

        analyzer.base.ollama_available = lambda: False
        analyzer.base.ollama_chat = forbidden_ollama_chat

        try:
            generated = client.post(
                f"/api/enterprise/datasets/{dataset_id}/analyze",
                headers=headers_a,
                json={
                    "prompt": (
                        "Analiza completamente este archivo y genera "
                        "un dashboard HTML, un reporte ejecutivo PDF "
                        "y un Excel analitico."
                    )
                },
            )
        finally:
            analyzer.base.ollama_available = (
                original_ollama_available
            )
            analyzer.base.ollama_chat = original_ollama_chat

        check(
            "AUTHORIZED_USER_CAN_START_ANALYSIS",
            generated.status_code == 200,
        )

        payload = generated.json()

        check(
            "ANALYSIS_RESULT_OK",
            payload.get("ok") is True,
        )

        check(
            "ANALYSIS_DATASET_ID",
            payload.get("dataset_id") == dataset_id,
        )

        check(
            "ANALYSIS_RUN_CREATED",
            isinstance(
                payload.get("deliverable_run"),
                dict,
            )
            and bool(
                payload["deliverable_run"].get("run_id")
            ),
        )

        check(
            "CORE_DELIVERABLE_GENERATION_WITHOUT_LLM",
            payload.get("ok") is True,
        )

        datasets_after = client.get(
            "/api/enterprise/datasets",
            headers=headers_a,
        ).json()["datasets"]

        before_ids = {
            item["id"]
            for item in datasets_before
        }
        after_ids = {
            item["id"]
            for item in datasets_after
        }

        check(
            "NO_DUPLICATE_DATASET_REGISTRATION",
            len(datasets_after) == len(datasets_before)
            and after_ids == before_ids,
        )

        run_id = payload["deliverable_run"]["run_id"]

        listing = client.get(
            "/api/deliverables",
            headers=headers_a,
        )

        check(
            "DELIVERABLE_LIST_AFTER_GENERATION",
            listing.status_code == 200,
        )

        records = listing.json()["items"]

        check(
            "DELIVERABLE_VISIBLE_IN_B3_PANEL",
            run_id in {
                item["run_id"]
                for item in records
            },
        )

        record = next(
            item
            for item in records
            if item["run_id"] == run_id
        )

        available_formats = {
            item["format"]
            for item in record.get("deliverables", [])
        }

        check(
            "REQUESTED_FORMATS_DECLARED",
            {
                "html",
                "pdf",
                "excel",
            }.issubset(available_formats),
        )

        for kind in ("html", "pdf", "excel"):
            download = client.get(
                f"/api/deliverables/{run_id}/download/{kind}",
                headers=headers_a,
            )

            check(
                f"{kind.upper()}_DOWNLOAD_GENERATED_RESULT",
                download.status_code == 200
                and bool(download.content),
            )

        token_b = client.post(
            "/api/auth/login",
            json={
                "username": "writer-b",
                "password": "WriterPassword!1",
            },
        ).json()["token"]

        headers_b = {
            "Authorization": "Bearer " + token_b,
        }

        cross_tenant = client.post(
            f"/api/enterprise/datasets/{dataset_id}/analyze",
            headers=headers_b,
            json={
                "prompt": "Genera un dashboard HTML.",
            },
        )

        check(
            "CROSS_TENANT_GENERATION_BLOCKED",
            cross_tenant.status_code == 404,
        )

        unauthenticated = client.post(
            f"/api/enterprise/datasets/{dataset_id}/analyze",
            json={
                "prompt": "Genera un dashboard HTML.",
            },
        )

        check(
            "GENERATION_401_REAL",
            unauthenticated.status_code == 401,
        )

        original_viewer_permissions = set(
            PERMISSIONS["VIEWER"]
        )

        try:
            PERMISSIONS["VIEWER"] = (
                original_viewer_permissions
                - {"analysis:run"}
            )

            reader_token = client.post(
                "/api/auth/login",
                json={
                    "username": "reader-a",
                    "password": "ReaderPassword!1",
                },
            ).json()["token"]

            reader_response = client.post(
                f"/api/enterprise/datasets/{dataset_id}/analyze",
                headers={
                    "Authorization": "Bearer " + reader_token
                },
                json={
                    "prompt": "Genera un dashboard HTML.",
                },
            )

            check(
                "GENERATION_ANALYSIS_PERMISSION_DENIED_403",
                reader_response.status_code == 403,
            )
        finally:
            PERMISSIONS["VIEWER"] = (
                original_viewer_permissions
            )

        original_analyst_permissions = set(
            PERMISSIONS["ANALYST"]
        )

        try:
            PERMISSIONS["ANALYST"] = (
                original_analyst_permissions
                - {"deliverable:read"}
            )

            check(
                "ANALYST_RETAINS_ANALYSIS_RUN",
                "analysis:run" in PERMISSIONS["ANALYST"],
            )

            analyst_token = client.post(
                "/api/auth/login",
                json={
                    "username": "analyst-a",
                    "password": "AnalystPassword!1",
                },
            ).json()["token"]

            dataset_read_denied = client.post(
                f"/api/enterprise/datasets/{dataset_id}/analyze",
                headers={
                    "Authorization": "Bearer " + analyst_token
                },
                json={
                    "prompt": "Genera un dashboard HTML.",
                },
            )

            check(
                "GENERATION_DATASET_READ_PERMISSION_DENIED_403",
                dataset_read_denied.status_code == 403,
            )

            denial_detail = (
                dataset_read_denied.json().get("detail") or {}
            )

            check(
                "GENERATION_DATASET_READ_PERMISSION_CODE",
                denial_detail.get("code")
                == "DATASET_READ_PERMISSION_DENIED",
            )
        finally:
            PERMISSIONS["ANALYST"] = (
                original_analyst_permissions
            )

    analyzer.ENTERPRISE_COMPONENTS.vectors.close()
    logging.shutdown()

print("PASS R10.23-B.4")
