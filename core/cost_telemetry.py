from __future__ import annotations

import hashlib
import logging
import math
import re
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from core.providers.contracts import ProviderUsage
from core.structured_logging import get_logger, log_event, log_provider_attempt


_MAX_TASKS = 256
_MAX_EVENTS_PER_TASK = 128
_SAFE_TASK_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,96}$")
_ALLOWED_SAVED_CALL_CATEGORIES = {
    "computer_use_batch",
    "cache_hit",
    "local_fast_path",
    "deterministic_route",
    "other",
}


@dataclass(frozen=True)
class ModelPricing:
    """USD per one million tokens for one configured provider/model.

    No prices are hardcoded in Antonella. Missing rates deliberately produce an
    unknown estimate rather than silently assuming a provider's commercial terms.
    """

    input_per_million: float | None = None
    output_per_million: float | None = None
    cached_input_per_million: float | None = None


@dataclass(frozen=True)
class CostTelemetryEvent:
    provider: str
    model: str
    capability: str
    role: str
    attempt: int
    ok: bool
    latency_ms: int
    fallback: bool
    retry: bool
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    estimated_cost_usd: float | None = None
    error_class: str = ""

    def safe_metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "capability": self.capability,
            "role": self.role,
            "attempt": self.attempt,
            "ok": self.ok,
            "latency_ms": self.latency_ms,
            "fallback": self.fallback,
            "retry": self.retry,
            "usage": self.usage.safe_metadata(),
            "estimated_cost_usd": self.estimated_cost_usd,
            "error_class": self.error_class,
        }


@dataclass
class _TaskCostState:
    task_id: str
    kind: str
    started_at: float
    started_monotonic: float
    finished_at: float = 0.0
    finished_monotonic: float = 0.0
    provider_attempts: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    retries: int = 0
    fallback_attempts: int = 0
    calls_saved: int = 0
    cache_hits: int = 0
    total_latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    billable_output_tokens: int = 0
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    known_cost_usd: float = 0.0
    cost_unknown_calls: int = 0
    events: list[CostTelemetryEvent] = field(default_factory=list)


