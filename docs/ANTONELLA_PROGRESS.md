# Antonella — Estado da execução

> Painel operacional do trabalho já realizado e do próximo passo. O [plano mestre](ANTONELLA_MASTER_ROADMAP.md) continua a ser a fonte do escopo completo e dos critérios `ANT-*`.

**Última atualização:** 2026-09-04

**Branch canónica:** `main`

**Responsável pelo produto:** Bruno Paulon

## Estado atual

Esta tabela descreve o estado que deve existir na `main`. Durante a revisão de uma atualização deste documento, a respetiva branch e pull request são exceções transitórias.

| Campo | Estado |
|---|---|
| Tarefa ativa | Nenhuma após a integração da conclusão de `ANT-013` |
| Pull requests abertas | Nenhuma após a integração desta entrega |
| Issues abertas | Nenhuma |
| Próxima tarefa recomendada | `ANT-014` — remover instalações automáticas em runtime |
| Tarefa seguinte | `ANT-015` — logging estruturado |
| Última CI integrada | [PR #6 — configuração tipada inicial](https://github.com/bfrpaulondev/Mark-BP/pull/6/checks) |

## Regras operacionais

- Manter no máximo uma branch de implementação e uma pull request ativa para o trabalho do Codex, salvo autorização explícita para trabalho paralelo.
- Atualizar este painel na mesma pull request de cada entrega relevante.
- Apagar branches integradas ou substituídas quando já não contiverem trabalho único.
- Quando a API disponível não permitir apagar uma branch integrada, reposicioná-la para a `main` atual antes de a reutilizar, sem conservar trabalho pendente.
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
| [PR #6](https://github.com/bfrpaulondev/Mark-BP/pull/6) | Primeiro corte de `ANT-013` | Contrato Pydantic Settings, precedência de ambiente, compatibilidade com JSON legado e lock reproduzível | [`config/settings.py`](../config/settings.py), [`tests/test_typed_settings.py`](../tests/test_typed_settings.py) e CI Python 3.11/3.12 |

## ANT-013 — conclusão preparada

A configuração tipada fica concluída nesta entrega:

- `AntonellaSettings` centraliza os campos conhecidos com Pydantic Settings;
- variáveis `ANTONELLA_*` têm precedência sobre o JSON legado sem obrigar migração imediata do ficheiro existente;
- `main.py`, UI, dashboard, `core/llm_client.py` e os leitores de configuração nas actions deixam de carregar diretamente `api_keys.json`;
- leitores da chave Gemini usam o contrato central e devolvem erro explícito quando a chave não existe;
- metadados mutáveis como `camera_index` continuam compatíveis com o JSON legado;
- caminhos de escrita que atualizam configuração persistida partem do JSON cru, impedindo que segredos fornecidos apenas por variáveis de ambiente sejam copiados para disco;
- o comportamento legado esparso de `memory/config_manager.py` é preservado;
- existe teste específico que prova que `ANTONELLA_GEMINI_API_KEY` pode sobrepor a chave em runtime sem ser persistida numa escrita de outra preferência;
- lock, export reproduzível, compilação e suíte unitária foram verificados antes da criação do PR final.

Depois do merge, `ANT-013` está concluída e a próxima tarefa operacional é `ANT-014`.

## Próxima sequência

1. `ANT-014`: remover instalações automáticas de pacotes em runtime, começando pelos fluxos já inventariados em `core/installer.py` e `actions/dev_agent.py`;
2. `ANT-015` e `ANT-016`: logging estruturado e tratamento global de erros sem reestruturar módulos não relacionados;
3. `ANT-017` e restante `ANT-019`: lint, formatter, tipos, auditoria de dependências e verificação de segredos de forma incremental.

Cada etapa deve preservar o comportamento legado, ter rollback simples e entrar por uma única branch/pull request ativa de cada vez.

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
5. depois do merge, confirmar CI verde e eliminar a branch integrada quando a API disponível permitir; caso contrário, alinhá-la à `main` sem trabalho único antes de reutilizar.
