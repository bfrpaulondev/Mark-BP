from __future__ import annotations

import importlib.util

from actions.verified_browser_automation import verified_browser_automation
from actions.verified_browser_events import verified_browser_event_action


_EVENT_ACTIONS = {
    "click",
    "smart_click",
    "click_popup",
    "click_download",
}


PLUGIN = {
    "name": "verified_browser_automation",
    "description": (
        "Verified Playwright automation for an explicitly managed browser session. Use this for DOM workflows "
        "that need go_to/search/click/type/scroll/forms/history/tab lifecycle with postconditions. Generic "
        "click/smart_click also use a local DOM-mutation probe so SPA updates can be verified without screenshots. "
        "Use click_popup when the requested click is expected to open a new page, and click_download when the "
        "requested click is expected to start a download. This is NOT the user's already-open browser window; "
        "for existing real windows/tabs use verified_desktop_control. The result exposes an explicit verified "
        "boolean and unverified effects must never be reported as done."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "session_status | go_to | search | click | smart_click | click_popup | click_download | "
                    "type | smart_type | scroll | fill_form | new_tab | close_tab | back | forward | reload"
                ),
            },
            "browser": {
                "type": "STRING",
                "description": "Optional managed browser: chrome | edge | firefox | opera | brave | vivaldi.",
            },
            "url": {"type": "STRING", "description": "URL for go_to/new_tab."},
            "query": {"type": "STRING", "description": "Search query for search."},
            "engine": {"type": "STRING", "description": "Search engine for search; default google."},
            "selector": {"type": "STRING", "description": "DOM selector for click/type or event-trigger actions."},
            "description": {
                "type": "STRING",
                "description": "Accessible description for smart_click/smart_type/click_popup/click_download.",
            },
            "text": {"type": "STRING", "description": "Text/visible label to enter or target. Input values are not copied into execution evidence."},
            "clear_first": {"type": "BOOLEAN", "description": "Clear an input before typing; default true."},
            "direction": {"type": "STRING", "description": "Scroll direction: up | down."},
            "amount": {"type": "INTEGER", "description": "Scroll amount, locally bounded."},
            "fields": {"type": "OBJECT", "description": "Selector-to-value mapping for fill_form."},
            "settle_ms": {
                "type": "INTEGER",
                "description": "Optional local settle time for click/SPA verification; bounded to 50-2000 ms.",
            },
            "timeout_ms": {
                "type": "INTEGER",
                "description": "Optional popup/download event timeout; locally bounded.",
            },
            "follow_popup": {
                "type": "BOOLEAN",
                "description": "For click_popup, make the verified popup the active managed page; default true.",
            },
            "save_download": {
                "type": "BOOLEAN",
                "description": (
                    "For click_download, persist the verified file under the user's Downloads folder. "
                    "Default false; set true only when the user asked to save/download the file."
                ),
            },
        },
        "required": ["action"],
    },
}


# -.-.-.-
def is_available() -> bool:
    return importlib.util.find_spec("playwright") is not None


# -.-.-.-
def run(parameters: dict, player=None, session_memory=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "").strip().lower()
    if action in _EVENT_ACTIONS:
        return verified_browser_event_action(
            parameters=params,
            player=player,
            session_memory=session_memory,
        )
    return verified_browser_automation(
        parameters=params,
        player=player,
        session_memory=session_memory,
    )
