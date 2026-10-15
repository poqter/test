-- 26: Academy courses, downloadable resources and private learning progress.
-- Existing feature permissions are reused; no extra grants to users.
begin;
create table if not exists public.hwarang_learning_content (
 id text primary key, data jsonb not null, updated_at timestamptz not null default now()
);
create table if not exists public.hwarang_learning_progress (
 user_id uuid not null references public.profiles(id), content_id text not null references public.hwarang_learning_content(id),
 revision integer not null, completed_lessons text[] not null default '{}', updated_at timestamptz not null default now(),
 primary key(user_id,content_id)
);
alter table public.hwarang_learning_content enable row level security;
alter table public.hwarang_learning_progress enable row level security;
revoke all on public.hwarang_learning_content, public.hwarang_learning_progress from public,anon,authenticated;
grant all on public.hwarang_learning_content, public.hwarang_learning_progress to service_role;
create or replace function private.learning_check(p_actor uuid) returns void language plpgsql security invoker set search_path='' as $$
begin
 if not exists(select 1 from public.profiles where id=p_actor and is_active)
 or not exists(select 1 from public.hwarang_app_access where user_id=p_actor and app_code='academy' and is_enabled)
 then raise exception 'LEARNING_ACCESS_DENIED'; end if;
end $$;
create or replace function public.hwarang_learning_catalog(p_actor uuid) returns jsonb language plpgsql security invoker set search_path='' as $$
begin
 perform private.learning_check(p_actor);
 return coalesce((select jsonb_agg(c.data || jsonb_build_object('progress',case when p.revision=(c.data->>'revision')::integer then to_jsonb(p) else null end))
 from public.hwarang_learning_content c left join public.hwarang_learning_progress p on p.content_id=c.id and p.user_id=p_actor
 where (coalesce((c.data->>'published')::boolean,false) and exists(select 1 from public.get_hwarang_effective_permissions(p_actor) where permission_code=c.data->>'permission'))
 or exists(select 1 from public.profiles where id=p_actor and role='super_admin' and is_active)),'[]');
end $$;
create or replace function public.hwarang_learning_complete(p_actor uuid,p_id text,p_revision integer,p_lesson text)
returns void language plpgsql security invoker set search_path='' as $$
declare d jsonb;
begin
 perform private.learning_check(p_actor);
 select data into d from public.hwarang_learning_content where id=p_id for share;
 if d is null or not coalesce((d->>'published')::boolean,false) or not exists(select 1 from public.get_hwarang_effective_permissions(p_actor) where permission_code=d->>'permission') then raise exception 'LEARNING_ACCESS_DENIED'; end if;
 if (d->>'revision')::integer<>p_revision then raise exception 'CONTENT_CHANGED_RELOAD';end if;
 if not exists(select 1 from jsonb_array_elements(d->'lessons') x where x->>'id'=p_lesson) then raise exception 'INVALID_LESSON';end if;
 insert into public.hwarang_learning_progress(user_id,content_id,revision,completed_lessons) values(p_actor,p_id,p_revision,array[p_lesson])
 on conflict(user_id,content_id) do update set revision=p_revision,
 completed_lessons=case when hwarang_learning_progress.revision<>p_revision then array[p_lesson] else array(select distinct unnest(hwarang_learning_progress.completed_lessons||array[p_lesson])) end,updated_at=now();
end $$;
create or replace function public.hwarang_learning_publish(p_actor uuid,p_data jsonb)
returns void language plpgsql security invoker set search_path='' as $$
declare current_revision integer;
begin
 perform private.learning_check(p_actor);
 if not exists(select 1 from public.profiles where id=p_actor and role='super_admin' and is_active) then raise exception 'LEARNING_ACCESS_DENIED';end if;
 if coalesce(length(p_data->>'id'),0) not between 1 and 100 or coalesce(length(trim(p_data->>'title')),0) not between 1 and 150
 or jsonb_typeof(p_data->'published') is distinct from 'boolean'
 or coalesce(length(p_data->>'category'),0) not between 1 and 40
 or p_data->>'kind' is distinct from 'resource' or p_data->>'permission' is distinct from 'academy.library'
 or octet_length(p_data::text)>3000000 or jsonb_typeof(p_data->'lessons') is distinct from 'array'
 then raise exception 'INVALID_CONTENT';end if;
 perform pg_advisory_xact_lock(hashtextextended(p_data->>'id',1));
 select (data->>'revision')::integer into current_revision from public.hwarang_learning_content where id=p_data->>'id' for update;
 if found and (p_data->>'revision')::integer is distinct from current_revision then raise exception 'CONTENT_CHANGED_RELOAD';end if;
 insert into public.hwarang_learning_content(id,data) values(p_data->>'id',jsonb_set(p_data,'{revision}',to_jsonb(coalesce(current_revision,0)+1)))
 on conflict(id) do update set data=excluded.data,updated_at=now();
