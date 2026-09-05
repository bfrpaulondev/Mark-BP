from __future__ import annotations

import json
import re
from typing import Any, Mapping

from core.computer_use.batching import MAX_ACTIONS_PER_PLAN, sanitize_action_batch
from core.computer_use.contracts import ComputerAction, FrameSnapshot
from core.cost_router import ModelRoute, normalize_cost_mode, select_visual_route
from core.cost_telemetry import get_cost_telemetry
from core.provider_router import ProviderExhaustedError, ProviderRole, ProviderRouter


_ALLOWED_ACTIONS = {
    "click",
    "double_click",
    "right_click",
    "move",
    "scroll",
    "type",
    "smart_type",
    "hotkey",
    "press",
    "wait",
    "done",
    "fail",
}


class ComputerUsePlanner:
    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        cost_mode: str = "economy",
        telemetry_task_id: str | None = None,
    ):
        self._config = dict(config)
        self._cost_mode = normalize_cost_mode(cost_mode)
        self.route: ModelRoute = select_visual_route(
            self._config,
            cost_mode=self._cost_mode,
        )
        # Computer Use keeps a session-local health state. One attempt per
        # provider is enough here because a fresh frame/replan is usually more
        # useful than repeatedly sending the same screenshot to one provider.
        self._provider_router = ProviderRouter(
            self._config,
            max_attempts_per_provider=1,
        )
        self._telemetry = get_cost_telemetry()
        self.telemetry_task_id = self._telemetry.start_task(
            telemetry_task_id,
            kind="computer_use",
        )
        self.calls = 0  # logical planning turns (compatibility + budget)
        self.provider_attempts = 0  # actual provider requests, including fallback
        self.fallbacks = 0
        self.last_provider = self.route.provider
        self.last_model = self.route.model
        self.last_fallback_count = 0

    def next_actions(
        self,
        *,
        objective: str,
        frame: FrameSnapshot,
        history: list[str],
        step: int,
    ) -> list[ComputerAction]:
        if self.calls >= self.route.budget.max_model_calls:
            return [
                ComputerAction(
                    action="fail",
                    description="Computer Use model-call budget exhausted.",
                    result=(
                        "Stopped because the configured Computer Use model-call budget "
                        "was exhausted."
                    ),
                )
            ]

        prompt = _build_prompt(
            objective=objective,
            frame=frame,
            history=history,
            step=step,
        )
        self.calls += 1

        try:
            result = self._provider_router.analyze_image(
                prompt=prompt,
                image_bytes=frame.jpeg_bytes,
                mime_type="image/jpeg",
                detail=self.route.budget.image_detail,
                role=_provider_role_for_cost_mode(self._cost_mode.value),
                # Preserve the existing cost-router decision as the primary
                # provider while still allowing the configured fallback.
                preference=self.route.provider,
                telemetry_task_id=self.telemetry_task_id,
            )
        except ProviderExhaustedError as exc:
            self.provider_attempts += len(exc.attempts)
            self.last_fallback_count = 0
            return [
                _fail_action(
                    "Visual planner providers were unavailable or rejected the request."
                )
            ]

        self.provider_attempts += len(result.attempts)
        self.fallbacks += result.fallback_count
        self.last_fallback_count = result.fallback_count
        self.last_provider = result.provider
        self.last_model = result.model
        return _parse_actions(result.text)

    def next_action(
        self,
        *,
        objective: str,
        frame: FrameSnapshot,
        history: list[str],
        step: int,
    ) -> ComputerAction:
        """Compatibility helper for callers that still expect one action."""
        return self.next_actions(
            objective=objective,
            frame=frame,
            history=history,
            step=step,
        )[0]

    def record_saved_model_call(self, *, count: int = 1) -> None:
        self._telemetry.record_saved_call(
            self.telemetry_task_id,
            category="computer_use_batch",
            count=count,
        )

    def telemetry_snapshot(self) -> dict[str, Any] | None:
        return self._telemetry.snapshot(self.telemetry_task_id)

    def finish_telemetry(self) -> dict[str, Any] | None:
        return self._telemetry.finish_task(self.telemetry_task_id)


def _provider_role_for_cost_mode(cost_mode: str) -> ProviderRole:
    normalized = str(cost_mode or "economy").strip().lower()
    if normalized == "quality":
        return ProviderRole.EXPERT
    if normalized == "balanced":
        return ProviderRole.BALANCED
    return ProviderRole.FAST


