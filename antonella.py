from __future__ import annotations

import asyncio
import threading
from datetime import datetime

from config import get_config
from google.genai import types
from main import (
    TOOL_DECLARATIONS,
    JarvisLive,
    _load_system_prompt,
    format_memory_for_prompt,
    load_memory,
)
from ui import JarvisUI
from ui.runtime_dashboard import attach_runtime_dashboard


DEFAULT_VOICE = "Kore"


class AntonellaLive(JarvisLive):
    """Antonella identity/voice layer over the stabilized legacy realtime engine."""

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
    def speak_error(self, tool_name: str, error: str) -> None:
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Não consegui concluir {tool_name}. {short}")


# -.-.-.-
def main() -> None:
    ui = JarvisUI()
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
