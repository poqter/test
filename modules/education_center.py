"""Session-only education, practice history, checklists and manual notes."""
from datetime import date
import streamlit as st
from .education_content import load_education, search_terms, record_answer, current_attempt
from .consultation_documents import document_pdf, fingerprint
from .session_store import input_revision
from .workspace_tools import field, session_notice
from .ui_components import page_header
from .navigation import navigate, allowed_ids

NOTE='일반 학습·상담 준비용 자료입니다. 법적 의무 이행이나 교육 수료의 증명이 아니며 개별 계약의 지급·가입을 판정하지 않습니다.'

@st.dialog('학습 해설')
def answer_dialog(correct,explanation):
    (st.success if correct else st.info)('맞게 이해하셨습니다.' if correct else '판단 근거를 다시 살펴보세요.')
    st.write(explanation)
    st.caption(NOTE)

@st.dialog('학습자료 미리보기',width='large')
def preview(title,body):
    st.subheader(title)
    st.text(body)

def export_report(key,title,body,data,valid=True):
    metadata=f"콘텐츠 편집일: {data['edited_at']}\n검증 상태: {data['verification_status']}\n출처: {data['source']}"
    full=body+'\n\n콘텐츠 기준\n'+metadata
    valid=valid and bool(body.strip()) and len(full)<=22000
    if len(full)>22000:st.info('출력은 22,000자 이내입니다. 검색 범위를 줄이거나 메모를 나누어 주세요.')
    if st.button('출력 미리보기',key=f'e_{key}_preview',disabled=not body.strip()):preview(title,full)
    token=fingerprint([title,full,date.today().isoformat(),input_revision('education_center')])
    if st.button('내용 확인 후 출력 준비',key=f'e_{key}_approve',disabled=not valid):st.session_state[f'e_{key}_review']=token
    if valid and st.session_state.get(f'e_{key}_review')==token:
        text=title+'\n작성일 '+date.today().isoformat()+'\n\n'+full+'\n\n'+NOTE
        st.download_button('TXT 내려받기',text.encode('utf-8-sig'),f'hwarang_education_{key}.txt','text/plain',key=f'e_{key}_download')
        try:pdf=document_pdf(title,full,prepared_on=date.today().isoformat(),note=NOTE)
        except Exception:st.warning('PDF를 만들지 못했습니다. TXT를 이용하거나 글꼴 설치 상태를 확인해 주세요.')
        else:st.download_button('PDF 내려받기',pdf,f'hwarang_education_{key}.pdf','application/pdf',key=f'e_{key}_pdf')

def retry(key):
    st.session_state[key]=None
    st.session_state['_ws_'+key]=None

def clear_practice():
    st.session_state['e_attempts']={}
    for key in list(st.session_state):
        if isinstance(key,str) and key.endswith('_answer') and (key.startswith('e_') or key.startswith('_ws_e_')):st.session_state[key]=None

@st.dialog('연습 기록을 초기화할까요?')
def reset_practice():
    st.write('현재 세션의 시뮬레이션·퀴즈 제출 기록을 지웁니다. 체크리스트와 연구노트는 유지됩니다.')
    if st.button('연습 기록 초기화',key='e_practice_reset_confirm',on_click=clear_practice):st.rerun()
    if st.button('취소',key='e_practice_reset_cancel'):st.rerun()

