"""Manager-only controls. No AI request is made by rendering this panel."""
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import streamlit as st
from .repository import BriefingRepositoryError
from .runtime import PROFILE_LABELS


def render_operations(repo):
    actor=str((st.session_state.get('login_profile') or {}).get('id') or '')
    day=datetime.now(ZoneInfo('Asia/Seoul')).date()
    _render_policy(repo, actor)
    with st.expander('공유 자료 자동 정리'):
        try:
            retention = repo.retention_status()
            if isinstance(retention, dict) and retention:
                labels = {'success':'정상 완료','failed':'실패 · 다음 예약 실행에서 재시도','running':'실행 중','never':'첫 실행 대기'}
                st.write('상태: '+labels.get(retention.get('status'),'확인 필요'))
                def local_time(value):
                    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M') if value else '아직 없음'
                st.caption('마지막 성공: '+local_time(retention.get('last_success_at')))
                counts = retention.get('counts') or {}
                st.caption('최근 삭제: 공유 링크 '+str(counts.get('deleted_shares',0))+'개 · 공통 이미지 '+str(counts.get('deleted_shared_previews',0))+'개')
            st.caption('매일 03:15 예약 · 신규 링크 7일 열람 / 만료 후 7일 보관 · 기존 링크는 원래 만료일 유지')
        except BriefingRepositoryError:
            st.warning('자동 정리 상태를 불러오지 못했습니다.')
    with st.expander('실행 이력 · 상세 오류 · 비용'):
        try:
            enabled=repo.ai_generation_enabled();st.info('전체 AI: '+('켜짐' if enabled else '꺼짐 · 유료 브리핑 생성 중단'))
            status=repo.operation_status(day)
            if status['runs']:st.dataframe(status['runs'],hide_index=True,use_container_width=True)
            else:st.warning('최근 7일 브리핑 예약 실행 기록이 없습니다. GitHub Actions의 HWARANG Daily Briefing 활성화와 Secrets 설정을 확인해 주세요.')
            if status['jobs']:st.dataframe(status['jobs'],hide_index=True,use_container_width=True)
            costs=repo.cost_status()
            for key,label in [('today','오늘'),('month','이번 달')]:
                c=costs[key];st.markdown('**'+label+' 브리핑 API 사용량**')
                st.write(f"요청 {c['requests']}회 · 검색 {c['search_actions']}회 · 입력 {c['input_tokens']:,} / 출력 {c['output_tokens']:,} 토큰")
                from .costs import cost_summary_label
                st.caption(cost_summary_label(c))
                if c['actual_known_usd']:st.caption(f"확인된 청구 비용 ${c['actual_known_usd']:.4f}")
                purpose = c.get('purpose_requests') or {}
                st.caption('실행 목적 · 운영 '+str(purpose.get('operation',0))+' / 검증 '+str(purpose.get('validation',0))+' / 복구 '+str(purpose.get('recovery',0))+' / 이전 기록 '+str(purpose.get('legacy',0)))
                from .execution_policy import budget_notice
                notice = budget_notice(c, 'day' if key == 'today' else 'month')
                if notice['state'] in {'near','exceeded'}:
                    st.warning('설정한 비용 알림 예산에 가까워졌거나 도달했습니다. 보강 검색·검증 범위를 먼저 점검하세요. '+notice['message'])
                else: st.caption(notice['message'])
            st.caption('브리핑 비용은 학습 AI 크레딧과 별도입니다. 단가표가 없으면 비용을 0원으로 표시하지 않습니다. 최종 청구액은 공급사에서 확인합니다. 뉴스 피드·지표 서비스의 계약 비용은 API 토큰 비용에 포함되지 않습니다.')
            if costs.get('row_limit_reached'):st.warning('이달 조회 한도 1,000건에 도달했습니다. 합계는 조회된 기록 기준입니다.')
        except BriefingRepositoryError as exc:st.warning(str(exc))
    with st.expander('관리자 선정 기록 · AI 호출 없음'):
        for code,label in PROFILE_LABELS.items():
            try:
                bundle=repo.bundle_for_date(code,day,include_draft=True)
                if bundle:
                    qa=bundle['snapshot'].get('qa_payload') or {}
                    st.markdown('**'+label+'**')
                    from collections import Counter
                    reasons=Counter(r.get('hold_reason') or r.get('selection_decision') for r in qa.get('editorial_audit',[]) if r.get('tier')=='excluded')
                    labels={'source_text_missing':'원문 근거 부족','essential_facts_missing':'핵심 조건·수치 누락','source_conflict':'출처 불일치','analysis_missing':'분석 결과 누락','cross_check_required':'추가 확인 필요','capacity':'수량 제한','below_importance_floor':'중요도 미달','quality_hold':'검증 보류'}
                    st.caption('게시 상태 · '+str(bundle['revision'].get('publication_status')))
                    if reasons:st.dataframe([{'제외·보류 사유':labels.get(k,k),'기사 수':n} for k,n in reasons.items()],hide_index=True)
                    st.caption('근거 부족은 원문 보충, 선정 부적합은 후보 교체가 필요합니다. 같은 근거로 분석을 반복하지 않습니다.')
                    st.json({'선정':qa.get('editorial_audit',[]),'수집':qa.get('collection_diagnostics',{}),'제외':qa.get('excluded_counts',{})},expanded=False)
            except BriefingRepositoryError as exc:st.warning(str(exc))
    with st.expander('수집 연결 확인 · AI 호출 없음'):
        if st.button('언론사 피드 연결 확인',key='launch_feed_probe'):
            from .direct_sources import load_direct_source_specs_from_env,probe_direct_sources
            with st.spinner('언론사 연결과 발행일을 확인합니다…'):
                try:st.session_state['launch_feed_probe_result']=probe_direct_sources(load_direct_source_specs_from_env())
                except Exception:
                    st.session_state.pop('launch_feed_probe_result',None)
                    st.error('피드 설정을 확인해 주세요.')
        # Button state is a transient bool; keep the report under a separate key.
        probe=st.session_state.get('launch_feed_probe_result')
        if probe:
            st.caption('이 확인은 현재 시각 기준입니다. 아침 브리핑은 07:30 이전 기사만 사용합니다.')
            st.dataframe([{'피드':code,**value} for code,value in probe['direct_sources'].items()],hide_index=True)
            st.download_button('피드 진단 저장',json.dumps(probe,ensure_ascii=False,indent=2),file_name='briefing_feed_diagnostics.json')
        st.caption('경제·금융은 기사 중심으로 생성합니다. 별도 시장 지표 API나 유료 공급원은 필요하지 않습니다.')
        if st.button('고객 공유 페이지 연결 확인',key='launch_reader_probe'):
            if repo.public_endpoint_ready():st.success('고객 읽기 페이지가 연결됐습니다.')
            else:st.warning('public_reader 고객 읽기 페이지를 먼저 배포해 주세요.')


