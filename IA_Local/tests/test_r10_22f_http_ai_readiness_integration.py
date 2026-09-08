"""R10.22F.5B productive HTTP readiness + real AI health adapter."""

from pathlib import Path
import json
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"

sys.path.insert(
    0,
    str(SCRIPTS),
)


def check(name, value):
    assert value, name
    print("PASS", name)


old_root = os.environ.get(
    "IA_LOCAL_ROOT"
)

with tempfile.TemporaryDirectory() as td:

    product = (
        Path(td)
        / "product"
    )

    runtime = (
        product
        / "IA_Local"
    )

    runtime.mkdir(
        parents=True
    )

    (
        product
        / "RELEASE_METADATA.json"
    ).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product":
                    "IA_EMPRESARIAL_LOCAL",
                "product_version":
                    "8.5.5",
                "release":
                    "r10.21f",
                "channel":
                    "stable",
            }
        ),
        encoding="utf-8",
    )

    os.environ[
        "IA_LOCAL_ROOT"
    ] = str(runtime)

    import analizador_universal as analyzer
    from fastapi.testclient import TestClient

    try:
        tenants = (
            analyzer._tenant_registry()
        )

        tenants.create(
            tenant_id="alpha",
            name="Alpha",
        )

        tenants.create(
            tenant_id="bravo",
            name="Bravo",
        )

        identities = (
            analyzer._identity_store()
        )

        identities.bootstrap_admin(
            user_id="sys",
            username="sys",
            display_name="System",
            password=
                "SystemPassword!1",
            tenant_id="alpha",
        )

        identities.create_user(
            user_id="tenant",
            username="tenant",
            display_name="Tenant",
            password=
                "TenantPassword!1",
            tenant_id="alpha",
            roles=["TENANT_ADMIN"],
        )

        identities.create_user(
            user_id="viewer",
            username="viewer",
            display_name="Viewer",
            password=
                "ViewerPassword!1",
            tenant_id="alpha",
            roles=["VIEWER"],
        )

        platform = (
            analyzer._platform_config()
        )

        platform.update_tenant(
            "alpha",
            {
                "enabled_features": {
                    "sql_enabled":
                        False,
                    "ai_enabled":
                        True,
                },
                "ai_provider": {
                    "provider_type":
                        "OLLAMA",
                    "base_url":
                        "http://127.0.0.1:11434",
                    "model":
                        "qwen3:4b-instruct",
                    "timeout":
                        10,
                    "enabled":
                        True,
                },
            },
        )

        platform.update_tenant(
            "bravo",
            {
                "enabled_features": {
                    "sql_enabled":
                        False,
                    "ai_enabled":
                        False,
                },
            },
        )

        original_ollama_health = (
            analyzer
            .OllamaProvider
            .healthy
        )

        original_lm_health = (
            analyzer
            .LMStudioProvider
            .healthy
        )

        with TestClient(
            analyzer.app
        ) as client:

            def login(
                username,
                password,
            ):
                response = client.post(
                    "/api/auth/login",
                    json={
                        "username":
                            username,
                        "password":
                            password,
                    },
                )

                check(
                    "login_" + username,
                    response.status_code
                    == 200
                    and response.json()
                    .get("token"),
                )

                return {
                    "Authorization":
                        "Bearer "
                        + response.json()[
                            "token"
                        ]
                }

            system = login(
                "sys",
                "SystemPassword!1",
            )

            tenant = login(
                "tenant",
                "TenantPassword!1",
            )

            viewer = login(
                "viewer",
                "ViewerPassword!1",
            )

            # --------------------------------------------------
            # Initial readiness:
            # configured AI is not automatically tested.
            # --------------------------------------------------

            pending = client.get(
                "/api/admin/tenants/alpha/readiness",
                headers=tenant,
            )

            check(
                "readiness_http_available",
                pending.status_code
                == 200,
            )

            pending_body = (
                pending.json()
            )

            check(
                "configured_ai_not_tested_over_http",
                pending_body[
                    "status"
                ] == "CONFIGURED"
                and pending_body[
                    "steps"
                ]["ai"]["status"]
                == "CONFIGURED",
            )

            # --------------------------------------------------
            # Tenant isolation / permissions.
            # --------------------------------------------------

            check(
                "tenant_cross_readiness_blocked",
                client.get(
                    "/api/admin/tenants/bravo/readiness",
                    headers=tenant,
                ).status_code
                == 403,
            )

            check(
                "viewer_readiness_denied",
                client.get(
                    "/api/admin/tenants/alpha/readiness",
                    headers=viewer,
                ).status_code
                == 403,
            )

            # --------------------------------------------------
            # Real adapter uses existing OllamaProvider.healthy().
            # --------------------------------------------------

            analyzer.OllamaProvider.healthy = (
                lambda self: True
            )

            provider_test = client.post(
                "/api/admin/ai/provider/test",
                headers=tenant,
                json={
                    "tenant_id":
                        "alpha",
                    "provider": {
                        "provider_type":
                            "OLLAMA",
                        "base_url":
                            "http://127.0.0.1:11434",
                        "model":
                            "qwen3:4b-instruct",
                        "timeout":
                            10,
                        "enabled":
                            True,
                    },
                },
            )

            check(
                "ollama_existing_health_authority_used",
                provider_test.status_code
                == 200
                and provider_test.json()[
                    "status"
                ] == "PASS"
                and provider_test.json()[
                    "provider_type"
                ] == "OLLAMA",
            )

            validated = client.post(
                "/api/admin/tenants/alpha/readiness/validate",
                headers=tenant,
            )

            check(
                "saved_provider_live_validation",
                validated.status_code
                == 200
                and validated.json()[
                    "ai_test"
                ]["status"]
                == "PASS",
            )

            check(
                "live_ai_pass_allows_ready",
                validated.json()[
                    "readiness"
                ]["status"]
                == "READY"
                and validated.json()[
                    "readiness"
                ]["steps"][
                    "ai"
                ]["status"]
                == "TESTED",
            )

            # Live evidence is intentionally not persisted.
            after_validation = (
                client.get(
                    "/api/admin/tenants/alpha/readiness",
                    headers=tenant,
                )
            )

            check(
                "live_ai_evidence_not_fake_persisted",
                after_validation.status_code
                == 200
                and after_validation.json()[
                    "steps"
                ]["ai"]["status"]
                == "CONFIGURED",
            )

            # --------------------------------------------------
            # Failure is aggregated into DEGRADED readiness,
            # rather than falsely returning READY.
            # --------------------------------------------------

            analyzer.OllamaProvider.healthy = (
                lambda self: False
            )

            degraded = client.post(
                "/api/admin/tenants/alpha/readiness/validate",
                headers=tenant,
            )

            check(
                "ai_unavailable_becomes_degraded",
                degraded.status_code
                == 200
                and degraded.json()[
                    "ai_test"
                ]["status"]
                == "FAIL"
                and degraded.json()[
                    "ai_test"
                ]["code"]
                == "AI_PROVIDER_UNAVAILABLE"
                and degraded.json()[
                    "readiness"
                ]["status"]
                == "DEGRADED",
            )

            # The explicit provider-test endpoint retains
            # its normal 503 unavailable contract.
            failed_test = client.post(
                "/api/admin/ai/provider/test",
                headers=tenant,
                json={
                    "tenant_id":
                        "alpha",
                    "provider": {
                        "provider_type":
                            "OLLAMA",
                        "base_url":
                            "http://127.0.0.1:11434",
                        "model":
                            "qwen3:4b-instruct",
                        "timeout":
                            10,
                        "enabled":
                            True,
                    },
                },
            )

            check(
                "provider_test_unavailable_is_503",
                failed_test.status_code
                == 503,
            )

            # --------------------------------------------------
            # OPENAI_COMPATIBLE_LOCAL reuses existing
            # LMStudioProvider health implementation.
            # --------------------------------------------------

            analyzer.LMStudioProvider.healthy = (
                lambda self: True
            )

            openai_test = client.post(
                "/api/admin/ai/provider/test",
                headers=tenant,
                json={
                    "tenant_id":
                        "alpha",
                    "provider": {
                        "provider_type":
                            "OPENAI_COMPATIBLE_LOCAL",
                        "base_url":
                            "http://127.0.0.1:1234/v1",
                        "model":
                            "local-model",
                        "timeout":
                            10,
                        "enabled":
                            True,
                    },
                },
            )

            check(
                "openai_compatible_reuses_existing_health",
                openai_test.status_code
                == 200
                and openai_test.json()[
                    "status"
                ] == "PASS"
                and openai_test.json()[
                    "provider_type"
                ]
                == "OPENAI_COMPATIBLE_LOCAL",
            )

            # Missing model must not certify readiness.
            no_model = client.post(
                "/api/admin/ai/provider/test",
                headers=tenant,
                json={
                    "tenant_id":
                        "alpha",
                    "provider": {
                        "provider_type":
                            "OLLAMA",
                        "base_url":
                            "http://127.0.0.1:11434",
                        "timeout":
                            10,
                        "enabled":
                            True,
                    },
                },
            )

            check(
                "missing_model_fail_closed",
                no_model.status_code
                == 400,
            )

            # SYSTEM_ADMIN may inspect another tenant.
            other = client.get(
                "/api/admin/tenants/bravo/readiness",
                headers=system,
            )

            check(
                "system_admin_cross_tenant_readiness",
                other.status_code
                == 200
                and other.json()[
                    "tenant_id"
                ] == "bravo",
            )

            safe = json.dumps(
                {
                    "pending":
                        pending_body,
                    "validated":
                        validated.json(),
                    "degraded":
                        degraded.json(),
                },
                ensure_ascii=False,
            ).lower()

            check(
                "http_readiness_secret_safe",
                all(
                    value
                    not in safe
                    for value in (
                        "password_hash",
                        "secret_reference",
                        "credential_ref",
                        "token_fingerprint",
                        "systempassword!1",
                        "tenantpassword!1",
                    )
                ),
            )

        analyzer.OllamaProvider.healthy = (
            original_ollama_health
        )

        analyzer.LMStudioProvider.healthy = (
            original_lm_health
        )

    finally:
        if old_root is None:
            os.environ.pop(
                "IA_LOCAL_ROOT",
                None,
            )
        else:
            os.environ[
                "IA_LOCAL_ROOT"
            ] = old_root


print(
    "PASS R10.22F.5B HTTP AI READINESS"
)
