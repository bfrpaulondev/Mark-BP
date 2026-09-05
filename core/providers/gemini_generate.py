from __future__ import annotations

from typing import Any

from core.providers.contracts import ProviderResponse, ProviderUsage


class GeminiGenerateClient:
    """Small non-realtime Gemini adapter used by the provider router.

    The realtime voice session remains owned by the existing Gemini Live runtime. This
    adapter is intentionally limited to bounded text/vision specialist calls.
    """

    def __init__(self, api_key: str):
        self._api_key = str(api_key or "").strip()
        if not self._api_key:
            raise ValueError("Gemini API key is required.")

    # -.-.-.-
    def generate_text(
        self,
        *,
        model: str,
        prompt: str,
        reasoning_effort: str = "low",
    ) -> ProviderResponse:
        del reasoning_effort  # Provider-neutral hint; not required by this stable adapter.
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError(
                "The 'google-genai' dependency is required for the Gemini provider."
            ) from exc

        client = genai.Client(api_key=self._api_key)
        response = client.models.generate_content(
            model=str(model or "").strip(),
            contents=str(prompt or ""),
        )
        text = str(getattr(response, "text", "") or "").strip()
        if not text:
            raise RuntimeError("Gemini response contained no output text.")
        return ProviderResponse(
            text=text,
            usage=extract_gemini_usage(getattr(response, "usage_metadata", None)),
        )

    # -.-.-.-
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
        del detail, reasoning_effort  # Provider-neutral hints; Gemini accepts the image directly.
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "The 'google-genai' dependency is required for the Gemini provider."
            ) from exc

        client = genai.Client(api_key=self._api_key)
        image_part = types.Part.from_bytes(
            data=bytes(image_bytes),
            mime_type=str(mime_type or "image/jpeg"),
        )
        response = client.models.generate_content(
            model=str(model or "").strip(),
            contents=[image_part, str(prompt or "")],
        )
        text = str(getattr(response, "text", "") or "").strip()
        if not text:
            raise RuntimeError("Gemini response contained no output text.")
        return ProviderResponse(
            text=text,
            usage=extract_gemini_usage(getattr(response, "usage_metadata", None)),
        )


def _usage_value(metadata: Any, *names: str) -> int:
    for name in names:
        value: Any = None
        if isinstance(metadata, dict):
            value = metadata.get(name)
        else:
            value = getattr(metadata, name, None)
        if value is None:
            continue
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            continue
    return 0


def extract_gemini_usage(metadata: Any) -> ProviderUsage:
    if metadata is None:
        return ProviderUsage()

    input_tokens = _usage_value(
        metadata,
        "prompt_token_count",
        "promptTokenCount",
    )
    output_tokens = _usage_value(
        metadata,
        "candidates_token_count",
        "candidatesTokenCount",
    )
    reasoning_tokens = _usage_value(
        metadata,
        "thoughts_token_count",
        "thoughtsTokenCount",
    )
    total_tokens = _usage_value(
        metadata,
        "total_token_count",
        "totalTokenCount",
    ) or (input_tokens + output_tokens + reasoning_tokens)

    return ProviderUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=_usage_value(
            metadata,
            "cached_content_token_count",
            "cachedContentTokenCount",
        ),
        reasoning_tokens=reasoning_tokens,
        total_tokens=total_tokens,
        # Gemini pricing treats generated thinking tokens as output in addition
        # to candidate/output tokens, so normalize that before generic costing.
        billable_output_tokens=output_tokens + reasoning_tokens,
    )
