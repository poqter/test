"""Home-only styling. Authentication, task screens and calculation rules stay separate."""
from html import escape
from pathlib import Path
import streamlit as st


def apply(surface: str) -> None:
    if surface not in ('workspace', 'calculator'):
        raise ValueError('Unknown home surface')
    css = Path(__file__).with_name('premium_homes.css').read_text(encoding='utf-8')
    st.markdown('<style>' + css + '</style>', unsafe_allow_html=True)
    st.markdown(f'<div class="hw-premium-{surface}" aria-hidden="true"></div>', unsafe_allow_html=True)


def identity_header(product: str, profile: dict | None = None) -> None:
    profile = profile or {}
    name = escape(str(profile.get('display_name') or profile.get('login_id') or '사용자'))
    meta = escape(' · '.join(str(profile.get(k) or '') for k in ('organization_name', 'position_name')).strip(' ·'))
    st.markdown(f'<header class="hp-header"><div class="hp-brand"><span>H</span><div>HWARANG<small>{escape(product)}</small></div></div><div class="hp-profile"><b>{name}</b><small>{meta}</small></div></header>', unsafe_allow_html=True)


def footer(product: str) -> None:
    st.markdown(f'<footer class="hp-footer"><span>HWARANG {escape(product)}</span><span>Planned &amp; Built by 박병선 팀장</span></footer>', unsafe_allow_html=True)


def emoji_markup(value: str) -> str:
    uri = _emoji_assets().get(value)
    return f'<img class="hp-emoji-image" src="{uri}" alt="" draggable="false">' if uri else escape(value)

from functools import lru_cache
@lru_cache(maxsize=1)
def _emoji_assets():
    import json
    return json.loads(Path(__file__).with_name('home_emoji.json').read_text(encoding='utf-8'))
