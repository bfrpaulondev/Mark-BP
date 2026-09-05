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

-- M2: child-table integrity — a row may only reference memories owned by
-- the same user. WITH CHECK uses EXISTS against the parent table, so a
-- forged owner_id from the frontend cannot attach a relation/feedback to
-- someone else's memory (ownership is proven server-side, never trusted
-- from the payload).
create policy memory_relations_owner_all on memory_relations
    for all using (auth.uid() = owner_id)
    with check (
        auth.uid() = owner_id
        and exists (select 1 from memories m where m.id = from_memory and m.owner_id = auth.uid())
        and exists (select 1 from memories m where m.id = to_memory and m.owner_id = auth.uid())
    );
create policy memory_feedback_owner_all on memory_feedback
    for all using (auth.uid() = owner_id)
    with check (
        auth.uid() = owner_id
        and exists (select 1 from memories m where m.id = memory_id and m.owner_id = auth.uid())
    );

-- Service operations (approve/expire/forget) run under an explicit
-- service role and are never exposed to client keys.
create policy memories_service_write on memories
    for all to service_role using (true) with check (true);
