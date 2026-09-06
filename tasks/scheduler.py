"""Scheduler abstraction (ANT-278 F9).

Deterministic due-time computation for one-shot, fixed-interval and
daily-at schedules with an explicit UTC-offset timezone. No external
triggers are wired here; the runtime decides when to poll ``next_due``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class SchedulerSpec:
    kind: str  # once | interval | daily | weekly
    at_epoch: float | None = None       # once
    interval_seconds: int | None = None  # interval
    daily_hour: int | None = None        # daily
    daily_minute: int = 0
    weekly_weekday: int | None = None    # weekly: 0=Monday .. 6=Sunday
    tz_offset_minutes: int = 0           # timezone as fixed UTC offset


def _to_local(now_epoch: float, tz_offset_minutes: int) -> datetime:
    tz = timezone(timedelta(minutes=tz_offset_minutes))
    return datetime.fromtimestamp(now_epoch, tz=tz)


def next_due(spec: SchedulerSpec, *, now: float, last_run: float | None = None) -> float | None:
    """Next due epoch for the spec, or None when it can never fire again."""
    if spec.kind == "once":
        if spec.at_epoch is None:
            return None
        return None if (last_run is not None and last_run >= spec.at_epoch) else spec.at_epoch

    if spec.kind == "interval":
        if not spec.interval_seconds or spec.interval_seconds <= 0:
            return None
        if last_run is None:
            return now
        return last_run + spec.interval_seconds

    if spec.kind == "weekly":
        if spec.daily_hour is None or spec.weekly_weekday is None:
            return None
        local = _to_local(now, spec.tz_offset_minutes)
        candidate = local.replace(hour=spec.daily_hour, minute=spec.daily_minute, second=0, microsecond=0)
        days_ahead = (spec.weekly_weekday - candidate.weekday()) % 7
        candidate += timedelta(days=days_ahead)
        candidate_epoch = candidate.timestamp()
        if last_run is not None and candidate_epoch <= last_run:
            candidate += timedelta(days=7)
            candidate_epoch = candidate.timestamp()
        if candidate_epoch <= now and (last_run is None or candidate_epoch > last_run):
            candidate += timedelta(days=7)
            candidate_epoch = candidate.timestamp()
        return candidate_epoch

    if spec.kind == "daily":
        if spec.daily_hour is None or not 0 <= spec.daily_hour <= 23:
            return None
        local = _to_local(now, spec.tz_offset_minutes)
        candidate = local.replace(hour=spec.daily_hour, minute=spec.daily_minute, second=0, microsecond=0)
        candidate_epoch = candidate.timestamp()
        if last_run is not None and candidate_epoch <= last_run:
            candidate += timedelta(days=1)
            candidate_epoch = candidate.timestamp()
        if candidate_epoch < now and (last_run is None or candidate_epoch > last_run):
            candidate += timedelta(days=1)
            candidate_epoch = candidate.timestamp()
        return candidate_epoch

    return None
