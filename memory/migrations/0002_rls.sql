-- ANT-276 D4: row level security — owner isolation, project scope,
-- and explicit separation of service operations.
-- NOT EXECUTED HERE.

alter table memories enable row level security;
alter table memory_relations enable row level security;
alter table memory_feedback enable row level security;

-- Owner isolation: a user only sees own rows.
create policy memories_owner_select on memories
    for select using (auth.uid() = owner_id);
create policy memories_owner_insert on memories
    for insert with check (auth.uid() = owner_id);
create policy memories_owner_update on memories
    for update using (auth.uid() = owner_id) with check (auth.uid() = owner_id);
create policy memories_owner_delete on memories
    for delete using (auth.uid() = owner_id);

create policy memory_relations_owner_all on memory_relations
    for all using (auth.uid() = owner_id) with check (auth.uid() = owner_id);
create policy memory_feedback_owner_all on memory_feedback
    for all using (auth.uid() = owner_id) with check (auth.uid() = owner_id);

-- Service operations (approve/expire/forget) run under an explicit
-- service role and are never exposed to client keys.
create policy memories_service_write on memories
    for all to service_role using (true) with check (true);
