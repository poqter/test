# 상담 시뮬레이터 퇴역 범위와 보존 데이터

2026-11-19 KST. 운영 hwarang-platform의 관계·함수 시그니처·트리거와 PR #43 병합본의 호출 코드를 대조했다. 아래 표는 후속 변경의 범위를 정한다. 운영 데이터와 기적용 SQL은 이번 변경에서 보존한다.

## 삭제할 코드와 DB 객체

| 기능 | 코드 | 운영 DB 객체 |
|---|---|---|
| 상담·평가·공유 | `hwarang_academy/studio/`, `history.py`, `review_export.py`, `pre_api/`. 상담 엔진은 같은 패키지의 `engine.py`, `service.py`, `content.py`, `evaluation.py`, `core_scenarios.py`, `dialogue_context.py`, `dialogue_v5.py`, `director_v5.py`, `mission_graph_v5.py`, `scenario_v2.py`, `semantic_v3.py`, `training_policy_v55.py`, `world_v5.py`와 전용 리소스가 대상 | `academy_cases`, `academy_sessions`, `academy_assessments`, `hwarang_studio_records`, `hwarang_studio_requests`, `hwarang_studio_shares`, `hwarang_studio_config`, `hwarang_studio_audit`. 상담 사례·평가 검증 트리거와 전용 함수 포함 |
| Credit·Voice 배정·사용 | `modules/shared/academy_credit_ui.py`, `admin_assets.py`, `ai_guardrails.py`, 이번에 분리한 `simulator_admin_ui.py`의 전용 조작 | `hwarang_ai_credit_accounts`, `hwarang_ai_credit_ledger`, `hwarang_voice_accounts`, `hwarang_voice_ledger`, `hwarang_credit_policy`, `private.hwarang_admin_asset_requests`. 가입 트리거 `on_profile_created_ai_credit_account`, `on_profile_created_voice_account`를 먼저 분리 |
| 상담 요청 예약·비용 | 상담 전용 모델·세션 잠금·예약·정산 호출과 해당 진단 | `hwarang_ai_limit_policies`, `hwarang_ai_model_policy`, `hwarang_ai_request_registry`, `hwarang_ai_session_locks`, `hwarang_ai_usage_log`, `hwarang_admin_ai_usage_daily_view`. 과거 사용·비용·원장의 보존본과 열람 가능성을 확인한 뒤 물리적 정리 |
| 전용 권한 | 일반 계정 편집에서 숨기는 상담 권한 3종 | `hwarang_permissions`와 `hwarang_user_permissions` 중 `academy.simulator`, `academy.voice_simulator`, `academy.formal_ai_assessment`에 해당하는 행만 대상. 공통 테이블을 보존 |

관계 이름의 기본 스키마는 public이다. 해당 테이블에 소속된 정책·인덱스·제약·트리거도 퇴역 전 종속성 대조 대상이다. 보관 범위가 확정되지 않은 상담 이력·자산 원장·비용·감사 행은 물리 삭제를 보류한다.

## 반드시 보존할 코드와 데이터

| 유지 업무 | 코드·DB | 보존 내용 |
|---|---|---|
| CBT | `hwarang_academy/exams/`, WORKSPACE CBT 진입, `hwarang_exam_bank`, `hwarang_exam_attempts`, `public.hwarang_exam`, `private.exam_*` | 문제·정답·출제 스냅샷, 진행·중단·완료 응시, 답안·채점·오답 복습·조직 학습 현황 |
| 신입교육·자료실 | `hwarang_academy/education/`, `academy_learning_profiles`, `hwarang_learning_content`, `hwarang_learning_progress`, `hwarang_learning_work`, `hwarang_learning_work_events`, 아래 교육 RPC | 과정·교안·실습, 진도, 임시 저장·제출·보완·재제출·승인, 검토자 피드백과 변경 이력 |
| 가입·세션·조직·권한 | `profiles`, `profiles_admin_view`, `organization_units`, `positions`, `hwarang_app_access`, `hwarang_user_sessions`, `hwarang_app_launch_tickets`, 권한·조직 범위 함수, 공통 감사·활동 테이블 | 신규 프로필 생성 시 `on_profile_created_app_access`와 `on_profile_created_learning_profile`을 유지. 앱 접근 및 관리자/직원 조회 범위 보존 |
| 브리핑·카카오·영업활동 | 브리핑 예산·사용량·공개 기록, 카카오 연결·예약·전송, 일정·활동 원본과 공통 감사 | 공개 링크·발송·예약 등 유지 업무의 DB와 기존 운영 이력 보존 |

## 먼저 분리해야 하는 공통 참조

