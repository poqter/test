-- V63.3: existing ACADEMY tables, private rule checkpoints and KST totals.
-- Apply after migrations 01-17. No briefing objects are changed.
begin;

create index if not exists academy_rule_history_owner_idx
on public.academy_sessions(user_id, updated_at desc)
where metadata->>'training_engine' = 'rules';

create or replace function public.get_hwarang_rule_learning_summary(p_user_id uuid)
returns jsonb language plpgsql volatile security invoker set search_path = '' as $$
begin
    if not exists (select 1 from public.profiles where id=p_user_id and is_active)
       or not exists (select 1 from public.hwarang_app_access where user_id=p_user_id and app_code='academy' and is_enabled)
       or not exists (select 1 from public.get_hwarang_effective_permissions(p_user_id)
                      where permission_code='academy.simulator') then
        raise exception 'RULE_TRAINING_ACCESS_DENIED';
    end if;
    return (select jsonb_build_object(
        'total',count(*), 'completed',count(*) filter(where status='completed'),
        'in_progress',count(*) filter(where status='in_progress'),
        'last_saved_at',max(updated_at))
        from public.academy_sessions
        where user_id=p_user_id and metadata->>'training_engine'='rules');
end $$;

create or replace function public.save_hwarang_rule_training(
    p_user_id uuid, p_record jsonb, p_expected_version integer
) returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
    v_id uuid; v_row public.academy_sessions; v_version integer;
    v_hash text; v_report jsonb; v_ended boolean; v_turn integer;
begin
    if not exists (select 1 from public.profiles where id=p_user_id and is_active)
       or not exists (select 1 from public.hwarang_app_access where user_id=p_user_id and app_code='academy' and is_enabled)
       or not exists (select 1 from public.get_hwarang_effective_permissions(p_user_id)
                      where permission_code='academy.simulator') then
        raise exception 'RULE_TRAINING_ACCESS_DENIED';
    end if;
    if jsonb_typeof(p_record) is distinct from 'object' or octet_length(p_record::text)>3000000
       or (p_record->'wire'->>'schema') is distinct from '1'
       or not coalesce((p_record->>'mode') in ('GUIDE','COACH','SOLO','ASSESSMENT'),false)
       or not coalesce((p_record->>'scenario_id') in ('C07-S01','A01-S01','D08-S01','F07-S01','G10-S01','H10-S01'),false)
       or not coalesce((p_record->>'session_length') in ('QUICK','STANDARD','DEEP'),false)
       or jsonb_typeof(p_record->'transcript') is distinct from 'array'
       or p_expected_version is null or p_expected_version<0 then
        raise exception 'INVALID_RULE_CHECKPOINT';
    end if;
    v_id := (p_record->>'id')::uuid;
    v_turn := (p_record->>'turn_count')::integer;
    v_ended := (p_record->>'ended')::boolean;
    if v_id is null or v_turn is null or v_turn<0 or v_turn>40 or v_ended is null then
        raise exception 'INVALID_RULE_CHECKPOINT';
    end if;
    v_hash := pg_catalog.md5(p_record::text);
    v_report := coalesce(p_record->'report','{}'::jsonb);

    -- One fictional case per training round. No real customer profile is created.
    insert into public.academy_cases(id,owner_user_id,title,customer_alias,metadata)
    values(v_id,p_user_id,p_record->>'scenario_id','가상 훈련 고객',
           jsonb_build_object('training_engine','rules')) on conflict(id) do nothing;
    if not exists(select 1 from public.academy_cases where id=v_id and owner_user_id=p_user_id
                  and metadata->>'training_engine'='rules') then
        raise exception 'RULE_TRAINING_ACCESS_DENIED';
    end if;
    insert into public.academy_sessions(id,case_id,user_id,stage,scenario_id,mode,metadata)
    values(v_id,v_id,p_user_id,'OPEN',p_record->>'scenario_id',p_record->>'mode',
           jsonb_build_object('training_engine','rules','history_version',0))
    on conflict(id) do nothing;
    select * into v_row from public.academy_sessions where id=v_id for update;
    if v_row.user_id is distinct from p_user_id
       or v_row.metadata->>'training_engine' is distinct from 'rules' then
        raise exception 'RULE_TRAINING_ACCESS_DENIED';
    end if;
    v_version := coalesce((v_row.metadata->>'history_version')::integer,0);
    -- A timed-out request may already have committed. Retrying identical data is safe.
    if v_row.metadata->>'checkpoint_hash'=v_hash then
        return jsonb_build_object('version',v_version,'summary',public.get_hwarang_rule_learning_summary(p_user_id));
    end if;
    if v_version<>p_expected_version then raise exception 'RULE_HISTORY_CONFLICT'; end if;
    if v_row.status<>'in_progress' then raise exception 'RULE_HISTORY_ALREADY_COMPLETED'; end if;
    v_version := v_version+1;
    update public.academy_sessions set
        status=case when v_ended then 'completed' else 'in_progress' end,
        stage=p_record->>'stage', scenario_id=p_record->>'scenario_id', mode=p_record->>'mode',
        engine_version=p_record->>'engine_version', scenario_version='5.5-training-route-ownership',
        transcript=p_record->'transcript', session_state=p_record->'wire',
        session_summary=v_report, last_turn_no=v_turn, resume_allowed=not v_ended,
        end_reason=p_record->>'end_reason', ended_at=case when v_ended then now() else null end,
        metadata=jsonb_build_object('training_engine','rules','history_version',v_version,
                                   'checkpoint_hash',v_hash,'session_length',p_record->>'session_length')
    where id=v_id;
    if v_ended then
        update public.academy_cases set status='completed',completed_at=now() where id=v_id;
        -- Immutable result snapshot; retries cannot create duplicate assessments.
        insert into public.academy_assessments(
            id,user_id,case_id,session_id,evaluator_type,framework_version,
            score_lower,score_upper,status,report_snapshot,metadata)
        values(v_id,p_user_id,v_id,v_id,'rules','v63.3-rules',
               (v_report->>'lower')::numeric,(v_report->>'upper')::numeric,
               v_report->>'status',v_report,jsonb_build_object('training_engine','rules'))
        on conflict(id) do nothing;
    end if;
    return jsonb_build_object('version',v_version,'summary',public.get_hwarang_rule_learning_summary(p_user_id));
