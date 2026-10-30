"""30-day learning workspace; authorization and grading remain server-side."""
from html import escape
from pathlib import Path
import json
import streamlit as st

COURSE_ID = 'newhire-30-v1'
STATUS = {'draft':'작성 중','submitted':'학습 완료','approved':'검토 완료','revision_requested':'보완 필요'}
WEEKS = ['전체', '1주 · 업무와 상담 기초', '2주 · 연락과 계약 확인', '3주 · 보장 이해와 분석', '4주 · 현장 실무와 종합 실습']

def completion(course, works):
    """Never count old/read-only records or rejected work as certification."""
    valid={w['lesson_id']:w for w in works if w.get('revision')==course['revision']}
    lessons=course['lessons']
    done=sum(valid.get(l['id'],{}).get('status') in ('submitted','approved') for l in lessons)
    required=[l for l in lessons if l.get('mentor_required')]
    approved=sum(valid.get(l['id'],{}).get('status')=='approved' for l in required)
    return done,approved, bool(lessons) and done==len(lessons) and approved==len(required)

def _styles():
    st.markdown('''<style>
    .edu-hero{background:#eef4fb;border:1px solid #dbe5ef;border-radius:18px;padding:22px 24px;margin:0 0 20px;color:#193858}
    .edu-hero h2{font-size:26px;margin:0 0 8px}.edu-hero p{margin:0;font-size:16px;line-height:1.65}
    .edu-flow{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:20px 0}
    .edu-node{padding:16px;border:1px solid #dae4ed;border-radius:12px;background:#f7fafc;font-size:17px;color:#193858}
    .edu-node small{display:block;color:#62778c;font-size:12px;margin-bottom:6px}
    .edu-case{border-left:4px solid #3172b2;background:#f2f7fc;padding:18px;margin:16px 0;font-size:19px;line-height:1.65}
    @media(max-width:640px){.edu-hero{padding:18px}.edu-hero h2{font-size:23px}.edu-flow{grid-template-columns:1fr 1fr}.edu-node{font-size:16px;padding:12px}}
    </style>''',unsafe_allow_html=True)

def _notice_error(exc):
    msg=str(exc)
    if 'WORK_CHANGED' in msg or 'CONTENT_CHANGED' in msg:
        st.error('다른 화면에서 기록이 변경됐습니다. 아래에서 최신 기록을 다시 불러와 주세요.')
    elif 'PRACTICE_TOO_SHORT' in msg: st.error('실습 내용을 30자 이상 작성해 주세요.')
    else: st.error('저장하지 못했습니다. 입력 내용은 이 화면에 남아 있습니다. 잠시 후 다시 시도해 주세요.')

def _reload(owner):
    for k in list(st.session_state):
        if k.startswith('edu_input_'+str(owner)+'_'): del st.session_state[k]
    st.rerun()

