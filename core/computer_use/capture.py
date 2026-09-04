from __future__ import annotations

import io
import platform
import threading
import time
from typing import Any

from core.computer_use.contracts import FrameSnapshot
from core.display_selection import select_monitor


class RealtimeDesktopCapture:
    def __init__(
        self,
        *,
        fps: int = 10,
        change_threshold: float = 0.025,
        monitor_hint: int | str | None = None,
        max_width: int = 1280,
        max_height: int = 720,
        jpeg_quality: int = 76,
    ):
        self._fps = max(2, min(30, int(fps)))
        self._change_threshold = max(0.001, min(1.0, float(change_threshold)))
        self._monitor_hint = monitor_hint
        self._max_width = max_width
        self._max_height = max_height
        self._jpeg_quality = max(45, min(92, jpeg_quality))

        self._stop_event = threading.Event()
        self._condition = threading.Condition()
        self._thread: threading.Thread | None = None
        self._latest: FrameSnapshot | None = None
        self._sequence = 0
        self._error = ""

    @property
    def error(self) -> str:
        return self._error

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="antonella-desktop-capture",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def latest(self, timeout: float = 3.0) -> FrameSnapshot:
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._latest is None and not self._error:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(timeout=remaining)

            if self._latest is not None:
                return self._latest

        raise RuntimeError(self._error or "Desktop capture did not produce a frame.")

    def wait_for_change(
        self,
        *,
        after_sequence: int,
        timeout: float = 2.5,
    ) -> FrameSnapshot:
        deadline = time.monotonic() + timeout
        with self._condition:
            while not self._error:
                if self._latest is not None and self._latest.sequence > after_sequence:
                    return self._latest
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(timeout=remaining)

            if self._latest is not None:
                return self._latest

        raise RuntimeError(self._error or "Desktop capture is unavailable.")

    def _run(self) -> None:
        try:
            import mss
            import numpy as np
            from PIL import Image
        except ImportError as exc:
            self._error = (
                "Realtime Computer Use requires mss, numpy and Pillow from the locked install."
            )
            with self._condition:
                self._condition.notify_all()
            return

        previous_gray = None
        previous_geometry = None
        interval = 1.0 / self._fps

        try:
            with mss.mss() as sct:
                while not self._stop_event.is_set():
                    started = time.perf_counter()
                    monitors = sct.monitors
                    point = _active_screen_point()
                    target = select_monitor(
                        monitors,
                        point=point,
                        hint=self._monitor_hint,
                    )
                    monitor_index = next(
                        (
                            index
                            for index, monitor in enumerate(monitors)
                            if monitor == target
                        ),
                        0,
                    )
                    shot = sct.grab(target)
                    rgb = np.frombuffer(shot.rgb, dtype=np.uint8).reshape(
                        shot.height,
                        shot.width,
                        3,
                    )

                    gray = _thumbnail_gray(rgb, np)
                    geometry = (
                        int(target["left"]),
                        int(target["top"]),
                        int(target["width"]),
                        int(target["height"]),
                        monitor_index,
                    )
                    changed_geometry = previous_geometry != geometry
                    change_score = _change_score(previous_gray, gray, np)

                    if (
                        self._latest is None
                        or changed_geometry
                        or change_score >= self._change_threshold
                    ):
                        jpeg, image_width, image_height = _encode_jpeg(
                            rgb,
                            Image,
                            max_width=self._max_width,
                            max_height=self._max_height,
                            quality=self._jpeg_quality,
                        )
                        self._sequence += 1
                        snapshot = FrameSnapshot(
                            sequence=self._sequence,
                            timestamp=time.time(),
                            left=int(target["left"]),
                            top=int(target["top"]),
                            monitor_width=int(target["width"]),
                            monitor_height=int(target["height"]),
                            image_width=image_width,
                            image_height=image_height,
                            monitor_index=monitor_index,
                            change_score=change_score,
                            jpeg_bytes=jpeg,
                        )
                        with self._condition:
                            self._latest = snapshot
                            self._condition.notify_all()

                    previous_gray = gray
                    previous_geometry = geometry

                    elapsed = time.perf_counter() - started
                    self._stop_event.wait(max(0.0, interval - elapsed))

        except Exception as exc:
            self._error = f"Desktop capture failed: {exc}"
            with self._condition:
                self._condition.notify_all()


def _active_screen_point() -> tuple[int, int] | None:
    if platform.system() != "Windows":
        return None

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        rect = wintypes.RECT()
        if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width > 0 and height > 0:
                return rect.left + width // 2, rect.top + height // 2

        cursor = wintypes.POINT()
        if user32.GetCursorPos(ctypes.byref(cursor)):
            return int(cursor.x), int(cursor.y)
    except Exception:
        return None

    return None


def _thumbnail_gray(rgb: Any, np: Any) -> Any:
    height, width, _ = rgb.shape
    step_y = max(1, height // 90)
    step_x = max(1, width // 160)
    thumb = rgb[::step_y, ::step_x]
    return thumb.astype(np.float32).mean(axis=2)


def _change_score(previous: Any, current: Any, np: Any) -> float:
    if previous is None or previous.shape != current.shape:
        return 1.0
    delta = np.abs(current - previous).mean()
    return float(delta / 255.0)


def _encode_jpeg(
    rgb: Any,
    image_module: Any,
    *,
    max_width: int,
    max_height: int,
    quality: int,
) -> tuple[bytes, int, int]:
    image = image_module.fromarray(rgb, "RGB")
    image.thumbnail((max_width, max_height), image_module.Resampling.BILINEAR)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=False)
    return buffer.getvalue(), int(image.width), int(image.height)
