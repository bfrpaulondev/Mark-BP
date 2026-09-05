# Windows CI (ANT-273)

Estado: implementado (primeira fatia), validado em CI.

## O que existe

- Job `windows-baseline` (`.github/workflows/ci.yml`): `windows-latest`,
  Python 3.11 + 3.12, com os mesmos passos do baseline Ubuntu
  (`pydantic-settings` como única dependência, `compileall`, suite de
  testes isolada) mais um passo novo.
- `scripts/ci_import_smoke.py`: import smoke dos módulos sem dependências
  pesadas (`core/`, `actions/`, `config/`, `dashboard/`, `memory/`,
  `scripts/` + ficheiros Qt-free fora do pacote `ui`). Módulos cuja única
  falha é dependência de terceiros em falta são **skip**; qualquer outro
  erro de import (sintaxe, import project-local partido, crash de
  plataforma) **falha o job**. `plugins/` é excluído por design (são
  drop-ins carregados pelo runtime).
- `PYTHONUTF8=1` no job Windows: o stdout do runner usa a code page ANSI;
  os testes imprimem texto pt-PT/emoji e a aplicação corre em UTF-8.

## Verificação local usada

Venv limpo Windows (Python 3.11.15) apenas com `pydantic-settings==2.15.0`:
compileall OK, suite OK, smoke OK (61 módulos importados, 7 skips por
dependência ausente).

## Próximas fatias (fora desta PR)

- Import smoke também no job Ubuntu.
- Ruff / Pyright / coverage / pip-audit / secret scanning como gates não
  bloqueantes antes de os tornar obrigatórios.
