-- UI exposes readiness only, never budgets or secrets. No activation.
begin;
create or replace function private.kakao_my_status() returns jsonb language plpgsql volatile security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user(); result jsonb;
begin
 -- Authenticated owner's abandoned confirmation expires even when delivery gate is OFF.
 update public.kakao_multi_connections set status='revoked',generation=generation+1,encrypted_tokens=null,account_id=null,
 confirmation_hash=null,confirmation_expires_at=null,talk_message_granted=false,updated_at=clock_timestamp()
 where owner_id=u and status='pending_confirmation' and confirmation_expires_at<=clock_timestamp();
 if found then update public.kakao_multi_preferences set enabled=false,updated_at=clock_timestamp() where owner_id=u; end if;
 update public.kakao_multi_oauth set ticket_hash=null,state_hash=null,browser_hash=null,
 status=case when status='consumed' then 'consumed' else 'cancelled' end
 where owner_id=u and expires_at<=clock_timestamp() and (ticket_hash is not null or state_hash is not null or browser_hash is not null);
 select jsonb_build_object('dispatch_ready',coalesce((private.kakao_service_gate()->>'enabled')::boolean,false),'connection_status',coalesce(c.status,'disconnected'),
 'enabled',coalesce(p.enabled,false),'time',coalesce(left(p.delivery_time::text,5),'08:00'),
 'weather_region_key',p.weather_region_key,'days',coalesce(to_jsonb(p.days),'[0,1,2,3,4,5,6]'::jsonb),'send_empty',coalesce(p.send_empty,true),
 'admin_paused',coalesce(p.admin_paused,false),'last_outcome',j.outcome,'last_attempt_at',j.claimed_at,'last_day',j.day,'today_outcome',case when j.day=(clock_timestamp() at time zone 'Asia/Seoul')::date then j.outcome end,'accepted_parts',coalesce(j.accepted_parts,0),'total_parts',coalesce(j.total_parts,0),
 'can_manage',exists(select 1 from private.sales_scope_for(u,false) s where s.managed and s.member<>u),
 'legacy_personal',private.kakao_service_excluded_owner(u))
 into result from (select u id) me
 left join public.kakao_multi_connections c on c.owner_id=me.id
 left join public.kakao_multi_preferences p on p.owner_id=me.id
 left join lateral(select b.day,coalesce(b.outcome,x.outcome) outcome,x.claimed_at,
 (select count(*) from public.kakao_multi_jobs z where z.batch_id=b.id and z.status='accepted') accepted_parts,
 (select count(*) from public.kakao_multi_jobs z where z.batch_id=b.id) total_parts from public.kakao_multi_batches b
 left join lateral(select outcome,claimed_at from public.kakao_multi_jobs where batch_id=b.id order by claimed_at desc nulls last,part desc limit 1) x on true
 where b.owner_id=u order by b.day desc,b.created_at desc limit 1) j on true;
 return result;
end $$;
commit;
