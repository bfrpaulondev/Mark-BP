from __future__ import annotations

import re
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
    "format",
    "shutdown",
    "restart",
    "reboot",
    "send",
    "submit",
    "publish",
    "pay",
    "payment",
    "purchase",
    "buy",
    "transfer",
    "wire",
    "trade",
    "sell",
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
}

_LOCAL_CONTEXT_APPROVAL_TERMS = {
    "delete",
    "remove",
    "erase",
    "send",
    "submit",
    "publish",
    "upload",
    "download",
    "buy",
    "purchase",
    "pay",
    "transfer",
    "confirm",
    "approve",
    "save",
    "apply",
    "accept",
    "allow",
    "install",
    "uninstall",
    "login",
    "signin",
    "run",
    "execute",
    "shutdown",
    "restart",
    "apagar",
    "eliminar",
    "remover",
    "enviar",
    "submeter",
    "publicar",
    "carregar",
    "descarregar",
    "comprar",
    "pagar",
    "transferir",
    "confirmar",
    "aprovar",
    "guardar",
    "aplicar",
    "aceitar",
    "permitir",
    "instalar",
    "desinstalar",
    "entrar",
    "executar",
    "desligar",
    "reiniciar",
}
_LOCAL_CONTEXT_APPROVAL_PHRASES = {
    "sign in",
    "log in",
    "place order",
    "grant access",
    "revoke access",
    "save changes",
    "confirm changes",
    "alterar permissões",
    "conceder acesso",
    "revogar acesso",
    "guardar alterações",
    "confirmar alterações",
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

    local_context = str(action.safety_context or "").strip().casefold()
    if local_context:
        local_tokens = set(
            re.findall(r"[\wÀ-ÿ]+", local_context, flags=re.UNICODE)
        )
        if (
            any(phrase in local_context for phrase in _LOCAL_CONTEXT_APPROVAL_PHRASES)
            or bool(local_tokens & _LOCAL_CONTEXT_APPROVAL_TERMS)
        ):
            return SafetyDecision(
                allowed=False,
                requires_approval=True,
                reason="The local UI target may create an external, privileged or irreversible effect.",
            )

    return SafetyDecision(allowed=True, requires_approval=False)
