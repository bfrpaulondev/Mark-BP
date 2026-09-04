# ADR-0001 — Identidade oficial da Antonella

- Estado: aceite
- Data: 2026-09-04
- Tarefa: ANT-000
- Responsável pelo produto: Bruno Paulon

## Contexto

O repositório nasceu como fork de `FatihMakes/Mark-LII` e a implementação herdada ainda usa os nomes Mark, JARVIS e referências visuais associadas. A evolução planeada é um assistente pessoal próprio, com identidade, arquitetura e regras de segurança independentes.

Uma substituição global imediata criaria risco de regressão em imports, nomes de classes, ficheiros de configuração, textos da interface e fluxos de instalação. A identidade nova deve ser adotada sem fingir que o legado já foi migrado.

## Decisão

O nome oficial do produto é **Antonella**.

Os identificadores técnicos novos seguem estas convenções:

| Elemento | Identificador |
|---|---|
| Produto | `Antonella` |
| Namespace Python | `antonella` |
| Cliente desktop | `antonella-desktop` |
| API/orquestrador | `antonella-api` |
| Worker de skills | `antonella-worker` |
| Broker local | `antonella-local-broker` |
| Skills | `antonella-skill-<slug>` |
| Variáveis de ambiente próprias | prefixo `ANTONELLA_` |

A partir desta decisão:

1. Código e documentação novos não introduzem Mark, JARVIS ou referências a Iron Man, exceto para identificar claramente o legado ou a sua proveniência.
2. Os nomes herdados permanecem temporariamente onde a alteração possa modificar o comportamento atual.
3. Cada renomeação do legado será feita numa tarefa própria, com teste de regressão e caminho de rollback.
4. A identidade visual, textual e sonora futura será original.
5. O nome do repositório pode permanecer `Mark-BP` durante a estabilização; uma eventual mudança será uma operação separada depois de links, deploys e integrações estarem inventariados.

## Consequências

- A documentação passa a distinguir explicitamente o protótipo herdado do produto alvo.
- Não será feita uma refatoração massiva apenas para mudar nomes.
- Novos pacotes e serviços já nascem com nomenclatura estável da Antonella.
- Textos e recursos herdados serão removidos gradualmente antes de qualquer lançamento público próprio.

## Verificação

A decisão é considerada aplicada quando:

- o roadmap referencia este ADR;
- o README identifica a transição sem afirmar que o legado já foi migrado;
- novos trabalhos usam os identificadores definidos acima;
- nenhuma alteração funcional é incluída neste ADR.
