from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from core.providers.gemini_generate import GeminiGenerateClient
from core.providers.openai_responses import OpenAIResponsesClient


class ProviderName(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"


class ProviderCapability(str, Enum):
    TEXT = "text"
    VISION = "vision"


class ProviderRole(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    EXPERT = "expert"
    CRITIC = "critic"
    VISION = "vision"


class ProviderAdapter(Protocol):
    def generate_text(
        self,
        *,
        model: str,
        prompt: str,
        reasoning_effort: str = "low",
    ) -> str: ...

    def analyze_image(
        self,
        *,
        model: str,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        detail: str = "low",
        reasoning_effort: str = "low",
    ) -> str: ...


@dataclass(frozen=True)
class ProviderCandidate:
    provider: ProviderName
    model: str
    role: ProviderRole
    reasoning_effort: str
    max_output_chars: int
    reason: str


@dataclass(frozen=True)
class ProviderAttempt:
    provider: str
    model: str
    attempt: int
    latency_ms: int
    ok: bool
    retryable: bool = False
    error_type: str = ""
    error_class: str = ""

    def safe_metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "attempt": self.attempt,
            "latency_ms": self.latency_ms,
            "ok": self.ok,
            "retryable": self.retryable,
            "error_type": self.error_type,
            "error_class": self.error_class,
        }


@dataclass(frozen=True)
class ProviderResult:
    text: str
    provider: str
    model: str
    role: str
    capability: str
    attempts: tuple[ProviderAttempt, ...] = field(default_factory=tuple)
    fallback_count: int = 0

    @property
    def used_fallback(self) -> bool:
        return self.fallback_count > 0

    def safe_metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "role": self.role,
            "capability": self.capability,
            "fallback_count": self.fallback_count,
            "attempts": [item.safe_metadata() for item in self.attempts],
        }


@dataclass
class _ProviderHealth:
    consecutive_failures: int = 0
    open_until: float = 0.0
    last_error_class: str = ""


class ProviderExhaustedError(RuntimeError):
    """All eligible providers failed, without echoing prompt/image/credentials."""

    def __init__(
        self,
        attempts: tuple[ProviderAttempt, ...],
        *,
        eligible_providers: tuple[str, ...] = (),
    ):
        self.attempts = attempts
        self.eligible_providers = eligible_providers
        providers = eligible_providers or tuple(
            dict.fromkeys(item.provider for item in attempts)
        )
        provider_text = ", ".join(providers) or "none configured"
        super().__init__(
            "No configured AI provider completed the request. "
            f"Eligible providers: {provider_text}."
        )


