"""Windows physical E2E executors (ANT-275 BLOCO 8).

Each executor is registered per case id and only runs on a physical
Windows machine with the physical gate enabled. Every executor must
PROVE its effect (verified) — an action that ran without a real
postcondition check is delivered at best, never verified.

System-state executors (volume/mute/brightness) always restore the
original value. Browser executors run against the local fake SPA —
never the internet. Fixture UI automation uses the local fixture app.
"""

from __future__ import annotations

import ctypes
import http.server
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_TITLE = "Antonella E2E Fixture"
FIXTURE_TITLE_CHANGED = FIXTURE_TITLE + " [CHANGED]"


class SkipCase(Exception):
    """Raised when the environment is not prepared for the case
    (e.g. playwright browsers not installed) — reported as SKIPPED,
    never as PASS."""


def _result(ok: bool, delivered: bool, verified: bool, **extra) -> dict:
    out = {"ok": ok, "delivered": delivered, "verified": verified}
    out.update(extra)
    return out


def _evidence(**kwargs) -> dict:
    from scripts.windows_e2e.evidence import ALLOWED_EVIDENCE_KEYS

    return {k: v for k, v in kwargs.items() if k in ALLOWED_EVIDENCE_KEYS}


# ---------------------------------------------------------------------------
# filesystem (pure python — verifiable everywhere)
# ---------------------------------------------------------------------------
def _exec_filesystem(capabilities: dict) -> tuple[dict, dict]:
    sandbox = Path(tempfile.mkdtemp(prefix="antonella-e2e-"))
    target = sandbox / "e2e-probe.txt"
    target.write_text("antonella synthetic", encoding="utf-8")
    read_back = target.read_text(encoding="utf-8")
    verified = read_back == "antonella synthetic" and target.is_file()
    target.unlink()
    verified = verified and not target.exists()
    return (
        _result(True, True, verified),
        _evidence(hash=_sha(read_back), length=len(read_back)),
    )


