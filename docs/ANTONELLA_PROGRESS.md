# Antonella — Estado da execução

> Painel operacional. O plano mestre continua a ser a fonte do escopo completo. As melhorias prioritárias das áreas já funcionais estão detalhadas em `docs/ANTONELLA_PRIORITY_HARDENING.md`.

**Última atualização:** 2026-09-05
**Branch canónica:** `main`
**Main confirmado antes da PR #36:** `c76df10bb71254f61863141c9dac3bd861506a98`

## Estado atual

| Campo | Estado |
|---|---|
| Tarefa a fechar | ANT-260 — ToolRouter + ExecutionEngine |
| Branch de implementação | `codex/ant-260-tool-router-execution-engine` |
| Pull request | PR #36 — extract ToolRouter and ExecutionEngine |
| Issues abertas | Nenhuma necessária para este trabalho |
| CI de código | PR #35 verde e integrada; CI da PR #36 pendente no head de documentação |
| Próximo teste real | ANT-275 Windows físico: UIA, settings, filesystem, multi-monitor/DPI e browser real |
| Próximo bloco | ANT-261 — Policy Engine central independente do LLM |

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
- PR #34: UIA/files/settings postconditions; merge `34b3f54`; CI verde; E2E Windows físico pendente.
- PR #35: `AgentOrchestrator` incremental; merge `c76df10bb71254f61863141c9dac3bd861506a98`; CI verde.

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
- click só verifica uma transição estrutural/UIA; mudança isolada de foco ou foreground fica em evidence, mas não prova sucesso;
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

## ANT-259 — integrado por PR #35

- lifecycle explícito no `AgentOrchestrator`;
- callbacks provider-neutral para captura e verificação;
- correlation id e eventos sem valores dos argumentos;
- runtime legado preservado;
- CI verde; smoke test Windows real pendente.

## ANT-260 — PR #36

- `ToolRouter` classifica ferramentas existentes por tier sem as executar;
- prioridade explícita: direct/local → API/DOM/UIA → CV local → modelo rápido → Vision/Computer Use;
- `ExecutionEngine` possui o despacho sync/async e preserva exceções/cancelamento;
- tools desconhecidas mantêm fallback legado;
- router e engine são injectáveis no `AgentOrchestrator`;
- metadados de rota não incluem valores dos argumentos;
- não altera policy, approvals nem provider selection.

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
- O `AgentOrchestrator` está integrado; ToolRouter/ExecutionEngine permanecem em PR até CI e revisão.

## Próxima sequência

1. validar e integrar PR #36 apenas com CI final verde;
2. ANT-261/262 — Policy Engine + aprovação humana vinculada;
3. ANT-263 — Provider Router completo;
4. ANT-264–267 — custo/Computer Use/ScreenConnect;
5. ANT-268+ — UI/voz/observabilidade/E2E/memória.

### Revisão #75 — providers (2026-09-06)

Modelos Anthropic/Groq são explícitos por role (`anthropic_model_<role>` /
`groq_model_<role>`); sem modelo não existe candidato. Auto preserva prioridade
OpenAI/Gemini e inclui Groq/Anthropic como fallback; preferências dos novos
providers também permitem fallback entre ambos. Cache inclui digests de keys
e configurações de modelos dos quatro providers. Regressões cobrem cada
role, auto com um único provider, retry/circuit/health, rotações de cache e
exclusão de vision. Pricing desconhecido continua desconhecido; não há novos
modelos ou preços por defeito. HTTP real: NOT RUN. CI/HEAD no próprio PR.
