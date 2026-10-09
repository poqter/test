from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dataclasses import asdict
import json
from typing import Callable
import streamlit as st
from .repository import BriefingRepository, BriefingRepositoryError
from .runtime import PROFILE_LABELS
from .public_body import customer_body, public_html, public_pdf
from .display import render_body, stamp
from .diagnostics import build_info, failure_diagnostic
from .scheduler import generate_group

PROFILE_ORDER=('MARKET','NEWS','INSURANCE')
KST=ZoneInfo('Asia/Seoul')


def _can_manage():
    profile=st.session_state.get('login_profile') or {}
    return profile.get('role')=='super_admin' or 'workspace.briefing_manage' in set(st.session_state.get('hw_feature_permissions') or ())


@st.cache_resource(show_spinner=False)
def _repo():
    from modules.shared.hwarang_auth import SupabaseConfig
    cfg=SupabaseConfig.from_mapping(st.secrets)
    return BriefingRepository(cfg.url,cfg.secret_key)


@st.cache_data(ttl=30,show_spinner=False)
def _published_summaries_cached():return _repo().latest_summaries(PROFILE_ORDER,include_draft=False)


@st.cache_data(ttl=30,show_spinner=False)
def _published_history_cached(code):return _repo().history(code,limit=30,include_draft=False)


def _latest_summaries(include_draft):
    return _repo().latest_summaries(PROFILE_ORDER,include_draft=True) if include_draft else _published_summaries_cached()


def _clear_read_caches():_published_summaries_cached.clear();_published_history_cached.clear()


def _counts(item):
    fast=((item or {}).get('snapshot') or {}).get('fast_brief_payload') or {}
    return int(fast.get('core_count') or 0),int(fast.get('light_count') or 0)


def render_home_summary(navigate:Callable):
    try:items=_published_summaries_cached()
    except Exception:return
    if not any(items.values()):return
    st.markdown('### 오늘의 브리핑')
    for code in PROFILE_ORDER:
        item=items.get(code)
        if item:
            a,b=_counts(item)
            st.write(f"{PROFILE_LABELS[code]} · {item['briefing']['briefing_date']} · 소식 {a+b}개")
    if st.button('브리핑 센터 열기',key='hw_home_briefing_open'):
        navigate('briefing')


def _body(snapshot):
    body=snapshot.get('external_content_payload') or {}
    if body.get('schema')=='hwarang-public-v2':return body
    return customer_body(snapshot.get('content_payload') or {})


def _sharing(repo,bundle,body):
    revision=bundle['revision'];profile=st.session_state.get('login_profile') or {};uid=str(profile.get('id') or '')
    key='hw_share_'+str(revision['id'])+'_'+uid
    with st.expander('고객에게 공유하기'):
        st.caption('뉴스·지표·리서치 본문은 동일하게 공유하며, 내부 상담 활용 문구는 포함하지 않습니다.')
        available=revision.get('publication_status')=='published' and revision.get('external_share_allowed') and revision.get('external_qa_passed')
        if not available:st.info('공개 검수가 완료되면 고객 공유가 열립니다.');return
        if not str(profile.get('position_name') or '').strip():st.info('등록 직함을 관리자에게 확인한 뒤 공유해 주세요.');return
        if st.button('공유 링크 만들기',key=key+'_make'):
            try:
                token,packet=repo.create_share(str(revision['id']),uid,{})
                st.session_state[key]={'token':token,'packet':packet}
            except BriefingRepositoryError as exc:st.error(str(exc))
        shared=st.session_state.get(key)
        if not shared:return
        packet=shared['packet'];url='https://hwarang-workspace.streamlit.app/?briefing='+shared['token']
        name=' '.join(str(packet['sender'].get(k) or '') for k in ('name','position')).strip()
        st.code(url,language=None)
        st.code(f"{name}의 {body.get('profile_label')}\n{packet.get('briefing_date')} · 오늘의 소식 {len(body.get('issues') or [])}개\n{url}",language=None)
        st.download_button('고객 브리핑 PDF',public_pdf(packet),file_name=f"hwarang_{bundle['briefing']['briefing_date']}_{body.get('profile_code')}.pdf",mime='application/pdf',key=key+'_pdf')
        st.download_button('고객 브리핑 HTML',public_html(packet),file_name='hwarang_briefing.html',mime='text/html',key=key+'_html')
        if st.button('이 공유 링크 취소',key=key+'_revoke'):
            repo.revoke_share(shared['token'],uid);st.session_state.pop(key,None);st.success('공유 링크를 취소했습니다.');st.rerun()


