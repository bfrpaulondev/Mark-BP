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
        self._resume_event = threading.Event()
        self._resume_event.set()
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
            self._resume_event.set()
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
        self._resume_event.set()
        self._log("Computer Use · stop requested")
        with self._lock:
            if self._state.state not in {"idle", "done", "failed", "stopped"}:
                self._state.state = "stopping"
                self._state.paused = False
        return {"ok": True, "status": self.status()}

    def pause(self) -> dict[str, Any]:
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                return {
                    "ok": False,
                    "error": "No active Computer Use session can be paused.",
                    "status": self._state.as_dict(),
                }
            if self._state.state in {"done", "failed", "stopped", "stopping"}:
                return {
                    "ok": False,
                    "error": "Computer Use is already finishing or finished.",
                    "status": self._state.as_dict(),
                }
            if self._state.paused:
                return {"ok": True, "status": self._state.as_dict()}
            self._state.paused = True
            self._state.state = "paused"
            self._resume_event.clear()
        self._log("Computer Use · paused by user")
        return {"ok": True, "status": self.status()}

    def resume(self) -> dict[str, Any]:
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                return {
                    "ok": False,
                    "error": "No active Computer Use session can be resumed.",
                    "status": self._state.as_dict(),
                }
            if not self._state.paused:
                return {"ok": True, "status": self._state.as_dict()}
            self._state.paused = False
            self._state.state = (
                "awaiting_approval" if self._state.awaiting_approval else "observing"
            )
            self._resume_event.set()
        self._log("Computer Use · resumed by user")
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
            if not self._state.paused:
                self._state.state = "executing"
        self._approval_event.set()
        self._log("Computer Use · one high-risk step approved")
        return {"ok": True, "status": self.status()}

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self._state.as_dict()

    def _run(self, *, config: dict[str, Any], max_steps_override: int | None) -> None:
        capture = None
        planner = None
        try:
            from core.computer_use.actuator import execute_action
            from core.computer_use.capture import RealtimeDesktopCapture
            from core.computer_use.planner import ComputerUsePlanner
            from core.computer_use.recovery import (
                RecoveryPolicy,
                RecoveryState,
                action_plan_is_stale,
                target_scope_is_valid,
            )
            from core.computer_use.safety import evaluate_action

            planner = ComputerUsePlanner(
                config,
                cost_mode=self._state.cost_mode,
                target_window=self._state.target_window,
            )
            budget = planner.route.budget
            max_steps = budget.max_steps
            if max_steps_override is not None:
                max_steps = max(1, min(max_steps, int(max_steps_override)))

            recovery_policy = RecoveryPolicy.for_step_budget(max_steps)
            recovery = RecoveryState()

            with self._lock:
                self._state.provider = planner.last_provider
                self._state.model = planner.last_model
                self._state.telemetry_task_id = planner.telemetry_task_id

            last_logged_provider = planner.last_provider
            last_logged_model = planner.last_model

            if self._state.target_window:
                self._focus_target_window()
                time.sleep(0.35)

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

            if self._state.target_window and not target_scope_is_valid(
                frame, self._state.target_window
            ):
                recovered = self._recover_target_window(
                    capture,
                    recovery,
                    recovery_policy,
                    reason="target window was not available at session start",
                )
                if recovered is None:
                    self._finish(
                        "failed",
                        error="The requested target window could not be acquired safely.",
                    )
                    return
                frame = recovered

            self._set_frame_state(frame, state="observing")
            self._apply_recovery_state(recovery)
            self._apply_perception_stats(capture)

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
            step = 1

            while step <= max_steps:
                if not self._wait_until_resumed():
                    self._finish("stopped", result="Computer Use stopped by user.")
                    return

                if self._state.target_window and not target_scope_is_valid(
                    frame, self._state.target_window
                ):
                    if not recovery.can_recover(recovery_policy):
                        self._finish(
                            "failed",
                            error="Computer Use exhausted its bounded target-window recovery budget.",
                        )
                        return
                    recovered = self._recover_target_window(
                        capture,
                        recovery,
                        recovery_policy,
                        reason="target window capture scope was lost",
                    )
                    self._apply_recovery_state(recovery)
                    if recovered is None:
                        if not recovery.can_recover(recovery_policy):
                            self._finish(
                                "failed",
                                error="The requested target window could not be reacquired safely.",
                            )
                            return
                        time.sleep(0.15)
                        try:
                            frame = capture.latest(timeout=0.5)
                        except Exception:
                            pass
                        continue
                    frame = recovered
                    history.append("Target window reacquired; visual plan will be recomputed.")
                    history = history[-12:]

                with self._lock:
                    self._state.state = "planning"
                    self._state.step = step
                    self._state.monitor_index = frame.monitor_index
                    self._state.capture_scope = frame.capture_scope
                    self._state.capture_savings_pct = int(round(frame.pixel_savings * 100))
                    self._state.target_locked = bool(
                        self._state.target_window and frame.capture_scope == "window"
                    )

                actions = planner.next_actions(
                    objective=self._state.objective,
                    frame=frame,
                    history=history,
                    step=step,
                )

                with self._lock:
                    self._state.model_calls = planner.provider_attempts
                    self._state.saved_model_calls = planner.saved_model_calls
                    self._state.local_perception_routes = planner.local_perception_routes
                    self._state.perception_cache_hits = planner.perception_cache_hits
                    self._state.provider = planner.last_provider
                    self._state.model = planner.last_model
                self._apply_cost_snapshot(planner.telemetry_snapshot())

                if planner.last_plan_source in {"uia", "uia_cache"}:
                    source = "cached UIA" if planner.last_plan_source == "uia_cache" else "UIA"
                    self._log(
                        f"Computer Use · local perception route ({source}) saved a VLM call"
                    )

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

                replan_requested = False

                for batch_index, action in enumerate(actions):
                    if step > max_steps:
                        self._finish(
                            "failed",
                            error=f"Computer Use reached the configured step limit ({max_steps}).",
                        )
                        return

                    if not self._wait_until_resumed():
                        self._finish("stopped", result="Computer Use stopped by user.")
                        return

                    try:
                        live_frame = capture.latest(timeout=0.08)
                    except Exception:
                        live_frame = frame

                    if action_plan_is_stale(action, frame, live_frame):
                        if not recovery.can_recover(recovery_policy):
                            self._finish(
                                "failed",
                                error="Computer Use exhausted its stale-plan recovery budget.",
                            )
                            return
                        recovery.note_recovery(
                            "desktop changed after planning; stale action discarded",
                            kind="stale",
                        )
                        self._apply_recovery_state(recovery)
                        history.append(
                            "Desktop changed after planning; discarded stale visual action and replanned."
                        )
                        history = history[-12:]
                        frame = live_frame
                        self._set_frame_state(frame, state="recovering")
                        self._log("Computer Use · stale visual plan discarded; replanning")
                        replan_requested = True
                        break

                    if self._state.target_window and not target_scope_is_valid(
                        live_frame, self._state.target_window
                    ):
                        frame = live_frame
                        replan_requested = True
                        break

                    with self._lock:
                        self._state.step = step
                        self._state.last_action = action.history_line()
                        if batch_index > 0:
                            self._state.batched_actions += 1
                    if batch_index > 0:
                        planner.record_saved_model_call()
                        with self._lock:
                            self._state.saved_model_calls = planner.saved_model_calls
                        self._apply_cost_snapshot(planner.telemetry_snapshot())

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
                        if not self._wait_until_resumed():
                            self._finish("stopped", result="Computer Use stopped by user.")
                            return

                        try:
                            approved_frame = capture.latest(timeout=0.08)
                        except Exception:
                            approved_frame = frame

                        if self._state.target_window and not target_scope_is_valid(
                            approved_frame, self._state.target_window
                        ):
                            frame = approved_frame
                            self._set_frame_state(frame, state="recovering")
                            history.append(
                                "Target window changed while approval was pending; approved action was discarded."
                            )
                            history = history[-12:]
                            self._log(
                                "Computer Use · target changed after approval; action discarded"
                            )
                            replan_requested = True
                            break

                        if action_plan_is_stale(action, frame, approved_frame):
                            if not recovery.can_recover(recovery_policy):
                                self._finish(
                                    "failed",
                                    error="Computer Use exhausted its post-approval stale-plan recovery budget.",
                                )
                                return
                            recovery.note_recovery(
                                "desktop changed while approval was pending; approved action discarded",
                                kind="stale",
                            )
                            self._apply_recovery_state(recovery)
                            frame = approved_frame
                            self._set_frame_state(frame, state="recovering")
                            history.append(
                                "Desktop changed while approval was pending; approved action was discarded and must be planned again."
                            )
                            history = history[-12:]
                            self._log(
                                "Computer Use · approved visual plan became stale; action discarded"
                            )
                            replan_requested = True
                            break

                    if replan_requested:
                        break

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
                        self._set_frame_state(frame, state="observing")
                        self._apply_perception_stats(capture)
                        continue

                    if expects_visual_change:
                        settle_timeout = recovery_policy.settle_timeout(
                            action,
                            recovery.no_change_streak,
                        )
                        new_frame = capture.wait_for_change(
                            after_sequence=previous_sequence,
                            timeout=settle_timeout,
                        )
                        changed = new_frame.sequence > previous_sequence
                        recovery.note_visual_change(changed)

                        if not changed and recovery.can_retry_action(
                            action, recovery_policy
                        ):
                            if recovery.can_recover(recovery_policy):
                                recovery.note_recovery(
                                    "scroll produced no observable change; one safe retry",
                                )
                                recovery.note_action_retry(action)
                                self._apply_recovery_state(recovery)
                                self._set_frame_state(new_frame, state="recovering")
                                self._log(
                                    "Computer Use · scroll had no observable effect; retrying once"
                                )
                                retry_sequence = new_frame.sequence
                                retry_result, _ = execute_action(
                                    action,
                                    new_frame,
                                    player=self._player,
                                )
                                history.append(
                                    f"bounded scroll retry -> {retry_result[:140]}"
                                )
                                history = history[-12:]
                                retried_frame = capture.wait_for_change(
                                    after_sequence=retry_sequence,
                                    timeout=recovery_policy.settle_timeout(
                                        action,
                                        recovery.no_change_streak,
                                    ),
                                )
                                retry_changed = retried_frame.sequence > retry_sequence
                                recovery.note_visual_change(retry_changed)
                                new_frame = retried_frame
                                changed = retry_changed

                        if changed:
                            time.sleep(0.08)
                            try:
                                new_frame = capture.latest(timeout=0.45)
                            except Exception:
                                pass
                        else:
                            if not recovery.can_recover(recovery_policy):
                                self._apply_recovery_state(recovery)
                                self._finish(
                                    "failed",
                                    error="Computer Use exhausted its bounded visual recovery budget.",
                                )
                                return
                            recovery.note_recovery(
                                "visual action produced no observable screen change",
                            )
                            history.append(
                                "Visual action produced no observable change; planner must re-evaluate instead of assuming success."
                            )
                            history = history[-12:]
                            self._log(
                                "Computer Use · no observable visual effect; replanning"
                            )
                        frame = new_frame
                    else:
                        time.sleep(min(1.0, action.seconds))
                        frame = capture.latest(timeout=1.0)

                    self._apply_recovery_state(recovery)
                    self._set_frame_state(frame, state="observing")
                    self._apply_perception_stats(capture)
                    break

                if replan_requested:
                    continue

            self._finish(
                "failed",
                error=f"Computer Use reached the configured step limit ({max_steps}).",
            )

        except Exception as exc:
            self._finish("failed", error=str(exc))
            self._log(f"Computer Use · error: {exc}")
        finally:
            if planner is not None:
                try:
                    self._apply_cost_snapshot(planner.finish_telemetry())
                except Exception:
                    pass
            if capture is not None:
                try:
                    self._apply_perception_stats(capture)
                except Exception:
                    pass
                try:
                    capture.stop()
                except Exception:
                    pass

    def _wait_until_resumed(self) -> bool:
        while not self._stop_event.is_set():
            if self._resume_event.wait(timeout=0.2):
                return True
        return False

    def _focus_target_window(self) -> str:
        title = str(self._state.target_window or "").strip()
        if not title:
            return ""
        try:
            from actions.computer_control import computer_control

            return str(
                computer_control(
                    parameters={"action": "focus_window", "title": title},
                    player=self._player,
                )
                or ""
            )
        except Exception as exc:
            return f"focus_window failed: {exc}"

    def _recover_target_window(
        self,
        capture: Any,
        recovery: Any,
        recovery_policy: Any,
        *,
        reason: str,
    ) -> Any | None:
        if not recovery.can_recover(recovery_policy):
            return None

        recovery.note_recovery(reason, kind="reacquire")
        self._apply_recovery_state(recovery)
        with self._lock:
            self._state.state = "recovering"
            self._state.target_locked = False
        self._log("Computer Use · target window lost; attempting bounded reacquisition")

        focus_result = self._focus_target_window()
        if "failed" in focus_result.casefold():
            return None

        deadline = time.monotonic() + recovery_policy.reacquire_timeout
        while not self._stop_event.is_set() and time.monotonic() < deadline:
            if not self._wait_until_resumed():
                return None
            try:
                candidate = capture.latest(timeout=0.25)
            except Exception:
                time.sleep(0.08)
                continue
            if candidate.capture_scope == "window":
                with self._lock:
                    self._state.target_locked = True
                self._log("Computer Use · target window reacquired")
                return candidate
            time.sleep(0.08)
        return None

    def _set_frame_state(self, frame: Any, *, state: str) -> None:
        with self._lock:
            self._state.state = state
            self._state.monitor_index = frame.monitor_index
            self._state.visual_updates = frame.sequence
            self._state.capture_scope = frame.capture_scope
            self._state.capture_savings_pct = int(round(frame.pixel_savings * 100))
            self._state.target_locked = bool(
                self._state.target_window and frame.capture_scope == "window"
            )

    def _apply_recovery_state(self, recovery: Any) -> None:
        try:
            snapshot = recovery.snapshot()
        except Exception:
            return
        with self._lock:
            self._state.recovery_count = int(snapshot.get("recoveries") or 0)
            self._state.retry_count = int(snapshot.get("safe_action_retries") or 0)
            self._state.no_change_streak = int(snapshot.get("no_change_streak") or 0)
            self._state.stale_replans = int(snapshot.get("stale_replans") or 0)
            self._state.target_reacquisitions = int(
                snapshot.get("target_reacquisitions") or 0
            )
            self._state.last_recovery_reason = str(snapshot.get("last_reason") or "")

    def _apply_cost_snapshot(self, snapshot: dict[str, Any] | None) -> None:
        if not isinstance(snapshot, dict):
            return
        with self._lock:
            self._state.telemetry_task_id = str(snapshot.get("task_id") or "")
            self._state.input_tokens = int(snapshot.get("input_tokens") or 0)
            self._state.output_tokens = int(snapshot.get("output_tokens") or 0)
            self._state.cached_input_tokens = int(
                snapshot.get("cached_input_tokens") or 0
            )
            estimated = snapshot.get("estimated_cost_usd")
            self._state.estimated_cost_usd = (
                float(estimated) if estimated is not None else None
            )
            self._state.known_cost_usd = float(snapshot.get("known_cost_usd") or 0.0)
            self._state.cost_complete = bool(snapshot.get("cost_complete", False))

    def _apply_perception_stats(self, capture: Any) -> None:
        try:
            stats = capture.perception_stats()
        except Exception:
            return
        if not isinstance(stats, dict):
            return
        with self._lock:
            self._state.perception_keyframes = int(stats.get("keyframes") or 0)
            self._state.perception_duplicates = int(
                stats.get("duplicates_suppressed") or 0
            )

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
            self._state.paused = False
            if result:
                self._state.result = result
            if error:
                self._state.last_error = error
        self._resume_event.set()

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
