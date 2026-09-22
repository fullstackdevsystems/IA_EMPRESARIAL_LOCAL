from pathlib import Path
from urllib.parse import parse_qs, urlparse
import re

ROOT = Path(__file__).resolve().parents[2]

HOME_UI = (
    ROOT
    / "IA_Local"
    / "scripts"
    / "enterprise_ai"
    / "product_ui.py"
)

ASSISTANT_UI = (
    ROOT
    / "IA_Local"
    / "scripts"
    / "enterprise_ai"
    / "product_assistant_ui.py"
)


def check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name)
    print(f"{name}=PASS")


home = HOME_UI.read_text(encoding="utf-8")
assistant = ASSISTANT_UI.read_text(encoding="utf-8")

check(
    "executive_questions_heading_once",
    home.count("Preguntas para tu negocio") == 1,
)

labels = [
    "Productos en caída",
    "Clientes que dejaron de comprar",
    "¿Por qué bajaron las ventas?",
    "Atención de dirección",
]

for index, label in enumerate(labels, start=1):
    check(
        f"executive_question_{index}",
        home.count(label) == 1,
    )

links = re.findall(
    r'href="(/assistant\?prompt=[^"]+)"',
    home,
)

check(
    "four_assistant_prompt_links",
    len(links) == 4,
)

decoded_prompts = []

for index, link in enumerate(links, start=1):
    parsed = urlparse(link)
    query = parse_qs(parsed.query)

    check(
        f"assistant_path_{index}",
        parsed.path == "/assistant",
    )

    prompts = query.get("prompt", [])

    check(
        f"single_prompt_{index}",
        len(prompts) == 1,
    )

    check(
        f"nonempty_prompt_{index}",
        bool(prompts[0].strip()),
    )

    decoded_prompts.append(prompts[0].strip())

check(
    "four_distinct_prompts",
    len(set(decoded_prompts)) == 4,
)

check(
    "assistant_url_parser_once",
    assistant.count(
        "new URLSearchParams(window.location.search)"
    ) == 1,
)

check(
    "assistant_prompt_parameter_once",
    assistant.count("params.get('prompt')") == 1,
)

check(
    "assistant_prompt_loader_once",
    assistant.count("function loadPromptFromUrl()") == 1,
)

check(
    "assistant_prompt_loader_invoked_once",
    assistant.count("loadPromptFromUrl();") == 1,
)

check(
    "assistant_prompt_preload_before_session",
    "loadPromptFromUrl();\nestablishSession();" in assistant,
)

check(
    "assistant_does_not_auto_send_deep_link",
    "loadPromptFromUrl();\nsend();" not in assistant,
)

check(
    "existing_prompt_function_preserved",
    "function usePrompt(value)" in assistant,
)

check(
    "existing_session_bootstrap_preserved",
    "establishSession();" in assistant,
)

check(
    "home_app_context_preserved",
    "/api/enterprise/app-context" in home,
)

for path in [
    "/assistant",
    "/analyze",
    "/data",
    "/reports",
]:
    check(
        "workspace_" + path.strip("/"),
        f'href="{path}"' in home,
    )

print("R10_26A_EXECUTIVE_HOME_QUESTIONS=PASS")