from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(
        0,
        str(SCRIPTS),
    )


from fastapi.testclient import TestClient

import analizador_universal as analyzer

from enterprise_sql_gateway import (
    EnterpriseSecretStore,
    EnterpriseSqlConnectionStore,
    EnterpriseSqlError,
    build_transient_sql_probe_profile,
    probe_sql_server_metadata,
)


def check(name, condition):
    if not condition:
        raise AssertionError(name)

    print(
        "PASS",
        name,
    )


class FakeProvider:
    def __init__(self):
        self.tested = []
        self.discovered = []

    def test_connection(
        self,
        profile,
        timeout_seconds,
    ):
        self.tested.append(
            dict(profile)
        )

        return {
            "database":
                profile["database"]
        }

    def discover(
        self,
        profile,
    ):
        self.discovered.append(
            dict(profile)
        )

        return [
            {
                "schema": "dbo",
                "name": "Ventas",
                "type": "BASE TABLE",
                "columns": [
                    {
                        "name": "Id",
                        "type": "int",
                        "nullable": False,
                    }
                ],
            },
            {
                "schema": "dbo",
                "name": "Clientes",
                "type": "BASE TABLE",
                "columns": [],
            },
            {
                "schema": "dbo",
                "name": "Ventas",
                "type": "BASE TABLE",
                "columns": [],
            },
            {
                "schema": "bad schema",
                "name": "Ignored",
                "type": "BASE TABLE",
                "columns": [],
            },
        ]


def pure_gateway_contract():
    profile = (
        build_transient_sql_probe_profile(
            server="sql01",
            database="ERP",
            auth_mode="WINDOWS",
        )
    )

    check(
        "transient_profile_windows_normalized",
        profile["auth_mode"]
        == "WINDOWS_INTEGRATED",
    )

    check(
        "transient_profile_has_no_allowlist",
        profile["allowed_schemas"]
        == []
        and profile["allowed_tables"]
        == [],
    )

    check(
        "transient_profile_is_read_only",
        profile["read_only"]
        is True,
    )

    provider = FakeProvider()

    result = (
        probe_sql_server_metadata(
            provider,
            profile,
        )
    )

    check(
        "probe_tests_connection",
        len(provider.tested)
        == 1,
    )

    check(
        "probe_discovers_metadata",
        len(provider.discovered)
        == 1,
    )

    check(
        "probe_returns_safe_selectable_objects",
        [
            item["qualified_name"]
            for item
            in result["objects"]
        ]
        == [
            "dbo.Clientes",
            "dbo.Ventas",
        ],
    )

    check(
        "probe_omits_columns",
        all(
            "columns"
            not in item
            for item
            in result["objects"]
        ),
    )

    check(
        "probe_deduplicates_objects",
        result[
            "discovered_object_count"
        ]
        == 2,
    )

    try:
        build_transient_sql_probe_profile(
            server="sql01",
            database="ERP",
            auth_mode="SQL_AUTH",
            username="reader",
        )

        raise AssertionError(
            "sql_auth_requires_reference"
        )

    except EnterpriseSqlError as exc:
        check(
            "sql_auth_requires_reference",
            exc.code
            == "SQL_SECRET_UNAVAILABLE",
        )


class ProbeProvider:
    instances = []

    def __init__(
        self,
        secret_store=None,
    ):
        self.secret_store = secret_store
        self.references_seen = []

        self.__class__.instances.append(
            self
        )

    def test_connection(
        self,
        profile,
        timeout_seconds,
    ):
        reference = str(
            profile.get(
                "secret_reference"
            )
            or ""
        )

        if (
            profile.get(
                "auth_mode"
            )
            == "SQL_AUTH"
        ):
            check(
                "provider_receives_transient_reference",
                reference.startswith(
                    "probe:"
                ),
            )

            check(
                "provider_can_resolve_transient_secret",
                self.secret_store.get(
                    reference
                )
                == "Sql-Probe-Secret-2026!",
            )

            self.references_seen.append(
                reference
            )

        return {
            "database":
                profile["database"]
        }

    def discover(
        self,
        profile,
    ):
        return [
            {
                "schema": "dbo",
                "name": "Ventas",
                "type": "BASE TABLE",
                "columns": [],
            },
            {
                "schema": "fin",
                "name": "Polizas",
                "type": "VIEW",
                "columns": [],
            },
        ]


