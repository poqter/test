"""Reviewed customer handouts with explicit templates and source selection."""
from datetime import date
import streamlit as st
from .content_repository import load_content
from .consultation_documents import document_pdf, fingerprint, unresolved, NOTE
from .material_transfer import candidate, selected_payload, payload_text, is_current
from .workspace_tools import field, session_notice
from .ui_components import page_header
from .navigation import navigate


def set_body(value):
    st.session_state['d_body']=value
    st.session_state['_ws_d_body']=value
    st.session_state.pop('d_review',None)


@st.dialog('자료 양식 적용',width='large')
def template_dialog(value):
    st.text(value)
    st.caption('예시 양식입니다. 확인하면 본문이 교체됩니다. 가져온 참고 항목은 별도 영역에 유지됩니다.')
    if st.button('본문을 이 양식으로 교체',key='d_template_confirm',on_click=set_body,args=(value,)):st.rerun()
    if st.button('취소',key='d_template_cancel'):st.rerun()


def install_import(payload):
    source=payload['source_page']
    st.session_state.setdefault('d_transfers',{})[source]=payload
    st.session_state['d_import_'+source]=payload_text(payload)
    st.session_state['_ws_d_import_'+source]=payload_text(payload)
    st.session_state.pop('d_review',None)


@st.dialog('선택한 항목 가져오기',width='large')
def import_dialog(payload):
    st.text(payload_text(payload))
    st.caption('본문은 유지합니다. 이 원본에서 이전에 가져온 참고 항목은 교체합니다. 실명·연락처 등 불필요한 정보가 없는지 확인하세요.')
    if not is_current(payload,st.session_state):
        st.warning('원본이 변경되었습니다. 다시 선택해 주세요.')
        return
    if st.button('확인 후 참고 항목으로 가져오기',key='d_import_confirm',on_click=install_import,args=(payload,)):st.rerun()
    if st.button('취소',key='d_import_cancel'):st.rerun()


def remove_import(source):
    st.session_state.get('d_transfers',{}).pop(source,None)
    for key in ('d_import_'+source,'_ws_d_import_'+source):st.session_state.pop(key,None)
    st.session_state.pop('d_review',None)


@st.dialog('고객 전달자료 미리보기',width='large')
def preview(title,body):
    st.subheader(title)
    st.text(body)
    st.caption('내용이 길면 PDF는 글자를 줄이지 않고 여러 페이지로 출력합니다.')


def run():
    data=load_content('customer_material_templates')
    page_header('고객 전달자료','고객자료 제작기','양식 선택 → 필요한 내용 작성·가져오기 → 검토 → TXT·PDF', 'CM')
    session_notice('d_')
    choice=field('selectbox','자료 종류','d_template','한 장 요약',options=list(data['templates']))
    st.caption('처음에는 빈 문서입니다. 양식은 예시이며 적용 버튼을 눌러야 본문에 반영됩니다.')
    if st.button('양식 미리보기·적용',key='d_template_open'):template_dialog(data['templates'][choice])
    if choice=='청구 준비':
        st.info('필요서류는 기존 보험금 청구 가이드에서 확인합니다. 이 도구에 별도 서류 규칙을 복사하지 않습니다.')
        st.button('보험금 청구 가이드 열기',key='d_claim_link',on_click=navigate,args=('insurance_claim_guide',))
    title=field('text_input','자료 제목','d_title','고객 전달자료',max_chars=100)
    body=field('text_area','본문 직접 작성 (개인정보 제외)','d_body','',height=330,max_chars=10000)
    with st.expander('상담·계산 결과에서 필요한 항목만 가져오기'):
        source=st.selectbox('원본 도구',['consultation_helper','quick_calculators'],format_func=lambda s:'상담 요약' if s=='consultation_helper' else '계산 결과',key='d_source')
        value=candidate(source,st.session_state)
        if value:
            selected=st.multiselect('가져올 항목',list(value['fields']),default=[],key='d_selection_'+source)
            st.caption('계산·상담 가정은 함께 가져옵니다. 생년월일·구분명·업로드 원본은 자동으로 가져오지 않습니다. 직접 쓴 문장 속 개인정보는 직접 확인하세요.')
            if st.button('선택 항목 미리보기',key='d_import_open',disabled=not selected):
                import_dialog(selected_payload(source,selected,st.session_state))
        else:st.info('원본 도구에서 현재 결과의 검토 확인을 마친 뒤 이용할 수 있습니다.')
    parts=[body] if body.strip() else []
    stale=False
    for source,payload in list(st.session_state.get('d_transfers',{}).items()):
        st.subheader('가져온 상담 요약' if source=='consultation_helper' else '가져온 계산 결과')
        current=is_current(payload,st.session_state)
        if not current:
            stale=True
            st.warning('원본이 수정·초기화되었거나 검토가 해제되었습니다. 최신 항목을 다시 가져오거나 이 참고 영역을 제거해 주세요.')
        imported=field('text_area','고객에게 전달할 참고 항목 편집','d_import_'+source,payload_text(payload),height=240,max_chars=12000)
        parts.append(imported)
        st.button('이 참고 영역 제거',key='d_remove_'+source,on_click=remove_import,args=(source,))
    final='\n\n'.join(parts)
    placeholders=unresolved(final)
    if placeholders:st.info('대괄호 예시 항목을 실제 문구로 바꾸세요: '+', '.join(placeholders[:10]))
    valid=bool(title.strip() and final.strip()) and not placeholders and not stale and len(final)<=22000
    if len(final)>22000:st.warning('전체 문서는 22,000자 이내로 작성해 주세요.')
    if st.button('전달자료 미리보기',key='d_preview',disabled=not final.strip()):preview(title,final)
    token=fingerprint([title,final,stale,date.today().isoformat()])
    if st.button('내용·가정·개인정보 확인 완료',key='d_approve',disabled=not valid):st.session_state['d_review']=token
    if valid and st.session_state.get('d_review')==token:
        prepared=date.today().isoformat()
        content=title+'\n작성일 '+prepared+'\n\n'+final+'\n\n'+NOTE
        st.download_button('TXT 내려받기',content.encode('utf-8-sig'),'hwarang_customer_material.txt','text/plain',key='d_txt')
        try:pdf=document_pdf(title,final,prepared_on=prepared)
        except Exception:st.warning('PDF를 만들지 못했습니다. TXT를 이용하거나 문서 길이·글꼴 설치 상태를 확인해 주세요.')
        else:st.download_button('PDF 내려받기',pdf,'hwarang_customer_material.pdf','application/pdf',key='d_pdf')
    else:st.caption('현재 내용의 검토를 마치면 내려받기가 표시됩니다. 원본 변경 시 다시 확인합니다.')
    with st.expander('양식 안내'):
        st.caption(data['source']+' · 편집일 '+data['edited_at'])
