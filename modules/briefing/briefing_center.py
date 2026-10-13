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

PROFILE_ORDER = ('NEWS', 'INSURANCE', 'MARKET')
KST = ZoneInfo('Asia/Seoul')
PAGES = ('오늘 브리핑', '지난 브리핑', '운영 설정')


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
    with st.container(border=True):
        st.markdown('#### 고객에게 공유하기')
        day = str(selected_day) if selected_day else (_customer_date_cached() if use_cache else repo.latest_complete_customer_date())
        if not day:
            st.info('세 영역의 같은 날짜 게시본이 준비되면 통합 공유가 열립니다.')
            st.button('통합 공유 링크 만들기', disabled=True, key='combined_not_ready')
            return
        if day != datetime.now(KST).date().isoformat():
            st.info(f'오늘 통합본이 아직 준비되지 않아 최근 정상 통합본({day})을 제공합니다.')
        st.caption(f'{day} · 경제·금융, 종합뉴스, 고객에게 적합한 보험 소식을 한 링크로 공유합니다.')
        available = []
        blocked_reasons = []
        policy = repo.operating_policy()
        try:
            reader_configured = bool(repo.public_base_url())
        except BriefingRepositoryError:
            reader_configured = False
        for code in ('MARKET', 'NEWS', 'INSURANCE'):
            bundle = repo.bundle_for_date(code, day)
            if bundle:
                reasons = sharing_blockers(bundle, policy, profile,
                                           reader_configured=reader_configured)
                if not reasons:
                    available.append(code)
                else:
                    blocked_reasons.extend(reasons)
        if not available and blocked_reasons:
            st.info(' / '.join(dict.fromkeys(blocked_reasons)))
        codes = st.multiselect('공유할 영역', available, default=available,
            format_func=lambda code: PROFILE_LABELS[code], key='combined_sections_' + day)
        if 'INSURANCE' not in available:
            st.caption('보험업계의 직원용 정보는 제외하며, 고객용 적격 기사가 있는 판본만 포함합니다.')
        approved = policy.get('external_sharing_approved')
        if not approved:
            st.info('관리자가 운영 설정에서 최초 고객 공유 승인을 켜면 사용할 수 있습니다.')
        key = 'combined_share_' + day + '_' + uid + '_' + '_'.join(codes)
        if st.button('통합 공유 링크 만들기', disabled=not codes or not approved,
                     type='primary', key=key + '_make', use_container_width=True):
            try:
                token, packet = repo.create_combined_share(day, codes, uid)
                st.session_state[key] = {'token': token, 'packet': packet}
            except BriefingRepositoryError as exc:
                st.error(str(exc))
        shared = st.session_state.get(key)
        if shared and codes and approved and all(code in available for code in codes):
            from .sharing import share_url
            url = share_url(repo.public_base_url(), shared['token'])
            packet = shared['packet']; sender = packet['sender']
            st.success('링크가 준비됐습니다. 아래 문구를 복사해 카카오톡이나 문자로 보내세요.')
            st.code(f"{sender['name']} {sender['position']}의 통합 브리핑\n{day} · 소식 {len(packet['body']['issues'])}개\n{url}", language=None)
            a, b = st.columns(2)
            a.link_button('고객 화면 열기', url, use_container_width=True)
            b.download_button('고객용 PDF 저장', public_pdf(packet), mime='application/pdf',
                file_name=f'hwarang_briefing_{day}.pdf', key=key + '_pdf', use_container_width=True)
            if st.button('이 공유 링크 취소', key=key + '_revoke'):
                repo.revoke_share(shared['token'], uid); st.session_state.pop(key, None); st.rerun()


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
        st.info(f'가장 최근에 저장된 {day} 브리핑입니다. 오늘 자료가 준비되면 새 판이 표시됩니다.')
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
        st.download_button('실패 내용 저장', json.dumps(st.session_state['hw_briefing_last_diagnostic'], ensure_ascii=False, indent=2), file_name='briefing_failure.json')
    with st.expander('상세 연결 상태'):
        st.dataframe([{'항목':c.code,'상태':'준비됨' if c.ok else '설정 필요','필수':c.required,'안내':c.message} for c in checks], hide_index=True, use_container_width=True)
        st.download_button('배포 진단 저장', json.dumps({'build':build_info(),'settings':[c.to_dict() for c in checks]}, ensure_ascii=False, indent=2), file_name='briefing_deployment.json')


