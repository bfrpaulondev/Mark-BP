from __future__ import annotations

from config import get_config, get_gemini_key, get_openai_key
from core.model_router import build_expert_prompt
from core.provider_router import ProviderRouter


PLUGIN = {
    "name": "expert_reasoning",
    "description": (
        "Optional specialist brain for genuinely difficult reasoning. Use balanced for complex "
        "debugging, architecture, analysis or decision support; expert only for the hardest "
        "engineering/reasoning tasks; critic to independently verify an important plan or "
        "conclusion. The provider router selects an available specialist provider and can fail "
        "over safely when the preferred provider is unavailable. Do NOT use for casual "
        "conversation, simple facts, ordinary computer commands, direct tool calls, or tasks "
        "the primary Gemini Live brain can answer reliably. This tool reasons only and does "
        "not operate the computer."
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
    return bool(get_openai_key() or get_gemini_key())


# -.-.-.-
def run(parameters: dict, player=None, session_memory=None) -> str:
    params = parameters or {}
    task = str(params.get("task") or "").strip()
    role = str(params.get("role") or "balanced").strip().lower()
    context = str(params.get("context") or "").strip()

    if not task:
        return "Expert reasoning requires a task."

    config = get_config()
    task = task[:24_000]
    context = context[:20_000]
    prompt = build_expert_prompt(role=role, task=task, context=context)

    router = ProviderRouter(config)
    result = router.generate_text(prompt=prompt, role=role)

    if player:
        try:
            fallback = f" · fallback={result.fallback_count}" if result.fallback_count else ""
            player.write_log(
                f"SYS: Expert reasoning · {result.provider}/{result.model} · "
                f"role={role or 'balanced'}{fallback}"
            )
        except Exception:
            pass

    return (
        f"[EXPERT_RESULT role={role or 'balanced'} provider={result.provider} "
        f"model={result.model} fallback={result.fallback_count}]\n"
        f"{result.text}"
    )