def api_contract():
    old_reports = analyzer.base.REPORTES
    old_actor = analyzer._sql_admin_actor
    old_scope = analyzer._sql_admin_scope
    old_provider_class = (
        analyzer.SqlServerPyodbcProvider
    )
    old_overrides = dict(
        analyzer._sql_admin_overrides
    )
    old_events = analyzer._sql_admin_events

    with tempfile.TemporaryDirectory() as td:
        reports = (
            Path(td)
            / "Reportes"
        )

        reports.mkdir(
            parents=True,
            exist_ok=True,
        )

        store = (
            EnterpriseSqlConnectionStore(
                Path(td)
                / "sql"
            )
        )

        permissions = []

        try:
            analyzer.base.REPORTES = (
                reports
            )

            analyzer._sql_admin_actor = (
                lambda authorization, permission: (
                    permissions.append(
                        permission
                    )
                    or {
                        "user_id":
                            "admin",
                        "tenant_id":
                            "empresa",
                        "roles": [
                            "TENANT_ADMIN"
                        ],
                    }
                )
            )

            analyzer._sql_admin_scope = (
                lambda actor, tenant_id: {
                    "company_id":
                        "empresa",
                    "user_id":
                        "sql-admin",
                    "business_unit":
                        None,
                    "branch":
                        None,
                }
            )

            analyzer.SqlServerPyodbcProvider = (
                ProbeProvider
            )

            events = []

            analyzer.configure_sql_admin_services(
                store=store,
                provider=None,
                secret_store=EnterpriseSecretStore(),
                audit_events=events,
            )

            ProbeProvider.instances.clear()

            client = TestClient(
                analyzer.app
            )

            response = client.post(
                "/api/admin/sql/probe",
                headers={
                    "Authorization":
                        "Bearer test"
                },
                json={
                    "server":
                        "sql01",
                    "database":
                        "ERP",
                    "auth_mode":
                        "SQL_AUTH",
                    "username":
                        "reader",
                    "password":
                        "Sql-Probe-Secret-2026!",
                },
            )

            check(
                "probe_http_success",
                response.status_code
                == 200,
            )

            payload = response.json()

            check(
                "probe_http_status_pass",
                payload.get(
                    "status"
                )
                == "PASS",
            )

            check(
                "probe_requires_sql_configure",
                permissions
                == [
                    "sql:configure"
                ],
            )

            check(
                "probe_returns_objects",
                [
                    item[
                        "qualified_name"
                    ]
                    for item
                    in payload[
                        "objects"
                    ]
                ]
                == [
                    "dbo.Ventas",
                    "fin.Polizas",
                ],
            )

            serialized = (
                response.text.lower()
            )

            check(
                "probe_response_secret_safe",
                "sql-probe-secret-2026!"
                not in serialized
                and "password"
                not in serialized
                and "secret_reference"
                not in serialized,
            )

            scope = {
                "company_id":
                    "empresa",
                "user_id":
                    "sql-admin",
                "business_unit":
                    None,
                "branch":
                    None,
            }

            check(
                "probe_does_not_persist_profile",
                store.list(
                    scope
                )
                == [],
            )

            probe_instances = [
                item
                for item
                in ProbeProvider.instances
                if item.secret_store
                is not None
            ]

            check(
                "probe_used_request_local_secret_store",
                bool(
                    probe_instances
                ),
            )

            references = []

            for instance in probe_instances:
                references.extend(
                    instance.references_seen
                )

            check(
                "probe_secret_reference_exercised",
                len(references)
                == 1,
            )

            for reference in references:
                try:
                    value = (
                        probe_instances[
                            -1
                        ].secret_store.get(
                            reference
                        )
                    )
                except EnterpriseSqlError:
                    value = None

                check(
                    "transient_secret_destroyed",
                    value is None,
                )

            check(
                "probe_audit_safe",
                len(events)
                == 1
                and events[0][
                    "event"
                ]
                == "SQL_CONNECTION_PROBED"
                and "password"
                not in str(
                    events[0]
                ).lower()
                and "secret"
                not in str(
                    events[0]
                ).lower(),
            )

            invalid = client.post(
                "/api/admin/sql/probe",
                headers={
                    "Authorization":
                        "Bearer test"
                },
                json={
                    "server":
                        "sql01",
                    "database":
                        "ERP",
                    "auth_mode":
                        "SQL_AUTH",
                    "username":
                        "reader",
                },
            )

            check(
                "probe_missing_password_blocked",
                invalid.status_code
                == 400
                and invalid.json()[
                    "detail"
                ][
                    "code"
                ]
                == "SQL_SECRET_UNAVAILABLE",
            )

        finally:
            analyzer.base.REPORTES = (
                old_reports
            )

            analyzer._sql_admin_actor = (
                old_actor
            )

            analyzer._sql_admin_scope = (
                old_scope
            )

            analyzer.SqlServerPyodbcProvider = (
                old_provider_class
            )

            analyzer._sql_admin_overrides = (
                old_overrides
            )

            analyzer._sql_admin_events = (
                old_events
            )


if __name__ == "__main__":
    pure_gateway_contract()
    api_contract()

    print(
        "PASS GA.3-B2-B1 SAFE SQL PRE-ALLOWLIST PROBE"
    )
