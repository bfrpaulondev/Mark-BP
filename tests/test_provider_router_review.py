import unittest
from unittest.mock import patch
from core.provider_router import (ProviderRouter, ProviderRole, ProviderName,
    ProviderExhaustedError, get_provider_router, clear_provider_router_cache)
from core.providers.contracts import ProviderResponse, ProviderUsage


class Adapter:
    def __init__(self, error=None):
        self.models = []
        self.error = error
    def generate_text(self, **kwargs):
        self.models.append(kwargs['model'])
        if self.error: raise self.error
        return ProviderResponse(text='ok', usage=ProviderUsage(input_tokens=1, output_tokens=1))


class RouterReviewTests(unittest.TestCase):
    def tearDown(self):
        clear_provider_router_cache()

    def test_auto_single_text_provider_resolves_each_explicit_role_model(self):
        for provider in ('groq', 'anthropic'):
            for role in ProviderRole:
                with self.subTest(provider=provider, role=role):
                    model = f'fixture-{provider}-{role.value}'
                    adapter = Adapter()
                    router = ProviderRouter({f'{provider}_model_{role.value}': model,
                        'gemini_model_balanced': 'wrong-provider'}, adapters={provider: adapter})
                    result = router.generate_text(prompt='test', role=role)
                    self.assertEqual(result.provider, provider)
                    self.assertEqual(adapter.models, [model])
                    self.assertIsNone(result.task_estimated_cost_usd)
                    self.assertFalse(result.cost_complete)

    def test_missing_or_whitespace_model_skips_candidate(self):
        for provider in ('groq', 'anthropic'):
            for value in ('', '   ', None):
                router = ProviderRouter({f'{provider}_model_fast': value}, adapters={provider: Adapter()})
                self.assertEqual(router.candidate_plan(role='fast'), ())
                with self.assertRaises(ProviderExhaustedError):
                    router.generate_text(prompt='test', role='fast')

    def test_explicit_preference_falls_back_to_other_text_provider(self):
        for preferred, fallback in (('groq', 'anthropic'), ('anthropic', 'groq')):
            router = ProviderRouter({f'{p}_model_balanced': f'fixture-{p}' for p in (preferred, fallback)},
                adapters={preferred: Adapter(RuntimeError('HTTP 401')), fallback: Adapter()})
            result = router.generate_text(prompt='test', preference=preferred)
            self.assertEqual(result.provider, fallback)
            self.assertTrue(result.used_fallback)
            self.assertEqual(len(result.attempts), 2)

    def test_circuit_opens_skips_and_recovers_for_each_new_provider(self):
        for provider in ('groq', 'anthropic'):
            now = [10.0]
            adapter = Adapter(TimeoutError())
            router = ProviderRouter({f'{provider}_model_balanced': 'fixture-model'}, adapters={provider: adapter},
                max_attempts_per_provider=1, breaker_threshold=1, breaker_cooldown_seconds=5,
                clock=lambda: now[0], sleeper=lambda _: None)
            for _ in range(2):
                with self.assertRaises(ProviderExhaustedError): router.generate_text(prompt='test')
            self.assertEqual(len(adapter.models), 1)
            health = router.health_snapshot()
            self.assertEqual(set(health), {p.value for p in ProviderName})
            self.assertTrue(health[provider]['circuit_open'])
            self.assertEqual(health[provider]['last_error_class'], 'transient_provider')
            now[0] += 6
            adapter.error = None
            self.assertEqual(router.generate_text(prompt='test').provider, provider)
            self.assertFalse(router.health_snapshot()[provider]['circuit_open'])

    def test_retries_are_bounded(self):
        for provider in ('groq', 'anthropic'):
            adapter = Adapter(TimeoutError())
            router = ProviderRouter({f'{provider}_model_balanced': 'fixture-model'},
                adapters={provider: adapter}, sleeper=lambda _: None)
            with self.assertRaises(ProviderExhaustedError) as error: router.generate_text(prompt='test')
            self.assertEqual(len(error.exception.attempts), 2)

    def test_key_and_role_model_rotations_rebuild_cache_for_all_four_providers(self):
        with patch.object(ProviderRouter, '_build_default_adapters', return_value={}):
            for provider in ProviderName:
                for field in [f'{provider.value}_api_key', *[f'{provider.value}_model_{r.value}' for r in ProviderRole]]:
                    before = get_provider_router({field: 'old-fixture'})
                    self.assertIs(before, get_provider_router({field: 'old-fixture'}))
                    self.assertIsNot(before, get_provider_router({field: 'new-fixture'}))

    def test_no_text_only_provider_selected_for_any_vision_preference(self):
        config = {f'{p}_model_{r.value}': 'fixture-model' for p in ('anthropic','groq') for r in ProviderRole}
        for preference in ('auto', 'openai', 'gemini', 'anthropic', 'groq'):
            for role in ProviderRole:
                router = ProviderRouter(config, adapters={'groq': Adapter(), 'anthropic': Adapter()})
                self.assertEqual(router.candidate_plan(role=role, capability='vision', preference=preference), ())

    def test_existing_auto_priority_is_preserved(self):
        router = ProviderRouter({}, adapters={'openai': Adapter(), 'gemini': Adapter()})
        self.assertEqual([c.provider.value for c in router.candidate_plan(role='fast')], ['gemini', 'openai'])
        self.assertEqual([c.provider.value for c in router.candidate_plan(role='expert')], ['openai', 'gemini'])


class ProviderRuntimeConfigurationTests(unittest.TestCase):
    def test_runtime_config_accepts_new_preferences_and_environment_keys_and_models(self):
        import os
        import tempfile
        from pathlib import Path
        from config.settings import load_config, load_settings
        for provider in ('groq', 'anthropic'):
            values = {f'ANTONELLA_{provider.upper()}_API_KEY': 'fixture-secret',
                      f'ANTONELLA_{provider.upper()}_MODEL_BALANCED': 'fixture-model',
                      'ANTONELLA_MODEL_PROVIDER_PREFERENCE': provider}
            with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, values, clear=True):
                path = Path(directory) / 'config.json'
                config = load_config(path)
                self.assertNotIn('fixture-secret', repr(load_settings(path)))
                with patch.object(ProviderRouter, '_build_default_adapters', return_value={ProviderName(provider): Adapter()}):
                    router = ProviderRouter(config)
                result = router.generate_text(prompt='test')
                self.assertEqual(result.provider, provider)
                self.assertEqual(result.model, 'fixture-model')

    def test_all_adapter_5xx_statuses_retry_and_trip_breaker(self):
        for status in (501, 529, 599):
            self.assertEqual(ProviderRouter._classify_error(RuntimeError(f'Anthropic Messages API returned HTTP {status} (retryable).')),
                             ('transient_provider', True, True))
