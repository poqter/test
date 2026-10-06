-- =========================================================
-- HWARANG PLATFORM
-- 16 BRIEFING ENGINE V1.6 - ACTION INTELLIGENCE BASELINE
--
-- Apply ONCE after migrations through 15 are applied.
--
-- This migration creates the first production schema for:
-- - Common Briefing Engine (INSURANCE / MARKET / NEWS)
-- - Revision + immutable Snapshot
-- - Persistent Shared Event + append-only Event Timeline
-- - CORE / LIGHT_DIGEST selection
-- - FAST BRIEF / TODAY ACTION / communication state
-- - generic audience segments + WORKSPACE actions
-- - Source/Evidence metadata
-- - Search/tool/token/cost logs
-- - Job / Checkpoint / Audit
-- - external_content_payload foundation for Phase 2 customer Web Share
--
-- IMPORTANT
-- - Migration 16 has not previously been applied. Do NOT apply older drafts.
-- - This migration does NOT create Scheduler jobs or deploy WORKSPACE UI.
-- - This migration does NOT expose public customer-share URLs.
-- - This migration does NOT store customer IDs inside briefing audience segments.
-- =========================================================

begin;

-- ---------------------------------------------------------
-- 0. Preflight
-- ---------------------------------------------------------
do $$
declare
    v_table text;
begin
    if to_regclass('public.profiles') is null then
        raise exception 'MISSING_REQUIRED_TABLE: public.profiles';
    end if;

    if to_regclass('public.hwarang_permissions') is null then
        raise exception 'MISSING_REQUIRED_TABLE: public.hwarang_permissions';
    end if;

    if to_regprocedure('private.set_updated_at()') is null then
        raise exception 'MISSING_REQUIRED_FUNCTION: private.set_updated_at()';
    end if;

    foreach v_table in array array[
        'hwarang_briefing_profiles',
        'hwarang_briefings',
        'hwarang_briefing_revisions',
        'hwarang_briefing_snapshots',
        'hwarang_briefing_events',
        'hwarang_briefing_event_updates',
        'hwarang_briefing_issues',
        'hwarang_briefing_actions',
        'hwarang_briefing_sources',
        'hwarang_briefing_issue_sources',
        'hwarang_briefing_event_update_sources',
        'hwarang_briefing_issue_locks',
        'hwarang_briefing_jobs',
        'hwarang_briefing_checkpoints',
        'hwarang_briefing_api_usage',
        'hwarang_briefing_audit_log'
    ]
    loop
        if to_regclass('public.' || v_table) is not null then
            raise exception 'MIGRATION_16_ALREADY_OR_PARTIALLY_APPLIED: public.%', v_table;
        end if;
    end loop;
end;
$$;

-- ---------------------------------------------------------
-- 1. Profile runtime config
-- Stable content rules live in code/SPEC.
-- This table stores runtime switches and operational settings.
-- ---------------------------------------------------------
create table public.hwarang_briefing_profiles (
    profile_code text primary key
        check (profile_code in ('INSURANCE', 'MARKET', 'NEWS')),
    display_name text not null,
    is_enabled boolean not null default true,
    run_mode text not null default 'shadow'
        check (run_mode in ('shadow', 'manual', 'auto')),
    timezone text not null default 'Asia/Seoul',
    publish_time_kst time not null,
    collect_cutoff_time_kst time,
    external_share_default boolean not null default false,
    routine_model_override text,
    discovery_model_override text,
    escalation_model_override text,
    settings jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint hwarang_briefing_profiles_settings_object
        check (jsonb_typeof(settings) = 'object')
);

create trigger hwarang_briefing_profiles_set_updated_at
before update on public.hwarang_briefing_profiles
for each row execute function private.set_updated_at();

-- ---------------------------------------------------------
-- 2. Logical briefing record
-- One row per profile/date/type. Content changes become revisions.
-- ---------------------------------------------------------
create table public.hwarang_briefings (
    id uuid primary key default gen_random_uuid(),
    profile_code text not null
        references public.hwarang_briefing_profiles(profile_code) on delete restrict,
    briefing_date date not null,
    briefing_type text not null,
    current_published_revision_id uuid,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint hwarang_briefings_identity_unique
        unique (profile_code, briefing_date, briefing_type)
);

