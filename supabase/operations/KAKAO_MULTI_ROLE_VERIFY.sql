-- STAGING ONLY. All fixtures and tests roll back; no network. Run after SECURITY_PATCH.
begin;
create temporary table kakao_role_fixture(owner_id uuid,peer_id uuid,session_id uuid);
create temporary table kakao_role_results(name text);
grant select on kakao_role_fixture to authenticated,anon;
grant insert,select on kakao_role_results to authenticated,anon;
do $$ declare u uuid; v uuid; sid uuid:=gen_random_uuid(); begin
 select id into u from public.profiles where login_id='qa_staff';
 select id into v from public.profiles where login_id='qa_peer';
 if u is null or v is null then raise exception 'Synthetic staging fixtures missing'; end if;
 insert into auth.sessions(id,user_id) values(sid,u);
 insert into kakao_role_fixture values(u,v,sid);
 insert into public.kakao_multi_connections(owner_id,status,generation,account_id,encrypted_tokens,talk_message_granted,confirmation_hash,confirmation_expires_at)
 values(u,'pending_confirmation',1,'900000000099',repeat('expired-token',4),true,repeat('d',64),clock_timestamp()-interval '1 minute')
 on conflict(owner_id) do update set status=excluded.status,generation=excluded.generation,account_id=excluded.account_id,encrypted_tokens=excluded.encrypted_tokens,talk_message_granted=true,confirmation_hash=excluded.confirmation_hash,confirmation_expires_at=excluded.confirmation_expires_at;
 insert into public.kakao_multi_preferences(owner_id,enabled) values(u,false) on conflict(owner_id) do update set enabled=false;
 update public.kakao_multi_controls set enabled=false;
end $$;
set local role authenticated;
select set_config('request.jwt.claims',(select jsonb_build_object('sub',owner_id,'role','authenticated','session_id',session_id)::text from kakao_role_fixture),true);
do $$ declare denied boolean:=false; v uuid; r jsonb; begin
 if current_user<>'authenticated' then raise exception 'Role test not actually authenticated'; end if;
 if exists(select 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname in ('public','private') and p.proname like 'kakao_service_%' and has_function_privilege(current_user,p.oid,'execute')) then raise exception 'Service function exposed'; end if;
 begin perform 1 from public.kakao_multi_connections; exception when insufficient_privilege then denied:=true; end;
 if not denied then raise exception 'Authenticated read tokens table'; end if;
 insert into kakao_role_results values('Authenticated role cannot read private table or execute service RPCs');
 denied:=false;begin perform public.kakao_service_gate(); exception when insufficient_privilege then denied:=true; end;
 if not denied then raise exception 'Authenticated service RPC executed'; end if;
 select peer_id into v from kakao_role_fixture;
 denied:=false;begin perform public.kakao_admin_history(v,7); exception when insufficient_privilege then denied:=true; end;
 if not denied then raise exception 'Cross-user history allowed'; end if;
 denied:=false;begin perform public.kakao_admin_pause(v,true); exception when insufficient_privilege then denied:=true; end;
 if not denied then raise exception 'Cross-user pause allowed'; end if;
 insert into kakao_role_results values('Authenticated staff cannot read another user history or pause them');
 r:=public.kakao_my_status();
 if r->>'connection_status'<>'revoked' then raise exception 'Expired confirmation stuck with gate off'; end if;
 insert into kakao_role_results values('Own status purges expired confirmation while send gate is OFF');
end $$;
reset role;
do $$ begin
 if exists(select 1 from public.kakao_multi_connections c join kakao_role_fixture f on f.owner_id=c.owner_id where c.encrypted_tokens is not null or c.account_id is not null or c.confirmation_hash is not null or c.generation<>2) then raise exception 'Expiry cleanup retained secret data or generation'; end if;
end $$;
set local role anon;
select set_config('request.jwt.claims','{"role":"anon"}',true);
do $$ declare denied boolean:=false; begin
 if current_user<>'anon' then raise exception 'Role test not actually anon'; end if;
 if exists(select 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname in ('public','private') and p.proname like 'kakao_%' and has_function_privilege(current_user,p.oid,'execute')) then raise exception 'Anonymous function exposed'; end if;
 begin perform 1 from public.kakao_multi_jobs; exception when insufficient_privilege then denied:=true; end;
 if not denied then raise exception 'Anon read message table'; end if;
 denied:=false;begin perform public.kakao_my_status(); exception when insufficient_privilege then denied:=true; end;
 if not denied then raise exception 'Anon status RPC executed'; end if;
 insert into kakao_role_results values('Anon role cannot read message table or execute any Kakao RPC');
end $$;
reset role;
-- Mock only when the legacy table is absent on staging; never mutate an existing legacy table.
do $$ declare u uuid; tid uuid:=gen_random_uuid(); denied boolean:=false; begin
 if to_regclass('public.dot_kakao_connections') is not null then
  insert into kakao_role_results values('Legacy collision fixture skipped: existing legacy table intentionally untouched');return;
 end if;
 create table public.dot_kakao_connections(account_id text,status text);
 insert into public.dot_kakao_connections values('900000000098','approved');
 select owner_id into u from kakao_role_fixture;
 update public.kakao_multi_connections set status='connecting',generation=3 where owner_id=u;
 insert into public.kakao_multi_oauth(id,owner_id,generation,ticket_hash,status,expires_at) values(tid,u,3,repeat('e',64),'exchanging',clock_timestamp()+interval '10 minutes');
 begin perform public.kakao_service_finish(tid,3,'900000000098',repeat('synthetic-cipher',4),repeat('f',64));exception when raise_exception then denied:=true;end;
 if not denied then raise exception 'Legacy Kakao account duplicate accepted'; end if;
 insert into kakao_role_results values('Legacy approved Kakao account cannot finish a different workspace connection');
end $$;
select jsonb_agg(name) as passed from kakao_role_results;
rollback;
