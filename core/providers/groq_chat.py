"""Groq chat provider adapter (ANT-276 BLOCO 12 G2).

OpenAI-compatible text endpoint with the same provider-neutral response
contract as the other specialist adapters. Errors never include provider
response bodies, prompts, outputs, or credentials.
"""

from __future__ import annotations

from typing import Any

from core.providers.anthropic_messages import (
    classify_http_status,
    classify_transport_exception,
)
from core.providers.contracts import ProviderResponse, ProviderUsage

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


class GroqChatClient:
    def __init__(self, api_key: str, *, timeout: float = 45.0):
        self._api_key = str(api_key or "").strip()
        if not self._api_key:
            raise ValueError("Groq API key is required.")
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
        # The generic router effort is intentionally accepted but not mapped
        # to a provider-specific option until such a mapping is configured.
        _ = reasoning_effort
        normalized_model = str(model or "").strip()
        normalized_prompt = str(prompt or "").strip()
        if not normalized_model:
            raise ValueError("Groq model is required.")
        if not normalized_prompt:
            raise ValueError("Groq prompt is required.")
        payload = {
            "model": normalized_model,
            "messages": [{"role": "user", "content": normalized_prompt}],
            "max_tokens": max(1, min(32768, int(max_tokens))),
        }
        return self._request(payload)

    # -.-.-.-
    def _request(self, payload: dict[str, Any]) -> ProviderResponse:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError(
                "The 'requests' dependency is required for the Groq provider."
            ) from exc

        try:
            response = requests.post(
                ENDPOINT,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout,
            )
        except Exception as exc:
            classification = classify_transport_exception(exc)
            raise RuntimeError(
                f"Groq transport error ({classification}; {type(exc).__name__})."
            ) from None

        status = int(getattr(response, "status_code", 0) or 0)
        if status >= 400:
            raise RuntimeError(
                f"Groq Chat API returned HTTP {status} "
                f"({classify_http_status(status)})."
            )
        try:
            data = response.json()
        except Exception:
            raise RuntimeError("Groq response was not valid JSON.") from None
        if not isinstance(data, dict):
            raise RuntimeError("Groq response JSON had an unexpected shape.")

        text = extract_groq_text(data)
        if not text:
            raise RuntimeError("Groq response contained no output text.")
        headers = getattr(response, "headers", {}) or {}
        return ProviderResponse(
            text=text,
            usage=extract_groq_usage(data),
            request_id=str(headers.get("x-request-id", "") or ""),
        )


# -.-.-.-
def extract_groq_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message") or {}
    if not isinstance(message, dict):
        return ""
    return str(message.get("content") or "").strip()


# -.-.-.-
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


# -.-.-.-
def _safe_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