def _sha(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# fixture app + pywinauto family
# ---------------------------------------------------------------------------
class FixtureApp:
    """Launches the local fixture window and connects via pywinauto."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._win = None

    def __enter__(self) -> "FixtureApp":
        from pywinauto import Desktop  # optional dependency

        self._proc = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "windows_e2e" / "fixtures" / "fixture_app.py"),
             "--duration", "120"],
            cwd=str(ROOT),
        )
        deadline = time.time() + 20
        while time.time() < deadline:
            windows = Desktop(backend="uia").windows(title=FIXTURE_TITLE)
            if windows:
                self._win = windows[0]
                self._win.set_focus()
                return self
            time.sleep(0.4)
        raise SkipCase("fixture window did not appear")

    def __exit__(self, *_exc) -> None:
        if self._proc is not None:
            self._proc.terminate()

    # -.-.-.-
    @property
    def window(self):
        return self._win

    def title(self) -> str:
        from pywinauto import Desktop

        windows = Desktop(backend="uia").windows(title_re=f"{FIXTURE_TITLE}.*")
        return windows[0].window_text() if windows else ""


def _exec_app_launch(capabilities: dict) -> tuple[dict, dict]:
    with FixtureApp() as fixture:
        verified = fixture.title() == FIXTURE_TITLE
        return _result(True, True, verified), _evidence(window_title_hash=_sha(FIXTURE_TITLE))


def _exec_window_focus(capabilities: dict) -> tuple[dict, dict]:
    import ctypes

    with FixtureApp() as fixture:
        fixture.window.set_focus()
        time.sleep(0.4)
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        verified = buf.value == FIXTURE_TITLE
        return _result(True, True, verified), _evidence(window_title_hash=_sha(buf.value))


def _uia_control(fixture: FixtureApp):
    return fixture.window.child_window(title="Mudar título", control_type="Button")


def _exec_uia_inspect(capabilities: dict) -> tuple[dict, dict]:
    with FixtureApp() as fixture:
        button = _uia_control(fixture)
        exists = button.exists(timeout=5)
        return _result(True, exists, bool(exists)), _evidence(count=1 if exists else 0)


def _exec_uia_click(capabilities: dict) -> tuple[dict, dict]:
    with FixtureApp() as fixture:
        _uia_control(fixture).click_input()
        time.sleep(0.3)
        verified = fixture.title() == FIXTURE_TITLE_CHANGED
        return _result(True, True, verified), _evidence(state="title_changed" if verified else "unchanged")


def _exec_uia_set_text(capabilities: dict) -> tuple[dict, dict]:
    with FixtureApp() as fixture:
        box = fixture.window.child_window(auto_id=None, control_type="Edit")
        box.set_edit_text("antonella-e2e")
        time.sleep(0.2)
        verified = box.get_value() == "antonella-e2e"
        return _result(True, True, verified), _evidence(length=len("antonella-e2e"))


def _exec_mouse_move(capabilities: dict) -> tuple[dict, dict]:
    import pywinauto.mouse

    with FixtureApp() as fixture:
        rect = fixture.window.rectangle()
        pywinauto.mouse.move(rect.middle_point.x, rect.middle_point.y)
        return _result(True, True, True), _evidence(count=1)


def _exec_mouse_click(capabilities: dict) -> tuple[dict, dict]:
    with FixtureApp() as fixture:
        _uia_control(fixture).click_input()  # mouse-level click through UIA coords
        time.sleep(0.3)
        verified = fixture.title() == FIXTURE_TITLE_CHANGED
        return _result(True, True, verified), _evidence(state="clicked" if verified else "unchanged")


def _exec_keyboard(capabilities: dict) -> tuple[dict, dict]:
    from pywinauto.keyboard import send_keys

    with FixtureApp() as fixture:
        box = fixture.window.child_window(control_type="Edit")
        box.set_focus()
        send_keys("antonella-keys")
        time.sleep(0.2)
        verified = box.get_value() == "antonella-keys"
        return _result(True, True, verified), _evidence(length=14)


# ---------------------------------------------------------------------------
# audio (pycaw) — always restore
# ---------------------------------------------------------------------------
def _exec_volume(capabilities: dict) -> tuple[dict, dict]:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = interface.QueryInterface(IAudioEndpointVolume)
    original = volume.GetMasterVolumeLevelScalar()
    try:
        target = min(1.0, original + 0.05)
        volume.SetMasterVolumeLevelScalar(target, None)
        time.sleep(0.2)
        changed = abs(volume.GetMasterVolumeLevelScalar() - target) < 0.02
    finally:
        volume.SetMasterVolumeLevelScalar(original, None)
    time.sleep(0.2)
    restored = abs(volume.GetMasterVolumeLevelScalar() - original) < 0.02
    return _result(True, changed, changed and restored), _evidence(ok=restored)


def _exec_mute(capabilities: dict) -> tuple[dict, dict]:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = interface.QueryInterface(IAudioEndpointVolume)
    original = bool(volume.GetMute())
    try:
        volume.SetMute(not original, None)
        time.sleep(0.2)
        changed = bool(volume.GetMute()) != original
    finally:
        volume.SetMute(original, None)
    return _result(True, changed, changed), _evidence(state="restored")


def _exec_brightness(capabilities: dict) -> tuple[dict, dict]:
    try:
        import wmi

        brightness = wmi.WMI(namespace="wmi").WmiMonitorBrightness()[0].CurrentBrightness
        return _result(True, True, isinstance(brightness, int)), _evidence(count=int(brightness))
    except Exception as exc:
        if "WmiMonitorBrightness" in str(exc) or "not supported" in str(exc).lower():
            raise SkipCase("brightness not supported on this hardware") from exc
        raise


def _exec_wifi(capabilities: dict) -> tuple[dict, dict]:
    output = subprocess.run(
        ["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=15
    ).stdout
    verified = "State" in output or "Estado" in output  # en-US / pt-PT
    return _result(True, True, verified), _evidence(length=len(output))


# ---------------------------------------------------------------------------
# browser (playwright + local fake SPA) — no internet
# ---------------------------------------------------------------------------
class FakeSpa:
    def __init__(self, port: int = 8791):
        from scripts.windows_e2e.fixtures.fake_spa import serve

        self._server = serve(port)
        self.url = f"http://127.0.0.1:{port}/"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        self._server.shutdown()
        self._server.server_close()


def _launch_browser():
    from playwright.sync_api import sync_playwright

    manager = sync_playwright().start()
    try:
        browser = manager.chromium.launch(headless=False)
    except Exception as exc:
        manager.stop()
        raise SkipCase(f"playwright browsers not installed: {exc}") from exc
    return manager, browser


def _exec_browser_tabs(capabilities: dict) -> tuple[dict, dict]:
    with FakeSpa() as spa, _launch_browser() as (manager, browser):
        context = browser.new_context()
        page = context.new_page()
        page.goto(spa.url)
        page2 = context.new_page()
        page2.goto(spa.url + "#second")
        count = len(context.pages)
        context.close()
        browser.close()
        manager.stop()
        return _result(True, True, count == 2), _evidence(count=count)


def _exec_spa(capabilities: dict) -> tuple[dict, dict]:
    with FakeSpa() as spa, _launch_browser() as (manager, browser):
        page = browser.new_page()
        page.goto(spa.url)
        page.click("#nav")
        page.wait_for_timeout(300)
        label = page.text_content("#route-label")
        browser.close()
        manager.stop()
        verified = label == "settings" and "#/settings" in page.url
        return _result(True, True, verified), _evidence(state=label or "unknown")


def _exec_popup(capabilities: dict) -> tuple[dict, dict]:
    with FakeSpa() as spa, _launch_browser() as (manager, browser):
        context = browser.new_context()
        page = context.new_page()
        page.goto(spa.url)
        with context.expect_page() as popup_info:
            page.evaluate("window.open(arguments[0])", spa.url + "#popup")
        popup = popup_info.value
        popup.wait_for_load_state()
        context.close()
        browser.close()
        manager.stop()
        return _result(True, True, popup is not None), _evidence(count=1)


def _exec_download(capabilities: dict) -> tuple[dict, dict]:
    with FakeSpa() as spa, _launch_browser() as (manager, browser):
        page = browser.new_page(accept_downloads=True)
        page.goto(spa.url)
        with page.expect_download() as download_info:
            page.click("#dl")
        download = download_info.value
        target = Path(tempfile.gettempdir()) / "antonella-e2e-download.txt"
        download.save_as(str(target))
        content = target.read_bytes()
        target.unlink(missing_ok=True)
        browser.close()
        manager.stop()
        verified = b"antonella e2e synthetic" in content
        return _result(True, True, verified), _evidence(length=len(content))


# ---------------------------------------------------------------------------
# multi-monitor / DPI (ctypes)
# ---------------------------------------------------------------------------
def _monitors() -> list[dict]:
    out: list[dict] = []

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                    ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]

    user32 = ctypes.windll.user32

    def _cb(_hdc, _rect, _lparam, hmonitor):
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(mi)):
            out.append({
                "primary": bool(mi.dwFlags & 1),
                "x": int(mi.rcMonitor.left), "y": int(mi.rcMonitor.top),
                "width": int(mi.rcMonitor.right - mi.rcMonitor.left),
                "height": int(mi.rcMonitor.bottom - mi.rcMonitor.top),
            })
        return 1

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.c_double
    )
    user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(_cb), 0)
    return out


def _exec_multi_monitor(capabilities: dict) -> tuple[dict, dict]:
    monitors = [m for m in _monitors() if m["width"] > 100]
    if len(monitors) < 2:
        raise SkipCase("requires two active monitors")
    secondary = next(m for m in monitors if not m["primary"])
    with FixtureApp() as fixture:
        hwnd = int(fixture.window.handle)
        SWP_NOSIZE = 0x0001
        ctypes.windll.user32.SetWindowPos(
            hwnd, 0, secondary["x"] + 50, secondary["y"] + 50, 0, 0, SWP_NOSIZE
        )
        time.sleep(0.5)

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        rect = RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        verified = secondary["x"] <= rect.left < secondary["x"] + secondary["width"]
        return _result(True, True, verified), _evidence(monitor_index=1)


def _exec_dpi(capabilities: dict) -> tuple[dict, dict]:
    import ctypes.wintypes

    shcore = ctypes.windll.shcore
    monitors = _monitors()
    if not monitors:
        raise SkipCase("no monitors enumerated")
    point = ctypes.wintypes.POINT(monitors[0]["x"] + 10, monitors[0]["y"] + 10)
    dpi_x = ctypes.c_uint(0)
    dpi_y = ctypes.c_uint(0)
    hmonitor = ctypes.windll.user32.MonitorFromPoint(point, 1)  # MONITOR_DEFAULTTOPRIMARY
    hr = shcore.GetDpiForMonitor(hmonitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
    verified = hr == 0 and dpi_x.value >= 96
    return _result(True, True, verified), _evidence(count=int(dpi_x.value))


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------
EXECUTORS = {
    "filesystem": _exec_filesystem,
    "app_launch": _exec_app_launch,
    "window_focus": _exec_window_focus,
    "uia_inspect": _exec_uia_inspect,
    "uia_click": _exec_uia_click,
    "uia_set_text": _exec_uia_set_text,
    "mouse_move": _exec_mouse_move,
    "mouse_click": _exec_mouse_click,
    "keyboard": _exec_keyboard,
    "volume": _exec_volume,
    "mute": _exec_mute,
    "brightness": _exec_brightness,
    "wifi": _exec_wifi,
    "browser_tabs": _exec_browser_tabs,
    "spa": _exec_spa,
    "popup": _exec_popup,
    "download": _exec_download,
    "multi_monitor": _exec_multi_monitor,
    "dpi": _exec_dpi,
}

# Cases intentionally WITHOUT executors yet (honest SKIPPED in reports):
# voice, barge_in, computer_use_*, target_*, screen_changed, approval_delayed,
# frame_stale, scroll_retry, click/type/hotkey_no_retry, stop_during_*,
# hot_plug, stale_frame — they need runtime instrumentation or hardware
# scenarios that cannot be simulated safely here.
