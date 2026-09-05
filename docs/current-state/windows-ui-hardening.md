# Windows UI Hardening (ANT-270)

Estado: **fatia 1 de várias** — foco, acessibilidade, fail-closed de teclado
e multi-monitor. Base reconciliada com a `main` que já inclui o ANT-269
revisto e o ANT-264 (telemetria de custo).

## Fatia 1 (esta)

- **Acessibilidade**: nomes acessíveis nos botões só-ícone ("Abrir
  definições", "Interromper resposta", "Pausar ou retomar microfone") e nos
  botões do painel do agente; estilos `:focus` visíveis em todos os botões.
- **Tab order**: barra de comandos segue a ordem visual
  (comando → interromper → microfone); painel do agente segue o gradiente
  de risco (aprovar → parar → fechar).
- **Fail-closed de teclado na aprovação**: `QDialog` promove QPushButtons a
  alvos auto-default de Return/Enter; o botão de aprovação (e os restantes)
  tem explicitamente `setAutoDefault(False)` + `setDefault(False)`. Provado
  por testes comportamentais: Return/Enter ao nível do diálogo, com foco no
  histórico e noutros botões **nunca** chamam `approve_once()`; o clique
  explícito só funciona com a sessão em `awaiting_approval`.
- **Multi-monitor**: `AntonellaWindow` liga `windowHandle().screenChanged`
  no primeiro `showEvent` e recoloca a janela dentro da
  `availableGeometry()` do novo ecrã (clamp por `frameGeometry`).

## Testes

- `tests/test_windows_ui_hardening.py` — contratos de fonte, incluindo o
  guarda de constantes do módulo (regressão do bug `_BORDER_HOVER`) e as
  asserções `setAutoDefault(False)`/`setDefault(False)`.
- `tests/test_ui_widget_behaviour.py` — **testes Qt reais (offscreen)**:
  construção do diálogo, accessible names, tab order, approve não-default,
  Enter/Return fail-closed (histórico, diálogo e outro botão), clique
  explícito só em `awaiting_approval`, escape de HTML no histórico, hook de
  screen change, clamp para ecrã distante, janela maior que a geometria,
  coordenadas negativas, `screen=None` e janela já visível não movida.
  Nas pernas CI sem PyQt6 os testes saltam limpos (`skipped=13`); o job
  novo `ui-widget-tests` corre-os com PyQt6 offscreen em Windows 3.11/3.12.

## Limitações

- O clamp é lógico (pontos Qt); DPI físico e scaling por monitor só são
  provados em ANT-275 (E2E Windows real).
- Fatias futuras: redimensionamento (min sizes por conteúdo), visual
  regression offscreen, performance de repaint do orb.
