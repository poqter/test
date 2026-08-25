"""화랑 WORKSPACE 업무 자료실."""

from __future__ import annotations

import html
from dataclasses import dataclass
import streamlit as st

from modules.ui_components import page_footer, page_header, section_intro, tool_guide


@dataclass(frozen=True)
class LibraryItem:
    title: str
    category: str
    group: str
    summary: str
    keywords: tuple[str, ...]
    url: str
    material_type: str = "노션 자료"
    status: str = "최신 확인"
    related_app: str = ""


ITEMS = (
    LibraryItem("1차 미팅 고객 등록 및 자료 준비", "신입·미팅", "업무 매뉴얼", "고객등록부터 보장분석표와 비교자료 준비까지 순서대로 확인합니다.", ("신입", "고객등록", "보장분석", "보분"), "https://app.notion.com/p/1-1-24e1c9a298c7805f8463d1d7a6c83977", related_app="보장 분석 도우미"),
    LibraryItem("계약 후 필수 진행 매뉴얼", "계약 후 처리", "업무 매뉴얼", "계약완료 알림, 청약속보, 비교안내서 등 후속 절차를 확인합니다.", ("계약 후", "청약속보", "비교안내", "고지의무"), "https://app.notion.com/p/24f1c9a298c78038aee5c1bb05c9a4ff"),
    LibraryItem("이관 DB 활용을 위한 전산 바로알기", "이관 DB", "업무 매뉴얼", "이관고객 조회, 계약관리, 환급금과 감액완납 업무를 정리한 교육자료입니다.", ("이관", "환급금", "감액완납", "세그맵"), "https://app.notion.com/p/1-DB-25a1c9a298c7809fbb78d7cdecb5f844"),
    LibraryItem("보험정보망 이용자 동의", "공통 전산", "전산 매뉴얼", "보험료 산출 전 필요한 보험정보망 이용자 등록 절차입니다.", ("보험정보망", "자동차보험", "이륜차", "동의"), "https://app.notion.com/p/2611c9a298c7800a84ebc56a1f4c03b6"),
    LibraryItem("KB손해보험 가상계좌", "가상계좌", "전산 매뉴얼", "입금대상 조회부터 가상계좌 부여와 SMS 발송까지 확인합니다.", ("KB", "가상계좌", "가계좌", "입금"), "https://app.notion.com/p/KB-25c1c9a298c780cdb45ff21ce6979d04"),
    LibraryItem("DB손해보험 가상계좌", "가상계좌", "전산 매뉴얼", "장기계약조회 후 계속분 입금과 가상계좌 발급 경로를 확인합니다.", ("DB손보", "가상계좌", "가계좌", "계속분"), "https://app.notion.com/p/DB-25c1c9a298c7809a83dbc77d5282a111"),
    LibraryItem("한화손해보험 가상계좌", "가상계좌", "전산 매뉴얼", "계약상세조회에서 가상계좌 발급과 보험료 발송 절차를 확인합니다.", ("한화손보", "가상계좌", "가계좌"), "https://app.notion.com/p/25c1c9a298c7809397f7d3f8dd946d9f"),
    LibraryItem("암·뇌·심장·수술 자료실", "3대 질환·수술", "영업 자료", "질환별 발생률, 보장범위, 담보 변천사와 수술 비교자료를 모았습니다.", ("암", "뇌", "심장", "뇌심", "수술"), "https://app.notion.com/p/1-24e1c9a298c780d88ed9d66287bc1f15", related_app="보장 분석 도우미"),
    LibraryItem("실손·당뇨 자료실", "실손·당뇨", "영업 자료", "실손 세대별 약관과 비교자료, 당뇨 상담자료를 확인합니다.", ("실손", "실비", "당뇨", "약관"), "https://app.notion.com/p/2-24f1c9a298c7800d97fdc5d753069676", related_app="실손보험 세대 비교"),
    LibraryItem("사망·치매·간병·요양 자료실", "사망·간병", "영업 자료", "사망통계와 장기요양·치매·간병 상담자료를 확인합니다.", ("사망", "치매", "간병", "요양", "재가급여"), "https://app.notion.com/p/3-2581c9a298c780c2ba20d1e28947b72f"),
    LibraryItem("태아·치아·운전자 자료실", "태아·치아·운전자", "영업 자료", "태아보험, 치아보험, 운전자보험 상담자료를 확인합니다.", ("태아", "어린이", "치아", "운전자"), "https://app.notion.com/p/4-24f1c9a298c780a8ac32c60c74d800cb"),
    LibraryItem("한화생명 과거상품 가이드 1", "2000~2010년대", "과거상품 가이드", "초기 종신·CI·변액·여성보험의 특징과 상담 포인트를 정리했습니다.", ("대한종신", "CI", "변액", "굿모닝", "여성보험"), "https://app.notion.com/p/2-1-2681c9a298c78087af16d221cd0d9109"),
    LibraryItem("한화생명 과거상품 가이드 2", "GI·종신·암보험", "과거상품 가이드", "GI보험과 종신·암보험의 상품별 특징을 정리했습니다.", ("GI", "어른이보험", "명품암", "통합종신"), "https://app.notion.com/p/3-2-26f1c9a298c78097bbb7de32e16f2b9d"),
    LibraryItem("금소법 이행 확인서", "금소법", "업무 서식", "계약체결 관련 확인서 원본입니다. 사용 전 기준일을 확인하세요.", ("금소법", "이행확인서", "고지의무"), "https://app.notion.com/p/2541c9a298c780ca813ac1f8026c8abe", "PDF", "업데이트 확인 필요"),
    LibraryItem("비교안내확인서 작성 안내", "비교안내", "업무 서식", "비교안내확인서와 고지의무확인서 작성·제출 순서를 확인합니다.", ("비교안내", "상품비교", "고지의무"), "https://app.notion.com/p/2681c9a298c780b7b0a8f3876de3c9c9", status="업데이트 확인 필요"),
    LibraryItem("지난 수수료표", "수수료 보관함", "수수료 자료", "연도와 월별 생·손보 수수료 예시표 및 시상자료를 확인합니다.", ("수수료", "익월수당", "시책", "시상"), "https://app.notion.com/p/2601c9a298c78082bb22c4a81b89214e", related_app="수수료 계산기"),
)

