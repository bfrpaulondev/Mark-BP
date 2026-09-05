from __future__ import annotations

from actions.display_manager import display_manager


PLUGIN = {
    "name": "display_manager",
    "description": (
        "Zero-token live display inventory for multi-monitor Windows setups. Use it when the user asks "
        "which monitors are available, refers to monitor/screen 1/2/3, changes display layout/scaling, "
        "or when you need to resolve the active display before a visual task. It returns physical virtual "
        "desktop coordinates, sizes, active/primary state, effective DPI/scale and a topology token that "
        "changes when monitor geometry, primary display, DPI or connection state changes. Explicit missing "
        "monitor numbers fail closed instead of silently falling back to another display."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "list | status | resolve. Default: list.",
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
