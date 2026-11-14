"""Super-admin operations console. Mutations are limited to review audit records."""
from __future__ import annotations
import json
from html import escape
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


def _copy(text, label, primary=False):
    # JSON-encode and escape script delimiters; never interpolate evidence into HTML.
    encoded=json.dumps(text,ensure_ascii=True).replace('<','\\u003c')
    markup=('''<button id="copy" style="font:600 14px sans-serif;padding:11px 18px;border:1px solid #bbc9d8;border-radius:9px;background:COLOR;background-color:COLOR;color:INK;cursor:pointer;width:100%;min-height:44px"></button><span id="status" role="status" style="font:12px sans-serif;display:block;margin-top:5px;color:#536075"></span><script>
const text='''+encoded+''';document.getElementById('copy').textContent='''+json.dumps(label)+''';
document.getElementById('copy').onclick=async()=>{try{await navigator.clipboard.writeText(text);document.getElementById('status').textContent='복사 완료';}catch(e){const t=document.createElement('textarea');t.value=text;document.body.appendChild(t);t.select();const ok=document.execCommand('copy');t.remove();document.getElementById('status').textContent=ok?'복사 완료':'아래 요청문을 직접 선택해 복사해 주세요.';}};</script>''')
    components.html(markup.replace('COLOR','#ee8534' if primary else '#ffffff',2).replace('INK','#ffffff' if primary else '#14263d',1),height=80)


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


def _select_issue(key):
    st.session_state['ops_selected']=key
    st.session_state['ops_mobile_detail']=True


def _back_to_list():
    st.session_state['ops_mobile_detail']=False


def _styles():
    st.markdown("""<style>
    [class*="st-key-ops_shell"] {color:#14263d;}
    .ops-summary {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:8px 0 22px;}
    .ops-stat {border:1px solid #e2e7ee;border-radius:12px;padding:18px 22px;background:#f7f9fc;}
    .ops-stat span {font-size:14px;font-weight:600;display:block;}
    .ops-stat strong {font-size:30px;line-height:1.4;}
    .ops-stat.warn {background:#fff7ec;color:#975414;}
    .ops-stat.running {background:#f0f5ff;color:#2458a7;}
    .ops-stat.ok {background:#f0f8f5;color:#22664f;}
    .ops-badge {display:inline-block;border-radius:7px;padding:4px 9px;font-size:13px;font-weight:600;background:#fff0d7;color:#915000;}
    .ops-badge.fail {background:#fff0f0;color:#a82d36;}
    .ops-badge.running {background:#edf3ff;color:#2458a7;}
    .ops-badge.ok {background:#eaf5ef;color:#22664f;}
    .ops-detail-title {font-size:25px;font-weight:750;margin:0 0 8px;overflow-wrap:anywhere;}
    .ops-meta {font-size:13px;color:#69778a;margin-bottom:20px;}
    .ops-fact {display:grid;grid-template-columns:100px minmax(0,1fr);gap:14px;margin:6px 0;line-height:1.65;overflow-wrap:anywhere;}
    .ops-fact b {font-size:14px;color:#536075;}
    .ops-fact span {font-size:15px;}
    .st-key-ops_list, .st-key-ops_detail {border:1px solid #e0e6ee;border-radius:12px;padding:20px;background:#fff;gap:0.65rem;}
    .st-key-ops_list button {text-align:left;justify-content:flex-start;min-height:70px;white-space:normal;}
    .st-key-ops_list button p {white-space:pre-line;line-height:1.65;font-size:14px;}
    .st-key-ops_list button[kind="primary"] {background:#fff6e9!important;color:#14263d!important;border:1px solid #ee8534!important;}
    .st-key-ops_back {display:none;}
    @media (max-width:850px) {
      .ops-summary {gap:7px;margin-bottom:12px;}
      .ops-stat {padding:12px 9px;}
      .ops-stat span {font-size:11px;}
      .ops-stat strong {font-size:24px;}
      .st-key-ops_workspace [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .st-key-ops_list) {flex-direction:column;}
      .st-key-ops_workspace [data-testid="stColumn"]:has(.st-key-ops_list),
      .st-key-ops_workspace [data-testid="stColumn"]:has(.st-key-ops_detail) {width:100%!important;flex:1 1 100%!important;min-width:0!important;}
      .st-key-ops_shell_list [data-testid="stColumn"]:has(> div .st-key-ops_detail) {display:none;}
      .st-key-ops_shell_detail [data-testid="stColumn"]:has(> div .st-key-ops_list) {display:none;}
      .st-key-ops_shell_detail .st-key-ops_back {display:block;}
      .st-key-ops_shell_detail .ops-summary {display:none;}
      .st-key-ops_list, .st-key-ops_detail {padding:14px;}
      .ops-fact {grid-template-columns:1fr;gap:3px;margin:8px 0;}
      .ops-detail-title {font-size:22px;}
    }
    </style>""",unsafe_allow_html=True)