class ProviderRouter:
    """Provider-neutral specialist text/vision router.

    Gemini Live continues to own realtime speech. This router handles bounded
    specialist text/vision calls with deterministic role selection, retry for
    transient provider failures, cross-provider fallback and an in-memory
    circuit breaker. It never stores raw prompts, images or credentials in
    health/telemetry metadata.
    """

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        adapters: Mapping[str | ProviderName, ProviderAdapter] | None = None,
        max_attempts_per_provider: int = 2,
        breaker_threshold: int = 2,
        breaker_cooldown_seconds: float = 30.0,
        clock=time.monotonic,
        sleeper=time.sleep,
    ) -> None:
        self._config = dict(config or {})
        self._max_attempts = max(1, min(3, int(max_attempts_per_provider)))
        self._breaker_threshold = max(1, min(10, int(breaker_threshold)))
        self._breaker_cooldown = max(
            1.0,
            min(600.0, float(breaker_cooldown_seconds)),
        )
        self._clock = clock
        self._sleeper = sleeper
        self._lock = threading.RLock()
        self._health: dict[ProviderName, _ProviderHealth] = {
            ProviderName.OPENAI: _ProviderHealth(),
            ProviderName.GEMINI: _ProviderHealth(),
        }

        if adapters is None:
            self._adapters = self._build_default_adapters()
        else:
            normalized: dict[ProviderName, ProviderAdapter] = {}
            for key, adapter in adapters.items():
                try:
                    provider = (
                        key
                        if isinstance(key, ProviderName)
                        else ProviderName(str(key).strip().lower())
                    )
                except ValueError:
                    continue
                normalized[provider] = adapter
            self._adapters = normalized

    # -.-.-.-
    def _build_default_adapters(self) -> dict[ProviderName, ProviderAdapter]:
        adapters: dict[ProviderName, ProviderAdapter] = {}
        openai_key = str(self._config.get("openai_api_key") or "").strip()
        gemini_key = str(self._config.get("gemini_api_key") or "").strip()
        if openai_key:
            adapters[ProviderName.OPENAI] = OpenAIResponsesClient(openai_key)
        if gemini_key:
            adapters[ProviderName.GEMINI] = GeminiGenerateClient(gemini_key)
        return adapters

    # -.-.-.-
    def candidate_plan(
        self,
        *,
        role: str | ProviderRole | None = None,
        capability: str | ProviderCapability = ProviderCapability.TEXT,
        preference: str | None = None,
    ) -> tuple[ProviderCandidate, ...]:
        selected_role = self._normalize_role(role)
        selected_capability = self._normalize_capability(capability)
        preferred = str(
            preference
            if preference is not None
            else self._config.get("model_provider_preference") or "auto"
        ).strip().lower()
        if preferred not in {"auto", "openai", "gemini"}:
            preferred = "auto"

        # An explicit setting means "prefer", not "lock"; the existing UI uses
        # that wording. Fallback therefore remains available when both providers
        # are configured.
        if preferred == "openai":
            order = (ProviderName.OPENAI, ProviderName.GEMINI)
        elif preferred == "gemini":
            order = (ProviderName.GEMINI, ProviderName.OPENAI)
        elif selected_role == ProviderRole.FAST:
            order = (ProviderName.GEMINI, ProviderName.OPENAI)
        else:
            order = (ProviderName.OPENAI, ProviderName.GEMINI)

        return tuple(
            self._candidate_for(
                provider=provider,
                role=selected_role,
                capability=selected_capability,
            )
            for provider in order
            if provider in self._adapters
        )

    # -.-.-.-
    def generate_text(
        self,
        *,
        prompt: str,
        role: str | ProviderRole | None = None,
        preference: str | None = None,
    ) -> ProviderResult:
        prompt = str(prompt or "").strip()
        if not prompt:
            raise ValueError("Provider text request requires a prompt.")
        return self._execute(
            capability=ProviderCapability.TEXT,
            role=self._normalize_role(role),
            preference=preference,
            prompt=prompt,
            image_bytes=None,
            mime_type="",
            detail="low",
        )

    # -.-.-.-
    def analyze_image(
        self,
        *,
        prompt: str,
        image_bytes: bytes,
        role: str | ProviderRole | None = ProviderRole.VISION,
        preference: str | None = None,
        mime_type: str = "image/jpeg",
        detail: str = "low",
    ) -> ProviderResult:
        prompt = str(prompt or "").strip()
        image = bytes(image_bytes or b"")
        if not prompt:
            raise ValueError("Provider vision request requires a prompt.")
        if not image:
            raise ValueError("Provider vision request requires image bytes.")
        return self._execute(
            capability=ProviderCapability.VISION,
            role=self._normalize_role(role or ProviderRole.VISION),
            preference=preference,
            prompt=prompt,
            image_bytes=image,
            mime_type=str(mime_type or "image/jpeg"),
            detail=str(detail or "low"),
        )

    # -.-.-.-
    def _execute(
        self,
        *,
        capability: ProviderCapability,
        role: ProviderRole,
        preference: str | None,
        prompt: str,
        image_bytes: bytes | None,
        mime_type: str,
        detail: str,
    ) -> ProviderResult:
        candidates = self.candidate_plan(
            role=role,
            capability=capability,
            preference=preference,
        )
        eligible = tuple(item.provider.value for item in candidates)
        if not candidates:
            raise ProviderExhaustedError((), eligible_providers=eligible)

        attempts: list[ProviderAttempt] = []
        for candidate_index, candidate in enumerate(candidates):
            if not self._provider_available(candidate.provider):
                continue

            adapter = self._adapters[candidate.provider]
            for attempt_number in range(1, self._max_attempts + 1):
                started = self._clock()
                try:
                    if capability == ProviderCapability.VISION:
                        if image_bytes is None:
                            raise ValueError("Vision request requires image bytes.")
                        raw_text = adapter.analyze_image(
                            model=candidate.model,
                            prompt=prompt,
                            image_bytes=image_bytes,
                            mime_type=mime_type,
                            detail=detail,
                            reasoning_effort=candidate.reasoning_effort,
                        )
                    else:
                        raw_text = adapter.generate_text(
                            model=candidate.model,
                            prompt=prompt,
                            reasoning_effort=candidate.reasoning_effort,
                        )

                    bounded = str(raw_text or "").strip()[: candidate.max_output_chars]
                    if not bounded:
                        raise RuntimeError("Provider response contained no usable text.")

                    latency = max(0, round((self._clock() - started) * 1000))
                    attempts.append(
                        ProviderAttempt(
                            provider=candidate.provider.value,
                            model=candidate.model,
                            attempt=attempt_number,
                            latency_ms=latency,
                            ok=True,
                        )
                    )
                    self._record_success(candidate.provider)
                    return ProviderResult(
                        text=bounded,
                        provider=candidate.provider.value,
                        model=candidate.model,
                        role=role.value,
                        capability=capability.value,
                        attempts=tuple(attempts),
                        fallback_count=candidate_index,
                    )
                except Exception as exc:
                    latency = max(0, round((self._clock() - started) * 1000))
                    error_class, retryable, trips_breaker = self._classify_error(exc)
                    attempts.append(
                        ProviderAttempt(
                            provider=candidate.provider.value,
                            model=candidate.model,
                            attempt=attempt_number,
                            latency_ms=latency,
                            ok=False,
                            retryable=retryable,
                            error_type=type(exc).__name__,
                            error_class=error_class,
                        )
                    )
                    if trips_breaker:
                        self._record_failure(candidate.provider, error_class)

                    if not retryable or attempt_number >= self._max_attempts:
                        break
                    self._sleeper(
                        min(0.75, 0.15 * (2 ** (attempt_number - 1)))
                    )

        raise ProviderExhaustedError(
            tuple(attempts),
            eligible_providers=eligible,
        )

    # -.-.-.-
    def health_snapshot(self) -> dict[str, dict[str, Any]]:
        now = self._clock()
        with self._lock:
            output: dict[str, dict[str, Any]] = {}
            for provider, health in self._health.items():
                output[provider.value] = {
                    "configured": provider in self._adapters,
                    "circuit_open": health.open_until > now,
                    "retry_after_seconds": max(
                        0,
                        round(health.open_until - now, 3),
                    ),
                    "consecutive_failures": health.consecutive_failures,
                    "last_error_class": health.last_error_class,
                }
            return output

    # -.-.-.-
    def reset_provider(self, provider: str | ProviderName) -> None:
        selected = (
            provider
            if isinstance(provider, ProviderName)
            else ProviderName(str(provider).strip().lower())
        )
        with self._lock:
            self._health[selected] = _ProviderHealth()

    # -.-.-.-
    def _provider_available(self, provider: ProviderName) -> bool:
        now = self._clock()
        with self._lock:
            health = self._health[provider]
            if health.open_until <= now:
                if health.open_until:
                    health.open_until = 0.0
                    health.consecutive_failures = 0
                return True
            return False

    # -.-.-.-
    def _record_success(self, provider: ProviderName) -> None:
        with self._lock:
            self._health[provider] = _ProviderHealth()

    # -.-.-.-
    def _record_failure(self, provider: ProviderName, error_class: str) -> None:
        now = self._clock()
        with self._lock:
            health = self._health[provider]
            health.consecutive_failures += 1
            health.last_error_class = error_class
            if health.consecutive_failures >= self._breaker_threshold:
                health.open_until = now + self._breaker_cooldown

    # -.-.-.-
    def _candidate_for(
        self,
        *,
        provider: ProviderName,
        role: ProviderRole,
        capability: ProviderCapability,
    ) -> ProviderCandidate:
        if provider == ProviderName.OPENAI:
            model_by_role = {
                ProviderRole.FAST: str(
                    self._config.get("openai_model_fast") or "gpt-5.6-luna"
                ).strip(),
                ProviderRole.BALANCED: str(
                    self._config.get("openai_model_balanced") or "gpt-5.6-terra"
                ).strip(),
                ProviderRole.EXPERT: str(
                    self._config.get("openai_model_expert") or "gpt-5.6-sol"
                ).strip(),
                ProviderRole.CRITIC: str(
                    self._config.get("openai_model_balanced") or "gpt-5.6-terra"
                ).strip(),
                ProviderRole.VISION: str(
                    self._config.get("openai_model_fast") or "gpt-5.6-luna"
                ).strip(),
            }
            effort_by_role = {
                ProviderRole.FAST: "low",
                ProviderRole.BALANCED: "low",
                ProviderRole.EXPERT: "medium",
                ProviderRole.CRITIC: "medium",
                ProviderRole.VISION: "low",
            }
        else:
            model_by_role = {
                ProviderRole.FAST: str(
                    self._config.get("gemini_model_fast")
                    or "gemini-flash-lite-latest"
                ).strip(),
                ProviderRole.BALANCED: str(
                    self._config.get("gemini_model_balanced")
                    or "gemini-flash-latest"
                ).strip(),
                ProviderRole.EXPERT: str(
                    self._config.get("gemini_model_expert")
                    or "gemini-flash-latest"
                ).strip(),
                ProviderRole.CRITIC: str(
                    self._config.get("gemini_model_critic")
                    or "gemini-flash-latest"
                ).strip(),
                ProviderRole.VISION: str(
                    self._config.get("gemini_model_vision")
                    or "gemini-flash-latest"
                ).strip(),
            }
            effort_by_role = {item: "low" for item in ProviderRole}

        max_output_by_role = {
            ProviderRole.FAST: 4_000,
            ProviderRole.BALANCED: 8_000,
            ProviderRole.EXPERT: 12_000,
            ProviderRole.CRITIC: 8_000,
            ProviderRole.VISION: 8_000,
        }
        return ProviderCandidate(
            provider=provider,
            model=model_by_role[role],
            role=role,
            reasoning_effort=effort_by_role[role],
            max_output_chars=max_output_by_role[role],
            reason=f"{provider.value} candidate for {role.value}/{capability.value}.",
        )

    # -.-.-.-
    @staticmethod
    def _normalize_role(value: str | ProviderRole | None) -> ProviderRole:
        if isinstance(value, ProviderRole):
            return value
        normalized = str(value or ProviderRole.BALANCED.value).strip().lower()
        try:
            return ProviderRole(normalized)
        except ValueError:
            return ProviderRole.BALANCED

    # -.-.-.-
    @staticmethod
    def _normalize_capability(
        value: str | ProviderCapability,
    ) -> ProviderCapability:
        if isinstance(value, ProviderCapability):
            return value
        try:
            return ProviderCapability(str(value or "text").strip().lower())
        except ValueError:
            return ProviderCapability.TEXT

    # -.-.-.-
    @staticmethod
    def _classify_error(exc: Exception) -> tuple[str, bool, bool]:
        text = str(exc or "").casefold()
        if "no usable text" in text or "no output text" in text:
            return "empty_response", True, False

        if isinstance(exc, (TimeoutError, ConnectionError)) or any(
            marker in text
            for marker in (
                "timeout",
                "timed out",
                "connection",
                "temporarily unavailable",
                "rate limit",
                "resource_exhausted",
                "429",
                "500",
                "502",
                "503",
                "504",
            )
        ):
            return "transient_provider", True, True

        if any(
            marker in text
            for marker in (
                "401",
                "403",
                "invalid api key",
                "authentication",
                "unauthorized",
            )
        ):
            return "provider_auth", False, True

        if any(
            marker in text
            for marker in (
                "400",
                "invalid argument",
                "bad request",
                "safety",
                "blocked",
            )
        ):
            return "request_rejected", False, False

        return "provider_error", False, False


