from __future__ import annotations

from typing import Any


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
    ) -> str:
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
        return text

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
    ) -> str:
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
        return text
