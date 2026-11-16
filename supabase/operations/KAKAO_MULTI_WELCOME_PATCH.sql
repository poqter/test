-- LOCAL REVIEW: first-ready welcome, lifelong owner ledger, normal budgets, no retrofit sends.
begin;
create table public.kakao_multi_welcomes(
 owner_id uuid primary key references public.profiles(id),id uuid not null unique default gen_random_uuid(),
 status text not null check(status in('legacy_excluded','waiting_setup','queued','processing','accepted','failed','uncertain','expired','suppressed_existing_delivery')),
 first_confirmed_at timestamptz,ready_at timestamptz,day date,regular_not_before date,generation bigint,
 batch_id uuid unique references public.kakao_multi_batches(id),ticket_hash text unique,ticket_expires_at timestamptz,
 expires_at timestamptz,claim_token uuid,scope_hash text,completed_at timestamptz
);
alter table public.kakao_multi_welcomes enable row level security;
revoke all on public.kakao_multi_welcomes from public,anon,authenticated,service_role;
grant select on public.kakao_multi_welcomes to service_role;
insert into public.kakao_multi_welcomes(owner_id,status) select owner_id,'legacy_excluded' from (select owner_id from public.kakao_multi_connections union select owner_id from public.kakao_multi_batches union select owner_id from public.kakao_multi_test_requests) legacy;
alter table public.kakao_multi_batches drop constraint kakao_multi_batches_outcome_check;
alter table public.kakao_multi_batches add constraint kakao_multi_batches_outcome_check check(outcome in('api_accepted','setup_failed','reauth_required','outcome_uncertain','revoked','paused','quota_held','empty_day_skipped','scope_changed','schedule_missed','welcome_day_reserved'));
create function private.kakao_welcome_maybe_ready(p_owner uuid) returns void language plpgsql security definer set search_path='' as $$
declare c public.kakao_multi_connections;w public.kakao_multi_welcomes;p public.kakao_multi_preferences;d date;ts timestamptz:=clock_timestamp();ticket text;endpoint text;bid uuid;netid bigint;
begin
 select * into c from public.kakao_multi_connections where owner_id=p_owner for update;
 if not found then return;end if;
 select * into w from public.kakao_multi_welcomes where owner_id=p_owner for update;
 if not found then insert into public.kakao_multi_welcomes(owner_id,status) values(p_owner,'waiting_setup');select * into w from public.kakao_multi_welcomes where owner_id=p_owner;end if;
 if w.status<>'waiting_setup' or c.status<>'connected' or not c.talk_message_granted then return;end if;
 update public.kakao_multi_welcomes set first_confirmed_at=coalesce(first_confirmed_at,ts) where owner_id=p_owner;
 select * into p from public.kakao_multi_preferences where owner_id=p_owner;
 if not found or not p.enabled or p.admin_paused or not private.kakao_weather_region_valid(p.weather_region_key)
 or not private.kakao_service_owner_active(p_owner) or private.kakao_service_legacy_conflict(c.account_id)
 or not coalesce((private.kakao_service_gate()->>'enabled')::boolean,false) then return;end if;
 select tick_endpoint into endpoint from public.kakao_multi_controls where singleton;
 if endpoint is null or not private.kakao_function_budget_ok('normal',true) then return;end if;
 d:=(ts at time zone 'Asia/Seoul')::date;
 insert into public.kakao_multi_batches(owner_id,day,generation,status,outcome,delivery_deadline)
 values(p_owner,d,c.generation,'cancelled','welcome_day_reserved',least(ts+interval '10 minutes',((d+1)::timestamp at time zone 'Asia/Seoul')))
 on conflict(owner_id,day) do nothing returning id into bid;
 if bid is null then update public.kakao_multi_welcomes set status='suppressed_existing_delivery',completed_at=ts where owner_id=p_owner;return;end if;
 ticket:=encode(extensions.gen_random_bytes(32),'hex');
 update public.kakao_multi_welcomes set status='queued',ready_at=ts,day=d,regular_not_before=d+1,generation=c.generation,batch_id=bid,
 ticket_hash=encode(extensions.digest(ticket,'sha256'),'hex'),ticket_expires_at=least(ts+interval '2 minutes',((d+1)::timestamp at time zone 'Asia/Seoul')),
 expires_at=least(ts+interval '10 minutes',((d+1)::timestamp at time zone 'Asia/Seoul')) where owner_id=p_owner;
 netid:=net.http_post(url:=regexp_replace(endpoint,'/hwarang-kakao/tick$','/hwarang-kakao-welcome'),headers:='{"Content-Type":"application/json"}'::jsonb,body:=jsonb_build_object('ticket',ticket),timeout_milliseconds:=60000);
 if netid is null then raise exception 'Could not enqueue welcome';end if;
