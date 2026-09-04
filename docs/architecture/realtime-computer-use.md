# Antonella — Realtime Computer Use

## Objetivo

Permitir que a Antonella execute tarefas visuais multi-etapa em aplicações desktop desconhecidas ou remotas sem transformar Computer Use no caminho padrão de todas as ações.

A regra de custo é obrigatória:

```text
API / ferramenta determinística
→ DOM / Windows UI Automation / ferramenta estruturada
→ processamento local
→ visão barata
→ modelo avançado
→ Realtime Computer Use
```

Computer Use é fallback, não substituto de ferramentas locais.

## Fluxo implementado

```text
desktop ativo ou monitor escolhido
   ↓
janela-alvo resolvida localmente quando possível
   ↓
captura local 10–20 FPS: janela ROI ou monitor
   ↓
detetor de alterações local
   ↓
frame relevante
   ↓
planner visual com orçamento
   ↓
1 ação OU micro-lote seguro
   ↓
execução local de rato/teclado
   ↓
captura continua localmente
   ↓
espera alteração real quando necessária
   ↓
planner recebe apenas o novo estado relevante
```

Frames sem alteração significativa não originam chamadas de modelo.

## Captura por janela — ROI local

Quando `target_window` é informado, a Antonella tenta resolver a geometria real dessa janela através de Win32, sem screenshot e sem chamada de modelo. Se a janela for encontrada e estiver visível, o Computer Use captura somente o rectângulo dessa aplicação.

Benefícios:

- menos pixels de origem antes da compressão;
- menos conteúdo irrelevante enviado ao planner visual;
- melhor resolução efectiva da aplicação-alvo dentro do mesmo orçamento de imagem;
- menor risco de incluir outras aplicações visíveis no monitor;
- coordenadas continuam correctas no desktop virtual porque cada frame guarda `left/top/width/height` da ROI.

A geometria é reavaliada periodicamente para acompanhar movimento/redimensionamento da janela. Se a janela deixar de ser resolvida, a captura volta automaticamente para o monitor escolhido/activo em vez de abortar a tarefa.

`capture_scope` indica `window` ou `monitor`. `capture_savings_pct` estima a percentagem de pixels de origem evitados em relação ao monitor dominante e aparece na telemetria do agente.

## Micro-batching seguro

O planner pode devolver até três ações numa única chamada, mas o runtime só mantém mais de uma quando a continuação é determinística e de baixo risco.

Exemplos permitidos:

- clicar num campo estável e escrever nesse campo;
- `Ctrl+A` num campo já focado e escrever a substituição;
- `Tab` para o próximo campo conhecido e escrever.

O runtime força nova observação antes de scroll, segundo clique por coordenadas, Enter/Return, waits, ações medium/high risk ou qualquer continuação que dependa de novos pixels. O modelo não pode alargar esta allowlist.

Cada ação extra realmente executada no micro-lote incrementa `saved_model_calls`, tornando a poupança visível na telemetria/HUD.

## Multi-monitor

A captura usa o desktop virtual do sistema. Por defeito segue o monitor que contém o centro da janela foreground. Também é possível escolher explicitamente `monitor 1`, `ecrã 2`, `segundo monitor`, `screen 3` ou `todos os ecrãs`.

Coordenadas negativas são suportadas. O planner trabalha em coordenadas relativas à imagem e o actuator converte-as para coordenadas reais do desktop virtual.

Uma ROI de janela pode atravessar dois monitores; o runtime mantém coordenadas do desktop virtual e associa a captura ao monitor com maior área visível da janela.

## Windows UI Automation

Antes de recorrer a pixels em aplicações Windows normais, a Antonella pode usar `windows_ui_automation` para listar janelas e operar controlos expostos por UIA, como `Button`, `Edit`, `TabItem`, `ListItem` e `MenuItem`.

Esta camada não usa tokens visuais. Interfaces remotas como ScreenConnect podem expor apenas uma superfície gráfica; nesses casos o router pode escalar para Realtime Computer Use.

## Modos de custo

- `economy`: até 6 chamadas, 12 passos, 10 FPS local, frame até 960×540.
- `balanced`: até 12 chamadas, 20 passos, 15 FPS local, frame até 1280×720.
- `quality`: até 20 chamadas, 30 passos, 20 FPS local, frame até 1600×900.

O FPS é local; não significa que todos esses frames são enviados à cloud.

## Providers

Quando `ANTONELLA_OPENAI_API_KEY` está configurada e a preferência está em `auto`, o planner visual usa OpenAI: economy → `gpt-5.6-luna`, balanced → `gpt-5.6-terra`, quality → `gpt-5.6-sol`. Sem chave OpenAI, há fallback Gemini.

A voz principal continua no Gemini Live. Provider de planeamento e provider de voz são responsabilidades independentes.

## Segurança

O loop pausa antes de ações que aparentem apagar/remover dados, enviar/publicar/submeter, alterar permissões ou segurança, usar credenciais, fazer operações financeiras ou confirmar mudanças irreversíveis. A aprovação é de uso único. `stop` interrompe também uma espera de aprovação.

Micro-batches não atravessam ações de risco: qualquer passo medium/high risk encerra a cadeia local e força nova decisão/observação.

## Plugin

A integração usa `realtime_computer_use`, evitando aumentar o monólito `main.py`. Ações: `start`, `status`, `stop`, `approve`.

`display_manager` resolve e lista ecrãs sem modelo. `windows_ui_automation` oferece o caminho estruturado Windows antes de Computer Use.

## Limitações atuais

Ainda não existe persistência cloud de runs/checkpoints, OCR local especializado, Policy Engine completo ou sobrevivência a reinício. O micro-batching é deliberadamente conservador: só elimina chamadas quando a sequência pode ser executada sem depender semanticamente de uma nova imagem. A ROI por janela depende de a aplicação possuir uma janela Win32 visível resolvível pelo título; caso contrário, o fallback continua a ser a captura do monitor.
