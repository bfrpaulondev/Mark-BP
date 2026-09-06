"""Voice runtime primitives (ANT-271 A3–A5, V1–V3).

Pure, deterministic, thread-safe helpers used by the live audio engine:

- ``TurnRegistry`` (A3/V2): generation tokens for the playback queue —
  when a turn is interrupted the token advances and any stale audio that
  was already queued is rejected instead of played.
- ``BargeInGate`` (V1/A4): energy-gated automatic barge-in. Mic frames
  are analysed while the assistant speaks; the gate only fires after
  ``frames_above`` consecutive loud frames and then enforces a cooldown
  (speaker bleed protection). Disabled by default — opt-in via config.
- ``VoiceLatency`` (V3/V5): bounded milestone tracker for the client-side
  latencies that can actually be measured. Never stores speech content —
  timestamps only.
"""

from __future__ import annotations

import threading
import time


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
    """Energy-gated automatic barge-in (V1).

    ``feed(rms, now)`` returns True exactly once per detection when the
    gate is enabled and ``frames_above`` consecutive frames exceed the
    threshold; a cooldown then suppresses further triggers.
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
        self._streak = 0
        self._last_trigger = float("-inf")

    # -.-.-.-
    def feed(self, rms: float, now: float) -> bool:
        if not self.enabled:
            return False
        if rms >= self.threshold:
            self._streak += 1
        else:
            self._streak = 0
            return False
        if self._streak >= self.frames_above and now - self._last_trigger >= self.cooldown_seconds:
            self._streak = 0
            self._last_trigger = now
            return True
        return False


class VoiceLatency:
    """Bounded client-side latency milestones (V3/V5). Timestamps only.

    Honest limitation: there is NO local VAD, so "last_user_audio" marks
    the LAST CAPTURED MIC FRAME, not a proven end-of-speech. Server-side
    VAD owns the real end-of-turn signal.
    """

    MILESTONES = (
        "last_user_audio",
        "input_transcription",
        "agent_start",
        "first_action",
        "first_response_audio",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._marks: dict[str, float] = {}

    # -.-.-.-
    def mark(self, milestone: str, now: float | None = None) -> None:
        if milestone not in self.MILESTONES:
            raise ValueError(f"unknown latency milestone: {milestone}")
        value = now if now is not None else time.monotonic()
        with self._lock:
            # "first_*" milestones keep their first value within a turn.
            if milestone.startswith("first_") and milestone in self._marks:
                return
            self._marks[milestone] = value

    # -.-.-.-
    def new_turn(self) -> None:
        with self._lock:
            self._marks.clear()

    # -.-.-.-
    def snapshot(self) -> dict[str, float | None]:
        """Durations the client can honestly measure (V3)."""
        with self._lock:
            marks = dict(self._marks)
        last_user = marks.get("last_user_audio")
        transcription = marks.get("input_transcription")
        agent = marks.get("agent_start")
        first_action = marks.get("first_action")
        first_audio = marks.get("first_response_audio")

        def delta(a: float | None, b: float | None) -> float | None:
            return None if a is None or b is None else round(b - a, 3)

        # V5: without local VAD there is NO proven end-of-speech — the
        # mic-frame milestone is the LAST CAPTURED FRAME, not the end of
        # speech. Name it accordingly and never report it as
        # "after end of speech".
        return {
            "transcription_latency_ms": _ms(delta(last_user, transcription)),
            "route_to_agent_ms": _ms(delta(transcription, agent)),
            "agent_to_first_action_ms": _ms(delta(agent, first_action)),
            "last_mic_frame_to_first_audio_ms": _ms(delta(last_user, first_audio)),
        }


def _ms(value: float | None) -> float | None:
    return None if value is None else round(value * 1000.0, 1)


def percentile(values: list[float], pct: float) -> float | None:
    """Honest percentile: None for empty input, never an invented number."""
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[index]
