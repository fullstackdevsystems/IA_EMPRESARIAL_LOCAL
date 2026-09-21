import sys
from pathlib import Path
from types import SimpleNamespace

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from enterprise_ai.service import EnterpriseAIService


def _service():
    service = object.__new__(EnterpriseAIService)
    return service


def _profile(num_ctx=4096, reserve=1536):
    return {
        "name": "normal",
        "generation_mode": "natural",
        "num_ctx": num_ctx,
        "reserve_output_tokens": reserve,
    }


def test_internal_context_budget_preserves_small_evidence():
    service = _service()
    built = SimpleNamespace(
        system_prompt="SYSTEM",
        evidence_text="evidencia gobernada",
    )

    messages, plan = service._build_internal_context_messages(
        "pregunta",
        built,
        _profile(),
    )

    assert plan["contract"] == "r10.25d1"
    assert plan["route"] == "internal_context"
    assert plan["evidence_truncated"] is False
    assert plan["deterministic_evidence_authority_preserved"] is True
    assert plan["llm_calculation_authority"] is False
    assert plan["estimated_input_tokens"] <= (
        plan["num_ctx"] - plan["reserve_output_tokens"]
    )
    assert messages[-1] == {"role": "user", "content": "pregunta"}
    assert any(
        "evidencia gobernada" in message["content"]
        for message in messages
    )


def test_internal_context_budget_truncates_only_evidence():
    service = _service()
    evidence = "E" * 50000
    built = SimpleNamespace(
        system_prompt="SYSTEM AUTHORITY MUST REMAIN",
        evidence_text=evidence,
    )

    messages, plan = service._build_internal_context_messages(
        "QUESTION MUST REMAIN",
        built,
        _profile(num_ctx=4096, reserve=1536),
    )

    assert plan["evidence_truncated"] is True
    assert plan["selected_evidence_tokens"] <= plan["evidence_budget_tokens"]
    assert plan["estimated_input_tokens"] <= (
        plan["num_ctx"] - plan["reserve_output_tokens"]
    )

    assert messages[0]["content"] == "SYSTEM AUTHORITY MUST REMAIN"
    assert messages[-1]["content"] == "QUESTION MUST REMAIN"
    assert len(messages[1]["content"]) < len(
        "CONTEXTO INTERNO RECUPERADO:\n" + evidence
    )


def test_internal_context_budget_is_deterministic():
    service = _service()
    built = SimpleNamespace(
        system_prompt="SYSTEM",
        evidence_text="X" * 20000,
    )

    first_messages, first_plan = service._build_internal_context_messages(
        "pregunta",
        built,
        _profile(),
    )
    second_messages, second_plan = service._build_internal_context_messages(
        "pregunta",
        built,
        _profile(),
    )

    assert first_messages == second_messages
    assert first_plan == second_plan