"""Password prompt retains the uploaded PDF, never the submitted password."""
from io import BytesIO
from modules.shared.runtime_cache import digest_bytes

STATE_KEY = 'analyzer_kb_unlock'
PASSWORD_KEY = 'analyzer_kb_password'


def is_encrypted(content):
    from pypdf import PdfReader
    return PdfReader(BytesIO(content)).is_encrypted


def verify_password(content, password):
    from pypdf import PdfReader
    reader=PdfReader(BytesIO(content))
    return not reader.is_encrypted or bool(reader.decrypt(password))


def attempt_unlock(state, content, token):
    """Form callback: discard password even on an incorrect password or parse error."""
    from modules.consultation.analyzer_pdf import extract_kb_pdf
    from pdfminer.pdfdocument import PDFPasswordIncorrect
    password=state.pop(PASSWORD_KEY, '')
    state[STATE_KEY]={'token':token,'raw':None,'error':None}
    try:
        if not verify_password(content,password):
            state[STATE_KEY]['error']='비밀번호가 맞지 않습니다. 파일은 유지되어 있으니 다시 입력해 주세요.'
            return
        state[STATE_KEY]['raw']=extract_kb_pdf(content,password=password)
    except PDFPasswordIncorrect:
        state[STATE_KEY]['error']='비밀번호가 맞지 않습니다. 파일은 유지되어 있으니 다시 입력해 주세요.'
    except ValueError as exc:
        state[STATE_KEY]['error']=str(exc)
    except Exception:
        state[STATE_KEY]['error']='암호 또는 PDF 구조를 처리하지 못했습니다. 지원하는 KB PDF인지 확인해 주세요.'
    finally:
        state.pop(PASSWORD_KEY,None)
        password=None


def prepare_pdf_input(content):
    import streamlit as st
    token=digest_bytes(content) if content else None
    previous=st.session_state.get(STATE_KEY,{})
    if previous.get('token')!=token or not content:
        st.session_state.pop(PASSWORD_KEY,None)
        st.session_state[STATE_KEY]={'token':token,'raw':None,'error':None}
    if not content:
        return {'ready':False}
    try:
        encrypted=is_encrypted(content)
    except Exception:
        st.error('PDF 구조를 읽을 수 없습니다.')
        return {'ready':False}
    if not encrypted:
        return {'ready':True}
    current=st.session_state[STATE_KEY]
    if current.get('raw') is not None:
        st.caption('암호 확인 완료 · 비밀번호는 저장하지 않습니다.')
        return {'ready':True,'raw':current['raw']}
    if current.get('error'):
        st.error(current['error'])
    st.info('암호가 설정된 PDF입니다. 비밀번호를 입력하면 업로드한 파일로 계속 진행합니다.')
    with st.form('analyzer_kb_password_form',clear_on_submit=True):
        st.text_input('PDF 비밀번호',type='password',key=PASSWORD_KEY)
        st.form_submit_button('잠금 해제 및 분석',on_click=attempt_unlock,
                              args=(st.session_state,content,token))
    return {'ready':False}
