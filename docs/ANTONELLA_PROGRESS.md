# Antonella — Estado da execução

> Painel operacional do estado real da `main`. O plano mestre continua em `docs/ANTONELLA_MASTER_ROADMAP.md`; prioridades e gates estão em `docs/ANTONELLA_PRIORITY_HARDENING.md`.

**Última actualização:** 2026-09-06  
**Branch canónica:** `main`  
**Main consolidada antes desta PR de documentação:** `674c3ee6d1846fb938ec6e3f65280e359896f413`  
**Critério central:** quando consegue, prova; quando não consegue, sabe que não conseguiu e não inventa sucesso.

## ANT-275 em revisão — PR #86

Follow-up do review do Principal sobre `f4ec40e5df23853333a308514ceeab90f62b3e4f`, na branch `glm/ant-275-physical-fixes`, sem merge:

- Os quatro campos de barge-in pertencem a `AntonellaSettings` e são materializados por `load_config()`. Defaults desktop: `True / 900 / 3 / 2.0`; precedência canónica `env > config legado > defaults`. Valores inválidos são rejeitados pela validação tipada.
- O runtime chama `get_config()` uma vez. `BargeInSettings` apenas transporta os valores já resolvidos; não lê ambiente nem fornece defaults alternativos.
- O teste de arranque restaura os shims de `sys.modules` em `finally`, preserva entradas existentes e falha nos jobs Qt se o runtime não importar. Há regressões para sucesso, falha de importação e dependência transitiva ausente.
- Os jobs Qt instalam também `numpy`, `playwright` e `psutil`, já usados pelo runtime, para executar a construção real e a concorrência sem skips causados por imports em falta.
- As fixtures de arranque e layout usam uma chave sintética apenas durante a construção da janela, evitando diálogos interactivos durante os testes. Todas as assertions de UI são mantidas; os shims de anotações rejeitam qualquer tentativa de executar código do provider.
- O fallback pycaw usa o GUID em `Activate` e o tipo `IAudioEndpointVolume` em `QueryInterface`; o caminho moderno `EndpointVolume` continua prioritário.
- `Any` é importado explicitamente e retirado da whitelist. O audit é descrito como heurístico, com limitações de scope; o import de `get_config` ao nível do módulo e a construção real do runtime são os gates principais.
- Preservados: WindowSpecification, centro RECT pelas coordenadas, VOICE 4 dependente de barge-in PASS, wording do benchmark, agendamento thread-safe da interrupção, locks e invalidação de turnos stale.

Validação local Python 3.12: 805/805 testes PASS com Qt, sem skips; baseline com 805 testes, 771 PASS e 34 skips de dependências opcionais; compileall, import smoke, lockfile/export e 21 estados visuais offscreen PASS. A matriz CI Linux/Windows Python 3.11/3.12 + Qt deve correr no novo HEAD; os resultados e o run id final ficam na descrição do PR.

**NOT PHYSICALLY RE-TESTED**: este follow-up não altera o resultado da ronda física anterior. Barge-in, speaker bleed, falsos positivos, latência audível e acceptance interactiva continuam dependentes de nova ronda real no Windows.

## Resumo operacional

| Área | Estado |
|---|---|
| P0 execução verificável — ANT-251–258 | Integrado no código; validação física continua em ANT-275 |
| Agent core — ANT-259–263 | Integrado |
| Custo/percepção/Computer Use — ANT-264–267 | Integrado no código; físico pendente |
| UI — ANT-268–270 | Integrada no escopo automático; DPI/render físico pendente |
| Voz — ANT-271 | Código A1–A8 integrado; barge-in/bleed/latência audível físicos pendentes; fast voice path completo ainda não |
| Identidade — ANT-272 | Superfícies vivas limpas e `ui.py` removido; aliases/asset legado remanescentes ainda precisam de remoção final |
| Windows CI/observabilidade — ANT-273/274 | Integrados |
| Windows E2E — ANT-275 | Harness + executores físicos integrados; execução formal no hardware do utilizador pendente |
| Memory — ANT-276 | Core + lifecycle + Supabase adapter + runtime wiring integrados; Supabase/RLS reais e aprovação UI específica pendentes |
| Skills — ANT-277 | Core + registry + runner + selecção dinâmica + 4 product skills em DRAFT integrados; wiring end-to-end ao orchestrator/activação ainda pendente |
| Persistent Tasks — ANT-278 | Core + runner + scheduler + proactividade bounded integrados; experiência de produto completa ainda pendente |
| Anthropic/Groq | Adapters + ProviderRouter text-only integrados; HTTP real não executado |
| MT5/Fimathe | Ainda não iniciado; subordinado aos gates acima |

## Entregas integradas relevantes

### Execução verificável e agente

- PR #24: Local Fast Path + `ExecutionResult`.
- PR #25: Verifier central.
- PR #26–#34: apps/janelas, mouse/teclado, browser verificável, CDP seguro, multi-monitor/DPI e postconditions para UIA/files/settings.
- PR #35: `AgentOrchestrator`.
- PR #36: `ToolRouter` + `ExecutionEngine`.
- PR #38: Policy Engine central.
- PR #39: aprovação humana action-bound, expirada e one-use.
- PR #41: ProviderRouter OpenAI/Gemini.

### Custo, percepção e Computer Use

- PR #43: usage/custo bounded, sem pricing inventado.
- PR #45: percepção/cache local e UIA-first fail-closed.
- PR #48: recovery bounded, stale-plan rejection, target reacquisition, pause/resume/stop e revalidação pós-aprovação.

