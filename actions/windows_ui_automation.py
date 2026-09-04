from __future__ import annotations

import json
import platform
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ControlSummary:
    name: str
    control_type: str
    automation_id: str
    class_name: str
    enabled: bool
    visible: bool
    rectangle: tuple[int, int, int, int] | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "control_type": self.control_type,
            "automation_id": self.automation_id,
            "class_name": self.class_name,
            "enabled": self.enabled,
            "visible": self.visible,
            "rectangle": list(self.rectangle) if self.rectangle else None,
        }


# -.-.-.-
def _require_windows() -> None:
    if platform.system() != "Windows":
        raise RuntimeError("Windows UI Automation is available only on Windows.")


# -.-.-.-
def _load_pywinauto():
    _require_windows()
    try:
        from pywinauto import Desktop
    except ImportError as exc:
        raise RuntimeError(
            "Windows UI Automation requires pywinauto from the locked Windows install."
        ) from exc
    return Desktop


# -.-.-.-
def _foreground_handle() -> int:
    _require_windows()
    import ctypes

    handle = int(ctypes.windll.user32.GetForegroundWindow())
    if not handle:
        raise RuntimeError("Could not resolve the foreground window.")
    return handle


# -.-.-.-
def _window_wrapper(title: str = ""):
    Desktop = _load_pywinauto()
    desktop = Desktop(backend="uia")
    normalized = str(title or "").strip()

    if not normalized:
        return desktop.window(handle=_foreground_handle())

    windows = desktop.windows()
    ranked: list[tuple[int, Any]] = []
    needle = normalized.casefold()
    for window in windows:
        try:
            text = str(window.window_text() or "")
        except Exception:
            continue
        haystack = text.casefold()
        if not haystack:
            continue
        if haystack == needle:
            score = 0
        elif haystack.startswith(needle):
            score = 1
        elif needle in haystack:
            score = 2
        else:
            continue
        ranked.append((score, window))

    if not ranked:
        raise RuntimeError(f"No visible window matched '{normalized}'.")

    ranked.sort(key=lambda item: item[0])
    return ranked[0][1]


# -.-.-.-
def _safe_rectangle(control: Any) -> tuple[int, int, int, int] | None:
    try:
        rect = control.rectangle()
        return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)
    except Exception:
        return None


# -.-.-.-
def _summary(control: Any) -> ControlSummary:
    info = getattr(control, "element_info", None)

    def _attr(name: str, default: Any = "") -> Any:
        try:
            value = getattr(info, name, default) if info is not None else default
            return value() if callable(value) else value
        except Exception:
            return default

    try:
        enabled = bool(control.is_enabled())
    except Exception:
        enabled = bool(_attr("enabled", False))

    try:
        visible = bool(control.is_visible())
    except Exception:
        visible = bool(_attr("visible", False))

    name = str(_attr("name", "") or "")
    if not name:
        try:
            name = str(control.window_text() or "")
        except Exception:
            name = ""

    return ControlSummary(
        name=name,
        control_type=str(_attr("control_type", "") or ""),
        automation_id=str(_attr("automation_id", "") or ""),
        class_name=str(_attr("class_name", "") or ""),
        enabled=enabled,
        visible=visible,
        rectangle=_safe_rectangle(control),
    )


# -.-.-.-
def _candidate_score(
    summary: ControlSummary,
    *,
    name: str = "",
    automation_id: str = "",
    control_type: str = "",
) -> int | None:
    target_name = str(name or "").strip().casefold()
    target_id = str(automation_id or "").strip().casefold()
    target_type = str(control_type or "").strip().casefold()

    if target_id and summary.automation_id.casefold() == target_id:
        if target_type and summary.control_type.casefold() != target_type:
            return None
        return 0

    if target_name:
        candidate = summary.name.casefold()
        if candidate == target_name:
            score = 1
        elif candidate.startswith(target_name):
            score = 2
        elif target_name in candidate:
            score = 3
        else:
            return None
        if target_type and summary.control_type.casefold() != target_type:
            return None
        return score

    if target_type and summary.control_type.casefold() == target_type:
        return 4

    return None


