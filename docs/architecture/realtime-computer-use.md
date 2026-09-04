# Antonella — Realtime Computer Use

## Objetivo

Permitir que a Antonella execute tarefas visuais multi-etapa em aplicações desktop desconhecidas ou remotas sem transformar Computer Use no caminho padrão de todas as ações.

A regra de custo é obrigatória:

```text
API / ferramenta determinística
→ DOM / UI Automation / ferramenta estruturada
→ processamento local
→ visão barata
→ modelo avançado
→ Realtime Computer Use
```

Computer Use é fallback, não substituto de ferramentas locais.

## Fluxo implementado

```text
desktop ativo
   ↓
captura local multi-monitor 10–20 FPS
   ↓
detetor de alterações local
   ↓
frame relevante
   ↓
planner visual com orçamento
   ↓
ação de rato/teclado
   ↓
captura continua localmente
   ↓
espera alteração real
   ↓
planner recebe apenas o novo estado relevante
```

Frames sem alteração significativa não originam chamadas de modelo.

## Multi-monitor

A captura usa o desktop virtual do sistema e seleciona o monitor que contém o centro da janela foreground. Coordenadas negativas são suportadas. O planner trabalha em coordenadas relativas à imagem e o actuator converte-as para coordenadas reais do desktop virtual.

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

## Plugin

A integração usa `realtime_computer_use`, evitando aumentar o monólito `main.py`. Ações: `start`, `status`, `stop`, `approve`.

## Limitações desta primeira entrega

Ainda não existe persistência cloud de runs/checkpoints, Windows UI Automation integrada ao router, OCR local especializado, Policy Engine completo ou sobrevivência a reinício. O planner ainda faz uma chamada de visão por decisão relevante. Esta é uma primeira slice sobre o runtime atual.
