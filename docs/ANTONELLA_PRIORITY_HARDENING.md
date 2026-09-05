# Antonella — Prioridades de Hardening 2026-09-05

> Anexo operacional do `ANTONELLA_MASTER_ROADMAP.md`. Estas tarefas não substituem o plano mestre: reordenam o trabalho imediato para elevar as áreas já funcionais a um nível pessoal robusto antes de ampliar o escopo.

## Regra de qualidade

O objectivo não é afirmar que uma função “nunca falha”. O contrato do produto é:

```text
quando consegue → prova que conseguiu
quando não consegue → sabe que não conseguiu
quando pode recuperar → recupera dentro de limites
quando não pode → informa claramente sem inventar sucesso
```

## P0 — confiabilidade das capacidades já entregues

- [x] **ANT-251 — Integrar Local Command Fast Path.** Executar comandos simples e inequívocos de baixo risco sem um novo turno LLM; multi-etapa deve continuar para o cérebro. Integrado em `main` por PR #24.
- [x] **ANT-252 — Criar `ExecutionResult` canónico.** Contrato machine-readable com `ok`, `delivered`, `verified`, `evidence`, `error`, `risk`, `requires_approval`, timestamps/correlation quando aplicável. Primeira versão integrada em `main` por PR #24.
- [x] **ANT-253 — Criar Verifier central.** Separar postconditions da implementação de cada tool e impedir que ausência de exception seja tratada como sucesso. Integrado em `main` por PR #25.
- [x] **ANT-254 — Verificar aplicações/janelas.** `open_app` e `focus_window` usam processo/janela/foreground real; `minimize`, `maximize` e `switch_window` passam a verificar estado Win32 antes/depois. PR #27 endureceu abertura/foreground e PR #28 fecha as window postconditions. E2E Windows físico continua na matriz ANT-275.
- [x] **ANT-255 — Verificar mouse e teclado.** `move/click/double/right/drag/scroll/hotkey/press/type/smart_type/paste/clear_field` recebem pre/post state e só ficam `verified=true` quando a postcondition disponível prova o efeito. Texto real de controlos permanece privado em memória e não é serializado em `ExecutionResult.evidence`. PR #28.
- [x] **ANT-256 — Consolidar browser real verificável.** PR #29 cobre janelas/tabs reais por UIA/Win32; PR #30 cobre efeitos DOM Playwright com postconditions; PR #31 acrescenta SPA/popups/downloads; PR #32 fecha a camada opcional CDP com loopback-only, porta explícita, sem scan/relaunch e `no_defaults=True` obrigatório antes de attach ao daily-driver. E2E Windows/Playwright físico permanece centralizado no ANT-275.
- [x] **ANT-257 — Hardening multi-monitor/DPI.** PR #33 integra Per-Monitor DPI Awareness V2, topologia física Win32/MSS, DPI/scale/primary, monitores negativos/acima, hot-plug, pinning de display explícito e stale-frame rejection. Ausência de topologia viva falha fechada. E2E físico continua no ANT-275.
- [x] **ANT-258 — Aplicar verificação a UIA, ficheiros e settings.** PR #34 fecha o escopo de código: UIA effect reads estruturados e ambiguity fail-closed; filesystem relê source/destination dentro dos mesmos safety roots e verifica conteúdo/estado sem expor paths/conteúdo; settings Windows observáveis são relidos após a acção. Acções sem postcondition observável permanecem explicitamente `verified=false`. E2E físico continua no ANT-275.

**Gate P0:** concluído no código. Nenhuma acção física/externa crítica das áreas cobertas é anunciada como concluída apenas porque a chamada não lançou exception. O gate de hardware/Windows real permanece separado no ANT-275.

## P1 — core de agente

- [x] **ANT-259 — Extrair `AgentOrchestrator`.** PR #35 integra o ciclo incremental de execução/observação/verificação preservando o runtime legado.
- [x] **ANT-260 — Extrair `ToolRouter` e `ExecutionEngine`.** PR #36 separa routing e execução sem big-bang rewrite do runtime.
- [x] **ANT-261 — Criar Policy Engine central.** PR #38 integra classificação determinística READ/WRITE/EXTERNAL/DESTRUCTIVE/FINANCIAL/PRIVILEGED/BLOCKED independente do LLM.
- [x] **ANT-262 — Aprovação humana vinculada à acção.** PR #39 integra grants de uso único, expiração e fingerprint da acção; flags do modelo não constituem autorização humana.
- [x] **ANT-263 — Provider Router completo.** PR #41 integra fronteira provider-neutral para specialist text/vision, roles, fallback, retry controlado e circuit breaker OpenAI↔Gemini. Claude/Groq continuam como expansão futura da interface.

**Gate P1:** o core central de orchestration/routing/policy/approval/provider está integrado. Wiring de todas as superfícies legadas continua a ser endurecido incrementalmente; não se assume que E2E físico esteja coberto.

## P1 — custo, percepção e Computer Use

