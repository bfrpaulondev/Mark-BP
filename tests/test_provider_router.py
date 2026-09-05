import unittest

from core.provider_router import (
    ProviderCapability,
    ProviderExhaustedError,
    ProviderName,
    ProviderRole,
    ProviderRouter,
    clear_provider_router_cache,
    get_provider_router,
)


class _FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += float(seconds)


class _FakeAdapter:
    def __init__(self, *, text_events=None, vision_events=None):
        self.text_events = list(text_events or [])
        self.vision_events = list(vision_events or [])
        self.text_calls = []
        self.vision_calls = []

    def generate_text(self, *, model, prompt, reasoning_effort="low"):
        self.text_calls.append((model, prompt, reasoning_effort))
        event = self.text_events.pop(0) if self.text_events else "ok"
        if isinstance(event, Exception):
            raise event
        return event

    def analyze_image(
        self,
        *,
        model,
        prompt,
        image_bytes,
        mime_type="image/jpeg",
        detail="low",
        reasoning_effort="low",
    ):
        self.vision_calls.append(
            (model, prompt, bytes(image_bytes), mime_type, detail, reasoning_effort)
        )
        event = self.vision_events.pop(0) if self.vision_events else "vision-ok"
        if isinstance(event, Exception):
            raise event
        return event


class ProviderRouterPlanTests(unittest.TestCase):
    def setUp(self):
        self.openai = _FakeAdapter()
        self.gemini = _FakeAdapter()
        self.config = {
            "model_provider_preference": "auto",
            "openai_model_fast": "oa-fast",
            "openai_model_balanced": "oa-balanced",
            "openai_model_expert": "oa-expert",
            "gemini_model_fast": "gm-fast",
            "gemini_model_balanced": "gm-balanced",
            "gemini_model_expert": "gm-expert",
            "gemini_model_critic": "gm-critic",
            "gemini_model_vision": "gm-vision",
        }
        self.router = ProviderRouter(
            self.config,
            adapters={"openai": self.openai, "gemini": self.gemini},
            sleeper=lambda _: None,
        )

    def test_auto_fast_prefers_gemini_for_low_cost_path(self):
        plan = self.router.candidate_plan(role="fast")
        self.assertEqual(
            [item.provider for item in plan],
            [ProviderName.GEMINI, ProviderName.OPENAI],
        )
        self.assertEqual(plan[0].model, "gm-fast")

    def test_auto_expert_and_critic_prefer_openai_specialist(self):
        expert = self.router.candidate_plan(role=ProviderRole.EXPERT)
        critic = self.router.candidate_plan(role=ProviderRole.CRITIC)
        self.assertEqual(expert[0].provider, ProviderName.OPENAI)
        self.assertEqual(expert[0].model, "oa-expert")
        self.assertEqual(critic[0].provider, ProviderName.OPENAI)
        self.assertEqual(critic[0].model, "oa-balanced")

    def test_explicit_preference_means_prefer_and_keeps_fallback(self):
        plan = self.router.candidate_plan(role="expert", preference="gemini")
        self.assertEqual(
            [item.provider for item in plan],
            [ProviderName.GEMINI, ProviderName.OPENAI],
        )

    def test_missing_preferred_provider_uses_configured_fallback(self):
        router = ProviderRouter(
            self.config,
            adapters={"gemini": self.gemini},
            sleeper=lambda _: None,
        )
        plan = router.candidate_plan(role="expert", preference="openai")
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0].provider, ProviderName.GEMINI)