# -.-.-.-
def _find_control(
    window: Any,
    *,
    name: str = "",
    automation_id: str = "",
    control_type: str = "",
    max_scan: int = 500,
) -> tuple[Any, ControlSummary] | None:
    candidates: list[tuple[int, int, Any, ControlSummary]] = []
    try:
        descendants = window.descendants()
    except Exception as exc:
        raise RuntimeError(f"Could not enumerate UI Automation controls: {exc}") from exc

    for index, control in enumerate(descendants[: max(1, min(2000, max_scan))]):
        summary = _summary(control)
        score = _candidate_score(
            summary,
            name=name,
            automation_id=automation_id,
            control_type=control_type,
        )
        if score is not None:
            candidates.append((score, index, control, summary))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    _, _, control, summary = candidates[0]
    return control, summary


# -.-.-.-
def _list_windows(limit: int) -> list[dict[str, Any]]:
    Desktop = _load_pywinauto()
    desktop = Desktop(backend="uia")
    output: list[dict[str, Any]] = []
    for window in desktop.windows()[: max(1, min(100, limit))]:
        summary = _summary(window)
        if not summary.name:
            continue
        output.append(summary.as_dict())
    return output


# -.-.-.-
def _inspect_window(window: Any, limit: int) -> dict[str, Any]:
    root = _summary(window)
    controls: list[dict[str, Any]] = []
    try:
        descendants: Iterable[Any] = window.descendants()
    except Exception as exc:
        raise RuntimeError(f"Could not inspect window controls: {exc}") from exc

    for control in descendants:
        summary = _summary(control)
        if not (summary.name or summary.automation_id):
            continue
        controls.append(summary.as_dict())
        if len(controls) >= max(1, min(250, limit)):
            break

    return {"window": root.as_dict(), "controls": controls, "truncated": len(controls) >= limit}


# -.-.-.-
def _activate_control(control: Any) -> str:
    try:
        control.invoke()
        return "invoked"
    except Exception:
        pass
    try:
        control.click_input()
        return "clicked"
    except Exception as exc:
        raise RuntimeError(f"Control could not be activated: {exc}") from exc


# -.-.-.-
def _set_control_text(control: Any, text: str, clear_first: bool) -> str:
    if clear_first:
        try:
            control.set_edit_text("")
        except Exception:
            try:
                control.type_keys("^a{BACKSPACE}", set_foreground=True)
            except Exception:
                pass

    try:
        control.set_edit_text(text)
        return "set_edit_text"
    except Exception:
        pass

    try:
        control.set_focus()
        control.type_keys(text, with_spaces=True, set_foreground=True)
        return "type_keys"
    except Exception as exc:
        raise RuntimeError(f"Could not enter text in control: {exc}") from exc


# -.-.-.-
def windows_ui_automation(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = str(params.get("action") or "").strip().lower()
    title = str(params.get("window") or params.get("title") or "").strip()
    limit = int(params.get("limit") or 80)

    if not action:
        return json.dumps({"ok": False, "error": "No UI Automation action specified."})

    try:
        if action == "list_windows":
            result = {"ok": True, "windows": _list_windows(limit)}
            return json.dumps(result, ensure_ascii=False)

        window = _window_wrapper(title)

        if action == "inspect":
            result = {"ok": True, **_inspect_window(window, limit)}
            return json.dumps(result, ensure_ascii=False)

        found = _find_control(
            window,
            name=str(params.get("name") or ""),
            automation_id=str(params.get("automation_id") or ""),
            control_type=str(params.get("control_type") or ""),
            max_scan=int(params.get("max_scan") or 500),
        )
        if not found:
            return json.dumps(
                {"ok": False, "error": "Control not found through Windows UI Automation."},
                ensure_ascii=False,
            )

        control, summary = found

        if action == "find":
            return json.dumps(
                {"ok": True, "control": summary.as_dict()},
                ensure_ascii=False,
            )

        if action == "click":
            method = _activate_control(control)
            return json.dumps(
                {"ok": True, "method": method, "control": summary.as_dict()},
                ensure_ascii=False,
            )

        if action == "set_text":
            method = _set_control_text(
                control,
                str(params.get("text") or ""),
                bool(params.get("clear_first", True)),
            )
            return json.dumps(
                {"ok": True, "method": method, "control": summary.as_dict()},
                ensure_ascii=False,
            )

        return json.dumps(
            {"ok": False, "error": f"Unknown UI Automation action: {action}"},
            ensure_ascii=False,
        )

    except Exception as exc:
        if player:
            try:
                player.write_log(f"SYS: Windows UI Automation · {exc}")
            except Exception:
                pass
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
