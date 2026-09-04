# Antonella — teste local rápido

Este é o caminho mais curto para validar a `main` atual sem instalações silenciosas.

## O que estás a testar

O entrypoint canónico do desktop é `antonella.py`.

Esta versão já inclui:

- UI Antonella redesenhada segundo a referência aprovada: fundo dark premium, métricas à esquerda, esfera neural de partículas no centro, `REGISTO` à direita, drop-zone e comando inferior;
- identidade Antonella por defeito;
- voz Gemini Live configurável, com `Kore` por defeito e estilo feminino, quente e natural;
- configuração tipada e variáveis `ANTONELLA_*`;
- dependências bloqueadas e instalação reproduzível;
- interrupção, mute, texto, áudio, câmara, anexos e painel contextual;
- motor realtime legado mantido por baixo como camada de compatibilidade durante a migração.

Este teste ainda não valida memória Supabase, router multimodelo, arquitetura cloud final ou integração MT5.

## 1. Atualizar a main

```powershell
git checkout main
git pull origin main
```

## 2. Confirmar Python

```powershell
python --version
```

Python 3.11 é a versão principal. Python 3.12 também é validado pela CI.

## 3. Instalar o ambiente reproduzível

```powershell
python -m pip install uv==0.11.33
uv sync --locked
uv run playwright install chromium
```

Se o `doctor` indicar extras de voz em falta, instala apenas o comando explícito apresentado por ele.

## 4. Configurar a chave Gemini

```powershell
$env:ANTONELLA_GEMINI_API_KEY="A_TUA_CHAVE"
```

## 5. Voz feminina

A voz predefinida é:

```text
Kore
```

Podes escolher outra voz suportada sem alterar código:

```powershell
$env:ANTONELLA_VOICE_NAME="Aoede"
```

O estilo da voz também é configurável:

```powershell
$env:ANTONELLA_VOICE_STYLE="feminine, warm, natural, calm and conversational"
```

## 6. Executar o doctor

```powershell
uv run python scripts/doctor.py
```

Só avança se o resultado final for:

```text
[RESULT] Antonella is ready for a local smoke test. Run: uv run python antonella.py
```

## 7. Abrir a Antonella

```powershell
uv run python antonella.py
```

## 8. Smoke test manual

Valida estes fluxos:

1. a nova janela Antonella abre sem crash;
2. o cabeçalho mostra `ANTONELLA` e `Adaptive neural companion`;
3. CPU, MEM, NET e CORE STATUS aparecem à esquerda;
4. a esfera central é composta por partículas roxas e reage aos estados;
5. os estados mudam entre `A ESCUTAR`, `A PENSAR` e `A RESPONDER`;
6. `REGISTO` aparece à direita e recebe eventos/conversa;
7. `Largar ficheiro` aceita clique e drag-and-drop;
8. a sessão Gemini liga sem expor a chave nos logs;
9. a voz ouvida é a voz configurada (`Kore` por defeito);
10. uma pergunta simples por voz recebe resposta;
11. `Esc` interrompe a resposta sem bloquear a UI;
12. `F4` pausa e retoma o microfone;
13. escrever em `Diz alguma coisa…` envia um comando;
14. pedir para abrir uma aplicação simples produz efeito real;
15. fechar a aplicação termina o processo sem ficar preso em background.

## Se falhar

Guarda:

- output completo de `uv run python scripts/doctor.py`;
- traceback/erro de `uv run python antonella.py`;
- passo exato do smoke test onde ocorreu a falha;
- se a falha for de voz, qual `ANTONELLA_VOICE_NAME` estava ativo.

Não instales dependências ad hoc depois da falha. A correção deve entrar no lock/configuração do projeto para continuar reproduzível.
