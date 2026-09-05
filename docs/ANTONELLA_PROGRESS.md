# Antonella — Estado da execução

> Painel operacional. O plano mestre continua a ser a fonte do escopo completo. As melhorias prioritárias das áreas já funcionais estão detalhadas em `docs/ANTONELLA_PRIORITY_HARDENING.md`.

**Última atualização:** 2026-09-05
**Branch canónica:** `main`
**Main confirmado:** `2952eb9c26f4c04b8dbd6e945daf2395eebe6107`

## Estado atual

| Campo | Estado |
|---|---|
| Tarefa ativa | ANT-251 — Local Command Fast Path |
| Branch ativa | `codex/reliability-priority-wave1` |
| Pull requests abertas | Nenhuma no início desta slice; abrir apenas esta implementação quando reviewable |
| Issues abertas | Nenhuma necessária para este trabalho |
| Próximo teste real | Windows: fast path + browser real + rato + multi-monitor + ScreenConnect |
| Próxima tarefa | ANT-252/253 — `ExecutionResult` + Verifier central |

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
- PR #23: runtime-readiness; README/setup apontam para `antonella.py`, doctor alinhado ao Gemini Live, probes isolados de GUI/áudio e diagnóstico de Chromium. CI verde em Python 3.11, Python 3.12 e dependency lock antes do merge. Merge: `2952eb9c26f4c04b8dbd6e945daf2395eebe6107`.

## Trabalho em curso — ANT-251 Local Command Fast Path

A branch `codex/local-command-fast-path` histórica estava 6 commits à frente e 2 atrás da `main`, baseada em `e24e6e7`. Para evitar integrar uma branch divergente, o trabalho útil está a ser portado de forma limpa para `codex/reliability-priority-wave1`, baseada na `main` atual.

Escopo desta slice:

- reconhecer apenas comandos simples/inequívocos de baixo risco;
- executar localmente sem novo turno Gemini/OpenAI;
- manter pedidos multi-etapa no cérebro principal;
- comandos iniciais: abrir app, scroll, listar ecrãs, status/parar/aprovar agente, status do sistema, modo de custo e preferência de provider;
- router local não importa SDK Gemini/OpenAI;
- testes de regressão garantem que pedidos complexos não são interceptados.

## Implementação integrada — Realtime Computer Use económico (E2E pendente)

### Perceção contínua local

- stream desktop em background;
- 10/15/20 FPS conforme modo de custo;
- seleção automática ou explícita de monitor;
- coordenadas negativas;
- `frame diff` local;
- target-window ROI com fallback para monitor;
- compressão diferente por tier.

### Loop

```text
observe → plan → safety → act → observe → verify/change → continue
```

O loop corre em background para a conversa de voz continuar disponível.

### Controlo de custo

- `economy` default;
- limites de chamadas/passos;
- resolução menor em economy;
- OpenAI por tier quando configurado;
- fallback Gemini;
- micro-batching conservador e `saved_model_calls`.

### Segurança atual

- baixo risco automático dentro do Computer Use;
- efeitos destrutivos, externos, privilegiados, financeiros ou permissões pausam;
- aprovação de uso único;
- `stop` interrompe inclusive espera de aprovação;
- este gate ainda não cobre universalmente todas as tools legadas — ANT-261/262 continuam prioritárias.

## Validações e limites conhecidos

- O utilizador já confirmou smoke anterior de UI/voz/Notepad, mas as novas slices de browser/rato/Computer Use precisam de novo E2E Windows após atualização da `main`.
- Unit tests/CI Linux não provam Win32, UIA, áudio físico, DPI, multi-monitor ou ScreenConnect.
- O browser real e o rato agora possuem controlos verificáveis para os casos corrigidos, mas a verificação ainda precisa ser generalizada às restantes tools.
- O código herdado ainda concentra responsabilidades em `main.py`; a extração será incremental, não big-bang.

## Próxima sequência

1. concluir ANT-251 e integrar apenas com CI verde;
2. ANT-252/253 `ExecutionResult` + Verifier;
3. aplicar o contrato às tools legadas começando pelas que causam efeitos no desktop;
4. browser real + DPI/multi-monitor hardening;
5. AgentOrchestrator/Policy Engine;
6. continuar custo/UI/observabilidade;
7. memória Supabase/skills depois do core confiável.