def practice(data,simulation):
    items=data['simulations' if simulation else 'quizzes']
    prefix='sim' if simulation else 'quiz'
    attempts=st.session_state.setdefault('e_attempts',{})
    wrong_only=field('checkbox','오답만 복습',f'e_{prefix}_wrong',False)
    indexes=[i for i,item in enumerate(items) if not wrong_only or (current_attempt(attempts,item) and not current_attempt(attempts,item)['correct'])]
    if indexes:
        case_key=f'e_{prefix}_case'
        if st.session_state.get(case_key) not in indexes:st.session_state[case_key]=indexes[0]
        selected_case=st.selectbox('연습 사례',indexes,format_func=lambda i:f"사례 {i+1} · {items[i]['question']}",key=case_key)
        item=items[selected_case]
        st.subheader(item['question'])
        answer_key=f"e_{prefix}_{item['id']}_answer"
        if st.session_state.get(answer_key) not in [None,*item['options']]:retry(answer_key)
        selected=field('radio','가장 적절한 답변',answer_key,None,options=item['options'],index=None)
        if st.button('답변 확인과 해설',disabled=selected is None,key=f'e_{prefix}_submit',type='primary'):
            attempts[item['id']]=record_answer(attempts,item,selected)
            answer_dialog(attempts[item['id']]['correct'],item['explanation'])
        result=current_attempt(attempts,item)
        if result:
            st.caption(f"제출 {result['attempts']}회 · 첫 답변 {'정답' if result['first_correct'] else '오답'} · 최근 제출 {'정답' if result['correct'] else '오답'}")
            if selected!=result['selected']:st.info('선택을 바꿨습니다. 다시 제출해야 학습 기록에 반영됩니다.')
            if st.button('해설 다시 보기',key=f'e_{prefix}_help'):answer_dialog(result['correct'],item['explanation'])
        st.button('답변 선택 비우고 다시 풀기',key=f'e_{prefix}_retry',on_click=retry,args=(answer_key,))
    else:st.info('현재 기록에 복습할 오답이 없습니다. 전체 사례에서 연습해 보세요.')
    done=[(item,current_attempt(attempts,item)) for item in items if current_attempt(attempts,item)]
    correct=sum(bool(result['correct']) for _,result in done)
    st.progress(len(done)/len(items),text=f'제출한 사례 {len(done)}/{len(items)} · 최근 제출 정답 {correct}개')
    st.caption('현재 세션에서 제출한 답변 기준입니다. 고객정보 없이 가상 사례로 연습하며, 학습 기록은 수료증이 아닙니다.')
    if st.button('연습 기록 초기화',key='e_practice_reset_open'):reset_practice()
    body='\n\n'.join(f"{item['question']}\n최근 제출: {result['selected']}\n결과: {'정답' if result['correct'] else '오답'} · 제출 {result['attempts']}회\n해설: {item['explanation']}" for item,result in done)
    export_report(prefix,'상담 시뮬레이션 학습 기록' if simulation else '청구 사례 퀴즈 학습 기록',body,data,valid=bool(done))

