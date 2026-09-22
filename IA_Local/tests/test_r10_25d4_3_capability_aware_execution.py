from enterprise_ai.service import EnterpriseAIService


def _service(provider):
    service = object.__new__(EnterpriseAIService)
    service.llm = provider
    return service


class GovernedProvider:
    name = "probe"
    model = "probe-model"

    def __init__(self, *, request_num_ctx, completion_metadata):
        self._request_num_ctx = request_num_ctx
        self._completion_metadata = completion_metadata
        self.last_completion = {"done_reason": "length"}

    def capabilities(self):
        return {
            "contract": "r10.25d4",
            "provider": self.name,
            "model": self.model,
            "native_streaming": True,
            "json_mode": True,
            "request_num_ctx": self._request_num_ctx,
            "completion_metadata": self._completion_metadata,
        }


class LegacyProvider:
    name = "legacy"
    model = "legacy-model"
    last_completion = {"done_reason": "length"}


class BrokenCapabilityProvider(LegacyProvider):
    def capabilities(self):
        raise RuntimeError("capability probe failed")


def test_num_ctx_is_forwarded_only_when_explicitly_supported():
    supported = _service(
        GovernedProvider(request_num_ctx=True, completion_metadata=True)
    )
    unsupported = _service(
        GovernedProvider(request_num_ctx=False, completion_metadata=True)
    )

    assert supported._provider_num_ctx(16384) == 16384
    assert unsupported._provider_num_ctx(16384) is None


def test_completion_metadata_is_read_only_when_explicitly_supported():
    supported = _service(
        GovernedProvider(request_num_ctx=True, completion_metadata=True)
    )
    unsupported = _service(
        GovernedProvider(request_num_ctx=True, completion_metadata=False)
    )

    assert supported._provider_done_reason() == "length"
    assert unsupported._provider_done_reason() is None


def test_legacy_provider_fails_closed():
    service = _service(LegacyProvider())

    caps = service._llm_capabilities()

    assert caps["request_num_ctx"] is False
    assert caps["completion_metadata"] is False
    assert service._provider_num_ctx(8192) is None
    assert service._provider_done_reason() is None


def test_capability_probe_failure_fails_closed():
    service = _service(BrokenCapabilityProvider())

    caps = service._llm_capabilities()

    assert caps["request_num_ctx"] is False
    assert caps["completion_metadata"] is False
    assert service._provider_num_ctx(8192) is None
    assert service._provider_done_reason() is None

def test_inherited_base_capabilities_preserve_legacy_completion_metadata():
    from enterprise_ai.providers import LLMProvider

    class LegacyLLMProviderSubclass(LLMProvider):
        name = "legacy-subclass"
        model = "legacy-subclass-model"

        def __init__(self):
            self.last_completion = {"done_reason": "length"}

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

    service = _service(LegacyLLMProviderSubclass())

    # num_ctx remains fail-closed because the legacy provider never declared
    # request-level context support.
    assert service._provider_num_ctx(16384) is None

    # Completion metadata preserves the pre-D4 behavior for legacy subclasses
    # that expose last_completion but only inherit the base capability contract.
    assert service._provider_done_reason() == "length"
