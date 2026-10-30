"""Server-authenticated education pages. No simulator permissions are implied."""
from datetime import date
from uuid import uuid4
from pathlib import Path
import base64
import streamlit as st

NAV = {'courses': ('교육 과정', None), 'library': ('교육자료실', 'academy.library'), 'my_learning': ('나의 학습', 'academy.my_learning')}
CATEGORIES = {'new_hire':'신입교육','consultation':'상담교육','insurance_practice':'보험실무','assessment':'시험·평가'}

def rpc(auth, owner, name, **kwargs):
    return auth._request('POST', '/rest/v1/rpc/hwarang_learning_'+name, admin=True, json={'p_actor':owner, **kwargs})

def render(auth, owner, permissions, profile, surface):
    label,permission=NAV[surface]
    st.title(label)
    if permission and permission not in permissions:
        st.warning('이 메뉴의 이용 권한이 없습니다.');return
    try: items=rpc(auth,owner,'catalog') or []
    except Exception:
        st.error('교육 저장소를 연결하지 못했습니다. SQL 26 적용 및 아카데미 접근 권한을 확인해 주세요.');return
    items.sort(key=lambda r: (0 if r.get('id')=='newhire-30-v1' else 1, r.get('title','')))
    if surface=='library':
        st.caption('자료를 검색하고 기준일을 확인하세요. 법령·약관은 최신 원본을 별도로 확인합니다.')
        query=st.text_input('자료 검색',placeholder='제목, 설명, 분류 검색')
        groups=['전체']+sorted({r['category'] for r in items if r['kind']=='resource' and r.get('published')})
        category=st.selectbox('자료 분류',groups)
        resources=[r for r in items if r['kind']=='resource' and r.get('published') and (category=='전체' or r['category']==category) and query.casefold() in ' '.join(str(r.get(k,'')) for k in ('title','summary','category')).casefold()]
        st.caption(f'{len(resources)}개 자료')
        for r in resources:
            with st.expander(r['title']):
                st.caption(f"{r['category']} · 기준일 {r.get('updated_on','확인 필요')} · 개정 {r['revision']}")
                st.write(r.get('summary',''));st.markdown(r.get('body',''))
                st.download_button('학습 노트 내려받기',r.get('body',''),file_name=r['id']+'.md',mime='text/markdown',key='note_'+r['id'])
                attachment=r.get('attachment')
                if attachment:
                    try:
                        data=base64.b64decode(attachment['data'],validate=True)
                        st.download_button('첨부 자료 내려받기 · '+attachment['name'],data,file_name=Path(attachment['name']).name,mime=attachment['mime'],key='file_'+r['id'])
                    except (ValueError,KeyError):st.warning('첨부 파일 정보를 확인해 주세요.')
        if profile.get('role')=='super_admin': _editor(auth,owner,items)
        return
    courses=[r for r in items if r['kind']=='course' and r.get('published') and r.get('permission') in permissions]
    if surface=='my_learning':
        st.caption('신입 공통 과정의 실습과 진도는 연결된 상위 관리자도 확인할 수 있습니다. AI 상담 기록은 시뮬레이터에서 확인하세요.')
        for course in courses:
            if course.get('learning_mode')=='practice':
                from .onboarding import completion
                try:
                    works=rpc(auth,owner,'work_get',p_id=course['id']) or []
                    done,approved,graduated=completion(course,works)
                    st.subheader(course['title']);st.progress(done/len(course['lessons']),text=f'{done}/30 학습 · {approved}/4 주간 검토')
                    st.success('수료') if graduated else st.caption('실습과 주간 검토를 완료하면 수료로 표시됩니다.')
                    if st.button('학습 이어하기',key='resume_'+course['id']):
                        from hwarang_academy.shell import course_open
                        course_open(course['id']);st.rerun()
                except Exception:st.warning('신입 과정 기록을 불러오지 못했습니다.')
                continue
            done=len((course.get('progress') or {}).get('completed_lessons') or [])
            total=len(course['lessons']);st.subheader(course['title']);st.progress(done/total if total else 0,text=f'{done}/{total} 학습 완료')
        if not courses:st.info('이용 가능한 교육 과정이 없습니다.')
        return
    if not courses:st.info('이용 가능한 교육 과정이 없습니다. 교육 메뉴 권한을 확인해 주세요.');return
    selected=st.selectbox('교육 과정',courses,index=next((i for i,c in enumerate(courses) if c['id']==st.session_state.get('_academy_course_id')),0),format_func=lambda c:c['title'])
    if selected.get('learning_mode')=='practice':
        from .onboarding import render as render_onboarding
        render_onboarding(auth,owner,permissions,profile,selected,rpc)
        return
    st.caption(selected['summary']+' · 자체 기초 학습 콘텐츠 / 자격 인증 과정 아님')
    done=set((selected.get('progress') or {}).get('completed_lessons') or [])
    st.progress(len(done)/len(selected['lessons']),text=f"{len(done)}/{len(selected['lessons'])} 완료")
    for lesson in selected['lessons']:
        key=selected['id']+'_'+lesson['id']
        with st.expander(('✓ ' if lesson['id'] in done else '')+lesson['title'],expanded=lesson['id'] not in done):
            st.markdown(lesson['body'])
            checked=st.checkbox('내용을 읽고 실천 항목을 확인했습니다.',key='read_'+key)
            passed=True
            if selected['category']=='assessment' and lesson['id']=='3':
                answer=st.radio('자료에서 확인하지 못한 보장은 어떻게 설명할까요?', ['선택해 주세요','확인되지 않았음을 알리고 원본을 확인한다','고객이 원하면 보장된다고 설명한다'],key='quiz_'+key)
                passed=answer=='확인되지 않았음을 알리고 원본을 확인한다'
                if answer=='고객이 원하면 보장된다고 설명한다':st.info('고객의 희망과 계약상 보장은 다릅니다. 원본을 확인하는 답변으로 다시 생각해 보세요.')
            if st.button('학습 완료 기록',key='complete_'+key,disabled=not checked or not passed or lesson['id'] in done):
                try:rpc(auth,owner,'complete',p_id=selected['id'],p_revision=selected['revision'],p_lesson=lesson['id']);st.rerun()
                except Exception:st.error('진도를 저장하지 못했습니다. 새로고침 후 다시 시도해 주세요.')
    if len(done)==len(selected['lessons']):
        st.success('과정을 완료했습니다. 나의 학습에 기록되었습니다.')
        if 'academy.simulator' in permissions and st.button('배운 내용으로 상담 연습하기 →'):
            from hwarang_academy.shell import go
            go('simulator');st.rerun()

