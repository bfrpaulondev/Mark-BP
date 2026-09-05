from __future__ import annotations

import hashlib
import platform
from collections.abc import Mapping
from typing import Any

from core.execution_result import ExecutionResult


COMPUTER_CONTROL_INPUT_ACTIONS = {
    "type",
    "smart_type",
    "click",
    "left_click",
    "double_click",
    "right_click",
    "move",
    "drag",
    "hotkey",
    "press",
    "scroll",
    "paste",
    "clear_field",
}

WINDOW_SETTING_ACTIONS = {
    "minimize",
    "maximize",
    "switch_window",
}


# -.-.-.-
def _cursor_position() -> tuple[int, int] | None:
    if platform.system() != "Windows":
        return None
    try:
        import win32api

        point = win32api.GetCursorPos()
        return int(point[0]), int(point[1])
    except Exception:
        return None


# -.-.-.-
def _window_snapshot(hwnd: int | None = None) -> dict[str, Any]:
    if platform.system() != "Windows":
        return {}
    try:
        import win32gui
        import win32process

        target = int(hwnd or win32gui.GetForegroundWindow() or 0)
        if not target or not win32gui.IsWindow(target):
            return {"hwnd": target, "exists": False}
        _thread_id, pid = win32process.GetWindowThreadProcessId(target)
        left, top, right, bottom = win32gui.GetWindowRect(target)
        process_name = ""
        try:
            import psutil

            process_name = str(psutil.Process(int(pid)).name() or "").lower()
        except Exception:
            pass
        return {
            "hwnd": target,
            "pid": int(pid),
            "process": process_name,
            "exists": True,
            "visible": bool(win32gui.IsWindowVisible(target)),
            "iconic": bool(win32gui.IsIconic(target)),
            "zoomed": bool(win32gui.IsZoomed(target)),
            "rect": [int(left), int(top), int(right), int(bottom)],
        }
    except Exception:
        return {}


# -.-.-.-
def _window_from_point(point: tuple[int, int] | None) -> dict[str, Any]:
    if platform.system() != "Windows" or point is None:
        return {}
    try:
        import win32gui

        hwnd = int(win32gui.WindowFromPoint((int(point[0]), int(point[1]))) or 0)
        while hwnd:
            parent = int(win32gui.GetParent(hwnd) or 0)
            if not parent:
                break
            hwnd = parent
        return _window_snapshot(hwnd)
    except Exception:
        return {}


# -.-.-.-
def _focused_control_snapshot(foreground_hwnd: int | None) -> dict[str, Any]:
    """Read focused UIA metadata while keeping the actual value private in-memory."""
    if platform.system() != "Windows" or not foreground_hwnd:
        return {}
    try:
        from pywinauto import Desktop

        window = Desktop(backend="uia").window(handle=int(foreground_hwnd))
        candidates = [window]
        try:
            candidates.extend(window.descendants()[:500])
        except Exception:
            pass

        for control in candidates:
            try:
                if not control.has_keyboard_focus():
                    continue
                info = control.element_info
                control_type = str(getattr(info, "control_type", "") or "")
                automation_id = str(getattr(info, "automation_id", "") or "")
                raw_value: str | None = None
                try:
                    value = control.get_value()
                    if value is not None:
                        raw_value = str(value)
                except Exception:
                    pass
                return {
                    "control_type": control_type,
                    "automation_id": automation_id[:160],
                    "value_length": len(raw_value) if raw_value is not None else None,
                    "_value": raw_value,
                }
            except Exception:
                continue
    except Exception:
        pass
    return {}


# -.-.-.-
def _frame_sample(window: Mapping[str, Any]) -> dict[str, Any]:
    """Capture a tiny in-memory grayscale sample; never persists screenshots."""
    if platform.system() != "Windows" or not window.get("exists"):
        return {}
    rect = window.get("rect")
    if not isinstance(rect, list) or len(rect) != 4:
        return {}
    try:
        import mss
        import numpy as np

        left, top, right, bottom = (int(value) for value in rect)
        width = max(1, right - left)
        height = max(1, bottom - top)
        with mss.mss() as sct:
            desktop = sct.monitors[0]
            desk_left = int(desktop["left"])
            desk_top = int(desktop["top"])
            desk_right = desk_left + int(desktop["width"])
            desk_bottom = desk_top + int(desktop["height"])
            clip_left = max(left, desk_left)
            clip_top = max(top, desk_top)
            clip_right = min(right, desk_right)
            clip_bottom = min(bottom, desk_bottom)
            if clip_right <= clip_left or clip_bottom <= clip_top:
                return {}
            image = np.asarray(
                sct.grab(
                    {
                        "left": clip_left,
                        "top": clip_top,
                        "width": clip_right - clip_left,
                        "height": clip_bottom - clip_top,
                    }
                ),
                dtype=np.uint8,
            )
        if image.ndim != 3 or image.shape[0] < 1 or image.shape[1] < 1:
            return {}
        bgr = image[:, :, :3].astype(np.uint16)
        gray = ((bgr[:, :, 0] * 29 + bgr[:, :, 1] * 150 + bgr[:, :, 2] * 77) >> 8).astype(np.uint8)
        y_idx = np.linspace(0, gray.shape[0] - 1, num=min(18, gray.shape[0]), dtype=int)
        x_idx = np.linspace(0, gray.shape[1] - 1, num=min(32, gray.shape[1]), dtype=int)
        sample = gray[np.ix_(y_idx, x_idx)].tobytes()
        return {
            "signature": hashlib.sha256(sample).hexdigest()[:20],
            "sample_length": len(sample),
            "_sample": sample,
            "source_size": [width, height],
        }
    except Exception:
        return {}