create index hwarang_briefings_profile_date_idx
    on public.hwarang_briefings(profile_code, briefing_date desc);

create trigger hwarang_briefings_set_updated_at
before update on public.hwarang_briefings
for each row execute function private.set_updated_at();

-- ---------------------------------------------------------
-- 3. Revision workflow/control state
-- ---------------------------------------------------------
create table public.hwarang_briefing_revisions (
    id uuid primary key default gen_random_uuid(),
    briefing_id uuid not null
        references public.hwarang_briefings(id) on delete restrict,
    revision_no integer not null check (revision_no > 0),
    revision_type text not null
        check (revision_type in ('initial', 'update', 'correction', 'regeneration')),
    publication_status text not null default 'draft'
        check (publication_status in ('draft', 'published', 'partial', 'hidden')),
    validation_status text not null default 'required'
        check (validation_status in ('ok', 'required', 'rejected')),
    coverage_status text not null default 'insufficient'
        check (coverage_status in ('healthy', 'degraded', 'insufficient')),
    internal_pdf_status text not null default 'not_requested'
        check (internal_pdf_status in ('not_requested', 'pending', 'ready', 'failed')),
    external_pdf_status text not null default 'not_requested'
        check (external_pdf_status in ('not_requested', 'pending', 'ready', 'failed')),
    external_share_allowed boolean not null default false,
    external_qa_passed boolean not null default false,
    carry_forward_eligible boolean not null default false,
    carry_forward_reason text,
    data_as_of timestamptz,
    generated_at timestamptz,
    published_at timestamptz,
    created_by uuid references public.profiles(id) on delete set null,
    approved_by uuid references public.profiles(id) on delete set null,
    change_summary text,
    version_trace jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint hwarang_briefing_revisions_number_unique
        unique (briefing_id, revision_no),
    constraint hwarang_briefing_revisions_briefing_id_id_unique
        unique (briefing_id, id),
    constraint hwarang_briefing_revisions_version_trace_object
        check (jsonb_typeof(version_trace) = 'object'),
    constraint hwarang_briefing_revisions_external_share_gate
        check (
            external_share_allowed = false
            or (
                publication_status = 'published'
                and validation_status = 'ok'
                and external_qa_passed = true
            )
        )
);

create index hwarang_briefing_revisions_briefing_idx
    on public.hwarang_briefing_revisions(briefing_id, revision_no desc);

create index hwarang_briefing_revisions_publication_idx
    on public.hwarang_briefing_revisions(publication_status, published_at desc);

create index hwarang_briefing_revisions_carry_idx
    on public.hwarang_briefing_revisions(carry_forward_eligible, published_at desc)
    where carry_forward_eligible = true;

create trigger hwarang_briefing_revisions_set_updated_at
before update on public.hwarang_briefing_revisions
for each row execute function private.set_updated_at();

alter table public.hwarang_briefings
    add constraint hwarang_briefings_current_revision_fk
    foreign key (id, current_published_revision_id)
    references public.hwarang_briefing_revisions(briefing_id, id)
    on delete restrict;

-- ---------------------------------------------------------
-- 4. Immutable Snapshot
-- content_payload = internal render/data contract.
-- external_content_payload = sanitized external variant foundation.
-- FAST BRIEF and TODAY ACTION remain explicit queryable payloads.
-- ---------------------------------------------------------
create table public.hwarang_briefing_snapshots (
    id uuid primary key default gen_random_uuid(),
    revision_id uuid not null unique
        references public.hwarang_briefing_revisions(id) on delete restrict,
    content_hash text,
    content_payload jsonb not null,
    external_content_payload jsonb not null default '{}'::jsonb,
    fast_brief_payload jsonb not null default '{}'::jsonb,
    today_action_payload jsonb not null default '{}'::jsonb,
    qa_payload jsonb not null default '{}'::jsonb,
    snapshot_created_at timestamptz not null default now(),
    constraint hwarang_briefing_snapshots_content_object
        check (jsonb_typeof(content_payload) = 'object'),
    constraint hwarang_briefing_snapshots_external_object
        check (jsonb_typeof(external_content_payload) = 'object'),
    constraint hwarang_briefing_snapshots_fast_object
        check (jsonb_typeof(fast_brief_payload) = 'object'),
    constraint hwarang_briefing_snapshots_action_object
        check (jsonb_typeof(today_action_payload) = 'object'),
    constraint hwarang_briefing_snapshots_qa_object
        check (jsonb_typeof(qa_payload) = 'object')
);

