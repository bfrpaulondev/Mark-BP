from __future__ import annotations

import json
from typing import Any

from core.display_selection import (
    describe_monitors,
    normalize_monitor_hint,
    select_monitor,
    selected_monitor_index,
)
from core.display_topology import (
    active_screen_point,
    describe_dpi_metadata,
    monitor_metadata_by_index,
    per_monitor_dpi_context,
    topology_token,
)


# -.-.-.-
def display_manager(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = str(params.get("action") or "list").strip().lower()

    try:
        import mss
    except ImportError:
        return json.dumps(
            {"ok": False, "error": "Display manager requires mss from the locked install."},
            ensure_ascii=False,
        )

    try:
        with per_monitor_dpi_context():
            with mss.mss() as sct:
                monitors = list(sct.monitors)
        active_point = active_screen_point()
        metadata = monitor_metadata_by_index(monitors)
        token = topology_token(monitors, metadata)

        if action in {"list", "status"}:
            displays = describe_monitors(monitors, active_point=active_point)
            for display in displays:
                display.update(describe_dpi_metadata(int(display["index"]), metadata))
            return json.dumps(
                {
                    "ok": True,
                    "count": len(displays),
                    "displays": displays,
                    "combined": dict(monitors[0]) if monitors else None,
                    "topology_token": token,
                },
                ensure_ascii=False,
            )

        if action == "resolve":
            hint: Any = params.get("monitor")
            normalized_hint = normalize_monitor_hint(hint)
            target = select_monitor(
                monitors,
                point=active_point,
                hint=hint,
                strict_hint=isinstance(normalized_hint, int),
            )
            index = selected_monitor_index(monitors, target)
            dpi = describe_dpi_metadata(index, metadata) if index > 0 else {}
            return json.dumps(
                {
                    "ok": True,
                    "requested": hint,
                    "resolved_index": index,
                    "monitor": dict(target),
                    "dpi": dpi,
                    "topology_token": token,
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {"ok": False, "error": "Use action=list or resolve."},
            ensure_ascii=False,
        )
    except ValueError as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
    except Exception as exc:
        if player:
            try:
                player.write_log(f"SYS: Display manager · {exc}")
            except Exception:
                pass
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
