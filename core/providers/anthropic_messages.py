"""Anthropic Messages provider adapter (ANT-276 BLOCO 12 G1).

Follows the OpenAI adapter shape: requests POST, structured errors with
retryability classification, provider-neutral usage. Never logs prompt
or response content.
"""

from __future__ import annotations

from typing import Any

from core.providers.contracts import ProviderResponse, ProviderUsage

ENDPOINT = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


def classify_http_status(status: int) -> str:
    """G1: retryability — 429/5xx/timeouts are retryable, other 4xx fatal."""
    if status == 429 or status >= 500:
        return "retryable"
    return "fatal"


class AnthropicMessagesClient:
    def __init__(self, api_key: str, *, timeout: float = 45.0):
        self._api_key = str(api_key or "").strip()
        if not self._api_key:
            raise ValueError("Anthropic API key is required.")
        self._timeout = timeout

    def generate_text(self, *, model: str, prompt: str, max_tokens: int = 1024) -> ProviderResponse:
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        }
        return self._request(payload)

    def _request(self, payload: dict[str, Any]) -> ProviderResponse:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("The 'requests' dependency is required for the Anthropic provider.") from exc

        response = requests.post(
            ENDPOINT,
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": API_VERSION,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self._timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Anthropic Messages API returned HTTP {response.status_code} "
                f"({classify_http_status(response.status_code)}): {response.text[:300]}"
            )
        data = response.json()
        text = extract_anthropic_text(data)
        if not text:
            raise RuntimeError("Anthropic response contained no text content.")
        return ProviderResponse(
            text=text,
            usage=extract_anthropic_usage(data),
            request_id=str(response.headers.get("request-id", "") or ""),
        )


def extract_anthropic_text(data: dict[str, Any]) -> str:
    parts = [
        block.get("text", "")
        for block in (data.get("content") or [])
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "".join(parts).strip()


def extract_anthropic_usage(data: dict[str, Any]) -> ProviderUsage:
    usage = data.get("usage") or {}
    input_tokens = _safe_count(usage.get("input_tokens"))
    output_tokens = _safe_count(usage.get("output_tokens"))
    return ProviderUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        billable_output_tokens=output_tokens,
    )


def _safe_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