-- ---------------------------------------------------------
-- 5. Persistent Shared Event
-- One event can appear across profiles and days.
-- ---------------------------------------------------------
create table public.hwarang_briefing_events (
    id uuid primary key default gen_random_uuid(),
    event_key text not null unique,
    canonical_title text not null,
    primary_category text,
    event_status text not null default 'active'
        check (event_status in ('active', 'watching', 'resolved', 'archived')),
    first_seen_at timestamptz not null,
    last_seen_at timestamptz not null,
    resolved_at timestamptz,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint hwarang_briefing_events_seen_order
        check (last_seen_at >= first_seen_at),
    constraint hwarang_briefing_events_metadata_object
        check (jsonb_typeof(metadata) = 'object')
);

create index hwarang_briefing_events_last_seen_idx
    on public.hwarang_briefing_events(last_seen_at desc);
create index hwarang_briefing_events_status_idx
    on public.hwarang_briefing_events(event_status, last_seen_at desc);

create trigger hwarang_briefing_events_set_updated_at
before update on public.hwarang_briefing_events
for each row execute function private.set_updated_at();

-- ---------------------------------------------------------
-- 6. Append-only Event Timeline updates
-- ---------------------------------------------------------
create table public.hwarang_briefing_event_updates (
    id uuid primary key default gen_random_uuid(),
    event_id uuid not null
        references public.hwarang_briefing_events(id) on delete restrict,
    revision_id uuid
        references public.hwarang_briefing_revisions(id) on delete restrict,
    update_key text not null,
    update_type text not null
        check (update_type in ('initial', 'development', 'clarification', 'correction', 'resolution')),
    evidence_status text not null
        check (evidence_status in (
            'official_confirmed', 'multi_source_confirmed', 'reported',
            'single_source', 'conflicted'
        )),
    title text not null,
    change_summary text not null,
    observed_at timestamptz not null,
    effective_at timestamptz,
    details jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint hwarang_briefing_event_updates_event_key_unique
        unique (event_id, update_key),
    constraint hwarang_briefing_event_updates_details_object
        check (jsonb_typeof(details) = 'object')
);

create index hwarang_briefing_event_updates_event_time_idx
    on public.hwarang_briefing_event_updates(event_id, observed_at desc);

-- ---------------------------------------------------------
-- 7. Snapshot issues
-- ---------------------------------------------------------
create table public.hwarang_briefing_issues (
    id uuid primary key default gen_random_uuid(),
    snapshot_id uuid not null
        references public.hwarang_briefing_snapshots(id) on delete restrict,
    event_id uuid
        references public.hwarang_briefing_events(id) on delete restrict,
    carry_forward_source_update_id uuid
        references public.hwarang_briefing_event_updates(id) on delete restrict,
    issue_key text not null,
    sort_order integer not null default 0,
    category text,
    tags text[] not null default '{}'::text[],
    importance_score numeric(5,2)
        check (importance_score is null or (importance_score >= 0 and importance_score <= 100)),
    importance_label text,
    issue_status text,
    selection_tier text not null
        check (selection_tier in ('core', 'light_digest', 'excluded')),
    evidence_status text not null
        check (evidence_status in (
            'official_confirmed', 'multi_source_confirmed', 'reported',
            'single_source', 'conflicted'
        )),
    title text not null,
    summary text,
    fact_payload jsonb not null default '{}'::jsonb,
    analysis_payload jsonb not null default '{}'::jsonb,
    profile_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint hwarang_briefing_issues_snapshot_key_unique
        unique (snapshot_id, issue_key),
    constraint hwarang_briefing_issues_fact_object
        check (jsonb_typeof(fact_payload) = 'object'),
    constraint hwarang_briefing_issues_analysis_object
        check (jsonb_typeof(analysis_payload) = 'object'),
    constraint hwarang_briefing_issues_profile_object
        check (jsonb_typeof(profile_payload) = 'object')
);