def _badge(result):
    tone={'실패':'fail','진행 중':'running','통과':'ok','게시 예정':'running','정규 게시 휴무':'running'}.get(result,'warn')
    label={'실패':'검사 실패','진행 중':'검사 중','통과':'확인 범위 정상'}.get(result,result)
    return f'<span class="ops-badge {tone}">{escape(label)}</span>'


def _load_detail(run_id,sha,evidence):
    try:
        st.session_state['ops_detail:'+evidence]=_details(run_id,sha)
        st.session_state.pop('ops_detail_error:'+evidence,None)
    except Exception:
        st.session_state['ops_detail_error:'+evidence]=True


def _detail(auth,actor,original):
    item=dict(original)
    with st.container(key='ops_back'):
        st.button('← 문제 목록',on_click=_back_to_list,use_container_width=True)
    detail=st.session_state.get('ops_detail:'+item['evidence'])
    if detail:item=op.enrich(item,detail)
    st.markdown(f'<div class="ops-detail-title">{escape(item["title"])}</div>'+_badge(item['result'])+
                f'<div class="ops-meta">{escape(item["area"])} · {escape(item.get("change",""))}</div>',unsafe_allow_html=True)
    for label,value in [('확인된 내용',item['fact']),('사용자 영향',item['impact']),('다음 확인',item['next'])]:
        st.markdown(f'<div class="ops-fact"><b>{label}</b><span>{escape(str(value))}</span></div>',unsafe_allow_html=True)
    if item['result']!='통과':
        st.caption('검사 결과와 실제 사용자 영향은 구분해서 확인합니다. 미확인 내용은 확정하지 않습니다.')
    st.divider()
    scope=st.selectbox('요청 범위',op.SCOPES,index=1,key='ops_scope')
    text=op.request_text([item],scope,op.release_id())
    primary,secondary=st.columns([3,2])
    with primary:_copy(text,'요청문 복사',primary=True)
    with secondary:_copy(op.redact(f"{item['title']}\n위치: {item['area']}\n{item['fact']}\n사용자 영향: {item['impact']}"),'요약 복사')
    st.caption('선택한 범위는 요청문에만 반영됩니다. 이 화면에서는 수정·재실행·배포하지 않습니다.')
    with st.expander('요청문 미리보기'):
        preview_key='ops_preview:'+item['evidence']+':'+scope
        st.session_state[preview_key]=text
        st.text_area('요청문 미리보기',height=300,key=preview_key,disabled=True,label_visibility='collapsed')
    with st.expander('상세 근거 · 검사 단계 및 변경 파일'):
        if item.get('run_id'):
            st.button('단계별 근거 불러오기',key='ops_load_details',on_click=_load_detail,args=(item['run_id'],item['sha'],item['evidence']))
            if st.session_state.get('ops_detail_error:'+item['evidence']):
                st.error('상세 근거 수집 실패. 실행 링크에서 확인해 주세요.')
            if detail:
                st.dataframe(detail['steps'],hide_index=True,use_container_width=True)
                if detail['truncated']:st.warning('100개 작업을 초과해 일부 단계가 생략되었습니다.')
                st.caption('해당 커밋 변경 파일 · 원인 파일 확정 아님')
                st.code('\n'.join(detail.get('files',[])) or '변경 파일 정보 없음',language=None)
            if item.get('url'):st.link_button('GitHub 실행 근거 열기',item['url'])
        for label,value in [('원인 판단',item['classification']+' · '+item['cause']),('재현 절차',item['reproduction']),
                            ('기대 결과',item['expected']),('최소 변경안',item['minimum'])]:
            st.write('**'+label+'**  '+value)
        st.caption('실제 사용자 재현·오류 원문·원인 파일·운영 반영 여부는 근거가 없으면 미확인으로 전달됩니다.')
    with st.expander('점검 기록 · 상태와 메모'):
        try:_review(auth,actor,item)
        except Exception:st.error('점검 기록을 조회하지 못했습니다. 저장 입력을 열지 않습니다.')


