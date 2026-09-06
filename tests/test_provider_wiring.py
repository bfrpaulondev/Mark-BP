import unittest

from core.provider_router import (
    ProviderCapability,
    ProviderName,
    ProviderRouter,
)
from core.providers.contracts import ProviderResponse, ProviderUsage


class _StubAdapter:
    """Records calls and returns a fixed text response."""

    def __init__(self, text="olá"):
        self.calls = 0
        self.text = text

    def generate_text(self, *, model, prompt, reasoning_effort="low"):
        self.calls += 1
        return ProviderResponse(
            text=self.text,
            usage=ProviderUsage(input_tokens=1, output_tokens=2, total_tokens=3),
            request_id="stub",
        )


def _router(adapters='__unset__', config=None, **kwargs) -> ProviderRouter:
    if adapters == '__unset__':
        return ProviderRouter(config or {}, **kwargs)
    return ProviderRouter(config if config is not None else {
        f"{provider}_model_{role}": f"test-{provider}-{role}"
        for provider in ("groq", "anthropic") for role in ("fast", "balanced")
    }, adapters=adapters, **kwargs)


class NewProviderWiringTests(unittest.TestCase):
    """BLOCO 12 wiring — Anthropic/Groq registered in the canonical router."""

    def test_new_provider_names_exist(self):
        self.assertEqual(ProviderName.ANTHROPIC.value, "anthropic")
        self.assertEqual(ProviderName.GROQ.value, "groq")

    def test_fallback_order_includes_new_providers(self):
        anthropic = _StubAdapter()
        groq = _StubAdapter()
        openai = _StubAdapter()
        router = _router({"openai": openai, "anthropic": anthropic, "groq": groq})
        plan = router.candidate_plan(role="fast", preference="anthropic")
        order = [candidate.provider for candidate in plan]
        self.assertEqual(order[0], ProviderName.ANTHROPIC)
        self.assertIn(ProviderName.OPENAI, order)

    def test_groq_preference_orders_groq_first(self):
        groq = _StubAdapter()
        openai = _StubAdapter()
        router = _router({"groq": groq, "openai": openai})
        plan = router.candidate_plan(role="fast", preference="groq")
        self.assertEqual(plan[0].provider, ProviderName.GROQ)

    def test_generate_text_falls_back_to_anthropic_when_openai_fails(self):
        class _Broken:
            def generate_text(self, **kwargs):
                raise RuntimeError("openai down")

        anthropic = _StubAdapter()
        router = _router({"openai": _Broken(), "anthropic": anthropic})
        result = router.generate_text(prompt="teste", preference="openai")
        self.assertTrue(result.text)
        self.assertTrue(result.used_fallback)

    def test_text_only_providers_never_selected_for_vision(self):
        anthropic = _StubAdapter()
        gemini = _StubAdapter()
        router = _router({"anthropic": anthropic, "gemini": gemini})
        plan = router.candidate_plan(
            role="vision", capability=ProviderCapability.VISION, preference="anthropic"
        )
        providers = [candidate.provider for candidate in plan]
        self.assertNotIn(ProviderName.ANTHROPIC, providers)
        self.assertEqual(providers, [ProviderName.GEMINI])

    def test_default_adapters_built_from_config_keys(self):
        from core.providers.anthropic_messages import AnthropicMessagesClient
        from core.providers.groq_chat import GroqChatClient

        router = _router(
            config={
                "anthropic_api_key": "sk-ant-test",
                "groq_api_key": "gsk-test",
            },
        )
        self.assertIsInstance(
            router._adapters.get(ProviderName.ANTHROPIC), AnthropicMessagesClient
        )
        self.assertIsInstance(router._adapters.get(ProviderName.GROQ), GroqChatClient)

    def test_missing_keys_register_nothing(self):
        router = _router(config={})
        self.assertNotIn(ProviderName.ANTHROPIC, router._adapters)
        self.assertNotIn(ProviderName.GROQ, router._adapters)


if __name__ == "__main__":
    unittest.main()
