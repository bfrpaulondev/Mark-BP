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

OpenAI é opcional para especialista e planner visual:

```powershell
$env:ANTONELLA_OPENAI_API_KEY="A_TUA_CHAVE"
```

Com `auto`, OpenAI pode ser usado pelo especialista/Computer Use quando a chave existe; a voz continua no Gemini Live. Podes preferir `ANTONELLA_MODEL_PROVIDER_PREFERENCE="openai"` ou `"gemini"`.

O modo de custo default é:

```powershell
$env:ANTONELLA_COMPUTER_USE_COST_MODE="economy"
```

Outras opções: `balanced`, `quality`.

Estas preferências também podem ser alteradas no botão `•••`. As chaves introduzidas pelo centro de preferências ficam apenas na sessão actual do processo; para persistência usa variáveis de ambiente `ANTONELLA_*`.

## Doctor e arranque

```powershell
uv run python scripts/doctor.py
uv run python antonella.py
```

## Smoke normal

Valida:

1. UI Antonella abre com orb, CPU/MEM/NET/CORE STATUS, REGISTO, drop-zone e command bar;
2. faixa de runtime mostra `LIVE`, `ESPECIALISTA`, `CUSTO`, `VISÃO` e `AGENTE`;
3. `Ctrl+K` foca a caixa `Diz alguma coisa…`;
4. voz, interrupção, mute, texto, aplicações, browser e ficheiros continuam funcionais;
5. `•••` abre Preferências e não mostra valores das chaves já configuradas;
6. clicar em `CUSTO` ou `ESPECIALISTA` abre Preferências;
7. análise visual segue por defeito o monitor onde está a janela foreground.

## Browser real — navegação entre abas com verificação

Abre Chrome, Edge ou Firefox normalmente com pelo menos duas abas diferentes e deixa o browser visível.

Testa por voz:

```text
Antonella, vai para a próxima aba.
Antonella, volta para a aba anterior.
Antonella, lista as abas do Chrome.
Antonella, muda para a aba do GitHub.
```

Requisitos:

- para navegação entre abas do browser real deve aparecer `Verified control` no REGISTO;
- `browser_control action=switch` não deve ser usado como navegação de abas;
- a Antonella só pode dizer que mudou de aba quando o resultado tiver `verified=true`;
- se não houver browser visível, se existirem vários browsers ambíguos ou se o Windows não permitir verificar a mudança, a Antonella deve dizer que não conseguiu confirmar — nunca afirmar `feito`;
- quando existirem vários browsers, testa `no Chrome`, `no Edge`, etc.

## Rato — movimento verificável

Testa:

```text
Antonella, mexe o rato um pouco.
Antonella, move o rato 100 pixels para a direita.
```

A posição física do cursor deve mudar. O resultado de `verified_desktop_control` deve indicar `verified=true` e incluir posição anterior, alvo e posição final. Se `verified=false`, a Antonella não pode afirmar que moveu o rato.

## Multi-monitor

Coloca ScreenConnect num monitor secundário, torna-o foreground e pede para a Antonella olhar para essa janela. A resposta deve corresponder ao monitor secundário.

Testa também selecção explícita:

```text
Antonella, que ecrãs tenho?
Antonella, usa o segundo monitor.
Antonella, usa o ecrã 3 para esta tarefa.
```

Devem funcionar aliases como `ecrã 2`, `monitor dois`, `segundo monitor`, `screen 3` e `todos os ecrãs`.

## Windows UI Automation — caminho sem visão

Numa aplicação Windows normal, pede primeiro uma tarefa de navegação simples. Quando a aplicação expõe controlos UIA, a Antonella deve preferir `windows_ui_automation` a screenshots/Computer Use.

O objectivo é confirmar que botões, campos, tabs e listas acessíveis podem ser lidos/accionados sem chamadas de visão.

## Realtime Computer Use

Usa uma tarefa realmente visual:

```text
Antonella, usa Computer Use em modo económico no ScreenConnect e procura nesta aplicação onde posso ver as permissões deste utilizador. Não alteres nada.
```

Confirma no REGISTO: `live capture started`, monitor correcto, provider/model, passos e conclusão/limite explícito.

O `AGENTE` do HUD deve mudar de estado durante a tarefa. Clica nele ou usa `Ctrl+Shift+A` para abrir o painel de controlo.

No painel do agente confirma:

- objectivo actual;
- passo;
- chamadas IA;
- chamadas poupadas por micro-batching;
- ecrã;
- provider/model;
- histórico recente;
- `PARAR AGENTE`;
- `APROVAR 1 PASSO` disponível apenas quando a sessão realmente aguarda aprovação.

Durante a execução também continua válido:

```text
Antonella, pára o Computer Use.
```

Deve parar sem fechar a Antonella.

Num ambiente de teste, uma ação de gravação/permissões deve pausar para aprovação explícita. A aprovação é apenas para o passo pendente.

## Teste de custo / micro-batching

Usa uma interface de teste com um campo de texto visível e pede uma tarefa que exija focar o campo e escrever. Quando o planner conseguir devolver um micro-lote seguro, `saved_model_calls` deve aumentar sem eliminar a verificação visual posterior.

Não deve haver batching entre dois clicks por coordenadas, após scroll, Enter/Return ou em ações medium/high risk.
