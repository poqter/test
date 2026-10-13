from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import html
import json
from typing import Callable
import streamlit as st
from .repository import BriefingRepository, BriefingRepositoryError
from .runtime import PROFILE_LABELS, body_quality_ready
from .public_body import customer_body, staff_body, public_html, public_pdf
from .display import render_body, stamp
from .diagnostics import build_info, failure_diagnostic
from .scheduler import generate_group
from .experience import publication_blockers, sharing_blockers, selection_summary

PROFILE_ORDER = ('MARKET', 'NEWS', 'INSURANCE')
KST = ZoneInfo('Asia/Seoul')
PAGES = ('오늘 브리핑', '지난 브리핑', '고객에게 공유', '운영 관리')


def _can_manage():
    profile = st.session_state.get('login_profile') or {}
    return profile.get('role') == 'super_admin' or 'workspace.briefing_manage' in set(st.session_state.get('hw_feature_permissions') or ())


@st.cache_resource(show_spinner=False)
def _repo():
    from modules.shared.hwarang_auth import SupabaseConfig
    cfg = SupabaseConfig.from_mapping(st.secrets)
    return BriefingRepository(cfg.url, cfg.secret_key)


@st.cache_data(ttl=30, show_spinner=False)
def _published_summaries_cached():
    return _repo().latest_summaries(PROFILE_ORDER, include_draft=False)


@st.cache_data(ttl=30, show_spinner=False)
def _published_history_cached(code):
    return _repo().history(code, limit=30, include_draft=False)


@st.cache_data(ttl=30, show_spinner=False)
def _customer_date_cached():
    return _repo().latest_complete_customer_date()


def _latest_summaries(include_draft):
    return _repo().latest_summaries(PROFILE_ORDER, include_draft=True) if include_draft else _published_summaries_cached()


def _clear_read_caches():
    _published_summaries_cached.clear()
    _published_history_cached.clear()
    _customer_date_cached.clear()


def _counts(item):
    fast = ((item or {}).get('snapshot') or {}).get('fast_brief_payload') or {}
    return int(fast.get('core_count') or 0), int(fast.get('light_count') or 0)


def _navigate(page):
    st.session_state['hw_briefing_page'] = page


def _open_share(day):
    st.session_state['hw_briefing_share_day'] = str(day)
    _navigate('고객에게 공유')


def _actor():
    return str((st.session_state.get('login_profile') or {}).get('id') or '')


def render_home_summary(navigate: Callable):
    try:
        items = _published_summaries_cached()
    except Exception:
        return
    if not any(items.values()):
        return
    st.markdown('### 오늘의 브리핑')
    for code in PROFILE_ORDER:
        item = items.get(code)
        if item:
            a, b = _counts(item)
            st.write(f"{PROFILE_LABELS[code]} · {item['briefing']['briefing_date']} · 소식 {a+b}개")
    if st.button('브리핑 센터 열기', key='hw_home_briefing_open'):
        navigate('briefing')


def _body(snapshot):
    content = snapshot.get('content_payload') or {}
    if content.get('issues'):
        return staff_body(content)
    body = snapshot.get('external_content_payload') or {}
    return body if body.get('schema') == 'hwarang-public-v2' else customer_body(content)


