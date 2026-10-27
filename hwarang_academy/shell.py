"""One native sidebar and data-backed home across Academy routes."""
import streamlit as st
from modules.shared import brand_ui as ui

def go(surface):
    st.session_state['_academy_surface']=surface
    st.session_state['_studio_open']=False
    if surface in ('simulator','history'):
        st.session_state['_studio_open']=True
        st.session_state['_studio_history_open']=surface=='history'
        st.session_state['_studio_owner']=st.session_state.get('_academy_model_owner')
        if surface=='history':
            st.session_state.pop('_studio_state',None)
            st.session_state.pop('_studio_preview',None)

def course_open(course_id=None):
    st.session_state['_academy_course_id']=course_id
    go('courses')

def shell(profile,permissions):
    ui.apply()
    ui.identity('ACADEMY',profile)
    current=st.session_state.get('_academy_surface','academy')
    with st.sidebar:
        st.markdown('### 화랑 ACADEMY')
        st.caption('배움과 상담 연습')
        for key,label,permission in [('academy','아카데미 홈',None),('exams','보험시험 CBT','academy.assessment'),('courses','교육 과정',None),('library','교육자료실','academy.library'),('my_learning','나의 학습','academy.my_learning'),('simulator','상담 연습','academy.simulator'),('history','상담 기록','academy.simulator')]:
            if not permission or permission in permissions:
                st.button(label,key='academy_nav_'+key,type='primary' if current==key else 'secondary',on_click=go,args=(key,),use_container_width=True)
        st.caption('Planned & Built by 박병선 팀장')

def home(auth,owner,permissions,profile,credit_status):
    from hwarang_academy.education.ui import rpc
    from hwarang_academy.studio.repository import Repository
    st.title('오늘의 배움을 상담으로 이어가세요')
    st.caption('교육과 상담 연습을 한곳에서 시작하세요.')
    with st.container(key='brand_pair_wrap'):
        left,right=st.columns(2)
        with left, st.container(key='brand_feature_learning'):
            st.subheader('나의 교육')
            try:
                courses=[c for c in (rpc(auth,owner,'catalog') or []) if c.get('kind')=='course' and c.get('published') and c.get('permission') in permissions]
                active=next((c for c in courses if 0<len((c.get('progress') or {}).get('completed_lessons') or [])<len(c.get('lessons') or [])),None)
                if active:
                    done=set((active.get('progress') or {}).get('completed_lessons') or [])
                    lessons=active.get('lessons') or []
                    st.write(active['title']);st.progress(len(done)/len(lessons),text=f'{len(done)}/{len(lessons)} 학습 완료')
                    next_lesson=next((l for l in lessons if l['id'] not in done),None)
                    if next_lesson:st.caption('다음 학습 · '+next_lesson['title'])
                    st.button('이어서 학습하기 →',on_click=course_open,args=(active['id'],),type='primary')
                else:
                    completed=sum(bool(c.get('lessons')) and len((c.get('progress') or {}).get('completed_lessons') or [])>=len(c['lessons']) for c in courses)
                    st.write(f'{completed}개 과정을 완료했어요.' if completed else '첫 교육 과정을 시작해 보세요.')
                    st.caption('필요한 주제를 선택해 차근차근 학습하세요.' if courses else '현재 이용 가능한 교육 과정이 없습니다.')
                    st.button('교육 과정 둘러보기 →',on_click=course_open,type='primary')
            except Exception:
                st.warning('교육 진도를 불러오지 못했습니다.')
                st.button('다시 확인',key='academy_home_retry')
        with right, st.container(key='brand_feature_practice'):
            st.subheader('상담 연습')
            if 'academy.simulator' not in permissions:
                st.caption('상담 연습 이용 권한이 필요합니다.')
            else:
                try:
                    rows=Repository(auth,owner).rows() or []
                    active=next((x for x in rows if str(x.get('ended')).lower() not in ('true','1')),None)
                    st.write('진행 중인 상담이 있어요.' if active else '고객과의 대화를 미리 연습해 보세요.')
                    st.caption('저장된 상담을 이어서 진행할 수 있어요.' if active else '상담 상황을 선택하고 연습을 시작하세요.')
                    if st.button('이어서 연습하기 →' if active else '상담 연습 시작 →',type='primary'):
                        if active:st.session_state['_studio_state']=Repository(auth,owner).load(active['id'])
                        else:
                            st.session_state.pop('_studio_state',None)
                            st.session_state.pop('_studio_preview',None)
                        go('simulator');st.rerun()
                except Exception:st.warning('상담 기록을 불러오지 못했습니다.')
                if credit_status:
                    st.caption(f'남은 크레딧 {credit_status.available_credits:,} · 음성 {credit_status.voice_available_seconds//60}분')
                else:st.caption('이용량을 불러오지 못했습니다.')
    st.subheader('학습 바로가기')
    with st.container(key='brand_grid_academy',horizontal=True):
        for key,title,desc,icon,permission in [('exams','보험시험 CBT','모의시험·자유학습과 오답 복기','▦','academy.assessment'),('courses','교육 과정','필요한 주제를 골라 학습하세요.','▤',None),('library','교육자료실','교육 자료를 찾아 확인하세요.','▥','academy.library'),('my_learning','나의 학습','학습 진도와 완료 과정을 확인하세요.','✓','academy.my_learning'),('history','상담 기록','이전 상담과 복기 내용을 확인하세요.','◷','academy.simulator')]:
            if not permission or permission in permissions:ui.card(title,desc,icon,'brand_tile_academy_'+key,go,(key,))

def legacy_history(auth,owner):
    from hwarang_academy.history import TrainingHistory
    from hwarang_academy.service import AppState
    with st.expander('기존 상담 훈련 기록'):
        try:
            client=TrainingHistory(auth,owner);rows=client.rows()
            if not rows:st.caption('저장된 기존 훈련 기록이 없습니다.');return
            row=st.selectbox('훈련 기록',rows,format_func=lambda x:f"{x.get('scenario_id','')} · {x.get('updated_at','')[:16]}")
            if st.button('기존 기록 열기'):
                session,version=client.load(row['id'])
                st.session_state['_academy_model']=AppState(session=session,independent=True,selection=session.scenario_id,mode=session.mode)
                st.session_state['_academy_route']=(st.query_params.get('view')=='simulator',st.query_params.get('scenario','C07-S01'))
                st.session_state['_academy_history_state']={'user_id':owner,'available':True,'rows':rows,'summary':{},'session_id':session.session_id,'version':version}
                go('legacy');st.rerun()
        except Exception:st.warning('기존 훈련 기록을 불러오지 못했습니다.')
