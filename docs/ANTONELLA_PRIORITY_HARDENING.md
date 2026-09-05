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
- [ ] **ANT-254 — Verificar aplicações/janelas.** `open_app`, focus/minimize/maximize/switch devem confirmar processo/janela/foreground quando tecnicamente possível. PR #26 integrou a primeira slice; a branch `codex/ant-254-open-app-hardening` acrescenta pre-state/delta e remove o shell do launcher Windows.
- [ ] **ANT-255 — Verificar mouse e teclado.** Move/click/double/right/drag/scroll/hotkeys/type/paste com target/foreground/postcondition; `verified=false` quando efeito não puder ser provado.
- [ ] **ANT-256 — Consolidar browser real verificável.** Tabs por índice/título/URL, múltiplas janelas, popups/downloads e SPA; CDP/Playwright quando possível, UIA/Win32 como fallback e input verificável por último.
- [ ] **ANT-257 — Hardening multi-monitor/DPI.** Diferentes escalas DPI, monitor acima/abaixo/esquerda, mudança do principal, disconnect/reconnect, coordenadas relativas à janela e virtual desktop.
- [ ] **ANT-258 — Aplicar verificação a UIA, ficheiros e settings.** Respostas estruturadas e postconditions apropriadas a cada domínio.

**Gate P0:** nenhuma acção física/externa crítica das áreas já cobertas pode ser anunciada como concluída apenas porque a chamada não lançou exception.

## P1 — core de agente

- [ ] **ANT-259 — Extrair `AgentOrchestrator`.** Ciclo incremental `intent → route → policy → execute → observe → verify → recover → finish`, preservando compatibilidade com o runtime actual.
- [ ] **ANT-260 — Extrair `ToolRouter` e `ExecutionEngine`.** Direct/local → API/DOM/UIA → CV local → modelo barato → Vision/Computer Use.
- [ ] **ANT-261 — Criar Policy Engine central.** READ/WRITE/EXTERNAL/DESTRUCTIVE/FINANCIAL/PRIVILEGED/BLOCKED, independente do LLM.
- [ ] **ANT-262 — Aprovação humana vinculada à acção.** Uso único, expiração e identidade da acção; `confirmed=true` vindo do modelo não constitui autorização humana.
- [ ] **ANT-263 — Provider Router completo.** Interface provider-neutral, roles, fallback, retry controlado, circuit breaker, custo/latência/qualidade e critic.

**Gate P1:** nenhuma tool relevante ignora policy/orchestrator; provider pode ser trocado sem regra de negócio depender do SDK.

## P1 — custo, percepção e Computer Use

- [ ] **ANT-264 — Telemetria de custo por tarefa.** Chamadas, tokens quando disponíveis, custo estimado, latência, cache hit e chamadas poupadas.
- [ ] **ANT-265 — Cache e percepção local.** Frame/keyframe cache, OpenCV/UIA-first e chamadas VLM somente quando acrescentam semântica necessária.
- [ ] **ANT-266 — Hardening ScreenConnect.** Target-window locking/reacquisition, settle adaptativo, scroll verificável, recuperação, pause/resume/cancel e frames efémeros por default.
- [ ] **ANT-267 — Melhorar Computer Use recovery.** Replanning quando UI muda, state tracking, bounded retries e evidência de conclusão.

## P1 — UI/UX e voz das áreas prontas

- [ ] **ANT-268 — Estados operacionais explícitos na UI.** A OUVIR, A PENSAR, A OBSERVAR, A EXECUTAR, A AGUARDAR APROVAÇÃO, FALHOU, CONCLUÍDO.
- [ ] **ANT-269 — Evoluir Agent Control Center.** Progresso, timeline/evidência, provider/model/custo, janela/ecrã alvo, erro/recovery, Stop/Approve contextuais.
- [ ] **ANT-270 — Hardening UI Windows.** DPI/responsividade, keyboard accessibility, empty/error states, microtransições, visual regression e performance.
- [ ] **ANT-271 — Sincronizar voz com verificação.** Nunca falar sucesso antes do verifier; melhorar barge-in, cancelamento, silêncio/end-of-turn e progresso falado conciso.
- [ ] **ANT-272 — Limpar identidade herdada.** Remover gradualmente resíduos JARVIS/Mark visíveis ou internos onde não sejam necessários para compatibilidade.

## P1/P2 — testes e observabilidade

- [ ] **ANT-273 — Windows CI e gates de qualidade.** Windows runner quando viável, Ruff, typecheck, secret/dependency scan, coverage, browser/import/GUI-safe smoke e contract tests.
- [ ] **ANT-274 — Structured logging completo.** Correlation/task ID, tool, provider/model, latência, custo, `verified`, erro/recovery e redaction; reduzir `print()` legado progressivamente.
- [ ] **ANT-275 — Matriz E2E Windows real.** Voz, browser real, UIA, multi-monitor/DPI e ScreenConnect; distinguir sempre unit/integration/CI de E2E físico.

## P2 — inteligência persistente depois do core confiável

- [ ] **ANT-276 — Supabase Memory.** Episódica/semântica/procedural/project, proveniência, confiança, TTL/forgetting, embeddings/pgvector e retrieval híbrido.
- [ ] **ANT-277 — Skills aprendíveis e aprovadas.** `SKILL.md`, manifest, Python, tests, permissões e lifecycle draft→validate→approve→active.
- [ ] **ANT-278 — Persistent Tasks antes de MT5.** Pause/resume/cancel, idempotência, scheduling/proactividade limitada; MT5/Fimathe continua subordinado ao core, risk engine, kill switch e confirmação humana.

## Ordem imediata de execução

1. ANT-251 Local Fast Path;
2. ANT-252/253 ExecutionResult + Verifier;
3. ANT-254–258 postconditions das ferramentas prontas;
4. ANT-259–263 Orchestrator/ToolRouter/Policy/Provider Router;
5. ANT-264–267 custo + Computer Use/ScreenConnect;
6. ANT-268–272 UI/voz/identidade;
7. ANT-273–275 CI/observabilidade/E2E;
8. ANT-276–278 memória/skills/tasks persistentes;
9. retomar a sequência MT5/Fimathe do plano mestre quando os gates anteriores estiverem verdes.

## Definição de concluído deste anexo

Uma tarefa só pode ser marcada concluída quando código/documentação final estiverem integrados, testes relevantes estiverem verdes, regressões conhecidas estiverem cobertas e limitações de Windows/hardware/providers estiverem explicitamente separadas de validações automáticas. Para acções físicas/externas, a evidência de execução deve ser compatível com o risco e com a capacidade técnica de observação.
