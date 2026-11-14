"""Authenticated bridge for the FP course; DB owns grading and completion."""
from pathlib import Path
import json
import streamlit as st
import streamlit.components.v1 as components
from .onboarding import completion, _team

COURSE_ID='fp-foundation-v2'
_surface=components.declare_component('hwarang_fp_foundation',path=str(Path(__file__).parent/'interactive_frontend'))

def answers_for(lesson,state):
    if not isinstance(state,(dict,list)) or len(json.dumps(state,ensure_ascii=False))>8000:
        raise ValueError('INVALID_STATE')
    result={'_state':state}
    if lesson=='l02':
        result.update(roles=int(state.get('roles')==['이서연 · 엄마','박하준 · 자녀','박하준 · 자녀']),amounts=int(state.get('amounts')==['5만 원','1,000만 원','500만 원']),period=int(state.get('period')=='1'),final=int(state.get('finalRoles')==['0','0','1'] and state.get('finalAmount')=='0' and state.get('finalPeriod')=='0' and state.get('evidence')=='1'))
    elif lesson.startswith('l'):
        result.update(pick=state.get('pick'),transfer=state.get('transfer'))
    elif lesson.startswith('m'):
        result.update({'q'+str(i):v for i,v in enumerate(state.get('answers',[])[:3])})
    return result

def render(auth,owner,permissions,profile,course,rpc):
    from modules.shared.maintenance import guard
    if guard(COURSE_ID,profile):return
    try:rows=rpc(auth,owner,'work_get',p_id=COURSE_ID) or []
    except Exception:st.error('학습 기록을 불러오지 못했습니다. 다시 시도해 주세요.');return
    required={**course,'lessons':[l for l in course['lessons'] if not l.get('optional')]}
    done,approved,graduated=completion(required,rows)
    mode=st.radio('학습 화면',['나의 학습','조직 학습·피드백'],horizontal=True,key='fp_mode') if profile.get('role')=='super_admin' else '나의 학습'
    if mode!='나의 학습':_team(auth,owner,required,rpc);return
    classroom(auth,owner,course,rpc,rows)

@st.fragment
def classroom(auth,owner,course,rpc,initial):
    key='fp_wire_'+str(owner)
    wire=st.session_state.setdefault(key,dict(rows=initial,ack=None,error='',reload=False))
    required={**course,'lessons':[l for l in course['lessons'] if not l.get('optional')]}
    done,approved,graduated=completion(required,wire['rows'])
    st.caption(f'필수 학습 {done}/18 · 종합 실습 승인 {approved}/3 · '+('과정 수료' if graduated else '학습 진행 중'))
    event=_surface(**wire,key='fp_surface_'+str(owner),default=None)
    if not event or event.get('id')==wire['ack']:return
    wire.update(ack=event.get('id'),error='',reload=False)
    try:
        if event.get('action')=='reload':wire['reload']=True
        elif event.get('action') in ('save','submit'):
            lesson=event.get('lesson'); allowed={l['id'] for l in course['lessons']}
            if lesson not in allowed:raise ValueError('INVALID_LESSON')
            normalized=answers_for(lesson,event.get('state'))
            current=next((w for w in (rpc(auth,owner,'work_get',p_id=COURSE_ID) or []) if w['lesson_id']==lesson),{})
            if current.get('version',0)!=event['version'] and current.get('answers')==normalized and current.get('status')==('submitted' if event['action']=='submit' else 'draft'):
                result={'passed':event['action']=='submit'}
            else:
                result=rpc(auth,owner,'interactive_save',p_id=COURSE_ID,p_revision=course['revision'],p_lesson=lesson,p_version=event['version'],p_answers=normalized,p_submit=event['action']=='submit')
            if event['action']=='submit' and not result.get('passed'):wire['error']='필수 활동이 아직 완료되지 않았습니다. 선택과 근거를 다시 확인해 주세요.'
        else:raise ValueError('INVALID_ACTION')
        wire['rows']=rpc(auth,owner,'work_get',p_id=COURSE_ID) or []
    except Exception as exc:
        wire['error']=('다른 화면에서 기록이 변경되었습니다. 저장된 기록 다시 불러오기를 눌러 확인해 주세요.' if 'WORK_CHANGED' in str(exc) else '저장 결과를 확인하지 못했습니다. 화면의 선택은 유지됩니다. 저장된 기록을 다시 불러와 확인해 주세요.')
    st.rerun(scope='fragment')
