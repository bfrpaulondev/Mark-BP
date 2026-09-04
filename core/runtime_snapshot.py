from __future__ import annotations

import json
from typing import Any, Mapping

from config import get_config


_AGENT_LABELS = {
    "idle": "Em espera",
    "starting": "A iniciar",
    "observing": "A observar",
    "planning": "A planear",
    "executing": "A executar",
    "awaiting_approval": "A aguardar aprovação",
    "stopping": "A parar",
    "stopped": "Parado",
    "done": "Concluído",
    "failed": "Falhou",
}

_COST_LABELS = {
    "economy": "Económico",
    "balanced": "Equilibrado",
    "quality": "Qualidade",
}


# -.-.-.-
def _computer_use_status() -> dict[str, Any]:
    try:
        from core.computer_use import get_realtime_computer_use_session

        return get_realtime_computer_use_session().status()
    except Exception:
        return {}


# -.-.-.-
def _display_status() -> dict[str, Any]:
    try:
        from actions.display_manager import display_manager

        raw = display_manager({"action": "list"})
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


# -.-.-.-
def build_runtime_snapshot(
    config: Mapping[str, Any] | None = None,
    *,
    computer_use_status: Mapping[str, Any] | None = None,
    display_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    runtime = dict(config or get_config())
    agent = dict(computer_use_status or _computer_use_status())
    displays = dict(display_status or _display_status())

    cost_mode = str(runtime.get("computer_use_cost_mode") or "economy").strip().lower()
    openai_ready = bool(str(runtime.get("openai_api_key") or "").strip())

    display_label = "Auto"
    active_display = None
    for item in displays.get("displays") or []:
        if isinstance(item, dict) and item.get("active"):
            active_display = item.get("index")
            break

    requested_monitor = agent.get("requested_monitor")
    resolved_monitor = agent.get("monitor_index")
    if requested_monitor not in {None, "", "active", "auto"}:
        display_label = f"Ecrã {resolved_monitor or requested_monitor}"
    elif active_display:
        display_label = f"Ecrã {active_display} · auto"

    agent_state = str(agent.get("state") or "idle").strip().lower()
    agent_label = _AGENT_LABELS.get(agent_state, agent_state.replace("_", " ").title())
    step = int(agent.get("step") or 0)
    calls = int(agent.get("model_calls") or 0)
    batched = int(agent.get("batched_actions") or 0)
    saved_calls = int(agent.get("saved_model_calls") or 0)

    if agent_state in {"observing", "planning", "executing", "awaiting_approval"}:
        agent_detail = f"passo {step} · {calls} IA"
        if saved_calls:
            agent_detail += f" · {saved_calls} chamada(s) poupada(s)"
    elif agent_state == "done" and agent.get("result"):
        agent_detail = str(agent.get("result"))[:80]
        if saved_calls:
            agent_detail += f" · {saved_calls} IA poupada(s)"
    elif agent_state == "failed" and agent.get("last_error"):
        agent_detail = str(agent.get("last_error"))[:80]
    else:
        agent_detail = "Computer Use disponível"

    return {
        "live": "Gemini Live",
        "expert": "OpenAI pronto" if openai_ready else "Opcional",
        "expert_ready": openai_ready,
        "cost": _COST_LABELS.get(cost_mode, cost_mode.title()),
        "cost_mode": cost_mode,
        "display": display_label,
        "display_count": len(displays.get("displays") or []),
        "agent": agent_label,
        "agent_state": agent_state,
        "agent_detail": agent_detail,
        "agent_provider": str(agent.get("provider") or ""),
        "agent_model": str(agent.get("model") or ""),
        "agent_step": step,
        "agent_model_calls": calls,
        "agent_batched_actions": batched,
        "agent_saved_model_calls": saved_calls,
    }