def _render_today(repo, can_manage):
    _combined_sharing(repo, use_cache=True)
    summaries = _latest_summaries(False)
    selected = st.radio('브리핑 영역', PROFILE_ORDER, format_func=lambda x:PROFILE_LABELS[x], horizontal=True, key='hw_briefing_profile')
    item = summaries.get(selected)
    if not item:
        st.info('아직 '+PROFILE_LABELS[selected]+' 브리핑이 '+('저장되지 않았습니다.' if can_manage else '게시되지 않았습니다.'))
        if can_manage:
            st.button('브리핑 생성하러 가기', on_click=_navigate, args=('운영 설정',), key='empty_generate')
        return
    snapshot = repo._snapshot_for_revision(str(item['revision']['id']))
    if not snapshot:
        st.warning('저장된 본문을 불러오지 못했습니다.')
        return
    _render_profile_detail(repo, selected, repo.bundle_from_parts(item['briefing'], item['revision'], snapshot), can_manage)


def _render_history(repo, can_manage):
    code = st.radio('브리핑 영역', PROFILE_ORDER, format_func=lambda x:PROFILE_LABELS[x], horizontal=True, key='history_profile')
    now = datetime.now(KST).date()
    day = st.date_input('읽을 날짜', value=now, min_value=now-timedelta(days=29), max_value=now)
    bundle = repo.bundle_for_date(code, day, include_draft=False)
    if bundle:
        _combined_sharing(repo, day)
        _render_profile_detail(repo, code, bundle, can_manage)
    else:
        st.info('선택한 날짜에 저장된 브리핑이 없습니다.' if can_manage else '선택한 날짜에 게시된 브리핑이 없습니다.')


def _render_manager_editions(repo):
    st.subheader('저장된 브리핑 · 게시와 공유')
    summaries = _latest_summaries(True)
    for code in PROFILE_ORDER:
        item = summaries.get(code)
        with st.container(border=True):
            st.markdown('**'+PROFILE_LABELS[code]+'**')
            if not item:
                st.caption('아직 저장된 자료가 없습니다.')
                continue
            snapshot = repo._snapshot_for_revision(str(item['revision']['id']))
            if not snapshot:
                continue
            bundle = repo.bundle_from_parts(item['briefing'], item['revision'], snapshot)
            count = len((snapshot.get('content_payload') or {}).get('issues') or [])
            st.caption(str(item['briefing'].get('briefing_date'))+f' · 기사 {count}개 · '+('게시됨' if item['revision'].get('publication_status')=='published' else '게시 대기'))
            _publish_actions(repo, bundle)
            st.button('본문 읽기', key='read_'+code, on_click=_open_profile, args=(code,), use_container_width=True)


def _open_profile(code):
    st.session_state['hw_briefing_profile'] = code
    _navigate('오늘 브리핑')


def run():
    with st.container(key='hw_briefing_center'):
        from .display import render_style
        render_style()
        st.markdown('<div class="hw-briefing-hero"><span>HWARANG BRIEFING</span><h1>오늘의 흐름, 한눈에</h1><p>뉴스를 읽고, 필요한 소식을 고객과 나누세요.</p></div>', unsafe_allow_html=True)
        try:
            repo = _repo()
            can_manage = _can_manage()
            flash = st.session_state.pop('hw_briefing_flash', '')
            if flash:
                st.success(flash)
            pages = PAGES if can_manage else PAGES[:2]
            if can_manage:
                st.button('운영 설정', on_click=_navigate, args=('운영 설정',), key='briefing_manager_settings')
            if st.session_state.get('hw_briefing_page') not in pages:
                st.session_state['hw_briefing_page'] = pages[0]
            if st.session_state['hw_briefing_page'] == '운영 설정':
                mode = '운영 설정'
                st.button('오늘 브리핑으로 돌아가기', on_click=_navigate, args=('오늘 브리핑',), key='back_reading')
            else:
                mode = st.radio('브리핑 메뉴', PAGES[:2], horizontal=True, label_visibility='collapsed', key='hw_briefing_page')
            if mode == '오늘 브리핑':
                _render_today(repo, can_manage)
            elif mode == '지난 브리핑':
                _render_history(repo, can_manage)
            elif can_manage:
                _render_generate_panel(repo)
                _render_manager_editions(repo)
                from .operations_ui import render_operations
                render_operations(repo)
        except BriefingRepositoryError as exc:
            st.error(str(exc))