def _combined_sharing(repo, selected_day=None, *, use_cache=False):
    profile = st.session_state.get('login_profile') or {}
    uid = str(profile.get('id') or '')
    day = str(selected_day) if selected_day else (_customer_date_cached() if use_cache else repo.latest_complete_customer_date())
    if not day:
        st.info('같은 날짜의 정상 게시본이 준비되면 고객 공유를 사용할 수 있습니다.')
        st.button('통합 공유 링크 만들기', disabled=True, key='combined_not_ready')
        return
    if day != datetime.now(KST).date().isoformat():
        st.info(f'선택한 공유 자료는 {day}입니다. 오늘 자료와 섞지 않습니다.')
    policy = repo.operating_policy()
    try: reader_configured = bool(repo.public_base_url())
    except BriefingRepositoryError: reader_configured = False
    available = []; bundles = {}; reasons_by_code = {}
    for code in PROFILE_ORDER:
        bundle = repo.bundle_for_date(code, day)
        if bundle:
            reasons = sharing_blockers(bundle, policy, profile, reader_configured=reader_configured)
            if not reasons: available.append(code); bundles[code] = bundle
            else: reasons_by_code[code] = reasons[0]
        else: reasons_by_code[code] = '이 날짜에 공유 가능한 게시본이 없습니다.'
    approved = bool(policy.get('external_sharing_approved'))
    left, right = st.columns([1,1], gap='large')
    with left:
        with st.container(border=True):
            st.subheader('공유할 내용 선택')
            st.caption(day+' · 같은 날짜의 고객용 본문')
            codes = []
            for code in PROFILE_ORDER:
                label = '보험 생활정보' if code == 'INSURANCE' else PROFILE_LABELS[code]
                chosen = st.checkbox(label, value=code in available, disabled=code not in available,
                                     key='share_section_'+uid+'_'+day+'_'+code)
                if chosen and code in available: codes.append(code)
                if code not in available: st.caption(reasons_by_code.get(code,'고객 적격 기사 없음'))
            st.caption('보험업계의 내부 정보와 상담 문구는 고객 본문에 포함되지 않습니다.')
            if not approved: st.info('최고관리자가 운영 관리에서 고객 공유를 허용하면 사용할 수 있습니다.')
            preview = st.toggle('고객 화면 미리보기', key='share_preview_'+uid+'_'+day, disabled=not codes)
    key = 'combined_share_'+day+'_'+uid+'_'+'_'.join(codes)
    with right:
        with st.container(border=True):
            st.subheader('보낼 문구와 링크')
            if st.button('통합 공유 링크 만들기', disabled=not codes or not approved, type='primary',
                         key=key+'_make', use_container_width=True):
                try:
                    token, packet = repo.create_combined_share(day, codes, uid)
                    st.session_state[key] = {'token':token, 'packet':packet}
                except BriefingRepositoryError as exc: st.error(str(exc))
            shared = st.session_state.get(key)
            if shared and codes and approved and all(code in available for code in codes):
                from .sharing import share_url
                url = share_url(repo.public_base_url(), shared['token'])
                packet = shared['packet']; sender = packet['sender']
                st.caption('아래 문구의 복사 버튼으로 링크까지 복사한 뒤 카카오톡·문자에 붙여넣으세요.')
                st.code(f"{sender['name']} {sender['position']}의 통합 브리핑\n{day} · 소식 {len(packet['body']['issues'])}개\n{url}", language=None)
                a,b = st.columns(2)
                a.link_button('고객 화면 열기', url, use_container_width=True)
                try:
                    pdf = public_pdf(packet)
                except Exception:
                    st.warning('PDF 생성이 지연됐습니다. 공유 링크는 사용할 수 있습니다.')
                else:
                    b.download_button('고객 PDF 저장', pdf, mime='application/pdf',
                        file_name=f'hwarang_briefing_{day}.pdf', key=key+'_pdf', use_container_width=True)
                if st.button('이 공유 링크 취소', key=key+'_revoke'):
                    try:
                        repo.revoke_share(shared['token'],uid)
                        st.session_state.pop(key,None);st.rerun()
                    except BriefingRepositoryError as exc: st.error(str(exc))
            else:
                st.info('영역을 선택하고 링크를 만들면 발신자 이름·직책이 포함된 문구가 표시됩니다.')
    if preview and codes:
        from .sharing import combine_bodies
        with st.container(border=True):
            st.subheader('고객에게 보이는 본문')
            try:
                sender = repo.staff_sender(uid)
                st.caption(day+' · '+sender['name']+' '+sender['position'])
                render_body(combine_bodies([bundles[code] for code in codes]))
            except BriefingRepositoryError as exc: st.warning(str(exc))


