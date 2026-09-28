"""Question selection, session-local editing and PDF export."""
import re
import streamlit as st
from modules.shared.ui_components import page_header
from modules.shared.workspace_tools import field, session_notice
from modules.consultation.question_bank import BANK, QUESTIONS, RECOMMENDED
from modules.consultation.question_pdf import build_question_pdf


def question_pdf_filename(title):
    """Preserve the displayed title while producing a portable PDF filename."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', '_', str(title)).strip().rstrip('. ')
    if name.lower().endswith('.pdf'):
        name = name[:-4].rstrip('. ')
    name = name or '상담 질문지'
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(i) for i in range(1,10)), *('LPT'+str(i) for i in range(1,10))}:
        name = '_' + name
    return name + '.pdf'


def _init():
    st.session_state.setdefault('b_questions', [])
    st.session_state.setdefault('b_question_edits', {})
    st.session_state.setdefault('b_question_serial', 0)


def _select(qid):
    order=st.session_state['b_questions']
    if st.session_state['b_pick_'+qid]:
        if qid not in order:order.append(qid)
    elif qid in order:order.remove(qid)


def _add_set(ids):
    for number in ids:
        qid=f'Q{number:02d}'
        if qid not in st.session_state['b_questions']:st.session_state['b_questions'].append(qid)
        st.session_state['b_pick_'+qid]=True


def _move(qid, delta):
    order=st.session_state['b_questions'];i=order.index(qid);j=i+delta
    if 0<=j<len(order):order[i],order[j]=order[j],order[i]


def _remove(qid):
    st.session_state['b_questions'].remove(qid)
    st.session_state['b_pick_'+qid]=False


def _edit(qid):
    st.session_state['b_question_edits'][qid]=st.session_state['b_edit_'+qid]


def _restore(qid):
    st.session_state['b_question_edits'].pop(qid,None)
    st.session_state['b_edit_'+qid]=QUESTIONS[qid]['text']


def _add_custom():
    text=st.session_state.get('b_new_question','').strip()
    if not text:return
    st.session_state['b_question_serial']+=1
    qid=f"직접{st.session_state['b_question_serial']:02d}"
    st.session_state['b_questions'].append(qid)
    st.session_state['b_question_edits'][qid]=text
    st.session_state['b_new_question']=''


def run():
    _init()
    page_header('상담·제안서','상담·제안서 스튜디오','필요한 질문을 고르고, 고객에 맞게 다듬어 상담 질문지로 저장하세요.','CH')
    session_notice('b_')
    st.subheader('1. 질문 선택')
    cols=st.columns(3)
    for col,(name,ids,description) in zip(cols,RECOMMENDED):
        with col:
            with st.container(border=True):
                st.markdown('**'+name+'**');st.caption(description)
                st.button('추천 질문 10개 추가',key='b_add_set_'+name,on_click=_add_set,args=(ids,),use_container_width=True)
    search=st.text_input('질문 검색',key='b_question_search',placeholder='예: 보험료, 가족, 갱신')
    category=st.selectbox('질문 분류',['전체']+[x[0] for x in BANK],key='b_question_category')
    with st.container(height=330,border=True):
        found=0
        for qid,q in QUESTIONS.items():
            if category!='전체' and q['category']!=category:continue
            if search.strip() and search.strip().casefold() not in (qid+' '+q['text']+' '+q['category']).casefold():continue
            found+=1
            # Rehydrate selection after a filter hides a checkbox and Streamlit cleans its widget state.
            st.session_state['b_pick_'+qid]=qid in st.session_state['b_questions']
            st.checkbox(qid+' · '+q['text'],key='b_pick_'+qid,on_change=_select,args=(qid,))
        if not found:st.info('검색된 질문이 없습니다. 다른 단어로 찾아보세요.')
    st.caption('추천 묶음을 여러 번 추가해도 같은 질문은 한 번만 들어갑니다.')
    st.subheader('2. 선택한 질문 편집')
    st.caption('문구 수정은 이번 질문지에만 적용됩니다. 위·아래 버튼으로 상담 순서를 바꿀 수 있습니다.')
    order=list(st.session_state['b_questions'])
    for index,qid in enumerate(order):
        original=QUESTIONS.get(qid,{}).get('text','')
        value=st.session_state['b_question_edits'].get(qid,original)
        st.session_state.setdefault('b_edit_'+qid,value)
        with st.container(border=True):
            st.text_area(f'{index+1:02d} · {qid}',key='b_edit_'+qid,height=80,max_chars=500,on_change=_edit,args=(qid,))
            cols=st.columns(4)
            cols[0].button('↑ 위로',key='b_move_up_'+qid,disabled=index==0,on_click=_move,args=(qid,-1),use_container_width=True)
            cols[1].button('↓ 아래로',key='b_move_down_'+qid,disabled=index==len(order)-1,on_click=_move,args=(qid,1),use_container_width=True)
            cols[2].button('선택 해제',key='b_remove_'+qid,on_click=_remove,args=(qid,),use_container_width=True)
            if qid in QUESTIONS:cols[3].button('원문으로',key='b_restore_'+qid,on_click=_restore,args=(qid,),use_container_width=True)
    if not order:st.info('위에서 질문을 선택하거나 아래에서 직접 추가해 주세요.')
    with st.container(border=True):
        st.text_area('내 질문 추가',key='b_new_question',max_chars=500,height=80,placeholder='이번 고객에게 물어보고 싶은 질문을 적어주세요.')
        st.button('질문 추가',key='b_add_custom',on_click=_add_custom,disabled=not st.session_state.get('b_new_question','').strip())
    st.subheader('3. PDF 저장')
    title=field('text_input','질문지 제목','b_question_title','상담 질문지',max_chars=80)
    left,right=st.columns(2)
    with left:customer=field('text_input','고객명 (선택)','b_question_customer','',max_chars=40,placeholder='비워두면 필기란으로 출력')
    with right:day=field('date_input','상담일 (선택)','b_question_date',None,format='YYYY-MM-DD')
    st.caption('고객명·상담일을 비워두면 PDF에 빈 작성란을 남깁니다. 질문별 메모 3줄과 마지막 종합 메모가 포함됩니다.')
    questions=[{'id':qid,'text':st.session_state['b_question_edits'].get(qid,QUESTIONS.get(qid,{}).get('text',''))} for qid in order]
    invalid=[q['id'] for q in questions if not q['text'].strip()]
    if invalid:st.warning('질문 내용을 입력해 주세요: '+', '.join(invalid))
    if not title.strip():st.warning('질문지 제목을 입력해 주세요.')
    if questions and not invalid and title.strip():
        payload,pages=build_question_pdf(title,questions,customer,day.isoformat() if day else '')
        st.caption(f'선택한 질문 {len(questions)}개 · PDF {pages}페이지 (종합 메모 포함)')
        st.download_button('PDF 질문지 다운로드',payload,question_pdf_filename(title),'application/pdf',type='primary',use_container_width=True,key='b_question_download')
    else:
        st.button('PDF 질문지 다운로드',disabled=True,type='primary',use_container_width=True)
