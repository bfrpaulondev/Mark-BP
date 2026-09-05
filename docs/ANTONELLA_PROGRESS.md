# Antonella — Estado da execução

> Painel operacional. O plano mestre continua a ser a fonte do escopo completo. As melhorias prioritárias das áreas já funcionais estão detalhadas em `docs/ANTONELLA_PRIORITY_HARDENING.md`.

**Última atualização:** 2026-09-05
**Branch canónica:** `main`
**Main confirmado:** `56a91411d7b30a69096305e1c7267875911b33fb`

## Estado atual

| Campo | Estado |
|---|---|
| Tarefa ativa | ANT-256 — browser verificável |
| Branch de implementação | `codex/ant-256-playwright-verification` |
| Pull request | PR #30 — verified managed Playwright effects |
| Issues abertas | Nenhuma necessária para este trabalho |
| Próximo teste real | Windows: browser real multi-window/tabs + browser gerido go_to/type/scroll/click/form/tab lifecycle |
| Próximo bloco | fechar PR #30; depois CDP opcional/popups/downloads/SPA ou ANT-257 conforme dependências |

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
- PR #29: real browser windows/tabs; merge `56a91411d7b30a69096305e1c7267875911b33fb`; múltiplas janelas reais, tabs por índice/título/URL e ambiguity fail-closed; CI final verde após corrigir regressões de contrato.

## ANT-251–255 — integrados

- comandos simples podem evitar um novo turno LLM;
- `ExecutionResult` e `core/verifier.py` são fail-closed;
- apps/janelas e input físico usam estado Windows/UIA/frame-diff local quando disponível;
- texto digitado e amostras efémeras não são serializados na evidence.

## ANT-256 — duas superfícies explicitamente separadas

### Browser real já aberto — integrado na PR #29

- `verified_desktop_control` usa `actions/real_browser_control.py` para Chrome/Edge/Firefox/Opera/Brave/Vivaldi;
- enumera/foca janelas reais por Win32/processo;
- não adivinha entre múltiplas janelas/apps;
- UIA enumera tabs e selected state;
- next/previous usam fingerprint de title + URL + selected tab;
- tab por índice/título/URL, incluindo índices >9 quando UIA existe;
- `browser_current` confirma estado actual;
- clipboard usado para ler URL é restaurado;
- o prompt proíbe criar Playwright apenas para manipular tabs/janelas que já existem.

### Browser Playwright explicitamente gerido — PR #30

Novo `verified_browser_automation` evita que o legado `browser_control` seja a superfície preferida para efeitos DOM:

- `go_to/search`: confirma URL final contra destino;
- `type/smart_type`: relê `input_value()` e compara; texto real não entra na evidence;
- `scroll`: compara `window.scrollY` antes/depois;
- `click/smart_click`: compara URL/title/foco/page-count e estados do elemento (`checked`, `aria-expanded`, `aria-pressed`, selected/value length); click sem efeito observável fica não verificado;
- `fill_form`: cada selector é relido e validado, sem guardar valores na evidence;
- `new_tab/close_tab`: page-count + page state;
- `back/forward`: mudança de URL;
- `reload`: conclusão Playwright + página activa;
- `session_status`: read-only e não cria sessão;
- plugin entra sempre no central execution verification contract;
- `browser_control` permanece apenas por compatibilidade, enquanto o prompt prefere a camada verificada.

Testes novos cobrem helpers, policy, contrato do plugin/prompt e efeitos async com fake page para scroll/type. A primeira CI da PR #30 ficou verde em Python 3.11, Python 3.12 e dependency lock. O commit final de docs deve voltar a passar antes do merge.

ANT-256 ainda não deve ser marcada concluída: CDP opcional para browsers já iniciados explicitamente com remote debugging, popups/downloads e alguns efeitos SPA continuam pendentes. Não relançar silenciosamente o perfil real do utilizador com flags de debugging.

## Realtime Computer Use económico — integrado, E2E físico pendente

- stream desktop em background com tiers locais;
- monitor automático/explícito e coordenadas negativas;
- frame diff local e target-window ROI;
- economy default, budgets, OpenAI opcional/fallback Gemini;
- micro-batching conservador;
- approvals de uso único e stop durante execução/espera.

## Validações e limites conhecidos

- Unit tests/CI Linux não provam Win32, UIA, áudio físico, DPI, multi-monitor, Playwright GUI real ou ScreenConnect.
- Um efeito sem estado observável suficiente permanece `verified=false`.
- E2E Windows físico deve validar as novas superfícies antes de elevar a nota de produção.
- A extracção do `main.py` começa apenas depois do P0 ANT-254–258.

## Próxima sequência

1. integrar PR #30 apenas se a CI final continuar verde;
2. concluir ANT-256 com CDP opcional/popups/downloads/SPA quando seguro;
3. ANT-257 — multi-monitor/DPI hardening;
4. ANT-258 — UIA/files/settings;
5. ANT-259–263 — Orchestrator/Policy/Provider Router;
6. custo/UI/observabilidade;
7. memória Supabase/skills depois do core confiável.