def _internal_actions(bundle):
    useful = [r for r in bundle.get('actions') or [] if any((r.get('conversation_payload') or {}).values()) or r.get('workspace_actions')]
    if not useful:
        return
    with st.expander('상담에 활용할 내용 · 직원용'):
        for row in useful:
            st.markdown('**'+str(row.get('title') or '')+'**')
            for k, label in [('recommended_expression','상담 표현'), ('check_first','먼저 확인'), ('avoid_expression','주의할 표현')]:
                if (row.get('conversation_payload') or {}).get(k):
                    st.write(label+' · '+str(row['conversation_payload'][k]))
            if row.get('audience_segments'):
                st.caption('관련 대상 · '+' / '.join(row['audience_segments']))
            state=row.get('communication_state')
            expression=str((row.get('conversation_payload') or {}).get('recommended_expression') or '').strip()
            key=str(bundle.get('snapshot',{}).get('id') or '')+'_'+str(row.get('id') or row.get('action_key') or row.get('title'))
            confirmed=False
            if state=='consultation_reference' and expression:
                confirmed=st.checkbox('이 기사에서 먼저 확인할 조건을 확인했습니다.',key='consult_checked_'+key)
            if expression and (state=='customer_ready' or state=='consultation_reference' and confirmed):
                st.caption('고객 설명 복사 · 아래 복사 버튼을 사용하세요.')
                st.code(expression,language=None)
            elif expression:
                st.caption('내부 준비용 · 상담 조건 확인 또는 고객 표현 검증 전에는 고객용 복사를 제공하지 않습니다.')
            from modules.shell.app_registry import APP_BY_ID
            from modules.shell.navigation import allowed_ids, navigate
            permitted=set(allowed_ids(st.session_state.get('login_user')))
            for action in (row.get('workspace_actions') or [])[:2]:
                tool=action.get('tool_code') if isinstance(action,dict) else None
                spec=APP_BY_ID.get(tool)
                if spec and tool in permitted and not spec.external_app_key:
                    st.button(spec.label+' 열기',key='consult_tool_'+key+'_'+tool,on_click=navigate,args=(tool,))


def _publish_actions(repo, bundle):
    if not _can_manage():
        return
    revision = bundle['revision']
    reasons = publication_blockers(bundle)
    if revision.get('publication_status') != 'published':
        if st.button('이 브리핑 게시하기', key='publish_'+revision['id'], type='primary', disabled=bool(reasons), use_container_width=True):
            try:
                repo.publish_revision(bundle['briefing']['id'], revision['id'], actor_user_id=_actor())
                _clear_read_caches()
                st.session_state['hw_briefing_flash'] = '브리핑을 게시했습니다. 직원 화면에서 읽을 수 있습니다.'
                st.rerun()
            except BriefingRepositoryError as exc:
                st.error(str(exc))
        if reasons:
            st.caption(reasons[0])
    else:
        st.caption('직원 화면에 게시된 브리핑입니다.')