def _render_policy(repo, actor):
    with st.container(border=True):
        st.subheader('자동 운영')
        st.caption('06:30 사전 수집 · 07:20 최종 후보 확인 · 07:30 마감 · 08:00 영역별 게시 · 08:40 새 탐색 중단 · 08:50 최종 게시 시도')
        try:
            policy=repo.operating_policy()
            st.caption('최초 조직 승인 후 품질 검증을 통과한 다음 판본부터 예약 공개합니다.')
            if (st.session_state.get('login_profile') or {}).get('role')!='super_admin':
                st.caption('최고관리자가 직원 자동 게시와 고객 공유 사용 여부를 설정합니다.');return
            with st.form('launch_policy'):
                scheduled=st.checkbox('매일 자동 생성 · API 요금 발생',value=bool(policy.get('scheduled_generation_enabled')))
                st.caption('켜면 예약 시간에 생성합니다. 생성 결과를 직원 화면에 게시하는 설정은 아래에서 별도로 선택합니다.')
                automatic=st.checkbox('품질 검증을 통과한 영역별 예약 자동 공개',value=bool(policy.get('automatic_publication_enabled')))
                external=st.checkbox('검증된 고객용 본문 공유 허용',value=bool(policy.get('external_sharing_approved')))
                st.caption('고객 공유를 허용하면 검증된 게시 본문에서 공유 버튼을 사용할 수 있습니다. 이 설정은 조직에 한 번 적용하며, 이후 매일 승인할 필요는 없습니다.')
                if st.form_submit_button('운영 정책 저장'):
                    repo.set_operating_policy(actor,automatic=automatic,external=external,scheduled=scheduled);st.success('운영 정책을 저장했습니다.');st.rerun()
        except BriefingRepositoryError as exc:st.warning(str(exc))


