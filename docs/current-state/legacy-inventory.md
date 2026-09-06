# Inventário técnico do legado

- Baseline: `main@b319082a98aeb887a161d75cba7487c4181b7bba`
- Data da análise: 2026-09-04
- Tarefa: ANT-001
- Origem: fork `FatihMakes/Mark-LII`
- Classificação atual: protótipo funcional de assistente desktop

## Resumo mensurável

| Indicador | Baseline |
|---|---:|
| Ficheiros Python | 39 |
| Linhas Python aproximadas | 18 101 |
| Módulos de ações | 22 |
| Ficheiros de teste encontrados | 0 |
| Workflows GitHub Actions encontrados | 0 |
| Dependências declaradas | 29 |
| Branch principal | `main` |

Os números foram recolhidos da árvore Git e dos ficheiros existentes no baseline indicado. Devem ser atualizados quando a estabilização alterar a estrutura.

## Mapa de módulos

| Área | Ficheiros principais | Responsabilidade atual | Acoplamento observado |
|---|---|---|---|
| Entrada e sessão | `main.py` — 1 626 linhas | Gemini Live, áudio, tools, memória, proatividade e ciclo principal | Importa diretamente UI, memória e todas as ações |
| Interface desktop | `ui.py` — 3 481 linhas | HUD PyQt6, métricas, câmara, plugins, configuração e atalhos | UI, sistema operativo e configuração no mesmo módulo |
| Cliente LLM alternativo | `core/llm_client.py` — 587 linhas | Ollama e endpoints compatíveis com OpenAI | Não governa a sessão principal, que continua ligada ao Gemini Live |
| Voz local | `core/stt.py`, `core/tts.py` | Whisper/Vosk e Edge/Kokoro/ElevenLabs | Integração parcial e dependências incompletas |
| Plugins | `core/plugin_loader.py` | Descoberta, validação básica e execução | Importação e execução dentro do processo principal |
| Memória | `memory/memory_manager.py` | Memória JSON local e resumos de sessão | Limite global de 2 200 caracteres e sem proveniência |
| Configuração | `memory/config_manager.py`, `config/__init__.py` | Chaves, nome, preferências e estado de plugins | Leituras e escritas de `api_keys.json` espalhadas |
| Ferramentas | `actions/*.py` | Browser, ficheiros, código, desktop, mensagens, pesquisa e sistema | Chamadas diretas ao SO, rede e Gemini |
| Dashboard remoto | `dashboard/server.py` — 885 linhas | FastAPI local, WebSocket, áudio, comandos e partilha de ficheiros | Partilha o processo e a fila de comandos do assistente |
| Instalação | `setup.py`, `requirements.txt` | Instalação de pacotes e Playwright | Sem lockfile e sem instalação reproduzível |

## Capacidades presentes no código

- conversa de voz em tempo real através do Gemini Live;
- captura de ecrã e câmara;
- controlo de rato, teclado, janelas e definições do computador;
- automação de browser com Playwright e abertura do perfil nativo;
- leitura, escrita, movimentação e envio para o lixo de ficheiros dentro da home;
- pesquisa web, YouTube, meteorologia, lembretes e mensagens;
- geração e execução de código e criação de projetos;
- dashboard remoto com áudio, comandos e transferência de ficheiros;
- memória local em JSON, resumo de sessões e ações proativas;
- carregamento de plugins Python.

A presença de uma capacidade no código não prova que funcione de forma consistente em todos os sistemas operativos. Essa evidência pertence à ANT-009.

## Dependências

O `requirements.txt` declara a base gráfica, Gemini, automação, visão, dashboard e bibliotecas específicas de Windows. Contudo, há imports associados a funcionalidades que não estão declarados diretamente:

- `faster-whisper`, `torch` e `vosk`;
- `edge-tts`, `miniaudio` e `kokoro`;
- `mediapipe`;
- `PyPDF2`, `pdfplumber`, `pandas`, `python-docx` e `pydub`;
- `plyer`;
- pacote que fornece `pynvml` e pacote `WMI`;
- `duckduckgo-search`, usado como fallback legado.

Alguns imports são opcionais ou executados apenas quando a funcionalidade é chamada. A ANT-012 deve separar extras opcionais, declarar versões suportadas e devolver erros acionáveis sem instalar pacotes silenciosamente.

## Pontos de acoplamento prioritários

1. `main.py` concentra transporte de voz, configuração, memória, dispatch e política de tools.
2. A sessão principal instancia diretamente o SDK Gemini e um modelo preview.
3. Vários módulos leem a mesma chave Gemini diretamente de `config/api_keys.json`.
4. O dispatcher passa argumentos gerados pelo modelo diretamente às funções de sistema.
5. UI, dashboard e agente partilham estado e efeitos dentro do mesmo processo.
6. Plugins são importados no processo principal durante a descoberta.
7. Memória e configuração dependem de ficheiros locais mutáveis.