class ProviderRouterExecutionTests(unittest.TestCase):
    def test_transient_failure_retries_then_falls_back(self):
        openai = _FakeAdapter(
            text_events=[
                RuntimeError("HTTP 503 unavailable"),
                RuntimeError("HTTP 503 unavailable"),
            ]
        )
        gemini = _FakeAdapter(text_events=["fallback-answer"])
        sleeps = []
        router = ProviderRouter(
            {"model_provider_preference": "auto"},
            adapters={"openai": openai, "gemini": gemini},
            sleeper=sleeps.append,
            breaker_threshold=2,
        )

        result = router.generate_text(prompt="hard problem", role="expert")

        self.assertEqual(result.text, "fallback-answer")
        self.assertEqual(result.provider, "gemini")
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.fallback_count, 1)
        self.assertEqual(len(openai.text_calls), 2)
        self.assertEqual(len(gemini.text_calls), 1)
        self.assertEqual(len(sleeps), 1)
        self.assertEqual([item.ok for item in result.attempts], [False, False, True])
        self.assertTrue(router.health_snapshot()["openai"]["circuit_open"])

    def test_empty_response_is_not_recorded_as_success_before_retry(self):
        openai = _FakeAdapter(text_events=["", "usable"])
        router = ProviderRouter(
            {},
            adapters={"openai": openai},
            sleeper=lambda _: None,
        )

        result = router.generate_text(prompt="task", role="expert")

        self.assertEqual(result.text, "usable")
        self.assertEqual(len(result.attempts), 2)
        self.assertFalse(result.attempts[0].ok)
        self.assertEqual(result.attempts[0].error_class, "empty_response")
        self.assertTrue(result.attempts[0].retryable)
        self.assertTrue(result.attempts[1].ok)

    def test_non_retryable_auth_failure_falls_back_without_retry(self):
        openai = _FakeAdapter(text_events=[RuntimeError("HTTP 401 invalid api key")])
        gemini = _FakeAdapter(text_events=["gemini-answer"])
        router = ProviderRouter(
            {},
            adapters={"openai": openai, "gemini": gemini},
            sleeper=lambda _: self.fail("auth failure must not retry"),
        )

        result = router.generate_text(prompt="task", role="expert")

        self.assertEqual(result.provider, "gemini")
        self.assertEqual(len(openai.text_calls), 1)
        self.assertEqual(result.attempts[0].error_class, "provider_auth")
        self.assertFalse(result.attempts[0].retryable)

    def test_request_rejection_does_not_open_global_circuit(self):
        openai = _FakeAdapter(text_events=[RuntimeError("HTTP 400 bad request")])
        gemini = _FakeAdapter(text_events=["answer"])
        router = ProviderRouter(
            {},
            adapters={"openai": openai, "gemini": gemini},
            sleeper=lambda _: None,
            breaker_threshold=1,
        )

        router.generate_text(prompt="task", role="expert")

        health = router.health_snapshot()["openai"]
        self.assertFalse(health["circuit_open"])
        self.assertEqual(health["consecutive_failures"], 0)

    def test_open_circuit_skips_provider_until_cooldown(self):
        clock = _FakeClock()
        openai = _FakeAdapter(
            text_events=[RuntimeError("HTTP 503 unavailable"), "recovered-openai"]
        )
        gemini = _FakeAdapter(
            text_events=["first-fallback", "second-fallback"]
        )
        router = ProviderRouter(
            {},
            adapters={"openai": openai, "gemini": gemini},
            max_attempts_per_provider=1,
            breaker_threshold=1,
            breaker_cooldown_seconds=20,
            clock=clock,
            sleeper=lambda _: None,
        )

        first = router.generate_text(prompt="one", role="expert")
        second = router.generate_text(prompt="two", role="expert")
        self.assertEqual(first.provider, "gemini")
        self.assertEqual(second.provider, "gemini")
        self.assertEqual(len(openai.text_calls), 1)

        clock.advance(21)
        third = router.generate_text(prompt="three", role="expert")
        self.assertEqual(third.provider, "openai")
        self.assertEqual(third.text, "recovered-openai")
        self.assertFalse(router.health_snapshot()["openai"]["circuit_open"])

    def test_success_after_transient_retry_resets_health(self):
        openai = _FakeAdapter(
            text_events=[TimeoutError("timeout"), "ok-after-retry"]
        )
        router = ProviderRouter(
            {},
            adapters={"openai": openai},
            breaker_threshold=3,
            sleeper=lambda _: None,
        )

        result = router.generate_text(prompt="task", role="expert")

        self.assertEqual(result.text, "ok-after-retry")
        health = router.health_snapshot()["openai"]
        self.assertEqual(health["consecutive_failures"], 0)
        self.assertEqual(health["last_error_class"], "")

    def test_vision_does_not_serialize_image_or_prompt_in_metadata(self):
        gemini = _FakeAdapter(vision_events=["screen-result"])
        router = ProviderRouter(
            {},
            adapters={"gemini": gemini},
            sleeper=lambda _: None,
        )
        secret_image = b"private-image-bytes"

        result = router.analyze_image(
            prompt="find the button",
            image_bytes=secret_image,
            role="vision",
        )

        self.assertEqual(result.capability, ProviderCapability.VISION.value)
        self.assertEqual(result.text, "screen-result")
        self.assertNotIn("private-image-bytes", str(result.safe_metadata()))
        self.assertNotIn("find the button", str(result.safe_metadata()))

    def test_exhausted_error_does_not_echo_prompt_or_secret_content(self):
        secret = "TOP-SECRET-PROMPT-VALUE"
        router = ProviderRouter({}, adapters={}, sleeper=lambda _: None)

        with self.assertRaises(ProviderExhaustedError) as caught:
            router.generate_text(prompt=secret, role="expert")

        self.assertNotIn(secret, str(caught.exception))
        self.assertEqual(caught.exception.attempts, ())

    def test_invalid_requests_stop_before_provider_dispatch(self):
        adapter = _FakeAdapter()
        router = ProviderRouter({}, adapters={"openai": adapter})

        with self.assertRaises(ValueError):
            router.generate_text(prompt="", role="fast")
        with self.assertRaises(ValueError):
            router.analyze_image(prompt="vision", image_bytes=b"")

        self.assertEqual(adapter.text_calls, [])
        self.assertEqual(adapter.vision_calls, [])

    def test_safe_health_snapshot_contains_no_credentials_or_prompt_data(self):
        router = ProviderRouter(
            {
                "openai_api_key": "super-secret",
                "gemini_api_key": "other-secret",
            },
            adapters={"openai": _FakeAdapter(), "gemini": _FakeAdapter()},
        )
        text = str(router.health_snapshot())
        self.assertNotIn("super-secret", text)
        self.assertNotIn("other-secret", text)


class ProviderRouterCacheTests(unittest.TestCase):
    def tearDown(self):
        clear_provider_router_cache()

    def test_same_runtime_configuration_reuses_health_router(self):
        config = {
            "openai_api_key": "key-one",
            "openai_model_fast": "fast-one",
        }
        first = get_provider_router(config)
        second = get_provider_router(dict(config))
        self.assertIs(first, second)

    def test_key_rotation_rebuilds_router_without_exposing_key(self):
        first = get_provider_router({"openai_api_key": "key-one"})
        second = get_provider_router({"openai_api_key": "key-two"})
        self.assertIsNot(first, second)
        self.assertNotIn("key-two", str(second.health_snapshot()))

    def test_model_configuration_change_rebuilds_router(self):
        first = get_provider_router(
            {"openai_api_key": "key", "openai_model_fast": "one"}
        )
        second = get_provider_router(
            {"openai_api_key": "key", "openai_model_fast": "two"}
        )
        self.assertIsNot(first, second)


if __name__ == "__main__":
    unittest.main()