create index hwarang_briefing_issues_snapshot_sort_idx
    on public.hwarang_briefing_issues(snapshot_id, selection_tier, sort_order, id);
create index hwarang_briefing_issues_category_idx
    on public.hwarang_briefing_issues(category);
create index hwarang_briefing_issues_event_idx
    on public.hwarang_briefing_issues(event_id)
    where event_id is not null;

-- ---------------------------------------------------------
-- 8. Action Intelligence cards
-- No customer IDs are stored here. audience_segments are generic labels.
-- ---------------------------------------------------------
create table public.hwarang_briefing_actions (
    id uuid primary key default gen_random_uuid(),
    snapshot_id uuid not null
        references public.hwarang_briefing_snapshots(id) on delete restrict,
    issue_id uuid
        references public.hwarang_briefing_issues(id) on delete restrict,
    event_id uuid
        references public.hwarang_briefing_events(id) on delete restrict,
    action_key text not null,
    action_scope text not null default 'issue'
        check (action_scope in ('briefing', 'issue')),
    action_state text not null
        check (action_state in ('review_now', 'reference_today', 'watch')),
    communication_state text not null default 'not_applicable'
        check (communication_state in (
            'customer_ready', 'consultation_reference', 'internal_check',
            'do_not_mention', 'not_applicable'
        )),
    title text not null,
    summary text not null,
    audience_segments text[] not null default '{}'::text[],
    conversation_payload jsonb not null default '{}'::jsonb,
    workspace_actions jsonb not null default '[]'::jsonb,
    academy_practice_hint jsonb not null default '{}'::jsonb,
    sort_order integer not null default 0,
    created_at timestamptz not null default now(),
    constraint hwarang_briefing_actions_snapshot_key_unique
        unique (snapshot_id, action_key),
    constraint hwarang_briefing_actions_scope_issue_check
        check (
            (action_scope = 'briefing' and issue_id is null)
            or (action_scope = 'issue' and issue_id is not null)
        ),
    constraint hwarang_briefing_actions_conversation_object
        check (jsonb_typeof(conversation_payload) = 'object'),
    constraint hwarang_briefing_actions_workspace_array
        check (jsonb_typeof(workspace_actions) = 'array'),
    constraint hwarang_briefing_actions_academy_object
        check (jsonb_typeof(academy_practice_hint) = 'object')
);

create index hwarang_briefing_actions_snapshot_idx
    on public.hwarang_briefing_actions(snapshot_id, action_state, sort_order);
create index hwarang_briefing_actions_issue_idx
    on public.hwarang_briefing_actions(issue_id)
    where issue_id is not null;

-- ---------------------------------------------------------
-- 9. Snapshot source metadata
-- ---------------------------------------------------------
create table public.hwarang_briefing_sources (
    id uuid primary key default gen_random_uuid(),
    snapshot_id uuid not null
        references public.hwarang_briefing_snapshots(id) on delete restrict,
    source_code text,
    source_family_code text,
    endpoint_role text
        check (endpoint_role is null or endpoint_role in ('primary', 'fallback', 'discovery')),
    source_kind text not null
        check (source_kind in ('official', 'industry_official', 'news', 'market_data', 'discovery')),
    source_tier text,
    collector_provider text,
    source_name text not null,
    publisher_name text,
    publisher_domain text,
    title text not null,
    url text not null,
    canonical_url text,
    published_at timestamptz,
    updated_at timestamptz,
    retrieved_at timestamptz not null default now(),
    last_verified_at timestamptz,
    access_status text not null default 'unknown'
        check (access_status in (
            'ok', 'unavailable', 'moved', 'blocked', 'rate_limited',
            'credential_missing', 'unknown'
        )),
    content_fingerprint text,
    untrusted_external boolean not null default true,
    created_at timestamptz not null default now(),
    constraint hwarang_briefing_sources_snapshot_url_unique
        unique (snapshot_id, url)
);

create index hwarang_briefing_sources_snapshot_idx
    on public.hwarang_briefing_sources(snapshot_id, source_kind, source_tier);
create index hwarang_briefing_sources_published_idx
    on public.hwarang_briefing_sources(published_at desc);
create index hwarang_briefing_sources_publisher_idx
    on public.hwarang_briefing_sources(publisher_domain)
    where publisher_domain is not null;

