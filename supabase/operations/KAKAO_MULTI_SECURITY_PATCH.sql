-- REVIEW PATCH: staging correction only; no scheduler/network calls.
begin;
create or replace function private.kakao_my_status() returns jsonb language plpgsql volatile security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user(); result jsonb;
begin
 -- Authenticated owner's abandoned confirmation expires even when delivery gate is OFF.
 update public.kakao_multi_connections set status='revoked',generation=generation+1,encrypted_tokens=null,account_id=null,
 confirmation_hash=null,confirmation_expires_at=null,talk_message_granted=false,updated_at=clock_timestamp()
 where owner_id=u and status='pending_confirmation' and confirmation_expires_at<=clock_timestamp();
 if found then update public.kakao_multi_preferences set enabled=false,updated_at=clock_timestamp() where owner_id=u; end if;
 update public.kakao_multi_oauth set ticket_hash=null,state_hash=null,browser_hash=null,
 status=case when status='consumed' then 'consumed' else 'cancelled' end
 where owner_id=u and expires_at<=clock_timestamp() and (ticket_hash is not null or state_hash is not null or browser_hash is not null);
 select jsonb_build_object('connection_status',coalesce(c.status,'disconnected'),
 'enabled',coalesce(p.enabled,false),'time',coalesce(left(p.delivery_time::text,5),'08:00'),
 'days',coalesce(to_jsonb(p.days),'[0,1,2,3,4,5,6]'::jsonb),'send_empty',coalesce(p.send_empty,true),
 'admin_paused',coalesce(p.admin_paused,false),'last_outcome',j.outcome,'last_attempt_at',j.claimed_at,
 'can_manage',exists(select 1 from private.sales_scope_for(u,false) s where s.managed and s.member<>u),
 'legacy_personal',private.kakao_service_excluded_owner(u))
 into result from (select u id) me
 left join public.kakao_multi_connections c on c.owner_id=me.id
 left join public.kakao_multi_preferences p on p.owner_id=me.id
 left join lateral(select outcome,claimed_at from public.kakao_multi_jobs where owner_id=u order by claimed_at desc nulls last,id desc limit 1) j on true;
 return result;
end $$;

create or replace function private.kakao_service_legacy_conflict(p_account_id text) returns boolean language plpgsql stable security definer set search_path='' as $$
declare conflict boolean:=false;
begin
 if p_account_id is null or to_regclass('public.dot_kakao_connections') is null then return false; end if;
 execute 'select exists(select 1 from public.dot_kakao_connections where account_id=$1 and status in (''approved'',''pending_owner_confirmation''))' into conflict using p_account_id;
 return conflict;
end $$;

create or replace function private.kakao_service_finish(p_ticket_id uuid,p_generation bigint,p_account_id text,p_encrypted_tokens text,p_receipt_hash text) returns jsonb language plpgsql security definer set search_path='' as $$
declare t public.kakao_multi_oauth; c public.kakao_multi_connections;
begin
 select * into t from public.kakao_multi_oauth where id=p_ticket_id;
 if not found then raise exception 'Invalid connection'; end if;
 -- Consistent connection-first order shared by revoke/begin/finish.
 select * into c from public.kakao_multi_connections where owner_id=t.owner_id for update;
 select * into t from public.kakao_multi_oauth where id=p_ticket_id for update;
 if p_generation is null or t.status<>'exchanging' or t.expires_at<=now() or t.generation<>p_generation or c.generation<>p_generation or c.status<>'connecting'
 or not private.kakao_service_owner_active(t.owner_id) or p_account_id is null or p_account_id !~ '^[0-9]{1,20}$'
 or private.kakao_service_legacy_conflict(p_account_id) or p_receipt_hash is null or p_receipt_hash !~ '^[a-f0-9]{64}$' or p_encrypted_tokens is null or length(p_encrypted_tokens) not between 40 and 32768 then raise exception 'Invalid connection'; end if;
 update public.kakao_multi_connections set status='pending_confirmation',confirmation_hash=p_receipt_hash,confirmation_expires_at=now()+interval '10 minutes',account_id=p_account_id,encrypted_tokens=p_encrypted_tokens,talk_message_granted=true,updated_at=now() where owner_id=t.owner_id;
 update public.kakao_multi_preferences set enabled=false,updated_at=now() where owner_id=t.owner_id;
 update public.kakao_multi_oauth set status='consumed',state_hash=null,browser_hash=null where id=p_ticket_id;
 return jsonb_build_object('pending_confirmation',true);
end $$;

create or replace function private.kakao_confirm_connection(p_receipt_hash text) returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user();
begin
 if p_receipt_hash is null or p_receipt_hash !~ '^[a-f0-9]{64}$' then raise exception 'Invalid confirmation'; end if;
 update public.kakao_multi_connections set status='connected',confirmation_hash=null,confirmation_expires_at=null,updated_at=now()
 where owner_id=u and status='pending_confirmation' and confirmation_hash=p_receipt_hash and confirmation_expires_at>now() and talk_message_granted and not private.kakao_service_excluded_owner(u) and not private.kakao_service_legacy_conflict(account_id);
 if not found then raise exception 'Invalid confirmation'; end if;
 return private.kakao_my_status();
