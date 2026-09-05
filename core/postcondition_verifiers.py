from __future__ import annotations

import platform
import unicodedata
from collections.abc import Mapping
from typing import Any

from core.desktop_postconditions import (
    COMPUTER_CONTROL_INPUT_ACTIONS,
    WINDOW_SETTING_ACTIONS,
    capture_computer_input_state,
    capture_window_setting_state,
    verify_computer_input_postcondition,
    verify_window_setting_postcondition,
)
from core.execution_result import ExecutionResult
from core.verifier import verify_tool_result


_WINDOWS_APP_PROCESSES: dict[str, set[str]] = {
    "chrome": {"chrome.exe"},
    "google chrome": {"chrome.exe"},
    "edge": {"msedge.exe"},
    "microsoft edge": {"msedge.exe"},
    "firefox": {"firefox.exe"},
    "brave": {"brave.exe"},
    "opera": {"opera.exe"},
    "whatsapp": {"whatsapp.exe"},
    "telegram": {"telegram.exe"},
    "discord": {"discord.exe"},
    "slack": {"slack.exe"},
    "zoom": {"zoom.exe"},
    "teams": {"ms-teams.exe", "msteams.exe"},
    "spotify": {"spotify.exe"},
    "vlc": {"vlc.exe"},
    "vscode": {"code.exe"},
    "visual studio code": {"code.exe"},
    "code": {"code.exe"},
    "terminal": {"windowsterminal.exe", "wt.exe"},
    "cmd": {"cmd.exe"},
    "powershell": {"powershell.exe", "pwsh.exe"},
    "postman": {"postman.exe"},
    "figma": {"figma.exe"},
    "blender": {"blender.exe"},
    "word": {"winword.exe"},
    "excel": {"excel.exe"},
    "powerpoint": {"powerpnt.exe"},
    "notepad": {"notepad.exe"},
    "bloco de notas": {"notepad.exe"},
    "explorer": {"explorer.exe"},
    "file explorer": {"explorer.exe"},
    "explorador de ficheiros": {"explorer.exe"},
    "task manager": {"taskmgr.exe"},
    "gestor de tarefas": {"taskmgr.exe"},
    "settings": {"systemsettings.exe"},
    "definicoes": {"systemsettings.exe"},
    "calculator": {"calculatorapp.exe", "calculator.exe"},
    "calculadora": {"calculatorapp.exe", "calculator.exe"},
    "paint": {"mspaint.exe"},
    "notion": {"notion.exe"},
    "obsidian": {"obsidian.exe"},
    "capcut": {"capcut.exe"},
    "steam": {"steam.exe"},
    "epic": {"epicgameslauncher.exe"},
    "epic games": {"epicgameslauncher.exe"},
}


# -.-.-.-
def _normalize_app_name(value: str) -> str:
    raw = " ".join(str(value or "").strip().lower().split())
    normalized = unicodedata.normalize("NFKD", raw)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


# -.-.-.-
def _expected_windows_processes(app_name: str) -> set[str]:
    normalized = _normalize_app_name(app_name)
    if normalized in _WINDOWS_APP_PROCESSES:
        return set(_WINDOWS_APP_PROCESSES[normalized])

    compact = normalized.replace(" ", "")
    if not compact:
        return set()
    return {f"{compact}.exe"}


# -.-.-.-
def _running_process_matches(expected: set[str]) -> list[dict[str, Any]]:
    if not expected:
        return []
    try:
        import psutil
    except ImportError:
        return []

    matches: list[dict[str, Any]] = []
    expected_lower = {value.lower() for value in expected}
    for process in psutil.process_iter(["pid", "name"]):
        try:
            name = str(process.info.get("name") or "").lower()
            if name in expected_lower:
                matches.append({"pid": int(process.info.get("pid") or 0), "process": name})
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
            continue
    return matches


# -.-.-.-
def _visible_windows_for_pids(pids: set[int]) -> list[dict[str, Any]]:
    if platform.system() != "Windows" or not pids:
        return []
    try:
        import win32gui
        import win32process
    except ImportError:
        return []

    windows: list[dict[str, Any]] = []

    def _collect(hwnd, _extra):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
            if int(pid) not in pids:
                return True
            title = str(win32gui.GetWindowText(hwnd) or "").strip()
            if title:
                windows.append({"hwnd": int(hwnd), "pid": int(pid), "title": title})
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_collect, None)
    except Exception:
        return []
    return windows


# -.-.-.-
def _foreground_window_snapshot() -> dict[str, Any]:
    if platform.system() != "Windows":
        return {}
    try:
        import win32gui
        import win32process

        hwnd = int(win32gui.GetForegroundWindow() or 0)
        if not hwnd:
            return {}
        _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
        title = str(win32gui.GetWindowText(hwnd) or "").strip()
        return {"hwnd": hwnd, "pid": int(pid), "title": title}
    except Exception:
        return {}


# -.-.-.-
def capture_open_app_state(app_name: str) -> dict[str, Any]:
    """Capture the observable Windows state used to attribute an app launch."""
    if platform.system() != "Windows":
        return {}

    expected = _expected_windows_processes(app_name)
    processes = _running_process_matches(expected)
    pids = {int(item["pid"]) for item in processes if int(item.get("pid") or 0) > 0}
    windows = _visible_windows_for_pids(pids)
    return {
        "expected_processes": sorted(expected),
        "processes": processes[:10],
        "visible_windows": windows[:10],
        "foreground": _foreground_window_snapshot(),
    }


