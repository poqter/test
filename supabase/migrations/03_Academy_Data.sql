-- =========================================================
-- HWARANG ACADEMY
-- DATA CORE v1
--
-- User -> Case -> Session -> Assessment -> Learning Profile
-- 01 HWARANG PLATFORM CORE가 먼저 적용되어 있어야 합니다.
-- =========================================================

begin;

-- ---------------------------------------------------------
-- 1. CASE
-- 한 명의 가상 고객 전체
-- TA -> 1차 -> 보장분석 -> 2차 -> 계약/반론 -> 후속상담
-- ---------------------------------------------------------
create table public.academy_cases (
    id uuid primary key default gen_random_uuid(),

    owner_user_id uuid not null
        references public.profiles(id) on delete cascade,

    status text not null default 'active'
        check (status in ('active', 'completed', 'paused', 'archived')),

    current_stage text not null default 'TA',

    title text,
    customer_alias text,
    customer_seed bigint,

    -- 변하지 않는 고객 사실, 고객 인식, 성향, 경제, 니즈 등
    customer_state jsonb not null default '{}'::jsonb,

    -- FP가 상담 시작 전 실제로 볼 수 있는 정보
    public_state jsonb not null default '{}'::jsonb,

    -- 보험계약 원본. Excel은 필요할 때 이 데이터로 재생성
    insurance_state jsonb not null default '{}'::jsonb,

    -- 상담 간 연속성, 공개된 정보, 약속, 다음 행동 등
    journey_state jsonb not null default '{}'::jsonb,

    metadata jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz,
    archived_at timestamptz
);

create index academy_cases_owner_idx
    on public.academy_cases(owner_user_id, updated_at desc);

create index academy_cases_status_idx
    on public.academy_cases(owner_user_id, status, updated_at desc);

create trigger academy_cases_set_updated_at
before update on public.academy_cases
for each row execute function private.set_updated_at();


-- ---------------------------------------------------------
-- 2. SESSION
-- 한 Case 고객과 진행한 개별 상담 회차
-- ---------------------------------------------------------
create table public.academy_sessions (
    id uuid primary key default gen_random_uuid(),

    case_id uuid not null
        references public.academy_cases(id) on delete cascade,

    user_id uuid not null
        references public.profiles(id) on delete cascade,

    sequence_no integer not null default 1
        check (sequence_no > 0),

    stage text not null,
    scenario_id text,
    mode text,
    difficulty text,

    status text not null default 'in_progress'
        check (status in ('in_progress', 'completed', 'stopped', 'abandoned')),

    engine_version text,
    scenario_version text,

    seed bigint,
    customer_seed bigint,

    -- 이어하기 복원용 사용자 입력
    replay_inputs jsonb not null default '[]'::jsonb,

    -- 화면/보고서 복기용 대화 원문
    transcript jsonb not null default '[]'::jsonb,

    -- 진행 중 상태 스냅샷
    session_state jsonb not null default '{}'::jsonb,

    -- 종료 후 핵심 요약
    session_summary jsonb not null default '{}'::jsonb,

    last_turn_no integer not null default 0
        check (last_turn_no >= 0),

    resume_allowed boolean not null default true,
    end_reason text,

    started_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    ended_at timestamptz,

    metadata jsonb not null default '{}'::jsonb,

    unique(case_id, sequence_no)
);

create index academy_sessions_user_idx
    on public.academy_sessions(user_id, updated_at desc);

create index academy_sessions_case_idx
    on public.academy_sessions(case_id, sequence_no);

create index academy_sessions_resume_idx
    on public.academy_sessions(user_id, status, resume_allowed, updated_at desc);

create trigger academy_sessions_set_updated_at
before update on public.academy_sessions
for each row execute function private.set_updated_at();


-- ---------------------------------------------------------
-- 3. ASSESSMENT
-- 상담 종료 당시 평가보고서 Snapshot
-- 과거 보고서는 덮어쓰지 않음
-- ---------------------------------------------------------
create table public.academy_assessments (
    id uuid primary key default gen_random_uuid(),

    user_id uuid not null
        references public.profiles(id) on delete cascade,

    case_id uuid not null
        references public.academy_cases(id) on delete cascade,

    session_id uuid not null
        references public.academy_sessions(id) on delete cascade,

    assessment_type text not null default 'original'
        check (assessment_type in ('original', 'reanalysis')),

    evaluator_type text not null default 'rules'
        check (evaluator_type in ('rules', 'ai', 'hybrid')),

    framework_version text not null,

    supersedes_assessment_id uuid
        references public.academy_assessments(id) on delete set null,

    overall_score numeric(6,2),
    score_lower numeric(6,2),
    score_upper numeric(6,2),
    grade text,
    status text,

    competency_scores jsonb not null default '{}'::jsonb,

    strengths jsonb not null default '[]'::jsonb,
    development_areas jsonb not null default '[]'::jsonb,
    evidence jsonb not null default '[]'::jsonb,
    missed_opportunities jsonb not null default '[]'::jsonb,
    coaching_plan jsonb not null default '{}'::jsonb,
    next_training jsonb not null default '{}'::jsonb,

    -- 상업형 보고서 전체 스냅샷
    report_snapshot jsonb not null default '{}'::jsonb,

    source_snapshot_hash text,

    generated_at timestamptz not null default now(),

    metadata jsonb not null default '{}'::jsonb
);

create index academy_assessments_user_idx
    on public.academy_assessments(user_id, generated_at desc);

create index academy_assessments_session_idx
    on public.academy_assessments(session_id, generated_at desc);

create index academy_assessments_case_idx
    on public.academy_assessments(case_id, generated_at desc);


