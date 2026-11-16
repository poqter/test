-- Apply selected and subsequent planned events atomically through the existing editor.
create function public.sales_edit_recurring_event(
 p_id uuid,p_revision integer,p_data jsonb,p_follow date,p_follow_id uuid,p_future jsonb
) returns integer language plpgsql security invoker set search_path='' as $$
declare anchor public.sales_events; occurrence public.sales_events; expected jsonb; changed integer:=1;
begin
 if auth.uid() is null or jsonb_typeof(p_future) is distinct from 'object' or p_data->>'kind'='휴무' then
   raise exception '반복 일정 수정 범위를 확인해 주세요.';
 end if;
 perform pg_advisory_xact_lock(hashtextextended('sales.series.edit.'||auth.uid()::text,0));
 select * into anchor from public.sales_events
 where id=p_id and owner=auth.uid() and deleted_at is null for update;
 if not found or anchor.series_id is null or anchor.kind='휴무' or anchor.revision<>p_revision then
   raise exception '반복 일정이 변경되었습니다. 최신 일정을 확인해 주세요.';
 end if;
 for occurrence in
   select * from public.sales_events where owner=auth.uid() and series_id=anchor.series_id
   and id<>p_id and day>=anchor.day and deleted_at is null and status='예정' order by id for update
 loop
   expected:=p_future->occurrence.id::text;
   if expected is null or (expected->>'revision')::integer is distinct from occurrence.revision then
     raise exception '반복 일정이 변경되었습니다. 최신 일정을 확인해 주세요.';
   end if;
   if not public.sales_edit_event(occurrence.id,occurrence.revision,
      to_jsonb(occurrence)||coalesce((
        select jsonb_object_agg(key,value) from jsonb_each(expected->'data')
        where key in ('day','title','kind','start_time','end_time','time_pending','place','note','companion','common')
      ),'{}'::jsonb),
      null,null) then
     raise exception '이후 반복 일정을 저장하지 못했습니다.';
   end if;
   changed:=changed+1;
 end loop;
 if changed-1<>(select count(*) from jsonb_object_keys(p_future)) or
    not public.sales_edit_event(p_id,p_revision,p_data,p_follow,p_follow_id) then
   raise exception '반복 일정이 변경되었습니다. 최신 일정을 확인해 주세요.';
 end if;
 return changed;
end $$;
revoke all on function public.sales_edit_recurring_event(uuid,integer,jsonb,date,uuid,jsonb) from public,anon;
grant execute on function public.sales_edit_recurring_event(uuid,integer,jsonb,date,uuid,jsonb) to authenticated;