def _render_profile_detail(repo, code, bundle, can_manage):
    revision, briefing, snapshot = bundle['revision'], bundle['briefing'], bundle['snapshot']
    content = snapshot.get('content_payload') or {}
    day = str(briefing.get('briefing_date') or '')
    published = revision.get('publication_status') == 'published'
    status = '게시됨' if published else '게시 전 초안'
    st.markdown(f'<div class="hw-edition"><span class="hw-edition-state">{html.escape(status)}</span><strong>{html.escape(PROFILE_LABELS[code])}</strong><span>{html.escape(day)} · 수집 마감 {html.escape(stamp(content.get("as_of")))}</span></div>', unsafe_allow_html=True)
    if day != datetime.now(KST).date().isoformat():
        st.info(f'오늘 브리핑은 아직 준비되지 않았습니다. 최근 정상본({day})을 보여드립니다.')
    body = _body(snapshot)
    c1, c2 = st.columns([2, 1])
    with c1:
        st.caption(f"요약 기사 {len(body.get('issues') or [])}개 · 저장된 본문을 읽습니다.")
    with c2:
        large = st.toggle('큰 글자로 읽기', key='large_'+revision['id'])
    if can_manage:
        _publish_actions(repo, bundle)
    render_body(body, large=large)
    if can_manage:
        with st.expander('고객에게 보이는 본문 미리보기'):
            preview = customer_body(content)
            st.caption(f"고객용 기사 {len(preview['issues'])}개 · 현재 화면은 직원 미리보기이며 외부 공개가 아닙니다.")
            render_body(preview, large=large)
    from .staff_exports import team_summary, staff_pdf
    tools, export, share = st.columns([2, 2, 2])
    with tools:
        with st.popover('팀 1분 요약', use_container_width=True):
            st.caption('직원 내부용 · 저장된 판본')
            st.code(team_summary(bundle), language=None)
    with export:
        with st.popover('직원 PDF', use_container_width=True):
            st.caption('상담 준비를 포함한 내부용 자료입니다.')
            if st.button('PDF 준비', key='staff_prepare_'+revision['id']):
                try:
                    sender = repo.staff_sender(_actor())
                    st.session_state['staff_pdf_'+revision['id']+'_'+str(_actor())] = staff_pdf(bundle, sender)
                except Exception:
                    st.error('직원 PDF를 만들지 못했습니다. 본문은 계속 읽을 수 있습니다.')
            if st.session_state.get('staff_pdf_'+revision['id']+'_'+str(_actor())):
                st.download_button('직원 내부용 PDF 저장', st.session_state['staff_pdf_'+revision['id']+'_'+str(_actor())],
                    file_name=f'hwarang_{code}_{day}_staff.pdf', mime='application/pdf', key='staff_download_'+revision['id'])
    with share:
        st.button('고객에게 공유', key='share_from_'+revision['id'], type='primary',
                  on_click=_open_share, args=(day,), use_container_width=True)
    _internal_actions(bundle)
    if can_manage:
        from .operations_ui import render_correction, render_important_update
        render_correction(repo, bundle)
        render_important_update(repo, bundle)
        with st.expander('기사 수와 저장 상태 확인'):
            st.write(' · '.join(f'{label} {value}개' for label, value in selection_summary(snapshot).items()))
            qa = snapshot.get('qa_payload') or {}
            counts = qa.get('selection_diagnostics') or {}
            if counts.get('analysis_missing'):
                st.caption(f"모델 응답에서 빠진 사건 {counts['analysis_missing']}개는 요약 기사에 넣지 않았습니다.")
            st.caption('기사 수는 실제 날짜·출처·내용이 확인된 사건 기준입니다. 같은 사건의 여러 출처를 별도 기사로 세지 않습니다.')
            st.download_button('상세 진단 저장', json.dumps({'build':build_info(),'qa':qa}, ensure_ascii=False, indent=2), file_name='hwarang_briefing_diagnostics.json', key='diag_'+snapshot['id'])
        if published:
            with st.expander('게시 관리'):
                if st.button('공개 중단·공유 링크 차단', key='hide_'+revision['id']):
                    repo.hide_revision(briefing['id'], revision['id'], _actor())
                    _clear_read_caches()
                    st.rerun()


