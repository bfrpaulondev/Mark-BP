# Voice + Verification UX (ANT-271)

Estado: camada de mapeamento implementada e testada; ligação ao fluxo TTS vivo é follow-up do runtime.

## O que é

`ui/voice_feedback.py` é um módulo puro (sem Qt) entre o contrato `ExecutionResult`/verifier e as frases de voz pt-PT.

Fonte única de verdade: o verifier. **NO SUCCESS SPEECH BEFORE VERIFIED SUCCESS.**

## Fronteira de confiança

A camada de voz aceita sucesso apenas quando recebe uma instância real de `ExecutionResult` do runtime. Dicionários/mappings com flags como `ok`, `delivered` ou `verified` são tratados como input não confiável e resultam em feedback de falha.

Isto impede um provider/model/tool de fabricar uma fala de sucesso apenas definindo `verified=true` num payload.

## Mapeamento

| Resultado | Categoria | Frase |
|---|---|---|
| `can_claim_success` | `verified_success` | `Concluído.` |
| ok + delivered + não verified | `unverified_delivery` | `Executei a acção, mas não consegui confirmar o resultado.` |
| qualquer falha | `failure` | `Não consegui concluir.` |
| `requires_approval` | `waiting_approval` | `Preciso da tua aprovação para continuar.` |
| cancelamento | `cancelled` | `Cancelado.` |
| retry/recuperação | `recovery` | `Não encontrei o esperado. Vou tentar novamente.` |

Garantias:

- qualquer input que não seja `ExecutionResult` falha fechado;
- só `can_claim_success` anuncia sucesso;
- a camada não aprova, não cria grants e não simula confirmação;
- evidência/erros técnicos nunca entram nas frases;
- propriedade testada sobre as **32 combinações booleanas** de ok/delivered/verified/error/approval.

## Fora desta slice

- wiring no TTS vivo;
- barge-in/cancelamento real da fila de fala;
- progresso falado ocasional;
- validação física de áudio em Windows.

Esses pontos continuam a pertencer ao runtime/ANT-275 e não são simulados por esta camada.
