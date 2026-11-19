-- Connected-member briefings. Actual roles only; no UI scope or super-admin expansion.
alter table public.kakao_multi_preferences add column member_briefing_enabled boolean not null default true;

create function private.kakao_member_summary(p_owner uuid,p_day date)
returns jsonb language sql stable security definer set search_path='' as $$
 select (select jsonb_build_object('name',case when me.position_code='branch_manager' then u.name else me.display_name||' '||case when me.position_code='team_leader' then '팀' else '담당 구성원' end end,'members',coalesce((select jsonb_agg(jsonb_build_object(
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
 and m.position_code is distinct from 'branch_manager'
 and (me.position_code='branch_manager'
 or (me.position_code='team_leader' and m.position_code='fp' and exists(
 select 1 from public.sales_team_assignments a where a.leader=me.id and a.member=m.id))
 or (me.position_code='deputy_branch_manager' and (
 (m.position_code in ('team_leader','fp') and exists(select 1 from public.sales_deputy_assignments a where a.leader=me.id and a.member=m.id))
 or (m.position_code='fp' and exists(select 1 from public.sales_deputy_assignments d
 join public.profiles leader on leader.id=d.member and leader.is_active and leader.position_code='team_leader' and leader.organization_unit_id=me.organization_unit_id
 join public.sales_team_assignments t on t.leader=leader.id and t.member=m.id
 where d.leader=me.id and not exists(select 1 from private.kakao_briefing_member_exclusions x where x.member_id=leader.id)))
 )))),'[]'::jsonb))
 from public.organization_units u where u.id=me.organization_unit_id and u.is_active)
 from public.profiles me where me.id=p_owner and private.kakao_service_owner_active(p_owner)
 and me.position_code in ('branch_manager','team_leader','deputy_branch_manager')
 and not exists(select 1 from private.kakao_briefing_member_exclusions x where x.member_id=me.id)
$$;
revoke all on function private.kakao_member_summary(uuid,date) from public,anon,authenticated,service_role;

CREATE OR REPLACE FUNCTION private.kakao_service_snapshot(p_owner uuid, p_day date)
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
 select jsonb_build_object(
 'identity',jsonb_build_object('owner_id',me.id,'unit',me.organization_unit_id,'position',me.position_code,'role',me.role),
 'preferences',(select jsonb_build_object('time',p.delivery_time,'days',p.days,'send_empty',p.send_empty,'enabled',p.enabled,'weather_region_key',p.weather_region_key,'weather_catalog',(select jsonb_build_object('nx',r.nx,'ny',r.ny,'forecast_code',r.forecast_code,'enabled',r.enabled,'verified_at',r.verified_at) from public.kakao_weather_regions r where r.region_key=p.weather_region_key)) from public.kakao_multi_preferences p where p.owner_id=me.id),
 'branch',case when coalesce((select member_briefing_enabled from public.kakao_multi_preferences where owner_id=me.id),true)
 and jsonb_array_length(private.kakao_member_summary(me.id,p_day)->'members')>0 then private.kakao_member_summary(me.id,p_day) end,
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

CREATE OR REPLACE FUNCTION private.kakao_service_reserve_branch(p_owner uuid, p_day date, p_generation bigint, p_parts text[], p_scope_hash text, p_branch_parts integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare result jsonb;
begin
 if p_branch_parts is null or p_branch_parts<1 or p_branch_parts>=coalesce(cardinality(p_parts),0)
 or not exists(select 1 from public.profiles where id=p_owner and position_code in ('branch_manager','team_leader','deputy_branch_manager'))
 then return jsonb_build_object('status','invalid_parts'); end if;
 result:=private.kakao_service_reserve(p_owner,p_day,p_generation,p_parts,p_scope_hash);
 if result->>'status'='reserved' then
  update public.kakao_multi_batches set branch_parts=p_branch_parts where id=(result->>'batch_id')::uuid;
 end if;
 return result;
end $function$
;

CREATE OR REPLACE FUNCTION private.kakao_welcome_reserve_branch(p_id uuid, p_claim_token uuid, p_parts text[], p_branch_parts integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare result jsonb;
begin
 if p_branch_parts is null or p_branch_parts<1 or p_branch_parts>=coalesce(cardinality(p_parts),0)
 or not exists(select 1 from public.kakao_multi_welcomes w join public.profiles p on p.id=w.owner_id where w.id=p_id and p.position_code in ('branch_manager','team_leader','deputy_branch_manager')) then return jsonb_build_object('reserved',false);end if;
 result:=private.kakao_welcome_reserve(p_id,p_claim_token,p_parts);
 if result->>'reserved'='true' then
 update public.kakao_multi_batches b set branch_parts=p_branch_parts from public.kakao_multi_welcomes w where w.id=p_id and b.id=w.batch_id;
 end if;
 return result;
end $function$
;

create function private.kakao_member_briefing_status()
returns jsonb language plpgsql stable security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user(); d date:=(now() at time zone 'Asia/Seoul')::date; s jsonb;
begin
 s:=private.kakao_member_summary(u,d);
 return jsonb_build_object('eligible',s is not null,'enabled',coalesce((select member_briefing_enabled from public.kakao_multi_preferences where owner_id=u),true),'day',d,'branch',s);
end $$;
create function public.kakao_member_briefing_status()
returns jsonb language sql set search_path='' as $$select private.kakao_member_briefing_status()$$;
create function private.kakao_save_member_briefing(p_enabled boolean)
returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user();
begin
 if p_enabled is null or private.kakao_member_summary(u,(now() at time zone 'Asia/Seoul')::date) is null then raise exception 'Unavailable';end if;
 update public.kakao_multi_preferences set member_briefing_enabled=p_enabled,updated_at=now() where owner_id=u;
 if not found then raise exception 'Save personal preferences first';end if;
 return private.kakao_member_briefing_status();
end $$;
create function public.kakao_save_member_briefing(p_enabled boolean)
returns jsonb language sql set search_path='' as $$select private.kakao_save_member_briefing(p_enabled)$$;
revoke all on function private.kakao_member_briefing_status(),public.kakao_member_briefing_status(),private.kakao_save_member_briefing(boolean),public.kakao_save_member_briefing(boolean) from public,anon,service_role;
grant execute on function private.kakao_member_briefing_status(),public.kakao_member_briefing_status(),private.kakao_save_member_briefing(boolean),public.kakao_save_member_briefing(boolean) to authenticated;