end $$;
revoke all on function private.kakao_service_legacy_conflict(text) from public,anon,authenticated;
grant execute on function private.kakao_service_legacy_conflict(text) to service_role;
create or replace function private.kakao_service_claim(p_job_id uuid,p_run_id uuid) returns jsonb language plpgsql security definer set search_path='' as $$
declare ctl public.kakao_multi_controls; c public.kakao_multi_connections; pref public.kakao_multi_preferences;
 j public.kakao_multi_jobs; b public.kakao_multi_batches; run public.kakao_multi_runs; token uuid;
begin
 -- Read only to identify owner. Real mutation order: controls -> connection -> run -> job.
 select * into j from public.kakao_multi_jobs where id=p_job_id;
 if not found then return jsonb_build_object('claimed',false,'reason','missing'); end if;
 select * into ctl from public.kakao_multi_controls where singleton for update;
 if not found or not ctl.enabled or ctl.cost_verified_until is null or ctl.cost_verified_until<=clock_timestamp() or ctl.monthly_message_budget<=0 or ctl.monthly_function_budget<=0 then return jsonb_build_object('claimed',false,'reason','disabled'); end if;
 select * into c from public.kakao_multi_connections where owner_id=j.owner_id for update;
 select * into run from public.kakao_multi_runs where id=p_run_id for update;
 if not found or run.claimed_job is not null or run.entered_at<=clock_timestamp()-interval '2 minutes' then return jsonb_build_object('claimed',false,'reason','invalid_run'); end if;
 select * into j from public.kakao_multi_jobs where id=p_job_id for update;
 select * into b from public.kakao_multi_batches where id=j.batch_id;
 select * into pref from public.kakao_multi_preferences where owner_id=j.owner_id;
 if j.status<>'reserved' or b.status not in ('reserved','sending') then return jsonb_build_object('claimed',false,'reason','not_reserved'); end if;
 if pref.owner_id is null or c.owner_id is null or private.kakao_service_legacy_conflict(c.account_id) or c.status<>'connected' or not c.talk_message_granted or c.generation<>j.generation or not pref.enabled or pref.admin_paused
 or not private.kakao_service_owner_active(j.owner_id) or b.day<>(clock_timestamp() at time zone 'Asia/Seoul')::date
 or private.kakao_service_snapshot_hash(private.kakao_service_snapshot(j.owner_id,b.day)) is distinct from b.scope_hash then
  update public.kakao_multi_jobs set status='cancelled',outcome='scope_changed',completed_at=clock_timestamp() where batch_id=b.id and status='reserved';
  update public.kakao_multi_batches set status='cancelled',outcome='scope_changed',completed_at=clock_timestamp() where id=b.id;
  return jsonb_build_object('claimed',false,'reason','scope_changed');
 end if;
 if (select count(*) from public.kakao_multi_jobs x join public.kakao_multi_batches y on y.id=x.batch_id where (y.created_at>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul') or y.delivery_deadline>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul')))>ctl.monthly_message_budget
 or (select count(*) from public.kakao_multi_runs where entered_at>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul'))>ctl.monthly_function_budget then
  update public.kakao_multi_batches set status='held',outcome='quota_held' where id=b.id;
  update public.kakao_multi_jobs set status='cancelled',outcome='quota_held',completed_at=clock_timestamp() where batch_id=b.id and status='reserved';
  return jsonb_build_object('claimed',false,'reason','quota_held');
 end if;
 if exists(select 1 from public.kakao_multi_jobs where owner_id=j.owner_id and status='sending')
 or exists(select 1 from public.kakao_multi_jobs where batch_id=j.batch_id and part<j.part and status<>'accepted') then return jsonb_build_object('claimed',false,'reason','previous_incomplete'); end if;
 token:=gen_random_uuid();
 update public.kakao_multi_jobs set status='sending',claimed_at=clock_timestamp(),claim_token=token where id=j.id;
 update public.kakao_multi_batches set status='sending' where id=b.id;
 update public.kakao_multi_runs set claimed_job=j.id where id=p_run_id;
 return jsonb_build_object('claimed',true,'job_id',j.id,'claim_token',token,'owner_id',j.owner_id,'generation',j.generation,'part',j.part,'body',j.body,'encrypted_tokens',c.encrypted_tokens);
end $$;

create or replace function private.kakao_service_validate_claim(p_job_id uuid,p_claim_token uuid) returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.kakao_multi_jobs j join public.kakao_multi_batches b on b.id=j.batch_id
 join public.kakao_multi_connections c on c.owner_id=j.owner_id join public.kakao_multi_preferences p on p.owner_id=j.owner_id
 where j.id=p_job_id and j.claim_token=p_claim_token and j.status='sending' and j.claimed_at>clock_timestamp()-interval '5 minutes'
 and not private.kakao_service_legacy_conflict(c.account_id) and c.status='connected' and c.talk_message_granted and c.generation=j.generation and p.enabled and not p.admin_paused
 and private.kakao_service_owner_active(j.owner_id) and b.day=(clock_timestamp() at time zone 'Asia/Seoul')::date
 and private.kakao_service_snapshot_hash(private.kakao_service_snapshot(j.owner_id,b.day))=b.scope_hash
 and coalesce((private.kakao_service_gate()->>'enabled')::boolean,false)
 and exists(select 1 from public.kakao_multi_controls ctl where ctl.singleton
 and (select count(*) from public.kakao_multi_jobs x join public.kakao_multi_batches y on y.id=x.batch_id where (y.created_at>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul') or y.delivery_deadline>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul')))<=ctl.monthly_message_budget
 and (select count(*) from public.kakao_multi_runs r where r.entered_at>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul'))<=ctl.monthly_function_budget))
$$;
commit;
