"""CBT: one question, server deadline, durable answers and original review text."""
from uuid import uuid4
import html
import streamlit as st
import pandas as pd
from .repository import Repository

MANAGERS={'team_leader','deputy_branch_manager','branch_manager','division_head','chief_representative'}

def _text(text):
    st.markdown('<div class="exam-text">'+html.escape(str(text)).replace('\n','<br>')+'</div>',unsafe_allow_html=True)

def _question(q):
    _text(q['question'])
    if q.get('passage'): _text(q['passage'])
    if q.get('underlined_text'): st.caption('밑줄 표시: '+q['underlined_text'])
    if q.get('table'):
        table=q['table']; st.table(pd.DataFrame(table['rows'],columns=table['headers']))

def _put(repo,a,**changes):
    payload={k:a[k] for k in ('id','revision','answers','flags','cursor')};payload.update(changes)
    try:
        saved=repo.call('save',**payload)
        st.session_state['_academy_exam_attempt']=saved
        st.session_state.pop('_academy_exam_error',None)
        return saved
    except Exception as exc:
        # Keep visible pending input and never acknowledge a failed write.
        st.session_state['_academy_exam_pending']=payload
        st.session_state['_academy_exam_error']='답안 저장을 확인하지 못했습니다. 재시도하거나 저장된 답안을 다시 불러오세요.'
        return None

def _answer(repo,a,key,number):
    answers=dict(a['answers']);value=st.session_state.get(key)
    if value is None:answers.pop(str(number),None)
    else:answers[str(number)]=value
    _put(repo,a,answers=answers)

def _flag(repo,a,key,number):
    flags=set(a['flags'])
    if st.session_state.get(key):flags.add(number)
    else:flags.discard(number)
    _put(repo,a,flags=sorted(flags))

def _result(a,manager=False):
    st.subheader('시험 결과' if a['mode']=='exam' else '자유학습 결과')
    for col,s in zip(st.columns(len(a['result']['sections'])),a['result']['sections']):
        col.metric(s['name'],f"{s['score']}점",'합격' if s['passed'] else '불합격')
    st.caption('합격기준 60점 · 통합 응시는 과목별로 판정합니다.')
    only=st.checkbox('오답·미응답만 보기',value=True,key='exam_wrong_'+a['id'])
    for q in a['questions']:
        answer=a['answers'].get(str(q['number']));correct=answer==q['answer']
        if only and correct:continue
        with st.expander(f"{q['number']}번 · {'정답' if correct else '미응답' if answer is None else '오답'}"):
            _question(q)
            for c in q['choices']: _text(f"{'①②③④'[c['number']-1]} {c['text']}")
            st.write(f"내 답: {answer if answer else '미응답'} · 정답: {q['answer']}")
            st.markdown('**원본 해설**');_text(q['explanation'])
    if st.button('상세 닫기' if manager else '시험 목록으로',key='exam_back_'+a['id']):
        if manager:
            st.session_state.pop('_academy_exam_review',None);st.rerun()
        st.session_state.pop('_academy_exam_attempt',None);st.session_state.pop('_academy_exam_id',None);st.rerun()

