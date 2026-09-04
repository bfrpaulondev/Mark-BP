# Antonella — Estado da execução

> Painel operacional do trabalho já realizado e do próximo passo. O [plano mestre](ANTONELLA_MASTER_ROADMAP.md) continua a ser a fonte do escopo completo e dos critérios `ANT-*`.

**Última atualização:** 2026-09-04

**Branch canónica:** `main`

**Responsável pelo produto:** Bruno Paulon

## Estado atual

Esta tabela descreve o estado que deve existir na `main`. Durante a revisão de uma atualização deste documento, a respetiva branch e pull request são exceções transitórias.

| Campo | Estado |
|---|---|
| Tarefa ativa | `ANT-013` — migração incremental dos leitores runtime para a configuração tipada |
| Pull requests abertas | Uma durante a entrega `ANT-013` |
| Issues abertas | Nenhuma |
| Próxima tarefa recomendada | Concluir `ANT-013` migrando os leitores diretos restantes de `api_keys.json` |
| Tarefa seguinte | `ANT-014` — remover instalações automáticas em runtime |
| Última CI integrada | [PR #5 — verificações obrigatórias](https://github.com/bfrpaulondev/Mark-BP/pull/5/checks) |

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
| [PR #5](https://github.com/bfrpaulondev/Mark-BP/pull/5) | Extensão de `ANT-005` | Painel operacional único e regras de higiene para branches, pull requests e issues | Este documento e [`CONTRIBUTING.md`](../CONTRIBUTING.md) |

## Trabalho atual de ANT-013

Primeiro corte pronto para integração rápida:

- `config/settings.py` introduz `AntonellaSettings` com Pydantic Settings;
- variáveis `ANTONELLA_*` têm precedência sobre o JSON legado;
- `config/__init__.py` e `memory/config_manager.py` passam pelo contrato central;
- escritas continuam a preservar o formato JSON existente e não copiam automaticamente segredos do ambiente para disco;
- `pydantic-settings==2.15.0` fica fixado no lock reproduzível;
- testes cobrem JSON legado, normalização, precedência do ambiente e preservação de campos desconhecidos.

A tarefa `ANT-013` permanece aberta até `main.py`, UI, dashboard, `core/llm_client.py` e actions que ainda leem `api_keys.json` diretamente usarem o contrato central.

## Próxima sequência

1. concluir `ANT-013`: migrar os leitores runtime diretos restantes sem alterar comportamento funcional;
2. `ANT-014`: inventariar e remover os restantes fluxos de instalação automática em `core/installer.py` e `actions/dev_agent.py`;
3. `ANT-017` e restante `ANT-019`: introduzir lint, formatter, tipos, auditoria de dependências e verificação de segredos de forma incremental.

Cada etapa deve preservar o comportamento legado, ter rollback simples e entrar por uma única branch/pull request ativa de cada vez.

## Riscos e bloqueios conhecidos

| Item | Situação | Próxima decisão |
|---|---|---|
| `ANT-002` — licença herdada | Uso comercial ainda não validado | Auditar licença e autorização antes de comercializar |
| `ANT-004` — chave privada no histórico | Deve ser tratada como comprometida | Revogar material relacionado e decidir sobre reescrita segura do histórico |
| `ANT-013` — leitores diretos de JSON | Contrato tipado existe, mas leitores runtime herdados ainda estão dispersos | Migrar gradualmente sem refatoração estrutural |
| `ANT-014` — instalações em runtime | Remoção parcial; ainda existem fluxos herdados | Caracterizar e substituir por instalação explícita |
| `ANT-019` — CI completa | Compilação, testes e lock passam; faltam lint, tipos, auditoria e secret scan | Completar depois de definir as ferramentas em `ANT-017` |
| Smoke test Windows/áudio | Ainda sem evidência ponta a ponta | Executar em ambiente Windows com hardware e extras selecionados |

## Protocolo de atualização

Em cada pull request relevante:

1. atualizar a data e o estado atual;
2. acrescentar a entrega e respetiva evidência;
3. registar apenas riscos novos ou alterados;
4. definir uma única tarefa seguinte;
5. depois do merge, confirmar CI verde e eliminar a branch integrada quando a API disponível permitir.
