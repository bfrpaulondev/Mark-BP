-- ANT-276 D4: SQL isolation assertions. Run against a scratch database
-- with a two-user fixture; every failure must abort the migration check.

-- 1) cross-owner read must return nothing
do $$
declare visible integer;
begin
    set local role authenticated;
    set local request.jwt.claims = '{"sub":"11111111-1111-1111-1111-111111111111"}';
    select count(*) into visible from memories where owner_id <> auth.uid();
    if visible <> 0 then
        raise exception 'RLS FAILURE: cross-owner rows visible (% rows)', visible;
    end if;
end $$;

-- 2) unauthenticated writes must fail
do $$
begin
    set local role anon;
    begin
        insert into memories (owner_id, type, title, content, source_kind)
        values (gen_random_uuid(), 'semantic', 'x', 'y', 'user');
        raise exception 'RLS FAILURE: anon insert succeeded';
    exception when insufficient_privilege or check_violation then
        null; -- expected
    end;
end $$;

-- M2 negative cases: child rows referencing another owner's memory must
-- be blocked by RLS WITH CHECK. Fixture: user A (aaaaaaaa-...) owns
-- memory_A; user B (bbbbbbbb-...) owns memory_B.

-- case 1: A -> memory_A = allowed
do $$
begin
    set local role authenticated;
    perform set_config('request.jwt.claims',
        '{"sub":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}', true);
    insert into memory_relations (owner_id, from_memory, to_memory, relation)
    values ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            '11111111-1111-1111-1111-111111111111'::uuid,  -- memory_A (fixture)
            '11111111-1111-1111-1111-111111111112'::uuid,  -- memory_A2 (fixture)
            'related');
exception when others then
    raise exception 'M2 FAILURE: legitimate same-owner relation was blocked';
end $$;

-- case 2: A -> memory_B = blocked
do $$
begin
    set local role authenticated;
    perform set_config('request.jwt.claims',
        '{"sub":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}', true);
    insert into memory_relations (owner_id, from_memory, to_memory, relation)
    values ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            '11111111-1111-1111-1111-111111111111'::uuid,
            '22222222-2222-2222-2222-222222222222'::uuid,  -- memory_B
            'related');
    raise exception 'M2 FAILURE: cross-owner relation accepted';
exception when insufficient_privilege or check_violation then
    null; -- expected
end $$;

-- case 3: feedback A -> memory_B = blocked
do $$
begin
    set local role authenticated;
    perform set_config('request.jwt.claims',
        '{"sub":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}', true);
    insert into memory_feedback (owner_id, memory_id, helpful)
    values ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            '22222222-2222-2222-2222-222222222222'::uuid, true);
    raise exception 'M2 FAILURE: cross-owner feedback accepted';
exception when insufficient_privilege or check_violation then
    null; -- expected
end $$;

-- case 4: anon writes = blocked
do $$
begin
    set local role anon;
    insert into memories (owner_id, type, title, content, source_kind)
    values (gen_random_uuid(), 'semantic', 'x', 'y', 'user');
    raise exception 'M2 FAILURE: anon insert succeeded';
exception when insufficient_privilege or check_violation then
    null; -- expected
end $$;
