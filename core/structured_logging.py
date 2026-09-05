from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Iterator, Mapping, TextIO


_CORRELATION_ID: ContextVar[str] = ContextVar("antonella_correlation_id", default="-")
_TASK_ID: ContextVar[str] = ContextVar("antonella_task_id", default="-")

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "cookies",
    "credential",
    "credentials",
    "gemini_api_key",
    "openai_api_key",
    "password",
    "secret",
    "session_token",
    "token",
}
_CONTENT_KEYS = {
    "args",
    "arguments",
    "clipboard",
    "clipboard_text",
    "content",
    "description",
    "error_message",
    "exception_message",
    "file_content",
    "filename",
    "image",
    "image_bytes",
    "message_text",
    "objective",
    "path",
    "prompt",
    "query",
    "raw_response",
    "receiver",
    "response",
    "response_payload",
    "result_text",
    "screenshot",
    "text",
    "url",
    "value",
}
_CANONICAL_FIELDS = {
    "task_id",
    "tool",
    "stage",
    "provider",
    "model",
    "capability",
    "role",
    "route_tier",
    "policy_effect",
    "status",
    "attempt",
    "latency_ms",
    "duration_ms",
    "cost_usd",
    "cost_complete",
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "reasoning_tokens",
    "total_tokens",
    "billable_output_tokens",
    "delivered",
    "verified",
    "can_claim_success",
    "retry",
    "retryable",
    "fallback",
    "recovery",
    "recovery_count",
    "retry_count",
    "stale_replans",
    "target_reacquisitions",
    "reason_code",
    "requires_approval",
    "executed",
    "ok",
    "error",
    "error_type",
    "error_class",
}
_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")
_EVENT_RE = re.compile(r"[^A-Za-z0-9_.:-]+")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+\-/]+=*")
_OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")
_GOOGLE_KEY_RE = re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_MAX_STRING_LENGTH = 512
_MAX_DEPTH = 5
_MAX_MAPPING_ITEMS = 48
_MAX_SEQUENCE_ITEMS = 32


# -.-.-.-
def _normalize_key(key: str) -> str:
    return str(key or "").strip().lower().replace("-", "_")


# -.-.-.-
def _is_sensitive_key(key: str) -> bool:
    normalized = _normalize_key(key)
    return (
        normalized in _SENSITIVE_KEYS
        or normalized.endswith("_token")
        or normalized.endswith("_secret")
        or normalized.endswith("_password")
        or normalized.endswith("_api_key")
    )


# -.-.-.-
def _is_private_content_key(key: str) -> bool:
    normalized = _normalize_key(key)
    return normalized in _CONTENT_KEYS or normalized.endswith("_content")


# -.-.-.-
def _safe_context_id(value: str | None, *, prefix: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "-"
    if _ID_RE.fullmatch(raw):
        return raw
    digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"{prefix}-{digest}"


# -.-.-.-
def _safe_event_name(event: str) -> str:
    cleaned = _EVENT_RE.sub("_", str(event or "event").strip()).strip("_.:-")
    return (cleaned or "event")[:96]


# -.-.-.-
def _redact_string(value: str) -> str:
    output = str(value)
    output = _BEARER_RE.sub("Bearer [REDACTED]", output)
    output = _OPENAI_KEY_RE.sub("[REDACTED_API_KEY]", output)
    output = _GOOGLE_KEY_RE.sub("[REDACTED_API_KEY]", output)
    output = _JWT_RE.sub("[REDACTED_TOKEN]", output)
    output = _EMAIL_RE.sub("[REDACTED_EMAIL]", output)
    if len(output) > _MAX_STRING_LENGTH:
        output = output[:_MAX_STRING_LENGTH] + "…"
    return output


# -.-.-.-
def redact(value: Any, key: str | None = None) -> Any:
    """Redact and bound values before they enter structured observability.

    Content-bearing fields are removed rather than pattern-scrubbed. The traversal is
    depth/item bounded and cycle-safe so malformed metadata cannot break task execution or
    create unbounded log records.
    """
    return _redact(value, key=key, depth=0, seen=set())


# -.-.-.-
def _redact(value: Any, *, key: str | None, depth: int, seen: set[int]) -> Any:
    if key is not None and _is_sensitive_key(key):
        return "[REDACTED]"
    if key is not None and _is_private_content_key(key):
        if isinstance(value, (bytes, bytearray, memoryview, str)):
            return {"redacted": True, "length": len(value)}
        return "[REDACTED_CONTENT]"
    if depth >= _MAX_DEPTH:
        return "[MAX_DEPTH]"

    if isinstance(value, Mapping):
        marker = id(value)
        if marker in seen:
            return "[CYCLE]"
        seen.add(marker)
        try:
            output: dict[str, Any] = {}
            for index, (item_key, item_value) in enumerate(value.items()):
                if index >= _MAX_MAPPING_ITEMS:
                    output["_truncated"] = True
                    break
                normalized_key = str(item_key)[:96]
                output[normalized_key] = _redact(
                    item_value,
                    key=normalized_key,
                    depth=depth + 1,
                    seen=seen,
                )
            return output
        finally:
            seen.discard(marker)

    if isinstance(value, (list, tuple, set)):
        marker = id(value)
        if marker in seen:
            return "[CYCLE]"
        seen.add(marker)
        try:
            items = list(value)
            output = [
                _redact(item, key=None, depth=depth + 1, seen=seen)
                for item in items[:_MAX_SEQUENCE_ITEMS]
            ]
            if len(items) > _MAX_SEQUENCE_ITEMS:
                output.append("[TRUNCATED]")
            return output
        finally:
            seen.discard(marker)

    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"type": "bytes", "length": len(value)}
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return _redact_string(type(value).__name__)


