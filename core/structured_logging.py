from __future__ import annotations

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
_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "gemini_api_key",
    "password",
    "secret",
    "token",
}
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+\-/]+=*")


# -.-.-.-
def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in _SENSITIVE_KEYS or normalized.endswith("_token") or normalized.endswith("_secret")


# -.-.-.-
def redact(value: Any, key: str | None = None) -> Any:
    """Redact known secrets and common PII from structured log values."""
    if key is not None and _is_sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = _BEARER_RE.sub("Bearer [REDACTED]", value)
        return _EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    return value


class AntonellaJsonFormatter(logging.Formatter):
    # -.-.-.-
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "correlation_id": getattr(record, "correlation_id", _CORRELATION_ID.get()),
            "message": redact(record.getMessage()),
        }
        fields = getattr(record, "antonella_fields", None)
        if isinstance(fields, Mapping):
            payload["fields"] = redact(fields)
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class CorrelationFilter(logging.Filter):
    # -.-.-.-
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _CORRELATION_ID.get()
        return True


# -.-.-.-
def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> logging.Logger:
    """Configure Antonella's root logger with one JSON handler."""
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
def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    logger.log(level, event, extra={"antonella_fields": fields})


# -.-.-.-
@contextmanager
def correlation_context(correlation_id: str | None = None) -> Iterator[str]:
    value = correlation_id or uuid.uuid4().hex
    token = _CORRELATION_ID.set(value)
    try:
        yield value
    finally:
        _CORRELATION_ID.reset(token)