- 운영 `public.hwarang_reserve_briefing_request`와 `modules/briefing/repository.py`는 모두 `hwarang_ai_runtime_config.service_enabled`를 읽는다. 브리핑 사용 스위치·관리 경로를 먼저 이관하고 정상·정지 양쪽을 검증할 때까지 테이블과 관리 기능을 유지한다.
- `hwarang_admin_user_operations_view`와 `get_hwarang_admin_operations_summary`에는 공통 사용자와 상담 집계가 섞여 있다. 일반 관리자센터는 `profiles_admin_view`를 사용한다. 잔여 소비자를 확인한 뒤 상담용 뷰·집계만 퇴역한다.
- `academy_app.py`와 `hwarang_academy/shell.py`는 교육·CBT 진입점이다. 상담 분기와 전용 프론트엔드·리소스만 정리한다. 신입교육의 고객 미션과 CBT 자체 프론트엔드를 포함한 패키지 전체 삭제는 범위 밖이다.
- 동일 테이블의 공통 감사와 과거 권한 변경 기록을 유지한다. 적용이 끝난 migration 파일도 보존한다. 후속 migration은 명시한 객체별로 리허설하고, 가입·권한 저장·CBT·교육 피드백·브리핑을 함께 확인한다.

## 운영에서 확인한 함수 시그니처

관련 이름 및 테이블을 참조하는 함수 본문을 검색했다. 오버로드를 개별 표기했다. 이 목록은 실행용 삭제 SQL이 아니다.

### 삭제 예정 · 상담 이력·자산

- `private.claim_hwarang_ai_session(p_user_id uuid, p_academy_session_id uuid, p_ttl_seconds integer)`
- `private.ensure_hwarang_ai_credit_account()`
- `private.ensure_hwarang_monthly_credit(p_user_id uuid)`
- `private.ensure_hwarang_voice_account()`
- `private.hwarang_credit_period()`
- `private.prune_hwarang_ai_reservations()`
- `private.register_hwarang_ai_block(p_user_id uuid, p_academy_session_id uuid, p_turn_no integer, p_purpose text, p_interaction_mode text, p_billing_bucket text, p_idempotency_key text, p_reason text, p_feature_code text)`
- `private.sync_hwarang_credit_aggregate(p_user_id uuid)`
- `private.validate_academy_assessment_links()`
- `public.acquire_hwarang_ai_session(p_user_id uuid, p_academy_session_id uuid)`
- `public.admin_adjust_hwarang_ai_credits(p_actor_user_id uuid, p_target_user_id uuid, p_operation text, p_amount bigint, p_note text)`
- `public.admin_adjust_hwarang_purchased_credits(p_actor_user_id uuid, p_target_user_id uuid, p_operation text, p_amount bigint, p_source_type text, p_note text)`
- `public.admin_adjust_hwarang_voice_minutes(p_actor_user_id uuid, p_target_user_id uuid, p_operation text, p_minutes bigint, p_note text)`
- `public.admin_adjust_hwarang_voice_minutes(p_actor_user_id uuid, p_target_user_id uuid, p_operation text, p_minutes bigint, p_source_type text, p_note text)`
- `public.admin_apply_hwarang_asset_request(p_actor_user_id uuid, p_request_id uuid, p_asset text, p_target_user_ids uuid[], p_operation text, p_amount bigint, p_source_type text, p_note text)`
- `public.admin_bulk_adjust_hwarang_purchased_credits(p_actor_user_id uuid, p_target_user_ids uuid[], p_operation text, p_amount bigint, p_source_type text, p_note text)`
- `public.admin_bulk_adjust_hwarang_voice_minutes(p_actor_user_id uuid, p_target_user_ids uuid[], p_operation text, p_minutes bigint, p_source_type text, p_note text)`
- `public.admin_bulk_grant_hwarang_purchased_credits(p_actor_user_id uuid, p_target_user_ids uuid[], p_amount bigint, p_source_type text, p_note text)`
- `public.admin_get_hwarang_asset_request(p_actor_user_id uuid, p_request_id uuid)`
- `public.admin_update_hwarang_ai_model_policy(p_actor_user_id uuid, p_role_code text, p_provider_model text, p_max_output_tokens integer)`
- `public.admin_update_hwarang_credit_policy(p_actor_user_id uuid, p_monthly_free_credits bigint, p_remaining_warning_percent integer, p_default_voice_minutes integer, p_monthly_ai_budget_usd numeric, p_budget_warning_percent integer)`
- `public.finalize_hwarang_ai_request(p_request_id uuid, p_result_status text, p_actual_credits bigint)`
- `public.finalize_hwarang_voice_request(p_request_id uuid, p_result_status text, p_actual_seconds bigint)`
- `public.get_hwarang_ai_entitlement_status(p_user_id uuid)`
- `public.get_hwarang_rule_learning_summary(p_user_id uuid)`
- `public.get_hwarang_training_credit_status(p_user_id uuid)`
- `public.heartbeat_hwarang_ai_session(p_user_id uuid, p_academy_session_id uuid)`
- `public.release_hwarang_ai_session(p_user_id uuid, p_academy_session_id uuid)`
- `public.reserve_hwarang_ai_request(p_user_id uuid, p_academy_session_id uuid, p_turn_no integer, p_purpose text, p_interaction_mode text, p_idempotency_key text, p_estimated_credits bigint)`
- `public.reserve_hwarang_voice_request(p_user_id uuid, p_academy_session_id uuid, p_turn_no integer, p_idempotency_key text, p_requested_seconds bigint)`
- `public.start_hwarang_ai_request(p_request_id uuid, p_extend_seconds integer)`
- `public.save_hwarang_rule_training(p_user_id uuid, p_record jsonb, p_expected_version integer)`

