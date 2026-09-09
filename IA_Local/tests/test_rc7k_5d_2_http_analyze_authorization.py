"""RC.7K.5D.2 - HTTP /api/analyze authorization gate."""

from pathlib import Path
import json
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

sys.path.insert(
    0,
    str(SCRIPTS),
)

from fastapi.testclient import TestClient

import analizador_universal as universal

base = universal.base


class FakeIdentityStore:
    def __init__(self):
        self.users = {
            "viewer-token": {
                "user_id": "viewer",
                "username": "viewer",
                "tenant_id": "tenant-a",
                "roles": ["VIEWER"],
            },
            "analyst-token": {
                "user_id": "analyst",
                "username": "analyst",
                "tenant_id": "tenant-a",
                "roles": ["ANALYST"],
            },
        }

    def authenticate(self, token):
        token = str(token or "")

        user = self.users.get(token)

        if user is None:
            raise universal.IdentityError(
                "AUTH_SESSION_INVALID",
                "Sesion invalida",
            )

        return dict(user)

    def has_permission(
        self,
        user,
        permission,
    ):
        if permission != "analysis:run":
            return False

        return (
            "ANALYST"
            in set(
                user.get("roles")
                or []
            )
        )


checks = []


def ck(name, condition):
    condition = bool(condition)

    print(
        ("PASS" if condition else "FAIL"),
        name,
    )

    checks.append(condition)


tmp = Path(
    tempfile.mkdtemp(
        prefix="rc7k5d2_"
    )
)

entrada = tmp / "Entrada"

entrada.mkdir(
    parents=True,
    exist_ok=True,
)

original_entrada = base.ENTRADA
original_store = universal._identity_store
original_analyze_file = base.analyze_file

fake_store = FakeIdentityStore()


def fake_identity_store():
    return fake_store


def fake_analyze_file(
    path,
    prompt,
):
    return {
        "ok": True,
        "narrativa": "AUTHORIZED",
        "filas": 1,
        "segundos": 0.001,
        "plan": {},
        "secciones": {},
    }


try:
    base.ENTRADA = entrada

    universal._identity_store = (
        fake_identity_store
    )

    base.analyze_file = (
        fake_analyze_file
    )

    ck(
        "guard_callable",
        callable(
            base.ANALYZE_AUTHORIZER
        ),
    )

    client = TestClient(
        universal.app
    )

    payload = {
        "prompt":
            "Genera un dashboard de prueba",
        "request_id":
            "rc7k-5d2-http",
    }

    def make_file():
        return {
            "file": (
                "rc7k_security.csv",
                b"columna\n1\n",
                "text/csv",
            )
        }

    def count_files():
        return len(
            [
                path
                for path
                in entrada.iterdir()
                if path.is_file()
            ]
        )

    before = count_files()

    no_auth = client.post(
        "/api/analyze",
        data=payload,
        files=make_file(),
    )

    after_no_auth = count_files()

    ck(
        "no_bearer_is_401",
        no_auth.status_code == 401,
    )

    ck(
        "no_bearer_no_file_write",
        after_no_auth == before,
    )

    invalid = client.post(
        "/api/analyze",
        headers={
            "Authorization":
                "Bearer invalid-token",
        },
        data=payload,
        files=make_file(),
    )

    after_invalid = count_files()

    ck(
        "invalid_bearer_is_401",
        invalid.status_code == 401,
    )

    ck(
        "invalid_bearer_no_file_write",
        after_invalid == before,
    )

    viewer = client.post(
        "/api/analyze",
        headers={
            "Authorization":
                "Bearer viewer-token",
        },
        data=payload,
        files=make_file(),
    )

    after_viewer = count_files()

    ck(
        "viewer_without_analysis_run_is_403",
        viewer.status_code == 403,
    )

    viewer_body = viewer.json()

    viewer_detail = (
        viewer_body.get("detail")
        if isinstance(
            viewer_body,
            dict,
        )
        else None
    )

    viewer_code = (
        viewer_detail.get("code")
        if isinstance(
            viewer_detail,
            dict,
        )
        else None
    )

    ck(
        "viewer_permission_code",
        viewer_code
        == "ANALYSIS_PERMISSION_DENIED",
    )

    ck(
        "viewer_denied_no_file_write",
        after_viewer == before,
    )

    analyst = client.post(
        "/api/analyze",
        headers={
            "Authorization":
                "Bearer analyst-token",
        },
        data=payload,
        files=make_file(),
    )

    after_analyst = count_files()

    ck(
        "analyst_with_analysis_run_is_200",
        analyst.status_code == 200,
    )

    analyst_body = analyst.json()

    ck(
        "authorized_result_ok",
        isinstance(
            analyst_body,
            dict,
        )
        and analyst_body.get("ok")
            is True,
    )

    ck(
        "authorized_writes_exactly_one",
        after_analyst
        == before + 1,
    )

    files_written = [
        path.name
        for path
        in entrada.iterdir()
        if path.is_file()
    ]

    ck(
        "authorized_filename_safe",
        len(files_written) == 1
        and files_written[0].endswith(
            ".csv"
        ),
    )

    print(
        json.dumps(
            {
                "status":
                    "PASS"
                    if all(checks)
                    else "FAIL",
                "no_auth_status":
                    no_auth.status_code,
                "invalid_status":
                    invalid.status_code,
                "viewer_status":
                    viewer.status_code,
                "analyst_status":
                    analyst.status_code,
                "files_before":
                    before,
                "files_after_no_auth":
                    after_no_auth,
                "files_after_invalid":
                    after_invalid,
                "files_after_viewer":
                    after_viewer,
                "files_after_analyst":
                    after_analyst,
                "file_names":
                    files_written,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )

finally:
    base.ENTRADA = (
        original_entrada
    )

    universal._identity_store = (
        original_store
    )

    base.analyze_file = (
        original_analyze_file
    )

    shutil.rmtree(
        tmp,
        ignore_errors=True,
    )


if not all(checks):
    raise SystemExit(1)

print(
    "\nPASS RC.7K.5D.2 HTTP ANALYZE AUTHORIZATION"
)