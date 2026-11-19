-- Corrective change: independent leave headcount and explicit aggregate exclusions.
-- Membership exclusions do not disable accounts or their personal briefing preferences.
create table private.kakao_briefing_member_exclusions(
 member_id uuid primary key,
 reason text not null,
 created_at timestamptz not null default now()
);
alter table private.kakao_briefing_member_exclusions enable row level security;
revoke all on private.kakao_briefing_member_exclusions from public,anon,authenticated,service_role;

CREATE OR REPLACE FUNCTION private.kakao_service_snapshot(p_owner uuid, p_day date)
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
 select jsonb_build_object(
 'identity',jsonb_build_object('owner_id',me.id,'unit',me.organization_unit_id,'position',me.position_code,'role',me.role),
 'preferences',(select jsonb_build_object('time',p.delivery_time,'days',p.days,'send_empty',p.send_empty,'enabled',p.enabled,'weather_region_key',p.weather_region_key,'weather_catalog',(select jsonb_build_object('nx',r.nx,'ny',r.ny,'forecast_code',r.forecast_code,'enabled',r.enabled,'verified_at',r.verified_at) from public.kakao_weather_regions r where r.region_key=p.weather_region_key)) from public.kakao_multi_preferences p where p.owner_id=me.id),
 'branch',case when me.position_code='branch_manager' then
 (select jsonb_build_object('name',u.name,'members',coalesce((select jsonb_agg(jsonb_build_object(
 'id',m.id,'name',m.display_name,'count',s.work_count,'on_leave',s.leave_count>0,
 'state',case when s.work_count>0 then 'scheduled' when s.leave_count>0 then 'leave'
 when exists(select 1 from public.sales_empty_days d where d.owner=m.id and d.day=p_day) then 'empty'
 when m.position_code in ('branch_manager','division_head','chief_representative') then 'excluded' else 'missing' end)
 order by m.display_name,m.id)
 from public.profiles m cross join lateral (
 select count(*) filter(where e.kind<>'휴무') work_count,
 count(*) filter(where e.kind='휴무') leave_count
 from public.sales_events e join public.profiles author on author.id=e.owner
 where e.unit=me.organization_unit_id and author.organization_unit_id=me.organization_unit_id and author.is_active
 and (e.owner=m.id or e.companion=m.id) and not e.common
 and e.day=p_day and e.deleted_at is null and e.status not in ('취소','연기')
 ) s where m.organization_unit_id=me.organization_unit_id and m.is_active and m.id<>me.id
 and not exists(select 1 from private.kakao_briefing_member_exclusions x where x.member_id=m.id)
 and m.position_code is distinct from 'branch_manager'),'[]'::jsonb))
 from public.organization_units u where u.id=me.organization_unit_id and u.is_active) end,
 'empty_explicit',exists(select 1 from public.sales_empty_days x where x.owner=me.id and x.day=p_day),
 'events',coalesce((select jsonb_agg(jsonb_build_object(
 'id',e.id,'day',e.day,'start_time',e.start_time,'time_pending',e.time_pending,'title',e.title,'kind',e.kind,'status',e.status,
 'own',e.owner=me.id,'companion',e.companion=me.id,'common',e.common,
 'end_time',case when e.owner=me.id then e.end_time end,'place',case when e.owner=me.id then e.place end)
 order by e.start_time nulls last,e.id)
 from public.sales_events e join public.profiles author on author.id=e.owner
 where e.unit=me.organization_unit_id and author.organization_unit_id=me.organization_unit_id and author.is_active
 and e.day=p_day and e.deleted_at is null and (e.owner=me.id or e.companion=me.id or e.common)),'[]'::jsonb))
 from public.profiles me where me.id=p_owner and private.kakao_service_owner_active(p_owner)
$function$
;
