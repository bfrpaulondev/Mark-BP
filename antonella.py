from __future__ import annotations

import asyncio
import threading
from datetime import datetime

from config import get_config
from core.agent_orchestrator import AgentOrchestrator, AgentStage, OrchestrationEvent
from core.local_command_router import execute_local_intent, parse_local_text_command
from core.postcondition_verifiers import (
    capture_open_app_state,
    capture_postcondition_state,
    verify_open_app_postcondition,
    verify_postcondition,
)
from core.tool_verification_policy import requires_postcondition
from google.genai import types
from main import (
    TOOL_DECLARATIONS,
    AntonellaRuntime,
    _load_system_prompt,
    format_memory_for_prompt,
    load_memory,
)
from memory.bootstrap import create_memory_stack
from memory.command_bridge import MemoryCommandBridge
from ui import AntonellaUI
from ui.runtime_dashboard import attach_runtime_dashboard
from ui.voice_feedback import local_command_feedback


DEFAULT_VOICE = "Kore"

# Deterministic fast-path kinds that deserve a short spoken confirmation;
# informational kinds (help/status/list) stay log-only.
_SPOKEN_LOCAL_KINDS = frozenset(
    {"agent_stop", "agent_approve", "set_cost", "set_provider", "scroll", "open_app"}
)