-- ---------------------------------------------------------
-- 10. Issue <-> Source relation
-- ---------------------------------------------------------
create table public.hwarang_briefing_issue_sources (
    issue_id uuid not null
        references public.hwarang_briefing_issues(id) on delete restrict,
    source_id uuid not null
        references public.hwarang_briefing_sources(id) on delete restrict,
    relation_type text not null default 'supporting'
        check (relation_type in ('primary', 'supporting', 'context', 'market_reaction')),
    created_at timestamptz not null default now(),
    primary key (issue_id, source_id)
);

-- ---------------------------------------------------------
-- 11. Event Update <-> Source relation
-- ---------------------------------------------------------
create table public.hwarang_briefing_event_update_sources (
    event_update_id uuid not null
        references public.hwarang_briefing_event_updates(id) on delete restrict,
    source_id uuid not null
        references public.hwarang_briefing_sources(id) on delete restrict,
    relation_type text not null default 'supporting'
        check (relation_type in ('primary', 'supporting', 'context')),
    created_at timestamptz not null default now(),
    primary key (event_update_id, source_id)
);

-- ---------------------------------------------------------
-- 12. Manual issue locks
-- ---------------------------------------------------------
create table public.hwarang_briefing_issue_locks (
    briefing_id uuid not null
        references public.hwarang_briefings(id) on delete restrict,
    issue_key text not null,
    is_locked boolean not null default true,
    locked_by uuid references public.profiles(id) on delete set null,
    reason text,
    locked_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (briefing_id, issue_key)
);

create trigger hwarang_briefing_issue_locks_set_updated_at
before update on public.hwarang_briefing_issue_locks
for each row execute function private.set_updated_at();

-- ---------------------------------------------------------
-- 13. Job execution history / concurrency control
-- ---------------------------------------------------------
create table public.hwarang_briefing_jobs (
    id uuid primary key default gen_random_uuid(),
    profile_code text not null
        references public.hwarang_briefing_profiles(profile_code) on delete restrict,
    briefing_id uuid
        references public.hwarang_briefings(id) on delete set null,
    briefing_date date not null,
    briefing_type text not null,
    job_key text not null,
    attempt_no integer not null default 1 check (attempt_no > 0),
    trigger_type text not null default 'scheduled'
        check (trigger_type in ('scheduled', 'manual', 'retry', 'update_check')),
    job_status text not null default 'scheduled'
        check (job_status in (
            'scheduled', 'collecting', 'normalizing', 'validating',
            'analyzing', 'generating', 'completed', 'failed'
        )),
    failure_code text,
    failure_message text,
    metadata jsonb not null default '{}'::jsonb,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz not null default now(),
    constraint hwarang_briefing_jobs_attempt_unique
        unique (job_key, attempt_no),
    constraint hwarang_briefing_jobs_metadata_object
        check (jsonb_typeof(metadata) = 'object')
);

create unique index hwarang_briefing_jobs_one_active_idx
    on public.hwarang_briefing_jobs(job_key)
    where job_status in (
        'scheduled', 'collecting', 'normalizing',
        'validating', 'analyzing', 'generating'
    );
create index hwarang_briefing_jobs_profile_date_idx
    on public.hwarang_briefing_jobs(profile_code, briefing_date desc, created_at desc);
create index hwarang_briefing_jobs_status_idx
    on public.hwarang_briefing_jobs(job_status, created_at desc);

-- ---------------------------------------------------------
-- 14. Checkpoint
-- ---------------------------------------------------------
create table public.hwarang_briefing_checkpoints (
    id uuid primary key default gen_random_uuid(),
    job_id uuid not null
        references public.hwarang_briefing_jobs(id) on delete cascade,
    checkpoint_code text not null
        check (checkpoint_code in (
            'direct_collection_complete', 'web_discovery_complete',
            'normalized', 'clustered', 'validated', 'analyzed',
            'action_intelligence_generated', 'snapshot_created',
            'published', 'pdf_rendered'
        )),
    payload jsonb not null default '{}'::jsonb,
    completed_at timestamptz not null default now(),
    expires_at timestamptz,
    constraint hwarang_briefing_checkpoints_job_code_unique
        unique (job_id, checkpoint_code),
    constraint hwarang_briefing_checkpoints_payload_object
        check (jsonb_typeof(payload) = 'object')
);

