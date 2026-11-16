-- Definitive provider revocation only; no network, no automatic retries.
begin;
create or replace function private.kakao_service_require_reauth(p_owner uuid,p_generation bigint) returns boolean language plpgsql security definer set search_path='' as $$
begin
 -- Lock connection before jobs, matching claim/complete and revocation order.
 perform 1 from public.kakao_multi_connections where owner_id=p_owner for update;
 update public.kakao_multi_connections set status='reauth_required',generation=generation+1,
 encrypted_tokens=null,talk_message_granted=false,confirmation_hash=null,confirmation_expires_at=null,updated_at=clock_timestamp()
 where owner_id=p_owner and generation=p_generation and status='connected';
 if not found then return false; end if;
 update public.kakao_multi_preferences set enabled=false,updated_at=clock_timestamp() where owner_id=p_owner;
 update public.kakao_multi_oauth set status='cancelled',ticket_hash=null,state_hash=null,browser_hash=null
 where owner_id=p_owner and status in ('invited','started','exchanging');
 update public.kakao_multi_jobs set status='cancelled',outcome='reauth_required',completed_at=clock_timestamp()
 where owner_id=p_owner and generation=p_generation and status='reserved';
 -- Leave in-flight job and its claim token intact: completion records the actual result.
 update public.kakao_multi_batches set status='failed',outcome='reauth_required',completed_at=clock_timestamp()
 where owner_id=p_owner and generation=p_generation and status in ('reserved','sending','held');
 return true;
end $$;
create or replace function public.kakao_service_require_reauth(p_owner uuid,p_generation bigint) returns boolean language sql security invoker set search_path='' as $$ select private.kakao_service_require_reauth(p_owner,p_generation) $$;
revoke all on function private.kakao_service_require_reauth(uuid,bigint),public.kakao_service_require_reauth(uuid,bigint) from public,anon,authenticated;
grant execute on function private.kakao_service_require_reauth(uuid,bigint),public.kakao_service_require_reauth(uuid,bigint) to service_role;
create or replace function private.kakao_service_complete(p_job_id uuid,p_claim_token uuid,p_status text) returns boolean language plpgsql security definer set search_path='' as $$
declare j public.kakao_multi_jobs; outcome_value text; deadline timestamptz;
begin
 if p_status is null or p_status not in ('accepted','uncertain','failed') or p_claim_token is null then return false; end if;
 select * into j from public.kakao_multi_jobs where id=p_job_id;
 if not found then return false; end if;
 perform 1 from public.kakao_multi_connections where owner_id=j.owner_id for update;
 select * into j from public.kakao_multi_jobs where id=p_job_id for update;
 if j.status<>'sending' or j.claim_token is distinct from p_claim_token then return false; end if;
 select delivery_deadline into deadline from public.kakao_multi_batches where id=j.batch_id;
 outcome_value:=case when p_status='failed' and exists(select 1 from public.kakao_multi_batches where id=j.batch_id and outcome='reauth_required') then 'reauth_required' when p_status='failed' and (deadline is null or deadline<=clock_timestamp()) then 'schedule_missed' else case p_status when 'accepted' then 'api_accepted' when 'uncertain' then 'outcome_uncertain' else 'setup_failed' end end;
 update public.kakao_multi_jobs set status=p_status,outcome=outcome_value,completed_at=clock_timestamp(),claim_token=null where id=j.id;
 if p_status<>'accepted' then
  update public.kakao_multi_jobs set status='cancelled',outcome=outcome_value,completed_at=clock_timestamp() where batch_id=j.batch_id and status='reserved';
  update public.kakao_multi_batches set status=p_status,outcome=outcome_value,completed_at=clock_timestamp() where id=j.batch_id;
 elsif (deadline is null or deadline<=clock_timestamp()) and exists(select 1 from public.kakao_multi_jobs where batch_id=j.batch_id and status='reserved') then
  update public.kakao_multi_jobs set status='cancelled',outcome='schedule_missed',completed_at=clock_timestamp() where batch_id=j.batch_id and status='reserved';
  update public.kakao_multi_batches set status='failed',outcome='schedule_missed',completed_at=clock_timestamp() where id=j.batch_id;
 elsif not exists(select 1 from public.kakao_multi_jobs where batch_id=j.batch_id and status<>'accepted') then
  update public.kakao_multi_batches set status='accepted',outcome='api_accepted',completed_at=clock_timestamp() where id=j.batch_id;
 end if;
 return true;
end $$;
commit;