def _editor(auth,owner,items):
    with st.expander('관리자 · 자료 등록 및 개정'):
        resources=[r for r in items if r['kind']=='resource']
        selection=st.selectbox('수정할 자료',[None]+resources,format_func=lambda r:'새 자료 등록' if r is None else r['title']+(' · 비공개' if not r.get('published') else ''))
        current=selection or {}; suffix=current.get('id','new')
        with st.form('resource_'+suffix,clear_on_submit=False):
            title=st.text_input('제목',current.get('title',''),max_chars=150)
            summary=st.text_input('짧은 설명',current.get('summary',''),max_chars=300)
            category=st.text_input('분류',current.get('category','상담·설명'),max_chars=40)
            body=st.text_area('학습 내용 (Markdown)',current.get('body',''),height=200,max_chars=50000)
            basis=st.date_input('자료 기준일',value=date.fromisoformat(current.get('updated_on',date.today().isoformat())))
            upload=st.file_uploader('첨부 PDF / TXT / MD · 최대 2MB',type=['pdf','txt','md'])
            remove=st.checkbox('기존 첨부 제거') if current.get('attachment') else False
            published=st.checkbox('직원에게 게시',value=bool(current.get('published',False)))
            submit=st.form_submit_button('자료 저장')
        if submit:
            if not title.strip() or not category.strip():st.error('제목과 분류를 입력해 주세요.');return
            attachment=None if remove else current.get('attachment')
            if upload:
                content=upload.getvalue()
                if len(content)>2_000_000:st.error('첨부 파일은 2MB 이하여야 합니다.');return
                if upload.name.lower().endswith('.pdf') and not content.startswith(b'%PDF-'):st.error('PDF 파일 형식을 확인해 주세요.');return
                attachment={'name':Path(upload.name).name,'mime':'application/pdf' if upload.name.lower().endswith('.pdf') else 'text/plain','data':base64.b64encode(content).decode('ascii')}
            data=dict(id=current.get('id','resource-'+str(uuid4())),kind='resource',permission='academy.library',category=category.strip(),title=title.strip(),summary=summary,body=body,lessons=[],revision=current.get('revision',0),updated_on=basis.isoformat(),published=published,attachment=attachment)
            try:rpc(auth,owner,'publish',p_data=data);st.success('저장했습니다.');st.rerun()
            except Exception:st.error('자료를 저장하지 못했습니다. 변경 충돌 또는 저장소 설정을 확인해 주세요.')
