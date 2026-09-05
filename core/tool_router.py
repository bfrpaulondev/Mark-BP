from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any


class RouteTier(str, Enum):
    DIRECT_LOCAL = "direct_local"
    API_DOM_UIA = "api_dom_uia"
    LOCAL_CV = "local_cv"
    FAST_MODEL = "fast_model"
    VISION_COMPUTER_USE = "vision_computer_use"
    LEGACY = "legacy"


@dataclass(frozen=True)
class ToolRoute:
    tool_name: str
    action: str
    tier: RouteTier
    reason: str


_DIRECT_LOCAL_TOOLS = {
    "open_app",
    "computer_control",
    "computer_settings",
    "file_controller",
    "display_manager",
    "system_monitor",
    "shutdown_jarvis",
}

_API_DOM_UIA_TOOLS = {
    "verified_browser_automation",
    "browser_control",
    "windows_ui_automation",
}

_LOCAL_CV_TOOLS = {
    "screenconnect",
    "screen_connect",
    "screenconnect_control",
}

_FAST_MODEL_TOOLS = {
    "code_helper",
    "dev_agent",
}

_VISION_COMPUTER_USE_TOOLS = {
    "realtime_computer_use",
    "computer_use",
}


class ToolRouter:
    """Classify existing tools without executing them or changing authorization.

    ANT-260 deliberately routes only already-selected tool calls. Text intent routing,
    authorization and provider selection remain separate concerns.
    """

    # -.-.-.-
    def route(
        self,
        tool_name: str,
        args: Mapping[str, Any] | None = None,
    ) -> ToolRoute:
        name = str(tool_name or "").strip().lower()
        params = args or {}
        action = str(params.get("action") or "").strip().lower()

        if name in _DIRECT_LOCAL_TOOLS:
            return ToolRoute(name, action, RouteTier.DIRECT_LOCAL, "deterministic_local_tool")
        if name in _API_DOM_UIA_TOOLS:
            return ToolRoute(name, action, RouteTier.API_DOM_UIA, "structured_control_available")
        if name in _LOCAL_CV_TOOLS:
            return ToolRoute(name, action, RouteTier.LOCAL_CV, "local_perception_tool")
        if name in _FAST_MODEL_TOOLS:
            return ToolRoute(name, action, RouteTier.FAST_MODEL, "model_assisted_tool")
        if name in _VISION_COMPUTER_USE_TOOLS:
            return ToolRoute(name, action, RouteTier.VISION_COMPUTER_USE, "last_resort_visual_control")
        return ToolRoute(name, action, RouteTier.LEGACY, "unclassified_legacy_tool")
