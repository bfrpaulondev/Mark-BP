# Voice Pipeline (A1 — auditoria da implementação real)

Estado: documentação do pipeline **como implementado** (main `2eeaf8c`).
Nenhuma arquitectura imaginária; referências aos pontos reais do código.

## Fluxo real

```text
microphone
→ capture (sounddevice InputStream, main.py _listen_audio)
→ VAD/end-of-turn (SERVER-SIDE: Gemini Live, sem VAD local)
→ STT (server-side: input_audio_transcription; main.py _receive_audio in_buf)
→ agent (modelo Gemini Live com TOOL_DECLARATIONS + plugins, antonella.py _build_config)
→ tools (main.py/AntonellaLive._execute_tool → AgentOrchestrator.run_tool
         → executor legado → verifier → ExecutionResult)
→ response (payload do FunctionResponse volta ao modelo)
→ TTS (NATIVA do modelo: response_modalities=["AUDIO"], sem TTS local no caminho vivo)
→ playback (main.py _play_audio ← audio_in_queue)
```

## Pontos-chave (ficheiro · mecanismo)

- **Captura**: `main.py::_listen_audio` — `sd.InputStream` 16 kHz mono int16;
  o callback só envia áudio quando `not _is_speaking and not ui.muted and not
  _phone_active` (mic fecha durante a fala do modelo).
- **VAD/end-of-turn**: do lado do servidor Gemini Live. Não existe VAD local;
  latências de end-of-turn não são controladas pelo cliente.
- **STT**: transcrição do áudio de entrada activada em
  `antonella.py::_build_config` (`input_audio_transcription`); usada para o
  contexto/log, não para routing local.
- **Fast path local** (`antonella.py::_on_text_command`): texto →
  `parse_local_text_command` → `execute_local_intent` → `LocalCommandResult`
  (core/local_command_router.py) — corre fora da sessão, sem turno LLM.
  O resultado ia apenas para o log (sem fala) — wiring de fala adicionado
  nesta slice (ver `voice-verification-ux.md` e `ui/voice_feedback.py`).
- **Ferramentas**: `AntonellaLive._execute_tool` corre sempre via
  `AgentOrchestrator.run_tool` (verificador + postconditions); o
  `ExecutionResult` é registado em log (`SYS: verify · …`) e o payload
  devolvido ao modelo — **o modelo é quem narra o resultado**, portanto a
  honestidade da fala no caminho de ferramentas depende do payload (que só
  afirma sucesso verificado) e não de texto scripted.
- **Fala iniciada pelo motor**: `main.py::speak(text)` envia um turno de
  texto à sessão (o modelo voa-o naturalmente); thread-safe via
  `run_coroutine_threadsafe`; no-op sem sessão. `plugin_say` é o canal para
  plugins durante tarefas.
- **Barge-in (actual)**: `main.py::interrupt()` drena `audio_in_queue`,
  limpa `_is_speaking` e `_turn_done_event` (Esc / botão ↓). **Não existe
  barge-in por voz automática** — o mic está fechado enquanto o modelo fala.
- **TTS local**: `core/tts.py` existe (Win32 SAPI/fallbacks) para caminhos
  não-Live; não é usado no caminho de voz principal.

## Métricas de latência (A5/A8)

Ainda não instrumentadas (`speech_end_detected_ms`, `transcription_*_ms`,
`first_audio_ms`, …). O end-of-turn ser server-side torna
`speech_end_detected_ms` não mensurável no cliente hoje; as restantes são
mensuráveis nos eventos de `_receive_audio` — follow-up que toca o motor
(requer coordenação com o Principal Agent).

## Limitações declaradas

- Barge-in por voz automática e fila TTS cancelável (A3/A4) exigem cirurgia
  no motor de áudio de `main.py` — fora desta slice, mantida compatível.
- `NOT PHYSICALLY BENCHMARKED`: nenhum valor de latência medido em hardware.
