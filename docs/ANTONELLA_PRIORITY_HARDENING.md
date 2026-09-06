# Antonella — Prioridades de Hardening

> Anexo operacional do `ANTONELLA_MASTER_ROADMAP.md`. Estado sincronizado com a `main` de 2026-09-06 depois da revisão/integracão dos lotes de Voice, Windows E2E, Memory, Skills, Tasks e Providers.

## Regra de qualidade

```text
quando consegue → prova que conseguiu
quando não consegue → sabe que não conseguiu
quando pode recuperar → recupera dentro de limites
quando não pode → informa claramente sem inventar sucesso
```

`CI verde` não é sinónimo de `hardware físico validado`, `provider real validado` ou `produção pronta`.

## P0 — confiabilidade da execução

- [x] **ANT-251 — Local Command Fast Path.** PR #24.
- [x] **ANT-252 — `ExecutionResult` canónico.** PR #24.
- [x] **ANT-253 — Verifier central.** PR #25.
- [x] **ANT-254 — apps/janelas verificáveis.** PR #27/#28.
- [x] **ANT-255 — mouse/teclado com postconditions.** PR #28.
- [x] **ANT-256 — browser real verificável.** PR #29–#32.
- [x] **ANT-257 — multi-monitor/DPI hardening.** PR #33; validação física continua em ANT-275.
- [x] **ANT-258 — UIA/files/settings verificados.** PR #34; validação física continua em ANT-275.

**Gate P0:** fechado no código. Efeitos não observáveis continuam `verified=false`; hardware real é gate separado.

## P1 — core de agente

- [x] **ANT-259 — `AgentOrchestrator`.** PR #35.
- [x] **ANT-260 — `ToolRouter` + `ExecutionEngine`.** PR #36.
- [x] **ANT-261 — Policy Engine.** PR #38.
- [x] **ANT-262 — aprovação humana action-bound.** PR #39; grants expiram, são one-use e não podem ser fabricados pelo modelo.
- [x] **ANT-263 — Provider Router base.** PR #41 OpenAI/Gemini; PR #71 adapters Anthropic/Groq; PR #77 integra routing text-only dos quatro providers.

### Limites de providers

- OpenAI/Gemini permanecem os providers já existentes no runtime especializado.
- Anthropic/Groq exigem chave + modelo explícito por role; sem modelo, não existe candidato.
- Anthropic/Groq não entram em `VISION` até existir suporte real no adapter.
- Pricing desconhecido continua desconhecido.
- HTTP real Anthropic/Groq: **NOT RUN**.

## P1 — custo, percepção e Computer Use

- [x] **ANT-264 — telemetria de custo/usage.** PR #43.
- [x] **ANT-265 — cache e percepção local/UIA-first.** PR #45.
- [x] **ANT-266 — cancelado como arquitectura ScreenConnect específica.** Capacidades úteis absorvidas no Computer Use genérico.
- [x] **ANT-267 — Computer Use Reliability & Recovery.** PR #48.

**Gate:** código integrado; interacção Windows/GUI física continua ANT-275.

## P1 — UI/UX, voz e identidade

- [x] **ANT-268 — estados operacionais explícitos.** PR #37.
- [x] **ANT-269 — Agent Control Center.** PR #42.
- [x] **ANT-270 — Windows UI hardening automático.** PR #44/#49/#54; DPI/render físico continuam ANT-275.
- [~] **ANT-271 — voz/verificação.** PR #55/#57/#66 integram fala honesta, turn tokens, stale-audio rejection, barge-in opt-in thread-safe, métricas por turno e benchmark real do ficheiro produzido pelo runtime.
  - [ ] barge-in/bleed/threshold físicos;
  - [ ] latência audível física;
  - [ ] true end-of-speech p95 com sinal fiável;
  - [ ] fast voice path completo sem double execution/supressão insegura do turno Live;
  - [ ] progresso falado bounded durante tarefas, sem spam.
- [~] **ANT-272 — identidade original Antonella.** PR #58 remove resíduos vivos; PR #63 remove `ui.py`; PR #64 torna `AntonellaUI`/`AntonellaRuntime` canónicos.
  - [ ] provar zero consumidores dos aliases de compatibilidade e removê-los;
  - [ ] auditar/remover `config/jarvis.ico` se continuar morto;
  - [ ] manter regressões contra JARVIS/J.A.R.V.I.S./Tony Stark/Iron Man/MARK LI em superfícies activas.

`[~]` significa código substancial integrado, mas definição final de concluído ainda não atingida.

## P1/P2 — CI, observabilidade e Windows físico

