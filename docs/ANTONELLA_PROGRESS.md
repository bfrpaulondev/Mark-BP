# Antonella — Estado da execução

> Painel operacional. O plano mestre continua a ser a fonte do escopo completo.

**Última atualização:** 2026-09-04  
**Branch canónica:** `main`

## Estado atual

| Campo | Estado |
|---|---|
| Tarefa ativa | Realtime Computer Use + routing de custo |
| Pull requests abertas | Uma no máximo durante implementação |
| Issues abertas | Nenhuma |
| Próximo teste | Windows multi-monitor + ScreenConnect |
| Próxima tarefa | Extrair mais routing/orquestração do `main.py` |

## Entregas integradas

- PR #1–#11: roadmap, estabilização, config, dependências, testes, logging e doctor.
- PR #12: nova UI Antonella + voz feminina.
- PR #13: visão multi-monitor e identidade da sessão de visão.

## Entrega em curso — Realtime Computer Use económico

### Perceção contínua local

- stream desktop em background;
- 10/15/20 FPS conforme modo de custo;
- seleção automática do monitor ativo;
- coordenadas negativas;
- `frame diff` local;
- apenas alterações relevantes ficam disponíveis ao planner;
- compressão diferente por tier.

### Loop

```text
observe → plan → safety → act → observe → verify/change → continue
```

O loop corre em background para a conversa de voz continuar disponível.

### Controlo de custo

- `economy` default;
- limites de chamadas/passos;
- resolução menor em economy;
- OpenAI Luna/Terra/Sol por tier quando configurado;
- fallback Gemini.

### Segurança

- baixo risco automático;
- efeitos destrutivos, externos, privilegiados, financeiros ou permissões pausam;
- aprovação de uso único;
- `stop` interrompe inclusive espera de aprovação.

### Integração

Entra como plugin `realtime_computer_use`, evitando aumentar o monólito `main.py`. Esta primeira slice não marca as tarefas amplas de autonomia/segurança como concluídas.

## Próxima sequência

1. validar ScreenConnect em Windows real;
2. adicionar UI Automation/estrutura Windows antes de visão quando disponível;
3. extrair Tool Router/Agent Orchestrator;
4. expandir router multimodelo para além de Computer Use;
5. Policy Engine completo;
6. memória Supabase/skills;
7. MT5 observer/drawing após core estável.