create index hwarang_briefing_checkpoints_expiry_idx
    on public.hwarang_briefing_checkpoints(expires_at)
    where expires_at is not null;

-- ---------------------------------------------------------
-- 15. API usage / cost log
-- Search Tool Call and actual Search Action are distinct.
-- No API keys/secrets are stored.
-- ---------------------------------------------------------
create table public.hwarang_briefing_api_usage (
    id uuid primary key default gen_random_uuid(),
    job_id uuid not null
        references public.hwarang_briefing_jobs(id) on delete cascade,
    profile_code text not null
        references public.hwarang_briefing_profiles(profile_code) on delete restrict,
    provider text not null,
    operation text not null,
    model_name text,
    service_tier text,
    input_tokens integer not null default 0 check (input_tokens >= 0),
    cached_input_tokens integer not null default 0 check (cached_input_tokens >= 0),
    output_tokens integer not null default 0 check (output_tokens >= 0),
    reasoning_tokens integer not null default 0 check (reasoning_tokens >= 0),
    web_tool_calls integer not null default 0 check (web_tool_calls >= 0),
    search_actions integer not null default 0 check (search_actions >= 0),
    search_retry_count integer not null default 0 check (search_retry_count >= 0),
    verification_search_actions integer not null default 0 check (verification_search_actions >= 0),
    estimated_cost_usd numeric(14,6)
        check (estimated_cost_usd is null or estimated_cost_usd >= 0),
    actual_cost_usd numeric(14,6)
        check (actual_cost_usd is null or actual_cost_usd >= 0),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint hwarang_briefing_api_usage_metadata_object
        check (jsonb_typeof(metadata) = 'object')
);

create index hwarang_briefing_api_usage_job_idx
    on public.hwarang_briefing_api_usage(job_id, created_at);
create index hwarang_briefing_api_usage_profile_idx
    on public.hwarang_briefing_api_usage(profile_code, created_at desc);

-- ---------------------------------------------------------
-- 16. Briefing audit log
-- ---------------------------------------------------------
create table public.hwarang_briefing_audit_log (
    id uuid primary key default gen_random_uuid(),
    actor_type text not null check (actor_type in ('system', 'user')),
    actor_user_id uuid references public.profiles(id) on delete set null,
    action text not null,
    profile_code text
        references public.hwarang_briefing_profiles(profile_code) on delete restrict,
    briefing_id uuid
        references public.hwarang_briefings(id) on delete restrict,
    revision_id uuid
        references public.hwarang_briefing_revisions(id) on delete restrict,
    event_id uuid
        references public.hwarang_briefing_events(id) on delete restrict,
    issue_key text,
    details jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint hwarang_briefing_audit_actor_check
        check (
            actor_type = 'system'
            or (actor_type = 'user' and actor_user_id is not null)
        ),
    constraint hwarang_briefing_audit_details_object
        check (jsonb_typeof(details) = 'object')
);

create index hwarang_briefing_audit_created_idx
    on public.hwarang_briefing_audit_log(created_at desc);
create index hwarang_briefing_audit_briefing_idx
    on public.hwarang_briefing_audit_log(briefing_id, created_at desc)
    where briefing_id is not null;
create index hwarang_briefing_audit_event_idx
    on public.hwarang_briefing_audit_log(event_id, created_at desc)
    where event_id is not null;

-- ---------------------------------------------------------
-- 17. Immutable content protection
-- Event master rows are mutable, Event Updates are append-only.
-- ---------------------------------------------------------
create or replace function private.reject_briefing_immutable_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    raise exception 'BRIEFING_IMMUTABLE_RECORD';
end;
$$;

revoke all on function private.reject_briefing_immutable_mutation() from public;

create trigger hwarang_briefing_snapshots_immutable
before update or delete on public.hwarang_briefing_snapshots
for each row execute function private.reject_briefing_immutable_mutation();

create trigger hwarang_briefing_event_updates_immutable
before update or delete on public.hwarang_briefing_event_updates
for each row execute function private.reject_briefing_immutable_mutation();