def _internal_actions(bundle):
    actions=bundle.get('actions') or []
    useful=[r for r in actions if any((r.get('conversation_payload') or {}).values()) or r.get('workspace_actions')]
    if not useful:return
    with st.expander('상담 활용 · 직원용'):
        for row in useful:
            st.markdown('**'+str(row.get('title') or '')+'**')
            for k,label in [('recommended_expression','상담에 활용할 표현'),('check_first','먼저 확인'),('avoid_expression','주의할 표현')]:
                v=(row.get('conversation_payload') or {}).get(k)
                if v:st.write(label+' · '+str(v))
            if row.get('audience_segments'):st.caption('관련 대상 · '+' / '.join(row['audience_segments']))
            for tool in row.get('workspace_actions') or []:
                from .tool_policy import registered_briefing_tools
                if tool.get('tool_code') in {r.get('tool_code') for r in registered_briefing_tools()}:st.caption('활용 도구 · '+str(tool.get('label') or tool.get('tool_code')))


def _render_profile_detail(repo,code,bundle,can_manage):
    revision=bundle['revision'];briefing=bundle['briefing'];snapshot=bundle['snapshot'];day=str(briefing.get('briefing_date') or '')
    st.subheader(PROFILE_LABELS[code]);st.caption(day+' · 수집 기준 '+stamp((snapshot.get('content_payload') or {}).get('as_of')))
    if day!=datetime.now(KST).date().isoformat():st.info('오늘 자료가 아직 공개되지 않아 마지막으로 확인된 브리핑을 표시합니다. 기준일은 '+day+'입니다.')
    if revision.get('publication_status')!='published':st.warning('관리자 미리보기입니다. 검수 중이거나 자료가 충분하지 않아 아직 공개되지 않았습니다.')
    body=_body(snapshot)
    if can_manage and code=='MARKET':
        missing=((snapshot.get('content_payload') or {}).get('market_metrics') or {}).get('missing',[])
        if missing:st.info('출처·표시 권한 확인이 필요한 지표: '+', '.join(missing))
    render_body(body)
    _internal_actions(bundle)
    _sharing(repo,bundle,body)
    if can_manage:
        with st.expander('운영 관리·진단'):
            qa=snapshot.get('qa_payload') or {};st.json(qa)
            st.download_button('진단 다운로드',json.dumps({'build':build_info(),'qa':qa},ensure_ascii=False,indent=2),file_name='hwarang_briefing_diagnostics.json',key='diag_'+snapshot['id'])
            publishable=revision.get('validation_status')=='ok' and revision.get('coverage_status')=='healthy' and qa.get('public_body_ready')
            actor=str((st.session_state.get('login_profile') or {}).get('id') or '')
            if revision.get('publication_status')=='draft' and st.button('검수 완료 브리핑 공개',key='publish_'+revision['id'],disabled=not publishable):
                try:repo.publish_revision(briefing['id'],revision['id'],actor_user_id=actor);_clear_read_caches();st.rerun()
                except BriefingRepositoryError as exc:st.error(str(exc))
            if revision.get('publication_status')=='published' and st.button('공개 중단·공유 링크 차단',key='hide_'+revision['id']):
                repo.hide_revision(briefing['id'],revision['id'],actor);_clear_read_caches();st.rerun()


