-- Editing a submitted record never changes the submitted snapshot until resubmission.
create table public.sales_report_drafts(
 id uuid primary key default gen_random_uuid(), owner uuid not null references public.profiles,
 report uuid not null unique references public.sales_reports on delete cascade,
 day date not null, period text not null check(period in ('일일','주간')),
 data jsonb not null, base_revision integer not null, revision integer not null default 1,
 updated_at timestamptz not null default now());
alter table public.sales_report_drafts enable row level security;
revoke all on public.sales_report_drafts from public,anon,authenticated;
grant select on public.sales_report_drafts to authenticated;
create policy report_draft_owner on public.sales_report_drafts for select to authenticated
 using(owner=auth.uid() and private.sales_enabled());

create table public.sales_report_checks(
 report uuid not null references public.sales_reports on delete cascade,
 reviewer uuid not null references public.profiles,
 report_revision integer not null, checked_at timestamptz not null default now(),
 primary key(report,reviewer));
alter table public.sales_report_checks enable row level security;
revoke all on public.sales_report_checks from public,anon,authenticated;
grant select on public.sales_report_checks to authenticated;
create policy report_check_read on public.sales_report_checks for select to authenticated
 using(private.sales_enabled() and exists(select 1 from public.sales_reports r where r.id=report));

create function private.sales_save_report(p_day date,p_period text,p_data jsonb,p_base_revision integer,p_draft_revision integer,p_submit boolean)
returns jsonb language plpgsql security definer set search_path='' as $$
declare r public.sales_reports; d public.sales_report_drafts; k text;
begin
 if auth.uid() is null or not private.sales_enabled() then raise exception '기록 작성 권한이 없습니다' using errcode='42501';end if;
 if p_base_revision is null or p_base_revision<0 or p_draft_revision is null or p_draft_revision<0 or p_period is null or p_data is null or p_period not in ('일일','주간') or p_day is null or p_day>(now() at time zone 'Asia/Seoul')::date or p_submit is null
 or (p_period='주간' and extract(isodow from p_day)<>1) or jsonb_typeof(p_data)<>'object'
 then raise exception '기록 날짜와 내용을 확인해 주세요';end if;
 foreach k in array array['TA','AP','PC','CS','약속 확보','청약'] loop
  if coalesce(p_data->'counts'->>k,'') !~ '^[0-9]{1,8}$' then raise exception '활동 건수는 0 이상의 정수로 입력해 주세요';end if;
 end loop;
 if p_submit and p_period='일일' and not exists(select 1 from jsonb_each_text(p_data->'counts') v where v.key=any(array['TA','AP','PC','CS','약속 확보','청약']) and v.value::int>0)
 and coalesce((p_data->>'no_activity')::boolean,false)=false then raise exception '활동 없는 날 여부를 선택해 주세요';end if;
 perform pg_advisory_xact_lock(hashtextextended(auth.uid()::text||p_period||p_day::text,0));
 select * into r from public.sales_reports where owner=auth.uid() and day=p_day and period=p_period for update;
 if coalesce(r.revision,0)<>p_base_revision then raise exception '다른 화면에서 기록이 변경됐습니다. 최신 기록을 확인해 주세요' using errcode='40001';end if;
 select * into d from public.sales_report_drafts where report=r.id for update;
 if coalesce(d.revision,0)<>p_draft_revision then raise exception '다른 화면에서 수정 초안이 변경됐습니다. 최신 기록을 확인해 주세요' using errcode='40001';end if;
 if r.submitted and not p_submit then
  insert into public.sales_report_drafts(owner,report,day,period,data,base_revision)
  values(auth.uid(),r.id,p_day,p_period,p_data,r.revision)
  on conflict(report) do update set data=excluded.data,base_revision=excluded.base_revision,revision=sales_report_drafts.revision+1,updated_at=now()
  returning * into d;
 else
  if r.id is null then
   insert into public.sales_reports(id,owner,day,period,data,submitted)
   values(gen_random_uuid(),auth.uid(),p_day,p_period,p_data,p_submit) returning * into r;
  else
   update public.sales_reports set data=p_data,submitted=p_submit where id=r.id returning * into r;
  end if;
  delete from public.sales_report_drafts where report=r.id;
  d:=null;
 end if;
 return jsonb_build_object('report',to_jsonb(r),'draft',to_jsonb(d));
end $$;
create function public.sales_save_report(p_day date,p_period text,p_data jsonb,p_base_revision integer,p_draft_revision integer,p_submit boolean default false)
returns jsonb language sql security invoker set search_path='' as $$select private.sales_save_report(p_day,p_period,p_data,p_base_revision,p_draft_revision,p_submit)$$;
revoke all on function private.sales_save_report(date,text,jsonb,integer,integer,boolean),public.sales_save_report(date,text,jsonb,integer,integer,boolean) from public,anon;
grant execute on function private.sales_save_report(date,text,jsonb,integer,integer,boolean),public.sales_save_report(date,text,jsonb,integer,integer,boolean) to authenticated;

create function private.sales_check_report(p_report uuid,p_revision integer) returns boolean
language plpgsql security definer set search_path='' as $$
declare r public.sales_reports;
begin
 if not private.sales_enabled() then raise exception '기록 확인 권한이 없습니다' using errcode='42501';end if;
 select * into r from public.sales_reports where id=p_report for share;
 if p_revision is null or r.id is null or not r.submitted or r.revision<>p_revision
 or not exists(select 1 from private.sales_scope() s where s.member=r.owner and s.managed)
 then raise exception '조회 권한 또는 최신 제출 내용을 확인해 주세요' using errcode='42501';end if;
 insert into public.sales_report_checks(report,reviewer,report_revision) values(r.id,auth.uid(),r.revision)
 on conflict(report,reviewer) do update set report_revision=excluded.report_revision,checked_at=now();
 return true;
end $$;
create function public.sales_check_report(p_report uuid,p_revision integer) returns boolean
language sql security invoker set search_path='' as $$select private.sales_check_report(p_report,p_revision)$$;
revoke all on function private.sales_check_report(uuid,integer),public.sales_check_report(uuid,integer) from public,anon;
grant execute on function private.sales_check_report(uuid,integer),public.sales_check_report(uuid,integer) to authenticated;

create index sales_draft_owner on public.sales_report_drafts(owner);
create index sales_check_reviewer on public.sales_report_checks(reviewer);
