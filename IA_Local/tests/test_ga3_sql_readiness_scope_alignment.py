"""
GA.3 regression for canonical SQL readiness scope.

The SQL connection store is governed under the synthetic
per-tenant administrative user_id "sql-admin". Readiness must
read the same scope while still accepting either SYSTEM_ADMIN
or TENANT_ADMIN as the administrative prerequisite.
"""

from pathlib import Path
import sys
import tempfile


ROOT = Path(
    __file__
).resolve().parents[2]

sys.path.insert(
    0,
    str(
        ROOT
        / "IA_Local"
        / "scripts"
    ),
)

from enterprise_onboarding import (
    EnterpriseOnboarding,
)


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print("PASS", name)


def expected_scope(tenant_id):
    return {
        "company_id": tenant_id,
        "user_id": "sql-admin",
        "business_unit": None,
        "branch": None,
    }


with tempfile.TemporaryDirectory(
    prefix="ga3_sql_scope_"
) as temporary:

    reports = (
        Path(temporary)
        / "Reportes"
    )

    onboarding = (
        EnterpriseOnboarding(
            reports
        )
    )

    onboarding.configure(
        tenant_id="services",
        tenant_name="Services",
        admin_user_id="system-admin",
        admin_username="system-admin",
        admin_display_name="System Admin",
        password="SystemPassword!1",
    )

    system_scope = (
        onboarding.sql_readiness_scope(
            "services"
        )
    )

    check(
        "system_admin_readiness_uses_sql_admin_scope",
        system_scope
        == expected_scope("services"),
    )

    check(
        "configure_sql_scope_matches_readiness_scope",
        onboarding._scope("services")
        == system_scope,
    )

    profile = onboarding.configure_sql(
        tenant_id="services",
        connection_id="primary",
        server="sql-host",
        database="enterprise",
        auth_mode="WINDOWS_INTEGRATED",
        allowed_schemas=["dbo"],
        allowed_tables=[
            "dbo.Allowed"
        ],
    )

    check(
        "configure_sql_created_profile",
        profile["connection_id"]
        == "primary"
        and profile["enabled"]
        is True
        and profile["read_only"]
        is True,
    )

    stored = onboarding.sql.list(
        system_scope
    )

    check(
        "readiness_scope_can_read_configured_profile",
        len(stored) == 1
        and stored[0][
            "connection_id"
        ]
        == "primary",
    )

    readiness = onboarding.readiness(
        "services"
    )

    check(
        "configured_sql_visible_to_readiness",
        readiness["steps"]["sql"][
            "status"
        ]
        == "CONFIGURED"
        and readiness["steps"]["sql"][
            "configured_count"
        ]
        == 1
        and readiness["steps"]["sql"][
            "tested_count"
        ]
        == 0,
    )

    check(
        "configured_not_tested_overall_contract",
        readiness["status"]
        == "CONFIGURED"
        and readiness[
            "verification_status"
        ]
        == "CONFIGURED",
    )

    onboarding.tenants.create(
        tenant_id="branchco",
        name="Branch Co",
    )

    onboarding.identity.create_user(
        user_id="branch-admin",
        username="branch-admin",
        display_name="Branch Admin",
        password="BranchPassword!1",
        tenant_id="branchco",
        roles=["TENANT_ADMIN"],
    )

    tenant_admin_scope = (
        onboarding.sql_readiness_scope(
            "branchco"
        )
    )

    check(
        "tenant_admin_also_resolves_sql_admin_scope",
        tenant_admin_scope
        == expected_scope("branchco"),
    )

    check(
        "scope_is_not_bound_to_real_admin_user_id",
        tenant_admin_scope[
            "user_id"
        ]
        != "branch-admin",
    )


print(
    "PASS GA.3 SQL READINESS SCOPE ALIGNMENT"
)