create trigger hwarang_briefing_issues_immutable
before update or delete on public.hwarang_briefing_issues
for each row execute function private.reject_briefing_immutable_mutation();

create trigger hwarang_briefing_actions_immutable
before update or delete on public.hwarang_briefing_actions
for each row execute function private.reject_briefing_immutable_mutation();

create trigger hwarang_briefing_sources_immutable
before update or delete on public.hwarang_briefing_sources
for each row execute function private.reject_briefing_immutable_mutation();

create trigger hwarang_briefing_issue_sources_immutable
before update or delete on public.hwarang_briefing_issue_sources
for each row execute function private.reject_briefing_immutable_mutation();

create trigger hwarang_briefing_event_update_sources_immutable
before update or delete on public.hwarang_briefing_event_update_sources
for each row execute function private.reject_briefing_immutable_mutation();

-- ---------------------------------------------------------
-- 18. Profile seed config
-- ---------------------------------------------------------
insert into public.hwarang_briefing_profiles (
    profile_code, display_name, is_enabled, run_mode, timezone,
    publish_time_kst, collect_cutoff_time_kst,
    external_share_default, settings
)
values
(
    'INSURANCE',
    '보험업계 브리핑',
    true,
    'shadow',
    'Asia/Seoul',
    time '08:00',
    time '07:30',
    false,
    '{
      "briefing_types": ["MORNING"],
      "pipeline_start_kst": "06:30",
      "retry_times_kst": ["08:10"],
      "update_check_times_kst": ["09:30", "11:30", "14:30"],
      "max_daily_updates": 3,
      "selection": {"core_threshold": 50, "light_floor": 20, "light_ceiling": 49},
      "freshness_hours": {"core": 36, "light": 96},
      "discovery_search_actions": {"target": 2, "soft": 3, "hard": 4},
      "shared_discovery_pool": {"pool_code": "INSURANCE_NEWS", "target": 4, "soft": 5, "hard": 6},
      "verification_search_actions": {"target": 1, "hard": 2},
      "action_intelligence": true,
      "event_timeline": true
    }'::jsonb
),
(
    'MARKET',
    '경제·주식 브리핑',
    true,
    'shadow',
    'Asia/Seoul',
    time '07:30',
    time '07:10',
    false,
    '{
      "briefing_types": ["MORNING", "WEEKLY_CLOSE", "HOLIDAY"],
      "pipeline_start_kst": "06:30",
      "retry_times_kst": ["07:40", "07:55"],
      "realtime_required": false,
      "market_provider_strategy": "adapter_first",
      "selection": {"core_threshold": 55, "light_floor": 30, "light_ceiling": 54},
      "web_search_actions": {"target_min": 0, "target_max": 2, "soft": 4, "hard": 6},
      "action_intelligence": true,
      "event_timeline": true
    }'::jsonb
),
(
    'NEWS',
    '국내 주요 뉴스 브리핑',
    true,
    'shadow',
    'Asia/Seoul',
    time '08:00',
    time '07:30',
    false,
    '{
      "briefing_types": ["MORNING", "HOLIDAY"],
      "pipeline_start_kst": "06:30",
      "retry_times_kst": ["08:10"],
      "update_check_times_kst": ["12:00", "17:00"],
      "max_daily_updates": 2,
      "selection": {"core_threshold": 50, "light_floor": 20, "light_ceiling": 49},
      "freshness_hours": {"core": 36, "light": 96},
      "discovery_search_actions": {"target": 2, "soft": 3, "hard": 4},
      "shared_discovery_pool": {"pool_code": "INSURANCE_NEWS", "target": 4, "soft": 5, "hard": 6},
      "verification_search_actions": {"target": 1, "hard": 2},
      "action_intelligence": true,
      "event_timeline": true
    }'::jsonb
);

