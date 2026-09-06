# Memória Supabase no desktop

O runtime aceita apenas chave pública e uma sessão de utilizador previamente
obtida pelo fluxo de autenticação Supabase. Não foi criada uma UI de login.
Contrato de ambiente (nunca guardar tokens no repositório ou em relatórios):

- `ANTONELLA_SUPABASE_URL`: URL HTTPS do projecto;
- `ANTONELLA_SUPABASE_KEY`: publishable key ou legacy anon;
- `ANTONELLA_SUPABASE_ACCESS_TOKEN`: token de utilizador autenticado;
- `ANTONELLA_SUPABASE_REFRESH_TOKEN`: refresh token da mesma sessão.

`client_from_env()` estabelece a sessão com `auth.set_session()` e valida o
utilizador com `auth.get_user()`. A leitura local de claims apenas rejeita
formatos/roles inválidos; não substitui a validação no servidor. O owner é o
UUID validado, não `local`, metadata editável ou valor escolhido pelo cliente.
O repository do runtime recusa outro owner ou uma sessão que mude de conta.
Tokens ficam no cliente em memória; não existe gravação adicional em disco.

| Configuração | Estado | Comportamento |
|---|---|---|
| Todos os campos ausentes | NOT CONFIGURED | InMemory, aviso explícito de memória apenas desta sessão |
| Algum campo presente mas inválido, sem auth ou schema inacessível | CONFIGURED BUT FAILED | Comandos de memória desactivados; restantes comandos continuam |
| Sessão válida e schema acessível | READY | Repository Supabase vinculado ao utilizador |
| Falha numa operação posterior | OPERATION FAILED | Sem afirmação de sucesso e sem fallback temporário |

O probe lê as colunas exigidas pelas migrations 0001 e 0005 nas três tabelas.
Não prova políticas RLS, índices ou histórico de migrations. As políticas de
0002 têm de estar aplicadas no projecto antes da utilização; o desktop não
usa privilégios administrativos nem aplica SQL para contornar erros.

## Validação separada

`python scripts/validate_supabase_memory.py --output <ficheiro.json>`

O script grava um relatório também quando não há configuração. Usa apenas
registos sintéticos com IDs próprios e tenta limpá-los em `finally`, incluindo
escritas cuja resposta se perdeu. Falha de cleanup deixa o resultado FAIL.
Não escreve nem remove memórias existentes do utilizador.

Para testar RLS de `memories`, fornecer as quatro variáveis também com prefixo
`ANTONELLA_SUPABASE_TEST_B`, com outro utilizador do mesmo projecto. São
verificados read/update/delete cruzados e insert com owner forjado; apenas
uma recusa de autorização (42501) prova a rejeição do insert. Timeout não é
prova de RLS. Sem segundo utilizador: RLS NOT TESTED. O relatório não afirma
cobertura das políticas de tabelas filhas, índices ou histórico de migrations.

Nesta revisão: testes determinísticos executados; HTTP e RLS em Postgres
real NOT RUN. A validação com sessões reais continua necessária antes de
considerar o backend validado em produção.

Referências oficiais verificadas nesta revisão:
- [get_user: validação de JWT no servidor](https://supabase.com/docs/reference/python/auth-getuser)
- [set_session](https://supabase.com/docs/reference/python/auth-setsession)
- [Chaves públicas e privilegiadas](https://supabase.com/docs/guides/getting-started/api-keys)
