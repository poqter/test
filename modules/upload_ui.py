"""Validate before existing parsers without changing the UploadedFile object."""
import streamlit as st
from .validators import ValidationError, validate_upload


def other_upload_bytes(current, values):
    """Count unique active upload objects, never retain a second reference."""
    from streamlit.runtime.uploaded_file_manager import UploadedFile
    seen = {getattr(current, 'file_id', id(current))}
    total = 0
    for value in values:
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, UploadedFile):
                identity = getattr(item, 'file_id', id(item))
                if identity not in seen:
                    seen.add(identity)
                    total += item.size
    return total


def guarded_upload(*args, **kwargs):
    uploaded = st.file_uploader(*args, **kwargs)
    if uploaded is None:
        return None
    try:
        validate_upload(uploaded.name, uploaded, session_total=other_upload_bytes(uploaded, list(st.session_state.values())))
    except ValidationError as error:
        st.error('파일을 처리할 수 없습니다. '+str(error))
        st.info('빈 파일·손상 여부와 형식을 확인한 뒤 다시 선택하세요. 파일당 처리 한도는 20MB입니다.')
        # Stop this run: never display a previous file's result as this file's result.
        st.stop()
    return uploaded
