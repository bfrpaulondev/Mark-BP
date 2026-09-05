# Windows CI (ANT-273)

Estado: implementado (primeira fatia), validado em CI e endurecido em principal review.

## O que existe

- Job `windows-baseline` (`.github/workflows/ci.yml`): `windows-latest`,
  Python 3.11 + 3.12, com os mesmos passos essenciais do baseline Ubuntu
  (`pydantic-settings` como única dependência, `compileall`, suite de
  testes isolada) mais um import smoke específico de Windows.
- O gate `compileall` de Ubuntu e Windows cobre agora também a entrada canónica
  `antonella.py` e os pacotes `config/`, `scripts/` e `ui/`, além das superfícies
  legadas ainda mantidas por compatibilidade.
- `scripts/ci_import_smoke.py`: import smoke dos módulos sem dependências
  pesadas (`core/`, `actions/`, `config/`, `dashboard/`, `memory/`,
  `scripts/` + ficheiros Qt-free fora do pacote `ui`). Apenas raízes de
  dependências externas conhecidas podem ser classificadas como **skip**;
  um `ModuleNotFoundError` desconhecido ou project-local falha fechado para
  não esconder typos de imports. `plugins/` continua excluído por design
  porque são drop-ins carregados pelo runtime.
- `ui/runtime_state.py`, integrado pelo ANT-268, entra no smoke como ficheiro
  Qt-free sem importar o pacote `ui` completo.
- `PYTHONUTF8=1` no job Windows: o stdout do runner usa a code page ANSI;
  os testes imprimem texto pt-PT/emoji e a aplicação corre em UTF-8.

## Verificação

A CI valida cinco gates nesta fatia:

- Dependency lock;
- Ubuntu Python 3.11;
- Ubuntu Python 3.12;
- Windows Python 3.11;
- Windows Python 3.12.

O runner Windows continua a ser CI de software, não substitui validação física
com UIA, áudio, DPI/multi-monitor, Playwright GUI ou Computer Use real.

## Próximas fatias (fora desta PR)

- Import smoke também no job Ubuntu.
- Ruff / Pyright / coverage / pip-audit / secret scanning como gates não
  bloqueantes antes de os tornar obrigatórios.
