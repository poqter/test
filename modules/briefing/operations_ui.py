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
    with st.expander('운영 상태 · 예약 실행 · 비용'):
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
                st.caption(f"확인된 추정 비용 ${c['estimated_known_usd']:.4f} · 비용 미확인 요청 {c['unknown_cost_requests']}회 · 응답 미확인 {c['charge_uncertain_requests']}회")
                if c['actual_known_usd']:st.caption(f"확인된 청구 비용 ${c['actual_known_usd']:.4f}")
            st.caption('브리핑 비용은 학습 AI 크레딧과 별도입니다. 단가표가 없으면 비용을 0원으로 표시하지 않습니다. 최종 청구액은 공급사에서 확인합니다. 뉴스 피드·지표 서비스의 계약 비용은 API 토큰 비용에 포함되지 않습니다.')
            if costs.get('row_limit_reached'):st.warning('이달 조회 한도 1,000건에 도달했습니다. 합계는 조회된 기록 기준입니다.')
        except BriefingRepositoryError as exc:st.warning(str(exc))
    with st.expander('수집 연결 확인 · AI 호출 없음'):
        if st.button('언론사 피드 연결 확인',key='launch_feed_probe'):
            from .direct_sources import load_direct_source_specs_from_env,probe_direct_sources
            with st.spinner('언론사 연결과 발행일을 확인합니다…'):
                try:st.session_state['launch_feed_probe']=probe_direct_sources(load_direct_source_specs_from_env())
                except Exception:st.error('피드 설정을 확인해 주세요.')
        probe=st.session_state.get('launch_feed_probe')
        if probe:
            st.caption('이 확인은 현재 시각 기준입니다. 아침 브리핑은 07:00/07:30 이전 기사만 사용합니다.')
            st.dataframe([{'피드':code,**value} for code,value in probe['direct_sources'].items()],hide_index=True)
            st.download_button('피드 진단 저장',json.dumps(probe,ensure_ascii=False,indent=2),file_name='briefing_feed_diagnostics.json')
        st.caption('지표는 공급사 API 키·이용 계약을 연결해야 합니다. 생성 시 먼저 6개 지표를 확인하고, 누락되면 OpenAI 호출 전에 중단합니다.')
        if st.button('고객 공유 페이지 연결 확인',key='launch_reader_probe'):
            if repo.public_endpoint_ready():st.success('고객 읽기 페이지가 연결됐습니다.')
            else:st.warning('public_reader 고객 읽기 페이지를 먼저 배포해 주세요.')
    with st.expander('최초 운영 승인 · 영역별 관찰 일수'):
        try:
            policy=repo.operating_policy()
            for code in ('MARKET','NEWS','INSURANCE'):
                st.caption(PROFILE_LABELS[code]+f' · 검증된 영업일 {repo.verified_business_days(code)}일 / 자동 공개 기준 3일')
            if (st.session_state.get('login_profile') or {}).get('role')!='super_admin':
                st.caption('최고관리자가 자동 공개와 고객 공유 정책을 최초 설정합니다.');return
            with st.form('launch_policy'):
                scheduled=st.checkbox('매일 자동 생성 · API 요금 발생',value=bool(policy.get('scheduled_generation_enabled')))
                st.caption('1회 생성 검수 중에는 자동 생성을 꺼 둡니다. 저장된 자료 조회·공유에는 영향을 주지 않습니다.')
                automatic=st.checkbox('관찰 3영업일 이후 영역별 자동 공개',value=bool(policy.get('automatic_publication_enabled')))
                external=st.checkbox('검증된 고객용 본문 공유 허용',value=bool(policy.get('external_sharing_approved')))
                st.caption('뉴스·지표의 고객 표시 이용 조건을 확인한 뒤 공유를 켜 주세요. 지표 공급원의 고객 표시 허용 설정도 별도로 확인합니다. 이후 매일 승인할 필요는 없습니다.')
                if st.form_submit_button('운영 정책 저장'):
                    repo.set_operating_policy(actor,automatic=automatic,external=external,scheduled=scheduled);st.success('운영 정책을 저장했습니다.');st.rerun()
        except BriefingRepositoryError as exc:st.warning(str(exc))


def render_correction(repo,bundle):
    content=(bundle['snapshot'].get('content_payload') or {});issues=content.get('issues') or []
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