-- ---------------------------------------------------------
-- 19. WORKSPACE permissions
-- Content manager remains a feature permission, not a new system role.
-- ---------------------------------------------------------
insert into public.hwarang_permissions
(permission_code, app_code, group_label, display_name, description, sort_order, default_granted)
values
(
    'workspace.briefing',
    'workspace',
    '브리핑',
    '브리핑 조회',
    '보험업계·경제시장·국내뉴스 브리핑 조회',
    90,
    true
),
(
    'workspace.briefing_manage',
    'workspace',
    '브리핑',
    '브리핑 콘텐츠 관리',
    '브리핑 재생성, 수정, 출처 검수, 외부 공유 제어, Event 연결/분리 및 로그 조회',
    95,
    false
)
on conflict (permission_code) do update set
    app_code = excluded.app_code,
    group_label = excluded.group_label,
    display_name = excluded.display_name,
    description = excluded.description,
    sort_order = excluded.sort_order,
    default_granted = excluded.default_granted,
    is_active = true,
    updated_at = now();

-- ---------------------------------------------------------
-- 20. RLS / grants
-- App server uses service_role. Browser clients do not access tables directly.
-- ---------------------------------------------------------
alter table public.hwarang_briefing_profiles enable row level security;
alter table public.hwarang_briefings enable row level security;
alter table public.hwarang_briefing_revisions enable row level security;
alter table public.hwarang_briefing_snapshots enable row level security;
alter table public.hwarang_briefing_events enable row level security;
alter table public.hwarang_briefing_event_updates enable row level security;
alter table public.hwarang_briefing_issues enable row level security;
alter table public.hwarang_briefing_actions enable row level security;
alter table public.hwarang_briefing_sources enable row level security;
alter table public.hwarang_briefing_issue_sources enable row level security;
alter table public.hwarang_briefing_event_update_sources enable row level security;
alter table public.hwarang_briefing_issue_locks enable row level security;
alter table public.hwarang_briefing_jobs enable row level security;
alter table public.hwarang_briefing_checkpoints enable row level security;
alter table public.hwarang_briefing_api_usage enable row level security;
alter table public.hwarang_briefing_audit_log enable row level security;

revoke all on table public.hwarang_briefing_profiles from anon, authenticated;
revoke all on table public.hwarang_briefings from anon, authenticated;
revoke all on table public.hwarang_briefing_revisions from anon, authenticated;
revoke all on table public.hwarang_briefing_snapshots from anon, authenticated;
revoke all on table public.hwarang_briefing_events from anon, authenticated;
revoke all on table public.hwarang_briefing_event_updates from anon, authenticated;
revoke all on table public.hwarang_briefing_issues from anon, authenticated;
revoke all on table public.hwarang_briefing_actions from anon, authenticated;
revoke all on table public.hwarang_briefing_sources from anon, authenticated;
revoke all on table public.hwarang_briefing_issue_sources from anon, authenticated;
revoke all on table public.hwarang_briefing_event_update_sources from anon, authenticated;
revoke all on table public.hwarang_briefing_issue_locks from anon, authenticated;
revoke all on table public.hwarang_briefing_jobs from anon, authenticated;
revoke all on table public.hwarang_briefing_checkpoints from anon, authenticated;
revoke all on table public.hwarang_briefing_api_usage from anon, authenticated;
revoke all on table public.hwarang_briefing_audit_log from anon, authenticated;

-- Mutable config/control/workflow
grant select, insert, update on table public.hwarang_briefing_profiles to service_role;
grant select, insert, update on table public.hwarang_briefings to service_role;
grant select, insert, update on table public.hwarang_briefing_revisions to service_role;
grant select, insert, update on table public.hwarang_briefing_events to service_role;
grant select, insert, update on table public.hwarang_briefing_issue_locks to service_role;

-- Immutable content records
grant select, insert on table public.hwarang_briefing_snapshots to service_role;
grant select, insert on table public.hwarang_briefing_event_updates to service_role;
grant select, insert on table public.hwarang_briefing_issues to service_role;
grant select, insert on table public.hwarang_briefing_actions to service_role;
grant select, insert on table public.hwarang_briefing_sources to service_role;
grant select, insert on table public.hwarang_briefing_issue_sources to service_role;
grant select, insert on table public.hwarang_briefing_event_update_sources to service_role;

-- Operational records
grant select, insert, update, delete on table public.hwarang_briefing_jobs to service_role;
grant select, insert, update, delete on table public.hwarang_briefing_checkpoints to service_role;
grant select, insert, delete on table public.hwarang_briefing_api_usage to service_role;

-- Audit append-only
grant select, insert on table public.hwarang_briefing_audit_log to service_role;

commit;

notify pgrst, 'reload schema';
