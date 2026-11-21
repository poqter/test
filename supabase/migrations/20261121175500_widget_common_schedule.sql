CREATE OR REPLACE FUNCTION public.sales_widget_month(first_day date, last_day date, p_team boolean DEFAULT false)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE
 SET search_path TO ''
AS $function$
declare result jsonb; empty_days jsonb;
begin
 if first_day is null or last_day is null or last_day<first_day or last_day-first_day>62 then raise exception '날짜 범위를 확인해 주세요.';end if;
 result:=public.sales_calendar_compact(first_day,last_day,null,p_team,null);
 select coalesce(jsonb_agg(day),'[]'::jsonb) into empty_days from public.sales_empty_days
 where owner=auth.uid() and day between first_day and last_day;
 return result||jsonb_build_object('empty_days',empty_days,'can_common',coalesce((select managed from private.sales_scope() where member=auth.uid()),false));
end $function$;
CREATE OR REPLACE FUNCTION public.sales_widget_save(p_id uuid, p_revision integer, p_data jsonb, p_overlap boolean DEFAULT false)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
declare old public.sales_events; saved public.sales_events; own_unit uuid; d date; s time; e time; k text; t text; pending boolean;
begin
 if not coalesce(private.sales_enabled(),false) then raise exception '일정 등록 권한이 없습니다.' using errcode='42501';end if;
 d:=(p_data->>'day')::date;s:=nullif(p_data->>'start_time','')::time;e:=nullif(p_data->>'end_time','')::time;
 k:=p_data->>'kind';t:=btrim(p_data->>'title');pending:=coalesce((p_data->>'time_pending')::boolean,true);
 if p_id is null or d is null or d not between date '1900-01-01' and date '2100-12-31' or t is null or length(t) not between 1 and 200 or k is null or k<>all(array['미분류','TA','AP','PC','CS','청약','교육','회의','휴무','기타']) then raise exception '날짜·일정명·활동 종류를 확인해 주세요.';end if;
 if k='휴무' then s:=null;e:=null;pending:=false;t:='휴무';end if;
 if e is not null and (s is null or e<=s) or pending and s is not null then raise exception '시작·종료 시간을 확인해 주세요.';end if;
 select * into old from public.sales_events where id=p_id and owner=auth.uid() for update;
 if found then
  if old.deleted_at is not null then raise exception '삭제된 일정입니다.' using errcode='42501';end if;
  if p_revision is null or old.revision<>p_revision then raise exception '일정이 변경되었습니다. 목록에서 다시 열어 주세요.' using errcode='40001';end if;
 elsif p_revision is not null then raise exception '일정이 삭제되었거나 조회 권한이 없습니다.' using errcode='42501';
 end if;
 if p_data ? 'common' and coalesce((p_data->>'common')::boolean,false) is distinct from coalesce(old.common,false) and not exists(select 1 from private.sales_scope() where member=auth.uid() and managed) then raise exception '지점 공통 일정 등록 권한이 없습니다.' using errcode='42501';end if;
 if s is not null and coalesce(old.status,'예정')='예정' and not p_overlap and exists(
  select 1 from public.sales_events x where x.owner=auth.uid() and x.day=d and x.status='예정' and x.deleted_at is null and x.id<>p_id and x.start_time is not null
  and (s=x.start_time or s<coalesce(x.end_time,x.start_time) and x.start_time<coalesce(e,s))
 ) then return jsonb_build_object('overlap',true);end if;
 if s is not null and old.companion is not null and old.status='예정' and not p_overlap and exists(
  select 1 from public.sales_companion_busy_times(d,d,old.companion) x where x.id<>p_id
  and (s=x.start_time or s<coalesce(x.end_time,x.start_time) and x.start_time<coalesce(e,s))
 ) then return jsonb_build_object('overlap',true);end if;
 if old.id is not null then
  update public.sales_events set common=coalesce((p_data->>'common')::boolean,old.common),day=d,title=t,kind=k,start_time=s,end_time=e,time_pending=pending,
   place=coalesce(p_data->>'place',''),note=coalesce(p_data->>'note','') where id=p_id and revision=p_revision returning * into saved;
 else
  select unit into own_unit from private.sales_scope() where member=auth.uid();
  insert into public.sales_events(id,unit,common,day,title,kind,start_time,end_time,time_pending,place,note)
   values(p_id,own_unit,coalesce((p_data->>'common')::boolean,false),d,t,k,s,e,pending,coalesce(p_data->>'place',''),coalesce(p_data->>'note','')) returning * into saved;
 end if;
 if saved.id is null then raise exception '저장 결과를 확인하지 못했습니다.';end if;
 return jsonb_build_object('id',saved.id,'revision',saved.revision,'day',saved.day);
end $function$;

