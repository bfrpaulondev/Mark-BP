# Voice + Verification UX (ANT-271)

Estado: camada de mapeamento implementada e testada; ligação ao fluxo TTS
vivo é follow-up do runtime.

## O que é

`ui/voice_feedback.py` — módulo puro (sem Qt) entre o contrato
`ExecutionResult`/verifier e as frases de voz pt-PT. Fonte única de verdade:
o verifier. **NO SUCCESS SPEECH BEFORE VERIFIED SUCCESS.**

## Mapeamento

| Resultado | Categoria | Frase |
|---|---|---|
| `can_claim_success` (ok + delivered + verified, sem erro) | `verified_success` | "Concluído." |
| ok + delivered + **não** verified | `unverified_delivery` | "Executei a acção, mas não consegui confirmar o resultado." |
| qualquer falha | `failure` | "Não consegui concluir." |
| `requires_approval` | `waiting_approval` | "Preciso da tua aprovação para continuar." |
| cancelamento (factory) | `cancelled` | "Cancelado." — **nunca** "falhou" |
| retry/recuperação (factory) | `recovery` | "Não encontrei o esperado. Vou tentar novamente." |

Garantias:

- Fail-closed total: qualquer input malformado (`None`, strings, números)
  cai na frase de falha — lixo nunca soa a sucesso.
- Propriedade testada sobre **todas as 16 combinações booleanas**
  (ok/delivered/verified/erro/aprovação): só a combinação integralmente
  verificada produz `verified_success`.
- A camada não aprova, não cria grants, não simula confirmação.
- Frases são strings fixas — evidência/erros técnicos nunca vaziam para a
  voz (testado com segredo sintético no `evidence`).

## Consumo previsto (fora desta slice)

- Motores chamam `execution_result_to_voice_feedback(result)` e falam
  `phrase_pt` apenas quando `announce`; detalhe técnico vai para o Agent
  Control Center.
- **Barge-in/cancelamento do TTS** e progresso falhado ocasional: exigem
  coordenação com o fluxo de voz do runtime (main/antonella) — follow-up
  para o Principal Agent; esta slice não toca no motor de voz.
- Semântica de `ExecutionResult`/`can_claim_success` intocada (contrato do
  core consumido, não alterado).

## Testes

`tests/test_voice_feedback.py` — 10 testes Qt-free (correm em todas as
pernas da CI): categorias, propriedade 2⁵, fail-closed contra lixo,
privacidade de frases, imutabilidade.
