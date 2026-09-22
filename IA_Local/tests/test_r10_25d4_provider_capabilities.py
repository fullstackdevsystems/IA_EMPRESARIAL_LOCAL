from enterprise_ai.providers import LLMProvider, LMStudioProvider, OllamaProvider


class FallbackProvider(LLMProvider):
    name = "fallback-probe"
    model = "fallback-model"

    def chat(
        self,
        messages,
        *,
        json_mode=False,
        max_tokens=None,
        temperature=None,
        num_ctx=None,
    ):
        return "ok"


def test_base_provider_capabilities_fail_closed():
    caps = FallbackProvider().capabilities()

    assert caps == {
        "contract": "r10.25d4",
        "provider": "fallback-probe",
        "model": "fallback-model",
        "native_streaming": False,
        "json_mode": False,
        "request_num_ctx": False,
        "completion_metadata": False,
    }


def test_ollama_declares_only_implemented_execution_capabilities():
    provider = OllamaProvider(
        "http://127.0.0.1:11434",
        "qwen3:4b-instruct",
        num_ctx=4096,
    )

    assert provider.capabilities() == {
        "contract": "r10.25d4",
        "provider": "ollama",
        "model": "qwen3:4b-instruct",
        "native_streaming": True,
        "json_mode": True,
        "request_num_ctx": True,
        "completion_metadata": True,
    }


def test_lmstudio_does_not_claim_num_ctx_or_completion_metadata():
    provider = LMStudioProvider(
        "http://127.0.0.1:1234/v1",
        "qwen3-4b-instruct-2507",
    )

    assert provider.capabilities() == {
        "contract": "r10.25d4",
        "provider": "lmstudio",
        "model": "qwen3-4b-instruct-2507",
        "native_streaming": True,
        "json_mode": True,
        "request_num_ctx": False,
        "completion_metadata": False,
    }