# -.-.-.-
def _safe_task_id(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return uuid.uuid4().hex[:16]
    if _SAFE_TASK_ID_RE.fullmatch(raw):
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"task-{digest}"


# -.-.-.-
def _safe_label(value: Any, *, fallback: str = "") -> str:
    return str(value or fallback).strip()[:160]


# -.-.-.-
def _optional_non_negative_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0 or not math.isfinite(number):
        return None
    return number


# -.-.-.-
def parse_model_pricing(value: Mapping[str, Any] | None) -> ModelPricing | None:
    if not isinstance(value, Mapping):
        return None
    input_rate = _optional_non_negative_float(
        value.get("input") if "input" in value else value.get("input_per_million")
    )
    output_rate = _optional_non_negative_float(
        value.get("output") if "output" in value else value.get("output_per_million")
    )
    cached_rate = _optional_non_negative_float(
        value.get("cached_input")
        if "cached_input" in value
        else value.get("cached_input_per_million")
    )
    if input_rate is None and output_rate is None and cached_rate is None:
        return None
    return ModelPricing(
        input_per_million=input_rate,
        output_per_million=output_rate,
        cached_input_per_million=cached_rate,
    )


# -.-.-.-
def resolve_model_pricing(
    config: Mapping[str, Any] | None,
    *,
    provider: str,
    model: str,
) -> ModelPricing | None:
    """Resolve an explicitly configured price without network calls or defaults."""
    if not isinstance(config, Mapping):
        return None
    table = config.get("model_pricing_usd_per_million_tokens")
    if not isinstance(table, Mapping):
        return None
    provider_name = _safe_label(provider).lower()
    model_name = _safe_label(model)
    for key in (f"{provider_name}/{model_name}", model_name):
        entry = table.get(key)
        if isinstance(entry, Mapping):
            return parse_model_pricing(entry)
    return None


# -.-.-.-
def estimate_usage_cost_usd(
    usage: ProviderUsage | None,
    pricing: ModelPricing | None,
) -> float | None:
    """Return a defensible estimate or None when required information is absent."""
    if usage is None or not usage.has_usage or pricing is None:
        return None

    input_tokens = max(0, int(usage.input_tokens))
    priced_output_tokens = max(0, int(usage.priced_output_tokens))
    cached_tokens = min(input_tokens, max(0, int(usage.cached_input_tokens)))
    uncached_tokens = max(0, input_tokens - cached_tokens)

    if not input_tokens and not priced_output_tokens:
        return None
    if uncached_tokens and pricing.input_per_million is None:
        return None
    if cached_tokens and pricing.cached_input_per_million is None:
        return None
    if priced_output_tokens and pricing.output_per_million is None:
        return None

    cost = 0.0
    if uncached_tokens:
        cost += uncached_tokens * float(pricing.input_per_million or 0.0) / 1_000_000
    if cached_tokens:
        cost += cached_tokens * float(pricing.cached_input_per_million or 0.0) / 1_000_000
    if priced_output_tokens:
        cost += priced_output_tokens * float(pricing.output_per_million or 0.0) / 1_000_000
    if not math.isfinite(cost):
        return None
    return round(cost, 12)


class CostTelemetry:
    """Process-local, bounded and content-free AI cost telemetry."""

    def __init__(
        self,
        *,
        max_tasks: int = _MAX_TASKS,
        max_events_per_task: int = _MAX_EVENTS_PER_TASK,
        wall_clock=time.time,
        monotonic_clock=time.monotonic,
    ) -> None:
        self._max_tasks = max(1, min(4096, int(max_tasks)))
        self._max_events = max(1, min(2048, int(max_events_per_task)))
        self._wall_clock = wall_clock
        self._monotonic = monotonic_clock
        self._lock = threading.RLock()
        self._tasks: OrderedDict[str, _TaskCostState] = OrderedDict()

    # -.-.-.-
    def start_task(self, task_id: str | None = None, *, kind: str = "provider") -> str:
        selected = _safe_task_id(task_id)
        with self._lock:
            existing = self._tasks.get(selected)
            if existing is not None:
                self._tasks.move_to_end(selected)
                return selected
            self._tasks[selected] = _TaskCostState(
                task_id=selected,
                kind=_safe_label(kind, fallback="provider") or "provider",
                started_at=float(self._wall_clock()),
                started_monotonic=float(self._monotonic()),
            )
            self._evict_locked()
        return selected

    # -.-.-.-
    def record_provider_attempt(
        self,
        task_id: str,
        *,
        provider: str,
        model: str,
        capability: str,
        role: str,
        attempt: int,
        ok: bool,
        latency_ms: int,
        fallback: bool = False,
        retry: bool = False,
        usage: ProviderUsage | None = None,
        pricing: ModelPricing | None = None,
        error_class: str = "",
    ) -> float | None:
        selected = self.start_task(task_id)
        safe_usage = usage if isinstance(usage, ProviderUsage) else ProviderUsage()
        estimate = estimate_usage_cost_usd(safe_usage, pricing)
        event = CostTelemetryEvent(
            provider=_safe_label(provider),
            model=_safe_label(model),
            capability=_safe_label(capability),
            role=_safe_label(role),
            attempt=max(1, int(attempt or 1)),
            ok=bool(ok),
            latency_ms=max(0, int(latency_ms or 0)),
            fallback=bool(fallback),
            retry=bool(retry),
            usage=safe_usage,
            estimated_cost_usd=estimate,
            error_class=_safe_label(error_class),
        )

        with self._lock:
            state = self._tasks[selected]
            state.provider_attempts += 1
            state.successful_calls += int(bool(ok))
            state.failed_calls += int(not bool(ok))
            state.retries += int(bool(retry))
            state.fallback_attempts += int(bool(fallback))
            state.total_latency_ms += event.latency_ms
            state.input_tokens += safe_usage.input_tokens
            state.output_tokens += safe_usage.output_tokens
            state.billable_output_tokens += safe_usage.priced_output_tokens
            state.cached_input_tokens += safe_usage.cached_input_tokens
            state.reasoning_tokens += safe_usage.reasoning_tokens
            state.total_tokens += safe_usage.total_tokens
            if estimate is None:
                state.cost_unknown_calls += 1
            else:
                state.known_cost_usd += estimate
            state.events.append(event)
            if len(state.events) > self._max_events:
                del state.events[: len(state.events) - self._max_events]
            self._tasks.move_to_end(selected)

        try:
            log_provider_attempt(
                get_logger("provider"),
                task_id=selected,
                provider=event.provider,
                model=event.model,
                capability=event.capability,
                role=event.role,
                attempt=event.attempt,
                latency_ms=event.latency_ms,
                ok=event.ok,
                retry=event.retry,
                retryable=False,
                fallback=event.fallback,
                cost_usd=event.estimated_cost_usd,
                usage=safe_usage.safe_metadata(),
                error_class=event.error_class,
            )
        except Exception:
            pass
        return estimate

    # -.-.-.-
    def record_saved_call(
        self,
        task_id: str,
        *,
        category: str = "other",
        count: int = 1,
    ) -> None:
        selected = self.start_task(task_id)
        safe_category = str(category or "other").strip().lower()
        if safe_category not in _ALLOWED_SAVED_CALL_CATEGORIES:
            safe_category = "other"
        amount = max(0, min(10_000, int(count or 0)))
        with self._lock:
            state = self._tasks[selected]
            state.calls_saved += amount
            if safe_category == "cache_hit":
                state.cache_hits += amount
            self._tasks.move_to_end(selected)

    # -.-.-.-
    def finish_task(self, task_id: str) -> dict[str, Any] | None:
        selected = _safe_task_id(task_id)
        with self._lock:
            state = self._tasks.get(selected)
            if state is None:
                return None
            just_finished = not bool(state.finished_at)
            if just_finished:
                state.finished_at = float(self._wall_clock())
                state.finished_monotonic = float(self._monotonic())
            snapshot = self._snapshot_locked(state)

        if just_finished:
            try:
                log_event(
                    get_logger("provider"),
                    logging.INFO,
                    "provider.task_finished",
                    task_id=selected,
                    duration_ms=int(snapshot.get("duration_ms") or 0),
                    latency_ms=int(snapshot.get("total_latency_ms") or 0),
                    cost_usd=snapshot.get("estimated_cost_usd"),
                    cost_complete=bool(snapshot.get("cost_complete", False)),
                    input_tokens=int(snapshot.get("input_tokens") or 0),
                    output_tokens=int(snapshot.get("output_tokens") or 0),
                    cached_input_tokens=int(snapshot.get("cached_input_tokens") or 0),
                    reasoning_tokens=int(snapshot.get("reasoning_tokens") or 0),
                    total_tokens=int(snapshot.get("total_tokens") or 0),
                    billable_output_tokens=int(snapshot.get("billable_output_tokens") or 0),
                    retry=int(snapshot.get("retries") or 0) > 0,
                    fallback=int(snapshot.get("fallback_attempts") or 0) > 0,
                    ok=(
                        int(snapshot.get("successful_calls") or 0) > 0
                        or int(snapshot.get("provider_attempts") or 0) == 0
                    ),
                )
            except Exception:
                pass
        return snapshot

    # -.-.-.-
    def snapshot(self, task_id: str) -> dict[str, Any] | None:
        selected = _safe_task_id(task_id)
        with self._lock:
            state = self._tasks.get(selected)
            if state is None:
                return None
            return self._snapshot_locked(state)

    # -.-.-.-
    def recent_snapshots(self, *, limit: int = 20) -> list[dict[str, Any]]:
        count = max(1, min(200, int(limit or 20)))
        with self._lock:
            states = list(self._tasks.values())[-count:]
            return [self._snapshot_locked(state) for state in reversed(states)]

    # -.-.-.-
    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()

    # -.-.-.-
    def _snapshot_locked(self, state: _TaskCostState) -> dict[str, Any]:
        ended = state.finished_monotonic or float(self._monotonic())
        duration_ms = max(0, round((ended - state.started_monotonic) * 1000))
        cost_complete = state.provider_attempts == 0 or state.cost_unknown_calls == 0
        estimated_cost = (
            round(state.known_cost_usd, 12) if cost_complete else None
        )
        return {
            "task_id": state.task_id,
            "kind": state.kind,
            "started_at": state.started_at,
            "finished_at": state.finished_at or None,
            "duration_ms": duration_ms,
            "provider_attempts": state.provider_attempts,
            "successful_calls": state.successful_calls,
            "failed_calls": state.failed_calls,
            "retries": state.retries,
            "fallback_attempts": state.fallback_attempts,
            "calls_saved": state.calls_saved,
            "cache_hits": state.cache_hits,
            "total_latency_ms": state.total_latency_ms,
            "input_tokens": state.input_tokens,
            "output_tokens": state.output_tokens,
            "billable_output_tokens": state.billable_output_tokens,
            "cached_input_tokens": state.cached_input_tokens,
            "reasoning_tokens": state.reasoning_tokens,
            "total_tokens": state.total_tokens,
            "estimated_cost_usd": estimated_cost,
            "known_cost_usd": round(state.known_cost_usd, 12),
            "cost_complete": cost_complete,
            "cost_unknown_calls": state.cost_unknown_calls,
            "events": [event.safe_metadata() for event in state.events],
        }

    # -.-.-.-
    def _evict_locked(self) -> None:
        while len(self._tasks) > self._max_tasks:
            self._tasks.popitem(last=False)


_TELEMETRY = CostTelemetry()


# -.-.-.-
def get_cost_telemetry() -> CostTelemetry:
    return _TELEMETRY