# -.-.-.-
def _public_focus(value: Mapping[str, Any] | None) -> dict[str, Any]:
    source = value or {}
    return {
        key: item
        for key, item in source.items()
        if not str(key).startswith("_")
    }


# -.-.-.-
def _public_frame(value: Mapping[str, Any] | None) -> dict[str, Any]:
    source = value or {}
    return {
        key: item
        for key, item in source.items()
        if not str(key).startswith("_")
    }


# -.-.-.-
def _public_state(state: Mapping[str, Any] | None) -> dict[str, Any]:
    source = state or {}
    return {
        "cursor": source.get("cursor"),
        "foreground": source.get("foreground") or {},
        "target_window": source.get("target_window") or {},
        "focus": _public_focus(source.get("focus") if isinstance(source.get("focus"), Mapping) else {}),
        "frame": _public_frame(source.get("frame") if isinstance(source.get("frame"), Mapping) else {}),
    }


# -.-.-.-
def _frame_delta(before: Mapping[str, Any] | None, after: Mapping[str, Any] | None) -> float | None:
    before_sample = (before or {}).get("_sample")
    after_sample = (after or {}).get("_sample")
    if not isinstance(before_sample, (bytes, bytearray)) or not isinstance(after_sample, (bytes, bytearray)):
        return None
    if not before_sample or len(before_sample) != len(after_sample):
        return None
    differences = [abs(int(a) - int(b)) for a, b in zip(before_sample, after_sample)]
    return round(sum(differences) / len(differences), 3) if differences else 0.0


# -.-.-.-
def _focus_identity(value: Mapping[str, Any] | None) -> tuple[str, str]:
    source = value or {}
    return (
        str(source.get("control_type") or ""),
        str(source.get("automation_id") or ""),
    )


# -.-.-.-
def _point_for_action(action: str, args: Mapping[str, Any]) -> tuple[int, int] | None:
    if action == "drag":
        if args.get("x2") is not None and args.get("y2") is not None:
            return int(args["x2"]), int(args["y2"])
        return None
    if args.get("x") is not None and args.get("y") is not None:
        return int(args["x"]), int(args["y"])
    return _cursor_position()


