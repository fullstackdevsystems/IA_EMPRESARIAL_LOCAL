from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(
        0,
        str(SCRIPTS),
    )


from enterprise_ai.admin_console import (
    UNIFIED_ADMIN_HTML,
)


def check(name, condition):
    if not condition:
        raise AssertionError(name)

    print(
        "PASS",
        name,
    )


html = UNIFIED_ADMIN_HTML


check(
    "guided_sql_card_present",
    'id="guidedSqlCard"'
    in html,
)

check(
    "guided_sql_customer_labels",
    "Conectar SQL Server"
    in html
    and "Probar conexión y buscar tablas"
    in html
    and "Elegir tablas"
    in html
    and "Guardar fuente SQL"
    in html,
)

check(
    "guided_sql_simple_fields",
    'id="gsSqlServer"'
    in html
    and 'id="gsSqlDatabase"'
    in html
    and 'id="gsSqlAuth"'
    in html,
)

check(
    "guided_sql_auth_fields",
    'id="gsSqlUsername"'
    in html
    and 'id="gsSqlSecret"'
    in html,
)

check(
    "secret_change_invalidates_probe",
    'id="gsSqlSecret" type="password" '
    'autocomplete="new-password" '
    'oninput="guidedSqlInvalidate()"'
    in html,
)

check(
    "probe_endpoint_used",
    "'/api/admin/sql/probe'"
    in html,
)

check(
    "probe_uses_tenant_context",
    "'/api/admin/sql/probe'+controlTenantQuery()"
    in html,
)

check(
    "guided_sql_probe_function",
    "async function guidedSqlProbe()"
    in html,
)

check(
    "guided_sql_save_function",
    "async function guidedSqlSave()"
    in html,
)

check(
    "guided_sql_requires_permission",
    "if(!can('sql:configure'))return;"
    in html,
)

check(
    "selection_is_visual",
    'class="gsSqlObject"'
    in html
    and "guidedSqlSelectAll"
    in html,
)

check(
    "allowlist_derived_from_selection",
    "allowed_schemas:schemas"
    in html
    and "allowed_tables:objects"
    in html,
)

check(
    "connection_id_is_derived",
    "function guidedSqlConnectionId()"
    in html
    and "connection_id:guidedSqlConnectionId()"
    in html,
)

check(
    "advanced_form_preserved",
    'id="cpSqlCreate"'
    in html
    and 'id="cpSqlId"'
    in html
    and 'id="cpSqlSchemas"'
    in html
    and 'id="cpSqlTables"'
    in html
    and "async function controlCreateSql()"
    in html,
)

check(
    "advanced_form_collapsed",
    'data-cp-advanced-sql="true"'
    in html
    and "controlToggleSqlAdvanced"
    in html,
)

check(
    "advanced_mode_default_off",
    "let CONTROL_SQL_ADVANCED=false;"
    in html,
)

check(
    "advanced_toggle_rerenders_list",
    "CONTROL_SQL_ADVANCED=!CONTROL_SQL_ADVANCED;"
    in html
    and "controlRenderSqlTable()"
    in html,
)

renderer_start = html.find(
    "function controlRenderSqlTable(){"
)

renderer_end = html.find(
    "async function controlLoadSql(){",
    renderer_start,
)

check(
    "customer_list_renderer_present",
    renderer_start >= 0
    and renderer_end > renderer_start,
)

renderer = (
    html[
        renderer_start:renderer_end
    ]
    if (
        renderer_start >= 0
        and renderer_end > renderer_start
    )
    else ""
)

check(
    "customer_list_renderer_semantic_columns",
    "'Fuente'"
    in renderer
    and "'display_name'"
    in renderer
    and "'Base de datos'"
    in renderer
    and "'database'"
    in renderer,
)

check(
    "customer_primary_action_is_friendly",
    "if(!CONTROL_SQL_ADVANCED)"
    in html
    and "Comprobar conexión"
    in html,
)

check(
    "technical_table_preserved_only_for_advanced_mode",
    "if(CONTROL_SQL_ADVANCED)"
    in html
    and "['Conexion','connection_id']"
    in html
    and "['Max filas','max_rows']"
    in html
    and "'secret_configured'"
    in html,
)

check(
    "advanced_actions_preserved",
    "Allowlist"
    in html
    and "Rotar secret"
    in html
    and "Descubrir"
    in html,
)

guided_html = html.split(
    '<div class="card guided-sql"',
    1,
)[1].split(
    '<div class="card table"><h3>Fuentes SQL Server</h3>',
    1,
)[0]

check(
    "guided_card_hides_internal_identifiers",
    "connection_id"
    not in guided_html
    and "allowed_schemas"
    not in guided_html
    and "allowed_tables"
    not in guided_html
    and "max_rows"
    not in guided_html,
)

check(
    "no_local_storage",
    "localStorage"
    not in html,
)

check(
    "session_storage_preserved",
    "sessionStorage"
    in html,
)

check(
    "password_not_persisted_client_side",
    "sessionStorage.setItem('gsSqlSecret'"
    not in html
    and "localStorage.setItem('gsSqlSecret'"
    not in html,
)

check(
    "safe_error_parser",
    "detail.message"
    in html
    and "detail.code"
    in html,
)

check(
    "readiness_refresh_after_save",
    "controlLoadReadiness(false)"
    in html,
)

check(
    "legacy_sql_create_preserved",
    "'/api/admin/sql/connections'+controlTenantQuery()"
    in html,
)


print(
    "PASS GA.3-B2-B2 GUIDED SQL VISUAL UX"
)
