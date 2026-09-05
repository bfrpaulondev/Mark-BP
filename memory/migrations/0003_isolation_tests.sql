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
