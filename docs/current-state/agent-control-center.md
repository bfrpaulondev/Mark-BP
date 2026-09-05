# Agent Control Center (ANT-269)

Estado: implementado (evolução da superfície existente), sem validação física em Windows.

## Âmbito

Evolução de `ui/agent_control.py` consumindo **apenas** os campos publicados
por `SessionState.as_dict()` (`core/computer_use/contracts.py`). Sem alterações
no core/Computer Use (área do lote de execução) e sem ler logs ou inferir estado.

## O que mudou

- **Progresso honesto** — a sessão não publica total de passos; enquanto
  activa, a barra é indeterminada (`setRange(0,0)`), verde em `done`,
  vermelha em `failed`. Nunca uma percentagem inventada.
- **Janela alvo** — novo stat `target_window` (antes não era mostrada).
- **Custo** — mostra o `cost_mode` publicado (Económico/Equilibrado/Premium).
  Estimativa de custo ainda não existe no runtime (chega com ANT-264); a UI
  não inventa valores — sem literal `$` no painel, travado por teste.
- **Timeline** — histórico renderizado como linhas estruturadas
  `NN · acção · detalhe`, com escape de HTML do conteúdo do runtime.
- **Progressive disclosure** — evidência técnica de captura (`capture_scope`,
  `capture_savings_pct`, `visual_updates`, `batched_actions`) fica oculta
  atrás de "Detalhes técnicos" (estado explícito, não `isVisible()`, que
  é False para filhos de diálogo não mostrado).
- **Stop/Approve contextuais** — o botão de aprovação passa a nomear o passo
  pendente (`APROVAR: <last_action[:38]>`); Enter nunca está ligado à
  aprovação (fail-closed no teclado); lógica `stop()`/`approve_once()` intacta.

## Contratos travados por testes

`tests/test_agent_control_center_evolution.py`:

- **Contrato cruzado**: toda a chave `status.get("...")` no painel tem de
  existir no `as_dict()` do core — apanha drift e typos (apanhou um campo
  inventado durante o desenvolvimento desta slice).
- Progresso sem total fabricado; custo sem literal `$`; histórico escapado;
  disclosure oculto por omissão; Enter nunca ligado a aprovação.

O contrato antigo (`test_agent_control_center_contract.py`) continua a passar
sem alterações.

## Limitações

- Estimativa de custo e campos de recovery ainda não existem no `status()`;
  quando o lote de execução os publicar, é wiring de uma linha no painel.
- Validação física (DPI, foco, dialog real em Windows) não feita — ANT-275.
