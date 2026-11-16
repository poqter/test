-- Service-only atomic budget admission + claim. No sends or schedule mutations.
begin;
create function private.kakao_service_begin_job(p_job_id uuid) returns jsonb language plpgsql security definer set search_path='' as $$
declare run uuid:=gen_random_uuid();
begin
 -- tick_enter locks controls; claim retains that lock in the same transaction.
 if not private.kakao_service_tick_enter(run) then return jsonb_build_object('claimed',false,'reason','quota_held');end if;
 return private.kakao_service_claim(p_job_id,run);
end $$;
create function public.kakao_service_begin_job(p_job_id uuid) returns jsonb language sql security invoker set search_path='' as $$select private.kakao_service_begin_job(p_job_id)$$;
revoke all on function private.kakao_service_begin_job(uuid),public.kakao_service_begin_job(uuid) from public,anon,authenticated;
grant execute on function private.kakao_service_begin_job(uuid),public.kakao_service_begin_job(uuid) to service_role;
create or replace function private.kakao_service_pending(p_limit integer default 25) returns jsonb language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(jsonb_build_object('id',q.id,'owner_id',q.owner_id,'part',q.part,'atomic_claim',true) order by q.owner_turn,q.created_at,q.batch_id,q.part),'[]'::jsonb) from (
 select ranked.* from (
 select j.id,j.owner_id,b.created_at,j.batch_id,j.part,
 row_number() over(partition by j.owner_id order by b.created_at,j.batch_id,j.part) owner_turn
 from public.kakao_multi_jobs j join public.kakao_multi_batches b on b.id=j.batch_id
 where b.delivery_deadline is not null and clock_timestamp()<b.delivery_deadline
 and not exists(select 1 from public.kakao_multi_jobs busy where busy.owner_id=j.owner_id and busy.status='sending')
 and j.status='reserved' and b.status in('reserved','sending')
 and b.day between (clock_timestamp() at time zone 'Asia/Seoul')::date-1 and (clock_timestamp() at time zone 'Asia/Seoul')::date
 ) ranked order by owner_turn,created_at,batch_id,part limit greatest(1,least(coalesce(p_limit,25),100))) q
$$;
commit;
