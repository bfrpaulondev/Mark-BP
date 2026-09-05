from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from core.execution_result import ExecutionResult


@dataclass(frozen=True)
class LocalCommandIntent:
    kind: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LocalCommandResult:
    handled: bool
    kind: str = ""
    message: str = ""
    verified: bool = False


_COST_ALIASES = {
    "economy": "economy",
    "economico": "economy",
    "economica": "economy",
    "equilibrado": "balanced",
    "equilibrada": "balanced",
    "balanced": "balanced",
    "qualidade": "quality",
    "quality": "quality",
}
_PROVIDER_ALIASES = {
    "auto": "auto",
    "automatico": "auto",
    "automatica": "auto",
    "openai": "openai",
    "gemini": "gemini",
}
_SCROLL_DIRECTIONS = {
    "baixo": "down",
    "down": "down",
    "cima": "up",
    "up": "up",
}


# -.-.-.-
def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().strip()


# -.-.-.-
def _clean_command(text: str) -> str:
    text = " ".join(str(text or "").strip().split())
    return text.rstrip(".!?").strip()


# -.-.-.-
def _is_safe_single_app_name(value: str) -> bool:
    name = _clean_command(value)
    if not name or len(name) > 60 or len(name.split()) > 6:
        return False

    folded = f" {_fold(name)} "
    blocked_fragments = (
        " e depois ",
        " e pesquisa ",
        " e procura ",
        " e abre ",
        " and then ",
        " then ",
        ";",
        ",",
        "http://",
        "https://",
    )
    return not any(fragment in folded for fragment in blocked_fragments)


# -.-.-.-
def parse_local_text_command(text: str) -> LocalCommandIntent | None:
    raw = _clean_command(text)
    if not raw:
        return None
    folded = _fold(raw)

    if folded in {"/local", "/local help", "/help local", "comandos locais"}:
        return LocalCommandIntent("help")

    if folded in {
        "que ecras tenho",
        "quais ecras tenho",
        "lista os ecras",
        "listar ecras",
        "lista os monitores",
        "listar monitores",
        "/displays",
        "/monitors",
    }:
        return LocalCommandIntent("display_list")

    if folded in {
        "status do agente",
        "estado do agente",
        "status computer use",
        "estado computer use",
        "/agent status",
    }:
        return LocalCommandIntent("agent_status")

    if folded in {
        "para o agente",
        "parar agente",
        "para computer use",
        "parar computer use",
        "stop computer use",
        "/agent stop",
    }:
        return LocalCommandIntent("agent_stop")

    if folded in {
        "aprovar passo",
        "aprova o passo",
        "aprovar um passo",
        "approve step",
        "/agent approve",
    }:
        return LocalCommandIntent("agent_approve")

    if folded in {
        "status do sistema",
        "estado do sistema",
        "status do computador",
        "estado do computador",
        "/system status",
    }:
        return LocalCommandIntent("system_status")

    cost_match = re.fullmatch(r"(?:/cost|modo)(?:\s+computer\s+use)?\s+([\w-]+)", folded)
    if cost_match:
        mode = _COST_ALIASES.get(cost_match.group(1))
        if mode:
            return LocalCommandIntent("set_cost", {"mode": mode})

    provider_match = re.fullmatch(r"/provider\s+([\w-]+)", folded)
    if provider_match:
        provider = _PROVIDER_ALIASES.get(provider_match.group(1))
        if provider:
            return LocalCommandIntent("set_provider", {"provider": provider})

    scroll_match = re.fullmatch(
        r"(?:faz\s+)?scroll(?:\s+para)?\s+(baixo|cima|down|up)(?:\s+(\d{1,2}))?",
        folded,
    )
    if scroll_match:
        amount = max(1, min(12, int(scroll_match.group(2) or 3)))
        return LocalCommandIntent(
            "scroll",
            {
                "direction": _SCROLL_DIRECTIONS[scroll_match.group(1)],
                "amount": amount,
            },
        )

    app_match = re.fullmatch(r"(?:abre|abrir|open|launch)\s+(.+)", raw, flags=re.IGNORECASE)
    if app_match:
        app_name = app_match.group(1).strip()
        if _is_safe_single_app_name(app_name):
            return LocalCommandIntent("open_app", {"app_name": app_name})

    return None


# -.-.-.-
def _format_display_list(raw: str) -> str:
    try:
        payload = json.loads(raw)
    except Exception:
        return raw or "Não consegui listar os ecrãs."

    displays = payload.get("displays") if isinstance(payload, dict) else None
    if not isinstance(displays, list) or not displays:
        return "Não encontrei ecrãs disponíveis."

    parts = []
    for item in displays:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        width = item.get("width")
        height = item.get("height")
        active = " activo" if item.get("active") else ""
        parts.append(f"ecrã {index}: {width}×{height}{active}")
    return f"Detectei {len(parts)} ecrã(s): " + "; ".join(parts) + "."


