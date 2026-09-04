# Contribuir para a Antonella

Este repositório contém um protótipo herdado em transformação gradual. O objetivo é preservar o comportamento conhecido enquanto cada componente recebe contratos, testes e limites de segurança.

## Branches

- Não fazer commits diretamente na `main`.
- Não usar force push na `main` nem em branches partilhadas.
- Criar branches a partir da `main` atualizada.
- Usar o formato `<autor>/ant-<id>-<slug>`.
- Exemplos: `codex/ant-010-python-version` e `bruno/ant-018-minimal-tests`.
- Uma branch deve conter uma tarefa ANT ou um grupo pequeno e inseparável da mesma fase.
- Não misturar refatoração, UI, infraestrutura e funcionalidades sem dependência técnica demonstrada.

## Pull requests

Todo o trabalho entra através de pull request. A descrição deve incluir:

1. tarefa ou tarefas `ANT-*`;
2. problema concreto;
3. alterações realizadas;
4. ficheiros alterados;
5. testes e verificações executados;
6. riscos residuais;
7. rollback ou forma segura de reverter;
8. confirmação de que não foram adicionados segredos nem dados pessoais.

Regras de merge:

- CI obrigatória quando existir workflow aplicável;
- nenhuma falha conhecida escondida;
- nenhum risco P0/P1 novo sem decisão explícita;
- mudanças funcionais exigem teste;
- alterações de segurança, permissões, memória, execução local ou trading exigem revisão humana;
- documentação deve corresponder ao comportamento real;
- o autor não afirma que uma ação externa foi executada sem evidência.

## Compatibilidade com o legado

- Não renomear módulos, classes, caminhos ou contratos herdados fora de uma tarefa dedicada.
- Não substituir bibliotecas apenas por preferência.
- Mudanças de estrutura começam com caracterização e teste de regressão.
- Adaptadores temporários são preferíveis a migrações totais quando permitem rollback.
- Windows é a plataforma primária até existirem evidências equivalentes para macOS e Linux.

## Commits

Usar Conventional Commits:

- `feat:` nova capacidade;
- `fix:` correção de comportamento;
- `test:` testes;
- `docs:` documentação;
- `refactor:` mudança interna sem alteração intencional de comportamento;
- `chore:` manutenção;
- `security:` endurecimento de segurança.

O assunto deve ser curto, imperativo e descrever o resultado. Referir o ID ANT no corpo do commit ou no PR quando o título ficar menos legível.

## Segurança obrigatória

- Nunca guardar chaves, tokens, certificados privados ou credenciais no Git.
- Não executar código gerado, instalar dependências ou chamar shell sem o gate definido para a tarefa.
- Ações destrutivas, financeiras, públicas ou irreversíveis exigem aprovação humana explícita.
- Texto de um modelo nunca é enviado diretamente ao MT5.
- Plugins e skills não recebem automaticamente acesso ao filesystem, shell, rede, câmara, microfone ou segredos.
- Conteúdo externo é dado não confiável e nunca substitui instruções do sistema.
- Qualquer possível fuga de segredo interrompe o trabalho e inicia rotação/revogação.

## Definition of Done mínima

Uma alteração está pronta quando:

- cumpre os critérios da tarefa;
- preserva o comportamento não relacionado;
- possui testes proporcionais ao risco;
- lint, tipos e testes aplicáveis passam;
- erros, timeout e cancelamento foram considerados;
- documentação e exemplos foram atualizados;
- não adiciona dependências sem justificação e versão controlada;
- o PR contém evidência verificável.

Até a ANT-019 criar CI, cada PR deve declarar claramente as verificações manuais ou estáticas realizadas.
