# Memory Core (ANT-276 D1/D2/D6/D7/D8/D9/D12–D18 núcleo)

Estado: domínio + repositório in-memory + serviço implementados e testados
(14 testes). Supabase adapter físico é follow-up; migrations SQL incluídas
mas NÃO EXECUTADAS (NOT RUN — sem credenciais/BD nesta fase, por desenho).

## Módulos

- `memory/domain.py` — `MemoryType`, `MemoryState`, `SourceKind`,
  `MemoryRecord` (modelo mínimo D2, imutável, confidence bounded 0–1),
  `is_external_source` (D18), `is_strong_preference` (D9,
  `STRONG_PREFERENCE_CONFIDENCE = 0.6`; observação única nunca chega lá —
  default 0.3).
- `memory/repository.py` — Protocol `MemoryRepository` +
  `InMemoryMemoryRepository` (thread-safe, isolamento de owner na fronteira
  de storage, ordenação determinística confidence→recency). Adapter
  Supabase/Postgres chega depois atrás do mesmo Protocol (D6).
- `memory/service.py` — ciclo de vida: `propose` (nunca activa sozinha),
  `approve` (único caminho para ACTIVE; supersession explícita reforma o
  antigo), `retrieve` (só ACTIVE não-expirado, `top_k` budget D17, conteúdo
  externo marcado como informação D18), `supersede` (versionada),
  `archive`/`restore`/`forget` (D14 soft/hard), `explain_source` (D15
  cadeia de proveniência), `strong_preferences` (D9), `expire` (D13).
- Conflitos (D12): proposta sobre subject ocupado por memória activa fica
  PROPOSED com `conflict_with_id` — revisão obrigatória, nunca overwrite
  silencioso.

## Migrations (D3–D5) — NOT RUN

`memory/migrations/0001_memories.sql` (tabelas memories/memory_relations/
memory_feedback, índices owner/project/type/state/expires/lexical
tsvector/pgvector ivfflat), `0002_rls.sql` (RLS: isolamento de owner,
project scope, service_role separado), `0003_isolation_tests.sql`
(assertions SQL de isolamento cross-owner/anon — correr em BD scratch).
Aplicação em produção é decisão do Principal Agent.

## Fora desta slice

- Adapter Supabase concreto (mesmo Protocol); pgvector embeddings reais
  (coluna preparada); comandos naturais D19 (classificação é LLM); Brain
  Studio UI D20 (contratos de serviço já suficientes: list/search/approve/
  correct/archive/forget/explain).
