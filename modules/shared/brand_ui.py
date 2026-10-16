"""Shared presentation only. Navigation callbacks retain existing authorization."""
from pathlib import Path
from html import escape
import streamlit as st

def apply():
    st.markdown('<style>'+Path(__file__).with_suffix('.css').read_text()+'</style><span class="hw-brand-ui"></span>',unsafe_allow_html=True)

def card(title, description, icon, key, callback, args=(), *, badge=''):
    with st.container(key=key):
        st.markdown(f'<div class="brand-card"><span class="brand-icon" aria-hidden="true">{escape(icon)}</span><div><h3>{escape(title)}</h3><p>{escape(description)}</p></div><span class="brand-end">{escape(badge)} ›</span></div>',unsafe_allow_html=True)
        st.button(title+' 열기',key=key+'_cover',on_click=callback,args=args,use_container_width=True)

def identity(product, profile):
    name=escape(str(profile.get('display_name') or profile.get('login_id') or '사용자'))
    meta=escape(' · '.join(str(profile.get(k) or '') for k in ('organization_name','position_name')).strip(' ·'))
    st.markdown(f'<div class="brand-header"><b>화랑 {escape(product)}</b><span>{name}<small>{meta}</small></span></div>',unsafe_allow_html=True)
