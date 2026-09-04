from __future__ import annotations

from config import get_config, get_openai_key
from core.model_router import build_expert_prompt, select_reasoning_route
from core.providers.openai_responses import OpenAIResponsesClient


PLUGIN = {
    "name": "expert_reasoning",
    "description": (
        "Optional OpenAI specialist brain for genuinely difficult reasoning. Use balanced for "
        "complex debugging, architecture, analysis or decision support; expert only for the "
        "hardest engineering/reasoning tasks; critic to independently verify an important "
        "plan or conclusion. Do NOT use for casual conversation, simple facts, ordinary "
        "computer commands, direct tool calls, or tasks the primary Gemini Live brain can "
        "answer reliably. This tool reasons only and does not operate the computer."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "task": {
                "type": "STRING",
                "description": "The exact difficult question/problem for the specialist model.",
            },
            "role": {
                "type": "STRING",
                "description": "fast | balanced | expert | critic. Default: balanced.",
            },
            "context": {
                "type": "STRING",
                "description": (
                    "Only the minimum relevant non-secret context needed to solve the task. "
                    "Do not include passwords, API keys or unnecessary personal data."
                ),
            },
        },
        "required": ["task"],
    },
}


# -.-.-.-
def is_available() -> bool:
    return bool(get_openai_key())


# -.-.-.-
def run(parameters: dict, player=None, session_memory=None) -> str:
    params = parameters or {}
    task = str(params.get("task") or "").strip()
    role = str(params.get("role") or "balanced").strip().lower()
    context = str(params.get("context") or "").strip()

    if not task:
        return "Expert reasoning requires a task."

    config = get_config()
    route = select_reasoning_route(config, role=role)

    task = task[:24_000]
    context = context[:20_000]
    prompt = build_expert_prompt(role=role, task=task, context=context)

    if player:
        try:
            player.write_log(
                f"SYS: Expert reasoning · {route.model} · role={role or 'balanced'}"
            )
        except Exception:
            pass

    client = OpenAIResponsesClient(str(config.get("openai_api_key") or ""))
    answer = client.generate_text(
        model=route.model,
        prompt=prompt,
        reasoning_effort=route.reasoning_effort,
    )
    answer = answer.strip()[: route.max_output_chars]

    return (
        f"[EXPERT_RESULT role={role or 'balanced'} model={route.model}]\n"
        f"{answer}"
    )
