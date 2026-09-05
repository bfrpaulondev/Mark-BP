# UI Runtime State (ANT-268)

Estado: implementado (slice inicial), sem validação física em Windows.

## Modelo central

`ui/runtime_state.py` — módulo puro (sem Qt, sem imports do runtime):

- `UiState` (StrEnum) — vocabulário operacional canónico:
  `IDLE, LISTENING, THINKING, OBSERVING, EXECUTING, VERIFYING, RECOVERING,
  WAITING_APPROVAL, COMPLETED, FAILED, CANCELLED`, mais `UNKNOWN` como estado
  conservador para valores inválidos/inesperados. Membros de compatibilidade
  legados mantidos: `INITIALISING, SPEAKING, SLEEPING, MUTED`.
- `STATE_LABELS_PT` — rótulo pt-PT único por estado (fonte única para o orb).
- `normalize_state(value)` — função total: aceita `UiState | str | None`,
  mapeia strings legadas (`PROCESSING → EXECUTING`, `READY/STANDBY → IDLE`,
  `ERROR → FAILED`, `ABORTED → CANCELLED`, `AWAITING_APPROVAL /
  PENDING_APPROVAL → WAITING_APPROVAL`) e devolve `UNKNOWN` em valores
  desconhecidos/vazios. Isto evita que um estado inesperado seja apresentado
  falsamente como `PRONTA`.
- `UiRuntimeState` — snapshot imutável com metadados técnicos (`task_id`,
  `task_name`, `progress` (0–100, clamp), `current_step`, `tool`, `provider`,
  `model`, `target_window`, `target_monitor`, `verified`, `error`,
  `approval`, `model_calls`, `calls_saved`, `estimated_cost`, `elapsed`).
  Nunca transporta segredos, texto privado ou clipboard.

## Binding na UI

- `AntonellaWindow._runtime_state_signal` (pyqtSignal(object), thread-safe)
  → `_apply_runtime_state(snapshot)`:
  - `ParticleOrb` — estado, velocidade/energia por estado (mesmo tick 33 ms,
    sem timers novos) e rótulo/cor via `STATE_LABELS_PT`
    (`VERIFYING` → azul, `WAITING_APPROVAL` → rosa, `COMPLETED` → verde,
    `FAILED` → vermelho).
  - `CORE STATUS` card — mostra `tarefa · passo` quando existem, senão
    `⟐ Sincronizado`.
- `AntonellaWindow._apply_state(str)` mantém-se como ponto de entrada legado:
  normaliza para o modelo em vez de propagar strings cruas.
- `JarvisUI.set_state(str)` (contrato antigo dos motores) continua a
  funcionar sem alterações nos motores; `JarvisUI.set_runtime_state(...)` é o
  novo caminho estruturado.
- `ui/runtime_dashboard.py` — chip Live trata `EXECUTING/VERIFYING/
  RECOVERING` como "A processar" (os estados chegam já normalizados).

## Migração futura (fora desta slice)

- ANT-269 Agent Control Center deve consumir `UiRuntimeState` (não inferir de
  logs); ANT-271 deve mapear `ExecutionResult → estado de voz/UI` num
  componente isolado sem alterar a semântica de `ExecutionResult`.
- Motores podem migrar incrementalmente de `set_state("STRING")` para
  `set_runtime_state(UiRuntimeState(...))`.

## Testes

`tests/test_ui_runtime_state.py` cobre normalização total + aliases legados,
estado `UNKNOWN` conservador, rótulos pt-PT completos, clamp de progresso,
imutabilidade/cópia, `to_dict` só com metadados técnicos e contratos de binding
(`_runtime_state_signal`, `_apply_runtime_state`, `set_runtime_state`, dashboard
normalizado).

Limitação: validação em Qt offscreen apenas; não validado em Windows físico
(DPI, multi-monitor) nem com o runtime Gemini Live activo.
