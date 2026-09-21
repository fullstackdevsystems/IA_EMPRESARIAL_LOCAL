from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SERVICE = SCRIPTS / "enterprise_ai" / "service.py"


def check(name, condition):
    if not condition:
        raise AssertionError(name)


def method_slice(text, start_marker, end_marker=None):
    start = text.index(start_marker)
    if end_marker is None:
        return text[start:]
    end = text.index(end_marker, start)
    return text[start:end]


def main():
    text = SERVICE.read_text(encoding="utf-8")

    chat = method_slice(
        text,
        "    def chat(",
        "    def stream_general(",
    )

    stream = method_slice(
        text,
        "    def stream_general(",
    )

    # One central routing decision per execution surface.
    check(
        "chat_router_once",
        chat.count("route_enterprise_question(") == 1,
    )
    check(
        "stream_router_once",
        stream.count("route_enterprise_question(") == 1,
    )

    # Both surfaces preserve the same governed precedence inputs.
    required_inputs = (
        "governed_sql_available=connected_sql is not None",
        "direct_memory_question=self._direct_memory_question(message)",
        "system_capabilities_question=self._looks_system_capabilities(message)",
        "general_knowledge_question=self._looks_general_knowledge(message)",
    )

    for token in required_inputs:
        check(
            f"chat_input_{token}",
            token in chat,
        )
        check(
            f"stream_input_{token}",
            token in stream,
        )

    # Streaming executes only the routes it already supported directly.
    check(
        "stream_governed_sql_gate",
        'if route_decision.route == "governed_sql":' in stream,
    )
    check(
        "stream_system_capabilities_gate",
        'if route_decision.route == "system_capabilities":' in stream,
    )
    check(
        "stream_general_llm_gate",
        'if route_decision.route != "general_llm":' in stream,
    )

    # Memory/internal enterprise questions continue through the existing
    # fallback contract rather than adding RAG/memory execution to streaming.
    check(
        "stream_fallback_event",
        '"type": "fallback"' in stream,
    )
    check(
        "stream_fallback_route",
        '"route": route_decision.route' in stream,
    )
    check(
        "no_stream_memory_search",
        "self.memory.search_lexical(" not in stream,
    )
    check(
        "no_stream_context_build",
        "self.context.build(" not in stream,
    )

    # Classifier decisions must no longer independently gate streaming.
    check(
        "no_direct_capabilities_gate",
        "if self._looks_system_capabilities(message):" not in stream,
    )
    check(
        "no_direct_general_gate",
        "if not self._looks_general_knowledge(message):" not in stream,
    )

    # Existing public event routes remain intact.
    check(
        "governed_sql_event_route",
        '"route": "governed_sql"' in stream,
    )
    check(
        "system_capabilities_event_route",
        '"route": "system_capabilities"' in stream,
    )
    check(
        "general_llm_event_route",
        '"route": "general_llm"' in stream,
    )

    print("R10_25B2_STREAMING_ROUTING_CONTRACT=PASS")


if __name__ == "__main__":
    main()