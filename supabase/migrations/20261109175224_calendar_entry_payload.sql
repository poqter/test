-- Batch initial calendar reads under the same caller permissions.
create or replace function public.sales_calendar_context() returns jsonb
language sql stable security invoker set search_path='' as $$
 select jsonb_build_object(
 'members',coalesce((select jsonb_agg(to_jsonb(s)) from private.sales_scope() s),'[]'::jsonb),
 'branch',coalesce((select jsonb_agg(to_jsonb(b)) from private.sales_branch_members() b),'[]'::jsonb),
 'entry',case when coalesce(nullif(current_setting('request.headers',true),'')::jsonb->>'x-hwarang-calendar-entry','')='1' then
 jsonb_build_object(
 'day',(now() at time zone 'Asia/Seoul')::date,
 'summary',coalesce((select jsonb_agg(to_jsonb(s)) from private.sales_calendar_days((now() at time zone 'Asia/Seoul')::date,(now() at time zone 'Asia/Seoul')::date) s),'[]'::jsonb),
 'empty_days',coalesce((select jsonb_agg(jsonb_build_object('owner',owner)) from public.sales_empty_days where day=(now() at time zone 'Asia/Seoul')::date),'[]'::jsonb),
 'notices',coalesce((select jsonb_agg(to_jsonb(n)) from (
 select n.id,n.message,case when e.id is not null then jsonb_build_object('day',e.day,'kind',e.kind) end as sales_events
 from public.sales_notices n left join public.sales_events e on e.id=n.event
 where not n.seen order by n.created_at desc limit 50) n),'[]'::jsonb))
 else null end)
$$;
