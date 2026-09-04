# Antonella — teste local rápido

Este é o caminho mais curto para validar a `main` atual sem instalar dependências silenciosamente nem alterar a arquitetura do protótipo.

## Estado do que estás a testar

A aplicação ainda usa a UI e a sessão de voz herdadas do Mark/JARVIS. A estabilização Antonella já inclui configuração tipada, dependências bloqueadas, testes Python 3.11/3.12, remoção de instalações automáticas em runtime e a fundação do logging estruturado.

Este teste não valida ainda a arquitetura cloud, memória Supabase, router multimodelo, nova UI ou integração MT5.

## 1. Atualizar a main

```powershell
git checkout main
git pull origin main
```

## 2. Confirmar Python

A versão principal é Python 3.11. Python 3.12 também é validado pela CI durante a estabilização.

```powershell
python --version
```

## 3. Instalar o ambiente reproduzível

```powershell
python -m pip install uv==0.11.33
uv sync --locked
uv run playwright install chromium
```

Não uses `pip install` para corrigir módulos individualmente. Se uma capacidade de voz opcional for necessária, instala o extra indicado pelo `doctor`.

## 4. Configurar a chave Gemini

Preferência atual para evitar gravar a chave no JSON:

```powershell
$env:ANTONELLA_GEMINI_API_KEY="A_TUA_CHAVE"
```

A compatibilidade com `config/api_keys.json` continua disponível durante a migração.

## 5. Executar o doctor

```powershell
uv run python scripts/doctor.py
```

Só avança se o resultado final for:

```text
[RESULT] Antonella is ready for a local smoke test. Run: uv run python main.py
```

Se faltar uma dependência opcional, o próprio comando apresenta a linha `uv sync --locked --extra ...` que deve ser executada explicitamente.

## 6. Abrir a aplicação

```powershell
uv run python main.py
```

## 7. Smoke test manual

Valida apenas estes fluxos primeiro:

1. a janela abre sem crash;
2. a sessão Gemini liga sem expor a chave nos logs;
3. o microfone é inicializado;
4. uma pergunta simples recebe resposta;
5. interromper a voz não bloqueia a UI;
6. abrir uma aplicação simples através de tool call produz efeito real;
7. fechar a Antonella termina o processo sem ficar preso em background.

## Se falhar

Guarda estes três elementos:

- output completo de `uv run python scripts/doctor.py`;
- traceback/erro mostrado ao executar `uv run python main.py`;
- em que passo do smoke test ocorreu a falha.

Não instales dependências ad hoc depois da falha. A correção deve entrar no lock/configuração do projeto para continuar reproduzível.
