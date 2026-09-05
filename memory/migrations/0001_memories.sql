-- ANT-276 D3/D5: memories table, relations and indexes.
-- NOT EXECUTED HERE: applied to a real Supabase/Postgres by the principal agent.
-- Versioned, additive-only; never run against production from this repo.

create extension if not exists vector;

create table if not exists memories (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null,
    project_id uuid,
    type text not null check (type in ('working','episodic','semantic','procedural','project','feedback')),
    state text not null default 'proposed' check (state in ('proposed','approved','active','superseded','archived')),
    title text not null,
    content text not null,
    summary text not null default '',
    source_kind text not null check (source_kind in ('user','runtime','external')),
    source_ref text,
    confidence double precision not null default 0.3 check (confidence between 0 and 1),
    sensitivity text not null default 'normal',
    subject text,
    valid_from timestamptz,
    expires_at timestamptz,
    version integer not null default 1,
    supersedes_id uuid references memories (id),
    conflict_with_id uuid references memories (id),
    embedding_model text,
    embedding_version text,
    embedding vector(1536),
    created_at timestamptz not null default now(),
    approved_at timestamptz,
    updated_at timestamptz not null default now(),
    archived_at timestamptz
);

create table if not exists memory_relations (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null,
    from_memory uuid not null references memories (id) on delete cascade,
    to_memory uuid not null references memories (id) on delete cascade,
    relation text not null,
    created_at timestamptz not null default now(),
    unique (from_memory, to_memory, relation)
);

create table if not exists memory_feedback (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null,
    memory_id uuid not null references memories (id) on delete cascade,
    helpful boolean not null,
    note text,
    created_at timestamptz not null default now()
);

-- D5 indexes
create index if not exists memories_owner_idx on memories (owner_id);
create index if not exists memories_owner_project_idx on memories (owner_id, project_id);
create index if not exists memories_type_idx on memories (type);
create index if not exists memories_state_idx on memories (state);
create index if not exists memories_expires_idx on memories (expires_at) where expires_at is not null;
create index if not exists memories_supersedes_idx on memories (supersedes_id) where supersedes_id is not null;
create index if not exists memories_lexical_idx on memories
    using gin (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(content, '')));
create index if not exists memories_embedding_idx on memories
    using ivfflat (embedding vector_cosine_ops) with (lists = 100);