@st.fragment(run_every='5s')
def _active(repo,initial):
    a=st.session_state.get('_academy_exam_attempt') or initial
    try:
        current=repo.call('get',id=a['id'])
        if current['revision']!=a['revision']:
            # A concurrent tab changed the attempt: recreate input widgets from saved state.
            for key in list(st.session_state):
                if key.startswith('_academy_exam_choice_') or key.startswith('_academy_exam_flag_'):del st.session_state[key]
        a=current;st.session_state['_academy_exam_attempt']=a
    except Exception:
        st.error('연결을 확인하지 못했습니다. 저장되지 않은 답안이 있을 수 있습니다. 연결 복구 후 다시 불러오세요.');return
    if a['status']=='submitted':st.rerun()
    pending=st.session_state.get('_academy_exam_pending')
    if pending and pending['id']==a['id']:
        st.error(st.session_state.get('_academy_exam_error','저장 대기 중인 답안이 있습니다.'))
        x,y=st.columns(2)
        if x.button('저장 재시도'):
            # Do not overwrite a newer revision from another tab.
            if pending['revision']!=a['revision']:st.warning('다른 화면에서 답안이 변경되었습니다. 저장된 답안을 다시 불러오세요.')
            elif _put(repo,a,**{k:pending[k] for k in ('answers','flags','cursor')}):
                st.session_state.pop('_academy_exam_pending',None);st.rerun()
        if y.button('저장된 답안 다시 불러오기'):
            st.session_state.pop('_academy_exam_pending',None)
            for key in list(st.session_state):
                if key.startswith(('_academy_exam_choice_','_academy_exam_flag_')):del st.session_state[key]
            st.rerun()
        return
    questions=a['questions'];pos=a['cursor'];q=questions[pos];number=q['number']
    top=st.columns([3,1]);top[0].subheader(a['title'])
    seconds=a.get('remaining_seconds');top[1].metric('남은 시간',f'{int(seconds)//60:02}:{int(seconds)%60:02}' if seconds is not None else '자유학습')
    st.caption(f"{pos+1} / {len(questions)} 문항 · 응답 {len(a['answers'])}개 · 미응답 {len(questions)-len(a['answers'])}개")
    main,side=st.columns([4,1])
    with main:
        st.markdown(f'### 문제 {number}')
        _question(q)
        options=[c['number'] for c in q['choices']];labels={c['number']:f"{'①②③④'[c['number']-1]} {c['text']}" for c in q['choices']}
        key=f'_academy_exam_choice_{a["id"]}_{number}'
        if key not in st.session_state:st.session_state[key]=a['answers'].get(str(number))
        st.radio('답안 선택',options,index=None,format_func=lambda v:labels[v],key=key,on_change=_answer,args=(repo,a,key,number))
        flagkey=f'_academy_exam_flag_{a["id"]}_{number}'
        if flagkey not in st.session_state:st.session_state[flagkey]=number in a['flags']
        st.checkbox('다시 확인할 문제',key=flagkey,on_change=_flag,args=(repo,a,flagkey,number))
        left,right=st.columns(2)
        if left.button('← 이전',disabled=pos==0):
            if _put(repo,a,cursor=pos-1):st.rerun()
        if right.button('다음 →',disabled=pos==len(questions)-1):
            if _put(repo,a,cursor=pos+1):st.rerun()
        st.caption('답안 선택 즉시 저장 · 연결이 끊겨도 시험 시간은 계속 흐릅니다.')
    with side:
        st.markdown('**문항 이동**');st.caption('● 응답 · ★ 다시 확인')
        for start in range(0,len(questions),4):
            for col,item in zip(st.columns(4),questions[start:start+4]):
                n=item['number'];label=f'{n}'+('★' if n in a['flags'] else '●' if str(n) in a['answers'] else '')
                if col.button(label,key=f'exam_jump_{a["id"]}_{n}',type='primary' if n==number else 'secondary'):
                    if _put(repo,a,cursor=questions.index(item)):st.rerun()
    st.divider()
    confirm=st.checkbox(f"미응답 {len(questions)-len(a['answers'])}개를 확인했으며 제출하겠습니다.",key='_academy_exam_confirm_'+a['id'])
    if st.button('시험 종료·제출',type='primary',disabled=not confirm):
        try:st.session_state['_academy_exam_attempt']=repo.call('submit',id=a['id'],revision=a['revision']);st.rerun()
        except Exception:st.error('제출 결과를 확인하지 못했습니다. 다시 확인해 주세요. 중복 제출은 한 번만 처리됩니다.')

def _dashboard(repo):
    rows=repo.call('team') or [];roster=repo.call('roster') or []
    st.subheader('조직 학습 현황')
    st.caption('자유학습과 모의시험의 점수·오답을 연결된 상위 관리자가 확인합니다. 최근 1,000건 기준입니다.')
    level=st.radio('집계 단위',['team','branch','head_unit'],format_func=lambda v:{'team':'팀별','branch':'지점별','head_unit':'본부별'}[v],horizontal=True)
    groups={g['id']:g['name'] for r in roster for g in r.get('groups',[]) if g['type']==level}
    org=st.selectbox('조직',['all']+list(groups),format_func=lambda v:'전체' if v=='all' else groups[v])
    members=[r for r in roster if org=='all' or any(g['id']==org for g in r.get('groups',[]))]
    ids={r['id'] for r in members};rows=[r for r in rows if r['user_id'] in ids]
    finished=[r for r in rows if r['status']=='submitted'];active={r['user_id'] for r in rows}
    cols=st.columns(4)
    for c,(label,val) in zip(cols,[('학습 대상',len(members)),('학습 참여',len(active)),('미참여',len(ids-active)),('완료 응시',len(finished))]):c.metric(label,val)
    report=[]
    for r in members:
        mine=[x for x in rows if x['user_id']==r['id']];done=[x for x in mine if x['status']=='submitted']
        scores=[s['score'] for x in done for s in (x.get('result') or {}).get('sections',[])]
        report.append({'이름':r['display_name'],'조직':r.get('organization_name'),'응시':len(mine),'완료':len(done),'평균 점수':round(sum(scores)/len(scores),1) if scores else None,'합격 응시':sum(bool(x['result']['passed']) for x in done)})
    st.dataframe(report,width='stretch',hide_index=True)
    if rows:
        selected=st.selectbox('개인별 응시 상세',rows,format_func=lambda r:f"{r['display_name']} · {r['title']} · {'자유학습' if r['mode']=='practice' else '모의시험'} · {r['started_at'][:10]}")
        if st.button('점수·오답 열기'):
            a=repo.call('get',id=selected['id'])
            if a['status']!='submitted':st.info('진행 중인 시험입니다. 제출 후 점수와 오답을 확인할 수 있습니다.')
            else:st.session_state['_academy_exam_review']=a
        a=st.session_state.get('_academy_exam_review')
        if a and a['id']==selected['id']:
            # Recheck current permissions rather than trusting a previously cached result.
            _result(repo.call('get',id=a['id']),manager=True)