def render(auth,owner,permissions,profile,course,rpc):
    _styles()
    flash=st.session_state.pop('edu_flash_'+str(owner),None)
    if flash:st.success(flash)
    st.markdown('<div class="edu-hero"><h2>신입 공통 과정 · 첫 30일</h2><p>하루 한 가지를 배우고, 내 말로 설명하고, 현장에서 연습하세요.</p></div>',unsafe_allow_html=True)
    st.caption('실습 답변과 진도는 연결된 상위 관리자에게 공개됩니다. 실제 고객의 이름·연락처·진료 정보는 입력하지 마세요.')
    mode=st.radio('학습 화면',['나의 30일','조직 학습 현황'] if profile.get('role')=='super_admin' or profile.get('position_code') in ('team_leader','deputy_branch_manager','branch_manager','division_head','chief_representative') else ['나의 30일'],horizontal=True,key='edu_view_'+str(owner))
    if mode=='조직 학습 현황':
        _team(auth,owner,course,rpc);return
    try: works=rpc(auth,owner,'work_get',p_id=course['id']) or []
    except Exception:
        st.error('학습 기록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');return
    done,approved,graduated=completion(course,works)
    a,b,c=st.columns(3);a.metric('학습 완료',f'{done} / {len(course["lessons"])}');b.metric('주간 실습 검토',f'{approved} / 4');c.metric('과정 상태','수료' if graduated else '학습 중' if works else '시작 전')
    st.progress(done/len(course['lessons']))
    if graduated:st.success('첫 30일 공통 과정을 수료했습니다. 아래에서 다음 관심 분야와 60·90일 목표를 정리해 보세요.')
    with st.expander('학습 방법과 수료 기준'):
        st.write('기본 30분: 개념 8분, 사례 7분, 실습 10분, 확인 5분. 집중 60분: 자료 읽기 15분과 동료 역할극 15분을 추가합니다. 일차는 권장 순서이며 일정에 맞게 앞뒤 수업을 열 수 있습니다.')
        st.write('30개 수업의 확인 문제를 맞히고 실습을 제출한 뒤, 7·14·21·30일차 실습을 상위 관리자에게 검토받으면 수료합니다. 보완 요청을 받으면 수정 후 다시 제출하세요. 오답은 해설을 읽고 재시도할 수 있습니다.')
        st.caption('기존 시범 과정의 읽기 기록은 그대로 유지합니다. 새 과정은 문제와 실습 기준이 추가되어 별도로 기록합니다. 회사 위촉 및 보험 모집 자격은 별도입니다.')
    by_id={w['lesson_id']:w for w in works}
    next_lesson=next((l for l in course['lessons'] if by_id.get(l['id'],{}).get('status') not in ('submitted','approved')),course['lessons'][-1])
    if st.button('이어서 학습 · '+next_lesson['title'],type='primary',use_container_width=True):
        st.session_state['edu_week_'+str(owner)]='전체'
        st.session_state['edu_lesson_'+str(owner)]=next_lesson['id'];st.rerun()
    week=st.selectbox('주차',WEEKS,key='edu_week_'+str(owner))
    idx=WEEKS.index(week)
    lessons=[l for l in course['lessons'] if idx==0 or min((l['day']-1)//7+1,4)==idx]
    ids=[l['id'] for l in lessons];selection_key='edu_lesson_'+str(owner)
    if st.session_state.get(selection_key) not in ids:st.session_state[selection_key]=ids[0]
    selected_id=st.selectbox('학습할 일차',ids,format_func=lambda lid:next(f"{l['day']:02}일 · {l['title']} · {STATUS.get(by_id.get(lid,{}).get('status'),'시작 전')}" for l in lessons if l['id']==lid),key=selection_key)
    lesson=next(l for l in lessons if l['id']==selected_id)
    _lesson(auth,owner,course,lesson,by_id.get(selected_id,{}),rpc)
    if lesson['day']<30:
        def advance():
            st.session_state['edu_week_'+str(owner)]='전체'
            st.session_state[selection_key]=f"d{lesson['day']+1:02}"
        st.button('다음 일차 보기 →',key='edu_next',on_click=advance)
    if st.button('최신 기록 다시 불러오기',key='edu_reload'): _reload(owner)
    with st.expander('공통 과정 이후 · 60일과 90일'):
        st.markdown('**31~60일**에는 보장분석·청구, 가족·실손, 상담·고객관리 중 관심 분야를 정하고 선배와 사례를 검토합니다. **61~90일**에는 선택한 분야의 상담을 진행하고 결과와 다음 행동을 피드백받습니다.')
        st.caption('후속 심화 과정은 이번 공통 과정의 수료 항목에 포함되지 않습니다. 30일차 실습에 희망 분야와 목표를 남겨 주세요.')

def _lesson(auth,owner,course,l,w,rpc):
    st.subheader(f"{l['day']}일차 · {l['title']}")
    duration=st.radio('오늘의 학습 시간',['30분 기본','60분 집중'],horizontal=True,key='edu_duration_'+str(owner))
    st.markdown('<div class="edu-case">'+escape(l['scenario'])+'</div>',unsafe_allow_html=True)
    st.markdown('<div class="edu-flow">'+''.join(f'<div class="edu-node"><small>{i+1:02}</small>{escape(s)}</div>' for i,s in enumerate(l['flow']))+'</div>',unsafe_allow_html=True)
    st.markdown(l['body'])
    if l.get('image_b64'):
        import base64
        st.image(base64.b64decode(l['image_b64']),caption=l.get('image_caption','학습 참고 그림'),use_container_width=True)
    if l.get('case_reading'):
        with st.expander('사례를 자세히 읽기',expanded=True):st.markdown(l['case_reading'])
    if duration=='60분 집중':st.info(l['deepening'])
    with st.expander('학습 자료와 기준일'):
        for src in l['sources']:st.caption(src)
        st.caption('내용 확인: '+course['updated_on'])
        if l.get('reference_url'):st.link_button('공식 자료 확인',l['reference_url'])
    st.markdown('#### 직접 해보기')
    st.write(l['practice'])
    if l.get('mentor_required'):st.info('이번 실습은 상위 관리자의 검토가 필요한 주간 실습입니다.')
    if w.get('feedback'):
        st.markdown('**선배 피드백**')
        for k,title in [('good','잘한 점'),('improve','보완할 점'),('next','다음 연습')]:st.write(title+' · '+str(w['feedback'].get(k,'')))
    locked=w.get('status') in ('submitted','approved')
    if locked:
        st.success('검토 완료' if w['status']=='approved' else '제출했습니다. 주간 실습은 관리자 검토 후 수료에 반영됩니다.' if l.get('mentor_required') else '오늘의 학습을 완료했습니다.')
        st.write(w.get('practice',''))
        for q in l['quiz']:st.caption('이해 확인 · '+q['explanation'])
        return
    prefix=f"edu_input_{owner}_{course['id']}_{course['revision']}_{l['id']}_{w.get('version',0)}"
    with st.form(prefix):
        practice=st.text_area('내 설명과 실습 기록',value=w.get('practice',''),height=180,max_chars=5000,key=prefix+'_practice',placeholder='가상 사례로 작성하세요. 작성 중 저장하면 다음에 이어서 쓸 수 있습니다.')
        answers={}
        for q in l['quiz']:
            values=[None]+list(range(len(q['options'])))
            old=w.get('answers',{}).get(q['id']);old=int(old) if str(old).isdigit() else None
            answers[q['id']]=st.radio(q['question'],values,index=values.index(old) if old in values else 0,format_func=lambda x:'선택해 주세요' if x is None else q['options'][x],key=prefix+'_'+q['id'])
        read=st.checkbox('학습 내용을 읽고, 실제로 수행한 실습과 앞으로 할 계획을 구분해 작성했습니다.')
        left,right=st.columns(2)
        save=left.form_submit_button('작성 중 저장',use_container_width=True)
        submit=right.form_submit_button('확인하고 학습 완료',type='primary',use_container_width=True)
    if save or submit:
        if submit and (not read or any(v is None for v in answers.values()) or len(practice.strip())<30):
            st.warning('확인 문제에 답하고 실습을 30자 이상 작성한 뒤 읽기 확인을 체크해 주세요.');return
        try:
            result=rpc(auth,owner,'work_save',p_id=course['id'],p_revision=course['revision'],p_lesson=l['id'],p_version=w.get('version',0),p_answers=answers,p_practice=practice,p_submit=submit)
            if submit and not result.get('passed'):
                st.warning('확인 문제를 다시 살펴보세요. 입력한 실습은 그대로 남아 있습니다.')
                for q in l['quiz']:st.info(q['explanation'])
            else:
                st.session_state['edu_flash_'+str(owner)]='학습을 완료했습니다.' if submit else '작성 중인 내용을 저장했습니다.'
                st.rerun()
        except Exception as exc:_notice_error(exc)

def _team(auth,owner,course,rpc):
    try: rows=rpc(auth,owner,'team',p_id=course['id']) or []
    except Exception:st.error('조직 학습 현황을 불러오지 못했습니다.');return
    st.caption('현재 조직 연결에 따라 조회 가능한 구성원만 표시합니다. AI 상담 자유연습 기록은 이 화면에 포함하지 않습니다.')
    if not rows:st.info('조회 가능한 구성원이 없습니다.');return
    org=st.selectbox('소속',['전체']+sorted({r['organization'] for r in rows}))
    state=st.selectbox('학습 상태',['전체','검토 대기','시작 전','학습 중','수료'])
    def label(r):return '수료' if r['completed']==30 and r['approved']==4 else '학습 중' if r['last_activity'] else '시작 전'
    scope=[r for r in rows if org=='전체' or r['organization']==org]
    a,b,c=st.columns(3);a.metric('구성원',len(scope));b.metric('검토 대기',sum(r['waiting'] for r in scope));c.metric('수료',sum(label(r)=='수료' for r in scope))
    filtered=[r for r in scope if state=='전체' or (r['waiting']>0 if state=='검토 대기' else label(r)==state)]
    st.dataframe([{'이름':r['display_name'],'소속':r['organization'],'학습 완료':f"{r['completed']}/30",'주간 검토':f"{r['approved']}/4",'검토 대기':r['waiting'],'상태':label(r)} for r in filtered],hide_index=True,use_container_width=True)
    if not filtered:st.info('조건에 맞는 구성원이 없습니다.');return
    target=st.selectbox('상세 기록을 볼 구성원',filtered,format_func=lambda r:r['display_name']+' · '+r['organization'])
    try: works=rpc(auth,owner,'work_get',p_id=course['id'],p_target=target['user_id']) or []
    except Exception:st.error('구성원 기록을 불러오지 못했습니다.');return
    by_id={l['id']:l for l in course['lessons']}
    for w in works:
        l=by_id.get(w['lesson_id'])
        if not l:continue
        with st.expander(f"{l['day']}일 · {l['title']} · {STATUS[w['status']]}",expanded=w['status']=='submitted' and l.get('mentor_required',False)):
            st.write(w['practice']);st.caption(f"확인 문제: {w.get('score') if w.get('score') is not None else '미제출'}")
            if w.get('feedback'):
                for k,t in [('good','잘한 점'),('improve','보완할 점'),('next','다음 연습')]:st.write(t+' · '+str(w['feedback'].get(k,'')))
            if w['status']!='submitted':continue
            key=f"edu_review_{owner}_{target['user_id']}_{l['id']}_{w['version']}"
            with st.form(key):
                good=st.text_area('잘한 점',max_chars=600)
                improve=st.text_area('보완할 점',max_chars=600)
                nxt=st.text_area('다음 연습',max_chars=600)
                decision=st.radio('검토 결과',['검토 완료','보완 요청'],horizontal=True)
                sent=st.form_submit_button('피드백 저장',type='primary')
            if sent:
                if not all(x.strip() for x in [good,improve,nxt]):st.warning('피드백 세 항목을 모두 작성해 주세요.');continue
                try:
                    rpc(auth,owner,'work_review',p_target=target['user_id'],p_id=course['id'],p_revision=course['revision'],p_lesson=l['id'],p_version=w['version'],p_approve=decision=='검토 완료',p_feedback={'good':good,'improve':improve,'next':nxt});st.rerun()
                except Exception as exc:_notice_error(exc)
