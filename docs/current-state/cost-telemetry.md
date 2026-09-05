# Cost Telemetry (ANT-264)

Estado: implementado no core desta branch; integração depende de CI/review final.

## Objectivo

Medir custo operacional de chamadas de IA sem transformar telemetria numa nova
superfície de dados privados. O módulo é process-local, bounded e content-free.

## O que é medido

Por tarefa:

- provider attempts;
- chamadas concluídas/falhadas;
- retries e fallback;
- latência acumulada;
- input/output/cached/reasoning tokens quando o provider os reporta;
- output tokens normalizados para billing por provider;
- chamadas poupadas e cache hits;
- custo conhecido e, apenas quando completo, custo estimado total.

Os adapters OpenAI Responses e Gemini Generate convertem metadata de usage para o
contrato provider-neutral `ProviderUsage`. Adapters legados que continuam a devolver
`str` permanecem compatíveis, mas a usage/custo desses pedidos fica explicitamente
indisponível.

## Custo financeiro

Antonella **não contém uma tabela de preços hardcoded**. Um preço desactualizado é
pior do que um custo desconhecido.

A estimativa só é feita quando existe a configuração explícita:

```json
{
  "model_pricing_usd_per_million_tokens": {
    "openai/model-name": {
      "input": 0.0,
      "output": 0.0,
      "cached_input": 0.0
    }
  }
}
```

Os valores são USD por 1.000.000 tokens. `cached_input` é opcional, mas se o provider
reportar tokens cached e não existir essa taxa, a chamada permanece com custo
`unknown` em vez de assumir que cached custa o mesmo que input normal.

`NaN`, infinito e valores negativos são rejeitados.

## Semântica de reasoning/thinking

A normalização evita dupla contagem:

- OpenAI Responses: `reasoning_tokens` é breakdown de `output_tokens`; o output
  facturável continua a ser o total de `output_tokens`.
- Gemini Generate: thinking (`thoughts_token_count`) é separado dos candidate/output
  tokens e entra adicionalmente no output facturável.

Isto fica encapsulado em `ProviderUsage.billable_output_tokens`, para que o cálculo
genérico não tenha de conhecer particularidades do SDK.

## Custo incompleto

Uma tarefa só publica `estimated_cost_usd` quando **todos os provider attempts** têm
usage e pricing suficientes para um cálculo defensável. Caso contrário:

- `estimated_cost_usd = null`;
- `cost_complete = false`;
- `known_cost_usd` mantém apenas a parcela efectivamente calculada;
- `cost_unknown_calls` mostra quantos attempts ficaram sem custo determinável.

Falhas HTTP/provider sem usage autoritativa ficam como custo desconhecido. Não é
assumido silenciosamente que uma falha foi gratuita.

## Privacidade

Não entram na telemetria:

- prompt/objective;
- screenshot/image bytes;
- response text;
- API keys/tokens;
- clipboard;
- conteúdo de campos.

`task_id` só é preservado quando parece um identificador técnico seguro. Texto
arbitrário é substituído por um digest SHA-256 truncado, impedindo usar IDs como canal
de armazenamento de conteúdo privado.

## Computer Use

Uma sessão Computer Use usa um único `telemetry_task_id` para todos os planning turns.
O estado da sessão publica apenas counters seguros:

- input/output/cached tokens;
- custo conhecido/estimado;
- `cost_complete`;
- task ID técnico.

Micro-batches determinísticos incrementam `calls_saved`.

## Limites desta fatia

- Gemini Live realtime ainda não alimenta esta telemetria;
- Local Fast Path ainda não incrementa `calls_saved` nesta fatia;
- não existe persistência histórica; o registry é intencionalmente bounded e local ao
  processo;
- preços comerciais não são descobertos automaticamente;
- billing real do provider continua a ser a fonte de verdade financeira.
