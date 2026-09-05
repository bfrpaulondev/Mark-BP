from __future__ import annotations

import inspect
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from core.tool_router import ToolRoute


@dataclass(frozen=True)
class ExecutionDispatch:
    route: ToolRoute
    raw_response: Any
    duration_ms: int


class ExecutionEngine:
    """Dispatch an already-authorized route through the existing runtime executor."""

    # -.-.-.-
    async def execute(
        self,
        route: ToolRoute,
        executor: Callable[[], Any | Awaitable[Any]],
    ) -> ExecutionDispatch:
        started = time.monotonic()
        raw_response = executor()
        if inspect.isawaitable(raw_response):
            raw_response = await raw_response
        duration_ms = max(0, round((time.monotonic() - started) * 1000))
        return ExecutionDispatch(
            route=route,
            raw_response=raw_response,
            duration_ms=duration_ms,
        )