end $$;
create function private.kakao_welcome_ready_trigger() returns trigger language plpgsql security definer set search_path='' as $$
begin perform private.kakao_welcome_maybe_ready(new.owner_id);return new;end $$;
-- No rows are modified when these triggers are installed.
create trigger kakao_welcome_connection_ready after insert or update of status on public.kakao_multi_connections for each row execute function private.kakao_welcome_ready_trigger();
create trigger kakao_welcome_preferences_ready after insert or update on public.kakao_multi_preferences for each row execute function private.kakao_welcome_ready_trigger();
create function private.kakao_welcome_validate(p_id uuid,p_claim_token uuid) returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.kakao_multi_welcomes w join public.kakao_multi_connections c using(owner_id) join public.kakao_multi_preferences p using(owner_id)
 where w.id=p_id and w.claim_token=p_claim_token and w.status='processing' and w.expires_at>clock_timestamp() and w.ticket_expires_at>clock_timestamp()
 and w.day=(clock_timestamp() at time zone 'Asia/Seoul')::date and c.generation=w.generation and c.status='connected' and c.talk_message_granted
 and p.enabled and not p.admin_paused and private.kakao_weather_region_valid(p.weather_region_key) and private.kakao_service_owner_active(w.owner_id)
 and not private.kakao_service_legacy_conflict(c.account_id) and coalesce((private.kakao_service_gate()->>'enabled')::boolean,false)
 and private.kakao_function_budget_ok('normal',false)
 and (select count(*) from public.kakao_multi_jobs j join public.kakao_multi_batches b on b.id=j.batch_id where b.created_at>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul') or b.delivery_deadline>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul'))<=(select monthly_message_budget from public.kakao_multi_controls where singleton)
 and not exists(select 1 from public.kakao_multi_jobs where batch_id=w.batch_id and status in('uncertain','failed','cancelled'))
 and private.kakao_service_snapshot_hash(private.kakao_service_snapshot(w.owner_id,w.day))=w.scope_hash)
$$;
create function private.kakao_welcome_claim(p_ticket_hash text) returns jsonb language plpgsql security definer set search_path='' as $$
declare w public.kakao_multi_welcomes;c public.kakao_multi_connections;s jsonb;token uuid:=gen_random_uuid();parts jsonb;
begin
 perform 1 from public.kakao_multi_controls where singleton for update;
 select * into w from public.kakao_multi_welcomes where ticket_hash=p_ticket_hash;
 if not found then return null;end if;
 select * into c from public.kakao_multi_connections where owner_id=w.owner_id for update;
 select * into w from public.kakao_multi_welcomes where id=w.id for update;
 if w.status<>'queued' or w.ticket_expires_at<=clock_timestamp() or w.expires_at<=clock_timestamp() or w.day<>(clock_timestamp() at time zone 'Asia/Seoul')::date then return null;end if;
 if c.status<>'connected' or c.generation<>w.generation or not c.talk_message_granted or not private.kakao_service_owner_active(w.owner_id)
 or private.kakao_service_legacy_conflict(c.account_id) or not exists(select 1 from public.kakao_multi_preferences p where p.owner_id=w.owner_id and p.enabled and not p.admin_paused and private.kakao_weather_region_valid(p.weather_region_key)) then return null;end if;
 if exists(select 1 from public.kakao_multi_jobs where batch_id=w.batch_id and status in('sending','uncertain','failed','cancelled')) then return null;end if;
 s:=private.kakao_service_snapshot(w.owner_id,w.day);
 if w.scope_hash is not null and w.scope_hash<>private.kakao_service_snapshot_hash(s) then return null;end if;
 if not private.kakao_service_tick_enter(gen_random_uuid()) then return null;end if;
 update public.kakao_multi_welcomes set status='processing',claim_token=token,scope_hash=private.kakao_service_snapshot_hash(s) where id=w.id;
 update public.kakao_multi_batches set scope_hash=private.kakao_service_snapshot_hash(s) where id=w.batch_id;
 select jsonb_agg(body order by part) into parts from public.kakao_multi_jobs where batch_id=w.batch_id;
 return jsonb_build_object('id',w.id,'owner_id',w.owner_id,'day',w.day,'generation',w.generation,'summary',s,'claim_token',token,'encrypted_tokens',c.encrypted_tokens,'expires_at',w.expires_at,'parts',parts,'next_part',coalesce((select min(part) from public.kakao_multi_jobs where batch_id=w.batch_id and status='reserved'),1));
