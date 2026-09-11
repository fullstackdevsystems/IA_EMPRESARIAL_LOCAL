"""
GA.3-B1 secure guided first-run web bootstrap regression.
"""

from pathlib import Path
import sys
import tempfile

from fastapi import HTTPException


ROOT = Path(
    __file__
).resolve().parents[2]

SCRIPTS = (
    ROOT
    / "IA_Local"
    / "scripts"
)

sys.path.insert(
    0,
    str(SCRIPTS),
)

import analizador_universal as analyzer


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print("PASS", name)


class FakeClient:
    def __init__(self, host):
        self.host = host


class FakeUrl:
    def __init__(self, hostname):
        self.hostname = hostname


class FakeRequest:
    def __init__(
        self,
        client_host="127.0.0.1",
        request_host="127.0.0.1",
    ):
        self.client = FakeClient(
            client_host
        )
        self.url = FakeUrl(
            request_host
        )


def expect_http(
    name,
    status_code,
    fn,
):
    try:
        fn()
    except HTTPException as exc:
        check(
            name,
            exc.status_code
            == status_code,
        )
        return exc
    raise AssertionError(
        name + "_NOT_BLOCKED"
    )


source = (
    ROOT
    / "IA_Local"
    / "scripts"
    / "analizador_universal.py"
).read_text(
    encoding="utf-8"
)

login_start = source.index(
    '_ANALYZE_LOGIN_SCRIPT = r"""'
)

login_end = source.index(
    '"""\n\nif \'id="ia-analyze-auth"\'',
    login_start,
)

login_script = source[
    login_start:login_end
]


check(
    "first_run_ui_present",
    'id="ia-first-run-panel"'
    in source
    and "Configura tu empresa"
    in source,
)

check(
    "guided_bootstrap_endpoints_present",
    "/api/onboarding/status"
    in source
    and "/api/onboarding/bootstrap"
    in source,
)

check(
    "bootstrap_loopback_guard_present",
    "_bootstrap_client_is_loopback"
    in source
    and "_bootstrap_host_is_local"
    in source
    and "BOOTSTRAP_LOCAL_ONLY"
    in source,
)

check(
    "bootstrap_nonce_guard_present",
    "_BOOTSTRAP_NONCE"
    in source
    and "X-IA-Bootstrap-Nonce"
    in source
    and "BOOTSTRAP_NONCE_INVALID"
    in source,
)

check(
    "bootstrap_concurrency_guard_present",
    "_BOOTSTRAP_LOCK"
    in source
    and "with _BOOTSTRAP_LOCK:"
    in source,
)

check(
    "no_token_in_url",
    "?token="
    not in login_script
    and "#token="
    not in login_script
    and "access_token="
    not in login_script,
)

check(
    "no_local_storage",
    "localStorage"
    not in login_script,
)

check(
    "admin_session_uses_existing_session_storage",
    "sessionStorage.setItem"
    in login_script
    and "iaEnterpriseSession"
    in login_script,
)


old_reports = (
    analyzer.base.REPORTES
)

