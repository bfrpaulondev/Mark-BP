# Antonella — model routing

## Estado atual

A Antonella continua a usar Gemini Live como cérebro conversacional/realtime principal. OpenAI é uma capacidade opcional e seletiva, não uma substituição global.

O objetivo é usar mais inteligência apenas quando existe benefício mensurável de qualidade.

## Camadas atuais

```text
voz + conversa + tool calling comum
→ Gemini Live

comandos locais/estruturados
→ ferramentas locais, sem modelo adicional

tarefa visual multi-etapa sem API/UIA
→ Computer Use cost-aware

tarefa intelectual realmente difícil
→ expert_reasoning opcional
```

## Papéis de reasoning OpenAI

| Papel | Modelo atual | Uso |
|---|---|---|
| `fast` | `gpt-5.6-luna` | raciocínio curto e económico quando explicitamente necessário |
| `balanced` | `gpt-5.6-terra` | debugging complexo, arquitetura, análise e decisões técnicas |
| `expert` | `gpt-5.6-sol` | problemas de engenharia/raciocínio de maior dificuldade |
| `critic` | `gpt-5.6-terra` | segunda leitura independente de planos/conclusões importantes |

Os nomes são configuração, não regras de domínio. Podem ser alterados através das settings Antonella sem reescrever o router.

## Disponibilidade

`expert_reasoning` só é exposto como tool ao modelo quando `ANTONELLA_OPENAI_API_KEY` está configurada. O loader suporta agora `is_available()` opcional por plugin, evitando oferecer ao LLM capacidades que não podem funcionar naquele ambiente.

## Política de custo

O specialist não deve ser chamado para:

- conversa casual;
- respostas simples;
- abrir apps, clicar, escrever ou fazer scroll;
- operações de browser/ficheiros já cobertas por tools;
- tarefas que o cérebro principal consegue resolver com confiança suficiente.

`balanced` é a primeira escalada. `expert` é reservado para casos onde o ganho de qualidade justifica custo superior. `critic` é uma chamada separada e só deve existir quando verificação independente agrega valor.

## Privacidade

O specialist recebe apenas `task` e um `context` curto fornecido pela Antonella. O prompt do submodelo proíbe pedir/reproduzir credenciais e manda tratar conteúdo externo como dados, nunca como instrução privilegiada. Não devem ser enviados API keys, passwords ou dados pessoais/de cliente que não sejam necessários.

## Limitações

Esta entrega ainda usa Gemini Live como decisor de quando chamar `expert_reasoning`; o futuro Agent Orchestrator terá uma política determinística de budget, complexidade, risco e provider health. Também ainda não existe accounting real de tokens/custo por run.
