from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderUsage:
    """Provider-neutral token usage returned by a completed model request.

    Counts are telemetry only. They never contain prompt, image or response content.
    A zero value means the provider did not report that field, not that the field is
    guaranteed to have been free.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0

    def __post_init__(self) -> None:
        for name in (
            "input_tokens",
            "output_tokens",
            "cached_input_tokens",
            "reasoning_tokens",
            "total_tokens",
        ):
            value = max(0, int(getattr(self, name) or 0))
            object.__setattr__(self, name, value)

        # Cached input is a subset of input for the providers we support. Clamp
        # defensive SDK/API inconsistencies instead of producing negative billable input.
        object.__setattr__(
            self,
            "cached_input_tokens",
            min(self.cached_input_tokens, self.input_tokens)
            if self.input_tokens
            else self.cached_input_tokens,
        )

    @property
    def has_usage(self) -> bool:
        return any(
            (
                self.input_tokens,
                self.output_tokens,
                self.cached_input_tokens,
                self.reasoning_tokens,
                self.total_tokens,
            )
        )

    def safe_metadata(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class ProviderResponse:
    """Content plus provider-reported usage.

    The response text deliberately stays outside telemetry snapshots. ProviderRouter
    consumes it and only forwards the usage counters to cost telemetry.
    """

    text: str
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    request_id: str = ""

    def __str__(self) -> str:
        return str(self.text or "")

    def safe_metadata(self) -> dict[str, Any]:
        return {
            "usage": self.usage.safe_metadata(),
            "has_request_id": bool(self.request_id),
        }
