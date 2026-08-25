import base64
import textwrap
from pathlib import Path

import streamlit as st
import modules.commission_calculator as commission_calculator
import modules.insurance_claim_guide as insurance_claim_guide
import modules.silson_generation_comparison as silson_generation_comparison

from modules import (
    analyzer,
    convention,
    deposit_vs_shortpay,
    inheritance_tax,
    insurer_portal,
    manager_results,
    remodeling,
    renewal_vs_nonrenewal,
    summer,
    work_library,
)
from modules.ui_components import inject_global_styles


st.set_page_config(
    page_title="화랑WORKSPACE",
    page_icon="🧰",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_styles()


@st.cache_data(show_spinner=False)
def _pretendard_font_data() -> str:
    font_path = Path(__file__).resolve().parent / "assets" / "fonts" / "PretendardVariable.ttf"
    if not font_path.is_file():
        return ""
    return base64.b64encode(font_path.read_bytes()).decode("ascii")


def inject_pretendard_font() -> None:
    font_data = _pretendard_font_data()
    if not font_data:
        return
    st.markdown(
        f"""
        <style>
        @font-face {{
            font-family: 'Pretendard';
            src: url(data:font/ttf;base64,{font_data}) format('truetype');
            font-weight: 100 900;
            font-style: normal;
            font-display: swap;
        }}
        html, body, [class*="css"], [data-testid="stAppViewContainer"],
        [data-testid="stSidebar"], button, input, textarea, select {{
            font-family: 'Pretendard', 'Noto Sans KR', 'Apple SD Gothic Neo', sans-serif !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_pretendard_font()


# 공지는 이 목록만 수정하면 로그인 화면에 반영됩니다.
NOTICE = {
    "date": "2026.08.25",
    "title": "화랑 WORKSPACE 업무 허브가 새롭게 정리되었습니다.",
    "items": [
        "기능과 업무 자료를 한 번에 찾는 통합검색을 추가했습니다.",
        "즐겨찾기와 업무 자료실로 자주 쓰는 업무에 더 빠르게 접근할 수 있습니다.",
        "사업부 일정은 사이드바에서 노션 월간 일정으로 바로 연결됩니다.",
        "기존 계산식과 데이터 처리 방식은 그대로 유지됩니다.",
    ],
    "important": "비밀번호 또는 이용 권한은 박병선에게 문의해 주세요.",
    "contact_url": "https://open.kakao.com/o/sFxdv4Rf",
}


APP_DEFINITIONS = {
    "analyzer": {
        "name": "보장 분석 도우미", "icon": "📑", "code": "BA", "category": "고객 상담",
        "badge": {"text": "BEST", "tone": "best"},
        "description": "보험사 보장분석 자료를 고객용 양식으로 변환합니다.", "action": "보장 분석 시작", "run": analyzer.run,
    },
    "remodeling": {
        "name": "보험 리모델링", "icon": "🔁", "code": "RM", "category": "고객 상담",
        "badge": {"text": "NEW", "tone": "new"},
        "description": "변경안을 비교하고 고객용 엑셀 자료를 만듭니다.", "action": "리모델링 시작", "run": remodeling.run,
    },
    "deposit_vs_shortpay": {
        "name": "적금 vs 단기납", "icon": "💰", "code": "DS", "category": "고객 상담",
        "badge": {"text": "UPDATE", "tone": "update"},
        "description": "10년 기준 적금과 단기납의 예상 결과를 비교합니다.", "action": "비교 계산 시작", "run": deposit_vs_shortpay.run,
    },
    "renewal_vs_nonrenewal": {
        "name": "갱신 vs 비갱신", "icon": "📊", "code": "RN", "category": "고객 상담",
        "badge": {"text": "UPDATE", "tone": "update"},
        "description": "보험료 변동을 반영해 장기 총납입액을 비교합니다.", "action": "보험료 비교 시작", "run": renewal_vs_nonrenewal.run,
    },
    "inheritance_tax": {
        "name": "상속세 계산기", "icon": "🧾", "code": "IT", "category": "고객 상담",
        "badge": {"text": "NEW", "tone": "new"},
        "description": "예상 상속세와 부족한 현금성 납부재원을 계산합니다.", "action": "상속세 계산 시작", "run": inheritance_tax.run,
    },
    "insurer_portal": {
        "name": "원수사 전산 포털", "icon": "↗", "code": "IP", "category": "고객 상담",
        "badge": {"text": "NEW", "tone": "new"},
        "description": "생명·손해보험사 원수사 전산을 한 화면에서 연결합니다.", "action": "전산 포털 열기", "run": insurer_portal.run,
    },
    "insurance_claim_guide": {
        "name": "보험금 청구 가이드", "icon": "📋", "code": "CG", "category": "고객 상담",
        "badge": {"text": "NEW", "tone": "new"},
        "description": "청구 항목별 필요서류를 안내하고 보장분석 PDF에서 관련 담보를 찾습니다.",
        "action": "청구 가이드 시작", "run": insurance_claim_guide.run,
    },
    "silson_generation_comparison": {
        "name": "실손보험 세대 비교", "icon": "🩺", "code": "SC", "category": "고객 상담",
        "badge": {"text": "NEW", "tone": "new"},
        "description": "현재 가입 실손과 5세대 실손의 보험료와 입원 보장을 비교합니다.",
        "action": "실손 세대 비교 시작", "run": silson_generation_comparison.run,
    },
    "convention": {
        "name": "컨벤션 계산기", "icon": "🏆", "code": "CV", "category": "실적 관리",
        "description": "계약 실적을 환산하고 컨벤션 달성 여부를 확인합니다.", "action": "컨벤션 계산 시작", "run": convention.run,
    },
    "summer": {
        "name": "썸머 계산기", "icon": "🌞", "code": "SU", "category": "실적 관리",
        "description": "7·8월 업적을 반영해 썸머 업적을 계산합니다.", "action": "썸머 실적 계산", "run": summer.run,
    },
    "manager_results": {
        "name": "매니저 업적 환산", "icon": "📈", "code": "MR", "category": "실적 관리",
        "description": "지점 실적 환산금액을 집계합니다.", "action": "매니저 실적 확인", "run": manager_results.run,
    },
    "commission_calculator": {
        "name": "수수료 계산기", "icon": "💼", "code": "CC", "category": "실적 관리",
        "badge": {"text": "NEW", "tone": "new"},
        "description": "생보·손보 예시표에서 상품별 수수료율을 찾아 예상 수당을 계산합니다.",
        "action": "수수료 계산 시작", "run": commission_calculator.run,
    },
    "work_library": {
        "name": "업무 자료실", "icon": "▤", "code": "WL", "category": "업무 지원",
        "badge": {"text": "NEW", "tone": "new"},
        "description": "업무 절차·전산 매뉴얼·영업 자료를 통합검색합니다.",
        "action": "자료 검색 시작", "run": work_library.run,
    },
}


# 홈 카드용 아이콘입니다. 외부 이미지나 추가 패키지 없이 동일한 모양으로 표시됩니다.
HOME_ICONS = {
    "analyzer": '<svg viewBox="0 0 24 24"><path d="M9 11l2 2 4-4"/><path d="M12 3l7 3v5c0 4.6-3 8.1-7 10-4-1.9-7-5.4-7-10V6l7-3z"/></svg>',
    "insurance_claim_guide": '<svg viewBox="0 0 24 24"><path d="M7 3h10v3H7z"/><path d="M5 5h14v16H5z"/><path d="M8 11l2 2 4-4M8 17h8"/></svg>',
    "silson_generation_comparison": '<svg viewBox="0 0 24 24"><path d="M6 3v6a6 6 0 0012 0V3"/><path d="M9 3v5a3 3 0 006 0V3M12 15v6"/><circle cx="18" cy="18" r="3"/></svg>',
    "remodeling": '<svg viewBox="0 0 24 24"><path d="M20 7h-6V1"/><path d="M20 7a9 9 0 10 1 7"/><path d="M4 17h6v6"/></svg>',
    "deposit_vs_shortpay": '<svg viewBox="0 0 24 24"><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v5c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 11v5c0 1.7 3.1 3 7 3 1 0 2-.1 2.8-.3"/><circle cx="18" cy="17" r="3"/><path d="M18 15.5v3M16.8 16.2h2.4"/></svg>',
    "renewal_vs_nonrenewal": '<svg viewBox="0 0 24 24"><path d="M20 7h-5V2"/><path d="M20 7a8 8 0 00-14.5-2"/><path d="M4 17h5v5"/><path d="M4 17a8 8 0 0014.5 2"/></svg>',
    "inheritance_tax": '<svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="3"/><circle cx="16" cy="9" r="2.5"/><path d="M3 20c.3-4 2.3-6 6-6s5.7 2 6 6"/><path d="M14 14c4 0 6 2 6 6"/></svg>',
    "insurer_portal": '<svg viewBox="0 0 24 24"><path d="M5 3h14v18H5z"/><path d="M8 7h2M12 7h2M16 7h1M8 11h2M12 11h2M16 11h1"/><path d="M9 21v-5h6v5"/></svg>',
    "convention": '<svg viewBox="0 0 24 24"><path d="M8 4h8v4a4 4 0 01-8 0V4z"/><path d="M8 6H4c0 4 2 6 5 6M16 6h4c0 4-2 6-5 6"/><path d="M12 12v5M8 21h8M9 17h6v4"/></svg>',
    "summer": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9L7 7M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1"/></svg>',
    "manager_results": '<svg viewBox="0 0 24 24"><path d="M4 20V10M10 20V6M16 20V3M22 20H2"/><path d="M4 8l5-4 5 2 6-5"/><path d="M17 1h3v3"/></svg>',
    "commission_calculator": '<svg viewBox="0 0 24 24"><path d="M4 7h16v13H4z"/><path d="M8 7V4h8v3M4 11h16"/><path d="M9 15h6M12 13v4"/></svg>',
    "work_library": '<svg viewBox="0 0 24 24"><path d="M5 4h14v16H5z"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>',
}


USER_PERMISSIONS = {
    "Admin": {
        "insurance_claim_guide": True,
        "silson_generation_comparison": True,
        "analyzer": True, "remodeling": True, "deposit_vs_shortpay": True,
        "renewal_vs_nonrenewal": True, "inheritance_tax": True,
        "insurer_portal": True,
        "convention": True, "summer": True, "manager_results": True,
        "commission_calculator": True,
        "work_library": True,
    },
    "Manager1": {
        "insurance_claim_guide": True,
        "silson_generation_comparison": True,
        "analyzer": True, "remodeling": True, "deposit_vs_shortpay": True,
        "renewal_vs_nonrenewal": True, "inheritance_tax": True,
        "insurer_portal": True,
        "convention": True, "summer": True, "manager_results": True,
        "commission_calculator": True,
        "work_library": True,
    },
    "Basic": {
        "insurance_claim_guide": True,
        "silson_generation_comparison": True,
        "analyzer": True, "remodeling": False, "deposit_vs_shortpay": False,
        "renewal_vs_nonrenewal": False, "inheritance_tax": False,
        "insurer_portal": True,
        "convention": True, "summer": True, "manager_results": False,
        "commission_calculator": False,
        "work_library": True,
    },
    "Crew": {
        "insurance_claim_guide": True,
        "silson_generation_comparison": True,
        "analyzer": True, "remodeling": False, "deposit_vs_shortpay": True,
        "renewal_vs_nonrenewal": True, "inheritance_tax": False,
        "insurer_portal": True,
        "convention": True, "summer": True, "manager_results": False,
        "commission_calculator": False,
        "work_library": True,
    },
    "Dream": {
        "insurance_claim_guide": True,
        "silson_generation_comparison": True,
        "analyzer": True, "remodeling": True, "deposit_vs_shortpay": True,
        "renewal_vs_nonrenewal": True, "inheritance_tax": True,
        "insurer_portal": True,
        "convention": True, "summer": True, "manager_results": False,
        "commission_calculator": False,
        "work_library": True,
    },
}


def initialize_state() -> None:
    st.session_state.setdefault("password_correct", False)
    st.session_state.setdefault("login_user", None)
    st.session_state.setdefault("active_app", "home")


def render_notice() -> None:
    st.markdown("### 공지사항")
    st.caption(f"최근 업데이트 · {NOTICE['date']}")
    with st.container(border=True):
        st.markdown(f"**{NOTICE['title']}**")
        for item in NOTICE["items"]:
            st.markdown(f"- {item}")
    st.markdown(
        textwrap.dedent(
            f'''
            <style>
            .hw-login-contact {{ display:flex; align-items:center; justify-content:space-between; gap:.9rem;
                margin-top:.55rem; padding:.78rem .9rem; border:1px solid #C9DCF7; border-radius:.75rem;
                background:linear-gradient(135deg,#F3F8FF 0%,#EDF5FF 100%); }}
            .hw-login-contact-copy {{ display:flex; align-items:center; gap:.55rem; min-width:0;
                color:#3F5870; font-size:.82rem; line-height:1.4; }}
            .hw-login-contact-icon {{ flex:0 0 1.55rem; width:1.55rem; height:1.55rem; display:flex;
                align-items:center; justify-content:center; border-radius:50%; background:#DCEAFF;
                color:#2563D9; font-size:.76rem; font-weight:850; }}
            .hw-login-contact-link {{ flex:0 0 auto; display:inline-flex; align-items:center; gap:.28rem;
                padding:.48rem .72rem; border:1px solid #F0C900; border-radius:.58rem;
                background:#FEE500; color:#332A00 !important; text-decoration:none !important;
                font-size:.76rem; line-height:1; font-weight:800;
                box-shadow:0 4px 10px rgba(145,122,0,.12); transition:all .18s ease; }}
            .hw-login-contact-link:hover {{ transform:translateY(-1px); background:#FFEA35;
                box-shadow:0 6px 14px rgba(145,122,0,.18); }}
            @media(max-width:700px) {{
                .hw-login-contact {{ align-items:stretch; flex-direction:column; }}
                .hw-login-contact-link {{ justify-content:center; }}
            }}
            </style>
            <div class="hw-login-contact">
              <div class="hw-login-contact-copy">
                <span class="hw-login-contact-icon">i</span>
                <span>변경된 비밀번호가 필요하신가요?</span>
              </div>
              <a class="hw-login-contact-link" href="{NOTICE['contact_url']}" target="_blank" rel="noopener noreferrer">
                박병선에게 문의해 주세요 <span>↗</span>
              </a>
            </div>
            '''
        ),
        unsafe_allow_html=True,
    )


def render_login() -> bool:
    if st.session_state["password_correct"]:
        return True

    st.markdown(
        """
        <div class="hw-login-brand"><span class="hw-logo">H</span><div><strong>화랑 <b>WORKSPACE</b></strong><small>Insurance Consulting Support</small></div></div>
        <div class="hw-login-hero">
          <div class="hw-login-copy">
            <span class="hw-login-kicker"><i></i>HWARANG BUSINESS WORKSPACE</span>
            <h1><span class="hw-title-top">보험 업무의 복잡함을,</span><em class="hw-title-accent">더 간단하게.</em></h1>
            <p>상담자료 제작부터 실적 관리까지 필요한 업무를 한곳에서 이용하세요.</p>
          </div>
          <div class="hw-glass-stack" aria-label="화랑 WORKSPACE 핵심 업무 영역">
            <div class="hw-glass-card"><span class="hw-glass-signal"></span><b>CONSULTING</b></div>
            <div class="hw-glass-card"><span class="hw-glass-signal"></span><b>PERFORMANCE</b></div>
            <div class="hw-glass-card"><span class="hw-glass-signal"></span><b>INSURANCE PORTAL</b></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    login_col, notice_col = st.columns([1, 1.15], gap="large")
    with login_col:
        st.markdown("### 로그인")
        st.write("발급받은 비밀번호를 입력해 주세요.")
        with st.form("login_form", clear_on_submit=False):
            password = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")
            submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)

        if submitted:
            passwords = dict(st.secrets["passwords"])
            matched_user = next((name for name, saved in passwords.items() if password == saved), None)
            if matched_user:
                st.session_state["password_correct"] = True
                st.session_state["login_user"] = matched_user
                st.session_state["active_app"] = "home"
                st.rerun()
            else:
                st.error("입력한 비밀번호를 확인해 주세요.")

    with notice_col:
        render_notice()
    return False


def allowed_app_ids() -> list[str]:
    permissions = USER_PERMISSIONS.get(st.session_state.get("login_user"), {})
    return [app_id for app_id in APP_DEFINITIONS if permissions.get(app_id, False)]


def navigate(app_id: str) -> None:
    st.session_state["active_app"] = app_id
    st.rerun()


def logout() -> None:
    st.session_state.clear()
    st.rerun()


def render_sidebar(allowed_ids: list[str]) -> None:
    with st.sidebar:
        st.markdown(
            textwrap.dedent('''
            <style>
            .hw-side-brand-signature{display:flex;align-items:center;gap:.72rem;margin:.05rem 0 .8rem;padding:.8rem;
                border:1px solid #D9E6F1;border-radius:.9rem;background:linear-gradient(145deg,#FFFFFF,#F3F8FF)}
            .hw-side-brand-mark{flex:0 0 2.35rem;width:2.35rem;height:2.35rem;display:grid;place-items:center;border-radius:.7rem;
                background:#1769DC;color:#FFF;box-shadow:0 6px 15px rgba(23,105,220,.2);font-size:1rem;font-weight:850}
            .hw-side-brand-title{display:block;color:#17334B;font-size:.92rem;font-weight:800;letter-spacing:-.025em;white-space:nowrap}
            .hw-side-brand-title b{color:#1769DC}.hw-side-brand-credit{margin:.12rem 0 0!important;color:#6C8192;font-size:.6rem!important}
            .hw-side-section{margin:1rem .15rem .35rem;color:#6D8191;font-size:.65rem;font-weight:850;letter-spacing:.08em}
            [data-testid="stSidebar"] .stButton button,[data-testid="stSidebar"] .stLinkButton a{justify-content:flex-start!important;
                min-height:2.55rem!important;border-radius:.72rem!important;font-size:.78rem!important}
            </style>
            <div class="hw-side-brand-signature">
              <span class="hw-side-brand-mark">H</span>
              <div>
                <span class="hw-side-brand-title">화랑 <b>WORKSPACE</b></span>
                <p class="hw-side-brand-credit">Planned &amp; Built by <b>박병선</b></p>
              </div>
            </div>
            '''),
            unsafe_allow_html=True,
        )
        home_active = st.session_state["active_app"] == "home"
        if st.button("⌂  홈", key="nav_home", type="primary" if home_active else "secondary", use_container_width=True):
            navigate("home")

        for category in ("고객 상담", "실적 관리", "업무 지원"):
            category_apps = [app_id for app_id in allowed_ids if APP_DEFINITIONS[app_id]["category"] == category]
            if not category_apps:
                continue
            st.markdown(f'<div class="hw-side-section">{category}</div>', unsafe_allow_html=True)
            for app_id in category_apps:
                app = APP_DEFINITIONS[app_id]
                active = st.session_state["active_app"] == app_id
                if st.button(f"{app['icon']}  {app['name']}", key=f"nav_{app_id}", type="primary" if active else "secondary", use_container_width=True):
                    navigate(app_id)

        st.markdown('<div class="hw-side-section">외부 업무</div>', unsafe_allow_html=True)
        st.link_button(
            "▣  사업부 일정  ↗",
            "https://app.notion.com/p/24d1c9a298c780808dc1f8d9503c3cd5",
            use_container_width=True,
            help="노션 월간 일정을 새 탭에서 엽니다.",
        )
        st.divider()
        st.caption(f"접속 계정 · {st.session_state['login_user']}")
        with st.expander("최근 공지"):
            st.caption(NOTICE["date"])
            st.markdown(f"**{NOTICE['title']}**")
        if st.button("⇥  로그아웃", key="logout", use_container_width=True):
            logout()


def render_app_card(app_id: str, is_allowed: bool) -> None:
    app = APP_DEFINITIONS[app_id]
    card_key = f"available_card_{app_id}" if is_allowed else f"locked_card_{app_id}"
    with st.container(border=True, key=card_key):
        badge = app.get("badge")
        badge_html = ""
        if badge:
            badge_html = (
                f'<span class="hw-corner-badge hw-badge-{badge.get("tone", "default")}">'
                f'{badge["text"]}</span>'
            )
        lock_html = '<span class="hw-card-lock">권한 제한</span>' if not is_allowed else ""
        st.markdown(
            f"""
            {badge_html}{lock_html}
            <div class="hw-tool-heading">
              <span class="hw-tool-icon hw-icon-{app_id}">{HOME_ICONS[app_id]}</span>
              <div class="hw-tool-title">{app['name']}</div>
            </div>
            <div class="hw-tool-desc">{app['description']}</div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "시작하기  →" if is_allowed else "🔒  사용 권한 없음",
            key=f"home_{app_id}",
            disabled=not is_allowed,
            use_container_width=True,
        ):
            navigate(app_id)


def render_home(allowed_ids: list[str]) -> None:
    user = st.session_state["login_user"]
    st.markdown(
        """
        <style>
        .hw-command-head{display:flex;justify-content:space-between;align-items:flex-end;gap:1rem;margin:.15rem 0 1.1rem}
        .hw-command-kicker{color:#1769DC;font-size:.68rem;font-weight:850;letter-spacing:.11em}
        .hw-command-title{margin:.3rem 0 0;color:#10283D;font-size:2rem;font-weight:820;letter-spacing:-.055em}
        .hw-command-user{color:#607789;font-size:.78rem}.hw-command-search-note{margin:-.35rem 0 1.1rem;color:#748899;font-size:.75rem}
        .hw-route{min-height:8.8rem;padding:1.2rem;border:1px solid #D5E3EE;border-radius:1rem;background:#FFF;position:relative;overflow:hidden}
        .hw-route-primary{background:linear-gradient(135deg,#EAF3FF,#FBFDFF);border-color:#C8DCF2}
        .hw-route-label{color:#52758A;font-size:.64rem;font-weight:850;letter-spacing:.09em}.hw-route-title{margin:1.05rem 0 .3rem;color:#10283D;font-size:1.25rem;font-weight:820}
        .hw-route-copy{color:#687E90;font-size:.75rem;line-height:1.5}.hw-route-mark{position:absolute;right:-1.5rem;top:-2.2rem;width:7rem;height:7rem;border:1px solid rgba(23,105,220,.14);border-radius:50%}
        .hw-home-section{margin:1.8rem 0 .7rem}.hw-home-section b{display:block;color:#10283D;font-size:1.25rem}.hw-home-section span{color:#667D8F;font-size:.78rem}
        .hw-search-result{padding:.75rem .9rem;border-left:3px solid #1769DC;background:#F7FAFD;margin:.35rem 0;border-radius:0 .65rem .65rem 0}
        .hw-search-result b{color:#18364D;font-size:.84rem}.hw-search-result span{display:block;color:#6A8192;font-size:.73rem;margin-top:.2rem}
        [class*="st-key-locked_card_"] { background-color:#F2F5F7 !important; opacity:.72;
            border:1px dashed #B8C7D2 !important; border-radius:.95rem !important; position:relative; min-height:10.65rem; }
        [class*="st-key-available_card_"] { min-height:10.65rem; position:relative; overflow:visible;
            background:#FFFFFF; border:1px solid #DCE6EE !important; border-radius:.95rem !important;
            box-shadow:0 7px 22px rgba(27,64,93,.055); transition:transform .18s ease,box-shadow .18s ease; }
        [class*="st-key-available_card_"]:hover { transform:translateY(-2px); box-shadow:0 12px 28px rgba(27,64,93,.1); }
        [class*="st-key-available_card_"] button,
        [class*="st-key-locked_card_"] button { width:100% !important; min-height:2.65rem !important; margin:0 !important;
            padding:.48rem .8rem !important; background:#FFFFFF !important; border:1px solid #C8D9E7 !important;
            border-radius:.62rem !important; box-shadow:none !important; color:#1769DC !important;
            font-size:.79rem !important; font-weight:750 !important;
            transition:background-color .18s ease,color .18s ease,border-color .18s ease,box-shadow .18s ease,transform .18s ease !important; }
        [class*="st-key-available_card_"] button:hover { color:#FFFFFF !important; background:#1769DC !important;
            border-color:#1769DC !important; box-shadow:0 7px 16px rgba(23,105,220,.2) !important; transform:translateY(-1px); }
        [class*="st-key-available_card_"] button:active { transform:translateY(0); box-shadow:0 3px 9px rgba(23,105,220,.18) !important; }
        [class*="st-key-available_card_"] button:focus-visible { outline:3px solid rgba(23,105,220,.2) !important; outline-offset:2px; }
        [class*="st-key-locked_card_"] button:disabled { background:#E9EEF2 !important; border-color:#D5DEE5 !important;
            color:#7B8C99 !important; opacity:1 !important; }
        .hw-tool-heading { display:flex; align-items:center; gap:.72rem; min-height:3rem; padding-right:3.65rem; margin-bottom:.48rem; }
        .hw-tool-icon { flex:0 0 2.65rem; width:2.65rem; height:2.65rem; display:flex; align-items:center;
            justify-content:center; border:1px solid #CDDEFA; border-radius:.72rem; background:#F3F7FF; color:#2F6FDB; }
        .hw-tool-icon svg { width:1.55rem; height:1.55rem; fill:none; stroke:currentColor; stroke-width:1.75;
            stroke-linecap:round; stroke-linejoin:round; }
        .hw-icon-remodeling,.hw-icon-renewal_vs_nonrenewal,.hw-icon-summer { color:#10A6AA; background:#EFFBFA; border-color:#C8ECEA; }
        .hw-icon-deposit_vs_shortpay,.hw-icon-manager_results { color:#D89412; background:#FFF8E9; border-color:#F3DEAA; }
        .hw-icon-inheritance_tax { color:#7856D8; background:#F6F2FF; border-color:#DDD3FA; }
        .hw-tool-title { color:#10283D; font-size:1.02rem; line-height:1.3; font-weight:800; letter-spacing:-.035em; }
        .hw-tool-desc { color:#647789; font-size:.76rem; line-height:1.55; min-height:2.4rem; margin:0 0 .45rem 3.37rem; padding-right:.25rem; }
        .hw-corner-badge { position:absolute; z-index:3; top:.88rem; right:.88rem; display:inline-flex;
            align-items:center; justify-content:center; height:1.48rem; min-width:2.9rem; padding:0 .58rem;
            border-radius:999px; font-size:.62rem; line-height:1; font-weight:850; letter-spacing:.055em; }
        .hw-badge-best { background:#F6C453; color:#4A3100; border:1px solid #E7AE2B; box-shadow:0 4px 10px rgba(231,174,43,.2); }
        .hw-badge-new { background:#0EA5A8; color:#FFFFFF; border:1px solid #079195; box-shadow:0 4px 10px rgba(14,165,168,.22); }
        .hw-badge-update { background:linear-gradient(135deg,#2F73E0,#205CC3); color:#FFFFFF; border:1px solid #1B55B6; box-shadow:0 4px 11px rgba(37,99,217,.22); }
        .hw-badge-default { background:#1769DC; color:#FFFFFF; border:1px solid #0E5BC4; }
        .hw-card-lock { position:absolute; z-index:4; top:.88rem; right:.88rem; padding:.25rem .55rem;
            border-radius:999px; background:#E5EAEE; color:#697A87; font-size:.6rem; font-weight:750; }
        [class*="st-key-locked_card_"] .hw-corner-badge { display:none; }
        .hw-home-footer { display:flex; align-items:center; justify-content:center; gap:.75rem;margin:2.15rem 0 .45rem;padding:1.05rem 1.25rem;border-top:1px solid #D9E5F1;text-align:left; }
        .hw-footer-mark { flex:0 0 2.35rem; width:2.35rem; height:2.35rem; display:flex;
            align-items:center; justify-content:center; border-radius:.7rem;
            background:linear-gradient(145deg,#2F73E0,#205CC3); color:#FFFFFF;
            box-shadow:0 6px 14px rgba(37,99,217,.2); font-size:1rem; font-weight:850; }
        .hw-footer-copy { display:flex; flex-direction:column; gap:.14rem; }
        .hw-footer-brand { color:#17334B; font-size:.82rem; line-height:1.25; font-weight:750;
            letter-spacing:-.015em; }
        .hw-footer-brand b { color:#2563D9; font-weight:850; }
        .hw-footer-credit { margin:0 !important; padding:0 !important; color:#697E91;
            font-size:.72rem !important; line-height:1.35 !important; letter-spacing:.01em; }
        .hw-footer-credit b { color:#2B4861; font-weight:800; }
        @media(max-width:900px){.hw-tool-desc{margin-left:0}.hw-tool-heading{padding-right:3.3rem}}
        @media(max-width:650px){
            .hw-command-title{font-size:1.55rem}.hw-command-head{align-items:flex-start;flex-direction:column}.hw-tool-desc{min-height:auto}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f'''<div class="hw-command-head"><div><div class="hw-command-kicker">HWARANG WORKSPACE</div><div class="hw-command-title">무엇을 처리할까요?</div></div><div class="hw-command-user">{user} · 오늘 필요한 업무를 바로 시작하세요.</div></div>''', unsafe_allow_html=True)
    query = st.text_input("통합 업무 검색", placeholder="기능, 업무, 보험회사, 매뉴얼, 영업 자료를 검색하세요", label_visibility="collapsed", key="home_global_search")
    st.markdown('<div class="hw-command-search-note">예: 보장분석 · KB 가상계좌 · CI보험 · 보험금 청구 · 수수료</div>', unsafe_allow_html=True)

    if query.strip():
        needle = query.strip().lower().replace("실비", "실손").replace("보분", "보장분석").replace("가계좌", "가상계좌")
        app_results = []
        for app_id, app in APP_DEFINITIONS.items():
            haystack = " ".join((app["name"], app["description"], app["action"], app["category"])).lower()
            if all(token in haystack for token in needle.split()):
                app_results.append(app_id)
        library_results = work_library.quick_search(query, 6)
        st.markdown('<div class="hw-home-section"><b>검색 결과</b><span>프로그램과 업무 자료를 함께 찾았습니다.</span></div>', unsafe_allow_html=True)
        if not app_results and not library_results:
            st.info("일치하는 결과가 없습니다. 보험회사명이나 더 짧은 업무 용어로 검색해 주세요.")
        if app_results:
            st.caption(f"프로그램 · {len(app_results)}건")
            for app_id in app_results:
                app = APP_DEFINITIONS[app_id]
                cols = st.columns([5, 1.2])
                with cols[0]:
                    st.markdown(f'<div class="hw-search-result"><b>{app["name"]}</b><span>{app["description"]}</span></div>', unsafe_allow_html=True)
                with cols[1]:
                    if st.button("실행  →", key=f"search_app_{app_id}", disabled=app_id not in allowed_ids, use_container_width=True):
                        navigate(app_id)
        if library_results:
            st.caption(f"업무 자료 · {len(library_results)}건")
            for index, item in enumerate(library_results):
                cols = st.columns([5, 1.2])
                with cols[0]:
                    st.markdown(f'<div class="hw-search-result"><b>{item.title}</b><span>{item.group} · {item.summary}</span></div>', unsafe_allow_html=True)
                with cols[1]:
                    st.link_button("원본  ↗", item.url, use_container_width=True)
    else:
        route_cols = st.columns(3, gap="medium")
        performance_target = next(
            (app_id for app_id in allowed_ids if APP_DEFINITIONS[app_id]["category"] == "실적 관리"),
            "commission_calculator",
        )
        routes = [
            ("CUSTOMER CONSULTING", "고객 상담", "분석·비교·제안·청구 안내", "analyzer", True),
            ("PERFORMANCE", "실적·정산", "수수료와 개인·조직 실적 확인", performance_target, False),
            ("KNOWLEDGE HUB", "자료·매뉴얼", "업무 절차와 상담자료 검색", "work_library", False),
        ]
        for column, (label, title, copy, target, primary) in zip(route_cols, routes):
            with column:
                st.markdown(f'<div class="hw-route {"hw-route-primary" if primary else ""}"><span class="hw-route-mark"></span><div class="hw-route-label">{label}</div><div class="hw-route-title">{title}</div><div class="hw-route-copy">{copy}</div></div>', unsafe_allow_html=True)
                if st.button(f"{title} 시작  →", key=f"route_{target}", disabled=target not in allowed_ids, use_container_width=True):
                    navigate(target)

        st.markdown('<div class="hw-home-section"><b>전체 업무 도구</b><span>즐겨찾기 또는 업무 분류에서 필요한 기능을 선택하세요.</span></div>', unsafe_allow_html=True)
        favorite_ids = [app_id for app_id in ("analyzer", "commission_calculator", "insurance_claim_guide") if app_id in APP_DEFINITIONS]
        favorite_tab, all_tab, consulting_tab, performance_tab = st.tabs(["★ 즐겨찾기", "전체", "고객 상담", "실적 관리"])

        def render_app_grid(app_ids: list[str]) -> None:
            for start in range(0, len(app_ids), 3):
                columns = st.columns(3, gap="medium")
                for column, app_id in zip(columns, app_ids[start:start + 3]):
                    with column:
                        render_app_card(app_id, app_id in allowed_ids)

        with favorite_tab:
            render_app_grid(favorite_ids)
        with all_tab:
            render_app_grid(list(APP_DEFINITIONS))
        with consulting_tab:
            render_app_grid([app_id for app_id, app in APP_DEFINITIONS.items() if app["category"] == "고객 상담"])
        with performance_tab:
            render_app_grid([app_id for app_id, app in APP_DEFINITIONS.items() if app["category"] == "실적 관리"])

    st.markdown(
        '''<div class="hw-home-footer">
          <span class="hw-footer-mark">H</span>
          <div class="hw-footer-copy">
            <span class="hw-footer-brand">화랑 <b>WORKSPACE</b></span>
            <p class="hw-footer-credit">Planned &amp; Built by <b>박병선</b></p>
          </div>
        </div>''',
        unsafe_allow_html=True,
    )


def main() -> None:
    initialize_state()
    if not render_login():
        st.stop()

    allowed_ids = allowed_app_ids()
    active_app = st.session_state.get("active_app", "home")
    if active_app != "home" and active_app not in allowed_ids:
        st.session_state["active_app"] = "home"
        active_app = "home"

    render_sidebar(allowed_ids)
    if active_app == "home":
        render_home(allowed_ids)
    else:
        APP_DEFINITIONS[active_app]["run"]()


if __name__ == "__main__":
    main()
