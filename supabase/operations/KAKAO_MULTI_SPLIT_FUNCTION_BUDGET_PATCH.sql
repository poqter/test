-- Independent normal/test worker budgets. No provider-wide cost guarantee.
-- Defaults disable further tests and do not enlarge the existing shared budget.
-- No cron, preferences, time slots, normal batch/job or history deletions.
begin;
alter table public.kakao_multi_runs add column run_kind text not null default 'normal' check(run_kind in ('normal','test'));
update public.kakao_multi_runs r set run_kind='test' where exists(select 1 from public.kakao_multi_test_requests t where t.id=r.id);
-- Classification is assigned only at entry and cannot be rewritten afterward.
create function private.kakao_run_kind_immutable() returns trigger language plpgsql set search_path='' as $$
begin
 if new.run_kind is distinct from old.run_kind then raise exception 'Run kind is immutable';end if;
 return new;
end $$;
create trigger kakao_run_kind_immutable before update of run_kind on public.kakao_multi_runs for each row execute function private.kakao_run_kind_immutable();
revoke all on function private.kakao_run_kind_immutable() from public,anon,authenticated,service_role;
-- Worker writes already go through SECURITY DEFINER entry/claim functions.
revoke insert,update,delete,truncate,references,trigger on public.kakao_multi_runs from service_role;
grant select on public.kakao_multi_runs to service_role;
create table public.kakao_multi_function_budgets(
 singleton boolean primary key default true check(singleton),
 monthly_test_budget integer not null default 0 check(monthly_test_budget>=0),
 monthly_shared_budget integer not null check(monthly_shared_budget>=0)
);
insert into public.kakao_multi_function_budgets(singleton,monthly_shared_budget) select true,monthly_function_budget from public.kakao_multi_controls where singleton;
alter table public.kakao_multi_function_budgets enable row level security;
revoke all on public.kakao_multi_function_budgets from public,anon,authenticated;
grant select,update on public.kakao_multi_function_budgets to service_role;
create function private.kakao_function_budget_ok(p_kind text,p_entering boolean) returns boolean language sql stable security definer set search_path='' as $$
 select coalesce((select
 b.monthly_shared_budget>=c.monthly_function_budget+b.monthly_test_budget
 and case when p_entering then counts.total<b.monthly_shared_budget else counts.total<=b.monthly_shared_budget end
 and case p_kind when 'normal' then case when p_entering then counts.normal<c.monthly_function_budget else counts.normal<=c.monthly_function_budget end
 when 'test' then case when p_entering then counts.tests<b.monthly_test_budget else counts.tests<=b.monthly_test_budget end else false end
 from public.kakao_multi_controls c cross join public.kakao_multi_function_budgets b
 cross join lateral(select count(*) total,count(*) filter(where run_kind='normal') normal,count(*) filter(where run_kind='test') tests
 from public.kakao_multi_runs where entered_at>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul')) counts
 where c.singleton and b.singleton),false)
$$;
create function private.kakao_function_enter(p_run_id uuid,p_kind text) returns boolean language plpgsql security definer set search_path='' as $$
declare c public.kakao_multi_controls;
begin
 if p_run_id is null or p_kind not in ('normal','test') then return false;end if;
 select * into c from public.kakao_multi_controls where singleton for update;
 perform 1 from public.kakao_multi_function_budgets where singleton for update;
 if not found or not c.enabled or c.cost_verified_until is null or c.cost_verified_until<=clock_timestamp() or c.monthly_message_budget<=0
 or not private.kakao_function_budget_ok(p_kind,true) then return false;end if;
 if p_kind='normal' and exists(select 1 from public.kakao_multi_test_requests where id=p_run_id) then return false;end if;
 if p_kind='test' and not exists(select 1 from public.kakao_multi_test_requests where id=p_run_id and status='queued') then return false;end if;
 insert into public.kakao_multi_runs(id,run_kind) values(p_run_id,p_kind) on conflict do nothing;
 return found;
end $$;
create or replace function private.kakao_service_tick_enter(p_run_id uuid) returns boolean language sql security definer set search_path='' as $$select private.kakao_function_enter(p_run_id,'normal')$$;
-- Modify only exact budget expressions in installed bodies; abort on drift.
-- This preserves whichever latest deadline/midnight/security patch is installed.
do $$declare def text;old text;replacement text;sig text;begin
 for sig,old,replacement in select * from (values
 ('private.kakao_service_enqueue_tick(uuid,bigint)',
 '(select count(*) from public.kakao_multi_runs where entered_at>=(date_trunc(''month'',clock_timestamp() at time zone ''Asia/Seoul'') at time zone ''Asia/Seoul''))>=ctl.monthly_function_budget',
 'not private.kakao_function_budget_ok(''normal'',true)'),
 ('private.kakao_service_claim(uuid,uuid)',
 '(select count(*) from public.kakao_multi_runs where entered_at>=(date_trunc(''month'',clock_timestamp() at time zone ''Asia/Seoul'') at time zone ''Asia/Seoul''))>ctl.monthly_function_budget',
 'not private.kakao_function_budget_ok(''normal'',false)'),
 ('private.kakao_service_validate_claim(uuid,uuid)',
 '(select count(*) from public.kakao_multi_runs r where r.entered_at>=(date_trunc(''month'',clock_timestamp() at time zone ''Asia/Seoul'') at time zone ''Asia/Seoul''))<=ctl.monthly_function_budget',
 'private.kakao_function_budget_ok(''normal'',false)'),
 ('private.kakao_test_enqueue(uuid,uuid)',
 '(select count(*) from public.kakao_multi_runs where entered_at>=(date_trunc(''month'',at_time at time zone ''Asia/Seoul'') at time zone ''Asia/Seoul''))>=ctl.monthly_function_budget-2',
 'not private.kakao_function_budget_ok(''test'',true)'),
 ('private.kakao_test_claim(text)',
 '(select count(*) from public.kakao_multi_runs where entered_at>=(date_trunc(''month'',clock_timestamp() at time zone ''Asia/Seoul'') at time zone ''Asia/Seoul''))>=function_budget-2',
 'not private.kakao_function_budget_ok(''test'',true)')
 ) changes(sig,old,replacement) loop
 select pg_get_functiondef(sig::regprocedure) into def;
 if strpos(def,old)=0 or length(def)-length(replace(def,old,''))<>length(old) then raise exception 'Budget patch drift: %',sig;end if;
 def:=replace(def,old,replacement);
 if sig='private.kakao_service_claim(uuid,uuid)' then
  if strpos(def,'run.claimed_job is not null')=0 then raise exception 'Normal claim run guard drift';end if;
  def:=replace(def,'run.claimed_job is not null','run.run_kind<>''normal'' or run.claimed_job is not null');
 end if;
 if sig='private.kakao_test_claim(text)' then
  if strpos(def,'private.kakao_service_tick_enter(t.id)')=0 then raise exception 'Test claim entry drift';end if;
  def:=replace(def,'private.kakao_service_tick_enter(t.id)','private.kakao_function_enter(t.id,''test'')');
 end if;
 if sig='private.kakao_test_enqueue(uuid,uuid)' then
  def:=replace(def,' ticket:=encode(', ' if exists(select 1 from public.kakao_multi_runs where id=p_request_id) then raise exception ''Request ID already used by a run'';end if;'||chr(10)||' ticket:=encode(');
 end if;
 execute def;
 end loop;
end $$;
-- Test run IDs cannot authorize normal due discovery either.
do $$declare def text;begin
 select pg_get_functiondef('private.kakao_service_due(uuid,integer)'::regprocedure) into def;
 if strpos(def,'where id=p_run_id and entered_at>')=0 then raise exception 'Due run guard drift';end if;
 execute replace(def,'where id=p_run_id and entered_at>','where id=p_run_id and run_kind=''normal'' and entered_at>');
end $$;
revoke all on function private.kakao_function_budget_ok(text,boolean),private.kakao_function_enter(uuid,text) from public,anon,authenticated,service_role;
-- Existing SECURITY DEFINER wrappers remain the only callable entrypoints.
commit;