-- ---------------------------------------------------------
-- 4. LEARNING PROFILE
-- Assessment 이력에서 재계산 가능한 장기 성장 요약
-- ---------------------------------------------------------
create table public.academy_learning_profiles (
    user_id uuid primary key
        references public.profiles(id) on delete cascade,

    total_sessions integer not null default 0
        check (total_sessions >= 0),

    total_assessments integer not null default 0
        check (total_assessments >= 0),

    competency_summary jsonb not null default '{}'::jsonb,
    trend_summary jsonb not null default '{}'::jsonb,
    strengths_summary jsonb not null default '[]'::jsonb,
    development_summary jsonb not null default '[]'::jsonb,
    recommendation_summary jsonb not null default '{}'::jsonb,

    framework_version text,
    last_rebuilt_at timestamptz,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create trigger academy_learning_profiles_set_updated_at
before update on public.academy_learning_profiles
for each row execute function private.set_updated_at();


-- 기존 사용자 Learning Profile 생성
insert into public.academy_learning_profiles(user_id)
select id from public.profiles
on conflict (user_id) do nothing;


create or replace function private.ensure_academy_learning_profile()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    insert into public.academy_learning_profiles(user_id)
    values (new.id)
    on conflict (user_id) do nothing;

    return new;
end;
$$;

revoke all on function private.ensure_academy_learning_profile() from public;


create trigger on_profile_created_learning_profile
after insert on public.profiles
for each row execute function private.ensure_academy_learning_profile();


-- ---------------------------------------------------------
-- 5. Assessment 연결 무결성 검사
-- ---------------------------------------------------------
create or replace function private.validate_academy_assessment_links()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
    v_session_user uuid;
    v_session_case uuid;
begin
    select user_id, case_id
    into v_session_user, v_session_case
    from public.academy_sessions
    where id = new.session_id;

    if not found then
        raise exception 'ACADEMY_SESSION_NOT_FOUND';
    end if;

    if v_session_user <> new.user_id
       or v_session_case <> new.case_id then
        raise exception 'ACADEMY_ASSESSMENT_LINK_MISMATCH';
    end if;

    return new;
end;
$$;

revoke all on function private.validate_academy_assessment_links() from public;


create trigger academy_assessments_validate_links
before insert on public.academy_assessments
for each row execute function private.validate_academy_assessment_links();


-- ---------------------------------------------------------
-- 6. RLS
-- ---------------------------------------------------------
alter table public.academy_cases enable row level security;
alter table public.academy_sessions enable row level security;
alter table public.academy_assessments enable row level security;
alter table public.academy_learning_profiles enable row level security;


-- ---------------------------------------------------------
-- 7. Grants
-- ---------------------------------------------------------
revoke all on table public.academy_cases from anon, authenticated;
revoke all on table public.academy_sessions from anon, authenticated;
revoke all on table public.academy_assessments from anon, authenticated;
revoke all on table public.academy_learning_profiles from anon, authenticated;

grant select, insert, update
on public.academy_cases
to authenticated;

grant select, insert, update
on public.academy_sessions
to authenticated;

-- 평가 원본은 생성 후 일반 사용자가 수정/삭제하지 않음
grant select, insert
on public.academy_assessments
to authenticated;

grant select, insert, update
on public.academy_learning_profiles
to authenticated;

grant select, insert, update, delete
on public.academy_cases
to service_role;

grant select, insert, update, delete
on public.academy_sessions
to service_role;

grant select, insert, update, delete
on public.academy_assessments
to service_role;

grant select, insert, update, delete
on public.academy_learning_profiles
to service_role;


-- ---------------------------------------------------------
-- 8. RLS Policies
-- ---------------------------------------------------------

-- CASE
create policy academy_cases_select_scope
on public.academy_cases
for select
to authenticated
using (
    private.can_view_user(owner_user_id)
);

create policy academy_cases_insert_own
on public.academy_cases
for insert
to authenticated
with check (
    owner_user_id = (select auth.uid())
);

create policy academy_cases_update_own
on public.academy_cases
for update
to authenticated
using (
    owner_user_id = (select auth.uid())
)
with check (
    owner_user_id = (select auth.uid())
);


-- SESSION
create policy academy_sessions_select_scope
on public.academy_sessions
for select
to authenticated
using (
    private.can_view_user(user_id)
);

create policy academy_sessions_insert_own
on public.academy_sessions
for insert
to authenticated
with check (
    user_id = (select auth.uid())
    and exists (
        select 1
        from public.academy_cases c
        where c.id = case_id
          and c.owner_user_id = (select auth.uid())
    )
);

create policy academy_sessions_update_own
on public.academy_sessions
for update
to authenticated
using (
    user_id = (select auth.uid())
)
with check (
    user_id = (select auth.uid())
);


-- ASSESSMENT
create policy academy_assessments_select_scope
on public.academy_assessments
for select
to authenticated
using (
    private.can_view_user(user_id)
);

create policy academy_assessments_insert_own
on public.academy_assessments
for insert
to authenticated
with check (
    user_id = (select auth.uid())
    and exists (
        select 1
        from public.academy_sessions s
        where s.id = session_id
          and s.user_id = (select auth.uid())
          and s.case_id = case_id
    )
);


-- LEARNING PROFILE
create policy academy_learning_profiles_select_scope
on public.academy_learning_profiles
for select
to authenticated
using (
    private.can_view_user(user_id)
);

create policy academy_learning_profiles_insert_own
on public.academy_learning_profiles
for insert
to authenticated
with check (
    user_id = (select auth.uid())
);

create policy academy_learning_profiles_update_own
on public.academy_learning_profiles
for update
to authenticated
using (
    user_id = (select auth.uid())
)
with check (
    user_id = (select auth.uid())
);


commit;