try:
    with tempfile.TemporaryDirectory(
        prefix="ga3_b1_"
    ) as temporary:

        reports = (
            Path(temporary)
            / "Reportes"
        )

        reports.mkdir(
            parents=True,
            exist_ok=True,
        )

        analyzer.base.REPORTES = (
            reports
        )

        local_request = FakeRequest()

        first = (
            analyzer.onboarding_web_status(
                local_request
            )
        )

        check(
            "fresh_state_is_first_run",
            first["status"]
            == "FIRST_RUN"
            and first[
                "bootstrap_available"
            ]
            is True
            and bool(
                first[
                    "bootstrap_nonce"
                ]
            ),
        )

        expect_http(
            "remote_client_blocked",
            403,
            lambda:
                analyzer.onboarding_web_status(
                    FakeRequest(
                        client_host=
                            "192.168.1.25",
                        request_host=
                            "127.0.0.1",
                    )
                ),
        )

        expect_http(
            "non_local_host_blocked",
            403,
            lambda:
                analyzer.onboarding_web_status(
                    FakeRequest(
                        client_host=
                            "127.0.0.1",
                        request_host=
                            "empresa.example",
                    )
                ),
        )

        expect_http(
            "wrong_nonce_blocked",
            403,
            lambda:
                analyzer.onboarding_web_bootstrap(
                    {
                        "company_name":
                            "Empresa Demo",
                        "admin_username":
                            "admin",
                        "admin_display_name":
                            "Administrador",
                        "password":
                            "PasswordSeguro12",
                        "password_confirmation":
                            "PasswordSeguro12",
                    },
                    local_request,
                    "incorrecto",
                ),
        )

        expect_http(
            "password_confirmation_checked",
            400,
            lambda:
                analyzer.onboarding_web_bootstrap(
                    {
                        "company_name":
                            "Empresa Demo",
                        "admin_username":
                            "admin",
                        "admin_display_name":
                            "Administrador",
                        "password":
                            "PasswordSeguro12",
                        "password_confirmation":
                            "PasswordDistinto12",
                    },
                    local_request,
                    first[
                        "bootstrap_nonce"
                    ],
                ),
        )

        check(
            "mismatch_keeps_first_run",
            analyzer.EnterpriseOnboarding(
                reports
            ).status()["status"]
            == "FIRST_RUN",
        )

        weak_nonce = (
            analyzer.onboarding_web_status(
                local_request
            )[
                "bootstrap_nonce"
            ]
        )

        expect_http(
            "weak_password_blocked",
            400,
            lambda:
                analyzer.onboarding_web_bootstrap(
                    {
                        "company_name":
                            "Empresa Demo",
                        "admin_username":
                            "admin",
                        "admin_display_name":
                            "Administrador",
                        "password":
                            "corta",
                        "password_confirmation":
                            "corta",
                    },
                    local_request,
                    weak_nonce,
                ),
        )

        weak_state = (
            analyzer.EnterpriseOnboarding(
                reports
            ).status()
        )

        check(
            "weak_password_is_atomic",
            weak_state["status"]
            == "FIRST_RUN"
            and weak_state[
                "tenant_count"
            ]
            == 0
            and weak_state[
                "admin_count"
            ]
            == 0,
        )

        nonce = (
            analyzer.onboarding_web_status(
                local_request
            )[
                "bootstrap_nonce"
            ]
        )

        result = (
            analyzer.onboarding_web_bootstrap(
                {
                    "company_name":
                        "Empresa Demo",
                    "admin_username":
                        "Admin Principal",
                    "admin_display_name":
                        "Administrador Demo",
                    "password":
                        "PasswordSeguro12",
                    "password_confirmation":
                        "PasswordSeguro12",
                },
                local_request,
                nonce,
            )
        )

        check(
            "bootstrap_success",
            result["status"]
            == "CONFIGURED"
            and result[
                "bootstrap_available"
            ]
            is False
            and result[
                "company"
            ][
                "name"
            ]
            == "Empresa Demo"
            and result[
                "login_username"
            ]
            == "admin-principal",
        )

        check(
            "bootstrap_returns_authenticated_session",
            bool(result["token"])
            and analyzer
                ._identity_store()
                .authenticate(
                    result["token"]
                )[
                    "username"
                ]
            == "admin-principal",
        )

        serialized = str(
            result
        ).lower()

        check(
            "bootstrap_response_has_no_password",
            "passwordseguro12"
            not in serialized
            and "password_hash"
            not in serialized,
        )

        configured = (
            analyzer.EnterpriseOnboarding(
                reports
            ).status()
        )

        check(
            "configured_state_persisted",
            configured["status"]
            == "CONFIGURED"
            and configured[
                "tenant_count"
            ]
            == 1
            and configured[
                "admin_count"
            ]
            == 1,
        )

        after = (
            analyzer.onboarding_web_status(
                local_request
            )
        )

        check(
            "bootstrap_closes_after_success",
            after[
                "bootstrap_available"
            ]
            is False
            and after[
                "bootstrap_nonce"
            ]
            is None,
        )

        expect_http(
            "second_bootstrap_blocked",
            409,
            lambda:
                analyzer.onboarding_web_bootstrap(
                    {
                        "company_name":
                            "Otra Empresa",
                        "admin_username":
                            "otro-admin",
                        "admin_display_name":
                            "Otro Admin",
                        "password":
                            "PasswordSeguro34",
                        "password_confirmation":
                            "PasswordSeguro34",
                    },
                    local_request,
                    analyzer
                        ._BOOTSTRAP_NONCE,
                ),
        )

finally:
    analyzer.base.REPORTES = (
        old_reports
    )


print(
    "PASS GA.3-B1 SECURE FIRST-RUN WEB BOOTSTRAP"
)
