"""Super-admin operations console. Mutations are limited to review audit records."""
from __future__ import annotations
import json
import time
from uuid import uuid4
import streamlit as st
import streamlit.components.v1 as components
from modules.shared import operations as op


@st.cache_data(ttl=300, max_entries=2, show_spinner=False)
def _github():
    return op.github_overview()


@st.cache_data(ttl=300, max_entries=20, show_spinner=False)
def _details(run_id,sha):
    return op.run_details(run_id,sha)


def _copy(text, label):
    # JSON-encode and escape script delimiters; never interpolate evidence into HTML.
    encoded=json.dumps(text,ensure_ascii=True).replace('<','\\u003c')
    components.html('''<button id="copy" style="font:600 14px sans-serif;padding:11px 18px;border:1px solid #bbc9d8;border-radius:9px;background:#edf4fb;cursor:pointer"></button><span id="status" role="status" style="font:12px sans-serif;margin-left:10px"></span><script>
const text='''+encoded+''';document.getElementById('copy').textContent='''+json.dumps(label)+''';
document.getElementById('copy').onclick=async()=>{try{await navigator.clipboard.writeText(text);document.getElementById('status').textContent='복사 완료';}catch(e){const t=document.createElement('textarea');t.value=text;document.body.appendChild(t);t.select();const ok=document.execCommand('copy');t.remove();document.getElementById('status').textContent=ok?'복사 완료':'아래 요청문을 직접 선택해 복사해 주세요.';}};</script>''',height=54)


def _session_load(key, loader, ttl=120):
    entry=st.session_state.get(key)
    if entry and time.time()-entry['at']<ttl:return entry['data'],None
    try:
        data=loader()
        st.session_state[key]={'at':time.time(),'data':data}
        return data,None
    except Exception:
        return (entry['data'] if entry else None),'수집 실패 · 이전 결과가 있으면 유지합니다. 최신 여부를 확인해 주세요.'


def _review(auth,actor,item):
    records=op.review_history(auth,actor,item['id'])
    latest=next((r for r in records if r['details'].get('evidence')==item['evidence']),None)
    value=latest['details'] if latest else {}
    if records and not latest:st.info('새로운 검사 근거입니다. 이전 검토 완료와 별도로 확인해 주세요.')
    prefix=actor+':'+item['id']+':'+item['evidence']
    with st.form('review:'+prefix):
        options=['미확인','확인 중','검토 완료','보완 필요']
        status=st.selectbox('점검 상태',options,index=options.index(value.get('status','미확인')))
        checks={c:st.checkbox(c,value=bool(value.get('checks',{}).get(c))) for c in op.CHECKS}
        note=st.text_area('점검 메모 · 개인정보 입력 금지',value=value.get('note',''),max_chars=2000)
        submitted=st.form_submit_button('점검 기록 저장')
    if submitted:
        pending=st.session_state.setdefault('ops_pending:'+prefix,str(uuid4()))
        try:
            saved=op.save_review(auth,actor,item,status,checks,note,pending)
            if not saved:raise ValueError('저장 결과 미확인')
            st.session_state.pop('ops_pending:'+prefix,None)
            st.success('점검 기록을 저장했습니다. 검사 결과와 사용자 영향은 변경되지 않습니다.')
        except Exception as exc:
            if isinstance(exc,ValueError):st.error(str(exc))
            else:st.error('저장 결과 확인 필요. 아래 기록을 확인한 뒤 같은 내용으로 저장하면 요청 ID를 대조합니다.')
    if records:
        st.dataframe([{'시각':op.display_time(r['created_at']),'검토자':r['actor_user_id'],
                       '근거':r['details'].get('evidence'),'상태':r['details'].get('status'),
                       '메모':op.redact(r['details'].get('note'))} for r in records[:20]],hide_index=True,use_container_width=True)


