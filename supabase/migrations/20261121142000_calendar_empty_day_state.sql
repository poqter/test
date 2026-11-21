create function public.sales_empty_day_update_state(p_day date,p_confirmed boolean)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare
  result jsonb;
  has_events boolean := false;
begin
  result := public.sales_empty_day_set(p_day,p_confirmed);
  if not p_confirmed then
    select exists (
      select 1 from public.sales_calendar_days(p_day,p_day) e
      where auth.uid() in (e.owner,e.companion)
        and not e.common and e.status not in ('취소','연기')
    ) into has_events;
  end if;
  return result || jsonb_build_object('has_events',has_events);
end $$;
revoke all on function public.sales_empty_day_update_state(date,boolean) from public,anon;
grant execute on function public.sales_empty_day_update_state(date,boolean) to authenticated;
