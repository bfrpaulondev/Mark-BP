# Antonella — Estado da execução

> Painel operacional. O plano mestre continua a ser a fonte do escopo completo. As melhorias prioritárias das áreas já funcionais estão detalhadas em `docs/ANTONELLA_PRIORITY_HARDENING.md`.

**Última atualização:** 2026-09-05
**Branch canónica:** `main`
**Main confirmado antes da PR #34:** `6cd8601b9a0a9b4d3a9a94ceb701f5ab993fd8c8`

## Estado atual

| Campo | Estado |
|---|---|
| Tarefa a fechar | ANT-258 — UIA/files/settings verification |
| Branch de implementação | `codex/ant-258-uia-files-settings-verification` |
| Pull request | PR #34 — verify UIA, filesystem and Windows settings effects |
| Issues abertas | Nenhuma necessária para este trabalho |
| CI de código | #103 verde em Dependency lock + Python 3.11 + Python 3.12 antes do commit final de documentação |
| Próximo teste real | ANT-275 Windows físico: UIA, settings, filesystem, multi-monitor/DPI e browser real |
| Próximo bloco | ANT-259 — extrair `AgentOrchestrator` incremental sem quebrar o runtime actual |

## Prioridade aprovada em 2026-09-05

1. ANT-251–258 — execução verificável / P0;
2. ANT-259–263 — AgentOrchestrator, ToolRouter/ExecutionEngine, Policy Engine, aprovação humana e Provider Router;
3. ANT-264–267 — custo/telemetria, percepção local, ScreenConnect e recovery;
4. ANT-268–272 — UI/UX, Agent Control Center, voz/verificação e identidade;
5. ANT-273–275 — Windows CI, observabilidade e E2E real;
6. ANT-276–278 — Supabase Memory, Skills e Persistent Tasks;
7. MT5/Fimathe depois dos gates de core/segurança/confiabilidade.

Critério central: **quando consegue, prova; quando não consegue, sabe que não conseguiu e não inventa sucesso.**

## Entregas integradas

- PR #1–#22: baseline, UI/voz, multi-monitor, Computer Use económico, OpenAI, HUD, preferências, batching, painel do agente, captura por janela e primeiro controlo verificável de abas/rato.
- PR #23: runtime-readiness; merge `2952eb9c26f4c04b8dbd6e945daf2395eebe6107`; CI verde.
- PR #24: Local Fast Path + `ExecutionResult`; merge `3e084adaaf25d87a7cab71e352a2bb1c49b8f021`; CI verde.
- PR #25: Verifier central; merge `8b4371f15b312834743cdf08e07ad6a180d298ff`; fail-closed para side effects; CI verde.
- PR #26–#28: apps/janelas + desktop input postconditions; ANT-254/255 fechados no código; CI verde.
- PR #29: browser real Win32/UIA; merge `56a91411d7b30a69096305e1c7267875911b33fb`; ambiguity fail-closed.
- PR #30: managed Playwright verification; merge `6ca8e8e4cf37bca6bc4f5a8ce4c2aa0f708fe43a`.
- PR #31: SPA/popups/downloads; merge `3186a1406f496a7004c8696805680c50b7e59a3e`.
- PR #32: safe optional CDP bridge; merge `aaabdda9485483712b88413f3be4e584be3e3886`.
- PR #33: multi-monitor/DPI hardening; merge `6cd8601b9a0a9b4d3a9a94ceb701f5ab993fd8c8`; stale display frames falham fechados.

## ANT-257 — integrado

- Per-Monitor DPI Awareness V2 em Windows;
- geometria física Win32 + MSS, sem assumir ordem de enumeração;
- DPI/scale/primary/device por display;
- suporta monitor à esquerda/acima e coordenadas negativas;
- `topology_token` muda com geometria, DPI, primary e hot-plug;
- target de monitor explícito fica preso à identidade física (`device` + geometria fallback);
- disconnect/reconnect não reutiliza silenciosamente índice antigo;
- frame antigo é invalidado após mudança de topologia;
- input visual exige token capturado + token vivo iguais; se a topologia não puder ser lida, o input não é despachado;
- CI final #99 totalmente verde antes do merge;
- validação física permanece no ANT-275.

## ANT-258 — PR #34

### Windows UI Automation

- `list_windows`, `inspect` e `find` são tratados como reads;
- `click` e `set_text` são side effects e devolvem `delivered/verified` explícitos;
- janela/controlo com múltiplos matches igualmente fortes falha fechado;
- click só verifica transição estrutural/UIA ou foreground observável;
- set_text relê o valor exacto;
- texto real fica apenas em memória e não entra na evidence;
- erro no readback depois de input entregue fica `delivered=true, verified=false`.

### Filesystem

- pre-state e post-state usam exactamente source/destination resolvidos antes da mutação;
- o verificador respeita os mesmos `_SAFE_ROOTS` do `file_controller` e não inspecciona paths que a tool recusaria;
- create/write/append/delete/move/copy/rename/organize têm postconditions próprias;
- ficheiros pequenos usam hash completo; ficheiros grandes usam fingerprint bounded first/last + size;
- append confirma tamanho e tail exacto;
- move/copy/rename confirmam identidade estrutural/conteúdo;
- ficheiro vazio é suportado correctamente;
- full path, filename e conteúdo são retirados da evidence pública.

### Settings Windows

- volume set/up/down, mute/unmute/toggle: readback do endpoint de áudio;
- brightness up/down: estado WMI/CIM;
- dark mode: registry HKCU;
- Wi-Fi toggle: estado do adapter;
- minimize/maximize/switch_window mantêm o verificador Win32 anterior;
- se o estado não puder ser observado, a acção não é promovida a sucesso.

## Realtime Computer Use económico — integrado, E2E físico pendente

- stream desktop em background com tiers locais;
- monitor automático/explícito e coordenadas negativas;
- frame diff local e target-window ROI;
- economy default, budgets, OpenAI opcional/fallback Gemini;
- micro-batching conservador;
- approvals de uso único e stop durante execução/espera;
- ANT-257 agora impede input com frame/topologia obsoletos.

## Validações e limites conhecidos

- Unit tests/CI Linux não provam Win32, UIA, pycaw, WMI/CIM, áudio físico, DPI, multi-monitor, Playwright GUI/CDP real ou ScreenConnect.
- Um efeito sem estado observável suficiente permanece `verified=false`.
- E2E Windows físico continua centralizado no ANT-275.
- A extracção do `main.py` pode começar incrementalmente no ANT-259 depois da integração da PR #34.

## Próxima sequência

1. integrar PR #34 somente com a CI final do commit de documentação verde;
2. ANT-259 — `AgentOrchestrator` incremental;
3. ANT-260 — `ToolRouter` + `ExecutionEngine`;
4. ANT-261/262 — Policy Engine + aprovação humana vinculada;
5. ANT-263 — Provider Router completo;
6. ANT-264–267 — custo/Computer Use/ScreenConnect;
7. ANT-268+ — UI/voz/observabilidade/E2E/memória.