ALIASES = {"보분": "보장분석", "실비": "실손", "가계좌": "가상계좌", "뇌심": "뇌 심장", "익월수당": "수수료"}


def _norm(value: str) -> str:
    value = value.strip().lower().replace("·", " ")
    for source, target in ALIASES.items():
        value = value.replace(source, target)
    return " ".join(value.split())


def search_items(query: str = "", group: str = "전체", category: str = "전체") -> list[LibraryItem]:
    tokens = _norm(query).split()
    found = []
    for item in ITEMS:
        if group != "전체" and item.group != group:
            continue
        if category != "전체" and item.category != category:
            continue
        text = _norm(" ".join((item.title, item.group, item.category, item.summary, *item.keywords)))
        if tokens and not all(token in text for token in tokens):
            continue
        found.append(item)
    return found


def quick_search(query: str, limit: int = 5) -> list[LibraryItem]:
    return search_items(query)[:limit]


def _render_item(item: LibraryItem, index: int) -> None:
    tone = "warn" if "확인 필요" in item.status else "ok"
    with st.container(border=True, key=f"library_item_{index}"):
        st.markdown(f'<div class="wl-head"><div><div class="wl-meta">{html.escape(item.group)} · {html.escape(item.category)}</div><div class="wl-title">{html.escape(item.title)}</div></div><span class="wl-status wl-{tone}">{html.escape(item.status)}</span></div><div class="wl-summary">{html.escape(item.summary)}</div><div class="wl-foot">{html.escape(item.material_type)} · 최종 확인 2026.08.25</div>', unsafe_allow_html=True)
        cols = st.columns([1.5, 1] if item.related_app else [1])
        with cols[0]:
            st.link_button("노션 원본 열기  ↗", item.url, use_container_width=True)
        if item.related_app:
            with cols[1]:
                st.caption(f"관련 기능 · {item.related_app}")


def run() -> None:
    page_header("업무 지원", "업무 자료실", "업무 절차·전산 매뉴얼·영업 자료를 한곳에서 검색합니다.", "▤")
    st.markdown("""<style>.wl-note{margin:.15rem 0 1rem;color:#607789;font-size:.82rem}.wl-head{display:flex;justify-content:space-between;gap:1rem}.wl-meta{color:#1769DC;font-size:.68rem;font-weight:800}.wl-title{margin:.25rem 0;color:#132F45;font-size:1rem;font-weight:800}.wl-summary{margin:.55rem 0;color:#617689;font-size:.82rem}.wl-foot{color:#8494A2;font-size:.68rem}.wl-status{padding:.28rem .52rem;border-radius:999px;font-size:.64rem;font-weight:800}.wl-ok{background:#EAF7F3;color:#087B67}.wl-warn{background:#FFF4DE;color:#9A6500}</style>""", unsafe_allow_html=True)
    tool_guide("업무 자료실 사용 방법", "업무명·보험회사·전문 용어로 필요한 자료를 찾을 수 있습니다.", [("검색", "필요한 업무나 전문 용어를 입력합니다."), ("분류", "자료 유형과 세부 카테고리로 좁힙니다."), ("확인", "최신 확인일을 본 뒤 노션 원본을 엽니다.")], caution="- 최신성이 중요한 자료는 `업데이트 확인 필요` 표시를 확인하세요.\n- 접속 아이디·비밀번호는 제공하지 않습니다.")
    section_intro("SEARCH", "필요한 자료 찾기", "줄임말과 전문 용어를 함께 검색할 수 있습니다.")
    query = st.text_input("통합검색", placeholder="예: KB 가상계좌, CI보험 상담, 계약 후 처리", label_visibility="collapsed", key="work_library_query")
    cols = st.columns(2)
    groups = ["전체", "업무 매뉴얼", "전산 매뉴얼", "영업 자료", "과거상품 가이드", "업무 서식", "수수료 자료"]
    with cols[0]:
        group = st.selectbox("자료 유형", groups, key="work_library_group")
    categories = ["전체"] + sorted({item.category for item in ITEMS if group == "전체" or item.group == group})
    with cols[1]:
        category = st.selectbox("세부 카테고리", categories, key="work_library_category")
    results = search_items(query, group, category)
    st.markdown(f'<div class="wl-note">검색 결과 <b>{len(results)}건</b> · 노션 자료는 새 탭에서 열립니다.</div>', unsafe_allow_html=True)
    if not results:
        st.info("일치하는 자료가 없습니다. 보험회사명이나 더 짧은 업무 용어로 다시 검색해 주세요.")
    for index, item in enumerate(results):
        _render_item(item, index)
    page_footer("업무 자료실", "1.0.0", "2026.08.25")
