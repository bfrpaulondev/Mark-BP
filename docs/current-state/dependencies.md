# Dependências e instalação reproduzível

- Tarefas: ANT-011, ANT-012 e ANT-020
- Plataforma primária: Windows 10/11 x64
- Python principal: 3.11
- Ferramenta de lock: uv 0.11.33

## Fontes de verdade

| Ficheiro | Função | Editar manualmente |
|---|---|---|
| `pyproject.toml` | Dependências diretas, versões de Python e extras opcionais | Sim |
| `uv.lock` | Resolução completa, multiplataforma, com versões e hashes | Não |
| `requirements.txt` | Export compatível com pip das dependências base, com versões e hashes | Não |

Os marcadores de plataforma mantêm `comtypes`, `pycaw`, `pywin32`, `pywinauto` e `win10toast` limitados ao Windows. O lock também representa Python 3.11 e 3.12, mas a instalação e os testes completos continuam centrados em Python 3.11 no Windows.

## Instalação recomendada no Windows

No PowerShell, a partir da raiz do repositório:

```powershell
py -3.11 -m pip install uv==0.11.33
uv sync --locked
uv run playwright install chromium
uv run python main.py
```

`uv sync --locked` falha se `pyproject.toml` e `uv.lock` não corresponderem; não atualiza dependências silenciosamente. A instalação do Chromium é um passo explícito porque o binário do navegador não faz parte de um lock Python.

Para compatibilidade com um ambiente que use apenas pip:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install --require-hashes -r requirements.txt
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python main.py
```

O export pip contém apenas a base. Para motores de voz opcionais, usar uv e selecionar os extras necessários.

## Perfis opcionais de voz

| Extra | Capacidade | Dependências diretas adicionais |
|---|---|---|
| `stt-whisper` | Transcrição local com Faster Whisper | `faster-whisper` |
| `stt-vosk` | Transcrição local com Vosk | `vosk` |
| `tts-edge` | Síntese EdgeTTS e reprodução de áudio comprimido | `edge-tts`, `miniaudio` |
| `tts-kokoro` | Síntese neural local com Kokoro | `kokoro>=0.9`, `soundfile` |
| `tts-elevenlabs` | Reprodução da resposta ElevenLabs | `miniaudio` |

Exemplo com Whisper e EdgeTTS:

```powershell
uv sync --locked --extra stt-whisper --extra tts-edge
```

Selecionar em cada execução de `uv sync` todos os extras que devem permanecer no ambiente. Se um extra estiver ausente ou incompatível, os adaptadores STT/TTS indicam o comando exato; não executam `pip install` durante a aplicação.

PyTorch continua opcional no Faster Whisper: sem ele, a deteção de CUDA do adaptador recua para CPU. O Kokoro traz a sua própria dependência de PyTorch através do lock.

## Artefactos externos ao lock

- Chromium do Playwright é instalado pelo passo explícito acima.
- Modelos Whisper, Vosk e Kokoro podem exigir download ou configuração no primeiro uso.
- Drivers de áudio, câmara e GPU pertencem ao sistema operativo.
- Chaves de API e configuração pessoal nunca pertencem ao lock nem ao Git.

Estes artefactos impedem que a existência do lock, por si só, seja tratada como prova de um smoke test completo.

## Atualização controlada

Alterar primeiro `pyproject.toml` e depois executar:

```powershell
uv lock --python 3.11
uv export --locked --no-dev --no-emit-project --output-file requirements.txt
python -m compileall -q actions core dashboard memory plugins main.py ui.py setup.py
python -m unittest discover -s tests -v
```

O PR deve explicar a dependência alterada, o motivo, os riscos por sistema operativo e a evidência de teste. A CI rejeita um lock desatualizado ou um `requirements.txt` que não corresponda ao lock.

## Estado de macOS e Linux

O lock contém marcadores e artefactos publicados para múltiplas plataformas, e a suíte isolada executa em Linux. Isto não constitui validação funcional do cliente: áudio, GUI, automação de desktop, navegador e modelos de voz ainda não têm smoke tests equivalentes em macOS ou Linux.
