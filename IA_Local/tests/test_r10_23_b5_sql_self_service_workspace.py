"""R10.23-B.5: governed SQL self-service workspace."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(
        0,
        str(SCRIPTS),
    )


from fastapi.testclient import TestClient

import analizador_universal as analyzer

from enterprise_sql_gateway import (
    EnterpriseSqlConnectionStore,
    EnterpriseSqlExecutor,
)


def check(name, condition):
    if not condition:
        raise AssertionError(name)

    print(
        "PASS",
        name,
    )


api_source = (
    SCRIPTS
    / "enterprise_ai"
    / "api.py"
).read_text(
    encoding="utf-8",
)


check(
    "ASSISTANT_SQL_WORKSPACE_VISIBLE",
    'id="sqlConnection"'
    in api_source
    and 'id="sqlObject"'
    in api_source
    and 'id="sqlColumns"'
    in api_source
    and 'id="runSql"'
    in api_source,
)

check(
    "ASSISTANT_SQL_USES_USER_CONNECTION_API",
    (
        "protectedFetch("
        "'/api/sql/connections'"
        "+sqlTenantSuffix('?'))"
    )
    in api_source,
)

check(
    "ASSISTANT_SQL_SYSTEM_ADMIN_EXPLICIT_TENANT",
    (
        "function sqlTenantSuffix(prefix)"
        in api_source
        and "includes('SYSTEM_ADMIN')"
        in api_source
        and "currentUser.tenant_id"
        in api_source
        and (
            "encodeURIComponent(connectionId)"
            "+sqlTenantSuffix('&')"
        )
        in api_source
        and (
            "protectedFetch("
            "'/api/sql/query-safe'"
            "+sqlTenantSuffix('?')"
        )
        in api_source
    ),
)

check(
    "ASSISTANT_SQL_USES_SCHEMA_API",
    (
        "protectedFetch('/api/sql/schema?"
        "connection_id='"
    )
    in api_source,
)

check(
    "ASSISTANT_SQL_USES_SAFE_QUERY_API",
    (
        "protectedFetch("
        "'/api/sql/query-safe'"
    )
    in api_source,
)

check(
    "ASSISTANT_SQL_DOES_NOT_SEND_RAW_SQL",
    (
        "body:JSON.stringify({"
        "connection_id:connectionId,"
        "schema:String(object.schema),"
        "object:String(object.name),"
        "columns:columns,"
        "limit:limit"
        "})"
    )
    in api_source,
)

check(
    "ASSISTANT_SQL_403_PRESERVES_SESSION",
    (
        "response.status===403"
        in api_source
        and "clearEnterpriseSession();"
        not in (
            api_source[
                api_source.index(
                    "async function runSqlSelfService"
                ):
                api_source.index(
                    "async function uploadSource"
                )
            ]
        )
    ),
)

check(
    "SAFE_SQL_ENDPOINT_PRESENT",
    '@app.post("/api/sql/query-safe")'
    in (
        SCRIPTS
        / "analizador_universal.py"
    ).read_text(
        encoding="utf-8",
    ),
)


class FakeProvider:
    def __init__(self):
        self.sql = None
        self.timeout = None

    def discover(self, profile):
        return [
            {
                "schema": "dbo",
                "name": "Allowed",
                "type": "TABLE",
                "columns": [
                    {
                        "name": "Id",
                        "type": "int",
                        "nullable": False,
                    },
                    {
                        "name": "Name",
                        "type": "nvarchar",
                        "nullable": True,
                    },
                ],
            },
            {
                "schema": "private",
                "name": "Hidden",
                "type": "TABLE",
                "columns": [
                    {
                        "name": "Secret",
                        "type": "nvarchar",
                        "nullable": True,
                    }
                ],
            },
        ]

    def execute(
        self,
        profile,
        sql,
        parameters,
        timeout_seconds,
    ):
        self.sql = sql
        self.timeout = timeout_seconds

        return {
            "columns": [
                "Id",
                "Name",
            ],
            "rows": [
                [1, "Uno"],
                [2, "Dos"],
                [3, "Tres"],
                [4, "Cuatro"],
                [5, "Cinco"],
            ],
        }


with tempfile.TemporaryDirectory() as td:
    old_reports = analyzer.base.REPORTES
    old_sql_executor = analyzer._sql_executor

    reports = (
        Path(td)
        / "reports"
    )

    reports.mkdir(
        parents=True,
        exist_ok=True,
    )

    analyzer.base.REPORTES = reports

    try:
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
            user_id="system-a",
            username="system-a",
            display_name="System A",
            password="SystemPassword!1",
            tenant_id="tenant-a",
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
            user_id="viewer-a",
            username="viewer-a",
            display_name="Viewer A",
            password="ViewerPassword!1",
            tenant_id="tenant-a",
            roles=["VIEWER"],
        )

        identities.create_user(
            user_id="tenant-b-admin",
            username="tenant-b-admin",
            display_name="Tenant B Admin",
            password="TenantBPassword!1",
            tenant_id="tenant-b",
            roles=["TENANT_ADMIN"],
        )

        store = EnterpriseSqlConnectionStore(
            reports
            / ".sql_connections"
        )

        store.register(
            scope={
                "company_id":
                    "tenant-a",
                "user_id":
                    "sql-admin",
                "business_unit":
                    None,
                "branch":
                    None,
            },
            connection_id="erp",
            server="sql-a",
            database="ERP",
            auth_mode="WINDOWS_INTEGRATED",
            allowed_schemas=[
                "dbo",
            ],
            allowed_tables=[
                "dbo.Allowed",
            ],
            max_rows=3,
            timeout_seconds=11,
        )

        provider = FakeProvider()

        analyzer._sql_executor = (
            lambda:
                EnterpriseSqlExecutor(
                    store,
                    provider,
                )
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
                    "LOGIN_" + username,
                    response.status_code
                    == 200,
                )

                return {
                    "Authorization":
                        "Bearer "
                        + response.json()[
                            "token"
                        ]
                }

            system_headers = login(
                "system-a",
                "SystemPassword!1",
            )

            analyst_headers = login(
                "analyst-a",
                "AnalystPassword!1",
            )

            viewer_headers = login(
                "viewer-a",
                "ViewerPassword!1",
            )

            tenant_b_headers = login(
                "tenant-b-admin",
                "TenantBPassword!1",
            )

            unauthenticated = client.get(
                "/api/sql/connections"
            )

            check(
                "SQL_WORKSPACE_REQUIRES_AUTH",
                unauthenticated.status_code
                == 401,
            )

            connections = client.get(
                "/api/sql/connections",
                headers=analyst_headers,
            )

            check(
                "ANALYST_CAN_LIST_SQL_SOURCES",
                connections.status_code
                == 200,
            )

            items = (
                connections.json()
                .get("items")
                or []
            )

            check(
                "TENANT_SQL_SOURCE_VISIBLE",
                len(items)
                == 1
                and items[0][
                    "connection_id"
                ]
                == "erp",
            )

            check(
                "SQL_SOURCE_PUBLIC_SAFE",
                "secret"
                not in connections.text.lower()
                and "password"
                not in connections.text.lower()
                and "credential_ref"
                not in connections.text.lower(),
            )

            system_without_target = client.get(
                "/api/sql/connections",
                headers=system_headers,
            )

            check(
                "SYSTEM_ADMIN_SQL_REQUIRES_EXPLICIT_TARGET",
                system_without_target.status_code
                == 400,
            )

            system_connections = client.get(
                (
                    "/api/sql/connections"
                    "?tenant_id=tenant-a"
                ),
                headers=system_headers,
            )

            check(
                "SYSTEM_ADMIN_HOME_TENANT_SQL_LIST",
                system_connections.status_code
                == 200
                and len(
                    system_connections.json()
                    .get("items")
                    or []
                )
                == 1,
            )

            system_schema = client.get(
                (
                    "/api/sql/schema?"
                    "connection_id=erp"
                    "&tenant_id=tenant-a"
                ),
                headers=system_headers,
            )

            check(
                "SYSTEM_ADMIN_HOME_TENANT_SCHEMA",
                system_schema.status_code
                == 200,
            )

            system_query = client.post(
                (
                    "/api/sql/query-safe"
                    "?tenant_id=tenant-a"
                ),
                headers=system_headers,
                json={
                    "connection_id":
                        "erp",
                    "schema":
                        "dbo",
                    "object":
                        "Allowed",
                    "columns": [
                        "Id",
                        "Name",
                    ],
                    "limit":
                        2,
                },
            )

            check(
                "SYSTEM_ADMIN_HOME_TENANT_SAFE_QUERY",
                system_query.status_code
                == 200,
            )

            schema = client.get(
                (
                    "/api/sql/schema?"
                    "connection_id=erp"
                ),
                headers=analyst_headers,
            )

            check(
                "SQL_SCHEMA_AUTHORIZED",
                schema.status_code
                == 200,
            )

            schema_payload = (
                schema.json()
            )

            objects = (
                schema_payload.get(
                    "objects"
                )
                or []
            )

            check(
                "ONLY_ALLOWLISTED_OBJECT_VISIBLE",
                len(objects)
                == 1
                and objects[0][
                    "schema"
                ]
                == "dbo"
                and objects[0][
                    "name"
                ]
                == "Allowed",
            )

            safe_query = client.post(
                "/api/sql/query-safe",
                headers=analyst_headers,
                json={
                    "connection_id":
                        "erp",
                    "schema":
                        "dbo",
                    "object":
                        "Allowed",
                    "columns": [
                        "Id",
                        "Name",
                    ],
                    "limit":
                        2,
                },
            )

            check(
                "SAFE_SQL_QUERY_AUTHORIZED",
                safe_query.status_code
                == 200,
            )

            result = safe_query.json()

            check(
                "SAFE_SQL_QUERY_RESULT",
                result[
                    "status"
                ]
                == "PASS"
                and result[
                    "row_count"
                ]
                == 2
                and result[
                    "truncated"
                ]
                is True,
            )

            check(
                "SERVER_BUILDS_SQL",
                provider.sql
                == (
                    "SELECT TOP (2) "
                    "[Id], [Name] "
                    "FROM [dbo].[Allowed]"
                ),
            )

            check(
                "PROFILE_TIMEOUT_PRESERVED",
                provider.timeout
                == 11,
            )

            check(
                "SQL_RESULT_HAS_SAFE_PROVENANCE",
                result[
                    "provenance"
                ][
                    "schema"
                ]
                == "dbo"
                and result[
                    "provenance"
                ][
                    "object"
                ]
                == "Allowed"
                and "password"
                not in str(
                    result[
                        "provenance"
                    ]
                ).lower(),
            )

            raw_sql_attempt = (
                client.post(
                    "/api/sql/query-safe",
                    headers=analyst_headers,
                    json={
                        "connection_id":
                            "erp",
                        "schema":
                            "dbo",
                        "object":
                            "Allowed",
                        "columns": [
                            "Id",
                        ],
                        "limit":
                            1,
                        "sql":
                            (
                                "DELETE FROM "
                                "dbo.Allowed"
                            ),
                    },
                )
            )

            check(
                "RAW_SQL_FIELD_REJECTED",
                raw_sql_attempt.status_code
                == 400
                and raw_sql_attempt.json()[
                    "detail"
                ][
                    "code"
                ]
                == "SQL_QUERY_INVALID",
            )

            viewer = client.get(
                "/api/sql/connections",
                headers=viewer_headers,
            )

            check(
                "VIEWER_SQL_DENIED",
                viewer.status_code
                == 403,
            )

            tenant_b_list = client.get(
                "/api/sql/connections",
                headers=tenant_b_headers,
            )

            check(
                "CROSS_TENANT_SQL_LIST_ISOLATED",
                tenant_b_list.status_code
                == 200
                and (
                    tenant_b_list.json()
                    .get("items")
                    or []
                )
                == [],
            )

            cross_query = client.post(
                "/api/sql/query-safe",
                headers=tenant_b_headers,
                json={
                    "connection_id":
                        "erp",
                    "schema":
                        "dbo",
                    "object":
                        "Allowed",
                    "columns": [
                        "Id",
                    ],
                    "limit":
                        1,
                },
            )

            check(
                "CROSS_TENANT_SQL_QUERY_BLOCKED",
                cross_query.status_code
                == 404,
            )

    finally:
        analyzer._sql_executor = (
            old_sql_executor
        )

        analyzer.base.REPORTES = (
            old_reports
        )


print(
    "PASS R10.23-B.5"
)