def _build_prompt(
    *,
    objective: str,
    frame: FrameSnapshot,
    history: list[str],
    step: int,
) -> str:
    recent_history = "\n".join(f"- {line}" for line in history[-8:]) or "- none"
    savings_pct = int(round(frame.pixel_savings * 100))
    return f"""
You are Antonella's visual desktop planner.

OBJECTIVE:
{objective}

CURRENT FRAME:
- step: {step}
- image coordinates: 0..{max(0, frame.image_width - 1)} x 0..{max(0, frame.image_height - 1)}
- captured monitor: {frame.monitor_index}
- capture scope: {frame.capture_scope}
- source pixel reduction versus full monitor: {savings_pct}%
- screen change score: {frame.change_score:.4f}

RECENT ACTIONS:
{recent_history}

If capture scope is "window", the image is intentionally cropped to the target application's
visible window. Treat the image edges as that window's current boundaries. Do not infer content
outside the crop. Coordinates are still mapped correctly to the real virtual desktop by the
local actuator.

Return the smallest safe plan that moves toward the objective. Normally return ONE action.
You MAY return up to {MAX_ACTIONS_PER_PLAN} actions only when later actions are deterministic
and do not require visual reasoning between them. This is a cost optimisation, not permission
to guess.

Safe micro-batch examples:
- click a clearly visible stable text field, then type into that focused field;
- Ctrl+A in an already focused field, then type replacement text;
- Tab to the next known field, then type.

For the action immediately before a safe deterministic continuation, set reobserve=false.
Otherwise reobserve MUST be true. If unsure, return one action with reobserve=true.
Never use reobserve=false after scroll, double/right click, wait, Enter/Return, a medium/high
risk action, or when the next action depends on controls moving or appearing.

Prefer the minimum-cost, minimum-risk action. Do not repeat the same click when the previous
action produced no useful change. When scrolling, use a modest amount and reassess. If the
objective is already complete, return done. If you cannot continue safely, return fail.

Allowed actions:
- click, double_click, right_click, move
- scroll
- type, smart_type
- hotkey, press
- wait
- done
- fail

Coordinates MUST be relative to the provided image, not global desktop coordinates.

For any action that could delete data, send/publish something, change permissions,
change security settings, perform a financial action, or commit an irreversible change,
set "risk" to "high". Do not batch consequential actions and do not assume approval.

Return ONLY a JSON object with this schema:
{{
  "actions": [
    {{
      "action": "click|double_click|right_click|move|scroll|type|smart_type|hotkey|press|wait|done|fail",
      "description": "short description of what you intend to do",
      "x": null,
      "y": null,
      "direction": "down",
      "amount": 3,
      "text": "",
      "keys": "",
      "key": "",
      "seconds": 0.8,
      "confidence": 0.0,
      "risk": "low|medium|high",
      "result": "",
      "reobserve": true
    }}
  ]
}}
""".strip()


def _fail_action(message: str) -> ComputerAction:
    return ComputerAction(
        action="fail",
        description=message,
        result=message,
    )


def _decode_payload(raw: str) -> Any | None:
    text = str(raw or "").strip()
    if not text:
        return None

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _parse_actions(raw: str) -> list[ComputerAction]:
    payload = _decode_payload(raw)
    if payload is None:
        return [_fail_action("Visual planner returned invalid or empty JSON.")]

    if isinstance(payload, dict) and "actions" in payload:
        items = payload.get("actions")
    elif isinstance(payload, dict):
        items = [payload]
    else:
        return [_fail_action("Visual planner response was not an object.")]

    if not isinstance(items, list) or not items:
        return [_fail_action("Visual planner returned no actions.")]

    actions: list[ComputerAction] = []
    for item in items[:MAX_ACTIONS_PER_PLAN]:
        if not isinstance(item, dict):
            return [_fail_action("Visual planner returned an invalid action entry.")]
        action = ComputerAction.from_mapping(item)
        if action.action not in _ALLOWED_ACTIONS:
            return [_fail_action(f"Unsupported planner action: {action.action}")]
        actions.append(action)

    safe = sanitize_action_batch(actions)
    return safe or [_fail_action("Visual planner returned no executable actions.")]


def _parse_action(raw: str) -> ComputerAction:
    """Backward-compatible single-action parser used by older tests/callers."""
    return _parse_actions(raw)[0]
