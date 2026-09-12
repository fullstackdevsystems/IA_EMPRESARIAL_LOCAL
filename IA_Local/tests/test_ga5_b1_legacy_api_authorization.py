from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def check(name, condition):
    if not condition:
        raise AssertionError(name)

    print("PASS", name)


print("")
print("=== GA.5-B1 LEGACY API AUTHORIZATION ===")

original_root = os.environ.get(
    "IA_LOCAL_ROOT"
)

with tempfile.TemporaryDirectory(
    prefix="ga5_b1_auth_"
) as temp_name:
    temp = Path(temp_name)
    product = temp / "product"
    runtime = product / "IA_Local"

    for relative in (
        "workspace/Entrada",
        "workspace/Reportes",
        "workspace/Historico",
    ):
        (
            runtime / relative
        ).mkdir(
            parents=True,
            exist_ok=True,
        )

    shutil.copy2(
        ROOT / "RELEASE_METADATA.json",
        product / "RELEASE_METADATA.json",
    )

    os.environ[
        "IA_LOCAL_ROOT"
    ] = str(runtime)

    import enterprise_ai.api as enterprise_api

    original_install = (
        enterprise_api.install_enterprise_routes
    )

    enterprise_api.install_enterprise_routes = (
        lambda app, root: None
    )

    try:
        import analizador_universal as analyzer

    finally:
        enterprise_api.install_enterprise_routes = (
            original_install
        )

    from fastapi.testclient import TestClient

    from enterprise_identity import (
        EnterpriseIdentityStore,
    )

    from enterprise_tenant_registry import (
        EnterpriseTenantRegistry,
    )

    reports = analyzer.base.REPORTES

    tenants = EnterpriseTenantRegistry(
        reports / ".tenants"
    )

    tenants.create(
        tenant_id="alpha",
        name="Alpha",
    )

    tenants.create(
        tenant_id="bravo",
        name="Bravo",
    )

    identity = EnterpriseIdentityStore(
        reports / ".identity",
        tenants,
    )

    password = "GA5-Secure-Password!2026"

    for user_id, tenant_id, roles in (
        (
            "sys-alpha",
            "alpha",
            ["SYSTEM_ADMIN"],
        ),
        (
            "analyst-alpha",
            "alpha",
            ["ANALYST"],
        ),
        (
            "viewer-alpha",
            "alpha",
            ["VIEWER"],
        ),
        (
            "analyst-bravo",
            "bravo",
            ["ANALYST"],
        ),
    ):
        identity.create_user(
            user_id=user_id,
            username=user_id,
            display_name=user_id,
            password=password,
            tenant_id=tenant_id,
            roles=roles,
        )

    sys_token, _ = identity.login(
        "sys-alpha",
        password,
    )

    alpha_token, _ = identity.login(
        "analyst-alpha",
        password,
    )

    viewer_token, _ = identity.login(
        "viewer-alpha",
        password,
    )

    bravo_token, _ = identity.login(
        "analyst-bravo",
        password,
    )

    analyzer._identity_store = (
        lambda:
            identity
    )

    analyzer._tenant_registry = (
        lambda:
            tenants
    )

    captured = {
        "deliverable_scopes": [],
        "sql_scopes": [],
        "ask_calls": [],
    }

    artifact = reports / "ga5-probe.html"

    artifact.write_text(
        "<html>GA5</html>",
        encoding="utf-8",
    )


    class FakeRegistry:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            pass

        def list(
            self,
            scope,
            limit=100,
        ):
            captured[
                "deliverable_scopes"
            ].append(
                dict(scope)
            )

            return []

        def get(
            self,
            scope,
            run_id,
        ):
            captured[
                "deliverable_scopes"
            ].append(
                dict(scope)
            )

            return {
                "run_id":
                    str(run_id),
                "scope":
                    dict(scope),
            }

        def artifact_path(
            self,
            scope,
            run_id,
            kind,
        ):
            captured[
                "deliverable_scopes"
            ].append(
                dict(scope)
            )

            return artifact


    class FakeSqlConnectionStore:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            pass

        def list(
            self,
            scope,
        ):
            captured[
                "sql_scopes"
            ].append(
                dict(scope)
            )

            return []


    class FakeSqlExecutor:
        def discover(
            self,
            scope,
            connection_id,
        ):
            captured[
                "sql_scopes"
            ].append(
                dict(scope)
            )

            return {
                "connection_id":
                    str(connection_id),
                "objects":
                    [],
            }

        def execute(
            self,
            scope,
            connection_id,
            query_plan,
        ):
            captured[
                "sql_scopes"
            ].append(
                dict(scope)
            )

            return {
                "status":
                    "ANSWERED",
                "columns":
                    [],
                "rows":
                    [],
                "row_count":
                    0,
                "truncated":
                    False,
                "provenance":
                    {
                        "provider":
                            "probe"
                    },
            }


    class FakeKnowledgeStore:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            pass


    def fake_orchestrator(
        *,
        registry,
        knowledge_store,
        scope,
        question,
        run_id=None,
        sql_context=None,
        sql_executor=None,
        sql_scope=None,
    ):
        captured[
            "ask_calls"
        ].append(
            {
                "scope":
                    dict(scope),
                "sql_scope":
                    (
                        dict(sql_scope)
                        if sql_scope
                        is not None
                        else None
                    ),
            }
        )

        return {
            "status":
                "ANSWERED",
            "answer":
                "probe",
        }


    analyzer.GovernedDeliverableRegistry = FakeRegistry
    analyzer.EnterpriseSqlConnectionStore = FakeSqlConnectionStore
    analyzer._sql_executor = lambda: FakeSqlExecutor()
    analyzer.EnterpriseKnowledgeStore = FakeKnowledgeStore

    analyzer.answer_enterprise_question_orchestrated = (
        fake_orchestrator
    )


    def headers(token):
        return {
            "Authorization":
                "Bearer "
                + token
        }


    invalid_headers = {
        "Authorization":
            "Bearer invalid-ga5-session"
    }

    routes = (
        (
            "GET",
            "/api/deliverables",
            None,
        ),
        (
            "GET",
            "/api/deliverables/probe",
            None,
        ),
        (
            "GET",
            "/api/deliverables/probe/download/html",
            None,
        ),
        (
            "GET",
            "/api/sql/connections",
            None,
        ),
        (
            "GET",
            "/api/sql/schema?connection_id=probe",
            None,
        ),
        (
            "POST",
            "/api/sql/query",
            {
                "connection_id":
                    "probe",
                "query_plan":
                    {
                        "sql":
                            "SELECT 1"
                    },
            },
        ),
        (
            "POST",
            "/api/ask",
            {
                "question":
                    "probe"
            },
        ),
    )

    with TestClient(
        analyzer.app,
        raise_server_exceptions=False,
    ) as client:

        for method, url, payload in routes:
            kwargs = {}

            if payload is not None:
                kwargs["json"] = payload

            missing = client.request(
                method,
                url,
                **kwargs,
            )

            invalid = client.request(
                method,
                url,
                headers=invalid_headers,
                **kwargs,
            )

            check(
                "missing_auth_"
                + method
                + "_"
                + url,
                missing.status_code
                == 401,
            )

            check(
                "invalid_auth_"
                + method
                + "_"
                + url,
                invalid.status_code
                == 401,
            )

        viewer_deliverables = client.get(
            "/api/deliverables",
            headers=headers(
                viewer_token
            ),
        )

        check(
            "viewer_deliverable_read_allowed",
            viewer_deliverables.status_code
            == 200,
        )

        check(
            "viewer_scope_isolated",
            captured[
                "deliverable_scopes"
            ][-1]
            == {
                "company_id":
                    "alpha",
                "user_id":
                    "viewer-alpha",
                "business_unit":
                    None,
                "branch":
                    None,
            },
        )

        check(
            "viewer_sql_denied",
            client.get(
                "/api/sql/connections",
                headers=headers(
                    viewer_token
                ),
            ).status_code
            == 403,
        )

        check(
            "viewer_ask_denied",
            client.post(
                "/api/ask",
                headers=headers(
                    viewer_token
                ),
                json={
                    "question":
                        "probe"
                },
            ).status_code
            == 403,
        )

        alpha_list = client.get(
            "/api/deliverables",
            headers=headers(
                alpha_token
            ),
        )

        check(
            "alpha_deliverable_success",
            alpha_list.status_code
            == 200,
        )

        check(
            "alpha_content_scope",
            captured[
                "deliverable_scopes"
            ][-1]
            == {
                "company_id":
                    "alpha",
                "user_id":
                    "analyst-alpha",
                "business_unit":
                    None,
                "branch":
                    None,
            },
        )

        bravo_list = client.get(
            "/api/deliverables",
            headers=headers(
                bravo_token
            ),
        )

        check(
            "bravo_deliverable_success",
            bravo_list.status_code
            == 200,
        )

        check(
            "bravo_tenant_scope",
            captured[
                "deliverable_scopes"
            ][-1][
                "company_id"
            ]
            == "bravo",
        )

        sql_list = client.get(
            "/api/sql/connections",
            headers=headers(
                alpha_token
            ),
        )

        check(
            "alpha_sql_success",
            sql_list.status_code
            == 200,
        )

        check(
            "alpha_sql_service_scope",
            captured[
                "sql_scopes"
            ][-1]
            == {
                "company_id":
                    "alpha",
                "user_id":
                    "sql-admin",
                "business_unit":
                    None,
                "branch":
                    None,
            },
        )

        check(
            "cross_tenant_sql_denied",
            client.get(
                "/api/sql/connections?tenant_id=bravo",
                headers=headers(
                    alpha_token
                ),
            ).status_code
            == 403,
        )

        check(
            "system_admin_requires_target",
            client.get(
                "/api/sql/connections",
                headers=headers(
                    sys_token
                ),
            ).status_code
            == 400,
        )

        plain = client.post(
            "/api/ask",
            headers=headers(
                alpha_token
            ),
            json={
                "question":
                    "probe"
            },
        )

        check(
            "ask_plain_success",
            plain.status_code
            == 200,
        )

        plain_call = captured[
            "ask_calls"
        ][-1]

        check(
            "ask_content_scope",
            plain_call[
                "scope"
            ]
            == {
                "company_id":
                    "alpha",
                "user_id":
                    "analyst-alpha",
                "business_unit":
                    None,
                "branch":
                    None,
            },
        )

        check(
            "ask_plain_no_sql_scope",
            plain_call[
                "sql_scope"
            ]
            is None,
        )

        sql_ask = client.post(
            "/api/ask",
            headers=headers(
                alpha_token
            ),
            json={
                "question":
                    "probe",
                "sql":
                    {
                        "connection_id":
                            "probe",
                        "query_plan":
                            {
                                "sql":
                                    "SELECT 1"
                            },
                    },
            },
        )

        check(
            "ask_sql_success",
            sql_ask.status_code
            == 200,
        )

        sql_call = captured[
            "ask_calls"
        ][-1]

        check(
            "ask_sql_service_scope",
            sql_call[
                "sql_scope"
            ]
            == {
                "company_id":
                    "alpha",
                "user_id":
                    "sql-admin",
                "business_unit":
                    None,
                "branch":
                    None,
            },
        )

        check(
            "ask_cross_tenant_sql_denied",
            client.post(
                "/api/ask",
                headers=headers(
                    alpha_token
                ),
                json={
                    "question":
                        "probe",
                    "sql":
                        {
                            "tenant_id":
                                "bravo",
                            "connection_id":
                                "probe",
                            "query_plan":
                                {
                                    "sql":
                                        "SELECT 1"
                                },
                        },
                },
            ).status_code
            == 403,
        )

        analyze_actor = {}

        original_analyze = (
            analyzer.base.analyze_file
        )

        def fake_analyze(
            path,
            prompt,
        ):
            actor = (
                analyzer.base
                .ANALYZE_AUTH_CONTEXT
                .get()
            )

            analyze_actor.update(
                actor
                or {}
            )

            return {
                "ok":
                    True,
                "filas":
                    1,
                "segundos":
                    0.0,
                "narrativa":
                    "probe",
                "plan":
                    {},
                "secciones":
                    {},
            }

        analyzer.base.analyze_file = fake_analyze

        try:
            analyzed = client.post(
                "/api/analyze",
                headers=headers(
                    alpha_token
                ),
                files={
                    "file":
                        (
                            "probe.csv",
                            b"a\n1\n",
                            "text/csv",
                        )
                },
                data={
                    "prompt":
                        "Analiza el archivo"
                },
            )

        finally:
            analyzer.base.analyze_file = (
                original_analyze
            )

        check(
            "analyze_authenticated_success",
            analyzed.status_code
            == 200,
        )

        check(
            "analyze_actor_propagated",
            (
                analyze_actor.get(
                    "tenant_id"
                )
                == "alpha"
                and analyze_actor.get(
                    "user_id"
                )
                == "analyst-alpha"
            ),
        )

        check(
            "analyze_context_reset",
            (
                analyzer.base
                .ANALYZE_AUTH_CONTEXT
                .get()
                is None
            ),
        )

    universal_text = (
        ROOT
        / "IA_Local"
        / "scripts"
        / "analizador_universal.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    ask_start = universal_text.index(
        "async function enterpriseAsk()"
    )

    ask_block = universal_text[
        ask_start:
        ask_start + 4500
    ]

    check(
        "ask_memory_token_first",
        "window.__IA_ANALYZE_TOKEN__ ||"
        in ask_block,
    )

    check(
        "ask_session_fallback",
        (
            "sessionStorage.getItem("
            in ask_block
            and "'iaEnterpriseSession'"
            in ask_block
        ),
    )

    check(
        "ask_bearer_header",
        (
            "'Authorization':"
            in ask_block
            and "'Bearer '+sessionToken"
            in ask_block
        ),
    )

    check(
        "ask_no_localstorage",
        "localStorage"
        not in ask_block,
    )


if original_root is None:
    os.environ.pop(
        "IA_LOCAL_ROOT",
        None,
    )
else:
    os.environ[
        "IA_LOCAL_ROOT"
    ] = original_root


print("")
print(
    "PASS GA.5-B1 LEGACY API AUTHORIZATION"
)
