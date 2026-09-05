# Antonella — Estado da execução

> Painel operacional. O plano mestre continua a ser a fonte do escopo completo. As melhorias prioritárias das áreas já funcionais estão detalhadas em `docs/ANTONELLA_PRIORITY_HARDENING.md`.

**Última atualização:** 2026-09-05
**Branch canónica:** `main`
**Main confirmado:** `6ca8e8e4cf37bca6bc4f5a8ce4c2aa0f708fe43a`

## Estado atual

| Campo | Estado |
|---|---|
| Tarefa ativa | ANT-256 — browser verificável, terceira slice SPA/popups/downloads |
| Branch de implementação | `codex/ant-256-browser-events-spa` |
| Pull request | PR #31 — verified browser SPA/popups/downloads |
| Issues abertas | Nenhuma necessária para este trabalho |
| Próximo teste real | Windows: SPA sem mudança de URL, popup real e download Playwright com/sem persistência |
| Próximo bloco | CDP opcional read-only/attach apenas quando o browser já tiver remote debugging explícito; depois ANT-257 |

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
- PR #30: managed Playwright verification; merge `6ca8e8e4cf37bca6bc4f5a8ce4c2aa0f708fe43a`; go_to/search/type/scroll/click/forms/tab lifecycle/history/reload com postconditions estruturais; CI verde.

## ANT-251–255 — integrados

- comandos simples podem evitar um novo turno LLM;
- `ExecutionResult` e `core/verifier.py` são fail-closed;
- apps/janelas e input físico usam estado Windows/UIA/frame-diff local quando disponível;
- texto digitado e amostras efémeras não são serializados na evidence.

## ANT-256 — browser real e automação gerida separados

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

### Browser Playwright explicitamente gerido — integrado na PR #30

- `verified_browser_automation` é a superfície preferida para efeitos DOM geridos;
- `go_to/search`: confirma URL final contra destino;
- `type/smart_type`: relê `input_value()` e compara sem expor texto na evidence;
- `scroll`: compara `window.scrollY` antes/depois;
- `click/smart_click`: confirma estados estruturais conhecidos;
- `fill_form`: relê cada selector e valida sem guardar valores;
- `new_tab/close_tab`: page-count + page state;
- `back/forward`: mudança de URL;
- `reload`: conclusão Playwright + página activa;
- `session_status`: read-only e não cria sessão;
- plugin entra no central execution verification contract;
- `browser_control` permanece apenas por compatibilidade.

### SPA, popups e downloads — PR #31

Novo `actions/verified_browser_events.py` fecha os principais falsos negativos/falsos positivos que restavam em eventos de browser gerido:

- `click/smart_click` medem ruído DOM local antes da acção com `MutationObserver` e só aceitam mutação pós-clique acima desse baseline, ou outro estado estrutural já verificável;
- não envia screenshot nem conteúdo DOM para modelo;
- `click_popup` usa `expect_popup`, correlaciona o novo page event com o clique e confirma aumento do page-count/página aberta;
- popup verificado pode tornar-se a página activa do workflow;
- `click_download` usa `expect_download`, espera o estado final e permanece fail-closed se a conclusão não puder ser consultada;
- `save_download` é opt-in e só grava em `~/Downloads` com filename sanitizado e sem overwrite silencioso;
- evidence de download não inclui caminho completo nem filename, apenas metadados mínimos como extensão/tamanho quando guardado;
- `delivered=true` só é emitido quando o clique foi efectivamente enviado.

A primeira CI da PR #31 encontrou apenas uma regressão de sanitização (`control-only filename` produzia underscores). O código foi corrigido para cair em `download`; adicionalmente o fluxo popup/download foi endurecido para não assumir entrega/conclusão. A CI seguinte passou em lock e Python 3.11/3.12 antes do commit final de documentação; o head final deve voltar a ficar verde antes do merge.

ANT-256 ainda não deve ser marcada concluída: falta CDP opcional para browsers Chromium que já tenham sido iniciados explicitamente com remote debugging e E2E Windows/Playwright real. A Antonella não deve relançar silenciosamente o perfil real do utilizador com flags de debugging.

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

1. integrar PR #31 apenas se a CI final continuar verde;
2. concluir ANT-256 com CDP opcional seguro, sem relançar browser real;
3. ANT-257 — multi-monitor/DPI hardening;
4. ANT-258 — UIA/files/settings;
5. ANT-259–263 — Orchestrator/Policy/Provider Router;
6. custo/UI/observabilidade;
7. memória Supabase/skills depois do core confiável.