end $$;
revoke all on function private.learning_check(uuid),public.hwarang_learning_catalog(uuid),public.hwarang_learning_complete(uuid,text,integer,text),public.hwarang_learning_publish(uuid,jsonb) from public,anon,authenticated;
grant execute on function private.learning_check(uuid),public.hwarang_learning_catalog(uuid),public.hwarang_learning_complete(uuid,text,integer,text),public.hwarang_learning_publish(uuid,jsonb) to service_role;
insert into public.hwarang_learning_content(id,data) values('foundation-new_hire','{"id": "foundation-new_hire", "kind": "course", "category": "new_hire", "permission": "academy.new_hire", "title": "신입교육 · 상담의 기본", "summary": "3개 짧은 학습과 실천 체크 · 기초 과정", "body": "", "lessons": [{"id": "1", "title": "상담 준비", "body": "상담 전에는 목적, 예상 소요 시간, 준비 자료를 확인합니다. 고객에게 개인정보를 요구하기 전에 사용 목적을 설명하고 필요한 범위만 요청합니다.\n\n**실행 체크**\n- 오늘 확인할 주제 한 가지 정하기\n- 상담 시간과 진행 순서 안내하기\n- 확인되지 않은 내용은 추정이라고 밝히기"}, {"id": "2", "title": "질문하고 요약하기", "body": "처음에는 “이번 점검에서 가장 궁금한 점은 무엇인가요?”처럼 열린 질문을 사용합니다. 이후 보험료, 납입기간, 가족과의 의사결정 등 필요한 사실을 하나씩 확인합니다.\n\n**연습**\n“보험료가 부담되시는군요. 줄일 수 있는지 확인하면서, 유지하고 싶은 보장도 함께 살펴볼까요?”처럼 고객의 말과 다음 행동을 연결해 보세요."}, {"id": "3", "title": "다음 약속 마무리", "body": "다음 만남의 날짜·시각·장소·준비 자료를 서로 확인합니다. 고객이 동의한 행동만 약속으로 기록합니다. 상담 종료 인사 후 새 질문을 억지로 이어가지 않습니다.\n\n**실행 체크**\n- 일정을 구체적으로 확인하기\n- 증권 확인 방법과 자료 전달 동의 확인하기\n- 추가 질문이 있는지 묻고 마무리하기"}], "published": true, "revision": 1, "updated_on": "2026-10-15"}'::jsonb) on conflict(id) do nothing;
insert into public.hwarang_learning_content(id,data) values('foundation-consultation','{"id": "foundation-consultation", "kind": "course", "category": "consultation", "permission": "academy.consultation", "title": "상담교육 · 경청과 설명", "summary": "3개 짧은 학습과 실천 체크 · 기초 과정", "body": "", "lessons": [{"id": "1", "title": "고객의 기준 찾기", "body": "같은 보험료도 고객마다 부담 수준이 다릅니다. 금액만 듣고 많거나 적다고 단정하지 말고, 고객이 중요하게 생각하는 보장과 지출 기준을 확인합니다.\n\n**연습 질문**\n“현재 보험료에서 어떤 부분이 가장 부담되세요?”\n“가족과 상의할 때 먼저 확인하시는 기준이 있나요?”"}, {"id": "2", "title": "쉬운 말로 설명하기", "body": "보장 이름을 나열하는 대신 보장되는 상황, 지급 조건, 보장되지 않는 경우를 나누어 설명합니다. 실제 약관과 증권으로 확인되지 않은 내용은 결론을 유보합니다.\n\n**연습**\n설명을 마친 뒤 “제가 설명드린 내용 중 다시 확인하고 싶은 부분이 있으세요?”라고 물어보세요."}, {"id": "3", "title": "거절을 이해하기", "body": "거절에는 비용, 필요성, 신뢰, 시기 등 서로 다른 이유가 있을 수 있습니다. 반박보다 이유 확인이 먼저입니다. 원치 않는 고객에게 결정을 재촉하지 않습니다.\n\n**연습 질문**\n“지금 결정하시기 어려운 이유를 여쭤봐도 될까요?”\n“추가로 확인한 뒤 다시 이야기할지, 여기서 마칠지 편한 쪽을 말씀해 주세요.”"}], "published": true, "revision": 1, "updated_on": "2026-10-15"}'::jsonb) on conflict(id) do nothing;
insert into public.hwarang_learning_content(id,data) values('foundation-insurance_practice','{"id": "foundation-insurance_practice", "kind": "course", "category": "insurance_practice", "permission": "academy.insurance_practice", "title": "보험실무 · 자료 확인", "summary": "3개 짧은 학습과 실천 체크 · 기초 과정", "body": "", "lessons": [{"id": "1", "title": "증권 확인 순서", "body": "계약자·피보험자, 계약 상태, 보험기간, 납입기간, 보험료, 담보 및 가입금액을 구분해 정리합니다. 화면 캡처나 요약표만으로 확정하지 말고 원본과 대조합니다.\n\n**실행 체크**\n- 기준일과 자료 출처 기록\n- 누락된 계약 표시\n- 고객이 확인해야 할 항목 분리"}, {"id": "2", "title": "비교표 작성 원칙", "body": "보험료만 비교하지 말고 보장 범위, 면책·감액, 갱신 여부, 유지 조건을 함께 확인합니다. 기존 계약 해지와 신규 계약 가입은 각각의 불이익을 따로 확인해야 합니다.\n\n미확인 항목은 빈칸이나 “확인 필요”로 남기며 유리한 조건으로 임의 채우지 않습니다."}, {"id": "3", "title": "청구 안내 준비", "body": "청구 종류와 실제 진료 내역을 먼저 확인한 뒤 해당 보험사의 최신 안내를 대조합니다. 자료 제출만으로 지급이 확정된다고 설명하지 않습니다.\n\n**실행 체크**\n- 보험사와 청구 유형 확인\n- 필요한 서류와 발급처 확인\n- 민감 정보의 전달 방법 확인\n- 지급 여부는 심사 후 결정됨을 안내"}], "published": true, "revision": 1, "updated_on": "2026-10-15"}'::jsonb) on conflict(id) do nothing;
insert into public.hwarang_learning_content(id,data) values('foundation-assessment','{"id": "foundation-assessment", "kind": "course", "category": "assessment", "permission": "academy.assessment", "title": "학습 점검 · 기본 원칙", "summary": "3개 짧은 학습과 실천 체크 · 기초 과정", "body": "", "lessons": [{"id": "1", "title": "자가 점검 안내", "body": "이 과정은 상담 기본 원칙을 확인하는 학습용 점검입니다. 자격시험이나 공식 AI 역량 평가가 아닙니다. 오답은 해당 설명을 다시 읽고 재시도할 수 있습니다.\n\n공식 AI 평가는 시뮬레이터에서 별도 권한으로 진행합니다."}, {"id": "2", "title": "근거를 남기는 습관", "body": "결론마다 어떤 고객 발화나 자료를 근거로 판단했는지 남깁니다. 자료에 없는 조건은 사실처럼 설명하지 않습니다. 계산기 결과는 입력값과 적용 가정을 함께 전달합니다."}, {"id": "3", "title": "학습 점검", "body": "고객에게 실제로 확인한 내용과 추정한 내용을 구분하고, 설명의 근거를 다시 확인해 보세요. 아래 문제를 통과하면 학습 점검을 완료할 수 있습니다."}], "published": true, "revision": 1, "updated_on": "2026-10-15"}'::jsonb) on conflict(id) do nothing;
insert into public.hwarang_learning_content(id,data) values('guide-4','{"id": "guide-4", "kind": "resource", "category": "상품·보장", "permission": "academy.library", "title": "증권 확인 체크리스트", "summary": "다운로드해서 사용하는 실무 준비 노트", "body": "계약자·피보험자, 계약 상태, 보험기간, 납입기간, 보험료, 담보 및 가입금액을 구분해 정리합니다. 화면 캡처나 요약표만으로 확정하지 말고 원본과 대조합니다.\n\n**실행 체크**\n- 기준일과 자료 출처 기록\n- 누락된 계약 표시\n- 고객이 확인해야 할 항목 분리", "published": true, "revision": 1, "updated_on": "2026-10-15", "lessons": []}'::jsonb) on conflict(id) do nothing;
insert into public.hwarang_learning_content(id,data) values('guide-5','{"id": "guide-5", "kind": "resource", "category": "상담·설명", "permission": "academy.library", "title": "첫 상담 질문 노트", "summary": "다운로드해서 사용하는 실무 준비 노트", "body": "같은 보험료도 고객마다 부담 수준이 다릅니다. 금액만 듣고 많거나 적다고 단정하지 말고, 고객이 중요하게 생각하는 보장과 지출 기준을 확인합니다.\n\n**연습 질문**\n“현재 보험료에서 어떤 부분이 가장 부담되세요?”\n“가족과 상의할 때 먼저 확인하시는 기준이 있나요?”", "published": true, "revision": 1, "updated_on": "2026-10-15", "lessons": []}'::jsonb) on conflict(id) do nothing;
insert into public.hwarang_learning_content(id,data) values('guide-6','{"id": "guide-6", "kind": "resource", "category": "계약·청구", "permission": "academy.library", "title": "청구 안내 준비 체크리스트", "summary": "다운로드해서 사용하는 실무 준비 노트", "body": "청구 종류와 실제 진료 내역을 먼저 확인한 뒤 해당 보험사의 최신 안내를 대조합니다. 자료 제출만으로 지급이 확정된다고 설명하지 않습니다.\n\n**실행 체크**\n- 보험사와 청구 유형 확인\n- 필요한 서류와 발급처 확인\n- 민감 정보의 전달 방법 확인\n- 지급 여부는 심사 후 결정됨을 안내", "published": true, "revision": 1, "updated_on": "2026-10-15", "lessons": []}'::jsonb) on conflict(id) do nothing;
commit;
