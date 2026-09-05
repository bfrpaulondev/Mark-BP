# Antonella — Estado da execução

> Painel operacional. O plano mestre continua a ser a fonte do escopo completo. As melhorias prioritárias das áreas já funcionais estão detalhadas em `docs/ANTONELLA_PRIORITY_HARDENING.md`.

**Última atualização:** 2026-09-05
**Branch canónica:** `main`
**Main confirmado antes da PR #28:** `8558ce21a7e07e466198a706ed0cf90cef1c8bed`

## Estado atual

| Campo | Estado |
|---|---|
| Tarefa ativa | ANT-255 — verificação de input desktop; fecha também o restante ANT-254 |
| Branch de implementação | `codex/ant-255-input-verification` até integração da PR #28 |
| Pull request | PR #28 — desktop input/window postconditions |
| Issues abertas | Nenhuma necessária para este trabalho |
| Próximo teste real | Windows: Notepad/Chrome + click/scroll/type + window minimize/maximize/switch + multi-monitor + ScreenConnect |
| Próxima tarefa após integração | ANT-256 — browser real verificável |

## Prioridade aprovada em 2026-09-05

O desenvolvimento horário prioriza elevar as áreas já prontas antes de aumentar escopo:

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
- PR #27: hardening de `open_app`; merge `8558ce21a7e07e466198a706ed0cf90cef1c8bed`; pre-state/delta real, launcher Windows sem `shell=True`, input tratado como dados; CI verde.

## ANT-251–253 — concluídos

- comandos simples podem evitar um novo turno LLM;
- `ExecutionResult` é o contrato canónico de `ok/delivered/verified/evidence/error/risk/requires_approval`;
- `core/verifier.py` recusa inferir sucesso a partir de strings como `Done`, `Opened`, `Clicked`, `Typed` ou `Scrolled`;
- `AntonellaLive._execute_tool` recolhe pre-state quando necessário e anexa `execution` autoritativo antes de devolver o resultado ao modelo.

## ANT-254 — código fechado pela PR #28, E2E Windows pendente

- `open_app`: processos, janelas e foreground são capturados antes/depois; processo já existente não prova novo lançamento;
- launcher Windows não usa shell para executáveis e restringe URI especial a `ms-settings:`;
- `focus_window`: Win32 trata título como texto e confirma foreground;
- `minimize`: só verifica quando a janela alvo passa a `IsIconic`;
- `maximize`: só verifica quando a janela alvo passa a `IsZoomed`;
- `switch_window`: exige mudança real do `HWND` foreground.

## ANT-255 — implementado na PR #28

Novo `core/desktop_postconditions.py` adiciona observação local antes/depois para `computer_control`:

- `move`: cursor final tem de coincidir com o target;
- `click/left_click/double_click/right_click`: target de cursor + mudança observável; sem efeito observável fica `verified=false`;
- `drag`: endpoint + mudança observável;
- `scroll`: mudança visual local do foreground window; scroll sem movimento observável fica não verificado;
- `type/smart_type/paste/clear_field`: usa controlo focado UIA quando este expõe ValuePattern; conteúdo real é mantido apenas em memória e removido da evidence;
- `hotkey/press`: foreground/focus/value/frame são comparados e só estados observáveis permitem claim;
- amostras visuais são pequenas, grayscale, efémeras e nunca persistidas como screenshots;
- plataformas/controls sem estado observável continuam fail-closed.

Foram adicionados testes puros das transições e testes de wiring para garantir que `computer_control`/`computer_settings` passam pelo capturador/verifier. As primeiras execuções da CI da PR #28 passaram em Python 3.11, Python 3.12 e dependency lock; qualquer commit posterior de documentação deve voltar a ficar verde antes do merge.

## Realtime Computer Use económico — integrado, E2E físico pendente

- stream desktop em background com tiers locais;
- monitor automático/explícito e coordenadas negativas;
- frame diff local e target-window ROI;
- economy default, budgets, OpenAI opcional/fallback Gemini;
- micro-batching conservador;
- approvals de uso único dentro do Computer Use;
- stop durante execução/espera de aprovação.

## Validações e limites conhecidos

- O utilizador confirmou smoke anterior de UI/voz/Notepad, mas as novas postconditions precisam de novo E2E Windows após actualizar a `main`.
- Unit tests e CI Linux não provam Win32, UIA, áudio físico, DPI, multi-monitor ou ScreenConnect.
- A verificação de click/drag/scroll é deliberadamente fail-closed quando não existe mudança observável suficiente.
- Browser real e mouse movement já têm verificadores específicos da PR #22; ANT-256 vai consolidar browser por tabs/janelas/URL/CDP/UIA.
- O código herdado ainda concentra responsabilidades em `main.py`; a extracção será incremental em ANT-259/260.

## Próxima sequência

1. integrar PR #28 apenas se a CI final continuar verde;
2. ANT-256 — browser real verificável;
3. ANT-257 — multi-monitor/DPI hardening;
4. ANT-258 — UIA/files/settings;
5. ANT-259–263 — Orchestrator/Policy/Provider Router;
6. custo/UI/observabilidade;
7. memória Supabase/skills depois do core confiável.