### 유지 · 교육·시험

- `private.ensure_academy_learning_profile()`
- `private.exam_check(p_actor uuid)`
- `private.exam_fingerprint(q jsonb)`
- `private.exam_finish(p_id uuid)`
- `private.exam_grade(p_snapshot jsonb, p_answers jsonb)`
- `private.exam_normalize(v jsonb)`
- `private.exam_random_snapshot(actor uuid, family_code text, track_code text)`
- `private.exam_view(p_id uuid)`
- `private.fp_learning_audit()`
- `private.learning_check(p_actor uuid)`
- `public.hwarang_exam(p_actor uuid, p_action text, p_payload jsonb)`
- `public.hwarang_learning_catalog(p_actor uuid)`
- `public.hwarang_learning_complete(p_actor uuid, p_id text, p_revision integer, p_lesson text)`
- `public.hwarang_learning_interactive_save(p_actor uuid, p_id text, p_revision integer, p_lesson text, p_version integer, p_answers jsonb, p_submit boolean)`
- `public.hwarang_learning_publish(p_actor uuid, p_data jsonb)`
- `public.hwarang_learning_team(p_actor uuid, p_id text)`
- `public.hwarang_learning_work_get(p_actor uuid, p_id text, p_target uuid)`
- `public.hwarang_learning_work_review(p_actor uuid, p_target uuid, p_id text, p_revision integer, p_lesson text, p_version integer, p_approve boolean, p_feedback jsonb)`
- `public.hwarang_learning_work_save(p_actor uuid, p_id text, p_revision integer, p_lesson text, p_version integer, p_answers jsonb, p_practice text, p_submit boolean)`

### 삭제 예정 · 상담 Studio

- `private.studio_can_view(p_actor uuid, p_target_user_id uuid)`
- `private.studio_check(p_actor uuid)`
- `public.hwarang_studio_claim(p_actor uuid, p_id uuid, p_version integer, p_op text, p_purpose text)`
- `public.hwarang_studio_configure(p_actor uuid, p_settings jsonb)`
- `public.hwarang_studio_get(p_actor uuid, p_id uuid)`
- `public.hwarang_studio_list(p_actor uuid)`
- `public.hwarang_studio_manager(p_actor uuid, p_id uuid)`
- `public.hwarang_studio_my_pending(p_actor uuid)`
- `public.hwarang_studio_operations(p_actor uuid)`
- `public.hwarang_studio_pending(p_actor uuid)`
- `public.hwarang_studio_recipients(p_actor uuid)`
- `public.hwarang_studio_release_unknown(p_actor uuid, p_op text, p_note text)`
- `public.hwarang_studio_report_incidents(p_actor uuid)`
- `public.hwarang_studio_request_update(p_actor uuid, p_op text, p_status text, p_request uuid, p_result jsonb)`
- `public.hwarang_studio_resolve(p_actor uuid, p_op text, p_delivered boolean, p_note text)`
- `public.hwarang_studio_review(p_actor uuid, p_id uuid, p_note text, p_response boolean)`
- `public.hwarang_studio_reviews(p_actor uuid, p_id uuid)`
- `public.hwarang_studio_settings(p_actor uuid)`
- `public.hwarang_studio_settle_report(p_actor uuid, p_data jsonb, p_op text, p_failure_reason text)`
- `public.hwarang_studio_share(p_actor uuid, p_id uuid, p_recipient uuid, p_fields text[], p_active boolean)`
- `public.hwarang_studio_store(p_actor uuid, p_data jsonb, p_version integer, p_op text)`

### 공통 설정·혼합 집계 검토

- `public.admin_update_hwarang_ai_runtime(p_actor_user_id uuid, p_service_enabled boolean, p_text_enabled boolean, p_voice_enabled boolean, p_assessment_enabled boolean, p_soft_limit_percent integer, p_contact_label text, p_contact_url text)`
- `public.get_hwarang_admin_operations_summary(p_actor_user_id uuid)`
- `public.hwarang_reserve_briefing_request(p_date date, p_kind text)`
