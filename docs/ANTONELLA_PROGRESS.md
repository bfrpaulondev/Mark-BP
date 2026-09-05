# Antonella — Estado da execução

> Painel operacional. O plano mestre continua a ser a fonte do escopo completo. As melhorias prioritárias das áreas já funcionais estão detalhadas em `docs/ANTONELLA_PRIORITY_HARDENING.md`.

**Última atualização:** 2026-09-05
**Branch canónica:** `main`
**Main confirmado antes da PR #32:** `3186a1406f496a7004c8696805680c50b7e59a3e`

## Estado atual

| Campo | Estado |
|---|---|
| Tarefa ativa | ANT-256 — última slice CDP seguro; escopo de código fecha com PR #32 |
| Branch de implementação | `codex/ant-256-safe-cdp-bridge` |
| Pull request | PR #32 — safe optional CDP bridge |
| Issues abertas | Nenhuma necessária para este trabalho |
| Próximo teste real | Windows: browser Chromium já iniciado explicitamente com remote debugging local; status/list/switch CDP |
| Próximo bloco | ANT-257 — multi-monitor/DPI hardening |

## Prioridade aprovada em 2026-09-05

1. ANT-251 — Local Fast Path;
2. ANT-252/253 — `ExecutionResult` + Verifier central;
3. ANT-254–258 — postconditions reais das ferramentas prontas;
4. ANT-259–263 — AgentOrchestrator, ToolRouter/ExecutionEngine, Policy Engine, aprovação humana e Provider Router;
5. ANT-264–267 — custo/telemetria, percepção local, ScreenConnect e recovery;
6. ANT-268–272 — UI/UX, Agent Control Center, voz/verificação e identidade;
7. ANT-273–275 — Windows CI, observabilidade e E2E real;
8. ANT-276–278 — Supabase Memory, Skills e Persistent Tasks;
9. MT5/Fimathe depois dos gates de core/segurança/confiabilidade.

Critério central: **quando consegue, prova; quando não consegue, sabe que não conseguiu e não inventa sucesso.**

## Entregas integradas

- PR #1–#22: baseline, UI/voz, multi-monitor, Computer Use económico, OpenAI, HUD, preferências, batching, painel do agente, captura por janela e primeiro controlo verificável de abas/rato.
- PR #23: runtime-readiness; merge `2952eb9c26f4c04b8dbd6e945daf2395eebe6107`; CI verde.
- PR #24: Local Fast Path + `ExecutionResult`; merge `3e084adaaf25d87a7cab71e352a2bb1c49b8f021`; CI verde.
- PR #25: Verifier central; merge `8b4371f15b312834743cdf08e07ad6a180d298ff`; fail-closed para side effects; CI verde.
- PR #26: primeira slice `open_app`/focus; merge `6bd204892b3e72fb3ea8ed6f68f6497155f807e5`; CI verde.
- PR #27: hardening `open_app`; merge `8558ce21a7e07e466198a706ed0cf90cef1c8bed`; pre-state/delta real e launcher Windows sem `shell=True`; CI verde.
- PR #28: desktop input/window postconditions; merge `680c537e6d31244aceca444648315d82e1d596cf`; ANT-254/255 cobertos por verificadores locais; CI verde.
- PR #29: real browser windows/tabs; merge `56a91411d7b30a69096305e1c7267875911b33fb`; múltiplas janelas reais, tabs por índice/título/URL e ambiguity fail-closed; CI verde.
- PR #30: managed Playwright verification; merge `6ca8e8e4cf37bca6bc4f5a8ce4c2aa0f708fe43a`; efeitos DOM com postconditions estruturais; CI verde.
- PR #31: SPA/popups/downloads; merge `3186a1406f496a7004c8696805680c50b7e59a3e`; MutationObserver com baseline de ruído, `expect_popup`, `expect_download`, persistência opt-in segura; CI verde.

## ANT-251–255 — integrados

- comandos simples podem evitar um novo turno LLM;
- `ExecutionResult` e `core/verifier.py` são fail-closed;
- apps/janelas e input físico usam estado Windows/UIA/frame-diff local quando disponível;
- texto digitado e amostras efémeras não são serializados na evidence.

