"""Voice runtime primitives (ANT-271 A3–A5, V1–V3).

Pure, deterministic, thread-safe helpers used by the live audio engine:

- ``TurnRegistry`` (A3/V2): generation tokens for the playback queue —
  when a turn is interrupted the token advances and stale queued audio is
  rejected instead of played.
- ``BargeInGate`` (V1/A4): energy-gated automatic barge-in. Disabled by
  default and guarded by a lock because audio callbacks may arrive from a
  native sound thread.
- ``VoiceLatency`` (V3/V5): bounded client-side latency milestones that can
  actually be measured. It never stores speech content — timestamps only.
"""

from __future__ import annotations

import threading
import time
import json
import os
import tempfile
from collections import deque
from pathlib import Path


class TurnRegistry:
    """Monotonic turn ownership for the playback queue."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current = 0

    # -.-.-.-
    def current(self) -> int:
        with self._lock:
            return self._current

    # -.-.-.-
    def advance(self) -> int:
        """Invalidate everything belonging to the previous turn."""
        with self._lock:
            self._current += 1
            return self._current

    # -.-.-.-
    def is_current(self, token: int) -> bool:
        with self._lock:
            return token == self._current


class BargeInGate:
    """Thread-safe energy-gated automatic barge-in (V1).

    ``feed(rms, now)`` returns True once per detection when the gate is
    enabled and ``frames_above`` consecutive frames exceed the threshold;
    a cooldown then suppresses further triggers. The state transition is
    guarded because native audio callbacks are not an asyncio-owned surface.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        threshold: int = 900,
        frames_above: int = 3,
        cooldown_seconds: float = 2.0,
    ):
        self.enabled = enabled
        self.threshold = max(0, int(threshold))
        self.frames_above = max(1, int(frames_above))
        self.cooldown_seconds = max(0.0, float(cooldown_seconds))
        self._lock = threading.Lock()
        self._streak = 0
        self._last_trigger = float("-inf")

    # -.-.-.-
    def feed(self, rms: float, now: float) -> bool:
        if not self.enabled:
            return False
        with self._lock:
            if rms >= self.threshold:
                self._streak += 1
            else:
                self._streak = 0
                return False
            if (
                self._streak >= self.frames_above
                and now - self._last_trigger >= self.cooldown_seconds
            ):
                self._streak = 0
                self._last_trigger = now
                return True
            return False


class VoiceLatency:
    """Bounded client-side latency milestones (V3/V5). Timestamps only.

    Honest limitation: there is NO trustworthy local VAD in this layer, so
    ``last_user_audio`` is only the last captured mic frame. It must never be
    presented as a proven end-of-speech timestamp.
    """

    MILESTONES = (
        "last_user_audio",
        "input_transcription",
        "agent_start",
        "first_action",
        "first_response_audio",
    )

    def __init__(self, *, output_path: str | Path = "voice_metrics.json", max_turns: int = 200) -> None:
        self._lock = threading.RLock()
        self._marks: dict[str, float] = {}
        self._turns: deque[dict] = deque(maxlen=max(1, min(1000, int(max_turns))))
        self._output_path = Path(output_path)
        self._turn_id = 0

    # -.-.-.-
    def mark(self, milestone: str, now: float | None = None) -> None:
        if milestone not in self.MILESTONES:
            raise ValueError(f"unknown latency milestone: {milestone}")
        value = now if now is not None else time.monotonic()
        with self._lock:
            # First-occurrence milestones keep their first value in a turn.
            if milestone != "last_user_audio" and milestone in self._marks:
                return
            self._marks[milestone] = value

    # -.-.-.-
    def new_turn(self) -> None:
        with self._lock:
            self._marks.clear()

    # -.-.-.-
    def complete_turn(self, *, interrupted: bool = False) -> None:
        """Record/export a bounded, content-free snapshot before resetting marks.

        Called on the receive loop, never from the microphone callback. An
        export failure is surfaced to the caller; history remains in memory
        for the next export, while marks are cleared to avoid mixing turns.
        """
        with self._lock:
            self._turn_id += 1
            self._turns.append({"turn_id": self._turn_id,
                                "interrupted": interrupted,
                                "metrics": self.snapshot()})
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                        dir=self._output_path.parent, delete=False) as stream:
                    temporary = stream.name
                    json.dump({"schema_version": 1, "source": "antonella.voice_runtime",
                               "end_of_speech_status": "NOT MEASURED",
                               "turns": list(self._turns)}, stream, allow_nan=False)
                os.replace(temporary, self._output_path)
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
                self._marks.clear()

    # -.-.-.-
    def snapshot(self) -> dict[str, float | None]:
        """Return only client-side durations that this runtime can measure."""
        with self._lock:
            marks = dict(self._marks)
        last_user = marks.get("last_user_audio")
        transcription = marks.get("input_transcription")
        agent = marks.get("agent_start")
        first_action = marks.get("first_action")
        first_audio = marks.get("first_response_audio")

        def delta(a: float | None, b: float | None) -> float | None:
            if a is None or b is None:
                return None
            value = b - a
            # A negative delta means the milestones did not describe the
            # causal order assumed by the metric; report it as unavailable.
            return None if value < 0 else round(value, 3)

        return {
            "transcription_latency_ms": _ms(delta(last_user, transcription)),
            "route_to_agent_ms": _ms(delta(transcription, agent)),
            "agent_to_first_action_ms": _ms(delta(agent, first_action)),
            "input_transcription_to_first_audio_ms": _ms(
                delta(transcription, first_audio)
            ),
            # Diagnostic only. This is NOT end-of-speech latency.
            "last_mic_frame_to_first_audio_ms": _ms(delta(last_user, first_audio)),
        }


def _ms(value: float | None) -> float | None:
    return None if value is None else round(value * 1000.0, 1)


def percentile(values: list[float], pct: float) -> float | None:
    """Honest percentile: None for empty input, never an invented number."""
    if not values:
        return None
    ordered = sorted(values)
    index = min(
        len(ordered) - 1,
        max(0, round((pct / 100.0) * (len(ordered) - 1))),
    )
    return ordered[index]
