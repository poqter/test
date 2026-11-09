-- Preserve existing callers while allowing a separate follow-up time.
create or replace function public.sales_edit_event(p_id uuid,p_revision integer,p_data jsonb,p_follow date,p_follow_id uuid)
returns boolean language plpgsql security invoker set search_path='' as $$
declare updated public.sales_events;
begin
 update public.sales_events set
 companion=case when p_data ? 'companion' then (p_data->>'companion')::uuid else companion end,
 time_pending=case when p_data ? 'time_pending' then (p_data->>'time_pending')::boolean else time_pending end,
 day=(p_data->>'day')::date,start_time=(p_data->>'start_time')::time,end_time=(p_data->>'end_time')::time,
 title=p_data->>'title',kind=p_data->>'kind',place=p_data->>'place',note=p_data->>'note',
 help=p_data->>'help',common=(p_data->>'common')::boolean,status=p_data->>'status',result=p_data->>'result'
 where id=p_id and revision=p_revision and deleted_at is null returning * into updated;
 if not found then return false; end if;
 if p_follow is not null then
   if p_follow_id is null or p_follow<updated.day then
     raise exception '후속 일정 날짜를 확인해 주세요';
   end if;
   if p_data ? 'follow_start_time' and p_data->>'follow_end_time' is not null and
      (p_data->>'follow_start_time' is null or (p_data->>'follow_end_time')::time <= (p_data->>'follow_start_time')::time) then
     raise exception '종료 시간은 시작 시간보다 늦어야 합니다';
   end if;
   insert into public.sales_events(id,owner,unit,day,start_time,end_time,kind,title,place,note,common,companion,time_pending,previous_event,contact_method)
   values(p_follow_id,updated.owner,updated.unit,p_follow,case when p_data ? 'follow_start_time' then (p_data->>'follow_start_time')::time else updated.start_time end,
          case when p_data ? 'follow_end_time' then (p_data->>'follow_end_time')::time else updated.end_time end,updated.kind,
          updated.title,updated.place,updated.note,updated.common,updated.companion,case when p_data ? 'follow_time_pending' then (p_data->>'follow_time_pending')::boolean else updated.time_pending end,updated.id,updated.contact_method);
 end if;
 return true;
end $$;