def render(auth,owner,permissions,profile):
    st.title('보험시험 CBT')
    if 'academy.assessment' not in permissions:st.warning('시험·평가 이용 권한이 필요합니다.');return
    st.markdown('''<style>.exam-text{font-size:18px;line-height:1.9;white-space:normal;overflow-wrap:anywhere;margin:14px 0}div[data-testid="stRadio"] label p{font-size:17px;line-height:1.8}@media(max-width:700px){.exam-text{font-size:17px}}</style>''',unsafe_allow_html=True)
    repo=Repository(auth,owner)
    try:
        aid=st.session_state.get('_academy_exam_id')
        if aid:
            a=repo.call('get',id=aid);st.session_state['_academy_exam_attempt']=a
            if a['status']=='submitted':_result(a)
            else:_active(repo,a)
            return
        tabs=['시험 시작','나의 응시 기록']
        if profile.get('role')=='super_admin' or profile.get('position_code') in MANAGERS:tabs.append('조직 학습 현황')
        page=st.radio('메뉴',tabs,horizontal=True,label_visibility='collapsed')
        if page=='조직 학습 현황':_dashboard(repo);return
        rows=repo.call('list') or []
        if page=='나의 응시 기록':
            if not rows:st.info('아직 응시 기록이 없습니다.')
            for r in rows:
                label=f"{r['title']} · {'자유학습' if r['mode']=='practice' else '모의시험'} · {'진행 중' if r['status']=='active' else '완료'} · {r['started_at'][:10]}"
                if st.button(label,key='exam_history_'+r['id']):st.session_state['_academy_exam_id']=r['id'];st.rerun()
            return
        active=next((r for r in rows if r['status']=='active'),None)
        if active:
            st.info('진행 중인 응시가 있습니다.')
            if st.button('이어서 풀기',type='primary'):st.session_state['_academy_exam_id']=active['id'];st.rerun()
            return
        catalog=repo.call('catalog') or []
        if not catalog:st.info('시험 자료를 준비하고 있습니다.');return
        family=st.radio('문제집 구분',['손해보험','생명보험'],horizontal=True)
        choices=[e for e in catalog if e['family']==('life' if family=='생명보험' else 'nonlife')]
        picked=st.selectbox('모의고사',choices,format_func=lambda e:e['title'])
        track=st.radio('응시 과목',['main','third','combined'],format_func=lambda v:{'main':family,'third':'제3보험','combined':family+' + 제3보험 (통합)'}[v],horizontal=True)
        mode=st.radio('풀이 방식',['exam','practice'],format_func=lambda v:'모의시험 · 50분' if v=='exam' else '자유학습 · 시간 제한 없음',horizontal=True)
        st.info('원본 문제·보기 순서로 응시합니다. 합격기준은 과목별 60점입니다. 제출 후 원본 정답과 해설을 확인할 수 있습니다.')
        st.caption('자유학습을 포함한 점수·오답은 연결된 팀장·부지점장·지점장·본부장·총괄이 확인할 수 있습니다.')
        if st.button('시작하기',type='primary'):
            # Retain the request ID if the response is lost.
            rid=st.session_state.setdefault('_academy_exam_start_request',str(uuid4()))
            a=repo.call('start',id=rid,exam_id=picked['id'],track=track,mode=mode)
            st.session_state['_academy_exam_id']=a['id'];st.session_state.pop('_academy_exam_start_request',None);st.rerun()
    except Exception:
        st.error('시험 저장소에 연결하지 못했습니다. 연결과 시험 기능 설정을 확인한 후 다시 시도해 주세요.')
        st.button('다시 확인',key='exam_retry')