def _render_generate_panel(repo):
    if not _can_manage():
        return
    st.subheader('브리핑 생성')
    st.caption('이미 완료한 작업은 재사용합니다. 새 수집·분석에는 기존 API 요금이 발생할 수 있습니다.')
    group = st.selectbox('생성할 영역', ['DAILY','MARKET'], format_func=lambda x:'종합뉴스·보험업계' if x=='DAILY' else '경제·금융')
    from .preflight import run_runtime_preflight, preflight_ready
    checks = run_runtime_preflight(require_direct_sources=False)
    for check in checks:
        if check.required and not check.ok:
            st.error(check.message)
    day = datetime.now(KST).date()
    from .scheduler import cutoff
    from .execution_policy import request_plan
    plan = request_plan(group)
    st.caption(f"최초 실행 계획: 검색 요청 최대 {plan['web_requests_max']}회 · 분석 최대 {plan['analysis_requests_max']}회. 저장 결과는 재사용합니다.")
    st.caption(f"최초 요청의 출력 토큰 설정 합계 상한 {plan['output_tokens_max']:,} · 총 청구액 상한을 의미하지 않습니다.")
    st.caption(plan['note'])
    run = repo.daily_run_status(day, group)
    retry = run.get('status') == 'failed'
    retry_exhausted = retry and int(run.get('attempts') or 0) >= 2
    blocked = run.get('status') == 'blocked'
    completed = run.get('status') == 'completed'
    before_cutoff = datetime.now(KST) < cutoff(day, group)
    disabled = before_cutoff or not preflight_ready(checks) or not repo.ai_generation_enabled()
    st.caption('수집 마감 · '+('07:00' if group=='MARKET' else '07:30')+' KST. 이후 발행된 뉴스는 다음 아침 브리핑에 포함됩니다.')
    if not repo.ai_generation_enabled():
        st.warning('전체 AI가 꺼져 있습니다. 관리자센터에서 전체 AI 서비스를 켜면 생성할 수 있습니다.')
    if before_cutoff:
        st.info('오늘 수집 마감 시각 이후에 생성할 수 있습니다.')
    if retry:
        st.caption('중단 전에 저장된 수집·분석 응답부터 이어서 사용합니다.')
    if retry_exhausted:
        st.warning('오늘 복구 1회를 사용했습니다. 저장된 자료를 읽거나 다음 예약 실행을 기다려 주세요.')
    if blocked:
        st.warning('이전 유료 요청의 응답이 확인되지 않아 추가 호출이 잠겨 있습니다.')
    if completed:
        st.success('오늘 이 영역의 생성은 완료됐습니다. 아래 저장된 브리핑에서 게시와 공유를 진행하세요.')
    label = '중단된 브리핑 이어서 생성' if retry else '오늘 브리핑 생성'
    if st.button(label, disabled=disabled or retry_exhausted or blocked or completed, key='hw_briefing_generate_today', type='primary', use_container_width=True):
        with st.spinner('기사를 수집하고 저장하고 있습니다…'):
            try:
                kwargs = {'retry':retry, 'actor':_actor() or None}
                result = generate_group(repo, day, group, **kwargs)
                st.session_state.pop('hw_briefing_last_diagnostic', None)
                messages = {'completed':'브리핑을 저장했습니다. 아래에서 본문을 읽고 게시할 수 있습니다.', 'skipped':'이미 처리된 작업입니다. 저장된 브리핑을 이용해 주세요.', 'configuration_required':'연결 설정을 확인해 주세요.', 'blocked':'이전 요청의 상태 확인이 필요합니다.'}
                st.session_state['hw_briefing_flash'] = messages.get(result.get('status'), '처리 상태를 확인해 주세요.')
                _clear_read_caches()
                st.rerun()
            except Exception as exc:
                st.session_state['hw_briefing_last_diagnostic'] = failure_diagnostic(exc)
                st.error('생성을 마치지 못했습니다. 저장된 결과와 실패 이유를 아래에서 확인할 수 있습니다.')
    if st.session_state.get('hw_briefing_last_diagnostic'):
        advice=(st.session_state['hw_briefing_last_diagnostic'].get('recovery_guidance') or {}).get('action')
        if advice: st.info(advice)
        st.download_button('실패 내용 저장', json.dumps(st.session_state['hw_briefing_last_diagnostic'], ensure_ascii=False, indent=2), file_name='briefing_failure.json')
    with st.expander('상세 연결 상태'):
        st.dataframe([{'항목':c.code,'상태':'준비됨' if c.ok else '설정 필요','필수':c.required,'안내':c.message} for c in checks], hide_index=True, use_container_width=True)
        st.download_button('배포 진단 저장', json.dumps({'build':build_info(),'settings':[c.to_dict() for c in checks]}, ensure_ascii=False, indent=2), file_name='briefing_deployment.json')


def _render_today(repo, can_manage):
    summaries = _latest_summaries(False)
    selected = st.radio('브리핑 영역', PROFILE_ORDER, format_func=lambda x:PROFILE_LABELS[x], horizontal=True, key='hw_briefing_profile')
    item = summaries.get(selected)
    if not item:
        st.info('아직 '+PROFILE_LABELS[selected]+' 브리핑이 '+('저장되지 않았습니다.' if can_manage else '게시되지 않았습니다.'))
        if can_manage:
            st.button('브리핑 생성하러 가기', on_click=_navigate, args=('운영 관리',), key='empty_generate')
        return
    snapshot = repo._snapshot_for_revision(str(item['revision']['id']))
    if not snapshot:
        st.warning('저장된 본문을 불러오지 못했습니다.')
        return
    _render_profile_detail(repo, selected, repo.bundle_from_parts(item['briefing'], item['revision'], snapshot), False)


def _render_history(repo, can_manage):
    code = st.radio('브리핑 영역', PROFILE_ORDER, format_func=lambda x:PROFILE_LABELS[x], horizontal=True, key='history_profile')
    now = datetime.now(KST).date()
    day = st.date_input('읽을 날짜', value=now, min_value=now-timedelta(days=29), max_value=now)
    bundle = repo.bundle_for_date(code, day, include_draft=False)
    if bundle:
        _render_profile_detail(repo, code, bundle, False)
    else:
        st.info('선택한 날짜에 저장된 브리핑이 없습니다.' if can_manage else '선택한 날짜에 게시된 브리핑이 없습니다.')


