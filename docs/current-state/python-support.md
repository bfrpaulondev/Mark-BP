# Suporte de Python

- Tarefa: ANT-010
- Decisão: Python 3.11 é a versão principal da Antonella durante a estabilização
- Compatibilidade observada: a verificação estática e a suíte mínima também executam em Python 3.12

## Motivo

O protótipo herdado declara Python 3.11 ou 3.12, mas não possuía uma versão principal nem validação automatizada. Python 3.11 oferece uma base conservadora para as dependências de áudio, visão, PyQt e automação usadas pelo projeto.

A seleção de 3.11 não significa que toda a aplicação já foi validada nesse ambiente. A execução completa depende de hardware, sistema operativo e extras que serão estabilizados nas ANT-011 e ANT-012.

## Política durante a estabilização

- novos trabalhos devem funcionar em Python 3.11;
- compatibilidade com Python 3.12 é mantida quando não exigir comportamento divergente;
- alterações de versão principal exigem um PR próprio com testes do cliente desktop;
- o instalador não deve escolher silenciosamente outra versão;
- dependências específicas de Windows continuam condicionadas por plataforma.

## Verificação sem instalar dependências pesadas

```bash
python -m compileall -q actions core dashboard memory plugins main.py ui.py setup.py
python -m unittest discover -s tests -v
```

Estes comandos validam sintaxe e o núcleo legado isolável. Não substituem um smoke test de voz, câmara, dashboard ou controlo do Windows.
