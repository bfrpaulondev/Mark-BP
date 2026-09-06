"""Groq chat provider adapter (ANT-276 BLOCO 12 G2).

OpenAI-compatible chat completions endpoint; same error/usage contract
as the other providers.
"""

from __future__ import annotations

from typing import Any

from core.providers.contracts import ProviderResponse, ProviderUsage

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


class GroqChatClient:
    def __init__(self, api_key: str, *, timeout: float = 45.0):
        self._api_key = str(api_key or "").strip()
        if not self._api_key:
            raise ValueError("Groq API key is required.")
        self._timeout = timeout

    def generate_text(self, *, model: str, prompt: str, max_tokens: int = 1024) -> ProviderResponse:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        return self._request(payload)

    def _request(self, payload: dict[str, Any]) -> ProviderResponse:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("The 'requests' dependency is required for the Groq provider.") from exc

        response = requests.post(
            ENDPOINT,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self._timeout,
        )
        if response.status_code >= 400:
            from core.providers.anthropic_messages import classify_http_status

            raise RuntimeError(
                f"Groq Chat API returned HTTP {response.status_code} "
                f"({classify_http_status(response.status_code)}): {response.text[:300]}"
            )
        data = response.json()
        text = extract_groq_text(data)
        if not text:
            raise RuntimeError("Groq response contained no output text.")
        return ProviderResponse(
            text=text,
            usage=extract_groq_usage(data),
            request_id=str(response.headers.get("x-request-id", "") or ""),
        )


def extract_groq_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or "").strip()


def extract_groq_usage(data: dict[str, Any]) -> ProviderUsage:
    usage = data.get("usage") or {}
    input_tokens = _safe_count(usage.get("prompt_tokens"))
    output_tokens = _safe_count(usage.get("completion_tokens"))
    return ProviderUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=_safe_count(usage.get("total_tokens")) or input_tokens + output_tokens,
        billable_output_tokens=output_tokens,
    )


def _safe_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