def _render_generate_panel(repo):
    if not _can_manage():return
    with st.expander('브리핑 운영 관리'):
        st.caption('매일 아침 자동 생성합니다. 처음 3영업일의 검증된 결과를 관찰한 뒤 영역별로 자동 공개됩니다. 조회·공유·PDF에는 OpenAI를 호출하지 않습니다.')
        for p in repo.profiles():st.caption(PROFILE_LABELS.get(p['profile_code'],p['profile_code'])+' · '+str(p.get('run_mode')))
        st.caption('수동 생성은 기존 OpenAI API를 사용합니다. 자동 생성과 같은 날짜별 잠금·호출 상한을 적용하며 이미 생성한 결과는 재사용합니다.')
        group=st.selectbox('생성할 영역',['DAILY','MARKET'],format_func=lambda x:'종합뉴스·보험업계' if x=='DAILY' else '경제·금융')
        from .preflight import run_runtime_preflight, preflight_ready
        checks=run_runtime_preflight(require_direct_sources=False)
        for check in checks:
            if check.required and not check.ok: st.error(check.message)
        st.download_button('배포 진단 · API 호출 없음',json.dumps({'build':build_info(),'settings':[c.to_dict() for c in checks]},ensure_ascii=False,indent=2),file_name='briefing_deployment.json')
        day=datetime.now(KST).date()
        from .scheduler import cutoff
        disabled=datetime.now(KST)<cutoff(day,group) or not preflight_ready(checks)
        if st.button('오늘 브리핑 생성',disabled=disabled,key='hw_briefing_generate_today'):
            with st.spinner('출처를 수집하고 브리핑을 저장하고 있습니다…'):
                try:
                    result=generate_group(repo,day,group,actor=str((st.session_state.get('login_profile') or {}).get('id') or '') or None)
                    st.session_state['hw_briefing_flash']='처리 결과: '+str(result.get('status'));_clear_read_caches();st.rerun()
                except Exception as exc:st.session_state['hw_briefing_last_diagnostic']=failure_diagnostic(exc);st.error('생성을 완료하지 못했습니다. 저장된 이전 브리핑을 이용해 주세요.')
        if st.session_state.get('hw_briefing_last_diagnostic'):
            st.download_button('실패 진단 다운로드',json.dumps(st.session_state['hw_briefing_last_diagnostic'],ensure_ascii=False,indent=2),file_name='briefing_failure.json')


def _render_today(repo,can_manage):
    preview=st.toggle('관리자 미리보기',value=False) if can_manage else False
    summaries=_latest_summaries(preview)
    selected=st.radio('브리핑 영역',PROFILE_ORDER,format_func=lambda x:PROFILE_LABELS[x],horizontal=True)
    item=summaries.get(selected)
    if not item:st.info('아직 공개된 브리핑이 없습니다. 매일 아침 수집 후 검수가 끝난 자료부터 표시합니다.');return
    snapshot=repo._snapshot_for_revision(str(item['revision']['id']))
    if not snapshot:st.info('본문을 불러오지 못했습니다.');return
    bundle=repo.bundle_from_parts(item['briefing'],item['revision'],snapshot)
    _render_profile_detail(repo,selected,bundle,can_manage)


def _render_history(repo,can_manage):
    code=st.selectbox('브리핑 영역',PROFILE_ORDER,format_func=lambda x:PROFILE_LABELS[x],key='history_profile')
    now=datetime.now(KST).date();day=st.date_input('날짜',value=now,min_value=now-timedelta(days=29),max_value=now)
    preview=st.toggle('관리자 미리보기',key='history_preview') if can_manage else False
    bundle=repo.bundle_for_date(code,day,include_draft=preview)
    if bundle:_render_profile_detail(repo,code,bundle,can_manage)
    else:st.info('선택한 날짜에 공개된 브리핑이 없습니다.')


def run():
    st.title('브리핑 센터');st.write('오늘의 뉴스와 시장 흐름을 편하게 확인하세요.')
    try:
        repo=_repo();can_manage=_can_manage()
        flash=st.session_state.pop('hw_briefing_flash','')
        if flash:st.success(flash)
        mode=st.radio('보기',['오늘 브리핑','최근 30일'],horizontal=True,label_visibility='collapsed')
        if mode=='오늘 브리핑':_render_today(repo,can_manage)
        else:_render_history(repo,can_manage)
        _render_generate_panel(repo)
    except BriefingRepositoryError:
        st.error('브리핑을 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.')
