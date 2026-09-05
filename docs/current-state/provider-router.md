# Provider Router (ANT-263)

Estado: implementação em review; não substitui Gemini Live realtime.

## Escopo

`core/provider_router.py` cria uma fronteira provider-neutral para chamadas especialistas de texto e visão:

```text
role/capability
→ candidate plan
→ preferred provider
→ bounded retry
→ fallback provider
→ circuit breaker
→ ProviderResult
```

Roles suportados nesta fatia:

- `fast`
- `balanced`
- `expert`
- `critic`
- `vision`

Providers concretos nesta fatia:

- OpenAI Responses API;
- Gemini Generate Content.

A arquitectura aceita adapters por protocolo; Claude/Groq não são adicionados nesta PR porque ainda não existem configuração/dependência/contratos aprovados no projecto.

## Regras

- `model_provider_preference` continua a significar **preferir**, conforme a UI existente; se ambos os providers estiverem configurados, fallback cross-provider permanece possível.
- `fast` em modo automático prefere Gemini e depois OpenAI; roles mais exigentes preferem OpenAI e depois Gemini.
- erros transitórios (`timeout`, conexão, 429/5xx) podem receber retry curto e abrir circuit breaker;
- auth inválida não recebe retry imediato;
- rejeição do próprio pedido (400/safety) não degrada globalmente a saúde do provider;
- resposta vazia não é registada como sucesso;
- health/circuit state é mantido em memória entre chamadas especialistas enquanto configuração/chaves/modelos não mudarem;
- rotação de uma API key reconstrói o router sem expor a chave em metadata.

## Privacidade

`ProviderAttempt.safe_metadata()` e `ProviderResult.safe_metadata()` contêm apenas provider/model/role/capability/latência/estado de tentativa/fallback.

Não contêm:

- prompt;
- imagem;
- API key;
- conteúdo de resposta;
- cookies/storage.

O fingerprint interno de configuração usa digest das chaves apenas para detectar rotação; o valor bruto não é publicado nem devolvido.

## Computer Use

`ComputerUsePlanner` passa a usar o mesmo Provider Router para visão, mantendo `core/cost_router.py` como fonte dos budgets de Economy/Balanced/Quality.

Mapeamento:

- economy → `fast`;
- balanced → `balanced`;
- quality → `expert`.

A decisão de provider do cost router é preservada como preferência primária. Se esse provider falhar, o router pode usar o outro provider configurado. A sessão expõe o provider/model realmente usados e conta requests reais de provider, incluindo fallback.

Para Computer Use é usado no máximo um attempt por provider em cada turno visual; re-observar/replanear um frame novo é preferível a repetir várias vezes a mesma screenshot.

## Expert Reasoning

`expert_reasoning` deixa de estar preso à OpenAI. Continua disponível com OpenAI ou Gemini e usa um router de processo partilhado, preservando circuit breaker entre chamadas.

O `core/model_router.py` OpenAI-only permanece por compatibilidade com testes/callers antigos nesta fatia; não é a nova fronteira canónica.

## Limites

- Gemini Live continua a ser o runtime realtime de voz; não é migrado nesta tarefa.
- custo financeiro/tokens por chamada entra no ANT-264; ANT-263 expõe tentativas e latência necessárias para essa telemetria, mas não inventa preços/tokens.
- retry/fallback prova comportamento por unit tests e CI; não constitui teste de disponibilidade real dos serviços externos.
- provider-specific SDK/API changes continuam a exigir validação real fora do CI dependency-light.
