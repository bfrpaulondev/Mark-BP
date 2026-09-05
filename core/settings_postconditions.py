from __future__ import annotations

import platform
import subprocess
from collections.abc import Mapping
from typing import Any

from core.execution_result import ExecutionResult


SETTINGS_OBSERVABLE_ACTIONS = {
    "volume_set",
    "volume_up",
    "volume_down",
    "mute",
    "unmute",
    "toggle_mute",
    "brightness_up",
    "brightness_down",
    "dark_mode",
    "toggle_wifi",
}


# -.-.-.-
def _windows_volume_state() -> dict[str, Any]:
    if platform.system() != "Windows":
        return {}
    try:
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        device = AudioUtilities.GetSpeakers()
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        endpoint = cast(interface, POINTER(IAudioEndpointVolume))
        scalar = float(endpoint.GetMasterVolumeLevelScalar())
        return {
            "volume_percent": int(round(max(0.0, min(1.0, scalar)) * 100)),
            "muted": bool(endpoint.GetMute()),
        }
    except Exception:
        return {}


# -.-.-.-
def _run_powershell_read(command: str) -> str:
    if platform.system() != "Windows":
        return ""
    creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=4,
            creationflags=creationflags,
        )
        if result.returncode != 0:
            return ""
        return str(result.stdout or "").strip()
    except Exception:
        return ""


# -.-.-.-
def _windows_brightness_state() -> dict[str, Any]:
    raw = _run_powershell_read(
        "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness "
        "| Select-Object -First 1 -ExpandProperty CurrentBrightness)"
    )
    if not raw:
        return {}
    try:
        return {"brightness_percent": max(0, min(100, int(raw.splitlines()[-1].strip())))}
    except (TypeError, ValueError):
        return {}


# -.-.-.-
def _windows_dark_mode_state() -> dict[str, Any]:
    if platform.system() != "Windows":
        return {}
    try:
        import winreg

        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            apps_light, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
            system_light, _kind = winreg.QueryValueEx(key, "SystemUsesLightTheme")
        return {
            "apps_dark": int(apps_light) == 0,
            "system_dark": int(system_light) == 0,
        }
    except Exception:
        return {}


# -.-.-.-
def _windows_wifi_state() -> dict[str, Any]:
    raw = _run_powershell_read(
        "$adapter = Get-NetAdapter | Where-Object {$_.PhysicalMediaType -eq 'Native 802.11'} "
        "| Select-Object -First 1; if ($adapter) { $adapter.Status }"
    )
    if not raw:
        return {}
    status = raw.splitlines()[-1].strip()
    return {
        "wifi_status": status[:64],
        "wifi_enabled": status.casefold() != "disabled",
    }


# -.-.-.-
def capture_settings_state(action: str) -> dict[str, Any]:
    normalized = str(action or "").strip().lower()
    if normalized.startswith("volume") or normalized in {"mute", "unmute", "toggle_mute"}:
        return _windows_volume_state()
    if normalized.startswith("brightness"):
        return _windows_brightness_state()
    if normalized == "dark_mode":
        return _windows_dark_mode_state()
    if normalized == "toggle_wifi":
        return _windows_wifi_state()
    return {}


# -.-.-.-
def verify_settings_postcondition(
    action: str,
    args: Mapping[str, Any] | None,
    *,
    before_state: Mapping[str, Any] | None,
    delivered: bool,
) -> ExecutionResult:
    normalized = str(action or "").strip().lower()
    result_action = f"computer_settings.{normalized or 'unknown'}"
    if not delivered:
        return ExecutionResult.failure(result_action, "Settings command was not delivered.")
    if platform.system() != "Windows":
        return ExecutionResult.unverified_delivery(
            result_action,
            message="Settings command was delivered; this postcondition verifier currently targets Windows.",
        )

    before = dict(before_state or {})
    after = capture_settings_state(normalized)
    evidence = {"before": before, "after": after}
    if not after:
        return ExecutionResult.unverified_delivery(
            result_action,
            evidence=evidence,
            message="Settings command was delivered, but the Windows state could not be read back.",
        )

    params = args or {}
    verified = False

    if normalized == "volume_set":
        try:
            expected = max(0, min(100, int(params.get("value") if params.get("value") is not None else 50)))
        except (TypeError, ValueError):
            expected = 50
        actual = after.get("volume_percent")
        evidence["expected_volume_percent"] = expected
        verified = isinstance(actual, int) and abs(actual - expected) <= 2

    elif normalized == "volume_up":
        verified = (
            isinstance(before.get("volume_percent"), int)
            and isinstance(after.get("volume_percent"), int)
            and int(after["volume_percent"]) > int(before["volume_percent"])
        )

    elif normalized == "volume_down":
        verified = (
            isinstance(before.get("volume_percent"), int)
            and isinstance(after.get("volume_percent"), int)
            and int(after["volume_percent"]) < int(before["volume_percent"])
        )

    elif normalized == "mute":
        verified = after.get("muted") is True

    elif normalized == "unmute":
        verified = after.get("muted") is False

    elif normalized == "toggle_mute":
        verified = (
            isinstance(before.get("muted"), bool)
            and isinstance(after.get("muted"), bool)
            and before.get("muted") != after.get("muted")
        )

    elif normalized == "brightness_up":
        verified = (
            isinstance(before.get("brightness_percent"), int)
            and isinstance(after.get("brightness_percent"), int)
            and int(after["brightness_percent"]) > int(before["brightness_percent"])
        )

    elif normalized == "brightness_down":
        verified = (
            isinstance(before.get("brightness_percent"), int)
            and isinstance(after.get("brightness_percent"), int)
            and int(after["brightness_percent"]) < int(before["brightness_percent"])
        )

    elif normalized == "dark_mode":
        verified = (
            isinstance(before.get("apps_dark"), bool)
            and isinstance(after.get("apps_dark"), bool)
            and before.get("apps_dark") != after.get("apps_dark")
            and isinstance(before.get("system_dark"), bool)
            and isinstance(after.get("system_dark"), bool)
            and before.get("system_dark") != after.get("system_dark")
        )

    elif normalized == "toggle_wifi":
        verified = (
            isinstance(before.get("wifi_enabled"), bool)
            and isinstance(after.get("wifi_enabled"), bool)
            and before.get("wifi_enabled") != after.get("wifi_enabled")
        )

    if verified:
        return ExecutionResult.verified_success(
            result_action,
            evidence=evidence,
            message="Windows setting postcondition was observed and verified.",
        )

    return ExecutionResult.unverified_delivery(
        result_action,
        evidence=evidence,
        message="Settings command was delivered, but the expected state transition was not observed.",
    )