## ANT-256 — escopo de código fechado pela PR #32

### Browser real já aberto — PR #29

- `verified_desktop_control` controla Chrome/Edge/Firefox/Opera/Brave/Vivaldi via Win32/UIA;
- enumera/foca janelas reais, não adivinha ambiguidades e verifica tabs por índice/título/URL;
- clipboard usado para ler URL é restaurado;
- Playwright paralelo não é apresentado como se fosse a janela já aberta do utilizador.

### Browser Playwright explicitamente gerido — PR #30

- `verified_browser_automation` valida `go_to/search/type/smart_type/scroll/click/smart_click/fill_form/new_tab/close_tab/back/forward/reload`;
- valores de inputs/formulários não entram na evidence;
- `session_status` é read-only e não cria sessão;
- o legado `browser_control` permanece apenas por compatibilidade.

### SPA, popups e downloads — PR #31

- click em SPA mede mutações DOM acima do ruído local, sem screenshot/modelo;
- popup é correlacionado com o clique por `expect_popup` e verificado por page-count/página aberta;
- download é correlacionado por `expect_download` e permanece fail-closed se o estado final não puder ser consultado;
- persistência é opt-in em `~/Downloads`, com nome sanitizado e sem overwrite silencioso;
- evidence não inclui caminho completo, filename ou conteúdo do download.

### CDP opcional seguro — PR #32

Novo `actions/real_browser_cdp.py` fornece fallback estruturado somente quando um browser Chromium já foi explicitamente iniciado com remote debugging local:

- endpoint fixo em `127.0.0.1`; apenas `cdp_port` é configurável e não existe scan/discovery;
- `/json/version` é lido por stdlib com timeout curto e resposta limitada;
- `webSocketDebuggerUrl` e User-Agent não são serializados;
- Firefox/outros engines são recusados antes do probe;
- `browser_cdp_status` confirma o endpoint;
- `browser_cdp_list_tabs` faz attach temporário e lista tabs estruturadas;
- `browser_cdp_switch_tab` selecciona por índice/título/URL e verifica `document.visibilityState` após activação;
- attach ao daily-driver exige `connect_over_cdp(no_defaults=True)`; versões Playwright sem esta protecção falham fechadas;
- `is_local=True` é usado quando suportado;
- não são lançados browsers, não são adicionadas flags, não são criados contextos nem recolhidos cookies/storage/DOM text;
- a conexão é limitada por timeout e `browser.close()` serve apenas para desligar o cliente de um browser conectado.

A primeira CI da PR #32 detectou apenas a regressão textual `verified boolean` no contrato antigo do plugin. O wording foi restaurado sem reduzir a segurança e o lifecycle da thread CDP foi adicionalmente limitado para não esperar implicitamente após timeout. A CI final do head/documentação tem de ficar verde antes do merge.

O escopo de implementação do ANT-256 fica fechado com esta PR. O E2E físico de browser real/Playwright/CDP permanece na matriz transversal ANT-275, tal como os E2E Windows das ANT-254/255.

## Realtime Computer Use económico — integrado, E2E físico pendente

- stream desktop em background com tiers locais;
- monitor automático/explícito e coordenadas negativas;
- frame diff local e target-window ROI;
- economy default, budgets, OpenAI opcional/fallback Gemini;
- micro-batching conservador;
- approvals de uso único e stop durante execução/espera.

## Validações e limites conhecidos

- Unit tests/CI Linux não provam Win32, UIA, áudio físico, DPI, multi-monitor, Playwright GUI/CDP real ou ScreenConnect.
- Um efeito sem estado observável suficiente permanece `verified=false`.
- E2E Windows físico continua no ANT-275 e deve ser executado antes de elevar a nota de produção.
- A extracção do `main.py` começa apenas depois do P0 ANT-254–258.

## Próxima sequência

1. integrar PR #32 apenas se a CI final continuar verde;
2. ANT-257 — multi-monitor/DPI hardening;
3. ANT-258 — UIA/files/settings;
4. ANT-259–263 — Orchestrator/Policy/Provider Router;
5. custo/UI/observabilidade;
6. memória Supabase/skills depois do core confiável.
