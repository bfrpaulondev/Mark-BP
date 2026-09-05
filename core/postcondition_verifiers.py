from __future__ import annotations

import platform
from collections.abc import Mapping
from typing import Any

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
    return " ".join(str(value or "").strip().lower().split())


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
def verify_open_app_postcondition(app_name: str) -> ExecutionResult:
    if platform.system() != "Windows":
        return ExecutionResult.unverified_delivery(
            "open_app",
            message="Application launch was requested; this postcondition verifier currently targets Windows.",
        )

    expected = _expected_windows_processes(app_name)
    processes = _running_process_matches(expected)
    if not processes:
        return ExecutionResult.failure(
            "open_app",
            f"No expected process was observed after requesting '{app_name}'.",
            delivered=True,
            evidence={"expected_processes": sorted(expected)},
        )

    pids = {int(item["pid"]) for item in processes if int(item.get("pid") or 0) > 0}
    windows = _visible_windows_for_pids(pids)
    evidence = {
        "expected_processes": sorted(expected),
        "processes": processes[:10],
        "visible_windows": windows[:10],
    }
    return ExecutionResult.verified_success(
        "open_app",
        evidence=evidence,
        message=(
            f"Application '{app_name}' is running and a visible window was observed."
            if windows
            else f"Application '{app_name}' is running after the launch request."
        ),
    )


# -.-.-.-
def verify_postcondition(
    tool_name: str,
    args: Mapping[str, Any] | None,
    raw_result: Any,
) -> ExecutionResult:
    """Run the strongest available domain verifier, otherwise fail closed."""
    name = str(tool_name or "").strip().lower()
    params = args or {}
    generic = verify_tool_result(raw_result, action=name)

    if generic.can_claim_success or generic.error or generic.requires_approval:
        return generic

    if name == "open_app" and generic.delivered:
        app_name = str(params.get("app_name") or "").strip()
        if app_name:
            return verify_open_app_postcondition(app_name)

    return generic
