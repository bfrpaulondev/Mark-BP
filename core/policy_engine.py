from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any


class PolicyEffect(str, Enum):
    READ = "read"
    WRITE = "write"
    EXTERNAL = "external"
    DESTRUCTIVE = "destructive"
    FINANCIAL = "financial"
    PRIVILEGED = "privileged"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class PolicyDecision:
    effect: PolicyEffect
    allowed: bool
    requires_approval: bool
    rule_id: str
    reason: str

    @property
    def blocks_execution(self) -> bool:
        return (not self.allowed) or self.requires_approval

    def safe_metadata(self) -> dict[str, Any]:
        return {
            "effect": self.effect.value,
            "allowed": self.allowed,
            "requires_approval": self.requires_approval,
            "rule_id": self.rule_id,
            "reason": self.reason,
        }


_READ_ACTIONS = {
    "list",
    "status",
    "resolve",
    "inspect",
    "find",
    "read",
    "search",
    "current",
    "info",
    "summarize",
    "get_info",
    "trending",
    "session_status",
    "browser_current",
    "browser_list_tabs",
    "browser_list_windows",
    "browser_cdp_status",
    "browser_cdp_list_tabs",
    "cursor_position",
}

_DESTRUCTIVE_ACTIONS = {
    "delete",
    "delete_file",
    "remove",
    "erase",
    "format",
    "shutdown",
    "restart",
    "reboot",
    "uninstall",
}

_PRIVILEGED_ACTIONS = {
    "grant_access",
    "revoke_access",
    "change_permission",
    "change_permissions",
    "set_permissions",
    "disable_firewall",
    "disable_defender",
    "disable_antivirus",
    "wifi_toggle",
    "run",
    "execute",
}

_BLOCKED_ACTIONS = {
    "disable_defender",
    "disable_antivirus",
    "bypass_security",
    "steal_password",
    "reveal_password",
    "export_password",
}

_EXTERNAL_TOOLS = {
    "send_message",
}

_FINANCIAL_TOOLS = {
    "trade",
    "broker_order",
    "mt5_order",
    "payment",
    "purchase",
}

_READ_TOOLS = {
    "system_status",
    "system_monitor",
    "weather_report",
    "web_search",
    "flight_finder",
    "display_manager",
    "screen_process",
}

_ALWAYS_WRITE_TOOLS = {
    "open_app",
    "reminder",
    "close_camera",
    "save_memory",
    "manage_monitor",
}


class PolicyEngine:
    """Provider-independent deterministic safety classification for tool effects.

    The engine intentionally reasons only from the selected tool and bounded action metadata.
    It never trusts model-supplied `confirmed`, `approved`, `risk` or similar flags as human
    authorization. ANT-262 will add action-bound one-use human approval tokens.
    """

    # -.-.-.-
    def evaluate(
        self,
        tool_name: str,
        args: Mapping[str, Any] | None = None,
    ) -> PolicyDecision:
        name = str(tool_name or "").strip().lower()
        params = dict(args or {})
        action = str(params.get("action") or "").strip().lower()

        if action in _BLOCKED_ACTIONS:
            return PolicyDecision(
                effect=PolicyEffect.BLOCKED,
                allowed=False,
                requires_approval=False,
                rule_id="blocked.security_bypass",
                reason="This operation is blocked by Antonella's local security policy.",
            )

        if name in _FINANCIAL_TOOLS or action in {"pay", "payment", "purchase", "buy", "sell", "trade", "transfer", "wire"}:
            return PolicyDecision(
                effect=PolicyEffect.FINANCIAL,
                allowed=True,
                requires_approval=True,
                rule_id="approval.financial",
                reason="Financial effects require explicit human approval before execution.",
            )

        if name in _EXTERNAL_TOOLS or action in {"send", "submit", "publish", "post", "share"}:
            return PolicyDecision(
                effect=PolicyEffect.EXTERNAL,
                allowed=True,
                requires_approval=True,
                rule_id="approval.external",
                reason="External communication or publication requires explicit human approval.",
            )

        if action in _DESTRUCTIVE_ACTIONS:
            return PolicyDecision(
                effect=PolicyEffect.DESTRUCTIVE,
                allowed=True,
                requires_approval=True,
                rule_id="approval.destructive",
                reason="Destructive or shutdown effects require explicit human approval.",
            )

        if action in _PRIVILEGED_ACTIONS:
            return PolicyDecision(
                effect=PolicyEffect.PRIVILEGED,
                allowed=True,
                requires_approval=True,
                rule_id="approval.privileged",
                reason="Privileged system changes require explicit human approval.",
            )

        if name == "file_controller":
            if action in {"list", "read", "find", "largest", "get_largest_files"}:
                return self._read("read.filesystem")
            return self._write("write.filesystem")

        if name == "file_processor":
            if action in {"summarize", "extract_text", "info", "analyze", "stats", "validate", "word_count", "explain", "review", "list"}:
                return self._read("read.file_processor")
            if action in {"run", "test"}:
                return PolicyDecision(
                    effect=PolicyEffect.PRIVILEGED,
                    allowed=True,
                    requires_approval=True,
                    rule_id="approval.code_execution",
                    reason="Executing user-provided code requires explicit human approval.",
                )
            return self._write("write.file_processor")

        if name in {"computer_settings", "computer_control", "desktop_control", "verified_desktop_control"}:
            if action in _READ_ACTIONS:
                return self._read("read.desktop")
            return self._write("write.desktop")

        if name in {"browser_control", "verified_browser_automation", "windows_ui_automation"}:
            if action in _READ_ACTIONS:
                return self._read("read.structured_control")
            return self._write("write.structured_control")

        if name in _READ_TOOLS:
            return self._read("read.tool")

        if name in _ALWAYS_WRITE_TOOLS:
            if name == "manage_monitor" and action in {"list", "status"}:
                return self._read("read.monitoring")
            return self._write("write.local")

        if action in _READ_ACTIONS:
            return self._read("read.action")

        # Unknown tools remain executable for compatibility, but are classified as WRITE
        # rather than READ so later policy/approval layers never treat them as harmless.
        return self._write("write.unknown_compatible")

    # -.-.-.-
    @staticmethod
    def _read(rule_id: str) -> PolicyDecision:
        return PolicyDecision(
            effect=PolicyEffect.READ,
            allowed=True,
            requires_approval=False,
            rule_id=rule_id,
            reason="Read-only operation.",
        )

    # -.-.-.-
    @staticmethod
    def _write(rule_id: str) -> PolicyDecision:
        return PolicyDecision(
            effect=PolicyEffect.WRITE,
            allowed=True,
            requires_approval=False,
            rule_id=rule_id,
            reason="Non-destructive local write or interaction.",
        )
