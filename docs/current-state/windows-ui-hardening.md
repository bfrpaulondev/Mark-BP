# Windows UI Hardening (ANT-270)

Estado: **fatia 2 de várias** — sizing honesto, empty/error states, orbe
económico, histórico limitado e visual regression offscreen. A fatia 1
(foco, acessibilidade, fail-closed de teclado, multi-monitor) já foi
integrada com as correcções do Principal Agent (`ApprovalButton` incluído).

## Fatia 2 (esta)

- **Sizing honesto**: o `minimumSizeHint` real era 988×522 contra um mínimo
  declarado de 980×650 (o mínimo do orb de 360 px era inatingível com os
  painéis fixos). O orb passa a 320×320 (948 ≤ 980) e testes comportamentais
  garantem `minimumSizeHint ≤ declarado` e widgets dentro da viewport ao
  tamanho mínimo.
- **Orb económico**: o timer de 30 FPS liga/desliga com a visibilidade da
  janela (`showEvent`/`hideEvent`) — janela escondida não gasta CPU.
  NOT PHYSICALLY BENCHMARKED (offscreen não mede CPU real).
- **Histórico limitado**: `LogView` com `document().setMaximumBlockCount(400)`
  — a coluna de registo já não cresce sem limite (bounded memory).
- **Empty states (Agent Control Center)**: sem tarefa → "Nenhuma tarefa
  activa", sem provider/target → "—", sem timeline → placeholder explícito;
  nenhum dado inventado.
- **Error states**: a notice do painel segue a cor do estado (rosa =
  aprovação, vermelho = falha, verde = concluído) com mensagem humana em
  primeiro lugar; o detalhe técnico fica nos "Detalhes técnicos".
- **Acessibilidade**: descrições acessíveis nos botões de ícone (Esc/F4
  documentadas) e no toggle de detalhes técnicos.
- **Visual regression offscreen**: `scripts/ui_visual_states.py` renderiza
  os 15 estados `UiState` da janela + 4 casos do Agent Control Center
  (vazio/aprovação/falha/concluído) em PNGs determinísticos, conteúdo 100%
  sintético. O job `ui-widget-tests` gera os screenshots e publica-os como
  artefactos da CI. OFFSCREEN ≠ WINDOWS FÍSICO (documentado no script).

## Testes

- `tests/test_windows_ui_hardening.py` — contratos de fonte (fatias 1 e 2),
  incluindo o guarda de constantes do módulo (regressão `_BORDER_HOVER`) e
  as asserções `setAutoDefault(False)`/`setDefault(False)`.
- `tests/test_ui_widget_behaviour.py` — testes Qt reais (offscreen): além
  de toda a cobertura da fatia 1, mínimo declarado exequível, widgets na
  viewport ao mínimo, timer do orb segue a visibilidade, histórico limitado
  a 400 blocos, empty states sem dados inventados, cor da notice por
  estado e valores `None` sem crash.
- `tests/test_visual_states_contract.py` — cobertura total dos estados,
  casos do diálogo, escrita apenas de renders e limitação offscreen
  documentada.
- `tests/test_approval_keyboard_guard.py` (fatia 1, do Principal Agent)
  continua a passar sem alterações.
- Nas pernas CI sem PyQt6 os testes Qt saltam de forma limpa; o job
  `ui-widget-tests` corre a suíte completa com PyQt6 offscreen em Windows
  3.11/3.12.

## Limitações

- Clamp e sizing usam coordenadas lógicas Qt; DPI físico e scaling por
  monitor só são provados em ANT-275 (E2E Windows real).
- CPU do orbe: NOT PHYSICALLY BENCHMARKED — apenas eliminado o trabalho
  quando a janela está invisível.
- Fatias futuras: redimensionamento fino por conteúdo, acessibilidade de
  contraste e mais cobertura de visual regression.
