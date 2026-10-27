"""Exam selection, immutable results, and scoped learning dashboard."""
from uuid import uuid4
from datetime import datetime,timedelta
import html
import streamlit as st
import pandas as pd
from .repository import Repository
from .component import active
from .analytics import KST,stamp,mode_label,in_window,summarize
MANAGERS={'team_leader','deputy_branch_manager','branch_manager','division_head','chief_representative'}

def _text(value):
    st.markdown('<div class="exam-prose">'+html.escape(str(value)).replace('\n','<br>')+'</div>',unsafe_allow_html=True)

def _question(q):
    _text(q['question'])
    if q.get('passage'):_text(q['passage'])
    if q.get('underlined_text'):st.caption('밑줄 표시: '+q['underlined_text'])
    if q.get('table'):st.table(pd.DataFrame(q['table']['rows'],columns=q['table']['headers']))

def _open(aid):
    st.session_state['_academy_exam_id']=aid;st.rerun()

def _close():
    st.session_state.pop('_academy_exam_id',None);st.rerun()

def _result(repo,a,manager=False):
    review=a.get('source_kind')=='review'
    st.subheader('오답 복습 결과' if review else mode_label(a)+' 결과')
    st.caption(a['title']+' · '+stamp(a['submitted_at']).strftime('%Y.%m.%d %H:%M'))
    for col,s in zip(st.columns(len(a['result']['sections'])),a['result']['sections']):
        col.metric(s['name'],f"{s['score']}{'%' if review else '점'}",None if review else '합격' if s['passed'] else '기준 미달')
    if not review:st.caption('과목별 60점 이상 · 통합 시험은 과목별로 판정합니다.')
    wrong=[q for q in a['questions'] if a['answers'].get(str(q['number']))!=q['answer']]
    missing=sum(str(q['number']) not in a['answers'] for q in a['questions'])
    seconds=max(0,int((stamp(a['submitted_at'])-stamp(a['started_at'])).total_seconds()))
    for c,(label,value) in zip(st.columns(4),[('정답',len(a['questions'])-len(wrong)),('오답',len(wrong)-missing),('미응답',missing),('소요 시간',f'{seconds//60}분 {seconds%60}초')]):c.metric(label,value)
    if not manager and wrong:
        if st.button('다시 틀린 문제 풀기' if review else '오답 다시 풀기',type='primary',key='review_'+a['id']):
            rid=st.session_state.setdefault('_academy_exam_start_request',str(uuid4()))
            b=repo.call('review_start',id=rid,parent_id=a['id'])
            st.session_state.pop('_academy_exam_start_request',None);_open(b['id'])
        st.caption('복습 결과는 별도로 저장되며 원래 시험 점수는 바뀌지 않습니다.')
    only=st.toggle('오답·미응답만 보기',value=True,key='exam_wrong_'+a['id'])
    questions=wrong if only else a['questions']
    if not questions:st.success('모든 문제를 맞혔습니다.')
    else:
        key='_academy_exam_result_cursor_'+a['id']
        pos=min(st.session_state.get(key,0),len(questions)-1)
        q=questions[pos];answer=a['answers'].get(str(q['number']))
        with st.container(border=True):
            st.markdown(f"### 문제 {q['number']} · {'미응답' if answer is None else '정답' if answer==q['answer'] else '오답'}")
            _question(q)
            for c in q['choices']:
                marker=' ✓ 정답' if c['number']==q['answer'] else ''
                if c['number']==answer:marker+=' · 내 답'
                _text(f"{c['number']}. {c['text']}{marker}")
            st.divider();st.markdown('**원본 해설**');_text(q['explanation'])
            st.caption(f"출처: {q.get('source_title',a['title'])} · 원본 {q.get('source_number',q['number'])}번")
        x,y,z=st.columns([1,2,1]);y.caption(f'{pos+1} / {len(questions)}문제')
        if x.button('← 이전 문제',disabled=pos==0,key='result_prev_'+a['id']):st.session_state[key]=pos-1;st.rerun()
        if z.button('다음 문제 →',disabled=pos==len(questions)-1,key='result_next_'+a['id']):st.session_state[key]=pos+1;st.rerun()
    if not manager and st.button('시험 목록으로',key='result_back'):_close()

