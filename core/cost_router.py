from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class CostMode(str, Enum):
    ECONOMY = "economy"
    BALANCED = "balanced"
    QUALITY = "quality"


@dataclass(frozen=True)
class ExecutionBudget:
    max_model_calls: int
    max_vision_calls: int
    max_steps: int
    capture_fps: int
    change_threshold: float
    image_detail: str
    max_image_width: int
    max_image_height: int
    jpeg_quality: int


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str
    reasoning_effort: str
    budget: ExecutionBudget
    reason: str


_BUDGETS = {
    CostMode.ECONOMY: ExecutionBudget(
        max_model_calls=6,
        max_vision_calls=6,
        max_steps=12,
        capture_fps=10,
        change_threshold=0.025,
        image_detail="low",
        max_image_width=960,
        max_image_height=540,
        jpeg_quality=68,
    ),
    CostMode.BALANCED: ExecutionBudget(
        max_model_calls=12,
        max_vision_calls=12,
        max_steps=20,
        capture_fps=15,
        change_threshold=0.015,
        image_detail="auto",
        max_image_width=1280,
        max_image_height=720,
        jpeg_quality=76,
    ),
    CostMode.QUALITY: ExecutionBudget(
        max_model_calls=20,
        max_vision_calls=20,
        max_steps=30,
        capture_fps=20,
        change_threshold=0.010,
        image_detail="high",
        max_image_width=1600,
        max_image_height=900,
        jpeg_quality=82,
    ),
}


def normalize_cost_mode(value: str | CostMode | None) -> CostMode:
    if isinstance(value, CostMode):
        return value
    normalized = str(value or CostMode.ECONOMY.value).strip().lower()
    try:
        return CostMode(normalized)
    except ValueError:
        return CostMode.ECONOMY


def budget_for_mode(value: str | CostMode | None) -> ExecutionBudget:
    return _BUDGETS[normalize_cost_mode(value)]


def select_visual_route(
    config: Mapping[str, Any],
    *,
    cost_mode: str | CostMode | None = None,
) -> ModelRoute:
    mode = normalize_cost_mode(
        cost_mode or config.get("computer_use_cost_mode") or CostMode.ECONOMY.value
    )
    budget = budget_for_mode(mode)
    preference = str(config.get("model_provider_preference") or "auto").strip().lower()

    openai_key = str(config.get("openai_api_key") or "").strip()
    gemini_key = str(config.get("gemini_api_key") or "").strip()

    if preference not in {"auto", "openai", "gemini"}:
        preference = "auto"

    if preference == "openai" and not openai_key:
        preference = "auto"
    if preference == "gemini" and not gemini_key:
        preference = "auto"

    if preference == "openai" or (preference == "auto" and openai_key):
        model_by_mode = {
            CostMode.ECONOMY: str(
                config.get("openai_model_fast") or "gpt-5.6-luna"
            ).strip(),
            CostMode.BALANCED: str(
                config.get("openai_model_balanced") or "gpt-5.6-terra"
            ).strip(),
            CostMode.QUALITY: str(
                config.get("openai_model_expert") or "gpt-5.6-sol"
            ).strip(),
        }
        effort_by_mode = {
            CostMode.ECONOMY: "low",
            CostMode.BALANCED: "low",
            CostMode.QUALITY: "medium",
        }
        return ModelRoute(
            provider="openai",
            model=model_by_mode[mode],
            reasoning_effort=effort_by_mode[mode],
            budget=budget,
            reason=f"OpenAI selected for {mode.value} visual planning.",
        )

    if gemini_key:
        model_by_mode = {
            CostMode.ECONOMY: "gemini-flash-lite-latest",
            CostMode.BALANCED: "gemini-flash-latest",
            CostMode.QUALITY: "gemini-flash-latest",
        }
        return ModelRoute(
            provider="gemini",
            model=model_by_mode[mode],
            reasoning_effort="low",
            budget=budget,
            reason=f"Gemini selected for {mode.value} visual planning.",
        )

    raise RuntimeError(
        "Realtime Computer Use requires ANTONELLA_OPENAI_API_KEY or "
        "ANTONELLA_GEMINI_API_KEY."
    )


def cost_class_for_tool(tool_name: str) -> str:
    normalized = str(tool_name or "").strip().lower()

    if normalized in {
        "open_app",
        "computer_settings",
        "computer_control",
        "file_controller",
        "desktop_control",
        "system_status",
        "reminder",
    }:
        return "local"

    if normalized in {"browser_control", "file_processor"}:
        return "structured"

    if normalized in {"screen_process"}:
        return "vision"

    if normalized in {"realtime_computer_use"}:
        return "computer_use"

    return "model"
