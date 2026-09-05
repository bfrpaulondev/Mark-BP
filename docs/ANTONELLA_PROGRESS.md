# Antonella — Estado da execução

> Painel operacional. O plano mestre continua a ser a fonte do escopo completo. As melhorias prioritárias das áreas já funcionais estão detalhadas em `docs/ANTONELLA_PRIORITY_HARDENING.md`.

**Última atualização:** 2026-09-05
**Branch canónica:** `main`
**Main confirmado:** `3e084adaaf25d87a7cab71e352a2bb1c49b8f021`

## Estado atual

| Campo | Estado |
|---|---|
| Tarefa ativa | ANT-253 — Verifier central |
| Branch ativa | `codex/execution-verifier-core` |
| Pull requests abertas | abrir apenas esta implementação quando reviewable |
| Issues abertas | Nenhuma necessária para este trabalho |
| Próximo teste real | Windows: fast path + browser real + rato + multi-monitor + ScreenConnect |
| Próxima tarefa | ANT-254/255 — postconditions de apps/janelas e input desktop |

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
- PR #24: Reliability Hardening Wave 1; merge `3e084adaaf25d87a7cab71e352a2bb1c49b8f021`; ANT-251 Local Fast Path integrado e ANT-252 `ExecutionResult` canónico integrado. CI verde em Python 3.11/3.12 e lock.

## ANT-251 — concluído e integrado

- comandos simples/inequívocos podem ser resolvidos localmente sem novo turno LLM;
- pedidos multi-etapa continuam para o cérebro principal;
- router local não importa SDK Gemini/OpenAI;
- `open_app`/`scroll` legados não são promovidos a sucesso verificado apenas pelo texto de retorno;
- branch antiga `codex/local-command-fast-path` foi alinhada à `main` depois de o trabalho útil ser portado/supersedido.

## ANT-252 — concluído e integrado

`core/execution_result.py` define o contrato canónico com:

- `ok`;
- `delivered`;
- `verified`;
- `evidence`;
- `error`;
- `risk`;
- `requires_approval`;
- `correlation_id`;
- `can_claim_success`.

`ok=true` ou ausência de exception não implicam `verified=true`.

## ANT-253 — em implementação

A branch `codex/execution-verifier-core` introduz:

- `core/verifier.py` para converter resultados estruturados/legados sem inventar postconditions;
- `core/tool_verification_policy.py` para identificar tools/actions que exigem evidência antes de claim de sucesso;
- integração no `AntonellaLive._execute_tool`: respostas side-effecting recebem um objecto `execution` autoritativo antes de voltar ao modelo;
- prompt actualizado: `execution.can_claim_success=true` é a condição runtime para anunciar conclusão;
- strings legadas `Done`, `Opened`, `Scrolled`, etc. permanecem `verified=false` até um verifier específico provar o efeito;
- testes fail-closed para structured JSON, erros inconsistentes, aprovação e tools mutantes.

Esta slice ainda não substitui os verifiers específicos de cada domínio. ANT-254–258 continuam necessários para transformar entrega não verificada em sucesso comprovado quando tecnicamente possível.

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
- Browser real e rato possuem verificação específica nos casos da PR #22; restantes tools estão agora a entrar no contrato universal.
- O código herdado ainda concentra responsabilidades em `main.py`; a extração será incremental.

## Próxima sequência

1. concluir ANT-253 e integrar apenas com CI verde;
2. ANT-254/255: postconditions de app/window e mouse/keyboard/click/scroll/type;
3. ANT-256/257: browser real e multi-monitor/DPI hardening;
4. ANT-258: UIA/files/settings;
5. AgentOrchestrator/Policy Engine;
6. custo/UI/observabilidade;
7. memória Supabase/skills depois do core confiável.
