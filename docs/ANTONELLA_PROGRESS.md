# Antonella — Estado da execução

> Painel operacional. O plano mestre continua a ser a fonte do escopo completo.

**Última atualização:** 2026-09-05
**Branch canónica:** `main`

## Estado atual

| Campo | Estado |
|---|---|
| Tarefa ativa | ANT-020/ANT-018 — arranque e diagnóstico real do runtime |
| Pull requests abertas | Uma no máximo durante implementação |
| Issues abertas | Nenhuma |
| Próximo teste | Windows multi-monitor + ScreenConnect |
| Próxima tarefa | Rever esta correção; depois autorização humana central das ferramentas legadas |

## Entregas integradas

- PR #1–#11: roadmap, estabilização, config, dependências, testes, logging e doctor.
- PR #12: nova UI Antonella + voz feminina.
- PR #13: visão multi-monitor e identidade da sessão de visão.
- PR #14–#22: Computer Use económico, especialista OpenAI, seleção de ecrãs, HUD, preferências, batching, painel do agente, captura por janela e controlo verificável de abas/rato.

## Correção preparada — arranque e doctor

Branch: `codex/ant-020-runtime-readiness`, baseada em `main@0366d6c`.
Ainda não integrada; aguarda PR/CI/revisão.

- README e instalador apontam para `antonella.py`.
- Doctor usa o perfil Gemini Live, sem exigir os adaptadores legados Whisper/EdgeTTS.
- Configuração inválida gera relatório sem repetir a leitura que lançava exceção.
- Imports nativos e descoberta de microfone/altifalante são testados em subprocessos com timeout, sem gravar/reproduzir áudio e sem imprimir saídas potencialmente sensíveis.
- Chromium ausente gera aviso; presença de chave não é apresentada como conectividade validada.
- 115 testes unitários passaram em Python 3.11; compilação e `git diff --check` passaram.
- E2E Windows, GUI renderizada, voz real, providers, browsers e ScreenConnect continuam não comprovados.
- O gate de segurança do Computer Use não cobre todas as ferramentas legadas. Não classificar o protótipo como seguro para autonomia geral.
- Preservar `codex/local-command-fast-path`: contém trabalho ainda não integrado.

## Implementação integrada — Realtime Computer Use económico (E2E pendente)

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