def _history(rows):
    if not rows:st.info('아직 응시 기록이 없습니다. 시험 시작에서 첫 문제를 풀어보세요.')
    page=st.number_input('기록 페이지',min_value=1,max_value=max(1,(len(rows)+9)//10),value=1,step=1,key='_academy_exam_history_page')
    for r in rows[(page-1)*10:page*10]:
        with st.container(border=True):
            st.write(r['title']);st.caption(f"{mode_label(r)} · {stamp(r['started_at']).strftime('%Y.%m.%d %H:%M')} · {'진행 중' if r['status']=='active' else '완료'}")
            if r.get('result'):st.write(' / '.join(f"{s['name']} {s['score']}{'%' if r.get('source_kind')=='review' else '점'}" for s in r['result']['sections']))
            if st.button('이어서 풀기' if r['status']=='active' else '결과·오답 보기',key='history_'+r['id']):_open(r['id'])

def _dashboard(repo,profile):
    # Detach list widget state while the personal detail page hides those widgets.
    for key in ('_academy_exam_search','_academy_exam_filter','_academy_exam_people_page'):
        if key in st.session_state:st.session_state[key]=st.session_state[key]
    st.subheader('조직 학습 현황');st.caption('학습 참여를 확인하고 필요한 복습을 안내하세요.')
    rows=repo.call('team') or [];roster=repo.call('roster') or []
    if len(rows)>=10000:st.warning('최근 10,000건 조회 한도에 도달했습니다. 아래 집계는 조회된 기록 기준이며 전체 통계가 아닙니다.')
    today=datetime.now(KST).date();x,y=st.columns(2)
    dates=x.date_input('조회 기간',(today-timedelta(days=29),today),max_value=today,key='_academy_exam_dates')
    if len(dates)!=2:st.info('시작일과 종료일을 선택해 주세요.');return
    groups={g['id']:g for r in roster for g in r.get('groups',[])}
    org=y.selectbox('조직',['all']+list(groups),format_func=lambda v:'관리 가능한 전체 조직' if v=='all' else groups[v]['name'],key='_academy_exam_org')
    members=[m for m in roster if org=='all' or any(g['id']==org for g in m.get('groups',[]))]
    filtered=[r for r in rows if in_window(r,*dates)]
    people,subjects=summarize(members,filtered)
    participant=sum(bool(p['attempts']) for p in people)
    for c,(label,val) in zip(st.columns(3),[('학습 대상',len(people)),('참여 인원',participant),('미참여',len(people)-participant)]):c.metric(label,val)
    st.markdown('**과목별 최근 모의시험 합격률**')
    if subjects:
        for c,(name,v) in zip(st.columns(len(subjects)),subjects.items()):c.metric(name,f"{v['passed']/v['total']:.0%}",f"{v['passed']} / {v['total']}명")
    else:st.caption('선택 기간에 완료한 모의시험이 없습니다. 미응시를 0점으로 계산하지 않습니다.')
    st.caption('참여: 기간 내 완료 또는 마지막 저장 기록 · 합격률: 기간 내 완료한 모의시험의 개인·과목별 최신 결과. 자유학습과 복습 제외.')
    detail=st.session_state.get('_academy_exam_person')
    person=next((p for p in people if p['id']==detail),None)
    if detail and not person:st.session_state.pop('_academy_exam_person',None);st.session_state.pop('_academy_exam_review',None)
    if person:
        if st.button('← 학습자 목록',key='person_back'):st.session_state['_academy_exam_restore_list']=True;st.session_state.pop('_academy_exam_person',None);st.session_state.pop('_academy_exam_review',None);st.rerun()
        st.subheader(person['display_name']);st.caption(person.get('organization_name') or '소속 미지정')
        mine=person['attempts']
        graph=[{'날짜':stamp(r['submitted_at']),'과목':s['name'],'점수':s['score']} for r in mine if r['mode']=='exam' and r['status']=='submitted' for s in (r.get('result') or {}).get('sections',[])]
        if graph:st.line_chart(pd.DataFrame(graph),x='날짜',y='점수',color='과목')
        st.caption('아래 이력은 선택한 조회 기간 기준입니다.')
        pno=st.number_input('개인 기록 페이지',min_value=1,max_value=max(1,(len(mine)+9)//10),value=1,key='_academy_exam_person_page_'+detail)
        for r in mine[(pno-1)*10:pno*10]:
            cols=st.columns([4,1]);cols[0].write(f"{r['title']} · {mode_label(r)}");cols[0].caption(stamp(r['started_at']).strftime('%Y.%m.%d %H:%M'))
            if cols[1].button('결과 보기',key='manager_'+r['id'],disabled=r['status']!='submitted'):st.session_state['_academy_exam_review']=r['id']
        aid=st.session_state.get('_academy_exam_review')
        if aid and any(r['id']==aid for r in mine):_result(repo,repo.call('get',id=aid),manager=True)
        return
    position=profile.get('position_code')
    level='head_unit' if profile.get('role')=='super_admin' or position=='chief_representative' else 'branch' if position=='division_head' else 'team'
    if org!='all':level={'root':'head_unit','head_unit':'branch','branch':'team','team':'team'}.get(groups[org]['type'],'team')
    if position!='team_leader' or profile.get('role')=='super_admin':
        with st.expander('조직별 비교',expanded=True):
            comparison=[]
            for gid,g in groups.items():
                if g['type']!=level:continue
                subset=[p for p in members if any(x['id']==gid for x in p.get('groups',[]))]
                if not subset:continue
                pp,ss=summarize(subset,filtered);participated=sum(bool(p['attempts']) for p in pp)
                comparison.append({'조직':g['name'],'대상':len(pp),'참여':participated,'참여율':participated/len(pp),**{name+' 합격률':round(100*v['passed']/v['total']) for name,v in ss.items()}})
            if comparison:st.dataframe(comparison,hide_index=True,width='stretch',column_config={'참여율':st.column_config.ProgressColumn(format='percent',min_value=0,max_value=1)})
            else:st.caption('비교할 하위 조직이 없습니다. 아래 학습자 목록을 확인해 주세요.')
    pending=sum(p['below'] for p in people)
    st.info(f"미참여 {len(people)-participant}명 · 최근 모의시험 기준 미달 {pending}명")
    x,y=st.columns([2,1]);query=x.text_input('이름 검색',key='_academy_exam_search');status=y.selectbox('학습 상태',['전체','미참여','학습 중','합격 기준 미달'],key='_academy_exam_filter')
    visible=[p for p in people if query.casefold() in p['display_name'].casefold() and (status=='전체' or status=='합격 기준 미달' and p['below'] or status==p['state'])]
    if not visible:st.info('조건에 맞는 학습자가 없습니다. 검색어나 필터를 변경해 주세요.');return
    # Stable pagination resets when query context changes.
    context=(query,status,org,str(dates));old=st.session_state.get('_academy_exam_page_context')
    if old!=context:st.session_state['_academy_exam_people_page']=1;st.session_state['_academy_exam_page_context']=context
    page=st.number_input('학습자 페이지',min_value=1,max_value=max(1,(len(visible)+9)//10),key='_academy_exam_people_page')
    from .list_position import remember
    remember(st.session_state.pop('_academy_exam_restore_list',False))
    for p in visible[(page-1)*10:page*10]:
        with st.container(border=True,key='exam_person_'+p['id']):
            left,right=st.columns([3,1])
            if left.button(p['display_name']+' →',key='person_'+p['id']):st.session_state['_academy_exam_person']=p['id'];st.rerun()
            left.caption((p.get('organization_name') or '소속 미지정')+' · '+p['state'])
            right.caption('최근 활동 '+(stamp(p['last']).strftime('%m.%d %H:%M') if p['last'] else '없음'))
            st.write(' · '.join(f"{s['name']} {s['score']}점{' · 기준 미달' if not s['passed'] else ''}" for s in p['scores']) or '모의시험 성적 없음')
            if p['state']=='학습 중' and p['last'] and datetime.now(KST)-stamp(p['last'])>timedelta(days=1):st.caption('마지막 활동 후 24시간 이상 · 학습 중단으로 단정하지 않고 확인이 필요합니다.')

def render(auth,owner,permissions,profile):
    st.title('보험시험 CBT')
    if 'academy.assessment' not in permissions:st.warning('시험·평가 이용 권한이 필요합니다.');return
    st.markdown('<style>.exam-prose{font-size:18px;line-height:1.85;overflow-wrap:anywhere;margin:12px 0}</style>',unsafe_allow_html=True)
    repo=Repository(auth,owner)
    try:
        aid=st.session_state.get('_academy_exam_id')
        if aid:
            a=repo.call('get',id=aid)
            if a['status']=='submitted':_result(repo,a)
            else:
                st.markdown('<style>[data-testid="stSidebar"]{display:none}</style>',unsafe_allow_html=True)
                if st.button('← 시험 목록',help='저장된 시험은 이어 풀 수 있으며 제한시간은 계속 흐릅니다.'):_close()
                active(repo,a)
            return
        tabs=['시험 시작','나의 응시 기록']
        if profile.get('role')=='super_admin' or profile.get('position_code') in MANAGERS:tabs.append('조직 학습 현황')
        page=st.radio('메뉴',tabs,horizontal=True,label_visibility='collapsed',key='_academy_exam_page')
        if page=='조직 학습 현황':_dashboard(repo,profile);return
        rows=repo.call('list') or []
        if page=='나의 응시 기록':_history(rows);return
        existing=next((r for r in rows if r['status']=='active'),None)
        if existing:
            st.info('진행 중인 응시가 있습니다. '+existing['title'])
            if st.button('이어서 풀기',type='primary'):_open(existing['id'])
            return
        catalog=repo.call('catalog') or []
        if not catalog:st.info('시험 자료를 준비하고 있습니다.');return
        with st.container(border=True):
            family=st.radio('보험 구분',['손해보험','생명보험'],horizontal=True)
            family_code='life' if family=='생명보험' else 'nonlife'
            choices=[{'id':'random','title':'🎲 랜덤 출제'}]+[e for e in catalog if e['family']==family_code]
            picked=st.selectbox('모의고사',choices,index=1,format_func=lambda e:e['title'])
            track=st.radio('응시 과목',['main','third','combined'],format_func=lambda v:{'main':family,'third':'제3보험','combined':family+' + 제3보험 (통합)'}[v],horizontal=True)
            mode=st.radio('풀이 방식',['exam','practice'],format_func=lambda v:'모의시험 · 50분' if v=='exam' else '자유학습 · 시간 제한 없음',horizontal=True)
            st.caption('과목별 60점 이상 · 원문 문제와 해설 사용 · 랜덤 출제는 동일 문제 중복 제외')
            if st.button('시작하기',type='primary'):
                rid=st.session_state.setdefault('_academy_exam_start_request',str(uuid4()))
                a=repo.call('random_start' if picked['id']=='random' else 'start',id=rid,exam_id=picked['id'],family=family_code,track=track,mode=mode)
                st.session_state.pop('_academy_exam_start_request',None);_open(a['id'])
        st.caption('자유학습을 포함한 점수·오답은 연결된 상위 관리자가 확인할 수 있습니다.')
    except Exception:
        st.error('자료를 불러오거나 저장하지 못했습니다. 입력 상태를 유지하고 다시 시도해 주세요.')
        st.button('다시 시도',key='exam_retry')