# -.-.-.-
def capture_computer_input_state(action: str, args: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if platform.system() != "Windows":
        return {}
    params = args or {}
    cursor = _cursor_position()
    foreground = _window_snapshot()
    foreground_hwnd = int(foreground.get("hwnd") or 0)
    target_point = _point_for_action(str(action or "").strip().lower(), params)
    return {
        "cursor": list(cursor) if cursor is not None else None,
        "foreground": foreground,
        "target_window": _window_from_point(target_point),
        "focus": _focused_control_snapshot(foreground_hwnd),
        "frame": _frame_sample(foreground),
    }


# -.-.-.-
def capture_window_setting_state(target_hwnd: int | None = None) -> dict[str, Any]:
    if platform.system() != "Windows":
        return {}
    foreground = _window_snapshot()
    hwnd = int(target_hwnd or foreground.get("hwnd") or 0)
    return {
        "foreground": foreground,
        "target": _window_snapshot(hwnd) if hwnd else {},
    }


# -.-.-.-
def _observable_signals(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    before_foreground = before.get("foreground") if isinstance(before.get("foreground"), Mapping) else {}
    after_foreground = after.get("foreground") if isinstance(after.get("foreground"), Mapping) else {}
    before_focus = before.get("focus") if isinstance(before.get("focus"), Mapping) else {}
    after_focus = after.get("focus") if isinstance(after.get("focus"), Mapping) else {}
    frame_delta = _frame_delta(
        before.get("frame") if isinstance(before.get("frame"), Mapping) else {},
        after.get("frame") if isinstance(after.get("frame"), Mapping) else {},
    )
    before_value = before_focus.get("_value")
    after_value = after_focus.get("_value")
    return {
        "foreground_changed": bool(
            before_foreground.get("hwnd")
            and after_foreground.get("hwnd")
            and before_foreground.get("hwnd") != after_foreground.get("hwnd")
        ),
        "focus_changed": _focus_identity(before_focus) != _focus_identity(after_focus),
        "value_readable": isinstance(before_value, str) and isinstance(after_value, str),
        "value_changed": bool(
            isinstance(before_value, str)
            and isinstance(after_value, str)
            and before_value != after_value
        ),
        "frame_delta": frame_delta,
        "frame_changed": bool(frame_delta is not None and frame_delta >= 1.25),
    }


# -.-.-.-
def _cursor_matches(after: Mapping[str, Any], target: tuple[int, int] | None, tolerance: int = 3) -> bool:
    cursor = after.get("cursor")
    if target is None or not isinstance(cursor, list) or len(cursor) != 2:
        return False
    return abs(int(cursor[0]) - int(target[0])) <= tolerance and abs(int(cursor[1]) - int(target[1])) <= tolerance


# -.-.-.-
def verify_computer_input_transition(
    action: str,
    args: Mapping[str, Any] | None,
    before_state: Mapping[str, Any] | None,
    after_state: Mapping[str, Any] | None,
) -> ExecutionResult:
    action_name = str(action or "").strip().lower()
    params = args or {}
    before = dict(before_state or {})
    after = dict(after_state or {})
    full_action = f"computer_control.{action_name}"

    if not before or not after:
        return ExecutionResult.unverified_delivery(
            full_action,
            message="The input command was delivered, but Windows pre/post state was unavailable for verification.",
        )

    signals = _observable_signals(before, after)
    evidence: dict[str, Any] = {
        "before": _public_state(before),
        "after": _public_state(after),
        "signals": signals,
    }

    if action_name == "move":
        target = _point_for_action(action_name, params)
        evidence["signals"]["cursor_matches_target"] = _cursor_matches(after, target)
        if evidence["signals"]["cursor_matches_target"]:
            return ExecutionResult.verified_success(
                full_action,
                evidence=evidence,
                message="Cursor reached the requested desktop coordinate.",
            )
        return ExecutionResult.unverified_delivery(
            full_action,
            evidence=evidence,
            message="Mouse movement was requested, but the final cursor position did not prove the target was reached.",
        )

    if action_name == "drag":
        target = _point_for_action(action_name, params)
        endpoint_ok = _cursor_matches(after, target)
        observable = bool(signals["foreground_changed"] or signals["focus_changed"] or signals["frame_changed"])
        evidence["signals"].update({"cursor_matches_endpoint": endpoint_ok, "observable_effect": observable})
        if endpoint_ok and observable:
            return ExecutionResult.verified_success(
                full_action,
                evidence=evidence,
                message="Drag endpoint and an observable desktop change were confirmed.",
            )
        return ExecutionResult.unverified_delivery(
            full_action,
            evidence=evidence,
            message="The drag gesture was delivered, but its resulting UI effect was not proven.",
        )

    if action_name in {"click", "left_click", "double_click", "right_click"}:
        target = _point_for_action(action_name, params)
        pointer_ok = _cursor_matches(after, target)
        observable = bool(signals["foreground_changed"] or signals["focus_changed"] or signals["frame_changed"] or signals["value_changed"])
        evidence["signals"].update({"cursor_matches_target": pointer_ok, "observable_effect": observable})
        if pointer_ok and observable:
            return ExecutionResult.verified_success(
                full_action,
                evidence=evidence,
                message="Pointer target and an observable click effect were confirmed.",
            )
        return ExecutionResult.unverified_delivery(
            full_action,
            evidence=evidence,
            message="The click was delivered, but its UI effect could not be verified.",
        )

    if action_name == "scroll":
        if signals["frame_changed"]:
            return ExecutionResult.verified_success(
                full_action,
                evidence=evidence,
                message="An observable visual scroll transition was confirmed.",
            )
        return ExecutionResult.unverified_delivery(
            full_action,
            evidence=evidence,
            message="The scroll command was delivered, but no observable content movement was confirmed.",
        )

    if action_name in {"type", "smart_type", "paste", "clear_field"}:
        before_focus = before.get("focus") if isinstance(before.get("focus"), Mapping) else {}
        after_focus = after.get("focus") if isinstance(after.get("focus"), Mapping) else {}
        before_value = before_focus.get("_value")
        after_value = after_focus.get("_value")
        expected = str(params.get("text") or "")
        expected_match = False
        if action_name == "clear_field":
            expected_match = isinstance(after_value, str) and after_value == "" and before_value != after_value
        elif isinstance(after_value, str) and expected:
            if action_name == "smart_type" and bool(params.get("clear_first", True)):
                expected_match = after_value == expected
            else:
                expected_match = after_value.endswith(expected) or expected in after_value
        evidence["signals"].update(
            {
                "expected_length": 0 if action_name == "clear_field" else len(expected),
                "expected_text_match": expected_match,
            }
        )
        if signals["value_changed"] and expected_match:
            return ExecutionResult.verified_success(
                full_action,
                evidence=evidence,
                message="Focused control value changed as expected.",
            )
        return ExecutionResult.unverified_delivery(
            full_action,
            evidence=evidence,
            message="Text/key input was delivered, but the focused control did not expose enough matching state to prove the result.",
        )

    if action_name in {"hotkey", "press"}:
        raw_keys = params.get("keys") if action_name == "hotkey" else params.get("key")
        if isinstance(raw_keys, str):
            keys = [item.strip().lower() for item in raw_keys.replace(" ", "").split("+") if item.strip()]
        elif isinstance(raw_keys, (list, tuple)):
            keys = [str(item).strip().lower() for item in raw_keys if str(item).strip()]
        else:
            keys = []
        key_set = set(keys)
        observable = bool(signals["foreground_changed"] or signals["focus_changed"] or signals["value_changed"] or signals["frame_changed"])
        if {"alt", "tab"}.issubset(key_set):
            observable = bool(signals["foreground_changed"])
        elif keys == ["tab"]:
            observable = bool(signals["focus_changed"])
        evidence["signals"].update({"keys": keys, "observable_effect": observable})
        if observable:
            return ExecutionResult.verified_success(
                full_action,
                evidence=evidence,
                message="An observable desktop effect from the key input was confirmed.",
            )
        return ExecutionResult.unverified_delivery(
            full_action,
            evidence=evidence,
            message="The key input was delivered, but its resulting desktop effect was not proven.",
        )

    return ExecutionResult.unverified_delivery(
        full_action,
        evidence=evidence,
        message="No specialised desktop-input postcondition is available for this action yet.",
    )


# -.-.-.-
def verify_computer_input_postcondition(
    action: str,
    args: Mapping[str, Any] | None,
    *,
    before_state: Mapping[str, Any] | None,
) -> ExecutionResult:
    after = capture_computer_input_state(action, args)
    return verify_computer_input_transition(action, args, before_state, after)


# -.-.-.-
def verify_window_setting_transition(
    action: str,
    before_state: Mapping[str, Any] | None,
    after_state: Mapping[str, Any] | None,
) -> ExecutionResult:
    action_name = str(action or "").strip().lower()
    full_action = f"computer_settings.{action_name}"
    before = dict(before_state or {})
    after = dict(after_state or {})
    before_target = before.get("target") if isinstance(before.get("target"), Mapping) else {}
    after_target = after.get("target") if isinstance(after.get("target"), Mapping) else {}
    before_foreground = before.get("foreground") if isinstance(before.get("foreground"), Mapping) else {}
    after_foreground = after.get("foreground") if isinstance(after.get("foreground"), Mapping) else {}
    evidence = {
        "before": {"foreground": before_foreground, "target": before_target},
        "after": {"foreground": after_foreground, "target": after_target},
    }

    if not before_target.get("hwnd"):
        return ExecutionResult.unverified_delivery(
            full_action,
            evidence=evidence,
            message="No foreground target window was captured before the window command.",
        )

    if action_name == "minimize":
        verified = bool(after_target.get("exists") and after_target.get("iconic"))
    elif action_name == "maximize":
        verified = bool(after_target.get("exists") and after_target.get("zoomed"))
    elif action_name == "switch_window":
        verified = bool(
            before_foreground.get("hwnd")
            and after_foreground.get("hwnd")
            and before_foreground.get("hwnd") != after_foreground.get("hwnd")
        )
    else:
        verified = False

    if verified:
        return ExecutionResult.verified_success(
            full_action,
            evidence=evidence,
            message=f"Window action '{action_name}' was confirmed from Windows state.",
        )
    return ExecutionResult.unverified_delivery(
        full_action,
        evidence=evidence,
        message=f"Window action '{action_name}' was delivered, but the expected Windows state was not confirmed.",
    )


# -.-.-.-
def verify_window_setting_postcondition(
    action: str,
    *,
    before_state: Mapping[str, Any] | None,
) -> ExecutionResult:
    before = dict(before_state or {})
    before_target = before.get("target") if isinstance(before.get("target"), Mapping) else {}
    target_hwnd = int(before_target.get("hwnd") or 0)
    after = capture_window_setting_state(target_hwnd or None)
    return verify_window_setting_transition(action, before, after)
