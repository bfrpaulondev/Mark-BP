-- ANT-276 D6 adapter compatibility: domain MemoryRecord carries bounded
-- metadata used for lifecycle facts such as expiry/conflict resolution.
-- Keep this additive so deployments that already applied 0001 remain valid.

alter table memories
    add column if not exists metadata jsonb not null default '{}'::jsonb;
