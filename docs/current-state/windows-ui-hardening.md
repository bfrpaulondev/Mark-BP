# Windows UI Hardening (ANT-270)

Estado: **fatia 1 de várias** — foco, acessibilidade, fail-closed de teclado
e multi-monitor. A validação final desta fatia deve correr contra a `main`
actual antes da integração.

## Fatia 1 (esta)

- **Acessibilidade**: nomes acessíveis nos botões só-ícone ("Abrir
  definições", "Interromper resposta", "Pausar ou retomar microfone") e nos
  botões do painel do agente; estilos `:focus` visíveis em todos os botões.
- **Tab order**: barra de comandos segue a ordem visual
  (comando → interromper → microfone); painel do agente mantém navegação por
  teclado entre aprovar → parar → fechar.
- **Fail-closed de teclado na aprovação**: `QDialog` promove `QPushButton` a
  alvos auto-default de Return/Enter, por isso os botões têm explicitamente
  `setAutoDefault(False)` + `setDefault(False)`. Além disso, o controlo de
  aprovação usa `ApprovalButton`, que consome `Return` e `Enter` mesmo quando
  o próprio botão tem foco. Assim essas teclas nunca chamam `approve_once()`.
  Acessibilidade por teclado é preservada: `Space` continua a activar o botão
  quando ele está focado e habilitado, e o clique explícito continua válido.
  O botão só fica habilitado em `awaiting_approval`.
- **Multi-monitor**: `AntonellaWindow` liga `windowHandle().screenChanged`
  no primeiro `showEvent` e recoloca a janela dentro da
  `availableGeometry()` do novo ecrã (clamp por `frameGeometry`).

## Testes

- `tests/test_windows_ui_hardening.py` — contratos de fonte, incluindo o
  guarda de constantes do módulo (regressão do bug `_BORDER_HOVER`) e as
  asserções `setAutoDefault(False)`/`setDefault(False)`.
- `tests/test_ui_widget_behaviour.py` — testes Qt reais (offscreen) para
  construção do diálogo, accessible names, tab order, approve não-default,
  Enter/Return fail-closed fora do botão de aprovação, clique explícito só em
  `awaiting_approval`, escape de HTML no histórico, hook de screen change,
  clamp para ecrã distante, janela maior que a geometria, coordenadas
  negativas, `screen=None` e janela já visível não movida.
- `tests/test_approval_keyboard_guard.py` — prova comportamental específica
  de segurança: com o botão de aprovação habilitado **e focado**, `Return` e
  `Enter` produzem zero aprovações; `Space` continua a produzir exactamente
  uma activação explícita.
- Nas pernas CI sem PyQt6 estes testes saltam de forma limpa; o job
  `ui-widget-tests` corre a suíte completa com PyQt6 offscreen em Windows
  3.11/3.12.

## Limitações

- O clamp é lógico (pontos Qt); DPI físico e scaling por monitor só são
  provados em ANT-275 (E2E Windows real).
- Testes Qt offscreen validam comportamento de widgets, não substituem
  renderização física em Windows.
- Fatias futuras: redimensionamento (min sizes por conteúdo), visual
  regression offscreen e performance de repaint do orb.
