# Local Perception Cache (ANT-265)

Estado: implementação de código da primeira fatia completa; validação física Windows continua em ANT-275.

## Objectivo

Reduzir escaladas desnecessárias para VLM sem transformar heurísticas locais em
"visão semântica" falsa. A ordem desta fatia é conservadora:

```text
frame MSS local
→ mudança local / fingerprint
→ UIA determinística quando o pedido é explícito e inequívoco
→ VLM quando a semântica continua necessária
```

## Frame/keyframe cache

`core/computer_use/perception_cache.py` introduz um cache process-local,
bounded e com TTL. O cache retém apenas:

- digest técnico do frame;
- perceptual hash de 64 bits;
- bucket de luminância;
- scope técnico;
- timestamps monotónicos.

Não retém screenshot, JPEG, OCR, texto de UI ou buffers de pixels.

A igualdade exacta usa digest do byte stream RGB completo. O perceptual hash
serve apenas como metadata/keyframe classification e **não** autoriza ocultar
um frame. Isto evita tratar pequenas assinaturas amostradas como prova de que
duas imagens são iguais.

Mudanças de topologia limpam o cache. O cache também força keyframes
periódicos na classificação para não manter estado visual indefinidamente.

## Captura

`RealtimeDesktopCapture` passa a publicar em `FrameSnapshot`:

- `perception_digest`;
- `perception_keyframe`;
- `perception_duplicate`;
- `perception_distance`.

A captura mantém contadores de keyframes e duplicados exactos suprimidos. O
algoritmo antigo de `change_score` continua activo; esta fatia não reduz a
sensibilidade usando apenas similaridade perceptual.

## UIA-first

`core/computer_use/local_perception.py` implementa uma rota sem modelo apenas
para um caso deliberadamente estreito:

1. existe uma janela alvo explícita;
2. o pedido é uma instrução simples de click;
3. o nome do controlo é explícito;
4. UI Automation encontra exactamente um controlo visível/activo com esse
   nome;
5. o tipo é interactivo conhecido;
6. o rectângulo está dentro do frame actualmente capturado;
7. não existem termos de risco/destrutivos/financeiros/confirmatórios.

Qualquer ambiguidade, plataforma sem UIA, erro de enumeração, controlo fora do
frame, pedido multi-etapa ou acção sensível cai imediatamente para o VLM.

Para evitar repetição de clicks depois de uma acção, a rota UIA local só é
considerada no primeiro passo sem histórico. Recovery posterior continua a
replanear normalmente.

## Cache UIA

O pequeno cache de sugestões UIA guarda apenas coordenadas, tipo de controlo e
expiração. Objectivo, label do controlo e título da janela entram apenas num
digest de request e não são retidos como texto.

## Telemetria

Quando UIA resolve o primeiro passo sem VLM:

- `calls_saved += 1`;
- `local_perception_routes += 1`;
- cache reuse usa a categoria `cache_hit` existente no ANT-264;
- `model_calls` continua a contar somente requests reais ao provider.

A UI pode consumir estes contadores posteriormente sem inventar poupança.

## Configuração

A rota local pode ser desactivada com:

```text
ANTONELLA_COMPUTER_USE_LOCAL_PERCEPTION_ENABLED=false
```

Default: `true`.

## Limitações

- UIA-first nesta fatia resolve apenas clicks simples e inequívocos; não tenta
  compreender tarefas multi-etapa nem preencher texto.
- O cache não guarda output do modelo e, portanto, não reutiliza planos VLM
  potencialmente sensíveis.
- Não há OCR local nesta fatia.
- OpenCV não é necessário para o fingerprint: reutiliza o frame NumPy que MSS
  já criou, evitando uma segunda pipeline de imagem. OpenCV continua disponível
  para futuras percepções locais que realmente precisem de CV.
- CI Windows valida imports/testes, não DPI/multi-monitor/UIA físico real.
