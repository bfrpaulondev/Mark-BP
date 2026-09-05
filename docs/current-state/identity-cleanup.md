# Identity Cleanup (ANT-272)

Estado: implementado (resíduos visíveis), sem renames internos.

## Âmbito

- `ui.py` (ficheiro legado **morto**, sombreado pelo pacote `ui/`): títulos
  "MARK LI" e badge → "Antonella". Nunca deve ressuscitar a identidade antiga.
- `LogView`: passa a mascarar também o token exacto de produto legado
  "MARK LI" em strings dos motores. **Nomes pessoais não são mascarados** —
  um "Mark" a solo é um nome próprio comum e reescrevê-lo corromperia
  conteúdo real do utilizador (testado).
- Títulos das janelas vivas já eram "Antonella"; sem assets legados
  (.ico/.png) no repo; sem tray icon.

## Fora de âmbito (deliberado)

- `class JarvisUI` mantém-se como nome interno de compatibilidade
  (nenhuma superfície visível a expõe).
- Sem renames em massa, sem alterar imports, sem tocar no core.
