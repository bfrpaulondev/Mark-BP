# Antonella — Estado da execução

> Painel operacional do trabalho já realizado e do próximo passo. O [plano mestre](ANTONELLA_MASTER_ROADMAP.md) continua a ser a fonte do escopo completo e dos critérios `ANT-*`.

**Última atualização:** 2026-09-04

**Branch canónica:** `main`

**Responsável pelo produto:** Bruno Paulon

## Estado atual

Esta tabela descreve o estado esperado depois da integração da entrega atual.

| Campo | Estado |
|---|---|
| Tarefa ativa | Nenhuma após a integração do smoke/doctor |
| Pull requests abertas | Nenhuma após a integração da entrega atual |
| Issues abertas | Nenhuma |
| Próxima tarefa recomendada | Continuação de `ANT-015` — migrar pontos de entrada principais para logging estruturado |
| Tarefa seguinte | `ANT-016` — tratamento global de erros |
| Teste local | [`docs/TESTING.md`](TESTING.md) + `uv run python scripts/doctor.py` |

## Regras operacionais

- Manter no máximo uma branch de implementação e uma pull request ativa para o trabalho do Codex, salvo autorização explícita para trabalho paralelo.
- Fazer merge assim que a entrega estiver validada e a CI estiver verde.
- Apagar branches integradas ou substituídas quando a API permitir; caso contrário, reposicioná-las para a `main` atual sem trabalho pendente.
- Não criar issues para duplicar tarefas do plano mestre.
- Criar uma issue apenas por decisão explícita de Bruno ou quando existir um bloqueio real que exija discussão independente.
- Atualizar este painel na mesma pull request das entregas relevantes.
- Não marcar uma tarefa como concluída sem evidência verificável no repositório, testes ou CI.

## Entregas integradas

| Entrega | Tarefas | Resultado |
|---|---|---|
| PR #1 | Planeamento | Plano mestre de transformação criado |
| PR #2 | `ANT-000`, `ANT-001`, `ANT-005` | Identidade, inventário técnico e política de contribuição |
| PR #3 | `ANT-010`, `ANT-018`; parte de `ANT-019` | Python 3.11/3.12, testes mínimos e CI inicial |
| PR #4 | `ANT-011`, `ANT-012`, `ANT-020`; parte de `ANT-019` | Lock reproduzível, extras de voz e instalação documentada |
| PR #5 | Extensão de `ANT-005` | Painel operacional e higiene de branches/PRs/issues |
| PR #6 e #7 | `ANT-013` | Configuração tipada, variáveis `ANTONELLA_*`, compatibilidade JSON legado e proteção de segredos |
| PR #8 | `ANT-014` | Remoção de `pip install` e downloads automáticos em runtime; dependências passam a exigir instalação explícita |
| PR #9 | Primeiro corte de `ANT-015` | Logging JSON, `correlation_id`, redação de segredos/PII e primeira integração no readiness check |

## Entrega atual — preparação para teste rápido

A entrega atual reduz o tempo entre checkout e diagnóstico:

- adiciona `scripts/doctor.py` para validar Python, configuração, chave Gemini, prompt e dependências selecionadas;
- o `doctor` nunca instala pacotes automaticamente;
- dependências em falta geram um comando `uv sync --locked --extra ...` explícito;
- adiciona testes unitários para ambiente pronto, chave ausente e dependências opcionais em falta;
- adiciona [`docs/TESTING.md`](TESTING.md) com o caminho Windows mais curto para testar a `main`;
- este smoke test produz evidência para a futura conclusão de `ANT-009`, mas não marca ainda o baseline funcional como concluído até existir execução real no Windows com áudio/UI.

## Próxima sequência

1. continuar `ANT-015`: integrar logging estruturado nos pontos de entrada e componentes principais, de forma incremental;
2. `ANT-016`: introduzir classes/contratos de erro para configuração, provider, permissão, recuperação e falha interna;
3. `ANT-017` e restante `ANT-019`: Ruff, formatter, type checking, auditoria de dependências e secrets scan;
4. usar o primeiro smoke test real do Windows para fechar regressões antes de cortes arquiteturais maiores.

## Riscos e bloqueios conhecidos

| Item | Situação | Próxima decisão |
|---|---|---|
| `ANT-002` — licença herdada | Uso comercial ainda não validado | Auditar antes de qualquer comercialização |
| `ANT-004` — chave privada no histórico | Deve ser tratada como comprometida | Revogar material relacionado e decidir sobre reescrita segura do histórico |
| `ANT-009` — baseline funcional | Ferramenta de smoke preparada; falta execução real Windows/áudio | Executar `docs/TESTING.md` e registar os resultados |
| `ANT-015` — logging estruturado | Fundação integrada; migração do legado ainda parcial | Migrar pontos críticos sem refatoração ampla |
| `ANT-019` — CI completa | Compilação, testes e lock passam; faltam lint, tipos, auditoria e secret scan | Completar depois de `ANT-017` |
| Smoke test Windows/áudio | Ainda sem evidência ponta a ponta | Executar em Windows com microfone e chave configurada |

## Protocolo de atualização

Em cada pull request relevante:

1. atualizar o estado atual;
2. acrescentar a entrega e respetiva evidência;
3. registar apenas riscos novos ou alterados;
4. definir uma única tarefa seguinte;
5. depois do merge, confirmar CI verde e remover qualquer estado transitório desnecessário.
