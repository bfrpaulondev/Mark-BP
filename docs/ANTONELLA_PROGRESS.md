# Antonella — Estado da execução

> Painel operacional do trabalho já realizado e do próximo passo. O [plano mestre](ANTONELLA_MASTER_ROADMAP.md) continua a ser a fonte do escopo completo e dos critérios `ANT-*`.

**Última atualização:** 2026-09-04  
**Branch canónica:** `main`  
**Responsável pelo produto:** Bruno Paulon

## Estado atual

| Campo | Estado |
|---|---|
| Tarefa ativa | Nenhuma — redesign desktop e voz feminina integrados |
| Pull requests abertas | Nenhuma |
| Issues abertas | Nenhuma |
| Próximo teste | Windows real: `uv run python scripts/doctor.py` → `uv run python antonella.py` |
| Próxima tarefa após smoke | Continuar `ANT-015` e iniciar `ANT-016` |

## Regras operacionais

- Manter no máximo uma branch e uma pull request de implementação ativa para este fluxo.
- Fazer merge assim que a CI estiver verde.
- Não criar issues para duplicar o plano mestre.
- Não marcar baseline funcional como concluído sem evidência real Windows/áudio.
- Após squash merge, alinhar a branch transitória à `main` se a API não permitir apagá-la.

## Entregas integradas

| Entrega | Tarefas | Resultado |
|---|---|---|
| PR #1 | Planeamento | Plano mestre de transformação criado |
| PR #2 | `ANT-000`, `ANT-001`, `ANT-005` | Identidade, inventário técnico e política de contribuição |
| PR #3 | `ANT-010`, `ANT-018`; parte de `ANT-019` | Python 3.11/3.12, testes mínimos e CI inicial |
| PR #4 | `ANT-011`, `ANT-012`, `ANT-020`; parte de `ANT-019` | Lock reproduzível, extras de voz e instalação documentada |
| PR #5 | Extensão de `ANT-005` | Painel operacional e higiene de branches/PRs/issues |
| PR #6 e #7 | `ANT-013` | Configuração tipada, variáveis `ANTONELLA_*`, compatibilidade JSON e proteção de segredos |
| PR #8 | `ANT-014` | Instalações automáticas em runtime removidas |
| PR #9 | Primeiro corte de `ANT-015` | Logging JSON, correlation id e redação de dados sensíveis |
| PR #10 | Test readiness | `doctor`, documentação e smoke test reproduzível |
| PR #11 | Correção doctor | Execução direta de `scripts/doctor.py` corrigida e coberta por regressão |
| PR #12 | UI/UX + voz | Referência visual Antonella, orb neural optimizado, voz feminina configurável e novo entrypoint |

## Entrega atual — identidade visual Antonella + voz feminina

A entrega substitui o aspecto herdado do Mark/JARVIS no teste desktop sem reescrever ainda o motor realtime estabilizado.

### UI/UX

- novo package `ui/` assume o import canónico, mantendo `ui.py` legado apenas como rollback;
- layout dark premium inspirado na referência aprovada;
- cabeçalho `ANTONELLA` + `Adaptive neural companion`;
- relógio e data em pt-PT;
- CPU, MEM, NET e CORE STATUS em cartões à esquerda;
- esfera neural central renderizada com partículas pré-calculadas e animação optimizada a ~30 FPS;
- estados visuais `A ESCUTAR`, `A PENSAR`, `A EXECUTAR`, `A RESPONDER` e mute;
- `REGISTO` à direita com sanitização do branding herdado;
- drag-and-drop/click para anexar ficheiro;
- barra inferior `Diz alguma coisa…`, interrupção e mute;
- câmara e conteúdo contextual preservados por compatibilidade.

### Voz/identidade

- novo entrypoint canónico `antonella.py`;
- `assistant_name` passa a `Antonella` por defeito;
- voz Gemini Live passa a ser configurável por `ANTONELLA_VOICE_NAME`;
- `Kore` é o default atual;
- estilo vocal feminino, quente, natural, calmo e conversacional por defeito;
- prompt deixa de instruir a persona JARVIS e passa a usar `ANTONELLA CORE PROTOCOL`.

### Regressões adicionadas

- resolução do import `ui` para o novo package;
- contrato visual da referência (`ParticleOrb`, métricas, `REGISTO`, drop-zone e input);
- default de voz feminina/configurável;
- ausência da instrução herdada `Act: Always act like Jarvis`.

## Próxima sequência

1. executar smoke real em Windows com microfone e confirmar aparência/voz;
2. corrigir apenas regressões descobertas no smoke;
3. continuar `ANT-015` — logging estruturado em pontos críticos do runtime;
4. `ANT-016` — contratos globais de erro;
5. `ANT-017`/`ANT-019` — lint, tipos, auditoria e secret scan;
6. avançar para memória cloud e router multimodelo depois do desktop estabilizado.

## Riscos e bloqueios conhecidos

| Item | Situação | Próxima decisão |
|---|---|---|
| `ANT-002` — licença herdada | Uso comercial ainda não validado | Auditar antes de comercialização |
| `ANT-004` — chave privada no histórico | Deve ser tratada como comprometida | Revogar material relacionado e decidir reescrita segura |
| `ANT-009` — baseline funcional | Doctor pronto; falta evidência Windows/áudio da UI nova | Executar smoke real |
| `ANT-015` — logging estruturado | Fundação integrada; runtime legado ainda parcial | Migrar incrementalmente |
| `ANT-019` — CI completa | Compilação/testes/lock presentes; faltam gates adicionais | Completar depois do smoke |
| Motor realtime legado | Ainda contém nomes internos JARVIS em console/código | Migrar por camadas sem quebrar compatibilidade |

## Protocolo de atualização

Em cada pull request relevante:

1. atualizar este estado;
2. registar evidência da entrega;
3. manter apenas riscos reais;
4. definir uma única tarefa seguinte;
5. depois do merge, confirmar CI verde e remover estado transitório.