_ROUTER_CACHE_LOCK = threading.RLock()
_ROUTER_CACHE: tuple[str, ProviderRouter] | None = None


# -.-.-.-
def _provider_config_signature(config: Mapping[str, Any]) -> str:
    """Internal config identity that detects key rotation without retaining raw keys."""
    relevant_names = (
        "model_provider_preference",
        "openai_model_fast",
        "openai_model_balanced",
        "openai_model_expert",
        "gemini_model_fast",
        "gemini_model_balanced",
        "gemini_model_expert",
        "gemini_model_critic",
        "gemini_model_vision",
    )
    payload = {
        name: str(config.get(name) or "")
        for name in relevant_names
    }
    for secret_name in ("openai_api_key", "gemini_api_key"):
        secret = str(config.get(secret_name) or "")
        payload[f"{secret_name}_digest"] = (
            hashlib.sha256(secret.encode("utf-8")).hexdigest() if secret else ""
        )
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# -.-.-.-
def get_provider_router(config: Mapping[str, Any]) -> ProviderRouter:
    """Return a process-local router so circuit health survives individual tool calls."""
    global _ROUTER_CACHE
    signature = _provider_config_signature(config)
    with _ROUTER_CACHE_LOCK:
        if _ROUTER_CACHE is not None and _ROUTER_CACHE[0] == signature:
            return _ROUTER_CACHE[1]
        router = ProviderRouter(config)
        _ROUTER_CACHE = (signature, router)
        return router


# -.-.-.-
def clear_provider_router_cache() -> None:
    """Test/runtime reset hook; no credential or prompt material is returned."""
    global _ROUTER_CACHE
    with _ROUTER_CACHE_LOCK:
        _ROUTER_CACHE = None
