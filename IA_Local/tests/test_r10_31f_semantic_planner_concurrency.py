from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

API = (
    ROOT
    / "scripts"
    / "enterprise_ai"
    / "api.py"
)

SERVICE = (
    ROOT
    / "scripts"
    / "enterprise_ai"
    / "service.py"
)


def _read(path: Path) -> str:
    return path.read_text(
        encoding="utf-8-sig"
    )


def _function(
    source: str,
    name: str,
) -> tuple[ast.AST, str]:
    tree = ast.parse(
        source
    )

    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
        and node.name == name
    ]

    assert len(matches) == 1

    node = matches[0]

    segment = ast.get_source_segment(
        source,
        node,
    )

    assert segment

    return node, segment


def test_semantic_planner_uses_service_generation_authority() -> None:
    api_source = _read(
        API
    )

    _, planner = _function(
        api_source,
        "resolve_semantic_analytics_plan",
    )

    assert "components.llm.chat(" not in planner

    assert (
        "components.service._llm_chat_with_queue("
        in planner
    )

    assert (
        "Devuelve únicamente JSON"
        in planner
    )


def test_service_queue_remains_single_generation_slot_authority() -> None:
    service_source = _read(
        SERVICE
    )

    _, queue = _function(
        service_source,
        "_llm_chat_with_queue",
    )

    assert "_generation_slots.acquire" in queue
    assert "_generation_slots.release" in queue
    assert "self.llm.chat" in queue


def test_connected_sql_fast_path_has_no_independent_semaphore() -> None:
    service_source = _read(
        SERVICE
    )

    _, connected = _function(
        service_source,
        "_connected_sql_answer",
    )

    assert "_generation_slots" not in connected
    assert "_llm_chat_with_queue" not in connected

    #
    # The semantic callback itself delegates generation to the
    # existing service authority; do not create a second semaphore
    # around the entire SQL fast path.
    #