end $$;
create function private.kakao_welcome_reserve(p_id uuid,p_claim_token uuid,p_parts text[]) returns jsonb language plpgsql security definer set search_path='' as $$
declare w public.kakao_multi_welcomes;budget integer;used integer;
begin
 select monthly_message_budget into budget from public.kakao_multi_controls where singleton for update;
 select * into w from public.kakao_multi_welcomes where id=p_id for update;
 if not private.kakao_welcome_validate(p_id,p_claim_token) or exists(select 1 from public.kakao_multi_jobs where batch_id=w.batch_id) then return jsonb_build_object('reserved',false);end if;
 if p_parts is null or cardinality(p_parts)<1 or array_ndims(p_parts)<>1 or exists(select 1 from unnest(p_parts) x where x is null or length(x)=0 or (select sum(case when ascii(ch)>65535 then 2 else 1 end) from regexp_split_to_table(x,'')ch)>200) then return jsonb_build_object('reserved',false);end if;
 select count(*) into used from public.kakao_multi_jobs j join public.kakao_multi_batches b on b.id=j.batch_id where b.created_at>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul') or b.delivery_deadline>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul');
 if used+cardinality(p_parts)>budget then return jsonb_build_object('reserved',false);end if;
 insert into public.kakao_multi_jobs(batch_id,owner_id,generation,part,body) select w.batch_id,w.owner_id,w.generation,n::integer,body from unnest(p_parts) with ordinality a(body,n);
 return jsonb_build_object('reserved',true);
end $$;
create function private.kakao_welcome_begin_part(p_id uuid,p_claim_token uuid,p_part integer) returns jsonb language plpgsql security definer set search_path='' as $$
declare w public.kakao_multi_welcomes;j public.kakao_multi_jobs;run uuid:=gen_random_uuid();
begin
 perform 1 from public.kakao_multi_controls where singleton for update;
 select * into w from public.kakao_multi_welcomes where id=p_id;
 perform 1 from public.kakao_multi_connections where owner_id=w.owner_id for update;
 select * into w from public.kakao_multi_welcomes where id=p_id for update;
 if not private.kakao_welcome_validate(p_id,p_claim_token) then return jsonb_build_object('claimed',false);end if;
 if exists(select 1 from public.kakao_multi_jobs where owner_id=w.owner_id and status='sending') or exists(select 1 from public.kakao_multi_jobs where batch_id=w.batch_id and part<p_part and status<>'accepted') then return jsonb_build_object('claimed',false);end if;
 select * into j from public.kakao_multi_jobs where batch_id=w.batch_id and part=p_part for update;
 if not found or j.status<>'reserved' or not private.kakao_service_tick_enter(run) then return jsonb_build_object('claimed',false);end if;
 update public.kakao_multi_jobs set status='sending',claim_token=p_claim_token,claimed_at=clock_timestamp() where id=j.id;
 update public.kakao_multi_runs set claimed_job=j.id where id=run;
 return jsonb_build_object('claimed',true,'body',j.body);
end $$;
create function private.kakao_welcome_complete_part(p_id uuid,p_claim_token uuid,p_part integer,p_status text) returns boolean language plpgsql security definer set search_path='' as $$
declare w public.kakao_multi_welcomes;
begin
 if p_status not in('accepted','failed','uncertain') then return false;end if;
 select * into w from public.kakao_multi_welcomes where id=p_id for update;
 if w.status<>'processing' or w.claim_token is distinct from p_claim_token then return false;end if;
 update public.kakao_multi_jobs set status=p_status,outcome=case p_status when 'accepted' then 'api_accepted' when 'uncertain' then 'outcome_uncertain' else 'setup_failed' end,completed_at=clock_timestamp(),claim_token=null where batch_id=w.batch_id and part=p_part and status='sending' and claim_token=p_claim_token;
 if not found then return false;end if;
 if p_status<>'accepted' then
 update public.kakao_multi_jobs set status='cancelled',outcome='setup_failed',completed_at=clock_timestamp() where batch_id=w.batch_id and status='reserved';
 update public.kakao_multi_welcomes set status=p_status,completed_at=clock_timestamp() where id=w.id;
 elsif not exists(select 1 from public.kakao_multi_jobs where batch_id=w.batch_id and status<>'accepted') then
 update public.kakao_multi_welcomes set status='accepted',completed_at=clock_timestamp() where id=w.id;
 end if;
 return true;
