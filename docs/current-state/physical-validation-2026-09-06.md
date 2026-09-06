# ANT-275 — primeira validação física Windows (2026-09-06)

A primeira execução física em hardware do utilizador foi concluída com o gate `ANTONELLA_E2E_PHYSICAL=1`.

Resultado observado:

- PASS: 10
- FAIL: 8
- SKIPPED: 20
- NOT AVAILABLE: 1
- NOT PHYSICALLY TESTED: 0

Passaram fisicamente: abertura/foco da fixture, filesystem, Wi-Fi, browser tabs/SPA/popup/download, multi-monitor e DPI.

Falharam: UIA inspect/click/set-text, mouse move/click, keyboard, volume e mute. O primeiro runner só preservava `AttributeError`, sem mensagem, portanto a causa exacta ainda não pode ser afirmada.

Brightness ficou `NOT AVAILABLE` por ausência de WMI. Casos sem executor permanecem `SKIPPED` e não contam como PASS.

A validação interactiva de voz não começou: o processo Antonella terminou antes dos passos interactivos. O runner anterior não preservava stderr do processo, logo a causa de arranque ainda não pode ser afirmada.

Follow-up: o harness passa a guardar apenas detalhes técnicos sanitizados e bounded, versões conhecidas de dependências e diagnóstico sanitizado de early-exit da Antonella. Nenhum áudio, transcript, prompt, token, cookie, screenshot ou caminho local deve ser persistido pelo diagnóstico.
