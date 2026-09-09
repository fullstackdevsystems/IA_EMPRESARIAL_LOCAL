"""RC.7K.6B - TrustServerCertificate onboarding/CLI regression."""

from pathlib import Path
import ast
import re

ROOT = Path(__file__).resolve().parents[1]

ONBOARDING = (
    ROOT
    / "scripts"
    / "enterprise_onboarding.py"
)

OPERAR = (
    ROOT.parent
    / "OperarIA.ps1"
)

onboarding = ONBOARDING.read_text(
    encoding="utf-8"
)

operar = OPERAR.read_text(
    encoding="utf-8"
)

checks = []


def ck(name, condition):
    condition = bool(condition)
    print(
        ("PASS" if condition else "FAIL"),
        name,
    )
    checks.append(condition)


tree = ast.parse(onboarding)

configure_sql = next(
    (
        node
        for node in ast.walk(tree)
        if isinstance(
            node,
            ast.FunctionDef,
        )
        and node.name == "configure_sql"
    ),
    None,
)

ck(
    "configure_sql_exists",
    configure_sql is not None,
)

parameter_names = (
    []
    if configure_sql is None
    else [
        arg.arg
        for arg
        in configure_sql.args.kwonlyargs
    ]
)

ck(
    "configure_sql_has_driver",
    "driver" in parameter_names,
)

ck(
    "configure_sql_has_trust",
    "trust_server_certificate"
    in parameter_names,
)

ck(
    "default_driver_odbc18",
    'driver="ODBC Driver 18 for SQL Server"'
    in onboarding,
)

ck(
    "register_receives_driver",
    "driver=driver"
    in onboarding,
)

ck(
    "register_receives_trust",
    "trust_server_certificate=bool(trust_server_certificate)"
    in onboarding,
)

ck(
    "cli_driver_argument",
    'parser.add_argument("--driver", default="ODBC Driver 18 for SQL Server")'
    in onboarding,
)

ck(
    "cli_trust_flag",
    'parser.add_argument("--trust-server-certificate", action="store_true")'
    in onboarding,
)

ck(
    "cli_dispatch_driver",
    "driver=args.driver"
    in onboarding,
)

ck(
    "cli_dispatch_trust",
    "trust_server_certificate=args.trust_server_certificate"
    in onboarding,
)

ck(
    "operaria_driver_parameter",
    '[string]$Driver = "ODBC Driver 18 for SQL Server"'
    in operar,
)

ck(
    "operaria_trust_switch",
    "[switch]$TrustServerCertificate"
    in operar,
)

ck(
    "operaria_forwards_driver",
    "@('--driver', $Driver)"
    in operar,
)

ck(
    "operaria_forwards_trust",
    "$TrustServerCertificate.IsPresent"
    in operar
    and "'--trust-server-certificate'"
    in operar,
)

if not all(checks):
    raise SystemExit(1)

print(
    "\nPASS RC.7K.6B TRUST SERVER CERTIFICATE CLI REGRESSION"
)
