-- Remove arbitrary test count/cooldown limits. Shared free budgets remain authoritative.
-- Preserves all history, permissions, pending/uncertain safety and normal schedule.
-- Does NOT change any configured budget, cost gate, preference or cron.
begin;
create or replace function private.kakao_test_enqueue(p_owner uuid,p_request_id uuid) returns jsonb language plpgsql security definer set search_path='' as $$
declare t public.kakao_multi_test_requests;c public.kakao_multi_connections;ctl public.kakao_multi_controls;
 ticket text;network_id bigint;at_time timestamptz:=clock_timestamp();endpoint text;
begin
 if p_owner is null or p_request_id is null then raise exception 'Invalid request';end if;
 -- Serialize request idempotency and pending-request checks across every caller.
 perform pg_advisory_xact_lock(1746948683,20261119);
 select * into t from public.kakao_multi_test_requests where id=p_request_id;
 if found then
  if t.owner_id<>p_owner then raise exception 'Request belongs to another owner';end if;
  return jsonb_build_object('id',t.id,'status',case when t.status='queued' and t.expires_at<=at_time then 'expired' when t.status='processing' and t.expires_at<=at_time then 'uncertain' else t.status end,'reused',true);
 end if;
 select * into ctl from public.kakao_multi_controls where singleton;
 if not found or not coalesce((private.kakao_service_gate()->>'enabled')::boolean,false)
 or ctl.tick_endpoint is null or ctl.tick_endpoint !~ '^https://[a-z0-9]+\.supabase\.co/functions/v1/hwarang-kakao/tick$' then return jsonb_build_object('status','blocked','reason','service_unavailable');end if;
 select * into c from public.kakao_multi_connections where owner_id=p_owner;
 if not found or c.status<>'connected' or not c.talk_message_granted or not private.kakao_service_owner_active(p_owner)
 or private.kakao_service_legacy_conflict(c.account_id)
 or not exists(select 1 from public.kakao_multi_preferences p where p.owner_id=p_owner and not p.admin_paused and private.kakao_weather_region_valid(p.weather_region_key)) then return jsonb_build_object('status','blocked','reason','connection_unavailable');end if;
 if exists(select 1 from public.kakao_multi_test_requests where owner_id=p_owner and (status in ('processing','uncertain') or (status='queued' and expires_at>at_time))) then return jsonb_build_object('status','blocked','reason','previous_request_pending');end if;
 -- Reserve room for at least a normal tick and a normal send; both paths also enforce the shared budget.
 if (select count(*) from public.kakao_multi_runs where entered_at>=(date_trunc('month',at_time at time zone 'Asia/Seoul') at time zone 'Asia/Seoul'))>=ctl.monthly_function_budget-2 then return jsonb_build_object('status','blocked','reason','function_budget');end if;
 ticket:=encode(extensions.gen_random_bytes(32),'hex');
 insert into public.kakao_multi_test_requests(id,owner_id,ticket_hash,created_at,expires_at,cached_weather_only)
 values(p_request_id,p_owner,encode(extensions.digest(ticket,'sha256'),'hex'),at_time,at_time+interval '3 minutes',false);
 endpoint:=regexp_replace(ctl.tick_endpoint,'/hwarang-kakao/tick$','/hwarang-kakao-test');
 network_id:=net.http_post(url:=endpoint,headers:='{"Content-Type":"application/json"}'::jsonb,body:=jsonb_build_object('ticket',ticket),timeout_milliseconds:=60000);
 if network_id is null then raise exception 'Could not queue test';end if;
 return jsonb_build_object('id',p_request_id,'status','queued','reused',false);
end $$;
create or replace function private.kakao_my_test_status() returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user();t public.kakao_multi_test_requests;at_time timestamptz:=clock_timestamp();used integer;
begin
 select count(*) into used from public.kakao_multi_test_requests where owner_id=u and created_at>=(date_trunc('day',at_time at time zone 'Asia/Seoul') at time zone 'Asia/Seoul');
 select * into t from public.kakao_multi_test_requests where owner_id=u order by created_at desc,id desc limit 1;
 if not found then return jsonb_build_object('status','none','used_today',used);end if;
 return jsonb_build_object('id',t.id,'status',case when t.status='queued' and t.expires_at<=at_time then 'expired' when t.status='processing' and t.expires_at<=at_time then 'uncertain' else t.status end,'created_at',t.created_at,'completed_at',t.completed_at,'used_today',used);
end $$;
commit;
