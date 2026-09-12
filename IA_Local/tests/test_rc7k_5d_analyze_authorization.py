"""RC.7K.5D - commercial /api/analyze authorization regression."""

from pathlib import Path
import ast
import re

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "scripts" / "analizador_app.py"
UNIVERSAL = ROOT / "scripts" / "analizador_universal.py"
IDENTITY = ROOT / "scripts" / "enterprise_identity.py"

app = APP.read_text(encoding="utf-8")
universal = UNIVERSAL.read_text(encoding="utf-8")
identity = IDENTITY.read_text(encoding="utf-8")

checks = []

def ck(name, condition):
    condition = bool(condition)
    print(("PASS" if condition else "FAIL"), name)
    checks.append(condition)

ck(
    "permission_exists",
    "analysis:run" in identity or "analysis:run" in universal,
)

app_tree = ast.parse(app)

analyze_node = next(
    (
        node
        for node in ast.walk(app_tree)
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "api_analyze"
    ),
    None,
)

authorization_arg = None
authorization_default = None

if analyze_node is not None:
    positional_args = list(
        analyze_node.args.posonlyargs
    ) + list(
        analyze_node.args.args
    )

    defaults = [None] * (
        len(positional_args)
        - len(analyze_node.args.defaults)
    ) + list(
        analyze_node.args.defaults
    )

    for argument, default in zip(
        positional_args,
        defaults,
    ):
        if argument.arg == "authorization":
            authorization_arg = argument
            authorization_default = default
            break

authorization_is_header = (
    authorization_arg is not None
    and isinstance(
        authorization_default,
        ast.Call,
    )
    and isinstance(
        authorization_default.func,
        ast.Name,
    )
    and authorization_default.func.id == "Header"
)

ck(
    "analyze_has_authorization_header",
    authorization_is_header,
)

ck(
    "analyze_fail_closed_guard",
    "ANALYZE_AUTH_GUARD_UNAVAILABLE" in app
    and "authorizer(authorization)" in app,
)

route_start = app.index('@app.post("/api/analyze")')
route_end = app.find('@app.', route_start + 10)
if route_end < 0:
    route_end = len(app)

route = app[route_start:route_end]

ck(
    "auth_before_upload_write",
    route.index("authorizer(authorization)")
    < route.index('dest = unique_path('),
)

ck(
    "commercial_guard_installed",
    "def _authorize_analysis(" in universal
    and 'has_permission(actor, "analysis:run")' in universal
    and "base.ANALYZE_AUTHORIZER = _authorize_analysis" in universal,
)

ck(
    "permission_denied_is_403",
    '"ANALYSIS_PERMISSION_DENIED"' in universal
    and "status_code=403" in universal,
)

ck(
    "frontend_sends_bearer",
    "window.__IA_ANALYZE_TOKEN__" in app
    and "'Authorization':'Bearer '+window.__IA_ANALYZE_TOKEN__" in app,
)

ck(
    "frontend_has_login",
    'id="ia-analyze-auth"' in universal
    and "/api/auth/login" in universal
    and "async function login()" in universal,
)

login_start = universal.index(
    "async function login()"
)
login_end = universal.index(
    "button.addEventListener(",
    login_start,
)
login_block = universal[
    login_start:login_end
]

ck(
    "frontend_token_memory_only",
    re.search(
        r"window\.__IA_ANALYZE_TOKEN__\s*=\s*"
        r"String\s*\(\s*data\.token\s*\)",
        login_block,
    )
    is not None
    and "localStorage" not in login_block
    and "sessionStorage.setItem" not in login_block,
)

ck(
    "enterprise_session_storage_is_scoped",
    "sessionStorage.setItem(" in universal
    and "'iaEnterpriseSession'" in universal
    and "localStorage" not in universal,
)

ck(
    "password_cleared_after_login",
    "pass.value = ''" in universal,
)

if not all(checks):
    raise SystemExit(1)

print("\nPASS RC.7K.5D ANALYZE AUTHORIZATION REGRESSION")