def render(auth,actor):
    op.require(auth,actor)
    owner=st.session_state.get('ops_owner')
    if owner!=actor:
        for key in list(st.session_state):
            if str(key).startswith('ops_'):del st.session_state[key]
        st.session_state['ops_owner']=actor
    _styles()
    left,right=st.columns([3,1])
    left.caption('문제를 확인하고 필요한 요청을 정리하세요.')
    if right.button('최신 상태 조회',key='ops_refresh',use_container_width=True):
        _github.clear();_details.clear()
        for key in ['ops_github','ops_briefing','ops_studio']:
            if key in st.session_state:st.session_state[key]['at']=0
    github,gerr=_session_load('ops_github',_github,300)
    briefing,berr=_session_load('ops_briefing',lambda:op.briefing_overview(auth,actor))
    studio,serr=_session_load('ops_studio',lambda:op.studio_report_overview(auth,actor))
    sources=[('GitHub',github,gerr),('브리핑',briefing,berr),('ACADEMY 평가',studio,serr)]
    for label,data,err in sources:
        if err:st.warning(label+' · '+err)
    collected=[(data or {}).get('collected_at') for _,data,_ in sources if (data or {}).get('collected_at')]
    st.caption('마지막 수집 기준: '+op.display_time(min(collected) if collected else None))
    with st.expander('수집 시각과 점검 범위'):
        for label,data,err in sources:st.caption(label+' 마지막 수집: '+op.display_time((data or {}).get('collected_at')))
        st.caption('GitHub: main 최근 40회 내 워크플로별 최신 결과 · 브리핑: 최근 작업 60건/게시 기록 90건 · ACADEMY 평가: 최근 7일의 근거 검증 실패 최대 30건. 미수집 범위는 정상 판정하지 않습니다.')
    issues=[op.run_issue(r,github['history']) for r in github['runs']] if github else []
    issues+=op.briefing_issues(briefing) if briefing else []
    issues+=op.studio_report_issues(studio) if studio else []
    if not issues:
        st.info('확인 가능한 결과가 없습니다. 수집 상태를 먼저 확인해 주세요.');return
    issues.sort(key=lambda i:({'실패':0,'확인 필요':1,'진행 중':2,'통과':3,'게시 예정':4,'정규 게시 휴무':4}.get(i['result'],1),i['title']))
    byid={i['id']:i for i in issues}
    if st.session_state.get('ops_selected') not in byid:
        st.session_state['ops_selected']=issues[0]['id']
        st.session_state['ops_mobile_detail']=False
    shell='ops_shell_detail' if st.session_state.get('ops_mobile_detail') else 'ops_shell_list'
    with st.container(key=shell):
        counts=[sum(i['result'] not in ('통과','진행 중','정규 게시 휴무','게시 예정') for i in issues),sum(i['result']=='진행 중' for i in issues),sum(i['result']=='통과' for i in issues)]
        st.markdown('<div class="ops-summary">'+''.join(f'<div class="ops-stat {tone}"><span>{label}</span><strong>{count}</strong></div>' for tone,label,count in zip(['warn','running','ok'],['확인 필요','검사 중','확인 범위 정상'],counts))+'</div>',unsafe_allow_html=True)
        tabs=st.tabs(['문제 확인','기능별 현황','자동 작업·최근 변경'])
        with tabs[0]:
            with st.container(key='ops_workspace'):
                listing,content=st.columns([0.38,0.62],gap='medium')
                with listing,st.container(key='ops_list'):
                    st.markdown('### 확인할 문제')
                    chosen=st.selectbox('표시할 항목',['확인 필요·검사 중','전체','검사 실패','확인 범위 정상'],key='ops_filter',label_visibility='collapsed')
                    visible=[i for i in issues if chosen=='전체' or (chosen=='확인 필요·검사 중' and i['result'] in ('실패','확인 필요','진행 중','확인 불가')) or (chosen=='검사 실패' and i['result']=='실패') or (chosen=='확인 범위 정상' and i['result']=='통과')]
                    if not visible:st.info('이 조건에 해당하는 항목이 없습니다. 전체 목록에서 검사 결과를 확인할 수 있습니다.')
                    for i in visible:
                        label={'실패':'검사 실패','진행 중':'검사 중','통과':'확인 범위 정상'}.get(i['result'],i['result'])
                        st.button(i['title']+'\n'+(i['fact'][:65]+'…' if len(i['fact'])>65 else i['fact'])+'\n'+label+' · '+op.display_time(i.get('last')),key='ops_pick:'+i['id'],type='primary' if st.session_state['ops_selected']==i['id'] else 'secondary',on_click=_select_issue,args=(i['id'],),use_container_width=True)
                    st.caption('검토 완료만으로 미해결 문제가 사라지지 않습니다.')
                    with st.expander('여러 문제 한 번에 요청'):
                        actionable = [key for key, item in byid.items() if item['result'] == '실패' or item['result'] == '확인 필요']
                        st.session_state['ops_many'] = [key for key in st.session_state.get('ops_many', []) if key in actionable]
                        selected_many=st.multiselect('한 번에 요청할 문제',actionable,format_func=lambda key:byid[key]['title'],key='ops_many')
                        if selected_many:
                            batch=[op.enrich(dict(byid[key]),st.session_state.get('ops_detail:'+byid[key]['evidence'],{})) for key in dict.fromkeys(selected_many)]
                            batch_scope=st.selectbox('묶음 요청 범위',op.SCOPES,index=1,key='ops_batch_scope')
                            bundled=op.request_text(batch,batch_scope,op.release_id())
                            _copy(bundled,'선택한 문제 묶어서 복사',primary=True)
                            with st.expander('묶음 요청문 미리보기'):st.code(bundled,language=None)
                with content,st.container(key='ops_detail'):_detail(auth,actor,byid[st.session_state['ops_selected']])
        with tabs[1]:
            st.dataframe([{'영역':i['area'],'항목':i['title'],'검사·게시 결과':i['result'],'사용자 영향':i['impact'],'변화':i['change'],'원인':i['classification']} for i in issues],hide_index=True,use_container_width=True)
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
