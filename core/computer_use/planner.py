from __future__ import annotations

import json
import re
from typing import Any, Mapping

from core.computer_use.contracts import ComputerAction, FrameSnapshot
from core.cost_router import ModelRoute, select_visual_route


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

    def next_action(
        self,
        *,
        objective: str,
        frame: FrameSnapshot,
        history: list[str],
        step: int,
    ) -> ComputerAction:
        if self.calls >= self.route.budget.max_model_calls:
            return ComputerAction(
                action="fail",
                description="Computer Use model-call budget exhausted.",
                result=(
                    "Stopped because the configured Computer Use model-call budget "
                    "was exhausted."
                ),
            )

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

        return _parse_action(raw)

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

Choose exactly ONE next action. Prefer the minimum-cost, minimum-risk action that moves
toward the objective. Do not repeat the same click when the previous action produced no
useful change. When scrolling, use a modest amount and reassess. If the objective is
already complete, return done. If you cannot continue safely, return fail.

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
set "risk" to "high". Do not assume approval.

Return ONLY a JSON object with this schema:
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
  "result": ""
}}
""".strip()


def _parse_action(raw: str) -> ComputerAction:
    text = str(raw or "").strip()
    if not text:
        return ComputerAction(
            action="fail",
            description="Visual planner returned no action.",
            result="Visual planner returned no action.",
        )

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return ComputerAction(
                action="fail",
                description="Visual planner returned invalid JSON.",
                result="Visual planner returned invalid JSON.",
            )
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return ComputerAction(
                action="fail",
                description="Visual planner returned invalid JSON.",
                result="Visual planner returned invalid JSON.",
            )

    if not isinstance(payload, dict):
        return ComputerAction(
            action="fail",
            description="Visual planner response was not an object.",
            result="Visual planner response was not an object.",
        )

    action = ComputerAction.from_mapping(payload)
    if action.action not in {
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
    }:
        return ComputerAction(
            action="fail",
            description=f"Unsupported planner action: {action.action}",
            result=f"Unsupported planner action: {action.action}",
        )
    return action
