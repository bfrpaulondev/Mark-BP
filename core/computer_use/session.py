from __future__ import annotations

import json
import threading
import time
from typing import Any

from config import get_config
from core.computer_use.contracts import SessionState
from core.display_selection import normalize_monitor_hint


class RealtimeComputerUseSession:
    def __init__(self):
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._approval_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state = SessionState()
        self._player = None

    def start(
        self,
        *,
        objective: str,
        target_window: str = "",
        monitor: int | str | None = None,
        cost_mode: str = "",
        max_steps: int | None = None,
        player=None,
    ) -> dict[str, Any]:
        objective = str(objective or "").strip()
        if not objective:
            return {"ok": False, "error": "Computer Use requires an objective."}

        with self._lock:
            if self._thread and self._thread.is_alive():
                return {
                    "ok": False,
                    "error": "A Realtime Computer Use session is already running.",
                    "status": self._state.as_dict(),
                }

            config = get_config()
            mode = (
                str(cost_mode or config.get("computer_use_cost_mode") or "economy")
                .strip()
                .lower()
            )
            requested_monitor = normalize_monitor_hint(monitor)
            self._player = player
            self._stop_event.clear()
            self._approval_event.clear()
            self._state = SessionState(
                state="starting",
                objective=objective,
                target_window=str(target_window or "").strip(),
                requested_monitor=requested_monitor,
                cost_mode=mode,
            )
            self._thread = threading.Thread(
                target=self._run,
                kwargs={
                    "config": config,
                    "max_steps_override": max_steps,
                },
                daemon=True,
                name="antonella-realtime-computer-use",
            )
            self._thread.start()

        return {
            "ok": True,
            "message": (
                "Realtime Computer Use started in the background. "
                "Antonella remains available for voice interruption."
            ),
            "status": self.status(),
        }

    def stop(self) -> dict[str, Any]:
        self._stop_event.set()
        self._approval_event.set()
        self._log("Computer Use · stop requested")
        with self._lock:
            if self._state.state not in {"idle", "done", "failed", "stopped"}:
                self._state.state = "stopping"
        return {"ok": True, "status": self.status()}

    def approve_once(self) -> dict[str, Any]:
        with self._lock:
            if not self._state.awaiting_approval:
                return {
                    "ok": False,
                    "error": "Computer Use is not waiting for approval.",
                    "status": self._state.as_dict(),
                }
            self._state.awaiting_approval = False
            self._state.state = "executing"
        self._approval_event.set()
        self._log("Computer Use · one high-risk step approved")
        return {"ok": True, "status": self.status()}

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self._state.as_dict()

    def _run(self, *, config: dict[str, Any], max_steps_override: int | None) -> None:
        capture = None
        try:
            from core.computer_use.actuator import execute_action
            from core.computer_use.capture import RealtimeDesktopCapture
            from core.computer_use.planner import ComputerUsePlanner
            from core.computer_use.safety import evaluate_action

            planner = ComputerUsePlanner(
                config,
                cost_mode=self._state.cost_mode,
            )
            budget = planner.route.budget
            max_steps = budget.max_steps
            if max_steps_override is not None:
                max_steps = max(1, min(max_steps, int(max_steps_override)))

            with self._lock:
                self._state.provider = planner.last_provider
                self._state.model = planner.last_model

            last_logged_provider = planner.last_provider
            last_logged_model = planner.last_model

            if self._state.target_window:
                from actions.computer_control import computer_control

                computer_control(
                    parameters={
                        "action": "focus_window",
                        "title": self._state.target_window,
                    },
                    player=self._player,
                )
                time.sleep(0.4)

            capture = RealtimeDesktopCapture(
                fps=budget.capture_fps,
                change_threshold=budget.change_threshold,
                monitor_hint=self._state.requested_monitor,
                window_title=self._state.target_window,
                max_width=budget.max_image_width,
                max_height=budget.max_image_height,
                jpeg_quality=budget.jpeg_quality,
            )
            capture.start()
            frame = capture.latest(timeout=4.0)

            with self._lock:
                self._state.state = "observing"
                self._state.monitor_index = frame.monitor_index
                self._state.visual_updates = frame.sequence
                self._state.capture_scope = frame.capture_scope
                self._state.capture_savings_pct = int(round(frame.pixel_savings * 100))

            requested = self._state.requested_monitor
            requested_text = "active" if requested is None else str(requested)
            scope_text = (
                f"window ROI, ~{int(round(frame.pixel_savings * 100))}% fewer source pixels"
                if frame.capture_scope == "window"
                else "full monitor"
            )
            self._log(
                "Computer Use · live capture started "
                f"(requested={requested_text}, resolved monitor {frame.monitor_index}, "
                f"scope={scope_text}, {budget.capture_fps} FPS local, "
                f"{planner.last_provider}/{planner.last_model})"
            )

            history: list[str] = []
            no_change_count = 0
            step = 1

            while step <= max_steps:
                if self._stop_event.is_set():
                    self._finish("stopped", result="Computer Use stopped by user.")
                    return

                with self._lock:
                    self._state.state = "planning"
                    self._state.step = step
                    self._state.monitor_index = frame.monitor_index
                    self._state.capture_scope = frame.capture_scope
                    self._state.capture_savings_pct = int(round(frame.pixel_savings * 100))

                actions = planner.next_actions(
                    objective=self._state.objective,
                    frame=frame,
                    history=history,
                    step=step,
                )

                with self._lock:
                    # Count actual provider requests, including fallback, instead
                    # of reporting only logical planning turns.
                    self._state.model_calls = planner.provider_attempts
                    self._state.provider = planner.last_provider
                    self._state.model = planner.last_model

                if (
                    planner.last_provider != last_logged_provider
                    or planner.last_model != last_logged_model
                ):
                    self._log(
                        "Computer Use · provider fallback/route change → "
                        f"{planner.last_provider}/{planner.last_model}"
                    )
                    last_logged_provider = planner.last_provider
                    last_logged_model = planner.last_model

                for batch_index, action in enumerate(actions):
                    if step > max_steps:
                        self._finish(
                            "failed",
                            error=f"Computer Use reached the configured step limit ({max_steps}).",
                        )
                        return

                    if self._stop_event.is_set():
                        self._finish("stopped", result="Computer Use stopped by user.")
                        return

                    with self._lock:
                        self._state.step = step
                        self._state.last_action = action.history_line()
                        if batch_index > 0:
                            self._state.batched_actions += 1
                            self._state.saved_model_calls += 1

                    if action.action == "done":
                        result = action.result or action.description or "Objective completed."
                        self._finish("done", result=result)
                        self._log(f"Computer Use · completed: {result}")
                        return

                    if action.action == "fail":
                        error = action.result or action.description or "Planner could not continue."
                        self._finish("failed", error=error)
                        self._log(f"Computer Use · stopped: {error}")
                        return

                    decision = evaluate_action(action)
                    if not decision.allowed:
                        if not decision.requires_approval:
                            self._finish("failed", error=decision.reason)
                            self._log(f"Computer Use · blocked: {decision.reason}")
                            return

                        with self._lock:
                            self._state.state = "awaiting_approval"
                            self._state.awaiting_approval = True
                        self._approval_event.clear()
                        self._log(
                            "Computer Use · approval required: "
                            f"{action.description or action.action}"
                        )

                        while not self._stop_event.is_set():
                            if self._approval_event.wait(timeout=0.2):
                                break

                        if self._stop_event.is_set():
                            self._finish("stopped", result="Computer Use stopped by user.")
                            return

                    with self._lock:
                        self._state.state = "executing"
                        self._state.awaiting_approval = False

                    previous_sequence = frame.sequence
                    result, expects_visual_change = execute_action(
                        action,
                        frame,
                        player=self._player,
                    )
                    history.append(f"{action.history_line()} -> {result[:160]}")
                    history = history[-12:]

                    with self._lock:
                        self._state.history = list(history)

                    batch_label = " · lote" if batch_index > 0 else ""
                    self._log(
                        f"Computer Use · step {step}/{max_steps}{batch_label}: "
                        f"{action.description or action.action}"
                    )
                    step += 1

                    if self._stop_event.is_set():
                        self._finish("stopped", result="Computer Use stopped by user.")
                        return

                    if expects_visual_change and not action.reobserve:
                        time.sleep(0.08)
                        try:
                            frame = capture.latest(timeout=0.35)
                        except Exception:
                            pass
                        with self._lock:
                            self._state.visual_updates = frame.sequence
                            self._state.monitor_index = frame.monitor_index
                            self._state.capture_scope = frame.capture_scope
                            self._state.capture_savings_pct = int(round(frame.pixel_savings * 100))
                        continue

                    if expects_visual_change:
                        new_frame = capture.wait_for_change(
                            after_sequence=previous_sequence,
                            timeout=2.5,
                        )
                        if new_frame.sequence == previous_sequence:
                            no_change_count += 1
                        else:
                            no_change_count = 0
                            time.sleep(0.08)
                            try:
                                new_frame = capture.latest(timeout=0.5)
                            except Exception:
                                pass
                        frame = new_frame
                    else:
                        time.sleep(min(1.0, action.seconds))
                        frame = capture.latest(timeout=1.0)

                    with self._lock:
                        self._state.state = "observing"
                        self._state.monitor_index = frame.monitor_index
                        self._state.visual_updates = frame.sequence
                        self._state.capture_scope = frame.capture_scope
                        self._state.capture_savings_pct = int(round(frame.pixel_savings * 100))

                    if no_change_count >= 3:
                        history.append(
                            "Three consecutive visual actions produced no meaningful screen change."
                        )
                        no_change_count = 0

                    break

            self._finish(
                "failed",
                error=f"Computer Use reached the configured step limit ({max_steps}).",
            )

        except Exception as exc:
            self._finish("failed", error=str(exc))
            self._log(f"Computer Use · error: {exc}")
        finally:
            if capture is not None:
                try:
                    capture.stop()
                except Exception:
                    pass

    def _finish(
        self,
        state: str,
        *,
        result: str = "",
        error: str = "",
    ) -> None:
        with self._lock:
            self._state.state = state
            self._state.awaiting_approval = False
            if result:
                self._state.result = result
            if error:
                self._state.last_error = error

    def _log(self, message: str) -> None:
        player = self._player
        if player is not None:
            try:
                player.write_log(f"SYS: {message}")
                return
            except Exception:
                pass
        print(f"[Antonella] {message}")


_SESSION = RealtimeComputerUseSession()


def get_realtime_computer_use_session() -> RealtimeComputerUseSession:
    return _SESSION


def format_status(status: dict[str, Any]) -> str:
    return json.dumps(status, ensure_ascii=False, sort_keys=True)
