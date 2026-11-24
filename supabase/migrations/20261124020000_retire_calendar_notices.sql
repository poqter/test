-- Keep the empty notices field until older calendar sessions have refreshed.
CREATE OR REPLACE FUNCTION public.sales_calendar_context()
 RETURNS jsonb
 LANGUAGE sql
 STABLE
 SET search_path TO ''
AS $function$
 select jsonb_build_object(
 'members',coalesce((select jsonb_agg(to_jsonb(s)) from private.sales_scope() s),'[]'::jsonb),
 'branch',coalesce((select jsonb_agg(to_jsonb(b)) from private.sales_branch_members() b),'[]'::jsonb),
 'entry',case when coalesce(nullif(current_setting('request.headers',true),'')::jsonb->>'x-hwarang-calendar-entry','')='1' then
 jsonb_build_object(
 'day',(now() at time zone 'Asia/Seoul')::date,
 'summary',coalesce((select jsonb_agg(to_jsonb(s)) from private.sales_calendar_days((now() at time zone 'Asia/Seoul')::date,(now() at time zone 'Asia/Seoul')::date) s),'[]'::jsonb),
 'empty_days',coalesce((select jsonb_agg(jsonb_build_object('owner',owner)) from public.sales_empty_days where day=(now() at time zone 'Asia/Seoul')::date),'[]'::jsonb),
 'notices','[]'::jsonb)
 else null end)
$function$
;
-- Keep support recipient validation and the original request on the event/report.
CREATE OR REPLACE FUNCTION private.sales_support_notify()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare target uuid; content text; previous_content text; previous_target uuid; sender text; source_label text; fingerprint text;
begin
 if tg_table_name='sales_events' then
  content:=btrim(coalesce(new.help,''));target:=new.help_recipient;
  if tg_op='UPDATE' then previous_content:=btrim(coalesce(old.help,''));previous_target:=old.help_recipient;end if;
  if new.deleted_at is not null or new.status in ('취소','연기') then return new;end if;
  source_label:=new.day::text||' · '||new.title;
 else
  if not new.submitted then return new;end if;
  content:=btrim(coalesce(new.data->>'help',''));target:=nullif(new.data->>'help_recipient','')::uuid;
  if tg_op='UPDATE' and old.submitted then previous_content:=btrim(coalesce(old.data->>'help',''));previous_target:=nullif(old.data->>'help_recipient','')::uuid;end if;
  source_label:=new.day::text||case when new.period='주간' then ' ~ '||(new.day+6)::text else '' end||' · '||new.period||' 활동 기록';
 end if;
 if content='' then return new;end if;
 -- Preserve untouched historical requests that predate recipient selection.
 if target is null and content=previous_content and previous_target is null then return new;end if;
 if target is null or not exists(select 1 from private.sales_support_candidates(new.owner) c where c.member=target)
 then raise exception '연결된 관리자 중 지원 요청 대상을 선택해 주세요' using errcode='23514';end if;
 return new;
end $function$
;
drop trigger if exists sales_notice_reply on public.sales_reviews;
drop trigger if exists sales_notice_change on public.sales_events;

CREATE OR REPLACE FUNCTION public.sales_check_daily_period(p_owner uuid, p_first date, p_last date, p_versions jsonb, p_message text, p_request uuid)
 RETURNS boolean
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
declare actual jsonb;r record;
begin
 if auth.uid() is null or not private.sales_enabled() or not exists(select 1 from private.sales_scope() s where s.member=p_owner and s.managed) then raise exception '검토 권한을 확인해 주세요' using errcode='42501';end if;
 if p_first is null or p_last is null or p_last<p_first or p_last-p_first>366 or p_request is null then raise exception '검토 기간을 확인해 주세요';end if;
 perform pg_advisory_xact_lock(hashtextextended('daily.review.'||auth.uid()::text||p_owner::text,0));
 for r in select * from public.sales_reports where owner=p_owner and period='일일' and submitted and day between p_first and p_last order by id for share loop
  actual:=coalesce(actual,'{}'::jsonb)||jsonb_build_object(r.id::text,r.revision);
 end loop;
 if actual is null or actual is distinct from p_versions then raise exception '일일 기록이 변경되었습니다. 최신 내용을 확인한 뒤 다시 처리해 주세요';end if;
 for r in select * from public.sales_reports where id::text in(select jsonb_object_keys(actual)) order by day,id loop
  perform public.sales_check_report(r.id,r.revision);
 end loop;
 return true;
end $function$
;