end $$;
create function private.kakao_welcome_fail(p_id uuid,p_claim_token uuid,p_reason text default 'setup_failed') returns boolean language plpgsql security definer set search_path='' as $$
declare w public.kakao_multi_welcomes;uncertain boolean;
begin
 if p_reason not in('setup_failed','reauth_required','outcome_uncertain') then return false;end if;
 select * into w from public.kakao_multi_welcomes where id=p_id for update;
 if w.status<>'processing' or w.claim_token is distinct from p_claim_token then return false;end if;
 select exists(select 1 from public.kakao_multi_jobs where batch_id=w.batch_id and status='sending') into uncertain;
 update public.kakao_multi_jobs set status=case when status='sending' then 'uncertain' else 'cancelled' end,outcome=case when status='sending' then 'outcome_uncertain' else p_reason end,completed_at=clock_timestamp(),claim_token=null where batch_id=w.batch_id and status in('sending','reserved');
 update public.kakao_multi_welcomes set status=case when uncertain or p_reason='outcome_uncertain' then 'uncertain' else 'failed' end,completed_at=clock_timestamp() where id=w.id;
 return true;
end $$;
create function private.kakao_welcome_continue(p_id uuid,p_claim_token uuid) returns boolean language plpgsql security definer set search_path='' as $$
declare w public.kakao_multi_welcomes;ticket text;endpoint text;n bigint;
begin
 select * into w from public.kakao_multi_welcomes where id=p_id for update;
 if not private.kakao_welcome_validate(p_id,p_claim_token) or exists(select 1 from public.kakao_multi_jobs where batch_id=w.batch_id and status not in('reserved','accepted')) or not exists(select 1 from public.kakao_multi_jobs where batch_id=w.batch_id and status='reserved') then return false;end if;
 select tick_endpoint into endpoint from public.kakao_multi_controls where singleton;
 ticket:=encode(extensions.gen_random_bytes(32),'hex');
 update public.kakao_multi_welcomes set status='queued',claim_token=null,ticket_hash=encode(extensions.digest(ticket,'sha256'),'hex'),ticket_expires_at=least(clock_timestamp()+interval '2 minutes',expires_at) where id=w.id;
 n:=net.http_post(url:=regexp_replace(endpoint,'/hwarang-kakao/tick$','/hwarang-kakao-welcome'),headers:='{"Content-Type":"application/json"}'::jsonb,body:=jsonb_build_object('ticket',ticket),timeout_milliseconds:=60000);
 if n is null then raise exception 'Could not continue welcome';end if;return true;
end $$;
-- Read-only projection also reconciles abandoned/expired worker state without retrying.
create function private.kakao_welcome_status(p_owner uuid) returns jsonb language sql stable security definer set search_path='' as $$
 select jsonb_build_object('status',case
 when w.status in('processing','queued') and exists(select 1 from public.kakao_multi_jobs where batch_id=w.batch_id and status='uncertain') then 'uncertain'
 when w.status='processing' and (w.ticket_expires_at<=clock_timestamp() or w.expires_at<=clock_timestamp()) then 'uncertain'
 when w.status='queued' and (w.ticket_expires_at<=clock_timestamp() or w.expires_at<=clock_timestamp()) then 'expired'
 else w.status end,'reason',case when w.status='waiting_setup' then
 case when not exists(select 1 from public.kakao_multi_connections c where c.owner_id=w.owner_id and c.status='connected' and c.talk_message_granted) then 'connection_required'
 when not exists(select 1 from public.kakao_multi_preferences p where p.owner_id=w.owner_id and private.kakao_weather_region_valid(p.weather_region_key)) then 'region_required'
 when not exists(select 1 from public.kakao_multi_preferences p where p.owner_id=w.owner_id and p.enabled and not p.admin_paused) then 'preferences_required'
 when not coalesce((private.kakao_service_gate()->>'enabled')::boolean,false) then 'service_unavailable_resave'
 when not private.kakao_function_budget_ok('normal',true) then 'budget_unavailable_resave' else 'save_required' end else null end,'regular_not_before',w.regular_not_before,'ready_day',w.day)
 from public.kakao_multi_welcomes w where owner_id=p_owner
