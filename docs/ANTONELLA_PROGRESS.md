# Antonella — Estado da execução

> Painel operacional do trabalho já realizado e do próximo passo. O [plano mestre](ANTONELLA_MASTER_ROADMAP.md) continua a ser a fonte do escopo completo e dos critérios `ANT-*`.

**Última atualização:** 2026-09-04

**Branch canónica:** `main`

**Responsável pelo produto:** Bruno Paulon

## Estado atual

Esta tabela descreve o estado que deve existir na `main`. Durante a revisão de uma atualização deste documento, a respetiva branch e pull request são exceções transitórias.

| Campo | Estado |
|---|---|
| Tarefa ativa | Nenhuma após a integração deste painel |
| Pull requests abertas | Nenhuma após a integração deste painel |
| Issues abertas | Nenhuma |
| Próxima tarefa recomendada | `ANT-013` — configuração tipada |
| Tarefa seguinte | `ANT-014` — remover instalações automáticas em runtime |
| Última CI integrada | [PR #4 — CI concluída com sucesso](https://github.com/bfrpaulondev/Mark-BP/actions/runs/33880329607) |

## Regras operacionais

- Manter no máximo uma branch de implementação e uma pull request ativa para o trabalho do Codex, salvo autorização explícita para trabalho paralelo.
- Atualizar este painel na mesma pull request de cada entrega relevante.
- Apagar branches integradas ou substituídas quando já não contiverem trabalho único.
- Não criar issues para repetir tarefas que já existem no plano mestre.
- Criar uma issue apenas por decisão explícita de Bruno ou para um bloqueio real que precise de discussão independente.
- Não marcar uma tarefa como concluída sem evidência verificável no repositório, nos testes ou na CI.

## Entregas integradas

| Entrega | Tarefas | Resultado | Evidência |
|---|---|---|---|
| [PR #1](https://github.com/bfrpaulondev/Mark-BP/pull/1) | Planeamento | Plano mestre de transformação criado | [`ANTONELLA_MASTER_ROADMAP.md`](ANTONELLA_MASTER_ROADMAP.md) |
| [PR #2](https://github.com/bfrpaulondev/Mark-BP/pull/2) | `ANT-000`, `ANT-001`, `ANT-005` | Identidade, inventário técnico e política de contribuição | [ADR de identidade](adr/0001-antonella-project-identity.md), [inventário](current-state/legacy-inventory.md) e [`CONTRIBUTING.md`](../CONTRIBUTING.md) |
| [PR #3](https://github.com/bfrpaulondev/Mark-BP/pull/3) | `ANT-010`, `ANT-018`; parte de `ANT-019` | Baseline Python 3.11/3.12, testes mínimos e CI inicial | [suporte de Python](current-state/python-support.md), [`tests/`](../tests) e [workflow de CI](../.github/workflows/ci.yml) |
| [PR #4](https://github.com/bfrpaulondev/Mark-BP/pull/4) | `ANT-011`, `ANT-012`, `ANT-020`; parte de `ANT-014` e `ANT-019` | Lock reproduzível, extras de voz e instalação documentada | [gestão de dependências](current-state/dependencies.md), [`pyproject.toml`](../pyproject.toml) e [`uv.lock`](../uv.lock) |

## Próxima sequência

1. `ANT-013`: centralizar a configuração num contrato tipado sem quebrar os ficheiros JSON herdados.
2. `ANT-014`: inventariar e remover os restantes fluxos de instalação automática em `core/installer.py` e `actions/dev_agent.py`.
3. `ANT-017` e restante `ANT-019`: introduzir lint, formatter, tipos, auditoria de dependências e verificação de segredos de forma incremental.

Cada etapa deve preservar o comportamento legado, ter rollback simples e entrar pela mesma branch e pull request até ser integrada.

## Riscos e bloqueios conhecidos

| Item | Situação | Próxima decisão |
|---|---|---|
| `ANT-002` — licença herdada | Uso comercial ainda não validado | Auditar licença e autorização antes de comercializar |
| `ANT-004` — chave privada no histórico | Deve ser tratada como comprometida | Revogar material relacionado e decidir sobre reescrita segura do histórico |
| `ANT-014` — instalações em runtime | Remoção parcial; ainda existem fluxos herdados | Caracterizar e substituir por instalação explícita |
| `ANT-019` — CI completa | Compilação, testes e lock passam; faltam lint, tipos, auditoria e secret scan | Completar depois de definir as ferramentas em `ANT-017` |
| Smoke test Windows/áudio | Ainda sem evidência ponta a ponta | Executar em ambiente Windows com hardware e extras selecionados |

## Protocolo de atualização

Em cada pull request relevante:

1. atualizar a data e o estado atual;
2. acrescentar a entrega e respetiva evidência;
3. registar apenas riscos novos ou alterados;
4. definir uma única tarefa seguinte;
5. depois do merge, confirmar CI verde e eliminar a branch integrada.
