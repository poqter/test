-- Additive transport projection. Existing endpoints and caller RLS are unchanged.
-- The original payload repeats readable events in both rows and summary.
create function public.sales_calendar_compact(first_day date,last_day date,p_member uuid default null,p_team boolean default false,p_known jsonb default null)
returns jsonb language plpgsql stable security invoker set search_path='' as $$
declare result jsonb; cards jsonb;
begin
 result:=public.sales_calendar_changes(first_day,last_day,p_member,p_team,p_known);
 if coalesce((result->>'unchanged')::boolean,false) then return result;end if;
 with details as materialized(select value from jsonb_array_elements(result->'rows')),
 visible as (
  select d.value,true readable from details d where p_member is not null
  union all
  select coalesce(d.value,s.value),d.value is not null
  from jsonb_array_elements(result->'summary') s
  left join details d on d.value->>'id'=s.value->>'id' where p_member is null
 ), projected as (
  select (select jsonb_object_agg(key,value) from jsonb_each(v.value)
   where key=any(array['id','owner','day','start_time','kind','status','companion','common','time_pending','title','revision','place','help']))
   ||jsonb_build_object('readable',v.readable) card from visible v
 ) select coalesce(jsonb_agg(card),'[]'::jsonb) into cards from projected;
 return (result-'rows'-'summary')||jsonb_build_object('compact',true,'rows',cards);
end $$;
revoke all on function public.sales_calendar_compact(date,date,uuid,boolean,jsonb) from public,anon;
grant execute on function public.sales_calendar_compact(date,date,uuid,boolean,jsonb) to authenticated;