### UI, voz e identidade

- PR #37/#42/#44/#49/#54: estados operacionais, Agent Control Center, acessibilidade, sizing, visual regression e settings fail-closed.
- PR #55/#57: fala de sucesso vinculada a verificação e wiring de feedback no fast path.
- PR #58: resíduos vivos de identidade antiga removidos do runtime.
- PR #63: `ui.py` legado removido.
- PR #64: nomes canónicos `AntonellaUI` / `AntonellaRuntime`; aliases temporários continuam apenas por compatibilidade.
- PR #65: QSS e tab order corrigidos; DPI físico continua gate separado.
- PR #66: Voice A3–A8 integrado após principal review: turn tokens, barge-in opt-in thread-safe, stale-audio rejection, métricas por turno e benchmark que consome o ficheiro real do runtime. `last_user_audio` não é tratado como end-of-speech.

### Testes físicos

- PR #59: harness Windows E2E, capability probe, matriz, evidência sanitizada e fixtures.
- PR #67: executores físicos revistos pelo Principal e integrados. Sem gate físico nada é promovido a PASS. A execução formal continua pendente no Windows real.

### Memory / Skills / Tasks

- PR #60: Memory core, migrations e lifecycle com conflitos/supersession/owner isolation.
- PR #61: Skills core versionado e lifecycle seguro.
- PR #62: Persistent Tasks com checkpoint, approval canónico, reconciliation e verificação separada de delivery.
- PR #68: Supabase Memory adapter, timestamptz real e migration de metadata.
- PR #69: proactividade bounded, quiet hours, weekly schedule e evidence.
- PR #70: Skill runner em subprocess best-effort, com timeout/cancel/secrets redacted.
- PR #72: `daily-report`, `meeting-copilot`, `meeting-action-items`, `workday-summary` em DRAFT.
- PR #73: comandos naturais de memória.
- PR #74: selecção dinâmica bounded/relevant-only.
- PR #78: runtime Memory wiring revisto e integrado sobre a árvore que já contém Voice e Providers. Supabase configurado mas avariado falha fechado; configuração ausente usa InMemory explicitamente como memória apenas da sessão.

### Providers adicionais

- PR #71: adapters Anthropic/Groq text-only.
- PR #77: integração revista no ProviderRouter depois de #66. Modelos são explícitos por provider/role; auto/fallback/circuit/health/cache cobrem os quatro providers; Anthropic/Groq ficam excluídos de Vision até suporte real. Pricing não é inventado.

## Gates ainda abertos

### G1 — ANT-275: Windows físico

Executar formalmente no hardware real:

- UIA, mouse/teclado, filesystem e settings;
- browser real/Playwright;
- DPI 100/125/150% e multi-monitor;
- hot-plug/reacquisition onde suportado;
- áudio, barge-in e speaker bleed;
- métricas de voz físicas.

CI/offscreen não substitui este gate.

### G2 — Voz

- threshold físico de barge-in;
- distinguir bleed da própria Antonella de fala do utilizador;
- latência audível real;
- true end-of-speech continua `NOT MEASURED` sem sinal VAD/end-turn fiável;
- fast voice path completo continua pendente porque a supressão segura do turno Live em voo ainda não está resolvida.

### G3 — Supabase real

- aplicar/verificar migrations num projecto controlado;
- autenticação real de utilizador;
- RLS com duas sessões/owners;
- archive/read-back/cleanup;
- reconnect/session expiry;
- nenhuma service-role/secret key no desktop.

O validador existe, mas HTTP/Postgres/RLS reais continuam `NOT RUN`.

### G4 — Memory approval UX

Os comandos mutantes criam propostas ou identificam a acção e exigem aprovação; ainda falta ligar a conclusão dessa aprovação de memória à superfície canónica de aprovação/Brain Studio. Não marcar `Aprende...`/`Esquece...` como fluxo de produto completo até este wiring existir.

### G5 — Skills end-to-end

Core, runner e selection existem, mas falta fechar o caminho:

`intent → select → policy/approval → SkillRunner → ExecutionResult → verifier → evidence`.

As quatro product skills permanecem DRAFT até aprovação humana explícita.

### G6 — Identidade final

- remover aliases `JarvisUI`/compatibilidade equivalentes depois de provar zero consumidores;
- auditar/remover `config/jarvis.ico` se continuar sem consumidor;
- manter regressão que impede referências activas a JARVIS/Mark/Tony Stark/Iron Man.

## Próxima sequência

1. executar ANT-275 físico no Windows e produzir relatórios formais;
2. validar Supabase/RLS real separadamente;
3. fechar Memory approval UX + Brain Studio backend/API;
4. fechar Skills end-to-end e activar as product skills uma a uma após aprovação;
5. completar Persistent Tasks/proactividade na experiência de produto;
6. remover aliases/assets de identidade herdada que se provem mortos;
7. só então iniciar MT5/Fimathe em `observer → drawing → replay → backtest → demo-confirmed → live-confirmed`.

## Limites que não podem ser sobredeclarados

- HTTP real Anthropic/Groq: `NOT RUN`.
- Supabase/Postgres/RLS real: `NOT RUN`.
- barge-in/bleed/DPI/multi-monitor/latência audível físicos: `NOT PHYSICALLY TESTED` nesta árvore.
- subprocess de Skills é isolamento best-effort, não sandbox forte.
- product skills em DRAFT não significam integração Teams/relatório empresarial end-to-end.
- MT5/Fimathe ainda não está implementado.
