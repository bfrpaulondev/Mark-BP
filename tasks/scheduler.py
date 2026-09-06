"""Scheduler abstraction (ANT-278 F9).

Deterministic due-time computation for one-shot, fixed-interval, daily
and weekly schedules with an explicit fixed UTC-offset timezone. No
external triggers are wired here; the runtime decides when to poll
``next_due``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class SchedulerSpec:
    kind: str  # once | interval | daily | weekly
    at_epoch: float | None = None        # once
    interval_seconds: int | None = None  # interval
    daily_hour: int | None = None        # daily / weekly
    daily_minute: int = 0
    weekly_weekday: int | None = None     # weekly: 0=Monday .. 6=Sunday
    tz_offset_minutes: int = 0            # fixed UTC offset


def _valid_clock(spec: SchedulerSpec) -> bool:
    return (
        spec.daily_hour is not None
        and 0 <= spec.daily_hour <= 23
        and 0 <= spec.daily_minute <= 59
        and -24 * 60 < spec.tz_offset_minutes < 24 * 60
    )


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
        if not _valid_clock(spec):
            return None
        if spec.weekly_weekday is None or not 0 <= spec.weekly_weekday <= 6:
            return None
        local = _to_local(now, spec.tz_offset_minutes)
        candidate = local.replace(
            hour=spec.daily_hour,
            minute=spec.daily_minute,
            second=0,
            microsecond=0,
        )
        days_ahead = (spec.weekly_weekday - candidate.weekday()) % 7
        candidate += timedelta(days=days_ahead)
        candidate_epoch = candidate.timestamp()

        # If this week's occurrence has already been recorded, move to the
        # next one. Exact ``now == candidate`` remains due; using <= here
        # would silently skip a whole week at the scheduled instant.
        if last_run is not None and candidate_epoch <= last_run:
            candidate += timedelta(days=7)
            candidate_epoch = candidate.timestamp()
        if candidate_epoch < now and (last_run is None or candidate_epoch > last_run):
            candidate += timedelta(days=7)
            candidate_epoch = candidate.timestamp()
        return candidate_epoch

    if spec.kind == "daily":
        if not _valid_clock(spec):
            return None
        local = _to_local(now, spec.tz_offset_minutes)
        candidate = local.replace(
            hour=spec.daily_hour,
            minute=spec.daily_minute,
            second=0,
            microsecond=0,
        )
        candidate_epoch = candidate.timestamp()
        if last_run is not None and candidate_epoch <= last_run:
            candidate += timedelta(days=1)
            candidate_epoch = candidate.timestamp()
        if candidate_epoch < now and (last_run is None or candidate_epoch > last_run):
            candidate += timedelta(days=1)
            candidate_epoch = candidate.timestamp()
        return candidate_epoch

    return None