# -.-.-.-
def safe_error_metadata(error: BaseException | None) -> dict[str, Any]:
    if error is None:
        return {"error": False, "error_type": ""}
    return {
        "error": True,
        "error_type": type(error).__name__[:96],
    }


class AntonellaJsonFormatter(logging.Formatter):
    # -.-.-.-
    def format(self, record: logging.LogRecord) -> str:
        fields = getattr(record, "antonella_fields", None)
        safe_fields = redact(fields) if isinstance(fields, Mapping) else {}
        if not isinstance(safe_fields, Mapping):
            safe_fields = {}

        correlation_id = _safe_context_id(
            getattr(record, "correlation_id", _CORRELATION_ID.get()),
            prefix="corr",
        )
        task_id = _safe_context_id(
            str(safe_fields.get("task_id") or _TASK_ID.get()),
            prefix="task",
        )

        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "correlation_id": correlation_id,
            "task_id": task_id,
            "event": _safe_event_name(record.getMessage()),
            "message": _safe_event_name(record.getMessage()),
        }

        remaining: dict[str, Any] = {}
        for field_key, field_value in safe_fields.items():
            normalized = str(field_key)
            if normalized == "task_id":
                continue
            if normalized in _CANONICAL_FIELDS:
                payload[normalized] = field_value
            else:
                remaining[normalized] = field_value
        if remaining:
            payload["fields"] = remaining

        if record.exc_info:
            exc_type = record.exc_info[0]
            payload["exception"] = {
                "type": getattr(exc_type, "__name__", "Exception")[:96]
            }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class CorrelationFilter(logging.Filter):
    # -.-.-.-
    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "correlation_id", None):
            record.correlation_id = _CORRELATION_ID.get()
        return True


# -.-.-.-
def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> logging.Logger:
    """Configure Antonella's root logger with one bounded JSON handler."""
    logger = logging.getLogger("antonella")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    logger.handlers.clear()

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(AntonellaJsonFormatter())
    handler.addFilter(CorrelationFilter())
    logger.addHandler(handler)
    return logger


# -.-.-.-
def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"antonella.{name}")
    if not logging.getLogger("antonella").handlers:
        configure_logging()
    return logger


# -.-.-.-
def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    *,
    correlation_id: str | None = None,
    task_id: str | None = None,
    **fields: Any,
) -> None:
    extra_fields = dict(fields)
    if task_id is not None:
        extra_fields["task_id"] = _safe_context_id(task_id, prefix="task")
    extra: dict[str, Any] = {"antonella_fields": extra_fields}
    if correlation_id is not None:
        extra["correlation_id"] = _safe_context_id(correlation_id, prefix="corr")
    logger.log(level, _safe_event_name(event), extra=extra)


