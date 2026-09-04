# Antonella — teste local rápido

O entrypoint canónico é `antonella.py`.

## Atualizar

```powershell
git checkout main
git pull origin main
python -m pip install uv==0.11.33
uv sync --locked
uv run playwright install chromium
```

## Configuração base

```powershell
$env:ANTONELLA_GEMINI_API_KEY="A_TUA_CHAVE"
```

OpenAI é opcional para o planner visual:

```powershell
$env:ANTONELLA_OPENAI_API_KEY="A_TUA_CHAVE"
```

Com `auto`, OpenAI é usado no Computer Use quando a chave existe; a voz continua no Gemini Live. Podes forçar `ANTONELLA_MODEL_PROVIDER_PREFERENCE="openai"` ou `"gemini"`.

O modo de custo default é:

```powershell
$env:ANTONELLA_COMPUTER_USE_COST_MODE="economy"
```

Outras opções: `balanced`, `quality`.

## Doctor e arranque

```powershell
uv run python scripts/doctor.py
uv run python antonella.py
```

## Smoke normal

Valida UI, voz, interrupção, texto, aplicações, browser, ficheiros e análise do monitor onde está a janela ativa.

## Multi-monitor

Coloca ScreenConnect num monitor secundário, torna-o foreground e pede para a Antonella olhar para essa janela. A resposta deve corresponder ao monitor secundário.

## Realtime Computer Use

Usa uma tarefa realmente visual:

```text
Antonella, usa Computer Use em modo económico no ScreenConnect e procura nesta aplicação onde posso ver as permissões deste utilizador. Não alteres nada.
```

Confirma no REGISTO: `live capture started`, monitor correto, provider/model, passos e conclusão/limite explícito.

Durante a execução:

```text
Antonella, pára o Computer Use.
```

Deve parar sem fechar a Antonella.

Num ambiente de teste, uma ação de gravação/permissões deve pausar para aprovação explícita.
