from __future__ import annotations

from dataclasses import dataclass

from core.computer_use.contracts import ComputerAction


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    requires_approval: bool
    reason: str = ""


_BLOCKED_PHRASES = {
    "disable antivirus",
    "disable defender",
    "bypass security",
    "steal password",
    "export password",
    "reveal password",
}

_APPROVAL_PHRASES = {
    "delete",
    "remove",
    "erase",
    "uninstall",
    "install",
    "format",
    "shutdown",
    "restart",
    "reboot",
    "send",
    "submit",
    "publish",
    "upload",
    "pay",
    "payment",
    "purchase",
    "buy",
    "checkout",
    "place order",
    "transfer",
    "wire",
    "trade",
    "sell",
    "approve",
    "allow",
    "grant access",
    "revoke access",
    "change permission",
    "change permissions",
    "edit permission",
    "edit permissions",
    "save permission",
    "save permissions",
    "administrator",
    "credential",
    "password",
    "security setting",
    "save changes",
    "confirm changes",
    "sign in",
    "log in",
    "login",
    "run",
    "execute",
}


# -.-.-.-
def evaluate_action(action: ComputerAction) -> SafetyDecision:
    material = " ".join(
        part
        for part in (
            action.action,
            action.description,
            action.text,
            action.keys,
            action.result,
            action.safety_context,
        )
        if part
    ).lower()

    if any(term in material for term in _BLOCKED_PHRASES):
        return SafetyDecision(
            allowed=False,
            requires_approval=False,
            reason="This action is blocked by the local Computer Use safety policy.",
        )

    if action.risk in {"high", "critical", "red"}:
        return SafetyDecision(
            allowed=False,
            requires_approval=True,
            reason="The visual planner marked this step as high risk.",
        )

    if any(term in material for term in _APPROVAL_PHRASES):
        return SafetyDecision(
            allowed=False,
            requires_approval=True,
            reason="This step may create a destructive, external, privileged or financial effect.",
        )

    return SafetyDecision(allowed=True, requires_approval=False)
