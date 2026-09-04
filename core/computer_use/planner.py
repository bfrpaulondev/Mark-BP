from __future__ import annotations

import json
import re
from typing import Any, Mapping

from core.computer_use.batching import MAX_ACTIONS_PER_PLAN, sanitize_action_batch
from core.computer_use.contracts import ComputerAction, FrameSnapshot
from core.cost_router import ModelRoute, select_visual_route


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
    ):
        self._config = dict(config)
        self.route: ModelRoute = select_visual_route(
            self._config,
            cost_mode=cost_mode,
        )
        self.calls = 0

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

        if self.route.provider == "openai":
            raw = self._openai(prompt, frame)
        elif self.route.provider == "gemini":
            raw = self._gemini(prompt, frame)
        else:
            raise RuntimeError(f"Unsupported provider: {self.route.provider}")

        return _parse_actions(raw)

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

    def _openai(self, prompt: str, frame: FrameSnapshot) -> str:
        from core.providers.openai_responses import OpenAIResponsesClient

        client = OpenAIResponsesClient(
            str(self._config.get("openai_api_key") or "")
        )
        return client.analyze_image(
            model=self.route.model,
            prompt=prompt,
            image_bytes=frame.jpeg_bytes,
            mime_type="image/jpeg",
            detail=self.route.budget.image_detail,
            reasoning_effort=self.route.reasoning_effort,
        )

    def _gemini(self, prompt: str, frame: FrameSnapshot) -> str:
        from google import genai
        from google.genai import types as gtypes

        api_key = str(self._config.get("gemini_api_key") or "").strip()
        if not api_key:
            raise RuntimeError("Gemini API key is not configured.")

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=self.route.model,
            contents=[
                gtypes.Part.from_bytes(
                    data=frame.jpeg_bytes,
                    mime_type="image/jpeg",
                ),
                prompt,
            ],
        )
        return str(response.text or "").strip()


def _build_prompt(
    *,
    objective: str,
    frame: FrameSnapshot,
    history: list[str],
    step: int,
) -> str:
    recent_history = "\n".join(f"- {line}" for line in history[-8:]) or "- none"
    return f"""
You are Antonella's visual desktop planner.

OBJECTIVE:
{objective}

CURRENT FRAME:
- step: {step}
- image coordinates: 0..{max(0, frame.image_width - 1)} x 0..{max(0, frame.image_height - 1)}
- captured monitor: {frame.monitor_index}
- monitor change score: {frame.change_score:.4f}

RECENT ACTIONS:
{recent_history}

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
