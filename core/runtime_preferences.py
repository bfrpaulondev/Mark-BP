from __future__ import annotations

import os
from collections.abc import MutableMapping
from typing import Any


_ALLOWED_COST_MODES = {"economy", "balanced", "quality"}
_ALLOWED_PROVIDERS = {"auto", "openai", "gemini"}


# -.-.-.-
def apply_session_preferences(
    *,
    gemini_api_key: str = "",
    openai_api_key: str = "",
    cost_mode: str = "economy",
    provider_preference: str = "auto",
    voice_name: str = "Kore",
    environ: MutableMapping[str, str] | None = None,
) -> dict[str, Any]:
    """Apply runtime preferences without persisting secret values to disk."""
    target = environ if environ is not None else os.environ
    changed: list[str] = []
    restart_required: list[str] = []

    normalized_cost = str(cost_mode or "economy").strip().lower()
    if normalized_cost not in _ALLOWED_COST_MODES:
        normalized_cost = "economy"

    normalized_provider = str(provider_preference or "auto").strip().lower()
    if normalized_provider not in _ALLOWED_PROVIDERS:
        normalized_provider = "auto"

    normalized_voice = str(voice_name or "Kore").strip() or "Kore"

    values = {
        "ANTONELLA_COMPUTER_USE_COST_MODE": normalized_cost,
        "ANTONELLA_MODEL_PROVIDER_PREFERENCE": normalized_provider,
        "ANTONELLA_VOICE_NAME": normalized_voice,
    }

    for key, value in values.items():
        if target.get(key) != value:
            target[key] = value
            changed.append(key)

    if "ANTONELLA_VOICE_NAME" in changed:
        restart_required.append("voice")

    gemini = str(gemini_api_key or "").strip()
    if gemini:
        if target.get("ANTONELLA_GEMINI_API_KEY") != gemini:
            target["ANTONELLA_GEMINI_API_KEY"] = gemini
            changed.append("ANTONELLA_GEMINI_API_KEY")
            restart_required.append("gemini_live")

    openai = str(openai_api_key or "").strip()
    if openai:
        if target.get("ANTONELLA_OPENAI_API_KEY") != openai:
            target["ANTONELLA_OPENAI_API_KEY"] = openai
            changed.append("ANTONELLA_OPENAI_API_KEY")
            restart_required.append("expert_tool_schema")

    public_changed = [
        {
            "ANTONELLA_COMPUTER_USE_COST_MODE": "cost_mode",
            "ANTONELLA_MODEL_PROVIDER_PREFERENCE": "provider_preference",
            "ANTONELLA_VOICE_NAME": "voice_name",
            "ANTONELLA_GEMINI_API_KEY": "gemini_api_key",
            "ANTONELLA_OPENAI_API_KEY": "openai_api_key",
        }.get(item, item)
        for item in changed
    ]

    return {
        "changed": public_changed,
        "restart_required": sorted(set(restart_required)),
        "cost_mode": normalized_cost,
        "provider_preference": normalized_provider,
        "voice_name": normalized_voice,
        "gemini_updated": "ANTONELLA_GEMINI_API_KEY" in changed,
        "openai_updated": "ANTONELLA_OPENAI_API_KEY" in changed,
    }
