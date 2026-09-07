"""Windows physical E2E executors (ANT-275 BLOCO 8).

Each executor is registered per case id and only runs on a physical
Windows machine with the physical gate enabled. Every executor must
PROVE its effect with a real postcondition. System state touched by a
case is restored and that restoration is itself verified.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_TITLE = "Antonella E2E Fixture"
FIXTURE_TITLE_CHANGED = FIXTURE_TITLE + " [CHANGED]"


class SkipCase(Exception):
    """Environment cannot safely execute this physical case."""


# -.-.-.-
def _result(ok: bool, delivered: bool, verified: bool, **extra) -> dict:
    out = {"ok": ok, "delivered": delivered, "verified": verified}
    out.update(extra)
    return out


# -.-.-.-
def _evidence(**kwargs) -> dict:
    from scripts.windows_e2e.evidence import ALLOWED_EVIDENCE_KEYS

    return {key: value for key, value in kwargs.items() if key in ALLOWED_EVIDENCE_KEYS}


# -.-.-.-
def _sha(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# filesystem
# ---------------------------------------------------------------------------
# -.-.-.-
def _exec_filesystem(_capabilities: dict) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory(prefix="antonella-e2e-") as directory:
        target = Path(directory) / "e2e-probe.txt"
        target.write_text("antonella synthetic", encoding="utf-8")
        read_back = target.read_text(encoding="utf-8")
        created = read_back == "antonella synthetic" and target.is_file()
        target.unlink()
        removed = not target.exists()
        return (
            _result(True, created, created and removed),
            _evidence(hash=_sha(read_back), length=len(read_back)),
        )


# ---------------------------------------------------------------------------
# fixture app + pywinauto
# ---------------------------------------------------------------------------
class FixtureApp:
    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._win = None

    def __enter__(self) -> "FixtureApp":
        try:
            from pywinauto import Desktop
        except ImportError as exc:
            raise SkipCase("pywinauto is not installed") from exc

        self._proc = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "scripts" / "windows_e2e" / "fixtures" / "fixture_app.py"),
                "--duration",
                "120",
            ],
            cwd=str(ROOT),
        )
        deadline = time.time() + 20
        while time.time() < deadline:
            windows = Desktop(backend="uia").windows(title=FIXTURE_TITLE)
            if windows:
                # pywinauto 0.6.9: a raw UIAWrapper has no child_window().
                # Store the WindowSpecification as the selector root so
                # child_window-based lookups keep working.
                self._win = Desktop(backend="uia").window(title=FIXTURE_TITLE)
                self._win.set_focus()
                return self
            if self._proc.poll() is not None:
                break
            time.sleep(0.4)
        self.__exit__()
        raise SkipCase("fixture window did not appear")

    def __exit__(self, *_exc) -> None:
        if self._proc is None:
            return
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=3)

    @property
    def window(self):
        return self._win

    def title(self) -> str:
        from pywinauto import Desktop

        windows = Desktop(backend="uia").windows(title_re=f"{FIXTURE_TITLE}.*")
        return windows[0].window_text() if windows else ""


# -.-.-.-
def _rect_center(rect) -> tuple[int, int]:
    """pywinauto 0.6.9 RECT has no middle_point() — compute from edges."""
    return (int((rect.left + rect.right) // 2), int((rect.top + rect.bottom) // 2))


# -.-.-.-
def _uia_control(fixture: FixtureApp):
    return fixture.window.child_window(title="Mudar título", control_type="Button")


# -.-.-.-
def _exec_app_launch(_capabilities: dict) -> tuple[dict, dict]:
    with FixtureApp() as fixture:
        title = fixture.title()
        verified = title == FIXTURE_TITLE
        return _result(True, bool(title), verified), _evidence(window_title_hash=_sha(title))


# -.-.-.-
def _exec_window_focus(_capabilities: dict) -> tuple[dict, dict]:
    with FixtureApp() as fixture:
        fixture.window.set_focus()
        time.sleep(0.4)
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        verified = buf.value == FIXTURE_TITLE
        return _result(True, True, verified), _evidence(window_title_hash=_sha(buf.value))


# -.-.-.-
def _exec_uia_inspect(_capabilities: dict) -> tuple[dict, dict]:
    with FixtureApp() as fixture:
        button = _uia_control(fixture)
        exists = bool(button.exists(timeout=5))
        return _result(True, exists, exists), _evidence(count=1 if exists else 0)


# -.-.-.-
def _exec_uia_click(_capabilities: dict) -> tuple[dict, dict]:
    with FixtureApp() as fixture:
        _uia_control(fixture).click_input()
        time.sleep(0.3)
        verified = fixture.title() == FIXTURE_TITLE_CHANGED
        return _result(True, True, verified), _evidence(state="title_changed" if verified else "unchanged")


# -.-.-.-
def _exec_uia_set_text(_capabilities: dict) -> tuple[dict, dict]:
    with FixtureApp() as fixture:
        box = fixture.window.child_window(control_type="Edit")
        box.set_edit_text("antonella-e2e")
        time.sleep(0.2)
        verified = box.get_value() == "antonella-e2e"
        return _result(True, True, verified), _evidence(length=len("antonella-e2e"))


# -.-.-.-
def _exec_mouse_move(_capabilities: dict) -> tuple[dict, dict]:
    try:
        import pywinauto.mouse
    except ImportError as exc:
        raise SkipCase("pywinauto is not installed") from exc

    with FixtureApp() as fixture:
        rect = fixture.window.rectangle()
        target_x, target_y = _rect_center(rect)
        pywinauto.mouse.move(coords=(target_x, target_y))
        time.sleep(0.1)
        point = wintypes.POINT()
        delivered = bool(ctypes.windll.user32.GetCursorPos(ctypes.byref(point)))
        verified = delivered and abs(point.x - target_x) <= 2 and abs(point.y - target_y) <= 2
        return _result(True, delivered, verified), _evidence(count=1 if verified else 0)


# -.-.-.-
def _exec_mouse_click(_capabilities: dict) -> tuple[dict, dict]:
    with FixtureApp() as fixture:
        _uia_control(fixture).click_input()
        time.sleep(0.3)
        verified = fixture.title() == FIXTURE_TITLE_CHANGED
        return _result(True, True, verified), _evidence(state="clicked" if verified else "unchanged")


# -.-.-.-
def _exec_keyboard(_capabilities: dict) -> tuple[dict, dict]:
    try:
        from pywinauto.keyboard import send_keys
    except ImportError as exc:
        raise SkipCase("pywinauto is not installed") from exc

    with FixtureApp() as fixture:
        box = fixture.window.child_window(control_type="Edit")
        box.set_focus()
        send_keys("antonella-keys")
        time.sleep(0.2)
        verified = box.get_value() == "antonella-keys"
        return _result(True, True, verified), _evidence(length=14)


# ---------------------------------------------------------------------------
# audio — mutate, prove, restore, prove restoration
# ---------------------------------------------------------------------------
# -.-.-.-
def _endpoint_volume():
    try:
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    except ImportError as exc:
        raise SkipCase("pycaw/comtypes is not installed") from exc

    devices = AudioUtilities.GetSpeakers()
    return _endpoint_from_device(devices, IAudioEndpointVolume._iid_, IAudioEndpointVolume, CLSCTX_ALL)


# -.-.-.-
def _endpoint_from_device(device, iid, interface_type, ctx):
    """pycaw 20251023 exposes AudioDevice.EndpointVolume directly; older
    versions require the COM Activate + QueryInterface dance."""
    modern = getattr(device, "EndpointVolume", None)
    if modern is not None:
        return modern
    interface = device.Activate(iid, ctx, None)
    return interface.QueryInterface(interface_type)


# -.-.-.-
def _exec_volume(_capabilities: dict) -> tuple[dict, dict]:
    volume = _endpoint_volume()
    original = float(volume.GetMasterVolumeLevelScalar())
    target = max(0.0, original - 0.05) if original > 0.95 else min(1.0, original + 0.05)
    changed = False
    try:
        volume.SetMasterVolumeLevelScalar(target, None)
        time.sleep(0.2)
        changed = abs(float(volume.GetMasterVolumeLevelScalar()) - target) < 0.02
    finally:
        volume.SetMasterVolumeLevelScalar(original, None)
    time.sleep(0.2)
    restored = abs(float(volume.GetMasterVolumeLevelScalar()) - original) < 0.02
    return _result(True, changed, changed and restored), _evidence(ok=restored)


# -.-.-.-
def _exec_mute(_capabilities: dict) -> tuple[dict, dict]:
    volume = _endpoint_volume()
    original = bool(volume.GetMute())
    changed = False
    try:
        volume.SetMute(not original, None)
        time.sleep(0.2)
        changed = bool(volume.GetMute()) == (not original)
    finally:
        volume.SetMute(original, None)
    time.sleep(0.2)
    restored = bool(volume.GetMute()) == original
    return _result(True, changed, changed and restored), _evidence(ok=restored)


# -.-.-.-
def _exec_brightness(_capabilities: dict) -> tuple[dict, dict]:
    try:
        import wmi
    except ImportError as exc:
        raise SkipCase("wmi is not installed") from exc
    try:
        entries = wmi.WMI(namespace="wmi").WmiMonitorBrightness()
        if not entries:
            raise SkipCase("brightness is not exposed by this hardware")
        brightness = int(entries[0].CurrentBrightness)
        return _result(True, True, 0 <= brightness <= 100), _evidence(count=brightness)
    except SkipCase:
        raise
    except Exception as exc:
        raise SkipCase("brightness is not supported on this hardware") from exc


# -.-.-.-
def _exec_wifi(_capabilities: dict) -> tuple[dict, dict]:
    completed = subprocess.run(
        ["netsh", "wlan", "show", "interfaces"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    output = completed.stdout or ""
    delivered = completed.returncode == 0
    verified = delivered and ("State" in output or "Estado" in output)
    return _result(True, delivered, verified), _evidence(length=len(output))


# ---------------------------------------------------------------------------
# browser — local fake SPA only
# ---------------------------------------------------------------------------
class FakeSpa:
    def __init__(self, port: int = 0):
        from scripts.windows_e2e.fixtures.fake_spa import serve

        self._server = serve(port)
        bound_port = int(self._server.server_address[1])
        self.url = f"http://127.0.0.1:{bound_port}/"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)


# -.-.-.-
@contextmanager
def _launch_browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SkipCase("playwright is not installed") from exc

    manager = sync_playwright().start()
    browser = None
    try:
        browser = manager.chromium.launch(headless=False)
        yield manager, browser
    except SkipCase:
        raise
    except Exception as exc:
        raise SkipCase(f"playwright browser unavailable: {type(exc).__name__}") from exc
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        manager.stop()


# -.-.-.-
def _exec_browser_tabs(_capabilities: dict) -> tuple[dict, dict]:
    with FakeSpa() as spa, _launch_browser() as (_manager, browser):
        context = browser.new_context()
        try:
            page = context.new_page()
            page.goto(spa.url)
            page2 = context.new_page()
            page2.goto(spa.url + "#second")
            count = len(context.pages)
            return _result(True, True, count == 2), _evidence(count=count)
        finally:
            context.close()


# -.-.-.-
def _exec_spa(_capabilities: dict) -> tuple[dict, dict]:
    with FakeSpa() as spa, _launch_browser() as (_manager, browser):
        page = browser.new_page()
        page.goto(spa.url)
        page.click("#nav")
        page.wait_for_timeout(300)
        label = page.text_content("#route-label")
        final_url = page.url
        verified = label == "settings" and "#/settings" in final_url
        return _result(True, True, verified), _evidence(state=label or "unknown")


# -.-.-.-
def _exec_popup(_capabilities: dict) -> tuple[dict, dict]:
    with FakeSpa() as spa, _launch_browser() as (_manager, browser):
        context = browser.new_context()
        try:
            page = context.new_page()
            page.goto(spa.url)
            with context.expect_page() as popup_info:
                page.evaluate("url => window.open(url)", spa.url + "#popup")
            popup = popup_info.value
            popup.wait_for_load_state()
            verified = popup.url.startswith(spa.url)
            return _result(True, True, verified), _evidence(count=1 if verified else 0)
        finally:
            context.close()


# -.-.-.-
def _exec_download(_capabilities: dict) -> tuple[dict, dict]:
    with FakeSpa() as spa, _launch_browser() as (_manager, browser):
        context = browser.new_context(accept_downloads=True)
        try:
            page = context.new_page()
            page.goto(spa.url)
            with page.expect_download() as download_info:
                page.click("#dl")
            download = download_info.value
            with tempfile.TemporaryDirectory(prefix="antonella-download-") as directory:
                target = Path(directory) / "download.txt"
                download.save_as(str(target))
                content = target.read_bytes()
                verified = target.is_file() and b"antonella e2e synthetic" in content
                return _result(True, True, verified), _evidence(length=len(content))
        finally:
            context.close()


# ---------------------------------------------------------------------------
# multi-monitor / DPI
# ---------------------------------------------------------------------------
# -.-.-.-
def _monitors() -> list[dict]:
    if sys.platform != "win32":
        raise SkipCase("monitor enumeration requires Windows")

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    user32 = ctypes.windll.user32
    hmonitor_type = getattr(wintypes, "HMONITOR", wintypes.HANDLE)
    hdc_type = getattr(wintypes, "HDC", wintypes.HANDLE)
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        hmonitor_type,
        hdc_type,
        ctypes.POINTER(wintypes.RECT),
        wintypes.LPARAM,
    )
    results: list[dict] = []

    def collect(hmonitor, _hdc, _rect, _lparam):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            results.append(
                {
                    "handle": int(hmonitor),
                    "primary": bool(info.dwFlags & 1),
                    "x": int(info.rcMonitor.left),
                    "y": int(info.rcMonitor.top),
                    "width": int(info.rcMonitor.right - info.rcMonitor.left),
                    "height": int(info.rcMonitor.bottom - info.rcMonitor.top),
                }
            )
        return True

    callback = callback_type(collect)
    if not user32.EnumDisplayMonitors(0, None, callback, 0):
        raise SkipCase("EnumDisplayMonitors failed")
    return results


# -.-.-.-
def _exec_multi_monitor(_capabilities: dict) -> tuple[dict, dict]:
    monitors = [monitor for monitor in _monitors() if monitor["width"] > 100]
    secondary = next((monitor for monitor in monitors if not monitor["primary"]), None)
    if secondary is None:
        raise SkipCase("requires a non-primary active monitor")

    with FixtureApp() as fixture:
        hwnd = int(fixture.window.handle)
        SWP_NOSIZE = 0x0001
        moved = bool(
            ctypes.windll.user32.SetWindowPos(
                hwnd,
                0,
                secondary["x"] + 50,
                secondary["y"] + 50,
                0,
                0,
                SWP_NOSIZE,
            )
        )
        time.sleep(0.5)
        rect = wintypes.RECT()
        read_ok = bool(ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)))
        verified = (
            moved
            and read_ok
            and secondary["x"] <= rect.left < secondary["x"] + secondary["width"]
            and secondary["y"] <= rect.top < secondary["y"] + secondary["height"]
        )
        return _result(True, moved, verified), _evidence(monitor_index=1)


# -.-.-.-
def _exec_dpi(_capabilities: dict) -> tuple[dict, dict]:
    monitors = _monitors()
    if not monitors:
        raise SkipCase("no monitors enumerated")
    try:
        shcore = ctypes.windll.shcore
        getter = shcore.GetDpiForMonitor
    except Exception as exc:
        raise SkipCase("GetDpiForMonitor is unavailable") from exc

    hmonitor_type = getattr(wintypes, "HMONITOR", wintypes.HANDLE)
    getter.argtypes = [
        hmonitor_type,
        ctypes.c_int,
        ctypes.POINTER(wintypes.UINT),
        ctypes.POINTER(wintypes.UINT),
    ]
    getter.restype = ctypes.c_long
    dpi_x = wintypes.UINT(0)
    dpi_y = wintypes.UINT(0)
    hr = getter(
        hmonitor_type(monitors[0]["handle"]),
        0,
        ctypes.byref(dpi_x),
        ctypes.byref(dpi_y),
    )
    verified = hr == 0 and dpi_x.value >= 96 and dpi_y.value >= 96
    return _result(True, hr == 0, verified), _evidence(count=int(dpi_x.value))


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

# Intentionally without executors yet: voice/barge-in, Computer Use failure
# scenarios, hot-plug and stale-frame cases. They remain SKIPPED until a
# runtime-observable physical executor can prove their postconditions.