def render(auth,actor):
    op.require(auth,actor)
    owner=st.session_state.get('ops_owner')
    if owner!=actor:
        for key in list(st.session_state):
            if str(key).startswith('ops_'):del st.session_state[key]
        st.session_state['ops_owner']=actor
    left,right=st.columns([3,1])
    left.caption('운영 데이터 조회 · 점검 기록 · 요청문 복사')
    if right.button('최신 상태 조회',key='ops_refresh',use_container_width=True):
        _github.clear();_details.clear()
        for key in ['ops_github','ops_briefing']: 
            if key in st.session_state:st.session_state[key]['at']=0
    github,gerr=_session_load('ops_github',_github,300)
    briefing,berr=_session_load('ops_briefing',lambda:op.briefing_overview(auth,actor))
    for label,data,err in [('GitHub',github,gerr),('브리핑',briefing,berr)]:
        if err:st.warning(label+' · '+err)
        st.caption(label+' 마지막 수집: '+op.display_time((data or {}).get('collected_at')))
    issues=[op.run_issue(r,github['history']) for r in github['runs']] if github else []
    issues+=op.briefing_issues(briefing) if briefing else []
    st.caption('GitHub: main 최근 40회 내 워크플로별 최신 결과 · 브리핑: 최근 작업 60건/게시 기록 90건. 미수집 범위는 정상 판정하지 않습니다.')
    if not issues:
        st.info('확인 가능한 결과가 없습니다. 수집 상태를 먼저 확인해 주세요.');return
    tabs=st.tabs(['오늘 확인할 문제','기능별 현황','자동 작업·최근 변경'])
    with tabs[0]:
        pending=[x for x in issues if x['result']!='통과']
        st.subheader('오늘 확인할 문제')
        st.caption('검사 실패 → 확인 필요 → 진행 중 순서입니다. 검토 완료만으로 미해결 문제가 사라지지 않습니다.')
        if not pending:st.success('수집한 범위에서 현재 확인할 이상 항목이 없습니다.')
        for item in sorted(pending,key=lambda i:({'실패':0,'확인 필요':1,'진행 중':2}.get(i['result'],1),i['title'])):
            with st.container(border=True):
                st.markdown('**'+item['title']+'**')
                st.write(item['result']+' · '+item['impact']+' · '+item['change'])
                st.caption(item['fact']);st.write('다음 확인: '+item['next'])
        changes=[i for i in issues if i['change'] in ('해결 확인 (검사 범위)','재발 후보')]
        if changes:st.dataframe([{'항목':i['title'],'변화':i['change']} for i in changes],hide_index=True,use_container_width=True)
    with tabs[1]:
        st.dataframe([{'영역':i['area'],'항목':i['title'],'검사·게시 결과':i['result'],'사용자 영향':i['impact'],'원인':i['classification']} for i in issues],hide_index=True,use_container_width=True)
        st.info('일정·일일 기록·지원 요청·모바일·홈 설치·ACADEMY의 세부 결과는 해당 실행의 단계별 근거에서 확인합니다. 실제 기기 설치 및 사용자 저장·삭제는 별도 확인이 필요합니다.')
    with tabs[2]:
        if briefing:
            st.markdown('**브리핑 자동 작업**')
            st.dataframe(briefing['runs'],hide_index=True,use_container_width=True)
            st.dataframe(op.schedules(),hide_index=True,use_container_width=True)
            st.caption('예약식은 현재 운영 코드 기준입니다. 실제 시작은 GitHub 대기열에 따라 늦어질 수 있으며 게시 시각과 다릅니다.')
        if github:
            st.markdown('**최근 변경**')
            for commit in github['commits']:
                st.write(commit['sha'][:8]+' · '+op.redact(commit['commit']['message'].splitlines()[0]))
                st.link_button('커밋 근거',commit['html_url'])
            st.caption('커밋 존재는 운영 반영 완료를 의미하지 않습니다.')
        st.code('현재 WORKSPACE 운영 점검 코드 표식: '+op.release_id())
    st.divider()
    st.subheader('문제 상세·요청문')
    byid={i['id']:i for i in issues}
    selected=st.selectbox('확인할 항목',list(byid),format_func=lambda key:byid[key]['title'],key='ops_selected')
    item=dict(byid[selected])
    if item.get('run_id'):
        if st.button('단계별 근거 불러오기',key='ops_load_details'):
            try:st.session_state['ops_detail:'+item['evidence']]=_details(item['run_id'],item['sha'])
            except Exception:st.error('상세 근거 수집 실패. 실행 링크에서 확인해 주세요.')
        detail=st.session_state.get('ops_detail:'+item['evidence'])
        if detail:
            item=op.enrich(item,detail)
            st.dataframe(detail['steps'],hide_index=True,use_container_width=True)
            if detail['truncated']:st.warning('100개 작업을 초과해 일부 단계가 생략되었습니다.')
        if item.get('url'):st.link_button('GitHub 실행 근거 열기',item['url'])
    for label,value in [('확인된 사실',item['fact']),('사용자 영향',item['impact']),('원인 판단',item['classification']+' · '+item['cause']),
                        ('재현 절차',item['reproduction']),('기대 결과',item['expected']),('최소 변경안',item['minimum']),('다음 확인',item['next'])]:
        st.write('**'+label+'**  '+value)
    st.caption('정보 부족: 실제 사용자 재현·오류 원문·원인 파일·해당 커밋 운영 반영 여부는 근거가 없으면 미확인으로 전달됩니다.')
    with st.expander('점검 체크리스트·기록',expanded=False):
        try:_review(auth,actor,item)
        except Exception:st.error('점검 기록을 조회하지 못했습니다. 저장 입력을 열지 않습니다.')
    scope=st.selectbox('요청 범위',op.SCOPES,index=1,key='ops_scope')
    st.caption('선택한 범위는 복사 문구에만 반영됩니다. 이 화면에서는 수정·재실행·배포하지 않습니다.')
    text=op.request_text([item],scope,op.release_id())
    _copy(op.redact(f"{item['title']}\n위치: {item['area']}\n{item['fact']}\n사용자 영향: {item['impact']}"),'문제 요약 복사')
    _copy(text,'요청문 복사')
    preview_key='ops_preview:'+item['evidence']+':'+scope
    st.session_state[preview_key]=text
    st.text_area('요청문 미리보기',height=300,key=preview_key,disabled=True)
    selected_many=st.multiselect('한 번에 요청할 문제',list(byid),format_func=lambda key:byid[key]['title'],key='ops_many')
    if selected_many:
        batch=[]
        for key in dict.fromkeys(selected_many):
            entry=dict(byid[key]);detail=st.session_state.get('ops_detail:'+entry['evidence'],{})
            entry=op.enrich(entry,detail);batch.append(entry)
        bundled=op.request_text(batch,scope,op.release_id())
        _copy(bundled,'선택한 문제 묶어서 복사')
        with st.expander('묶음 요청문 미리보기'):st.code(bundled,language=None)