$$;
alter function private.kakao_my_status() rename to kakao_my_status_before_welcome;
create function private.kakao_my_status() returns jsonb language sql volatile security definer set search_path='' as $$
 select private.kakao_my_status_before_welcome()||jsonb_build_object('welcome',private.kakao_welcome_status(private.kakao_require_user()))
$$;
revoke all on function private.kakao_my_status() from public,anon;
grant execute on function private.kakao_my_status() to authenticated;
-- The unique cancelled batch is the atomic day claim. Explicit not-before guards
-- are additional defenses for normal discovery/reservation, never a time change.
create function private.kakao_welcome_regular_allowed(p_owner uuid,p_day date) returns boolean language sql stable security definer set search_path='' as $$
 select not exists(select 1 from public.kakao_multi_welcomes where owner_id=p_owner and regular_not_before is not null and p_day<regular_not_before)
$$;
do $$declare sig text;def text;old text;replacement text;begin
 for sig,old,replacement in select * from (values
 ('private.kakao_service_due(uuid,integer)','and extract(dow from dates.scheduled_day)::integer=any(p.days)','and private.kakao_welcome_regular_allowed(c.owner_id,dates.scheduled_day) and extract(dow from dates.scheduled_day)::integer=any(p.days)'),
 ('private.kakao_service_has_work()','and extract(dow from dates.scheduled_day)::integer=any(p.days)','and private.kakao_welcome_regular_allowed(c.owner_id,dates.scheduled_day) and extract(dow from dates.scheduled_day)::integer=any(p.days)'),
 ('private.kakao_service_reserve(uuid,date,bigint,text[],text)','if p_day is null','if not private.kakao_welcome_regular_allowed(p_owner,p_day) or p_day is null')
 ) x(sig,old,replacement) loop
 select pg_get_functiondef(sig::regprocedure) into def;
 if strpos(def,old)=0 then raise exception 'Welcome day guard drift: %',sig;end if;
 execute replace(def,old,replacement);
 end loop;
end $$;
-- Public service wrappers and minimal ACLs.
create function public.kakao_welcome_claim(p_ticket_hash text) returns jsonb language sql security invoker set search_path='' as $$select private.kakao_welcome_claim(p_ticket_hash)$$;
create function public.kakao_welcome_validate(p_id uuid,p_claim_token uuid) returns boolean language sql security invoker set search_path='' as $$select private.kakao_welcome_validate(p_id,p_claim_token)$$;
create function public.kakao_welcome_reserve(p_id uuid,p_claim_token uuid,p_parts text[]) returns jsonb language sql security invoker set search_path='' as $$select private.kakao_welcome_reserve(p_id,p_claim_token,p_parts)$$;
create function public.kakao_welcome_begin_part(p_id uuid,p_claim_token uuid,p_part integer) returns jsonb language sql security invoker set search_path='' as $$select private.kakao_welcome_begin_part(p_id,p_claim_token,p_part)$$;
create function public.kakao_welcome_complete_part(p_id uuid,p_claim_token uuid,p_part integer,p_status text) returns boolean language sql security invoker set search_path='' as $$select private.kakao_welcome_complete_part(p_id,p_claim_token,p_part,p_status)$$;
create function public.kakao_welcome_fail(p_id uuid,p_claim_token uuid,p_reason text default 'setup_failed') returns boolean language sql security invoker set search_path='' as $$select private.kakao_welcome_fail(p_id,p_claim_token,p_reason)$$;
create function public.kakao_welcome_continue(p_id uuid,p_claim_token uuid) returns boolean language sql security invoker set search_path='' as $$select private.kakao_welcome_continue(p_id,p_claim_token)$$;
do $$declare f record;sig text;begin
 for f in select n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) args from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname in('public','private') and p.proname like 'kakao_welcome_%' loop
 sig:=format('%I.%I(%s)',f.nspname,f.proname,f.args);
 execute 'revoke all on function '||sig||' from public,anon,authenticated,service_role';
 if f.proname in('kakao_welcome_claim','kakao_welcome_validate','kakao_welcome_reserve','kakao_welcome_begin_part','kakao_welcome_complete_part','kakao_welcome_fail','kakao_welcome_continue') then execute 'grant execute on function '||sig||' to service_role';end if;
 end loop;
end $$;
commit;
