begin;
set local lock_timeout='5s';
alter table public.kakao_multi_test_requests add column sample_body text;
create function private.kakao_test_body_valid(v text) returns boolean language sql immutable set search_path='' as $$
 select v is not null and length(btrim(v))>0 and octet_length(v)<=800 and
 (select coalesce(sum(case when ascii(ch)>65535 then 2 else 1 end),0) from regexp_split_to_table(v,'') ch)<=200
$$;
alter table public.kakao_multi_test_requests add constraint kakao_test_sample_body_valid check(sample_body is null or private.kakao_test_body_valid(sample_body));
create function private.kakao_test_enqueue_sample(p_owner uuid,p_request_id uuid,p_body text) returns jsonb language plpgsql security definer set search_path='' as $$
declare result jsonb; old public.kakao_multi_test_requests;
begin
 if not private.kakao_test_body_valid(p_body) then raise exception 'Test text must contain 1-200 UTF16 units';end if;
 perform pg_advisory_xact_lock(1746948683,20261119);
 select * into old from public.kakao_multi_test_requests where id=p_request_id;
 if found and (old.owner_id<>p_owner or old.sample_body is distinct from p_body) then raise exception 'Existing request cannot change';end if;
 result:=private.kakao_test_enqueue(p_owner,p_request_id);
 if result->>'status'='queued' and not coalesce((result->>'reused')::boolean,false) then
  update public.kakao_multi_test_requests set sample_body=p_body where id=p_request_id and owner_id=p_owner and status='queued';
 end if;
 return result;
end $$;
create function public.kakao_request_sample_test(p_request_id uuid,p_body text) returns jsonb language sql security invoker set search_path='' as $$select private.kakao_test_enqueue_sample(private.kakao_require_user(),p_request_id,p_body)$$;
create function public.kakao_service_request_sample_test(p_owner uuid,p_request_id uuid,p_body text) returns jsonb language sql security invoker set search_path='' as $$select private.kakao_test_enqueue_sample(p_owner,p_request_id,p_body)$$;
revoke all on function private.kakao_test_body_valid(text),private.kakao_test_enqueue_sample(uuid,uuid,text),public.kakao_request_sample_test(uuid,text),public.kakao_service_request_sample_test(uuid,uuid,text) from public,anon,authenticated;
grant execute on function private.kakao_test_body_valid(text) to service_role;
grant execute on function private.kakao_test_enqueue_sample(uuid,uuid,text) to service_role;
-- Authenticated calls resolve identity before invoking the internal enqueuer.
create function private.kakao_request_sample_test(p_request_id uuid,p_body text) returns jsonb language plpgsql security definer set search_path='' as $$
begin return private.kakao_test_enqueue_sample(private.kakao_require_user(),p_request_id,p_body);end $$;
revoke all on function private.kakao_request_sample_test(uuid,text) from public,anon;
grant execute on function private.kakao_request_sample_test(uuid,text) to authenticated;
create or replace function public.kakao_request_sample_test(p_request_id uuid,p_body text) returns jsonb language sql security invoker set search_path='' as $$select private.kakao_request_sample_test(p_request_id,p_body)$$;
grant execute on function public.kakao_request_sample_test(uuid,text) to authenticated;
grant execute on function public.kakao_service_request_sample_test(uuid,uuid,text) to service_role;
do $$declare def text;needle text:='''summary'',s,''claim_token'',token';begin
 select pg_get_functiondef('private.kakao_test_claim(text)'::regprocedure) into def;
 if strpos(def,needle)=0 then raise exception 'Claim drift';end if;
 execute replace(def,needle,'''summary'',s,''sample_body'',t.sample_body,''claim_token'',token');
 if not private.kakao_test_body_valid(repeat('가',200)) or private.kakao_test_body_valid(repeat('가',201)) or not private.kakao_test_body_valid(repeat('😀',100)) or private.kakao_test_body_valid(repeat('😀',101)) or private.kakao_test_body_valid('   ') then raise exception 'Body validator failed';end if;
 if has_function_privilege('anon','public.kakao_request_sample_test(uuid,text)','execute') or has_function_privilege('authenticated','public.kakao_service_request_sample_test(uuid,uuid,text)','execute') or has_function_privilege('authenticated','private.kakao_test_enqueue_sample(uuid,uuid,text)','execute') then raise exception 'ACL failure';end if;
end $$;
commit;