# -.-.-.-
def capture_postcondition_state(
    tool_name: str,
    args: Mapping[str, Any] | None,
) -> dict[str, Any]:
    name = str(tool_name or "").strip().lower()
    params = args or {}
    action = str(params.get("action") or "").strip().lower()
    if name == "open_app":
        return capture_open_app_state(str(params.get("app_name") or "").strip())
    if name == "computer_control" and action in COMPUTER_CONTROL_INPUT_ACTIONS:
        return capture_computer_input_state(action, params)
    if name == "computer_settings" and action in WINDOW_SETTING_ACTIONS:
        return capture_window_setting_state()
    return {}


# -.-.-.-
def verify_open_app_postcondition(
    app_name: str,
    *,
    before_state: Mapping[str, Any] | None = None,
) -> ExecutionResult:
    if platform.system() != "Windows":
        return ExecutionResult.unverified_delivery(
            "open_app",
            message="Application launch was requested; this postcondition verifier currently targets Windows.",
        )

    after = capture_open_app_state(app_name)
    expected = set(after.get("expected_processes") or _expected_windows_processes(app_name))
    processes = list(after.get("processes") or [])
    if not processes:
        return ExecutionResult.failure(
            "open_app",
            f"No expected process was observed after requesting '{app_name}'.",
            delivered=True,
            evidence={"expected_processes": sorted(expected)},
        )

    if before_state is None:
        return ExecutionResult.unverified_delivery(
            "open_app",
            evidence={"after": after},
            message=(
                f"Application '{app_name}' is running, but no pre-action state was captured "
                "to attribute that state to this request."
            ),
        )

    before = dict(before_state)
    before_pids = {
        int(item.get("pid") or 0)
        for item in before.get("processes", [])
        if isinstance(item, Mapping)
    }
    after_pids = {
        int(item.get("pid") or 0)
        for item in processes
        if isinstance(item, Mapping)
    }
    before_windows = {
        int(item.get("hwnd") or 0)
        for item in before.get("visible_windows", [])
        if isinstance(item, Mapping)
    }
    after_windows = {
        int(item.get("hwnd") or 0)
        for item in after.get("visible_windows", [])
        if isinstance(item, Mapping)
    }
    before_foreground = (
        before.get("foreground") if isinstance(before.get("foreground"), Mapping) else {}
    )
    after_foreground = (
        after.get("foreground") if isinstance(after.get("foreground"), Mapping) else {}
    )
    foreground_pid = int(after_foreground.get("pid") or 0)
    foreground_changed = bool(
        after_foreground.get("hwnd")
        and after_foreground.get("hwnd") != before_foreground.get("hwnd")
        and foreground_pid in after_pids
    )
    delta = {
        "new_process_pids": sorted(pid for pid in after_pids - before_pids if pid),
        "new_window_handles": sorted(hwnd for hwnd in after_windows - before_windows if hwnd),
        "foreground_changed_to_target": foreground_changed,
    }
    evidence = {
        "before": before,
        "after": after,
        "delta": delta,
    }
    if delta["new_process_pids"] or delta["new_window_handles"] or foreground_changed:
        return ExecutionResult.verified_success(
            "open_app",
            evidence=evidence,
            message=f"An observable application transition was confirmed for '{app_name}'.",
        )

    return ExecutionResult.unverified_delivery(
        "open_app",
        evidence=evidence,
        message=(
            f"Application '{app_name}' is running, but no observable change could be "
            "attributed to this request."
        ),
    )


# -.-.-.-
def verify_focus_window_postcondition(title: str) -> ExecutionResult:
    requested = str(title or "").strip()
    if not requested:
        return ExecutionResult.failure("computer_control.focus_window", "No target window title was provided.")
    if platform.system() != "Windows":
        return ExecutionResult.unverified_delivery(
            "computer_control.focus_window",
            message="Focus command was delivered; this postcondition verifier currently targets Windows.",
        )

    foreground = _foreground_window_snapshot()
    actual_title = str(foreground.get("title") or "").strip()
    verified = bool(actual_title and requested.casefold() in actual_title.casefold())
    evidence = {"requested_title": requested, "foreground": foreground}
    if verified:
        return ExecutionResult.verified_success(
            "computer_control.focus_window",
            evidence=evidence,
            message=f"Foreground window matches '{requested}'.",
        )
    return ExecutionResult.failure(
        "computer_control.focus_window",
        f"Foreground window did not match '{requested}' after the focus request.",
        delivered=True,
        evidence=evidence,
    )


# -.-.-.-
def verify_postcondition(
    tool_name: str,
    args: Mapping[str, Any] | None,
    raw_result: Any,
    *,
    before_state: Mapping[str, Any] | None = None,
) -> ExecutionResult:
    """Run the strongest available domain verifier, otherwise fail closed."""
    name = str(tool_name or "").strip().lower()
    params = args or {}
    action = str(params.get("action") or "").strip().lower()
    generic = verify_tool_result(raw_result, action=name)

    if generic.can_claim_success or generic.error or generic.requires_approval:
        return generic

    if name == "open_app" and generic.delivered:
        app_name = str(params.get("app_name") or "").strip()
        if app_name:
            return verify_open_app_postcondition(app_name, before_state=before_state)

    if name == "computer_control" and action == "focus_window" and generic.delivered:
        return verify_focus_window_postcondition(str(params.get("title") or ""))

    if name == "computer_control" and action in COMPUTER_CONTROL_INPUT_ACTIONS and generic.delivered:
        return verify_computer_input_postcondition(
            action,
            params,
            before_state=before_state,
        )

    if name == "computer_settings" and action in WINDOW_SETTING_ACTIONS and generic.delivered:
        return verify_window_setting_postcondition(
            action,
            before_state=before_state,
        )

    return generic
