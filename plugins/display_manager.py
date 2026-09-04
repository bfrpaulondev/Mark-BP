from __future__ import annotations

from actions.display_manager import display_manager


PLUGIN = {
    "name": "display_manager",
    "description": (
        "Zero-token display inventory for multi-monitor setups. Use it when the user asks "
        "which monitors are available, refers to monitor/screen 1/2/3, or when you need to "
        "resolve the active display before a visual task. It returns monitor indexes, virtual "
        "desktop coordinates, sizes and which monitor contains the foreground window."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "list | resolve. Default: list.",
            },
            "monitor": {
                "type": "STRING",
                "description": "For resolve: active | all | 1 | 2 | 3 or 'monitor 2'.",
            },
        },
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    return display_manager(
        parameters=parameters,
        player=player,
        session_memory=session_memory,
    )
