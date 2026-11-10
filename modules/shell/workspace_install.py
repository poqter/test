"""Workspace branding and user-initiated installation; no account/session changes."""
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components


def setup():
    st.html('<style>.st-key-workspace_install_bridge{display:none}</style>')
    with st.container(key='workspace_install_bridge'):
        components.html(Path(__file__).with_name('workspace_install.html').read_text(),height=0)


def sidebar_button():
    st.html('<button type="button" class="workspace-install" style="width:100%;min-height:44px;border:1px solid #d8e1e8;border-radius:8px;background:white;color:#17233c;font:inherit;cursor:pointer">홈 화면에 추가</button>')
