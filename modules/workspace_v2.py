"""화랑 WORKSPACE 2.0 공통 탐색과 반응형 홈 화면."""

from __future__ import annotations

import html
from collections.abc import Callable

import streamlit as st


CATEGORY_ORDER = (
    "보장 분석",
    "리모델링·비교",
    "재무·세금",
    "보험금 청구",
    "업무 지원",
    "실적 관리",
)

CATEGORY_META = {
    "보장 분석": ("보장분석 자료를 정리하고 고객 상담의 출발점을 준비합니다.", "⌁"),
    "리모델링·비교": ("보험료와 보장 변화를 다양한 기준으로 비교합니다.", "↗"),
    "재무·세금": ("상속세와 납부재원을 체계적으로 확인합니다.", "₩"),
    "보험금 청구": ("청구 유형별 필요서류와 고객 안내문을 준비합니다.", "+"),
    "업무 지원": ("보험사 전산과 공식 업무 페이지를 빠르게 엽니다.", "↗"),
    "실적 관리": ("계약자료를 검증하고 개인·조직 실적을 계산합니다.", "▥"),
}


def inject_workspace_v2_styles() -> None:
    """기존 도구에도 적용되는 고시인성 디자인 토큰과 홈 전용 스타일."""
    st.markdown(
        """
        <style>
        :root {
            --v2-navy:#09263F; --v2-blue:#1769DC; --v2-ink:#132334;
            --v2-muted:#5E7184; --v2-line:#D9E3EC; --v2-bg:#F4F7FA;
            --v2-soft:#EAF3FF; --v2-green:#16845B;
        }
        html, body, [data-testid="stAppViewContainer"] { font-size:16px !important; }
        [data-testid="stAppViewContainer"] { background:var(--v2-bg) !important; }
        [data-testid="stMainBlockContainer"], .stMainBlockContainer,
        [data-testid="stAppViewContainer"] .main .block-container {
            max-width:1380px !important; padding-left:2rem !important;
            padding-right:2rem !important; padding-bottom:5rem !important;
        }
        p, li, label, [data-testid="stMarkdownContainer"] { line-height:1.62; }
        [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label,
        [data-testid="stMarkdownContainer"] p { font-size:1rem !important; }
        [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
            font-size:.9rem !important; line-height:1.55 !important;
        }
        .stButton>button, .stDownloadButton>button,
        [data-testid="stFormSubmitButton"]>button {
            min-height:3rem !important; font-size:1rem !important;
            font-weight:750 !important; border-radius:12px !important;
        }
        [data-baseweb="input"] input,
        [data-baseweb="textarea"] textarea, textarea {
            min-height:3rem; font-size:1rem !important;
        }
        [data-testid="stFileUploaderDropzone"] button,
        [data-testid="stFileUploaderDropzoneInstructions"] span,
        [data-testid="stFileUploaderDropzoneInstructions"] small { font-size:.9rem !important; }
        [data-testid="stMetricLabel"] p { font-size:.95rem !important; }
        [data-testid="stMetricValue"] { font-size:2rem !important; }
        [data-testid="stDataFrame"], [data-testid="stDataEditor"] { font-size:.94rem !important; }
        button:focus-visible, input:focus-visible, textarea:focus-visible {
            outline:3px solid #1769DC !important; outline-offset:3px;
        }
        .hw-page-title { font-size:2.15rem !important; }
        .hw-page-desc { font-size:1rem !important; }
        .hw-breadcrumb { font-size:.875rem !important; }
        .hw-section-title { font-size:1.48rem !important; }
        .hw-section-desc, .hw-guide-intro { font-size:.95rem !important; }
        .hw-guide-copy b { font-size:.95rem !important; }
        .hw-guide-copy span { font-size:.9rem !important; }
        .hw-page-footer { font-size:.875rem !important; }

        .v2-hero { position:relative; overflow:hidden; margin:0 0 2rem; padding:2rem 2.2rem;
            border-radius:1.45rem; color:#FFF;
            background:linear-gradient(125deg,#082640 0%,#10486F 72%,#1769DC 145%);
            box-shadow:0 16px 38px rgba(15,43,66,.13); }
        .v2-hero:after { content:"H"; position:absolute; right:1.5rem; top:-4.8rem;
            color:rgba(255,255,255,.05); font-size:14rem; line-height:1; font-weight:900; }
        .v2-kicker { position:relative; z-index:1; margin-bottom:.45rem; color:#8FC4FF;
            font-size:.88rem; font-weight:850; letter-spacing:.08em; }
        .v2-hero h1 { position:relative; z-index:1; margin:0 !important; color:#FFF !important;
            font-size:2.45rem !important; line-height:1.22 !important; font-weight:850 !important; }
        .v2-hero p { position:relative; z-index:1; margin:.65rem 0 0 !important; color:#D5E6F5;
            font-size:1.05rem !important; line-height:1.58 !important; }
        .v2-section-head { margin:2rem 0 1rem; }
        .v2-section-head h2 { margin:0 !important; color:var(--v2-navy) !important;
            font-size:1.48rem !important; line-height:1.35 !important; font-weight:820 !important; }
        .v2-section-head p { margin:.25rem 0 0 !important; color:var(--v2-muted);
            font-size:1rem !important; }
        [class*="st-key-v2_task_"] { min-height:11rem; padding:1.2rem 1.25rem !important;
            border:1px solid var(--v2-line) !important; border-radius:1.05rem !important;
            background:#FFF !important; box-shadow:0 8px 24px rgba(15,43,66,.055);
            transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease; }
        [class*="st-key-v2_task_"]:hover { transform:translateY(-2px);
            border-color:#A9C9EC !important; box-shadow:0 14px 30px rgba(15,43,66,.095); }
        .v2-task-icon { width:2.8rem; height:2.8rem; display:grid; place-items:center;
            margin-bottom:.8rem; border-radius:.85rem; background:var(--v2-soft); color:var(--v2-blue);
            font-size:1.3rem; font-weight:850; }
        .v2-task-title { color:var(--v2-navy); font-size:1.16rem; line-height:1.35;
            font-weight:820; letter-spacing:-.025em; }
        .v2-task-desc { min-height:2.9rem; margin:.3rem 0 .6rem; color:var(--v2-muted);
            font-size:.91rem; line-height:1.55; }
        [class*="st-key-v2_task_"] .stButton>button { min-height:2.7rem !important;
            color:var(--v2-blue) !important; background:#FFF !important; border-color:#C8D9E7 !important; }
        [class*="st-key-v2_task_"] .stButton>button:hover { color:#FFF !important;
            background:var(--v2-blue) !important; border-color:var(--v2-blue) !important; }
        [class*="st-key-v2_tool_"] { min-height:9.5rem; padding:1.1rem 1.15rem !important;
            border:1px solid var(--v2-line) !important; border-radius:1rem !important;
            background:#FFF !important; box-shadow:0 7px 20px rgba(15,43,66,.045); }
        [class*="st-key-v2_tool_"] .stButton>button { min-height:2.6rem !important;
            font-size:.95rem !important; }
        .v2-tool-head { display:flex; align-items:center; gap:.7rem; margin-bottom:.35rem; }
        .v2-tool-icon { flex:0 0 2.55rem; width:2.55rem; height:2.55rem; display:grid;
            place-items:center; border-radius:.78rem; background:#F1F6FB; color:var(--v2-blue); }
        .v2-tool-icon svg { width:1.45rem; height:1.45rem; fill:none; stroke:currentColor;
            stroke-width:1.75; stroke-linecap:round; stroke-linejoin:round; }
        .v2-tool-title { color:var(--v2-navy); font-size:1.03rem; font-weight:800; line-height:1.3; }
        .v2-tool-desc { min-height:2.55rem; color:var(--v2-muted); font-size:.89rem; line-height:1.48; }
        .v2-status-row { display:grid; grid-template-columns:1.2fr 1fr; gap:1rem; margin-top:2rem; }
        .v2-status-card { padding:1.15rem 1.25rem; border:1px solid var(--v2-line);
            border-radius:1rem; background:#FFF; }
        .v2-status-card b { display:block; color:var(--v2-navy); font-size:1.02rem; }
        .v2-status-card span { display:block; margin-top:.25rem; color:var(--v2-muted);
            font-size:.9rem; line-height:1.5; }
        .v2-footer { display:flex; justify-content:space-between; gap:1rem; margin-top:2.8rem;
            padding-top:1.1rem; border-top:1px solid var(--v2-line); color:#718394; font-size:.88rem; }
        [data-testid="stSidebar"] { background:#FFF !important; }
        [data-testid="stSidebar"] .stButton>button { min-height:2.85rem !important;
            justify-content:flex-start; padding-left:.8rem !important; }
        .v2-side-brand { display:flex; align-items:center; gap:.75rem; padding:.65rem .5rem 1rem; }
        .v2-side-mark { width:2.55rem; height:2.55rem; display:grid; place-items:center;
            border-radius:.8rem; background:var(--v2-navy); color:#70B4FF; font-size:1.05rem; font-weight:900; }
        .v2-side-brand strong { display:block; color:var(--v2-navy); font-size:1.05rem; }
        .v2-side-brand small { display:block; color:var(--v2-muted); font-size:.875rem; }
        .v2-side-label { margin:1.15rem .5rem .4rem; color:#5E7184; font-size:.875rem;
            font-weight:800; letter-spacing:.04em; }
        .v2-side-privacy { margin-top:1.4rem; padding:.8rem; border-radius:.8rem;
            background:#F3F8FC; color:#526B80; font-size:.875rem; line-height:1.48; }
        @media(prefers-reduced-motion:reduce) {
            [class*="st-key-v2_task_"], .stButton>button { transition:none !important; transform:none !important; }
        }
        @media(max-width:768px) {
            .st-key-v2_home [data-testid="stHorizontalBlock"] { flex-direction:column; }
            .st-key-v2_home [data-testid="stColumn"] { width:100% !important; flex:1 1 100% !important; min-width:0 !important; }
        }
        @media(max-width:900px) {
            [data-testid="stMainBlockContainer"], .stMainBlockContainer,
            [data-testid="stAppViewContainer"] .main .block-container {
                padding-left:1rem !important; padding-right:1rem !important;
            }
            .v2-hero { padding:1.55rem 1.25rem; border-radius:1.2rem; }
            .v2-hero h1 { font-size:1.9rem !important; }
            .v2-hero p { font-size:1rem !important; }
            .v2-status-row { grid-template-columns:1fr; }
            .v2-task-desc, .v2-tool-desc { min-height:0; }
            .v2-footer { display:block; }
            .v2-footer span { display:block; margin-top:.25rem; }
            .hw-page-title { font-size:1.75rem !important; }
            .hw-page-desc { font-size:1rem !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _category_apps(definitions: dict, category: str) -> list[str]:
    return [app_id for app_id, app in definitions.items() if app.get("group") == category]


def render_sidebar(
    allowed_ids: list[str],
    definitions: dict,
    navigate: Callable[[str], None],
    logout: Callable[[], None],
    notice: dict,
) -> None:
    """권한에 따라 노출되는 새 탐색 메뉴."""
    with st.sidebar:
        st.markdown(
            """<div class="v2-side-brand"><span class="v2-side-mark">H</span>
            <div><strong>화랑 WORKSPACE</strong><small>Insurance Business Platform</small></div></div>""",
            unsafe_allow_html=True,
        )
        home_active = st.session_state.get("active_app") == "home"
        if st.button("⌂  홈", key="v2_nav_home", type="primary" if home_active else "secondary", use_container_width=True):
            navigate("home")

        st.markdown('<div class="v2-side-label">업무 도구</div>', unsafe_allow_html=True)
        for category in CATEGORY_ORDER:
            category_ids = [app_id for app_id in _category_apps(definitions, category) if app_id in allowed_ids]
            if not category_ids:
                continue
            with st.expander(category, expanded=st.session_state.get("active_app") in category_ids):
                for app_id in category_ids:
                    app = definitions[app_id]
                    active = st.session_state.get("active_app") == app_id
                    if st.button(
                        f"{app['icon']}  {app['name']}",
                        key=f"v2_nav_{app_id}",
                        type="primary" if active else "secondary",
                        use_container_width=True,
                    ):
                        navigate(app_id)

        st.markdown(
            '<div class="v2-side-privacy">🔒 별도 고객 DB를 추가하지 않습니다.<br>입력 자료는 서버에서 처리되므로 테스트에는 가상·비식별 자료를 사용해 주세요.</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"접속 계정 · {st.session_state.get('login_user', '-')}")
        st.caption("화면 이동·새로고침 시 입력값이 초기화될 수 있습니다. 필요한 결과를 먼저 내려받아 주세요.")
        with st.expander("최근 업데이트"):
            st.caption(notice["date"])
            st.markdown(f"**{notice['title']}**")
        if st.button("로그아웃", key="v2_logout", use_container_width=True):
            logout()


def _task_card(
    key: str,
    icon: str,
    title: str,
    description: str,
    app_id: str,
    allowed_ids: list[str],
    navigate: Callable[[str], None],
) -> None:
    with st.container(border=True, key=f"v2_task_{key}"):
        st.markdown(
            f'<div class="v2-task-icon">{html.escape(icon)}</div>'
            f'<div class="v2-task-title">{html.escape(title)}</div>'
            f'<div class="v2-task-desc">{html.escape(description)}</div>',
            unsafe_allow_html=True,
        )
        enabled = app_id in allowed_ids
        if st.button(
            "업무 시작  →" if enabled else "사용 권한 없음",
            key=f"v2_launch_task_{key}",
            disabled=not enabled,
            use_container_width=True,
        ):
            navigate(app_id)


def _tool_card(
    app_id: str,
    allowed_ids: list[str],
    definitions: dict,
    icons: dict,
    navigate: Callable[[str], None],
) -> None:
    app = definitions[app_id]
    enabled = app_id in allowed_ids
    with st.container(border=True, key=f"v2_tool_{app_id}"):
        st.markdown(
            f'<div class="v2-tool-head"><span class="v2-tool-icon">{icons[app_id]}</span>'
            f'<span class="v2-tool-title">{html.escape(app["name"])}</span></div>'
            f'<div class="v2-tool-desc">{html.escape(app["description"])}</div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "열기  →" if enabled else "권한 제한",
            key=f"v2_launch_tool_{app_id}",
            disabled=not enabled,
            use_container_width=True,
        ):
            navigate(app_id)


def render_home(
    allowed_ids: list[str],
    definitions: dict,
    icons: dict,
    navigate: Callable[[str], None],
    notice: dict,
) -> None:
    """업무 상황을 중심으로 설계한 반응형 홈."""
    with st.container(key="v2_home"):
        _render_home_contents(allowed_ids, definitions, icons, navigate, notice)


def _render_home_contents(allowed_ids, definitions, icons, navigate, notice) -> None:
    user = html.escape(str(st.session_state.get("login_user") or "사용자"))
    st.markdown(
        f"""<div class="v2-hero"><div class="v2-kicker">HWARANG WORKSPACE 2.0 · TEST</div>
        <h1>{user}님, 오늘 어떤 업무를 시작하시겠어요?</h1>
        <p>고객 상담부터 실적 확인까지, 업무 상황에 맞는 도구를 빠르게 찾으세요.</p></div>""",
        unsafe_allow_html=True,
    )

    query = st.text_input(
        "통합검색",
        key="v2_global_search",
        placeholder="예: 갱신보험료, 실손 비교, 청구서류, 상속세",
        label_visibility="collapsed",
    ).strip().lower()

    if query:
        matches = [
            app_id for app_id, app in definitions.items()
            if query in " ".join((app["name"], app["description"], app.get("group", ""), " ".join(app.get("keywords", ())))).lower()
        ]
        st.markdown('<div class="v2-section-head"><h2>검색 결과</h2><p>입력한 업무와 관련된 도구입니다.</p></div>', unsafe_allow_html=True)
        if not matches:
            st.info("관련 도구를 찾지 못했습니다. ‘보험료’, ‘청구’, ‘실적’처럼 짧은 단어로 검색해 보세요.")
        else:
            for start in range(0, len(matches), 4):
                cols = st.columns(4, gap="medium")
                for col, app_id in zip(cols, matches[start:start + 4]):
                    with col:
                        _tool_card(app_id, allowed_ids, definitions, icons, navigate)
        return

    st.markdown(
        '<div class="v2-section-head"><h2>빠른 업무 시작</h2>'
        '<p>프로그램 이름을 몰라도 업무 목적에 따라 시작할 수 있습니다.</p></div>',
        unsafe_allow_html=True,
    )
    tasks = (
        ("analysis", "⌁", "기존 보험을 점검할게요", "보장분석 자료를 고객용 양식으로 정리합니다.", "analyzer"),
        ("renewal", "↗", "보험료를 비교할게요", "갱신·비갱신의 장래 보험료 부담을 비교합니다.", "renewal_vs_nonrenewal"),
        ("claim", "+", "보험금을 청구할게요", "청구유형별 필요서류와 안내문을 준비합니다.", "insurance_claim_guide"),
        ("tax", "₩", "상속 상담을 시작할게요", "예상 상속세와 부족한 납부재원을 확인합니다.", "inheritance_tax"),
        ("result", "▥", "실적을 계산할게요", "계약자료를 환산하고 달성 현황을 확인합니다.", "convention"),
        ("portal", "↗", "보험사 전산을 열게요", "생명·손해보험사 전산으로 빠르게 이동합니다.", "insurer_portal"),
    )
    for start in range(0, len(tasks), 3):
        cols = st.columns(3, gap="medium")
        for col, task in zip(cols, tasks[start:start + 3]):
            with col:
                _task_card(*task, allowed_ids, navigate)

    st.markdown(
        '<div class="v2-section-head"><h2>전체 업무 도구</h2>'
        '<p>핵심 프로그램을 업무 단계에 맞게 분류했습니다.</p></div>',
        unsafe_allow_html=True,
    )
    for category in CATEGORY_ORDER:
        app_ids = _category_apps(definitions, category)
        if not app_ids:
            continue
        description, category_icon = CATEGORY_META[category]
        st.markdown(
            f'<div class="v2-section-head"><h2>{html.escape(category_icon)}&nbsp; {html.escape(category)}</h2>'
            f'<p>{html.escape(description)}</p></div>',
            unsafe_allow_html=True,
        )
        for start in range(0, len(app_ids), 4):
            cols = st.columns(4, gap="medium")
            for col, app_id in zip(cols, app_ids[start:start + 4]):
                with col:
                    _tool_card(app_id, allowed_ids, definitions, icons, navigate)

    st.markdown(
        f"""<div class="v2-status-row">
        <div class="v2-status-card"><b>최근 업데이트</b><span>{html.escape(notice['date'])} · {html.escape(notice['title'])}</span></div>
        <div class="v2-status-card"><b>테스트 자료 사용 안내</b><span>별도 고객 DB는 추가하지 않습니다. 업로드·입력 자료는 서버에서 처리되므로 가상·비식별 자료로 테스트해 주세요.</span></div>
        </div><div class="v2-footer"><span>화랑 WORKSPACE 2.0 · Test Server</span>
        <span>Planned &amp; Built by 박병선 팀장</span></div>""",
        unsafe_allow_html=True,
    )
