# Antonella — Estado da execução

> Painel operacional. O plano mestre continua a ser a fonte do escopo completo. As melhorias prioritárias das áreas já funcionais estão detalhadas em `docs/ANTONELLA_PRIORITY_HARDENING.md`.

**Última atualização:** 2026-09-05
**Branch canónica:** `main`
**Main confirmado:** `6bd204892b3e72fb3ea8ed6f68f6497155f807e5`

## Estado atual

| Campo | Estado |
|---|---|
| Tarefa ativa | ANT-254 — verificação de aplicações/janelas |
| Branch ativa | `codex/ant-254-open-app-hardening` |
| Pull requests abertas | abrir apenas esta implementação quando reviewable |
| Issues abertas | Nenhuma necessária para este trabalho |
| Próximo teste real | Windows: abrir Bloco de Notas/Chrome + focus + browser/rato + multi-monitor + ScreenConnect |
| Próxima tarefa | concluir ANT-254; depois ANT-255 input desktop verificável |

## Prioridade aprovada em 2026-09-05

O desenvolvimento horário passa a priorizar elevar as áreas já prontas antes de aumentar escopo. Ordem operacional:

1. ANT-251 — Local Fast Path sem chamada LLM para comandos simples;
2. ANT-252/253 — `ExecutionResult` e Verifier universal;
3. ANT-254–258 — postconditions reais em apps/janelas, mouse/teclado, browser, multi-monitor/DPI, UIA/ficheiros/settings;
4. ANT-259–263 — AgentOrchestrator, ToolRouter/ExecutionEngine, Policy Engine, aprovação humana e Provider Router;
5. ANT-264–267 — custo/telemetria, percepção local, ScreenConnect e recovery do Computer Use;
6. ANT-268–272 — UI/UX, Agent Control Center, voz/verificação e limpeza de identidade herdada;
7. ANT-273–275 — Windows CI, observabilidade e matriz E2E real;
8. ANT-276–278 — Supabase Memory, Skills e Persistent Tasks;
9. MT5/Fimathe depois dos gates de core/segurança/confiabilidade.

Critério central: **quando consegue, prova; quando não consegue, sabe que não conseguiu e não inventa sucesso.**

## Entregas integradas

- PR #1–#11: roadmap, estabilização, config, dependências, testes, logging e doctor.
- PR #12: nova UI Antonella + voz feminina.
- PR #13: visão multi-monitor e identidade da sessão de visão.
- PR #14–#22: Computer Use económico, especialista OpenAI, seleção de ecrãs, HUD, preferências, batching, painel do agente, captura por janela e controlo verificável de abas/rato.
- PR #23: runtime-readiness; merge `2952eb9c26f4c04b8dbd6e945daf2395eebe6107`; CI verde em Python 3.11/3.12 e lock.
- PR #24: Reliability Hardening Wave 1; merge `3e084adaaf25d87a7cab71e352a2bb1c49b8f021`; ANT-251 Local Fast Path + ANT-252 `ExecutionResult`; CI verde.
- PR #25: Verifier central; merge `8b4371f15b312834743cdf08e07ad6a180d298ff`; respostas side-effecting recebem `execution` autoritativo e claims ficam fail-closed; CI verde em Python 3.11/3.12 e lock.
- PR #26: primeira slice de postconditions para `open_app` e foco; merge `6bd204892b3e72fb3ea8ed6f68f6497155f807e5`; CI final verde após corrigir os testes em Python 3.11/3.12.

## ANT-251 — concluído e integrado

- comandos simples/inequívocos podem ser resolvidos localmente sem novo turno LLM;
- pedidos multi-etapa continuam para o cérebro principal;
- router local não importa SDK Gemini/OpenAI;
- branch antiga divergente foi alinhada depois de o trabalho útil ser portado.

## ANT-252/253 — concluídos e integrados

- `ExecutionResult`: `ok`, `delivered`, `verified`, `evidence`, `error`, `risk`, `requires_approval`, `correlation_id`, `can_claim_success`;
- `core/verifier.py` recusa inferir verificação a partir de `Done`, `Opened`, `Scrolled` ou ausência de exception;
- `core/tool_verification_policy.py` identifica tools/actions mutantes que exigem postcondition;
- `AntonellaLive._execute_tool` anexa `execution` antes de devolver o resultado ao modelo;
- prompt trata `execution.can_claim_success=true` como condição autoritativa para anunciar conclusão.

## ANT-254 — em implementação

A PR #26 introduziu os primeiros verifiers específicos, mantendo o fallback fail-closed do ANT-253. A continuação em `codex/ant-254-open-app-hardening` corrige dois riscos observados após a integração:

- `open_app` no Windows deixa de depender do texto `Opened X`;
- mapeia aplicações conhecidas para processos esperados e observa processos via `psutil`;
- recolhe janelas visíveis associadas aos PIDs via Win32 quando disponível;
- captura processos, janelas visíveis e foreground antes e depois de `open_app`;
- só promove a `verified=true` quando observa novo PID, nova janela ou mudança de foreground para o alvo;
- uma aplicação que já estava aberta sem transição observável permanece `verified=false`;
- o launcher Windows deixa de usar `shell=True`: executáveis usam argumentos estruturados e apenas `ms-settings:` é aceite como URI conhecida;
- `computer_control.focus_window` compara o título solicitado com a janela foreground real;
- o Local Fast Path também revalida `open_app` antes de usar wording de sucesso;
- em plataformas sem o verifier específico, mantém `verified=false` em vez de inventar sucesso.

Validação local desta continuação: 159 testes passaram em Python 3.11 no ambiente bloqueado por `uv.lock`; compilação e `git diff --check` passaram. O E2E Windows não foi executado. Ainda faltam nesta família minimize/maximize/switch com pre-state/target identity robustos; não marcar ANT-254 como concluída até cobrir/limitar esses casos e passar CI/E2E apropriados.

## Implementação integrada — Realtime Computer Use económico (E2E pendente)

- stream desktop em background com tiers 10/15/20 FPS locais;
- monitor automático/explícito e coordenadas negativas;
- frame diff local;
- target-window ROI;
- economy default, budgets, OpenAI opcional/fallback Gemini;
- micro-batching conservador;
- approvals de uso único dentro do Computer Use;
- stop durante execução/espera de aprovação.

## Validações e limites conhecidos

- O utilizador confirmou smoke anterior de UI/voz/Notepad, mas as novas slices precisam de novo E2E Windows após actualizar a `main`.
- Unit tests/CI Linux não provam Win32, UIA, áudio físico, DPI, multi-monitor ou ScreenConnect.
- Browser real e rato possuem verificação específica nos casos da PR #22; restantes tools estão a entrar no contrato universal.
- O código herdado ainda concentra responsabilidades em `main.py`; a extração será incremental.

## Próxima sequência

1. concluir ANT-254 e integrar apenas com CI verde;
2. ANT-255: mouse/keyboard/click/scroll/type com pre/post state;
3. ANT-256/257: browser real e multi-monitor/DPI hardening;
4. ANT-258: UIA/files/settings;
5. AgentOrchestrator/Policy Engine;
6. custo/UI/observabilidade;
7. memória Supabase/skills depois do core confiável.
