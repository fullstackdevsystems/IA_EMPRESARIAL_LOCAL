from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[2]

api_path = (
    ROOT
    / "IA_Local"
    / "scripts"
    / "enterprise_ai"
    / "api.py"
)

ui_path = (
    ROOT
    / "IA_Local"
    / "scripts"
    / "enterprise_ai"
    / "product_assistant_ui.py"
)

api = api_path.read_text(encoding="utf-8")
ui = ui_path.read_text(encoding="utf-8")

ast.parse(api)
ast.parse(ui)

checks = []

def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)

check(
    "product_assistant_import",
    "from .product_assistant_ui import PRODUCT_ASSISTANT_HTML"
    in api,
)

check(
    "assistant_product_route",
    '@router.get("/assistant", response_class=HTMLResponse)'
    in api
    and "return PRODUCT_ASSISTANT_HTML" in api,
)

check(
    "legacy_preserved",
    '"/assistant/legacy"' in api
    and "return ASSISTANT_HTML" in api,
)

for value in [
    "Pregunta a tu empresa",
    "Resumen ejecutivo",
    "Qué revisar hoy",
    "Tendencias y alertas",
    "Información disponible",
    "Privacidad empresarial",
    "/api/enterprise/chat/stream",
    "/api/enterprise/app-context",
    "/api/enterprise/documents",
    "/api/enterprise/datasets",
    "iaEnterpriseSession",
    "mobile-nav",
]:
    check(
        f"required:{value}",
        value in ui,
    )

for value in [
    "V8.5.5 Base Productiva + Streaming",
    "Fuentes del workspace",
    "Deliverables / Reportes",
    "Documentos / RAG",
    "Bindings analíticos",
    "Contexto base LLM",
    "Proveedor LLM",
]:
    check(
        f"technical_copy_hidden:{value}",
        value not in ui,
    )

for route in [
    'href="/app"',
    'href="/assistant"',
    'href="/analyze"',
    'href="/data"',
    'href="/reports"',
    'href="/settings"',
]:
    check(
        f"nav:{route}",
        route in ui,
    )

check(
    "responsive",
    "@media(max-width:820px)" in ui
    and "@media(max-width:560px)" in ui,
)

check(
    "permission_settings",
    "capabilities.settings" in ui,
)

check(
    "feedback_preserved",
    "/api/enterprise/feedback" in ui,
)

print(
    f"R10_24A2_CONTRACT=PASS checks={len(checks)}"
)
print("PROFESSIONAL_ASSISTANT=PASS")
print("LEGACY_CAPABILITY_PRESERVED=YES")
print("TECHNICAL_COPY_HIDDEN=YES")
print("RESPONSIVE_CONTRACT=PASS")