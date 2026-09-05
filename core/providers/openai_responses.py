from __future__ import annotations

import base64
from typing import Any

from core.providers.contracts import ProviderResponse, ProviderUsage


class OpenAIResponsesClient:
    ENDPOINT = "https://api.openai.com/v1/responses"

    def __init__(self, api_key: str, *, timeout: float = 45.0):
        self._api_key = str(api_key or "").strip()
        if not self._api_key:
            raise ValueError("OpenAI API key is required.")
        self._timeout = timeout

    def generate_text(
        self,
        *,
        model: str,
        prompt: str,
        reasoning_effort: str = "low",
    ) -> ProviderResponse:
        payload = {
            "model": model,
            "input": prompt,
            "reasoning": {"effort": reasoning_effort},
            "text": {"verbosity": "low"},
            "store": False,
        }
        return self._request(payload)

    def analyze_image(
        self,
        *,
        model: str,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        detail: str = "low",
        reasoning_effort: str = "low",
    ) -> ProviderResponse:
        image_url = (
            f"data:{mime_type};base64,"
            + base64.b64encode(image_bytes).decode("ascii")
        )
        payload = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": image_url,
                            "detail": detail,
                        },
                    ],
                }
            ],
            "reasoning": {"effort": reasoning_effort},
            "text": {"verbosity": "low"},
            "store": False,
        }
        return self._request(payload)

    def _request(self, payload: dict[str, Any]) -> ProviderResponse:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError(
                "The 'requests' dependency is required for the OpenAI provider."
            ) from exc

        response = requests.post(
            self.ENDPOINT,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self._timeout,
        )

        if response.status_code >= 400:
            request_id = response.headers.get("x-request-id", "")
            detail = ""
            try:
                body = response.json()
                detail = str(body.get("error", {}).get("message") or "")
            except Exception:
                detail = response.text[:300]
            suffix = f" request_id={request_id}" if request_id else ""
            raise RuntimeError(
                f"OpenAI Responses API returned HTTP {response.status_code}: "
                f"{detail or 'request failed'}.{suffix}"
            )

        data = response.json()
        text = extract_output_text(data)
        if not text:
            raise RuntimeError("OpenAI response contained no output text.")
        return ProviderResponse(
            text=text,
            usage=extract_openai_usage(data),
            request_id=str(response.headers.get("x-request-id", "") or ""),
        )


def _safe_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def extract_openai_usage(payload: dict[str, Any]) -> ProviderUsage:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return ProviderUsage()

    input_tokens = _safe_count(usage.get("input_tokens"))
    output_tokens = _safe_count(usage.get("output_tokens"))
    total_tokens = _safe_count(usage.get("total_tokens")) or (
        input_tokens + output_tokens
    )

    input_details = usage.get("input_tokens_details")
    if not isinstance(input_details, dict):
        input_details = {}
    output_details = usage.get("output_tokens_details")
    if not isinstance(output_details, dict):
        output_details = {}

    return ProviderUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=_safe_count(input_details.get("cached_tokens")),
        reasoning_tokens=_safe_count(output_details.get("reasoning_tokens")),
        total_tokens=total_tokens,
        # Responses API reports reasoning_tokens as a breakdown of output_tokens,
        # so adding it again would double count the priced output.
        billable_output_tokens=output_tokens,
    )


def extract_output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    chunks: list[str] = []
    output = payload.get("output")
    if not isinstance(output, list):
        return ""

    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())

    return "\n".join(chunks).strip()