def _render_manager_editions(repo):
    st.subheader('생성·게시 관리')
    code = st.selectbox('관리할 영역', PROFILE_ORDER, format_func=lambda x:PROFILE_LABELS[x], key='manager_edition_profile')
    summaries = _latest_summaries(True)
    item = summaries.get(code)
    if not item:
        st.info('이 영역에 저장된 자료가 없습니다.')
        return
    snapshot = repo._snapshot_for_revision(str(item['revision']['id']))
    if not snapshot:
        st.warning('저장된 판본을 불러오지 못했습니다.')
        return
    bundle = repo.bundle_from_parts(item['briefing'], item['revision'], snapshot)
    revision = bundle['revision']; briefing = bundle['briefing']
    st.caption(str(briefing.get('briefing_date'))+' · '+('게시됨' if revision.get('publication_status')=='published' else '게시 전 초안'))
    _publish_actions(repo, bundle)
    with st.expander('저장된 본문 확인'):
        render_body(_body(snapshot))
    from .operations_ui import render_correction, render_important_update
    render_correction(repo, bundle)
    render_important_update(repo, bundle)
    if revision.get('publication_status') == 'published':
        if st.button('공개 중단·공유 링크 차단', key='hide_'+revision['id']):
            repo.hide_revision(briefing['id'], revision['id'], _actor())
            _clear_read_caches(); st.rerun()
    with st.expander('판본 품질·상세 진단'):
        qa = snapshot.get('qa_payload') or {}
        st.write(' · '.join(f'{label} {value}개' for label,value in selection_summary(snapshot).items()))
        st.download_button('상세 진단 저장', json.dumps({'build':build_info(),'qa':qa}, ensure_ascii=False, indent=2),
                           file_name='hwarang_briefing_diagnostics.json', key='diag_'+snapshot['id'])


def _open_profile(code):
    st.session_state['hw_briefing_profile'] = code
    _navigate('오늘 브리핑')


def run():
    with st.container(key='hw_briefing_center'):
        from .display import render_style
        render_style()
        try:
            repo = _repo()
            can_manage = _can_manage()
            pages = PAGES if can_manage else PAGES[:3]
            # Migrate navigation only; existing authentication and content stay intact.
            if st.session_state.get('hw_briefing_page') == '운영 설정':
                st.session_state['hw_briefing_page'] = '운영 관리'
            if st.session_state.get('hw_briefing_page') not in pages:
                st.session_state['hw_briefing_page'] = pages[0]
            current = st.session_state['hw_briefing_page']
            title = {'오늘 브리핑':'오늘의 브리핑','지난 브리핑':'지난 브리핑','고객에게 공유':'고객에게 공유','운영 관리':'운영 관리'}[current]
            st.markdown('<div class="hw-briefing-hero"><span>화랑 WORKSPACE / BRIEFING CENTER</span><h1>'+html.escape(title)+'</h1></div>', unsafe_allow_html=True)
            mode = st.radio('브리핑 메뉴', pages, horizontal=True, label_visibility='collapsed', key='hw_briefing_page')
            flash = st.session_state.pop('hw_briefing_flash', '')
            if flash: st.success(flash)
            if mode == '오늘 브리핑':
                _render_today(repo, can_manage)
            elif mode == '지난 브리핑':
                _render_history(repo, can_manage)
            elif mode == '고객에게 공유':
                day = st.session_state.get('hw_briefing_share_day')
                a,b = st.columns([3,1])
                with a:
                    st.caption('같은 날짜의 고객용 기사만 선택해 공유합니다. 직원 상담·운영 정보는 제외됩니다.')
                with b:
                    if st.button('최근 통합본 선택', key='share_latest'):
                        st.session_state.pop('hw_briefing_share_day',None);st.rerun()
                _combined_sharing(repo, day, use_cache=not bool(day))
            elif can_manage:
                from .operations_ui import render_operations
                settings, editions = st.columns([1,1], gap='large')
                with settings:
                    render_operations(repo)
                with editions:
                    _render_manager_editions(repo)
                with st.expander('수동 생성 · 실패 작업 복구'):
                    _render_generate_panel(repo)
        except BriefingRepositoryError as exc:
            st.error(str(exc))