def render_correction(repo,bundle):
    content=(bundle['snapshot'].get('content_payload') or {});issues=(content.get('issues') or [])+(content.get('important_updates') or [])
    if bundle['revision'].get('publication_status')!='published' or not issues:return
    with st.expander('공개 문구 정정 · AI 호출 없음'):
        st.caption('정정은 새 판으로 저장됩니다. 원래 출처·지표·수집 기준은 유지하며 기존 공유 링크의 본문과 PDF를 함께 갱신합니다. 카카오톡에 이미 저장된 미리보기 이미지는 즉시 바뀌지 않을 수 있습니다.')
        chosen=st.selectbox('정정할 소식',range(len(issues)),format_func=lambda i:issues[i]['title'],key='correct_select_'+bundle['revision']['id'])
        row=issues[chosen]
        with st.form('correct_'+bundle['revision']['id']+'_'+str(chosen)):
            changes={key:st.text_area(label,value=str(row.get(key) or '')) for key,label in [('title','제목'),('summary','요약'),('why_important','해설'),('impact_summary','영향')]}
            reason=st.text_input('정정 사유')
            if st.form_submit_button('새 정정판 공개'):
                from .corrections import apply_correction
                try:
                    apply_correction(repo,bundle,row['event_key'],changes,reason,str((st.session_state.get('login_profile') or {}).get('id') or ''))
                    from .briefing_center import _clear_read_caches
                    _clear_read_caches();st.success('정정판을 공개했습니다.');st.rerun()
                except (BriefingRepositoryError,ValueError) as exc:st.error(str(exc))




def render_important_update(repo, bundle):
    if bundle['revision'].get('publication_status') != 'published':
        return
    if str(bundle['briefing']['briefing_date']) != datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat():
        return
    with st.expander('중요 공식 발표 추가 · 필요할 때만'):
        st.caption('새 공식 발표를 확인한 관리자가 추가합니다. 정규 기사와 별도로 표시하며, 공유 링크와 최신 PDF에 반영합니다. AI 호출은 없습니다.')
        code=bundle['briefing']['profile_code']
        from .profile_rules import PROFILE_RULES
        with st.form('important_update_'+bundle['revision']['id']):
            title=st.text_input('발표 제목')
            summary=st.text_area('확인한 사실 요약')
            source_name=st.text_input('공식 기관·협회 이름')
            url=st.text_input('공식 원문 주소')
            published_at=st.text_input('실제 발표 시각',placeholder='2026-10-13T10:00:00+09:00')
            category=st.selectbox('발표 분야',PROFILE_RULES[code].categories)
            reason=st.text_input('추가 사유')
            checked=st.checkbox('원문의 사실·시행일과 고객에게 제공할 표현을 확인했습니다.')
            if st.form_submit_button('중요 발표를 새 판으로 게시',disabled=not checked):
                from .corrections import apply_correction
                try:
                    issue=(bundle['snapshot'].get('content_payload') or {})['issues'][0]
                    apply_correction(repo,bundle,issue['event_key'],{},reason,
                        str((st.session_state.get('login_profile') or {}).get('id') or ''),
                        important_update={'title':title,'summary':summary,'source_name':source_name,
                            'url':url,'published_at':published_at,'category':category})
                    from .briefing_center import _clear_read_caches
                    _clear_read_caches();st.success('중요 발표를 추가했습니다. 기존 공유 링크에서 최신 판을 읽을 수 있습니다.');st.rerun()
                except (BriefingRepositoryError,ValueError) as exc:
                    st.error(str(exc))
