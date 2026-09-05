from __future__ import annotations

import importlib.util

from actions.verified_browser_automation import verified_browser_automation


PLUGIN = {
    "name": "verified_browser_automation",
    "description": (
        "Verified Playwright automation for an explicitly managed browser session. Use this for DOM workflows "
        "that need go_to/search/click/type/scroll/forms/history/tab lifecycle with postconditions. This is NOT "
        "the user's already-open browser window; for existing real windows/tabs use verified_desktop_control. "
        "The result exposes an explicit verified boolean and unverified effects must never be reported as done."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "session_status | go_to | search | click | smart_click | type | smart_type | scroll | "
                    "fill_form | new_tab | close_tab | back | forward | reload"
                ),
            },
            "browser": {
                "type": "STRING",
                "description": "Optional managed browser: chrome | edge | firefox | opera | brave | vivaldi.",
            },
            "url": {"type": "STRING", "description": "URL for go_to/new_tab."},
            "query": {"type": "STRING", "description": "Search query for search."},
            "engine": {"type": "STRING", "description": "Search engine for search; default google."},
            "selector": {"type": "STRING", "description": "DOM selector for click/type."},
            "description": {"type": "STRING", "description": "Accessible description for smart_click/smart_type."},
            "text": {"type": "STRING", "description": "Text to enter. The value is not copied into execution evidence."},
            "clear_first": {"type": "BOOLEAN", "description": "Clear an input before typing; default true."},
            "direction": {"type": "STRING", "description": "Scroll direction: up | down."},
            "amount": {"type": "INTEGER", "description": "Scroll amount, locally bounded."},
            "fields": {"type": "OBJECT", "description": "Selector-to-value mapping for fill_form."},
        },
        "required": ["action"],
    },
}


# -.-.-.-
def is_available() -> bool:
    return importlib.util.find_spec("playwright") is not None


# -.-.-.-
def run(parameters: dict, player=None, session_memory=None) -> str:
    return verified_browser_automation(
        parameters=parameters,
        player=player,
        session_memory=session_memory,
    )
