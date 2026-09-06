import contextlib
import sys
import types
import unittest


_FAKE_REQUESTS = types.SimpleNamespace(post=lambda *a, **kw: None)


@contextlib.contextmanager
def fake_requests(response):
    """CI legs may have no `requests`; injecting into sys.modules wins
    over the real module even when it is installed."""
    saved = sys.modules.get("requests")
    sys.modules["requests"] = types.SimpleNamespace(post=lambda *a, **kw: response)
    try:
        yield
    finally:
        if saved is not None:
            sys.modules["requests"] = saved
        else:
            sys.modules.pop("requests", None)

from core.providers.anthropic_messages import (
    AnthropicMessagesClient,
    classify_http_status,
    extract_anthropic_text,
    extract_anthropic_usage,
)
from core.providers.groq_chat import GroqChatClient, extract_groq_text, extract_groq_usage


class _FakeResponse:
    def __init__(self, status=200, payload=None, text="", headers=None):
        self.status_code = status
        self._payload = payload
        self.text = text or json.dumps(payload or {})
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


import json  # noqa: E402


def _install_fake_requests(module, response):
    fake = types.SimpleNamespace(post=lambda *a, **kw: response)
    module_marker = types.SimpleNamespace(post=fake.post)
    sys.modules["requests"] = module_marker
    return module_marker


class RetryabilityTests(unittest.TestCase):
    def test_429_and_5xx_are_retryable(self):
        self.assertEqual(classify_http_status(429), "retryable")
        self.assertEqual(classify_http_status(500), "retryable")
        self.assertEqual(classify_http_status(503), "retryable")

    def test_auth_and_validation_are_fatal(self):
        self.assertEqual(classify_http_status(401), "fatal")
        self.assertEqual(classify_http_status(400), "fatal")
        self.assertEqual(classify_http_status(403), "fatal")


class AnthropicAdapterTests(unittest.TestCase):
    def test_success_parses_text_and_usage(self):
        response = _FakeResponse(200, {
            "content": [{"type": "text", "text": "Olá"}],
            "usage": {"input_tokens": 12, "output_tokens": 7},
        }, headers={"request-id": "req-1"})
        with fake_requests(response):
            client = AnthropicMessagesClient("key")
            result = client.generate_text(model="claude-x", prompt="oi")
        self.assertEqual(result.text, "Olá")
        self.assertEqual(result.usage.input_tokens, 12)
        self.assertEqual(result.usage.billable_output_tokens, 7)
        self.assertEqual(result.request_id, "req-1")

    def test_auth_error_raises_with_classification(self):
        response = _FakeResponse(401, {"error": {"message": "bad key"}})
        with fake_requests(response):
            client = AnthropicMessagesClient("key")
            with self.assertRaises(RuntimeError) as ctx:
                client.generate_text(model="m", prompt="oi")
        self.assertIn("fatal", str(ctx.exception))

    def test_rate_limit_error_is_marked_retryable(self):
        response = _FakeResponse(429, text="slow down")
        with fake_requests(response):
            client = AnthropicMessagesClient("key")
            with self.assertRaises(RuntimeError) as ctx:
                client.generate_text(model="m", prompt="oi")
        self.assertIn("retryable", str(ctx.exception))

    def test_empty_content_raises(self):
        response = _FakeResponse(200, {"content": []})
        with fake_requests(response):
            client = AnthropicMessagesClient("key")
            with self.assertRaises(RuntimeError):
                client.generate_text(model="m", prompt="oi")

    def test_missing_key_fails_closed(self):
        with self.assertRaises(ValueError):
            AnthropicMessagesClient("")


class GroqAdapterTests(unittest.TestCase):
    def test_success_parses_text_and_usage(self):
        response = _FakeResponse(200, {
            "choices": [{"message": {"content": "Feito"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        })
        with fake_requests(response):
            client = GroqChatClient("key")
            result = client.generate_text(model="llama-x", prompt="oi")
        self.assertEqual(result.text, "Feito")
        self.assertEqual(result.usage.total_tokens, 8)
        self.assertEqual(result.usage.billable_output_tokens, 3)

    def test_5xx_is_marked_retryable(self):
        response = _FakeResponse(503, text="unavailable")
        with fake_requests(response):
            client = GroqChatClient("key")
            with self.assertRaises(RuntimeError) as ctx:
                client.generate_text(model="m", prompt="oi")
        self.assertIn("retryable", str(ctx.exception))

    def test_empty_choices_raises(self):
        response = _FakeResponse(200, {"choices": []})
        with fake_requests(response):
            client = GroqChatClient("key")
            with self.assertRaises(RuntimeError):
                client.generate_text(model="m", prompt="oi")

    def test_missing_key_fails_closed(self):
        with self.assertRaises(ValueError):
            GroqChatClient("")


if __name__ == "__main__":
    unittest.main()
