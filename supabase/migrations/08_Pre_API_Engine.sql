-- =========================================================
-- HWARANG ACADEMY
-- PRE-API ENGINE SUPPORT v1
--
-- Adds versioned Case/Session fields for the deterministic customer,
-- insurance, analysis, proposal and evidence-log engine.
-- No paid AI/API dependency is introduced by this migration.
-- =========================================================

begin;

alter table public.academy_cases
    add column if not exists coverage_analysis jsonb not null default '{}'::jsonb,
    add column if not exists proposal_state jsonb not null default '{}'::jsonb,
    add column if not exists customer_generator_version text,
    add column if not exists insurance_generator_version text,
    add column if not exists coverage_mapping_version text,
    add column if not exists excel_template_version text,
    add column if not exists proposal_generator_version text;

alter table public.academy_sessions
    add column if not exists training_focus text not null default 'comprehensive',
    add column if not exists interaction_mode text not null default 'TEXT',
    add column if not exists evidence_log jsonb not null default '[]'::jsonb,
    add column if not exists prompt_version text,
    add column if not exists model_version text;

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conname = 'academy_sessions_interaction_mode_check'
          and conrelid = 'public.academy_sessions'::regclass
    ) then
        alter table public.academy_sessions
            add constraint academy_sessions_interaction_mode_check
            check (interaction_mode in ('TEXT', 'VOICE'));
    end if;
end
$$;

create index if not exists academy_sessions_training_focus_idx
    on public.academy_sessions(user_id, training_focus, updated_at desc);

create index if not exists academy_sessions_interaction_mode_idx
    on public.academy_sessions(user_id, interaction_mode, updated_at desc);

-- Existing service_role table grants continue to cover the new columns.
-- Authenticated user RLS policies remain unchanged because ownership rules
-- are still based on user_id / owner_user_id.

commit;