# -.-.-.-
def _format_agent_status(status: dict[str, Any]) -> str:
    state = str(status.get("state") or "idle")
    step = int(status.get("step") or 0)
    calls = int(status.get("model_calls") or 0)
    saved = int(status.get("saved_model_calls") or 0)
    monitor = status.get("monitor_index")
    scope = str(status.get("capture_scope") or "monitor")
    savings = int(status.get("capture_savings_pct") or 0)

    parts = [f"estado {state}", f"passo {step}", f"{calls} chamada(s) IA"]
    if saved:
        parts.append(f"{saved} chamada(s) poupada(s)")
    if monitor:
        parts.append(f"ecrã {monitor}")
    if scope == "window":
        parts.append(f"captura da janela, cerca de {savings}% menos pixels")
    return "Agente: " + ", ".join(parts) + "."


# -.-.-.-
def local_command_help() -> str:
    return (
        "Fast path local: abre <app>; scroll para baixo/cima; que ecrãs tenho; "
        "status do sistema; status do agente; parar agente; aprovar passo; "
        "modo económico/equilibrado/qualidade; /provider auto|openai|gemini."
    )


# -.-.-.-
def _legacy_side_effect_message(action: str, raw_result: object) -> LocalCommandResult:
    """Do not turn a legacy 'no exception' string into a verified success claim."""
    raw = str(raw_result or "").strip()
    lowered = raw.lower()
    if any(token in lowered for token in ("failed", "error", "could not", "not found")):
        return LocalCommandResult(True, action, raw or "A acção local falhou.", False)

    execution = ExecutionResult.unverified_delivery(
        action,
        evidence={"legacy_result": raw[:240]} if raw else {},
        message="Acção enviada localmente; o efeito ainda não foi verificado.",
    )
    return LocalCommandResult(True, action, execution.message, execution.verified)


# -.-.-.-
def execute_local_intent(
    intent: LocalCommandIntent,
    *,
    player=None,
) -> LocalCommandResult:
    kind = intent.kind

    try:
        if kind == "help":
            return LocalCommandResult(True, kind, local_command_help(), True)

        if kind == "display_list":
            from actions.display_manager import display_manager

            raw = display_manager({"action": "list"})
            return LocalCommandResult(True, kind, _format_display_list(raw), True)

        if kind == "agent_status":
            from core.computer_use import get_realtime_computer_use_session

            status = get_realtime_computer_use_session().status()
            return LocalCommandResult(True, kind, _format_agent_status(status), True)

        if kind == "agent_stop":
            from core.computer_use import get_realtime_computer_use_session

            result = get_realtime_computer_use_session().stop()
            message = (
                "Pedido de paragem enviado ao agente."
                if result.get("ok")
                else str(result.get("error") or "Não consegui parar o agente.")
            )
            return LocalCommandResult(True, kind, message, False)

        if kind == "agent_approve":
            from core.computer_use import get_realtime_computer_use_session

            result = get_realtime_computer_use_session().approve_once()
            message = (
                "Aprovado apenas o passo actualmente pendente."
                if result.get("ok")
                else str(result.get("error") or "O agente não aguarda aprovação.")
            )
            return LocalCommandResult(True, kind, message, bool(result.get("ok")))

        if kind == "system_status":
            from actions.system_monitor import get_system_status

            return LocalCommandResult(True, kind, str(get_system_status()), True)

        if kind == "set_cost":
            mode = str(intent.args.get("mode") or "economy")
            os.environ["ANTONELLA_COMPUTER_USE_COST_MODE"] = mode
            labels = {
                "economy": "económico",
                "balanced": "equilibrado",
                "quality": "qualidade",
            }
            verified = os.environ.get("ANTONELLA_COMPUTER_USE_COST_MODE") == mode
            return LocalCommandResult(
                True,
                kind,
                f"Modo de Computer Use alterado para {labels.get(mode, mode)}.",
                verified,
            )

        if kind == "set_provider":
            provider = str(intent.args.get("provider") or "auto")
            os.environ["ANTONELLA_MODEL_PROVIDER_PREFERENCE"] = provider
            verified = os.environ.get("ANTONELLA_MODEL_PROVIDER_PREFERENCE") == provider
            return LocalCommandResult(
                True,
                kind,
                f"Preferência de provider alterada para {provider}.",
                verified,
            )

        if kind == "scroll":
            from actions.computer_control import computer_control

            raw = computer_control(
                parameters={
                    "action": "scroll",
                    "direction": intent.args.get("direction", "down"),
                    "amount": int(intent.args.get("amount") or 3),
                },
                player=player,
            )
            return _legacy_side_effect_message("scroll", raw)

        if kind == "open_app":
            from actions.open_app import open_app

            app_name = str(intent.args.get("app_name") or "").strip()
            raw = open_app(
                parameters={"app_name": app_name},
                response=None,
                player=player,
            )
            result = _legacy_side_effect_message("open_app", raw)
            if result.verified:
                return result
            return LocalCommandResult(
                True,
                kind,
                f"Enviei o pedido para abrir {app_name}; ainda não verifiquei a janela.",
                False,
            )

    except Exception as exc:
        return LocalCommandResult(
            True,
            kind,
            f"Comando local falhou: {type(exc).__name__}: {str(exc)[:120]}",
            False,
        )

    return LocalCommandResult(False)


# -.-.-.-
def run_local_text_command(text: str, *, player=None) -> LocalCommandResult:
    intent = parse_local_text_command(text)
    if intent is None:
        return LocalCommandResult(False)
    return execute_local_intent(intent, player=player)