- [x] **ANT-273 — Windows CI.** PR #40, Python 3.11/3.12 + import smoke fail-closed.
- [x] **ANT-274 — structured logging crítico.** PR #53.
- [~] **ANT-275 — Windows E2E real.** PR #59 cria harness/matriz/evidence/fixtures; PR #67 integra executores físicos revistos.
  - [ ] execução formal com `ANTONELLA_E2E_PHYSICAL=1` no Windows do utilizador;
  - [ ] UIA/rato/teclado/files/settings;
  - [ ] browser/Playwright;
  - [ ] DPI 100/125/150% + multi-monitor;
  - [ ] hot-plug/reacquisition quando suportado;
  - [ ] voice/barge-in/bleed;
  - [ ] cenários físicos Computer Use que a matriz não pode provar em CI.

Sem gate físico, o runner nunca converte ausência de execução em PASS.

## P2 — Memory

- [~] **ANT-276 — Memory.** PR #60 core/lifecycle/migrations; PR #68 Supabase adapter; PR #73 comandos naturais; PR #78 runtime wiring autenticado/fail-closed.

Integrado:

- memória semântica/procedural e contratos extensíveis a episódios/projectos;
- estados `proposed → approved → active → superseded → archived`;
- proveniência/confiança/TTL/conflitos/supersession;
- owner/project scoping;
- adapter Supabase e conversão `timestamptz`;
- `Aprende que…`, `Aprende como…`, `Prefiro…`, `Corrige…`, `Esquece…`, `Mostra…`, `De onde…`;
- Supabase ausente → InMemory explicitamente session-only;
- Supabase configurado mas quebrado → `CONFIGURED BUT FAILED`, sem fallback silencioso;
- desktop recusa service-role/secret keys; owner vem de sessão autenticada validada.

Ainda aberto:

- [ ] executar/verificar migrations em projecto real;
- [ ] RLS real com duas sessões/owners;
- [ ] reconnect/expiry/cleanup real;
- [ ] UI/login/session flow apropriado em vez de depender apenas de env;
- [ ] ligar propostas/forget ao approval UX canónico para concluir a mutação;
- [ ] Brain Studio/API formal;
- [ ] embedding provider/dimensão e pgvector/retrieval híbrido reais.

Supabase/Postgres/RLS reais: **NOT RUN**.

## P2 — Skills

- [~] **ANT-277 — Skills aprendíveis/aprovadas.** PR #61 core; PR #70 runner; PR #72 quatro product skills DRAFT; PR #74 selection bounded/relevant-only.

Integrado:

- manifest/version/lifecycle/permissions;
- versões imutáveis + rollback;
- validação estática;
- subprocess runner com timeout/cancel e redacção de segredos;
- selection só ACTIVE + relevante + permissões disponíveis;
- `daily-report`, `meeting-copilot`, `meeting-action-items`, `workday-summary` em DRAFT.

Ainda aberto:

- [ ] wiring end-to-end `intent → select → policy/approval → runner → ExecutionResult → verifier`;
- [ ] activação individual das product skills apenas após aprovação humana;
- [ ] resource limits/sandbox forte se necessário para skills não confiáveis;
- [ ] Skill Builder draft-only e learning UX completo;
- [ ] integração real Teams/audio/diarização para `meeting-copilot`.

O subprocess actual é isolamento **best-effort**, não sandbox forte.

## P2 — Persistent Tasks e proactividade

- [~] **ANT-278 — Persistent Tasks.** PR #62 core/runner/scheduler; PR #69 habit ladder/quiet hours/weekly/evidence; PR #78 observa execuções locais no runtime.

Integrado:

- pause/resume/cancel;
- checkpoint/reconciliation;
- approval canónico em passos sensíveis;
- delivery separado de verification;
- idempotency/replay conservador;
- schedules semanais e quiet hours;
- `observed_once → possible_habit → probable_habit → approved_routine` sem auto-aprovação por frequência.

Ainda aberto:

- [ ] experiência de produto completa para tasks persistentes;
- [ ] storage/cloud/scheduler final onde aplicável;
- [ ] approved routine execution com policies independentes;
- [ ] ligação de evidence à UI/Activity;
- [ ] proactividade final sem spam e respeitando quiet hours em todos os canais.

## Ordem imediata

1. **ANT-275 físico** — executar a matriz formal no Windows real.
2. **ANT-276 real** — validar Supabase/Auth/RLS e depois fechar approval UX/Brain Studio.
3. **ANT-277 runtime** — fechar wiring end-to-end e activar product skills uma a uma.
4. **ANT-278 produto** — fechar tasks/proactividade sobre os gates acima.
5. **ANT-272 final** — remover aliases/assets herdados mortos depois de provar zero consumidores.
6. **ANT-271 físico/performance** — calibrar barge-in e medir latências reais; fast voice path só se puder evitar double execution.
7. **MT5/Fimathe** — iniciar apenas depois destes gates, na sequência `observer → drawing → replay → backtest → demo-confirmed → live-confirmed`.

## Definição de concluído

Uma tarefa só recebe `[x]` quando código/documentação estão integrados, regressões relevantes estão cobertas e toda validação externa/física necessária foi realmente executada. `SKIPPED`, `NOT RUN`, `NOT AVAILABLE` e `NOT PHYSICALLY TESTED` nunca contam como PASS.