class AntonellaLive(AntonellaRuntime):
    """Antonella identity/voice layer over the stabilized realtime engine."""

    # -.-.-.-
    def __init__(self, ui: AntonellaUI):
        super().__init__(ui)
        self._last_orchestration_event: OrchestrationEvent | None = None
        # R1/R2/R5: memory stack + natural command bridge + habit ladder.
        self.memory_stack = create_memory_stack()
        self.memory_bridge = MemoryCommandBridge(
            self.memory_stack.service,
            log=lambda text: self.ui.write_log(f"SYS: memória · {text}"),
        )
        self._agent_orchestrator = AgentOrchestrator(
            requires_postcondition=requires_postcondition,
            capture_postcondition_state=capture_postcondition_state,
            verify_postcondition=verify_postcondition,
            event_sink=self._on_orchestration_event,
        )

    # -.-.-.-
    def _on_orchestration_event(self, event: OrchestrationEvent) -> None:
        """Keep a lightweight provider-neutral lifecycle signal for UI/observability consumers."""
        self._last_orchestration_event = event
        if event.stage == AgentStage.FAILED:
            self.ui.write_log(
                f"SYS: agent · failed · {event.tool_name} · "
                f"{event.metadata.get('error_type', 'error')}"
            )

    # -.-.-.-
    def _build_config(self) -> types.LiveConnectConfig:
        config = get_config()
        self._asst_name = (config.get("assistant_name") or "Antonella").strip() or "Antonella"
        user_name = (config.get("user_name") or "").strip()
        voice_name = (config.get("voice_name") or DEFAULT_VOICE).strip() or DEFAULT_VOICE
        voice_style = (
            config.get("voice_style")
            or "feminine, warm, natural, calm, confident, concise and conversational"
        ).strip()

        memory = load_memory()
        memory_context = format_memory_for_prompt(memory)
        system_prompt = _load_system_prompt()
        now = datetime.now()
        time_context = (
            "[CURRENT DATE & TIME]\n"
            f"Right now it is: {now.strftime('%A, %B %d, %Y — %I:%M %p')}\n"
            "Use this to calculate exact times for reminders.\n"
        )

        address = (
            f"Address the user as '{user_name}' when natural."
            if user_name
            else "Address the user naturally in the language they are using."
        )
        identity_context = (
            "[ANTONELLA IDENTITY]\n"
            f"Your name is {self._asst_name}. Always refer to yourself as {self._asst_name}.\n"
            f"{address}\n"
            f"Voice delivery: {voice_style}. Avoid robotic cadence and unnecessary formality.\n"
            "Do not call yourself JARVIS, Mark, or any inherited project name.\n"
        )

        prompt_parts = [time_context, identity_context]
        if memory_context:
            prompt_parts.append(memory_context)
        prompt_parts.append(system_prompt)

        live_config: dict = {
            "response_modalities": ["AUDIO"],
            "output_audio_transcription": {},
            "input_audio_transcription": {},
            "system_instruction": "\n\n".join(prompt_parts),
            "tools": [
                {
                    "function_declarations": TOOL_DECLARATIONS
                    + self._plugin_registry.get_tool_declarations()
                }
            ],
            "session_resumption": types.SessionResumptionConfig(),
            "context_window_compression": types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow(),
            ),
            "speech_config": types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            ),
        }

        if self._enhanced_live:
            live_config["enable_affective_dialog"] = True
            live_config["proactivity"] = types.ProactivityConfig(proactive_audio=True)

        return types.LiveConnectConfig(**live_config)

    # -.-.-.-
    def _on_text_command(self, text: str) -> None:
        """Memory commands first, then deterministic local actions."""
        memory_result = self.memory_bridge.handle(text)
        if memory_result is not None:
            user_text = str(text or "").strip()
            self.ui.write_log(f"You: {user_text}")
            self.ui.write_log(f"SYS: memória · {memory_result['intent']}")
            self._session_log.append(f"You: {user_text}")
            assistant_name = getattr(self, "_asst_name", "Antonella")
            self.ui.write_log(f"{assistant_name}: {memory_result['spoken']}")
            self._session_log.append(f"{assistant_name}: {memory_result['spoken']}")
            self.speak(memory_result["spoken"])
            return

        intent = parse_local_text_command(text)
        if intent is None:
            super()._on_text_command(text)
            return

        user_text = str(text or "").strip()
        assistant_name = (
            str(get_config().get("assistant_name") or "Antonella").strip() or "Antonella"
        )
        self.ui.write_log(f"You: {user_text}")
        self.ui.write_log(f"SYS: fast path local · {intent.kind}")
        self.ui.set_state("PROCESSING")
        self._session_log.append(f"User: {user_text}")

        def _execute() -> None:
            app_name = str(intent.args.get("app_name") or "").strip()
            before_state = (
                capture_open_app_state(app_name) if intent.kind == "open_app" else None
            )
            result = execute_local_intent(intent, player=self.ui)
            verification = None
            if intent.kind == "open_app" and not result.verified:
                verification = verify_open_app_postcondition(
                    app_name,
                    before_state=before_state,
                )
                self.ui.write_log(
                    "SYS: verify · fast-path open_app · "
                    f"delivered={verification.delivered} · "
                    f"verified={verification.verified}"
                )
                # Keep the verifier's canonical success gate explicit at the
                # fast-path boundary. Voice still comes from the shared
                # feedback mapper, so this guard cannot invent a success.
                if verification.can_claim_success:
                    self.ui.write_log("SYS: verify · fast-path open_app · confirmed")
            feedback = local_command_feedback(result, verification)
            self.ui.write_log(f"{assistant_name}: {feedback.phrase_pt}")
            self._session_log.append(f"{assistant_name}: {feedback.phrase_pt}")

            # One real execution produces one observation. The bridge also
            # de-duplicates accidental duplicate instrumentation defensively.
            suggestion = self.memory_bridge.observe(f"local.{intent.kind}")
            if suggestion:
                self.ui.write_log(f"SYS: {suggestion}")

            if intent.kind in _SPOKEN_LOCAL_KINDS:
                self.speak(feedback.phrase_pt)
            if not self.ui.muted:
                self.ui.set_state("LISTENING")

        threading.Thread(
            target=_execute,
            daemon=True,
            name=f"antonella-local-{intent.kind}",
        ).start()

    # -.-.-.-
    async def _execute_tool(self, fc) -> types.FunctionResponse:
        """Run the legacy tool through the provider-neutral orchestration lifecycle."""
        name = str(fc.name or "")
        args = dict(fc.args or {})

        async def _legacy_executor():
            return await super(AntonellaLive, self)._execute_tool(fc)

        outcome = await self._agent_orchestrator.run_tool(
            tool_name=name,
            args=args,
            executor=_legacy_executor,
        )

        execution = outcome.execution
        if execution is None:
            return outcome.raw_response

        action_suffix = str(args.get("action") or "").strip()
        action_name = f"{name}.{action_suffix}" if action_suffix else name
        self.ui.write_log(
            "SYS: verify · "
            f"{action_name} · delivered={execution.delivered} · "
            f"verified={execution.verified} · task={outcome.correlation_id}"
        )
        return types.FunctionResponse(
            id=fc.id,
            name=name,
            response=outcome.response_payload,
        )

    # -.-.-.-
    def speak_error(self, tool_name: str, error: str) -> None:
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Não consegui concluir {tool_name}. {short}")


# -.-.-.-
def main() -> None:
    ui = AntonellaUI()
    attach_runtime_dashboard(ui)

    def runner() -> None:
        ui.wait_for_api_key()
        antonella = AntonellaLive(ui)
        try:
            asyncio.run(antonella.run())
        except KeyboardInterrupt:
            print("\nAntonella stopped.")

    threading.Thread(target=runner, daemon=True, name="antonella-runtime").start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()
