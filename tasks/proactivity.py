"""Proactivity rules, quiet hours and task evidence (ANT-278 F10–F15).

Principles that never bend:
- an observation NEVER creates a strong routine (F10/F11): the ladder is
  observed_once -> possible_habit -> probable_habit -> approved_routine,
  and only the last stage exists because the user explicitly approved it;
- Antonella may SUGGEST; she never executes a routine automatically;
- quiet hours (F12) gate any suggestion by timezone and channel;
- task evidence (F15) reports what was requested/executed/delivered/
  verified/remaining/failed — cost and provider only when actually
  provided, never invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tasks.model import Task, TaskState

STAGES = ("observed_once", "possible_habit", "probable_habit", "approved_routine")
SUGGESTION_MIN_STAGE = "possible_habit"


# ---------------------------------------------------------------------------
# F11 — habit ladder (deterministic, no magic)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Observation:
    signature: str          # what was observed (normalised, e.g. "open_ide@morning")
    at_epoch: float


def habit_stage(
    observations: list[Observation],
    *,
    signature: str,
    approved: bool = False,
    min_occurrences_possible: int = 3,
    min_occurrences_probable: int = 5,
) -> str:
    """Return the ladder stage for a signature.

    approved=True is the ONLY path to approved_routine — the user's
    explicit authorisation, never inferred from frequency.
    """
    occurrences = sorted(o.at_epoch for o in observations if o.signature == signature)
    if approved:
        return "approved_routine"
    if len(occurrences) >= min_occurrences_probable:
        return "probable_habit"
    if len(occurrences) >= min_occurrences_possible:
        return "possible_habit"
    return "observed_once"


def suggestion_allowed(stage: str) -> bool:
    """F10: suggest from possible_habit upwards; never auto-execute."""
    order = STAGES
    if stage not in order:
        return False
    return order.index(stage) >= order.index(SUGGESTION_MIN_STAGE)


# ---------------------------------------------------------------------------
# F12 — quiet hours
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class QuietHours:
    tz_offset_minutes: int = 0
    start_minute: int = 22 * 60   # 22:00 local
    end_minute: int = 7 * 60      # 07:00 local
    allowed_channels: tuple[str, ...] = ("ui",)

    # -.-.-.-
    def is_quiet(self, now_epoch: float) -> bool:
        from datetime import datetime, timedelta, timezone

        tz = timezone(timedelta(minutes=self.tz_offset_minutes))
        local = datetime.fromtimestamp(now_epoch, tz=tz)
        minute_of_day = local.hour * 60 + local.minute
        if self.start_minute <= self.end_minute:
            return self.start_minute <= minute_of_day < self.end_minute
        # wrap-around window (e.g. 22:00 -> 07:00)
        return minute_of_day >= self.start_minute or minute_of_day < self.end_minute

    # -.-.-.-
    def channel_allowed(self, channel: str) -> bool:
        return channel in self.allowed_channels


# ---------------------------------------------------------------------------
# F15 — final task evidence
# ---------------------------------------------------------------------------
def task_evidence(
    task: Task,
    *,
    cost: float | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Evidence summary for a finished task — never invents cost/provider."""
    executed = [s for s in task.steps if s.state == "done"]
    failed = [s for s in task.steps if s.state == "failed"]
    remaining = [s for s in task.steps if s.state not in ("done", "failed")]
    evidence: dict[str, Any] = {
        "requested": task.title,
        "state": task.state.value,
        "executed": [s.name for s in executed],
        "delivered": len(executed),
        "verified_steps": sum(1 for s in executed if bool(s.outcome.get("verified"))),
        "failures": [
            {"step": s.name, "error": str(s.outcome.get("error") or s.outcome.get("error_type") or "unknown")}
            for s in failed
        ],
        "remaining": [s.name for s in remaining],
        "total_steps": len(task.steps),
    }
    if cost is not None:
        evidence["cost"] = cost
    if provider:
        evidence["provider"] = provider
    if model:
        evidence["model"] = model
    return evidence


def is_suggestion_ready(task: Task) -> bool:
    """A task parked in awaiting_approval/recovering is a suggestion target,
    never an auto-run: explicit helper so callers cannot conflate states."""
    return task.state in (TaskState.AWAITING_APPROVAL, TaskState.CREATED)
EOF_MARKER_UNUSED = None