# -.-.-.-
def log_orchestration_event(event: Any, logger: logging.Logger | None = None) -> None:
    """Log an OrchestrationEvent without importing the orchestrator module."""
    target = logger or get_logger("orchestrator")
    stage_obj = getattr(event, "stage", "unknown")
    stage = str(getattr(stage_obj, "value", stage_obj) or "unknown")
    correlation_id = str(getattr(event, "correlation_id", "") or "")
    tool = str(getattr(event, "tool_name", "") or "")[:96]
    detail = _safe_event_name(str(getattr(event, "detail", "") or stage))
    metadata = getattr(event, "metadata", None)
    safe_metadata = dict(metadata) if isinstance(metadata, Mapping) else {}
    safe_metadata.pop("argument_names", None)
    log_event(
        target,
        logging.INFO,
        f"agent.{stage}.{detail}",
        correlation_id=correlation_id,
        task_id=_TASK_ID.get() if _TASK_ID.get() != "-" else correlation_id,
        tool=tool,
        stage=stage,
        **safe_metadata,
    )


# -.-.-.-
def log_provider_attempt(
    logger: logging.Logger,
    *,
    task_id: str,
    provider: str,
    model: str,
    capability: str,
    role: str,
    attempt: int,
    latency_ms: int,
    ok: bool,
    retry: bool,
    fallback: bool,
    cost_usd: float | None,
    retryable: bool | None = None,
    usage: Mapping[str, Any] | None = None,
    error_type: str = "",
    error_class: str = "",
) -> None:
    usage_fields: dict[str, int] = {}
    if isinstance(usage, Mapping):
        for name in (
            "input_tokens",
            "output_tokens",
            "cached_input_tokens",
            "reasoning_tokens",
            "total_tokens",
            "billable_output_tokens",
        ):
            try:
                usage_fields[name] = max(0, int(usage.get(name) or 0))
            except (TypeError, ValueError):
                usage_fields[name] = 0

    fields: dict[str, Any] = {
        "provider": str(provider)[:64],
        "model": str(model)[:128],
        "capability": str(capability)[:32],
        "role": str(role)[:32],
        "attempt": max(1, int(attempt)),
        "latency_ms": max(0, int(latency_ms)),
        "ok": bool(ok),
        "retry": bool(retry),
        "fallback": bool(fallback),
        "cost_usd": float(cost_usd) if cost_usd is not None else None,
        "error": not bool(ok),
        "error_type": str(error_type or "")[:96],
        "error_class": str(error_class or "")[:96],
        **usage_fields,
    }
    if retryable is not None:
        fields["retryable"] = bool(retryable)

    log_event(
        logger,
        logging.INFO if ok else logging.WARNING,
        "provider.attempt",
        task_id=task_id,
        **fields,
    )


# -.-.-.-
def log_recovery_event(
    logger: logging.Logger,
    *,
    task_id: str,
    reason_code: str,
    recovery_count: int,
    retry_count: int = 0,
    stale_replans: int = 0,
    target_reacquisitions: int = 0,
    retry: bool = False,
    status: str = "recovering",
) -> None:
    """Emit only bounded, runtime-generated recovery metadata."""
    log_event(
        logger,
        logging.WARNING,
        "computer_use.recovery",
        task_id=task_id,
        stage="recover",
        status=str(status or "recovering")[:32],
        recovery=True,
        reason_code=_safe_event_name(reason_code),
        recovery_count=max(0, int(recovery_count)),
        retry_count=max(0, int(retry_count)),
        stale_replans=max(0, int(stale_replans)),
        target_reacquisitions=max(0, int(target_reacquisitions)),
        retry=bool(retry),
    )


# -.-.-.-
@contextmanager
def correlation_context(correlation_id: str | None = None) -> Iterator[str]:
    value = _safe_context_id(correlation_id or uuid.uuid4().hex, prefix="corr")
    token = _CORRELATION_ID.set(value)
    try:
        yield value
    finally:
        _CORRELATION_ID.reset(token)


# -.-.-.-
@contextmanager
def task_context(task_id: str | None = None) -> Iterator[str]:
    value = _safe_context_id(task_id or uuid.uuid4().hex, prefix="task")
    token = _TASK_ID.set(value)
    try:
        yield value
    finally:
        _TASK_ID.reset(token)
