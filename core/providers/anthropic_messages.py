"""Anthropic Messages provider adapter (ANT-276 BLOCO 12 G1).

Provider-neutral text adapter compatible with ``ProviderRouter``.
Errors expose only technical classification/status, never provider body,
prompt, response content, or credentials.
"""

from __future__ import annotations

from typing import Any

from core.providers.contracts import ProviderResponse, ProviderUsage

ENDPOINT = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


# -.-.-.-
def classify_http_status(status: int) -> str:
    """G1: 429/5xx are retryable; other HTTP errors are fatal."""
    if status == 429 or status >= 500:
        return "retryable"
    return "fatal"


# -.-.-.-
def classify_transport_exception(exc: Exception) -> str:
    """Classify transport failures without returning their raw message."""
    name = type(exc).__name__.casefold()
    if any(marker in name for marker in ("timeout", "connection", "connect", "temporary")):
        return "retryable"
    return "fatal"


class AnthropicMessagesClient:
    def __init__(self, api_key: str, *, timeout: float = 45.0):
        self._api_key = str(api_key or "").strip()
        if not self._api_key:
            raise ValueError("Anthropic API key is required.")
        self._timeout = max(1.0, min(180.0, float(timeout)))

    # -.-.-.-
    def generate_text(
        self,
        *,
        model: str,
        prompt: str,
        reasoning_effort: str = "low",
        max_tokens: int = 1024,
    ) -> ProviderResponse:
        # Anthropic Messages does not use the router's generic
        # ``reasoning_effort`` knob in this adapter. Accepting it keeps the
        # provider contract compatible without inventing provider settings.
        _ = reasoning_effort
        normalized_model = str(model or "").strip()
        normalized_prompt = str(prompt or "").strip()
        if not normalized_model:
            raise ValueError("Anthropic model is required.")
        if not normalized_prompt:
            raise ValueError("Anthropic prompt is required.")
        payload = {
            "model": normalized_model,
            "max_tokens": max(1, min(32768, int(max_tokens))),
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": normalized_prompt}],
                }
            ],
        }
        return self._request(payload)

    # -.-.-.-
    def _request(self, payload: dict[str, Any]) -> ProviderResponse:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError(
                "The 'requests' dependency is required for the Anthropic provider."
            ) from exc

        try:
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
        except Exception as exc:  # requests may be optional/injected in tests
            classification = classify_transport_exception(exc)
            raise RuntimeError(
                f"Anthropic transport error ({classification}; {type(exc).__name__})."
            ) from None

        status = int(getattr(response, "status_code", 0) or 0)
        if status >= 400:
            raise RuntimeError(
                f"Anthropic Messages API returned HTTP {status} "
                f"({classify_http_status(status)})."
            )
        try:
            data = response.json()
        except Exception:
            raise RuntimeError("Anthropic response was not valid JSON.") from None
        if not isinstance(data, dict):
            raise RuntimeError("Anthropic response JSON had an unexpected shape.")

        text = extract_anthropic_text(data)
        if not text:
            raise RuntimeError("Anthropic response contained no text content.")
        headers = getattr(response, "headers", {}) or {}
        return ProviderResponse(
            text=text,
            usage=extract_anthropic_usage(data),
            request_id=str(headers.get("request-id", "") or ""),
        )


# -.-.-.-
def extract_anthropic_text(data: dict[str, Any]) -> str:
    parts = [
        block.get("text", "")
        for block in (data.get("content") or [])
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "".join(str(part) for part in parts).strip()


# -.-.-.-
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


# -.-.-.-
def _safe_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