end $$;

create or replace function public.get_hwarang_admin_operations_summary(p_actor_user_id uuid)
returns jsonb language plpgsql stable security invoker set search_path = '' as $$
declare
    v_day timestamptz := date_trunc('day',now() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul';
    v_month timestamptz := date_trunc('month',now() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul';
    v_end timestamptz := now(); v_ai jsonb; v_academy jsonb; v_users jsonb; v_models jsonb;
begin
    if not exists(select 1 from public.profiles where id=p_actor_user_id and is_active and role='super_admin') then
        raise exception 'ADMIN_ACCESS_DENIED';
    end if;
    select jsonb_build_object(
        'month_cost',coalesce(sum(calculated_cost_usd),0),
        'today_cost',coalesce(sum(calculated_cost_usd) filter(where created_at>=v_day),0),
        'text_requests',count(*) filter(where ai_role<>'VOICE'),
        'voice_seconds',coalesce(sum(voice_seconds_charged),0)) into v_ai
    from public.hwarang_ai_usage_log where created_at>=v_month and created_at<=v_end;
    v_ai := v_ai || jsonb_build_object('failed_count',
        (select count(*) from public.hwarang_ai_request_registry where created_at>=v_month and created_at<=v_end
         and (status in ('blocked','failed') or block_reason is not null)));
    select coalesce(jsonb_agg(x),'[]'::jsonb) into v_users from (
        select user_id,count(*) as requests,sum(credits_charged) as credits,
               sum(voice_seconds_charged) as voice_seconds,sum(calculated_cost_usd) as cost
        from public.hwarang_ai_usage_log where created_at>=v_month and created_at<=v_end group by user_id
    ) x;
    select coalesce(jsonb_agg(x),'[]'::jsonb) into v_models from (
        select model,count(*) as requests,sum(calculated_cost_usd) as cost
        from public.hwarang_ai_usage_log where created_at>=v_month and created_at<=v_end group by model
    ) x;
    select jsonb_build_object(
        'today_started',count(*) filter(where started_at>=v_day and started_at<=v_end),
        'today_completed',count(*) filter(where status='completed' and ended_at>=v_day and ended_at<=v_end),
        'in_progress',count(*) filter(where status='in_progress'),
        'voice_in_progress',count(*) filter(where status='in_progress' and interaction_mode='VOICE'),
        'today_voice',count(*) filter(where started_at>=v_day and started_at<=v_end and interaction_mode='VOICE')
    ) into v_academy from public.academy_sessions;
    v_academy := v_academy || jsonb_build_object(
        'today_formal',(select count(*) from public.academy_assessments
                       where generated_at>=v_day and generated_at<=v_end and evaluator_type in ('ai','hybrid')),
        'today_rules',(select count(*) from public.academy_assessments
                      where generated_at>=v_day and generated_at<=v_end and evaluator_type='rules'));
    return jsonb_build_object('ai',v_ai,'by_user',v_users,'by_model',v_models,
                             'academy',v_academy,'updated_at',v_end,'timezone','Asia/Seoul');
end $$;

revoke all on function public.get_hwarang_rule_learning_summary(uuid) from public,anon,authenticated;
revoke all on function public.save_hwarang_rule_training(uuid,jsonb,integer) from public,anon,authenticated;
revoke all on function public.get_hwarang_admin_operations_summary(uuid) from public,anon,authenticated;
grant execute on function public.get_hwarang_rule_learning_summary(uuid) to service_role;
grant execute on function public.save_hwarang_rule_training(uuid,jsonb,integer) to service_role;
grant execute on function public.get_hwarang_admin_operations_summary(uuid) to service_role;
notify pgrst,'reload schema';
commit;
