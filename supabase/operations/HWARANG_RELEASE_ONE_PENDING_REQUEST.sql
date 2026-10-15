-- HWARANG: 박병선님이 2026-10-15 승인한 보류 요청 1건만 복구합니다.
-- Supabase SQL Editor에서 전체 실행. 소스 재배포나 새 권한 부여는 없습니다.
-- 공급자 처리/비용은 unknown으로 보존합니다. API 재호출은 하지 않습니다.
-- 다음 답변을 보내면 별도 API 비용이 발생할 수 있습니다.
-- 동일 스크립트 재실행은 감사 기록 확인 후 아무것도 변경하지 않습니다.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '30s';
do $recovery$
declare
  target_op constant text := 'f7a631ef4ed5e3bf4430b94dd74c8972d7eda5776eb260dd4bb44983f8857b36';
  target_user constant uuid := '92336306-16fb-4582-a690-bc932cf5ea74';
  target_session uuid;
  rec public.hwarang_studio_records;
  req public.hwarang_studio_requests;
  ledger public.hwarang_ai_request_registry;
  recovery_note constant text := '2026-10-15 사용자 승인: 공급자 처리 여부는 미확인으로 보존하고 오래된 고객 응답 보류만 해제. 외부 API 미호출. 재전송 시 추가 비용 가능.';
begin
  if not exists(select 1 from public.profiles where id=target_user and role='super_admin' and is_active) then
    raise exception 'STOP: expected active super_admin owner not found';
  end if;
  perform pg_advisory_xact_lock(hashtextextended(target_user::text,0));
  select session_id into target_session from public.hwarang_studio_requests
    where op_key=target_op and user_id=target_user;
  if not found then raise exception 'STOP: exact request not found; no change'; end if;
  -- Same lock order as normal Studio save/claim.
  select * into rec from public.hwarang_studio_records
    where id=target_session and user_id=target_user for update;
  if not found then raise exception 'STOP: request session not found'; end if;
  select * into req from public.hwarang_studio_requests
    where op_key=target_op and user_id=target_user for update;
  if exists(select 1 from public.hwarang_studio_audit
    where session_id=target_session and event='authorized_unknown_release'
      and detail->>'op_key'=target_op) then
    raise notice 'Already released by this script; no further changes';
    return;
  end if;
  if req.status<>'uncertain' or req.purpose<>'CUSTOMER'
      or req.updated_at>now()-interval '10 minutes' then
    raise exception 'STOP: request state/age changed; review before recovery';
  end if;
  if rec.locked_by is not null and rec.locked_by<>target_op then
    raise exception 'STOP: session has a different lock';
  end if;
  if req.request_id is null then
    raise exception 'STOP: credit request reference missing; manual ledger review needed';
  end if;
  select * into ledger from public.hwarang_ai_request_registry
    where request_id=req.request_id for update;
  if not found or ledger.user_id<>target_user
      or ledger.academy_session_id is distinct from target_session then
    raise exception 'STOP: credit ledger identity mismatch';
  end if;
  -- Release only an outstanding learner-credit reservation using the existing
  -- bucket-aware function. This does NOT assert that the provider charged zero.
  -- Already completed/expired/failed ledgers and prior consumed credits stay intact.
  if ledger.status in ('reserved','processing') then
    perform public.finalize_hwarang_ai_request(ledger.request_id,'failed',0);
  elsif ledger.status not in ('completed','expired','failed','blocked') then
    raise exception 'STOP: unexpected credit ledger state';
  end if;
  update public.hwarang_ai_request_registry
    set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
      'studio_recovery','authorized_unknown_release',
      'provider_processing_status','unknown','provider_cost_status','unknown',
      'recovery_note',recovery_note,'recovered_at',now())
    where request_id=ledger.request_id;
  update public.hwarang_studio_requests
    set status='failed',updated_at=now(),
      result=coalesce(result,'{}'::jsonb)||jsonb_build_object('recovery',jsonb_build_object(
        'kind','authorized_unknown_release','provider_processing_status','unknown',
        'provider_cost_status','unknown','note',recovery_note))
    where op_key=target_op;
  update public.hwarang_studio_records
    set locked_by=null,version=version+1,
      data=jsonb_set(data,'{version}',to_jsonb(version+1)),updated_at=now()
    where id=target_session;
  perform public.release_hwarang_ai_session(target_user,target_session);
  insert into public.hwarang_studio_audit(actor,session_id,event,detail)
    values(target_user,target_session,'authorized_unknown_release',jsonb_build_object(
      'op_key',target_op,'request_id',req.request_id,
      'previous_studio_status',req.status,'previous_ledger_status',ledger.status,
      'previous_record_version',rec.version,'provider_processing_status','unknown',
      'provider_cost_status','unknown','provider_recalled',false,'note',recovery_note));
end
$recovery$;
commit;

-- Expected: studio_status failed; target_lock_released true;
-- provider_cost_status unknown; remaining_pending_for_owner 0 (unless another request exists).
select r.status as studio_status,
       (s.locked_by is distinct from r.op_key) as target_lock_released,
       q.status as learner_credit_status,
       q.metadata->>'provider_cost_status' as provider_cost_status,
       (select count(*) from public.hwarang_studio_requests p
         where p.user_id=r.user_id and p.status in ('claimed','processing','uncertain'))
         as remaining_pending_for_owner
from public.hwarang_studio_requests r
join public.hwarang_studio_records s on s.id=r.session_id
join public.hwarang_ai_request_registry q on q.request_id=r.request_id
where r.op_key='f7a631ef4ed5e3bf4430b94dd74c8972d7eda5776eb260dd4bb44983f8857b36';
