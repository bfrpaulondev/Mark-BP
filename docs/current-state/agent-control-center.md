# Agent Control Center (ANT-269)

Estado: implementado (evolução da superfície existente), sem validação física em Windows.

## Âmbito

Evolução de `ui/agent_control.py` consumindo **apenas** os campos publicados
por `SessionState.as_dict()` (`core/computer_use/contracts.py`). Sem alterações
no core/Computer Use e sem ler logs ou inferir estado.

## O que mudou

- **Progresso honesto** — a sessão não publica total de passos; enquanto
  activa, a barra é indeterminada (`setRange(0,0)`), verde em `done`,
  vermelha em `failed`. Nunca uma percentagem inventada.
- **Janela alvo** — novo stat `target_window`.
- **Custo** — usa a telemetria ANT-264 já publicada pelo runtime:
  `estimated_cost_usd` apenas quando `cost_complete=true`; quando existe só
  uma parcela defensável, mostra `known_cost_usd` como limite inferior
  marcado `parcial`; sem telemetria suficiente, mostra apenas o modo
  Económico/Equilibrado/Qualidade. A UI não cria preços nem custos próprios.
- **Timeline** — histórico renderizado como linhas estruturadas
  `NN · acção · detalhe`, com `html.escape` antes de inserir conteúdo em HTML.
- **Progressive disclosure** — evidência técnica de captura (`capture_scope`,
  `capture_savings_pct`, `visual_updates`, `batched_actions`) fica oculta
  atrás de "Detalhes técnicos".
- **Stop/Approve contextuais** — o botão de aprovação nomeia o passo
  pendente (`APROVAR: <last_action[:38]>`); Enter nunca está ligado à
  aprovação; a lógica `stop()`/`approve_once()` permanece intacta.

## Contratos travados por testes

`tests/test_agent_control_center_evolution.py` cobre:

- todas as chaves `status.get("...")` usadas pelo painel têm de existir em
  `SessionState.as_dict()`;
- progresso sem total fabricado;
- custo apenas a partir dos campos publicados por ANT-264 ou do modo;
- escape completo do histórico antes do HTML;
- detalhes técnicos ocultos por omissão;
- Enter não ligado à aprovação.

O contrato anterior `tests/test_agent_control_center_contract.py` continua
compatível.

## Limitações

- Campos específicos de recovery/retry ainda não são publicados no `status()`;
  serão ligados quando o runtime os expuser.
- O valor financeiro é uma estimativa baseada na tabela de preços configurada;
  billing do provider continua a ser a fonte financeira definitiva.
- Validação física de DPI, foco e diálogo real em Windows continua no ANT-275.
