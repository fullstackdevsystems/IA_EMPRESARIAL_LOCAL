from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from enterprise_ai.governed_sql_assistant import GovernedSqlAssistantBridge


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS|{name}")


SCOPE = {
    "company_id": "company-a",
    "user_id": "sql-admin",
    "business_unit": None,
    "branch": None,
}

PROFILE = {
    "connection_id": "connection-a",
    "server": "SERVER-MUST-NOT-LEAK",
    "database": "DB_TEST",
    "auth_mode": "WINDOWS_INTEGRATED",
    "timeout_seconds": 30,
    "max_rows": 500,
    "allowed_schemas": ["dbo"],
    "allowed_tables": ["dbo.Clientes"],
    "read_only": True,
    "enabled": True,
    "status": "ACTIVE",
    "scope": dict(SCOPE),
}


class FakeStore:
    def list(self, scope):
        check(
            "company_scope_received",
            scope["company_id"] == "company-a",
        )
        return [dict(PROFILE)]

    def get(self, scope, connection_id):
        if connection_id != "connection-a":
            raise KeyError(connection_id)

        profile = dict(PROFILE)
        profile["scope"] = dict(scope)
        return profile


class FakeProvider:
    def __init__(self):
        self.calls = []

    def execute(
        self,
        profile,
        sql,
        parameters,
        timeout_seconds,
    ):
        self.calls.append(
            {
                "sql": sql,
                "parameters": list(parameters),
                "timeout_seconds": timeout_seconds,
            }
        )

        check(
            "only_select_executed",
            sql.upper().startswith("SELECT "),
        )

        check(
            "allowlisted_table_executed",
            "CLIENTES" in sql.upper(),
        )

        return {
            "columns": ["TOTAL_REGISTROS"],
            "rows": [[500]],
        }


provider = FakeProvider()

bridge = GovernedSqlAssistantBridge(
    store=FakeStore(),
    provider_factory=lambda: provider,
)


target = bridge.resolve(
    scope=dict(SCOPE),
    question=(
        "Usa exclusivamente la conexión SQL empresarial configurada. "
        "Consulta la tabla dbo.Clientes. "
        "¿Cuántos registros contiene actualmente? "
        "Responde exactamente con el formato TOTAL_REGISTROS=<numero>."
    ),
)

check("target_answered", target is not None)
check("target_exact_count", target["answer"] == "TOTAL_REGISTROS=500")
check("target_structured", target["retrieval"]["structured"] is True)
check("target_governed_route", target["retrieval"]["fast_path"] == "governed_sql")
check("target_source_count", len(target["sources"]) == 1)
check("target_friendly_source", target["sources"][0]["name"] == "Datos conectados")
check("target_single_execution", len(provider.calls) == 1)


natural = bridge.resolve(
    scope=dict(SCOPE),
    question="¿Cuántos clientes hay?",
)

check(
    "natural_language_count",
    natural is not None
    and natural["answer"] == "Total de registros: 500",
)

check("natural_second_execution", len(provider.calls) == 2)


before_blocked = len(provider.calls)

blocked = bridge.resolve(
    scope=dict(SCOPE),
    question="¿Cuántos registros hay en dbo.Secretos?",
)

check(
    "outside_allowlist_fail_closed",
    blocked is not None
    and "autorizada" in blocked["answer"].lower(),
)

check(
    "outside_allowlist_never_executed",
    len(provider.calls) == before_blocked,
)


plain = bridge.resolve(
    scope=dict(SCOPE),
    question="Explícame qué es inteligencia artificial.",
)

check("plain_question_falls_through", plain is None)


serialized = json.dumps(target, ensure_ascii=False)

check(
    "server_not_exposed",
    "SERVER-MUST-NOT-LEAK" not in serialized,
)

check(
    "connection_id_not_exposed",
    "connection-a" not in serialized,
)

check(
    "database_not_exposed",
    "DB_TEST" not in serialized,
)

check(
    "query_fingerprint_not_exposed",
    "query_fingerprint_sha256" not in serialized,
)


service_text = (
    SCRIPTS / "enterprise_ai" / "service.py"
).read_text(encoding="utf-8")

api_text = (
    SCRIPTS / "enterprise_ai" / "api.py"
).read_text(encoding="utf-8")

check(
    "service_bridge_hook",
    "self.connected_sql_resolver = None" in service_text
    and "def _connected_sql_answer(" in service_text,
)

check(
    "service_chat_governed_route",
    'route="governed_sql"' in service_text,
)

check(
    "service_stream_governed_route",
    '"route": "governed_sql"' in service_text,
)

check(
    "api_bridge_import",
    "GovernedSqlAssistantBridge" in api_text,
)

check(
    "api_permission_gate",
    '"sql:read"' in api_text
    and "enterprise_identity.has_permission" in api_text,
)

check(
    "api_company_scope",
    "data_connection_scope(principal)" in api_text,
)

check(
    "api_service_wiring",
    "components.service.connected_sql_resolver = resolve_connected_sql"
    in api_text,
)

print("R10_24C2_GOVERNED_SQL_ASSISTANT_BRIDGE=PASS")