- [x] **ANT-264 — Telemetria de custo por tarefa.** PR #43 integrada em `main`: usage provider-neutral, latência/retry/fallback, calls saved/cache hits, registry bounded/content-free e custo somente com pricing explícito configurado. Billing real do provider permanece fonte de verdade financeira.
- [x] **ANT-265 — Cache e percepção local.** PR #45 integrada em `main` após principal review e CI Linux/Windows 3.11/3.12: frame/keyframe cache bounded/content-free, exact-digest classification, UIA-first apenas para primeiro click explícito/único/baixo risco, telemetria de chamadas poupadas e `safety_context` transitório que não entra em histórico/telemetria. E2E físico continua no ANT-275.
- [x] **ANT-266 — Cancelado como arquitectura específica.** A antiga tarefa “ScreenConnect hardening” foi removida por decisão de produto: Antonella deve usar o mesmo Computer Use genérico para qualquer UI visual. As capacidades úteis (target locking/reacquisition, settle, recovery, pause/resume/cancel) foram absorvidas no ANT-267; não existe uma dependência ScreenConnect no core.
- [x] **ANT-267 — Computer Use Reliability & Recovery.** PR #48 integrada em `main`: recovery determinístico/bounded, target-window capture-scope fail-closed e reacquisition, stale-plan action-aware, adaptive settle, um único retry automático apenas para scroll, pause/resume/stop, revalidação pós-aprovação e bloqueio de auto-aprovação model-callable. Click/type/hotkey nunca são repetidos automaticamente. E2E físico continua no ANT-275.

## P1 — UI/UX e voz das áreas prontas

- [x] **ANT-268 — Estados operacionais explícitos na UI.** PR #37 integrada após principal review; estados desconhecidos permanecem conservadores em vez de aparecerem como PRONTA.
- [x] **ANT-269 — Evoluir Agent Control Center.** PR #42 integrada após principal review/correcções: progresso/timeline/evidência/janela alvo, custo ANT-264 e Stop/Approve contextuais sem inventar percentagens/custo.
- [x] **ANT-270 — Hardening UI Windows, escopo automático.** PR #44 integrou focus/accessibility, clamp multi-monitor e aprovação fail-closed; PR #49 integrou sizing exequível, histórico bounded, orb visibility-aware, empty/error states e visual regression offscreen; PR #54 integrou a fatia de Preferências com commit explícito onde Enter/Return não aplicam mesmo com o botão focado, mantendo Space/click. DPI/multi-monitor físico e benchmark real continuam no ANT-275 e não são confundidos com CI offscreen.
- [ ] **ANT-271 — Sincronizar voz com verificação.** A camada pura de feedback foi integrada pela PR #55 após principal review: só uma instância canónica de `ExecutionResult` pode produzir fala de sucesso; mappings arbitrários falham fechado. Continuam pendentes wiring no TTS vivo, barge-in real, cancelamento coerente da fila de fala, silêncio/end-of-turn e progresso falado conciso; áudio físico pertence ao ANT-275.
- [ ] **ANT-272 — Limpar identidade herdada.** PR #51 integrou a limpeza segura das superfícies vivas relevantes e mascara o token exacto legado `MARK LI` sem corromper nomes pessoais “Mark”. O módulo monolítico legado `ui.py` continua fora do runtime actual e ainda contém referências internas/visíveis antigas; não se considera esta tarefa totalmente concluída até esse legado ser removido/migrado ou provado definitivamente inacessível.

## P1/P2 — testes e observabilidade

- [x] **ANT-273 — Windows CI, primeira fatia.** PR #40 integrada após principal review: Windows Python 3.11/3.12, compile/unit/import-smoke fail-closed e paridade essencial com Ubuntu. Ruff/typecheck/coverage/audits continuam como follow-ups; isto não substitui ANT-275 físico.
- [x] **ANT-274 — Structured logging do caminho crítico.** PR #53 integrada após principal review e CI final: schema JSON bounded/estrito, correlation/task ID, tool/stage, provider/model, latência/custo/tokens, `verified`/delivery, erro por classe/tipo sem mensagem/traceback, retry/fallback, recovery reason codes e redaction content-minimised. Orchestrator, CostTelemetry/provider attempts e Computer Use recovery estão ligados; prints legados restantes não são tratados como concluídos por associação.
- [ ] **ANT-275 — Matriz E2E Windows real.** Voz, browser real, UIA, Computer Use, multi-monitor/DPI e cenários visuais desconhecidos; distinguir sempre unit/integration/CI de E2E físico. A primeira fatia de harness/fixture está em desenvolvimento separado e ainda não substitui execução no hardware real.

## P2 — inteligência persistente depois do core confiável

- [ ] **ANT-276 — Supabase Memory.** Episódica/semântica/procedural/project, proveniência, confiança, TTL/forgetting, embeddings/pgvector e retrieval híbrido.
- [ ] **ANT-277 — Skills aprendíveis e aprovadas.** `SKILL.md`, manifest, Python, tests, permissões e lifecycle draft→validate→approve→active.
- [ ] **ANT-278 — Persistent Tasks antes de MT5.** Pause/resume/cancel, idempotência, scheduling/proactividade limitada; MT5/Fimathe continua subordinado ao core, risk engine, kill switch e confirmação humana.

## Ordem imediata de execução

1. ANT-251–263 — execução verificável + core de agente integrados;
2. ANT-264–267 — custo + percepção + Computer Use reliability genérico;
3. ANT-268–272 — UI/voz/identidade com principal review; ANT-270 fechado no escopo automático, ANT-271/272 ainda têm follow-ups explícitos;
4. ANT-273–275 — CI/observabilidade/E2E, com ANT-273 e ANT-274 integrados e ANT-275 físico ainda aberto;
5. ANT-276–278 — memória/skills/tasks persistentes;
6. retomar a sequência MT5/Fimathe do plano mestre quando os gates anteriores estiverem verdes.

## Definição de concluído deste anexo

Uma tarefa só pode ser marcada concluída quando código/documentação final estiverem integrados, testes relevantes estiverem verdes, regressões conhecidas estiverem cobertas e limitações de Windows/hardware/providers estiverem explicitamente separadas de validações automáticas. Para acções físicas/externas, a evidência de execução deve ser compatível com o risco e com a capacidade técnica de observação.
