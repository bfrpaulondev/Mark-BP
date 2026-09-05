# Antonella — Estado da execução

> Painel operacional. O plano mestre continua a ser a fonte do escopo completo. As melhorias prioritárias das áreas já funcionais estão detalhadas em `docs/ANTONELLA_PRIORITY_HARDENING.md`.

**Última atualização:** 2026-09-05
**Branch canónica:** `main`
**Main confirmado:** `680c537e6d31244aceca444648315d82e1d596cf`

## Estado atual

| Campo | Estado |
|---|---|
| Tarefa ativa | ANT-256 — browser real verificável |
| Branch de implementação | `codex/ant-256-browser-real-verification` |
| Pull request | PR #29 — real browser windows/tabs |
| Issues abertas | Nenhuma necessária para este trabalho |
| Próximo teste real | Windows: múltiplas janelas Chrome/Edge, tabs por título/URL e verificação da janela foreground |
| Próximo bloco | continuar ANT-256 com CDP opcional/popups/downloads/SPA; depois ANT-257 |

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

- PR #1–#11: roadmap, estabilização, config, dependências, testes, logging e doctor.
- PR #12: UI Antonella + voz feminina.
- PR #13: visão multi-monitor e identidade da sessão de visão.
- PR #14–#22: Computer Use económico, especialista OpenAI, seleção de ecrãs, HUD, preferências, batching, painel do agente, captura por janela e controlo verificável de abas/rato.
- PR #23: runtime-readiness; merge `2952eb9c26f4c04b8dbd6e945daf2395eebe6107`; CI verde.
- PR #24: Local Fast Path + `ExecutionResult`; merge `3e084adaaf25d87a7cab71e352a2bb1c49b8f021`; CI verde.
- PR #25: Verifier central; merge `8b4371f15b312834743cdf08e07ad6a180d298ff`; fail-closed para side effects; CI verde.
- PR #26: primeira slice `open_app`/focus; merge `6bd204892b3e72fb3ea8ed6f68f6497155f807e5`; CI verde.
- PR #27: hardening `open_app`; merge `8558ce21a7e07e466198a706ed0cf90cef1c8bed`; pre-state/delta real e launcher Windows sem `shell=True`; CI verde.
- PR #28: desktop input/window postconditions; merge `680c537e6d31244aceca444648315d82e1d596cf`; ANT-254/255 cobertos por verificadores locais; CI verde em Python 3.11/3.12 e lock.

## ANT-251–255 — integrados

- comandos simples podem evitar um novo turno LLM;
- `ExecutionResult` é o contrato canónico de `ok/delivered/verified/evidence/error/risk/requires_approval`;
- `core/verifier.py` é fail-closed para resultados legacy;
- `open_app`, focus/minimize/maximize/switch usam estado Windows quando disponível;
- move/click/double/right/drag/scroll/hotkey/press/type/smart_type/paste/clear_field usam pre/post state e só permitem success claim quando a postcondition disponível prova o efeito;
- texto real digitado e amostras visuais efémeras não são serializados na evidence.

## ANT-256 — PR #29 em implementação

Foi identificado um problema estrutural no browser legado: `go_to/search/new_tab` podem abrir o browser nativo do utilizador, mas interacções DOM posteriores podem criar uma sessão Playwright separada e navegar essa sessão para a última URL. `browser_control action='switch'` troca a sessão de automação, não uma tab real.

A PR #29 adiciona `actions/real_browser_control.py` e liga-o ao `verified_desktop_control`:

- enumera janelas reais Chrome/Edge/Firefox/Opera/Brave/Vivaldi via Win32 + processo;
- selecciona por browser, índice de janela ou título e prefere a janela foreground quando inequívoca;
- múltiplas janelas/apps ambíguas não são adivinhadas;
- foco de janela confirma o `HWND` foreground;
- UIA enumera tabs e estado selected;
- tabs podem ser escolhidas por índice ou título; quando UIA existe, índices >9 são suportados;
- next/previous comparam fingerprint de title + URL + selected-tab;
- `browser_switch_tab_url` percorre tabs UIA, lê a URL real, verifica o match e tenta restaurar a tab original quando nenhum match existe;
- `browser_current` devolve o estado real actual;
- clipboard usado para ler URL é restaurado;
- o prompt proíbe criar uma sessão Playwright paralela apenas para listar/focar/trocar tabs/janelas já abertas.

A primeira CI da PR #29 revelou três regressões exclusivamente de testes/contrato: wording legado `verified boolean` e mocks sobre um objecto de plugin que podia ser recarregado pelo plugin loader. O wording foi preservado e os mocks passaram a usar `patch.object` sobre o objecto realmente importado. A CI seguinte tem de ficar verde antes do merge.

ANT-256 permanece aberta depois desta slice: CDP opcional para browsers que já estejam explicitamente em remote-debugging, popups/downloads e verificação SPA continuam pendentes. Não relançar silenciosamente o perfil real do utilizador com flags de debugging.

## Realtime Computer Use económico — integrado, E2E físico pendente

- stream desktop em background com tiers locais;
- monitor automático/explícito e coordenadas negativas;
- frame diff local e target-window ROI;
- economy default, budgets, OpenAI opcional/fallback Gemini;
- micro-batching conservador;
- approvals de uso único e stop durante execução/espera.

## Validações e limites conhecidos

- O utilizador confirmou smoke anterior de UI/voz/Notepad, mas as novas postconditions precisam de novo E2E Windows após actualizar a `main`.
- Unit tests e CI Linux não provam Win32, UIA, áudio físico, DPI, multi-monitor ou ScreenConnect.
- Um efeito sem estado observável suficiente permanece deliberadamente `verified=false`.
- A extracção do `main.py` começa apenas depois do P0 ANT-254–258.

## Próxima sequência

1. integrar PR #29 apenas com CI final verde;
2. continuar ANT-256 com CDP opcional/popups/downloads/SPA;
3. ANT-257 — multi-monitor/DPI hardening;
4. ANT-258 — UIA/files/settings;
5. ANT-259–263 — Orchestrator/Policy/Provider Router;
6. custo/UI/observabilidade;
7. memória Supabase/skills depois do core confiável.