def run():
    try:data=load_education()
    except (ValueError,OSError,TypeError):
        st.warning('교육 콘텐츠 형식을 확인해 주세요. 다른 업무 메뉴는 계속 이용할 수 있습니다.')
        return
    page_header('교육·체크리스트','교육·체크리스트 센터','용어 찾기 → 상담 점검·가상 연습 → 연구노트와 학습자료', 'ED')
    session_notice('e_')
    choices=['보험용어 검색',*data['checklists'],'상담유형별 권장 도구','신입 FP 상담 시뮬레이션','보험금 청구 사례 퀴즈','자주 묻는 질문','수동 연구노트']
    mode=st.selectbox('학습할 내용',choices,key='e_mode')
    if mode=='보험용어 검색':
        query=field('text_input','용어 또는 설명 검색','e_query','',max_chars=100)
        category=field('selectbox','용어 분류','e_category','전체',options=['전체',*dict.fromkeys(item['category'] for item in data['terms'])])
        favorites=field('checkbox','즐겨찾기만 보기','e_favorites_only',False)
        matches=search_terms(data['terms'],query,category)
        if favorites:matches=[item for item in matches if st.session_state.get('e_favorite_'+item['id'],False)]
        st.caption(f'검색 결과 {len(matches)}개 · 즐겨찾기는 현재 세션에서만 유지됩니다.')
        if not matches:st.info('일치하는 용어가 없습니다. 검색어·분류·즐겨찾기 조건을 확인하세요.')
        for item in matches:
            with st.expander(item['title'],expanded=bool(query)):
                st.write(item['body'])
                field('checkbox','즐겨찾기','e_favorite_'+item['id'],False)
        body='\n\n'.join(item['title']+'\n'+item['body'] for item in matches)
        export_report('terms','보험용어 학습자료',body,data,valid=bool(matches))
    elif mode in data['checklists']:
        items=data['checklists'][mode]
        st.info('상담 준비용 일반 점검표입니다. 체크 완료가 법적 의무 이행을 증명하지 않습니다.')
        done=[field('checkbox',item,f'e_{mode}_{i}',False) for i,item in enumerate(items)]
        st.progress(sum(done)/len(done),text=f'확인 {sum(done)}/{len(done)} · 미확인 {len(done)-sum(done)}')
        note=field('text_area','미확인 이유·추가 확인 메모 (고객정보 제외)','e_check_note_'+mode,'',max_chars=3000)
        body='\n'.join(('확인: ' if flag else '미확인: ')+item for flag,item in zip(done,items))+'\n\n추가 확인 메모\n'+(note or '미기재')
        export_report('check',mode,body,data)
    elif mode=='상담유형별 권장 도구':
        subject=field('selectbox','상담 유형','e_type',next(iter(data['guides'])),options=list(data['guides']))
        name,app_id,desc=data['guides'][subject]
        st.subheader(name);st.write(desc)
        if app_id in allowed_ids(st.session_state.get('login_user')):
            st.button('추천 도구 열기',key='e_recommended_go',type='primary',on_click=navigate,args=(app_id,))
        else:st.info('현재 계정에서 사용할 수 없는 도구입니다. 접근 권한을 변경하지 않습니다.')
    elif mode in ('신입 FP 상담 시뮬레이션','보험금 청구 사례 퀴즈'):
        practice(data,mode.startswith('신입'))
    elif mode=='자주 묻는 질문':
        query=field('text_input','질문 검색','e_faq_search','',max_chars=100)
        matches=[(q,a) for q,a in data['faq'].items() if query.casefold() in (q+' '+a).casefold()]
        for q,a in matches:
            with st.expander(q,expanded=bool(query)):st.write(a)
        if not matches:st.info('검색 결과가 없습니다.')
        export_report('faq','교육 FAQ','\n\n'.join(q+'\n'+a for q,a in matches),data,valid=bool(matches))
    else:
        st.caption('직접 확인한 내용과 미확인 내용을 구분합니다. URL을 적어도 사이트 내용을 자동으로 읽거나 검증하지 않습니다.')
        values=[]
        for key,label,limit in [('topic','연구 주제',200),('source','자료명·출처 URL·확인일',1500),('facts','직접 확인한 근거',4000),('pending','미확인 사항·추가 질문',3000),('action','다음 확인 계획',1500)]:
            values.append(field('text_area',label,'e_note_'+key,'',max_chars=limit))
        status=field('selectbox','근거 확인 상태','e_note_status','확인 중',options=['확인 중','일부 확인','직접 확인 완료'])
        st.caption('확인 상태는 작성자의 표시이며 시스템의 검증 결과가 아닙니다.')
        body='\n\n'.join(label+'\n'+(value.strip() or '미기재') for label,value in zip(['주제','자료명·출처·확인일','직접 확인한 근거','미확인 사항','다음 확인 계획'],values))+'\n\n작성자 표시 상태\n'+status
        export_report('note','수동 연구노트',body,data,valid=bool(values[0].strip() and values[2].strip()))
    with st.expander('콘텐츠 출처·기준·검증 상태'):
        st.caption('편집일 '+data['edited_at'])
        st.write(data['source'])
        st.write(data['verification_status'])
        st.caption('편집일은 법령·약관의 최신성 확인일을 뜻하지 않습니다. 고객정보를 입력하지 마세요.')
