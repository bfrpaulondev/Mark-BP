"""Windows physical E2E test matrix (ANT-275 C3, C7, C9).

Machine-readable case definitions. Every case declares its capability
requirements (keys produced by ``capability_probe.probe``) so the runner
can mark missing-hardware cases ``NOT AVAILABLE`` instead of pretending.

Risk classes:
- safe: no side effects outside fixture apps/sandbox paths;
- medium: touches real OS state (volume, windows) with bounded recovery;
- dangerous: destructive/irreversible — requires explicit human approval
  gate before execution and is never auto-retried.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class E2ECase:
    case_id: str
    category: str
    description: str
    requirements: tuple[str, ...]
    risk: str = "safe"
    retry_allowed: bool = True


CASES: tuple[E2ECase, ...] = (
    # C3 baseline
    E2ECase("app_launch", "ui", "Launch the Antonella window", ("pyqt6",)),
    E2ECase("window_focus", "ui", "Focus the fixture window", ("pyqt6", "pywinauto")),
    E2ECase("uia_inspect", "uia", "Inspect fixture window tree via UIA", ("pywinauto",)),
    E2ECase("uia_click", "uia", "Click fixture button via UIA", ("pywinauto",)),
    E2ECase("uia_set_text", "uia", "Set fixture textbox text via UIA", ("pywinauto",)),
    E2ECase("mouse_move", "mouse", "Mouse move to fixture coordinates", ("pywinauto",)),
    E2ECase("mouse_click", "mouse", "Mouse click on fixture button", ("pywinauto",)),
    E2ECase("keyboard", "keyboard", "Type into fixture textbox", ("pywinauto",)),
    E2ECase("filesystem", "filesystem", "Create/verify/delete file in sandbox temp dir", ()),
    E2ECase("volume", "audio", "Read and restore volume via pycaw", ("pycaw",), risk="medium"),
    E2ECase("mute", "audio", "Toggle mute and restore", ("pycaw",), risk="medium"),
    E2ECase("brightness", "system", "Read brightness via WMI", ("wmi",), risk="medium"),
    E2ECase("wifi", "system", "Read Wi-Fi state via OS tools", (), risk="medium"),
    E2ECase("browser_tabs", "browser", "Open fixture page, open/switch tabs", ("chrome_available", "playwright")),
    E2ECase("spa", "browser", "SPA route change on local fake SPA", ("chrome_available", "playwright")),
    E2ECase("popup", "browser", "Popup window detection on local fake SPA", ("chrome_available", "playwright")),
    E2ECase("download", "browser", "Local download into sandbox dir", ("chrome_available", "playwright")),
    E2ECase("computer_use_pause", "computer_use", "Pause computer use session", ("pyqt6",), risk="medium"),
    E2ECase("computer_use_resume", "computer_use", "Resume computer use session", ("pyqt6",), risk="medium"),
    E2ECase("computer_use_stop", "computer_use", "Stop computer use session", ("pyqt6",), risk="medium"),
    E2ECase("multi_monitor", "multi_monitor", "Window across two monitors", ("monitor_count>=2",)),
    E2ECase("dpi", "multi_monitor", "DPI change handling", ("pyqt6",)),
    E2ECase("hot_plug", "multi_monitor", "Monitor connect/disconnect handling", (), risk="medium"),
    E2ECase("stale_frame", "multi_monitor", "Stale capture → input must fail closed", ()),
    E2ECase("voice", "voice", "Microphone capture produces audio levels", ("microphone_available",), risk="medium"),
    E2ECase("barge_in", "voice", "Speech during playback interrupts cleanly", ("microphone_available",), risk="medium"),
    # C9 Computer Use failure scenarios
    E2ECase("target_disappeared", "computer_use_failure", "Target window closed mid-task", (), risk="medium"),
    E2ECase("target_moved", "computer_use_failure", "Target window moved mid-task", (), risk="medium"),
    E2ECase("target_minimized", "computer_use_failure", "Target window minimized mid-task", (), risk="medium"),
    E2ECase("window_recreated", "computer_use_failure", "Target window recreated (new HWND)", (), risk="medium"),
    E2ECase("screen_changed", "computer_use_failure", "Screen resolution changed mid-task", (), risk="medium"),
    E2ECase("approval_delayed", "computer_use_failure", "Approval grant arrives late", ()),
    E2ECase("frame_stale", "computer_use_failure", "Capture frame older than input", ()),
    E2ECase("scroll_retry", "computer_use_failure", "Scroll retries bounded", ()),
    E2ECase("click_no_retry", "computer_use_failure", "Click never auto-retries", ()),
    E2ECase("type_no_retry", "computer_use_failure", "Type never auto-retries", ()),
    E2ECase("hotkey_no_retry", "computer_use_failure", "Hotkey never auto-retries", ()),
    E2ECase("stop_during_wait", "computer_use_failure", "Stop honoured during wait", ()),
    E2ECase("stop_during_recovery", "computer_use_failure", "Stop honoured during recovery", ()),
)

CASE_IDS = frozenset(case.case_id for case in CASES)


def get_case(case_id: str) -> E2ECase | None:
    return next((case for case in CASES if case.case_id == case_id), None)