## Riscos técnicos e de segurança observados

| Prioridade | Observação | Consequência |
|---|---|---|
| P0 | Não existe motor independente de permissões/aprovação antes do dispatch das tools | Um tool call pode escrever ficheiros, enviar mensagens ou controlar o computador sem gate técnico |
| P0 | `actions/desktop.py` executa Python gerado pelo modelo com `exec` | O dicionário de objetos permitido reduz risco, mas não constitui sandbox de segurança |
| P0 | Plugins são importados e executados no processo principal e ficam ativos por padrão | Código de plugin possui os privilégios do processo antes da validação completa |
| P1 | `actions/dev_agent.py` pode instalar dependências, executar projetos e abrir VS Code | Efeitos de supply chain e execução não estão isolados |
| P1 | A chave Gemini é guardada em JSON local sem cofre do sistema operativo | Exposição por cópia, malware, permissões ou diagnóstico |
| P1 | O dashboard remoto pode abrir acesso de rede e encaminhar comandos ao mesmo executor | A superfície remota precisa de threat model, sessões revogáveis e autorização por capacidade |
| P1 | Não existem testes nem CI | Regressões e diferenças entre sistemas operativos não são detetadas |
| P1 | O prompt atual termina com uma instrução para assumir e executar | A segurança depende do modelo em vez de uma política determinística |
| P2 | Memória é truncada para um orçamento muito pequeno e não guarda proveniência | Perda silenciosa de contexto e dificuldade em corrigir conhecimento |
| P2 | Existem monólitos grandes em `main.py` e `ui.py` | Alterações simples têm uma área de regressão elevada |

## Licenças e proveniência

- O repositório é um fork de `FatihMakes/Mark-LII`.
- O ficheiro `LICENSE` identifica o material como CC BY-NC 4.0 e proíbe utilização comercial.
- O histórico mostra a remoção de ficheiros de certificado/chave; a ANT-004 deve tratá-los como comprometidos.
- Esta secção é apenas inventário factual. A interpretação completa, compatibilidade de dependências e estratégia comercial pertencem às ANT-002 e ANT-003.

## O que ainda não existe

A `main` analisada não contém:

- arquitetura cloud-first;
- Supabase;
- router multimodelo aplicado ao agente principal;
- contratos de domínio e orquestrador independente;
- sandbox real para código e skills;
- aprovações persistentes por capacidade e nível de risco;
- suíte automatizada de testes, evals ou CI;
- integração MetaTrader 5/Fimathe PCM;
- implementação da nova UI Antonella.

## Critério de atualização

Este inventário é um snapshot, não documentação eterna. Qualquer PR que elimine ou introduza um risco estrutural deve atualizar a secção correspondente ou ligar para um inventário posterior.

## Actualização runtime (2026-09-05 · ANT-272 B1)

O mapa acima descreve o baseline ANT-001. Estado actual do legado após a
reestruturação (pacote `ui/` viva, `main.py`+`antonella.py` como entrypoints):

| Path | Runtime reachable? | User visible? | Compatibility required? | Safe to remove? |
|---|---|---|---|---|
| `ui.py` (3 481 linhas) | **Não** — o pacote `ui/` sombreia o módulo; execução directa é inerte (sem `__main__`) | Não (títulos MARK LI já purgados) | Não encontrado consumidor | **Removido** (B4 autorizado): ficheiro apagado, `compileall` da CI actualizado, testes de ausência adicionados |
| `main.py` resíduos JARVIS (prints, defaults, comentários) | Sim | Console (stdout) + fallback de prompt | `shutdown_jarvis` é nome interno de tool (nunca falado) | Purgados nesta slice; 0 ocorrências restantes |
| `main.py` fallback `_load_system_prompt` | Sim (só se `core/prompt.txt` faltar) | Não (instrução interna) | — | Identidade neutra agora |
| `core/prompt.txt` menções | Sim | Não (proibição explícita + nome interno de tool) | Sim (proibição é intencional) | Não — manter |
| `class JarvisUI` (`ui/__init__.py`) | Sim (fachada de compatibilidade) | Não (nome interno) | Sim — motores importam-no | Não por agora |
| `memory/config_manager.py` leituras legadas | Sim | Não | Sim (config existente) | Não por agora |

Prova de inacessibilidade: `tests/test_legacy_inaccessibility.py`
(`ui.__file__` resolve ao pacote; sem `__main__` no legado; entrypoints só
usam o pacote). Regressão de identidade: tokens exactos proibidos em
superfícies vivas, com a máscara do LogView e a proibição do prompt como
únicas ocorrências legítimas.
