import contextlib
import sys
import types
import unittest

from core.providers.anthropic_messages import AnthropicMessagesClient
from core.providers.groq_chat import GroqChatClient


class _Response:
    def __init__(self, status=200, payload=None, text="", headers=None):
        self.status_code = status
        self._payload = payload
        self.text = text
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


@contextlib.contextmanager
def fake_requests(response):
    saved = sys.modules.get("requests")
    sys.modules["requests"] = types.SimpleNamespace(post=lambda *args, **kwargs: response)
    try:
        yield
    finally:
        if saved is None:
            sys.modules.pop("requests", None)
        else:
            sys.modules["requests"] = saved


class ProviderAdapterReviewRegressions(unittest.TestCase):
    def test_anthropic_accepts_router_reasoning_effort_argument(self):
        response = _Response(
            payload={
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        )
        with fake_requests(response):
            result = AnthropicMessagesClient("key").generate_text(
                model="claude-test",
                prompt="hello",
                reasoning_effort="medium",
            )
        self.assertEqual(result.text, "ok")

    def test_groq_accepts_router_reasoning_effort_argument(self):
        response = _Response(
            payload={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }
        )
        with fake_requests(response):
            result = GroqChatClient("key").generate_text(
                model="groq-test",
                prompt="hello",
                reasoning_effort="low",
            )
        self.assertEqual(result.text, "ok")

    def test_anthropic_http_error_never_exposes_response_body(self):
        response = _Response(status=401, payload={}, text="secret-response-body")
        with fake_requests(response):
            with self.assertRaises(RuntimeError) as caught:
                AnthropicMessagesClient("key").generate_text(model="m", prompt="p")
        message = str(caught.exception)
        self.assertIn("401", message)
        self.assertNotIn("secret-response-body", message)

    def test_groq_http_error_never_exposes_response_body(self):
        response = _Response(status=429, payload={}, text="private-provider-message")
        with fake_requests(response):
            with self.assertRaises(RuntimeError) as caught:
                GroqChatClient("key").generate_text(model="m", prompt="p")
        message = str(caught.exception)
        self.assertIn("retryable", message)
        self.assertNotIn("private-provider-message", message)

    def test_invalid_json_fails_without_raw_body(self):
        response = _Response(
            status=200,
            payload=ValueError("decoder saw secret-payload"),
            text="secret-payload",
        )
        with fake_requests(response):
            with self.assertRaises(RuntimeError) as caught:
                AnthropicMessagesClient("key").generate_text(model="m", prompt="p")
        self.assertEqual(str(caught.exception), "Anthropic response was not valid JSON.")


if __name__ == "__main__":
    unittest.main()
