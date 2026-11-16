-- STAGING ONLY after EXCLUSIONS_PATCH. Synthetic fixtures, no external calls, all ROLLBACK.
begin;
create temporary table kakao_exclusion_fixture(owner_id uuid,session_id uuid);
create temporary table kakao_exclusion_results(name text);
grant select on kakao_exclusion_fixture to authenticated,service_role;
grant insert,select on kakao_exclusion_results to authenticated,service_role;
do $$ declare u uuid; sid uuid:=gen_random_uuid(); begin
 select id into u from public.profiles where login_id='qa_staff';
 if u is null then raise exception 'Synthetic fixture missing'; end if;
 insert into auth.sessions(id,user_id) values(sid,u);
 insert into kakao_exclusion_fixture values(u,sid);
 insert into public.kakao_multi_exclusions(owner_id) values(u) on conflict(owner_id) do nothing;
 if not private.kakao_service_excluded_owner(u) then raise exception 'Owner not excluded'; end if;
 if private.kakao_service_owner_active(u) then raise exception 'Excluded owner dispatch authorization active'; end if;
 insert into kakao_exclusion_results values('Persistent service-only exclusion disables owner authorization');
end $$;
set local role authenticated;
select set_config('request.jwt.claims',(select jsonb_build_object('sub',owner_id,'role','authenticated','session_id',session_id)::text from kakao_exclusion_fixture),true);
do $$ declare denied boolean:=false; result jsonb; begin
 if current_user<>'authenticated' then raise exception 'Actual role missing'; end if;
 if has_function_privilege(current_user,'private.kakao_service_excluded_owner(uuid)','execute') then raise exception 'Exclusion lookup helper publicly exposed'; end if;
 begin perform 1 from public.kakao_multi_exclusions;exception when insufficient_privilege then denied:=true;end;
 if not denied then raise exception 'Authenticated can read service exclusions'; end if;
 result:=public.kakao_my_status();
 if (result->>'legacy_personal')::boolean is distinct from true then raise exception 'Own legacy status not projected'; end if;
 insert into kakao_exclusion_results values('Own status shows legacy flag without exposing exclusions table/helper');
end $$;
reset role;
set local role service_role;
select set_config('request.jwt.claims','{"role":"service_role"}',true);
do $$ declare denied boolean:=false; u uuid; begin
 if current_user<>'service_role' then raise exception 'Actual service role missing'; end if;
 if not has_function_privilege(current_user,'public.kakao_service_begin(uuid,text)','execute') then raise exception 'Test cannot distinguish ACL failure'; end if;
 select owner_id into u from kakao_exclusion_fixture;
 begin perform public.kakao_service_begin(u,repeat('b',64));exception when insufficient_privilege then denied:=true;end;
 if not denied then raise exception 'Service begin accepted excluded owner'; end if;
 insert into kakao_exclusion_results values('Authorized service begin rejects excluded synthetic owner');
end $$;
reset role;
do $$ declare owner_att smallint; begin
 select attnum into owner_att from pg_attribute where attrelid='public.kakao_multi_connections'::regclass and attname='owner_id' and not attisdropped;
 if exists(select 1 from pg_constraint where conrelid='public.kakao_multi_connections'::regclass and contype='c' and conkey=array[owner_att]::smallint[] and pg_get_constraintdef(oid) like 'CHECK ((owner_id <> %' and position('::uuid' in pg_get_constraintdef(oid))>0) then raise exception 'Owner-specific literal CHECK still exists'; end if;
 insert into kakao_exclusion_results values('Former owner-specific CHECK removed by metadata match');
end $$;
select jsonb_agg(name) as passed from kakao_exclusion_results;
rollback;
