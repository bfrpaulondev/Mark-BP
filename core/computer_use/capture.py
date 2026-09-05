from __future__ import annotations

import io
import threading
import time
from typing import Any

from core.computer_use.contracts import FrameSnapshot
from core.display_selection import normalize_monitor_hint, select_monitor, selected_monitor_index
from core.display_topology import (
    active_screen_point,
    describe_dpi_metadata,
    display_topology_state,
    per_monitor_dpi_context,
)
from core.window_geometry import region_savings_ratio, resolve_window_region


class RealtimeDesktopCapture:
    def __init__(
        self,
        *,
        fps: int = 10,
        change_threshold: float = 0.025,
        monitor_hint: int | str | None = None,
        window_title: str = "",
        max_width: int = 1280,
        max_height: int = 720,
        jpeg_quality: int = 76,
    ):
        self._fps = max(2, min(30, int(fps)))
        self._change_threshold = max(0.001, min(1.0, float(change_threshold)))
        self._monitor_hint = monitor_hint
        self._window_title = str(window_title or "").strip()
        self._max_width = max_width
        self._max_height = max_height
        self._jpeg_quality = max(45, min(92, jpeg_quality))

        self._stop_event = threading.Event()
        self._condition = threading.Condition()
        self._thread: threading.Thread | None = None
        self._latest: FrameSnapshot | None = None
        self._sequence = 0
        self._error = ""
        self._availability_error = ""

    @property
    def error(self) -> str:
        return self._error or self._availability_error

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._error = ""
        self._availability_error = ""
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

        raise RuntimeError(
            self._error
            or self._availability_error
            or "Desktop capture did not produce a frame."
        )

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

        raise RuntimeError(
            self._error
            or self._availability_error
            or "Desktop capture is unavailable."
        )

    def _invalidate_latest(self, reason: str = "") -> None:
        with self._condition:
            self._latest = None
            self._availability_error = str(reason or "")
            self._condition.notify_all()

    def _run(self) -> None:
        try:
            import mss
            import numpy as np
            from PIL import Image
        except ImportError:
            self._error = (
                "Realtime Computer Use requires mss, numpy and Pillow from the locked install."
            )
            with self._condition:
                self._condition.notify_all()
            return

        previous_gray = None
        previous_geometry = None
        interval = 1.0 / self._fps
        window_region = None
        window_monitor_index = 0
        window_region_checked_at = 0.0
        topology_checked_at = 0.0
        current_token = ""
        metadata: dict[int, dict[str, Any]] = {}
        pinned_device = ""
        normalized_hint = normalize_monitor_hint(self._monitor_hint)
        explicit_monitor = isinstance(normalized_hint, int)
        sct = None

        try:
            with per_monitor_dpi_context():
                sct = mss.mss()
                while not self._stop_event.is_set():
                    started = time.perf_counter()
                    now = time.monotonic()

                    if not current_token or (now - topology_checked_at) >= 0.5:
                        monitors = list(sct.monitors)
                        live_metadata, live_token = display_topology_state(monitors)
                        topology_checked_at = now

                        if current_token and live_token != current_token:
                            self._invalidate_latest(
                                "Display topology changed; waiting for a fresh physical frame."
                            )
                            try:
                                sct.close()
                            except Exception:
                                pass
                            sct = mss.mss()
                            monitors = list(sct.monitors)
                            live_metadata, live_token = display_topology_state(monitors)
                            previous_gray = None
                            previous_geometry = None
                            window_region = None
                            window_monitor_index = 0
                            window_region_checked_at = 0.0

                        metadata = live_metadata
                        current_token = live_token
                    else:
                        monitors = list(sct.monitors)

                    point = active_screen_point()
                    try:
                        if explicit_monitor and pinned_device:
                            pinned_index = next(
                                (
                                    index
                                    for index, item in metadata.items()
                                    if str(item.get("device") or "") == pinned_device
                                ),
                                0,
                            )
                            if not pinned_index or pinned_index >= len(monitors):
                                raise ValueError(
                                    "The explicitly targeted display is disconnected; waiting for it to return."
                                )
                            base_monitor = monitors[pinned_index]
                        else:
                            base_monitor = select_monitor(
                                monitors,
                                point=point,
                                hint=self._monitor_hint,
                                strict_hint=explicit_monitor,
                            )
                            base_index = selected_monitor_index(monitors, base_monitor)
                            if explicit_monitor and base_index > 0:
                                pinned_device = str(
                                    metadata.get(base_index, {}).get("device") or ""
                                )
                    except ValueError as exc:
                        self._invalidate_latest(str(exc))
                        self._stop_event.wait(min(0.25, interval))
                        continue

                    self._availability_error = ""
                    base_monitor_index = selected_monitor_index(monitors, base_monitor)
                    target = base_monitor
                    monitor_index = base_monitor_index
                    capture_scope = "monitor"
                    pixel_savings = 0.0

                    if self._window_title:
                        if window_region is None or (now - window_region_checked_at) >= 0.75:
                            resolved = resolve_window_region(self._window_title, monitors)
                            window_region_checked_at = now
                            if resolved is None:
                                window_region = None
                                window_monitor_index = 0
                            else:
                                window_region, window_monitor_index = resolved

                        if window_region is not None:
                            target = window_region
                            monitor_index = window_monitor_index
                            capture_scope = "window"
                            reference_monitor = (
                                monitors[monitor_index]
                                if 0 < monitor_index < len(monitors)
                                else base_monitor
                            )
                            pixel_savings = region_savings_ratio(target, reference_monitor)

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
                        capture_scope,
                        current_token,
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
                        dpi = describe_dpi_metadata(monitor_index, metadata)
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
                            capture_scope=capture_scope,
                            pixel_savings=pixel_savings,
                            topology_token=current_token,
                            dpi_x=int(dpi.get("dpi_x") or 96),
                            dpi_y=int(dpi.get("dpi_y") or 96),
                            scale_x=float(dpi.get("scale_x") or 1.0),
                            scale_y=float(dpi.get("scale_y") or 1.0),
                            monitor_device=str(dpi.get("device") or ""),
                            monitor_primary=bool(dpi.get("primary", False)),
                        )
                        with self._condition:
                            self._latest = snapshot
                            self._availability_error = ""
                            self._condition.notify_all()

                    previous_gray = gray
                    previous_geometry = geometry

                    elapsed = time.perf_counter() - started
                    self._stop_event.wait(max(0.0, interval - elapsed))

        except Exception as exc:
            self._error = f"Desktop capture failed: {exc}"
            with self._condition:
                self._latest = None
                self._condition.notify_all()
        finally:
            if sct is not None:
                try:
                    sct.close()
                except Exception:
                    pass


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
